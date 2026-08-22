from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import ipaddress
import json
import re
import shlex
import shutil
import tempfile
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
from ..security import redact_text
from .common import _deep_merge_dict, record_event


_REDIS_SERVICE_KEYS = {"redis-core", "airflow-redis"}
_REDIS_REPEATABLE_DIRECTIVES = {"save", "rename-command", "include", "user"}


def _config_format(service: ServiceInstance | None) -> str:
    if service is not None and service.service_key in _REDIS_SERVICE_KEYS:
        return "redis"
    return "yaml"


def _parse_redis_config(content: str) -> tuple[dict[str, Any], list[str]]:
    parsed: dict[str, Any] = {}
    errors: list[str] = []
    if "\x00" in content:
        return {}, ["Redis config contains a NUL byte."]
    if len(content.encode("utf-8")) > 1_048_576:
        return {}, ["Redis config exceeds the 1 MiB editor limit."]
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"Line {line_number}: directive and value are required.")
            continue
        directive, value = parts[0].lower(), parts[1].strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", directive):
            errors.append(f"Line {line_number}: invalid Redis directive {parts[0]!r}.")
            continue
        if not value:
            errors.append(f"Line {line_number}: {directive} requires a value.")
            continue
        if directive in parsed and directive not in _REDIS_REPEATABLE_DIRECTIVES:
            errors.append(f"Line {line_number}: duplicate Redis directive {directive!r}.")
            continue
        if directive == "maxmemory" and not re.fullmatch(r"\d+(?:[kKmMgGtT][bB]?)?", value):
            errors.append(f"Line {line_number}: invalid maxmemory value {value!r}.")
        elif directive == "loglevel" and value.lower() not in {"debug", "verbose", "notice", "warning", "nothing"}:
            errors.append(f"Line {line_number}: invalid loglevel {value!r}.")
        elif directive in {"appendonly", "protected-mode", "daemonize"} and value.lower() not in {"yes", "no"}:
            errors.append(f"Line {line_number}: {directive} must be yes or no.")
        if directive in _REDIS_REPEATABLE_DIRECTIVES:
            parsed.setdefault(directive, []).append(value)
        else:
            parsed[directive] = value
    if not parsed and not errors:
        errors.append("Redis config content is empty.")
    return parsed, errors


def _parse_config_document(service: ServiceInstance, content: str) -> dict[str, Any]:
    if _config_format(service) == "redis":
        parsed, errors = _parse_redis_config(content)
        if errors:
            raise ValueError(" ".join(errors))
        return parsed
    raw = yaml.safe_load(content)
    if raw is None:
        raise ValueError("Config content is empty.")
    if not isinstance(raw, dict):
        raise ValueError("Root element of config must be a YAML dictionary.")
    return raw


def _render_redis_config(values: dict[str, Any]) -> str:
    lines: list[str] = []
    for directive in sorted(values):
        value = values[directive]
        if isinstance(value, list):
            lines.extend(f"{directive} {item}" for item in value)
        else:
            lines.append(f"{directive} {value}")
    return "\n".join(lines) + "\n"


def _merge_redis_config_text(left: str, right: str) -> str:
    """Preserve target comments/order and append baseline-only directives."""
    left_values, left_errors = _parse_redis_config(left)
    right_values, right_errors = _parse_redis_config(right)
    if left_errors or right_errors:
        raise ValueError(" ".join(left_errors + right_errors))
    merged = right.rstrip("\n")
    missing = {key: value for key, value in left_values.items() if key not in right_values}
    if missing:
        merged += "\n" + _render_redis_config(missing).rstrip("\n")
    return merged + "\n"


def _require_config_capability(service: ServiceInstance, capability: str) -> None:
    capabilities = config_capabilities_for_service(service)
    if not capabilities.get(capability):
        reason = capabilities.get("disabled_reason") or f"Config capability {capability} is disabled."
        raise ValueError(str(reason))


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

    left = _parse_config_document(service, left_snapshot.content)
    right = _parse_config_document(service, right_snapshot.content)

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
    """Read the declared runtime file from the service's node, never the API host."""
    contract = _merged_service_contract(service)
    runtime_path = str(contract.get("runtime_config_path") or contract.get("config_path") or "")
    if not runtime_path.startswith("/"):
        return None, "No absolute runtime_config_path is defined for this service."
    container = (service.container_name or "").strip()
    node = service.node
    if not container or node is None:
        return None, "Service container and node are required for runtime config reads."
    from .discovery import resolve_connection_mode

    connection_mode = resolve_connection_mode(node)
    if connection_mode == "local":
        from .docker_runtime import exec_container

        ok, output, error = exec_container(container, ["cat", runtime_path])
        return (output, None) if ok else (None, error or "runtime config read failed")

    if not node.host:
        return None, "Remote node host is not configured."
    return _remote_read_container_file(node, container, runtime_path)


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
            expected = _parse_config_document(service, latest_snapshot.content)
            actual = _parse_config_document(service, live_content)
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
        except (TypeError, ValueError, yaml.YAMLError):
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
    nonempty_instance: dict[str, Any] = {}
    for k, v in instance.items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        nonempty_instance[k] = v
    merged = _deep_merge_dict(catalog, nonempty_instance)
    # Ensure config_files from catalog when instance empty
    if not merged.get("config_files") and catalog.get("config_files"):
        merged["config_files"] = catalog["config_files"]
    if not merged.get("runtime_config_path") and catalog.get("runtime_config_path"):
        merged["runtime_config_path"] = catalog["runtime_config_path"]
    return merged


def current_config(service: ServiceInstance) -> str:
    contract = _merged_service_contract(service)
    # Prefer real file on disk / in container
    remote_content, remote_err = _read_remote_config_content(service)
    if remote_content is not None and remote_content.strip():
        return remote_content
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
    has_config_surface = bool(config_path and service.container_name and service.node is not None)
    restart_required = kind in {"infrastructure", "helper"} or service.service_key.startswith("dtrain")
    disabled_reason = ""
    if not has_config_surface:
        disabled_reason = "No editable runtime config surface is defined for this service card."
    return {
        "snapshot_enabled": has_config_surface,
        "apply_enabled": has_config_surface,
        "restore_enabled": has_config_surface,
        "migration_enabled": has_config_surface,
        "restart_required": restart_required,
        "config_path": config_path,
        "disabled_reason": disabled_reason,
        "requires_become_for_files": kind == "infrastructure" or bool(contract.get("requires_become", False)),
    }


def prepare_config_runtime_target(service: ServiceInstance) -> tuple[bool, str]:
    """Ensure a local DinD file bind has a real engine-visible source file."""

    from .discovery import resolve_connection_mode

    if service.node is None or resolve_connection_mode(service.node) != "local":
        return True, "remote target is prepared by Ansible on its own host"
    contract = _merged_service_contract(service)
    runtime_path = str(contract.get("runtime_config_path") or contract.get("config_path") or "")
    if not runtime_path.startswith("/"):
        return False, "No absolute runtime config path is defined."
    source_path = ""
    for volume in contract.get("volumes") or []:
        parts = str(volume).split(":")
        if len(parts) >= 2 and parts[1] == runtime_path:
            source_path = parts[0]
            break
    if not source_path:
        return True, f"No exact file bind maps to runtime config path {runtime_path}; no DinD staging needed."
    initial_content = str(contract.get("rendered_config_content") or "")
    if not initial_content:
        initial_content = (
            "# Managed by PlatformOps.\n"
            if _config_format(service) == "redis"
            else "# Managed by PlatformOps. Replace with service-specific config.\n"
        )
    from .docker_runtime import ensure_engine_host_file

    return ensure_engine_host_file(
        source_path,
        initial_content,
        helper_image="redis:7-alpine",
    )


def config_workspace(db: Session, service: ServiceInstance, *, source: str = "live") -> dict[str, Any]:
    snapshot_page = list_config_snapshots_page(db, service, limit=100, offset=0, source_filter="all", search="")
    snapshots = snapshot_page["items"]
    capabilities = config_capabilities_for_service(service)
    active_checkpoint = snapshots[0] if snapshots else None
    live_content, live_error = _read_remote_config_content(service)
    content = live_content if live_content is not None else current_config(service)
    content_source = "live" if live_content is not None else "runtime_unavailable"
    message = "Loaded live service config." if live_content is not None else f"Runtime read failed: {live_error}"
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
        "config_source_label": "Latest checkpoint" if content_source == "latest_snapshot" else ("Live config" if content_source == "live" else "Runtime unavailable"),
        "config_path": cfg_path,
        "file_label": f"{service.container_name}/{Path(str(cfg_path)).name}",
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "config_format": _config_format(service),
        "live_read_ok": live_content is not None,
        "live_read_error": live_error or "",
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
    _require_config_capability(service, "migration_enabled")
    if left_snapshot.service_id != service.id or right_snapshot.service_id != service.id:
        raise ValueError("Selected snapshots must belong to the active service.")
    try:
        left_data = _parse_config_document(service, left_snapshot.content)
        right_data = _parse_config_document(service, right_snapshot.content)
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to parse selected snapshots: {exc}") from exc
    merged = copy.deepcopy(left_data if isinstance(left_data, dict) else {"value": left_data})
    if isinstance(right_data, dict):
        merged = _deep_merge_dict(merged, right_data)
    else:
        merged = {"value": right_data}
    merged_yaml = (
        _merge_redis_config_text(left_snapshot.content, right_snapshot.content)
        if _config_format(service) == "redis"
        else yaml.safe_dump(merged, sort_keys=False)
    )
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
    validation = validate_config(merged_yaml, service=service)
    record_event(
        db, category="config", level="info",
        message=f"Prepared config migration artifact {artifact_id} for {service.name}",
        service_id=service.id, node_id=service.node_id,
        metadata={"action": "migration_prepared", "artifact_id": artifact_id},
    )
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
    _require_config_capability(service, "apply_enabled")
    validation = validate_config(content, service=service)
    if not validation["ok"]:
        raise ValueError(validation["message"])
    before = create_config_snapshot(db, service, source="pre-apply", requested_by=requested_by)
    job = apply_config(db, service, content=content, apply_mode=apply_mode, requested_by=requested_by)
    after = None
    if job.status == "success":
        db.refresh(service)
        after = create_config_snapshot(
            db,
            service,
            source="post-apply",
            requested_by=requested_by,
            content_override=content,
        )
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
    if result["job"].status == "success":
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
        "resolved_config_path": artifact.get("resolved_config_path", ""),
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
    content_override: str | None = None,
) -> ConfigSnapshot:
    _require_config_capability(service, "snapshot_enabled")
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
    live_content = content_override
    if live_content is None:
        live_content, live_error = _read_remote_config_content(service)
        if live_content is None:
            raise ValueError(f"Cannot snapshot unavailable runtime config: {live_error}")
    snapshot = ConfigSnapshot(
        service_id=service.id,
        version=version,
        name=final_name,
        content=live_content,
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
    _require_config_capability(service, "restore_enabled")
    if snapshot.service_id != service.id:
        raise ValueError("Config snapshot does not belong to the selected service.")
    service_id = int(service.id)
    node_id = int(service.node_id) if service.node_id else None
    snapshot_version = int(snapshot.version)
    snapshot_content = str(snapshot.content or "{}")
    snapshot_name = str(snapshot.name or f"v{snapshot_version}")
    service_name = str(service.name)

    # Validate snapshot YAML
    validation = validate_config(snapshot_content, service=service)
    if not validation["ok"]:
        job = create_job(
            db, action="restore-config-blocked", command="validate-yaml", service_id=service_id, node_id=node_id
        )
        return finish_job(db, job, ok=False, error=validation["message"])

    # The verified apply path owns write, lifecycle check, health verification,
    # persistence, and rollback. A failed restore must not start a second path.
    result = apply_config_direct(
        db,
        service,
        content=snapshot_content,
        apply_mode="restart",
        requested_by="platform-operator",
    )
    job = result["job"]
    if job.status == "success":
        record_event(
            db,
            category="config",
            level="info",
            message=f"Restored configuration to snapshot version {snapshot_version} ({snapshot_name}) for {service_name}",
            service_id=service_id,
            node_id=node_id,
            metadata={"job_id": job.id, "snapshot_version": snapshot_version},
        )
    return job


def validate_config(content: str, service: ServiceInstance | None = None) -> dict[str, Any]:
    if _config_format(service) == "redis":
        _parsed, errors = _parse_redis_config(content)
        if errors:
            return {"ok": False, "message": " ".join(errors)}
        return {"ok": True, "message": "Redis configuration validated successfully."}
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


_REDIS_CONFIG_GET_DIRECTIVES = {
    "appendfsync",
    "appendonly",
    "databases",
    "loglevel",
    "maxmemory",
    "maxmemory-policy",
    "tcp-keepalive",
    "timeout",
}


def _ansible_target_args(node: Any) -> tuple[list[str] | None, str | None, tuple[str, ...]]:
    """Build a safe explicit one-host inventory for an SSH node."""

    host = str(getattr(node, "host", "") or "").strip()
    if not host:
        return None, "Remote node host is not configured.", ()
    valid_host = False
    with contextlib.suppress(ValueError):
        valid_host = ipaddress.ip_address(host).version == 4
    if not valid_host:
        valid_host = (
            len(host) <= 253
            and all(
                label
                and len(label) <= 63
                and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                for label in host.rstrip(".").split(".")
            )
        )
    if not valid_host:
        return None, "Remote node host must be a safe IPv4 address or DNS name.", ()
    user = str(getattr(node, "ssh_user", "") or "ubuntu").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,118}", user):
        return None, "Remote SSH user contains unsafe characters.", ()
    key = str(getattr(node, "ssh_key_path", "") or "").strip()
    if key and not Path(key).is_file():
        return None, "Configured remote SSH key is not readable.", (key,)
    facts: dict[str, Any] = {}
    with contextlib.suppress(TypeError, json.JSONDecodeError):
        parsed = json.loads(getattr(node, "facts_json", "") or "{}")
        if isinstance(parsed, dict):
            facts = parsed
    raw_port = facts.get("ssh_port", facts.get("ansible_port", 22))
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        return None, "Configured remote SSH port is invalid.", (key,)
    if not 1 <= port <= 65535:
        return None, "Configured remote SSH port is invalid.", (key,)
    options = str(facts.get("ssh_options") or facts.get("ansible_ssh_common_args") or "").strip()
    if len(options) > 1000 or "\x00" in options or "\n" in options or "\r" in options:
        return None, "Configured remote SSH options are invalid.", (key, options)
    args = [host, "-i", f"{host},", "-u", user, "-e", f"ansible_port={port}"]
    if key:
        args.extend(["--private-key", key])
    if options:
        args.extend(["--ssh-common-args", options])
    return args, None, (key, options)


def _ansible_ad_hoc(node: Any, module: str, module_args: str, *, timeout: int = 90) -> tuple[bool, str, str]:
    """Run one target-bound Ansible module and read its machine result."""
    import subprocess

    target_args, target_error, redactions = _ansible_target_args(node)
    if target_args is None:
        return False, "", target_error or "Remote Ansible target is invalid."
    if not re.fullmatch(r"[A-Za-z0-9_.]+", module):
        return False, "", "Ansible module name contains unsafe characters."
    result_dir = Path(tempfile.mkdtemp(prefix="platformops-ansible-result-"))
    command = [
        "ansible",
        *target_args,
        "-m",
        module,
        "-a",
        module_args,
        "--tree",
        str(result_dir),
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result_files = [path for path in result_dir.iterdir() if path.is_file()]
        if not result_files:
            error = redact_text(
                (proc.stderr or proc.stdout or "Ansible returned no target result.").strip(),
                secrets=redactions,
            )
            return False, "", error[:1000]
        payload = json.loads(result_files[0].read_text(encoding="utf-8"))
        if isinstance(payload.get("content"), str):
            with contextlib.suppress(json.JSONDecodeError):
                payload = json.loads(payload["content"])
        stdout = str(payload.get("stdout") or "")
        stderr = str(payload.get("stderr") or payload.get("msg") or "")
        failed = bool(payload.get("failed")) or int(payload.get("rc") or 0) != 0 or proc.returncode != 0
        return (not failed), stdout, redact_text(stderr, secrets=redactions)[:1000]
    except Exception as exc:
        return False, "", redact_text(f"Ansible {module} failed: {exc}", secrets=redactions)
    finally:
        shutil.rmtree(result_dir, ignore_errors=True)


def _remote_exec_container(node: Any, container: str, args: list[str]) -> tuple[bool, str, str]:
    command = " ".join(shlex.quote(part) for part in ["docker", "exec", container, *args])
    return _ansible_ad_hoc(node, "command", command)


def _remote_read_container_file(node: Any, container: str, path: str) -> tuple[str | None, str | None]:
    ok, encoded, error = _remote_exec_container(node, container, ["base64", path])
    if not ok:
        return None, error or "Remote runtime config read failed."
    try:
        return base64.b64decode("".join(encoded.split()), validate=True).decode("utf-8"), None
    except (ValueError, UnicodeDecodeError) as exc:
        return None, f"Remote runtime config was not valid UTF-8/base64: {exc}"


def _remote_write_container_file(node: Any, container: str, path: str, content: str) -> tuple[bool, str]:
    if not path.startswith("/"):
        return False, "absolute runtime config path is required"
    local_path = ""
    remote_stage = f"/tmp/platformops-config-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"
    container_stage = f"{path}.platformops-stage"
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix="platformops-config-", delete=False) as handle:
            handle.write(content.encode("utf-8"))
            local_path = handle.name
        copy_args = f"src={shlex.quote(local_path)} dest={shlex.quote(remote_stage)} mode=0644"
        copied, _output, copy_error = _ansible_ad_hoc(node, "copy", copy_args)
        if not copied:
            return False, f"remote stage copy failed: {copy_error}"
        preserve_and_replace = (
            f"set -- $(stat -c '%a %u %g' {shlex.quote(path)}) && "
            f"chmod \"$1\" {shlex.quote(container_stage)} && "
            f"chown \"$2:$3\" {shlex.quote(container_stage)} && "
            f"mv -f {shlex.quote(container_stage)} {shlex.quote(path)}"
        )
        inspect_command = f"docker inspect {shlex.quote(container)}"
        running_parser = (
            "import json,sys; data=json.load(sys.stdin)[0]; "
            "print('true' if data['State']['Running'] else 'false')"
        )
        mount_parser = (
            "import json,sys; data=json.load(sys.stdin)[0]; target=sys.argv[1]; "
            "print(next((m.get('Source','') for m in data.get('Mounts',[]) "
            "if m.get('Type')=='bind' and m.get('Destination')==target),''))"
        )
        image_parser = "import json,sys; print(json.load(sys.stdin)[0]['Config']['Image'])"
        in_place_replace = (
            f"cat {shlex.quote(container_stage)} > {shlex.quote(path)} && "
            f"rm -f {shlex.quote(container_stage)}"
        )
        helper_replace = "test -f /platformops-target && cat /platformops-stage > /platformops-target"
        operation = (
            f"running=$({inspect_command} | python3 -c {shlex.quote(running_parser)}) && "
            f"mount_source=$({inspect_command} | python3 -c {shlex.quote(mount_parser)} {shlex.quote(path)}) && "
            f"if [ \"$running\" = true ]; then "
            f"docker cp {shlex.quote(remote_stage)} {shlex.quote(container + ':' + container_stage)} && "
            f"if [ -n \"$mount_source\" ]; then "
            f"docker exec -u 0 {shlex.quote(container)} sh -c {shlex.quote(in_place_replace)}; "
            f"else docker exec -u 0 {shlex.quote(container)} sh -c {shlex.quote(preserve_and_replace)}; fi; "
            f"elif [ -n \"$mount_source\" ]; then "
            f"image=$({inspect_command} | python3 -c {shlex.quote(image_parser)}) && "
            f"docker run --rm --user 0:0 --entrypoint sh "
            f"-v \"$mount_source:/platformops-target\" "
            f"-v {shlex.quote(remote_stage + ':/platformops-stage:ro')} "
            f"\"$image\" -c {shlex.quote(helper_replace)}; "
            f"else docker cp {shlex.quote(remote_stage)} {shlex.quote(container + ':' + path)}; fi"
        )
        shell_command = f"trap {shlex.quote('rm -f ' + shlex.quote(remote_stage))} EXIT; {operation}"
        wrote, _output, write_error = _ansible_ad_hoc(node, "shell", shell_command)
        return wrote, write_error
    finally:
        if local_path:
            with contextlib.suppress(OSError):
                Path(local_path).unlink()


def _remote_restart_container(node: Any, container: str, *, timeout: int = 30) -> tuple[bool, str]:
    status_parser = "import json,sys; print(json.load(sys.stdin)[0]['State']['Status'])"
    command = " && ".join(
        [
            f"docker restart -t {int(timeout)} {shlex.quote(container)}",
            f"test \"$(docker inspect {shlex.quote(container)} | python3 -c {shlex.quote(status_parser)})\" = running",
        ]
    )
    restarted, _output, restart_error = _ansible_ad_hoc(node, "shell", command, timeout=timeout + 60)
    return restarted, restart_error


def _redis_memory_bytes(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)([kKmMgGtT])?[bB]?", value.strip())
    if not match:
        return None
    multiplier = {None: 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[match.group(2).lower() if match.group(2) else None]
    return int(match.group(1)) * multiplier


def _verify_redis_runtime(
    container: str,
    content: str,
    exec_runtime: Any,
) -> tuple[bool, str]:
    ping_ok, ping_output, ping_error = exec_runtime(container, ["redis-cli", "--raw", "PING"])
    if not ping_ok or ping_output.strip().upper() != "PONG":
        return False, f"Redis PING failed: {ping_error or ping_output.strip() or 'no PONG'}"
    parsed, errors = _parse_redis_config(content)
    if errors:
        return False, "Redis verification parse failed: " + " ".join(errors)
    for directive in sorted(_REDIS_CONFIG_GET_DIRECTIVES.intersection(parsed)):
        ok, output, error = exec_runtime(container, ["redis-cli", "--raw", "CONFIG", "GET", directive])
        if not ok:
            return False, f"Redis CONFIG GET {directive} failed: {error or output.strip()}"
        lines = output.splitlines()
        if len(lines) < 2 or lines[0].strip().lower() != directive:
            return False, f"Redis CONFIG GET {directive} returned an unexpected response."
        expected = str(parsed[directive]).strip().strip('"\'')
        actual = lines[1].strip()
        matches = (
            _redis_memory_bytes(expected) == _redis_memory_bytes(actual)
            if directive == "maxmemory"
            else expected.casefold() == actual.casefold()
        )
        if not matches:
            return False, f"Redis CONFIG GET {directive} mismatch: expected {expected!r}, got {actual!r}."
    return True, "Redis PONG and applicable CONFIG GET values verified."


def _persist_verified_config(db: Session, service: ServiceInstance, content: str) -> None:
    try:
        contract = json.loads(service.config_json or "{}")
    except json.JSONDecodeError:
        contract = {}
    if not isinstance(contract, dict):
        contract = {}
    contract["rendered_config_content"] = content
    service.config_json = json.dumps(contract)
    db.add(service)
    db.commit()
    db.refresh(service)


def apply_config(
    db: Session,
    service: ServiceInstance,
    *,
    content: str,
    apply_mode: str,
    requested_by: str = "platform-operator",
) -> DeploymentJob:
    _require_config_capability(service, "apply_enabled")
    validation = validate_config(content, service=service)
    service_id = int(service.id)
    node_id = int(service.node_id) if service.node_id else None
    normalized_mode = apply_mode.strip().lower()
    if normalized_mode not in {"reload", "restart"}:
        validation = {"ok": False, "message": "apply_mode must be 'reload' or 'restart'."}
    job = create_job(
        db,
        action="apply-config",
        command=f"verified-runtime-config-apply mode={normalized_mode or apply_mode}",
        service_id=service_id,
        node_id=node_id,
    )
    if not validation["ok"]:
        record_event(
            db, category="config", level="error",
            message=f"Configuration apply rejected for {service.name}",
            service_id=service_id, node_id=node_id,
            metadata={"action": "apply_failed", "actor": requested_by, "apply_mode": normalized_mode, "error": validation["message"]},
        )
        return finish_job(db, job, ok=False, error=validation["message"])
    contract = _merged_service_contract(service)
    runtime_path = str(contract.get("runtime_config_path") or contract.get("config_path") or "")
    container = (service.container_name or "").strip()
    from .discovery import resolve_connection_mode

    mode = resolve_connection_mode(service.node)
    if mode == "local":
        from .docker_runtime import exec_container, restart_container, write_container_file

        exec_runtime = exec_container
        write_runtime = write_container_file
        restart_runtime = restart_container

        def read_runtime(target_container: str, target_path: str) -> tuple[bool, str, str]:
            return exec_container(target_container, ["cat", target_path])
    else:
        node = service.node

        def exec_runtime(target_container: str, args: list[str]) -> tuple[bool, str, str]:
            return _remote_exec_container(node, target_container, args)

        def write_runtime(target_container: str, target_path: str, target_content: str) -> tuple[bool, str]:
            return _remote_write_container_file(node, target_container, target_path, target_content)

        def restart_runtime(target_container: str, *, timeout: int = 30) -> tuple[bool, str]:
            return _remote_restart_container(node, target_container, timeout=timeout)

        def read_runtime(target_container: str, target_path: str) -> tuple[bool, str, str]:
            remote_content, remote_error = _remote_read_container_file(node, target_container, target_path)
            return (True, remote_content, "") if remote_content is not None else (False, "", remote_error or "remote read failed")

    read_ok, previous_content, read_error = read_runtime(container, runtime_path)
    if not read_ok:
        error = f"Unable to capture rollback bytes before apply: {read_error or previous_content.strip()}"
        record_event(db, category="config", level="error", message=f"Configuration apply failed for {service.name}", service_id=service_id, node_id=node_id, metadata={"action": "apply_failed", "actor": requested_by, "stage": "pre_read", "error": error})
        return finish_job(db, job, ok=False, error=error)

    wrote = False
    error = ""
    checks: list[str] = []
    ok, write_error = write_runtime(container, runtime_path, content)
    if not ok:
        error = f"Runtime config write failed: {write_error}"
    else:
        wrote = True
        verify_ok, live_content, verify_error = read_runtime(container, runtime_path)
        if not verify_ok or live_content.encode("utf-8") != content.encode("utf-8"):
            error = f"Runtime file byte verification failed: {verify_error or 'content mismatch'}"
        else:
            checks.append("runtime_bytes=verified")
    if not error:
        restarted, restart_error = restart_runtime(container)
        if not restarted:
            error = f"Runtime {normalized_mode} check failed: {restart_error}"
        else:
            checks.append(f"{normalized_mode}=verified")
    if not error and _config_format(service) == "redis":
        redis_ok, redis_message = _verify_redis_runtime(container, content, exec_runtime)
        if not redis_ok:
            error = redis_message
        else:
            checks.append("redis_runtime=verified")

    rollback_details = "not_needed"
    if error and wrote:
        rollback_ok, rollback_error = write_runtime(container, runtime_path, previous_content)
        if rollback_ok:
            rollback_restart_ok, rollback_restart_error = restart_runtime(container)
            rollback_read_ok, rollback_content, rollback_read_error = read_runtime(container, runtime_path)
            rollback_health_ok, rollback_health_error = True, ""
            if rollback_restart_ok and rollback_read_ok and _config_format(service) == "redis":
                ping_ok, ping_output, ping_error = exec_runtime(
                    container,
                    ["redis-cli", "--raw", "PING"],
                )
                rollback_health_ok = ping_ok and ping_output.strip().upper() == "PONG"
                rollback_health_error = ping_error or (
                    "Redis rollback PING did not return PONG." if not rollback_health_ok else ""
                )
            rollback_ok = (
                rollback_restart_ok
                and rollback_read_ok
                and rollback_content == previous_content
                and rollback_health_ok
            )
            rollback_error = (
                rollback_error
                or rollback_restart_error
                or rollback_read_error
                or rollback_health_error
            )
        rollback_details = "verified" if rollback_ok else f"failed:{rollback_error or 'rollback verification mismatch'}"
        error = f"{error}; rollback={rollback_details}"
    if error:
        record_event(db, category="config", level="error", message=f"Configuration apply failed for {service.name}", service_id=service_id, node_id=node_id, metadata={"action": "apply_failed", "actor": requested_by, "stage_checks": checks, "rollback": rollback_details, "error": error})
        return finish_job(db, job, ok=False, error=error, output=";".join(checks))

    _persist_verified_config(db, service, content)
    record_event(db, category="config", level="info", message=f"Applied verified configuration change to {service.name} ({normalized_mode})", service_id=service_id, node_id=node_id, metadata={"action": "applied", "actor": requested_by, "checks": checks, "runtime_path": runtime_path})
    return finish_job(db, job, ok=True, output=";".join(checks))
