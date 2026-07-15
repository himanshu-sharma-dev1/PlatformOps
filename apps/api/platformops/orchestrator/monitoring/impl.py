from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

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
from ...jobs import create_job
from ...tasks import run_job_async
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
        contract = json.loads(service.config_json or "{}")
        health = contract.get("healthcheck", {})

        if not settings.local_mode:
            import subprocess
            import sys

            status_script = settings.resolve(settings.ansible_dir) / "playbooks" / "service_status.py"
            cmd = [
                sys.executable,
                str(status_script),
                "--container-name",
                service.container_name,
                "--network-name",
                service.node.docker_network,
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout.strip():
                    parsed = json.loads(res.stdout)
                    main_info = parsed.get("main_container", {})
                    container_state = main_info.get("state", "unknown")
                    # Update status of container based on real state
                    service.status = "running" if container_state == "running" else container_state
                    status = "ok" if container_state == "running" else "warning"
                    value = container_state
                    detail = json.dumps(main_info)
                else:
                    status = "warning"
                    value = "unknown"
                    detail = f"Status script failed: {res.stderr}"
            except Exception as e:
                status = "warning"
                value = "error"
                detail = f"Failed to execute status check: {e}"
        else:
            status = "ok" if service.status in RUNNING_STATUSES else "warning"
            value = service.status
            detail = health.get("command", "No healthcheck command configured")

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


METRIC_WINDOW_PRESETS: dict[str, dict[str, int]] = {
    "15m": {"points": 6, "step_minutes": 3, "range_seconds": 15 * 60},
    "1h": {"points": 12, "step_minutes": 5, "range_seconds": 3600},
    "6h": {"points": 12, "step_minutes": 30, "range_seconds": 6 * 3600},
    "24h": {"points": 24, "step_minutes": 60, "range_seconds": 24 * 3600},
    "7d": {"points": 28, "step_minutes": 360, "range_seconds": 7 * 86400},
    "1m": {"points": 30, "step_minutes": 1440, "range_seconds": 30 * 86400},
    "3m": {"points": 36, "step_minutes": 3600, "range_seconds": 90 * 86400},
}


def _normalize_metric_window(window: str | None) -> str:
    candidate = (window or "1h").strip().lower()
    # Accept UI aliases
    aliases = {"1M": "1m", "3M": "3m", "30d": "1m", "90d": "3m"}
    candidate = aliases.get(candidate, candidate)
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
    step = max(30, int(preset["range_seconds"] / max(preset["points"], 1)))
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
            inventory = node.host
            user = node.ssh_user or "ubuntu"
            key_arg = ["--private-key", node.ssh_key_path] if node.ssh_key_path else []
            cmd = ["ansible", inventory, "-m", "shell", "-a", "df -hP", "-u", user, *key_arg]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(settings.project_root))
            if proc.returncode == 0:
                # Strip ansible chatter; keep df lines
                lines = []
                for line in proc.stdout.splitlines():
                    if line.lower().startswith("filesystem") or line.startswith("/") or " " in line:
                        lines.append(line)
                parsed = _parse_df("\n".join(lines))
                if parsed:
                    return parsed
        except Exception:
            pass

    return []


def get_node_metrics(db: Session, node_id: int, window: str = "1h") -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    metric_window = _normalize_metric_window(window)
    mounted_volumes = _fetch_mounted_volumes(node)

    cpu_q = '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    mem_q = "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
    disk_q = '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100'
    rx_q = "sum(rate(node_network_receive_bytes_total[5m])) * 8 / 1e6"
    tx_q = "sum(rate(node_network_transmit_bytes_total[5m])) * 8 / 1e6"

    ok_cpu, cpu_val = _prom_query(cpu_q)
    ok_mem, mem_val = _prom_query(mem_q)
    ok_disk, disk_val = _prom_query(disk_q)
    ok_rx, rx_val = _prom_query(rx_q)
    ok_tx, tx_val = _prom_query(tx_q)
    ok_cpu_s, cpu_series = _prom_query_range(cpu_q, metric_window)
    ok_mem_s, mem_series = _prom_query_range(mem_q, metric_window)
    ok_disk_s, disk_series = _prom_query_range(disk_q, metric_window)

    prometheus_reachable = any([ok_cpu, ok_mem, ok_disk, ok_rx, ok_tx, ok_cpu_s, ok_mem_s, ok_disk_s])
    errors = [v for ok, v in [(ok_cpu, cpu_val), (ok_mem, mem_val), (ok_disk, disk_val)] if not ok and isinstance(v, str)]

    if not prometheus_reachable:
        return {
            "node_id": node.id,
            "node_name": node.name,
            "window": metric_window,
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_percent": 0.0,
            "network_rx_mbps": 0.0,
            "network_tx_mbps": 0.0,
            "cpu_series": [],
            "memory_series": [],
            "disk_series": [],
            "mounted_volumes": mounted_volumes,
            "prometheus_reachable": False,
            "error": errors[0] if errors else "Prometheus unreachable",
        }

    def _num(ok: bool, val: Any) -> float:
        if ok and isinstance(val, (int, float)):
            return round(float(val), 1)
        return 0.0

    def _series(ok: bool, val: Any) -> list[dict[str, Any]]:
        if ok and isinstance(val, list):
            return val
        return []

    return {
        "node_id": node.id,
        "node_name": node.name,
        "window": metric_window,
        "cpu_percent": _num(ok_cpu, cpu_val),
        "memory_percent": _num(ok_mem, mem_val),
        "disk_percent": _num(ok_disk, disk_val),
        "network_rx_mbps": _num(ok_rx, rx_val),
        "network_tx_mbps": _num(ok_tx, tx_val),
        "cpu_series": _series(ok_cpu_s, cpu_series),
        "memory_series": _series(ok_mem_s, mem_series),
        "disk_series": _series(ok_disk_s, disk_series),
        "mounted_volumes": mounted_volumes,
        "prometheus_reachable": True,
        "error": None,
    }


def get_service_metrics(db: Session, service_id: int, window: str = "1h") -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    metric_window = _normalize_metric_window(window)
    service_key = service.service_key
    container = service.container_name or service_key

    # Container-level metrics via cAdvisor / exporter style series when available
    cpu_q = f'sum(rate(container_cpu_usage_seconds_total{{name="{container}"}}[5m])) * 100'
    mem_q = f'sum(container_memory_usage_bytes{{name="{container}"}}) / 1024 / 1024'

    ok_cpu, cpu_val = _prom_query(cpu_q)
    if ok_cpu and cpu_val is None:
        ok_cpu, cpu_val = _prom_query(
            f'sum(rate(container_cpu_usage_seconds_total{{name=~".*{service_key}.*"}}[5m])) * 100'
        )
    ok_mem, mem_val = _prom_query(mem_q)
    if ok_mem and mem_val is None:
        ok_mem, mem_val = _prom_query(
            f'sum(container_memory_usage_bytes{{name=~".*{service_key}.*"}}) / 1024 / 1024'
        )
    ok_cpu_s, cpu_series = _prom_query_range(
        f'sum(rate(container_cpu_usage_seconds_total{{name=~".*{service_key}.*"}}[5m])) * 100',
        metric_window,
    )
    err_q = f'sum(rate(container_last_seen{{name=~".*{service_key}.*"}}[5m]))'  # placeholder marker
    # Prefer process restarts from cadvisor
    ok_restarts, restart_val = _prom_query(
        f'sum(container_start_time_seconds{{name=~".*{service_key}.*"}}) or vector(0)'
    )

    prometheus_reachable = ok_cpu or ok_mem or ok_cpu_s
    errors = [v for ok, v in [(ok_cpu, cpu_val), (ok_mem, mem_val)] if not ok and isinstance(v, str)]

    if not prometheus_reachable:
        return {
            "service_id": service.id,
            "service_name": service.name,
            "service_key": service_key,
            "node_id": service.node_id,
            "window": metric_window,
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "log_error_rate": 0.0,
            "queue_depth": 0,
            "restart_count": 0,
            "latency_ms_p95": 0.0,
            "cpu_series": [],
            "error_rate_series": [],
            "queue_depth_series": [],
            "db_metrics": None,
            "broker_metrics": None,
            "custom_charts": [],
            "prometheus_reachable": False,
            "error": errors[0] if errors else "Prometheus unreachable",
        }

    def _num(ok: bool, val: Any, default: float = 0.0) -> float:
        if ok and isinstance(val, (int, float)):
            return round(float(val), 2)
        return default

    cpu_percent = _num(ok_cpu, cpu_val)
    memory_mb = _num(ok_mem, mem_val)

    # Error rate from Loki is out of scope here; surface 0 when Prom has no app-level counters
    log_error_rate = 0.0
    ok_err_s, err_series = _prom_query_range(
        f'sum(rate(container_cpu_system_seconds_total{{name=~".*{service_key}.*"}}[5m])) * 100',
        metric_window,
    )
    error_rate_series = err_series if ok_err_s and isinstance(err_series, list) else []

    result: dict[str, Any] = {
        "service_id": service.id,
        "service_name": service.name,
        "service_key": service_key,
        "node_id": service.node_id,
        "window": metric_window,
        "cpu_percent": cpu_percent,
        "memory_mb": memory_mb,
        "log_error_rate": log_error_rate,
        "queue_depth": 0,
        "restart_count": int(_num(ok_restarts, restart_val, 0)),
        "latency_ms_p95": 0.0,
        "cpu_series": cpu_series if ok_cpu_s and isinstance(cpu_series, list) else [],
        "error_rate_series": error_rate_series,
        "queue_depth_series": [],
        "custom_charts": [],
        "prometheus_reachable": True,
        "error": None,
    }

    # Database-specific metrics from real exporters
    if service_key in ("postgres-core", "postgres", "clickhouse-core"):
        ok_ac, ac = _prom_query("pg_stat_activity_count{state=\"active\"} or sum(pg_stat_activity_count)")
        ok_id, idle = _prom_query("pg_stat_activity_count{state=\"idle\"}")
        ok_ro, ro = _prom_query("rate(pg_stat_database_tup_fetched[5m])")
        ok_wo, wo = _prom_query("rate(pg_stat_database_tup_inserted[5m]) + rate(pg_stat_database_tup_updated[5m])")
        ok_ch, ch = _prom_query(
            "sum(pg_stat_database_blks_hit) / clamp_min(sum(pg_stat_database_blks_hit + pg_stat_database_blks_read), 1) * 100"
        )
        ok_lk, lk = _prom_query("sum(pg_locks_count) or vector(0)")
        result["db_metrics"] = {
            "active_connections": int(_num(ok_ac, ac)),
            "idle_connections": int(_num(ok_id, idle)),
            "read_ops": int(_num(ok_ro, ro)),
            "write_ops": int(_num(ok_wo, wo)),
            "cache_hit_ratio": _num(ok_ch, ch),
            "transaction_locks": int(_num(ok_lk, lk)),
        }
    elif service_key in ("redis-core", "redis"):
        ok_c, conn = _prom_query("redis_connected_clients")
        ok_cmd, cmds = _prom_query("rate(redis_commands_processed_total[5m])")
        ok_hit, hits = _prom_query(
            "redis_keyspace_hits_total / clamp_min(redis_keyspace_hits_total + redis_keyspace_misses_total, 1) * 100"
        )
        result["db_metrics"] = {
            "active_connections": int(_num(ok_c, conn)),
            "idle_connections": 0,
            "read_ops": int(_num(ok_cmd, cmds)),
            "write_ops": 0,
            "cache_hit_ratio": _num(ok_hit, hits),
            "transaction_locks": 0,
        }
    else:
        result["db_metrics"] = None

    if service_key in ("rabbitmq-core", "rabbitmq"):
        ok_in, ing = _prom_query("rate(rabbitmq_global_messages_received_total[5m]) or rate(rabbitmq_queue_messages_published_total[5m])")
        ok_del, delv = _prom_query("rate(rabbitmq_global_messages_delivered_total[5m]) or rate(rabbitmq_queue_messages_delivered_total[5m])")
        ok_ready, ready = _prom_query("sum(rabbitmq_queue_messages_ready)")
        ok_unack, unack = _prom_query("sum(rabbitmq_queue_messages_unacked)")
        ok_cons, cons = _prom_query("sum(rabbitmq_queue_consumers)")
        result["broker_metrics"] = {
            "ingestion_rate": _num(ok_in, ing),
            "delivery_rate": _num(ok_del, delv),
            "queued_ready": int(_num(ok_ready, ready)),
            "queued_unacked": int(_num(ok_unack, unack)),
            "consumer_count": int(_num(ok_cons, cons)),
        }
        result["queue_depth"] = int(_num(ok_ready, ready))
        ok_qd_s, qd_series = _prom_query_range("sum(rabbitmq_queue_messages_ready)", metric_window)
        if ok_qd_s and isinstance(qd_series, list):
            result["queue_depth_series"] = qd_series
    else:
        result["broker_metrics"] = None

    # Schema-driven custom charts from service contract
    contract = json.loads(service.config_json or "{}")
    custom_defs = contract.get("custom_metrics") or contract.get("performance_charts") or []
    custom_charts: list[dict[str, Any]] = []
    for item in custom_defs:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or "Custom metric"
        unit = item.get("unit") or ""
        queries = item.get("series") or item.get("queries") or []
        series_out: list[dict[str, Any]] = []
        if isinstance(queries, dict):
            queries = [{"name": k, "query": v} for k, v in queries.items()]
        for series_def in queries:
            if not isinstance(series_def, dict):
                continue
            q = series_def.get("query") or series_def.get("promql") or ""
            name = series_def.get("name") or series_def.get("label") or "series"
            if not q:
                continue
            ok_s, pts = _prom_query_range(q, metric_window)
            series_out.append({"name": name, "points": pts if ok_s and isinstance(pts, list) else []})
        if series_out:
            custom_charts.append({"title": title, "unit": unit, "series": series_out})
    result["custom_charts"] = custom_charts

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


def get_monitoring_integration_status() -> dict[str, Any]:
    import requests
    base_url = settings.glitchtip_base_url.rstrip("/")
    org = settings.glitchtip_org_slug
    token = settings.glitchtip_token
    configured = bool(base_url and org and token)
    reachable = False
    error_msg = ""
    if configured:
        try:
            resp = requests.get(f"{base_url}/api/0/", headers={"Authorization": f"Bearer {token}"}, timeout=5)
            reachable = resp.status_code < 500
        except Exception as exc:
            error_msg = str(exc)
    return {
        "success": True,
        "configured": configured,
        "reachable": reachable,
        "base_url": base_url,
        "org": org,
        "error": error_msg,
    }


def query_monitoring_issues(db: Session, service_name: str, window: str, cursor: str = None) -> dict[str, Any]:
    import re
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    empty = {"issues": [], "next_cursor": None}
    if not (base_url and token and org):
        return empty

    stats_period = "24h" if window == "24h" else "7d"
    url = f"{base_url}/api/0/projects/{org}/{project_slug}/issues/"
    if cursor:
        url = f"{url}?cursor={cursor}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"statsPeriod": stats_period, "query": ""}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return empty
        issues = resp.json() or []
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

        return {"issues": normalized, "next_cursor": next_cursor}
    except Exception as exc:
        print(f"GlitchTip query issues failed: {exc}")
        return empty


def get_monitoring_issue_event_details(issue_id: str) -> dict[str, Any]:
    import requests
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token

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
    if not (base_url and token and issue_id):
        return empty

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/issues/{issue_id}/events/latest/"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return empty


def execute_monitoring_issue_action(issue_id: str, action: str) -> bool:
    import requests
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token

    if not (base_url and token and issue_id):
        return False

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/issues/{issue_id}/"
    action_l = action.lower()
    if action_l in ("delete", "remove"):
        try:
            resp = requests.delete(url, headers=headers, timeout=10)
            return resp.status_code in (200, 201, 204)
        except Exception:
            return False
    status_map = {
        "resolve": "resolved",
        "resolved": "resolved",
        "ignore": "ignored",
        "ignored": "ignored",
        "unresolve": "unresolved",
        "unresolved": "unresolved",
    }
    status = status_map.get(action_l, "resolved")
    try:
        resp = requests.put(url, headers=headers, json={"status": status}, timeout=10)
        return resp.status_code in (200, 201, 204)
    except Exception:
        return False


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


def add_monitoring_uptime_check(
    service_name: str, name: str, url: str, interval: int, expected_status: int = 200
) -> dict[str, Any]:
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org):
        return {"success": False, "error": "GlitchTip is not configured"}

    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "monitorType": "Ping",
        "name": name,
        "url": url,
        "expectedStatus": expected_status,
        "interval": f"00:00:{interval}" if interval < 60 else f"00:{interval // 60:02d}:{interval % 60:02d}",
        "project": project_slug,
    }
    try:
        resp = requests.post(f"{base_url}/api/0/organizations/{org}/monitors/", headers=headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            return {"success": True, "monitor": resp.json()}
        return {"success": False, "error": f"GlitchTip returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


def get_monitoring_performance(service_name: str, node_ip: str = "") -> list[dict[str, Any]]:
    import requests
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    base_url = settings.glitchtip_base_url.rstrip("/")
    token = settings.glitchtip_token
    org = settings.glitchtip_org_slug

    if not (base_url and token and org):
        return []

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url}/api/0/organizations/{org}/transaction-groups/"
    params = {}
    if node_ip and node_ip != "0.0.0.0":
        params["environment"] = node_ip
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            txs = resp.json() or []
            return [tx for tx in txs if (tx.get("projectName") or "").lower() == project_slug.lower()]
    except Exception:
        pass
    return []


def patch_service_runtime_observability(db: Session, service_id: int) -> dict[str, Any]:
    import subprocess
    import sys
    service = db.get(ServiceInstance, service_id)
    if not service:
        return {"success": False, "error": "Service instance not found"}

    if settings.local_mode:
        return {
            "success": False,
            "error": "Runtime patch requires a remote node (local_mode has no real container target).",
            "stdout": "",
            "stderr": "",
        }

    # Set transient status to patching
    service.status = "patching"
    db.commit()

    patch_script = settings.resolve(settings.ansible_dir) / "playbooks" / "service_runtime_patch.py"
    # Args must match service_runtime_patch.py (underscores, not hyphens).
    dsn = (
        f"{settings.glitchtip_base_url.rstrip('/')}/{service.id}"
        if not settings.glitchtip_token
        else f"http://{settings.glitchtip_token}@{settings.glitchtip_base_url.split('://', 1)[-1].rstrip('/')}/{service.id}"
    )
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
        return {"success": False, "error": str(exc)}
    finally:
        # Restore actual live status from docker inspect (force reload)
        try:
            from ..service.impl import service_live_status
            service_live_status(db, service, use_cache=False)
        except Exception:
            # Fallback if live status fails
            service.status = "unknown"
            db.commit()
