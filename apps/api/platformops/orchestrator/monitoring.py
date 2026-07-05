from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
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
from ..settings import settings
from .common import (
    RUNNING_STATUSES,
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
    from .service import dependency_preflight

    dependency = dependency_preflight(db, service)
    latest_monitoring = db.scalar(
        select(MonitoringCheck)
        .where(MonitoringCheck.service_id == service.id)
        .order_by(MonitoringCheck.created_at.desc())
    )
    latest_slo = db.scalar(
        select(SloReport).where(SloReport.service_id == service.id).order_by(SloReport.created_at.desc())
    )
    open_incidents = (
        db.scalar(
            select(func.count())
            .select_from(IncidentRecord)
            .where(
                IncidentRecord.service_id == service.id,
                IncidentRecord.status == "open",
            )
        )
        or 0
    )

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


def get_service_summary(db: Session, service_id: int) -> dict[str, Any]:
    service = db.get(ServiceInstance, service_id)
    if not service:
        raise ValueError(f"Service instance not found: {service_id}")

    contract = json.loads(service.config_json or "{}")
    from .reports import get_service_capabilities
    from .service import dependency_preflight

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
    from .service import dependency_preflight

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
    from .reports import observability_pipeline_report

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
