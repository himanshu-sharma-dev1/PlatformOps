from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..catalog import (
    get_service_contract,
    observability_catalog,
    required_dependencies,
)
from ..jobs import create_job, finish_job
from ..models import (
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
from ..settings import settings
from ..tasks import run_job_async
from .common import (
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
    from .service import _service_by_key

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
    from .service import _service_by_key

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
    from .monitoring import get_service_metrics

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
    command = (
        f"{_ansible_base_command(service.node, 'service_log_backfill.yml')} --extra-vars service={service.service_key}"
    )
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


def deploy_observability_stack(db: Session, node: Node) -> DeploymentJob:
    from .common import _ansible_base_command

    command = f"{_ansible_base_command(node, 'observability_stack.yml')}"
    job = create_job(db, action="deploy-observability", command=command, node_id=node.id)

    if settings.local_mode:
        node.status = "healthy"
        db.commit()
        return finish_job(
            db, job, ok=True, output="Observability stack deployed successfully on its own network platformops-net."
        )

    return run_job_async(db, job, cwd=settings.project_root)
