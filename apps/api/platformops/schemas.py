from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClusterCreate(BaseModel):
    name: str
    region: str = "local"
    environment: str = "development"


class ClusterUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    environment: str | None = None


class ClusterOut(BaseModel):
    id: int
    name: str
    region: str
    environment: str

    model_config = {"from_attributes": True}


class NodeCreate(BaseModel):
    cluster_id: int
    name: str
    host: str = "localhost"
    ssh_user: str = "ubuntu"
    ssh_key_path: str = ""
    ssh_private_key: str | None = None
    environment: str = "local"
    volume_root: str = "/tmp/platformops"
    docker_network: str = "platformops-net"


class NodeUpdate(BaseModel):
    cluster_id: int | None = None
    name: str | None = None
    host: str | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    ssh_private_key: str | None = None
    environment: str | None = None
    volume_root: str | None = None
    docker_network: str | None = None
    status: str | None = None


class NodeOut(BaseModel):
    id: int
    cluster_id: int
    name: str
    host: str
    ssh_user: str
    ssh_key_path: str
    environment: str
    volume_root: str
    docker_network: str
    status: str
    facts_json: str

    model_config = {"from_attributes": True}


class ServiceCreate(BaseModel):
    node_id: int
    service_key: str
    name: str | None = None
    contract_overrides: dict[str, Any] = Field(default_factory=dict)


class ServiceUpdate(BaseModel):
    name: str | None = None
    contract_overrides: dict[str, Any] = Field(default_factory=dict)


class ServiceOut(BaseModel):
    id: int
    node_id: int
    service_key: str
    name: str
    kind: str
    container_name: str
    image: str
    status: str

    model_config = {"from_attributes": True}


class PreflightOut(BaseModel):
    ok: bool
    missing: list[str] = Field(default_factory=list)
    stopped: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)
    message: str


class DependencyInstallActionOut(BaseModel):
    service_id: int
    service_key: str
    action: str
    job_id: int
    job_status: str
    command: str
    message: str


class DependencyInstallResultOut(BaseModel):
    service_id: int
    service_key: str
    node_id: int
    dependency_actions: list[DependencyInstallActionOut]


class ServiceInstallFieldOut(BaseModel):
    key: str
    label: str
    field_type: str
    required: bool = False
    value: Any = None
    help_text: str = ""
    options: list[str] = Field(default_factory=list)
    section: str = "Configuration"


class ServiceInstallSchemaOut(BaseModel):
    service_key: str
    name: str
    kind: str
    configurable: bool
    exposure_supported: bool
    fields: list[ServiceInstallFieldOut]
    defaults: dict[str, Any]
    preflight: PreflightOut
    summary: str


class JobOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    action: str
    status: str
    command: str
    output: str
    error: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class NodeJobHistoryItemOut(BaseModel):
    id: int
    action: str
    status: str
    command: str
    output: str
    error: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    service_id: int | None = None
    service_name: str | None = None
    service_key: str | None = None


class NodeJobHistoryOut(BaseModel):
    node_id: int
    node_name: str
    total_jobs: int
    deployment_jobs: int
    config_jobs: int
    validation_jobs: int
    failed_jobs: int
    items: list[NodeJobHistoryItemOut]


class ConfigApply(BaseModel):
    content: str
    apply_mode: str = "reload"


class ConfigSnapshotCreate(BaseModel):
    name: str | None = None
    source: str = "manual"
    requested_by: str = "platform-operator"


class ConfigSnapshotRename(BaseModel):
    name: str
    requested_by: str = "platform-operator"


class ConfigValidateOut(BaseModel):
    ok: bool
    message: str


class ConfigSnapshotOut(BaseModel):
    id: int
    service_id: int
    version: int
    name: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfigSnapshotDetailOut(ConfigSnapshotOut):
    content: str


class ConfigSnapshotDiffItemOut(BaseModel):
    field: str
    expected: Any
    actual: Any
    severity: str


class ConfigSnapshotCompareOut(BaseModel):
    service_id: int
    left_snapshot: ConfigSnapshotDetailOut
    right_snapshot: ConfigSnapshotDetailOut
    differences: list[ConfigSnapshotDiffItemOut]
    difference_count: int
    summary: str


class ConfigSnapshotPageOut(BaseModel):
    service_id: int
    total: int
    limit: int
    offset: int
    has_more: bool
    source_filter: str
    search: str
    items: list[ConfigSnapshotOut]


class ConfigWorkspaceOut(BaseModel):
    service_id: int
    content: str
    content_source: str = "live"
    message: str = ""
    snapshots: list[ConfigSnapshotOut]
    snapshot_count: int = 0
    active_checkpoint: ConfigSnapshotOut | None = None
    drift_state: str = "unknown"
    config_source_label: str = "Live contract"
    config_path: str = ""
    file_label: str = ""
    config_capabilities: dict[str, Any] = Field(default_factory=dict)
    runtime_target: dict[str, Any] = Field(default_factory=dict)
    peers: list[dict[str, Any]] = Field(default_factory=list)


class ConfigTimelineEventOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    level: str
    message: str
    action: str
    actor: str
    metadata: dict[str, Any]
    created_at: str


class ConfigTimelinePageOut(BaseModel):
    service_id: int
    total: int
    limit: int
    offset: int
    has_more: bool
    action_filter: str
    actor_filter: str
    search: str
    created_after: str
    created_before: str
    available_actions: list[str]
    available_actors: list[str]
    items: list[ConfigTimelineEventOut]


class DiagnosticsOut(BaseModel):
    service_id: int
    source_service_id: int
    source_service_key: str
    target_service_key: str
    target: str
    status: str
    log_paths: list[str]
    recent_logs: list[dict[str, Any]]
    readiness: dict[str, Any]


class DiagnosticsTargetOut(BaseModel):
    service_id: int | None
    service_key: str
    name: str
    kind: str
    target_type: str
    container_name: str
    status: str
    ready: bool
    on_node: bool


class DiagnosticsLogLineOut(BaseModel):
    timestamp: str
    level: str
    message: str
    source: str


class DiagnosticsLiveOut(BaseModel):
    service_id: int
    target: str
    source_state: str
    poll_interval_ms: int
    tail_lines: int
    page_size: int
    cursor: int
    next_cursor: int
    total_available: int
    has_more_history: bool
    lines: list[DiagnosticsLogLineOut]
    generated_at: str


class DiagnosticsInsightActionOut(BaseModel):
    action_id: str
    label: str
    description: str
    service_key: str | None = None
    incident_id: int | None = None
    runbook_key: str | None = None
    target_view: str
    recommended: bool = False


class DiagnosticsInsightEvidenceOut(BaseModel):
    evidence_id: str
    label: str
    summary: str
    target_view: str
    severity: str = "info"
    service_key: str | None = None
    incident_id: int | None = None
    compare_left_snapshot_id: int | None = None
    compare_right_snapshot_id: int | None = None
    baseline_snapshot_id: int | None = None


class DiagnosticsInsightOut(BaseModel):
    insight_id: str
    title: str
    severity: str
    confidence: int
    summary: str
    rationale: str
    evidence_refs: list[str]
    supporting_evidence: list[DiagnosticsInsightEvidenceOut]
    actions: list[DiagnosticsInsightActionOut]


class DiagnosticsAnalysisOut(BaseModel):
    service_id: int
    service_name: str
    source_service_id: int
    source_service_name: str
    source_service_key: str
    target_service_key: str
    target_name: str
    overall_severity: str
    overview: str
    next_steps: list[str]
    generated_at: str
    recent_incidents: list[dict[str, Any]]
    historical_correlation: list[str]
    change_evidence: list[dict[str, Any]]
    insights: list[DiagnosticsInsightOut]


class OperationalEventOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    category: str
    level: str
    message: str
    metadata_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRunOut(BaseModel):
    id: int
    service_id: int
    status: str
    strategy: str
    artifact_path: str
    output: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class MonitoringCheckOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    name: str
    status: str
    value: str
    detail: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TopologyOut(BaseModel):
    nodes: list[dict[str, Any]]
    services: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    subsystems: dict[str, list[str]]


class DeploymentPlanOut(BaseModel):
    node_id: int
    service_key: str
    ok: bool
    summary: str
    steps: list[dict[str, Any]]
    blocked_by: list[str]


class DeploymentExecuteIn(BaseModel):
    auto_install_dependencies: bool = True


class DeploymentExecuteOut(BaseModel):
    service_id: int
    service_key: str
    node_id: int
    auto_install_dependencies: bool
    ok: bool
    summary: str
    plan: DeploymentPlanOut
    preflight_before: PreflightOut
    preflight_after: PreflightOut
    dependency_actions: list[DependencyInstallActionOut]
    target_job: JobOut | None = None


class GeneratedArtifactOut(BaseModel):
    name: str
    content_type: str
    content: str


class LogArchiveOut(BaseModel):
    id: int
    service_id: int
    path: str
    size_bytes: int
    line_count: int
    readable: str
    reason: str
    discovered_at: datetime

    model_config = {"from_attributes": True}


class ReleaseCreate(BaseModel):
    version: str
    image: str | None = None
    strategy: str = "rolling"
    notes: str = ""
    approval_id: int | None = None


class ReleaseRecordOut(BaseModel):
    id: int
    service_id: int
    version: str
    image: str
    status: str
    strategy: str
    notes: str
    previous_image: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DriftReportOut(BaseModel):
    id: int
    service_id: int
    status: str
    baseline_snapshot_id: int | None
    differences_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyFindingOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    rule_id: str
    severity: str
    status: str
    message: str
    remediation: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    service_id: int | None = None
    node_id: int | None = None
    title: str
    severity: str = "sev3"
    summary: str = ""


class IncidentRecordOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    title: str
    severity: str
    status: str
    summary: str
    remediation: str
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class RunbookExecutionOut(BaseModel):
    id: int
    incident_id: int | None
    service_id: int | None
    node_id: int | None
    runbook_key: str
    status: str
    steps_json: str
    output: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SloReportOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    name: str
    target: str
    observed: str
    status: str
    detail: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CapacityReportOut(BaseModel):
    id: int
    node_id: int
    status: str
    cpu_reserved: str
    memory_reserved_mb: int
    storage_reserved_gb: int
    detail_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricSeriesPointOut(BaseModel):
    label: str
    value: float


class NodeMetricsOut(BaseModel):
    node_id: int
    node_name: str
    window: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_rx_mbps: float
    network_tx_mbps: float
    cpu_series: list[MetricSeriesPointOut]
    memory_series: list[MetricSeriesPointOut]
    disk_series: list[MetricSeriesPointOut]


class ServiceMetricsOut(BaseModel):
    service_id: int
    service_name: str
    service_key: str
    node_id: int
    window: str
    cpu_percent: float
    memory_mb: float
    log_error_rate: float
    queue_depth: int
    restart_count: int
    latency_ms_p95: float
    cpu_series: list[MetricSeriesPointOut]
    error_rate_series: list[MetricSeriesPointOut]
    queue_depth_series: list[MetricSeriesPointOut]


class ServiceSummaryOut(BaseModel):
    service_id: int
    node_id: int
    service_key: str
    name: str
    kind: str
    subsystem: str
    status: str
    container_name: str
    image: str
    dependency: PreflightOut
    capabilities: ServiceCapabilities
    latest_job: JobOut | None
    latest_backup: BackupRunOut | None
    latest_release: ReleaseRecordOut | None
    latest_drift: DriftReportOut | None
    latest_monitoring: MonitoringCheckOut | None
    latest_slo: SloReportOut | None
    latest_runbook: RunbookExecutionOut | None
    active_incidents: list[IncidentRecordOut]
    snapshot_count: int
    recent_event_count: int
    recent_events: list[OperationalEventOut]


class ServiceReleaseTimelineItemOut(BaseModel):
    release: ReleaseRecordOut
    rollback_executed: bool
    notes: list[str]
    related_events: list[OperationalEventOut]


class ServiceReleaseTimelineOut(BaseModel):
    service_id: int
    service_name: str
    current_image: str
    current_status: str
    rollback_available: bool
    latest_rollback_job: JobOut | None
    items: list[ServiceReleaseTimelineItemOut]
    recent_change_events: list[OperationalEventOut]


class DashboardAttentionServiceOut(BaseModel):
    service_id: int
    service_name: str
    service_key: str
    node_id: int
    node_name: str
    cluster_id: int
    cluster_name: str
    status: str
    severity: str
    reasons: list[str]


class DashboardObservabilityNodeOut(BaseModel):
    node_id: int
    node_name: str
    cluster_name: str
    pipeline_ready: bool
    ingestion_state: str
    last_signal_at: str | None
    issues: list[str]


class DashboardSummaryOut(BaseModel):
    clusters: int
    nodes: int
    services: int
    running_services: int
    open_incidents: int
    burning_slos: int
    healthy_observability_nodes: int
    degraded_observability_nodes: int
    blocked_services: int
    attention_services: list[DashboardAttentionServiceOut]
    active_incidents: list[IncidentRecordOut]
    degraded_observability: list[DashboardObservabilityNodeOut]


class ClusterOperationItemOut(BaseModel):
    id: int
    category: str
    level: str
    message: str
    created_at: str
    service_id: int | None
    service_name: str | None
    service_key: str | None
    node_id: int | None
    node_name: str | None
    action_family: str


class ClusterOperationsOut(BaseModel):
    cluster_id: int
    cluster_name: str
    total_events: int
    change_events: int
    recovery_events: int
    governance_events: int
    active_incidents: int
    items: list[ClusterOperationItemOut]


class ReleaseSafetyOut(BaseModel):
    service_id: int
    service_name: str
    risky: bool
    severity: str
    reasons: list[str]
    recommended_action: str


class ReleaseApprovalCreate(BaseModel):
    service_id: int
    target_version: str
    target_image: str
    reason: str
    requested_by: str = "platform-operator"
    ttl_hours: int = 4


class ReleaseApprovalDecision(BaseModel):
    approver: str
    decision_note: str = ""
    status: str = "approved"


class ReleaseApprovalRevoke(BaseModel):
    actor: str
    note: str = ""


class ReleaseApprovalOut(BaseModel):
    id: int
    service_id: int
    target_version: str
    target_image: str
    reason: str
    requested_by: str
    status: str
    approver: str
    decision_note: str
    created_at: datetime
    approved_at: datetime | None
    expires_at: datetime | None
    used_at: datetime | None

    model_config = {"from_attributes": True}


class SecretCreate(BaseModel):
    service_id: int | None = None
    node_id: int | None = None
    key: str
    scope: str = "service"
    rotation_interval_days: int = 90


class SecretRecordOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    key: str
    masked_value: str
    scope: str
    status: str
    rotation_interval_days: int
    created_at: datetime
    rotated_at: datetime | None

    model_config = {"from_attributes": True}


class MaintenanceWindowCreate(BaseModel):
    service_id: int | None = None
    node_id: int | None = None
    title: str
    starts_at: str
    ends_at: str
    impact: str = ""


class MaintenanceWindowOut(BaseModel):
    id: int
    service_id: int | None
    node_id: int | None
    title: str
    status: str
    starts_at: str
    ends_at: str
    impact: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditExportOut(BaseModel):
    id: int
    export_type: str
    status: str
    artifact_path: str
    content_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LifecycleImpact(BaseModel):
    target_type: str
    target_id: int
    target_name: str
    severity: str
    can_delete_without_force: bool
    dependents: list[str]
    active_children: list[str]
    warnings: list[str]
    recommended_action: str


class SubsystemRolloutPlan(BaseModel):
    node_id: int
    subsystem: str
    ok: bool
    summary: str
    steps: list[dict[str, Any]]
    blocked_by: list[str]


class ServiceCapabilities(BaseModel):
    service_id: int
    service_key: str
    kind: str
    container_name: str
    diagnostics: bool
    config: bool
    backup: bool
    requires_sudo_for_file_logs: bool


class ClusterSummary(BaseModel):
    cluster_id: int
    node_count: int
    service_count: int
    healthy_count: int
    warning_count: int
    error_count: int


class NodeSummary(BaseModel):
    node_id: int
    service_count: int
    kind_counts: dict[str, int]
    docker_network: str
    volume_root: str
    capacity_status: str


class NodeValidationJobOut(BaseModel):
    id: int
    status: str
    created_at: str
    ended_at: str | None
    error: str
    output: str
    command: str


class NodeConnectionOut(BaseModel):
    node_id: int
    node_name: str
    host: str
    ssh_user: str
    ssh_key_path: str
    environment: str
    status: str
    connection_state: str
    facts_available: bool
    facts: dict[str, Any]
    facts_error: str | None
    last_checked_at: str | None
    validation_job: NodeValidationJobOut | None
    recommendations: list[str]


class NodeOnboardingCheckOut(BaseModel):
    check_id: str
    title: str
    status: str
    severity: str
    detail: str
    remediation: str


class NodeOnboardingOut(BaseModel):
    node_id: int
    node_name: str
    environment: str
    overall_status: str
    checked_at: str
    connection_state: str
    pass_count: int
    warn_count: int
    fail_count: int
    checks: list[NodeOnboardingCheckOut]
    next_actions: list[str]
    suggested_actions: list[str]


class NodeOnboardingRemediationRequest(BaseModel):
    action: str


class NodeOnboardingRemediationOut(BaseModel):
    node_id: int
    action: str
    ok: bool
    message: str
    updated_fields: dict[str, str]
    validation_job: NodeValidationJobOut | None


class DTrainOverview(BaseModel):
    tracker: dict[str, Any]
    controller: dict[str, Any]
    workers: list[dict[str, Any]]
    dependencies: dict[str, Any]
    metrics: dict[str, Any]
    rollout_ready: bool


class CapabilityCoverageItem(BaseModel):
    service_key: str
    kind: str
    subsystem: str
    diagnostics_ready: bool
    config_ready: bool
    config_mode: str
    backup_ready: bool
    stateful: bool
    requires_sudo_for_file_logs: bool
    issues: list[str]


class CapabilityCoverageOut(BaseModel):
    total_services: int
    diagnostics_ready: int
    config_ready: int
    backup_ready: int
    policy_risk_services: int
    issues_count: int
    items: list[CapabilityCoverageItem]


class LifecycleAuditOut(BaseModel):
    window_hours: int
    total_lifecycle_events: int
    blocked_deletions: int
    forced_deletions: int
    safe_deletions: int
    last_blocked_at: str | None
    last_forced_at: str | None
    last_safe_delete_at: str | None


class ForceDeleteApprovalCreate(BaseModel):
    target_type: str
    target_id: int
    reason: str
    requested_by: str = "platform-operator"
    ttl_hours: int = 4


class ForceDeleteApprovalDecision(BaseModel):
    approver: str
    decision_note: str = ""
    status: str = "approved"


class ForceDeleteApprovalRevoke(BaseModel):
    actor: str
    note: str = ""


class ForceDeleteApprovalOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    reason: str
    requested_by: str
    status: str
    approver: str
    decision_note: str
    created_at: datetime
    approved_at: datetime | None
    expires_at: datetime | None
    used_at: datetime | None

    model_config = {"from_attributes": True}


class PlacementCandidateOut(BaseModel):
    node_id: int
    node_name: str
    node_status: str
    score: int
    recommendation: str
    dependency_ready: bool
    dependency_missing: list[str]
    dependency_stopped: list[str]
    capacity_status: str
    projected_memory_mb: int
    projected_storage_gb: int
    projected_cpu: float
    notes: list[str]


class PlacementRecommendationOut(BaseModel):
    service_key: str
    generated_at: str
    prefer_node_id: int | None = None
    avoid_node_ids: list[int] = Field(default_factory=list)
    anti_affinity_service_key: str | None = None
    require_healthy: bool = False
    spread_subsystem: bool = False
    candidates: list[PlacementCandidateOut]


class ObservabilityNodePipelineOut(BaseModel):
    node_id: int
    node_name: str
    node_status: str
    pipeline_ready: bool
    ingestion_state: str
    last_signal_at: str | None
    components: dict[str, str]
    issues: list[str]


class ObservabilityPipelineOut(BaseModel):
    generated_at: str
    defaults: dict[str, Any]
    labels: dict[str, Any]
    sources: dict[str, Any]
    nodes: list[ObservabilityNodePipelineOut]
    summary: dict[str, int]


class ObservabilityBootstrapOut(BaseModel):
    node_id: int
    subsystem: str
    ok: bool
    summary: str
    jobs: list[dict[str, Any]]
    pipeline_ready: bool
    ingestion_state: str


class PlacementDeploymentActionOut(BaseModel):
    service_id: int
    service_key: str
    action: str
    job_id: int
    job_status: str
    message: str


class PlacementDeployOut(BaseModel):
    service_key: str
    node_id: int
    node_name: str
    generated_at: str
    selected_candidate: PlacementCandidateOut
    auto_install_dependencies: bool
    allow_capacity_risk: bool
    created_target: bool
    target_service_id: int
    target_service_status: str
    target_job_id: int
    target_job_status: str
    dependency_actions: list[PlacementDeploymentActionOut]
    preflight: PreflightOut
    summary: str
