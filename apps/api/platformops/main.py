from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db, init_db
from .models import (
    AuditExport,
    BackupRun,
    CapacityReport,
    Cluster,
    ConfigSnapshot,
    DeploymentJob,
    DriftReport,
    ForceDeleteApproval,
    IncidentRecord,
    LogArchive,
    MaintenanceWindow,
    MonitoringCheck,
    Node,
    OperationalEvent,
    PolicyFinding,
    ReleaseApproval,
    ReleaseRecord,
    RunbookExecution,
    SecretRecord,
    ServiceInstance,
    SloReport,
)
from .orchestrator import (
    apply_config,
    apply_config_direct,
    apply_config_migration,
    assess_release_safety,
    backfill_service_logs,
    bootstrap_observability_plane,
    capability_coverage_report,
    catalog_cards,
    compare_config_snapshots,
    complete_maintenance,
    create_audit_export,
    create_config_snapshot,
    create_force_delete_approval,
    create_incident,
    create_release,
    create_release_approval,
    create_secret_record,
    create_service_instance,
    decide_force_delete_approval,
    decide_release_approval,
    delete_service,
    dependency_preflight,
    deploy_service,
    deploy_subsystem,
    deployment_plan,
    detect_drift,
    diagnostics_targets_for_service,
    evaluate_force_delete_policy,
    evaluate_slos,
    execute_deployment_plan,
    execute_runbook,
    generate_capacity_report,
    generate_compose,
    generate_inventory,
    get_cluster_operations_view,
    get_cluster_summary,
    get_config_snapshot_detail,
    get_config_timeline_page,
    get_dashboard_summary,
    get_dtrain_overview,
    get_node_connection_report,
    get_node_job_history,
    get_node_metrics,
    get_node_onboarding_report,
    get_node_summary,
    get_service_capabilities,
    get_service_metrics,
    get_service_release_timeline,
    get_service_summary,
    get_subsystem_rollout_plan,
    index_log_archives,
    install_missing_dependencies,
    latest_audit_exports,
    latest_capacity_reports,
    latest_force_delete_approvals,
    latest_incidents,
    latest_maintenance_windows,
    latest_monitoring_checks,
    latest_policy_findings,
    latest_release_approvals,
    latest_runbook_executions,
    latest_secrets,
    latest_slo_reports,
    lifecycle_audit_report,
    lifecycle_impact,
    list_config_snapshots_page,
    list_events,
    list_releases,
    mark_force_delete_approval_used,
    observability_pipeline_report,
    placement_auto_deploy,
    placement_recommendations,
    prepare_config_migration,
    record_event,
    remediate_node_onboarding,
    rename_config_snapshot,
    resolve_incident,
    restore_config_migration,
    restore_config_snapshot,
    revoke_force_delete_approval,
    revoke_release_approval,
    rollback_release,
    rotate_secret_record,
    run_backup,
    run_monitoring_sweep,
    run_policy_scan,
    schedule_maintenance,
    service_diagnostics,
    service_diagnostics_analysis,
    service_install_schema,
    service_live_logs,
    topology,
    update_service_instance,
    validate_config,
    validate_force_delete_approval,
    validate_node,
)
from .orchestrator import (
    config_workspace as build_config_workspace,
)
from .schemas import (
    AuditExportOut,
    BackupRunOut,
    CapabilityCoverageOut,
    CapacityReportOut,
    ClusterCreate,
    ClusterOperationsOut,
    ClusterOut,
    ClusterSummary,
    ClusterUpdate,
    ConfigApply,
    ConfigSnapshotCompareOut,
    ConfigSnapshotCreate,
    ConfigSnapshotDetailOut,
    ConfigSnapshotOut,
    ConfigSnapshotPageOut,
    ConfigSnapshotRename,
    ConfigTimelinePageOut,
    ConfigValidateOut,
    ConfigWorkspaceOut,
    DashboardSummaryOut,
    DependencyInstallResultOut,
    DeploymentExecuteIn,
    DeploymentExecuteOut,
    DeploymentPlanOut,
    DiagnosticsAnalysisOut,
    DiagnosticsLiveOut,
    DiagnosticsOut,
    DiagnosticsTargetOut,
    DriftReportOut,
    DTrainOverview,
    ForceDeleteApprovalCreate,
    ForceDeleteApprovalDecision,
    ForceDeleteApprovalOut,
    ForceDeleteApprovalRevoke,
    GeneratedArtifactOut,
    IncidentCreate,
    IncidentRecordOut,
    JobOut,
    LifecycleAuditOut,
    LifecycleImpact,
    LogArchiveOut,
    MaintenanceWindowCreate,
    MaintenanceWindowOut,
    MonitoringCheckOut,
    NodeConnectionOut,
    NodeCreate,
    NodeJobHistoryOut,
    NodeMetricsOut,
    NodeOnboardingOut,
    NodeOnboardingRemediationOut,
    NodeOnboardingRemediationRequest,
    NodeOut,
    NodeSummary,
    NodeUpdate,
    ObservabilityBootstrapOut,
    ObservabilityPipelineOut,
    OperationalEventOut,
    PlacementDeployOut,
    PlacementRecommendationOut,
    PolicyFindingOut,
    PreflightOut,
    ReleaseApprovalCreate,
    ReleaseApprovalDecision,
    ReleaseApprovalOut,
    ReleaseApprovalRevoke,
    ReleaseCreate,
    ReleaseRecordOut,
    ReleaseSafetyOut,
    RunbookExecutionOut,
    SecretCreate,
    SecretRecordOut,
    ServiceCapabilities,
    ServiceCreate,
    ServiceInstallSchemaOut,
    ServiceMetricsOut,
    ServiceOut,
    ServiceReleaseTimelineOut,
    ServiceSummaryOut,
    ServiceUpdate,
    SloReportOut,
    SubsystemRolloutPlan,
    TopologyOut,
)

app = FastAPI(
    title="PlatformOps API",
    version="0.1.0",
    description="A portfolio-grade DevOps control plane for Ansible, Docker, config snapshots, and diagnostics.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def _get_cluster(db: Session, cluster_id: int) -> Cluster:
    cluster = db.get(Cluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


def _get_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def _get_service(db: Session, service_id: int) -> ServiceInstance:
    service = db.get(ServiceInstance, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


def _get_snapshot(db: Session, snapshot_id: int) -> ConfigSnapshot:
    snapshot = db.get(ConfigSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Config snapshot not found")
    return snapshot


def _get_release(db: Session, release_id: int) -> ReleaseRecord:
    release = db.get(ReleaseRecord, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


def _get_incident(db: Session, incident_id: int) -> IncidentRecord:
    incident = db.get(IncidentRecord, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _get_secret(db: Session, secret_id: int) -> SecretRecord:
    secret = db.get(SecretRecord, secret_id)
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")
    return secret


def _get_maintenance(db: Session, maintenance_id: int) -> MaintenanceWindow:
    window = db.get(MaintenanceWindow, maintenance_id)
    if window is None:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    return window


def _get_force_delete_approval(db: Session, approval_id: int) -> ForceDeleteApproval:
    approval = db.get(ForceDeleteApproval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Force delete approval not found")
    return approval


def _get_release_approval(db: Session, approval_id: int) -> ReleaseApproval:
    approval = db.get(ReleaseApproval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Release approval not found")
    return approval


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "platformops-api"}


@app.get("/api/catalog/services")
def list_catalog() -> list[dict]:
    return catalog_cards()


@app.get("/api/catalog/services/{service_key}/install-schema", response_model=ServiceInstallSchemaOut)
def get_service_install_schema(
    service_key: str,
    node_id: int,
    service_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    node = _get_node(db, node_id)
    service = _get_service(db, service_id) if service_id is not None else None
    return service_install_schema(db, service_key=service_key, node=node, service=service)


@app.get("/api/topology", response_model=TopologyOut)
def get_topology(db: Session = Depends(get_db)) -> dict:
    return topology(db)


@app.get("/api/nodes/{node_id}/deployment-plan/{service_key}", response_model=DeploymentPlanOut)
def get_deployment_plan(node_id: int, service_key: str, db: Session = Depends(get_db)) -> dict:
    try:
        return deployment_plan(db, _get_node(db, node_id), service_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/services/placement/recommendations/{service_key}", response_model=PlacementRecommendationOut)
def get_placement_recommendations(
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: str | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    parsed_avoid: list[int] = []
    if avoid_node_ids:
        parsed_avoid = [int(value.strip()) for value in avoid_node_ids.split(",") if value.strip()]
    try:
        return placement_recommendations(
            db,
            service_key=service_key,
            prefer_node_id=prefer_node_id,
            avoid_node_ids=parsed_avoid,
            anti_affinity_service_key=anti_affinity_service_key,
            require_healthy=require_healthy,
            spread_subsystem=spread_subsystem,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/placement/deploy/{service_key}", response_model=PlacementDeployOut)
def deploy_from_placement(
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: str | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
    auto_install_dependencies: bool = True,
    allow_capacity_risk: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    parsed_avoid: list[int] = []
    if avoid_node_ids:
        parsed_avoid = [int(value.strip()) for value in avoid_node_ids.split(",") if value.strip()]
    try:
        return placement_auto_deploy(
            db,
            service_key=service_key,
            prefer_node_id=prefer_node_id,
            avoid_node_ids=parsed_avoid,
            anti_affinity_service_key=anti_affinity_service_key,
            require_healthy=require_healthy,
            spread_subsystem=spread_subsystem,
            auto_install_dependencies=auto_install_dependencies,
            allow_capacity_risk=allow_capacity_risk,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/observability/pipeline", response_model=ObservabilityPipelineOut)
def observability_pipeline(db: Session = Depends(get_db)) -> dict:
    return observability_pipeline_report(db)



import subprocess
import json

@app.post("/api/observability/deploy")
def deploy_observability():
    result = subprocess.run(
        ["ansible-playbook", "-c", "local", "ops/ansible/playbooks/deploy_observability.yml"],
        cwd="/app",
        capture_output=True, text=True
    )
    return {"success": result.returncode == 0, "output": result.stdout + result.stderr}

@app.post("/api/observability/teardown")
def teardown_observability():
    result = subprocess.run(
        ["ansible-playbook", "-c", "local", "ops/ansible/playbooks/teardown_observability.yml"],
        cwd="/app",
        capture_output=True, text=True
    )
    return {"success": result.returncode == 0, "output": result.stdout + result.stderr}

@app.get("/api/observability/status")
def get_observability_status():
    result = subprocess.run(
        ["docker", "compose", "-f", "ops/compose/docker-compose.observability.yml", "-p", "platformops-obs", "ps", "--format", "json"],
        cwd="/app",
        capture_output=True, text=True
    )
    containers = []
    for line in result.stdout.strip().splitlines():
        if line:
            containers.append(json.loads(line))
    return {"containers": containers}


import urllib.request
import urllib.parse
from datetime import datetime, timedelta

@app.get("/api/diagnostics/logs")
def get_diagnostics_logs(service: str, start: str = None, end: str = None, limit: int = 100):
    try:
        if not start:
            start = str(int((datetime.now() - timedelta(hours=1)).timestamp() * 1e9))
        if not end:
            end = str(int(datetime.now().timestamp() * 1e9))
        
        query = '{container_name=~".*%s.*"}' % service
        params = urllib.parse.urlencode({
            'query': query,
            'start': start,
            'end': end,
            'limit': limit
        })
        url = f"http://platformops-obs-loki:3100/loki/api/v1/query_range?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metrics/node")
def get_node_metrics():
    try:
        queries = {
            "cpu": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "memory": '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
            "disk": '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100'
        }
        results = {}
        for key, q in queries.items():
            params = urllib.parse.urlencode({'query': q})
            url = f"http://platformops-obs-prometheus:9090/api/v1/query?{params}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                if data["data"]["result"]:
                    results[key] = data["data"]["result"][0]["value"][1]
                else:
                    results[key] = 0
        return results
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metrics/processes")
def get_process_metrics():
    try:
        q = 'topk(10, rate(namedprocess_namegroup_cpu_seconds_total[5m]))'
        params = urllib.parse.urlencode({'query': q})
        url = f"http://platformops-obs-prometheus:9090/api/v1/query?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            results = []
            for item in data["data"]["result"]:
                results.append({
                    "name": item["metric"].get("groupname", "unknown"),
                    "cpu": item["value"][1]
                })
            return {"processes": results}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_summary(db)


@app.post("/api/nodes/{node_id}/observability/bootstrap", response_model=ObservabilityBootstrapOut)
def bootstrap_observability(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return bootstrap_observability_plane(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/artifacts/inventory", response_model=GeneratedArtifactOut)
def node_inventory(node_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    node = _get_node(db, node_id)
    return {"name": f"{node.name}-inventory.ini", "content_type": "text/ini", "content": generate_inventory(node)}


@app.get("/api/nodes/{node_id}/artifacts/compose", response_model=GeneratedArtifactOut)
def node_compose(node_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    node = _get_node(db, node_id)
    return {
        "name": f"{node.name}-docker-compose.yml",
        "content_type": "application/x-yaml",
        "content": generate_compose(db, node),
    }


@app.get("/api/events", response_model=list[OperationalEventOut])
def get_events(
    limit: int = 100,
    category: str | None = None,
    level: str | None = None,
    node_id: int | None = None,
    service_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[OperationalEvent]:
    return list_events(
        db,
        limit=limit,
        category=category,
        level=level,
        node_id=node_id,
        service_id=service_id,
        search=search,
    )


@app.get("/api/capabilities/coverage", response_model=CapabilityCoverageOut)
def capabilities_coverage(db: Session = Depends(get_db)) -> dict:
    return capability_coverage_report(db)


@app.get("/api/lifecycle/audit", response_model=LifecycleAuditOut)
def lifecycle_audit(hours: int = 72, db: Session = Depends(get_db)) -> dict:
    return lifecycle_audit_report(db, hours=hours)


@app.post("/api/lifecycle/force-approvals", response_model=ForceDeleteApprovalOut)
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


@app.get("/api/lifecycle/force-approvals", response_model=list[ForceDeleteApprovalOut])
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


@app.post("/api/lifecycle/force-approvals/{approval_id}/decision", response_model=ForceDeleteApprovalOut)
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


@app.post("/api/lifecycle/force-approvals/{approval_id}/revoke", response_model=ForceDeleteApprovalOut)
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


@app.post("/api/policy/scan", response_model=list[PolicyFindingOut])
def policy_scan(db: Session = Depends(get_db)) -> list[PolicyFinding]:
    return run_policy_scan(db)


@app.get("/api/policy/findings", response_model=list[PolicyFindingOut])
def policy_findings(limit: int = 200, db: Session = Depends(get_db)) -> list[PolicyFinding]:
    return latest_policy_findings(db, limit=limit)


@app.post("/api/slo/evaluate", response_model=list[SloReportOut])
def slo_evaluate(db: Session = Depends(get_db)) -> list[SloReport]:
    return evaluate_slos(db)


@app.get("/api/slo/reports", response_model=list[SloReportOut])
def slo_reports(limit: int = 200, db: Session = Depends(get_db)) -> list[SloReport]:
    return latest_slo_reports(db, limit=limit)


@app.post("/api/incidents", response_model=IncidentRecordOut)
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


@app.get("/api/incidents", response_model=list[IncidentRecordOut])
def incidents(limit: int = 100, db: Session = Depends(get_db)) -> list[IncidentRecord]:
    return latest_incidents(db, limit=limit)


@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentRecordOut)
def close_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentRecord:
    return resolve_incident(db, _get_incident(db, incident_id))


@app.post("/api/incidents/{incident_id}/runbook/{runbook_key}", response_model=RunbookExecutionOut)
def incident_runbook(incident_id: int, runbook_key: str, db: Session = Depends(get_db)) -> RunbookExecution:
    try:
        return execute_runbook(db, runbook_key=runbook_key, incident=_get_incident(db, incident_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runbooks/executions", response_model=list[RunbookExecutionOut])
def runbook_executions(limit: int = 100, db: Session = Depends(get_db)) -> list[RunbookExecution]:
    return latest_runbook_executions(db, limit=limit)


@app.post("/api/nodes/{node_id}/capacity", response_model=CapacityReportOut)
def node_capacity(node_id: int, db: Session = Depends(get_db)) -> CapacityReport:
    return generate_capacity_report(db, _get_node(db, node_id))


@app.get("/api/capacity/reports", response_model=list[CapacityReportOut])
def capacity_reports(limit: int = 100, db: Session = Depends(get_db)) -> list[CapacityReport]:
    return latest_capacity_reports(db, limit=limit)


@app.post("/api/secrets", response_model=SecretRecordOut)
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


@app.get("/api/secrets", response_model=list[SecretRecordOut])
def secrets(limit: int = 100, db: Session = Depends(get_db)) -> list[SecretRecord]:
    return latest_secrets(db, limit=limit)


@app.post("/api/secrets/{secret_id}/rotate", response_model=SecretRecordOut)
def rotate_secret(secret_id: int, db: Session = Depends(get_db)) -> SecretRecord:
    return rotate_secret_record(db, _get_secret(db, secret_id))


@app.post("/api/maintenance", response_model=MaintenanceWindowOut)
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


@app.get("/api/maintenance", response_model=list[MaintenanceWindowOut])
def maintenance_windows(limit: int = 100, db: Session = Depends(get_db)) -> list[MaintenanceWindow]:
    return latest_maintenance_windows(db, limit=limit)


@app.post("/api/maintenance/{maintenance_id}/complete", response_model=MaintenanceWindowOut)
def maintenance_complete(maintenance_id: int, db: Session = Depends(get_db)) -> MaintenanceWindow:
    return complete_maintenance(db, _get_maintenance(db, maintenance_id))


@app.post("/api/audit/exports", response_model=AuditExportOut)
def audit_export(export_type: str = "summary", db: Session = Depends(get_db)) -> AuditExport:
    return create_audit_export(db, export_type=export_type)


@app.get("/api/audit/exports", response_model=list[AuditExportOut])
def audit_exports(limit: int = 100, db: Session = Depends(get_db)) -> list[AuditExport]:
    return latest_audit_exports(db, limit=limit)


@app.get("/api/clusters", response_model=list[ClusterOut])
def list_clusters(db: Session = Depends(get_db)) -> list[Cluster]:
    return list(db.scalars(select(Cluster).order_by(Cluster.created_at.desc())).all())


@app.post("/api/clusters", response_model=ClusterOut)
def create_cluster(payload: ClusterCreate, db: Session = Depends(get_db)) -> Cluster:
    existing = db.scalar(select(Cluster).where(Cluster.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Cluster name already exists")
    cluster = Cluster(name=payload.name, region=payload.region, environment=payload.environment)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@app.put("/api/clusters/{cluster_id}", response_model=ClusterOut)
def update_cluster(cluster_id: int, payload: ClusterUpdate, db: Session = Depends(get_db)) -> Cluster:
    cluster = _get_cluster(db, cluster_id)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return cluster
    if "name" in updates:
        existing = db.scalar(select(Cluster).where(Cluster.name == updates["name"], Cluster.id != cluster.id))
        if existing:
            raise HTTPException(status_code=409, detail="Cluster name already exists")
    for key, value in updates.items():
        setattr(cluster, key, value)
    db.commit()
    db.refresh(cluster)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Updated cluster '{cluster.name}'",
        metadata={"cluster_id": cluster.id, "updates": updates},
    )
    return cluster


@app.delete("/api/clusters/{cluster_id}")
def delete_cluster(
    cluster_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cluster = _get_cluster(db, cluster_id)
    impact = lifecycle_impact(db, "cluster", cluster_id)
    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="cluster",
            target_id=cluster_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete cluster '{cluster.name}' blocked by policy gates",
                metadata={"cluster_id": cluster_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="cluster",
            target_id=cluster_id,
            approval_id=force_approval_id,
        )
        if not approval_check["allowed"]:
            blocked = {
                **impact,
                "policy": {
                    **policy,
                    "approval": approval_check,
                    "violations": policy["violations"] + approval_check["violations"],
                },
                "recommended_action": "Get an approved force-delete request for this cluster before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete cluster '{cluster.name}' blocked: contains active nodes/services",
            node_id=None,
            metadata={"cluster_id": cluster_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    nodes = db.scalars(select(Node).where(Node.cluster_id == cluster.id)).all()
    node_count = len(nodes)
    service_count = 0
    for n in nodes:
        services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == n.id)).all()
        service_count += len(services)
        for s in services:
            db.delete(s)
        db.delete(n)
    db.delete(cluster)
    db.commit()

    record_event(
        db,
        category="lifecycle",
        level="warning" if force else "info",
        message=f"Deleted cluster '{cluster.name}' (cascaded {node_count} nodes, {service_count} services)"
        if force
        else f"Deleted empty cluster '{cluster.name}'",
        node_id=None,
        metadata={"cluster_id": cluster_id, "node_count": node_count, "service_count": service_count, "force": force},
    )
    if force and force_approval_id is not None:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return {"status": "deleted", "cascaded_nodes": node_count, "cascaded_services": service_count}


@app.get("/api/nodes", response_model=list[NodeOut])
def list_nodes(cluster_id: int | None = None, db: Session = Depends(get_db)) -> list[Node]:
    statement = select(Node).order_by(Node.created_at.desc())
    if cluster_id is not None:
        statement = statement.where(Node.cluster_id == cluster_id)
    return list(db.scalars(statement).all())


def _save_ssh_private_key(node_id: int, private_key_content: str) -> str:
    import os
    import stat

    from .settings import settings

    keys_dir = settings.resolve(settings.runtime_dir) / "ssh_keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key_file = keys_dir / f"node_{node_id}.pem"

    content = private_key_content.strip() + "\n"
    key_file.write_text(content, encoding="utf-8")

    os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
    return str(key_file)


@app.post("/api/nodes", response_model=NodeOut)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)) -> Node:
    _get_cluster(db, payload.cluster_id)
    private_key = payload.ssh_private_key
    node_data = payload.model_dump(exclude={"ssh_private_key"})
    node = Node(**node_data)
    db.add(node)
    db.commit()
    db.refresh(node)

    if private_key:
        key_path = _save_ssh_private_key(node.id, private_key)
        node.ssh_key_path = key_path
        db.commit()
        db.refresh(node)

    return node


@app.put("/api/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)) -> Node:
    node = _get_node(db, node_id)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return node
    if "cluster_id" in updates:
        _get_cluster(db, updates["cluster_id"])

    private_key = updates.pop("ssh_private_key", None)
    if private_key is not None:
        key_path = _save_ssh_private_key(node.id, private_key)
        node.ssh_key_path = key_path

    for key, value in updates.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Updated node '{node.name}'",
        node_id=node.id,
        metadata={"node_id": node.id, "updates": payload.model_dump(exclude_none=True)},
    )
    return node


@app.post("/api/nodes/{node_id}/validate", response_model=JobOut)
def validate_node_endpoint(node_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    return validate_node(db, _get_node(db, node_id))


@app.delete("/api/nodes/{node_id}")
def delete_node(
    node_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    node = _get_node(db, node_id)
    impact = lifecycle_impact(db, "node", node_id)
    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="node",
            target_id=node_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete node '{node.name}' blocked by policy gates",
                node_id=node_id,
                metadata={"node_id": node_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="node",
            target_id=node_id,
            approval_id=force_approval_id,
        )
        if not approval_check["allowed"]:
            blocked = {
                **impact,
                "policy": {
                    **policy,
                    "approval": approval_check,
                    "violations": policy["violations"] + approval_check["violations"],
                },
                "recommended_action": "Get an approved force-delete request for this node before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete node '{node.name}' blocked: has active services",
            node_id=node_id,
            metadata={"node_id": node_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all()
    service_count = len(services)
    for s in services:
        db.delete(s)
    db.delete(node)
    db.commit()

    record_event(
        db,
        category="lifecycle",
        level="warning" if force else "info",
        message=f"Deleted node '{node.name}' (cascaded {service_count} services)"
        if force
        else f"Deleted empty node '{node.name}'",
        node_id=node_id,
        metadata={"node_id": node_id, "service_count": service_count, "force": force, "policy": policy},
    )
    if force and force_approval_id is not None:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return {"status": "deleted", "cascaded_services": service_count}


@app.get("/api/services", response_model=list[ServiceOut])
def list_services(node_id: int | None = None, db: Session = Depends(get_db)) -> list[ServiceInstance]:
    statement = select(ServiceInstance).order_by(ServiceInstance.created_at.desc())
    if node_id is not None:
        statement = statement.where(ServiceInstance.node_id == node_id)
    return list(db.scalars(statement).all())


@app.post("/api/services", response_model=ServiceOut)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)) -> ServiceInstance:
    node = _get_node(db, payload.node_id)
    try:
        return create_service_instance(
            db,
            node=node,
            service_key=payload.service_key,
            name=payload.name,
            contract_overrides=payload.contract_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, payload: ServiceUpdate, db: Session = Depends(get_db)) -> ServiceInstance:
    service = _get_service(db, service_id)
    try:
        return update_service_instance(
            db,
            service,
            name=payload.name,
            contract_overrides=payload.contract_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/preflight", response_model=PreflightOut)
def preflight(service_id: int, db: Session = Depends(get_db)) -> dict:
    return dependency_preflight(db, _get_service(db, service_id))


@app.post("/api/services/{service_id}/dependencies/install-missing", response_model=DependencyInstallResultOut)
def install_service_dependencies(service_id: int, db: Session = Depends(get_db)) -> dict:
    return install_missing_dependencies(db, _get_service(db, service_id))


@app.post("/api/services/{service_id}/deploy", response_model=JobOut)
def deploy(service_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    return deploy_service(db, _get_service(db, service_id))


@app.post("/api/services/{service_id}/deployment/execute", response_model=DeploymentExecuteOut)
def execute_service_deployment(
    service_id: int,
    payload: DeploymentExecuteIn,
    db: Session = Depends(get_db),
) -> dict:
    return execute_deployment_plan(
        db,
        _get_service(db, service_id),
        auto_install_dependencies=payload.auto_install_dependencies,
    )


@app.post("/api/services/{service_id}/delete", response_model=JobOut)
def delete(
    service_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> DeploymentJob:
    service = _get_service(db, service_id)
    impact = lifecycle_impact(db, "service", service_id)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete service '{service.name}' blocked: has dependents or is critical infrastructure",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="service",
            target_id=service_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete service '{service.name}' blocked by policy gates",
                service_id=service_id,
                node_id=service.node_id,
                metadata={"service_id": service_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="service",
            target_id=service_id,
            approval_id=force_approval_id,
        )
        if not approval_check["allowed"]:
            blocked = {
                **impact,
                "policy": {
                    **policy,
                    "approval": approval_check,
                    "violations": policy["violations"] + approval_check["violations"],
                },
                "recommended_action": "Get an approved force-delete request for this service before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Force deleted service '{service.name}' despite warnings",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id, "impact": impact, "policy": policy},
        )
    else:
        record_event(
            db,
            category="lifecycle",
            level="info",
            message=f"Deleted service '{service.name}' successfully",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id},
        )
    deleted = delete_service(db, service)
    if force and force_approval_id is not None and not impact["can_delete_without_force"]:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return deleted


@app.post("/api/services/{service_id}/backup", response_model=BackupRunOut)
def backup_service(service_id: int, db: Session = Depends(get_db)) -> BackupRun:
    return run_backup(db, _get_service(db, service_id))


@app.get("/api/services/{service_id}/releases", response_model=list[ReleaseRecordOut])
def service_releases(service_id: int, limit: int = 100, db: Session = Depends(get_db)) -> list[ReleaseRecord]:
    return list_releases(db, _get_service(db, service_id), limit=limit)


@app.get("/api/services/{service_id}/releases/safety", response_model=ReleaseSafetyOut)
def service_release_safety(
    service_id: int, version: str, image: str | None = None, db: Session = Depends(get_db)
) -> dict:
    return assess_release_safety(db, _get_service(db, service_id), version=version, image=image)


@app.get("/api/services/{service_id}/releases/timeline", response_model=ServiceReleaseTimelineOut)
def service_release_timeline(service_id: int, limit: int = 8, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_release_timeline(db, service_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/release-approvals", response_model=ReleaseApprovalOut)
def create_release_approval_endpoint(payload: ReleaseApprovalCreate, db: Session = Depends(get_db)) -> ReleaseApproval:
    return create_release_approval(
        db,
        service=_get_service(db, payload.service_id),
        target_version=payload.target_version,
        target_image=payload.target_image,
        reason=payload.reason,
        requested_by=payload.requested_by,
        ttl_hours=payload.ttl_hours,
    )


@app.get("/api/release-approvals", response_model=list[ReleaseApprovalOut])
def list_release_approvals(
    service_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)
) -> list[ReleaseApproval]:
    return latest_release_approvals(db, service_id=service_id, limit=limit)


@app.post("/api/release-approvals/{approval_id}/decision", response_model=ReleaseApprovalOut)
def decide_release_approval_endpoint(
    approval_id: int, payload: ReleaseApprovalDecision, db: Session = Depends(get_db)
) -> ReleaseApproval:
    return decide_release_approval(
        db,
        _get_release_approval(db, approval_id),
        approver=payload.approver,
        status=payload.status,
        decision_note=payload.decision_note,
    )


@app.post("/api/release-approvals/{approval_id}/revoke", response_model=ReleaseApprovalOut)
def revoke_release_approval_endpoint(
    approval_id: int, payload: ReleaseApprovalRevoke, db: Session = Depends(get_db)
) -> ReleaseApproval:
    return revoke_release_approval(db, _get_release_approval(db, approval_id), actor=payload.actor, note=payload.note)


@app.post("/api/services/{service_id}/releases", response_model=ReleaseRecordOut)
def release_service(service_id: int, payload: ReleaseCreate, db: Session = Depends(get_db)) -> ReleaseRecord:
    try:
        return create_release(
            db,
            _get_service(db, service_id),
            version=payload.version,
            image=payload.image,
            strategy=payload.strategy,
            notes=payload.notes,
            approval_id=payload.approval_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=json.loads(str(exc))) from exc


@app.post("/api/releases/{release_id}/rollback", response_model=JobOut)
def rollback_service_release(release_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    try:
        return rollback_release(db, _get_release(db, release_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/monitoring/sweep", response_model=list[MonitoringCheckOut])
def monitoring_sweep(db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return run_monitoring_sweep(db)


@app.get("/api/monitoring/checks", response_model=list[MonitoringCheckOut])
def monitoring_checks(limit: int = 200, db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return latest_monitoring_checks(db, limit=limit)


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    job = db.get(DeploymentJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/logs")
def get_job_logs(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    job = db.get(DeploymentJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"output": job.output, "error": job.error, "command": job.command}


@app.get("/api/services/{service_id}/diagnostics", response_model=DiagnosticsOut)
def diagnostics(service_id: int, target_service_key: str | None = None, db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    if not target_service_key or target_service_key == service.service_key:
        return service_diagnostics(db, service, source_service=service)

    target = db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id == service.node_id,
            ServiceInstance.service_key == target_service_key,
        )
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
        )
    allowed_targets = {item["service_key"] for item in diagnostics_targets_for_service(db, service)}
    if target_service_key not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Target '{target_service_key}' is not part of diagnostics context for '{service.service_key}'.",
        )
    return service_diagnostics(db, target, source_service=service)


@app.get("/api/services/{service_id}/diagnostics/analysis", response_model=DiagnosticsAnalysisOut)
def diagnostics_analysis(service_id: int, target_service_key: str | None = None, db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    if not target_service_key or target_service_key == service.service_key:
        return service_diagnostics_analysis(db, service, source_service=service)

    target = db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id == service.node_id,
            ServiceInstance.service_key == target_service_key,
        )
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
        )
    allowed_targets = {item["service_key"] for item in diagnostics_targets_for_service(db, service)}
    if target_service_key not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Target '{target_service_key}' is not part of diagnostics context for '{service.service_key}'.",
        )
    return service_diagnostics_analysis(db, target, source_service=service)


@app.get("/api/services/{service_id}/diagnostics/targets", response_model=list[DiagnosticsTargetOut])
def diagnostics_targets(service_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return diagnostics_targets_for_service(db, _get_service(db, service_id))


@app.get("/api/services/{service_id}/diagnostics/live", response_model=DiagnosticsLiveOut)
def diagnostics_live(
    service_id: int,
    target_service_key: str | None = None,
    tail_lines: int = 150,
    page_size: int = 100,
    cursor: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    target = service
    if target_service_key and target_service_key != service.service_key:
        resolved = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == service.node_id,
                ServiceInstance.service_key == target_service_key,
            )
        )
        if resolved is None:
            raise HTTPException(
                status_code=404,
                detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
            )
        target = resolved
    return service_live_logs(
        db,
        target,
        tail_lines=tail_lines,
        page_size=page_size,
        cursor=cursor,
    )


@app.get("/api/services/{service_id}/diagnostics/archives", response_model=list[LogArchiveOut])
def diagnostics_archives(service_id: int, db: Session = Depends(get_db)) -> list[LogArchive]:
    return index_log_archives(db, _get_service(db, service_id))


@app.post("/api/services/{service_id}/diagnostics/backfill")
def diagnostics_backfill(service_id: int, db: Session = Depends(get_db)) -> dict:
    return backfill_service_logs(db, _get_service(db, service_id))


@app.get("/api/services/{service_id}/config", response_model=ConfigWorkspaceOut)
def config_workspace_endpoint(service_id: int, source: str = "live", db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    try:
        return build_config_workspace(db, service, source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/config/timeline", response_model=ConfigTimelinePageOut)
def config_timeline(
    service_id: int,
    limit: int = 20,
    offset: int = 0,
    action: str = "all",
    actor: str = "all",
    search: str = "",
    created_after: str = "",
    created_before: str = "",
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    return get_config_timeline_page(
        db,
        service,
        limit=limit,
        offset=offset,
        action_filter=action,
        actor_filter=actor,
        search=search,
        created_after=created_after,
        created_before=created_before,
    )


@app.get("/api/services/{service_id}/config/snapshots", response_model=ConfigSnapshotPageOut)
def list_config_snapshots_endpoint(
    service_id: int,
    limit: int = 20,
    offset: int = 0,
    source: str = "all",
    search: str = "",
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    return list_config_snapshots_page(
        db,
        service,
        limit=limit,
        offset=offset,
        source_filter=source,
        search=search,
    )


@app.post("/api/services/{service_id}/config/drift", response_model=DriftReportOut)
def config_drift(service_id: int, db: Session = Depends(get_db)) -> DriftReport:
    return detect_drift(db, _get_service(db, service_id))


@app.post("/api/services/{service_id}/config/snapshots", response_model=ConfigSnapshotOut)
def snapshot_config(service_id: int, payload: ConfigSnapshotCreate, db: Session = Depends(get_db)) -> ConfigSnapshot:
    service = _get_service(db, service_id)
    try:
        return create_config_snapshot(
            db,
            service,
            name=payload.name,
            source=payload.source,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/config/snapshots/{snapshot_id}", response_model=ConfigSnapshotDetailOut)
def get_snapshot_detail(service_id: int, snapshot_id: int, db: Session = Depends(get_db)) -> dict:
    _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    if snapshot.service_id != service_id:
        raise HTTPException(status_code=404, detail="Config snapshot not found for service")
    return get_config_snapshot_detail(db, snapshot)


@app.get("/api/services/{service_id}/config/compare", response_model=ConfigSnapshotCompareOut)
def compare_snapshots(
    service_id: int, left_snapshot_id: int, right_snapshot_id: int, db: Session = Depends(get_db)
) -> dict:
    service = _get_service(db, service_id)
    left_snapshot = _get_snapshot(db, left_snapshot_id)
    right_snapshot = _get_snapshot(db, right_snapshot_id)
    try:
        return compare_config_snapshots(
            db,
            service,
            left_snapshot=left_snapshot,
            right_snapshot=right_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/snapshots/{snapshot_id}/rename", response_model=ConfigSnapshotOut)
def rename_snapshot(
    service_id: int,
    snapshot_id: int,
    payload: ConfigSnapshotRename,
    db: Session = Depends(get_db),
) -> ConfigSnapshot:
    _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    if snapshot.service_id != service_id:
        raise HTTPException(status_code=404, detail="Config snapshot not found for service")
    try:
        return rename_config_snapshot(db, snapshot, name=payload.name, requested_by=payload.requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/snapshots/{snapshot_id}/restore", response_model=JobOut)
def restore_snapshot(service_id: int, snapshot_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    service = _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    try:
        return restore_config_snapshot(db, service, snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/validate", response_model=ConfigValidateOut)
def validate_config_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> dict:
    _get_service(db, service_id)
    result = validate_config(payload.content)
    return {"ok": result["ok"], "message": result["message"]}


@app.post("/api/services/{service_id}/config/apply", response_model=JobOut)
def apply_config_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> DeploymentJob:
    return apply_config(db, _get_service(db, service_id), content=payload.content, apply_mode=payload.apply_mode)


@app.post("/api/services/{service_id}/config/direct-apply")
def apply_config_direct_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> dict:
    try:
        result = apply_config_direct(
            db,
            _get_service(db, service_id),
            content=payload.content,
            apply_mode=payload.apply_mode,
        )
        return {
            "job": result["job"],
            "before_snapshot": result["before_snapshot"],
            "after_snapshot": result["after_snapshot"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/migration/prepare")
def prepare_config_migration_endpoint(
    service_id: int,
    payload: dict[str, int],
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    left_snapshot = _get_snapshot(db, int(payload.get("left_snapshot_id") or 0))
    right_snapshot = _get_snapshot(db, int(payload.get("right_snapshot_id") or 0))
    try:
        return prepare_config_migration(db, service, left_snapshot=left_snapshot, right_snapshot=right_snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/migration/apply")
def apply_config_migration_endpoint(
    service_id: int,
    payload: dict[str, str],
    db: Session = Depends(get_db),
) -> dict:
    try:
        return apply_config_migration(
            db,
            _get_service(db, service_id),
            artifact_id=str(payload.get("artifact_id") or ""),
            edited_yaml=str(payload.get("edited_yaml") or ""),
            apply_mode=str(payload.get("apply_mode") or "reload"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/config/migration/restore")
def restore_config_migration_endpoint(
    service_id: int,
    payload: dict[str, str],
    db: Session = Depends(get_db),
) -> dict:
    try:
        return restore_config_migration(
            db,
            _get_service(db, service_id),
            artifact_id=str(payload.get("artifact_id") or ""),
            apply_mode=str(payload.get("apply_mode") or "reload"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/capabilities", response_model=ServiceCapabilities)
def get_service_capabilities_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_capabilities(db, service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/metrics", response_model=ServiceMetricsOut)
def get_service_metrics_endpoint(service_id: int, window: str = "1h", db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_metrics(db, service_id, window=window)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/summary", response_model=ServiceSummaryOut)
def get_service_summary_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_summary(db, service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/services/{service_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_service_lifecycle_impact_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "service", service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_node_lifecycle_impact_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "node", node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/clusters/{cluster_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_cluster_lifecycle_impact_endpoint(cluster_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "cluster", cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/subsystems/{subsystem}/rollout-plan", response_model=SubsystemRolloutPlan)
def get_subsystem_rollout_plan_endpoint(node_id: int, subsystem: str, db: Session = Depends(get_db)) -> dict:
    try:
        return get_subsystem_rollout_plan(db, node_id, subsystem)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/nodes/{node_id}/subsystems/{subsystem}/deploy")
def deploy_subsystem_endpoint(node_id: int, subsystem: str, db: Session = Depends(get_db)) -> dict:
    try:
        return deploy_subsystem(db, node_id, subsystem)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/clusters/{cluster_id}/summary", response_model=ClusterSummary)
def get_cluster_summary_endpoint(cluster_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_cluster_summary(db, cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/clusters/{cluster_id}/operations", response_model=ClusterOperationsOut)
def get_cluster_operations_endpoint(cluster_id: int, limit: int = 40, db: Session = Depends(get_db)) -> dict:
    try:
        return get_cluster_operations_view(db, cluster_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/summary", response_model=NodeSummary)
def get_node_summary_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_summary(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/metrics", response_model=NodeMetricsOut)
def get_node_metrics_endpoint(node_id: int, window: str = "1h", db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_metrics(db, node_id, window=window)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/connection", response_model=NodeConnectionOut)
def get_node_connection_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_connection_report(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/jobs", response_model=NodeJobHistoryOut)
def get_node_jobs_endpoint(node_id: int, limit: int = 12, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_job_history(db, node_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/nodes/{node_id}/onboarding-readiness", response_model=NodeOnboardingOut)
def get_node_onboarding_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_onboarding_report(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/nodes/{node_id}/onboarding-remediate", response_model=NodeOnboardingRemediationOut)
def remediate_node_onboarding_endpoint(
    node_id: int,
    payload: NodeOnboardingRemediationRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return remediate_node_onboarding(db, node_id, action=payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/dtrain/overview", response_model=DTrainOverview)
def get_dtrain_overview_endpoint(db: Session = Depends(get_db)) -> dict:
    return get_dtrain_overview(db)


# Serve frontend SPA if dist folder exists
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

dist_path = "/app/dist"
if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=f"{dist_path}/assets"), name="static")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404)
        return FileResponse(f"{dist_path}/index.html")
