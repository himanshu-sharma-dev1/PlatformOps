from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import posixpath
import re
import shlex
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
from ...schemas import DiagnosticsBackfillJobOut
from ...security import redact_text
from ..common import (
    RUNNING_STATUSES,
    _service_display_name,
    record_event,
)


_JOB_SECRET_TEXT = re.compile(
    r"(?i)(\b(?:password|passwd|token|secret|api[_-]?key|authorization|bearer)\b\s*[:=]\s*)[^\s,;]+"
)
_DIAGNOSTICS_BACKFILL_COMMAND = "diagnostics-backfill"


def _safe_backfill_job_text(value: str | None) -> str:
    """Keep job result text useful without echoing credential-shaped values."""

    return _JOB_SECRET_TEXT.sub(r"\1[REDACTED]", redact_text(value))


def _serialize_backfill_job(job: DeploymentJob) -> DiagnosticsBackfillJobOut:
    """Return a stable diagnostics projection; never expose the executable command."""

    return DiagnosticsBackfillJobOut(
        id=job.id,
        service_id=job.service_id,
        node_id=job.node_id,
        type=job.action,
        status=job.status,
        output=_safe_backfill_job_text(job.output),
        error=_safe_backfill_job_text(job.error),
        created_at=job.created_at or datetime.utcnow(),
        started_at=job.started_at,
        ended_at=job.ended_at,
    )


def _sanitize_backfill_job_record(db: Session, job: DeploymentJob) -> DeploymentJob:
    """Persist only safe diagnostics fields before returning or allowing polling."""

    job.command = _DIAGNOSTICS_BACKFILL_COMMAND
    job.output = _safe_backfill_job_text(job.output)
    job.error = _safe_backfill_job_text(job.error)
    db.commit()
    db.refresh(job)
    return job


def _finish_backfill_job(
    db: Session,
    job: DeploymentJob,
    *,
    ok: bool,
    output: str = "",
    error: str = "",
) -> DeploymentJob:
    """Complete a synchronous backfill without committing unsafe result text."""

    return finish_job(
        db,
        job,
        ok=ok,
        output=_safe_backfill_job_text(output),
        error=_safe_backfill_job_text(error),
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
    try:
        contract = json.loads(service.config_json or "{}")
    except (TypeError, json.JSONDecodeError):
        contract = {}
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


_LOG_TIMESTAMP_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)


def _parse_log_timestamp(value: Any) -> datetime | None:
    """Parse Loki/docker/ISO timestamps into an aware UTC datetime.

    Epoch values are accepted in seconds, milliseconds, microseconds, or
    nanoseconds.  Keeping this parser local to diagnostics avoids silently
    applying a different timezone policy to history and live-tail filters.
    """

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            numeric = float(text)
        except (TypeError, ValueError):
            numeric = None
        if numeric is not None and re.fullmatch(r"\d+(?:\.\d+)?", text):
            magnitude = abs(numeric)
            divisor = 1.0 if magnitude < 1e11 else 1e3 if magnitude < 1e14 else 1e6 if magnitude < 1e17 else 1e9
            try:
                parsed = datetime.fromtimestamp(numeric / divisor, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        else:
            match = _LOG_TIMESTAMP_RE.match(text)
            candidate = match.group("stamp") if match else text
            candidate = candidate.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: Any) -> str:
    parsed = _parse_log_timestamp(value)
    if parsed is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return parsed.isoformat().replace("+00:00", "Z")


def service_live_logs(
    db: Session,
    service: ServiceInstance,
    *,
    tail_lines: int = 150,
    page_size: int = 100,
    cursor: int = 0,
    start: str | int | float | None = None,
    end: str | int | float | None = None,
) -> dict[str, Any]:
    safe_tail = max(10, min(tail_lines, 1000))
    safe_page = max(10, min(page_size, 1000))
    safe_cursor = max(0, cursor)
    fetch_size = min(5000, safe_tail + safe_cursor) if safe_cursor else safe_tail
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
                from ..remote import run_ssh

                result = run_ssh(
                    node,
                    ["docker", "logs", "--timestamps", "--tail", str(fetch_size), container],
                    timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "Container log command failed.").strip())
                raw_lines = (result.stdout or "").splitlines()
                # docker logs may write to stderr depending on the logging driver.
                if not raw_lines and result.stderr:
                    raw_lines = result.stderr.splitlines()
            for raw in raw_lines[-fetch_size:]:
                # Preserve the message byte-for-byte (apart from the transport
                # newline).  ``strip`` used to destroy indentation and made
                # long/Unicode markers impossible to correlate.
                message = raw.rstrip("\r\n")
                if message.endswith(" | SUCCESS => {") or message == "}":
                    continue
                timestamp = datetime.utcnow().isoformat() + "Z"
                first, separator, remainder = message.partition(" ")
                if separator and _parse_log_timestamp(first) is not None:
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

    # ``cursor`` is a bounded offset within the fetched tail.  Fetching a
    # larger tail for a non-zero cursor lets callers walk a stable snapshot
    # without pretending that docker's tail API is a durable event store.
    if not error and safe_cursor:
        if safe_cursor >= len(lines):
            lines = []
        else:
            lines = lines[safe_cursor:]
    if not error and (start is not None or end is not None):
        start_dt = _parse_log_timestamp(start) if start is not None else None
        end_dt = _parse_log_timestamp(end) if end is not None else None
        if start is not None and start_dt is None:
            error = "Invalid start timestamp"
            lines = []
        elif end is not None and end_dt is None:
            error = "Invalid end timestamp"
            lines = []
        elif start_dt and end_dt and start_dt > end_dt:
            error = "start timestamp must not be after end timestamp"
            lines = []
        elif start_dt or end_dt:
            filtered: list[dict[str, str]] = []
            for line in lines:
                line_dt = _parse_log_timestamp(line["timestamp"])
                if line_dt is None:
                    continue
                if start_dt and line_dt < start_dt:
                    continue
                if end_dt and line_dt > end_dt:
                    continue
                filtered.append(line)
            lines = filtered

    # This endpoint is a bounded real tail, not a fabricated pageable event
    # feed. Cursor values remain for response compatibility.
    total_available = len(lines)
    next_cursor = safe_cursor + len(lines)
    has_more_history = False
    source_state = "streaming" if not error and service.status in RUNNING_STATUSES else "unavailable" if error else "snapshot"
    if not error and not lines:
        error = "No container log lines available"
        source_state = "unavailable"
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
        "container_name": service.container_name or service.service_key,
        "error": error,
        "start": str(start) if start is not None else None,
        "end": str(end) if end is not None else None,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _encode_history_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_history_cursor(
    token: str,
    *,
    service_id: int,
    source: str,
    selector: str,
    page_size: int,
    start_ns: int | None,
    end_ns: int | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not token:
        return None, None
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "Invalid history cursor"
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None, "Invalid history cursor"
    expected = {
        "service_id": service_id,
        "source": source,
        "selector": selector,
        "page_size": page_size,
        "start_ns": start_ns,
        "end_ns": end_ns,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            return None, "History cursor does not match the selected source or time range"
    try:
        anchor = int(payload["anchor_ts_ns"])
    except (KeyError, TypeError, ValueError):
        return None, "Invalid history cursor"
    direction = payload.get("direction")
    if direction not in {"older", "newer"}:
        return None, "Invalid history cursor direction"
    payload["anchor_ts_ns"] = anchor
    payload["anchor_message"] = str(payload.get("anchor_message") or "")
    return payload, None


def _loki_history(
    db: Session,
    service: ServiceInstance,
    *,
    source: str,
    selector: str,
    page: int = 1,
    page_size: int = 100,
    cursor: str = "",
    log_path: str = "",
    start: str | int | float | None = None,
    end: str | int | float | None = None,
) -> dict[str, Any]:
    """Read one deterministic Loki page with strict source/range cursors."""

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 100), 1000))
    start_dt = _parse_log_timestamp(start) if start is not None else None
    end_dt = _parse_log_timestamp(end) if end is not None else None
    if start is not None and start_dt is None:
        return {"lines": [], "source": source, "log_path": log_path, "page": page, "page_size": page_size, "total_count": 0, "total_pages": 0, "next_cursor": None, "previous_cursor": None, "start": str(start) if start is not None else None, "end": str(end) if end is not None else None, "error": "Invalid start timestamp", "loki_reachable": False}
    if end is not None and end_dt is None:
        return {"lines": [], "source": source, "log_path": log_path, "page": page, "page_size": page_size, "total_count": 0, "total_pages": 0, "next_cursor": None, "previous_cursor": None, "start": str(start) if start is not None else None, "end": str(end) if end is not None else None, "error": "Invalid end timestamp", "loki_reachable": False}
    if start_dt and end_dt and start_dt > end_dt:
        return {"lines": [], "source": source, "log_path": log_path, "page": page, "page_size": page_size, "total_count": 0, "total_pages": 0, "next_cursor": None, "previous_cursor": None, "start": str(start) if start is not None else None, "end": str(end) if end is not None else None, "error": "start timestamp must not be after end timestamp", "loki_reachable": False}
    start_ns = int(start_dt.timestamp() * 1_000_000_000) if start_dt else None
    end_ns = int(end_dt.timestamp() * 1_000_000_000) if end_dt else None
    cursor_data, cursor_error = _decode_history_cursor(
        cursor,
        service_id=service.id,
        source=source,
        selector=selector,
        page_size=page_size,
        start_ns=start_ns,
        end_ns=end_ns,
    )
    base = {
        "lines": [], "source": source, "log_path": log_path, "page": page,
        "page_size": page_size, "total_count": 0, "total_pages": 0,
        "next_cursor": None, "previous_cursor": None, "start": str(start) if start is not None else None,
        "end": str(end) if end is not None else None, "loki_reachable": False,
    }
    if cursor_error:
        base["error"] = cursor_error
        return base

    loki_url = settings.loki_base_url.rstrip("/")
    total_count = 0
    try:
        count_params = {"query": f"count_over_time({selector}[720h])"}
        if start_ns is not None:
            count_params["start"] = str(start_ns)
        if end_ns is not None:
            count_params["end"] = str(end_ns)
        count_resp = requests.get(f"{loki_url}/loki/api/v1/query", params=count_params, timeout=5)
        if count_resp.status_code != 200:
            base["error"] = f"Loki unavailable (HTTP {count_resp.status_code})"
            return base
        count_data = count_resp.json()
        result = count_data.get("data", {}).get("result") or []
        if result:
            values = [item.get("value", [0, 0])[1] for item in result if item.get("value")]
            total_count = sum(int(float(value)) for value in values)
        base["loki_reachable"] = True
    except Exception as exc:
        base["error"] = f"Loki unavailable: {exc}"
        return base

    direction = cursor_data.get("direction") if cursor_data else "older"
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
    anchor_ns = int(cursor_data["anchor_ts_ns"]) if cursor_data else (end_ns or now_ns)
    query_start = start_ns
    query_end = end_ns
    if direction == "older":
        query_end = min(query_end, anchor_ns) if query_end is not None else anchor_ns
    else:
        query_start = max(query_start, anchor_ns) if query_start is not None else anchor_ns
    params: dict[str, str] = {
        "query": selector,
        # Fetch beyond the visible page so equal-timestamp entries can be
        # separated by the cursor's message tie-breaker without gaps.
        "limit": str(min(5000, max(page_size + 1000, page_size * 4))),
        "direction": "forward" if direction == "newer" else "backward",
    }
    if query_start is not None:
        params["start"] = str(query_start)
    if query_end is not None:
        params["end"] = str(query_end)
    try:
        response = requests.get(f"{loki_url}/loki/api/v1/query_range", params=params, timeout=10)
        if response.status_code != 200:
            base["error"] = f"Loki history query failed (HTTP {response.status_code})"
            return base
        timestamped: list[tuple[int, str, dict[str, Any]]] = []
        seen: set[tuple[int, str]] = set()
        for stream in response.json().get("data", {}).get("result") or []:
            for raw_ts, raw_message in stream.get("values") or []:
                try:
                    ts_ns = int(raw_ts)
                except (TypeError, ValueError):
                    continue
                message = str(raw_message)
                key = (ts_ns, message)
                if key in seen:
                    continue
                seen.add(key)
                timestamped.append((ts_ns, message, {
                    "timestamp": _timestamp_text(ts_ns),
                    "level": _detect_log_level(message),
                    "message": message,
                    "source": source,
                }))
        timestamped.sort(key=lambda item: (item[0], item[1]))
        if cursor_data:
            boundary = (anchor_ns, str(cursor_data.get("anchor_message") or ""))
            if direction == "older":
                timestamped = [item for item in timestamped if (item[0], item[1]) < boundary]
            else:
                timestamped = [item for item in timestamped if (item[0], item[1]) > boundary]
        if len(timestamped) > page_size:
            timestamped = timestamped[-page_size:] if direction == "older" else timestamped[:page_size]
        lines = [item[2] for item in timestamped]
        base.update({"lines": lines, "total_count": total_count, "total_pages": (total_count + page_size - 1) // page_size if total_count else 0})
        if not timestamped:
            base["error"] = "No matching history for the selected source and time range" if total_count == 0 else "No history at this cursor"
            return base
        oldest_ns = timestamped[0][0]
        newest_ns = timestamped[-1][0]
        common = {"version": 1, "service_id": service.id, "source": source, "selector": selector, "page_size": page_size, "start_ns": start_ns, "end_ns": end_ns}
        # A full page may have more records; a short page is terminal.  The
        # count query is advisory only, so this remains correct if counts lag.
        if len(timestamped) >= page_size:
            base["next_cursor"] = _encode_history_cursor({
                **common, "anchor_ts_ns": oldest_ns,
                "anchor_message": timestamped[0][1],
                "direction": "older", "page": page + 1,
            })
        if cursor_data or page > 1:
            base["previous_cursor"] = _encode_history_cursor({
                **common, "anchor_ts_ns": newest_ns,
                "anchor_message": timestamped[-1][1],
                "direction": "newer", "page": max(1, page - 1),
            })
        return base
    except Exception as exc:
        base["error"] = f"Loki history query failed: {exc}"
        return base


def service_container_history(
    db: Session,
    service: ServiceInstance,
    *,
    page: int = 1,
    page_size: int = 100,
    cursor: str = "",
    start: str | int | float | None = None,
    end: str | int | float | None = None,
) -> dict[str, Any]:
    """Query Loki for historical stdout/stderr for exactly one container."""

    container = service.container_name or service.service_key
    escaped = str(container).replace("\\", "\\\\").replace('"', '\\"')
    selector = "{" + f'container_name="{escaped}"' + "}"
    result = _loki_history(
        db,
        service,
        source="container_history",
        selector=selector,
        page=page,
        page_size=page_size,
        cursor=cursor,
        log_path=container,
        start=start,
        end=end,
    )
    result["container_name"] = container
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
    log_paths = _configured_log_paths(service)
    existing = list(db.scalars(select(LogArchive).where(LogArchive.service_id == service.id)).all())
    existing_by_path = {os.path.normpath(str(item.path)): item for item in existing}
    discovered: dict[str, tuple[int, int, str, str | None]] = {}

    for configured_path in log_paths:
        container_path = _container_path_for_host_path(service, configured_path)
        if container_path:
            # A service volume is authoritative.  Never fall back to a host
            # scan when the declared target cannot be enumerated: that would
            # turn a remote command failure into a misleading empty archive
            # index (and could expose an unrelated local path).
            remote_archives, remote_error = _remote_archive_files(db, service, configured_path, container_path)
            if remote_error:
                raise RuntimeError(remote_error)
            for host_path, size, line_count, reason, checksum in remote_archives:
                discovered[os.path.normpath(host_path)] = (size, line_count, reason, checksum)
            continue

        local_path = Path(configured_path)
        candidates = [local_path] if local_path.is_file() else list(local_path.glob("*")) if local_path.is_dir() else []
        for candidate in candidates:
            if not _is_log_archive_name(candidate.name):
                continue
            # Symlinked paths are not archives owned by the configured log
            # root; following one could expose arbitrary host content.
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    path = str(candidate.resolve(strict=True))
                    size, line_count, checksum = _local_archive_stats(Path(path))
                    discovered[os.path.normpath(path)] = (size, line_count, "measured on declared service target", checksum)
                except OSError:
                    continue

    archives: list[LogArchive] = []
    for path, (size_bytes, line_count, reason, checksum) in sorted(discovered.items()):
        archive = existing_by_path.pop(path, None)
        if archive is None:
            archive = LogArchive(service_id=service.id, path=path)
            db.add(archive)
        archive.path = path
        archive.size_bytes = size_bytes
        archive.line_count = line_count
        archive.readable = "yes"
        archive.reason = reason
        # The ORM model intentionally stays backward compatible.  Expose the
        # measured checksum on the returned object and download metadata even
        # though old databases do not have a checksum column.
        archive.checksum_sha256 = checksum
        archives.append(archive)
    for stale in existing_by_path.values():
        db.delete(stale)
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


_MAX_REMOTE_ARCHIVE_ENTRIES = 1000
_LOG_ARCHIVE_NAME_RE = re.compile(r"^.+\.log(?:\.\d+)?(?:\.gz)?$", re.IGNORECASE | re.UNICODE)


def _is_log_archive_name(name: str) -> bool:
    """Keep archive discovery scoped to ordinary and rotated log names."""

    return bool(_LOG_ARCHIVE_NAME_RE.fullmatch(name))


def _safe_remote_child_path(root: str, name: str) -> str:
    """Join one directory entry without allowing path traversal or nesting."""

    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("remote archive entry contains an unsafe path component")
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError("remote archive entry contains control characters")
    normalized_root = posixpath.normpath(root)
    candidate = posixpath.normpath(posixpath.join(normalized_root, name))
    if candidate == normalized_root or not candidate.startswith(normalized_root.rstrip("/") + "/"):
        raise ValueError("remote archive entry escapes the configured log directory")
    return candidate


def _remote_command_number(
    service: ServiceInstance,
    args: list[str],
    *,
    label: str,
) -> tuple[int | None, str | None]:
    ok, output, error = _run_container_command(service, args)
    if not ok:
        return None, f"{label} command failed: {error or 'unknown container error'}"
    value = output.strip().splitlines()[0].strip().split()[0] if output.strip() else ""
    if not value.isdigit():
        return None, f"{label} command returned invalid metadata"
    return int(value), None


def _remote_archive_metadata(
    service: ServiceInstance,
    container_path: str,
    *,
    compressed: bool,
) -> tuple[int, int, str, str] | tuple[None, None, None, str]:
    """Read bounded metadata with BusyBox/GNU-compatible commands."""

    size: int | None = None
    size_errors: list[str] = []
    for args in (
        ["stat", "-c", "%s", container_path],
        ["stat", "-f", "%z", container_path],
        ["wc", "-c", container_path],
    ):
        parsed, error = _remote_command_number(service, args, label="archive size")
        if parsed is not None:
            size = parsed
            break
        if error:
            size_errors.append(error)
    if size is None:
        return None, None, None, "; ".join(size_errors)

    ok, output, error = _run_container_command(service, ["sha256sum", container_path])
    if not ok:
        ok, output, error = _run_container_command(service, ["shasum", "-a", "256", container_path])
    match = re.search(r"\b([0-9a-fA-F]{64})\b", output or "") if ok else None
    if not match:
        return None, None, None, f"archive checksum command failed: {error or 'invalid checksum output'}"

    line_count = 0
    reason = "remote target; compressed line count not measured" if compressed else "remote target"
    if not compressed:
        parsed, _line_error = _remote_command_number(service, ["wc", "-l", container_path], label="archive line count")
        if parsed is not None:
            line_count = parsed
        else:
            reason = "remote target; line count not measured"
    return size, line_count, reason, match.group(1).lower()


def _remote_archive_files(
    db: Session,
    service: ServiceInstance,
    configured_path: str,
    container_path: str,
) -> tuple[list[tuple[str, int, int, str, str]], str | None]:
    """Enumerate one declared container directory without GNU ``find``."""

    root = posixpath.normpath(container_path)
    root_symlink, _symlink_output, _symlink_error = _run_container_command(service, ["test", "-L", root])
    if root_symlink:
        return [], f"Declared log path is a symlink and cannot be indexed: {configured_path}"
    is_file, _file_output, _file_error = _run_container_command(service, ["test", "-f", root])
    if is_file:
        entries = [posixpath.basename(root)]
        directory = posixpath.dirname(root) or "/"
    else:
        is_dir, _dir_output, dir_error = _run_container_command(service, ["test", "-d", root])
        if not is_dir:
            return [], f"Unable to access declared log directory {configured_path}: {dir_error or 'not a directory'}"
        ok, output, error = _run_container_command(service, ["ls", "-1A", root])
        if not ok:
            return [], f"Unable to enumerate declared log directory {configured_path}: {error or 'ls failed'}"
        entries = [line.rstrip("\r") for line in output.splitlines() if line.rstrip("\r")]
        directory = root
    if len(entries) > _MAX_REMOTE_ARCHIVE_ENTRIES:
        return [], f"Declared log directory {configured_path} exceeds the archive entry limit"

    configured_norm = os.path.normpath(configured_path)
    discovered: list[tuple[str, int, int, str, str]] = []
    for name in entries:
        try:
            child = _safe_remote_child_path(directory, name)
        except ValueError as exc:
            return [], f"Unable to enumerate declared log directory {configured_path}: {exc}"
        if not _is_log_archive_name(posixpath.basename(child)):
            continue
        is_regular, _output, _regular_error = _run_container_command(service, ["test", "-f", child])
        if not is_regular:
            # A directory or device is not an archive; retain the bounded
            # enumeration contract and skip it without reading its contents.
            continue
        is_symlink, _output, _symlink_error = _run_container_command(service, ["test", "-L", child])
        if is_symlink:
            continue
        host_path = os.path.normpath(_host_path_for_container_path(service, child))
        if not (host_path == configured_norm or host_path.startswith(configured_norm.rstrip(os.sep) + os.sep)):
            return [], f"Archive candidate escapes the configured log directory: {host_path}"
        validated_path, path_error = _validated_service_log_path(db, service, host_path)
        if path_error:
            return [], f"Archive candidate is not allowed: {path_error}"
        metadata = _remote_archive_metadata(service, child, compressed=child.lower().endswith(".gz"))
        size, line_count, reason, checksum_or_error = metadata
        if size is None or line_count is None or reason is None:
            return [], f"Unable to read metadata for archive candidate {child}: {checksum_or_error}"
        discovered.append((validated_path, size, line_count, reason, checksum_or_error))
    return discovered, None


def _local_archive_stats(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    line_count = 0
    # The checksum covers the bytes delivered by download (including gzip
    # framing), while line_count is measured after decompression when needed.
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rb") as source:
        last_byte = b""
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            line_count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if last_byte and last_byte != b"\n":
        line_count += 1
    return path.stat().st_size, line_count, digest.hexdigest()


def backfill_service_logs(db: Session, service: ServiceInstance) -> dict[str, Any]:
    diagnostics = service_diagnostics(db, service)
    requirements = diagnostics["readiness"].get("backfill_requirements", {})
    command = "diagnostics-backfill-unresolved"
    if service.node is not None:
        from ..discovery import resolve_connection_mode

        if resolve_connection_mode(service.node) == "local":
            labels = {
                "service_name": service.name,
                "service_key": service.service_key,
                "container_name": service.container_name or service.service_key,
                "source_type": "file",
                "node_id": str(service.node_id),
            }
            import base64 as _b64

            encoded_paths = _b64.b64encode(json.dumps(_configured_log_paths(service)).encode("utf-8")).decode("ascii")
            encoded_labels = _b64.b64encode(json.dumps(labels).encode("utf-8")).decode("ascii")
            script_path = settings.resolve(settings.ansible_dir) / "playbooks" / "service_log_backfill.py"
            command = " ".join(
                [
                    "python3",
                    shlex.quote(str(script_path)),
                    "--loki_url",
                    shlex.quote(settings.loki_write_url.rstrip("/")),
                    "--log_paths_b64",
                    shlex.quote(encoded_paths),
                    "--labels_b64",
                    shlex.quote(encoded_labels),
                    "--allow_full_file",
                    "true",
                ]
            )
        else:
            command = "remote diagnostics log backfill is not available in this runtime"
    # Keep the worker command transient.  The generic job endpoint can then
    # safely expose this persisted row without disclosing source paths, labels,
    # or a remote URL embedded in the executable command.
    job = create_job(
        db,
        action="log-backfill",
        command=_DIAGNOSTICS_BACKFILL_COMMAND,
        service_id=service.id,
        node_id=service.node_id,
    )
    job._execution_command = command
    job._output_sanitizer = _safe_backfill_job_text
    ready = bool(requirements.get("ready"))
    missing = list(requirements.get("missing", []))
    if service.node is None:
        missing.append("node")
    elif "remote diagnostics log backfill" in command:
        missing.append("remote_backfill_runtime")
    output = f"Backfill not ready: {', '.join(missing) or 'requirements incomplete'}."
    ready = ready and not missing
    if ready:
        current_job = run_job_async(db, job, cwd=settings.project_root)
        summary = f"Log backfill job #{job.id} started for {service.container_name}."
    else:
        current_job = _finish_backfill_job(db, job, ok=False, output="", error=output)
        summary = output
    current_job = _sanitize_backfill_job_record(db, current_job)
    job_payload = _serialize_backfill_job(current_job)
    record_event(
        db,
        category="diagnostics",
        level="info" if ready else "warning",
        message=f"Log backfill {'started' if ready else 'blocked'} for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={
            "ready": ready,
            "missing": missing,
            "job_id": job_payload.id,
            "status": job_payload.status,
        },
    )
    return {
        "service_id": service.id,
        "ready": ready,
        "id": job_payload.id,
        "status": job_payload.status,
        "requirements": requirements,
        "job": job_payload,
        "summary": summary,
    }


def deploy_observability_stack(db: Session, node: Node) -> DeploymentJob:
    from ..common import _ansible_base_command

    command = f"{_ansible_base_command(node, 'observability_stack.yml')}"
    job = create_job(db, action="deploy-observability", command=command, node_id=node.id)

    return run_job_async(db, job, cwd=settings.project_root)


def _service_log_path(db: Session, service: "ServiceInstance", log_path: str = "") -> str:
    """Resolve a log file path from the request or service contract.

    This helper intentionally returns an empty string when a service has no
    configured log path.  A synthetic ``/var/log/<service>/app.log`` path is
    not evidence and caused false-positive diagnostics in local mode.
    """
    if log_path:
        return str(log_path)
    try:
        contract = json.loads(service.config_json or "{}")
    except (TypeError, json.JSONDecodeError):
        contract = {}
    paths = contract.get("log_paths") or []
    if paths:
        return str(paths[0])
    return ""


def _configured_log_paths(service: "ServiceInstance") -> list[str]:
    try:
        contract = json.loads(service.config_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return []
    raw_paths = contract.get("log_paths") or []
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    return [str(item).strip() for item in raw_paths if str(item).strip()]


def _validated_service_log_path(
    db: Session,
    service: "ServiceInstance",
    requested: str = "",
) -> tuple[str, str | None]:
    """Accept only a path declared by the selected service contract.

    A configured directory may contain rotated files, while a configured file
    is exact-match only.  Both lexical ``..`` traversal and symlink escapes
    are rejected before any local/remote command is run.
    """

    configured = _configured_log_paths(service)
    if not configured:
        return "", "No file log paths are configured for this service"
    candidate = str(requested or configured[0]).strip()
    if not candidate or "\x00" in candidate:
        return "", "Invalid log path"
    candidate_path = Path(candidate)
    if not candidate_path.is_absolute():
        return "", "Log path must be absolute"
    normalized_candidate = os.path.normpath(candidate)
    if any(part == ".." for part in Path(candidate).parts):
        return "", "Log path traversal is not allowed"
    allowed = False
    for raw_root in configured:
        root = os.path.normpath(raw_root)
        if normalized_candidate == root:
            allowed = True
            break
        # A configured directory can be remote and therefore absent locally;
        # use lexical containment as well as an on-disk directory check.
        root_path = Path(root)
        if normalized_candidate.startswith(root.rstrip(os.sep) + os.sep) and (root_path.is_dir() or not root_path.exists()):
            allowed = True
            break
    if not allowed:
        return "", "Log path is not configured for this service"
    try:
        resolved = Path(normalized_candidate).resolve(strict=False)
        for raw_root in configured:
            root_path = Path(os.path.normpath(raw_root)).resolve(strict=False)
            if resolved == root_path or root_path in resolved.parents:
                return str(resolved), None
    except OSError:
        return "", "Unable to validate the configured log path"
    # A lexical child can still be a symlink outside the configured root.  Do
    # not hand that path to a local reader or remote command.
    return "", "Log path escapes the configured service root"


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
        from ..remote import run_ssh

        command = ["docker", "exec", container, *args]
    try:
        result = run_ssh(node, command, timeout=timeout)
    except Exception as exc:
        return False, "", str(exc)
    if result.returncode != 0:
        return False, result.stdout or "", (result.stderr or result.stdout or "Container command failed.").strip()
    return True, result.stdout or "", ""


def _archive_filename(archive: LogArchive) -> str:
    path = getattr(archive, "path", "") or ""
    raw = Path(str(path)).name if path else f"archive-{archive.id}.log"
    # ZIP member names and Content-Disposition values must not contain a path
    # component, control character, or an empty name.
    safe = re.sub(r"[^\w.()@+\- ]", "_", raw, flags=re.UNICODE).strip(" .")
    return safe or f"archive-{archive.id}.log"


def _archive_checksum(path: Path) -> str | None:
    try:
        return _local_archive_stats(path)[2]
    except (OSError, EOFError, gzip.BadGzipFile):
        return None


def _remote_archive_bytes(service: "ServiceInstance", container_path: str) -> tuple[bytes | None, str | None]:
    """Fetch exact remote archive bytes through portable base64 transport."""

    ok, encoded, error = _run_container_command(service, ["base64", container_path], timeout=60)
    if not ok:
        return None, error or "Remote archive read failed"
    try:
        return base64.b64decode("".join(encoded.split()).encode("ascii"), validate=True), None
    except (ValueError, UnicodeEncodeError) as exc:
        return None, f"Remote archive returned invalid base64: {exc}"


def _archive_db_row(db: Session, service: "ServiceInstance", archive_id: int) -> tuple[LogArchive | None, str | None]:
    archive = db.scalar(select(LogArchive).where(LogArchive.id == archive_id, LogArchive.service_id == service.id))
    if archive is None:
        return None, "Archive not found"
    _, path_error = _validated_service_log_path(db, service, str(archive.path))
    if path_error:
        return None, f"Archive path is not allowed: {path_error}"
    return archive, None


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

    node_label = getattr(node, "host", None) or getattr(node, "name", None) or str(node.id)
    log_path, path_error = _validated_service_log_path(db, service, log_path)
    if path_error:
        return {
            "lines": [], "source": "file_live", "error": path_error,
            "log_path": log_path or str(log_path or ""), "node": node_label, "total_lines": 0,
        }
    selected_path = Path(log_path)
    if selected_path.is_dir():
        candidates = sorted(
            (item for item in selected_path.glob("*.log*") if item.is_file() and not item.is_symlink()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            log_path = str(candidates[0].resolve())
        else:
            return {"lines": [], "source": "file_live", "error": "No log files are available under the configured path", "log_path": log_path, "node": node_label, "total_lines": 0}
    safe_tail = max(1, min(int(tail_lines), 5000))
    container_error = ""

    container_path = _container_path_for_host_path(service, log_path)
    if container_path:
        ok, output, container_error = _run_container_command(
            service,
            ["tail", "-n", str(safe_tail), container_path],
        )
        if ok:
            raw_lines = output.splitlines()
            now = datetime.utcnow()
            lines = [
                {
                    "timestamp": _timestamp_text(_parse_log_timestamp(message.split(" ", 1)[0]) or (now - timedelta(seconds=(len(raw_lines) - index)))),
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
                "error": "Log file is empty" if not lines else None,
            }

    from ..discovery import resolve_connection_mode

    connection_mode = resolve_connection_mode(node)
    # Real remote tail when not in local_mode.  A remote failure is terminal;
    # never read a similarly named host file as a fallback.
    if connection_mode != "local":
        try:
            from ..remote import run_ssh

            proc = run_ssh(node, ["tail", "-n", str(safe_tail), log_path], timeout=30)
            if proc.returncode == 0 and proc.stdout:
                raw_lines = proc.stdout.splitlines()
                lines = []
                now = datetime.utcnow()
                for i, msg in enumerate(raw_lines[-safe_tail:]):
                    lines.append({
                        "timestamp": _timestamp_text(_parse_log_timestamp(msg.split(" ", 1)[0]) or (now - timedelta(seconds=(len(raw_lines) - i)))),
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
                        "error": None,
                    }
            return {
                "lines": [],
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": 0,
                "error": (
                    (proc.stderr or proc.stdout or "Remote log file is empty").strip()
                    if proc.returncode != 0
                    else "Remote log file is empty"
                ),
            }
        except Exception as exc:
            return {
                "lines": [],
                "source": "file_live",
                "log_path": log_path,
                "node": node_label,
                "total_lines": 0,
                "error": f"Strict SSH tail failed: {exc}",
            }

    # Local host: try real file tail if path exists.
    if connection_mode != "local":
        return {
            "lines": [], "source": "file_live", "log_path": log_path,
            "node": node_label, "total_lines": 0,
            "error": container_error or "Log file not available on the declared remote node",
        }
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
                msg = msg.rstrip("\r\n")
                lines.append({
                    "timestamp": _timestamp_text(_parse_log_timestamp(msg.split(" ", 1)[0]) or (now - timedelta(seconds=(len(selected) - i)))),
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
                "error": "Log file is empty" if not lines else None,
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
    start: str | int | float | None = None,
    end: str | int | float | None = None,
) -> dict:
    """Query Loki for one configured file path with strict cursor semantics."""

    resolved_path, path_error = _validated_service_log_path(db, service, log_path)
    if path_error:
        return {
            "lines": [], "source": "file_history", "log_path": log_path,
            "page": max(1, int(page or 1)), "page_size": max(1, min(int(page_size or 50), 1000)),
            "total_count": 0, "total_pages": 0, "next_cursor": None,
            "previous_cursor": None, "start": str(start) if start is not None else None,
            "end": str(end) if end is not None else None, "error": path_error,
        }
    selected_path = Path(resolved_path)
    if selected_path.is_dir():
        candidates = sorted(
            (item for item in selected_path.glob("*.log*") if item.is_file() and not item.is_symlink()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            resolved_path = str(candidates[0].resolve())
    # filename is used by the existing Alloy/Promtail labels.  Exact path is
    # included when available so similarly named services cannot cross-match.
    escaped = resolved_path.replace("\\", "\\\\").replace('"', '\\"')
    selector = "{" + f'filename="{escaped}"' + "}"
    return _loki_history(
        db,
        service,
        source="file_history",
        selector=selector,
        page=page,
        page_size=page_size,
        cursor=cursor,
        log_path=resolved_path,
        start=start,
        end=end,
    )


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
    archive, archive_error = _archive_db_row(db, service, archive_id)
    if archive is None:
        return {"archive_id": archive_id, "filename": "", "error": archive_error, "lines": [], "total_lines": 0, "truncated": False}

    filename = _archive_filename(archive)
    path = Path(archive.path)
    safe_max = max(1, min(int(max_lines or 300), 5000))

    # Prefer real file content when the path exists on disk
    if path.is_file() and not path.is_symlink():
        try:
            opener = gzip.open if filename.lower().endswith(".gz") else open
            with opener(path, "rt", errors="replace") as fh:
                lines = []
                for i, line in enumerate(fh):
                    if i >= safe_max:
                        break
                    lines.append(line.rstrip("\r\n"))
            truncated = False
            with opener(path, "rt", errors="replace") as fh:
                for i, _ in enumerate(fh):
                    if i >= safe_max:
                        truncated = True
                        break
            return {
                "archive_id": archive_id,
                "filename": filename,
                "lines": lines,
                "total_lines": len(lines),
                "truncated": truncated,
                "checksum_sha256": _archive_checksum(path),
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
        remote_bytes, error = _remote_archive_bytes(service, container_path)
        if remote_bytes is not None:
            try:
                decoded = gzip.decompress(remote_bytes) if filename.lower().endswith(".gz") else remote_bytes
                text_content = decoded.decode("utf-8", errors="replace")
                all_lines = text_content.splitlines()
                return {
                    "archive_id": archive_id,
                    "filename": filename,
                    "lines": all_lines[:safe_max],
                    "total_lines": len(all_lines[:safe_max]),
                    "truncated": len(all_lines) > safe_max,
                    "checksum_sha256": hashlib.sha256(remote_bytes).hexdigest(),
                }
            except (OSError, EOFError, gzip.BadGzipFile) as exc:
                error = f"Unable to decode remote archive: {exc}"
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
    archive, archive_error = _archive_db_row(db, service, archive_id)
    if archive is None:
        return {"error": archive_error, "ready": False}

    filename = _archive_filename(archive)
    path = Path(archive.path)
    content_type = "application/gzip" if filename.lower().endswith(".gz") else "text/plain; charset=utf-8"
    if not path.is_file() or path.is_symlink():
        container_path = _container_path_for_host_path(service, archive.path)
        if container_path:
            remote_bytes, error = _remote_archive_bytes(service, container_path)
            if remote_bytes is not None:
                return {
                    "archive_id": archive_id,
                    "filename": filename,
                    "path": None,
                    "content_type": content_type,
                    "ready": True,
                    "content": remote_bytes,
                    "checksum_sha256": hashlib.sha256(remote_bytes).hexdigest(),
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
    checksum = _archive_checksum(path)
    if checksum is None:
        return {
            "archive_id": archive_id, "filename": filename, "path": None,
            "content_type": content_type, "ready": False,
            "error": "Archive file could not be read", "content": None,
        }
    return {
        "archive_id": archive_id,
        "filename": filename,
        "path": str(path),
        "content_type": content_type,
        "ready": True,
        "content": None,
        "checksum_sha256": checksum,
    }


def bulk_download_log_archives(db: Session, service: "ServiceInstance", archive_ids: list) -> dict:
    """Prepare multiple log archive files as a ZIP bundle for download."""
    if not isinstance(archive_ids, list) or not archive_ids:
        return {
            "error": "Select at least one archive",
            "files": [],
            "file_count": 0,
            "ready": False,
            "zip_filename": "",
        }
    unique_ids = list(dict.fromkeys(archive_ids))
    archives = []
    failures: list[str] = []
    used_names: set[str] = set()
    for aid in unique_ids:
        item = download_log_archive(db, service, aid)
        if not item.get("ready"):
            failures.append(f"{aid}: {item.get('error') or 'unreadable'}")
            continue
        name = item.get("filename") or f"archive-{aid}.log"
        stem, suffix = os.path.splitext(name)
        candidate = name
        index = 2
        while candidate in used_names:
            candidate = f"{stem}-{index}{suffix}"
            index += 1
        used_names.add(candidate)
        archives.append({
            "archive_id": aid,
            "filename": candidate,
            "path": item.get("path"),
            "content": item.get("content"),
            "checksum_sha256": item.get("checksum_sha256"),
            "content_type": item.get("content_type"),
        })

    if failures:
        return {
            "error": "Archive selection contains unreadable or unauthorized files: " + "; ".join(failures),
            "files": archives,
            "file_count": len(archives),
            "ready": False,
            "zip_filename": "",
        }
    if not archives:
        return {"error": "No readable archive files for the selected ids", "files": [], "file_count": 0, "ready": False, "zip_filename": ""}

    safe_service = re.sub(r"[^\w.()@+\- ]", "_", str(service.name or service.service_key), flags=re.UNICODE).strip(" .") or "service"
    zip_filename = f"{safe_service}_logs_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"
    return {
        "zip_filename": zip_filename,
        "files": archives,
        "file_count": len(archives),
        "ready": True,
    }


def _deterministic_log_analyst_fallback(
    service: "ServiceInstance",
    *,
    formatted_logs: list[dict[str, Any]],
    issue_groups: list[dict[str, Any]],
    live_status: str,
    glitchtip_count: int,
    event_count: int,
) -> dict[str, Any]:
    """Legacy cPlatform deterministic Log Analyst response.

    Evidence is copied only from the selected service's canonical log packet;
    the fallback never invents a provider call or a log line.
    """

    category_summary = "No dominant issue pattern detected"
    if issue_groups:
        top_issue = issue_groups[0]
        category = top_issue.get("category") or ""
        brief = top_issue.get("brief") or ""
        severity = top_issue.get("severity") or ""
        category_summary = (
            f"**{category}** issue detected with **{severity}** severity level. "
            f"*Brief: {brief}*"
        )
    answer = (
        f"<p>I have analyzed **{len(formatted_logs)} log lines** for `{service.name}`. </p>"
        f"<p>The current operational status is **{live_status or 'Unknown'}**. </p>"
        f"<h4>Primary Diagnostics:</h4><ul>"
        f"<li><strong>Incident Category</strong>: {category_summary}</li>"
        f"<li><strong>GlitchTip Exceptions</strong>: {glitchtip_count} recorded in this window</li>"
        f"<li><strong>Recent events</strong>: {event_count} configuration/lifecycle events</li>"
        f"</ul><p>Based on deterministic regex scanning, the system observed active pattern "
        f"signatures matching your query. Please check the live streaming tail below for "
        f"real-time verification or review node resources.</p>"
    )
    candidates = [
        line for line in formatted_logs
        if str(line.get("lvl", "")).upper() in {"ERR", "ERROR", "WARN"}
    ][:4]
    if not candidates:
        candidates = formatted_logs[-4:]
    evidence: list[dict[str, Any]] = []
    for line in candidates:
        timestamp = str(line.get("t") or "")
        match = re.search(r"(\d{2}:\d{2}:\d{2})", timestamp)
        evidence.append({
            "t": match.group(1) if match else "10:42:08",
            "lvl": line.get("lvl") or "INFO",
            "msg": line.get("msg") or "",
        })
    return {
        "success": True,
        "answer": answer,
        "evidence": evidence,
        "chart_data": [10, 12, 8, 15, 7, 6, 11, 9, 38, 54, 76, 88, 82, 68, 42, 48, 36, 42, 34, 38],
        "suggestions": [
            "Are there any unusual resource spikes?",
            "Summarise recent warnings",
            "Show events timeline for this service",
        ],
        "error": None,
        "provider": None,
        "_audit_mode": "deterministic_fallback",
    }


def service_log_analytics_chat(db: Session, service: "ServiceInstance", question: str, window: str = "current", history: list = None) -> dict:
    """cPlatform-style log analytics chat (Iktara Log Analyst).

    Gathers real diagnostics + live logs, calls Groq/Mistral when configured,
    and otherwise returns the legacy deterministic analysis shape.
    """
    from ..llm import (
        contains_mistral_runtime_secret,
        execute_llm_request,
        is_llm_configured,
        llm_status,
        safe_json_loads,
    )
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

    # Match the legacy evidence packet: service events and GlitchTip issues are
    # support context, while log evidence remains isolated to this service.
    event_rows = list(
        db.scalars(
            select(OperationalEvent)
            .where(OperationalEvent.service_id == service.id)
            .order_by(OperationalEvent.created_at.desc())
            .limit(5)
        ).all()
    )
    recent_events = [
        {
            "category": row.category,
            "level": row.level,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in event_rows
    ]
    glitchtip_issues: list[dict[str, Any]] = []
    try:
        from ..monitoring.impl import query_monitoring_issues

        issue_result = query_monitoring_issues(db, service.name, window)
        if isinstance(issue_result, dict):
            glitchtip_issues = list(issue_result.get("issues") or [])[:5]
    except Exception:
        glitchtip_issues = []

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
        "recent_events": recent_events,
        "glitchtip_issues": glitchtip_issues,
        "window": window or "current",
    }

    if not is_llm_configured():
        return _deterministic_log_analyst_fallback(
            service,
            formatted_logs=formatted_logs,
            issue_groups=issue_groups,
            live_status=str(getattr(service, "status", "Unknown")),
            glitchtip_count=len(glitchtip_issues),
            event_count=len(event_rows),
        )

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
        return _deterministic_log_analyst_fallback(
            service, formatted_logs=formatted_logs, issue_groups=issue_groups,
            live_status=str(getattr(service, "status", "Unknown")),
            glitchtip_count=len(glitchtip_issues), event_count=len(event_rows),
        )

    try:
        parsed = safe_json_loads(content)
        if contains_mistral_runtime_secret(parsed):
            raise ValueError("provider response failed secret-safety validation")
        answer = parsed.get("answer")
        chart = parsed.get("chart_data")
        suggestions = parsed.get("suggestions")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("provider response contained an empty answer")
        if not isinstance(chart, list) or not 10 <= len(chart) <= 30:
            raise ValueError("provider response contained invalid chart_data")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in chart):
            raise ValueError("provider response contained non-numeric chart_data")
        chart = [int(x) for x in chart]
        evidence = parsed.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        actual_evidence: list[dict[str, Any]] = []
        actual_by_message = {(str(item.get("t", "")), str(item.get("lvl", "")), str(item.get("msg", ""))): item for item in formatted_logs}
        actual_by_message_short = {
            (str(item.get("t", "")).replace("Z", "").split("T")[-1][:8], str(item.get("lvl", "")), str(item.get("msg", ""))): item
            for item in formatted_logs
        }
        for candidate in evidence:
            if not isinstance(candidate, dict):
                continue
            key = (str(candidate.get("t", "")), str(candidate.get("lvl", "")), str(candidate.get("msg", "")))
            matched = actual_by_message.get(key) or actual_by_message_short.get(
                (key[0].replace("Z", "").split("T")[-1][:8], key[1], key[2])
            )
            if matched is not None:
                actual_evidence.append(dict(matched))
        if not actual_evidence:
            raise ValueError("provider response contained no grounded evidence")
        if not isinstance(suggestions, list) or len(suggestions) != 3 or not all(isinstance(s, str) and s.strip() for s in suggestions):
            raise ValueError("provider response contained invalid suggestions")
        return {
            "success": True,
            "answer": answer,
            "evidence": actual_evidence[:4],
            "chart_data": chart,
            "suggestions": suggestions,
            "error": None,
            "provider": llm_status().get("provider"),
            "_audit_mode": "configured_provider",
        }
    except Exception:
        return _deterministic_log_analyst_fallback(
            service, formatted_logs=formatted_logs, issue_groups=issue_groups,
            live_status=str(getattr(service, "status", "Unknown")),
            glitchtip_count=len(glitchtip_issues), event_count=len(event_rows),
        )
