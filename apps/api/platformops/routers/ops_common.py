from __future__ import annotations

import json
from typing import Any

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..settings import settings
from ..models import (
    AuthSession,
    AuditExport,
    BackupRun,
    CapacityReport,
    Cluster,
    ConfigSnapshot,
    DeploymentJob,
    DriftReport,
    ForceDeleteApproval,
    IncidentRecord,
    InviteToken,
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
    UserInfo,
)
from ..orchestrator import (
    apply_config,
    apply_config_direct,
    apply_config_migration,
    add_monitoring_uptime_check,
    assess_release_safety,
    backfill_service_logs,
    bootstrap_observability_plane,
    bulk_download_log_archives,
    capability_coverage_report,
    catalog_cards,
    check_port_and_name_availability,
    compare_config_snapshots,
    config_capabilities_for_service,
    complete_maintenance,
    create_audit_export,
    create_config_snapshot,
    create_force_delete_approval,
    create_incident,
    create_release,
    create_release_approval,
    create_secret_record,
    create_service_instance,
    detach_resource_references,
    decide_force_delete_approval,
    decide_release_approval,
    delete_monitoring_uptime_check,
    delete_service,
    download_log_archive,
    dependency_preflight,
    deploy_observability_stack,
    deploy_service,
    deploy_subsystem,
    deployment_plan,
    detect_drift,
    diagnostics_targets_for_service,
    discover_infrastructure,
    evaluate_force_delete_policy,
    evaluate_slos,
    execute_monitoring_issue_action,
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
    get_ingestion_stats,
    get_monitoring_integration_status,
    get_monitoring_issue_event_details,
    get_monitoring_keys,
    get_monitoring_performance,
    get_monitoring_uptime_list,
    get_node_connection_report,
    probe_node_connection,
    get_node_job_history,
    get_node_onboarding_report,
    get_node_summary,
    cleanup_node_inventory,
    get_node_services_live_status,
    get_service_capabilities,
    get_service_live_status,
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
    launch_node_vm,
    lifecycle_audit_report,
    lifecycle_impact,
    list_config_snapshots_page,
    list_events,
    list_releases,
    mark_force_delete_approval_used,
    observability_pipeline_report,
    observability_status_report,
    placement_auto_deploy,
    placement_recommendations,
    patch_service_runtime_observability,
    query_monitoring_issues,
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
    service_container_history,
    service_file_history,
    service_file_tail,
    service_install_schema,
    service_live_logs,
    service_log_analytics_chat,
    sync_peer_config,
    teardown_node_vm,
    test_git_connection,
    test_registry_connection,
    topology,
    update_service_instance,
    validate_config,
    validate_force_delete_approval,
    validate_node,
    view_log_archive,
)
from ..orchestrator import (
    config_workspace as build_config_workspace,
)
from ..orchestrator.config import prepare_config_runtime_target
from ..orchestrator import (
    get_node_metrics as orchestrator_get_node_metrics,
)
from ..schemas import (
    AuditExportOut,
    BackupRunOut,
    CapabilityCoverageOut,
    CapacityReportOut,
    ClusterCreate,
    ClusterOperationsOut,
    ClusterOut,
    ClusterSummary,
    ClusterUpdate,
    TestGitRepoRequest,
    TestRegistryRequest,
    ConfigApply,
    ConfigDirectApplyOut,
    ConfigMigrationApplyOut,
    ConfigMigrationApplyRequest,
    ConfigMigrationPrepareOut,
    ConfigMigrationPrepareRequest,
    ConfigMigrationRestoreRequest,
    ConfigSnapshotCompareOut,
    ConfigSnapshotCreate,
    ConfigSnapshotDetailOut,
    ConfigSnapshotOut,
    ConfigSnapshotPageOut,
    ConfigSnapshotRename,
    ConfigSnapshotRestore,
    ConfigSyncPeer,
    ConfigSyncPeerOut,
    ConfigTimelinePageOut,
    ConfigValidateOut,
    ConfigWorkspaceOut,
    DashboardSummaryOut,
    DependencyInstallResultOut,
    DeploymentExecuteIn,
    DeploymentExecuteOut,
    DeploymentPlanOut,
    DiagnosticsAnalysisOut,
    DiagnosticsChatOut,
    DiagnosticsChatRequest,
    InviteAcceptRequest,
    LastVisitedUpdate,
    LoginOut,
    LoginRequest,
    UserCreate,
    UserInviteCreate,
    UserInviteResend,
    UserInviteRevoke,
    UserOut,
    UserUpdate,
    DiagnosticsFileHistoryOut,
    DiagnosticsFileTailOut,
    DiagnosticsLiveOut,
    DiagnosticsOut,
    DiagnosticsTargetOut,
    IngestionStatsOut,
    LogArchiveBulkDownloadOut,
    LogArchiveBulkDownloadRequest,
    LogArchiveDownloadOut,
    LogArchiveViewOut,
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
    NodeConnectionProbeRequest,
    NodeConnectionProbeOut,
    NodeInventoryCleanupIn,
    NodeInventoryCleanupOut,
    NodeCreate,
    NodeLaunchRequest,
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
    ObservabilityStatusOut,
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
    ServiceLiveStatusOut,
    NodeServicesLiveStatusOut,
    ServiceReleaseTimelineOut,
    ServiceSummaryOut,
    ServiceUpdate,
    SloReportOut,
    SubsystemRolloutPlan,
    TopologyOut,
)


# Shared helpers for domain routers


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




def _mask_cluster(cluster: Cluster) -> ClusterOut:
    """Build a response-safe cluster without mutating the ORM identity."""

    return ClusterOut.model_validate(cluster)
