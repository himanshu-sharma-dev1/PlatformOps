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


def _read_remote_config_content(service: ServiceInstance) -> tuple[str | None, str | None]:
    """Return (content, error) from a mounted file or the declared node."""
    import subprocess
    from pathlib import Path

    contract = _merged_service_contract(service)
    config_files = list(contract.get("config_files") or [])
    runtime_path = str(contract.get("runtime_config_path") or contract.get("config_path") or "")
    candidates: list[str] = []
    for p in config_files:
        if p:
            candidates.append(str(p))
    if runtime_path:
        candidates.append(runtime_path)
    volume_root = getattr(service.node, "volume_root", None) or "/tmp/platformops"
    if not candidates:
        candidates.append(f"{volume_root.rstrip('/')}/config/{service.service_key}/config.yaml")

    # 1) Host filesystem (volume mounts)
    for config_path in candidates:
        if config_path.startswith("/app/"):
            continue
        path = Path(config_path)
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace"), None
            except Exception as exc:
                return None, str(exc)

    # 2) Read from the declared node.  Local nodes use the configured SDK
    # engine (DOCKER_HOST in the isolated stack); remote nodes stay on SSH.
    container = (service.container_name or "").strip()
    if container:
        in_container_paths = [p for p in candidates if p.startswith("/app/")]
        if not in_container_paths and config_files:
            # map host volume .../config/file -> /app/config/file when standard mount
            for p in config_files:
                name = Path(p).name
                in_container_paths.append(f"/app/config/{name}")
        if not in_container_paths:
            in_container_paths = ["/app/config/dtrain_config.yaml", "/app/config/config.yaml"]
        node = service.node
        from .discovery import resolve_connection_mode

        connection_mode = resolve_connection_mode(node) if node is not None else "local"
        for cpath in in_container_paths:
            try:
                if connection_mode == "local":
                    from .docker_runtime import exec_container

                    ok, output, _error = exec_container(container, ["cat", cpath])
                    if ok and output.strip():
                        return output, None
                    continue

                if not node.host:
                    continue
                command = [
                    "ansible",
                    f"{node.host},",
                    "-m",
                    "command",
                    "-a",
                    f"docker exec {container} cat {cpath}",
                    "-u",
                    node.ssh_user or "ubuntu",
                ]
                if node.ssh_key_path:
                    command.extend(["--private-key", node.ssh_key_path])
                proc = subprocess.run(
                    command,
                    cwd=str(settings.project_root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if proc.returncode == 0 and (proc.stdout or "").strip():
                    return proc.stdout, None
            except Exception:
                continue

    return None, f"Config file not found (tried host paths + node container exec on {container or 'n/a'})"


def detect_drift(db: Session, service: ServiceInstance) -> DriftReport:
    latest_snapshot = db.scalar(
        select(ConfigSnapshot)
        .where(ConfigSnapshot.service_id == service.id)
        .order_by(ConfigSnapshot.version.desc())
        .limit(1)
    )
    differences: list[dict[str, Any]] = []
    remote_content, remote_err = _read_remote_config_content(service)
    # Prefer remote live file; fall back to DB current_config only for comparison baseline content
    live_content = remote_content if remote_content is not None else current_config(service)

    if remote_err and remote_content is None:
        differences.append(
            {
                "field": "_remote_read",
                "expected": "readable remote config",
                "actual": remote_err,
                "severity": "error",
            }
        )

    if latest_snapshot is None:
        differences.append(
            {
                "field": "baseline",
                "expected": "snapshot",
                "actual": "missing",
                "severity": "warning",
            }
        )
    elif (latest_snapshot.content or "").strip() != (live_content or "").strip():
        try:
            expected = yaml.safe_load(latest_snapshot.content) or {}
            actual = yaml.safe_load(live_content) or {}
            if isinstance(expected, dict) and isinstance(actual, dict):
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
            else:
                differences.append(
                    {
                        "field": "_content",
                        "expected": "matches snapshot",
                        "actual": "differs",
                        "severity": "warning",
                    }
                )
        except Exception:
            differences.append(
                {
                    "field": "_content",
                    "expected": "matches snapshot",
                    "actual": "differs (unparseable)",
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
        metadata={"differences": len(differences), "remote_error": remote_err},
    )
    return report


def _merged_service_contract(service: ServiceInstance) -> dict[str, Any]:
    """Merge catalog contract with instance config_json (adopted rows often lack config_files)."""
    from ..catalog import get_service_contract, rendered_contract

    node = service.node
    catalog = {}
    try:
        if node is not None:
            catalog = rendered_contract(
                service.service_key,
                node_id=node.id,
                volume_root=node.volume_root or "/tmp/platformops",
            ) or {}
        else:
            catalog = dict(get_service_contract(service.service_key) or {})
    except Exception:
        catalog = dict(get_service_contract(service.service_key) or {})
    instance: dict[str, Any] = {}
    try:
        instance = json.loads(service.config_json or "{}")
        if not isinstance(instance, dict):
            instance = {}
    except Exception:
        instance = {}
    merged = dict(catalog)
    for k, v in instance.items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    # Ensure config_files from catalog when instance empty
    if not merged.get("config_files") and catalog.get("config_files"):
        merged["config_files"] = catalog["config_files"]
    if not merged.get("runtime_config_path") and catalog.get("runtime_config_path"):
        merged["runtime_config_path"] = catalog["runtime_config_path"]
    return merged


def current_config(service: ServiceInstance) -> str:
    contract = _merged_service_contract(service)
    if contract.get("rendered_config_content"):
        return str(contract.get("rendered_config_content"))
    # Prefer real file on disk / in container
    remote_content, remote_err = _read_remote_config_content(service)
    if remote_content is not None and remote_content.strip():
        return remote_content
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
    if remote_err:
        rendered["_config_read_note"] = remote_err
    return yaml.safe_dump(rendered, sort_keys=False)


def config_capabilities_for_service(service: ServiceInstance) -> dict[str, Any]:
    contract = _merged_service_contract(service)
    config_files = contract.get("config_files") or []
    kind = contract.get("kind", service.kind)
    config_path = (
        config_files[0]
        if config_files
        else (contract.get("runtime_config_path") or contract.get("config_path") or "")
    )
    has_config_surface = bool(config_files or contract.get("runtime_config_path") or contract.get("environment") or contract.get("command"))
    restart_required = kind in {"infrastructure", "helper"} or service.service_key.startswith("dtrain")
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
    message = "Loaded live service config."
    if source == "latest_snapshot":
        latest = snapshots[0] if snapshots else None
        if latest is not None:
            content = latest.content
            content_source = "latest_snapshot"
            message = f"Loaded checkpoint {latest.name} (v{latest.version})."
        else:
            content_source = "live_fallback"
            message = "No snapshots found; fell back to live config."
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
    cfg_path = capabilities.get("config_path") or f"/runtime/{service.service_key}/config.yaml"
    return {
        "service_id": service.id,
        "content": content,
        "content_source": content_source,
        "message": message,
        "snapshots": snapshots,
        "snapshot_count": len(snapshots),
        "active_checkpoint": active_checkpoint,
        "drift_state": drift_state,
        "config_source_label": "Latest checkpoint" if content_source == "latest_snapshot" else "Live config",
        "config_path": cfg_path,
        "file_label": f"{service.container_name}/{Path(str(cfg_path)).name}",
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

    job = create_job(
        db,
        action="restore-config",
        command=f"restore-snapshot-{snapshot.version}",
        service_id=service.id,
        node_id=service.node_id,
    )
    return finish_job(
        db,
        job,
        ok=False,
        error=(
            "Config restore requires a real node target. "
            "Set PLATFORMOPS_LOCAL_MODE=false and configure SSH/Ansible for the service node."
        ),
    )


def validate_config(content: str, service: ServiceInstance | None = None) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(content)
        if parsed is None:
            return {"ok": False, "message": "Config content is empty."}
        if not isinstance(parsed, dict):
            return {"ok": False, "message": "Root element of config must be a YAML dictionary."}
        # Soft schema check against install schema when service known
        if service is not None:
            try:
                from ..catalog import get_service_contract

                contract = get_service_contract(service.service_key) or {}
                # Prefer install schema fields if present on contract
                fields = contract.get("install_fields") or contract.get("fields") or []
                required_keys = [
                    f.get("key") or f.get("name")
                    for f in fields
                    if isinstance(f, dict) and f.get("required") and (f.get("key") or f.get("name"))
                ]
                missing = [k for k in required_keys if k not in parsed and k not in (parsed.get("environment") or {})]
                if missing:
                    return {"ok": False, "message": f"Missing required config keys: {', '.join(missing)}"}
            except Exception:
                pass
        return {"ok": True, "message": "YAML validated successfully."}
    except Exception as exc:
        return {"ok": False, "message": f"YAML syntax error: {exc}"}


def apply_config(db: Session, service: ServiceInstance, *, content: str, apply_mode: str) -> DeploymentJob:
    import subprocess
    from pathlib import Path

    validation = validate_config(content, service=service)
    service_id = int(service.id)
    node_id = int(service.node_id) if service.node_id else None
    if not validation["ok"]:
        job = create_job(
            db, action="apply-config-blocked", command="validate-yaml", service_id=service_id, node_id=node_id
        )
        return finish_job(db, job, ok=False, error=validation["message"])

    # Write config to a temporary yaml file under data/runtime/
    runtime_dir = settings.resolve(settings.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    temp_yaml = runtime_dir / f"config-apply-{service_id}-{int(datetime.utcnow().timestamp())}.yml"
    temp_yaml.write_text(content, encoding="utf-8")

    # Always try host path + docker cp so apply works without relying on LOCAL_MODE alone
    contract = _merged_service_contract(service)
    host_paths = [str(p) for p in (contract.get("config_files") or []) if p and not str(p).startswith("/app/")]
    runtime_in_container = str(contract.get("runtime_config_path") or "")
    wrote_host = False
    write_log: list[str] = []
    for hp in host_paths:
        try:
            path = Path(hp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            wrote_host = True
            write_log.append(f"wrote_host:{hp}")
        except Exception as exc:
            write_log.append(f"host_fail:{hp}:{exc}")

    container = (service.container_name or "").strip()
    if container:
        targets = []
        if runtime_in_container:
            targets.append(runtime_in_container)
        for hp in host_paths:
            targets.append(f"/app/config/{Path(hp).name}")
        if not targets:
            targets = ["/app/config/dtrain_config.yaml"]
        for target in targets:
            try:
                # ensure dir exists then docker cp
                subprocess.run(
                    ["docker", "exec", container, "mkdir", "-p", str(Path(target).parent)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                proc = subprocess.run(
                    ["docker", "cp", str(temp_yaml), f"{container}:{target}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    write_log.append(f"docker_cp:{target}")
                    if apply_mode in {"restart", "reload"}:
                        subprocess.run(
                            ["docker", "restart", container],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        write_log.append(f"restarted:{container}")
                    break
                write_log.append(f"docker_cp_fail:{target}:{(proc.stderr or proc.stdout or '')[:120]}")
            except Exception as exc:
                write_log.append(f"docker_exc:{exc}")

    # Prefer direct host/docker write when it already succeeded (API shares host docker socket).
    # Do not mark failure solely because the ansible helper script is unavailable (e.g. no sudo).
    wrote_ok = any(x.startswith("wrote_host:") or x.startswith("docker_cp:") for x in write_log)
    if wrote_ok:
        job = create_job(
            db,
            action="apply-config",
            command=f"direct-config-apply mode={apply_mode} log={';'.join(write_log)}",
            service_id=service_id,
            node_id=node_id,
        )
        with contextlib.suppress(Exception):
            cfg = json.loads(service.config_json or "{}")
            if not isinstance(cfg, dict):
                cfg = {}
            cfg["rendered_config_content"] = content
            service.config_json = json.dumps(cfg)
            db.add(service)
            db.commit()
        record_event(
            db,
            category="config",
            level="info",
            message=f"Applied configuration change to {service.name} ({apply_mode})",
            service_id=service_id,
            node_id=node_id,
            metadata={"write_log": write_log, "apply_mode": apply_mode, "path": "direct"},
        )
        return finish_job(db, job, ok=True, output=";".join(write_log))

    if not settings.local_mode:
        script_path = settings.resolve(settings.ansible_dir) / "playbooks" / "service_config_apply.sh"
        command = (
            f"bash {script_path} "
            f"--container-name {service.container_name} "
            f"--config-yaml {temp_yaml} "
            f"--service-name {service.service_key} "
            f"--apply-mode {apply_mode}"
        )
        job = create_job(db, action="apply-config", command=command, service_id=service_id, node_id=node_id)

        def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
            bg_service = bg_db.get(ServiceInstance, service_id)
            if bg_service:
                if ok:
                    with contextlib.suppress(Exception):
                        cfg = json.loads(bg_service.config_json or "{}")
                        if not isinstance(cfg, dict):
                            cfg = {}
                        cfg["rendered_config_content"] = content
                        bg_service.config_json = json.dumps(cfg)
                        bg_db.add(bg_service)
                record_event(
                    bg_db,
                    category="config",
                    level="info" if ok else "error",
                    message=f"Applied configuration change to {bg_service.name} ({apply_mode})"
                    if ok
                    else f"Configuration apply failed for {bg_service.name}",
                    service_id=service_id,
                    node_id=node_id,
                    metadata={"job_id": bg_job.id, "write_log": write_log},
                )

        return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)

    # Fallback when neither direct write nor ansible path applied
    job = create_job(
        db,
        action="apply-config",
        command=f"direct-config-apply mode={apply_mode} log={';'.join(write_log)}",
        service_id=service_id,
        node_id=node_id,
    )
    return finish_job(
        db,
        job,
        ok=False,
        error=(
            "Config apply could not write host path or docker container. "
            f"log={';'.join(write_log) or 'empty'}"
        ),
        output="\n".join(write_log),
    )
