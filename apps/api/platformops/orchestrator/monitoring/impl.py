from __future__ import annotations

import json
import math
import re
import subprocess
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import (
    BackupRun,
    Cluster,
    ConfigSnapshot,
    DeploymentJob,
    DriftReport,
    IncidentRecord,
    JobStatus,
    MonitoringCheck,
    Node,
    OperationalEvent,
    ReleaseRecord,
    RunbookExecution,
    ServiceInstance,
    SloReport,
)
from ...settings import settings
from ...security import redact_text
from ...jobs import create_job
from ...tasks import run_job_async
from ...query import escape_query_regex_literal
from ..common import (
    RUNNING_STATUSES,
    _ansible_base_command,
    record_event,
)


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

    if settings.local_mode:
        backup.status = JobStatus.failed.value
        backup.completed_at = datetime.utcnow()
        backup.output = (
            "Backup requires a real node target. "
            "Set PLATFORMOPS_LOCAL_MODE=false and configure SSH/Ansible for the service node."
        )
        db.commit()
        db.refresh(backup)
        return backup

    # Real path: queue Ansible backup playbook (no synthetic success)
    try:
        command = (
            f"{_ansible_base_command(service.node, 'service_backup.yml')} "
            f"--extra-vars container_name={service.container_name} "
            f"--extra-vars artifact_path={backup.artifact_path}"
        )
        job = create_job(db, action="backup", command=command, service_id=service.id, node_id=service.node_id)

        def on_complete(bg_db, bg_job, ok: bool):
            bg_backup = bg_db.get(BackupRun, backup.id)
            if not bg_backup:
                return
            bg_backup.status = JobStatus.success.value if ok else JobStatus.failed.value
            bg_backup.completed_at = datetime.utcnow()
            bg_backup.output = (bg_job.output or bg_job.error or "")[:4000]
            bg_db.commit()

        run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)
        backup.output = f"Backup job {job.id} queued"
        db.commit()
        db.refresh(backup)
        return backup
    except Exception as exc:
        backup.status = JobStatus.failed.value
        backup.completed_at = datetime.utcnow()
        backup.output = f"Backup failed: {exc}"
        db.commit()
        db.refresh(backup)
        return backup


def run_monitoring_sweep(db: Session) -> list[MonitoringCheck]:
    checks: list[MonitoringCheck] = []
    services = list(db.scalars(select(ServiceInstance).order_by(ServiceInstance.name)).all())
    for service in services:
        # Never use ServiceInstance.status as probe evidence.  It is a
        # persisted cache and can be stale exactly when an operator needs this
        # sweep to detect degradation.
        probe = _direct_service_probe(db, service)
        status = str(probe.get("status") or "error")
        value = str(probe.get("value") or "unavailable")
        detail = json.dumps(probe, separators=(",", ":"))

        check = MonitoringCheck(
            service_id=service.id,
            node_id=service.node_id,
            name=f"{service.service_key}-health",
            status=status,
            value=value,
            detail=detail,
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


def _probe_timestamp() -> str:
    """Return a timezone-neutral timestamp for direct probe evidence."""

    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _remote_container_exec(node: Node, container_name: str, args: list[str]) -> tuple[bool, str, str]:
    """Execute a command on the selected remote Docker engine.

    This deliberately has no local-Docker fallback.  A response from the
    control-plane engine cannot be evidence for an SSH-selected target.
    """

    if not str(getattr(node, "host", "") or "").strip():
        return False, "", "remote node host is missing"
    # Keep all SSH construction in the target-bound adapter.  It validates a
    # pinned host fingerprint, resolves only approved secret references, and
    # deliberately has no local-Docker fallback.
    from ..remote import RemoteAuthError, run_ssh

    command = ["docker", "exec", container_name, *args]
    try:
        proc = run_ssh(node, command, timeout=8)
    except FileNotFoundError:
        return False, "", "ssh client is not available"
    except RemoteAuthError as exc:
        return False, "", str(exc)[:400]
    except Exception as exc:
        return False, "", str(exc)[:400]
    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip() or output
    return proc.returncode == 0, output, error[:400]


def _direct_service_probe(db: Session, service: ServiceInstance) -> dict[str, Any]:
    """Probe a service target and return evidence, never persisted status.

    Container inspection is used for all services; Redis additionally requires
    a target-bound ``redis-cli PING``.  The caller persists a check only after
    this function has returned.
    """

    checked_at = _probe_timestamp()
    try:
        from ..service.impl import get_service_live_status, _node_uses_local_docker

        live = get_service_live_status(db, service, use_cache=False)
    except Exception as exc:
        return {
            "status": "error",
            "value": "probe_error",
            "source": "docker_inspect",
            "checked_at": checked_at,
            "error": str(exc)[:400],
        }

    source = str(live.get("source") or "docker_inspect")
    if not live.get("running"):
        state = str(live.get("state") or live.get("overall_status") or "unknown")
        return {
            "status": "degraded" if state not in {"error", "not_found"} else "error",
            "value": state,
            "source": source,
            "checked_at": checked_at,
            "error": live.get("error") or "container is not running",
            "container_state": state,
        }

    if str(service.service_key or "").lower() in {"redis", "redis-core", "airflow-redis"}:
        node = service.node or (db.get(Node, service.node_id) if service.node_id else None)
        try:
            if node is not None and not _node_uses_local_docker(node):
                ok, output, error = _remote_container_exec(node, service.container_name, ["redis-cli", "--raw", "PING"])
                ping_source = "redis_ping_ssh"
            else:
                from ..docker_runtime import exec_container

                ok, output, error = exec_container(service.container_name, ["redis-cli", "--raw", "PING"])
                ping_source = "redis_ping"
        except Exception as exc:
            ok, output, error = False, "", str(exc)
            ping_source = "redis_ping"
        if ok and output.strip().upper() == "PONG":
            return {
                "status": "ok",
                "value": "PONG",
                "source": ping_source,
                "checked_at": checked_at,
                "error": None,
                "container_state": "running",
            }
        return {
            "status": "error",
            "value": "ping_failed",
            "source": ping_source,
            "checked_at": checked_at,
            "error": (error or output or "Redis did not return PONG")[:400],
            "container_state": "running",
        }

    return {
        "status": "ok",
        "value": str(live.get("state") or "running"),
        "source": source,
        "checked_at": checked_at,
        "error": None,
        "container_state": str(live.get("state") or "running"),
    }


METRIC_WINDOW_PRESETS: dict[str, dict[str, int]] = {
    # cPlatform's MachineStats cadence.  Keep the step explicit instead of
    # deriving it from an arbitrary point count: consumers compare PromQL
    # range timestamps and labels directly.
    "15m": {"points": 15, "step_minutes": 1, "range_seconds": 15 * 60},
    "1h": {"points": 60, "step_minutes": 1, "range_seconds": 3600},
    "6h": {"points": 72, "step_minutes": 5, "range_seconds": 6 * 3600},
    "24h": {"points": 96, "step_minutes": 15, "range_seconds": 24 * 3600},
    "7d": {"points": 84, "step_minutes": 120, "range_seconds": 7 * 86400},
    "1m": {"points": 90, "step_minutes": 480, "range_seconds": 30 * 86400},
    "3m": {"points": 90, "step_minutes": 1440, "range_seconds": 90 * 86400},
}


def _normalize_metric_window(window: str | None) -> str:
    raw = str(window or "1h").strip()
    # Accept cPlatform's case-sensitive labels and lower-case API aliases.
    aliases = {"1M": "1m", "3M": "3m", "30d": "1m", "90d": "3m"}
    candidate = aliases.get(raw, aliases.get(raw.lower(), raw.lower()))
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


def _prometheus_base() -> str:
    return (settings.prometheus_base_url or "http://localhost:9022").rstrip("/")


def _prom_query(query: str, timeout: float = 5.0) -> tuple[bool, Any]:
    """Instant query. Returns (ok, value_or_error)."""
    import requests

    try:
        resp = requests.get(
            f"{_prometheus_base()}/api/v1/query",
            params={"query": query},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return False, f"Prometheus HTTP {resp.status_code}"
        payload = resp.json()
        if payload.get("status") != "success":
            return False, payload.get("error") or "Prometheus query failed"
        result = payload.get("data", {}).get("result") or []
        if not result:
            return True, None
        return True, float(result[0].get("value", [0, 0])[1])
    except Exception as exc:
        return False, str(exc)


def _prom_query_range(query: str, window: str, timeout: float = 8.0) -> tuple[bool, list[dict[str, Any]] | str]:
    """Range query mapped into label/value series points."""
    import time

    import requests

    preset = METRIC_WINDOW_PRESETS[_normalize_metric_window(window)]
    end = int(time.time())
    start = end - int(preset["range_seconds"])
    step = max(1, int(preset["step_minutes"] * 60))
    try:
        resp = requests.get(
            f"{_prometheus_base()}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return False, f"Prometheus HTTP {resp.status_code}"
        payload = resp.json()
        if payload.get("status") != "success":
            return False, payload.get("error") or "Prometheus range query failed"
        result = payload.get("data", {}).get("result") or []
        if not result:
            return True, []
        values = result[0].get("values") or []
        series: list[dict[str, Any]] = []
        for ts, val in values:
            age = end - int(float(ts))
            if age >= 86400:
                label = f"T-{age // 86400}d"
            elif age >= 3600:
                label = f"T-{age // 3600}h"
            else:
                label = f"T-{max(0, age // 60)}m"
            series.append({"label": label, "value": round(float(val), 2)})
        return True, series
    except Exception as exc:
        return False, str(exc)


def _prom_observe(query: str, *, range_window: str | None = None, timeout: float = 8.0) -> dict[str, Any]:
    """Query Prometheus while retaining availability and sample evidence.

    ``_prom_query`` intentionally remains the small legacy scalar helper used
    by reports.  Page parity needs to distinguish an HTTP failure, an empty
    vector, a stale sample, and a genuine numeric zero, so page handlers use
    this richer observation envelope.
    """

    import requests

    observed_at = _probe_timestamp()
    endpoint = "/api/v1/query_range" if range_window else "/api/v1/query"
    params: dict[str, Any] = {"query": query}
    end = int(time.time())
    if range_window:
        preset = METRIC_WINDOW_PRESETS[_normalize_metric_window(range_window)]
        start = end - int(preset["range_seconds"])
        params.update({"start": start, "end": end, "step": max(1, int(preset["step_minutes"] * 60))})
    try:
        response = requests.get(f"{_prometheus_base()}{endpoint}", params=params, timeout=timeout)
    except Exception as exc:
        return {
            "state": "error",
            "reachable": False,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "error": str(exc)[:400],
        }
    if response.status_code != 200:
        return {
            "state": "error",
            "reachable": False,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "error": f"Prometheus HTTP {response.status_code}",
        }
    try:
        payload = response.json()
    except Exception as exc:
        return {
            "state": "error",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "error": f"invalid Prometheus response: {exc}",
        }
    if payload.get("status") != "success":
        return {
            "state": "error",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "error": str(payload.get("error") or "Prometheus query failed")[:400],
        }
    results = payload.get("data", {}).get("result") or []
    if not results:
        return {
            "state": "missing",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "error": "metric series not found",
        }
    result = results[0] if isinstance(results[0], dict) else {}
    if range_window:
        raw_values = result.get("values") or []
        if not isinstance(raw_values, (list, tuple)):
            raw_values = []
            malformed_samples = 1
        else:
            malformed_samples = 0
        series: list[dict[str, Any]] = []
        latest_sample_at: str | None = None
        latest_timestamp: float | None = None
        for item in raw_values:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                malformed_samples += 1
                continue
            try:
                ts = float(item[0])
                value = float(item[1])
                label = datetime.utcfromtimestamp(ts).isoformat(timespec="seconds") + "Z"
            except (OverflowError, TypeError, ValueError):
                malformed_samples += 1
                continue
            if not (math.isfinite(ts) and math.isfinite(value)):
                malformed_samples += 1
                continue
            if latest_timestamp is None or ts >= latest_timestamp:
                latest_timestamp = ts
                latest_sample_at = label
            series.append({"timestamp": ts, "label": label, "value": value})
        if not series:
            return {
                "state": "error" if malformed_samples else "missing",
                "reachable": True,
                "value": None,
                "series": [],
                "source": "prometheus",
                "observed_at": observed_at,
                "latest_sample_at": None,
                "malformed_samples": malformed_samples,
                "error": "all Prometheus samples were malformed" if malformed_samples else "metric series has no samples",
            }
        stale = bool(latest_timestamp is not None and time.time() - latest_timestamp > max(300, METRIC_WINDOW_PRESETS[_normalize_metric_window(range_window)]["step_minutes"] * 60 * 3))
        sample_error = "one or more Prometheus samples were malformed" if malformed_samples else None
        if stale:
            sample_error = f"{sample_error}; latest Prometheus sample is stale" if sample_error else "latest Prometheus sample is stale"
        return {
            "state": "stale" if stale else "available",
            "reachable": True,
            "value": series[-1]["value"],
            "series": series,
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": latest_sample_at,
            "malformed_samples": malformed_samples,
            "error": sample_error,
        }
    raw_value = result.get("value") or []
    if not isinstance(raw_value, (list, tuple)) or len(raw_value) < 2:
        return {
            "state": "error",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "malformed_samples": 1,
            "error": "malformed Prometheus sample",
        }
    try:
        timestamp = float(raw_value[0])
        value = float(raw_value[1])
        label = datetime.utcfromtimestamp(timestamp).isoformat(timespec="seconds") + "Z"
    except (OverflowError, TypeError, ValueError) as exc:
        return {
            "state": "error",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "malformed_samples": 1,
            "error": f"invalid Prometheus sample: {exc}",
        }
    if not (math.isfinite(timestamp) and math.isfinite(value)):
        return {
            "state": "error",
            "reachable": True,
            "value": None,
            "series": [],
            "source": "prometheus",
            "observed_at": observed_at,
            "latest_sample_at": None,
            "malformed_samples": 1,
            "error": "invalid Prometheus sample: non-finite value",
        }
    stale = time.time() - timestamp > 300
    return {
        "state": "stale" if stale else "available",
        "reachable": True,
        "value": value,
        "series": [{"timestamp": timestamp, "label": label, "value": value}],
        "source": "prometheus",
        "observed_at": observed_at,
        "latest_sample_at": label,
        "malformed_samples": 0,
        "error": "latest Prometheus sample is stale" if stale else None,
    }


def _metric_state(observations: list[dict[str, Any]]) -> tuple[str, str | None]:
    available = sum(item.get("state") == "available" for item in observations)
    errors = [str(item.get("error")) for item in observations if item.get("state") in {"error", "stale"} and item.get("error")]
    if available == len(observations) and available:
        warnings = [str(item.get("error")) for item in observations if item.get("error")]
        return "available", warnings[0] if warnings else None
    if available:
        return "degraded", errors[0] if errors else "one or more metric series are unavailable"
    if errors:
        if any(item.get("state") == "stale" for item in observations) and not any(item.get("state") == "error" for item in observations):
            return "stale", errors[0]
        return "error", errors[0]
    return "unavailable", "metric series not found"


def _fetch_mounted_volumes(node: Node) -> list[dict[str, Any]]:
    """Collect mounted volumes via Ansible/shell df -h (or local df)."""
    import re
    import subprocess

    def _parse_df(output: str) -> list[dict[str, Any]]:
        volumes: list[dict[str, Any]] = []
        for line in output.splitlines():
            if not line or line.lower().startswith("filesystem"):
                continue
            # Prefer df -P style: Filesystem 1024-blocks Used Available Capacity Mounted on
            parts = line.split()
            if len(parts) < 6:
                continue
            mount = parts[-1]
            usage_token = parts[-2].rstrip("%")
            try:
                # human sizes like 100G / 42G
                def _to_gb(token: str) -> float:
                    token = token.strip()
                    m = re.match(r"^([\d.]+)([KMGTP]i?B?)?$", token, re.I)
                    if not m:
                        # already 1K-blocks?
                        return round(float(token) / (1024 * 1024), 1) if token.isdigit() else 0.0
                    num = float(m.group(1))
                    unit = (m.group(2) or "").upper()
                    mult = 1.0
                    if unit.startswith("K"):
                        mult = 1 / 1024
                    elif unit.startswith("M"):
                        mult = 1 / 1024
                    elif unit.startswith("G"):
                        mult = 1.0
                    elif unit.startswith("T"):
                        mult = 1024.0
                    elif unit.startswith("P"):
                        mult = 1024 * 1024
                    return round(num * mult, 1)

                total_gb = _to_gb(parts[1])
                used_gb = _to_gb(parts[2])
                usage_pct = float(usage_token) if usage_token.replace(".", "", 1).isdigit() else 0.0
            except Exception:
                continue
            if not mount.startswith("/"):
                continue
            volumes.append(
                {
                    "mount": mount,
                    "fstype": "local",
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "usage_pct": usage_pct,
                }
            )
        return volumes

    # Local node or local_mode: run df on controller
    if settings.local_mode or getattr(node, "environment", "") == "local":
        try:
            proc = subprocess.run(["df", "-hP"], capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                parsed = _parse_df(proc.stdout)
                if parsed:
                    return parsed
        except Exception:
            pass
    else:
        try:
            from ..remote import RemoteAuthError, run_ssh

            proc = run_ssh(node, ["df", "-hP"], timeout=12)
            if proc.returncode == 0:
                parsed = _parse_df(proc.stdout or "")
                if parsed:
                    return parsed
        except (RemoteAuthError, FileNotFoundError, OSError):
            pass
        except Exception:
            pass

    return []


def _promql_label_value(value: Any) -> str:
    """Escape a user/inventory value before putting it in a PromQL matcher."""

    return str(value or "").replace("\\", "\\\\").replace('"', '\\"').strip()


def _prometheus_instance_match(node: Any) -> str:
    """Return a target-bound instance matcher, never a global fallback.

    Prometheus exporters commonly expose ``host:port`` while inventory may
    contain a DNS name, IP, or an explicit exporter instance in facts.  The
    regex deliberately accepts those representations but returns a matching
    nothing selector when no identity is available, preventing a different
    node's samples from being presented as the selected target.
    """

    facts: dict[str, Any] = {}
    try:
        raw = getattr(node, "facts_json", "") or "{}"
        facts = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
    except (TypeError, ValueError):
        facts = {}
    values = [
        facts.get("prometheus_instance"),
        facts.get("node_exporter_instance"),
        getattr(node, "host", ""),
        getattr(node, "name", ""),
    ]
    values = [_promql_label_value(value) for value in values if str(value or "").strip()]
    if not values:
        return 'instance=~"^$"'
    return 'instance=~".*(' + "|".join(re.escape(value) for value in values) + ').*"'


def get_node_metrics(db: Session, node_id: int, window: str = "1h") -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    metric_window = _normalize_metric_window(window)
    mounted_volumes = _fetch_mounted_volumes(node)

    instance_match = _prometheus_instance_match(node)

    cpu_q = f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",{instance_match}}}[5m])) * 100)'
    mem_q = f'(1 - node_memory_MemAvailable_bytes{{{instance_match}}} / node_memory_MemTotal_bytes{{{instance_match}}}) * 100'
    disk_q = f'(1 - node_filesystem_avail_bytes{{mountpoint="/",{instance_match}}} / node_filesystem_size_bytes{{mountpoint="/",{instance_match}}}) * 100'
    rx_q = f"sum(rate(node_network_receive_bytes_total{{{instance_match}}}[5m])) * 8 / 1e6"
    tx_q = f"sum(rate(node_network_transmit_bytes_total{{{instance_match}}}[5m])) * 8 / 1e6"
    instant = {
        "cpu_percent": _prom_observe(cpu_q),
        "memory_percent": _prom_observe(mem_q),
        "disk_percent": _prom_observe(disk_q),
        "network_rx_mbps": _prom_observe(rx_q),
        "network_tx_mbps": _prom_observe(tx_q),
    }
    ranges = {
        "cpu_series": _prom_observe(cpu_q, range_window=metric_window),
        "memory_series": _prom_observe(mem_q, range_window=metric_window),
        "disk_series": _prom_observe(disk_q, range_window=metric_window),
    }
    observations = list(instant.values()) + list(ranges.values())
    availability, first_error = _metric_state(observations)
    latest_samples = [item.get("latest_sample_at") for item in observations if item.get("latest_sample_at")]

    def _value(name: str) -> float | None:
        item = instant[name]
        return item.get("value") if item.get("state") == "available" else None

    return {
        "node_id": node.id,
        "node_name": node.name,
        "window": metric_window,
        "cpu_percent": _value("cpu_percent"),
        "memory_percent": _value("memory_percent"),
        "disk_percent": _value("disk_percent"),
        "network_rx_mbps": _value("network_rx_mbps"),
        "network_tx_mbps": _value("network_tx_mbps"),
        "cpu_series": ranges["cpu_series"].get("series", []),
        "memory_series": ranges["memory_series"].get("series", []),
        "disk_series": ranges["disk_series"].get("series", []),
        "mounted_volumes": mounted_volumes,
        "prometheus_reachable": any(item.get("reachable") for item in observations),
        "availability": availability,
        "source": "prometheus",
        "checked_at": _probe_timestamp(),
        "latest_sample_at": max(latest_samples) if latest_samples else None,
        "units": {"cpu_percent": "%", "memory_percent": "%", "disk_percent": "%", "network_rx_mbps": "Mbps", "network_tx_mbps": "Mbps"},
        "error": first_error,
    }


def get_service_metrics(db: Session, service_id: int, window: str = "1h") -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    metric_window = _normalize_metric_window(window)
    service_key = service.service_key
    container = service.container_name or service_key
    node = getattr(service, "node", None)
    if node is None and getattr(service, "node_id", None):
        node = db.get(Node, service.node_id)
    instance_match = _prometheus_instance_match(node)
    escaped_container = _promql_label_value(container)
    # cAdvisor metrics are scoped to the selected container.  Do not fall
    # back to a service-key regex: another instance could otherwise leak into
    # this target's page.
    cpu_q = f'sum(rate(container_cpu_usage_seconds_total{{name="{escaped_container}",{instance_match}}}[5m])) * 100'
    mem_q = f'sum(container_memory_usage_bytes{{name="{escaped_container}",{instance_match}}}) / 1024 / 1024'
    instant = {"cpu_percent": _prom_observe(cpu_q), "memory_mb": _prom_observe(mem_q)}
    ranges = {"cpu_series": _prom_observe(cpu_q, range_window=metric_window)}
    observations = list(instant.values()) + list(ranges.values())
    availability, first_error = _metric_state(observations)
    result: dict[str, Any] = {
        "service_id": service.id,
        "service_name": service.name,
        "service_key": service_key,
        "node_id": service.node_id,
        "window": metric_window,
        "cpu_percent": instant["cpu_percent"].get("value") if instant["cpu_percent"].get("state") == "available" else None,
        "memory_mb": instant["memory_mb"].get("value") if instant["memory_mb"].get("state") == "available" else None,
        # Application error, latency and queue telemetry are not derivable
        # from CPU/container counters.  They remain explicitly unavailable.
        "log_error_rate": None,
        "queue_depth": None,
        "restart_count": None,
        "latency_ms_p95": None,
        "cpu_series": ranges["cpu_series"].get("series", []),
        "error_rate_series": [],
        "queue_depth_series": [],
        "db_metrics": None,
        "broker_metrics": None,
        "custom_charts": [],
        "unavailable_fields": ["log_error_rate", "queue_depth", "restart_count", "latency_ms_p95"],
        "prometheus_reachable": any(item.get("reachable") for item in observations),
        "availability": availability,
        "source": "prometheus",
        "checked_at": _probe_timestamp(),
        # This is refreshed after exporter/database/custom observations are
        # collected below.  cAdvisor may be absent while Redis or another
        # collector still provides measured samples.
        "latest_sample_at": None,
        "units": {"cpu_percent": "%", "memory_mb": "MiB"},
        "error": first_error,
    }

    def _prom_values(definitions: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        values: dict[str, Any] = {}
        local_obs: list[dict[str, Any]] = []
        for key, query in definitions.items():
            item = _prom_observe(query)
            local_obs.append(item)
            values[key] = item.get("value") if item.get("state") == "available" else None
        return values, local_obs

    if service_key in ("postgres-core", "postgres", "clickhouse-core"):
        values, db_obs = _prom_values({
            "active_connections": f'pg_stat_activity_count{{state="active",{instance_match}}}',
            "idle_connections": f'pg_stat_activity_count{{state="idle",{instance_match}}}',
            "read_ops": f"rate(pg_stat_database_tup_fetched{{{instance_match}}}[5m])",
            "write_ops": f"rate(pg_stat_database_tup_inserted{{{instance_match}}}[5m]) + rate(pg_stat_database_tup_updated{{{instance_match}}}[5m])",
            "cache_hit_ratio": f"sum(pg_stat_database_blks_hit{{{instance_match}}}) / clamp_min(sum(pg_stat_database_blks_hit{{{instance_match}}} + pg_stat_database_blks_read{{{instance_match}}}), 1) * 100",
            "transaction_locks": f"sum(pg_locks_count{{{instance_match}}})",
        })
        result["db_metrics"] = values
        observations.extend(db_obs)
    elif service_key in ("redis-core", "redis", "airflow-redis"):
        values, db_obs = _prom_values({
            "active_connections": f"redis_connected_clients{{{instance_match}}}",
            "read_ops": f"rate(redis_commands_processed_total{{{instance_match}}}[5m])",
            "cache_hit_ratio": f"redis_keyspace_hits_total{{{instance_match}}} / clamp_min(redis_keyspace_hits_total{{{instance_match}}} + redis_keyspace_misses_total{{{instance_match}}}, 1) * 100",
        })
        result["db_metrics"] = {**values, "idle_connections": None, "write_ops": None, "transaction_locks": None}
        observations.extend(db_obs)
        cmd_series = _prom_observe(f"rate(redis_commands_processed_total{{{instance_match}}}[5m])", range_window=metric_window)
        result["commands_series"] = cmd_series.get("series", [])
        observations.append(cmd_series)
    elif service_key in ("rabbitmq-core", "rabbitmq"):
        values, broker_obs = _prom_values({
            "ingestion_rate": f"rate(rabbitmq_global_messages_received_total{{{instance_match}}}[5m])",
            "delivery_rate": f"rate(rabbitmq_global_messages_delivered_total{{{instance_match}}}[5m])",
            "queued_ready": f"sum(rabbitmq_queue_messages_ready{{{instance_match}}})",
            "queued_unacked": f"sum(rabbitmq_queue_messages_unacked{{{instance_match}}})",
            "consumer_count": f"sum(rabbitmq_queue_consumers{{{instance_match}}})",
        })
        result["broker_metrics"] = values
        result["queue_depth"] = values.get("queued_ready")
        result["unavailable_fields"] = ["log_error_rate", "restart_count", "latency_ms_p95"]
        result["units"]["queue_depth"] = "items"
        queue_series = _prom_observe(f"sum(rabbitmq_queue_messages_ready{{{instance_match}}})", range_window=metric_window)
        result["queue_depth_series"] = queue_series.get("series", [])
        observations.extend(broker_obs + [queue_series])

    try:
        contract = json.loads(service.config_json or "{}")
    except (TypeError, ValueError):
        contract = {}
    custom_defs = contract.get("custom_metrics") or contract.get("performance_charts") or []
    for item in custom_defs if isinstance(custom_defs, list) else []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or "Custom metric"
        unit = item.get("unit") or ""
        queries = item.get("series") or item.get("queries") or []
        if isinstance(queries, dict):
            queries = [{"name": key, "query": value} for key, value in queries.items()]
        series_out = []
        for series_def in queries if isinstance(queries, list) else []:
            if not isinstance(series_def, dict):
                continue
            query = series_def.get("query") or series_def.get("promql") or ""
            if not query:
                continue
            observed = _prom_observe(query, range_window=metric_window)
            observations.append(observed)
            series_out.append({"name": series_def.get("name") or series_def.get("label") or "series", "points": observed.get("series", [])})
        if series_out:
            result["custom_charts"].append({"title": title, "unit": unit, "series": series_out})

    result["availability"], result["error"] = _metric_state(observations)
    measured = [item for item in observations if item.get("latest_sample_at")]
    result["latest_sample_at"] = max((item["latest_sample_at"] for item in measured), default=None)
    measured_sources = sorted({str(item.get("source")) for item in measured if item.get("source")})
    if measured_sources:
        result["source"] = ",".join(measured_sources)
    return result


def get_service_summary(db: Session, service_id: int) -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    contract = json.loads(service.config_json or "{}")
    from ..reports import get_service_capabilities
    from ..service import dependency_preflight

    dependency = dependency_preflight(db, service)
    capabilities = get_service_capabilities(db, service.id)

    latest_job = db.scalar(
        select(DeploymentJob).where(DeploymentJob.service_id == service.id).order_by(DeploymentJob.created_at.desc())
    )
    latest_backup = db.scalar(
        select(BackupRun).where(BackupRun.service_id == service.id).order_by(BackupRun.created_at.desc())
    )
    latest_release = db.scalar(
        select(ReleaseRecord).where(ReleaseRecord.service_id == service.id).order_by(ReleaseRecord.created_at.desc())
    )
    latest_drift = db.scalar(
        select(DriftReport).where(DriftReport.service_id == service.id).order_by(DriftReport.created_at.desc())
    )
    latest_monitoring = db.scalar(
        select(MonitoringCheck)
        .where(MonitoringCheck.service_id == service.id)
        .order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(
        select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc())
    )
    latest_runbook = db.scalar(
        select(RunbookExecution)
        .where(RunbookExecution.service_id == service.id)
        .order_by(RunbookExecution.created_at.desc())
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
    snapshot_count = (
        db.scalar(select(func.count()).select_from(ConfigSnapshot).where(ConfigSnapshot.service_id == service.id)) or 0
    )
    recent_event_count = (
        db.scalar(select(func.count()).select_from(OperationalEvent).where(OperationalEvent.service_id == service.id))
        or 0
    )
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


def get_dashboard_summary(db: Session) -> dict[str, Any]:
    from ..service import dependency_preflight

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
    from ..reports import observability_pipeline_report

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
        1
        for service in services
        if service.status not in RUNNING_STATUSES or not dependency_preflight(db, service)["ok"]
    )

    gpu_node_count = db.query(Node).filter(Node.facts_json.like('%"gpu_available": true%')).count()
    node_online_count = sum(
        1
        for node in nodes
        if (node.status or "").lower() in RUNNING_STATUSES or (node.status or "").lower() in {"online", "ready", "healthy"}
    )

    return {
        "clusters": len(clusters),
        "nodes": len(nodes),
        "node_online_count": node_online_count,
        "services": len(services),
        "running_services": running_services,
        "open_incidents": len(open_incidents),
        "burning_slos": burning_slos,
        "healthy_observability_nodes": healthy_observability_nodes,
        "degraded_observability_nodes": degraded_observability_nodes,
        "blocked_services": blocked_services,
        "gpu_node_count": gpu_node_count,
        "attention_services": attention_services,
        "active_incidents": open_incidents,
        "degraded_observability": degraded_observability[:6],
    }


def _glitchtip_config() -> tuple[str, str, str, bool]:
    base_url = str(settings.glitchtip_base_url or "").rstrip("/")
    org = str(settings.glitchtip_org_slug or "").strip()
    token = str(settings.glitchtip_token or "").strip()
    return base_url, org, token, bool(base_url and org and token)


def _glitchtip_error(exc: BaseException, token: str = "") -> str:
    """Bound and redact adapter errors before exposing them to API clients."""

    return redact_text(str(exc), secrets=(token,) if token else ())[:400]


def _resolve_glitchtip_project_id(
    base_url: str, org: str, token: str, project_slug: str, *, timeout: float = 8.0
) -> tuple[int | None, str | None]:
    """Resolve a configured project slug to GlitchTip's numeric project ID.

    GlitchTip's project-key APIs use ``organization/project-slug`` while
    uptime monitor creation and event-envelope ingestion require ``project``
    to be the numeric ID.  Keep that compatibility detail in one adapter and
    return only bounded, redacted errors to callers.
    """

    import requests

    slug = str(project_slug or "").strip()
    if not slug:
        return None, "GlitchTip project slug is empty"
    if slug.isdigit() and int(slug) > 0:
        return int(slug), None
    try:
        response = requests.get(
            f"{base_url}/api/0/projects/{quote(org, safe='')}/{quote(slug, safe='')}/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
    except Exception as exc:
        return None, _glitchtip_error(exc, token)
    if response.status_code != 200:
        return None, f"GlitchTip project lookup HTTP {response.status_code}"
    try:
        payload = response.json() or {}
    except Exception as exc:
        return None, f"GlitchTip project lookup returned invalid JSON: {exc}"[:400]
    if not isinstance(payload, dict):
        return None, "GlitchTip project lookup returned a malformed payload"
    raw_id = payload.get("id")
    try:
        project_id = int(raw_id)
    except (TypeError, ValueError):
        project_id = 0
    if project_id <= 0:
        return None, "GlitchTip project lookup did not return a numeric project ID"
    return project_id, None


def _transaction_groups_from_payload(payload: Any) -> list[dict[str, Any]] | None:
    """Normalize current and legacy transaction-group response envelopes."""

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates: Any = None
        for key in ("items", "results", "transactions", "transaction_groups", "transactionGroups", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if key == "data" and isinstance(value, dict):
                candidates = _transaction_groups_from_payload(value)
                if candidates is not None:
                    break
        if candidates is None:
            return None
    else:
        return None
    return [item for item in candidates if isinstance(item, dict)]


def _filter_transaction_groups(
    transactions: list[dict[str, Any]], project_id: int
) -> list[dict[str, Any]]:
    """Retain groups for the resolved project without depending on slug fields."""

    filtered: list[dict[str, Any]] = []
    for item in transactions:
        raw_project = item.get("project_id", item.get("projectId", item.get("project")))
        if isinstance(raw_project, dict):
            raw_project = raw_project.get("id")
        if raw_project in (None, ""):
            # The request is project-scoped; older GlitchTip responses omit the
            # project field, so retain those records rather than discarding
            # valid groups solely because the serializer differs.
            filtered.append(item)
            continue
        try:
            if int(raw_project) == project_id:
                filtered.append(item)
        except (TypeError, ValueError):
            continue
    return filtered


def _fetch_monitoring_transaction_groups(
    *,
    base_url: str,
    org: str,
    token: str,
    project_id: int,
    node_ip: str = "",
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Fetch transaction groups using numeric project filtering.

    GlitchTip 6.x returns a cursor-paginated object for this endpoint, while
    older deployments returned a bare list.  Both are normalized here.  The
    optional environment filter is retained for cPlatform compatibility and
    retried without it when a valid response is empty.
    """

    import re
    import requests

    endpoint = f"{base_url}/api/0/organizations/{quote(org, safe='')}/transaction-groups/"
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, str] = {"project": str(project_id)}
    if node_ip and node_ip != "0.0.0.0":
        params["environment"] = node_ip

    def request(current_params: dict[str, str]) -> tuple[list[dict[str, Any]] | None, str | None, Any]:
        try:
            response = requests.get(endpoint, headers=headers, params=current_params, timeout=timeout)
        except Exception as exc:
            return None, _glitchtip_error(exc, token), None
        if response.status_code != 200:
            return None, f"GlitchTip transaction-groups HTTP {response.status_code}", response
        try:
            payload = response.json() or []
        except Exception as exc:
            return None, f"GlitchTip returned invalid transaction-groups JSON: {_glitchtip_error(exc, token)}"[:400], response
        normalized = _transaction_groups_from_payload(payload)
        if normalized is None:
            return None, "GlitchTip returned a malformed transaction-groups payload", response
        return _filter_transaction_groups(normalized, project_id), None, response

    transactions, error, response = request(params)
    if error:
        return {"transactions": [], "error": error, "next_cursor": None}
    if not transactions and "environment" in params:
        transactions, fallback_error, fallback_response = request({"project": str(project_id)})
        if fallback_error:
            return {"transactions": [], "error": fallback_error, "next_cursor": None}
        response = fallback_response

    next_cursor = None
    link_header = getattr(response, "headers", {}).get("Link", "") if response is not None else ""
    if link_header:
        match = re.search(r"[?&]cursor=([^&>\"]+)[^>]*>;\s*rel=\"next\"", link_header)
        if match:
            next_cursor = match.group(1)
    return {"transactions": transactions or [], "error": None, "next_cursor": next_cursor}


def _validate_uptime_url(url: Any) -> tuple[str | None, str | None]:
    """Accept only absolute HTTP(S) targets before creating a monitor.

    GlitchTip's monitor endpoint accepts a URL that it will actively request.
    Rejecting malformed or non-web schemes locally prevents an invalid target
    from being persisted remotely and keeps the typed action response honest.
    """

    candidate = "" if url is None else str(url)
    if not candidate or candidate != candidate.strip() or any(char.isspace() for char in candidate):
        return None, "url must be an absolute http or https URL"
    try:
        parsed = urlparse(candidate)
        hostname = parsed.hostname
    except ValueError:
        hostname = None
        parsed = None
    if parsed is None or parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
        return None, "url must be an absolute http or https URL"
    return candidate, None


def get_monitoring_integration_status() -> dict[str, Any]:
    import requests

    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not configured:
        return {
            "success": True,
            "configured": False,
            "reachable": False,
            "availability": "unavailable",
            "status": "unavailable",
            "base_url": base_url,
            "org": org,
            "checked_at": checked_at,
            "error": "GlitchTip integration is not configured",
        }
    # GlitchTip's generic API root is not a reliable authenticated health
    # signal across supported versions (some images return 500 there while
    # the mapped project/organization APIs work).  Probe the least-privilege
    # capability already required by the monitoring views instead: listing
    # projects visible to the configured organization.
    capability_url = f"{base_url}/api/0/organizations/{quote(org, safe='')}/projects/"
    try:
        resp = requests.get(capability_url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
    except Exception as exc:
        availability = "error"
        # Requests exceptions should not be able to echo the configured
        # bearer token, even when a mocked/adapter exception includes it.
        error_msg = redact_text(str(exc), secrets=(token,))[:400]
        reachable = False
    else:
        if not (200 <= resp.status_code < 300):
            availability = "error"
            error_msg = f"GlitchTip HTTP {resp.status_code}"
            reachable = False
        else:
            try:
                payload = resp.json()
            except Exception as exc:
                availability = "error"
                error_msg = f"GlitchTip capability response returned invalid JSON: {redact_text(str(exc), secrets=(token,))}"[:400]
                reachable = False
            else:
                # The organization can legitimately have no projects, so an
                # empty list/dict is still a successful capability response.
                if not isinstance(payload, (list, dict)):
                    availability = "error"
                    error_msg = "GlitchTip capability response was malformed"
                    reachable = False
                else:
                    availability = "available"
                    error_msg = None
                    reachable = True
    return {
        "success": True,
        "configured": True,
        "reachable": reachable,
        "availability": availability,
        "status": availability,
        "base_url": base_url,
        "org": org,
        "checked_at": checked_at,
        "error": error_msg,
    }


def _issue_items_from_payload(payload: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Normalize GlitchTip list and cursor-paginated issue responses."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if not isinstance(payload, dict):
        return None, None
    for key in ("issues", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            cursor = payload.get("next_cursor") or payload.get("nextCursor") or payload.get("next")
            return [item for item in value if isinstance(item, dict)], str(cursor) if cursor else None
    return None, None


def query_monitoring_issues(db: Session, service_name: str, window: str, cursor: str = None) -> dict[str, Any]:
    import re
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    empty = {
        "issues": [], "next_cursor": None, "has_more": False,
        "availability": "unavailable" if not configured else "error",
        "source": "glitchtip", "checked_at": checked_at,
        "error": "GlitchTip integration is not configured" if not configured else None,
    }
    if not configured:
        return empty

    stats_period = "24h" if str(window).lower() in {"24h", "1d"} else "7d"
    url = f"{base_url}/api/0/projects/{quote(org, safe='')}/{quote(str(project_slug), safe='')}/issues/"
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, Any] = {"statsPeriod": stats_period, "query": ""}
    if cursor:
        params["cursor"] = cursor
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return {**empty, "error": f"GlitchTip HTTP {resp.status_code}"}
        try:
            payload = resp.json() or []
        except Exception as exc:
            return {**empty, "error": f"GlitchTip returned invalid issues JSON: {_glitchtip_error(exc, token)}"}
        issues, payload_cursor = _issue_items_from_payload(payload)
        if issues is None:
            return {**empty, "error": "GlitchTip returned a malformed issues payload"}
        normalized = []
        for issue in issues[:20]:
            metadata = issue.get("metadata") or {}
            user_count = issue.get("userCount")
            if user_count is None:
                user_count = metadata.get("users")
            normalized.append({
                "id": str(issue.get("id", "")),
                "title": issue.get("title", ""),
                "level": issue.get("level", "error"),
                "count": str(issue.get("count", "0")),
                "userCount": str(user_count) if user_count is not None else "",
                "culprit": issue.get("culprit") or metadata.get("filename") or "",
                "type": metadata.get("type") or (issue.get("title") or "").split(":")[0],
                "first_seen": issue.get("firstSeen", ""),
                "last_seen": issue.get("lastSeen", ""),
                "permalink": issue.get("permalink", ""),
                "status": issue.get("status", ""),
            })

        next_cursor = None
        link_header = resp.headers.get("Link", "")
        if link_header:
            match = re.search(r'<[^>]*[?&]cursor=([^&>]+)[^>]*>;\s*rel="next"', link_header)
            if match:
                next_cursor = match.group(1)
        next_cursor = next_cursor or payload_cursor

        return {
            "issues": normalized, "next_cursor": next_cursor, "has_more": bool(next_cursor),
            "availability": "available", "source": "glitchtip", "checked_at": checked_at, "error": None,
        }
    except Exception as exc:
        return {**empty, "error": _glitchtip_error(exc, token)}


def get_monitoring_issue_event_details(issue_id: str) -> dict[str, Any]:
    import requests
    base_url, _org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()

    empty = {
        "id": "",
        "eventID": "",
        "title": "",
        "dateCreated": "",
        "user": None,
        "tags": [],
        "entries": [],
        "request": None,
    }
    if not (configured and issue_id):
        return {**empty, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/issues/{quote(str(issue_id), safe='')}/events/latest/"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            payload = resp.json() or empty
            if not isinstance(payload, dict):
                return {**empty, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip returned a malformed event payload"}
            return {**payload, "availability": "available", "source": "glitchtip", "checked_at": checked_at, "error": None}
        return {**empty, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": f"GlitchTip HTTP {resp.status_code}"}
    except Exception as exc:
        return {**empty, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": _glitchtip_error(exc, token)}


def execute_monitoring_issue_action_result(issue_id: str, action: str) -> dict[str, Any]:
    import requests
    base_url, _org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not (configured and issue_id):
        return {"success": False, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/issues/{quote(str(issue_id), safe='')}/"
    action_l = action.lower()
    if action_l in ("delete", "remove"):
        try:
            resp = requests.delete(url, headers=headers, timeout=10)
            ok = resp.status_code in (200, 201, 204)
            return {"success": ok, "availability": "available" if ok else "error", "source": "glitchtip", "checked_at": checked_at, "action": action_l, "target_id": str(issue_id), "error": None if ok else f"GlitchTip HTTP {resp.status_code}"}
        except Exception as exc:
            return {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "action": action_l, "target_id": str(issue_id), "error": _glitchtip_error(exc, token)}
    status_map = {
        "resolve": "resolved",
        "resolved": "resolved",
        "ignore": "ignored",
        "ignored": "ignored",
        "unresolve": "unresolved",
        "unresolved": "unresolved",
    }
    if action_l not in status_map:
        return {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "action": action_l, "target_id": str(issue_id), "error": f"Unsupported issue action: {action}"}
    status = status_map[action_l]
    try:
        resp = requests.put(url, headers=headers, json={"status": status}, timeout=10)
        ok = resp.status_code in (200, 201, 204)
        return {"success": ok, "availability": "available" if ok else "error", "source": "glitchtip", "checked_at": checked_at, "action": status, "target_id": str(issue_id), "error": None if ok else f"GlitchTip HTTP {resp.status_code}"}
    except Exception as exc:
        return {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "action": status, "target_id": str(issue_id), "error": _glitchtip_error(exc, token)}


def execute_monitoring_issue_action(issue_id: str, action: str) -> bool:
    """Legacy boolean adapter retained for existing callers."""

    return bool(execute_monitoring_issue_action_result(issue_id, action).get("success"))


def get_monitoring_uptime_list(service_name: str) -> list[dict[str, Any]]:
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org):
        return []

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{base_url}/api/0/organizations/{org}/monitors/", headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        monitors = resp.json() or []
        filtered = []
        for m in monitors:
            if (m.get("projectName") or "").lower() == project_slug.lower():
                mon_id = m.get("id")
                if mon_id:
                    try:
                        det_resp = requests.get(
                            f"{base_url}/api/0/organizations/{org}/monitors/{mon_id}/", headers=headers, timeout=5
                        )
                        if det_resp.status_code == 200:
                            m = det_resp.json()
                        checks_resp = requests.get(
                            f"{base_url}/api/0/organizations/{org}/monitors/{mon_id}/checks/",
                            params={"is_change": "true"},
                            headers=headers,
                            timeout=5,
                        )
                        if checks_resp.status_code == 200:
                            m["incidents"] = checks_resp.json() or []
                            m["checks"] = m.get("checks") or m.get("incidents") or []
                    except Exception:
                        pass
                filtered.append(m)
        return filtered
    except Exception:
        return []


def get_monitoring_uptime_result(service_name: str) -> dict[str, Any]:
    """Typed uptime collection envelope; the list helper remains compatible."""

    import requests

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not configured:
        return {"items": [], "project_slug": project_slug, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}
    try:
        response = requests.get(f"{base_url}/api/0/organizations/{org}/monitors/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code != 200:
            return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": f"GlitchTip HTTP {response.status_code}"}
        monitors = response.json() or []
        if not isinstance(monitors, list):
            return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip returned a malformed uptime payload"}
        # GlitchTip 6.1 may expose either a slug/name or only the numeric
        # project relation.  Resolve the numeric ID once so monitors from a
        # different project cannot leak into the selected service.
        project_id, _project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)

        def belongs_to_project(item: dict[str, Any]) -> bool:
            name = str(item.get("projectName") or item.get("projectSlug") or "").strip().lower()
            if name and name == str(project_slug).lower():
                return True
            raw = item.get("projectId", item.get("project"))
            if isinstance(raw, dict):
                raw = raw.get("id")
            try:
                return project_id is not None and int(raw) == project_id
            except (TypeError, ValueError):
                return False

        filtered = [item for item in monitors if isinstance(item, dict) and belongs_to_project(item)]
        for monitor in filtered:
            monitor_id = monitor.get("id")
            if not monitor_id:
                continue
            try:
                detail = requests.get(f"{base_url}/api/0/organizations/{org}/monitors/{monitor_id}/", headers={"Authorization": f"Bearer {token}"}, timeout=5)
                if detail.status_code == 200 and isinstance(detail.json(), dict):
                    monitor.update(detail.json())
                checks = requests.get(f"{base_url}/api/0/organizations/{org}/monitors/{monitor_id}/checks/", params={"is_change": "true"}, headers={"Authorization": f"Bearer {token}"}, timeout=5)
                if checks.status_code == 200:
                    monitor["incidents"] = checks.json() or []
                    monitor["checks"] = monitor.get("checks") or monitor["incidents"]
            except Exception:
                # Collection remains available; individual history is absent.
                continue
        return {"items": filtered, "project_slug": project_slug, "availability": "available", "source": "glitchtip", "checked_at": checked_at, "error": None}
    except Exception as exc:
        return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": _glitchtip_error(exc, token)}


def add_monitoring_uptime_check(
    service_name: str, name: str, url: str, interval: int, expected_status: int = 200
) -> dict[str, Any]:
    import requests

    validated_url, validation_error = _validate_uptime_url(url)
    if validation_error:
        return {"success": False, "availability": "error", "error": validation_error, "validation": "invalid_url"}

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org):
        return {"success": False, "error": "GlitchTip is not configured"}

    project_id, project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)
    if project_error:
        return {"success": False, "availability": "error", "error": project_error}

    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "monitorType": "Ping",
        "name": name,
        "url": validated_url,
        "expectedStatus": expected_status,
        "interval": f"00:00:{interval}" if interval < 60 else f"00:{interval // 60:02d}:{interval % 60:02d}",
        "project": str(project_id),
    }
    try:
        resp = requests.post(f"{base_url}/api/0/organizations/{org}/monitors/", headers=headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            return {"success": True, "monitor": resp.json()}
        return {"success": False, "error": f"GlitchTip HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": _glitchtip_error(e, token)}


def add_monitoring_uptime_result(
    *, service_name: str, name: str, url: str, interval: int, expected_status: int = 200,
    monitor_type: str = "Ping", timeout: int = 10, expected_body: str = "", db: Session | None = None,
) -> dict[str, Any]:
    import requests

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    checked_at = _probe_timestamp()
    validated_url, validation_error = _validate_uptime_url(url)
    if validation_error:
        result = {
            "success": False,
            "availability": "error",
            "source": "glitchtip",
            "checked_at": checked_at,
            "project_slug": project_slug,
            "error": validation_error,
            "validation": "invalid_url",
        }
        if db is not None:
            record_event(
                db,
                category="monitoring",
                level="error",
                message="GlitchTip uptime monitor add rejected",
                metadata={
                    "action": "uptime_add",
                    "service_name": service_name,
                    "monitor_name": name,
                    "success": False,
                    "availability": "error",
                    "validation": "invalid_url",
                    "error": validation_error,
                },
            )
        return result

    base_url, org, token, configured = _glitchtip_config()
    if not configured:
        result = {"success": False, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}
    else:
        project_id, project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)
        if project_error:
            result = {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "error": project_error}
        else:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {"monitorType": monitor_type, "name": name, "url": validated_url, "expectedStatus": expected_status, "interval": interval, "timeout": timeout, "expectedBody": expected_body, "project": str(project_id)}
            try:
                response = requests.post(f"{base_url}/api/0/organizations/{org}/monitors/", headers=headers, json=payload, timeout=10)
                ok = response.status_code in (200, 201)
                result = {"success": ok, "availability": "available" if ok else "error", "source": "glitchtip", "checked_at": checked_at, "monitor": response.json() if ok else None, "project_slug": project_slug, "project_id": project_id, "error": None if ok else f"GlitchTip HTTP {response.status_code}"}
            except Exception as exc:
                result = {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "error": _glitchtip_error(exc, token)}
    if db is not None:
        record_event(db, category="monitoring", level="info" if result.get("success") else "error", message="GlitchTip uptime monitor add", metadata={"action": "uptime_add", "service_name": service_name, "monitor_name": name, "success": result.get("success"), "availability": result.get("availability"), "error": result.get("error")})
    return result


def delete_monitoring_uptime_check(monitor_id: str) -> bool:
    import requests
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org and monitor_id):
        return False

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.delete(
            f"{base_url}/api/0/organizations/{org}/monitors/{monitor_id}/", headers=headers, timeout=10
        )
        return resp.status_code in (200, 201, 204)
    except Exception:
        return False


def delete_monitoring_uptime_result(monitor_id: str, db: Session | None = None) -> dict[str, Any]:
    import requests

    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not configured:
        result = {"success": False, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "target_id": str(monitor_id), "error": "GlitchTip integration is not configured"}
    else:
        try:
            response = requests.delete(f"{base_url}/api/0/organizations/{org}/monitors/{monitor_id}/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            ok = response.status_code in (200, 201, 204)
            result = {"success": ok, "availability": "available" if ok else "error", "source": "glitchtip", "checked_at": checked_at, "target_id": str(monitor_id), "error": None if ok else f"GlitchTip HTTP {response.status_code}"}
        except Exception as exc:
            result = {"success": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "target_id": str(monitor_id), "error": _glitchtip_error(exc, token)}
    if db is not None:
        record_event(db, category="monitoring", level="info" if result.get("success") else "error", message="GlitchTip uptime monitor delete", metadata={"action": "uptime_delete", "monitor_id": str(monitor_id), "success": result.get("success"), "availability": result.get("availability"), "error": result.get("error")})
    return result


def get_monitoring_keys(service_name: str) -> list[dict[str, Any]]:
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org):
        return []

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/projects/{org}/{project_slug}/keys/"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json() or []
    except Exception:
        pass
    return []


def get_monitoring_keys_result(service_name: str) -> dict[str, Any]:
    import requests

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not configured:
        return {"items": [], "project_slug": project_slug, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}
    try:
        response = requests.get(f"{base_url}/api/0/projects/{org}/{project_slug}/keys/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code != 200:
            return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": f"GlitchTip HTTP {response.status_code}"}
        items = response.json() or []
        if not isinstance(items, list):
            return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip returned a malformed keys payload"}
        return {"items": items, "project_slug": project_slug, "availability": "available", "source": "glitchtip", "checked_at": checked_at, "error": None}
    except Exception as exc:
        return {"items": [], "project_slug": project_slug, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": _glitchtip_error(exc, token)}


def get_monitoring_performance(service_name: str, node_ip: str = "") -> list[dict[str, Any]]:
    return get_monitoring_performance_result(service_name, node_ip).get("transactions", [])


def get_monitoring_performance_result(service_name: str, node_ip: str = "") -> dict[str, Any]:
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url, org, token, configured = _glitchtip_config()
    checked_at = _probe_timestamp()
    if not configured:
        return {"transactions": [], "project_slug": project_slug, "project_id": None, "node_ip": node_ip, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "error": "GlitchTip integration is not configured"}

    project_id, project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)
    if project_error:
        return {"transactions": [], "project_slug": project_slug, "project_id": None, "node_ip": node_ip, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": project_error}

    fetched = _fetch_monitoring_transaction_groups(
        base_url=base_url,
        org=org,
        token=token,
        project_id=project_id,
        node_ip=node_ip,
    )
    if fetched.get("error"):
        return {"transactions": [], "project_slug": project_slug, "project_id": project_id, "node_ip": node_ip, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "error": fetched["error"]}
    return {"transactions": fetched.get("transactions", []), "project_slug": project_slug, "project_id": project_id, "node_ip": node_ip, "next_cursor": fetched.get("next_cursor"), "availability": "available", "source": "glitchtip", "checked_at": checked_at, "error": None}


def ingest_monitoring_transaction_result(
    *,
    service_name: str,
    transaction: str,
    environment: str = "",
    duration_ms: float = 0.0,
    tags: dict[str, str] | None = None,
    db: Session | None = None,
    poll_attempts: int = 6,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Submit a real Sentry envelope and boundedly observe its group.

    GlitchTip 6.x accepts transaction telemetry through the project numeric
    ``/api/{project_id}/envelope/`` endpoint authenticated by a project DSN
    public key.  The configured PlatformOps API token is used only for project
    and key lookup; it is never placed in the envelope or returned to callers.
    """

    import requests

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    checked_at = _probe_timestamp()
    base_url, org, token, configured = _glitchtip_config()
    result: dict[str, Any]
    event_id = uuid.uuid4().hex
    if not configured:
        result = {"success": False, "accepted_pending": False, "availability": "unavailable", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": None, "event_id": event_id, "transactions": [], "error": "GlitchTip integration is not configured"}
    else:
        project_id, project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)
        if project_error:
            result = {"success": False, "accepted_pending": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": None, "event_id": event_id, "transactions": [], "error": project_error}
        else:
            keys_result = get_monitoring_keys_result(service_name)
            public_key = None
            for key in keys_result.get("items", []):
                if isinstance(key, dict):
                    public_key = key.get("public") or key.get("publicKey") or key.get("public_key")
                    if public_key:
                        break
            if not public_key:
                result = {"success": False, "accepted_pending": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": project_id, "event_id": event_id, "transactions": [], "error": keys_result.get("error") or "GlitchTip project has no ingest key"}
            else:
                now = time.time()
                event: dict[str, Any] = {
                    "event_id": event_id,
                    "type": "transaction",
                    "transaction": str(transaction),
                    "platform": "python",
                    "contexts": {},
                    "start_timestamp": now - max(0.0, float(duration_ms)) / 1000.0,
                    "timestamp": now,
                    "environment": environment or None,
                    "tags": {"platformops_service": service_name, **(tags or {})},
                }
                envelope = "\n".join([
                    json.dumps({"event_id": event_id, "sent_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"}),
                    json.dumps({"type": "transaction", "content_type": "application/json"}),
                    json.dumps(event),
                    "",
                ])
                try:
                    response = requests.post(
                        f"{base_url}/api/{project_id}/envelope/",
                        headers={
                            "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={public_key}, sentry_client=platformops/1.0",
                            "Content-Type": "application/x-sentry-envelope",
                        },
                        data=envelope,
                        timeout=10,
                    )
                except Exception as exc:
                    result = {"success": False, "accepted_pending": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": project_id, "event_id": event_id, "transactions": [], "error": _glitchtip_error(exc, token)}
                else:
                    if response.status_code not in (200, 201, 202):
                        result = {"success": False, "accepted_pending": False, "availability": "error", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": project_id, "event_id": event_id, "transactions": [], "error": f"GlitchTip envelope HTTP {response.status_code}"}
                    else:
                        result = {"success": True, "accepted_pending": True, "availability": "accepted_pending", "source": "glitchtip", "checked_at": checked_at, "project_slug": project_slug, "project_id": project_id, "event_id": event_id, "transactions": [], "error": "GlitchTip accepted the transaction; group materialization is pending"}
                        for attempt in range(max(1, min(int(poll_attempts), 12))):
                            fetched = _fetch_monitoring_transaction_groups(base_url=base_url, org=org, token=token, project_id=project_id, node_ip=environment)
                            if fetched.get("error"):
                                result["availability"] = "error"
                                result["error"] = fetched["error"]
                                break
                            if fetched.get("transactions"):
                                result["accepted_pending"] = False
                                result["availability"] = "available"
                                result["transactions"] = fetched["transactions"]
                                result["error"] = None
                                break
                            if attempt + 1 < max(1, min(int(poll_attempts), 12)):
                                time.sleep(max(0.0, min(float(poll_interval), 2.0)))
    if db is not None:
        record_event(
            db,
            category="monitoring",
            level="info" if result.get("success") else "error",
            message="GlitchTip transaction ingest",
            metadata={
                "action": "transaction_ingest",
                "service_name": service_name,
                "project_slug": project_slug,
                "project_id": result.get("project_id"),
                "event_id": event_id,
                "success": result.get("success"),
                "accepted_pending": result.get("accepted_pending"),
                "availability": result.get("availability"),
                "error": result.get("error"),
            },
        )
    return result


def patch_service_runtime_observability(db: Session, service_id: int) -> dict[str, Any]:
    import subprocess
    import sys
    service = db.get(ServiceInstance, service_id)
    if not service:
        return {"success": False, "error": "Service instance not found"}

    if settings.local_mode:
        return {
            "success": False,
            "availability": "error",
            "source": "runtime_patch",
            "error": "Runtime patch requires a remote node (local_mode has no real container target).",
            "stdout": "",
            "stderr": "",
        }

    # The PlatformOps GlitchTip credential is an API bearer token, not a DSN
    # key. Resolve the public project key before patching a target runtime so
    # the command never places a bearer secret in a service's DSN.
    base_url, org, token, configured = _glitchtip_config()
    project_slug = settings.glitchtip_project_map.get(service.name, service.name.lower())
    if not configured:
        return {
            "success": False,
            "availability": "unavailable",
            "source": "runtime_patch",
            "error": "GlitchTip integration is not configured",
            "stdout": "",
            "stderr": "",
        }
    project_id, project_error = _resolve_glitchtip_project_id(base_url, org, token, project_slug)
    if project_error:
        return {"success": False, "availability": "error", "source": "runtime_patch", "error": project_error, "stdout": "", "stderr": ""}
    keys_result = get_monitoring_keys_result(service.name)
    public_key = next(
        (
            key.get("public") or key.get("publicKey") or key.get("public_key")
            for key in keys_result.get("items", [])
            if isinstance(key, dict)
        ),
        None,
    )
    if not public_key:
        return {"success": False, "availability": "error", "source": "runtime_patch", "error": keys_result.get("error") or "GlitchTip project has no ingest key", "stdout": "", "stderr": ""}

    # Set transient status to patching
    service.status = "patching"
    db.commit()

    patch_script = settings.resolve(settings.ansible_dir) / "playbooks" / "service_runtime_patch.py"
    # Args must match service_runtime_patch.py (underscores, not hyphens).
    parsed_base = urlparse(base_url)
    dsn_host = parsed_base.netloc or parsed_base.path
    dsn_path = parsed_base.path.rstrip("/") if parsed_base.netloc else ""
    dsn = f"{parsed_base.scheme or 'http'}://{public_key}@{dsn_host}{dsn_path}/{project_id}"
    cmd = [
        sys.executable,
        str(patch_script),
        "--container_name",
        service.container_name or "",
        "--service_type",
        service.service_key or "",
        "--service_name",
        service.name or service.service_key or "",
        "--service_id",
        str(service.id),
        "--sentry_dsn",
        dsn,
        "--glitchtip_enabled",
        "true",
        "--environment",
        "validation",
        "--restart",
        "true",
    ]
    if service.node_id:
        cmd.extend(["--node_id", str(service.node_id)])
    if service.node and service.node.host:
        cmd.extend(["--node_ip", str(service.node.host)])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        payload: dict[str, Any] = {
            "success": False,
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
            "returncode": res.returncode,
        }
        # Script prints JSON and often exits 0 even on logical failure — parse honestly.
        raw = (res.stdout or "").strip()
        if raw:
            try:
                parsed = json.loads(raw.splitlines()[-1] if "\n" in raw else raw)
                if isinstance(parsed, dict):
                    payload["success"] = bool(parsed.get("success"))
                    if parsed.get("error"):
                        payload["error"] = parsed.get("error")
                    payload["result"] = parsed
            except json.JSONDecodeError:
                payload["success"] = res.returncode == 0
        else:
            payload["success"] = res.returncode == 0
            if not payload["success"]:
                payload["error"] = (res.stderr or "runtime patch failed").strip()
        return payload
    except Exception as exc:
        return {"success": False, "availability": "error", "source": "runtime_patch", "error": redact_text(str(exc), secrets=(token,))[:400]}
    finally:
        # Restore actual live status from docker inspect (force reload)
        try:
            from ..service.impl import service_live_status
            service_live_status(db, service, use_cache=False)
        except Exception:
            # Fallback if live status fails
            service.status = "unknown"
            db.commit()
