from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any

import requests

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...catalog import (
    get_service_contract,
    observability_catalog,
    required_dependencies,
)
from ...jobs import create_job, finish_job
from ...models import (
    ConfigSnapshot,
    DeploymentJob,
    DriftReport,
    IncidentRecord,
    LogArchive,
    MonitoringCheck,
    Node,
    OperationalEvent,
    ReleaseRecord,
    RunbookExecution,
    ServiceInstance,
    SloReport,
)
from ...settings import settings
from ...tasks import run_job_async
from ...query import escape_query_regex_literal
from ..common import (
    RUNNING_STATUSES,
    _ansible_base_command,
    _service_display_name,
    record_event,
)


def _diagnostics_target_label(kind: str) -> str:
    if kind == "infrastructure":
        return "Infrastructure Card"
    if kind == "helper":
        return "Helper"
    return "Main"


def diagnostics_targets_for_service(db: Session, service: ServiceInstance) -> list[dict[str, Any]]:
    from ..service import _service_by_key

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
    from ..service import _service_by_key

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
    # Do not manufacture diagnostic messages. The summary carries a small real
    # snapshot when the container can be reached and an honest empty list when
    # it cannot; the detailed live endpoint includes the underlying error.
    recent_logs = service_live_logs(db, service, tail_lines=20, page_size=20).get("lines", [])[-20:]
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
    fetch_size = safe_tail if safe_cursor == 0 else safe_page
    lines: list[dict[str, str]] = []
    error: str | None = None
    connection_mode = "unknown"
    node = service.node

    if node is None:
        error = "Service has no assigned node."
    else:
        from ..discovery import resolve_connection_mode

        connection_mode = resolve_connection_mode(node)
        container = service.container_name or service.service_key
        try:
            if connection_mode == "local":
                from ..docker_runtime import container_logs

                output, local_error = container_logs(container, tail=fetch_size)
                if local_error:
                    raise RuntimeError(local_error)
                raw_lines = output.decode("utf-8", errors="replace").splitlines()
            else:
                if not node.host:
                    raise RuntimeError("Remote node has no host address.")
                command = [
                    "ansible",
                    f"{node.host},",
                    "-m",
                    "command",
                    "-a",
                    f"docker logs --timestamps --tail {fetch_size} {container}",
                    "-u",
                    node.ssh_user or "ubuntu",
                ]
                if node.ssh_key_path:
                    command.extend(["--private-key", node.ssh_key_path])
                result = subprocess.run(
                    command,
                    cwd=str(settings.project_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "Container log command failed.").strip())
                raw_lines = (result.stdout or "").splitlines()
                # docker logs may write to stderr depending on the logging driver.
                if not raw_lines and result.stderr:
                    raw_lines = result.stderr.splitlines()
            for raw in raw_lines[-fetch_size:]:
                message = raw.strip()
                if not message or message.endswith(" | SUCCESS => {") or message == "}":
                    continue
                timestamp = datetime.utcnow().isoformat() + "Z"
                first, separator, remainder = message.partition(" ")
                if separator and "T" in first and first[:4].isdigit():
                    timestamp = first
                    message = remainder
                lines.append(
                    {
                        "timestamp": timestamp,
                        "level": _detect_log_level(message),
                        "message": message,
                        "source": "container_stdout",
                    }
                )
        except Exception as exc:
            error = str(exc)

    # This endpoint is a bounded real tail, not a fabricated pageable event
    # feed. Cursor values remain for response compatibility.
    total_available = len(lines)
    next_cursor = safe_cursor + len(lines)
    has_more_history = False
    source_state = "streaming" if not error and service.status in RUNNING_STATUSES else "unavailable" if error else "snapshot"
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
        "connection_mode": connection_mode,
        "error": error,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def service_container_history(
    db: Session,
    service: ServiceInstance,
    *,
    page: int = 1,
    page_size: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Query Loki for historical container stdout/stderr by container_name label."""
    import base64
    import time

    loki_url = settings.loki_base_url.rstrip("/")
    container = service.container_name or service.service_key
    selector = "{" + f'container_name="{container}"' + "}"
    # Also try docker name label variants
    alt_selector = "{" + f'name="{container}"' + "}"

    cache_key = f"ctrhist:{service.id}:{page}:{page_size}:{cursor or ''}"
    now_ts = time.time()
    cached = _LOKI_PAGE_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) < _LOKI_PAGE_CACHE_TTL_S:
        return cached[1]

    lines: list[dict[str, Any]] = []
    total_count = 0
    next_cursor = None
    previous_cursor = None
    loki_reachable = False
    used_selector = selector

    try:
        for sel in (selector, alt_selector, "{" + f'service_name=~".*{service.service_key}.*"' + "}"):
            count_resp = requests.get(
                f"{loki_url}/loki/api/v1/query",
                params={"query": f"count_over_time({sel}[720h])"},
                timeout=5,
            )
            if count_resp.status_code == 200:
                loki_reachable = True
                result = count_resp.json().get("data", {}).get("result") or []
                if result:
                    total_count = int(float(result[0].get("value", [0, 0])[1]))
                    used_selector = sel
                    break
    except Exception:
        pass

    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1

    if loki_reachable:
        try:
            end_ns = str(int(time.time()) * 1_000_000_000)
            direction = "older"
            anchor_ns = end_ns
            if cursor:
                try:
                    cursor_data = json.loads(base64.b64decode(cursor))
                    direction = "newer" if cursor_data.get("direction") == "newer" else "older"
                    anchor_ns = str(cursor_data.get("anchor_ts_ns", end_ns))
                except Exception:
                    direction = "older"
                    anchor_ns = end_ns
            params = {
                "query": used_selector,
                "limit": str(page_size),
                "direction": "forward" if direction == "newer" else "backward",
            }
            params["start" if direction == "newer" else "end"] = anchor_ns
            resp = requests.get(f"{loki_url}/loki/api/v1/query_range", params=params, timeout=10)
            if resp.status_code == 200:
                timestamped_lines: list[tuple[int, dict[str, Any]]] = []
                for stream in resp.json().get("data", {}).get("result") or []:
                    for ts_ns, msg in stream.get("values") or []:
                        timestamped_lines.append((int(ts_ns), {
                            "timestamp": datetime.utcfromtimestamp(int(ts_ns) / 1e9).strftime("%Y-%m-%dT%H:%M:%S"),
                            "level": _detect_log_level(msg),
                            "message": msg,
                            "source": "container_history",
                        }))
                timestamped_lines.sort(key=lambda item: item[0])
                lines = [item[1] for item in timestamped_lines]
                if timestamped_lines:
                    oldest_ns = timestamped_lines[0][0]
                    newest_ns = timestamped_lines[-1][0]
                    next_payload = {"anchor_ts_ns": oldest_ns - 1, "direction": "older", "page": page + 1}
                    previous_payload = {"anchor_ts_ns": newest_ns + 1, "direction": "newer", "page": max(1, page - 1)}
                    next_cursor = base64.b64encode(json.dumps(next_payload).encode()).decode()
                    previous_cursor = base64.b64encode(json.dumps(previous_payload).encode()).decode()
        except Exception:
            pass

    result = {
        "lines": lines,
        "source": "container_history",
        "container_name": container,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "next_cursor": next_cursor,
        "previous_cursor": previous_cursor,
        "loki_reachable": loki_reachable,
        "error": None if (loki_reachable or lines) else "No container history from Loki",
    }
    _LOKI_PAGE_CACHE[cache_key] = (now_ts, result)
    return result


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
    from ..monitoring import get_service_metrics

    source = source_service or service
    diagnostics = service_diagnostics(db, service, source_service=source)
    metrics = get_service_metrics(db, service.id, window="15m")
    dependency = diagnostics["readiness"]["dependency_summary"]
    readiness = diagnostics["readiness"]
    latest_monitoring = db.scalar(
        select(MonitoringCheck)
        .where(MonitoringCheck.service_id == service.id)
        .order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(
        select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc())
    )
    latest_release = db.scalar(
        select(ReleaseRecord).where(ReleaseRecord.service_id == service.id).order_by(ReleaseRecord.created_at.desc())
    )
    latest_snapshot = db.scalar(
        select(ConfigSnapshot)
        .where(ConfigSnapshot.service_id == service.id)
        .order_by(ConfigSnapshot.version.desc())
        .limit(1)
    )
    latest_drift = db.scalar(
        select(DriftReport).where(DriftReport.service_id == service.id).order_by(DriftReport.created_at.desc())
    )
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
                "created_at": incident.created_at.isoformat()
                if incident.created_at
                else datetime.utcnow().isoformat() + "Z",
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
                "created_at": latest_release.created_at.isoformat()
                if latest_release.created_at
                else datetime.utcnow().isoformat() + "Z",
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
                "created_at": latest_drift.created_at.isoformat()
                if latest_drift.created_at
                else datetime.utcnow().isoformat() + "Z",
                "severity": "warning" if latest_drift.status == "drifted" else "info",
                "detail": "Config drift can explain incidents if runtime behavior diverged from the last known snapshot.",
                "confidence": 90 if latest_drift.status == "drifted" and drift_fields else 66,
                "target_view": "config-compare",
                "baseline_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_left_snapshot_id": latest_drift.baseline_snapshot_id,
                "compare_right_snapshot_id": latest_snapshot.id
                if latest_snapshot
                else latest_drift.baseline_snapshot_id,
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
                "compare_right_snapshot_id": latest_snapshot.id
                if latest_snapshot
                else latest_drift.baseline_snapshot_id,
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
                "compare_right_snapshot_id": latest_snapshot.id
                if latest_snapshot
                else latest_drift.baseline_snapshot_id,
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
                    "label": "Run dependency recovery"
                    if dependency_runbook_key == "dependency-recovery"
                    else "Run suggested runbook",
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
                "evidence_refs": [
                    f"metric:error-rate:{metrics['log_error_rate']}",
                    f"metric:restarts:{metrics['restart_count']}",
                ]
                + common_refs[:2],
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
                "evidence_refs": [f"metric:queue-depth:{metrics['queue_depth']}"]
                + ([f"dependency:{broker_target['service_key']}"] if broker_target else []),
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
                "evidence_refs": [f"drift:{latest_drift.status}"]
                + [f"drift-field:{field}" for field in drift_fields[:3]],
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
                "rationale": latest_monitoring.detail
                or "The latest monitoring check flagged this target for follow-up.",
                "evidence_refs": [
                    f"monitoring:{latest_monitoring.name}",
                    f"monitoring-value:{latest_monitoring.value}",
                ],
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
        insight["supporting_evidence"] = [
            resolve_supporting_evidence(ref) for ref in insight.get("evidence_refs", [])[:4]
        ]

    severity_rank = {"info": 0, "warning": 1, "error": 2}
    insights.sort(
        key=lambda item: (-int(item.get("confidence", 0)), -severity_rank.get(item["severity"], 0), item["title"])
    )
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

    discovered: dict[str, int] = {}
    from pathlib import Path

    for configured_path in log_paths:
        container_path = _container_path_for_host_path(service, configured_path)
        if container_path:
            ok, output, _error = _run_container_command(
                service,
                ["find", container_path, "-maxdepth", "1", "-type", "f", "-printf", "%p\t%s\n"],
            )
            if ok:
                for row in output.splitlines():
                    raw_path, separator, raw_size = row.rpartition("\t")
                    if not separator or not raw_path.startswith("/"):
                        continue
                    try:
                        size = int(raw_size.strip())
                    except ValueError:
                        continue
                    discovered[_host_path_for_container_path(service, raw_path.strip())] = size
                continue

        local_path = Path(configured_path)
        candidates = [local_path] if local_path.is_file() else list(local_path.glob("*")) if local_path.is_dir() else []
        for candidate in candidates:
            if candidate.is_file():
                try:
                    discovered[str(candidate)] = candidate.stat().st_size
                except OSError:
                    continue

    archives: list[LogArchive] = []
    for path, size_bytes in sorted(discovered.items()):
        archive = LogArchive(
            service_id=service.id,
            path=path,
            size_bytes=size_bytes,
            line_count=0,
            readable="yes",
            reason="measured on declared service target",
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
    command = (
        f"{_ansible_base_command(service.node, 'service_log_backfill.yml')} --extra-vars service={service.service_key}"
    )
    job = create_job(db, action="log-backfill", command=command, service_id=service.id, node_id=service.node_id)
    ready = bool(requirements.get("ready"))
    output = f"Backfill not ready: {', '.join(requirements.get('missing', [])) or 'requirements incomplete'}."
    if ready:
        current_job = run_job_async(db, job, cwd=settings.project_root)
        summary = f"Log backfill job #{job.id} started for {service.container_name}."
    else:
        current_job = finish_job(db, job, ok=False, output="", error=output)
        summary = output
    record_event(
        db,
        category="diagnostics",
        level="info" if ready else "warning",
        message=f"Log backfill {'started' if ready else 'blocked'} for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"ready": ready, "missing": requirements.get("missing", [])},
    )
    return {
        "service_id": service.id,
        "ready": ready,
        "requirements": requirements,
        "job": current_job,
        "summary": summary,
    }


def deploy_observability_stack(db: Session, node: Node) -> DeploymentJob:
    from ..common import _ansible_base_command

    command = f"{_ansible_base_command(node, 'observability_stack.yml')}"
    job = create_job(db, action="deploy-observability", command=command, node_id=node.id)

    return run_job_async(db, job, cwd=settings.project_root)


# Simple in-process page cache for Loki file-history (45s TTL, DDR D3)
_LOKI_PAGE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LOKI_PAGE_CACHE_TTL_S = 45.0


def _service_log_path(db: Session, service: "ServiceInstance", log_path: str = "") -> str:
    """Resolve a log file path from the request or service contract."""
    if log_path:
        return log_path
    contract = json.loads(service.config_json or "{}")
    paths = contract.get("log_paths") or []
    if paths:
        return paths[0]
    # Fall back to first target's container log convention
    return f"/var/log/{service.service_key}/app.log"


def _service_volume_mappings(service: "ServiceInstance") -> list[tuple[str, str]]:
    """Return rendered host-to-container volume mappings from the saved contract."""
    try:
        contract = json.loads(service.config_json or "{}")
    except json.JSONDecodeError:
        contract = {}
    mappings: list[tuple[str, str]] = []
    for volume in contract.get("volumes") or []:
        if isinstance(volume, str):
            parts = volume.split(":")
            if len(parts) >= 2 and parts[0] and parts[1]:
                mappings.append((parts[0].rstrip("/"), parts[1].rstrip("/")))
        elif isinstance(volume, dict):
            source = str(volume.get("source") or volume.get("host") or "").rstrip("/")
            target = str(volume.get("target") or volume.get("container") or "").rstrip("/")
            if source and target:
                mappings.append((source, target))
    return mappings


def _container_path_for_host_path(service: "ServiceInstance", path: str) -> str | None:
    normalized = path.rstrip("/")
    for source, target in _service_volume_mappings(service):
        if normalized == source:
            return target
        if normalized.startswith(source + "/"):
            return target + normalized[len(source):]
    return None


def _host_path_for_container_path(service: "ServiceInstance", path: str) -> str:
    normalized = path.rstrip("/")
    for source, target in _service_volume_mappings(service):
        if normalized == target:
            return source
        if normalized.startswith(target + "/"):
            return source + normalized[len(target):]
    return path


def _run_container_command(
    service: "ServiceInstance",
    args: list[str],
    *,
    timeout: int = 30,
) -> tuple[bool, str, str]:
    """Run a non-shell docker command on the service's declared node only."""
    node = service.node
    if node is None:
        return False, "", "Service has no assigned node."
    from ..discovery import resolve_connection_mode

    mode = resolve_connection_mode(node)
    container = service.container_name or service.service_key
    if mode == "local":
        from ..docker_runtime import exec_container

        return exec_container(container, args)
    else:
        if not node.host:
            return False, "", "Remote node has no host address."
        remote_command = " ".join(["docker", "exec", container, *args])
        command = [
            "ansible",
            f"{node.host},",
            "-m",
            "command",
            "-a",
            remote_command,
            "-u",
            node.ssh_user or "ubuntu",
        ]
        if node.ssh_key_path:
            command.extend(["--private-key", node.ssh_key_path])
    try:
        result = subprocess.run(
            command,
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return False, "", str(exc)
    if result.returncode != 0:
        return False, result.stdout or "", (result.stderr or result.stdout or "Container command failed.").strip()
    return True, result.stdout or "", ""


def _archive_filename(archive: LogArchive) -> str:
    path = getattr(archive, "path", "") or ""
    return path.rsplit("/", 1)[-1] if path else f"archive-{archive.id}.log"


def get_ingestion_stats(db: Session | None = None) -> dict:
    """Query Loki for live ingestion rate, hourly error rate, and projected archive size."""
    try:
        from ...settings import settings
        loki_url = settings.loki_base_url
    except Exception:
        loki_url = "http://localhost:9021"

    ingestion_rate = 0.0
    error_count_current = 0
    error_count_previous = 0
    archive_size_bytes = 0
    loki_reachable = False

    if db is not None:
        archive_size_bytes = int(
            db.scalar(
                select(func.coalesce(func.sum(LogArchive.size_bytes), 0)).where(LogArchive.readable == "yes")
            )
            or 0
        )

    # Query 1: Live ingestion rate
    try:
        resp = requests.get(
            f"{loki_url}/loki/api/v1/query",
            params={"query": 'sum(rate({service_name=~".+"}[1h]))'},
            timeout=5,
        )
        if resp.status_code == 200:
            loki_reachable = True
            data = resp.json()
            result = data.get("data", {}).get("result", [])
            if result:
                ingestion_rate = float(result[0].get("value", [0, 0])[1])
    except Exception:
        pass

    # Query 2: Current hour error count
    try:
        resp = requests.get(
            f"{loki_url}/loki/api/v1/query",
            params={"query": 'sum(count_over_time({service_name=~".+"} |~ "(?i)error|exception|fail|fatal|crit"[1h]))'},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("data", {}).get("result", [])
            if result:
                error_count_current = int(float(result[0].get("value", [0, 0])[1]))
    except Exception:
        pass

    # Query 3: Previous hour error count for delta
    try:
        resp = requests.get(
            f"{loki_url}/loki/api/v1/query",
            params={"query": 'sum(count_over_time({service_name=~".+"} |~ "(?i)error|exception|fail|fatal|crit"[1h] offset 1h))'},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("data", {}).get("result", [])
            if result:
                error_count_previous = int(float(result[0].get("value", [0, 0])[1]))
    except Exception:
        pass

    # Compute delta
    if error_count_previous > 0:
        error_delta_pct = round(((error_count_current - error_count_previous) / error_count_previous) * 100, 1)
    else:
        error_delta_pct = 0.0 if error_count_current == 0 else 100.0

    # Format ingestion rate for display (blank-style zeros when Loki unreachable)
    if not loki_reachable:
        rate_display = ""
    elif ingestion_rate >= 1000:
        rate_display = f"{ingestion_rate / 1000:.1f}K/s"
    else:
        rate_display = f"{ingestion_rate:.0f}/s"

    return {
        "loki_reachable": loki_reachable,
        "ingestion_rate": ingestion_rate if loki_reachable else 0.0,
        "ingestion_rate_display": rate_display,
        "error_count_current_hour": error_count_current if loki_reachable else 0,
        "error_count_previous_hour": error_count_previous if loki_reachable else 0,
        "error_delta_pct": error_delta_pct if loki_reachable else 0.0,
        # No projected/fake size — only real measured value if set above (currently 0)
        "archive_size_bytes": archive_size_bytes,
    }


def service_file_tail(db: Session, service: "ServiceInstance", log_path: str = "", tail_lines: int = 100) -> dict:
    """Tail a real bound log file from the service container or its host."""
    node = service.node
    if not node:
        return {"lines": [], "source": "file_live", "error": "Service has no assigned node", "log_path": log_path or "", "node": "", "total_lines": 0}

    log_path = _service_log_path(db, service, log_path)
    safe_tail = max(1, min(int(tail_lines), 5000))
    node_label = getattr(node, "host", None) or getattr(node, "name", None) or str(node.id)

    container_path = _container_path_for_host_path(service, log_path)
    if container_path:
        ok, output, container_error = _run_container_command(
            service,
            ["tail", "-n", str(safe_tail), container_path],
        )
        if ok:
            raw_lines = [line for line in output.splitlines() if line.strip()]
            now = datetime.utcnow()
            lines = [
                {
                    "timestamp": (now - timedelta(seconds=(len(raw_lines) - index))).strftime("%Y-%m-%dT%H:%M:%S"),
                    "level": _detect_log_level(message),
                    "message": message,
                    "source": f"file:{log_path}",
                }
                for index, message in enumerate(raw_lines[-safe_tail:])
            ]
            return {
                "lines": lines,
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": len(lines),
            }

    # Real remote tail when not in local_mode
    if not settings.local_mode and node.environment != "local":
        try:
            import subprocess

            inventory = node.host
            user = node.ssh_user or "ubuntu"
            key_arg = ["--private-key", node.ssh_key_path] if node.ssh_key_path else []
            cmd = [
                "ansible",
                inventory,
                "-m",
                "shell",
                "-a",
                f"tail -n {safe_tail} {log_path}",
                "-u",
                user,
                *key_arg,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(settings.project_root))
            if proc.returncode == 0 and proc.stdout:
                raw_lines = [ln for ln in proc.stdout.splitlines() if ln.strip() and not ln.startswith(inventory)]
                lines = []
                now = datetime.utcnow()
                for i, msg in enumerate(raw_lines[-safe_tail:]):
                    # Strip ansible host prefix if present
                    if " | " in msg and msg.split(" | ", 1)[0].strip() in (inventory, "CHANGED", "SUCCESS"):
                        continue
                    if ">>" in msg:
                        msg = msg.split(">>", 1)[-1].strip()
                    lines.append({
                        "timestamp": (now - timedelta(seconds=(len(raw_lines) - i))).strftime("%Y-%m-%dT%H:%M:%S"),
                        "level": _detect_log_level(msg),
                        "message": msg,
                        "source": f"file:{log_path}",
                    })
                if lines:
                    return {
                        "lines": lines,
                        "source": "file_live",
                        "log_path": log_path,
                        "node": node_label,
                        "total_lines": len(lines),
                    }
        except Exception as exc:
            return {
                "lines": [],
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": 0,
                "error": f"SSH/Ansible tail failed: {exc}",
            }

    # Local host: try real file tail if path exists
    from pathlib import Path

    path = Path(log_path)
    if path.is_file():
        try:
            # Efficient-ish: read last N lines
            with path.open("r", errors="replace") as fh:
                content = fh.readlines()
            selected = content[-safe_tail:]
            now = datetime.utcnow()
            lines = []
            for i, msg in enumerate(selected):
                msg = msg.rstrip("\n")
                lines.append({
                    "timestamp": (now - timedelta(seconds=(len(selected) - i))).strftime("%Y-%m-%dT%H:%M:%S"),
                    "level": _detect_log_level(msg),
                    "message": msg,
                    "source": f"file:{log_path}",
                })
            return {
                "lines": lines,
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": len(lines),
            }
        except Exception as exc:
            return {
                "lines": [],
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": 0,
                "error": str(exc),
            }

    return {
        "lines": [],
        "source": "file_live",
        "log_path": log_path,
        "node": node_label,
        "total_lines": 0,
        "error": container_error if container_path else "Log file not available on the declared node",
    }


def service_file_history(
    db: Session,
    service: "ServiceInstance",
    log_path: str = "",
    page: int = 1,
    page_size: int = 50,
    cursor: str = "",
) -> dict:
    """Query Loki for historical file-based logs using file labels and cursor pagination."""
    import base64
    import time

    try:
        from ...settings import settings as _settings

        loki_url = _settings.loki_base_url
    except Exception:
        loki_url = "http://localhost:9021"

    log_path = _service_log_path(db, service, log_path)
    cache_key = f"{service.id}:{log_path}:{page}:{page_size}:{cursor or ''}"
    now_ts = time.time()
    cached = _LOKI_PAGE_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) < _LOKI_PAGE_CACHE_TTL_S:
        return cached[1]

    # Prune expired cache entries opportunistically
    expired = [k for k, (ts, _) in _LOKI_PAGE_CACHE.items() if now_ts - ts >= _LOKI_PAGE_CACHE_TTL_S]
    for k in expired:
        _LOKI_PAGE_CACHE.pop(k, None)

    basename = log_path.split("/")[-1]
    selector = "{" + f'filename=~".*{escape_query_regex_literal(basename)}.*"' + "}"

    lines: list[dict[str, Any]] = []
    total_count = 0
    next_cursor = None
    previous_cursor = None
    loki_reachable = False

    try:
        count_resp = requests.get(
            f"{loki_url}/loki/api/v1/query",
            params={"query": f"count_over_time({selector}[720h])"},
            timeout=5,
        )
        if count_resp.status_code == 200:
            loki_reachable = True
            result = count_resp.json().get("data", {}).get("result", [])
            if result:
                total_count = int(float(result[0].get("value", [0, 0])[1]))
    except Exception:
        pass

    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1

    if loki_reachable:
        try:
            end_ns = str(int(time.time()) * 1_000_000_000)
            direction = "older"
            anchor_ns = end_ns
            if cursor:
                try:
                    cursor_data = json.loads(base64.b64decode(cursor))
                    direction = "newer" if cursor_data.get("direction") == "newer" else "older"
                    anchor_ns = str(cursor_data.get("anchor_ts_ns", end_ns))
                except Exception:
                    direction = "older"
                    anchor_ns = end_ns
            params = {
                "query": selector,
                "limit": str(page_size),
                "direction": "forward" if direction == "newer" else "backward",
            }
            params["start" if direction == "newer" else "end"] = anchor_ns

            resp = requests.get(
                f"{loki_url}/loki/api/v1/query_range",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                streams = resp.json().get("data", {}).get("result", [])
                timestamped_lines: list[tuple[int, dict[str, Any]]] = []
                for stream in streams:
                    for ts_ns, msg in stream.get("values", []):
                        timestamped_lines.append((int(ts_ns), {
                            "timestamp": datetime.utcfromtimestamp(int(ts_ns) / 1e9).strftime("%Y-%m-%dT%H:%M:%S"),
                            "level": _detect_log_level(msg),
                            "message": msg,
                            "source": "file_history",
                        }))
                timestamped_lines.sort(key=lambda item: item[0])
                lines = [item[1] for item in timestamped_lines]
                if timestamped_lines:
                    oldest_ns = timestamped_lines[0][0]
                    newest_ns = timestamped_lines[-1][0]
                    cursor_payload = {
                        "anchor_ts_ns": oldest_ns - 1,
                        "direction": "older",
                        "page": page + 1,
                    }
                    next_cursor = base64.b64encode(json.dumps(cursor_payload).encode()).decode()
                    previous_payload = {
                        "anchor_ts_ns": newest_ns + 1,
                        "direction": "newer",
                        "page": max(1, page - 1),
                    }
                    previous_cursor = base64.b64encode(json.dumps(previous_payload).encode()).decode()
        except Exception:
            pass

    payload = {
        "lines": lines,
        "source": "file_history",
        "log_path": log_path,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "next_cursor": next_cursor,
        "previous_cursor": previous_cursor,
        "error": None if (loki_reachable or lines) else "No file history from Loki",
    }
    _LOKI_PAGE_CACHE[cache_key] = (now_ts, payload)
    return payload


def _detect_log_level(message: str) -> str:
    """Detect log level from a raw log message string."""
    msg_upper = message.upper()
    if any(kw in msg_upper for kw in ["ERROR", "ERR ", "CRITICAL", "FATAL"]):
        return "ERROR"
    if any(kw in msg_upper for kw in ["WARN", "WARNING"]):
        return "WARN"
    if "DEBUG" in msg_upper:
        return "DEBUG"
    return "INFO"


def view_log_archive(db: Session, service: "ServiceInstance", archive_id: int, max_lines: int = 300) -> dict:
    """Preview the first N lines of a log archive file."""
    from pathlib import Path

    archive = db.scalar(
        select(LogArchive).where(LogArchive.id == archive_id, LogArchive.service_id == service.id)
    )
    if not archive:
        return {"archive_id": archive_id, "filename": "", "error": "Archive not found", "lines": [], "total_lines": 0, "truncated": False}

    filename = _archive_filename(archive)
    path = Path(archive.path)

    # Prefer real file content when the path exists on disk
    if path.is_file():
        try:
            with path.open("r", errors="replace") as fh:
                lines = []
                for i, line in enumerate(fh):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n"))
            return {
                "archive_id": archive_id,
                "filename": filename,
                "lines": lines,
                "total_lines": len(lines),
                "truncated": len(lines) >= max_lines,
            }
        except Exception as exc:
            return {
                "archive_id": archive_id,
                "filename": filename,
                "error": str(exc),
                "lines": [],
                "total_lines": 0,
                "truncated": False,
            }

    container_path = _container_path_for_host_path(service, archive.path)
    if container_path:
        safe_max = max(1, min(int(max_lines), 5000))
        ok, output, error = _run_container_command(service, ["head", "-n", str(safe_max + 1), container_path])
        if ok:
            all_lines = output.splitlines()
            return {
                "archive_id": archive_id,
                "filename": filename,
                "lines": all_lines[:safe_max],
                "total_lines": len(all_lines[:safe_max]),
                "truncated": len(all_lines) > safe_max,
            }
        return {
            "archive_id": archive_id,
            "filename": filename,
            "lines": [],
            "total_lines": 0,
            "truncated": False,
            "error": error,
        }

    return {
        "archive_id": archive_id,
        "filename": filename,
        "lines": [],
        "total_lines": 0,
        "truncated": False,
        "error": f"Archive file not available on disk: {archive.path}",
    }


def download_log_archive(db: Session, service: "ServiceInstance", archive_id: int) -> dict:
    """Prepare a single log archive file for download (metadata + optional path)."""
    from pathlib import Path

    archive = db.scalar(
        select(LogArchive).where(LogArchive.id == archive_id, LogArchive.service_id == service.id)
    )
    if not archive:
        return {"error": "Archive not found", "ready": False}

    filename = _archive_filename(archive)
    path = Path(archive.path)
    content_type = "application/gzip" if filename.endswith(".gz") else "text/plain"
    if not path.is_file():
        container_path = _container_path_for_host_path(service, archive.path)
        if container_path and not filename.endswith(".gz"):
            ok, output, error = _run_container_command(service, ["cat", container_path], timeout=60)
            if ok:
                return {
                    "archive_id": archive_id,
                    "filename": filename,
                    "path": None,
                    "content_type": content_type,
                    "ready": True,
                    "content": output,
                }
            return {
                "archive_id": archive_id,
                "filename": filename,
                "path": None,
                "content_type": content_type,
                "ready": False,
                "error": error,
                "content": None,
            }
        return {
            "archive_id": archive_id,
            "filename": filename,
            "path": None,
            "content_type": content_type,
            "ready": False,
            "error": f"Archive file not available on disk: {archive.path}",
            "content": None,
        }
    return {
        "archive_id": archive_id,
        "filename": filename,
        "path": str(path),
        "content_type": content_type,
        "ready": True,
        "content": None,
    }


def bulk_download_log_archives(db: Session, service: "ServiceInstance", archive_ids: list) -> dict:
    """Prepare multiple log archive files as a ZIP bundle for download."""
    from pathlib import Path

    archives = []
    for aid in archive_ids:
        archive = db.scalar(
            select(LogArchive).where(LogArchive.id == aid, LogArchive.service_id == service.id)
        )
        if not archive:
            continue
        path = Path(archive.path)
        if path.is_file():
            archives.append({
                "archive_id": aid,
                "filename": _archive_filename(archive),
                "path": str(path),
                "content": None,
            })
            continue
        container_path = _container_path_for_host_path(service, archive.path)
        if container_path and not archive.path.endswith(".gz"):
            ok, output, _error = _run_container_command(service, ["cat", container_path], timeout=60)
            if ok:
                archives.append({
                    "archive_id": aid,
                    "filename": _archive_filename(archive),
                    "path": None,
                    "content": output,
                })

    if not archives:
        return {
            "error": "No readable archive files on disk for the selected ids",
            "files": [],
            "file_count": 0,
            "ready": False,
            "zip_filename": "",
        }

    zip_filename = f"{service.name}_logs_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.zip"
    return {
        "zip_filename": zip_filename,
        "files": archives,
        "file_count": len(archives),
        "ready": True,
    }


def service_log_analytics_chat(db: Session, service: "ServiceInstance", question: str, window: str = "current", history: list = None) -> dict:
    """cPlatform-style log analytics chat (Iktara Log Analyst).

    Gathers real diagnostics + live logs, calls Groq/Mistral, returns
    {success, answer, evidence, chart_data, suggestions}. Never invents success.
    """
    from ..llm import execute_llm_request, is_llm_configured, llm_status, safe_json_loads
    from ...settings import settings

    service_name = service.name
    max_logs = int(getattr(settings, "llm_max_logs", 80) or 80)

    diag = service_diagnostics(db, service, source_service=service)
    analysis = {}
    try:
        analysis = service_diagnostics_analysis(db, service, source_service=service) or {}
    except Exception:
        analysis = {}
    live_logs_data = service_live_logs(db, service, tail_lines=min(100, max_logs))
    log_lines = live_logs_data.get("lines", []) or []

    formatted_logs = []
    for line in log_lines[-max_logs:]:
        msg = line.get("message", "") or ""
        if len(msg) > 500:
            msg = msg[:500] + "... [truncated]"
        formatted_logs.append({
            "t": line.get("timestamp", ""),
            "lvl": line.get("level", "INFO"),
            "msg": msg,
        })

    issue_groups = []
    for insight in (analysis.get("insights") or [])[:5]:
        issue_groups.append({
            "category": insight.get("insight_id") or insight.get("title") or "issue",
            "severity": insight.get("severity") or "warning",
            "brief": insight.get("summary") or insight.get("title") or "",
            "count": 1,
            "evidence": (insight.get("evidence_refs") or [])[:2],
        })

    evidence_context = {
        "service": {
            "service_id": service.id,
            "service_name": service_name,
            "service_key": getattr(service, "service_key", ""),
            "status": getattr(service, "status", "unknown"),
            "container_name": getattr(service, "container_name", ""),
        },
        "live_status": {
            "overall_status": getattr(service, "status", "unknown"),
            "readiness": (diag.get("readiness") if isinstance(diag, dict) else {}) or {},
        },
        "issue_groups": issue_groups,
        "diagnostics_overview": analysis.get("overview") or analysis.get("summary") or "",
        "overall_severity": analysis.get("overall_severity") or "",
        "recent_logs": formatted_logs,
        "window": window or "current",
    }

    if not is_llm_configured():
        status = llm_status()
        return {
            "success": False,
            "answer": "",
            "evidence": formatted_logs[-4:],
            "chart_data": [],
            "suggestions": [
                "Configure PLATFORMOPS_LLM_PROVIDER and API keys",
                "Check live logs for errors",
                "Run diagnostics analysis",
            ],
            "error": f"LLM is not configured (provider={status.get('provider')}, has_key={status.get('has_api_key')})",
            "provider": status.get("provider"),
        }

    system_prompt = (
        "You are Iktara Log Analyst, an advanced operations AI diagnostics chatbot. "
        "Return strict JSON ONLY matching the requested schema. "
        "You are in a multi-turn conversation. You must focus entirely on answering the user's LATEST question "
        "located at the end of the prompt under the 'QUESTION:' block. "
        "Ignore any previous questions or instructions in the chat history; they are for reference only. "
        "If the user's question is conversational (e.g., greetings, asking your name, or asking about your capabilities), "
        "answer it directly and warmly in the 'answer' field, and ignore the diagnostic logs for that answer. "
        "If the question is diagnostic, answer it precisely using the provided system state, structured issue groups, and logs. "
        "Do not invent facts not present in the evidence. "
        "In your markdown answer, write concise paragraphs, lists, or bold key items. "
        "If referring to logs/errors, quote specific lines or timestamps using <span class=\"cited\">HH:MM:SS</span>. "
        "Provide up to 4 specific log lines as a JSON array in 'evidence' matching the actual logs. "
        "Generate a list of 10-30 numeric integer values for a mini error-rate bar chart in 'chart_data' that visually reflects "
        "the problem described in logs (use zeros if no errors). "
        "List 3 relevant natural language follow-up suggestions in 'suggestions'."
    )
    schema = {
        "answer": "string (markdown allowed, highly formatted, explaining root cause and answering user question specifically)",
        "evidence": [
            {"t": "string (timestamp HH:MM:SS)", "lvl": "INFO|WARN|ERR|DEBUG", "msg": "string"}
        ],
        "chart_data": [12, 18, 14, 22, 16],
        "suggestions": ["string"],
    }
    user_prompt_str = (
        f"Here is the context data for the service diagnostics:\n"
        f"{json.dumps(evidence_context, indent=2, default=str)}\n\n"
        f"Please analyze the context and logs above, and return strict JSON matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        f"CRITICAL INSTRUCTION:\n"
        f"Answering the following question is your primary directive. Address it directly and thoroughly.\n"
        f"QUESTION: {question}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-12:]:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)[:4000]})
    messages.append({"role": "user", "content": user_prompt_str})

    content = execute_llm_request(
        messages,
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    if not content:
        return {
            "success": False,
            "answer": "",
            "evidence": formatted_logs[-4:],
            "chart_data": [],
            "suggestions": [
                "Retry the question",
                "Check LLM API key / network",
                "Inspect raw live logs",
            ],
            "error": "LLM request failed or returned empty content",
            "provider": llm_status().get("provider"),
        }

    try:
        parsed = safe_json_loads(content)
        chart = parsed.get("chart_data") or []
        if not isinstance(chart, list):
            chart = []
        chart = [int(x) if isinstance(x, (int, float)) else 0 for x in chart][:30]
        evidence = parsed.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        suggestions = parsed.get("suggestions") or []
        if not isinstance(suggestions, list):
            suggestions = []
        return {
            "success": True,
            "answer": parsed.get("answer") or "No response generated.",
            "evidence": evidence[:8],
            "chart_data": chart,
            "suggestions": [str(s) for s in suggestions[:6]],
            "error": None,
            "provider": llm_status().get("provider"),
        }
    except Exception as exc:
        return {
            "success": False,
            "answer": "",
            "evidence": formatted_logs[-4:],
            "chart_data": [],
            "suggestions": [],
            "error": f"Failed to parse LLM JSON: {exc}",
            "provider": llm_status().get("provider"),
        }
