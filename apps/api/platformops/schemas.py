from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .security import redact_json_string, redact_secrets


class ClusterCreate(BaseModel):
    name: str
    region: str = "local"
    environment: str = "development"
    description: str = ""
    cluster_type: str = "standalone"
    # ``type`` is the field name used by the cPlatform editor.  Keep it as an
    # input alias while storing the canonical value in ``cluster_type``.
    type: str | None = None
    variant: str = ""
    role: str = ""
    repo_type: str = "github"
    repo_url: str = ""
    repo_branch: str = "main"
    repo_token: str = ""
    repo_path: str = ""
    repo_auth: str = "pat"
    registry_type: str = "dockerhub"
    registry_url: str = ""
    registry_user: str = ""
    registry_password: str = ""
    registry_namespace: str = ""
    registry_auth: str = "password"
    image_store: str = ""


class TestGitRepoRequest(BaseModel):
    repo_type: str = "github"
    repo_url: str = ""
    repo_branch: str = "main"
    repo_token: str | None = None


class TestRegistryRequest(BaseModel):
    registry_type: str = "dockerhub"
    registry_url: str = ""
    registry_user: str | None = None
    registry_password: str | None = None


class NodeLaunchRequest(BaseModel):
    ami_id: str
    instance_type: str
    region: str


class ClusterUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    environment: str | None = None
    description: str | None = None
    cluster_type: str | None = None
    type: str | None = None
    variant: str | None = None
    role: str | None = None
    repo_type: str | None = None
    repo_url: str | None = None
    repo_branch: str | None = None
    repo_token: str | None = None
    repo_path: str | None = None
    repo_auth: str | None = None
    registry_type: str | None = None
    registry_url: str | None = None
    registry_user: str | None = None
    registry_password: str | None = None
    registry_namespace: str | None = None
    registry_auth: str | None = None
    image_store: str | None = None


class ClusterOut(BaseModel):
    id: int
    name: str
    region: str
    environment: str
    description: str = ""
    cluster_type: str = "standalone"
    type: str = "standalone"
    variant: str = ""
    role: str = ""
    repo_type: str
    repo_url: str
    repo_branch: str
    repo_token: str  # Kept masked in output representation
    repo_path: str = ""
    repo_auth: str = "pat"
    registry_type: str
    registry_url: str
    registry_user: str
    registry_password: str  # Kept masked in output representation
    registry_namespace: str = ""
    registry_auth: str = "password"
    image_store: str = ""

    @field_validator("repo_token", "registry_password", mode="before")
    @classmethod
    def _mask_credentials(cls, value: Any) -> str:
        return "***" if value else ""

    @model_validator(mode="after")
    def _sync_type_alias(self):
        if not self.cluster_type and self.type:
            self.cluster_type = self.type
        self.type = self.cluster_type or self.type or "standalone"
        return self

    model_config = {"from_attributes": True}


class NodeCreate(BaseModel):
    cluster_id: int
    name: str
    host: str = "localhost"
    ssh_user: str = "ubuntu"
    # ``ssh_private_key``/``ssh_password`` are request-scoped only.  They are
    # accepted for one-shot onboarding and must never be persisted by a route.
    ssh_key_path: str = ""
    ssh_private_key: str | None = None
    ssh_password: str | None = None
    ssh_secret_ref: str = ""
    secret_ref: str = ""
    host_key_fingerprint: str = ""
    ssh_host_key_fingerprint: str = ""
    known_hosts_ref: str = ""
    ssh_known_hosts_ref: str = ""
    environment: str = "local"
    provider: str = "dc"
    region: str = "local"
    availability_zone: str = ""
    az: str | None = None
    auth_mode: str = "ssh_key"
    monitor_port: int = 9100
    monitoring_port: int | None = None
    ingress_ports: str | list[int] | list[str] = ""
    cloud_id: str = ""
    cloud_instance_id: str = ""
    cloud_resource_id: str = ""
    cloud_account_id: str = ""
    cloud_image_id: str = ""
    instance_id: str | None = None
    resource_id: str | None = None
    ami_id: str | None = None
    volume_root: str = "/tmp/platformops"
    docker_network: str = "platformops_prod_network"
    facts: dict[str, Any] = Field(default_factory=dict)


class NodeUpdate(BaseModel):
    cluster_id: int | None = None
    name: str | None = None
    host: str | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    ssh_private_key: str | None = None
    ssh_password: str | None = None
    ssh_secret_ref: str | None = None
    secret_ref: str | None = None
    host_key_fingerprint: str | None = None
    ssh_host_key_fingerprint: str | None = None
    known_hosts_ref: str | None = None
    ssh_known_hosts_ref: str | None = None
    environment: str | None = None
    provider: str | None = None
    region: str | None = None
    availability_zone: str | None = None
    az: str | None = None
    auth_mode: str | None = None
    monitor_port: int | None = None
    monitoring_port: int | None = None
    ingress_ports: str | list[int] | list[str] | None = None
    cloud_id: str | None = None
    cloud_instance_id: str | None = None
    cloud_resource_id: str | None = None
    cloud_account_id: str | None = None
    cloud_image_id: str | None = None
    instance_id: str | None = None
    resource_id: str | None = None
    ami_id: str | None = None
    volume_root: str | None = None
    docker_network: str | None = None
    status: str | None = None
    facts: dict[str, Any] | None = None


class NodeOut(BaseModel):
    id: int
    cluster_id: int
    name: str
    host: str
    ssh_user: str
    ssh_key_path: str
    ssh_secret_ref: str = ""
    host_key_fingerprint: str = ""
    known_hosts_ref: str = ""
    environment: str
    provider: str = "dc"
    region: str = "local"
    availability_zone: str = ""
    auth_mode: str = "ssh_key"
    monitor_port: int = 9100
    ingress_ports: str = ""
    cloud_id: str = ""
    cloud_instance_id: str = ""
    cloud_resource_id: str = ""
    cloud_account_id: str = ""
    cloud_image_id: str = ""
    volume_root: str
    docker_network: str
    status: str
    facts_json: str

    @field_validator("facts_json", mode="before")
    @classmethod
    def _mask_facts(cls, value: Any) -> str:
        import json

        if isinstance(value, str):
            return redact_json_string(value)
        return json.dumps(redact_secrets(value if isinstance(value, dict) else {}), separators=(",", ":"))

    model_config = {"from_attributes": True}


class ServiceCreate(BaseModel):
    node_id: int
    service_key: str
    name: str | None = None
    contract_overrides: dict[str, Any] = Field(default_factory=dict)
    install_mode: str | None = None  # manual | ansible


class ServiceUpdate(BaseModel):
    name: str | None = None
    contract_overrides: dict[str, Any] = Field(default_factory=dict)
    install_mode: str | None = None  # manual | ansible


class ServiceOut(BaseModel):
    id: int
    external_id: str = ""
    node_id: int
    service_key: str
    name: str
    kind: str
    container_name: str
    image: str
    status: str
    install_mode: str = "ansible"
    # Contract highlights for cluster UI (expose / adopt) — derived from config_json
    expose_service: bool = False
    host_port: str | int | None = None
    adopted: bool = False

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _derive_contract_flags(cls, values, handler):
        # Accept ORM ServiceInstance or dict
        raw = values
        data = handler(values)
        cfg_raw = ""
        if hasattr(raw, "config_json"):
            cfg_raw = getattr(raw, "config_json", "") or ""
        elif isinstance(raw, dict):
            cfg_raw = raw.get("config_json") or ""
        try:
            import json

            cfg = json.loads(cfg_raw) if cfg_raw else {}
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}
        object.__setattr__(data, "expose_service", bool(cfg.get("expose_service")))
        object.__setattr__(data, "host_port", cfg.get("host_port"))
        object.__setattr__(data, "adopted", bool(cfg.get("adopted")))
        raw_mode = cfg.get("install_mode") or cfg.get("service_install") or "ansible"
        mode = str(raw_mode).strip().lower()
        object.__setattr__(data, "install_mode", "manual" if mode.startswith("manual") else "ansible")
        return data


class ServiceLiveStatusOut(BaseModel):
    service_id: int
    external_id: str = ""
    service_key: str
    name: str
    container_name: str
    image: str = ""
    db_status: str = ""
    overall_status: str
    running: bool = False
    state: str = ""
    restart_count: int | None = None
    started_at: str | None = None
    exit_code: int | None = None
    oom_killed: bool = False
    error: str | None = None
    checked_at: str = ""
    source: str = "docker_inspect"
    connection_mode: str = "unknown"
    host: str = ""
    stale: bool = False
    cache_hit: bool = False


class NodeServicesLiveStatusOut(BaseModel):
    node_id: int
    count: int
    running_count: int
    items: list[ServiceLiveStatusOut]
    checked_at: str = ""
    source: str = "docker_inspect"
    connection_mode: str = "unknown"
    host: str = ""


class NodeInventoryCleanupIn(BaseModel):
    modes: list[str] = Field(default_factory=lambda: ["all"])
    dry_run: bool = True
    protect_orchestrator: bool = True


class NodeInventoryCleanupOut(BaseModel):
    node_id: int
    dry_run: bool
    modes: list[str]
    candidate_count: int
    removed_count: int
    items: list[dict[str, Any]]
    summary: str


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
    preflight: Optional[PreflightOut] = None
    summary: Optional[str] = None


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


class DiagnosticsBackfillJobOut(BaseModel):
    """Safe, pollable projection of a diagnostics backfill job.

    The general job response includes its executable command.  A diagnostics
    submission must not echo that command because it contains encoded source
    labels and runtime paths, so this projection deliberately exposes only
    lifecycle and result fields.
    """

    id: int
    service_id: int | None = None
    node_id: int | None = None
    type: str
    status: str
    output: str = ""
    error: str = ""
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None


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
    requested_by: str = "platform-operator"
    expected_content_hash: str = ""

    @field_validator("apply_mode")
    @classmethod
    def validate_apply_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"reload", "restart"}:
            raise ValueError("apply_mode must be 'reload' or 'restart'")
        return normalized


class ConfigSyncPeer(BaseModel):
    peer_id: int
    apply_mode: str = "reload"
    requested_by: str = "platform-operator"


class ConfigSnapshotCreate(BaseModel):
    name: str | None = None
    source: str = "manual"
    requested_by: str = "platform-operator"


class ConfigSnapshotRename(BaseModel):
    name: str
    requested_by: str = "platform-operator"
    expected_version: int | None = None


class ConfigSnapshotRestore(BaseModel):
    expected_content_hash: str = ""
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
    content_hash: str = ""

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
    content_hash: str = ""
    live_content_hash: str = ""
    config_format: str = "yaml"
    live_read_ok: bool = False
    live_read_error: str = ""
    config_capabilities: dict[str, Any] = Field(default_factory=dict)
    runtime_target: dict[str, Any] = Field(default_factory=dict)
    peers: list[dict[str, Any]] = Field(default_factory=list)
    target_identity: dict[str, Any] = Field(default_factory=dict)
    source_state: dict[str, Any] = Field(default_factory=dict)


class ConfigDirectApplyOut(BaseModel):
    job: JobOut
    before_snapshot: ConfigSnapshotOut
    after_snapshot: ConfigSnapshotOut | None = None
    requested_apply_mode: str = ""
    effective_apply_mode: str = ""
    target_identity: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""


class ConfigMigrationPrepareRequest(BaseModel):
    left_snapshot_id: int
    right_snapshot_id: int


class ConfigMigrationPrepareOut(BaseModel):
    artifact_id: str
    left_snapshot: ConfigSnapshotDetailOut
    right_snapshot: ConfigSnapshotDetailOut
    differences: list[ConfigSnapshotDiffItemOut]
    final_yaml: str
    final_content: str
    validation: ConfigValidateOut
    summary: str
    selected_configs: dict[str, Any] = Field(default_factory=dict)
    ranked_configs: dict[str, Any] = Field(default_factory=dict)
    config_rank_1: dict[str, Any] = Field(default_factory=dict)
    config_rank_2: dict[str, Any] = Field(default_factory=dict)
    migration_ops: list[dict[str, Any]] = Field(default_factory=list)
    migrated_config: dict[str, Any] = Field(default_factory=dict)
    final_merged_config: dict[str, Any] = Field(default_factory=dict)
    migration_artifact: dict[str, Any] = Field(default_factory=dict)


class ConfigMigrationApplyRequest(BaseModel):
    artifact_id: str
    edited_yaml: str = ""
    apply_mode: str = "reload"
    expected_content_hash: str = ""


class ConfigMigrationRestoreRequest(BaseModel):
    artifact_id: str
    apply_mode: str = "reload"
    expected_content_hash: str = ""


class ConfigMigrationApplyOut(BaseModel):
    artifact_id: str
    service_id: int
    job: JobOut
    backup_snapshot_id: int
    resolved_config_path: str = ""
    apply_mode: str | None = None
    applied_content: str
    requested_apply_mode: str | None = None
    effective_apply_mode: str | None = None
    target_identity: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""


class ConfigPeerSnapshotOut(BaseModel):
    id: int
    name: str
    version: int

    model_config = {"from_attributes": True}


class ConfigSyncPeerOut(BaseModel):
    source_service_id: int
    peer_service_id: int
    job: JobOut
    before_snapshot: ConfigPeerSnapshotOut
    after_snapshot: ConfigPeerSnapshotOut | None = None
    source_content_hash: str = ""
    target_identity: dict[str, Any] = Field(default_factory=dict)
    parity_status: str = "native-only-disabled"


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
    connection_mode: str = "unknown"
    error: str | None = None
    start: str | None = None
    end: str | None = None


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

    @field_validator("metadata_json", mode="before")
    @classmethod
    def _mask_metadata(cls, value: Any) -> str:
        return redact_json_string(value if isinstance(value, str) else "{}")

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


# Compatibility Monitoring / GlitchTip contracts.  Legacy fields remain
# available, while ``availability`` and ``source`` prevent an empty response
# from being mistaken for a healthy integration.
class MonitoringServiceRequest(BaseModel):
    service_name: str = Field(min_length=1)
    window: str = "24h"


class MonitoringIssuesRequest(MonitoringServiceRequest):
    cursor: str | None = None


class MonitoringIssueEventRequest(BaseModel):
    issue_id: str = Field(min_length=1)


class MonitoringIssueActionRequest(MonitoringIssueEventRequest):
    action: str = Field(min_length=1)


class MonitoringUptimeAddRequest(MonitoringServiceRequest):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    monitor_type: str = "Ping"
    interval: int = Field(default=60, ge=1, le=86400)
    expected_status: int = Field(default=200, ge=100, le=599)
    timeout: int = Field(default=10, ge=1, le=120)
    expected_body: str = ""


class MonitoringUptimeDeleteRequest(BaseModel):
    monitor_id: str = Field(min_length=1)


class MonitoringPatchRequest(BaseModel):
    service_id: int = Field(gt=0)


class IntegrationStatusOut(BaseModel):
    success: bool = True
    configured: bool = False
    reachable: bool = False
    availability: str = "unavailable"
    status: str = "unavailable"
    base_url: str = ""
    org: str = ""
    error: str | None = None
    checked_at: str | None = None


class MonitoringEnvelopeOut(BaseModel):
    success: bool
    availability: str = "unavailable"
    source: str = "glitchtip"
    checked_at: str | None = None
    error: str | None = None


class MonitoringHealthOut(MonitoringEnvelopeOut):
    health: str = "unavailable"
    running: bool | None = None
    container_state: str | None = None
    issue_count: int | None = None
    error_count: int | None = None
    warning_count: int | None = None
    service_name: str = ""
    project_slug: str = ""
    probe: dict[str, Any] = Field(default_factory=dict)


class MonitoringIssuesOut(MonitoringEnvelopeOut):
    issues: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    service_name: str = ""
    window: str = "24h"


class MonitoringEventOut(MonitoringEnvelopeOut):
    event: dict[str, Any] | None = None


class MonitoringMutationOut(MonitoringEnvelopeOut):
    action: str | None = None
    target_id: str | None = None
    monitor: dict[str, Any] | None = None


class MonitoringCollectionOut(MonitoringEnvelopeOut):
    items: list[dict[str, Any]] = Field(default_factory=list)
    monitors: list[dict[str, Any]] = Field(default_factory=list)
    keys: list[dict[str, Any]] = Field(default_factory=list)
    project_slug: str = ""


class MonitoringTransactionsOut(MonitoringEnvelopeOut):
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    project_slug: str = ""
    project_id: int | None = None
    node_ip: str = ""


class MonitoringTransactionIngestRequest(MonitoringServiceRequest):
    transaction: str = Field(min_length=1)
    environment: str = ""
    duration_ms: float = Field(default=0.0, ge=0.0, le=86_400_000.0)
    tags: dict[str, str] = Field(default_factory=dict)


class MonitoringTransactionIngestOut(MonitoringTransactionsOut):
    event_id: str | None = None
    accepted_pending: bool = False


class ProcessMetricOut(BaseModel):
    name: str
    cpu: float | None = None
    memory: float | None = None
    node_id: int | None = None
    node_name: str | None = None
    instance: str | None = None


class ProcessMetricsOut(BaseModel):
    processes: list[ProcessMetricOut] = Field(default_factory=list)
    node_id: int | None = None
    node_name: str | None = None
    sort: str = "cpu"
    memory_unit: str = "MiB"
    source: str = "prometheus"
    availability: str = "unavailable"
    checked_at: str | None = None
    error: str | None = None


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
    checksum_sha256: str | None = None

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


class MountedVolumeOut(BaseModel):
    mount: str
    fstype: str
    total_gb: float
    used_gb: float
    usage_pct: float


class NodeMetricsOut(BaseModel):
    node_id: int
    node_name: str
    window: str
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    network_rx_mbps: float | None
    network_tx_mbps: float | None
    cpu_series: list[MetricSeriesPointOut]
    memory_series: list[MetricSeriesPointOut]
    disk_series: list[MetricSeriesPointOut]
    mounted_volumes: list[MountedVolumeOut] = []
    prometheus_reachable: bool | None = None
    availability: str = "unavailable"
    source: str = "prometheus"
    checked_at: str | None = None
    latest_sample_at: str | None = None
    units: dict[str, str] = {}
    error: str | None = None


class ServiceDbMetricsOut(BaseModel):
    active_connections: int | None = None
    idle_connections: int | None = None
    read_ops: float | None = None
    write_ops: float | None = None
    cache_hit_ratio: float | None = None
    transaction_locks: int | None = None


class ServiceBrokerMetricsOut(BaseModel):
    ingestion_rate: float | None = None
    delivery_rate: float | None = None
    queued_ready: float | None = None
    queued_unacked: float | None = None
    consumer_count: float | None = None


class CustomChartSeriesOut(BaseModel):
    name: str
    points: list[MetricSeriesPointOut] = []


class CustomChartOut(BaseModel):
    title: str
    unit: str = ""
    series: list[CustomChartSeriesOut] = []


class ServiceMetricsOut(BaseModel):
    service_id: int
    service_name: str
    service_key: str
    node_id: int
    window: str
    cpu_percent: float | None
    memory_mb: float | None
    log_error_rate: float | None
    queue_depth: float | None
    restart_count: float | None
    latency_ms_p95: float | None
    cpu_series: list[MetricSeriesPointOut]
    error_rate_series: list[MetricSeriesPointOut]
    queue_depth_series: list[MetricSeriesPointOut]
    db_metrics: ServiceDbMetricsOut | None = None
    broker_metrics: ServiceBrokerMetricsOut | None = None
    custom_charts: list[CustomChartOut] = []
    prometheus_reachable: bool | None = None
    availability: str = "unavailable"
    source: str = "prometheus"
    checked_at: str | None = None
    latest_sample_at: str | None = None
    units: dict[str, str] = {}
    commands_series: list[MetricSeriesPointOut] = []
    error: str | None = None


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
    node_online_count: int = 0
    services: int
    running_services: int
    open_incidents: int
    burning_slos: int
    healthy_observability_nodes: int
    degraded_observability_nodes: int
    blocked_services: int
    gpu_node_count: int = 0
    attention_services: list[DashboardAttentionServiceOut]
    active_incidents: list[IncidentRecordOut]
    degraded_observability: list[DashboardObservabilityNodeOut]


class IngestionStatsOut(BaseModel):
    loki_reachable: bool
    ingestion_rate: float
    ingestion_rate_display: str
    error_count_current_hour: int
    error_count_previous_hour: int
    error_delta_pct: float
    archive_size_bytes: int


class DiagnosticsFileLogLineOut(BaseModel):
    timestamp: str
    level: str
    message: str
    source: str


class DiagnosticsFileTailOut(BaseModel):
    lines: list[DiagnosticsFileLogLineOut] = []
    source: str = "file_live"
    log_path: str = ""
    node: str = ""
    total_lines: int = 0
    error: str | None = None


class DiagnosticsFileHistoryOut(BaseModel):
    lines: list[DiagnosticsFileLogLineOut] = []
    source: str = "file_history"
    log_path: str = ""
    page: int = 1
    page_size: int = 50
    total_count: int = 0
    total_pages: int = 1
    next_cursor: str | None = None
    previous_cursor: str | None = None
    error: str | None = None
    start: str | None = None
    end: str | None = None


class LogArchiveViewOut(BaseModel):
    archive_id: int
    filename: str
    lines: list[str] = []
    total_lines: int = 0
    truncated: bool = False
    checksum_sha256: str | None = None
    error: str | None = None


class LogArchiveDownloadOut(BaseModel):
    archive_id: int | None = None
    filename: str = ""
    content_type: str = "text/plain"
    ready: bool = False
    checksum_sha256: str | None = None
    error: str | None = None


class LogArchiveBulkDownloadRequest(BaseModel):
    archive_ids: list[int]


class LogArchiveBulkDownloadOut(BaseModel):
    zip_filename: str = ""
    files: list[dict[str, Any]] = []
    file_count: int = 0
    ready: bool = False
    error: str | None = None


class DiagnosticsChatRequest(BaseModel):
    question: str
    window: str = "current"
    history: list[dict[str, Any]] | None = None


class DiagnosticsChatOut(BaseModel):
    success: bool
    answer: str = ""
    evidence: list[dict[str, Any]] = []
    chart_data: list[float | int] = []
    suggestions: list[str] = []
    error: str | None = None
    provider: str | None = None


class DiagnosticsBackfillOut(BaseModel):
    """Backfill submission plus the stable job identity used for polling."""

    id: int
    service_id: int
    ready: bool
    status: str
    requirements: dict[str, Any] = Field(default_factory=dict)
    job: DiagnosticsBackfillJobOut
    summary: str = ""


class UserOut(BaseModel):
    user_id: str
    user_name: str = ""
    user_email: str
    user_role: str
    user_number: str = ""
    permissions: list[str] = []
    status: str
    login_count: int = 0
    last_login: str = "—"
    last_login_ts: int | str = 0
    created_at: str = ""
    session_info: dict[str, Any] = {}
    invite_token: str = ""
    invite_link: str = ""


class UserCreate(BaseModel):
    user_name: str
    user_email: str
    password: str
    user_role: str = "Operational"
    user_number: str = ""
    permissions: list[str] = []


class UserUpdate(BaseModel):
    user_name: str | None = None
    user_role: str | None = None
    user_number: str | None = None
    password: str | None = None
    status: str | None = None
    permissions: list[str] | None = None


class UserInviteCreate(BaseModel):
    user_name: str
    user_email: str
    user_role: str = "Operational"
    user_number: str = ""
    permissions: list[str] = []


class UserInviteResend(BaseModel):
    emails: list[str]


class UserInviteRevoke(BaseModel):
    user_email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginOut(BaseModel):
    token: str
    expires_at: str
    user: UserOut


class InviteAcceptRequest(BaseModel):
    full_name: str
    password: str


class LastVisitedUpdate(BaseModel):
    view: str | None = None
    cluster_name: str | None = None
    node_name: str | None = None
    service_name: str | None = None


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
    ssh_secret_ref: str = ""
    host_key_fingerprint: str = ""
    known_hosts_ref: str = ""
    environment: str
    status: str
    connection_state: str
    facts_available: bool
    facts: dict[str, Any]
    facts_error: str | None
    last_checked_at: str | None
    validation_job: NodeValidationJobOut | None
    recommendations: list[str]
    live_probe: dict[str, Any] | None = None

    @field_validator("facts", mode="before")
    @classmethod
    def _mask_fact_values(cls, value: Any) -> dict[str, Any]:
        masked = redact_secrets(value if isinstance(value, dict) else {})
        return masked if isinstance(masked, dict) else {}


class NodeConnectionProbeRequest(BaseModel):
    """One-shot remote credentials; never persisted or returned."""

    ssh_private_key: str | None = None
    ssh_password: str | None = None


class NodeConnectionProbeOut(BaseModel):
    ssh_ok: bool | None = None
    docker_ok: bool | None = None
    connection_mode: str
    probed_at: str
    detail: str = ""


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


class ObservabilitySignalOut(BaseModel):
    state: Literal["available", "degraded", "unavailable", "error", "not_configured"]
    source: str
    checked_at: str
    evidence_at: str | None = None
    age_seconds: float | None = None
    fresh: bool = False
    error: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class ObservabilityTargetOut(BaseModel):
    cluster_id: int
    cluster_name: str
    node_id: int
    node_name: str
    service_id: int
    service_external_id: str
    service_name: str
    service_key: str
    container_name: str


class ObservabilityStatusOut(BaseModel):
    generated_at: str
    overall_state: Literal["available", "degraded", "unavailable", "error"]
    freshness_seconds: int
    target: ObservabilityTargetOut
    signals: dict[str, ObservabilitySignalOut]


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
