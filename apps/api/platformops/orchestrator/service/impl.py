from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...catalog import (
    get_service_contract,
    rendered_contract,
    required_dependencies,
    service_catalog,
)
from ...jobs import create_job, finish_job
from ...models import (
    DeploymentJob,
    DeploymentPlanRecord,
    JobStatus,
    Node,
    ServiceInstance,
)
from ...settings import settings
from ...tasks import run_job_async
from ..common import (
    RUNNING_STATUSES,
    _ansible_base_command,
    _service_contract_for_node,
    _service_display_name,
    record_event,
)


def create_service_instance(
    db: Session,
    *,
    node: Node,
    service_key: str,
    name: str | None = None,
    contract_overrides: dict[str, Any] | None = None,
) -> ServiceInstance:
    from ..ids import allocate_service_external_id

    # Normalize cPlatform aliases
    key = service_key
    alias_map = {
        "AIOrchestrator": "ai-orchestrator",
        "cplatform": "ai-orchestrator",
        "TrainingServer": "dtrain-controller",
        "dTrain": "dtrain-controller",
    }
    key = alias_map.get(key, key)

    contract = _service_contract_for_node(
        key,
        node_id=node.id,
        volume_root=node.volume_root,
        overrides=contract_overrides,
    )
    if not contract:
        # Soft contract for AIOrchestrator / dForm-only types not yet in services.yaml
        if key in {"ai-orchestrator"} or service_key in alias_map:
            contract = {
                "display_name": name or "AIOrchestrator",
                "name": "AIOrchestrator",
                "kind": "app",
                "container_name": f"node-{node.id}-ai-orchestrator",
                "image": "",
                "service_key": "ai-orchestrator",
            }
        else:
            raise ValueError(f"Unknown service key: {service_key}")

    existing = db.scalar(
        select(ServiceInstance).where(ServiceInstance.node_id == node.id, ServiceInstance.service_key == key)
    )
    if existing:
        if not existing.external_id:
            existing.external_id = allocate_service_external_id(db)
            db.commit()
            db.refresh(existing)
        return existing

    merged = dict(contract)
    if contract_overrides:
        merged.update(contract_overrides)
    install_mode = str(merged.get("install_mode") or merged.get("service_install") or "ansible").lower()
    if install_mode in {"manual", "ansible"}:
        merged["install_mode"] = install_mode

    external_id = allocate_service_external_id(db)
    status = "registered" if install_mode == "manual" else "created"

    service = ServiceInstance(
        external_id=external_id,
        node_id=node.id,
        service_key=key,
        name=name or contract.get("display_name") or contract.get("name") or key,
        kind=contract.get("kind", "app"),
        container_name=contract.get("container_name", f"node-{node.id}-{key}"),
        image=contract.get("image", ""),
        status=status,
        config_json=json.dumps(merged),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    record_event(
        db,
        category="catalog",
        level="info",
        message=f"Registered service card {service.name} ({service.external_id})",
        service_id=service.id,
        node_id=node.id,
        metadata={
            "service_key": service.service_key,
            "kind": service.kind,
            "external_id": service.external_id,
            "install_mode": install_mode,
            "overrides": contract_overrides or {},
        },
    )
    return service


def update_service_instance(
    db: Session,
    service: ServiceInstance,
    *,
    name: str | None = None,
    contract_overrides: dict[str, Any] | None = None,
) -> ServiceInstance:
    merged_contract = _service_contract_for_node(
        service.service_key,
        node_id=service.node_id,
        volume_root=service.node.volume_root,
        overrides=contract_overrides,
    )
    if not merged_contract:
        raise ValueError(f"Unknown service key: {service.service_key}")
    service.name = (
        (name or "").strip()
        or merged_contract.get("display_name")
        or merged_contract.get("name")
        or service.service_key
    )
    service.kind = merged_contract.get("kind", service.kind)
    service.container_name = merged_contract.get("container_name", service.container_name)
    service.image = merged_contract.get("image", service.image)
    service.config_json = json.dumps(merged_contract)
    db.commit()
    db.refresh(service)
    record_event(
        db,
        category="catalog",
        level="info",
        message=f"Updated service card {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"service_key": service.service_key, "overrides": contract_overrides or {}},
    )
    return service


def _flatten_contract_fields(
    value: Any,
    *,
    prefix: str = "",
) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        flattened: list[tuple[str, Any]] = []
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.extend(_flatten_contract_fields(item, prefix=next_prefix))
        return flattened
    return [(prefix, value)]


def service_install_schema(
    db: Session,
    *,
    service_key: str,
    node: Node,
    service: ServiceInstance | None = None,
) -> dict[str, Any]:
    from ..dform import dform_install_schema_for_key, list_dform_service_types, resolve_dform_type

    # Allow dForm-only types (e.g. AIOrchestrator) even if not yet in services.yaml
    in_catalog = service_key in service_catalog()
    dform_type = resolve_dform_type(service_key)
    if not in_catalog and not dform_type:
        raise ValueError(f"Unknown service key: {service_key}")

    contract = {}
    if service:
        try:
            contract = json.loads(service.config_json or "{}")
        except Exception:
            contract = {}
    elif in_catalog:
        contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root) or {}
    contract_defaults = copy.deepcopy(contract)

    # Prefer full dForm field set when available
    dform_pack = dform_install_schema_for_key(service_key)
    if dform_pack and dform_pack.get("fields"):
        fields = list(dform_pack["fields"])
        # Overlay current service values when editing
        if service:
            cfg = contract if isinstance(contract, dict) else {}
            for field in fields:
                key = field.get("key")
                if key == "service_name" and service.name:
                    field["value"] = service.name
                elif key in cfg:
                    field["value"] = cfg.get(key)
                elif key == "name" and service.name:
                    field["value"] = service.name
        # Ensure install_mode is always present
        if not any(f.get("key") in {"service_install", "install_mode"} for f in fields):
            fields.insert(
                0,
                {
                    "key": "install_mode",
                    "label": "Install mode",
                    "field_type": "select",
                    "required": True,
                    "value": "ANSIBLE",
                    "options": ["MANUAL", "ANSIBLE"],
                    "section": "Install",
                    "schema_source": "dform",
                },
            )
        # Shape must match ServiceInstallSchemaOut (response_model)
        clean_fields: list[dict[str, Any]] = []
        for field in fields:
            clean_fields.append(
                {
                    "key": str(field.get("key") or ""),
                    "label": str(field.get("label") or field.get("key") or ""),
                    "field_type": str(field.get("field_type") or "text"),
                    "required": bool(field.get("required")),
                    "value": field.get("value"),
                    "help_text": str(field.get("help_text") or ""),
                    "options": [str(o) for o in (field.get("options") or [])],
                    "section": str(field.get("section") or "Service parameters"),
                }
            )
        display_name = (
            (service.name if service else None)
            or contract.get("display_name")
            or contract.get("name")
            or dform_pack.get("dform_type")
            or service_key
        )
        return {
            "service_key": service_key,
            "name": display_name,
            "kind": contract.get("kind") or ("app" if service_key == "ai-orchestrator" else "app"),
            "configurable": True,
            "exposure_supported": bool(contract.get("kind") == "infrastructure"),
            "fields": clean_fields,
            "defaults": contract_defaults if isinstance(contract_defaults, dict) else {},
            "summary": f"dForm schema ({dform_pack.get('dform_type')}) · {len(clean_fields)} fields",
        }

    fields: list[dict[str, Any]] = [
        {
            "key": "name",
            "label": "Service name",
            "field_type": "text",
            "required": False,
            "value": service.name if service else "",
            "help_text": "Used as the service display and runtime name. Must remain unique within the cluster.",
            "section": "Identity",
        },
        {
            "key": "install_mode",
            "label": "Install mode",
            "field_type": "select",
            "required": True,
            "value": "ansible",
            "options": ["manual", "ansible"],
            "section": "Install",
            "schema_source": "catalog",
        },
    ]
    fields.append(
        {
            "key": "service_version",
            "label": "Service version",
            "field_type": "select",
            "required": False,
            "value": "local",
            "help_text": "PlatformOps currently tracks the active contract/image version for this card.",
            "options": ["local"],
            "section": "Version",
        }
    )

    environment = contract.get("environment", {})
    for env_key, env_value in environment.items():
        fields.append(
            {
                "key": f"environment.{env_key}",
                "label": env_key,
                "field_type": "text",
                "required": False,
                "value": env_value,
                "help_text": "Environment override saved into the service card contract.",
                "section": "Environment",
            }
        )

    list_sections = [
        ("ports", "Published ports", "Ports"),
        ("volumes", "Volume mounts", "Volumes"),
        ("config_files", "Config files", "Config"),
        ("log_paths", "Log paths", "Logs"),
    ]
    for key, label, section in list_sections:
        items = contract.get(key, [])
        fields.append(
            {
                "key": key,
                "label": label,
                "field_type": "list",
                "required": False,
                "value": items,
                "help_text": f"One entry per line for {label.lower()}.",
                "section": section,
            }
        )

    if contract.get("command"):
        fields.append(
            {
                "key": "command",
                "label": "Container command",
                "field_type": "text",
                "required": False,
                "value": contract.get("command", ""),
                "help_text": "Override the runtime command when needed.",
                "section": "Runtime",
            }
        )
    if (contract.get("healthcheck") or {}).get("command"):
        fields.append(
            {
                "key": "healthcheck.command",
                "label": "Health check command",
                "field_type": "text",
                "required": False,
                "value": (contract.get("healthcheck") or {}).get("command", ""),
                "help_text": "Operator-visible health command for this card.",
                "section": "Runtime",
            }
        )

    exposure_supported = contract.get("kind") == "infrastructure"
    if exposure_supported:
        fields.append(
            {
                "key": "expose_service",
                "label": "Expose service",
                "field_type": "boolean",
                "required": False,
                "value": bool(contract.get("expose_service", False)),
                "help_text": "Infrastructure cards stay internal-only unless explicitly exposed.",
                "section": "Network",
            }
        )
        fields.append(
            {
                "key": "host_port",
                "label": "Host port",
                "field_type": "number",
                "required": False,
                "value": contract.get("host_port", ""),
                "help_text": "Only used when expose service is enabled.",
                "section": "Network",
            }
        )

    return {
        "service_key": service_key,
        "name": contract.get("display_name") or contract.get("name") or service_key,
        "kind": contract.get("kind", "app"),
        "configurable": bool(contract.get("config_files") or environment or contract.get("command")),
        "exposure_supported": exposure_supported,
        "fields": fields,
        "defaults": contract_defaults,
    }


def dependency_preflight(db: Session, service: ServiceInstance) -> dict[str, Any]:
    required = required_dependencies(service.service_key)
    missing: list[str] = []
    stopped: list[str] = []

    for dependency_key in required:
        dependency = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == service.node_id,
                ServiceInstance.service_key == dependency_key,
            )
        )
        if dependency is None:
            missing.append(dependency_key)
        elif dependency.status not in RUNNING_STATUSES:
            stopped.append(dependency_key)

    ok = not missing and not stopped
    names = [_service_display_name(item) for item in missing + stopped]
    return {
        "ok": ok,
        "required": required,
        "missing": missing,
        "stopped": stopped,
        "message": "All dependencies are ready."
        if ok
        else f"Install or start these infrastructure cards first: {', '.join(names)}.",
    }


def deploy_service(db: Session, service: ServiceInstance) -> DeploymentJob:
    preflight = dependency_preflight(db, service)
    if not preflight["ok"]:
        job = create_job(
            db,
            action="deploy-blocked",
            command="dependency-preflight",
            service_id=service.id,
            node_id=service.node_id,
        )
        record_event(
            db,
            category="deployment",
            level="warning",
            message=f"Deployment blocked for {service.name}: {preflight['message']}",
            service_id=service.id,
            node_id=service.node_id,
            metadata=preflight,
        )
        return finish_job(db, job, ok=False, error=preflight["message"])

    node = service.node
    contract = json.loads(service.config_json or "{}")
    extra_vars = {
        "service_key": service.service_key,
        "service_name": service.name,
        "container_name": service.container_name,
        "image": service.image,
        "docker_network": node.docker_network,
        "volume_root": node.volume_root,
        "contract": contract,
    }
    vars_path = write_job_vars("deploy", service.id, extra_vars)
    command = f"{_ansible_base_command(node, 'docker_service.yml')} --extra-vars @{vars_path}"
    job = create_job(db, action="deploy", command=command, service_id=service.id, node_id=node.id)

    if settings.local_mode:
        return finish_job(
            db,
            job,
            ok=False,
            error=(
                "Deploy requires a real Ansible target. "
                "Set PLATFORMOPS_LOCAL_MODE=false and configure SSH inventory for the node."
            ),
        )

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_service = bg_db.get(ServiceInstance, service.id)
        if bg_service:
            bg_service.status = "running" if ok else "error"
            record_event(
                bg_db,
                category="deployment",
                level="info" if ok else "error",
                message=f"Deploy finished for {bg_service.name} with status {bg_service.status}",
                service_id=bg_service.id,
                node_id=bg_service.node_id,
                metadata={"job_id": bg_job.id},
            )

    return run_job_async(db, job, cwd=settings.project_root, timeout_seconds=300, on_complete=on_complete)


def _deployment_command_preview(node: Node, service: ServiceInstance | None, service_key: str) -> str:
    contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
    preview_service = service
    if preview_service is None:
        preview_service = ServiceInstance(
            node_id=node.id,
            service_key=service_key,
            name=contract.get("display_name") or contract.get("name") or service_key,
            kind=contract.get("kind", "app"),
            container_name=contract.get("container_name", f"node-{node.id}-{service_key}"),
            image=contract.get("image", ""),
            config_json=json.dumps(contract),
        )
    extra_vars = {
        "service_key": preview_service.service_key,
        "service_name": preview_service.name,
        "container_name": preview_service.container_name,
        "image": preview_service.image,
        "docker_network": node.docker_network,
        "volume_root": node.volume_root,
        "contract": contract,
    }
    vars_path = write_job_vars("plan-preview", preview_service.id or 0, extra_vars)
    return f"{_ansible_base_command(node, 'docker_service.yml')} --extra-vars @{vars_path}"


def delete_service(db: Session, service: ServiceInstance) -> DeploymentJob:
    node = service.node
    vars_path = write_job_vars(
        "delete",
        service.id,
        {
            "container_name": service.container_name,
            "service_name": service.name,
            "remove": True,
        },
    )
    command = f"{_ansible_base_command(node, 'docker_service.yml')} --extra-vars @{vars_path}"
    job = create_job(db, action="delete", command=command, service_id=service.id, node_id=node.id)

    if settings.local_mode:
        return finish_job(
            db,
            job,
            ok=False,
            error=(
                "Service delete requires a real Ansible target. "
                "Set PLATFORMOPS_LOCAL_MODE=false and configure SSH inventory for the node."
            ),
        )

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_service = bg_db.get(ServiceInstance, service.id)
        if bg_service:
            bg_service.status = "deleted" if ok else "error"
            record_event(
                bg_db,
                category="lifecycle",
                level="info" if ok else "error",
                message=f"Delete finished for {bg_service.name} with status {bg_service.status}",
                service_id=bg_service.id,
                node_id=bg_service.node_id,
                metadata={"job_id": bg_job.id},
            )

    return run_job_async(db, job, cwd=settings.project_root, timeout_seconds=180, on_complete=on_complete)


def install_missing_dependencies(db: Session, service: ServiceInstance) -> dict[str, Any]:
    ordered_keys: list[str] = []
    for key in _dependency_order(service.service_key):
        if key not in ordered_keys:
            ordered_keys.append(key)

    actions: list[dict[str, Any]] = []
    for dependency_key in ordered_keys:
        dependency = _service_by_key(db, service.node_id, dependency_key)
        if dependency is None:
            dependency = create_service_instance(db, node=service.node, service_key=dependency_key)
        if dependency.status in RUNNING_STATUSES:
            continue
        dependency_job = deploy_service(db, dependency)
        actions.append(
            {
                "service_id": dependency.id,
                "service_key": dependency.service_key,
                "action": "deploy",
                "job_id": dependency_job.id,
                "job_status": dependency_job.status,
                "command": dependency_job.command,
                "message": f"{dependency.name} deployment {dependency_job.status}",
            }
        )

    if not settings.local_mode and actions:
        import time

        for action in actions:
            job_id = action["job_id"]
            for _ in range(200):
                db.expire_all()
                dep_job = db.get(DeploymentJob, job_id)
                if dep_job and dep_job.status in {JobStatus.success.value, JobStatus.failed.value}:
                    break
                time.sleep(0.05)

    preflight = dependency_preflight(db, service)
    summary = (
        "All required dependencies are now running."
        if preflight["ok"]
        else "Some dependencies still need attention after install attempt."
    )
    record_event(
        db,
        category="deployment",
        level="info" if preflight["ok"] else "warning",
        message=f"Dependency install attempt completed for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={
            "target_service_key": service.service_key,
            "actions": len(actions),
            "preflight_ok": preflight["ok"],
            "remaining_missing": preflight["missing"],
            "remaining_stopped": preflight["stopped"],
        },
    )
    return {
        "service_id": service.id,
        "service_key": service.service_key,
        "node_id": service.node_id,
        "dependency_actions": actions,
        "preflight": preflight,
        "summary": summary,
    }


def _service_by_key(db: Session, node_id: int, service_key: str) -> ServiceInstance | None:
    return db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id == node_id,
            ServiceInstance.service_key == service_key,
        )
    )


def _dependency_order(service_key: str, seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    ordered: list[str] = []
    for dependency_key in required_dependencies(service_key):
        if dependency_key in seen:
            continue
        seen.add(dependency_key)
        ordered.extend(_dependency_order(dependency_key, seen))
        ordered.append(dependency_key)
    return ordered


def deployment_plan(db: Session, node: Node, service_key: str) -> dict[str, Any]:
    if service_key not in service_catalog():
        raise ValueError(f"Unknown service key: {service_key}")

    ordered_keys: list[str] = []
    for key in [*_dependency_order(service_key), service_key]:
        if key not in ordered_keys:
            ordered_keys.append(key)

    steps: list[dict[str, Any]] = []
    blocked_by: list[str] = []
    for index, key in enumerate(ordered_keys, start=1):
        service = _service_by_key(db, node.id, key)
        contract = rendered_contract(key, node_id=node.id, volume_root=node.volume_root)
        status = service.status if service else "missing"
        action = "skip"
        if service is None:
            action = "create-and-deploy"
            blocked_by.append(key)
        elif status not in RUNNING_STATUSES:
            action = "deploy"
            blocked_by.append(key)
        steps.append(
            {
                "order": index,
                "service_key": key,
                "name": contract.get("display_name") or key,
                "kind": contract.get("kind", "app"),
                "subsystem": contract.get("subsystem", "uncategorized"),
                "container_name": contract.get("container_name"),
                "status": status,
                "action": action,
                "dependencies": required_dependencies(key),
                "depends_on": required_dependencies(key),
                "ansible_command": _deployment_command_preview(node, service, key),
            }
        )

    target = _service_by_key(db, node.id, service_key)
    preflight = dependency_preflight(db, target) if target else {"ok": False}
    ok = bool(target and preflight["ok"] and target.status in RUNNING_STATUSES)
    summary = (
        "Target and dependencies are already running."
        if ok
        else "Plan includes missing or stopped cards before target deploy."
    )
    plan = {
        "node_id": node.id,
        "service_key": service_key,
        "ok": ok,
        "summary": summary,
        "steps": steps,
        "blocked_by": blocked_by,
    }
    record = DeploymentPlanRecord(
        node_id=node.id,
        service_key=service_key,
        status="ready" if not blocked_by else "requires-action",
        plan_json=json.dumps(plan),
    )
    db.add(record)
    db.commit()
    record_event(
        db,
        category="planning",
        level="info" if not blocked_by else "warning",
        message=f"Generated deployment plan for {_service_display_name(service_key)}",
        node_id=node.id,
        metadata={"service_key": service_key, "blocked_by": blocked_by},
    )
    return plan


def execute_deployment_plan(
    db: Session,
    service: ServiceInstance,
    *,
    auto_install_dependencies: bool = True,
) -> dict[str, Any]:
    plan = deployment_plan(db, service.node, service.service_key)
    preflight_before = dependency_preflight(db, service)
    dependency_actions: list[dict[str, Any]] = []
    if not preflight_before["ok"] and auto_install_dependencies:
        dependency_result = install_missing_dependencies(db, service)
        dependency_actions = dependency_result["dependency_actions"]
    preflight_after = dependency_preflight(db, service)
    target_job: DeploymentJob | None = None
    ok = False
    summary = "Deployment plan execution blocked."
    if preflight_after["ok"]:
        target_job = deploy_service(db, service)
        ok = target_job.status == JobStatus.success.value
        summary = (
            f"Executed deployment plan for {service.name}."
            if ok
            else f"Deployment plan executed for {service.name}, but target deploy finished with status {target_job.status}."
        )
    else:
        summary = (
            "Dependencies still require attention before the main service can be deployed."
            if auto_install_dependencies
            else "Deployment plan reviewed. Dependencies must be installed before executing the main service deploy."
        )
    record_event(
        db,
        category="deployment",
        level="info" if ok else "warning",
        message=f"Deployment plan execution for {service.name}: {summary}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={
            "service_key": service.service_key,
            "auto_install_dependencies": auto_install_dependencies,
            "dependency_actions": len(dependency_actions),
            "preflight_before_ok": preflight_before["ok"],
            "preflight_after_ok": preflight_after["ok"],
            "target_job_id": target_job.id if target_job else None,
        },
    )
    return {
        "service_id": service.id,
        "service_key": service.service_key,
        "node_id": service.node_id,
        "auto_install_dependencies": auto_install_dependencies,
        "ok": ok,
        "summary": summary,
        "plan": plan,
        "preflight_before": preflight_before,
        "preflight_after": preflight_after,
        "dependency_actions": dependency_actions,
        "target_job": target_job,
    }


def topology(db: Session) -> dict[str, Any]:
    nodes = list(db.scalars(select(Node).order_by(Node.name)).all())
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.name)).all())
    service_cards: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    subsystems: dict[str, list[str]] = {}

    for service in services:
        contract = json.loads(service.config_json or "{}")
        subsystem = contract.get("subsystem", "uncategorized")
        service_cards.append(
            {
                "id": service.id,
                "node_id": service.node_id,
                "service_key": service.service_key,
                "name": service.name,
                "kind": service.kind,
                "status": service.status,
                "container_name": service.container_name,
                "subsystem": subsystem,
                "tags": contract.get("tags", []),
            }
        )
        subsystems.setdefault(subsystem, []).append(service.service_key)
        for dependency_key in required_dependencies(service.service_key):
            dependency = next(
                (
                    candidate
                    for candidate in services
                    if candidate.node_id == service.node_id and candidate.service_key == dependency_key
                ),
                None,
            )
            edges.append(
                {
                    "from": dependency.id if dependency else None,
                    "from_key": dependency_key,
                    "to": service.id,
                    "to_key": service.service_key,
                    "status": "ready" if dependency and dependency.status in RUNNING_STATUSES else "blocked",
                }
            )

    return {
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "host": node.host,
                "status": node.status,
                "environment": node.environment,
                "docker_network": node.docker_network,
            }
            for node in nodes
        ],
        "services": service_cards,
        "edges": edges,
        "subsystems": subsystems,
    }


def generate_inventory(node: Node) -> str:
    if node.environment == "local":
        return "[platformops]\nlocalhost ansible_connection=local\n"

    key_part = f" ansible_ssh_private_key_file={node.ssh_key_path}" if node.ssh_key_path else ""
    return (
        "[platformops]\n"
        f"{node.name} ansible_host={node.host} ansible_user={node.ssh_user}{key_part}\n\n"
        "[platformops:vars]\n"
        f"platformops_volume_root={node.volume_root}\n"
        f"platformops_docker_network={node.docker_network}\n"
    )


def generate_compose(db: Session, node: Node) -> str:
    compose: dict[str, Any] = {
        "name": f"platformops-node-{node.id}",
        "networks": {node.docker_network: {"name": node.docker_network}},
        "services": {},
    }
    services = list(
        db.scalars(
            select(ServiceInstance)
            .where(ServiceInstance.node_id == node.id, ServiceInstance.status != "deleted")
            .order_by(ServiceInstance.kind, ServiceInstance.service_key)
        ).all()
    )
    for service in services:
        contract = json.loads(service.config_json or "{}")
        service_name = service.service_key.replace("_", "-")
        payload: dict[str, Any] = {
            "image": service.image,
            "container_name": service.container_name,
            "restart": "unless-stopped",
            "networks": [node.docker_network],
        }
        if contract.get("command"):
            payload["command"] = contract["command"]
        if contract.get("environment"):
            payload["environment"] = contract["environment"]
        if contract.get("ports"):
            payload["ports"] = contract["ports"]
        if contract.get("volumes"):
            payload["volumes"] = contract["volumes"]
        dependencies = [
            dependency
            for dependency in required_dependencies(service.service_key)
            if _service_by_key(db, node.id, dependency)
        ]
        if dependencies:
            payload["depends_on"] = [dependency.replace("_", "-") for dependency in dependencies]
        compose["services"][service_name] = payload
    return yaml.safe_dump(compose, sort_keys=False)


def placement_recommendations(
    db: Session,
    *,
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: list[int] | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
) -> dict[str, Any]:
    from ..reports import _project_node_capacity

    if service_key not in service_catalog():
        raise ValueError(f"Unknown service key: {service_key}")

    contract = get_service_contract(service_key)
    target_kind = contract.get("kind", "app")
    target_subsystem = contract.get("subsystem", "uncategorized")
    required = required_dependencies(service_key)
    now = datetime.utcnow().isoformat() + "Z"
    candidates: list[dict[str, Any]] = []
    avoid_set = set(avoid_node_ids or [])

    nodes = list(db.scalars(select(Node).order_by(Node.created_at.asc())).all())
    for node in nodes:
        existing = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == node.id,
                ServiceInstance.service_key == service_key,
            )
        )
        missing: list[str] = []
        stopped: list[str] = []
        for dep_key in required:
            dep = db.scalar(
                select(ServiceInstance).where(
                    ServiceInstance.node_id == node.id,
                    ServiceInstance.service_key == dep_key,
                )
            )
            if dep is None:
                missing.append(dep_key)
            elif dep.status not in RUNNING_STATUSES:
                stopped.append(dep_key)

        capacity = _project_node_capacity(db, node, target_kind)
        score = 100
        notes: list[str] = []
        recommendation = "recommended"
        ineligible = False
        subsystem_running_count = 0
        for service in db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all():
            if service.status in RUNNING_STATUSES:
                service_contract = get_service_contract(service.service_key)
                if service_contract.get("subsystem", "uncategorized") == target_subsystem:
                    subsystem_running_count += 1

        if node.status not in {"healthy", "running"}:
            score -= 20
            notes.append(f"Node status is {node.status}.")
            if require_healthy:
                ineligible = True
                recommendation = "ineligible"
                notes.append("Healthy-node-only policy enabled.")
        if missing:
            score -= len(missing) * 15
            notes.append(f"Missing dependencies: {', '.join(missing)}")
            recommendation = "needs-dependencies"
        if stopped:
            score -= len(stopped) * 10
            notes.append(f"Stopped dependencies: {', '.join(stopped)}")
            recommendation = "needs-dependencies"
        if capacity["capacity_status"] == "risk":
            score -= 25
            notes.append("Projected capacity crosses risk threshold.")
            recommendation = "capacity-risk"
        if prefer_node_id is not None and node.id == prefer_node_id:
            score += 15
            notes.append("Preferred node boost applied.")
        if node.id in avoid_set:
            score -= 40
            recommendation = "avoided"
            notes.append("Avoid-node policy penalty applied.")
        if anti_affinity_service_key:
            anti_service = db.scalar(
                select(ServiceInstance).where(
                    ServiceInstance.node_id == node.id,
                    ServiceInstance.service_key == anti_affinity_service_key,
                    ServiceInstance.status.in_(RUNNING_STATUSES),
                )
            )
            if anti_service is not None:
                score -= 30
                recommendation = "anti-affinity-hit"
                notes.append(f"Anti-affinity hit: {anti_affinity_service_key} already running on this node.")
        if spread_subsystem and subsystem_running_count >= 3:
            score -= 20
            recommendation = "subsystem-dense"
            notes.append(f"Subsystem spread penalty: {subsystem_running_count} running services in {target_subsystem}.")
        if existing and existing.status in RUNNING_STATUSES:
            score -= 80
            notes.append("Service already running on this node.")
            recommendation = "already-installed"
        elif existing:
            notes.append(f"Service exists with status {existing.status}; deploy can recover it.")

        if not notes:
            notes.append("Dependencies and projected capacity look healthy.")
        if ineligible:
            score = 0
            notes.append("Node marked ineligible by policy.")
        score = max(0, min(100, score))
        candidates.append(
            {
                "node_id": node.id,
                "node_name": node.name,
                "node_status": node.status,
                "score": score,
                "recommendation": recommendation,
                "dependency_ready": not missing and not stopped,
                "dependency_missing": missing,
                "dependency_stopped": stopped,
                "capacity_status": capacity["capacity_status"],
                "projected_memory_mb": capacity["projected_memory_mb"],
                "projected_storage_gb": capacity["projected_storage_gb"],
                "projected_cpu": capacity["projected_cpu"],
                "notes": notes,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {
        "service_key": service_key,
        "generated_at": now,
        "prefer_node_id": prefer_node_id,
        "avoid_node_ids": sorted(avoid_set),
        "anti_affinity_service_key": anti_affinity_service_key,
        "require_healthy": require_healthy,
        "spread_subsystem": spread_subsystem,
        "candidates": candidates,
    }


def bootstrap_observability_plane(db: Session, node_id: int) -> dict[str, Any]:
    from ..reports import observability_pipeline_report

    result = deploy_subsystem(db, node_id, "observability-plane")
    pipeline = observability_pipeline_report(db)
    node_report = next((item for item in pipeline["nodes"] if item["node_id"] == node_id), None)
    return {
        "node_id": node_id,
        "subsystem": "observability-plane",
        "ok": result["ok"],
        "summary": result["summary"],
        "jobs": result["jobs"],
        "pipeline_ready": node_report["pipeline_ready"] if node_report else False,
        "ingestion_state": node_report["ingestion_state"] if node_report else "unknown",
    }


def placement_auto_deploy(
    db: Session,
    *,
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: list[int] | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
    auto_install_dependencies: bool = True,
    allow_capacity_risk: bool = False,
) -> dict[str, Any]:
    recommendation = placement_recommendations(
        db,
        service_key=service_key,
        prefer_node_id=prefer_node_id,
        avoid_node_ids=avoid_node_ids,
        anti_affinity_service_key=anti_affinity_service_key,
        require_healthy=require_healthy,
        spread_subsystem=spread_subsystem,
    )
    candidates = recommendation["candidates"]
    selected = None
    for candidate in candidates:
        if candidate["recommendation"] in {"ineligible", "already-installed"}:
            continue
        if not allow_capacity_risk and candidate["capacity_status"] == "risk":
            continue
        selected = candidate
        break
    if selected is None and candidates:
        selected = candidates[0]
    if selected is None:
        raise ValueError(f"No placement candidates found for {service_key}")

    node = db.get(Node, selected["node_id"])
    if node is None:
        raise ValueError(f"Selected node {selected['node_id']} was not found")
    target = create_service_instance(db, node=node, service_key=service_key)
    created_target = target.status == "created"
    preflight = dependency_preflight(db, target)
    dependency_actions: list[dict[str, Any]] = []

    if not preflight["ok"] and auto_install_dependencies:
        for dependency_key in [*preflight["missing"], *preflight["stopped"]]:
            dependency = create_service_instance(db, node=node, service_key=dependency_key)
            if dependency.status in RUNNING_STATUSES:
                continue
            dependency_job = deploy_service(db, dependency)
            dependency_actions.append(
                {
                    "service_id": dependency.id,
                    "service_key": dependency.service_key,
                    "action": "deploy",
                    "job_id": dependency_job.id,
                    "job_status": dependency_job.status,
                    "command": dependency_job.command,
                    "message": f"{dependency.name} deployment {dependency_job.status}",
                }
            )
        preflight = dependency_preflight(db, target)

    if not preflight["ok"]:
        names = ", ".join([_service_display_name(item) for item in [*preflight["missing"], *preflight["stopped"]]])
        raise ValueError(f"Placement auto-deploy blocked. Missing/stopped dependencies: {names}")

    job = deploy_service(db, target)
    record_event(
        db,
        category="planning",
        level="info" if job.status == JobStatus.success.value else "warning",
        message=f"Placement auto-deploy executed for {_service_display_name(service_key)} on {node.name}",
        service_id=target.id,
        node_id=node.id,
        metadata={
            "service_key": service_key,
            "candidate_score": selected["score"],
            "dependency_actions": len(dependency_actions),
            "job_id": job.id,
        },
    )
    return {
        "service_key": service_key,
        "node_id": node.id,
        "node_name": node.name,
        "generated_at": recommendation["generated_at"],
        "selected_candidate": selected,
        "auto_install_dependencies": auto_install_dependencies,
        "allow_capacity_risk": allow_capacity_risk,
        "created_target": created_target,
        "target_service_id": target.id,
        "target_service_status": target.status,
        "target_job_id": job.id,
        "target_job_status": job.status,
        "dependency_actions": dependency_actions,
        "preflight": preflight,
        "summary": f"Placed {service_key} on {node.name} with {len(dependency_actions)} dependency actions.",
    }


def write_job_vars(prefix: str, entity_id: int, values: dict[str, Any]) -> Path:
    job_dir = settings.resolve(settings.runtime_dir) / "job-vars"
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"{prefix}-{entity_id}-{int(datetime.utcnow().timestamp())}.yml"
    path.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    return path


def catalog_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for key, contract in service_catalog().items():
        cards.append(
            {
                "service_key": key,
                "name": contract.get("display_name") or contract.get("name") or key,
                "kind": contract.get("kind", "app"),
                "image": contract.get("image", ""),
                "description": contract.get("description", ""),
                "dependencies": required_dependencies(key),
                "configurable": bool(contract.get("config_files")),
                "log_paths": contract.get("log_paths", []),
                "subsystem": contract.get("subsystem", "uncategorized"),
                "tags": contract.get("tags", []),
                "ports": contract.get("ports", []),
                "volumes": contract.get("volumes", []),
                "config_files": contract.get("config_files", []),
                "env": contract.get("environment") or {},
                "command": contract.get("command", ""),
                "health_command": (contract.get("healthcheck") or {}).get("command", ""),
            }
        )
    return cards


def topological_sort(keys: set[str]) -> list[str]:
    visited = {}
    result = []

    def visit(k: str):
        if visited.get(k) == "visiting":
            return
        if visited.get(k) == "visited":
            return
        visited[k] = "visiting"
        deps = required_dependencies(k)
        for dep in deps:
            if dep in keys:
                visit(dep)
        visited[k] = "visited"
        result.append(k)

    for k in sorted(keys):
        if k not in visited:
            visit(k)
    return result


def get_subsystem_rollout_plan(db: Session, node_id: int, subsystem: str) -> dict[str, Any]:
    normalized_subsystem = subsystem
    if subsystem in {"dtrain", "distributed-training-plane"}:
        normalized_subsystem = "distributed-training-plane"

    catalog = service_catalog()
    sub_keys = {k for k, v in catalog.items() if v.get("subsystem") == normalized_subsystem}
    if not sub_keys:
        sub_keys = {k for k, v in catalog.items() if subsystem in (v.get("subsystem") or "")}

    all_keys = set(sub_keys)
    to_expand = list(sub_keys)
    while to_expand:
        current = to_expand.pop()
        deps = required_dependencies(current)
        for dep in deps:
            if dep not in all_keys:
                all_keys.add(dep)
                to_expand.append(dep)

    ordered_keys = topological_sort(all_keys)
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    steps = []
    statuses = {}
    for k in ordered_keys:
        inst = db.scalar(
            select(ServiceInstance).where(ServiceInstance.node_id == node_id, ServiceInstance.service_key == k)
        )
        statuses[k] = inst.status if inst else "created"

    for k in ordered_keys:
        contract = rendered_contract(k, node_id=node_id, volume_root=node.volume_root)
        display_name = contract.get("display_name") or contract.get("name") or k
        kind = contract.get("kind", "app")
        status = statuses[k]
        action = "none" if status in RUNNING_STATUSES else "deploy"

        blockers = []
        for dep in required_dependencies(k):
            if dep in all_keys and statuses.get(dep, "created") not in RUNNING_STATUSES:
                blockers.append(dep)

        steps.append(
            {
                "service_key": k,
                # Keep both legacy and canonical field names for UI compatibility.
                "display_name": display_name,
                "name": display_name,
                "kind": kind,
                "current_status": status,
                "status": status,
                "action": action,
                "dependency_blockers": blockers,
                "blockers": blockers,
                "expected_container_name": contract.get("container_name") or f"node-{node_id}-{k}",
                "container_name": contract.get("container_name") or f"node-{node_id}-{k}",
            }
        )

    overall_blockers = [step["service_key"] for step in steps if step["current_status"] not in RUNNING_STATUSES]
    ok = len(overall_blockers) == 0
    summary = (
        f"Subsystem {subsystem} is fully operational."
        if ok
        else f"Subsystem {subsystem} requires deploying {len(overall_blockers)} service(s)."
    )

    return {
        "node_id": node_id,
        "subsystem": subsystem,
        "ok": ok,
        "summary": summary,
        "steps": steps,
        "blocked_by": overall_blockers,
    }


def deploy_subsystem(db: Session, node_id: int, subsystem: str) -> dict[str, Any]:
    plan = get_subsystem_rollout_plan(db, node_id, subsystem)
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    jobs = []
    deployed_keys = []

    for step in plan["steps"]:
        k = step["service_key"]
        service = db.scalar(
            select(ServiceInstance).where(ServiceInstance.node_id == node_id, ServiceInstance.service_key == k)
        )
        if not service:
            service = create_service_instance(db, node=node, service_key=k)

        if service.status not in RUNNING_STATUSES:
            job = deploy_service(db, service)
            jobs.append({"job_id": job.id, "service_key": k, "status": job.status, "action": job.action})
            deployed_keys.append(k)

    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Deployed subsystem {subsystem} on node {node.name}. Deployed services: {', '.join(deployed_keys) if deployed_keys else 'none'}",
        node_id=node_id,
        metadata={"subsystem": subsystem, "deployed_count": len(deployed_keys)},
    )

    return {
        "ok": True,
        "summary": f"Successfully rolled out subsystem '{subsystem}' on node '{node.name}'. Deployed {len(deployed_keys)} service(s).",
        "jobs": jobs,
    }


def check_port_and_name_availability(
    db: Session, node_id: int, port: int | None = None, name: str | None = None
) -> dict:
    collisions = []
    live_checked = False
    live_ports: list[int] = []

    if name:
        existing_name = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == node_id,
                ServiceInstance.container_name == name,
                ServiceInstance.status != "deleted",
            )
        )
        if existing_name:
            collisions.append(f"Container name '{name}' is already in use by service '{existing_name.name}'.")

    if port:
        active_services = db.scalars(
            select(ServiceInstance).where(ServiceInstance.node_id == node_id, ServiceInstance.status != "deleted")
        )
        for svc in active_services:
            try:
                cfg = json.loads(svc.config_json or "{}")
            except Exception:
                cfg = {}
            for key in ("port", "host_port", "service_port", "published_port"):
                if cfg.get(key) == port or str(cfg.get(key) or "") == str(port):
                    collisions.append(f"Host port {port} is already bound by service '{svc.name}' (inventory).")
                    break

        # Live docker published ports (Part A)
        node = db.get(Node, node_id)
        try:
            live = _live_host_ports_for_node(node)
            live_checked = True
            live_ports = sorted(live)
            if int(port) in live:
                collisions.append(f"Host port {port} is currently published by a running container on the node.")
        except Exception:
            live_checked = False

    return {
        "available": len(collisions) == 0,
        "collisions": collisions,
        "live_checked": live_checked,
        "live_host_ports_sample": live_ports[:40],
    }


# --- Live container status (real docker inspect only; never invent healthy) ---

_LIVE_STATUS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LIVE_STATUS_TTL_SECONDS = 5.0


def _docker_inspect_local(container_name: str) -> tuple[dict[str, Any] | None, str | None]:
    import subprocess

    if not container_name:
        return None, "empty container name"
    try:
        proc = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "docker inspect failed").strip()
            # Not found is not a hard failure of the platform
            if "No such object" in err or "no such object" in err.lower():
                return None, "not_found"
            return None, err[:400]
        data = json.loads(proc.stdout)
        if isinstance(data, list) and data:
            return data[0], None
        return None, "empty inspect payload"
    except FileNotFoundError:
        return None, "docker CLI not available"
    except Exception as exc:
        return None, str(exc)


def _docker_inspect_remote(node: Node, container_name: str) -> tuple[dict[str, Any] | None, str | None]:
    """docker inspect over SSH for true remote nodes."""
    import subprocess

    if not container_name:
        return None, "empty container name"
    host = (node.host or "").strip()
    user = (node.ssh_user or "ubuntu").strip()
    key = (node.ssh_key_path or "").strip()
    if not host:
        return None, "missing host"
    # Quote container name for remote shell
    safe_name = container_name.replace("'", "'\"'\"'")
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=8",
    ]
    if key:
        cmd.extend(["-i", key])
    cmd.append(f"{user}@{host}")
    cmd.append(f"docker inspect '{safe_name}'")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = proc.stdout or ""
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            combined = (err or out or "remote docker inspect failed").strip()
            if "No such object" in combined or "no such object" in combined.lower():
                return None, "not_found"
            return None, combined[:400]
        data = json.loads(out)
        if isinstance(data, list) and data:
            return data[0], None
        return None, "empty inspect payload"
    except FileNotFoundError:
        return None, "ssh client not available"
    except json.JSONDecodeError:
        return None, "invalid inspect JSON from remote"
    except Exception as exc:
        return None, str(exc)[:400]


def _node_uses_local_docker(node: Node | None) -> bool:
    if node is None:
        return True
    host = (node.host or "").strip().lower()
    return (
        settings.local_mode
        or (node.environment or "").lower() == "local"
        or host in {"localhost", "127.0.0.1", "0.0.0.0", "", "65.2.63.24"}
    )


def _docker_inspect_for_node(node: Node | None, container_name: str) -> tuple[dict[str, Any] | None, str | None, str]:
    """Return (inspect, error, source). Prefer local for this host; SSH for remote."""
    if node is None or _node_uses_local_docker(node):
        data, err = _docker_inspect_local(container_name)
        return data, err, "docker_inspect"
    data, err = _docker_inspect_remote(node, container_name)
    return data, err, "docker_inspect_ssh"


def _map_inspect_to_live(
    service: ServiceInstance,
    inspect: dict[str, Any] | None,
    error: str | None,
    *,
    source: str = "docker_inspect",
) -> dict[str, Any]:
    now = datetime.utcnow().isoformat() + "Z"
    base = {
        "service_id": service.id,
        "external_id": service.external_id or "",
        "service_key": service.service_key,
        "name": service.name,
        "container_name": service.container_name,
        "image": service.image,
        "db_status": service.status,
        "checked_at": now,
        "source": source,
    }
    if error == "not_found" or inspect is None:
        overall = "not_found" if error in (None, "not_found") else "error"
        return {
            **base,
            "overall_status": overall,
            "running": False,
            "state": overall,
            "restart_count": None,
            "started_at": None,
            "error": error if error not in (None, "not_found") else ("container not found" if error == "not_found" else error),
            "stale": False,
        }
    state = (inspect.get("State") or {}) if isinstance(inspect, dict) else {}
    status = str(state.get("Status") or "unknown").lower()
    running = bool(state.get("Running"))
    if running:
        overall = "running"
    elif status in {"exited", "dead"}:
        overall = "exited"
    elif status in {"paused", "restarting", "created"}:
        overall = status
    else:
        overall = status or "unknown"
    cfg = inspect.get("Config") or {}
    return {
        **base,
        "overall_status": overall,
        "running": running,
        "state": status,
        "restart_count": inspect.get("RestartCount"),
        "started_at": state.get("StartedAt"),
        "exit_code": state.get("ExitCode"),
        "oom_killed": bool(state.get("OOMKilled", False)),
        "image": cfg.get("Image") or service.image,
        "error": None,
        "stale": False,
    }


def get_service_live_status(db: Session, service: ServiceInstance, *, use_cache: bool = True) -> dict[str, Any]:
    import time

    # Ensure node is available for local vs remote decision
    node = service.node
    if node is None and service.node_id:
        node = db.get(Node, service.node_id)

    cache_key = f"svc:{service.id}:{service.container_name}:{getattr(node, 'host', '')}"
    now = time.monotonic()
    if use_cache and cache_key in _LIVE_STATUS_CACHE:
        created, payload = _LIVE_STATUS_CACHE[cache_key]
        if now - created < _LIVE_STATUS_TTL_SECONDS:
            out = dict(payload)
            out["stale"] = False
            out["cache_hit"] = True
            return out

    inspect, err, source = _docker_inspect_for_node(node, service.container_name)
    result = _map_inspect_to_live(service, inspect, err, source=source)
    result["cache_hit"] = False

    # Persist honest status on the inventory row when we got a real answer
    if result.get("overall_status") in {"running", "exited", "dead", "paused", "restarting", "not_found"}:
        mapped = result["overall_status"]
        if mapped == "not_found":
            mapped = "unknown"
        if service.status != mapped:
            service.status = mapped
            db.commit()

    _LIVE_STATUS_CACHE[cache_key] = (now, result)
    return result


def get_node_services_live_status(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    services = list(
        db.scalars(
            select(ServiceInstance)
            .where(ServiceInstance.node_id == node_id, ServiceInstance.status != "deleted")
            .order_by(ServiceInstance.id)
        ).all()
    )
    items = [get_service_live_status(db, svc) for svc in services]
    running = sum(1 for i in items if i.get("running"))
    source = "docker_inspect" if _node_uses_local_docker(node) else "docker_inspect_ssh"
    return {
        "node_id": node_id,
        "count": len(items),
        "running_count": running,
        "items": items,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "source": source,
    }


def _live_host_ports_for_node(node: Node | None) -> set[int]:
    """Parse published host ports from docker ps (local or remote)."""
    import re
    import subprocess

    ports: set[int] = set()
    if node is None:
        return ports
    try:
        if _node_uses_local_docker(node):
            proc = subprocess.run(
                ["docker", "ps", "--format", "{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            text = proc.stdout or ""
        else:
            host = (node.host or "").strip()
            user = (node.ssh_user or "ubuntu").strip()
            key = (node.ssh_key_path or "").strip()
            cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8"]
            if key:
                cmd.extend(["-i", key])
            cmd.append(f"{user}@{host}")
            cmd.append("docker ps --format '{{.Ports}}'")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            text = proc.stdout or ""
        # Match 0.0.0.0:8080-> or :::8080-> or 127.0.0.1:5432->
        for match in re.finditer(r"(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]|::):(\d+)->", text):
            try:
                ports.add(int(match.group(1)))
            except ValueError:
                continue
        for match in re.finditer(r":(\d+)->", text):
            try:
                ports.add(int(match.group(1)))
            except ValueError:
                continue
    except Exception:
        return ports
    return ports
