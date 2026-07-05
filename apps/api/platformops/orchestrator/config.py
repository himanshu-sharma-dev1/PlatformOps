from __future__ import annotations

import contextlib
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..jobs import create_job, finish_job
from ..models import (
    ConfigSnapshot,
    DeploymentJob,
    DriftReport,
    OperationalEvent,
    ServiceInstance,
)
from ..settings import settings
from ..tasks import run_job_async
from .common import (
    _ansible_base_command,
    _deep_merge_dict,
    record_event,
)


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
    _migration_artifact_path(service.id, artifact_id).write_text(
        json.dumps(artifact_payload, indent=2), encoding="utf-8"
    )
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


def sync_peer_config(
    db: Session,
    service: ServiceInstance,
    *,
    peer_id: int,
    apply_mode: str = "reload",
    requested_by: str = "platform-operator",
) -> dict[str, Any]:
    peer = db.get(ServiceInstance, peer_id)
    if peer is None:
        raise ValueError(f"Peer service with ID {peer_id} not found.")
    if peer.service_key != service.service_key:
        raise ValueError("Target peer service must run the same service type.")
    if peer.id == service.id:
        raise ValueError("Cannot sync configuration to the service itself.")

    # Get active configuration content from source service
    content = current_config(service)

    # Apply it to the peer service
    result = apply_config_direct(db, peer, content=content, apply_mode=apply_mode, requested_by=requested_by)
    return {
        "source_service_id": service.id,
        "peer_service_id": peer.id,
        "job": result["job"],
        "before_snapshot": result["before_snapshot"],
        "after_snapshot": result["after_snapshot"],
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
    # Write snapshot content to temporary file
    runtime_dir = settings.resolve(settings.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    temp_yaml = runtime_dir / f"config-restore-{service.id}-{int(datetime.utcnow().timestamp())}.yml"
    temp_yaml.write_text(snapshot.content or "{}", encoding="utf-8")

    if not settings.local_mode:
        script_path = settings.resolve(settings.ansible_dir) / "playbooks" / "service_config_apply.sh"
        command = (
            f"bash {script_path} "
            f"--container-name {service.container_name} "
            f"--config-yaml {temp_yaml} "
            f"--service-name {service.service_key} "
            f"--apply-mode restart"
        )
        job = create_job(db, action="restore-config", command=command, service_id=service.id, node_id=service.node_id)

        def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
            bg_service = bg_db.get(ServiceInstance, service.id)
            if bg_service:
                if ok:
                    with contextlib.suppress(Exception):
                        bg_service.config_json = json.dumps(yaml.safe_load(snapshot.content or "{}"))
                record_event(
                    bg_db,
                    category="config",
                    level="info" if ok else "error",
                    message=f"Restored configuration to snapshot version {snapshot.version} for {bg_service.name}"
                    if ok
                    else f"Configuration restore failed for {bg_service.name}",
                    service_id=bg_service.id,
                    node_id=bg_service.node_id,
                    metadata={"job_id": bg_job.id},
                )

        return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)

    from .service import write_job_vars

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

    # Write config to a temporary yaml file under data/runtime/
    runtime_dir = settings.resolve(settings.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    temp_yaml = runtime_dir / f"config-apply-{service.id}-{int(datetime.utcnow().timestamp())}.yml"
    temp_yaml.write_text(content, encoding="utf-8")

    if not settings.local_mode:
        script_path = settings.resolve(settings.ansible_dir) / "playbooks" / "service_config_apply.sh"
        command = (
            f"bash {script_path} "
            f"--container-name {service.container_name} "
            f"--config-yaml {temp_yaml} "
            f"--service-name {service.service_key} "
            f"--apply-mode {apply_mode}"
        )
        job = create_job(db, action="apply-config", command=command, service_id=service.id, node_id=service.node_id)

        def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
            bg_service = bg_db.get(ServiceInstance, service.id)
            if bg_service:
                if ok:
                    with contextlib.suppress(Exception):
                        bg_service.config_json = json.dumps(yaml.safe_load(content))
                record_event(
                    bg_db,
                    category="config",
                    level="info" if ok else "error",
                    message=f"Applied configuration change to {bg_service.name} ({apply_mode})"
                    if ok
                    else f"Configuration apply failed for {bg_service.name}",
                    service_id=bg_service.id,
                    node_id=bg_service.node_id,
                    metadata={"job_id": bg_job.id},
                )

        return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)

    from .service import write_job_vars

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
    return finish_job(db, job, ok=True, output="Configuration validated and simulated apply completed.")
