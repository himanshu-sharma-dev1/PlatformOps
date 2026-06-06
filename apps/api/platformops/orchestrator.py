from __future__ import annotations

import copy
import difflib
import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import (
    format_contract_value,
    get_service_contract,
    observability_catalog,
    rendered_contract,
    required_dependencies,
    service_catalog,
)
from .jobs import create_job, finish_job, run_local_job
from .tasks import run_job_async
from .models import (
    AuditExport,
    BackupRun,
    CapacityReport,
    Cluster,
    ConfigSnapshot,
    DeploymentJob,
    DeploymentPlanRecord,
    DriftReport,
    ForceDeleteApproval,
    IncidentRecord,
    JobStatus,
    LogArchive,
    MaintenanceWindow,
    MonitoringCheck,
    Node,
    OperationalEvent,
    PolicyFinding,
    ReleaseApproval,
    ReleaseRecord,
    RunbookExecution,
    SecretRecord,
    ServiceInstance,
    SloReport,
)
from .settings import settings

RUNNING_STATUSES = {"running", "healthy", "success"}


def _service_display_name(service_key: str) -> str:
    contract = get_service_contract(service_key)
    return contract.get("display_name") or contract.get("name") or service_key


def _container_name(service_key: str, node: Node) -> str:
    contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
    return contract.get("container_name", f"node-{node.id}-{service_key}")


def _deep_merge_dict(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _service_contract_for_node(
    service_key: str,
    *,
    node_id: int,
    volume_root: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = dict(get_service_contract(service_key))
    if overrides:
        contract = _deep_merge_dict(contract, overrides)
    return format_contract_value(contract, node_id=node_id, volume_root=volume_root)


def _ansible_inventory_arg(node: Node) -> str:
    if node.environment == "local":
        return "localhost,"
    return f"{node.host},"


def _ansible_base_command(node: Node, playbook: str) -> str:
    ansible_dir = settings.resolve(settings.ansible_dir)
    inventory = _ansible_inventory_arg(node)
    user_arg = "" if node.environment == "local" else f" -u {node.ssh_user}"
    key_arg = f" --private-key {node.ssh_key_path}" if node.ssh_key_path else ""
    connection = " -c local" if node.environment == "local" else ""
    return f"ansible-playbook -i {inventory}{connection}{user_arg}{key_arg} {ansible_dir / 'playbooks' / playbook}"


def validate_node(db: Session, node: Node) -> DeploymentJob:
    command = f"{_ansible_base_command(node, 'validate_node.yml')} --extra-vars node_name={node.name}"
    job = create_job(db, action="validate-node", command=command, node_id=node.id)

    if settings.local_mode:
        node.status = "healthy"
        node.facts_json = json.dumps(
            {
                "hostname": socket.gethostname(),
                "checked_at": datetime.utcnow().isoformat() + "Z",
                "mode": "local-simulation",
                "docker": "expected",
                "ansible": "command-recorded",
            }
        )
        db.commit()
        rich_output = (
            f"PLAY [Validate PlatformOps node prerequisites] **************************************\n\n"
            f"TASK [Gathering Facts] ***************************************************************\n"
            f"ok: [{node.name}]\n\n"
            f"TASK [Check Docker CLI] **************************************************************\n"
            f"ok: [{node.name}] => {{\"changed\": false, \"rc\": 0, \"stdout\": \"Docker version 24.0.7, build afdd53b\"}}\n\n"
            f"TASK [Check Docker daemon] ***********************************************************\n"
            f"ok: [{node.name}] => {{\"changed\": false, \"rc\": 0, \"stdout\": \"Server Version: 24.0.7\"}}\n\n"
            f"TASK [Print validation summary] ******************************************************\n"
            f"ok: [{node.name}] => {{\n"
            f"    \"msg\": {{\n"
            f"        \"docker_cli\": \"Docker version 24.0.7, build afdd53b\",\n"
            f"        \"docker_ready\": true,\n"
            f"        \"node\": \"{node.name}\",\n"
            f"        \"os\": \"Ubuntu 22.04\"\n"
            f"    }}\n"
            f"}}\n\n"
            f"PLAY RECAP ***************************************************************************\n"
            f"{node.name.ljust(28)}: ok=4    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0"
        )
        return finish_job(db, job, ok=True, output=rich_output)

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_node = bg_db.get(Node, node.id)
        if bg_node:
            bg_node.status = "healthy" if ok else "unreachable"

    return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)


def create_service_instance(
    db: Session,
    *,
    node: Node,
    service_key: str,
    name: str | None = None,
    contract_overrides: dict[str, Any] | None = None,
) -> ServiceInstance:
    contract = _service_contract_for_node(
        service_key,
        node_id=node.id,
        volume_root=node.volume_root,
        overrides=contract_overrides,
    )
    if not contract:
        raise ValueError(f"Unknown service key: {service_key}")

    existing = db.scalar(
        select(ServiceInstance).where(ServiceInstance.node_id == node.id, ServiceInstance.service_key == service_key)
    )
    if existing:
        return existing

    service = ServiceInstance(
        node_id=node.id,
        service_key=service_key,
        name=name or contract.get("display_name") or contract.get("name") or service_key,
        kind=contract.get("kind", "app"),
        container_name=contract.get("container_name", f"node-{node.id}-{service_key}"),
        image=contract.get("image", ""),
        config_json=json.dumps(contract),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    record_event(
        db,
        category="catalog",
        level="info",
        message=f"Registered service card {service.name}",
        service_id=service.id,
        node_id=node.id,
        metadata={"service_key": service.service_key, "kind": service.kind, "overrides": contract_overrides or {}},
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
    service.name = (name or "").strip() or merged_contract.get("display_name") or merged_contract.get("name") or service.service_key
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
    if service_key not in service_catalog():
        raise ValueError(f"Unknown service key: {service_key}")
    contract = json.loads(service.config_json or "{}") if service else rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
    contract_defaults = copy.deepcopy(contract)
    fields: list[dict[str, Any]] = [
        {
            "key": "name",
            "label": "Service name",
            "field_type": "text",
            "required": False,
            "value": service.name if service else "",
            "help_text": "Used as the service display and runtime name. Must remain unique within the cluster.",
            "section": "Identity",
        }
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
        service.status = "running"
        db.commit()
        rich_output = (
            f"PLAY [Deploy service container via Docker Compose] ***********************************\n\n"
            f"TASK [Gathering Facts] ***************************************************************\n"
            f"ok: [{node.name}]\n\n"
            f"TASK [Create service directories] ****************************************************\n"
            f"changed: [{node.name}] => {{\"changed\": true, \"path\": \"{node.volume_root}/{service.service_key}\"}}\n\n"
            f"TASK [Copy docker-compose templates] *************************************************\n"
            f"changed: [{node.name}] => {{\"changed\": true, \"dest\": \"{node.volume_root}/compose/docker-compose.{service.service_key}.yml\"}}\n\n"
            f"TASK [Start container service] *******************************************************\n"
            f"changed: [{node.name}] => {{\"changed\": true, \"rc\": 0, \"stdout\": \"Container {service.container_name} Started\"}}\n\n"
            f"PLAY RECAP ***************************************************************************\n"
            f"{node.name.ljust(28)}: ok=4    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0"
        )
        completed = finish_job(db, job, ok=True, output=rich_output)
        record_event(
            db,
            category="deployment",
            level="info",
            message=f"Deployed {service.name}",
            service_id=service.id,
            node_id=node.id,
            metadata={"mode": "local-simulation", "container": service.container_name},
        )
        return completed

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
        service.status = "deleted"
        db.commit()
        completed = finish_job(db, job, ok=True, output=f"Simulated delete for {service.container_name}.")
        record_event(
            db,
            category="lifecycle",
            level="info",
            message=f"Deleted {service.name}",
            service_id=service.id,
            node_id=node.id,
            metadata={"mode": "local-simulation"},
        )
        return completed

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


def _diagnostics_target_label(kind: str) -> str:
    if kind == "infrastructure":
        return "Infrastructure Card"
    if kind == "helper":
        return "Helper"
    return "Main"


def diagnostics_targets_for_service(db: Session, service: ServiceInstance) -> list[dict[str, Any]]:
    required = required_dependencies(service.service_key)
    targets: list[dict[str, Any]] = [
        {
            "service_id": service.id,
            "service_key": service.service_key,
            "name": service.name,
            "kind": service.kind,
            "target_type": _diagnostics_target_label(service.kind),
            "container_name": service.container_name,
            "status": service.status,
            "ready": service.status in RUNNING_STATUSES,
            "on_node": True,
        }
    ]
    for dependency_key in required:
        dependency_contract = get_service_contract(dependency_key)
        dependency = _service_by_key(db, service.node_id, dependency_key)
        dependency_kind = dependency_contract.get("kind", dependency.kind if dependency else "app")
        dependency_status = dependency.status if dependency else "missing"
        targets.append(
            {
                "service_id": dependency.id if dependency else None,
                "service_key": dependency_key,
                "name": dependency_contract.get("display_name") or _service_display_name(dependency_key),
                "kind": dependency_kind,
                "target_type": _diagnostics_target_label(dependency_kind),
                "container_name": dependency.container_name if dependency else "(not installed)",
                "status": dependency_status,
                "ready": dependency_status in RUNNING_STATUSES,
                "on_node": dependency is not None,
            }
        )
    return targets


def service_diagnostics(
    db: Session,
    service: ServiceInstance,
    *,
    source_service: ServiceInstance | None = None,
) -> dict[str, Any]:
    source = source_service or service
    contract = json.loads(service.config_json or "{}")
    log_paths = contract.get("log_paths", [])
    required = required_dependencies(source.service_key)
    available_targets = diagnostics_targets_for_service(db, source)
    dependency_targets: list[dict[str, Any]] = []
    missing_dependencies: list[str] = []
    stopped_dependencies: list[str] = []
    for dependency_key in required:
        dependency_contract = get_service_contract(dependency_key)
        dependency = _service_by_key(db, source.node_id, dependency_key)
        dependency_kind = dependency_contract.get("kind", dependency.kind if dependency else "app")
        dependency_status = dependency.status if dependency else "missing"
        if dependency is None:
            missing_dependencies.append(dependency_key)
        elif dependency.status not in RUNNING_STATUSES:
            stopped_dependencies.append(dependency_key)
        dependency_targets.append(
            {
                "service_key": dependency_key,
                "name": dependency_contract.get("display_name") or _service_display_name(dependency_key),
                "kind": dependency_kind,
                "target_type": _diagnostics_target_label(dependency_kind),
                "container_name": dependency.container_name if dependency else "(not installed)",
                "status": dependency_status,
                "ready": dependency_status in RUNNING_STATUSES,
                "on_node": dependency is not None,
            }
        )

    observability_defaults = observability_catalog().get("defaults", {})
    loki_url = observability_defaults.get("loki_url", "http://localhost:3100")
    backfill_ready = bool(log_paths) and bool(loki_url)
    readiness = {
        "container": service.container_name,
        "status": service.status,
        "target_type": _diagnostics_target_label(service.kind),
        "configurable": bool(contract.get("config_files")),
        "file_logs": bool(log_paths),
        "requires_become": bool(contract.get("requires_become", service.kind == "infrastructure")),
        "loki_url": loki_url,
        "backfill_requirements": {
            "loki_configured": bool(loki_url),
            "file_log_paths_present": bool(log_paths),
            "requires_become": bool(contract.get("requires_become", service.kind == "infrastructure")),
            "ready": backfill_ready,
            "missing": [
                item
                for item in [
                    "loki_url" if not loki_url else "",
                    "log_paths" if not log_paths else "",
                ]
                if item
            ],
        },
        "paths_checked": [
            {
                "path": path,
                "readable": settings.local_mode,
                "reason": "readable in local simulation"
                if settings.local_mode
                else "remote path scan requires host access",
            }
            for path in log_paths
        ],
        "dependency_targets": dependency_targets,
        "dependency_summary": {
            "required": required,
            "missing": missing_dependencies,
            "stopped": stopped_dependencies,
            "ready": len(missing_dependencies) == 0 and len(stopped_dependencies) == 0,
        },
        "config_actions": {
            "config_manager_available": bool(contract.get("config_files")),
            "open_infra_card_recommended": service.kind != "infrastructure" and len(required) > 0,
            "recommended_dependency_cards": [
                item["name"] for item in dependency_targets if item["kind"] == "infrastructure" and not item["ready"]
            ],
        },
        "available_targets": available_targets,
        "source_service_key": source.service_key,
        "source_service_name": source.name,
        "target_service_key": service.service_key,
        "target_service_name": service.name,
    }
    recent_logs = [
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "message": f"{service.name} diagnostics target is ready for {service.container_name}.",
        },
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "message": "Local mode is recording Ansible commands instead of changing Docker state."
            if settings.local_mode
            else f"{service.name} diagnostics target check requested.",
        },
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "WARN" if not backfill_ready else "INFO",
            "message": "File-log backfill readiness check complete."
            if backfill_ready
            else "File-log backfill is not ready until required paths and Loki endpoint are available.",
        },
    ]
    return {
        "service_id": service.id,
        "source_service_id": source.id,
        "source_service_key": source.service_key,
        "target_service_key": service.service_key,
        "target": service.container_name,
        "status": service.status,
        "log_paths": log_paths,
        "recent_logs": recent_logs,
        "readiness": readiness,
    }


def service_live_logs(
    db: Session,
    service: ServiceInstance,
    *,
    tail_lines: int = 150,
    page_size: int = 100,
    cursor: int = 0,
) -> dict[str, Any]:
    safe_tail = max(10, min(tail_lines, 1000))
    safe_page = max(10, min(page_size, 1000))
    safe_cursor = max(0, cursor)

    event_statement = select(OperationalEvent).where(
        OperationalEvent.service_id == service.id,
        OperationalEvent.category.in_(("diagnostics", "monitoring", "deployment", "config", "lifecycle")),
    )
    total_available = int(db.scalar(select(func.count()).select_from(event_statement.subquery())) or 0)
    fetch_size = safe_tail if safe_cursor == 0 else safe_page
    events = list(
        db.scalars(
            event_statement.order_by(OperationalEvent.created_at.desc()).offset(safe_cursor).limit(fetch_size)
        ).all()
    )

    lines: list[dict[str, str]] = []
    for item in events:
        lines.append(
            {
                "timestamp": item.created_at.isoformat() if item.created_at else datetime.utcnow().isoformat() + "Z",
                "level": (item.level or "INFO").upper(),
                "message": item.message,
                "source": item.category,
            }
        )

    if not lines:
        lines = [
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "message": f"No historical events yet for {service.name}. Waiting for diagnostics signal.",
                "source": "diagnostics",
            }
        ]

    next_cursor = safe_cursor + len(events)
    has_more_history = next_cursor < total_available
    source_state = "streaming" if service.status in RUNNING_STATUSES else "snapshot"
    defaults = observability_catalog().get("defaults", {})
    poll_interval_ms = int(defaults.get("poll_interval_ms", 2500))

    return {
        "service_id": service.id,
        "target": service.container_name,
        "source_state": source_state,
        "poll_interval_ms": poll_interval_ms,
        "tail_lines": safe_tail,
        "page_size": safe_page,
        "cursor": safe_cursor,
        "next_cursor": next_cursor,
        "total_available": total_available,
        "has_more_history": has_more_history,
        "lines": lines,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _recommended_runbook_for_diagnostics_context(
    *,
    dependency_missing: list[str],
    dependency_stopped: list[str],
    drift_status: str | None,
    drift_fields: list[str],
    latest_release: ReleaseRecord | None,
    metrics: dict[str, Any],
) -> str:
    if dependency_missing or dependency_stopped:
        return "dependency-recovery"
    if drift_status == "drifted" or drift_fields:
        return "config-rollback"
    if latest_release is not None and (metrics["log_error_rate"] >= 0.4 or metrics["restart_count"] > 0):
        return "restart-service"
    return "restart-service"


def service_diagnostics_analysis(
    db: Session,
    service: ServiceInstance,
    *,
    source_service: ServiceInstance | None = None,
) -> dict[str, Any]:
    source = source_service or service
    diagnostics = service_diagnostics(db, service, source_service=source)
    metrics = get_service_metrics(db, service.id, window="15m")
    dependency = diagnostics["readiness"]["dependency_summary"]
    readiness = diagnostics["readiness"]
    latest_monitoring = db.scalar(
        select(MonitoringCheck).where(MonitoringCheck.service_id == service.id).order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc()))
    latest_release = db.scalar(
        select(ReleaseRecord).where(ReleaseRecord.service_id == service.id).order_by(ReleaseRecord.created_at.desc())
    )
    latest_snapshot = db.scalar(
        select(ConfigSnapshot).where(ConfigSnapshot.service_id == service.id).order_by(ConfigSnapshot.version.desc()).limit(1)
    )
    latest_drift = db.scalar(select(DriftReport).where(DriftReport.service_id == service.id).order_by(DriftReport.created_at.desc()))
    drift_differences: list[dict[str, Any]] = []
    drift_fields: list[str] = []
    if latest_drift is not None:
        try:
            parsed_drift = json.loads(latest_drift.differences_json or "[]")
            if isinstance(parsed_drift, list):
                drift_differences = [item for item in parsed_drift if isinstance(item, dict)]
                drift_fields = [str(item.get("field")) for item in drift_differences if item.get("field")]
        except json.JSONDecodeError:
            drift_differences = []
            drift_fields = []
    config_events = list(
        db.scalars(
            select(OperationalEvent)
            .where(OperationalEvent.category == "config", OperationalEvent.service_id == service.id)
            .order_by(OperationalEvent.created_at.desc())
            .limit(4)
        ).all()
    )
    open_incidents = list(
        db.scalars(
            select(IncidentRecord)
            .where(IncidentRecord.service_id == source.id, IncidentRecord.status == "open")
            .order_by(IncidentRecord.created_at.desc())
            .limit(5)
        ).all()
    )
    recent_incidents = list(
        db.scalars(
            select(IncidentRecord)
            .where(IncidentRecord.service_id == source.id)
            .order_by(IncidentRecord.created_at.desc())
            .limit(6)
        ).all()
    )
    incident_ids = [incident.id for incident in recent_incidents]
    recent_runbooks = list(
        db.scalars(
            select(RunbookExecution)
            .where(RunbookExecution.incident_id.in_(incident_ids) if incident_ids else False)
            .order_by(RunbookExecution.created_at.desc())
        ).all()
    )
    runbooks_by_incident: dict[int, list[RunbookExecution]] = {}
    for runbook in recent_runbooks:
        if runbook.incident_id is None:
            continue
        runbooks_by_incident.setdefault(runbook.incident_id, []).append(runbook)

    recent_incident_summaries: list[dict[str, Any]] = []
    historical_correlation: list[str] = []
    change_evidence: list[dict[str, Any]] = []
    for incident in recent_incidents:
        latest_runbook = (runbooks_by_incident.get(incident.id) or [None])[0]
        match_reasons: list[str] = []
        if "health" in incident.title.lower():
            match_reasons.append("health incident")
        if metrics["restart_count"] > 0:
            match_reasons.append("restart pressure")
        if metrics["log_error_rate"] >= 0.4:
            match_reasons.append("high error rate")
        if dependency["missing"] or dependency["stopped"]:
            match_reasons.append("dependency disruption")
        if latest_drift is not None and latest_drift.status == "drifted":
            match_reasons.append("config drift")
        if latest_release is not None:
            match_reasons.append("recent release")
        suggested_runbook_key = _recommended_runbook_for_diagnostics_context(
            dependency_missing=dependency["missing"],
            dependency_stopped=dependency["stopped"],
            drift_status=latest_drift.status if latest_drift else None,
            drift_fields=drift_fields,
            latest_release=latest_release,
            metrics=metrics,
        )
        recent_incident_summaries.append(
            {
                "id": incident.id,
                "title": incident.title,
                "severity": incident.severity,
                "status": incident.status,
                "summary": incident.summary,
                "remediation": incident.remediation,
                "created_at": incident.created_at.isoformat() if incident.created_at else datetime.utcnow().isoformat() + "Z",
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "latest_runbook_key": latest_runbook.runbook_key if latest_runbook else None,
                "latest_runbook_status": latest_runbook.status if latest_runbook else None,
                "match_reason": ", ".join(match_reasons[:2]) if match_reasons else "recent service context",
                "suggested_runbook_key": suggested_runbook_key,
            }
        )
        if match_reasons:
            historical_correlation.append(
                f"Incident #{incident.id} overlaps with current signals: {', '.join(match_reasons[:2])}."
            )

    if latest_release is not None:
        release_notes = latest_release.notes.strip() if latest_release.notes else ""
        change_evidence.append(
            {
                "kind": "release",
                "title": f"Latest release {latest_release.version}",
                "summary": f"Image {latest_release.image} via {latest_release.strategy} strategy.",
                "created_at": latest_release.created_at.isoformat() if latest_release.created_at else datetime.utcnow().isoformat() + "Z",
                "severity": "warning" if metrics["log_error_rate"] >= 0.4 or metrics["restart_count"] > 0 else "info",
                "detail": release_notes or "Recent release may be relevant if symptoms started after deployment.",
                "confidence": 82 if metrics["log_error_rate"] >= 0.4 or metrics["restart_count"] > 0 else 58,
                "target_view": "release",
            }
        )
    if latest_drift is not None:
        difference_count = len(drift_differences)
        change_evidence.append(
            {
                "kind": "drift",
                "title": f"Latest drift check: {latest_drift.status}",
                "summary": f"{difference_count} difference(s) against the latest baseline snapshot.",
                "created_at": latest_drift.created_at.isoformat() if latest_drift.created_at else datetime.utcnow().isoformat() + "Z",
                "severity": "warning" if latest_drift.status == "drifted" else "info",
                "detail": "Config drift can explain incidents if runtime behavior diverged from the last known snapshot.",
                "confidence": 90 if latest_drift.status == "drifted" and drift_fields else 66,
                "target_view": "config-compare",
                "baseline_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_left_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_right_snapshot_id": latest_snapshot.id if latest_snapshot else latest_drift.baseline_snapshot_id,
                "drift_fields": drift_fields[:6],
                "drift_preview": drift_differences[:4],
            }
        )
    for event in config_events:
        try:
            metadata = json.loads(event.metadata_json or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except json.JSONDecodeError:
            metadata = {}
        change_evidence.append(
            {
                "kind": "config",
                "title": event.message,
                "summary": f"Config action {metadata.get('action', 'change')} by {metadata.get('actor', 'platform-operator')}.",
                "created_at": event.created_at.isoformat() if event.created_at else datetime.utcnow().isoformat() + "Z",
                "severity": "info",
                "detail": f"Snapshot/version reference: {metadata.get('version') or metadata.get('snapshot_id') or 'n/a'}.",
                "confidence": 72 if metadata.get("action") in {"restored", "renamed", "captured"} else 55,
                "target_view": "config-compare" if metadata.get("snapshot_id") else "config-timeline",
                "config_action": metadata.get("action"),
                "snapshot_id": metadata.get("snapshot_id"),
                "snapshot_version": metadata.get("version"),
                "actor": metadata.get("actor"),
                "compare_left_snapshot_id": latest_drift.baseline_snapshot_id if latest_drift else None,
                "compare_right_snapshot_id": metadata.get("snapshot_id"),
            }
        )
    change_evidence.sort(key=lambda item: (-int(item.get("confidence", 0)), item.get("kind", "")))
    config_events_by_id = {event.id: event for event in config_events}
    common_refs: list[str] = []
    if latest_release is not None:
        common_refs.append(f"release:{latest_release.version}")
    if latest_drift is not None:
        common_refs.append(f"drift:{latest_drift.status}")
    if drift_fields:
        common_refs.extend([f"drift-field:{field}" for field in drift_fields[:3]])
    if config_events:
        common_refs.extend([f"config-event:{event.id}" for event in config_events[:2]])
    if open_incidents:
        common_refs.append(f"incident:{open_incidents[0].id}")

    def resolve_supporting_evidence(evidence_ref: str) -> dict[str, Any]:
        prefix, _, raw_value = evidence_ref.partition(":")
        if prefix == "release" and latest_release is not None:
            return {
                "evidence_id": evidence_ref,
                "label": f"Release {latest_release.version}",
                "summary": f"Review image {latest_release.image} and deployment strategy {latest_release.strategy}.",
                "target_view": "release",
                "severity": "warning",
            }
        if prefix == "release-image" and latest_release is not None:
            return {
                "evidence_id": evidence_ref,
                "label": "Release image",
                "summary": latest_release.image,
                "target_view": "release",
                "severity": "info",
            }
        if prefix == "drift" and latest_drift is not None:
            return {
                "evidence_id": evidence_ref,
                "label": f"Drift status: {latest_drift.status}",
                "summary": f"Compare baseline snapshot #{latest_drift.baseline_snapshot_id} against the latest captured snapshot.",
                "target_view": "config-compare",
                "severity": "warning" if latest_drift.status == "drifted" else "info",
                "compare_left_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_right_snapshot_id": latest_snapshot.id if latest_snapshot else latest_drift.baseline_snapshot_id,
                "baseline_snapshot_id": latest_drift.baseline_snapshot_id,
            }
        if prefix == "drift-field" and latest_drift is not None:
            return {
                "evidence_id": evidence_ref,
                "label": f"Changed key: {raw_value}",
                "summary": f"Open snapshot compare focused on drift around `{raw_value}`.",
                "target_view": "config-compare",
                "severity": "warning",
                "compare_left_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_right_snapshot_id": latest_snapshot.id if latest_snapshot else latest_drift.baseline_snapshot_id,
                "baseline_snapshot_id": latest_drift.baseline_snapshot_id,
            }
        if prefix == "config-event":
            try:
                event_id = int(raw_value)
            except ValueError:
                event_id = 0
            event = config_events_by_id.get(event_id)
            if event is not None:
                try:
                    metadata = json.loads(event.metadata_json or "{}")
                    if not isinstance(metadata, dict):
                        metadata = {}
                except json.JSONDecodeError:
                    metadata = {}
                return {
                    "evidence_id": evidence_ref,
                    "label": event.message,
                    "summary": f"Config {metadata.get('action', 'change')} by {metadata.get('actor', 'platform-operator')}.",
                    "target_view": "config-compare" if metadata.get("snapshot_id") else "config-timeline",
                    "severity": "info",
                    "compare_left_snapshot_id": latest_drift.baseline_snapshot_id if latest_drift else None,
                    "compare_right_snapshot_id": metadata.get("snapshot_id"),
                    "baseline_snapshot_id": latest_drift.baseline_snapshot_id if latest_drift else None,
                }
        if prefix == "incident":
            try:
                incident_id = int(raw_value)
            except ValueError:
                incident_id = 0
            incident = next((item for item in recent_incident_summaries if item["id"] == incident_id), None)
            if incident is not None:
                return {
                    "evidence_id": evidence_ref,
                    "label": f"Incident #{incident_id}",
                    "summary": incident["match_reason"],
                    "target_view": "monitoring",
                    "severity": incident["severity"],
                    "incident_id": incident_id,
                }
        if prefix == "dependency":
            return {
                "evidence_id": evidence_ref,
                "label": _service_display_name(raw_value),
                "summary": "Inspect this dependency target in diagnostics.",
                "target_view": "diagnostics",
                "severity": "warning",
                "service_key": raw_value,
            }
        if prefix == "backfill-missing":
            return {
                "evidence_id": evidence_ref,
                "label": f"Backfill prerequisite: {raw_value}",
                "summary": "Review file-log readiness and readable archive paths.",
                "target_view": "files",
                "severity": "warning",
                "service_key": service.service_key,
            }
        if prefix in {"metric", "monitoring", "slo", "slo-observed"}:
            return {
                "evidence_id": evidence_ref,
                "label": evidence_ref.replace(":", " ", 1),
                "summary": "Correlate this signal with live logs and current telemetry.",
                "target_view": "tail",
                "severity": "info" if prefix == "metric" else "warning",
                "service_key": service.service_key,
            }
        return {
            "evidence_id": evidence_ref,
            "label": evidence_ref,
            "summary": "Review this supporting signal in diagnostics context.",
            "target_view": "diagnostics",
            "severity": "info",
            "service_key": service.service_key,
        }

    insights: list[dict[str, Any]] = []

    if dependency["missing"] or dependency["stopped"]:
        affected = dependency["missing"] + dependency["stopped"]
        dependency_runbook_key = _recommended_runbook_for_diagnostics_context(
            dependency_missing=dependency["missing"],
            dependency_stopped=dependency["stopped"],
            drift_status=latest_drift.status if latest_drift else None,
            drift_fields=drift_fields,
            latest_release=latest_release,
            metrics=metrics,
        )
        actions = [
            {
                "action_id": "ensure-dependency-cards",
                "label": "Ensure dependency cards",
                "description": "Create the missing dependency cards on this node before redeploying.",
                "service_key": None,
                "incident_id": None,
                "runbook_key": None,
                "target_view": "diagnostics",
                "recommended": len(dependency["missing"]) > 0,
            }
        ]
        if open_incidents:
            actions.append(
                {
                    "action_id": "run-incident-runbook",
                    "label": "Run dependency recovery" if dependency_runbook_key == "dependency-recovery" else "Run suggested runbook",
                    "description": "Execute the dependency recovery runbook against the active incident."
                    if dependency_runbook_key == "dependency-recovery"
                    else f"Execute the recommended {dependency_runbook_key} runbook for this context.",
                    "service_key": source.service_key,
                    "incident_id": open_incidents[0].id,
                    "runbook_key": dependency_runbook_key,
                    "target_view": "monitoring",
                    "recommended": len(dependency["missing"]) == 0 and len(dependency["stopped"]) > 0,
                }
            )
        else:
            actions.append(
                {
                    "action_id": "open-incident",
                    "label": "Open dependency incident",
                    "description": "Track dependency remediation in a dedicated incident before recovery actions.",
                    "service_key": source.service_key,
                    "incident_id": None,
                    "runbook_key": None,
                    "target_view": "monitoring",
                    "recommended": len(dependency["missing"]) == 0 and len(dependency["stopped"]) > 0,
                }
            )
        for service_key in affected[:2]:
            actions.append(
                {
                    "action_id": "focus-dependency-diagnostics",
                    "label": f"Inspect {service_key}",
                    "description": "Open dependency diagnostics to confirm container health and log readiness.",
                    "service_key": service_key,
                    "incident_id": None,
                    "runbook_key": None,
                    "target_view": "diagnostics",
                    "recommended": service_key == affected[0],
                }
            )
        insights.append(
            {
                "insight_id": "dependency-health",
                "title": "Dependency readiness is blocking stable operations",
                "severity": "error" if dependency["missing"] else "warning",
                "confidence": 96 if dependency["missing"] else 86,
                "summary": diagnostics["readiness"]["dependency_summary"]["required"]
                and f"Required dependency cards need attention: {', '.join(affected)}."
                or "Dependency cards need attention.",
                "rationale": source.name != service.name
                and f"{source.name} depends on {service.name} context and currently has unresolved dependency state."
                or "The dependency preflight reported missing or stopped infrastructure cards, which can break deployments and runtime health.",
                "evidence_refs": [f"dependency:{item}" for item in affected[:3]] + common_refs[:2],
                "actions": actions,
            }
        )

    if metrics["log_error_rate"] >= 0.4 or metrics["restart_count"] > 0:
        runtime_runbook_key = _recommended_runbook_for_diagnostics_context(
            dependency_missing=dependency["missing"],
            dependency_stopped=dependency["stopped"],
            drift_status=latest_drift.status if latest_drift else None,
            drift_fields=drift_fields,
            latest_release=latest_release,
            metrics=metrics,
        )
        runtime_actions: list[dict[str, Any]] = [
            {
                "action_id": "open-live-logs",
                "label": "Open live logs",
                "description": "Jump to the live tail console for current container output.",
                "service_key": service.service_key,
                "incident_id": None,
                "runbook_key": None,
                "target_view": "tail",
                "recommended": True,
            }
        ]
        if open_incidents:
            lead_incident = open_incidents[0]
            runtime_actions.extend(
                [
                    {
                        "action_id": "open-existing-incident",
                        "label": f"Review incident #{lead_incident.id}",
                        "description": "Continue remediation in the already open incident thread.",
                        "service_key": source.service_key,
                        "incident_id": lead_incident.id,
                        "runbook_key": None,
                        "target_view": "monitoring",
                        "recommended": metrics["restart_count"] > 0,
                    },
                    {
                        "action_id": "run-incident-runbook",
                        "label": "Run restart runbook"
                        if runtime_runbook_key == "restart-service"
                        else f"Run {runtime_runbook_key} runbook",
                        "description": "Trigger the standard restart-service incident runbook."
                        if runtime_runbook_key == "restart-service"
                        else f"Trigger the recommended {runtime_runbook_key} runbook for this failure pattern.",
                        "service_key": source.service_key,
                        "incident_id": lead_incident.id,
                        "runbook_key": runtime_runbook_key,
                        "target_view": "monitoring",
                        "recommended": metrics["restart_count"] > 0,
                    },
                ]
            )
        else:
            runtime_actions.append(
                {
                    "action_id": "open-incident",
                    "label": "Open incident",
                    "description": "Create an incident so remediation steps and runbooks are tracked.",
                    "service_key": source.service_key,
                    "incident_id": None,
                    "runbook_key": None,
                    "target_view": "monitoring",
                    "recommended": metrics["restart_count"] > 0,
                }
            )
        insights.append(
            {
                "insight_id": "runtime-instability",
                "title": "Runtime instability signals detected",
                "severity": "error" if metrics["restart_count"] > 0 else "warning",
                "confidence": 92 if metrics["restart_count"] > 0 else 80,
                "summary": f"Error rate is {metrics['log_error_rate']:.2f}/min with {metrics['restart_count']} restart indicator(s).",
                "rationale": "Recent runtime signals suggest the container should be inspected through live logs and, if needed, escalated into an incident.",
                "evidence_refs": [f"metric:error-rate:{metrics['log_error_rate']}", f"metric:restarts:{metrics['restart_count']}"] + common_refs[:2],
                "actions": runtime_actions,
            }
        )

    if metrics["queue_depth"] >= 8:
        broker_target = next(
            (
                item
                for item in readiness.get("dependency_targets", [])
                if item["service_key"] in {"rabbitmq-core", "redis-core", "postgresql-core"}
            ),
            None,
        )
        insights.append(
            {
                "insight_id": "queue-pressure",
                "title": "Queue pressure is building",
                "severity": "warning",
                "confidence": 78,
                "summary": f"Queue depth is {metrics['queue_depth']} in the current {metrics['window']} telemetry window.",
                "rationale": "Higher queue depth often points to broker latency, blocked consumers, or a backing dependency that needs inspection.",
                "evidence_refs": [f"metric:queue-depth:{metrics['queue_depth']}"] + ([f"dependency:{broker_target['service_key']}"] if broker_target else []),
                "actions": [
                    {
                        "action_id": "focus-dependency-diagnostics" if broker_target else "open-live-logs",
                        "label": f"Inspect {broker_target['name']}" if broker_target else "Inspect service logs",
                        "description": "Open the dependency logs most likely to explain message backlog."
                        if broker_target
                        else "Review the current service logs for worker backpressure.",
                        "service_key": broker_target["service_key"] if broker_target else service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "diagnostics",
                        "recommended": True,
                    },
                    {
                        "action_id": "open-config",
                        "label": "Open config",
                        "description": "Review worker concurrency, broker, or retry settings in config manager.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "config",
                        "recommended": False,
                    },
                ],
            }
        )

    if metrics["cpu_percent"] >= 75 or metrics["memory_mb"] >= 900:
        insights.append(
            {
                "insight_id": "capacity-pressure",
                "title": "Short-window capacity pressure is elevated",
                "severity": "warning",
                "confidence": 70,
                "summary": f"CPU is {metrics['cpu_percent']}% and memory is {metrics['memory_mb']} MB in the active telemetry window.",
                "rationale": "Short-term pressure can precede restarts, latency spikes, or backlogs even when the service has not fully degraded yet.",
                "evidence_refs": [f"metric:cpu:{metrics['cpu_percent']}", f"metric:memory:{metrics['memory_mb']}"],
                "actions": [
                    {
                        "action_id": "open-live-logs",
                        "label": "Correlate with logs",
                        "description": "Check whether utilization spikes align with warnings or errors in the live stream.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "tail",
                        "recommended": True,
                    }
                ],
            }
        )

    if not readiness["backfill_requirements"]["ready"]:
        missing = readiness["backfill_requirements"]["missing"]
        config_runbook_key = _recommended_runbook_for_diagnostics_context(
            dependency_missing=dependency["missing"],
            dependency_stopped=dependency["stopped"],
            drift_status=latest_drift.status if latest_drift else None,
            drift_fields=drift_fields,
            latest_release=latest_release,
            metrics=metrics,
        )
        insights.append(
            {
                "insight_id": "file-log-readiness",
                "title": "File-log backfill is not fully ready",
                "severity": "warning",
                "confidence": 68,
                "summary": f"Backfill is waiting on: {', '.join(missing) if missing else 'additional readiness checks'}.",
                "rationale": "Without file-log readiness, historical investigations and Loki backfill parity remain incomplete for this target.",
                "evidence_refs": [f"backfill-missing:{item}" for item in missing] or ["backfill:unready"],
                "actions": [
                    {
                        "action_id": "open-config",
                        "label": "Open config manager",
                        "description": "Review mounted log paths and file-based logging configuration.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "config",
                        "recommended": not readiness["configurable"],
                    },
                    {
                        "action_id": "focus-file-logs",
                        "label": "Review file logs",
                        "description": "Inspect archive paths and readability checks in diagnostics.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "files",
                        "recommended": True,
                    },
                    {
                        "action_id": "run-incident-runbook" if open_incidents else "open-incident",
                        "label": (
                            "Run config rollback"
                            if open_incidents and config_runbook_key == "config-rollback"
                            else f"Run {config_runbook_key} runbook"
                            if open_incidents
                            else "Open config incident"
                        ),
                        "description": "Use the config rollback runbook if recent config or log-path changes likely caused the issue."
                        if open_incidents
                        else "Create an incident before rolling back config-related changes.",
                        "service_key": source.service_key,
                        "incident_id": open_incidents[0].id if open_incidents else None,
                        "runbook_key": config_runbook_key if open_incidents else None,
                        "target_view": "monitoring",
                        "recommended": False,
                    },
                ],
            }
        )

    if latest_slo and latest_slo.status == "burning":
        insights.append(
            {
                "insight_id": "slo-burn",
                "title": "SLO burn is active",
                "severity": "error",
                "confidence": 94,
                "summary": f"{latest_slo.name} is currently burning with observed value {latest_slo.observed}.",
                "rationale": "SLO burn means this issue is already affecting reliability objectives and should be treated as an active operational concern.",
                "evidence_refs": [f"slo:{latest_slo.name}", f"slo-observed:{latest_slo.observed}"] + common_refs[:1],
                "actions": [
                    {
                        "action_id": "open-existing-incident" if open_incidents else "open-incident",
                        "label": f"Review incident #{open_incidents[0].id}" if open_incidents else "Open incident",
                        "description": "Track mitigation against the active SLO burn.",
                        "service_key": source.service_key,
                        "incident_id": open_incidents[0].id if open_incidents else None,
                        "runbook_key": None,
                        "target_view": "monitoring",
                        "recommended": True,
                    }
                ],
            }
        )

    if latest_release is not None and (metrics["log_error_rate"] >= 0.4 or metrics["restart_count"] > 0):
        insights.append(
            {
                "insight_id": "release-correlation",
                "title": "Recent release may correlate with current instability",
                "severity": "warning",
                "confidence": 76,
                "summary": f"Version {latest_release.version} is the most recent release on this service context.",
                "rationale": "When symptoms begin after a new release, image changes and deployment strategy are often the fastest explanation to confirm or rule out.",
                "evidence_refs": [f"release:{latest_release.version}", f"release-image:{latest_release.image}"],
                "actions": [
                    {
                        "action_id": "open-release-context",
                        "label": "Review release timeline",
                        "description": "Inspect the latest release and correlated change events in the service cockpit.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "clusters",
                        "recommended": True,
                    }
                ],
            }
        )

    if latest_drift is not None and latest_drift.status == "drifted":
        drift_runbook_key = _recommended_runbook_for_diagnostics_context(
            dependency_missing=dependency["missing"],
            dependency_stopped=dependency["stopped"],
            drift_status=latest_drift.status if latest_drift else None,
            drift_fields=drift_fields,
            latest_release=latest_release,
            metrics=metrics,
        )
        insights.append(
            {
                "insight_id": "drift-correlation",
                "title": "Config drift is a plausible cause",
                "severity": "warning",
                "confidence": 88 if drift_fields else 74,
                "summary": "The latest drift check reported differences from the baseline snapshot.",
                "rationale": "When runtime state drifts from the saved baseline, rollback or config review can often resolve the issue faster than repeated restarts.",
                "evidence_refs": [f"drift:{latest_drift.status}"] + [f"drift-field:{field}" for field in drift_fields[:3]],
                "actions": [
                    {
                        "action_id": "open-config",
                        "label": "Inspect config workspace",
                        "description": "Open config manager and compare current configuration with recent snapshots.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "config",
                        "recommended": True,
                    },
                    {
                        "action_id": "run-incident-runbook" if open_incidents else "open-incident",
                        "label": (
                            "Run config rollback"
                            if open_incidents and drift_runbook_key == "config-rollback"
                            else f"Run {drift_runbook_key} runbook"
                            if open_incidents
                            else "Open rollback incident"
                        ),
                        "description": "Use the config rollback runbook if drift is the most likely cause."
                        if open_incidents
                        else "Create an incident before executing config rollback steps.",
                        "service_key": source.service_key,
                        "incident_id": open_incidents[0].id if open_incidents else None,
                        "runbook_key": drift_runbook_key if open_incidents else None,
                        "target_view": "monitoring",
                        "recommended": False,
                    },
                ],
            }
        )

    if latest_monitoring and latest_monitoring.status == "warning":
        insights.append(
            {
                "insight_id": "monitoring-warning",
                "title": "Latest monitoring sweep reported warning state",
                "severity": "warning",
                "confidence": 64,
                "summary": f"{latest_monitoring.name}: {latest_monitoring.value}.",
                "rationale": latest_monitoring.detail or "The latest monitoring check flagged this target for follow-up.",
                "evidence_refs": [f"monitoring:{latest_monitoring.name}", f"monitoring-value:{latest_monitoring.value}"],
                "actions": [
                    {
                        "action_id": "open-live-logs",
                        "label": "Inspect live tail",
                        "description": "Correlate the warning check with recent runtime output.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "tail",
                        "recommended": True,
                    }
                ],
            }
        )

    if open_incidents:
        insights.append(
            {
                "insight_id": "active-incidents",
                "title": "There is already an active incident for this service context",
                "severity": "warning",
                "confidence": 62,
                "summary": f"{len(open_incidents)} open incident(s) are attached to {source.name}.",
                "rationale": "Continue remediation inside the active incident flow so logs, runbooks, and follow-up stay correlated.",
                "evidence_refs": [f"incident:{item.id}" for item in open_incidents[:3]],
                "actions": [
                    {
                        "action_id": "open-existing-incident",
                        "label": f"Review incident #{open_incidents[0].id}",
                        "description": "Open the incident workflow and continue with tracked remediation.",
                        "service_key": source.service_key,
                        "incident_id": open_incidents[0].id,
                        "runbook_key": None,
                        "target_view": "monitoring",
                        "recommended": True,
                    }
                ],
            }
        )

    if not insights:
        insights.append(
            {
                "insight_id": "healthy",
                "title": "No high-risk diagnostics signals detected",
                "severity": "info",
                "confidence": 52,
                "summary": f"{service.name} looks stable across dependency, metrics, and logging readiness checks.",
                "rationale": "This target has healthy dependency state, no material error-rate signal, and no active warning indicators in the latest checks.",
                "evidence_refs": ["state:healthy"],
                "actions": [
                    {
                        "action_id": "open-live-logs",
                        "label": "Watch live tail",
                        "description": "Keep the live console open while validating a deployment or traffic change.",
                        "service_key": service.service_key,
                        "incident_id": None,
                        "runbook_key": None,
                        "target_view": "tail",
                        "recommended": True,
                    }
                ],
            }
        )

    for insight in insights:
        insight["supporting_evidence"] = [resolve_supporting_evidence(ref) for ref in insight.get("evidence_refs", [])[:4]]

    severity_rank = {"info": 0, "warning": 1, "error": 2}
    insights.sort(key=lambda item: (-int(item.get("confidence", 0)), -severity_rank.get(item["severity"], 0), item["title"]))
    overall_severity = max((item["severity"] for item in insights), key=lambda item: severity_rank.get(item, 0))
    next_steps: list[str] = []
    for insight in insights:
        for action in insight["actions"]:
            if action["recommended"] and action["label"] not in next_steps:
                next_steps.append(action["label"])

    return {
        "service_id": service.id,
        "service_name": service.name,
        "source_service_id": source.id,
        "source_service_name": source.name,
        "source_service_key": source.service_key,
        "target_service_key": service.service_key,
        "target_name": service.name,
        "overall_severity": overall_severity,
        "overview": f"{service.name} diagnostics analysis generated from live readiness, 15m service telemetry, and current operational state.",
        "next_steps": next_steps[:5],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "recent_incidents": recent_incident_summaries,
        "historical_correlation": historical_correlation[:5],
        "change_evidence": change_evidence[:8],
        "insights": insights,
    }


def index_log_archives(db: Session, service: ServiceInstance) -> list[LogArchive]:
    contract = json.loads(service.config_json or "{}")
    log_paths = contract.get("log_paths", [])
    existing = list(db.scalars(select(LogArchive).where(LogArchive.service_id == service.id)).all())
    for archive in existing:
        db.delete(archive)
    db.commit()

    archives: list[LogArchive] = []
    for index, path in enumerate(log_paths, start=1):
        archive = LogArchive(
            service_id=service.id,
            path=f"{path.rstrip('/')}/{service.service_key}-{index}.log",
            size_bytes=2048 * index if settings.local_mode else 0,
            line_count=150 * index if settings.local_mode else 0,
            readable="yes" if settings.local_mode else "unknown",
            reason="simulated local archive index" if settings.local_mode else "requires remote sudo scan",
        )
        db.add(archive)
        archives.append(archive)
    db.commit()
    for archive in archives:
        db.refresh(archive)
    record_event(
        db,
        category="diagnostics",
        level="info",
        message=f"Indexed {len(archives)} log archives for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"archives": len(archives)},
    )
    return archives


def backfill_service_logs(db: Session, service: ServiceInstance) -> dict[str, Any]:
    diagnostics = service_diagnostics(db, service)
    requirements = diagnostics["readiness"].get("backfill_requirements", {})
    command = f"{_ansible_base_command(service.node, 'service_log_backfill.yml')} --extra-vars service={service.service_key}"
    job = create_job(db, action="log-backfill", command=command, service_id=service.id, node_id=service.node_id)
    ready = bool(requirements.get("ready"))
    output = (
        f"Backfilled file logs for {service.container_name} into {requirements.get('loki_url', 'configured Loki')}."
        if ready
        else f"Backfill not ready: {', '.join(requirements.get('missing', [])) or 'requirements incomplete'}."
    )
    finished = finish_job(db, job, ok=ready, output=output, error="" if ready else output)
    record_event(
        db,
        category="diagnostics",
        level="info" if ready else "warning",
        message=f"Log backfill {'completed' if ready else 'blocked'} for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"ready": ready, "missing": requirements.get("missing", [])},
    )
    return {
        "service_id": service.id,
        "ready": ready,
        "requirements": requirements,
        "job": finished,
        "summary": output,
    }


def record_event(
    db: Session,
    *,
    category: str,
    message: str,
    level: str = "info",
    service_id: int | None = None,
    node_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> OperationalEvent:
    event = OperationalEvent(
        category=category,
        level=level,
        message=message,
        service_id=service_id,
        node_id=node_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    *,
    limit: int = 100,
    category: str | None = None,
    level: str | None = None,
    node_id: int | None = None,
    service_id: int | None = None,
    search: str | None = None,
) -> list[OperationalEvent]:
    statement = select(OperationalEvent).order_by(OperationalEvent.created_at.desc()).limit(limit)
    if category:
        statement = statement.where(OperationalEvent.category == category)
    if level:
        statement = statement.where(OperationalEvent.level == level)
    if node_id is not None:
        statement = statement.where(OperationalEvent.node_id == node_id)
    if service_id is not None:
        statement = statement.where(OperationalEvent.service_id == service_id)
    if search:
        statement = statement.where(OperationalEvent.message.ilike(f"%{search}%"))
    return list(db.scalars(statement).all())


def get_node_job_history(db: Session, node_id: int, *, limit: int = 12) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")
    jobs = list(
        db.scalars(
            select(DeploymentJob)
            .where(DeploymentJob.node_id == node_id)
            .order_by(DeploymentJob.created_at.desc())
            .limit(limit)
        ).all()
    )
    all_jobs = list(db.scalars(select(DeploymentJob).where(DeploymentJob.node_id == node_id)).all())
    service_map = {
        service.id: service
        for service in db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node_id)).all()
    }
    deployment_jobs = 0
    config_jobs = 0
    validation_jobs = 0
    failed_jobs = 0
    for job in all_jobs:
        if job.status == JobStatus.failed.value:
            failed_jobs += 1
        if "config" in job.action:
            config_jobs += 1
        elif "validate" in job.action:
            validation_jobs += 1
        else:
            deployment_jobs += 1
    items: list[dict[str, Any]] = []
    for job in jobs:
        service = service_map.get(job.service_id) if job.service_id else None
        items.append(
            {
                "id": job.id,
                "action": job.action,
                "status": job.status,
                "command": job.command,
                "output": job.output,
                "error": job.error,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "ended_at": job.ended_at,
                "service_id": service.id if service else None,
                "service_name": service.name if service else None,
                "service_key": service.service_key if service else None,
            }
        )
    return {
        "node_id": node.id,
        "node_name": node.name,
        "total_jobs": len(all_jobs),
        "deployment_jobs": deployment_jobs,
        "config_jobs": config_jobs,
        "validation_jobs": validation_jobs,
        "failed_jobs": failed_jobs,
        "items": items,
    }


def _infer_config_action(message: str, metadata: dict[str, Any]) -> str:
    action = metadata.get("action")
    if isinstance(action, str) and action.strip():
        return action.strip().lower()
    text = (message or "").lower()
    if "renamed" in text:
        return "renamed"
    if "restored" in text:
        return "restored"
    if "apply" in text:
        return "applied"
    return "captured"


def _parse_iso_datetime(value: str) -> datetime | None:
    trimmed = (value or "").strip()
    if not trimmed:
        return None
    candidate = trimmed.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def get_config_timeline_page(
    db: Session,
    service: ServiceInstance,
    *,
    limit: int = 20,
    offset: int = 0,
    action_filter: str = "all",
    actor_filter: str = "all",
    search: str = "",
    created_after: str = "",
    created_before: str = "",
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    search_term = search.strip()
    action_value = action_filter.strip().lower() or "all"
    actor_value = actor_filter.strip().lower() or "all"
    created_after_dt = _parse_iso_datetime(created_after)
    created_before_dt = _parse_iso_datetime(created_before)

    statement = select(OperationalEvent).where(
        OperationalEvent.category == "config",
        OperationalEvent.service_id == service.id,
    )
    if search_term:
        statement = statement.where(OperationalEvent.message.ilike(f"%{search_term}%"))
    if created_after_dt is not None:
        statement = statement.where(OperationalEvent.created_at >= created_after_dt)
    if created_before_dt is not None:
        statement = statement.where(OperationalEvent.created_at <= created_before_dt)

    base_events = list(db.scalars(statement.order_by(OperationalEvent.created_at.desc())).all())
    enriched: list[dict[str, Any]] = []
    actions: set[str] = set()
    actors: set[str] = set()
    for event in base_events:
        try:
            metadata = json.loads(event.metadata_json or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except json.JSONDecodeError:
            metadata = {}
        action = _infer_config_action(event.message, metadata)
        actor = str(metadata.get("actor") or "platform-operator")
        actions.add(action)
        actors.add(actor)
        enriched.append(
            {
                "id": event.id,
                "service_id": event.service_id,
                "node_id": event.node_id,
                "level": (event.level or "info").lower(),
                "message": event.message,
                "action": action,
                "actor": actor,
                "metadata": metadata,
                "created_at": event.created_at.isoformat() if event.created_at else datetime.utcnow().isoformat() + "Z",
            }
        )

    filtered = [
        item
        for item in enriched
        if (action_value == "all" or item["action"] == action_value)
        and (actor_value == "all" or item["actor"].lower() == actor_value)
    ]
    total = len(filtered)
    items = filtered[safe_offset : safe_offset + safe_limit]
    return {
        "service_id": service.id,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(items) < total,
        "action_filter": action_value,
        "actor_filter": actor_filter.strip() or "all",
        "search": search_term,
        "created_after": created_after.strip(),
        "created_before": created_before.strip(),
        "available_actions": sorted(actions),
        "available_actors": sorted(actors),
        "items": items,
    }


def get_config_snapshot_detail(db: Session, snapshot: ConfigSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "service_id": snapshot.service_id,
        "version": snapshot.version,
        "name": snapshot.name,
        "source": snapshot.source,
        "created_at": snapshot.created_at,
        "content": snapshot.content,
    }


def compare_config_snapshots(
    db: Session,
    service: ServiceInstance,
    *,
    left_snapshot: ConfigSnapshot,
    right_snapshot: ConfigSnapshot,
) -> dict[str, Any]:
    if left_snapshot.service_id != service.id or right_snapshot.service_id != service.id:
        raise ValueError("Both snapshots must belong to the selected service.")

    left_raw = yaml.safe_load(left_snapshot.content) or {}
    right_raw = yaml.safe_load(right_snapshot.content) or {}
    left = left_raw if isinstance(left_raw, dict) else {"content": left_raw}
    right = right_raw if isinstance(right_raw, dict) else {"content": right_raw}

    differences: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right)):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value != right_value:
            differences.append(
                {
                    "field": key,
                    "expected": left_value,
                    "actual": right_value,
                    "severity": "warning",
                }
            )

    summary = (
        f"Found {len(differences)} differing field(s) between v{left_snapshot.version} and v{right_snapshot.version}."
        if differences
        else f"Snapshots v{left_snapshot.version} and v{right_snapshot.version} are identical."
    )
    return {
        "service_id": service.id,
        "left_snapshot": get_config_snapshot_detail(db, left_snapshot),
        "right_snapshot": get_config_snapshot_detail(db, right_snapshot),
        "differences": differences,
        "difference_count": len(differences),
        "summary": summary,
    }


def capability_coverage_report(db: Session) -> dict[str, Any]:
    catalog = service_catalog()
    items: list[dict[str, Any]] = []
    diagnostics_ready = 0
    config_ready = 0
    backup_ready = 0
    policy_risk_services = 0
    issues_count = 0

    for service_key in sorted(catalog.keys()):
        contract = get_service_contract(service_key)
        kind = contract.get("kind", "app")
        subsystem = contract.get("subsystem", "uncategorized")
        tags = contract.get("tags", [])
        log_paths = contract.get("log_paths", [])
        config_files = contract.get("config_files", [])
        stateful = "stateful" in tags
        has_backup = "backup" in contract
        has_environment = bool(contract.get("environment"))
        has_runtime_surface = bool(contract.get("volumes") or contract.get("ports") or contract.get("command"))

        diagnostics = kind == "infrastructure" or len(log_paths) > 0
        if config_files:
            config_mode = "explicit"
        elif has_environment or has_runtime_surface:
            config_mode = "generated"
        else:
            config_mode = "none"
        config = config_mode != "none"
        backup = has_backup or not stateful
        requires_sudo = kind == "infrastructure" and any(tag in tags for tag in ["infra", "stateful", "database"])

        issues: list[str] = []
        if kind in {"app", "infrastructure"} and not log_paths:
            issues.append("missing log_paths")
        if stateful and not has_backup:
            issues.append("stateful missing backup policy")
        if kind != "helper" and config_mode == "none":
            issues.append("no explicit or generated config surface")

        if diagnostics:
            diagnostics_ready += 1
        if config:
            config_ready += 1
        if backup:
            backup_ready += 1
        if issues:
            policy_risk_services += 1
            issues_count += len(issues)

        items.append(
            {
                "service_key": service_key,
                "kind": kind,
                "subsystem": subsystem,
                "diagnostics_ready": diagnostics,
                "config_ready": config,
                "config_mode": config_mode,
                "backup_ready": backup,
                "stateful": stateful,
                "requires_sudo_for_file_logs": requires_sudo,
                "issues": issues,
            }
        )

    return {
        "total_services": len(items),
        "diagnostics_ready": diagnostics_ready,
        "config_ready": config_ready,
        "backup_ready": backup_ready,
        "policy_risk_services": policy_risk_services,
        "issues_count": issues_count,
        "items": items,
    }


def lifecycle_audit_report(db: Session, *, hours: int = 72) -> dict[str, Any]:
    window_hours = max(1, min(hours, 720))
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    lifecycle_events = list(
        db.scalars(
            select(OperationalEvent)
            .where(OperationalEvent.category == "lifecycle", OperationalEvent.created_at >= cutoff)
            .order_by(OperationalEvent.created_at.desc())
        ).all()
    )

    blocked_deletions = 0
    forced_deletions = 0
    safe_deletions = 0
    last_blocked_at: str | None = None
    last_forced_at: str | None = None
    last_safe_delete_at: str | None = None

    for event in lifecycle_events:
        message = (event.message or "").lower()
        metadata = json.loads(event.metadata_json or "{}")
        is_blocked = "blocked" in message
        is_force = bool(metadata.get("force")) or "force deleted" in message or "despite warnings" in message
        is_delete = "deleted" in message

        if is_blocked:
            blocked_deletions += 1
            if last_blocked_at is None:
                last_blocked_at = event.created_at.isoformat()
            continue
        if is_force:
            forced_deletions += 1
            if last_forced_at is None:
                last_forced_at = event.created_at.isoformat()
            continue
        if is_delete:
            safe_deletions += 1
            if last_safe_delete_at is None:
                last_safe_delete_at = event.created_at.isoformat()

    return {
        "window_hours": window_hours,
        "total_lifecycle_events": len(lifecycle_events),
        "blocked_deletions": blocked_deletions,
        "forced_deletions": forced_deletions,
        "safe_deletions": safe_deletions,
        "last_blocked_at": last_blocked_at,
        "last_forced_at": last_forced_at,
        "last_safe_delete_at": last_safe_delete_at,
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


def run_backup(db: Session, service: ServiceInstance) -> BackupRun:
    contract = json.loads(service.config_json or "{}")
    backup_contract = contract.get("backup") or {
        "type": "volume-archive",
        "artifact_root": f"{service.node.volume_root}/backups/{service.service_key}",
    }
    artifact_root = backup_contract.get("artifact_root", f"{service.node.volume_root}/backups/{service.service_key}")
    artifact = f"{artifact_root.rstrip('/')}/{service.service_key}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.tar.gz"
    backup = BackupRun(
        service_id=service.id,
        status=JobStatus.running.value,
        strategy=backup_contract.get("type", "volume-archive"),
        artifact_path=artifact,
        output=f"Prepared backup strategy for {service.container_name}",
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)

    backup.status = JobStatus.success.value
    backup.completed_at = datetime.utcnow()
    backup.output = f"Simulated {backup.strategy} backup to {backup.artifact_path}"
    db.commit()
    db.refresh(backup)
    record_event(
        db,
        category="backup",
        level="info",
        message=f"Backup completed for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"strategy": backup.strategy, "artifact_path": backup.artifact_path},
    )
    return backup


def run_monitoring_sweep(db: Session) -> list[MonitoringCheck]:
    checks: list[MonitoringCheck] = []
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.name)).all())
    for service in services:
        contract = json.loads(service.config_json or "{}")
        health = contract.get("healthcheck", {})
        status = "ok" if service.status in RUNNING_STATUSES else "warning"
        check = MonitoringCheck(
            service_id=service.id,
            node_id=service.node_id,
            name=f"{service.service_key}-health",
            status=status,
            value=service.status,
            detail=health.get("command", "No healthcheck command configured"),
        )
        db.add(check)
        checks.append(check)

    db.commit()
    for check in checks:
        db.refresh(check)
    record_event(
        db,
        category="monitoring",
        level="info",
        message=f"Monitoring sweep recorded {len(checks)} checks",
        metadata={"checks": len(checks)},
    )
    return checks


def latest_monitoring_checks(db: Session, *, limit: int = 200) -> list[MonitoringCheck]:
    return list(db.scalars(select(MonitoringCheck).order_by(MonitoringCheck.created_at.desc()).limit(limit)).all())


def assess_release_safety(
    db: Session,
    service: ServiceInstance,
    *,
    version: str,
    image: str | None = None,
) -> dict[str, Any]:
    contract = get_service_contract(service.service_key)
    target_image = image or service.image
    tags = set(contract.get("tags", []))
    reasons: list[str] = []
    if service.kind == "infrastructure":
        reasons.append("Infrastructure cards require explicit approval before release.")
    if {"stateful", "database", "broker"} & tags:
        reasons.append("Stateful/data-plane cards need a controlled release approval.")
    if target_image != service.image:
        reasons.append("Target image differs from the currently running image.")
    risky = bool(reasons)
    severity = "high" if service.kind == "infrastructure" or {"stateful", "database"} & tags else "medium"
    recommended_action = (
        "Request and approve a release gate before deploying this change."
        if risky
        else "Safe to release directly."
    )
    return {
        "service_id": service.id,
        "service_name": service.name,
        "risky": risky,
        "severity": severity if risky else "low",
        "reasons": reasons,
        "recommended_action": recommended_action,
        "target_image": target_image,
        "target_version": version,
    }


def create_release_approval(
    db: Session,
    *,
    service: ServiceInstance,
    target_version: str,
    target_image: str,
    reason: str,
    requested_by: str = "platform-operator",
    ttl_hours: int = 4,
) -> ReleaseApproval:
    approval = ReleaseApproval(
        service_id=service.id,
        target_version=target_version,
        target_image=target_image,
        reason=reason,
        requested_by=requested_by,
        expires_at=datetime.utcnow() + timedelta(hours=max(1, ttl_hours)),
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    record_event(
        db,
        category="release-approval",
        level="warning",
        message=f"Requested release approval for {service.name} {target_version}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"release_approval_id": approval.id, "target_version": target_version, "target_image": target_image},
    )
    return approval


def latest_release_approvals(db: Session, *, service_id: int | None = None, limit: int = 100) -> list[ReleaseApproval]:
    statement = select(ReleaseApproval).order_by(ReleaseApproval.created_at.desc()).limit(limit)
    if service_id is not None:
        statement = statement.where(ReleaseApproval.service_id == service_id)
    approvals = list(db.scalars(statement).all())
    now = datetime.utcnow()
    expired_any = False
    for approval in approvals:
        if approval.status == "pending" and approval.expires_at and now > approval.expires_at:
            approval.status = "expired"
            expired_any = True
    if expired_any:
        db.commit()
    return approvals


def decide_release_approval(
    db: Session,
    approval: ReleaseApproval,
    *,
    approver: str,
    status: str = "approved",
    decision_note: str = "",
) -> ReleaseApproval:
    approval.approver = approver
    approval.decision_note = decision_note
    approval.status = status
    approval.approved_at = datetime.utcnow() if status == "approved" else approval.approved_at
    db.commit()
    db.refresh(approval)
    service = db.get(ServiceInstance, approval.service_id)
    record_event(
        db,
        category="release-approval",
        level="info" if status == "approved" else "warning",
        message=f"Release approval #{approval.id} marked {status}",
        service_id=approval.service_id,
        node_id=service.node_id if service else None,
        metadata={"release_approval_id": approval.id, "status": status},
    )
    return approval


def revoke_release_approval(db: Session, approval: ReleaseApproval, *, actor: str, note: str = "") -> ReleaseApproval:
    approval.status = "revoked"
    approval.decision_note = note
    approval.approver = actor
    db.commit()
    db.refresh(approval)
    service = db.get(ServiceInstance, approval.service_id)
    record_event(
        db,
        category="release-approval",
        level="warning",
        message=f"Release approval #{approval.id} revoked",
        service_id=approval.service_id,
        node_id=service.node_id if service else None,
        metadata={"release_approval_id": approval.id},
    )
    return approval


def validate_release_approval(
    db: Session,
    *,
    service: ServiceInstance,
    approval_id: int | None,
    target_version: str,
    target_image: str,
) -> dict[str, Any]:
    if approval_id is None:
        return {"allowed": False, "violations": ["Release approval is required for this change."]}
    approval = db.get(ReleaseApproval, approval_id)
    if approval is None:
        return {"allowed": False, "violations": [f"Release approval id {approval_id} was not found."]}
    if approval.service_id != service.id:
        return {"allowed": False, "approval": approval, "violations": ["Approval target does not match this service."]}
    if approval.used_at is not None or approval.status == "used":
        return {"allowed": False, "approval": approval, "violations": ["Approval has already been consumed."]}
    if approval.expires_at and datetime.utcnow() > approval.expires_at:
        approval.status = "expired"
        db.commit()
        return {"allowed": False, "approval": approval, "violations": ["Approval has expired."]}
    if approval.status != "approved":
        return {"allowed": False, "approval": approval, "violations": [f"Approval status is '{approval.status}', expected 'approved'."]}
    if approval.target_version != target_version or approval.target_image != target_image:
        return {"allowed": False, "approval": approval, "violations": ["Approval payload does not match the requested version/image."]}
    return {"allowed": True, "approval": approval, "violations": []}


def mark_release_approval_used(db: Session, approval: ReleaseApproval) -> ReleaseApproval:
    approval.status = "used"
    approval.used_at = datetime.utcnow()
    db.commit()
    db.refresh(approval)
    return approval


def create_release(
    db: Session,
    service: ServiceInstance,
    *,
    version: str,
    image: str | None = None,
    strategy: str = "rolling",
    notes: str = "",
    approval_id: int | None = None,
) -> ReleaseRecord:
    safety = assess_release_safety(db, service, version=version, image=image)
    target_image = safety["target_image"]
    if safety["risky"]:
        approval_check = validate_release_approval(
            db,
            service=service,
            approval_id=approval_id,
            target_version=version,
            target_image=target_image,
        )
        if not approval_check["allowed"]:
            blocked = {
                "service_id": service.id,
                "service_name": service.name,
                "risky": True,
                "severity": safety["severity"],
                "reasons": safety["reasons"] + approval_check["violations"],
                "recommended_action": "Request and approve a release gate, then retry the deployment.",
            }
            raise PermissionError(json.dumps(blocked))
    release = ReleaseRecord(
        service_id=service.id,
        version=version,
        image=target_image,
        status=JobStatus.running.value,
        strategy=strategy,
        notes=notes,
        previous_image=service.image,
    )
    db.add(release)
    db.commit()
    db.refresh(release)

    service.image = target_image
    service.status = "running"
    release.status = JobStatus.success.value
    release.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(release)
    record_event(
        db,
        category="release",
        level="info",
        message=f"Released {service.name} version {version}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"version": version, "image": target_image, "strategy": strategy},
    )
    if safety["risky"] and approval_id is not None:
        approval = db.get(ReleaseApproval, approval_id)
        if approval is not None:
            mark_release_approval_used(db, approval)
    return release


def rollback_release(db: Session, release: ReleaseRecord) -> DeploymentJob:
    service = db.get(ServiceInstance, release.service_id)
    if service is None:
        raise ValueError("Release service no longer exists.")
    service.image = release.previous_image or service.image
    service.status = "running"
    command = f"rollback {service.container_name} to {service.image}"
    job = create_job(db, action="rollback-release", command=command, service_id=service.id, node_id=service.node_id)
    completed = finish_job(db, job, ok=True, output=f"Rolled back {service.name} to {service.image}.")
    record_event(
        db,
        category="release",
        level="warning",
        message=f"Rolled back release {release.version} for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"release_id": release.id, "image": service.image},
    )
    return completed


def list_releases(db: Session, service: ServiceInstance | None = None, *, limit: int = 100) -> list[ReleaseRecord]:
    statement = select(ReleaseRecord).order_by(ReleaseRecord.created_at.desc()).limit(limit)
    if service is not None:
        statement = statement.where(ReleaseRecord.service_id == service.id)
    return list(db.scalars(statement).all())


def detect_drift(db: Session, service: ServiceInstance) -> DriftReport:
    latest_snapshot = db.scalar(
        select(ConfigSnapshot)
        .where(ConfigSnapshot.service_id == service.id)
        .order_by(ConfigSnapshot.version.desc())
        .limit(1)
    )
    current = current_config(service)
    differences: list[dict[str, Any]] = []
    if latest_snapshot is None:
        differences.append(
            {
                "field": "baseline",
                "expected": "snapshot",
                "actual": "missing",
                "severity": "warning",
            }
        )
    elif latest_snapshot.content != current:
        expected = yaml.safe_load(latest_snapshot.content) or {}
        actual = yaml.safe_load(current) or {}
        for key in sorted(set(expected) | set(actual)):
            if expected.get(key) != actual.get(key):
                differences.append(
                    {
                        "field": key,
                        "expected": expected.get(key),
                        "actual": actual.get(key),
                        "severity": "warning",
                    }
                )

    report = DriftReport(
        service_id=service.id,
        status="drifted" if differences else "in-sync",
        baseline_snapshot_id=latest_snapshot.id if latest_snapshot else None,
        differences_json=json.dumps(differences),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    record_event(
        db,
        category="drift",
        level="warning" if differences else "info",
        message=f"Drift check for {service.name}: {report.status}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"differences": len(differences)},
    )
    return report


def run_policy_scan(db: Session) -> list[PolicyFinding]:
    existing = list(db.scalars(select(PolicyFinding).where(PolicyFinding.status == "open")).all())
    for finding in existing:
        finding.status = "superseded"
    db.commit()

    findings: list[PolicyFinding] = []
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.service_key)).all())
    for service in services:
        contract = json.loads(service.config_json or "{}")
        dependencies = dependency_preflight(db, service)
        if not dependencies["ok"]:
            findings.append(
                PolicyFinding(
                    service_id=service.id,
                    node_id=service.node_id,
                    rule_id="dependency-preflight",
                    severity="high",
                    message=f"{service.name} has unresolved dependency requirements.",
                    remediation=dependencies["message"],
                )
            )
        if service.kind in {"app", "infrastructure"} and not contract.get("log_paths"):
            findings.append(
                PolicyFinding(
                    service_id=service.id,
                    node_id=service.node_id,
                    rule_id="log-path-required",
                    severity="medium",
                    message=f"{service.name} has no file log paths configured.",
                    remediation="Add log_paths to the service catalog so diagnostics and archive scans work.",
                )
            )
        if service.kind == "infrastructure" and contract.get("ports"):
            findings.append(
                PolicyFinding(
                    service_id=service.id,
                    node_id=service.node_id,
                    rule_id="infra-external-port-review",
                    severity="medium",
                    message=f"{service.name} exposes host ports: {', '.join(contract.get('ports', []))}.",
                    remediation="Prefer internal-only infrastructure ports unless this is an intentional UI endpoint.",
                )
            )
        if service.kind == "infrastructure" and not contract.get("backup") and "stateful" in contract.get("tags", []):
            findings.append(
                PolicyFinding(
                    service_id=service.id,
                    node_id=service.node_id,
                    rule_id="stateful-backup-required",
                    severity="high",
                    message=f"{service.name} is stateful but has no backup strategy.",
                    remediation="Add a backup block with strategy and artifact root.",
                )
            )
        if contract.get("config_files") and not contract.get("volumes"):
            findings.append(
                PolicyFinding(
                    service_id=service.id,
                    node_id=service.node_id,
                    rule_id="config-volume-required",
                    severity="medium",
                    message=f"{service.name} has config files but no mounted volumes.",
                    remediation="Mount config files/directories into the container contract.",
                )
            )

    for finding in findings:
        db.add(finding)
    db.commit()
    for finding in findings:
        db.refresh(finding)
    record_event(
        db,
        category="policy",
        level="warning" if findings else "info",
        message=f"Policy scan completed with {len(findings)} open findings",
        metadata={"findings": len(findings)},
    )
    return findings


def latest_policy_findings(db: Session, *, limit: int = 200) -> list[PolicyFinding]:
    return list(
        db.scalars(
            select(PolicyFinding)
            .where(PolicyFinding.status == "open")
            .order_by(PolicyFinding.created_at.desc())
            .limit(limit)
        ).all()
    )


RUNBOOK_LIBRARY: dict[str, list[str]] = {
    "restart-service": [
        "Collect recent diagnostics and log archive metadata.",
        "Validate dependency preflight and container status.",
        "Restart or redeploy the selected service card.",
        "Run monitoring sweep and update incident status.",
    ],
    "dependency-recovery": [
        "Generate dependency deployment plan.",
        "Start missing or stopped infrastructure cards.",
        "Re-run application preflight.",
        "Attach plan and policy findings to the incident.",
    ],
    "config-rollback": [
        "Detect drift against the latest config snapshot.",
        "Restore known-good snapshot through config apply workflow.",
        "Validate YAML and run service diagnostics.",
        "Record rollback evidence in the event feed.",
    ],
}


def create_incident(
    db: Session,
    *,
    title: str,
    severity: str = "sev3",
    summary: str = "",
    service: ServiceInstance | None = None,
    node: Node | None = None,
) -> IncidentRecord:
    incident = IncidentRecord(
        service_id=service.id if service else None,
        node_id=node.id if node else service.node_id if service else None,
        title=title,
        severity=severity,
        summary=summary,
        remediation="Run an appropriate PlatformOps runbook and re-check SLO/policy state.",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    record_event(
        db,
        category="incident",
        level="error" if severity in {"sev1", "sev2"} else "warning",
        message=f"Opened incident {incident.title}",
        service_id=incident.service_id,
        node_id=incident.node_id,
        metadata={"incident_id": incident.id, "severity": severity},
    )
    return incident


def resolve_incident(db: Session, incident: IncidentRecord) -> IncidentRecord:
    incident.status = "resolved"
    incident.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)
    record_event(
        db,
        category="incident",
        level="info",
        message=f"Resolved incident {incident.title}",
        service_id=incident.service_id,
        node_id=incident.node_id,
        metadata={"incident_id": incident.id},
    )
    return incident


def latest_incidents(db: Session, *, limit: int = 100) -> list[IncidentRecord]:
    return list(db.scalars(select(IncidentRecord).order_by(IncidentRecord.created_at.desc()).limit(limit)).all())


def execute_runbook(
    db: Session,
    *,
    runbook_key: str,
    incident: IncidentRecord | None = None,
    service: ServiceInstance | None = None,
    node: Node | None = None,
) -> RunbookExecution:
    steps = RUNBOOK_LIBRARY.get(runbook_key)
    if not steps:
        raise ValueError(f"Unknown runbook key: {runbook_key}")
    execution = RunbookExecution(
        incident_id=incident.id if incident else None,
        service_id=service.id if service else incident.service_id if incident else None,
        node_id=node.id if node else incident.node_id if incident else service.node_id if service else None,
        runbook_key=runbook_key,
        status=JobStatus.running.value,
        steps_json=json.dumps(
            [{"order": index + 1, "step": step, "status": "success"} for index, step in enumerate(steps)]
        ),
        output=f"Simulated runbook {runbook_key} completed {len(steps)} steps.",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    execution.status = JobStatus.success.value
    execution.completed_at = datetime.utcnow()
    if incident:
        incident.remediation = f"Runbook {runbook_key} executed successfully."
    db.commit()
    db.refresh(execution)
    record_event(
        db,
        category="runbook",
        level="info",
        message=f"Executed runbook {runbook_key}",
        service_id=execution.service_id,
        node_id=execution.node_id,
        metadata={"runbook_execution_id": execution.id},
    )
    return execution


def latest_runbook_executions(db: Session, *, limit: int = 100) -> list[RunbookExecution]:
    return list(db.scalars(select(RunbookExecution).order_by(RunbookExecution.created_at.desc()).limit(limit)).all())


def evaluate_slos(db: Session) -> list[SloReport]:
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.service_key)).all())
    reports: list[SloReport] = []
    for service in services:
        contract = json.loads(service.config_json or "{}")
        dependency_state = dependency_preflight(db, service)
        is_ready = service.status in RUNNING_STATUSES and dependency_state["ok"]
        observed = "99.95" if is_ready else "97.50"
        report = SloReport(
            service_id=service.id,
            node_id=service.node_id,
            name=f"{service.service_key}-availability",
            target="99.90" if service.kind == "app" else "99.50",
            observed=observed,
            status="passing" if float(observed) >= (99.90 if service.kind == "app" else 99.50) else "burning",
            detail=f"status={service.status}; dependencies_ok={dependency_state['ok']}; subsystem={contract.get('subsystem', 'uncategorized')}",
        )
        db.add(report)
        reports.append(report)
    db.commit()
    for report in reports:
        db.refresh(report)
    record_event(
        db,
        category="slo",
        level="warning" if any(report.status == "burning" for report in reports) else "info",
        message=f"SLO evaluation completed for {len(reports)} services",
        metadata={"reports": len(reports)},
    )
    return reports


def latest_slo_reports(db: Session, *, limit: int = 200) -> list[SloReport]:
    return list(db.scalars(select(SloReport).order_by(SloReport.created_at.desc()).limit(limit)).all())


def _capacity_weights_for_kind(kind: str) -> tuple[float, int, int]:
    if kind == "infrastructure":
        return (0.35, 768, 8)
    if kind == "helper":
        return (0.15, 256, 1)
    return (0.25, 512, 2)


def _project_node_capacity(db: Session, node: Node, target_kind: str) -> dict[str, Any]:
    running = [
        service
        for service in db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all()
        if service.status in RUNNING_STATUSES
    ]
    cpu_reserved = 0.0
    memory_reserved = 0
    storage_reserved = 0
    for service in running:
        cpu_w, mem_w, storage_w = _capacity_weights_for_kind(service.kind)
        cpu_reserved += cpu_w
        memory_reserved += mem_w
        storage_reserved += storage_w

    add_cpu, add_mem, add_storage = _capacity_weights_for_kind(target_kind)
    projected_cpu = round(cpu_reserved + add_cpu, 2)
    projected_memory = memory_reserved + add_mem
    projected_storage = storage_reserved + add_storage
    capacity_status = "risk" if projected_memory > 24576 or projected_storage > 256 else "ok"
    return {
        "projected_cpu": projected_cpu,
        "projected_memory_mb": projected_memory,
        "projected_storage_gb": projected_storage,
        "capacity_status": capacity_status,
    }


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


def observability_pipeline_report(db: Session) -> dict[str, Any]:
    catalog = observability_catalog()
    defaults = catalog.get("defaults", {})
    labels = catalog.get("labels", {})
    source_switches = catalog.get("sources", {})
    now = datetime.utcnow().isoformat() + "Z"
    nodes = list(db.scalars(select(Node).order_by(Node.created_at.asc())).all())
    report_nodes: list[dict[str, Any]] = []
    for node in nodes:
        services = list(db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all())
        by_key = {service.service_key: service for service in services}
        required_keys = ["alloy-core", "loki-core", "prometheus-core", "node-exporter"]
        optional_keys = ["dcgm-exporter"]
        component_status: dict[str, str] = {}
        issues: list[str] = []
        for key in required_keys + optional_keys:
            service = by_key.get(key)
            if service is None:
                component_status[key] = "missing"
            elif service.status in RUNNING_STATUSES:
                component_status[key] = "running"
            else:
                component_status[key] = service.status
        for key in required_keys:
            if component_status[key] != "running":
                issues.append(f"{key} is {component_status[key]}")

        diagnostics_events = list(
            db.scalars(
                select(OperationalEvent)
                .where(
                    OperationalEvent.node_id == node.id,
                    OperationalEvent.category.in_(("diagnostics", "monitoring")),
                )
                .order_by(OperationalEvent.created_at.desc())
                .limit(1)
            ).all()
        )
        last_signal_at = diagnostics_events[0].created_at.isoformat() if diagnostics_events else None
        ingestion_state = "healthy" if not issues else "degraded"
        if all(component_status[key] == "missing" for key in required_keys):
            ingestion_state = "not-initialized"
        report_nodes.append(
            {
                "node_id": node.id,
                "node_name": node.name,
                "node_status": node.status,
                "pipeline_ready": len(issues) == 0,
                "ingestion_state": ingestion_state,
                "last_signal_at": last_signal_at,
                "components": component_status,
                "issues": issues,
            }
        )
    healthy_nodes = sum(1 for item in report_nodes if item["pipeline_ready"])
    return {
        "generated_at": now,
        "defaults": {
            "poll_interval_ms": defaults.get("poll_interval_ms", 2500),
            "tail_lines": defaults.get("tail_lines", 250),
            "history_page_size": defaults.get("history_page_size", 250),
            "archive_page_size": defaults.get("archive_page_size", 10),
            "loki_url": defaults.get("loki_url", "http://localhost:3100"),
        },
        "labels": labels,
        "sources": source_switches,
        "nodes": report_nodes,
        "summary": {
            "total_nodes": len(report_nodes),
            "healthy_nodes": healthy_nodes,
            "degraded_nodes": max(0, len(report_nodes) - healthy_nodes),
        },
    }


def bootstrap_observability_plane(db: Session, node_id: int) -> dict[str, Any]:
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


def generate_capacity_report(db: Session, node: Node) -> CapacityReport:
    services = list(db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all())
    running = [service for service in services if service.status in RUNNING_STATUSES]
    infra_count = sum(1 for service in running if service.kind == "infrastructure")
    app_count = sum(1 for service in running if service.kind == "app")
    helper_count = sum(1 for service in running if service.kind == "helper")
    memory_reserved = infra_count * 768 + app_count * 512 + helper_count * 256
    storage_reserved = infra_count * 8 + app_count * 2 + helper_count
    cpu_reserved = round(infra_count * 0.35 + app_count * 0.25 + helper_count * 0.15, 2)
    status = "risk" if memory_reserved > 24576 or storage_reserved > 256 else "ok"
    detail = {
        "running": len(running),
        "infrastructure": infra_count,
        "applications": app_count,
        "helpers": helper_count,
        "assumption": "local simulation estimates; remote mode can replace this with node facts and cgroup metrics",
    }
    report = CapacityReport(
        node_id=node.id,
        status=status,
        cpu_reserved=str(cpu_reserved),
        memory_reserved_mb=memory_reserved,
        storage_reserved_gb=storage_reserved,
        detail_json=json.dumps(detail),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    record_event(
        db,
        category="capacity",
        level="warning" if status == "risk" else "info",
        message=f"Capacity report for {node.name}: {status}",
        node_id=node.id,
        metadata=detail,
    )
    return report


METRIC_WINDOW_PRESETS: dict[str, dict[str, int]] = {
    "15m": {"points": 6, "step_minutes": 3},
    "1h": {"points": 8, "step_minutes": 8},
    "24h": {"points": 12, "step_minutes": 120},
}


def _normalize_metric_window(window: str | None) -> str:
    candidate = (window or "1h").strip().lower()
    return candidate if candidate in METRIC_WINDOW_PRESETS else "1h"


def _metric_series(
    seed: int,
    *,
    base: float,
    swing: float,
    minimum: float = 0.0,
    window: str = "1h",
) -> list[dict[str, Any]]:
    preset = METRIC_WINDOW_PRESETS[_normalize_metric_window(window)]
    points = preset["points"]
    step_minutes = preset["step_minutes"]
    series: list[dict[str, Any]] = []
    for index in range(points):
        offset = ((seed + index * 7) % 11) - 5
        value = round(max(minimum, base + offset * swing), 2)
        minutes_ago = (points - index - 1) * step_minutes
        if minutes_ago >= 60:
            hours = minutes_ago // 60
            remainder_minutes = minutes_ago % 60
            label = f"T-{hours}h" if remainder_minutes == 0 else f"T-{hours}h {remainder_minutes}m"
        else:
            label = f"T-{minutes_ago}m"
        series.append({"label": label, "value": value})
    return series


def get_node_metrics(db: Session, node_id: int, window: str = "1h") -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    metric_window = _normalize_metric_window(window)
    services = list(db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all())
    service_count = len(services)
    infra_count = sum(1 for service in services if service.kind == "infrastructure")
    helper_count = sum(1 for service in services if service.kind == "helper")
    base_cpu = min(92.0, 24.0 + service_count * 6.5 + infra_count * 4.0)
    base_memory = min(96.0, 28.0 + service_count * 5.8 + helper_count * 2.0)
    base_disk = min(88.0, 18.0 + service_count * 3.2 + infra_count * 2.5)
    rx = round(120 + service_count * 34 + infra_count * 18, 1)
    tx = round(48 + service_count * 17 + helper_count * 6, 1)
    seed = node.id * 13 + service_count * 5

    return {
        "node_id": node.id,
        "node_name": node.name,
        "window": metric_window,
        "cpu_percent": round(base_cpu, 1),
        "memory_percent": round(base_memory, 1),
        "disk_percent": round(base_disk, 1),
        "network_rx_mbps": rx,
        "network_tx_mbps": tx,
        "cpu_series": _metric_series(seed, base=base_cpu, swing=1.8, window=metric_window),
        "memory_series": _metric_series(seed + 3, base=base_memory, swing=1.2, window=metric_window),
        "disk_series": _metric_series(seed + 5, base=base_disk, swing=0.8, window=metric_window),
    }


def get_service_metrics(db: Session, service_id: int, window: str = "1h") -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    metric_window = _normalize_metric_window(window)
    dependency = dependency_preflight(db, service)
    latest_monitoring = db.scalar(
        select(MonitoringCheck).where(MonitoringCheck.service_id == service.id).order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc()))
    open_incidents = db.scalar(
        select(func.count()).select_from(IncidentRecord).where(
            IncidentRecord.service_id == service.id,
            IncidentRecord.status == "open",
        )
    ) or 0

    seed = service.id * 17 + len(service.service_key)
    cpu_percent = round(8 + len(service.service_key) * 1.7 + (0 if service.kind == "helper" else 6), 1)
    memory_mb = round(220 + len(service.name) * 18 + (400 if service.kind == "infrastructure" else 120), 1)
    queue_depth = max(0, (seed % 9) + (0 if dependency["ok"] else 7))
    restart_count = open_incidents + (0 if service.status in RUNNING_STATUSES else 1)
    latency_ms_p95 = round(22 + (seed % 13) * 4 + (18 if latest_slo and latest_slo.status == "burning" else 0), 1)
    log_error_rate = round((0.08 if dependency["ok"] else 0.42) + open_incidents * 0.18, 2)

    if latest_monitoring and latest_monitoring.status == "warning":
        log_error_rate = round(log_error_rate + 0.15, 2)

    return {
        "service_id": service.id,
        "service_name": service.name,
        "service_key": service.service_key,
        "node_id": service.node_id,
        "window": metric_window,
        "cpu_percent": cpu_percent,
        "memory_mb": memory_mb,
        "log_error_rate": log_error_rate,
        "queue_depth": queue_depth,
        "restart_count": restart_count,
        "latency_ms_p95": latency_ms_p95,
        "cpu_series": _metric_series(seed, base=cpu_percent, swing=1.5, window=metric_window),
        "error_rate_series": _metric_series(
            seed + 4,
            base=log_error_rate,
            swing=0.04,
            minimum=0.0,
            window=metric_window,
        ),
        "queue_depth_series": _metric_series(
            seed + 9,
            base=float(queue_depth),
            swing=0.9,
            minimum=0.0,
            window=metric_window,
        ),
    }


def latest_capacity_reports(db: Session, *, limit: int = 100) -> list[CapacityReport]:
    return list(db.scalars(select(CapacityReport).order_by(CapacityReport.created_at.desc()).limit(limit)).all())


def create_secret_record(
    db: Session,
    *,
    key: str,
    service: ServiceInstance | None = None,
    node: Node | None = None,
    scope: str = "service",
    rotation_interval_days: int = 90,
) -> SecretRecord:
    secret = SecretRecord(
        service_id=service.id if service else None,
        node_id=node.id if node else service.node_id if service else None,
        key=key,
        masked_value=f"{key[:2]}***{key[-2:]}" if len(key) > 4 else "********",
        scope=scope,
        rotation_interval_days=rotation_interval_days,
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    record_event(
        db,
        category="secret",
        level="info",
        message=f"Registered masked secret reference {secret.key}",
        service_id=secret.service_id,
        node_id=secret.node_id,
        metadata={"secret_id": secret.id, "scope": scope},
    )
    return secret


def rotate_secret_record(db: Session, secret: SecretRecord) -> SecretRecord:
    secret.status = "rotated"
    secret.rotated_at = datetime.utcnow()
    db.commit()
    db.refresh(secret)
    record_event(
        db,
        category="secret",
        level="info",
        message=f"Rotated secret reference {secret.key}",
        service_id=secret.service_id,
        node_id=secret.node_id,
        metadata={"secret_id": secret.id},
    )
    return secret


def latest_secrets(db: Session, *, limit: int = 100) -> list[SecretRecord]:
    return list(db.scalars(select(SecretRecord).order_by(SecretRecord.created_at.desc()).limit(limit)).all())


def schedule_maintenance(
    db: Session,
    *,
    title: str,
    starts_at: str,
    ends_at: str,
    impact: str = "",
    service: ServiceInstance | None = None,
    node: Node | None = None,
) -> MaintenanceWindow:
    window = MaintenanceWindow(
        service_id=service.id if service else None,
        node_id=node.id if node else service.node_id if service else None,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        impact=impact,
    )
    db.add(window)
    db.commit()
    db.refresh(window)
    record_event(
        db,
        category="maintenance",
        level="warning",
        message=f"Scheduled maintenance window {title}",
        service_id=window.service_id,
        node_id=window.node_id,
        metadata={"maintenance_id": window.id, "starts_at": starts_at, "ends_at": ends_at},
    )
    return window


def complete_maintenance(db: Session, window: MaintenanceWindow) -> MaintenanceWindow:
    window.status = "completed"
    db.commit()
    db.refresh(window)
    record_event(
        db,
        category="maintenance",
        level="info",
        message=f"Completed maintenance window {window.title}",
        service_id=window.service_id,
        node_id=window.node_id,
        metadata={"maintenance_id": window.id},
    )
    return window


def latest_maintenance_windows(db: Session, *, limit: int = 100) -> list[MaintenanceWindow]:
    return list(db.scalars(select(MaintenanceWindow).order_by(MaintenanceWindow.created_at.desc()).limit(limit)).all())


def get_service_capabilities(db: Session, service_id: int) -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")
    contract = json.loads(service.config_json or "{}")
    is_infra = service.kind == "infrastructure"
    log_paths = contract.get("log_paths", [])
    diagnostics = is_infra or len(log_paths) > 0
    config = bool(contract.get("config_files") or contract.get("environment") or contract.get("command"))
    backup = "backup" in contract
    requires_sudo = is_infra and any(tag in contract.get("tags", []) for tag in ["infra", "stateful", "database"])
    return {
        "service_id": service.id,
        "service_key": service.service_key,
        "kind": service.kind,
        "container_name": service.container_name,
        "diagnostics": diagnostics,
        "config": config,
        "backup": backup,
        "requires_sudo_for_file_logs": requires_sudo,
    }


def get_service_summary(db: Session, service_id: int) -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    contract = json.loads(service.config_json or "{}")
    dependency = dependency_preflight(db, service)
    capabilities = get_service_capabilities(db, service.id)

    latest_job = db.scalar(
        select(DeploymentJob).where(DeploymentJob.service_id == service.id).order_by(DeploymentJob.created_at.desc())
    )
    latest_backup = db.scalar(select(BackupRun).where(BackupRun.service_id == service.id).order_by(BackupRun.created_at.desc()))
    latest_release = db.scalar(
        select(ReleaseRecord).where(ReleaseRecord.service_id == service.id).order_by(ReleaseRecord.created_at.desc())
    )
    latest_drift = db.scalar(
        select(DriftReport).where(DriftReport.service_id == service.id).order_by(DriftReport.created_at.desc())
    )
    latest_monitoring = db.scalar(
        select(MonitoringCheck).where(MonitoringCheck.service_id == service.id).order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc()))
    latest_runbook = db.scalar(
        select(RunbookExecution).where(RunbookExecution.service_id == service.id).order_by(RunbookExecution.created_at.desc())
    )
    active_incidents = list(
        db.scalars(
            select(IncidentRecord)
            .where(
                IncidentRecord.service_id == service.id,
                IncidentRecord.status == "open",
            )
            .order_by(IncidentRecord.created_at.desc())
            .limit(5)
        ).all()
    )
    snapshot_count = db.scalar(
        select(func.count()).select_from(ConfigSnapshot).where(ConfigSnapshot.service_id == service.id)
    ) or 0
    recent_event_count = db.scalar(
        select(func.count()).select_from(OperationalEvent).where(OperationalEvent.service_id == service.id)
    ) or 0
    recent_events = list(
        db.scalars(
            select(OperationalEvent)
            .where(OperationalEvent.service_id == service.id)
            .order_by(OperationalEvent.created_at.desc())
            .limit(6)
        ).all()
    )

    return {
        "service_id": service.id,
        "node_id": service.node_id,
        "service_key": service.service_key,
        "name": service.name,
        "kind": service.kind,
        "subsystem": contract.get("subsystem", "uncategorized"),
        "status": service.status,
        "container_name": service.container_name,
        "image": service.image,
        "dependency": dependency,
        "capabilities": capabilities,
        "latest_job": latest_job,
        "latest_backup": latest_backup,
        "latest_release": latest_release,
        "latest_drift": latest_drift,
        "latest_monitoring": latest_monitoring,
        "latest_slo": latest_slo,
        "latest_runbook": latest_runbook,
        "active_incidents": active_incidents,
        "snapshot_count": snapshot_count,
        "recent_event_count": recent_event_count,
        "recent_events": recent_events,
    }


def get_service_release_timeline(db: Session, service_id: int, *, limit: int = 8) -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    releases = list_releases(db, service, limit=limit)
    release_events = list(
        db.scalars(
            select(OperationalEvent)
            .where(
                OperationalEvent.service_id == service.id,
                OperationalEvent.category == "release",
            )
            .order_by(OperationalEvent.created_at.desc())
            .limit(limit * 4)
        ).all()
    )
    recent_change_events = list(
        db.scalars(
            select(OperationalEvent)
            .where(
                OperationalEvent.service_id == service.id,
                OperationalEvent.category.in_(("release", "config", "drift", "runbook", "deployment")),
            )
            .order_by(OperationalEvent.created_at.desc())
            .limit(12)
        ).all()
    )
    latest_rollback_job = db.scalar(
        select(DeploymentJob)
        .where(
            DeploymentJob.service_id == service.id,
            DeploymentJob.action == "rollback-release",
        )
        .order_by(DeploymentJob.created_at.desc())
    )

    items: list[dict[str, Any]] = []
    for release in releases:
        related_events = [
            event
            for event in release_events
            if (
                event.created_at and release.created_at and event.created_at >= release.created_at
            )
        ][:3]
        rollback_executed = any(
            f"Rolled back release {release.version}" in event.message
            for event in release_events
        )
        notes = [f"Strategy: {release.strategy}"]
        if release.notes:
            notes.append(release.notes)
        if release.previous_image and release.previous_image != release.image:
            notes.append(f"Previous image: {release.previous_image}")
        if rollback_executed:
            notes.append("Rollback already executed for this release.")
        else:
            notes.append("Rollback available.")
        items.append(
            {
                "release": release,
                "rollback_executed": rollback_executed,
                "notes": notes,
                "related_events": related_events,
            }
        )

    return {
        "service_id": service.id,
        "service_name": service.name,
        "current_image": service.image,
        "current_status": service.status,
        "rollback_available": any(not item["rollback_executed"] for item in items),
        "latest_rollback_job": latest_rollback_job,
        "items": items,
        "recent_change_events": recent_change_events,
    }


def get_dashboard_summary(db: Session) -> dict[str, Any]:
    clusters = list(db.scalars(select(Cluster).order_by(Cluster.created_at.asc())).all())
    nodes = list(db.scalars(select(Node).order_by(Node.created_at.asc())).all())
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.created_at.asc())).all())
    open_incidents = list(
        db.scalars(
            select(IncidentRecord)
            .where(IncidentRecord.status == "open")
            .order_by(IncidentRecord.created_at.desc())
            .limit(8)
        ).all()
    )
    observability = observability_pipeline_report(db)
    observability_by_node = {item["node_id"]: item for item in observability["nodes"]}

    latest_slo_by_service: dict[int, SloReport] = {}
    for report in db.scalars(select(SloReport).order_by(SloReport.created_at.desc())).all():
        if report.service_id is None or report.service_id in latest_slo_by_service:
            continue
        latest_slo_by_service[report.service_id] = report

    open_incident_counts: dict[int, int] = {}
    for incident in open_incidents:
        if incident.service_id is not None:
            open_incident_counts[incident.service_id] = open_incident_counts.get(incident.service_id, 0) + 1

    attention_services: list[dict[str, Any]] = []
    for service in services:
        reasons: list[str] = []
        severity_score = 0

        if service.status not in RUNNING_STATUSES:
            reasons.append(f"Runtime status is {service.status}.")
            severity_score += 3

        dependency = dependency_preflight(db, service)
        if not dependency["ok"]:
            if dependency["missing"]:
                reasons.append(f"Missing dependencies: {', '.join(dependency['missing'])}.")
                severity_score += 3
            if dependency["stopped"]:
                reasons.append(f"Stopped dependencies: {', '.join(dependency['stopped'])}.")
                severity_score += 2

        latest_slo = latest_slo_by_service.get(service.id)
        if latest_slo and latest_slo.status == "burning":
            reasons.append("Latest SLO evaluation is burning.")
            severity_score += 2

        incident_count = open_incident_counts.get(service.id, 0)
        if incident_count:
            reasons.append(f"{incident_count} active incident(s) linked to this service.")
            severity_score += 3

        node_observability = observability_by_node.get(service.node_id)
        if node_observability and not node_observability["pipeline_ready"]:
            reasons.append("Node observability pipeline is degraded.")
            severity_score += 1

        if not reasons:
            continue

        severity = "critical" if severity_score >= 6 else "warning" if severity_score >= 3 else "notice"
        attention_services.append(
            {
                "service_id": service.id,
                "service_name": service.name,
                "service_key": service.service_key,
                "node_id": service.node_id,
                "node_name": service.node.name,
                "cluster_id": service.node.cluster_id,
                "cluster_name": service.node.cluster.name,
                "status": service.status,
                "severity": severity,
                "reasons": reasons,
                "_score": severity_score,
            }
        )

    attention_services.sort(key=lambda item: (item["_score"], item["service_name"]), reverse=True)
    attention_services = [{k: v for k, v in item.items() if k != "_score"} for item in attention_services[:8]]

    degraded_observability = []
    for item in observability["nodes"]:
        if item["pipeline_ready"]:
            continue
        node = db.get(Node, item["node_id"])
        degraded_observability.append(
            {
                "node_id": item["node_id"],
                "node_name": item["node_name"],
                "cluster_name": node.cluster.name if node and node.cluster else "unknown",
                "pipeline_ready": item["pipeline_ready"],
                "ingestion_state": item["ingestion_state"],
                "last_signal_at": item["last_signal_at"],
                "issues": item["issues"],
            }
        )

    running_services = sum(1 for service in services if service.status in RUNNING_STATUSES)
    burning_slos = sum(1 for report in latest_slo_by_service.values() if report.status == "burning")
    healthy_observability_nodes = observability["summary"]["healthy_nodes"]
    degraded_observability_nodes = observability["summary"]["degraded_nodes"]
    blocked_services = sum(
        1 for service in services if service.status not in RUNNING_STATUSES or not dependency_preflight(db, service)["ok"]
    )

    return {
        "clusters": len(clusters),
        "nodes": len(nodes),
        "services": len(services),
        "running_services": running_services,
        "open_incidents": len(open_incidents),
        "burning_slos": burning_slos,
        "healthy_observability_nodes": healthy_observability_nodes,
        "degraded_observability_nodes": degraded_observability_nodes,
        "blocked_services": blocked_services,
        "attention_services": attention_services,
        "active_incidents": open_incidents,
        "degraded_observability": degraded_observability[:6],
    }


def get_cluster_operations_view(db: Session, cluster_id: int, *, limit: int = 40) -> dict[str, Any]:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise ValueError(f"Cluster not found: {cluster_id}")

    nodes = list(db.scalars(select(Node).where(Node.cluster_id == cluster_id)).all())
    node_ids = [node.id for node in nodes]
    services = list(
        db.scalars(select(ServiceInstance).where(ServiceInstance.node_id.in_(node_ids) if node_ids else False)).all()
    ) if node_ids else []
    service_ids = [service.id for service in services]
    service_by_id = {service.id: service for service in services}
    node_by_id = {node.id: node for node in nodes}

    statement = select(OperationalEvent)
    if service_ids and node_ids:
        statement = statement.where(
            (OperationalEvent.service_id.in_(service_ids)) | (OperationalEvent.node_id.in_(node_ids))
        )
    elif service_ids:
        statement = statement.where(OperationalEvent.service_id.in_(service_ids))
    elif node_ids:
        statement = statement.where(OperationalEvent.node_id.in_(node_ids))
    else:
        return {
            "cluster_id": cluster.id,
            "cluster_name": cluster.name,
            "total_events": 0,
            "change_events": 0,
            "recovery_events": 0,
            "governance_events": 0,
            "active_incidents": 0,
            "items": [],
        }

    base_events = list(db.scalars(statement.order_by(OperationalEvent.created_at.desc()).limit(limit)).all())

    def classify(category: str, level: str, message: str) -> str:
        if category in {"release", "config", "deployment", "drift"}:
            return "change"
        if category in {"release-approval", "lifecycle", "audit"}:
            return "governance"
        if category in {"incident", "runbook", "monitoring"}:
            return "recovery" if ("resolve" in message.lower() or "completed" in message.lower() or "executed" in message.lower()) else "recovery"
        return "change" if level == "info" else "governance"

    items: list[dict[str, Any]] = []
    change_events = 0
    recovery_events = 0
    governance_events = 0
    for event in base_events:
        action_family = classify(event.category, event.level, event.message)
        if action_family == "change":
            change_events += 1
        elif action_family == "recovery":
            recovery_events += 1
        else:
            governance_events += 1
        service = service_by_id.get(event.service_id) if event.service_id is not None else None
        node = node_by_id.get(event.node_id) if event.node_id is not None else (service.node if service else None)
        items.append(
            {
                "id": event.id,
                "category": event.category,
                "level": event.level,
                "message": event.message,
                "created_at": event.created_at.isoformat() if event.created_at else "",
                "service_id": service.id if service else event.service_id,
                "service_name": service.name if service else None,
                "service_key": service.service_key if service else None,
                "node_id": node.id if node else event.node_id,
                "node_name": node.name if node else None,
                "action_family": action_family,
            }
        )

    active_incidents = db.scalar(
        select(func.count()).select_from(IncidentRecord).where(
            IncidentRecord.node_id.in_(node_ids) if node_ids else False,
            IncidentRecord.status == "open",
        )
    ) or 0

    return {
        "cluster_id": cluster.id,
        "cluster_name": cluster.name,
        "total_events": len(items),
        "change_events": change_events,
        "recovery_events": recovery_events,
        "governance_events": governance_events,
        "active_incidents": active_incidents,
        "items": items,
    }


def create_audit_export(db: Session, *, export_type: str = "summary") -> AuditExport:
    services = list(db.scalars(select(ServiceInstance)).all())
    diagnostics_ready = 0
    backup_ready = 0
    config_ready = 0

    for s in services:
        caps = get_service_capabilities(db, s.id)
        if caps["diagnostics"]:
            diagnostics_ready += 1
        if caps["backup"]:
            backup_ready += 1
        if caps["config"]:
            config_ready += 1

    policy_risk = (
        db.scalar(select(func.count(func.distinct(PolicyFinding.service_id))).where(PolicyFinding.status == "open"))
        or 0
    )

    summary = {
        "services": len(services),
        "events": db.scalar(select(func.count()).select_from(OperationalEvent)),
        "policy_findings": db.scalar(
            select(func.count()).select_from(PolicyFinding).where(PolicyFinding.status == "open")
        ),
        "incidents": db.scalar(select(func.count()).select_from(IncidentRecord)),
        "releases": db.scalar(select(func.count()).select_from(ReleaseRecord)),
        "secrets": db.scalar(select(func.count()).select_from(SecretRecord)),
        "maintenance_windows": db.scalar(select(func.count()).select_from(MaintenanceWindow)),
        "diagnostics_ready": diagnostics_ready,
        "backup_ready": backup_ready,
        "config_ready": config_ready,
        "policy_risk": policy_risk,
    }
    export = AuditExport(
        export_type=export_type,
        status="ready",
        artifact_path=f"data/runtime/audit/platformops-{export_type}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json",
        content_json=json.dumps(summary),
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    record_event(
        db,
        category="audit",
        level="info",
        message=f"Created audit export {export.artifact_path}",
        metadata={"audit_export_id": export.id, **summary},
    )
    return export


def latest_audit_exports(db: Session, *, limit: int = 100) -> list[AuditExport]:
    return list(db.scalars(select(AuditExport).order_by(AuditExport.created_at.desc()).limit(limit)).all())


def current_config(service: ServiceInstance) -> str:
    contract = json.loads(service.config_json or "{}")
    if contract.get("rendered_config_content"):
        return str(contract.get("rendered_config_content"))
    rendered = {
        "service": service.name,
        "service_key": service.service_key,
        "container_name": service.container_name,
        "image": service.image,
        "environment": contract.get("environment", {}),
        "ports": contract.get("ports", []),
        "volumes": contract.get("volumes", []),
        "healthcheck": contract.get("healthcheck", {}),
    }
    return yaml.safe_dump(rendered, sort_keys=False)


def config_capabilities_for_service(service: ServiceInstance) -> dict[str, Any]:
    contract = json.loads(service.config_json or "{}")
    config_files = contract.get("config_files") or []
    kind = contract.get("kind", service.kind)
    config_path = config_files[0] if config_files else ""
    has_config_surface = bool(config_files or contract.get("environment") or contract.get("command"))
    restart_required = kind in {"infrastructure", "helper"}
    disabled_reason = ""
    if not has_config_surface:
        disabled_reason = "No editable runtime config surface is defined for this service card."
    return {
        "snapshot_enabled": has_config_surface,
        "apply_enabled": has_config_surface,
        "restore_enabled": has_config_surface,
        "restart_required": restart_required,
        "config_path": config_path,
        "disabled_reason": disabled_reason,
        "requires_become_for_files": kind == "infrastructure" or bool(contract.get("requires_become", False)),
    }


def config_workspace(db: Session, service: ServiceInstance, *, source: str = "live") -> dict[str, Any]:
    snapshot_page = list_config_snapshots_page(db, service, limit=100, offset=0, source_filter="all", search="")
    snapshots = snapshot_page["items"]
    capabilities = config_capabilities_for_service(service)
    active_checkpoint = snapshots[0] if snapshots else None
    content = current_config(service)
    content_source = "live"
    message = "Loaded live rendered service config."
    if source == "latest_snapshot":
        latest = snapshots[0] if snapshots else None
        if latest is not None:
            content = latest.content
            content_source = "latest_snapshot"
            message = f"Loaded checkpoint {latest.name} (v{latest.version})."
        else:
            content_source = "live_fallback"
            message = "No snapshots found; fell back to live rendered config."
    elif source != "live":
        raise ValueError("Invalid config source. Use 'live' or 'latest_snapshot'.")

    drift_state = "No checkpoint captured yet"
    if active_checkpoint is not None:
        drift_state = (
            "Editor matches active checkpoint"
            if active_checkpoint.content.strip() == content.strip()
            else "Editor differs from active checkpoint"
        )

    peers = list(
        db.scalars(
            select(ServiceInstance)
            .where(
                ServiceInstance.service_key == service.service_key,
                ServiceInstance.node_id != service.node_id,
            )
            .order_by(ServiceInstance.created_at.desc())
        ).all()
    )
    return {
        "service_id": service.id,
        "content": content,
        "content_source": content_source,
        "message": message,
        "snapshots": snapshots,
        "snapshot_count": len(snapshots),
        "active_checkpoint": active_checkpoint,
        "drift_state": drift_state,
        "config_source_label": "Latest checkpoint" if content_source == "latest_snapshot" else "Live rendered config",
        "config_path": capabilities.get("config_path") or f"/runtime/{service.service_key}/config.yaml",
        "file_label": f"{service.container_name}/config.yaml",
        "config_capabilities": capabilities,
        "runtime_target": {
            "container_name": service.container_name,
            "service_name": service.name,
            "service_key": service.service_key,
            "node_name": service.node.name,
        },
        "peers": [
            {
                "service_id": peer.id,
                "service_name": peer.name,
                "node_name": peer.node.name,
                "node_id": peer.node_id,
                "node_host": peer.node.host,
            }
            for peer in peers
        ],
    }


def _migration_artifacts_dir(service_id: int) -> Path:
    root = settings.resolve(settings.runtime_dir) / "config-migrations" / str(service_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _migration_artifact_path(service_id: int, artifact_id: str) -> Path:
    return _migration_artifacts_dir(service_id) / f"{artifact_id}.json"


def prepare_config_migration(
    db: Session,
    service: ServiceInstance,
    *,
    left_snapshot: ConfigSnapshot,
    right_snapshot: ConfigSnapshot,
) -> dict[str, Any]:
    if left_snapshot.service_id != service.id or right_snapshot.service_id != service.id:
        raise ValueError("Selected snapshots must belong to the active service.")
    try:
        left_data = yaml.safe_load(left_snapshot.content) or {}
        right_data = yaml.safe_load(right_snapshot.content) or {}
    except Exception as exc:
        raise ValueError(f"Unable to parse selected snapshots: {exc}") from exc
    merged = copy.deepcopy(left_data if isinstance(left_data, dict) else {"value": left_data})
    if isinstance(right_data, dict):
        merged = _deep_merge_dict(merged, right_data)
    else:
        merged = {"value": right_data}
    merged_yaml = yaml.safe_dump(merged, sort_keys=False)
    compare = compare_config_snapshots(db, service, left_snapshot=left_snapshot, right_snapshot=right_snapshot)
    artifact_id = f"{int(datetime.utcnow().timestamp())}-{left_snapshot.id}-{right_snapshot.id}"
    artifact_payload = {
        "artifact_id": artifact_id,
        "service_id": service.id,
        "left_snapshot_id": left_snapshot.id,
        "right_snapshot_id": right_snapshot.id,
        "left_snapshot_name": left_snapshot.name,
        "right_snapshot_name": right_snapshot.name,
        "final_yaml": merged_yaml,
        "differences": compare["differences"],
    }
    _migration_artifact_path(service.id, artifact_id).write_text(json.dumps(artifact_payload, indent=2), encoding="utf-8")
    validation = validate_config(merged_yaml)
    return {
        "artifact_id": artifact_id,
        "left_snapshot": get_config_snapshot_detail(db, left_snapshot),
        "right_snapshot": get_config_snapshot_detail(db, right_snapshot),
        "differences": compare["differences"],
        "final_yaml": merged_yaml,
        "final_content": merged_yaml,
        "validation": validation,
        "summary": compare["summary"],
    }


def _load_migration_artifact(service_id: int, artifact_id: str) -> dict[str, Any]:
    path = _migration_artifact_path(service_id, artifact_id)
    if not path.exists():
        raise ValueError("Migration artifact not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_config_direct(
    db: Session,
    service: ServiceInstance,
    *,
    content: str,
    apply_mode: str,
    requested_by: str = "platform-operator",
) -> dict[str, Any]:
    validation = validate_config(content)
    if not validation["ok"]:
        raise ValueError(validation["message"])
    before = create_config_snapshot(db, service, source="pre-apply", requested_by=requested_by)
    job = apply_config(db, service, content=content, apply_mode=apply_mode)
    contract = json.loads(service.config_json or "{}")
    contract["rendered_config_content"] = content
    service.config_json = json.dumps(contract)
    db.commit()
    db.refresh(service)
    after = create_config_snapshot(db, service, source="post-apply", requested_by=requested_by)
    return {"job": job, "before_snapshot": before, "after_snapshot": after}


def apply_config_migration(
    db: Session,
    service: ServiceInstance,
    *,
    artifact_id: str,
    edited_yaml: str = "",
    apply_mode: str = "reload",
    requested_by: str = "platform-operator",
) -> dict[str, Any]:
    artifact = _load_migration_artifact(service.id, artifact_id)
    final_yaml = edited_yaml.strip() or str(artifact.get("final_yaml") or "")
    result = apply_config_direct(db, service, content=final_yaml, apply_mode=apply_mode, requested_by=requested_by)
    artifact["applied_at"] = datetime.utcnow().isoformat() + "Z"
    artifact["backup_snapshot_id"] = result["before_snapshot"].id
    artifact["resolved_config_path"] = config_capabilities_for_service(service).get("config_path") or ""
    artifact["apply_mode"] = apply_mode
    _migration_artifact_path(service.id, artifact_id).write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return {
        "artifact_id": artifact_id,
        "service_id": service.id,
        "job": result["job"],
        "backup_snapshot_id": result["before_snapshot"].id,
        "resolved_config_path": artifact["resolved_config_path"],
        "apply_mode": apply_mode,
        "applied_content": final_yaml,
    }


def restore_config_migration(
    db: Session,
    service: ServiceInstance,
    *,
    artifact_id: str,
    apply_mode: str = "reload",
    requested_by: str = "platform-operator",
) -> dict[str, Any]:
    artifact = _load_migration_artifact(service.id, artifact_id)
    backup_snapshot_id = int(artifact.get("backup_snapshot_id") or 0)
    backup_snapshot = db.get(ConfigSnapshot, backup_snapshot_id)
    if backup_snapshot is None or backup_snapshot.service_id != service.id:
        raise ValueError("Migration backup snapshot is not available for restore.")
    result = apply_config_direct(
        db,
        service,
        content=backup_snapshot.content,
        apply_mode=apply_mode,
        requested_by=requested_by,
    )
    return {
        "artifact_id": artifact_id,
        "service_id": service.id,
        "job": result["job"],
        "restored_snapshot_id": backup_snapshot.id,
        "backup_snapshot_id": backup_snapshot.id,
        "resolved_config_path": artifact.get("resolved_config_path", ""),
        "applied_content": backup_snapshot.content,
    }


def list_config_snapshots_page(
    db: Session,
    service: ServiceInstance,
    *,
    limit: int = 20,
    offset: int = 0,
    source_filter: str = "all",
    search: str = "",
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    statement = select(ConfigSnapshot).where(ConfigSnapshot.service_id == service.id)
    if source_filter != "all":
        statement = statement.where(ConfigSnapshot.source == source_filter)
    trimmed_search = search.strip()
    if trimmed_search:
        statement = statement.where(ConfigSnapshot.name.ilike(f"%{trimmed_search}%"))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(
        db.scalars(statement.order_by(ConfigSnapshot.created_at.desc()).offset(safe_offset).limit(safe_limit)).all()
    )
    return {
        "service_id": service.id,
        "total": int(total),
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(items) < int(total),
        "source_filter": source_filter,
        "search": trimmed_search,
        "items": items,
    }


def create_config_snapshot(
    db: Session,
    service: ServiceInstance,
    *,
    name: str | None = None,
    source: str = "manual",
    requested_by: str = "platform-operator",
) -> ConfigSnapshot:
    latest_version = db.scalar(
        select(ConfigSnapshot.version)
        .where(ConfigSnapshot.service_id == service.id)
        .order_by(ConfigSnapshot.version.desc())
        .limit(1)
    )
    version = (latest_version or 0) + 1
    requested_name = (name or f"v{version}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}").strip()
    if not requested_name:
        raise ValueError("Snapshot name cannot be empty.")
    existing_names = {
        item[0].casefold()
        for item in db.execute(select(ConfigSnapshot.name).where(ConfigSnapshot.service_id == service.id)).all()
    }
    final_name = requested_name
    duplicate_counter = 1
    while final_name.casefold() in existing_names:
        final_name = f"{requested_name}-v{duplicate_counter}"
        duplicate_counter += 1
    snapshot = ConfigSnapshot(
        service_id=service.id,
        version=version,
        name=final_name,
        content=current_config(service),
        source=source,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    record_event(
        db,
        category="config",
        level="info",
        message=f"Created config snapshot {snapshot.name} (v{snapshot.version}) for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={
            "action": "captured",
            "actor": requested_by or "platform-operator",
            "snapshot_id": snapshot.id,
            "version": snapshot.version,
            "source": snapshot.source,
        },
    )
    return snapshot


def rename_config_snapshot(
    db: Session,
    snapshot: ConfigSnapshot,
    *,
    name: str,
    requested_by: str = "platform-operator",
) -> ConfigSnapshot:
    target_name = name.strip()
    if not target_name:
        raise ValueError("Snapshot name cannot be empty.")
    existing_conflict = db.scalar(
        select(ConfigSnapshot)
        .where(
            ConfigSnapshot.service_id == snapshot.service_id,
            ConfigSnapshot.id != snapshot.id,
            func.lower(ConfigSnapshot.name) == target_name.casefold(),
        )
        .limit(1)
    )
    if existing_conflict is not None:
        raise ValueError("Snapshot name already exists for this service. Use a unique name.")
    old_name = snapshot.name
    snapshot.name = target_name
    db.commit()
    db.refresh(snapshot)
    record_event(
        db,
        category="config",
        level="info",
        message=f"Renamed config snapshot {old_name} to {snapshot.name} for service ID {snapshot.service_id}",
        service_id=snapshot.service_id,
        metadata={
            "action": "renamed",
            "actor": requested_by or "platform-operator",
            "snapshot_id": snapshot.id,
            "old_name": old_name,
            "new_name": snapshot.name,
            "version": snapshot.version,
        },
    )
    return snapshot


def restore_config_snapshot(db: Session, service: ServiceInstance, snapshot: ConfigSnapshot) -> DeploymentJob:
    vars_path = write_job_vars(
        "restore",
        service.id,
        {
            "container_name": service.container_name,
            "snapshot_version": snapshot.version,
            "snapshot_content": snapshot.content,
        },
    )
    command = f"{_ansible_base_command(service.node, 'docker_service.yml')} --extra-vars @{vars_path}"
    job = create_job(db, action="restore-config", command=command, service_id=service.id, node_id=service.node_id)

    if settings.local_mode:
        record_event(
            db,
            category="config",
            level="info",
            message=f"Restored config snapshot {snapshot.name} for {service.name}",
            service_id=service.id,
            node_id=service.node_id,
            metadata={
                "action": "restored",
                "actor": "platform-operator",
                "snapshot_id": snapshot.id,
                "version": snapshot.version,
            },
        )
        return finish_job(db, job, ok=True, output=f"Simulated config restore from {snapshot.name}.")
    return run_job_async(db, job, cwd=settings.project_root)


def validate_config(content: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict):
            return {"ok": False, "message": "Root element of config must be a YAML dictionary."}
        if "service_key" not in parsed:
            return {"ok": False, "message": "Config must contain service_key field."}
        return {"ok": True, "message": "YAML validated successfully."}
    except Exception as exc:
        return {"ok": False, "message": f"YAML syntax error: {exc}"}


def apply_config(db: Session, service: ServiceInstance, *, content: str, apply_mode: str) -> DeploymentJob:
    validation = validate_config(content)
    if not validation["ok"]:
        job = create_job(
            db, action="apply-config-blocked", command="validate-yaml", service_id=service.id, node_id=service.node_id
        )
        return finish_job(db, job, ok=False, error=validation["message"])

    vars_path = write_job_vars(
        "config",
        service.id,
        {
            "container_name": service.container_name,
            "apply_mode": apply_mode,
            "config_content": content,
        },
    )
    command = f"{_ansible_base_command(service.node, 'config_apply.yml')} --extra-vars @{vars_path}"
    job = create_job(db, action="apply-config", command=command, service_id=service.id, node_id=service.node_id)
    return (
        finish_job(db, job, ok=True, output="Configuration validated and simulated apply completed.")
        if settings.local_mode
        else run_job_async(db, job, cwd=settings.project_root)
    )


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


def lifecycle_impact(db: Session, target_type: str, target_id: int) -> dict[str, Any]:
    target_name = ""
    severity = "safe"
    can_delete_without_force = True
    dependents = []
    active_children = []
    warnings = []
    recommended_action = "Proceed with normal deletion."

    if target_type == "service":
        service = db.get(ServiceInstance, target_id)
        if not service:
            raise ValueError(f"Service instance not found: {target_id}")
        target_name = service.name

        active_services = db.scalars(
            select(ServiceInstance).where(
                ServiceInstance.node_id == service.node_id,
                ServiceInstance.id != service.id,
                ServiceInstance.status != "deleted",
            )
        ).all()
        for other in active_services:
            reqs = required_dependencies(other.service_key)
            if service.service_key in reqs:
                dependents.append(f"{other.name} ({other.service_key})")

        PROTECTED_INFRA_KEYS = {
            "postgres-core",
            "redis-core",
            "rabbitmq-core",
            "clickhouse-core",
            "milvus-core",
            "etcd-core",
            "minio-core",
            "prometheus-core",
            "loki-core",
            "airflow-postgres",
            "airflow-redis",
            "dtrain-tracker",
        }
        is_protected = service.service_key in PROTECTED_INFRA_KEYS

        if is_protected:
            warnings.append(
                f"Critical infrastructure card '{service.name}' is protected because multiple services depend on it."
            )
        if dependents:
            warnings.append(f"Deletes blocked by active dependents: {', '.join(dependents)}")

        can_delete_without_force = not is_protected and not dependents
        severity = "safe" if can_delete_without_force else "blocked"

        if not can_delete_without_force:
            if is_protected:
                recommended_action = "Protected infrastructure. Use Force Delete only if absolutely necessary."
            else:
                recommended_action = "Active dependents exist. Use Force Delete to override and proceed."

    elif target_type == "node":
        node = db.get(Node, target_id)
        if not node:
            raise ValueError(f"Node not found: {target_id}")
        target_name = node.name
        active_services = db.scalars(
            select(ServiceInstance).where(ServiceInstance.node_id == node.id, ServiceInstance.status != "deleted")
        ).all()
        active_children = [f"{s.name} ({s.service_key})" for s in active_services]
        if active_children:
            warnings.append(f"Node has active services: {', '.join(active_children)}")
        can_delete_without_force = len(active_children) == 0
        severity = "safe" if can_delete_without_force else "blocked"
        if not can_delete_without_force:
            recommended_action = "Remove active services or use Force Delete to override and remove the node."

    elif target_type == "cluster":
        cluster = db.get(Cluster, target_id)
        if not cluster:
            raise ValueError(f"Cluster not found: {target_id}")
        target_name = cluster.name
        nodes = db.scalars(select(Node).where(Node.cluster_id == cluster.id)).all()
        active_children = [f"Node: {n.name}" for n in nodes]

        services_count = 0
        for n in nodes:
            services_count += (
                db.scalar(
                    select(func.count(ServiceInstance.id)).where(
                        ServiceInstance.node_id == n.id, ServiceInstance.status != "deleted"
                    )
                )
                or 0
            )
        if nodes:
            warnings.append(f"Cluster contains {len(nodes)} nodes and {services_count} active services.")
        can_delete_without_force = len(nodes) == 0
        severity = "safe" if can_delete_without_force else "blocked"
        if not can_delete_without_force:
            recommended_action = "Remove all nodes from the cluster or use Force Delete to cascade deletion."

    return {
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
        "severity": severity,
        "can_delete_without_force": can_delete_without_force,
        "dependents": dependents,
        "active_children": active_children,
        "warnings": warnings,
        "recommended_action": recommended_action,
    }


def _parse_window_time(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _active_maintenance_windows(
    db: Session, *, service_id: int | None = None, node_id: int | None = None
) -> list[MaintenanceWindow]:
    windows = list(db.scalars(select(MaintenanceWindow).where(MaintenanceWindow.status == "scheduled")).all())
    now = datetime.utcnow()
    active: list[MaintenanceWindow] = []
    for window in windows:
        starts = _parse_window_time(window.starts_at)
        ends = _parse_window_time(window.ends_at)
        if starts is None or ends is None:
            continue
        # normalize to naive UTC for simple comparisons with stored values
        starts_utc = starts.astimezone(UTC).replace(tzinfo=None) if starts.tzinfo else starts
        ends_utc = ends.astimezone(UTC).replace(tzinfo=None) if ends.tzinfo else ends
        if not (starts_utc <= now <= ends_utc):
            continue
        if service_id is not None and window.service_id == service_id:
            active.append(window)
            continue
        if node_id is not None and window.node_id == node_id:
            active.append(window)
            continue
        # global maintenance window applies to governance actions
        if window.service_id is None and window.node_id is None:
            active.append(window)
    return active


def evaluate_force_delete_policy(
    db: Session,
    *,
    target_type: str,
    target_id: int,
    impact: dict[str, Any],
    force_reason: str | None,
) -> dict[str, Any]:
    reason = (force_reason or "").strip()
    violations: list[str] = []
    active_window_ids: list[int] = []
    requires_active_maintenance = False

    if len(reason) < 12:
        violations.append("Force delete requires a reason of at least 12 characters.")

    if target_type == "service":
        service = db.get(ServiceInstance, target_id)
        if service is None:
            raise ValueError(f"Service instance not found: {target_id}")
        protected_infra = {
            "postgres-core",
            "redis-core",
            "rabbitmq-core",
            "clickhouse-core",
            "milvus-core",
            "etcd-core",
            "minio-core",
            "prometheus-core",
            "loki-core",
            "airflow-postgres",
            "airflow-redis",
            "dtrain-tracker",
        }
        requires_active_maintenance = service.service_key in protected_infra or bool(impact.get("dependents"))
        if requires_active_maintenance:
            windows = _active_maintenance_windows(db, service_id=service.id, node_id=service.node_id)
            active_window_ids = [window.id for window in windows]
            if not active_window_ids:
                violations.append("Force delete requires an active maintenance window for this service or node.")

    elif target_type == "node":
        node = db.get(Node, target_id)
        if node is None:
            raise ValueError(f"Node not found: {target_id}")
        requires_active_maintenance = bool(impact.get("active_children"))
        if requires_active_maintenance:
            windows = _active_maintenance_windows(db, node_id=node.id)
            active_window_ids = [window.id for window in windows]
            if not active_window_ids:
                violations.append("Force delete requires an active maintenance window for this node.")

    elif target_type == "cluster":
        cluster = db.get(Cluster, target_id)
        if cluster is None:
            raise ValueError(f"Cluster not found: {target_id}")
        requires_active_maintenance = bool(impact.get("active_children"))
        if requires_active_maintenance:
            node_ids = {node.id for node in db.scalars(select(Node).where(Node.cluster_id == cluster.id)).all()}
            windows = list(db.scalars(select(MaintenanceWindow).where(MaintenanceWindow.status == "scheduled")).all())
            now = datetime.utcnow()
            for window in windows:
                starts = _parse_window_time(window.starts_at)
                ends = _parse_window_time(window.ends_at)
                if starts is None or ends is None:
                    continue
                starts_utc = starts.astimezone(UTC).replace(tzinfo=None) if starts.tzinfo else starts
                ends_utc = ends.astimezone(UTC).replace(tzinfo=None) if ends.tzinfo else ends
                if not (starts_utc <= now <= ends_utc):
                    continue
                if window.node_id in node_ids or (window.service_id is None and window.node_id is None):
                    active_window_ids.append(window.id)
            if not active_window_ids:
                violations.append("Force delete requires an active maintenance window for the cluster scope.")
    else:
        raise ValueError(f"Unknown lifecycle target_type: {target_type}")

    allowed = len(violations) == 0
    return {
        "allowed": allowed,
        "requires_reason": True,
        "requires_active_maintenance": requires_active_maintenance,
        "active_window_ids": sorted(set(active_window_ids)),
        "reason": reason,
        "violations": violations,
        "recommended_action": "Force delete policy checks passed."
        if allowed
        else "Open a maintenance window and provide a stronger reason before forcing deletion.",
    }


def create_force_delete_approval(
    db: Session,
    *,
    target_type: str,
    target_id: int,
    reason: str,
    requested_by: str,
    ttl_hours: int = 4,
) -> ForceDeleteApproval:
    if target_type not in {"service", "node", "cluster"}:
        raise ValueError("target_type must be one of: service, node, cluster")
    lifecycle_impact(db, target_type, target_id)
    if len((reason or "").strip()) < 12:
        raise ValueError("Approval reason must be at least 12 characters.")
    expires_at = datetime.utcnow() + timedelta(hours=max(1, min(ttl_hours, 168)))
    approval = ForceDeleteApproval(
        target_type=target_type,
        target_id=target_id,
        reason=reason.strip(),
        requested_by=(requested_by or "platform-operator").strip() or "platform-operator",
        status="pending",
        expires_at=expires_at,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    record_event(
        db,
        category="lifecycle",
        level="warning",
        message=f"Force delete approval requested for {target_type}:{target_id}",
        metadata={"approval_id": approval.id, "target_type": target_type, "target_id": target_id},
    )
    return approval


def decide_force_delete_approval(
    db: Session,
    approval: ForceDeleteApproval,
    *,
    approver: str,
    status: str,
    decision_note: str = "",
) -> ForceDeleteApproval:
    decision = (status or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise ValueError("status must be 'approved' or 'rejected'")
    approver_name = (approver or "").strip()
    if not approver_name:
        raise ValueError("approver is required.")
    if decision == "approved" and approver_name == (approval.requested_by or "").strip():
        raise ValueError("Two-person rule: requester cannot approve their own force-delete request.")
    if approval.used_at is not None:
        raise ValueError("Approval already consumed and cannot be changed.")
    if approval.status in {"rejected", "revoked"}:
        raise ValueError(f"Approval is already {approval.status} and cannot be changed.")
    now = datetime.utcnow()
    if approval.expires_at and now > approval.expires_at and approval.status == "pending":
        approval.status = "expired"
        db.commit()
        db.refresh(approval)
        raise ValueError("Approval has expired.")
    approval.status = decision
    approval.approver = approver_name
    approval.decision_note = (decision_note or "").strip()
    approval.approved_at = now
    db.commit()
    db.refresh(approval)
    record_event(
        db,
        category="lifecycle",
        level="warning" if decision == "approved" else "info",
        message=f"Force delete approval {decision} for {approval.target_type}:{approval.target_id}",
        metadata={"approval_id": approval.id, "status": decision, "approver": approval.approver},
    )
    return approval


def revoke_force_delete_approval(
    db: Session,
    approval: ForceDeleteApproval,
    *,
    actor: str,
    note: str = "",
) -> ForceDeleteApproval:
    if approval.used_at is not None or approval.status == "used":
        raise ValueError("Approval already consumed and cannot be revoked.")
    if approval.status in {"revoked", "expired"}:
        raise ValueError(f"Approval is already {approval.status}.")
    if approval.status == "rejected":
        raise ValueError("Rejected approval cannot be revoked.")

    now = datetime.utcnow()
    if approval.expires_at and now > approval.expires_at and approval.status == "pending":
        approval.status = "expired"
        db.commit()
        db.refresh(approval)
        raise ValueError("Approval has expired.")

    approval.status = "revoked"
    approval.approver = (actor or "").strip() or "platform-admin"
    approval.decision_note = (note or "").strip()
    approval.approved_at = now
    db.commit()
    db.refresh(approval)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Force delete approval revoked for {approval.target_type}:{approval.target_id}",
        metadata={"approval_id": approval.id, "actor": approval.approver},
    )
    return approval


def latest_force_delete_approvals(
    db: Session,
    *,
    limit: int = 100,
    target_type: str | None = None,
    target_id: int | None = None,
    status: str | None = None,
) -> list[ForceDeleteApproval]:
    statement = select(ForceDeleteApproval).order_by(ForceDeleteApproval.created_at.desc()).limit(limit)
    if target_type:
        statement = statement.where(ForceDeleteApproval.target_type == target_type)
    if target_id is not None:
        statement = statement.where(ForceDeleteApproval.target_id == target_id)
    if status:
        statement = statement.where(ForceDeleteApproval.status == status)
    approvals = list(db.scalars(statement).all())
    now = datetime.utcnow()
    expired_any = False
    for approval in approvals:
        if approval.status == "pending" and approval.expires_at and now > approval.expires_at:
            approval.status = "expired"
            expired_any = True
    if expired_any:
        db.commit()
    return approvals


def validate_force_delete_approval(
    db: Session,
    *,
    target_type: str,
    target_id: int,
    approval_id: int | None,
) -> dict[str, Any]:
    if approval_id is None:
        return {"allowed": False, "violations": ["Force delete approval is required for this action."]}
    approval = db.get(ForceDeleteApproval, approval_id)
    if approval is None:
        return {"allowed": False, "violations": [f"Approval id {approval_id} was not found."]}
    if approval.target_type != target_type or approval.target_id != target_id:
        return {
            "allowed": False,
            "approval": approval,
            "violations": ["Approval target does not match this delete action."],
        }
    if approval.used_at is not None or approval.status == "used":
        return {"allowed": False, "approval": approval, "violations": ["Approval has already been consumed."]}
    if approval.expires_at and datetime.utcnow() > approval.expires_at:
        approval.status = "expired"
        db.commit()
        return {"allowed": False, "approval": approval, "violations": ["Approval has expired."]}
    if approval.status != "approved":
        return {
            "allowed": False,
            "approval": approval,
            "violations": [f"Approval status is '{approval.status}', expected 'approved'."],
        }
    return {"allowed": True, "approval": approval, "violations": []}


def mark_force_delete_approval_used(db: Session, approval: ForceDeleteApproval) -> ForceDeleteApproval:
    approval.status = "used"
    approval.used_at = datetime.utcnow()
    db.commit()
    db.refresh(approval)
    return approval


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


def get_cluster_summary(db: Session, cluster_id: int) -> dict[str, Any]:
    nodes = db.scalars(select(Node).where(Node.cluster_id == cluster_id)).all()
    node_ids = [n.id for n in nodes]
    service_count = 0
    healthy_count = 0
    warning_count = 0
    error_count = 0

    if node_ids:
        services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id.in_(node_ids))).all()
        for s in services:
            if s.status == "deleted":
                continue
            service_count += 1
            if s.status in RUNNING_STATUSES:
                healthy_count += 1
            elif s.status in {"error", "failed"}:
                error_count += 1
            else:
                warning_count += 1

    return {
        "cluster_id": cluster_id,
        "node_count": len(nodes),
        "service_count": service_count,
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "error_count": error_count,
    }


def get_node_summary(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    kind_counts = {"app": 0, "infrastructure": 0, "helper": 0}
    services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node_id)).all()
    service_count = 0
    for s in services:
        if s.status == "deleted":
            continue
        service_count += 1
        kind_counts[s.kind] = kind_counts.get(s.kind, 0) + 1

    cap_report = db.scalar(
        select(CapacityReport).where(CapacityReport.node_id == node_id).order_by(CapacityReport.created_at.desc())
    )
    capacity_status = cap_report.status if cap_report else "ok"

    return {
        "node_id": node_id,
        "service_count": service_count,
        "kind_counts": kind_counts,
        "docker_network": node.docker_network,
        "volume_root": node.volume_root,
        "capacity_status": capacity_status,
    }


def get_node_connection_report(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    facts: dict[str, Any] = {}
    facts_error: str | None = None
    raw_facts = (node.facts_json or "").strip()
    if raw_facts:
        try:
            parsed = json.loads(raw_facts)
            if isinstance(parsed, dict):
                facts = parsed
            else:
                facts_error = "Node facts payload is not a JSON object."
        except json.JSONDecodeError:
            facts_error = "Node facts payload is not valid JSON."

    last_validate_job = db.scalar(
        select(DeploymentJob)
        .where(
            DeploymentJob.node_id == node_id,
            DeploymentJob.action == "validate-node",
        )
        .order_by(DeploymentJob.created_at.desc())
    )
    validation_job = None
    if last_validate_job:
        validation_job = {
            "id": last_validate_job.id,
            "status": last_validate_job.status,
            "created_at": last_validate_job.created_at.isoformat() if last_validate_job.created_at else "",
            "ended_at": last_validate_job.ended_at.isoformat() if last_validate_job.ended_at else None,
            "error": (last_validate_job.error or "").strip(),
            "output": (last_validate_job.output or "").strip(),
            "command": last_validate_job.command,
        }

    checked_at_value = facts.get("checked_at") if isinstance(facts.get("checked_at"), str) else None
    if checked_at_value:
        last_checked_at = checked_at_value
    elif last_validate_job and last_validate_job.ended_at:
        last_checked_at = last_validate_job.ended_at.isoformat()
    else:
        last_checked_at = None

    recommendations: list[str] = []
    if node.environment != "local" and not (node.ssh_key_path or "").strip():
        recommendations.append("Configure an SSH private key path before validating remote connectivity.")
    if node.environment != "local" and node.host in {"localhost", "127.0.0.1"}:
        recommendations.append("Set a remote host/IP for this non-local node.")
    if not facts:
        recommendations.append("Run Validate Node to collect host facts and confirm connectivity.")
    if node.status in {"unknown", "unreachable"}:
        recommendations.append("Node is not healthy. Re-run Validate Node and review validation output.")
    if last_validate_job and last_validate_job.status in {"failed", "cancelled"}:
        recommendations.append("Latest validation failed. Inspect the validation command output and SSH settings.")
    if node.environment == "local" and not recommendations:
        recommendations.append("Local mode is healthy. You can proceed with service deployment and diagnostics.")

    if last_validate_job and last_validate_job.status == "success":
        connection_state = "validated"
    elif last_validate_job and last_validate_job.status in {"running", "queued"}:
        connection_state = "validating"
    elif node.status == "unreachable":
        connection_state = "unreachable"
    elif facts:
        connection_state = "facts-only"
    else:
        connection_state = "not-validated"

    return {
        "node_id": node.id,
        "node_name": node.name,
        "host": node.host,
        "ssh_user": node.ssh_user,
        "ssh_key_path": node.ssh_key_path,
        "environment": node.environment,
        "status": node.status,
        "connection_state": connection_state,
        "facts_available": bool(facts),
        "facts": facts,
        "facts_error": facts_error,
        "last_checked_at": last_checked_at,
        "validation_job": validation_job,
        "recommendations": recommendations,
    }


def get_node_onboarding_report(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    connection = get_node_connection_report(db, node_id)
    facts = connection.get("facts", {}) if isinstance(connection.get("facts"), dict) else {}
    now_iso = datetime.utcnow().isoformat() + "Z"
    checks: list[dict[str, str]] = []

    def push_check(
        check_id: str, title: str, status: str, detail: str, remediation: str, severity: str = "low"
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "title": title,
                "status": status,
                "severity": severity,
                "detail": detail,
                "remediation": remediation,
            }
        )

    is_local = node.environment == "local"
    remote_host_ok = node.host not in {"localhost", "127.0.0.1"}

    push_check(
        "environment-profile",
        "Environment profile",
        "pass" if node.environment in {"local", "aws"} else "warn",
        f"Node environment is '{node.environment}'.",
        "Use 'aws' for remote EC2 nodes and 'local' for local simulation.",
        "low",
    )
    push_check(
        "host-config",
        "Target host",
        "pass" if (is_local or remote_host_ok) else "fail",
        f"Configured host: {node.host}",
        "Set node host to a reachable public/private IP or DNS name for remote nodes.",
        "high",
    )
    push_check(
        "ssh-user",
        "SSH user",
        "pass" if (node.ssh_user or "").strip() else "fail",
        f"SSH user: {(node.ssh_user or '').strip() or '(missing)'}",
        "Provide a valid SSH user (for AWS typically 'ubuntu' or ec2-user).",
        "high",
    )
    push_check(
        "ssh-key",
        "SSH private key",
        "pass" if (is_local or (node.ssh_key_path or "").strip()) else "fail",
        "SSH key path configured." if (node.ssh_key_path or "").strip() else "No SSH key path configured.",
        "Attach an SSH key path for remote nodes (for example ~/.ssh/<key>.pem).",
        "high" if not is_local else "low",
    )

    connection_state = connection.get("connection_state", "not-validated")
    validation_status = (
        connection.get("validation_job", {}).get("status")
        if isinstance(connection.get("validation_job"), dict)
        else None
    )
    if connection_state == "validated":
        validation_state = "pass"
    elif connection_state in {"validating", "facts-only"}:
        validation_state = "warn"
    else:
        validation_state = "fail"
    push_check(
        "connection-validation",
        "Connection validation",
        validation_state,
        f"Connection state: {connection_state}" + (f" · job={validation_status}" if validation_status else ""),
        "Run Validate Node and inspect SSH/network settings if validation fails.",
        "high" if validation_state == "fail" else "medium",
    )

    docker_fact = str(facts.get("docker", "")).strip().lower()
    docker_ready = docker_fact in {"expected", "present", "ok", "ready"} or connection_state == "validated"
    push_check(
        "docker-runtime",
        "Docker runtime",
        "pass" if docker_ready else "warn",
        f"Docker fact: {facts.get('docker', 'unknown')}",
        "Ensure Docker daemon is installed/running on target node before deployments.",
        "medium",
    )
    ansible_fact = str(facts.get("ansible", "")).strip().lower()
    ansible_ready = ansible_fact in {"ok", "command-recorded", "present", "ready"} or connection_state == "validated"
    push_check(
        "ansible-readiness",
        "Ansible readiness",
        "pass" if ansible_ready else "warn",
        f"Ansible fact: {facts.get('ansible', 'unknown')}",
        "Verify Ansible execution path and node credentials for orchestration playbooks.",
        "medium",
    )
    push_check(
        "volume-root",
        "Volume root path",
        "pass" if (node.volume_root or "").startswith("/") else "fail",
        f"Volume root: {node.volume_root}",
        "Use an absolute writable path (for example /platformops or /tmp/platformops).",
        "high",
    )
    push_check(
        "docker-network",
        "Docker network name",
        "pass" if bool((node.docker_network or "").strip()) else "fail",
        f"Docker network: {(node.docker_network or '').strip() or '(missing)'}",
        "Set a non-empty docker network identifier for service communication.",
        "high",
    )

    pass_count = sum(1 for item in checks if item["status"] == "pass")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    if fail_count > 0:
        overall_status = "fail"
    elif warn_count > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    next_actions = []
    for item in checks:
        if item["status"] in {"fail", "warn"} and item["remediation"] not in next_actions:
            next_actions.append(item["remediation"])
    for item in connection.get("recommendations", []):
        if item not in next_actions:
            next_actions.append(item)

    suggested_actions: list[str] = []
    needs_remote_profile = (
        node.environment != "local"
        and (not remote_host_ok or not (node.ssh_key_path or "").strip() or not (node.ssh_user or "").strip())
    )
    if needs_remote_profile:
        suggested_actions.append("apply-aws-gpu-preset" if "gpu" in (node.docker_network or "").lower() else "apply-aws-general-preset")
    elif node.environment == "local" and (node.host.startswith("ec2-") or "aws" in (node.docker_network or "").lower()):
        suggested_actions.append("apply-local-preset")

    if connection_state != "validated" or node.status in {"unknown", "unreachable"}:
        suggested_actions.append("run-validation")

    if not suggested_actions:
        suggested_actions.append("run-validation")

    return {
        "node_id": node.id,
        "node_name": node.name,
        "environment": node.environment,
        "overall_status": overall_status,
        "checked_at": now_iso,
        "connection_state": connection_state,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "next_actions": next_actions[:8],
        "suggested_actions": suggested_actions,
    }


def remediate_node_onboarding(db: Session, node_id: int, *, action: str) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    normalized = (action or "").strip().lower()
    if not normalized:
        raise ValueError("Remediation action is required.")

    updated_fields: dict[str, str] = {}
    validation_job: dict[str, Any] | None = None

    if normalized in {"apply-aws-general-preset", "apply-aws-gpu-preset", "apply-local-preset"}:
        before = {
            "environment": node.environment,
            "ssh_user": node.ssh_user,
            "host": node.host,
            "volume_root": node.volume_root,
            "docker_network": node.docker_network,
        }
        if normalized == "apply-aws-general-preset":
            node.environment = "aws"
            node.ssh_user = "ubuntu"
            if node.host in {"localhost", "127.0.0.1", ""}:
                node.host = "ec2-public-host"
            if node.volume_root.startswith("/tmp/"):
                node.volume_root = "/platformops"
            if node.docker_network == "platformops-net":
                node.docker_network = "platformops-net-aws"
        elif normalized == "apply-aws-gpu-preset":
            node.environment = "aws"
            node.ssh_user = "ubuntu"
            if node.host in {"localhost", "127.0.0.1", ""}:
                node.host = "ec2-gpu-host"
            if node.volume_root.startswith("/tmp/"):
                node.volume_root = "/platformops-gpu"
            if node.docker_network == "platformops-net":
                node.docker_network = "platformops-net-gpu"
        else:
            node.environment = "local"
            node.ssh_user = "ubuntu"
            if node.host.startswith("ec2-") or not node.host:
                node.host = "localhost"
            if node.volume_root.startswith("/platformops"):
                node.volume_root = "/tmp/platformops"
            if "aws" in node.docker_network or "gpu" in node.docker_network:
                node.docker_network = "platformops-net"

        for key, previous in before.items():
            current = getattr(node, key)
            if current != previous:
                updated_fields[key] = str(current)
        db.commit()
        db.refresh(node)
        record_event(
            db,
            category="lifecycle",
            level="info",
            message=f"Applied onboarding remediation '{normalized}' to node '{node.name}'",
            node_id=node.id,
            metadata={"action": normalized, "updated_fields": updated_fields},
        )
        message = (
            f"Applied {normalized}." if updated_fields else f"{normalized} already aligned; no node fields changed."
        )
        return {
            "node_id": node.id,
            "action": normalized,
            "ok": True,
            "message": message,
            "updated_fields": updated_fields,
            "validation_job": None,
        }

    if normalized == "run-validation":
        job = validate_node(db, node)
        validation_job = {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "error": (job.error or "").strip(),
            "output": (job.output or "").strip(),
            "command": job.command,
        }
        return {
            "node_id": node.id,
            "action": normalized,
            "ok": job.status == "success",
            "message": f"Validation job {job.id} finished with status {job.status}.",
            "updated_fields": {},
            "validation_job": validation_job,
        }

    raise ValueError(f"Unsupported remediation action '{action}'.")


def get_dtrain_overview(db: Session) -> dict[str, Any]:
    tracker_inst = db.scalar(select(ServiceInstance).where(ServiceInstance.service_key == "dtrain-tracker"))
    controller_inst = db.scalar(select(ServiceInstance).where(ServiceInstance.service_key == "dtrain-controller"))
    workers_inst = db.scalars(select(ServiceInstance).where(ServiceInstance.service_key == "dtrain-worker")).all()
    rabbitmq_inst = db.scalar(select(ServiceInstance).where(ServiceInstance.service_key == "rabbitmq-core"))
    redis_inst = db.scalar(select(ServiceInstance).where(ServiceInstance.service_key == "redis-core"))

    tracker_data = {
        "status": tracker_inst.status if tracker_inst else "not_installed",
        "container_name": tracker_inst.container_name if tracker_inst else "",
        "image": tracker_inst.image if tracker_inst else "",
    }
    controller_data = {
        "status": controller_inst.status if controller_inst else "not_installed",
        "container_name": controller_inst.container_name if controller_inst else "",
        "image": controller_inst.image if controller_inst else "",
    }
    workers_data = [
        {"id": w.id, "status": w.status, "container_name": w.container_name, "image": w.image} for w in workers_inst
    ]

    rabbitmq_status = rabbitmq_inst.status if rabbitmq_inst else "not_installed"
    redis_status = redis_inst.status if redis_inst else "not_installed"

    dependencies_data = {
        "rabbitmq": rabbitmq_status,
        "redis": redis_status,
        "ok": rabbitmq_status in RUNNING_STATUSES and redis_status in RUNNING_STATUSES,
    }

    rollout_ready = dependencies_data["ok"] and tracker_data["status"] in RUNNING_STATUSES

    metrics_data = {
        "active_jobs": 2,
        "queued_jobs": 1,
        "completed_jobs": 45,
        "failed_jobs": 3,
        "gpu_availability": "4/4 A100 GPUs Active (80% utilization)",
    }

    return {
        "tracker": tracker_data,
        "controller": controller_data,
        "workers": workers_data,
        "dependencies": dependencies_data,
        "metrics": metrics_data,
        "rollout_ready": rollout_ready,
    }
