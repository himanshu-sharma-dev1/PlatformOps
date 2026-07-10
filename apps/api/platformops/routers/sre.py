from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["sre"])

@router.get("/api/lifecycle/audit", response_model=LifecycleAuditOut)
def lifecycle_audit(hours: int = 72, db: Session = Depends(get_db)) -> dict:
    return lifecycle_audit_report(db, hours=hours)


@router.post("/api/lifecycle/force-approvals", response_model=ForceDeleteApprovalOut)
def create_force_approval(payload: ForceDeleteApprovalCreate, db: Session = Depends(get_db)) -> ForceDeleteApproval:
    try:
        return create_force_delete_approval(
            db,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason,
            requested_by=payload.requested_by,
            ttl_hours=payload.ttl_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/lifecycle/force-approvals", response_model=list[ForceDeleteApprovalOut])
def list_force_approvals(
    limit: int = 100,
    target_type: str | None = None,
    target_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[ForceDeleteApproval]:
    return latest_force_delete_approvals(
        db,
        limit=limit,
        target_type=target_type,
        target_id=target_id,
        status=status,
    )


@router.post("/api/lifecycle/force-approvals/{approval_id}/decision", response_model=ForceDeleteApprovalOut)
def decide_force_approval(
    approval_id: int,
    payload: ForceDeleteApprovalDecision,
    db: Session = Depends(get_db),
) -> ForceDeleteApproval:
    try:
        return decide_force_delete_approval(
            db,
            _get_force_delete_approval(db, approval_id),
            approver=payload.approver,
            status=payload.status,
            decision_note=payload.decision_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/lifecycle/force-approvals/{approval_id}/revoke", response_model=ForceDeleteApprovalOut)
def revoke_force_approval(
    approval_id: int,
    payload: ForceDeleteApprovalRevoke,
    db: Session = Depends(get_db),
) -> ForceDeleteApproval:
    try:
        return revoke_force_delete_approval(
            db,
            _get_force_delete_approval(db, approval_id),
            actor=payload.actor,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/policy/scan", response_model=list[PolicyFindingOut])
def policy_scan(db: Session = Depends(get_db)) -> list[PolicyFinding]:
    return run_policy_scan(db)


@router.get("/api/policy/findings", response_model=list[PolicyFindingOut])
def policy_findings(limit: int = 200, db: Session = Depends(get_db)) -> list[PolicyFinding]:
    return latest_policy_findings(db, limit=limit)


@router.post("/api/slo/evaluate", response_model=list[SloReportOut])
def slo_evaluate(db: Session = Depends(get_db)) -> list[SloReport]:
    return evaluate_slos(db)


@router.get("/api/slo/reports", response_model=list[SloReportOut])
def slo_reports(limit: int = 200, db: Session = Depends(get_db)) -> list[SloReport]:
    return latest_slo_reports(db, limit=limit)


@router.post("/api/incidents", response_model=IncidentRecordOut)
def open_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> IncidentRecord:
    service = db.get(ServiceInstance, payload.service_id) if payload.service_id else None
    node = db.get(Node, payload.node_id) if payload.node_id else None
    return create_incident(
        db,
        title=payload.title,
        severity=payload.severity,
        summary=payload.summary,
        service=service,
        node=node,
    )


@router.get("/api/incidents", response_model=list[IncidentRecordOut])
def incidents(limit: int = 100, db: Session = Depends(get_db)) -> list[IncidentRecord]:
    return latest_incidents(db, limit=limit)


@router.post("/api/incidents/{incident_id}/resolve", response_model=IncidentRecordOut)
def close_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentRecord:
    return resolve_incident(db, _get_incident(db, incident_id))


@router.post("/api/incidents/{incident_id}/runbook/{runbook_key}", response_model=RunbookExecutionOut)
def incident_runbook(incident_id: int, runbook_key: str, db: Session = Depends(get_db)) -> RunbookExecution:
    try:
        return execute_runbook(db, runbook_key=runbook_key, incident=_get_incident(db, incident_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/runbooks/executions", response_model=list[RunbookExecutionOut])
def runbook_executions(limit: int = 100, db: Session = Depends(get_db)) -> list[RunbookExecution]:
    return latest_runbook_executions(db, limit=limit)


@router.get("/api/capacity/reports", response_model=list[CapacityReportOut])
def capacity_reports(limit: int = 100, db: Session = Depends(get_db)) -> list[CapacityReport]:
    return latest_capacity_reports(db, limit=limit)


@router.post("/api/secrets", response_model=SecretRecordOut)
def create_secret(payload: SecretCreate, db: Session = Depends(get_db)) -> SecretRecord:
    service = db.get(ServiceInstance, payload.service_id) if payload.service_id else None
    node = db.get(Node, payload.node_id) if payload.node_id else None
    return create_secret_record(
        db,
        key=payload.key,
        service=service,
        node=node,
        scope=payload.scope,
        rotation_interval_days=payload.rotation_interval_days,
    )


@router.get("/api/secrets", response_model=list[SecretRecordOut])
def secrets(limit: int = 100, db: Session = Depends(get_db)) -> list[SecretRecord]:
    return latest_secrets(db, limit=limit)


@router.post("/api/secrets/{secret_id}/rotate", response_model=SecretRecordOut)
def rotate_secret(secret_id: int, db: Session = Depends(get_db)) -> SecretRecord:
    return rotate_secret_record(db, _get_secret(db, secret_id))


@router.post("/api/maintenance", response_model=MaintenanceWindowOut)
def create_maintenance(payload: MaintenanceWindowCreate, db: Session = Depends(get_db)) -> MaintenanceWindow:
    service = db.get(ServiceInstance, payload.service_id) if payload.service_id else None
    node = db.get(Node, payload.node_id) if payload.node_id else None
    return schedule_maintenance(
        db,
        title=payload.title,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        impact=payload.impact,
        service=service,
        node=node,
    )


@router.get("/api/maintenance", response_model=list[MaintenanceWindowOut])
def maintenance_windows(limit: int = 100, db: Session = Depends(get_db)) -> list[MaintenanceWindow]:
    return latest_maintenance_windows(db, limit=limit)


@router.post("/api/maintenance/{maintenance_id}/complete", response_model=MaintenanceWindowOut)
def maintenance_complete(maintenance_id: int, db: Session = Depends(get_db)) -> MaintenanceWindow:
    return complete_maintenance(db, _get_maintenance(db, maintenance_id))


@router.post("/api/audit/exports", response_model=AuditExportOut)
def audit_export(export_type: str = "summary", db: Session = Depends(get_db)) -> AuditExport:
    return create_audit_export(db, export_type=export_type)


@router.get("/api/audit/exports", response_model=list[AuditExportOut])
def audit_exports(limit: int = 100, db: Session = Depends(get_db)) -> list[AuditExport]:
    return latest_audit_exports(db, limit=limit)


def _mask_cluster(cluster: Cluster) -> Cluster:
    """Return cluster ORM object with secrets masked for API responses (mutates in-memory only)."""
    if cluster.repo_token:
        cluster.repo_token = "***"
    if cluster.registry_password:
        cluster.registry_password = "***"
    return cluster


