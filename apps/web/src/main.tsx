import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Layout } from "./components/Layout";
import { GlassCard } from "./components/GlassCard";
import "./styles.css";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const OPERATOR_PREFERENCES_KEY = "platformops.operator.preferences.v1";

type CatalogCard = {
  service_key: string;
  name: string;
  kind: string;
  image: string;
  description: string;
  dependencies: string[];
  configurable: boolean;
  log_paths: string[];
  subsystem: string;
  tags: string[];
  ports: string[];
  volumes: string[];
  config_files: string[];
  env: Record<string, unknown>;
  command: string;
  health_command: string;
};

type Cluster = { id: number; name: string; region: string; environment: string };
type Node = {
  id: number;
  cluster_id: number;
  name: string;
  host: string;
  ssh_user: string;
  ssh_key_path?: string;
  environment: string;
  volume_root: string;
  docker_network: string;
  status: string;
  facts_json: string;
};
type ClusterDraft = {
  name: string;
  region: string;
  environment: string;
};
type NodeDraft = {
  cluster_id: number;
  name: string;
  host: string;
  ssh_user: string;
  ssh_key_path: string;
  environment: string;
  volume_root: string;
  docker_network: string;
  status: string;
};
type Service = {
  id: number;
  node_id: number;
  service_key: string;
  name: string;
  kind: string;
  container_name: string;
  image: string;
  status: string;
};
type Job = {
  id: number;
  action: string;
  status: string;
  command: string;
  output: string;
  error: string;
};
type Diagnostics = {
  service_id: number;
  source_service_id: number;
  source_service_key: string;
  target_service_key: string;
  target: string;
  status: string;
  log_paths: string[];
  recent_logs: { timestamp: string; level: string; message: string }[];
  readiness: {
    container: string;
    status: string;
    target_type?: string;
    configurable: boolean;
    file_logs: boolean;
    requires_become: boolean;
    loki_url: string;
    backfill_requirements?: {
      loki_configured: boolean;
      file_log_paths_present: boolean;
      requires_become: boolean;
      ready: boolean;
      missing: string[];
    };
    paths_checked: { path: string; readable: boolean; reason: string }[];
    dependency_targets?: {
      service_key: string;
      name: string;
      kind: string;
      target_type: string;
      container_name: string;
      status: string;
      ready: boolean;
      on_node: boolean;
    }[];
    dependency_summary?: {
      required: string[];
      missing: string[];
      stopped: string[];
      ready: boolean;
    };
    config_actions?: {
      config_manager_available: boolean;
      open_infra_card_recommended: boolean;
      recommended_dependency_cards: string[];
    };
  };
};
type DiagnosticsTarget = {
  service_id: number | null;
  service_key: string;
  name: string;
  kind: string;
  target_type: string;
  container_name: string;
  status: string;
  ready: boolean;
  on_node: boolean;
};
type DiagnosticsLive = {
  service_id: number;
  target: string;
  source_state: string;
  poll_interval_ms: number;
  tail_lines: number;
  page_size: number;
  cursor: number;
  next_cursor: number;
  total_available: number;
  has_more_history: boolean;
  lines: { timestamp: string; level: string; message: string; source: string }[];
  generated_at: string;
};
type DiagnosticsInsightAction = {
  action_id: string;
  label: string;
  description: string;
  service_key: string | null;
  incident_id: number | null;
  runbook_key: string | null;
  target_view: string;
  recommended: boolean;
};
type DiagnosticsInsightEvidence = {
  evidence_id: string;
  label: string;
  summary: string;
  target_view: string;
  severity: "info" | "warning" | "error";
  service_key: string | null;
  incident_id: number | null;
  compare_left_snapshot_id?: number | null;
  compare_right_snapshot_id?: number | null;
  baseline_snapshot_id?: number | null;
};
type DiagnosticsInsight = {
  insight_id: string;
  title: string;
  severity: "info" | "warning" | "error";
  confidence: number;
  summary: string;
  rationale: string;
  evidence_refs: string[];
  supporting_evidence: DiagnosticsInsightEvidence[];
  actions: DiagnosticsInsightAction[];
};
type DiagnosticsAnalysis = {
  service_id: number;
  service_name: string;
  source_service_id: number;
  source_service_name: string;
  source_service_key: string;
  target_service_key: string;
  target_name: string;
  overall_severity: "info" | "warning" | "error";
  overview: string;
  next_steps: string[];
  generated_at: string;
  recent_incidents: {
    id: number;
    title: string;
    severity: string;
    status: string;
    summary: string;
    remediation: string;
    created_at: string;
    resolved_at: string | null;
    latest_runbook_key: string | null;
    latest_runbook_status: string | null;
    match_reason: string;
    suggested_runbook_key: string;
  }[];
  historical_correlation: string[];
  change_evidence: {
    kind: string;
    title: string;
    summary: string;
    created_at: string;
    severity: "info" | "warning" | "error";
    detail: string;
    confidence: number;
    target_view: string;
    baseline_snapshot_id?: number | null;
    compare_left_snapshot_id?: number | null;
    compare_right_snapshot_id?: number | null;
    drift_fields?: string[];
    drift_preview?: { field?: string; expected?: unknown; actual?: unknown; severity?: string }[];
    config_action?: string;
    snapshot_id?: number;
    snapshot_version?: number;
    actor?: string;
  }[];
  insights: DiagnosticsInsight[];
};
type ConfigWorkspace = {
  service_id: number;
  content: string;
  content_source: string;
  message: string;
  snapshots: { id: number; version: number; name: string; source: string; created_at: string }[];
  snapshot_count: number;
  active_checkpoint: { id: number; version: number; name: string; source: string; created_at: string } | null;
  drift_state: string;
  config_source_label: string;
  config_path: string;
  file_label: string;
  config_capabilities: Record<string, unknown>;
  runtime_target: Record<string, unknown>;
  peers: { service_id: number; name: string; service_key: string; node_id: number; node_name: string; status: string }[];
};
type ConfigSnapshotItem = { id: number; version: number; name: string; source: string; created_at: string };
type ConfigSnapshotDetail = ConfigSnapshotItem & { service_id: number; content: string };
type ConfigMigrationPrepare = {
  artifact_id: string;
  service_id: number;
  left_snapshot_id: number;
  right_snapshot_id: number;
  final_content: string;
  validation: { ok: boolean; message: string };
  differences: { field: string; expected: unknown; actual: unknown; severity: string }[];
};
type ConfigMigrationApply = {
  artifact_id: string;
  service_id: number;
  job: Job;
  backup_snapshot_id: number | null;
  applied_content: string;
};
type ConfigSnapshotCompare = {
  service_id: number;
  left_snapshot: ConfigSnapshotDetail;
  right_snapshot: ConfigSnapshotDetail;
  differences: { field: string; expected: unknown; actual: unknown; severity: string }[];
  difference_count: number;
  summary: string;
};
type ConfigSnapshotPage = {
  service_id: number;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  source_filter: string;
  search: string;
  items: ConfigSnapshotItem[];
};
type ConfigTimelineEvent = {
  id: number;
  service_id: number | null;
  node_id: number | null;
  level: string;
  message: string;
  action: string;
  actor: string;
  metadata: Record<string, unknown>;
  created_at: string;
};
type ConfigTimelinePage = {
  service_id: number;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  action_filter: string;
  actor_filter: string;
  search: string;
  created_after: string;
  created_before: string;
  available_actions: string[];
  available_actors: string[];
  items: ConfigTimelineEvent[];
};
type Topology = {
  nodes: Record<string, unknown>[];
  services: { id: number; service_key: string; name: string; kind: string; status: string; subsystem: string }[];
  edges: { from: number | null; from_key: string; to: number; to_key: string; status: string }[];
  subsystems: Record<string, string[]>;
};
type EventItem = {
  id: number;
  service_id: number | null;
  node_id: number | null;
  category: string;
  level: string;
  message: string;
  metadata_json: string;
  created_at: string;
};
type MonitoringCheck = {
  id: number;
  service_id: number | null;
  name: string;
  status: string;
  value: string;
  detail: string;
  created_at: string;
};
type DeploymentPlan = {
  node_id: number;
  service_key: string;
  ok: boolean;
  summary: string;
  blocked_by: string[];
  steps: {
    order: number;
    service_key: string;
    name: string;
    kind: string;
    subsystem: string;
    container_name: string;
    status: string;
    action: string;
    dependencies?: string[];
    depends_on?: string[];
    ansible_command?: string;
  }[];
};
type DeploymentExecuteResult = {
  service_id: number;
  service_key: string;
  node_id: number;
  auto_install_dependencies: boolean;
  ok: boolean;
  summary: string;
  plan: DeploymentPlan;
  preflight_before: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string };
  preflight_after: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string };
  dependency_actions: {
    service_id: number;
    service_key: string;
    action: string;
    job_id: number;
    job_status: string;
    command: string;
    message: string;
  }[];
  target_job: Job | null;
};

type PlacementRecommendation = {
  service_key: string;
  generated_at: string;
  prefer_node_id: number | null;
  avoid_node_ids: number[];
  anti_affinity_service_key: string | null;
  require_healthy: boolean;
  spread_subsystem: boolean;
  candidates: {
    node_id: number;
    node_name: string;
    node_status: string;
    score: number;
    recommendation: string;
    dependency_ready: boolean;
    dependency_missing: string[];
    dependency_stopped: string[];
    capacity_status: string;
    projected_memory_mb: number;
    projected_storage_gb: number;
    projected_cpu: number;
    notes: string[];
  }[];
};
type PlacementDeployResult = {
  service_key: string;
  node_id: number;
  node_name: string;
  generated_at: string;
  selected_candidate: PlacementRecommendation["candidates"][number];
  auto_install_dependencies: boolean;
  allow_capacity_risk: boolean;
  created_target: boolean;
  target_service_id: number;
  target_service_status: string;
  target_job_id: number;
  target_job_status: string;
  dependency_actions: {
    service_id: number;
    service_key: string;
    action: string;
    job_id: number;
    job_status: string;
    command: string;
    message: string;
  }[];
  preflight: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string };
  summary: string;
};
type ObservabilityPipeline = {
  generated_at: string;
  defaults: {
    poll_interval_ms: number;
    tail_lines: number;
    history_page_size: number;
    archive_page_size: number;
    loki_url: string;
  };
  labels: Record<string, string>;
  sources: Record<string, boolean>;
  nodes: {
    node_id: number;
    node_name: string;
    node_status: string;
    pipeline_ready: boolean;
    ingestion_state: string;
    last_signal_at: string | null;
    components: Record<string, string>;
    issues: string[];
  }[];
  summary: {
    total_nodes: number;
    healthy_nodes: number;
    degraded_nodes: number;
  };
};
type ObservabilityBootstrap = {
  node_id: number;
  subsystem: string;
  ok: boolean;
  summary: string;
  jobs: { job_id: number; service_key: string; status: string; action: string }[];
  pipeline_ready: boolean;
  ingestion_state: string;
};
type DependencyInstallResult = {
  service_id: number;
  service_key: string;
  node_id: number;
  dependency_actions: {
    service_id: number;
    service_key: string;
    action: string;
    job_id: number;
    job_status: string;
    command: string;
    message: string;
  }[];
  preflight: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string };
  summary: string;
};
type DependencyTargetActionMode = "inspect" | "config" | "diagnostics" | "ensure";
type OperatorPreferences = {
  selectedClusterId: number | null;
  selectedNodeId: number | null;
  selectedServiceId: number | null;
  selectedPlacementServiceKey: string;
  configSource: "live" | "latest_snapshot";
  nodePreset: "local-default" | "aws-general" | "aws-gpu";
  nodeMetricsWindow: MetricWindow;
  serviceMetricsWindow: MetricWindow;
};
type GeneratedArtifact = {
  name: string;
  content_type: string;
  content: string;
};
type LogArchive = {
  id: number;
  path: string;
  size_bytes: number;
  line_count: number;
  readable: string;
  reason: string;
  discovered_at?: string;
};
type ReleaseRecord = {
  id: number;
  service_id: number;
  version: string;
  image: string;
  status: string;
  strategy: string;
  previous_image: string;
  created_at: string;
};
type DriftReport = {
  id: number;
  service_id: number;
  status: string;
  baseline_snapshot_id: number | null;
  differences_json: string;
  created_at: string;
};
type PolicyFinding = {
  id: number;
  service_id: number | null;
  node_id: number | null;
  rule_id: string;
  severity: string;
  status: string;
  message: string;
  remediation: string;
};
type IncidentRecord = {
  id: number;
  service_id: number | null;
  node_id: number | null;
  title: string;
  severity: string;
  status: string;
  summary: string;
  remediation: string;
};
type RunbookExecution = {
  id: number;
  runbook_key: string;
  status: string;
  steps_json: string;
  output: string;
};
type SloReport = {
  id: number;
  service_id: number | null;
  name: string;
  target: string;
  observed: string;
  status: string;
  detail: string;
};
type CapacityReport = {
  id: number;
  node_id: number;
  status: string;
  cpu_reserved: string;
  memory_reserved_mb: number;
  storage_reserved_gb: number;
  detail_json: string;
};
type MetricPoint = {
  label: string;
  value: number;
};
type MetricWindow = "15m" | "1h" | "24h";
type NodeMetrics = {
  node_id: number;
  node_name: string;
  window: MetricWindow;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  network_rx_mbps: number;
  network_tx_mbps: number;
  cpu_series: MetricPoint[];
  memory_series: MetricPoint[];
  disk_series: MetricPoint[];
};
type ServiceMetrics = {
  service_id: number;
  service_name: string;
  service_key: string;
  node_id: number;
  window: MetricWindow;
  cpu_percent: number;
  memory_mb: number;
  log_error_rate: number;
  queue_depth: number;
  restart_count: number;
  latency_ms_p95: number;
  cpu_series: MetricPoint[];
  error_rate_series: MetricPoint[];
  queue_depth_series: MetricPoint[];
};
type SecretRecord = {
  id: number;
  key: string;
  masked_value: string;
  scope: string;
  status: string;
  rotation_interval_days: number;
};
type MaintenanceWindow = {
  id: number;
  title: string;
  status: string;
  starts_at: string;
  ends_at: string;
  impact: string;
};
type AuditExport = {
  id: number;
  export_type: string;
  status: string;
  artifact_path: string;
  content_json: string;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = payload?.detail;
    if (typeof detail === "string") {
      throw new Error(detail);
    }
    if (detail && typeof detail === "object") {
      const action = typeof detail.recommended_action === "string" ? detail.recommended_action : "Request failed.";
      const warnings = Array.isArray(detail.warnings) && detail.warnings.length > 0
        ? ` Warnings: ${detail.warnings.join("; ")}`
        : "";
      const dependents = Array.isArray(detail.dependents) && detail.dependents.length > 0
        ? ` Dependents: ${detail.dependents.join(", ")}`
        : "";
      const policyViolations = detail.policy && Array.isArray(detail.policy.violations) && detail.policy.violations.length > 0
        ? ` Policy: ${detail.policy.violations.join("; ")}`
        : "";
      const error = new Error(`${action}${warnings}${dependents}${policyViolations}`) as Error & { detail?: unknown };
      error.detail = detail;
      throw error;
    }
    throw new Error(response.statusText);
  }
  return response.json();
}

type LifecycleImpact = {
  target_type: string;
  target_id: number;
  target_name: string;
  severity: string;
  can_delete_without_force: boolean;
  dependents: string[];
  active_children: string[];
  warnings: string[];
  recommended_action: string;
};

type SubsystemRolloutPlan = {
  node_id: number;
  subsystem: string;
  ok: boolean;
  summary: string;
  steps: {
    service_key: string;
    name: string;
    kind: string;
    status: string;
    action: string;
    blockers: string[];
    container_name: string;
  }[];
  blocked_by: string[];
};

type ServiceCapabilities = {
  service_id: number;
  service_key: string;
  kind: string;
  container_name: string;
  diagnostics: boolean;
  config: boolean;
  backup: boolean;
  requires_sudo_for_file_logs: boolean;
};
type ServiceSummary = {
  service_id: number;
  node_id: number;
  service_key: string;
  name: string;
  kind: string;
  subsystem: string;
  status: string;
  container_name: string;
  image: string;
  dependency: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string };
  capabilities: ServiceCapabilities;
  latest_job: Job | null;
  latest_backup: { id: number; status: string; strategy: string; artifact_path: string; created_at: string; completed_at: string | null } | null;
  latest_release: ReleaseRecord | null;
  latest_drift: DriftReport | null;
  latest_monitoring: MonitoringCheck | null;
  latest_slo: SloReport | null;
  latest_runbook: RunbookExecution | null;
  active_incidents: IncidentRecord[];
  snapshot_count: number;
  recent_event_count: number;
  recent_events: EventItem[];
};
type ServiceReleaseTimeline = {
  service_id: number;
  service_name: string;
  current_image: string;
  current_status: string;
  rollback_available: boolean;
  latest_rollback_job: Job | null;
  items: {
    release: ReleaseRecord;
    rollback_executed: boolean;
    notes: string[];
    related_events: EventItem[];
  }[];
  recent_change_events: EventItem[];
};
type DashboardSummary = {
  clusters: number;
  nodes: number;
  services: number;
  running_services: number;
  open_incidents: number;
  burning_slos: number;
  healthy_observability_nodes: number;
  degraded_observability_nodes: number;
  blocked_services: number;
  attention_services: {
    service_id: number;
    service_name: string;
    service_key: string;
    node_id: number;
    node_name: string;
    cluster_id: number;
    cluster_name: string;
    status: string;
    severity: string;
    reasons: string[];
  }[];
  active_incidents: IncidentRecord[];
  degraded_observability: {
    node_id: number;
    node_name: string;
    cluster_name: string;
    pipeline_ready: boolean;
    ingestion_state: string;
    last_signal_at: string | null;
    issues: string[];
  }[];
};
type ClusterOperations = {
  cluster_id: number;
  cluster_name: string;
  total_events: number;
  change_events: number;
  recovery_events: number;
  governance_events: number;
  active_incidents: number;
  items: {
    id: number;
    category: string;
    level: string;
    message: string;
    created_at: string;
    service_id: number | null;
    service_name: string | null;
    service_key: string | null;
    node_id: number | null;
    node_name: string | null;
    action_family: string;
  }[];
};

type ClusterSummary = {
  cluster_id: number;
  node_count: number;
  service_count: number;
  healthy_count: number;
  warning_count: number;
  error_count: number;
};

type NodeSummary = {
  node_id: number;
  service_count: number;
  kind_counts: Record<string, number>;
  docker_network: string;
  volume_root: string;
  capacity_status: string;
};
type NodeJobHistory = {
  node_id: number;
  node_name: string;
  total_jobs: number;
  deployment_jobs: number;
  config_jobs: number;
  validation_jobs: number;
  failed_jobs: number;
  items: {
    id: number;
    action: string;
    status: string;
    command: string;
    output: string;
    error: string;
    created_at: string;
    started_at: string | null;
    ended_at: string | null;
    service_id: number | null;
    service_name: string | null;
    service_key: string | null;
  }[];
};

type NodeConnection = {
  node_id: number;
  node_name: string;
  host: string;
  ssh_user: string;
  ssh_key_path: string;
  environment: string;
  status: string;
  connection_state: string;
  facts_available: boolean;
  facts: Record<string, unknown>;
  facts_error: string | null;
  last_checked_at: string | null;
  validation_job: {
    id: number;
    status: string;
    created_at: string;
    ended_at: string | null;
    error: string;
    output: string;
    command: string;
  } | null;
  recommendations: string[];
};
type NodeOnboarding = {
  node_id: number;
  node_name: string;
  environment: string;
  overall_status: string;
  checked_at: string;
  connection_state: string;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  checks: {
    check_id: string;
    title: string;
    status: string;
    severity: string;
    detail: string;
    remediation: string;
  }[];
  next_actions: string[];
  suggested_actions: string[];
};
type NodeOnboardingRemediation = {
  node_id: number;
  action: string;
  ok: boolean;
  message: string;
  updated_fields: Record<string, string>;
  validation_job: {
    id: number;
    status: string;
    created_at: string;
    ended_at: string | null;
    error: string;
    output: string;
    command: string;
  } | null;
};

type DTrainOverview = {
  tracker: { status: string; container_name: string; image: string };
  controller: { status: string; container_name: string; image: string };
  workers: { id: number; status: string; container_name: string; image: string }[];
  dependencies: { rabbitmq: string; redis: string; ok: boolean };
  metrics: { active_jobs: number; queued_jobs: number; completed_jobs: number; failed_jobs: number; gpu_availability: string };
  rollout_ready: boolean;
};

type CapabilityCoverageItem = {
  service_key: string;
  kind: string;
  subsystem: string;
  diagnostics_ready: boolean;
  config_ready: boolean;
  config_mode: string;
  backup_ready: boolean;
  stateful: boolean;
  requires_sudo_for_file_logs: boolean;
  issues: string[];
};

type CapabilityCoverage = {
  total_services: number;
  diagnostics_ready: number;
  config_ready: number;
  backup_ready: number;
  policy_risk_services: number;
  issues_count: number;
  items: CapabilityCoverageItem[];
};

type LifecycleAudit = {
  window_hours: number;
  total_lifecycle_events: number;
  blocked_deletions: number;
  forced_deletions: number;
  safe_deletions: number;
  last_blocked_at: string | null;
  last_forced_at: string | null;
  last_safe_delete_at: string | null;
};

type ForceDeleteApproval = {
  id: number;
  target_type: string;
  target_id: number;
  reason: string;
  requested_by: string;
  status: string;
  approver: string;
  decision_note: string;
  created_at: string;
  approved_at: string | null;
  expires_at: string | null;
  used_at: string | null;
};
type ReleaseSafety = {
  service_id: number;
  service_name: string;
  risky: boolean;
  severity: string;
  reasons: string[];
  recommended_action: string;
};
type ReleaseApproval = {
  id: number;
  service_id: number;
  target_version: string;
  target_image: string;
  reason: string;
  requested_by: string;
  status: string;
  approver: string;
  decision_note: string;
  created_at: string;
  approved_at: string | null;
  expires_at: string | null;
  used_at: string | null;
};

type ServiceInstallField = {
  key: string;
  label: string;
  field_type: string;
  required: boolean;
  value: unknown;
  help_text: string;
  options: string[];
  section: string;
};
type ServiceInstallSchema = {
  service_key: string;
  name: string;
  kind: string;
  configurable: boolean;
  exposure_supported: boolean;
  fields: ServiceInstallField[];
  defaults: Record<string, unknown>;
};

function formatExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "no expiry";
  const expiry = new Date(expiresAt).getTime();
  const now = Date.now();
  const deltaMs = expiry - now;
  if (deltaMs <= 0) return "expired";
  const totalMinutes = Math.floor(deltaMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${minutes}m remaining`;
}

function renderMetricSparkline(series: MetricPoint[], color: string) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: "44px", marginTop: "0.5rem" }}>
      {series.map((point) => (
        <div
          key={`${point.label}-${point.value}`}
          title={`${point.label}: ${point.value}`}
          style={{
            flex: 1,
            minWidth: "8px",
            height: `${Math.max(12, Math.min(100, point.value))}%`,
            borderRadius: "4px 4px 0 0",
            background: color,
            opacity: 0.85,
          }}
        />
      ))}
    </div>
  );
}

function renderMetricWindowPicker(
  value: MetricWindow,
  onChange: (window: MetricWindow) => void,
): React.ReactNode {
  return (
    <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
      {(["15m", "1h", "24h"] as MetricWindow[]).map((window) => (
        <button
          key={window}
          type="button"
          className={`btn btn-sm ${value === window ? "btn-primary" : "btn-secondary"}`}
          onClick={() => onChange(window)}
        >
          {window}
        </button>
      ))}
    </div>
  );
}

function generateMockLogs(archive: LogArchive) {
  const baseLogs = [
    { level: "INFO", message: "Starting syslog backfill parser v1.4.2" },
    { level: "INFO", message: "Configuring Loki client endpoints..." },
    { level: "DEBUG", message: "Discovered active docker log stream buffers" },
    { level: "INFO", message: `Scanning file target: ${archive.path}` },
    { level: "INFO", message: `File statistics: size=${archive.size_bytes} bytes, lines=${archive.line_count}` },
    { level: "WARN", message: "Slow socket connection detected on Loki ingress" },
    { level: "INFO", message: "Backfilling log lines batch [0 - 100]..." },
    { level: "INFO", message: "Ingested 150 lines successfully." },
    { level: "INFO", message: "Active log tail verification passed." },
    { level: "INFO", message: "Parser run finished. Awaiting next cron sequence." }
  ];
  
  const now = new Date(archive.discovered_at || new Date());
  return baseLogs.map((log, index) => {
    const timestamp = new Date(now.getTime() - (baseLogs.length - index) * 5000);
    return {
      timestamp: timestamp.toISOString(),
      level: log.level,
      message: log.message
    };
  });
}

function App() {
  const [catalog, setCatalog] = useState<CatalogCard[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [serviceSummary, setServiceSummary] = useState<ServiceSummary | null>(null);
  const [serviceReleaseTimeline, setServiceReleaseTimeline] = useState<ServiceReleaseTimeline | null>(null);
  const [serviceMetrics, setServiceMetrics] = useState<ServiceMetrics | null>(null);
  const [serviceMetricsWindow, setServiceMetricsWindow] = useState<MetricWindow>("1h");
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [clusterOperations, setClusterOperations] = useState<ClusterOperations | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsAnalysis | null>(null);
  const [diagnosticsLive, setDiagnosticsLive] = useState<DiagnosticsLive | null>(null);
  const [tailLines, setTailLines] = useState<number>(150);
  const [historyPageSize, setHistoryPageSize] = useState<number>(100);
  const [logsPollMs, setLogsPollMs] = useState<number>(2500);
  const [autoPollLogs, setAutoPollLogs] = useState<boolean>(false);
  const [diagnosticsTargetKey, setDiagnosticsTargetKey] = useState<string>("");
  const [diagnosticsTargets, setDiagnosticsTargets] = useState<DiagnosticsTarget[]>([]);
  const [diagnosticsSourceServiceId, setDiagnosticsSourceServiceId] = useState<number | null>(null);
  const [configTimelinePage, setConfigTimelinePage] = useState<ConfigTimelinePage | null>(null);
  const [configTimelineAction, setConfigTimelineAction] = useState<string>("all");
  const [configTimelineActor, setConfigTimelineActor] = useState<string>("all");
  const [configTimelineSearch, setConfigTimelineSearch] = useState<string>("");
  const [configTimelineCreatedAfter, setConfigTimelineCreatedAfter] = useState<string>("");
  const [configTimelineCreatedBefore, setConfigTimelineCreatedBefore] = useState<string>("");
  const [configTimelineLimit, setConfigTimelineLimit] = useState<number>(10);
  const [config, setConfig] = useState<ConfigWorkspace | null>(null);
  const [snapshotPage, setSnapshotPage] = useState<ConfigSnapshotPage | null>(null);
  const [snapshotCompare, setSnapshotCompare] = useState<ConfigSnapshotCompare | null>(null);
  const [snapshotSourceFilter, setSnapshotSourceFilter] = useState<string>("all");
  const [snapshotSearch, setSnapshotSearch] = useState<string>("");
  const [snapshotLimit, setSnapshotLimit] = useState<number>(20);
  const [migrationArtifactId, setMigrationArtifactId] = useState<string>("");
  const [migrationContent, setMigrationContent] = useState<string>("");
  const [migrationValidation, setMigrationValidation] = useState<string>("");
  const [migrationApplyResult, setMigrationApplyResult] = useState<ConfigMigrationApply | null>(null);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [checks, setChecks] = useState<MonitoringCheck[]>([]);
  const [plan, setPlan] = useState<DeploymentPlan | null>(null);
  const [placement, setPlacement] = useState<PlacementRecommendation | null>(null);
  const [observabilityPipeline, setObservabilityPipeline] = useState<ObservabilityPipeline | null>(null);
  const [observabilityBusyNodeId, setObservabilityBusyNodeId] = useState<number | null>(null);
  const [artifact, setArtifact] = useState<GeneratedArtifact | null>(null);
  const [archives, setArchives] = useState<LogArchive[]>([]);
  const [releases, setReleases] = useState<ReleaseRecord[]>([]);
  const [drift, setDrift] = useState<DriftReport | null>(null);
  const [findings, setFindings] = useState<PolicyFinding[]>([]);
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [runbooks, setRunbooks] = useState<RunbookExecution[]>([]);
  const [slos, setSlos] = useState<SloReport[]>([]);
  const [capacity, setCapacity] = useState<CapacityReport[]>([]);
  const [secrets, setSecrets] = useState<SecretRecord[]>([]);
  const [maintenance, setMaintenance] = useState<MaintenanceWindow[]>([]);
  const [auditExports, setAuditExports] = useState<AuditExport[]>([]);
  const [notice, setNotice] = useState<string>("Ready");

  // New state variables for cPlatform features
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [nodeMetrics, setNodeMetrics] = useState<NodeMetrics | null>(null);
  const [nodeMetricsWindow, setNodeMetricsWindow] = useState<MetricWindow>("1h");
  const [clusterEditor, setClusterEditor] = useState<{
    visible: boolean;
    mode: "create" | "edit";
    clusterId: number | null;
    draft: ClusterDraft;
    error: string;
  }>({
    visible: false,
    mode: "create",
    clusterId: null,
    draft: { name: "", region: "local", environment: "development" },
    error: "",
  });
  const [nodeEditor, setNodeEditor] = useState<{
    visible: boolean;
    mode: "create" | "edit";
    nodeId: number | null;
    draft: NodeDraft;
    error: string;
  }>({
    visible: false,
    mode: "create",
    nodeId: null,
    draft: {
      cluster_id: 0,
      name: "",
      host: "localhost",
      ssh_user: "ubuntu",
      ssh_key_path: "",
      environment: "local",
      volume_root: "/tmp/platformops",
      docker_network: "platformops-net",
      status: "healthy",
    },
    error: "",
  });
  const [nodePreset, setNodePreset] = useState<"local-default" | "aws-general" | "aws-gpu">("local-default");
  const [clusterSummary, setClusterSummary] = useState<ClusterSummary | null>(null);
  const [nodeSummary, setNodeSummary] = useState<NodeSummary | null>(null);
  const [nodeJobHistory, setNodeJobHistory] = useState<NodeJobHistory | null>(null);
  const [nodeConnection, setNodeConnection] = useState<NodeConnection | null>(null);
  const [nodeOnboarding, setNodeOnboarding] = useState<NodeOnboarding | null>(null);
  const [onboardingActionBusy, setOnboardingActionBusy] = useState<string>("");
  const [dtrainOverview, setDtrainOverview] = useState<DTrainOverview | null>(null);
  const [selectedSubsystem, setSelectedSubsystem] = useState<string>("distributed-training-plane");
  const [configSource, setConfigSource] = useState<"live" | "latest_snapshot">("live");
  const [selectedPlacementServiceKey, setSelectedPlacementServiceKey] = useState<string>("dtrain-controller");
  const [operatorPreferences, setOperatorPreferences] = useState<OperatorPreferences | null>(null);
  const [preferNodeId, setPreferNodeId] = useState<string>("");
  const [avoidNodeIds, setAvoidNodeIds] = useState<string>("");
  const [antiAffinityKey, setAntiAffinityKey] = useState<string>("");
  const [requireHealthyNodes, setRequireHealthyNodes] = useState<boolean>(false);
  const [spreadSubsystem, setSpreadSubsystem] = useState<boolean>(true);
  const [autoInstallDependencies, setAutoInstallDependencies] = useState<boolean>(true);
  const [allowPlacementCapacityRisk, setAllowPlacementCapacityRisk] = useState<boolean>(false);
  const [subsystemPlan, setSubsystemPlan] = useState<SubsystemRolloutPlan | null>(null);
  const [capabilities, setCapabilities] = useState<ServiceCapabilities | null>(null);
  const [coverage, setCoverage] = useState<CapabilityCoverage | null>(null);
  const [lifecycleAudit, setLifecycleAudit] = useState<LifecycleAudit | null>(null);
  const [forceApprovals, setForceApprovals] = useState<ForceDeleteApproval[]>([]);
  const [releaseApprovals, setReleaseApprovals] = useState<ReleaseApproval[]>([]);
  const [eventCategoryFilter, setEventCategoryFilter] = useState<string>("all");
  const [eventLevelFilter, setEventLevelFilter] = useState<string>("all");
  const [eventSearch, setEventSearch] = useState<string>("");
  const [eventLimit, setEventLimit] = useState<number>(120);

  // Lifecycle Deletion Safety Modal State
  const [deleteModal, setDeleteModal] = useState<{
    visible: boolean;
    targetType: "service" | "node" | "cluster";
    targetId: number;
    targetName: string;
    impact: LifecycleImpact | null;
    force: boolean;
    forceReason: string;
    forceApprovalId: string;
    requestedBy: string;
    approver: string;
    decisionNote: string;
    approvalStatus: string;
  }>({
    visible: false,
    targetType: "service",
    targetId: 0,
    targetName: "",
    impact: null,
    force: false,
    forceReason: "",
    forceApprovalId: "",
    requestedBy: "platform-operator",
    approver: "platform-admin",
    decisionNote: "",
    approvalStatus: "none",
  });
  const [renameModal, setRenameModal] = useState<{
    visible: boolean;
    snapshotId: number;
    value: string;
    error: string;
  }>({
    visible: false,
    snapshotId: 0,
    value: "",
    error: "",
  });
  const [releaseApprovalModal, setReleaseApprovalModal] = useState<{
    visible: boolean;
    serviceId: number;
    serviceName: string;
    version: string;
    image: string;
    safety: ReleaseSafety | null;
    reason: string;
    requestedBy: string;
    approvalId: string;
    approver: string;
    decisionNote: string;
    error: string;
  }>({
    visible: false,
    serviceId: 0,
    serviceName: "",
    version: "",
    image: "",
    safety: null,
    reason: "",
    requestedBy: "platform-operator",
    approvalId: "",
    approver: "platform-admin",
    decisionNote: "",
    error: "",
  });
  const [deploymentModal, setDeploymentModal] = useState<{
    visible: boolean;
    serviceId: number | null;
    serviceName: string;
    nodeName: string;
    preflight: { ok: boolean; missing: string[]; stopped: string[]; required: string[]; message: string } | null;
    autoInstallDependencies: boolean;
    loading: boolean;
    executing: boolean;
    error: string;
    result: DeploymentExecuteResult | null;
  }>({
    visible: false,
    serviceId: null,
    serviceName: "",
    nodeName: "",
    preflight: null,
    autoInstallDependencies: true,
    loading: false,
    executing: false,
    error: "",
    result: null,
  });

  // cPlatform Layout Sub-Tab states
  const [clusterSubTab, setClusterSubTab] = useState<"nodes" | "topology" | "policy" | "audit">("nodes");
  const [configTab, setConfigTab] = useState<"current" | "timeline" | "compare" | "migration">("current");
  const [diagTab, setDiagTab] = useState<"tail" | "files" | "analytics">("tail");

  // SRE Incident Analytics Chat state
  const [analyticsMessages, setAnalyticsMessages] = useState<{ sender: "user" | "assistant"; text: string; timestamp: string }[]>([
    {
      sender: "assistant",
      text: "Hello! I am your SRE Incident AI Analyst. I can help analyze your Loki logs, check service dependencies, or audit Ansible/Kubernetes trails to troubleshoot active incidents. Ask me anything about log anomalies or deployment errors.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [analyticsInput, setAnalyticsInput] = useState<string>("");

  // Drawer visibility states
  const [stepperDrawerVisible, setStepperDrawerVisible] = useState<boolean>(false);
  const [stepperStep, setStepperStep] = useState<number>(1);
  const [onboardingJobId, setOnboardingJobId] = useState<number | null>(null);
  const [onboardingOutput, setOnboardingOutput] = useState<string>("");
  const [onboardingError, setOnboardingError] = useState<string>("");
  const [onboardingStatus, setOnboardingStatus] = useState<string>("running");
  const [selectedArchive, setSelectedArchive] = useState<LogArchive | null>(null);
  const [catalogDrawerVisible, setCatalogDrawerVisible] = useState<boolean>(false);
  const [catalogOnboarding, setCatalogOnboarding] = useState<{
    visible: boolean;
    mode: "create" | "edit";
    card: CatalogCard | null;
    editingService: Service | null;
    installSchema: ServiceInstallSchema | null;
    installFieldValues: Record<string, unknown>;
    nodeId: number;
    customName: string;
    nextAction: "overview" | "config" | "deploy";
    overridesText: string;
    creating: boolean;
    error: string;
    registeredService: Service | null;
  }>({
    visible: false,
    mode: "create",
    card: null,
    editingService: null,
    installSchema: null,
    installFieldValues: {},
    nodeId: 0,
    customName: "",
    nextAction: "deploy",
    overridesText: "",
    creating: false,
    error: "",
    registeredService: null,
  });

  // Search filters
  const [treeSearchQuery, setTreeSearchQuery] = useState<string>("");
  const [nodeSearchQuery, setNodeSearchQuery] = useState<string>("");

  // Compare diff snapshot states
  const [compareSnapshotLeft, setCompareSnapshotLeft] = useState<number | null>(null);
  const [compareSnapshotRight, setCompareSnapshotRight] = useState<number | null>(null);

  async function loadServiceCapabilities(serviceId: number) {
    try {
      const caps = await api<ServiceCapabilities>(`/api/services/${serviceId}/capabilities`);
      setCapabilities(caps);
    } catch (e) {
      setCapabilities(null);
    }
  }

  async function loadServiceSummary(serviceId: number) {
    try {
      const summary = await api<ServiceSummary>(`/api/services/${serviceId}/summary`);
      setServiceSummary(summary);
    } catch (_error) {
      setServiceSummary(null);
    }
  }

  async function loadServiceReleaseTimeline(serviceId: number) {
    try {
      const timeline = await api<ServiceReleaseTimeline>(`/api/services/${serviceId}/releases/timeline?limit=8`);
      setServiceReleaseTimeline(timeline);
    } catch (_error) {
      setServiceReleaseTimeline(null);
    }
  }

  async function loadServiceMetrics(serviceId: number, window: MetricWindow = serviceMetricsWindow) {
    try {
      const metrics = await api<ServiceMetrics>(`/api/services/${serviceId}/metrics?window=${encodeURIComponent(window)}`);
      setServiceMetrics(metrics);
    } catch (_error) {
      setServiceMetrics(null);
    }
  }

  async function loadNodeConnection(nodeId: number) {
    try {
      const connection = await api<NodeConnection>(`/api/nodes/${nodeId}/connection`);
      setNodeConnection(connection);
    } catch (_error) {
      setNodeConnection(null);
    }
  }

  async function loadNodeOnboarding(nodeId: number) {
    try {
      const report = await api<NodeOnboarding>(`/api/nodes/${nodeId}/onboarding-readiness`);
      setNodeOnboarding(report);
    } catch (_error) {
      setNodeOnboarding(null);
    }
  }

  async function loadNodeMetrics(nodeId: number, window: MetricWindow = nodeMetricsWindow) {
    try {
      const metrics = await api<NodeMetrics>(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(window)}`);
      setNodeMetrics(metrics);
    } catch (_error) {
      setNodeMetrics(null);
    }
  }

  async function loadNodeJobHistory(nodeId: number) {
    try {
      const history = await api<NodeJobHistory>(`/api/nodes/${nodeId}/jobs?limit=10`);
      setNodeJobHistory(history);
    } catch (_error) {
      setNodeJobHistory(null);
    }
  }

  async function pollOnboardingJob(nodeId: number, jobId: number) {
    try {
      const history = await api<NodeJobHistory>(`/api/nodes/${nodeId}/jobs?limit=5`);
      const targetJob = history.items.find((j: any) => j.id === jobId);
      if (targetJob) {
        setOnboardingOutput(targetJob.output || "");
        setOnboardingError(targetJob.error || "");
        setOnboardingStatus(targetJob.status);
        if (targetJob.status === "running" || targetJob.status === "queued") {
          setTimeout(() => pollOnboardingJob(nodeId, jobId), 800);
        } else {
          await refresh();
        }
      } else {
        setTimeout(() => pollOnboardingJob(nodeId, jobId), 800);
      }
    } catch (e) {
      setTimeout(() => pollOnboardingJob(nodeId, jobId), 1500);
    }
  }

  async function loadClusterOperations(clusterId: number) {
    try {
      const operations = await api<ClusterOperations>(`/api/clusters/${clusterId}/operations?limit=40`);
      setClusterOperations(operations);
    } catch (_error) {
      setClusterOperations(null);
    }
  }

  async function runOnboardingRemediation(action: string) {
    if (!selectedNode) {
      setNotice("Select a node first.");
      return;
    }
    try {
      setOnboardingActionBusy(action);
      const result = await api<NodeOnboardingRemediation>(`/api/nodes/${selectedNode.id}/onboarding-remediate`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      if (result.validation_job) {
        setJob({
          id: result.validation_job.id,
          action: "validate-node",
          status: result.validation_job.status,
          command: result.validation_job.command,
          output: result.validation_job.output,
          error: result.validation_job.error,
        });
      }
      setNotice(result.message);
      await refresh();
      if (selectedNode) {
        await loadNodeConnection(selectedNode.id);
        await loadNodeOnboarding(selectedNode.id);
        await loadNodeJobHistory(selectedNode.id);
      }
    } catch (error: any) {
      setNotice(`Onboarding remediation failed: ${error.message}`);
    } finally {
      setOnboardingActionBusy("");
    }
  }

  async function bootstrapObservability(nodeId: number) {
    try {
      setObservabilityBusyNodeId(nodeId);
      const result = await api<ObservabilityBootstrap>(`/api/nodes/${nodeId}/observability/bootstrap`, {
        method: "POST",
      });
      setNotice(result.summary);
      await refresh();
      await loadNodeJobHistory(nodeId);
    } catch (error: any) {
      setNotice(`Observability bootstrap failed: ${error.message}`);
    } finally {
      setObservabilityBusyNodeId(null);
    }
  }

  function getOnboardingActionLabel(action: string) {
    if (action === "apply-aws-general-preset") return "Apply AWS General Preset";
    if (action === "apply-aws-gpu-preset") return "Apply AWS GPU Preset";
    if (action === "apply-local-preset") return "Apply Local Preset";
    if (action === "run-validation") return "Run Validation";
    return action;
  }

  async function loadConfigTimeline(
    serviceId: number,
    options?: { offset?: number; append?: boolean; silent?: boolean },
  ) {
    const nextOffset = options?.offset ?? 0;
    const params = new URLSearchParams({
      limit: String(configTimelineLimit),
      offset: String(nextOffset),
      action: configTimelineAction,
      actor: configTimelineActor,
      search: configTimelineSearch.trim(),
      created_after: configTimelineCreatedAfter.trim(),
      created_before: configTimelineCreatedBefore.trim(),
    });
    const next = await api<ConfigTimelinePage>(`/api/services/${serviceId}/config/timeline?${params.toString()}`);
    if (options?.append && configTimelinePage) {
      setConfigTimelinePage({
        ...next,
        items: [...configTimelinePage.items, ...next.items],
      });
      if (!options?.silent) {
        setNotice(`Loaded ${next.items.length} more config timeline events.`);
      }
      return;
    }
    setConfigTimelinePage(next);
    if (!options?.silent) {
      setNotice(`Loaded ${next.items.length} config timeline events (${next.total} total).`);
    }
  }

  function buildEventsPath() {
    const params = new URLSearchParams();
    params.set("limit", String(eventLimit));
    if (eventCategoryFilter !== "all") params.set("category", eventCategoryFilter);
    if (eventLevelFilter !== "all") params.set("level", eventLevelFilter);
    if (eventSearch.trim()) params.set("search", eventSearch.trim());
    return `/api/events?${params.toString()}`;
  }

  async function refresh() {
    const [
      catalogNext,
      clustersNext,
      nodesNext,
      servicesNext,
      topologyNext,
      eventsNext,
      checksNext,
      findingsNext,
      incidentsNext,
      runbooksNext,
      slosNext,
      dashboardSummaryNext,
      observabilityNext,
      capacityNext,
      secretsNext,
      maintenanceNext,
      auditExportsNext,
      coverageNext,
      lifecycleAuditNext,
      forceApprovalsNext,
      releaseApprovalsNext,
    ] = await Promise.all([
      api<CatalogCard[]>("/api/catalog/services"),
      api<Cluster[]>("/api/clusters"),
      api<Node[]>("/api/nodes"),
      api<Service[]>("/api/services"),
      api<Topology>("/api/topology"),
      api<EventItem[]>(buildEventsPath()),
      api<MonitoringCheck[]>("/api/monitoring/checks"),
      api<PolicyFinding[]>("/api/policy/findings"),
      api<IncidentRecord[]>("/api/incidents"),
      api<RunbookExecution[]>("/api/runbooks/executions"),
      api<SloReport[]>("/api/slo/reports"),
      api<DashboardSummary>("/api/dashboard/summary"),
      api<ObservabilityPipeline>("/api/observability/pipeline"),
      api<CapacityReport[]>("/api/capacity/reports"),
      api<SecretRecord[]>("/api/secrets"),
      api<MaintenanceWindow[]>("/api/maintenance"),
      api<AuditExport[]>("/api/audit/exports"),
      api<CapabilityCoverage>("/api/capabilities/coverage"),
      api<LifecycleAudit>("/api/lifecycle/audit?hours=72"),
      api<ForceDeleteApproval[]>("/api/lifecycle/force-approvals?limit=30"),
      api<ReleaseApproval[]>("/api/release-approvals?limit=30"),
    ]);

    setCatalog(catalogNext);
    setClusters(clustersNext);
    setNodes(nodesNext);
    setServices(servicesNext);
    setTopology(topologyNext);
    setEvents(eventsNext);
    setChecks(checksNext);
    setFindings(findingsNext);
    setIncidents(incidentsNext);
    setRunbooks(runbooksNext);
    setSlos(slosNext);
    setDashboardSummary(dashboardSummaryNext);
    setObservabilityPipeline(observabilityNext);
    setCapacity(capacityNext);
    setSecrets(secretsNext);
    setMaintenance(maintenanceNext);
    setAuditExports(auditExportsNext);
    setCoverage(coverageNext);
    setLifecycleAudit(lifecycleAuditNext);
    setForceApprovals(forceApprovalsNext);
    setReleaseApprovals(releaseApprovalsNext);

    if (selectedCluster) {
      const syncedCluster = clustersNext.find((cluster) => cluster.id === selectedCluster.id);
      if (syncedCluster) setSelectedCluster(syncedCluster);
      else setSelectedCluster(null);
    }
    if (selectedNode) {
      const syncedNode = nodesNext.find((node) => node.id === selectedNode.id);
      if (syncedNode) setSelectedNode(syncedNode);
      else setSelectedNode(null);
    }
    if (selectedService) {
      const syncedService = servicesNext.find((service) => service.id === selectedService.id);
      if (syncedService) setSelectedService(syncedService);
      else {
        setSelectedService(null);
        setServiceSummary(null);
        setServiceReleaseTimeline(null);
      }
    }

    if (clustersNext.length > 0 && !selectedCluster) {
      const defaultCluster = clustersNext[0];
      setSelectedCluster(defaultCluster);
      api<ClusterSummary>(`/api/clusters/${defaultCluster.id}/summary`)
        .then(setClusterSummary)
        .catch(console.error);
      loadClusterOperations(defaultCluster.id).catch(console.error);
    } else if (selectedCluster) {
      api<ClusterSummary>(`/api/clusters/${selectedCluster.id}/summary`)
        .then(setClusterSummary)
        .catch(console.error);
      loadClusterOperations(selectedCluster.id).catch(console.error);
    } else {
      setClusterOperations(null);
    }

    if (nodesNext.length > 0 && !selectedNode) {
      const defaultNode = nodesNext[0];
      setSelectedNode(defaultNode);
      api<NodeSummary>(`/api/nodes/${defaultNode.id}/summary`)
        .then(setNodeSummary)
        .catch(console.error);
      loadNodeConnection(defaultNode.id).catch(console.error);
      loadNodeMetrics(defaultNode.id).catch(console.error);
      loadNodeOnboarding(defaultNode.id).catch(console.error);
    } else if (selectedNode) {
      api<NodeSummary>(`/api/nodes/${selectedNode.id}/summary`)
        .then(setNodeSummary)
        .catch(console.error);
      loadNodeConnection(selectedNode.id).catch(console.error);
      loadNodeMetrics(selectedNode.id).catch(console.error);
      loadNodeOnboarding(selectedNode.id).catch(console.error);
    } else {
      setNodeConnection(null);
      setNodeMetrics(null);
      setNodeOnboarding(null);
    }

    api<DTrainOverview>("/api/dtrain/overview")
      .then(setDtrainOverview)
      .catch(console.error);

    if (!selectedService && servicesNext.length) {
      setSelectedService(servicesNext[0]);
      loadServiceCapabilities(servicesNext[0].id);
      loadServiceSummary(servicesNext[0].id);
      loadServiceReleaseTimeline(servicesNext[0].id);
      loadServiceMetrics(servicesNext[0].id);
    } else if (selectedService) {
      loadServiceCapabilities(selectedService.id);
      loadServiceSummary(selectedService.id);
      loadServiceReleaseTimeline(selectedService.id);
      loadServiceMetrics(selectedService.id);
    } else {
      setServiceSummary(null);
      setServiceReleaseTimeline(null);
      setServiceMetrics(null);
    }
  }

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(OPERATOR_PREFERENCES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as OperatorPreferences;
        setOperatorPreferences(parsed);
        if (parsed.configSource) setConfigSource(parsed.configSource);
        if (parsed.selectedPlacementServiceKey) setSelectedPlacementServiceKey(parsed.selectedPlacementServiceKey);
        if (parsed.nodePreset) setNodePreset(parsed.nodePreset);
        if (parsed.nodeMetricsWindow) setNodeMetricsWindow(parsed.nodeMetricsWindow);
        if (parsed.serviceMetricsWindow) setServiceMetricsWindow(parsed.serviceMetricsWindow);
      }
    } catch (_error) {
      // Ignore malformed local preference payloads.
    }
    refresh().catch((error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    const next: OperatorPreferences = {
      selectedClusterId: selectedCluster?.id ?? null,
      selectedNodeId: selectedNode?.id ?? null,
      selectedServiceId: selectedService?.id ?? null,
      selectedPlacementServiceKey,
      configSource,
      nodePreset,
      nodeMetricsWindow,
      serviceMetricsWindow,
    };
    setOperatorPreferences(next);
    try {
      window.localStorage.setItem(OPERATOR_PREFERENCES_KEY, JSON.stringify(next));
    } catch (_error) {
      // localStorage can fail in restricted modes; ignore.
    }
  }, [selectedCluster, selectedNode, selectedService, selectedPlacementServiceKey, configSource, nodePreset, nodeMetricsWindow, serviceMetricsWindow]);

  useEffect(() => {
    if (!operatorPreferences) return;
    if (!selectedCluster && operatorPreferences.selectedClusterId) {
      const preferredCluster = clusters.find((cluster) => cluster.id === operatorPreferences.selectedClusterId);
      if (preferredCluster) {
        setSelectedCluster(preferredCluster);
      }
    }
    if (!selectedNode && operatorPreferences.selectedNodeId) {
      const preferredNode = nodes.find((node) => node.id === operatorPreferences.selectedNodeId);
      if (preferredNode) {
        setSelectedNode(preferredNode);
      }
    }
    if (!selectedService && operatorPreferences.selectedServiceId) {
      const preferredService = services.find((service) => service.id === operatorPreferences.selectedServiceId);
      if (preferredService) {
        setSelectedService(preferredService);
      }
    }
  }, [clusters, nodes, services, operatorPreferences, selectedCluster, selectedNode, selectedService]);

  useEffect(() => {
    if (!selectedNode) return;
    loadNodeMetrics(selectedNode.id, nodeMetricsWindow).catch(console.error);
  }, [selectedNode, nodeMetricsWindow]);

  useEffect(() => {
    if (!selectedService) return;
    loadServiceMetrics(selectedService.id, serviceMetricsWindow).catch(console.error);
  }, [selectedService, serviceMetricsWindow]);

  useEffect(() => {
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    if (!autoPollLogs || !sourceService) return;
    const interval = window.setInterval(() => {
      loadDiagnosticsLive(sourceService, { cursor: 0, silent: true }).catch(() => {
        // Ignore polling failures; explicit refresh can recover.
      });
    }, Math.max(1000, logsPollMs));
    return () => window.clearInterval(interval);
  }, [autoPollLogs, selectedService, diagnosticsSourceServiceId, services, logsPollMs, tailLines, historyPageSize, diagnosticsTargetKey]);

  async function selectCluster(cluster: Cluster) {
    setSelectedCluster(cluster);
    try {
      const summary = await api<ClusterSummary>(`/api/clusters/${cluster.id}/summary`);
      setClusterSummary(summary);
      await loadClusterOperations(cluster.id);
      const clusterNodes = nodes.filter((n) => n.cluster_id === cluster.id);
      if (clusterNodes.length > 0) {
        await selectNode(clusterNodes[0]);
      } else {
        setSelectedNode(null);
        setNodeSummary(null);
        setNodeConnection(null);
        setNodeJobHistory(null);
        setNodeMetrics(null);
        setNodeOnboarding(null);
      }
    } catch (error: any) {
      setNotice(`Failed to load cluster summary: ${error.message}`);
    }
  }

  async function selectNode(node: Node) {
    setSelectedNode(node);
    try {
      const summary = await api<NodeSummary>(`/api/nodes/${node.id}/summary`);
      setNodeSummary(summary);
      await loadNodeConnection(node.id);
      await loadNodeJobHistory(node.id);
      await loadNodeMetrics(node.id);
      await loadNodeOnboarding(node.id);
    } catch (error: any) {
      setNotice(`Failed to load node summary: ${error.message}`);
    }
  }

  async function focusServiceInCluster(serviceId: number) {
    const service = services.find((item) => item.id === serviceId);
    if (!service) {
      setNotice("Service not found in current topology.");
      return;
    }
    const node = nodes.find((item) => item.id === service.node_id);
    const cluster = node ? clusters.find((item) => item.id === node.cluster_id) : null;
    if (cluster) {
      setSelectedCluster(cluster);
    }
    if (node) {
      await selectNode(node);
    }
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
  }

  function openClusterCreate() {
    setClusterEditor({
      visible: true,
      mode: "create",
      clusterId: null,
      draft: { name: "", region: "local", environment: "development" },
      error: "",
    });
  }

  function openClusterEdit(cluster: Cluster) {
    setClusterEditor({
      visible: true,
      mode: "edit",
      clusterId: cluster.id,
      draft: { name: cluster.name, region: cluster.region, environment: cluster.environment },
      error: "",
    });
  }

  async function saveClusterEditor() {
    try {
      const draft = clusterEditor.draft;
      const name = draft.name.trim();
      if (!name) {
        setClusterEditor((current) => ({ ...current, error: "Cluster name is required." }));
        return;
      }
      if (clusterEditor.mode === "create") {
        const created = await api<Cluster>("/api/clusters", {
          method: "POST",
          body: JSON.stringify({ name, region: draft.region.trim() || "local", environment: draft.environment.trim() || "development" }),
        });
        setClusterEditor((current) => ({ ...current, visible: false, error: "" }));
        setNotice(`Created cluster ${created.name}`);
        setSelectedCluster(created);
        await refresh();
        return;
      }
      if (!clusterEditor.clusterId) return;
      const updated = await api<Cluster>(`/api/clusters/${clusterEditor.clusterId}`, {
        method: "PUT",
        body: JSON.stringify({ name, region: draft.region.trim() || "local", environment: draft.environment.trim() || "development" }),
      });
      setClusterEditor((current) => ({ ...current, visible: false, error: "" }));
      setSelectedCluster(updated);
      setNotice(`Updated cluster ${updated.name}`);
      await refresh();
    } catch (error: any) {
      setClusterEditor((current) => ({ ...current, error: error.message || "Failed to save cluster." }));
    }
  }

  function applyNodePreset(preset: "local-default" | "aws-general" | "aws-gpu") {
    setNodePreset(preset);
    setNodeEditor((current) => {
      if (!current.visible) return current;
      if (preset === "aws-general") {
        return {
          ...current,
          draft: {
            ...current.draft,
            environment: "aws",
            ssh_user: "ubuntu",
            host: current.draft.host === "localhost" ? "ec2-public-host" : current.draft.host,
            volume_root: current.draft.volume_root.startsWith("/tmp/") ? "/platformops" : current.draft.volume_root,
            docker_network: current.draft.docker_network === "platformops-net" ? "platformops-net-aws" : current.draft.docker_network,
          },
        };
      }
      if (preset === "aws-gpu") {
        return {
          ...current,
          draft: {
            ...current.draft,
            environment: "aws",
            ssh_user: "ubuntu",
            host: current.draft.host === "localhost" ? "ec2-gpu-host" : current.draft.host,
            volume_root: current.draft.volume_root.startsWith("/tmp/") ? "/platformops-gpu" : current.draft.volume_root,
            docker_network: current.draft.docker_network === "platformops-net" ? "platformops-net-gpu" : current.draft.docker_network,
          },
        };
      }
      return {
        ...current,
        draft: {
          ...current.draft,
          environment: "local",
          ssh_user: "ubuntu",
          host: current.draft.host.includes("ec2") ? "localhost" : current.draft.host,
          volume_root: current.draft.volume_root.startsWith("/platformops") ? "/tmp/platformops" : current.draft.volume_root,
          docker_network: current.draft.docker_network.includes("aws") ? "platformops-net" : current.draft.docker_network,
        },
      };
    });
  }

  function openNodeCreate() {
    const baseClusterId = selectedCluster?.id ?? clusters[0]?.id ?? 0;
    setNodeEditor({
      visible: true,
      mode: "create",
      nodeId: null,
      draft: {
        cluster_id: baseClusterId,
        name: "",
        host: "localhost",
        ssh_user: "ubuntu",
        ssh_key_path: "",
        environment: "local",
        volume_root: "/tmp/platformops",
        docker_network: "platformops-net",
        status: "healthy",
      },
      error: "",
    });
    setNodePreset("local-default");
  }

  function openNodeEdit(node: Node) {
    setNodeEditor({
      visible: true,
      mode: "edit",
      nodeId: node.id,
      draft: {
        cluster_id: node.cluster_id,
        name: node.name,
        host: node.host,
        ssh_user: node.ssh_user,
        ssh_key_path: node.ssh_key_path ?? "",
        environment: node.environment,
        volume_root: node.volume_root,
        docker_network: node.docker_network,
        status: node.status,
      },
      error: "",
    });
    setNodePreset(node.environment === "aws" ? (node.docker_network.includes("gpu") ? "aws-gpu" : "aws-general") : "local-default");
  }

  async function saveNodeEditor() {
    try {
      const draft = nodeEditor.draft;
      const name = draft.name.trim();
      if (!draft.cluster_id) {
        setNodeEditor((current) => ({ ...current, error: "Select a parent cluster." }));
        return null;
      }
      if (!name) {
        setNodeEditor((current) => ({ ...current, error: "Node name is required." }));
        return null;
      }
      if (nodeEditor.mode === "create") {
        const created = await api<Node>("/api/nodes", {
          method: "POST",
          body: JSON.stringify({
            cluster_id: draft.cluster_id,
            name,
            host: draft.host.trim() || "localhost",
            ssh_user: draft.ssh_user.trim() || "ubuntu",
            ssh_key_path: draft.ssh_key_path.trim(),
            environment: draft.environment.trim() || "local",
            volume_root: draft.volume_root.trim() || "/tmp/platformops",
            docker_network: draft.docker_network.trim() || "platformops-net",
          }),
        });
        setNodeEditor((current) => ({ ...current, visible: false, error: "" }));
        setSelectedNode(created);
        setNotice(`Created node ${created.name}`);
        await refresh();
        return created;
      }
      if (!nodeEditor.nodeId) return null;
      const updated = await api<Node>(`/api/nodes/${nodeEditor.nodeId}`, {
        method: "PUT",
        body: JSON.stringify({
          cluster_id: draft.cluster_id,
          name,
          host: draft.host.trim() || "localhost",
          ssh_user: draft.ssh_user.trim() || "ubuntu",
          ssh_key_path: draft.ssh_key_path.trim(),
          environment: draft.environment.trim() || "local",
          volume_root: draft.volume_root.trim() || "/tmp/platformops",
          docker_network: draft.docker_network.trim() || "platformops-net",
          status: draft.status.trim() || "unknown",
        }),
      });
      setNodeEditor((current) => ({ ...current, visible: false, error: "" }));
      setSelectedNode(updated);
      setNotice(`Updated node ${updated.name}`);
      await refresh();
      return updated;
    } catch (error: any) {
      setNodeEditor((current) => ({ ...current, error: error.message || "Failed to save node." }));
      return null;
    }
  }

  async function installCard(card: CatalogCard) {
    const node = selectedNode || nodes[0];
    if (!node) {
      setNotice("Seed a node first with python scripts/seed_demo.py");
      return;
    }
    const service = await api<Service>("/api/services", {
      method: "POST",
      body: JSON.stringify({ node_id: node.id, service_key: card.service_key }),
    });
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    setNotice(`Added ${service.name} to ${node.name}`);
    await refresh();
  }

  function assignContractValue(target: Record<string, any>, key: string, value: unknown) {
    const parts = key.split(".");
    let cursor = target;
    parts.slice(0, -1).forEach((part) => {
      if (!cursor[part] || typeof cursor[part] !== "object" || Array.isArray(cursor[part])) {
        cursor[part] = {};
      }
      cursor = cursor[part];
    });
    cursor[parts[parts.length - 1]] = value;
  }

  function parseInstallFieldValue(field: ServiceInstallField, value: unknown) {
    if (field.key === "name") return value;
    if (field.field_type === "boolean") return Boolean(value);
    if (field.field_type === "number") {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : value;
    }
    if (field.field_type === "list") {
      if (Array.isArray(value)) return value;
      return String(value ?? "")
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return value;
  }

  function installSchemaValues(schema: ServiceInstallSchema | null) {
    if (!schema) return {};
    return Object.fromEntries(schema.fields.map((field) => {
      const value = field.field_type === "list" && Array.isArray(field.value)
        ? (field.value as unknown[]).join("\n")
        : field.value ?? "";
      return [field.key, value];
    }));
  }

  function buildInstallOverrides() {
    const overrides: Record<string, any> = {};
    const schema = catalogOnboarding.installSchema;
    if (schema) {
      schema.fields.forEach((field) => {
        if (field.key === "name") return;
        const value = parseInstallFieldValue(field, catalogOnboarding.installFieldValues[field.key]);
        assignContractValue(overrides, field.key, value);
      });
    }
    const trimmedOverrides = catalogOnboarding.overridesText.trim();
    if (trimmedOverrides) {
      const parsed = JSON.parse(trimmedOverrides);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Overrides must be a JSON object.");
      }
      Object.assign(overrides, parsed as Record<string, unknown>);
    }
    return overrides;
  }

  async function loadInstallSchemaFor(card: CatalogCard, nodeId: number, service?: Service | null) {
    const params = new URLSearchParams({ node_id: String(nodeId) });
    if (service) params.set("service_id", String(service.id));
    const schema = await api<ServiceInstallSchema>(`/api/catalog/services/${card.service_key}/install-schema?${params.toString()}`);
    return schema;
  }

  async function openCatalogOnboarding(card: CatalogCard) {
    const fallbackNode = selectedNode
      ?? (selectedCluster ? nodes.find((item) => item.cluster_id === selectedCluster.id) ?? nodes[0] : nodes[0]);
    if (!fallbackNode) {
      setNotice("Provision a node first before onboarding a service card.");
      return;
    }
    const defaultOverrides: Record<string, unknown> = {};
    const schema = await loadInstallSchemaFor(card, fallbackNode.id);
    setCatalogOnboarding({
      visible: true,
      mode: "create",
      card,
      editingService: null,
      installSchema: schema,
      installFieldValues: installSchemaValues(schema),
      nodeId: fallbackNode.id,
      customName: "",
      nextAction: card.configurable ? "config" : "deploy",
      overridesText: JSON.stringify(defaultOverrides, null, 2),
      creating: false,
      error: "",
      registeredService: null,
    });
  }

  async function openServiceEditor(service: Service) {
    const card = catalog.find((item) => item.service_key === service.service_key);
    if (!card) {
      setNotice(`Catalog definition for ${service.service_key} is not available.`);
      return;
    }
    const schema = await loadInstallSchemaFor(card, service.node_id, service);
    setCatalogOnboarding({
      visible: true,
      mode: "edit",
      card,
      editingService: service,
      installSchema: schema,
      installFieldValues: installSchemaValues(schema),
      nodeId: service.node_id,
      customName: service.name,
      nextAction: "overview",
      overridesText: "",
      creating: false,
      error: "",
      registeredService: null,
    });
  }

  async function confirmCatalogOnboarding() {
    const card = catalogOnboarding.card;
    if (!card) {
      setCatalogOnboarding((current) => ({ ...current, error: "No catalog card selected." }));
      return;
    }
    const node = nodes.find((item) => item.id === catalogOnboarding.nodeId);
    if (!node) {
      setCatalogOnboarding((current) => ({ ...current, error: "Choose a valid target node." }));
      return;
    }
    let contractOverrides: Record<string, unknown> = {};
    try {
      contractOverrides = buildInstallOverrides();
    } catch (error: any) {
      setCatalogOnboarding((current) => ({ ...current, error: `Invalid install configuration: ${error.message}` }));
      return;
    }
    setCatalogOnboarding((current) => ({ ...current, creating: true, error: "" }));
    try {
      const existing = services.find((service) => service.node_id === node.id && service.service_key === card.service_key);
      const targetService = catalogOnboarding.editingService;
      const payload = {
        node_id: node.id,
        service_key: card.service_key,
        name: catalogOnboarding.customName.trim() || undefined,
        contract_overrides: contractOverrides,
      };
      const service = targetService
        ? await api<Service>(`/api/services/${targetService.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              name: catalogOnboarding.customName.trim() || undefined,
              contract_overrides: contractOverrides,
            }),
          })
        : existing ?? await api<Service>("/api/services", {
            method: "POST",
            body: JSON.stringify(payload),
          });
      setSelectedNode(node);
      setSelectedService(service);
      await loadServiceCapabilities(service.id);
      await loadServiceSummary(service.id);
      await loadServiceReleaseTimeline(service.id);
      await loadServiceMetrics(service.id);
      if (!existing) {
        await refresh();
      }
      setCatalogOnboarding((current) => ({ ...current, creating: false, error: "", registeredService: service }));
      setCatalogDrawerVisible(false);
      await loadNodeJobHistory(node.id);
      if (catalogOnboarding.nextAction === "config") {
        await loadConfig(service, configSource);
        setActiveView("config");
        setCatalogOnboarding((current) => ({ ...current, visible: false }));
        setNotice(`Registered ${service.name} on ${node.name} and opened config manager.`);
        return;
      }
      if (catalogOnboarding.nextAction === "deploy") {
        await openDeploymentModal(service);
        setCatalogOnboarding((current) => ({ ...current, visible: false }));
        setNotice(`Registered ${service.name} on ${node.name} and opened deployment control.`);
        return;
      }
      setNotice(targetService ? `Updated ${service.name} install configuration.` : existing ? `Selected existing ${service.name} on ${node.name}.` : `Registered ${service.name} on ${node.name}.`);
    } catch (error: any) {
      setCatalogOnboarding((current) => ({
        ...current,
        creating: false,
        error: error.message || "Failed to onboard service card.",
      }));
    }
  }

  async function openDeploymentModal(service: Service) {
    const node = nodes.find((item) => item.id === service.node_id);
    setSelectedService(service);
    setDeploymentModal({
      visible: true,
      serviceId: service.id,
      serviceName: service.name,
      nodeName: node?.name ?? `node-${service.node_id}`,
      preflight: null,
      autoInstallDependencies: true,
      loading: true,
      executing: false,
      error: "",
      result: null,
    });
    try {
      const [nextPlan, preflight] = await Promise.all([
        api<DeploymentPlan>(`/api/nodes/${service.node_id}/deployment-plan/${service.service_key}`),
        api<{ ok: boolean; message: string; missing: string[]; stopped: string[]; required: string[] }>(
          `/api/services/${service.id}/preflight`,
          { method: "POST" },
        ),
      ]);
      setPlan(nextPlan);
      setDeploymentModal((current) => ({
        ...current,
        loading: false,
        preflight,
      }));
    } catch (error: any) {
      setDeploymentModal((current) => ({
        ...current,
        loading: false,
        error: error.message || "Failed to open deployment control.",
      }));
    }
  }

  async function executeDeploymentModal() {
    if (!deploymentModal.serviceId) {
      setDeploymentModal((current) => ({ ...current, error: "No service selected for deployment." }));
      return;
    }
    const service = services.find((item) => item.id === deploymentModal.serviceId);
    if (!service) {
      setDeploymentModal((current) => ({ ...current, error: "Selected service is no longer available." }));
      return;
    }
    setDeploymentModal((current) => ({ ...current, executing: true, error: "" }));
    try {
      const result = await api<DeploymentExecuteResult>(`/api/services/${service.id}/deployment/execute`, {
        method: "POST",
        body: JSON.stringify({ auto_install_dependencies: deploymentModal.autoInstallDependencies }),
      });
      setPlan(result.plan);
      setDeploymentModal((current) => ({
        ...current,
        executing: false,
        preflight: result.preflight_after,
        result,
      }));
      if (result.target_job) {
        setJob(result.target_job);
      }
      setNotice(result.summary);
      await refresh();
      await loadNodeJobHistory(service.node_id);
      await loadServiceSummary(service.id);
    } catch (error: any) {
      setDeploymentModal((current) => ({
        ...current,
        executing: false,
        error: error.message || "Deployment execution failed.",
      }));
    }
  }

  async function installMissingDependencies(service: Service) {
    try {
      const result = await api<DependencyInstallResult>(`/api/services/${service.id}/dependencies/install-missing`, {
        method: "POST",
      });
      const actionCount = result.dependency_actions.length;
      const nextPlan = await api<DeploymentPlan>(`/api/nodes/${service.node_id}/deployment-plan/${service.service_key}`);
      const preflight = await api<{ ok: boolean; message: string; missing: string[]; stopped: string[]; required: string[] }>(
        `/api/services/${service.id}/preflight`,
        { method: "POST" },
      );
      setPlan(nextPlan);
      setDeploymentModal((current) => current.serviceId === service.id ? {
        ...current,
        preflight,
        result: current.result
          ? {
              ...current.result,
              plan: nextPlan,
              preflight_after: preflight,
              dependency_actions: result.dependency_actions,
              summary: result.summary,
            }
          : null,
      } : current);
      setNotice(`${result.summary} (${actionCount} actions)`);
      await refresh();
      await loadNodeJobHistory(service.node_id);
      await loadServiceSummary(service.id);
    } catch (error: any) {
      setNotice(`Dependency install failed: ${error.message}`);
    }
  }

  async function openDependencyTarget(serviceKey: string, mode: DependencyTargetActionMode) {
    if (!selectedService) {
      setNotice("Select a service first.");
      return;
    }
    const nodeId = selectedService.node_id;
    let target = services.find((service) => service.node_id === nodeId && service.service_key === serviceKey);
    if (!target && mode === "ensure") {
      target = await api<Service>("/api/services", {
        method: "POST",
        body: JSON.stringify({ node_id: nodeId, service_key: serviceKey }),
      });
      setNotice(`Created dependency card ${target.name} on node.`);
      await refresh();
    }
    if (!target) {
      setNotice(`Dependency card ${serviceKey} is not installed on this node.`);
      return;
    }
    if (mode === "config") {
      setSelectedService(target);
      await loadServiceCapabilities(target.id);
      await loadConfig(target, configSource);
      return;
    }
    if (mode === "diagnostics") {
      await loadDiagnostics(selectedService, { targetServiceKey: serviceKey, preserveSelection: true });
      return;
    }
    setSelectedService(target);
    await loadServiceCapabilities(target.id);
    await loadServiceSummary(target.id);
    await loadServiceReleaseTimeline(target.id);
    await loadServiceMetrics(target.id);
    setNotice(`Selected dependency card ${target.name}`);
  }

  async function ensureMissingDependencyCards() {
    if (!selectedService || !diagnostics?.readiness.dependency_targets) {
      setNotice("Load diagnostics first to evaluate dependency cards.");
      return;
    }
    const missingTargets = diagnostics.readiness.dependency_targets.filter((target) => !target.on_node);
    if (missingTargets.length === 0) {
      setNotice("All dependency cards are already present on this node.");
      return;
    }
    for (const target of missingTargets) {
      await api<Service>("/api/services", {
        method: "POST",
        body: JSON.stringify({ node_id: selectedService.node_id, service_key: target.service_key }),
      });
    }
    setNotice(`Ensured ${missingTargets.length} missing dependency card(s).`);
    await refresh();
    await loadDiagnostics(selectedService);
  }

  async function requestDelete(
    type: "service" | "node" | "cluster",
    id: number,
    name: string,
    options?: { seedForce?: boolean; suggestedReason?: string }
  ) {
    try {
      setNotice(`Assessing deletion impact for ${name}...`);
      const impact = await api<LifecycleImpact>(
        `/api/${type === "service" ? "services" : type === "node" ? "nodes" : "clusters"}/${id}/lifecycle-impact`
      );
      setDeleteModal({
        visible: true,
        targetType: type,
        targetId: id,
        targetName: name,
        impact,
        force: Boolean(options?.seedForce),
        forceReason: options?.suggestedReason ?? "",
        forceApprovalId: "",
        requestedBy: "platform-operator",
        approver: "platform-admin",
        decisionNote: "",
        approvalStatus: "none",
      });
    } catch (error: any) {
      setNotice(`Failed to load deletion safety assessment: ${error.message}`);
    }
  }

  async function confirmDelete() {
    const { targetType, targetId, targetName, force, forceReason, forceApprovalId } = deleteModal;
    try {
      if (force && forceReason.trim().length < 12) {
        setNotice("Force delete requires a reason of at least 12 characters.");
        return;
      }

      const reasonParam = force ? `&force_reason=${encodeURIComponent(forceReason.trim())}` : "";
      const approvalParam = force ? `&force_approval_id=${encodeURIComponent(forceApprovalId || "")}` : "";
      let endpoint = "";
      if (targetType === "service") {
        endpoint = `/api/services/${targetId}/delete?force=${force}${reasonParam}${approvalParam}`;
      } else if (targetType === "node") {
        endpoint = `/api/nodes/${targetId}?force=${force}${reasonParam}${approvalParam}`;
      } else if (targetType === "cluster") {
        endpoint = `/api/clusters/${targetId}?force=${force}${reasonParam}${approvalParam}`;
      }

      const result = await api<any>(endpoint, { method: targetType === "service" ? "POST" : "DELETE" });

      if (targetType === "service") {
        setJob(result);
        setNotice(`Delete service ${targetName} job started: ${result.status}`);
      } else {
        setNotice(`Deleted ${targetType} ${targetName} successfully.`);
      }

      setDeleteModal((prev) => ({ ...prev, visible: false }));
      if (selectedService?.id === targetId && targetType === "service") {
        setSelectedService(null);
        setCapabilities(null);
      }
      await refresh();
    } catch (error: any) {
      setNotice(`Delete failed: ${error.message}`);
    }
  }

  async function requestForceDeleteApproval() {
    const { targetType, targetId, forceReason, requestedBy } = deleteModal;
    if (forceReason.trim().length < 12) {
      setNotice("Approval request reason must be at least 12 characters.");
      return;
    }
    const approval = await api<ForceDeleteApproval>("/api/lifecycle/force-approvals", {
      method: "POST",
      body: JSON.stringify({
        target_type: targetType,
        target_id: targetId,
        reason: forceReason.trim(),
        requested_by: requestedBy.trim() || "platform-operator",
        ttl_hours: 4,
      }),
    });
    setDeleteModal((prev) => ({ ...prev, forceApprovalId: String(approval.id), approvalStatus: approval.status }));
    setNotice(`Approval request created: #${approval.id} (${approval.status})`);
    await refresh();
  }

  async function approveForceDeleteApproval() {
    const approvalId = Number(deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setNotice("Enter a valid approval id before approving.");
      return;
    }
    const approval = await api<ForceDeleteApproval>(`/api/lifecycle/force-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: deleteModal.approver.trim() || "platform-admin",
        decision_note: deleteModal.decisionNote.trim(),
        status: "approved",
      }),
    });
    setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: true }));
    setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await refresh();
  }

  async function rejectForceDeleteApproval() {
    const approvalId = Number(deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setNotice("Enter a valid approval id before rejecting.");
      return;
    }
    const approval = await api<ForceDeleteApproval>(`/api/lifecycle/force-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: deleteModal.approver.trim() || "platform-admin",
        decision_note: deleteModal.decisionNote.trim(),
        status: "rejected",
      }),
    });
    setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: false }));
    setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await refresh();
  }

  async function revokeForceDeleteApproval() {
    const approvalId = Number(deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setNotice("Enter a valid approval id before revoking.");
      return;
    }
    const approval = await api<ForceDeleteApproval>(`/api/lifecycle/force-approvals/${approvalId}/revoke`, {
      method: "POST",
      body: JSON.stringify({
        actor: deleteModal.approver.trim() || "platform-admin",
        note: deleteModal.decisionNote.trim(),
      }),
    });
    setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: false }));
    setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await refresh();
  }

  async function backupService(service: Service) {
    const backup = await api<{ status: string; artifact_path: string }>(`/api/services/${service.id}/backup`, { method: "POST" });
    setNotice(`Backup ${backup.status}: ${backup.artifact_path}`);
    await refresh();
  }

  async function registerSecret(service: Service) {
    const secret = await api<SecretRecord>("/api/secrets", {
      method: "POST",
      body: JSON.stringify({
        service_id: service.id,
        key: `${service.service_key.toUpperCase().replace(/-/g, "_")}_TOKEN`,
        scope: "service",
        rotation_interval_days: 90,
      }),
    });
    setSecrets((current) => [secret, ...current]);
    setNotice(`Registered masked secret ${secret.key}`);
    await refresh();
  }

  async function rotateSecret(secret: SecretRecord) {
    const rotated = await api<SecretRecord>(`/api/secrets/${secret.id}/rotate`, { method: "POST" });
    setSecrets((current) => current.map((item) => (item.id === rotated.id ? rotated : item)));
    setNotice(`Rotated ${rotated.key}`);
    await refresh();
  }

  async function scheduleMaintenance(service?: Service) {
    const starts = new Date(Date.now() + 60 * 60 * 1000);
    const ends = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const window = await api<MaintenanceWindow>("/api/maintenance", {
      method: "POST",
      body: JSON.stringify({
        service_id: service?.id ?? selectedService?.id ?? null,
        node_id: service?.node_id ?? selectedService?.node_id ?? selectedNode?.id ?? nodes[0]?.id ?? null,
        title: `Maintenance for ${service?.name ?? selectedService?.name ?? "platform"}`,
        starts_at: starts.toISOString(),
        ends_at: ends.toISOString(),
        impact: "Portfolio-safe simulated maintenance window",
      }),
    });
    setMaintenance((current) => [window, ...current]);
    setNotice(`Scheduled maintenance ${window.id}`);
    await refresh();
  }

  async function completeMaintenance(window: MaintenanceWindow) {
    const completed = await api<MaintenanceWindow>(`/api/maintenance/${window.id}/complete`, { method: "POST" });
    setMaintenance((current) => current.map((item) => (item.id === completed.id ? completed : item)));
    setNotice(`Completed maintenance ${completed.id}`);
    await refresh();
  }

  async function createAuditExport() {
    const exportRecord = await api<AuditExport>("/api/audit/exports", { method: "POST" });
    setNotice(`Audit export ready: ${exportRecord.artifact_path}`);
    await refresh();
  }

  async function requestReleaseSafety(service: Service, version: string, image: string) {
    return api<ReleaseSafety>(
      `/api/services/${service.id}/releases/safety?version=${encodeURIComponent(version)}&image=${encodeURIComponent(image)}`,
    );
  }

  function openReleaseApprovalModal(service: Service, version: string, image: string, safety: ReleaseSafety) {
    setReleaseApprovalModal({
      visible: true,
      serviceId: service.id,
      serviceName: service.name,
      version,
      image,
      safety,
      reason: "",
      requestedBy: "platform-operator",
      approvalId: "",
      approver: "platform-admin",
      decisionNote: "",
      error: "",
    });
  }

  async function createReleaseApprovalRequest() {
    const reason = releaseApprovalModal.reason.trim();
    if (reason.length < 12) {
      setReleaseApprovalModal((current) => ({ ...current, error: "Approval reason must be at least 12 characters." }));
      return;
    }
    const approval = await api<ReleaseApproval>("/api/release-approvals", {
      method: "POST",
      body: JSON.stringify({
        service_id: releaseApprovalModal.serviceId,
        target_version: releaseApprovalModal.version,
        target_image: releaseApprovalModal.image,
        reason,
        requested_by: releaseApprovalModal.requestedBy.trim() || "platform-operator",
        ttl_hours: 4,
      }),
    });
    setReleaseApprovalModal((current) => ({ ...current, approvalId: String(approval.id), error: "" }));
    setNotice(`Release approval #${approval.id} created (${approval.status}).`);
    await refresh();
  }

  async function approveReleaseApprovalRequest() {
    const approvalId = Number(releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setReleaseApprovalModal((current) => ({ ...current, error: "Enter a valid approval id before approving." }));
      return;
    }
    const approval = await api<ReleaseApproval>(`/api/release-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: releaseApprovalModal.approver.trim() || "platform-admin",
        decision_note: releaseApprovalModal.decisionNote.trim(),
        status: "approved",
      }),
    });
    setReleaseApprovalModal((current) => ({ ...current, error: "" }));
    setNotice(`Release approval #${approval.id} is now ${approval.status}.`);
    await refresh();
  }

  async function revokeReleaseApprovalRequest() {
    const approvalId = Number(releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setReleaseApprovalModal((current) => ({ ...current, error: "Enter a valid approval id before revoking." }));
      return;
    }
    const approval = await api<ReleaseApproval>(`/api/release-approvals/${approvalId}/revoke`, {
      method: "POST",
      body: JSON.stringify({
        actor: releaseApprovalModal.approver.trim() || "platform-admin",
        note: releaseApprovalModal.decisionNote.trim(),
      }),
    });
    setReleaseApprovalModal((current) => ({ ...current, error: "" }));
    setNotice(`Release approval #${approval.id} is now ${approval.status}.`);
    await refresh();
  }

  async function confirmApprovedRelease() {
    const approvalId = Number(releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      setReleaseApprovalModal((current) => ({ ...current, error: "Provide an approved approval id before releasing." }));
      return;
    }
    const service = services.find((item) => item.id === releaseApprovalModal.serviceId);
    if (!service) {
      setReleaseApprovalModal((current) => ({ ...current, error: "Selected service is no longer available." }));
      return;
    }
    const release = await api<ReleaseRecord>(`/api/services/${service.id}/releases`, {
      method: "POST",
      body: JSON.stringify({
        version: releaseApprovalModal.version,
        image: releaseApprovalModal.image,
        strategy: "rolling",
        notes: "UI-triggered governed release",
        approval_id: approvalId,
      }),
    });
    setReleases((current) => [release, ...current]);
    setReleaseApprovalModal((current) => ({ ...current, visible: false, error: "" }));
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    setNotice(`Governed release ${release.version} ${release.status}`);
    await refresh();
  }

  async function releaseService(service: Service) {
    const version = `v${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
    const safety = await requestReleaseSafety(service, version, service.image);
    if (safety.risky) {
      openReleaseApprovalModal(service, version, service.image, safety);
      setNotice(`Release for ${service.name} requires approval.`);
      return;
    }
    const release = await api<ReleaseRecord>(`/api/services/${service.id}/releases`, {
      method: "POST",
      body: JSON.stringify({
        version,
        image: service.image,
        strategy: "rolling",
        notes: "UI-triggered portfolio release",
      }),
    });
    setReleases((current) => [release, ...current]);
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    setNotice(`Release ${release.version} ${release.status}`);
    await refresh();
  }

  async function loadReleases(service: Service) {
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    const nextReleases = await api<ReleaseRecord[]>(`/api/services/${service.id}/releases`);
    setReleases(nextReleases);
    setNotice(`Loaded ${nextReleases.length} releases for ${service.name}`);
  }

  async function rollbackRelease(release: ReleaseRecord) {
    const nextJob = await api<Job>(`/api/releases/${release.id}/rollback`, { method: "POST" });
    setJob(nextJob);
    setNotice(`Rollback ${nextJob.status}`);
    if (selectedService) {
      await loadServiceSummary(selectedService.id);
      await loadServiceReleaseTimeline(selectedService.id);
      await loadServiceMetrics(selectedService.id);
    }
    await refresh();
  }

  async function planService(service: Service) {
    const node = nodes.find((item) => item.id === service.node_id);
    if (!node) return;
    const nextPlan = await api<DeploymentPlan>(`/api/nodes/${node.id}/deployment-plan/${service.service_key}`);
    setPlan(nextPlan);
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    setNotice(nextPlan.summary);
  }

  async function planPlacement(serviceKey?: string) {
    const targetKey = serviceKey || selectedPlacementServiceKey || selectedService?.service_key;
    if (!targetKey) {
      setNotice("Select a service key for placement recommendations.");
      return;
    }
    const params = new URLSearchParams();
    if (preferNodeId.trim()) params.set("prefer_node_id", preferNodeId.trim());
    if (avoidNodeIds.trim()) params.set("avoid_node_ids", avoidNodeIds.trim());
    if (antiAffinityKey.trim()) params.set("anti_affinity_service_key", antiAffinityKey.trim());
    if (requireHealthyNodes) params.set("require_healthy", "true");
    if (spreadSubsystem) params.set("spread_subsystem", "true");
    const nextPlacement = await api<PlacementRecommendation>(
      `/api/services/placement/recommendations/${targetKey}?${params.toString()}`,
    );
    setPlacement(nextPlacement);
    setSelectedPlacementServiceKey(targetKey);
    const best = nextPlacement.candidates[0];
    if (best) {
      setNotice(`Placement advisor: best node for ${targetKey} is ${best.node_name} (score ${best.score}).`);
    }
  }

  async function deployFromPlacement(serviceKey?: string) {
    const targetKey = serviceKey || selectedPlacementServiceKey || selectedService?.service_key;
    if (!targetKey) {
      setNotice("Select a service key for placement auto-deploy.");
      return;
    }
    const params = new URLSearchParams();
    if (preferNodeId.trim()) params.set("prefer_node_id", preferNodeId.trim());
    if (avoidNodeIds.trim()) params.set("avoid_node_ids", avoidNodeIds.trim());
    if (antiAffinityKey.trim()) params.set("anti_affinity_service_key", antiAffinityKey.trim());
    if (requireHealthyNodes) params.set("require_healthy", "true");
    if (spreadSubsystem) params.set("spread_subsystem", "true");
    if (!autoInstallDependencies) params.set("auto_install_dependencies", "false");
    if (allowPlacementCapacityRisk) params.set("allow_capacity_risk", "true");
    const result = await api<PlacementDeployResult>(
      `/api/services/placement/deploy/${targetKey}?${params.toString()}`,
      { method: "POST" },
    );
    setNotice(result.summary);
    await refresh();
    const nextServices = await api<Service[]>(`/api/services?node_id=${result.node_id}`);
    const deployed = nextServices.find((service) => service.id === result.target_service_id);
    if (deployed) {
      setSelectedService(deployed);
      await loadServiceCapabilities(deployed.id);
      await loadServiceMetrics(deployed.id);
      await loadDiagnostics(deployed);
      await loadConfig(deployed);
    }
    await planPlacement(targetKey);
  }

  async function loadArtifact(kind: "inventory" | "compose") {
    const node = selectedNode || nodes[0];
    if (!node) {
      setNotice("No node selected for artifact generation");
      return;
    }
    const nextArtifact = await api<GeneratedArtifact>(`/api/nodes/${node.id}/artifacts/${kind}`);
    setArtifact(nextArtifact);
    setNotice(`Generated ${nextArtifact.name}`);
  }

  async function runMonitoringSweep() {
    const nextChecks = await api<MonitoringCheck[]>("/api/monitoring/sweep", { method: "POST" });
    setChecks(nextChecks);
    setNotice(`Recorded ${nextChecks.length} monitoring checks`);
    await refresh();
  }

  async function runPolicyScan() {
    const nextFindings = await api<PolicyFinding[]>("/api/policy/scan", { method: "POST" });
    setFindings(nextFindings);
    setNotice(`Policy scan found ${nextFindings.length} open findings`);
    await refresh();
  }

  async function evaluateSlo() {
    const reports = await api<SloReport[]>("/api/slo/evaluate", { method: "POST" });
    setSlos(reports);
    setNotice(`Evaluated ${reports.length} SLO reports`);
    await refresh();
  }

  async function generateCapacity() {
    const node = selectedNode || nodes[0];
    if (!node) {
      setNotice("No node available for capacity report");
      return;
    }
    const report = await api<CapacityReport>(`/api/nodes/${node.id}/capacity`, { method: "POST" });
    setCapacity((current) => [report, ...current]);
    setNotice(`Capacity ${report.status}: ${report.memory_reserved_mb} MB reserved`);
    await refresh();
  }

  async function openIncident(service?: Service) {
    const payload = {
      service_id: service?.id ?? selectedService?.id ?? null,
      node_id: service?.node_id ?? selectedService?.node_id ?? selectedNode?.id ?? nodes[0]?.id ?? null,
      title: `Investigate ${service?.name ?? selectedService?.name ?? "platform"} health`,
      severity: "sev3",
      summary: "UI-triggered reliability review",
    };
    const incident = await api<IncidentRecord>("/api/incidents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setIncidents((current) => [incident, ...current]);
    setNotice(`Opened incident ${incident.id}`);
    await refresh();
  }

  async function runIncidentRunbook(incident: IncidentRecord, runbookKey: string = "restart-service") {
    const runbook = await api<RunbookExecution>(`/api/incidents/${incident.id}/runbook/${runbookKey}`, {
      method: "POST",
    });
    setRunbooks((current) => [runbook, ...current]);
    setNotice(`Runbook ${runbook.runbook_key} ${runbook.status}`);
    await refresh();
  }

  async function resolveIncident(incident: IncidentRecord) {
    const resolved = await api<IncidentRecord>(`/api/incidents/${incident.id}/resolve`, { method: "POST" });
    setIncidents((current) => current.map((item) => (item.id === resolved.id ? resolved : item)));
    setNotice(`Resolved incident ${resolved.id}`);
    await refresh();
  }

  async function loadDiagnostics(
    service: Service,
    options?: { targetServiceKey?: string; preserveSelection?: boolean },
  ) {
    if (!options?.preserveSelection) {
      setSelectedService(service);
    }
    const targetServiceKey = options?.targetServiceKey ?? service.service_key;
    setDiagnosticsSourceServiceId(service.id);
    setDiagnosticsTargetKey(targetServiceKey);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    const params = new URLSearchParams();
    if (targetServiceKey) params.set("target_service_key", targetServiceKey);
    const diagnosticsPath = `/api/services/${service.id}/diagnostics${params.toString() ? `?${params.toString()}` : ""}`;
    const analysisPath = `/api/services/${service.id}/diagnostics/analysis${params.toString() ? `?${params.toString()}` : ""}`;
    const [nextDiagnostics, nextAnalysis, nextTargets] = await Promise.all([
      api<Diagnostics>(diagnosticsPath),
      api<DiagnosticsAnalysis>(analysisPath),
      api<DiagnosticsTarget[]>(`/api/services/${service.id}/diagnostics/targets`),
    ]);
    const targetServiceId = nextTargets.find((item) => item.service_key === nextDiagnostics.target_service_key)?.service_id ?? service.id;
    const nextArchives = await api<LogArchive[]>(`/api/services/${targetServiceId}/diagnostics/archives`);
    setDiagnosticsTargets(nextTargets);
    setDiagnostics(nextDiagnostics);
    setDiagnosticsAnalysis(nextAnalysis);
    setArchives(nextArchives);
    await loadDiagnosticsLive(service, {
      cursor: 0,
      targetServiceKey: nextDiagnostics.target_service_key,
    });
  }

  async function focusDiagnosticsTarget(serviceKey: string) {
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    if (!sourceService) {
      setNotice("Select a service first to inspect diagnostics targets.");
      return;
    }
    await loadDiagnostics(sourceService, { targetServiceKey: serviceKey, preserveSelection: true });
  }

  async function loadDiagnosticsLive(
    service: Service,
    options?: { cursor?: number; append?: boolean; silent?: boolean; targetServiceKey?: string },
  ) {
    const cursor = options?.cursor ?? 0;
    const params = new URLSearchParams({
      tail_lines: String(tailLines),
      page_size: String(historyPageSize),
      cursor: String(cursor),
    });
    const targetServiceKey = options?.targetServiceKey ?? diagnosticsTargetKey;
    if (targetServiceKey) params.set("target_service_key", targetServiceKey);
    const next = await api<DiagnosticsLive>(`/api/services/${service.id}/diagnostics/live?${params.toString()}`);
    if (!options?.silent) {
      setNotice(
        `Diagnostics ${next.source_state}: ${next.lines.length} lines · showing ${next.next_cursor}/${next.total_available}`,
      );
    }
    setLogsPollMs(next.poll_interval_ms);
    if (options?.append && diagnosticsLive) {
      setDiagnosticsLive({
        ...next,
        lines: [...diagnosticsLive.lines, ...next.lines],
      });
      return;
    }
    setDiagnosticsLive(next);
  }

  async function runLogBackfill() {
    if (!selectedService) return;
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    const targetKey = diagnostics?.target_service_key ?? diagnosticsTargetKey;
    const target = targetKey
      ? services.find((service) => service.node_id === sourceService.node_id && service.service_key === targetKey)
      : sourceService;
    const result = await api<{ ready: boolean; requirements: any; job: Job }>(`/api/services/${target?.id ?? sourceService.id}/diagnostics/backfill`, {
      method: "POST",
    });
    setJob(result.job);
    setNotice(`Log backfill job #${result.job.id} completed. Status: ${result.job.status}`);
    await loadDiagnostics(sourceService, { targetServiceKey: targetKey, preserveSelection: true });
  }

  async function loadConfigSnapshots(
    service: Service,
    options?: { offset?: number; append?: boolean; source?: string; search?: string; limit?: number },
  ) {
    const nextOffset = options?.offset ?? 0;
    const nextSource = options?.source ?? snapshotSourceFilter;
    const nextSearch = options?.search ?? snapshotSearch;
    const nextLimit = options?.limit ?? snapshotLimit;
    const params = new URLSearchParams({
      offset: String(nextOffset),
      limit: String(nextLimit),
      source: nextSource,
      search: nextSearch,
    });
    const next = await api<ConfigSnapshotPage>(`/api/services/${service.id}/config/snapshots?${params.toString()}`);
    if (options?.append && snapshotPage) {
      setSnapshotPage({
        ...next,
        items: [...snapshotPage.items, ...next.items],
      });
      return;
    }
    setSnapshotPage(next);
  }

  async function loadConfig(service: Service, source: "live" | "latest_snapshot" = configSource) {
    setSelectedService(service);
    await loadServiceCapabilities(service.id);
    await loadServiceSummary(service.id);
    await loadServiceReleaseTimeline(service.id);
    await loadServiceMetrics(service.id);
    const [next] = await Promise.all([
      api<ConfigWorkspace>(`/api/services/${service.id}/config?source=${source}`),
      loadConfigTimeline(service.id, { offset: 0, silent: true }),
    ]);
    setConfig(next);
    setConfigSource(source);
    await loadConfigSnapshots(service, { offset: 0 });
    setSnapshotCompare(null);
    setNotice(next.message || `Loaded ${source} config for ${service.name}`);
  }

  async function compareSelectedSnapshots() {
    if (!selectedService || !compareSnapshotLeft || !compareSnapshotRight) return;
    const next = await api<ConfigSnapshotCompare>(
      `/api/services/${selectedService.id}/config/compare?left_snapshot_id=${compareSnapshotLeft}&right_snapshot_id=${compareSnapshotRight}`,
    );
    setSnapshotCompare(next);
    setNotice(next.summary);
  }

  async function compareSpecificSnapshots(service: Service, leftSnapshotId: number | null, rightSnapshotId: number | null) {
    if (!leftSnapshotId || !rightSnapshotId) {
      setNotice("Snapshot compare needs both baseline and target snapshot ids.");
      return;
    }
    setCompareSnapshotLeft(leftSnapshotId);
    setCompareSnapshotRight(rightSnapshotId);
    const next = await api<ConfigSnapshotCompare>(
      `/api/services/${service.id}/config/compare?left_snapshot_id=${leftSnapshotId}&right_snapshot_id=${rightSnapshotId}`,
    );
    setSnapshotCompare(next);
    setNotice(next.summary);
  }

  async function detectConfigDrift() {
    if (!selectedService) return;
    const report = await api<DriftReport>(`/api/services/${selectedService.id}/config/drift`, {
      method: "POST",
    });
    setDrift(report);
    setNotice(`Drift status: ${report.status}`);
    await refresh();
  }

  async function captureSnapshot() {
    if (!selectedService) return;
    await api(`/api/services/${selectedService.id}/config/snapshots`, {
      method: "POST",
      body: JSON.stringify({ source: "ui-capture", requested_by: "platform-operator" }),
    });
    await loadConfig(selectedService, configSource);
    setNotice("Captured configuration snapshot");
  }

  async function applyCurrentConfig() {
    if (!selectedService || !config) return;
    const result = await api<{ job: Job; before_snapshot: ConfigSnapshotItem; after_snapshot: ConfigSnapshotItem }>(`/api/services/${selectedService.id}/config/direct-apply`, {
      method: "POST",
      body: JSON.stringify({ content: config.content, apply_mode: "reload" }),
    });
    setJob(result.job);
    setNotice(`Config apply ${result.job.status}: checkpoint v${result.before_snapshot.version} -> v${result.after_snapshot.version}`);
    await loadConfig(selectedService, configSource);
    await refresh();
  }

  async function prepareConfigMigration() {
    if (!selectedService || !compareSnapshotLeft || !compareSnapshotRight) {
      setNotice("Choose baseline and target snapshots before preparing migration.");
      return;
    }
    const prepared = await api<ConfigMigrationPrepare>(`/api/services/${selectedService.id}/config/migration/prepare`, {
      method: "POST",
      body: JSON.stringify({
        left_snapshot_id: compareSnapshotLeft,
        right_snapshot_id: compareSnapshotRight,
      }),
    });
    setMigrationArtifactId(prepared.artifact_id);
    setMigrationContent(prepared.final_content);
    setMigrationValidation(prepared.validation.message);
    setMigrationApplyResult(null);
    setNotice(`Prepared migration artifact ${prepared.artifact_id}`);
  }

  async function validateMigrationYaml() {
    if (!selectedService || !migrationContent.trim()) {
      setMigrationValidation("Prepare or paste migration YAML first.");
      return;
    }
    const validation = await api<{ ok: boolean; message: string }>(`/api/services/${selectedService.id}/config/validate`, {
      method: "POST",
      body: JSON.stringify({ content: migrationContent }),
    });
    setMigrationValidation(validation.message);
    setNotice(validation.message);
  }

  async function applyPreparedMigration() {
    if (!selectedService || !migrationArtifactId) {
      setNotice("Prepare a migration artifact first.");
      return;
    }
    const result = await api<ConfigMigrationApply>(`/api/services/${selectedService.id}/config/migration/apply`, {
      method: "POST",
      body: JSON.stringify({ artifact_id: migrationArtifactId, content: migrationContent, requested_by: "platform-operator" }),
    });
    setMigrationApplyResult(result);
    setJob(result.job);
    setNotice(`Migration apply ${result.job.status}`);
    await loadConfig(selectedService, configSource);
    await refresh();
  }

  async function restorePreparedMigration() {
    if (!selectedService || !migrationArtifactId) {
      setNotice("No migration artifact has a backup checkpoint yet.");
      return;
    }
    const result = await api<ConfigMigrationApply>(`/api/services/${selectedService.id}/config/migration/restore`, {
      method: "POST",
      body: JSON.stringify({ artifact_id: migrationArtifactId, requested_by: "platform-operator" }),
    });
    setMigrationApplyResult(result);
    setJob(result.job);
    setNotice(`Migration restore ${result.job.status}`);
    await loadConfig(selectedService, configSource);
    await refresh();
  }

  function openRenameSnapshot(snapshotId: number, currentName: string) {
    setRenameModal({
      visible: true,
      snapshotId,
      value: currentName,
      error: "",
    });
  }

  async function renameSnapshot() {
    if (!selectedService) return;
    const trimmed = renameModal.value.trim();
    if (!trimmed) {
      setRenameModal((current) => ({ ...current, error: "Snapshot name cannot be empty." }));
      return;
    }
    const conflicts = (snapshotPage?.items ?? []).some(
      (snapshot) =>
        snapshot.id !== renameModal.snapshotId &&
        snapshot.name.trim().toLowerCase() === trimmed.toLowerCase(),
    );
    if (conflicts) {
      setRenameModal((current) => ({ ...current, error: "Snapshot name already exists. Choose a unique name." }));
      return;
    }
    try {
      await api(`/api/services/${selectedService.id}/config/snapshots/${renameModal.snapshotId}/rename`, {
        method: "POST",
        body: JSON.stringify({ name: trimmed, requested_by: "platform-operator" }),
      });
      setRenameModal({ visible: false, snapshotId: 0, value: "", error: "" });
      await loadConfig(selectedService, configSource);
      setNotice(`Renamed snapshot to ${trimmed}`);
    } catch (error: any) {
      setRenameModal((current) => ({
        ...current,
        error: error.message || "Rename failed. Snapshot names must be unique.",
      }));
    }
  }

  async function restoreSnapshot(snapshotId: number) {
    if (!selectedService) return;
    const nextJob = await api<Job>(`/api/services/${selectedService.id}/config/snapshots/${snapshotId}/restore`, {
      method: "POST",
    });
    setJob(nextJob);
    setNotice(`Snapshot restore ${nextJob.status}`);
    await loadConfigTimeline(selectedService.id, { offset: 0, silent: true });
    await loadConfigSnapshots(selectedService, { offset: 0 });
    await refresh();
  }

  // Subsystem Rollout Orchestrator actions
  async function planSubsystem(subsystemName: string) {
    const node = selectedNode || nodes[0];
    if (!node) {
      setNotice("Please select or seed a node first");
      return;
    }
    try {
      const planData = await api<SubsystemRolloutPlan>(`/api/nodes/${node.id}/subsystems/${subsystemName}/rollout-plan`);
      setSubsystemPlan(planData);
      setSelectedSubsystem(subsystemName);
      setNotice(`Generated rollout plan for ${subsystemName}`);
    } catch (error: any) {
      setNotice(`Subsystem planning failed: ${error.message}`);
    }
  }

  async function deploySubsystem(subsystemName: string) {
    const node = selectedNode || nodes[0];
    if (!node) return;
    try {
      setNotice(`Triggering deployment for subsystem ${subsystemName}...`);
      const result = await api<any>(`/api/nodes/${node.id}/subsystems/${subsystemName}/deploy`, { method: "POST" });
      setNotice(`Subsystem deployment triggered: ${result.summary || "Success"}`);
      await refresh();
      await planSubsystem(subsystemName);
    } catch (error: any) {
      setNotice(`Deployment failed: ${error.message}`);
    }
  }

  async function validateNode(nodeId: number) {
    try {
      setNotice(`Running configuration validation for node ${nodeId}...`);
      const result = await api<Job>(`/api/nodes/${nodeId}/validate`, { method: "POST" });
      setJob(result);
      setNotice(`Node validation job triggered: ${result.status}`);
      await refresh();
      await loadNodeJobHistory(nodeId);
    } catch (error: any) {
      setNotice(`Validation failed: ${error.message}`);
    }
  }

  function getConfigStrategy(caps: ServiceCapabilities | null, service: Service | null) {
    if (!caps || !service) return "Loading...";
    if (caps.config) return "Live config file";
    if (service.kind === "helper") return "No external config";
    return "Catalog-generated config";
  }

  function getBackupStrategy(caps: ServiceCapabilities | null, service: Service | null) {
    if (!caps || !service) return "Loading...";
    if (!caps.backup) return "no backup required";
    const key = service.service_key;
    if (["postgres-core", "airflow-postgres", "clickhouse-core", "milvus-core"].includes(key)) {
      return "database dumps";
    }
    if (["redis-core", "airflow-redis", "rabbitmq-core", "etcd-core"].includes(key)) {
      return "volume archives";
    }
    if (["minio-core"].includes(key)) {
      return "object-store archives";
    }
    return "config-only backups";
  }

  function formatLocalTimestamp(value: string | null) {
    if (!value) return "--";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  }

  const visibleNodes = selectedCluster ? nodes.filter((node) => node.cluster_id === selectedCluster.id) : nodes;
  const diagnosticsSourceService =
    services.find((service) => service.id === diagnosticsSourceServiceId) ??
    selectedService;
  const [activeView, setActiveView] = useState<string>("clusters");

  async function runDiagnosticsInsightAction(action: DiagnosticsInsightAction) {
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    if (!sourceService) {
      setNotice("Select a service first to run diagnostics actions.");
      return;
    }
    if (action.action_id === "ensure-dependency-cards") {
      await ensureMissingDependencyCards();
      return;
    }
    if (action.action_id === "focus-dependency-diagnostics" && action.service_key) {
      setActiveView("diagnostics");
      setDiagTab("tail");
      await focusDiagnosticsTarget(action.service_key);
      return;
    }
    if (action.action_id === "open-config") {
      const matchedService = action.service_key
        ? services.find((item) => item.node_id === sourceService.node_id && item.service_key === action.service_key)
        : null;
      const targetService = matchedService ?? sourceService;
      setSelectedService(targetService);
      await loadConfig(targetService, configSource);
      setActiveView("config");
      return;
    }
    if (action.action_id === "open-release-context") {
      const matchedService = action.service_key
        ? services.find((item) => item.node_id === sourceService.node_id && item.service_key === action.service_key)
        : null;
      const targetService = matchedService ?? sourceService;
      setSelectedService(targetService);
      await loadServiceCapabilities(targetService.id);
      await loadServiceSummary(targetService.id);
      await loadServiceReleaseTimeline(targetService.id);
      await loadServiceMetrics(targetService.id);
      if (targetService.node_id !== selectedNode?.id) {
        const targetNode = nodes.find((item) => item.id === targetService.node_id);
        if (targetNode) {
          await selectNode(targetNode);
        }
      }
      setActiveView("clusters");
      setNotice(`Opened release context for ${targetService.name}.`);
      return;
    }
    if (action.action_id === "open-existing-incident" && action.incident_id) {
      setActiveView("monitoring");
      setNotice(`Review incident #${action.incident_id} in the monitoring panel.`);
      return;
    }
    if (action.action_id === "run-incident-runbook" && action.incident_id && action.runbook_key) {
      const incident = incidents.find((item) => item.id === action.incident_id);
      if (incident) {
        await runIncidentRunbook(incident, action.runbook_key);
      } else {
        const runbook = await api<RunbookExecution>(`/api/incidents/${action.incident_id}/runbook/${action.runbook_key}`, {
          method: "POST",
        });
        setRunbooks((current) => [runbook, ...current]);
        setNotice(`Runbook ${runbook.runbook_key} ${runbook.status}`);
        await refresh();
      }
      setActiveView("monitoring");
      return;
    }
    if (action.action_id === "open-incident") {
      await openIncident(sourceService);
      setActiveView("monitoring");
      return;
    }
    setActiveView("diagnostics");
    setDiagTab(action.target_view === "files" ? "files" : "tail");
    if (action.service_key && action.service_key !== diagnosticsTargetKey) {
      await focusDiagnosticsTarget(action.service_key);
      return;
    }
    await loadDiagnostics(sourceService, { targetServiceKey: action.service_key ?? diagnosticsTargetKey, preserveSelection: true });
  }

  async function openDiagnosticsSupportingEvidence(evidence: DiagnosticsInsightEvidence) {
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    if (!sourceService) {
      setNotice("Select a service first to open supporting evidence.");
      return;
    }
    if (evidence.target_view === "release") {
      await runDiagnosticsInsightAction({
        action_id: "open-release-context",
        label: evidence.label,
        description: evidence.summary,
        service_key: sourceService.service_key,
        incident_id: null,
        runbook_key: null,
        target_view: "clusters",
        recommended: false,
      });
      return;
    }
    if (evidence.target_view === "monitoring" && evidence.incident_id) {
      await runDiagnosticsInsightAction({
        action_id: "open-existing-incident",
        label: evidence.label,
        description: evidence.summary,
        service_key: diagnosticsAnalysis?.source_service_key ?? sourceService.service_key,
        incident_id: evidence.incident_id,
        runbook_key: null,
        target_view: "monitoring",
        recommended: false,
      });
      return;
    }
    if (evidence.target_view === "config-compare" || evidence.target_view === "config-timeline") {
      await loadConfig(sourceService, configSource);
      setActiveView("config");
      if (evidence.target_view === "config-compare") {
        setConfigTab("compare");
        const leftSnapshotId = evidence.compare_left_snapshot_id ?? evidence.baseline_snapshot_id ?? null;
        const rightSnapshotId = evidence.compare_right_snapshot_id ?? null;
        if (leftSnapshotId && rightSnapshotId) {
          await compareSpecificSnapshots(sourceService, leftSnapshotId, rightSnapshotId);
        } else {
          setCompareSnapshotLeft(leftSnapshotId);
          setCompareSnapshotRight(rightSnapshotId);
          setNotice(`Opened compare context for ${evidence.label}.`);
        }
      } else {
        setConfigTab("timeline");
        setNotice(`Opened timeline context for ${evidence.label}.`);
      }
      return;
    }
    if (evidence.target_view === "files") {
      setActiveView("diagnostics");
      setDiagTab("files");
      await loadDiagnostics(sourceService, {
        targetServiceKey: evidence.service_key ?? diagnosticsTargetKey,
        preserveSelection: true,
      });
      return;
    }
    setActiveView("diagnostics");
    setDiagTab("tail");
    if (evidence.service_key && evidence.service_key !== diagnosticsTargetKey) {
      await focusDiagnosticsTarget(evidence.service_key);
      return;
    }
    await loadDiagnostics(sourceService, {
      targetServiceKey: evidence.service_key ?? diagnosticsTargetKey,
      preserveSelection: true,
    });
  }

  async function openDiagnosticsChangeEvidence(evidence: DiagnosticsAnalysis["change_evidence"][number]) {
    const sourceService =
      services.find((service) => service.id === diagnosticsSourceServiceId) ??
      selectedService;
    if (!sourceService) {
      setNotice("Select a service first to open evidence context.");
      return;
    }
    if (evidence.target_view === "release") {
      await runDiagnosticsInsightAction({
        action_id: "open-release-context",
        label: "Review release timeline",
        description: evidence.summary,
        service_key: sourceService.service_key,
        incident_id: null,
        runbook_key: null,
        target_view: "clusters",
        recommended: false,
      });
      return;
    }
    await loadConfig(sourceService, configSource);
    if (evidence.target_view === "config-compare") {
      setConfigTab("compare");
      const leftSnapshotId = evidence.compare_left_snapshot_id ?? evidence.baseline_snapshot_id ?? null;
      const rightSnapshotId =
        evidence.compare_right_snapshot_id ??
        (snapshotPage?.items?.[0]?.id && snapshotPage.items[0].id !== leftSnapshotId ? snapshotPage.items[0].id : null);
      if (leftSnapshotId && rightSnapshotId) {
        await compareSpecificSnapshots(sourceService, leftSnapshotId, rightSnapshotId);
      } else {
        setCompareSnapshotLeft(leftSnapshotId);
        setCompareSnapshotRight(rightSnapshotId);
        setNotice("Opened config compare context from diagnostics evidence.");
      }
    } else {
      setConfigTab("timeline");
      setNotice("Opened config timeline context from diagnostics evidence.");
    }
    setActiveView("config");
  }

  function handleSendAnalyticsChat() {
    if (!analyticsInput.trim()) return;
    const userMsg = analyticsInput.trim();
    const timestamp = new Date().toLocaleTimeString();
    
    setAnalyticsMessages(prev => [...prev, { sender: "user", text: userMsg, timestamp }]);
    setAnalyticsInput("");
    
    // Use current diagnostics analysis context to ground the operator reply.
    setTimeout(() => {
      let reply = "";
      const lower = userMsg.toLowerCase();
      const nodeName = selectedNode ? selectedNode.name : "N/A";
      const svcName = selectedService ? selectedService.name : "N/A";
      const svcStatus = selectedService ? selectedService.status : "unknown";
      const leadInsight = diagnosticsAnalysis?.insights[0];
      
      if (lower.includes("log") || lower.includes("error")) {
        reply = leadInsight
          ? `Diagnostics analysis for ${svcName} on ${nodeName}: ${leadInsight.summary} Recommended next move: ${leadInsight.actions.find((action) => action.recommended)?.label ?? "Open live logs"}.`
          : `Review live logs for ${svcName} on ${nodeName}. Start with the live tail console, then correlate any warnings with config or dependency state.`;
      } else if (lower.includes("status") || lower.includes("health")) {
        reply = diagnosticsAnalysis
          ? `${svcName} is currently ${svcStatus} on ${nodeName}. Overall diagnostics severity is ${diagnosticsAnalysis.overall_severity}. ${diagnosticsAnalysis.overview}`
          : `Service ${svcName} is currently in a [${svcStatus}] state on ${nodeName}.`;
      } else if (lower.includes("cpu") || lower.includes("memory") || lower.includes("utilization")) {
        reply = serviceMetrics
          ? `Current ${serviceMetrics.window} telemetry for ${svcName}: CPU ${serviceMetrics.cpu_percent}%, memory ${serviceMetrics.memory_mb} MB, queue depth ${serviceMetrics.queue_depth}, error rate ${serviceMetrics.log_error_rate.toFixed(2)}/min.`
          : `Service telemetry is not loaded yet. Refresh diagnostics to pull the latest runtime metrics.`;
      } else if (lower.includes("dependency") || lower.includes("broker") || lower.includes("queue")) {
        const dependencyInsight = diagnosticsAnalysis?.insights.find((insight) => insight.insight_id === "dependency-health" || insight.insight_id === "queue-pressure");
        reply = dependencyInsight
          ? `${dependencyInsight.title}: ${dependencyInsight.summary} Suggested action: ${dependencyInsight.actions.find((action) => action.recommended)?.label ?? "Inspect dependency diagnostics"}.`
          : `No dependency warning is active right now. If queue depth rises, inspect broker dependencies from diagnostics targets.`;
      } else {
        reply = diagnosticsAnalysis
          ? `Operational summary for ${svcName} on ${nodeName}: ${diagnosticsAnalysis.overview} Top next steps: ${diagnosticsAnalysis.next_steps.join(", ") || "Open live logs and inspect recent warnings"}.`
          : `Investigating operational telemetry for ${svcName} on ${nodeName}. Refresh diagnostics to generate current recommendations.`;
      }
      
      setAnalyticsMessages(prev => [...prev, { sender: "assistant", text: reply, timestamp: new Date().toLocaleTimeString() }]);
    }, 1000);
  }

  function renderTreeNavigator(onSelectService: (service: Service) => void, activeServiceId: number | null) {
    const filteredClusters = clusters.filter(c => c.name.toLowerCase().includes(treeSearchQuery.toLowerCase()));
    
    return (
      <div className="tree-navigator" style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "100%", overflowY: "auto", paddingRight: "0.5rem" }}>
        <div className="tree-search">
          <input 
            type="text" 
            className="input"
            placeholder="Filter hierarchy..." 
            value={treeSearchQuery} 
            onChange={(e) => setTreeSearchQuery(e.target.value)}
            style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {clusters.map((cluster) => {
            const clusterNodes = nodes.filter((n) => n.cluster_id === cluster.id);
            const matchesSearch = cluster.name.toLowerCase().includes(treeSearchQuery.toLowerCase());
            if (clusterNodes.length === 0 && !matchesSearch) return null;
            return (
              <div key={`tree-cluster-${cluster.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.25rem", padding: "0.25rem", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.04)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.4rem 0.6rem", cursor: "pointer" }} onClick={() => selectCluster(cluster)}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>📁 {cluster.name}</span>
                  <span className="pill" style={{ fontSize: "0.7rem", scale: "0.9" }}>{cluster.environment}</span>
                </div>
                <div style={{ paddingLeft: "1rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                  {clusterNodes.map((node) => {
                    const nodeServices = services.filter((s) => s.node_id === node.id);
                    const nodeMatches = node.name.toLowerCase().includes(treeSearchQuery.toLowerCase()) || matchesSearch;
                    if (nodeServices.length === 0 && !nodeMatches) return null;
                    return (
                      <div key={`tree-node-${node.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", padding: "0.3rem 0.5rem", cursor: "pointer", borderRadius: "6px" }} onClick={() => selectNode(node)}>
                          <span style={{ fontSize: "0.8rem", color: "var(--ink-2)" }}>🖥️ {node.name}</span>
                          <span className={`status-dot ${node.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }}></span>
                        </div>
                        <div style={{ paddingLeft: "1rem", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                          {nodeServices.map((service) => {
                            if (treeSearchQuery && !service.name.toLowerCase().includes(treeSearchQuery.toLowerCase()) && !nodeMatches) return null;
                            const isActive = activeServiceId === service.id;
                            return (
                              <div 
                                key={`tree-service-${service.id}`} 
                                className={`tree-item service-item ${isActive ? "active" : ""}`}
                                onClick={() => onSelectService(service)}
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  padding: "0.25rem 0.4rem",
                                  cursor: "pointer",
                                  borderRadius: "4px",
                                  background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                                  border: isActive ? "1px solid rgba(99,102,241,0.3)" : "none"
                                }}
                              >
                                <span style={{ fontSize: "0.75rem", color: isActive ? "#ffffff" : "var(--ink-3)" }}>📦 {service.name}</span>
                                <span className={`status-dot ${service.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }}></span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderClustersView() {
    if (!selectedCluster) {
      // Cluster List view (02-clusters.html layout reference)
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          <div className="page-head">
            <div className="titles">
              <h1>Cluster <em>Registry</em></h1>
              <p className="sub">Deploy and manage high-availability clusters. Select a cluster below to configure nodes, pipelines, and ML instances.</p>
            </div>
            <div className="actions">
              <button className="btn btn-primary" onClick={openClusterCreate}>
                <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
                Create Cluster
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Clusters</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#ffffff", marginTop: "0.35rem" }}>{dashboardSummary?.clusters ?? clusters.length}</div>
            </GlassCard>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Nodes</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#ffffff", marginTop: "0.35rem" }}>{dashboardSummary?.nodes ?? nodes.length}</div>
            </GlassCard>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Running Services</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#ffffff", marginTop: "0.35rem" }}>
                {dashboardSummary ? `${dashboardSummary.running_services}/${dashboardSummary.services}` : services.length}
              </div>
            </GlassCard>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Open Incidents</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: dashboardSummary && dashboardSummary.open_incidents > 0 ? "#fca5a5" : "#ffffff", marginTop: "0.35rem" }}>{dashboardSummary?.open_incidents ?? incidents.length}</div>
            </GlassCard>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Burning SLOs</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: dashboardSummary && dashboardSummary.burning_slos > 0 ? "#fdba74" : "#ffffff", marginTop: "0.35rem" }}>{dashboardSummary?.burning_slos ?? 0}</div>
            </GlassCard>
            <GlassCard style={{ padding: "1.1rem" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", textTransform: "uppercase" }}>Observability</div>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#ffffff", marginTop: "0.35rem" }}>
                {dashboardSummary
                  ? `${dashboardSummary.healthy_observability_nodes}/${dashboardSummary.healthy_observability_nodes + dashboardSummary.degraded_observability_nodes}`
                  : (observabilityPipeline ? `${observabilityPipeline.summary.healthy_nodes}/${observabilityPipeline.summary.total_nodes}` : "0/0")}
              </div>
            </GlassCard>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.5rem" }}>
            <GlassCard style={{ padding: "1.5rem" }}>
              <div className="panel-title" style={{ marginBottom: "1rem" }}>
                <h2>Needs Attention</h2>
                <span>{dashboardSummary?.attention_services.length ?? 0} services</span>
              </div>
              <div className="timeline">
                {(dashboardSummary?.attention_services ?? []).map((item) => (
                  <article key={`attention-${item.service_id}`}>
                    <span className={`status ${item.severity === "critical" ? "error" : item.severity === "warning" ? "warning" : "running"}`}>
                      {item.severity}
                    </span>
                    <strong>{item.service_name}</strong>
                    <p>{item.cluster_name} / {item.node_name} / {item.service_key}</p>
                    <small>{item.reasons[0]}</small>
                    <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => focusServiceInCluster(item.service_id)}>Open service</button>
                    </div>
                  </article>
                ))}
                {(dashboardSummary?.attention_services.length ?? 0) === 0 && (
                  <p style={{ color: "var(--ink-4)" }}>No services need immediate attention. Platform state looks healthy.</p>
                )}
              </div>
            </GlassCard>

            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <GlassCard style={{ padding: "1.5rem" }}>
                <div className="panel-title" style={{ marginBottom: "1rem" }}>
                  <h2>Active Incidents</h2>
                  <span>{dashboardSummary?.active_incidents.length ?? 0}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {(dashboardSummary?.active_incidents ?? []).map((incident) => (
                    <div key={`dash-incident-${incident.id}`} style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                        <strong>{incident.title}</strong>
                        <span className={`pill ${incident.severity === "sev1" ? "pill-error" : "pill-warn"}`}>{incident.severity}</span>
                      </div>
                      <div style={{ marginTop: "0.3rem", color: "var(--ink-3)" }}>{incident.summary || "Reliability review in progress"}</div>
                    </div>
                  ))}
                  {(dashboardSummary?.active_incidents.length ?? 0) === 0 && (
                    <p style={{ color: "var(--ink-4)" }}>No open incidents.</p>
                  )}
                </div>
              </GlassCard>

              <GlassCard style={{ padding: "1.5rem" }}>
                <div className="panel-title" style={{ marginBottom: "1rem" }}>
                  <h2>Degraded Observability</h2>
                  <span>{dashboardSummary?.degraded_observability_nodes ?? 0} nodes</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {(dashboardSummary?.degraded_observability ?? []).map((node) => (
                    <div key={`degraded-node-${node.node_id}`} style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                        <strong>{node.node_name}</strong>
                        <span className="pill pill-warn">{node.ingestion_state}</span>
                      </div>
                      <div style={{ marginTop: "0.3rem", color: "var(--ink-3)" }}>{node.cluster_name}</div>
                      <small style={{ display: "block", marginTop: "0.35rem", color: "var(--ink-4)" }}>
                        {node.issues[0] ?? "Pipeline not fully ready"}
                      </small>
                    </div>
                  ))}
                  {(dashboardSummary?.degraded_observability.length ?? 0) === 0 && (
                    <p style={{ color: "var(--ink-4)" }}>Observability pipeline is healthy across all tracked nodes.</p>
                  )}
                </div>
              </GlassCard>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "1.5rem" }}>
            {clusters.map((cluster) => {
              const clusterNodes = nodes.filter((n) => n.cluster_id === cluster.id);
              const clusterServices = services.filter((s) => clusterNodes.some(n => n.id === s.node_id));
              
              return (
                <GlassCard key={cluster.id} className="card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.2rem", cursor: "pointer" }} onClick={() => selectCluster(cluster)}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <span className="pill" style={{ background: "rgba(99, 102, 241, 0.1)", color: "#818cf8", fontSize: "0.75rem", fontWeight: "bold" }}>{cluster.environment.toUpperCase()}</span>
                      <h3 style={{ fontSize: "1.5rem", fontFamily: "var(--display)", fontWeight: 500, marginTop: "0.5rem", color: "#ffffff" }}>{cluster.name}</h3>
                      <p style={{ fontSize: "0.85rem", color: "var(--ink-4)", fontFamily: "var(--mono)", marginTop: "2px" }}>{cluster.region}</p>
                    </div>
                    <span className="pill pill-ok">Healthy</span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)", padding: "1rem 0" }}>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 600, color: "#ffffff" }}>{clusterNodes.length}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Nodes</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 600, color: "#ffffff" }}>{clusterServices.length}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Services</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 600, color: "#ffffff" }}>99.9%</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Uptime</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                    <button className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); openClusterEdit(cluster); }}>Configure</button>
                    <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); selectCluster(cluster); }}>Enter Dashboard</button>
                  </div>
                </GlassCard>
              );
            })}
          </div>

          <GlassCard className="wide" style={{ padding: "1.5rem" }}>
            <div className="panel-title" style={{ marginBottom: "1rem" }}>
              <h2>Global Service Catalog Preview</h2>
              <button className="btn btn-secondary btn-sm" onClick={() => setCatalogDrawerVisible(true)}>View Full Catalog</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
              {catalog.slice(0, 4).map((card) => (
                <article key={card.service_key} style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", minHeight: "150px" }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <span style={{ fontSize: "0.7rem", color: "var(--navy-500)", textTransform: "uppercase", fontWeight: 600 }}>{card.kind}</span>
                      <span style={{ fontSize: "0.75rem", color: "var(--ink-4)", fontFamily: "var(--mono)" }}>v1.0.0</span>
                    </div>
                    <h4 style={{ fontSize: "1.05rem", fontWeight: 600, marginTop: "0.25rem" }}>{card.name}</h4>
                    <p style={{ fontSize: "0.8rem", color: "var(--ink-3)", marginTop: "4px" }}>{card.description || card.image}</p>
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end", borderTop: "1px solid var(--line)", paddingTop: "0.5rem" }}>
                    <small style={{ fontFamily: "var(--mono)", fontSize: "0.7rem", color: "var(--ink-4)" }}>{card.subsystem}</small>
                  </div>
                </article>
              ))}
            </div>
          </GlassCard>
        </div>
      );
    }

    // Cluster Details view (04-cluster-detail.html layout reference)
    const clusterNodes = nodes.filter((n) => n.cluster_id === selectedCluster.id);
    const clusterServices = services.filter((s) => clusterNodes.some(n => n.id === s.node_id));
    const activeSubTabTitle = clusterSubTab === "nodes" ? "Nodes list" : clusterSubTab === "topology" ? "Topology sequence" : clusterSubTab === "policy" ? "Compliance & force-deletes" : "Audit timeline";

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Manage <em>cluster</em></h1>
            <p className="sub">Provision nodes, deploy services. Drag from the service catalog onto any node to install via Ansible.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary" onClick={() => openClusterEdit(selectedCluster)}>
              <svg className="ic" viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>
              Cluster settings
            </button>
            <button className="btn btn-primary" onClick={() => setStepperDrawerVisible(true)}>
              <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
              Provision node
            </button>
          </div>
        </div>

        {/* CLUSTER SUMMARY BAND */}
        <div className="cluster-band">
          <div className="identity">
            <div className="badge-cloud">AWS</div>
            <div className="id-text">
              <div className="name" style={{ color: "#ffffff", fontWeight: 600 }}>{selectedCluster.name}</div>
              <div className="meta">{selectedCluster.region} · {selectedCluster.environment}</div>
            </div>
          </div>
          <div className="stats">
            <div className="stat"><div className="v" style={{ color: "#ffffff" }}>{clusterNodes.length}</div><div className="l">Nodes</div></div>
            <div className="stat"><div className="v" style={{ color: "#ffffff" }}>{clusterServices.length}</div><div className="l">Services</div></div>
            <div className="stat"><div className="v" style={{ color: "#ffffff" }}>32 <span className="unit">vCPU</span></div><div className="l">Allocated</div></div>
            <div className="stat"><div className="v" style={{ color: "#ffffff" }}>128 <span className="unit">GB</span></div><div className="l">RAM</div></div>
            <div className="stat"><div className="v" style={{ color: "#ffffff" }}>99.98<span className="unit">%</span></div><div className="l">Uptime 30d</div></div>
          </div>
          <div>
            <span className="pill pill-ok">Healthy</span>
          </div>
        </div>

        <GlassCard className="wide" style={{ padding: "1.5rem" }}>
          <div className="panel-title" style={{ marginBottom: "1rem" }}>
            <h2>Observability Pipeline</h2>
            <span>
              {observabilityPipeline
                ? `${observabilityPipeline.summary.healthy_nodes}/${observabilityPipeline.summary.total_nodes} healthy`
                : "loading"}
            </span>
          </div>
          {observabilityPipeline ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
              {observabilityPipeline.nodes
                .filter((node) => clusterNodes.some((clusterNode) => clusterNode.id === node.node_id))
                .map((node) => (
                  <article key={`obs-node-${node.node_id}`} style={{ border: "1px solid var(--line)", borderRadius: "14px", padding: "1rem", background: "rgba(255,255,255,0.03)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.75rem" }}>
                      <div>
                        <strong>{node.node_name}</strong>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginTop: "0.2rem" }}>
                          {node.last_signal_at ? `Last signal ${new Date(node.last_signal_at).toLocaleString()}` : "No signal yet"}
                        </div>
                      </div>
                      <span className={`pill ${node.pipeline_ready ? "pill-ok" : "pill-warn"}`}>{node.ingestion_state}</span>
                    </div>
                    <div className="tags" style={{ marginTop: "0.75rem" }}>
                      {Object.entries(node.components).map(([key, value]) => (
                        <span key={`${node.node_id}-${key}`}>{key}: {value}</span>
                      ))}
                    </div>
                    {node.issues.length > 0 && (
                      <ul style={{ margin: "0.75rem 0 0 1rem", color: "var(--ink-3)" }}>
                        {node.issues.map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    )}
                    <div className="actions compact" style={{ marginTop: "0.8rem", flexWrap: "wrap" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => bootstrapObservability(node.node_id)}
                        disabled={observabilityBusyNodeId === node.node_id}
                      >
                        {observabilityBusyNodeId === node.node_id ? "Bootstrapping..." : "Bootstrap observability plane"}
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          const service = services.find((item) => item.node_id === node.node_id && item.service_key === "alloy-core");
                          if (service) {
                            setSelectedService(service);
                            loadDiagnostics(service);
                            setActiveView("diagnostics");
                            setDiagTab("tail");
                          } else {
                            setNotice(`Alloy is not installed on ${node.node_name} yet.`);
                          }
                        }}
                      >
                        Open Alloy logs
                      </button>
                    </div>
                  </article>
                ))}
            </div>
          ) : (
            <p style={{ color: "var(--ink-4)" }}>Loading observability pipeline report...</p>
          )}
        </GlassCard>

        {/* TABS */}
        <div className="cluster-tabs">
          <div className={`tab ${clusterSubTab === "nodes" ? "active" : ""}`} onClick={() => setClusterSubTab("nodes")}>Nodes <span className="ct">{clusterNodes.length}</span></div>
          <div className={`tab ${clusterSubTab === "topology" ? "active" : ""}`} onClick={() => setClusterSubTab("topology")}>Topology &amp; Sequence</div>
          <div className={`tab ${clusterSubTab === "policy" ? "active" : ""}`} onClick={() => setClusterSubTab("policy")}>Policy &amp; compliance</div>
          <div className={`tab ${clusterSubTab === "audit" ? "active" : ""}`} onClick={() => setClusterSubTab("audit")}>Audit log</div>
        </div>

        {/* TAB VIEWS */}
        {clusterSubTab === "nodes" && (
          <div className="cluster-split">
            {/* Left Column: searchable node list */}
            <div className="node-list-wrap">
              <div className="node-list-head">
                <h3>Nodes</h3>
                <span style={{ fontFamily: "var(--mono)", fontSize: "10px", color: "var(--ink-4)" }}>{clusterNodes.length} total</span>
              </div>
              <div className="node-search">
                <svg className="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input 
                  type="text" 
                  placeholder="Search nodes…" 
                  value={nodeSearchQuery}
                  onChange={(e) => setNodeSearchQuery(e.target.value)}
                />
              </div>

              <div className="node-list">
                {clusterNodes
                  .filter(n => n.name.toLowerCase().includes(nodeSearchQuery.toLowerCase()))
                  .map((node) => {
                    const isSelected = selectedNode?.id === node.id;
                    const nodeServices = services.filter(s => s.node_id === node.id);
                    return (
                      <div 
                        key={node.id} 
                        className={`node-row ${isSelected ? "active" : ""}`}
                        onClick={() => selectNode(node)}
                      >
                        <div className={`nstat ${node.status}`}></div>
                        <div className="info">
                          <div className="nm">{node.name}</div>
                          <div className="sub">
                            <span className="cloud">{node.environment.toUpperCase()}</span>
                            {node.host}
                          </div>
                        </div>
                        <div className="svc-count">{nodeServices.length} svc</div>
                      </div>
                    );
                  })}
              </div>
              <div className="node-list-foot">
                <button className="btn btn-secondary btn-sm" onClick={() => setStepperDrawerVisible(true)}>
                  <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
                  Provision node
                </button>
              </div>
            </div>

            {/* Right Column: node details spec sheet & service stack */}
            {selectedNode ? (
              <div className="node-detail">
                <div className="node-spec-header">
                  <div className="top-row">
                    <div>
                      <div className="title">{selectedNode.name}</div>
                      <div className="subtitle">
                        <span className="cloud-tag">{selectedNode.environment.toUpperCase()}</span>
                        <span>IP: {selectedNode.host} · Volume: <code>{selectedNode.volume_root}</code></span>
                      </div>
                    </div>
                    <div className="actions">
                      <button className="btn btn-secondary btn-sm" onClick={() => validateNode(selectedNode.id)}>Validate</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => openNodeEdit(selectedNode)}>Edit</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => loadArtifact("inventory")}>Inventory</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => loadArtifact("compose")}>Compose</button>
                      <button className="btn btn-danger btn-sm" onClick={() => requestDelete("node", selectedNode.id, selectedNode.name)}>Delete</button>
                    </div>
                  </div>

                  <div className="spec-sheet">
                    <div className="spec-cell"><div className="l">vCPU</div><div className="v">16 <span className="unit">cores</span></div></div>
                    <div className="spec-cell"><div className="l">Memory</div><div className="v">128 <span className="unit">GB</span></div></div>
                    <div className="spec-cell"><div className="l">Storage</div><div className="v">500 <span className="unit">GB SSD</span></div></div>
                    <div className="spec-cell"><div className="l">GPU</div><div className="v">NVIDIA A10G</div></div>
                    <div className="spec-cell"><div className="l">OS</div><div className="v">Ubuntu 22.04</div></div>
                    <div className="spec-cell"><div className="l">Status</div><div className="v" style={{ textTransform: "capitalize" }}>{selectedNode.status}</div></div>
                  </div>

                  {nodeJobHistory && (
                    <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: "16px", padding: "1rem", background: "rgba(255,255,255,0.55)" }}>
                      <div className="panel-title" style={{ marginBottom: "0.75rem" }}>
                        <h2>Rollout Queue Summary</h2>
                        <span>{nodeJobHistory.items.filter((item) => item.status === "queued" || item.status === "running").length} active</span>
                      </div>
                      <div className="checks" style={{ marginBottom: "0.85rem" }}>
                        <div>
                          <span className="status running">recent</span>
                          <strong>{nodeJobHistory.total_jobs}</strong>
                          <small>total jobs</small>
                        </div>
                        <div>
                          <span className="status warning">queued</span>
                          <strong>{nodeJobHistory.items.filter((item) => item.status === "queued").length}</strong>
                          <small>queued</small>
                        </div>
                        <div>
                          <span className="status running">running</span>
                          <strong>{nodeJobHistory.items.filter((item) => item.status === "running").length}</strong>
                          <small>running</small>
                        </div>
                        <div>
                          <span className="status error">fail</span>
                          <strong>{nodeJobHistory.failed_jobs}</strong>
                          <small>failed jobs</small>
                        </div>
                      </div>
                      {nodeJobHistory.items[0] ? (
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                          <div>
                            <strong>{nodeJobHistory.items[0].action}</strong>
                            <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                              Latest target {nodeJobHistory.items[0].service_name ?? "node-level task"} · {formatLocalTimestamp(nodeJobHistory.items[0].created_at)}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                            <button className="btn btn-secondary btn-sm" onClick={() => loadNodeJobHistory(selectedNode.id)}>Refresh jobs</button>
                            {nodeJobHistory.items[0].service_id && (
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => focusServiceInCluster(nodeJobHistory.items[0].service_id!)}
                              >
                                Open latest target
                              </button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <p style={{ color: "var(--ink-4)", margin: 0 }}>No rollout jobs have been recorded on this node yet.</p>
                      )}
                    </div>
                  )}

                  <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: "16px", padding: "1rem", background: "rgba(255,255,255,0.55)" }}>
                    <div className="panel-title" style={{ marginBottom: "0.75rem" }}>
                      <h2>AWS / Node Onboarding Readiness</h2>
                      <span>{nodeOnboarding ? `${nodeOnboarding.overall_status} · ${nodeOnboarding.connection_state}` : "loading"}</span>
                    </div>
                    {nodeOnboarding ? (
                      <>
                        <div className="checks" style={{ marginBottom: "0.8rem" }}>
                          <div>
                            <span className={`status ${nodeOnboarding.overall_status === "pass" ? "running" : nodeOnboarding.overall_status === "warn" ? "warning" : "error"}`}>
                              {nodeOnboarding.overall_status}
                            </span>
                            <strong>Overall</strong>
                            <small>{new Date(nodeOnboarding.checked_at).toLocaleString()}</small>
                          </div>
                          <div>
                            <span className="status running">pass</span>
                            <strong>{nodeOnboarding.pass_count}</strong>
                            <small>checks</small>
                          </div>
                          <div>
                            <span className="status warning">warn</span>
                            <strong>{nodeOnboarding.warn_count}</strong>
                            <small>checks</small>
                          </div>
                          <div>
                            <span className="status error">fail</span>
                            <strong>{nodeOnboarding.fail_count}</strong>
                            <small>checks</small>
                          </div>
                        </div>

                        {nodeOnboarding.suggested_actions.length > 0 && (
                          <div style={{ marginBottom: "0.8rem" }}>
                            <strong>Suggested fix order</strong>
                            <div className="tags" style={{ marginTop: "0.35rem" }}>
                              {nodeOnboarding.suggested_actions.map((action, index) => (
                                <span key={`suggested-${action}`}>{index + 1}. {getOnboardingActionLabel(action)}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="actions compact" style={{ marginBottom: "0.8rem", flexWrap: "wrap" }}>
                          <button
                            className={`btn btn-sm ${nodeOnboarding.suggested_actions[0] === "apply-aws-general-preset" ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => runOnboardingRemediation("apply-aws-general-preset")}
                            disabled={onboardingActionBusy.length > 0}
                          >
                            {onboardingActionBusy === "apply-aws-general-preset" ? "Applying..." : nodeOnboarding.suggested_actions[0] === "apply-aws-general-preset" ? "Apply AWS General Preset (Recommended)" : "Apply AWS General Preset"}
                          </button>
                          <button
                            className={`btn btn-sm ${nodeOnboarding.suggested_actions[0] === "apply-aws-gpu-preset" ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => runOnboardingRemediation("apply-aws-gpu-preset")}
                            disabled={onboardingActionBusy.length > 0}
                          >
                            {onboardingActionBusy === "apply-aws-gpu-preset" ? "Applying..." : nodeOnboarding.suggested_actions[0] === "apply-aws-gpu-preset" ? "Apply AWS GPU Preset (Recommended)" : "Apply AWS GPU Preset"}
                          </button>
                          <button
                            className={`btn btn-sm ${nodeOnboarding.suggested_actions[0] === "apply-local-preset" ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => runOnboardingRemediation("apply-local-preset")}
                            disabled={onboardingActionBusy.length > 0}
                          >
                            {onboardingActionBusy === "apply-local-preset" ? "Applying..." : nodeOnboarding.suggested_actions[0] === "apply-local-preset" ? "Apply Local Preset (Recommended)" : "Apply Local Preset"}
                          </button>
                          <button
                            className={`btn btn-sm ${nodeOnboarding.suggested_actions[0] === "run-validation" ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => runOnboardingRemediation("run-validation")}
                            disabled={onboardingActionBusy.length > 0}
                          >
                            {onboardingActionBusy === "run-validation" ? "Validating..." : nodeOnboarding.suggested_actions[0] === "run-validation" ? "Run Validation (Recommended)" : "Run Validation"}
                          </button>
                        </div>

                        <div className="timeline" style={{ marginBottom: "0.8rem" }}>
                          {nodeOnboarding.checks.map((check) => (
                            <article key={`${nodeOnboarding.node_id}-${check.check_id}`}>
                              <span className={`status ${check.status === "pass" ? "running" : check.status === "warn" ? "warning" : "error"}`}>
                                {check.status}
                              </span>
                              <strong>{check.title}</strong>
                              <p>{check.detail}</p>
                              <small>{check.remediation}</small>
                            </article>
                          ))}
                        </div>

                        {nodeOnboarding.next_actions.length > 0 && (
                          <div>
                            <strong>Next actions</strong>
                            <ul style={{ margin: "0.35rem 0 0 1rem" }}>
                              {nodeOnboarding.next_actions.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    ) : (
                      <p style={{ color: "var(--ink-4)" }}>No onboarding readiness report yet.</p>
                    )}
                  </div>
                </div>

                <div className="utilization">
                  <div className="util">
                    <div className="top"><span className="name">CPU</span><span className="val">{nodeMetrics ? `${nodeMetrics.cpu_percent}%` : "62%"}</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${nodeMetrics?.cpu_percent ?? 62}%` }}></div></div>
                    <div className="sub">{nodeMetrics ? `${Math.round((nodeMetrics.cpu_percent / 100) * 16 * 10) / 10} / 16 cores` : "9.9 / 16 cores · load avg 4.2"}</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Memory</span><span className="val">{nodeMetrics ? `${nodeMetrics.memory_percent}%` : "81%"}</span></div>
                    <div className="bar"><div className="fill warn" style={{ width: `${nodeMetrics?.memory_percent ?? 81}%` }}></div></div>
                    <div className="sub">{nodeMetrics ? `${Math.round((nodeMetrics.memory_percent / 100) * 128)} / 128 GB used` : "103 / 128 GB used"}</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Disk</span><span className="val">{nodeMetrics ? `${nodeMetrics.disk_percent}%` : "34%"}</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${nodeMetrics?.disk_percent ?? 34}%` }}></div></div>
                    <div className="sub">{nodeMetrics ? `${Math.round((nodeMetrics.disk_percent / 100) * 500)} / 500 GB used` : "170 / 500 GB used"}</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Network</span><span className="val">{nodeMetrics ? `${nodeMetrics.network_rx_mbps} Mbps` : "2.4 GB/s"}</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${Math.min(100, ((nodeMetrics?.network_rx_mbps ?? 240) / 6))}%` }}></div></div>
                    <div className="sub">{nodeMetrics ? `↓ ${nodeMetrics.network_rx_mbps} Mbps · ↑ ${nodeMetrics.network_tx_mbps} Mbps` : "↓ 1.6 GB/s · ↑ 0.8 GB/s"}</div>
                  </div>
                </div>

                {nodeMetrics && (
                  <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: "16px", padding: "1rem", background: "rgba(255,255,255,0.55)" }}>
                    <div className="panel-title" style={{ marginBottom: "0.75rem" }}>
                      <h2>Runtime Metrics</h2>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                        <span>{nodeMetrics.node_name}</span>
                        {renderMetricWindowPicker(nodeMetricsWindow, setNodeMetricsWindow)}
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "0.75rem" }}>
                      <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                        <strong>CPU trend</strong>
                        <div style={{ marginTop: "0.25rem", color: "var(--ink-3)" }}>{nodeMetrics.cpu_percent}% current · {nodeMetrics.window} window</div>
                        {renderMetricSparkline(nodeMetrics.cpu_series, "linear-gradient(180deg, #38bdf8, #0f172a)")}
                      </div>
                      <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                        <strong>Memory trend</strong>
                        <div style={{ marginTop: "0.25rem", color: "var(--ink-3)" }}>{nodeMetrics.memory_percent}% current · {nodeMetrics.window} window</div>
                        {renderMetricSparkline(nodeMetrics.memory_series, "linear-gradient(180deg, #f59e0b, #7c2d12)")}
                      </div>
                      <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                        <strong>Disk trend</strong>
                        <div style={{ marginTop: "0.25rem", color: "var(--ink-3)" }}>{nodeMetrics.disk_percent}% current · {nodeMetrics.window} window</div>
                        {renderMetricSparkline(nodeMetrics.disk_series, "linear-gradient(180deg, #10b981, #064e3b)")}
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: "16px", padding: "1rem", background: "rgba(255,255,255,0.55)" }}>
                  <div className="panel-title" style={{ marginBottom: "0.75rem" }}>
                    <h2>Recent Deployment Jobs &amp; Ansible Runs</h2>
                    <span>{nodeJobHistory ? `${nodeJobHistory.total_jobs} total` : "loading"}</span>
                  </div>
                  {nodeJobHistory ? (
                    <>
                      {nodeJobHistory.items.filter((item) => item.status === "queued" || item.status === "running").length > 0 && (
                        <div style={{ marginBottom: "0.85rem" }}>
                          <strong>Active operations</strong>
                          <div style={{ marginTop: "0.4rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                            {nodeJobHistory.items
                              .filter((item) => item.status === "queued" || item.status === "running")
                              .map((item) => (
                                <div key={`active-node-job-${item.id}`} style={{ padding: "0.7rem 0.8rem", borderRadius: "10px", border: "1px solid var(--line-2)", background: "rgba(255,255,255,0.03)", display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                                  <div>
                                    <div style={{ display: "flex", gap: "0.45rem", alignItems: "center", flexWrap: "wrap" }}>
                                      <span className={`pill ${item.status === "running" ? "pill-ok" : "pill-warn"}`}>{item.status}</span>
                                      <strong>{item.action}</strong>
                                      {item.service_name && <span style={{ color: "var(--ink-4)", fontSize: "0.8rem" }}>{item.service_name}</span>}
                                    </div>
                                    <div style={{ color: "var(--ink-4)", fontSize: "0.78rem", marginTop: "0.2rem" }}>
                                      Started {formatLocalTimestamp(item.started_at || item.created_at)}
                                    </div>
                                  </div>
                                  <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => item.service_id && focusServiceInCluster(item.service_id)}
                                    disabled={!item.service_id}
                                  >
                                    Open target
                                  </button>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                      <div className="checks" style={{ marginBottom: "0.85rem" }}>
                        <div>
                          <span className="status running">deploy</span>
                          <strong>{nodeJobHistory.deployment_jobs}</strong>
                          <small>deploy jobs</small>
                        </div>
                        <div>
                          <span className="status warning">config</span>
                          <strong>{nodeJobHistory.config_jobs}</strong>
                          <small>config jobs</small>
                        </div>
                        <div>
                          <span className="status running">validate</span>
                          <strong>{nodeJobHistory.validation_jobs}</strong>
                          <small>validation jobs</small>
                        </div>
                        <div>
                          <span className="status error">fail</span>
                          <strong>{nodeJobHistory.failed_jobs}</strong>
                          <small>failed jobs</small>
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                        {nodeJobHistory.items.map((item) => (
                          <article key={`node-job-${item.id}`} style={{ border: "1px solid var(--line-2)", borderRadius: "12px", padding: "0.85rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                              <div style={{ display: "flex", gap: "0.45rem", alignItems: "center", flexWrap: "wrap" }}>
                                <span className={`pill ${item.status === "success" ? "pill-ok" : item.status === "failed" ? "pill-error" : "pill-warn"}`}>{item.status}</span>
                                <strong>{item.action}</strong>
                                {item.service_name && <span style={{ color: "var(--ink-4)", fontSize: "0.8rem" }}>{item.service_name}</span>}
                              </div>
                              <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(item.created_at)}</small>
                            </div>
                            <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                              {item.service_key ? `${item.service_key} · ` : ""}job #{item.id}
                            </div>
                            <pre style={{ margin: "0.45rem 0 0", padding: "0.65rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.75rem" }}>
                              <code>{item.command}</code>
                            </pre>
                            {item.output && (
                              <pre style={{ margin: "0.5rem 0 0", padding: "0.8rem", borderRadius: "10px", background: "#010307", color: "#34d399", overflowX: "auto", fontSize: "0.75rem", fontFamily: "var(--mono)", border: "1px solid var(--line)", whiteSpace: "pre", textAlign: "left" }}>
                                <code>{item.output}</code>
                              </pre>
                            )}
                            {item.error && (
                              <pre style={{ margin: "0.5rem 0 0", padding: "0.8rem", borderRadius: "10px", background: "#010307", color: "var(--err)", overflowX: "auto", fontSize: "0.75rem", fontFamily: "var(--mono)", border: "1px solid var(--err-bg)", whiteSpace: "pre-wrap", textAlign: "left" }}>
                                <code>{item.error}</code>
                              </pre>
                            )}
                            <div style={{ marginTop: "0.45rem", display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                              <small style={{ color: "var(--ink-4)" }}>
                                {!item.output && !item.error && "Command recorded"}
                              </small>
                              {item.service_id && (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => {
                                    const target = services.find((service) => service.id === item.service_id);
                                    if (target) {
                                      setSelectedService(target);
                                      loadServiceCapabilities(target.id);
                                      loadServiceSummary(target.id);
                                      loadServiceReleaseTimeline(target.id);
                                      loadServiceMetrics(target.id);
                                    }
                                  }}
                                >
                                  Open service
                                </button>
                              )}
                            </div>
                          </article>
                        ))}
                        {nodeJobHistory.items.length === 0 && (
                          <p style={{ color: "var(--ink-4)" }}>No deployment or Ansible jobs have been recorded for this node yet.</p>
                        )}
                      </div>
                    </>
                  ) : (
                    <p style={{ color: "var(--ink-4)" }}>Loading recent node jobs...</p>
                  )}
                </div>

                <div className="services-section">
                  <div className="services-head">
                    <h3>Services <span className="ct">{services.filter(s => s.node_id === selectedNode.id).length} running</span></h3>
                    <button className="btn btn-primary btn-sm" onClick={() => setCatalogDrawerVisible(true)}>
                      <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
                      Add service
                    </button>
                  </div>
                  <div className="service-stack">
                    {services.filter(s => s.node_id === selectedNode.id).map((service) => (
                      <div key={service.id} className={`svc-card ${service.status}`}>
                        <div className="svc-icon">{service.name[0]}</div>
                        <div className="svc-info">
                          <div className="nm" style={{ fontWeight: 600 }}>{service.name}</div>
                          <div className="meta">v1.0.0 · kind {service.kind} · image <code>{service.image}</code></div>
                        </div>
                        <div className="svc-ports"><span className="port">:8080</span></div>
                        <div className="svc-status">
                          <span className={`pill ${service.status === "healthy" || service.status === "running" ? "pill-ok" : "pill-warn"}`}>{service.status}</span>
                        </div>
                        <div className="svc-acts">
                          <button className="icon-btn" title="Inspect" onClick={() => { setSelectedService(service); loadServiceCapabilities(service.id); loadServiceSummary(service.id); loadServiceReleaseTimeline(service.id); loadServiceMetrics(service.id); }}><svg className="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg></button>
                          <button className="icon-btn" title="Configure install" onClick={() => openServiceEditor(service)}><svg className="ic" viewBox="0 0 24 24"><path d="M12 15.5A3.5 3.5 0 1112 8a3.5 3.5 0 010 7.5z"/><path d="M19.4 15a1.7 1.7 0 00.34 1.88l.06.06a2 2 0 01-2.83 2.83l-.06-.06A1.7 1.7 0 0015 19.4a1.7 1.7 0 00-1 1.55V21a2 2 0 01-4 0v-.09A1.7 1.7 0 009 19.4a1.7 1.7 0 00-1.88.34l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.88l-.06-.06a2 2 0 012.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 014 0v.09A1.7 1.7 0 0015 4.6a1.7 1.7 0 001.88-.34l.06-.06a2 2 0 012.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 001.55 1H21a2 2 0 010 4h-.09A1.7 1.7 0 0019.4 15z"/></svg></button>
                          <button className="icon-btn" title="Logs" onClick={() => { setSelectedService(service); loadDiagnostics(service); setActiveView("diagnostics"); setDiagTab("tail"); }}><svg className="ic" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg></button>
                          <button className="icon-btn" title="Deploy" onClick={() => openDeploymentModal(service)}><svg className="ic" viewBox="0 0 24 24"><path d="M12 2v20M17 5l-5-5-5 5"/></svg></button>
                          <button className="icon-btn danger" title="Uninstall" onClick={() => requestDelete("service", service.id, service.name)}><svg className="ic" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m1 0v14a2 2 0 01-2 2H8a2 2 0 01-2-2V6h12z"/></svg></button>
                        </div>
                      </div>
                    ))}
                    {services.filter(s => s.node_id === selectedNode.id).length === 0 && (
                      <div className="empty-state">
                        <h3>No installed services</h3>
                        <p>Open the service catalog to install service cards on this node.</p>
                      </div>
                    )}
                  </div>
                </div>

                {selectedService && serviceSummary && selectedService.node_id === selectedNode.id && serviceSummary.service_id === selectedService.id && (
                  <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: "16px", padding: "1rem", background: "rgba(255,255,255,0.55)" }}>
                    <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
                      <h2>Service Operations Cockpit</h2>
                      <span>{serviceSummary.name} · {serviceSummary.subsystem}</span>
                    </div>

                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.85rem" }}>
                      <span className={`pill ${serviceSummary.status === "healthy" || serviceSummary.status === "running" ? "pill-ok" : "pill-warn"}`}>{serviceSummary.status}</span>
                      <span className={`pill ${serviceSummary.dependency.ok ? "pill-ok" : "pill-warn"}`}>{serviceSummary.dependency.ok ? "dependencies ready" : "dependency attention"}</span>
                      <span className={`pill ${serviceSummary.latest_slo?.status === "burning" ? "pill-error" : "pill-ok"}`}>{serviceSummary.latest_slo?.status ?? "no slo"}</span>
                      <span className={`pill ${serviceSummary.latest_drift?.status === "drifted" ? "pill-warn" : "pill-ok"}`}>{serviceSummary.latest_drift?.status ?? "no drift scan"}</span>
                      <span className={`pill ${serviceSummary.latest_backup?.status === "success" ? "pill-ok" : "pill-warn"}`}>{serviceSummary.latest_backup ? `backup ${serviceSummary.latest_backup.status}` : "no backup yet"}</span>
                    </div>

                    <div className="spec-sheet" style={{ marginBottom: "1rem" }}>
                      <div className="spec-cell"><div className="l">Container</div><div className="v"><code>{serviceSummary.container_name}</code></div></div>
                      <div className="spec-cell"><div className="l">Kind</div><div className="v" style={{ textTransform: "capitalize" }}>{serviceSummary.kind}</div></div>
                      <div className="spec-cell"><div className="l">Snapshots</div><div className="v">{serviceSummary.snapshot_count}</div></div>
                      <div className="spec-cell"><div className="l">Open Incidents</div><div className="v">{serviceSummary.active_incidents.length}</div></div>
                      <div className="spec-cell"><div className="l">Recent Events</div><div className="v">{serviceSummary.recent_event_count}</div></div>
                      <div className="spec-cell"><div className="l">Image</div><div className="v"><code>{serviceSummary.image}</code></div></div>
                    </div>

                    <div className="actions compact" style={{ marginBottom: "1rem", flexWrap: "wrap" }}>
                      <button className="btn btn-primary btn-sm" onClick={() => openDeploymentModal(selectedService)}>Deployment control</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedService(selectedService); loadDiagnostics(selectedService); setActiveView("diagnostics"); setDiagTab("tail"); }}>Open logs</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedService(selectedService); loadConfig(selectedService); setActiveView("config"); }}>Open config</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => backupService(selectedService)}>Run backup</button>
                      <button className="btn btn-secondary btn-sm" onClick={detectConfigDrift}>Detect drift</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => openIncident(selectedService)}>Open incident</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => releaseService(selectedService)}>Create release</button>
                    </div>

                    {serviceMetrics && serviceMetrics.service_id === selectedService.id && (
                      <div style={{ marginBottom: "1rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                          <strong>Runtime telemetry</strong>
                          {renderMetricWindowPicker(serviceMetricsWindow, setServiceMetricsWindow)}
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "0.75rem" }}>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>CPU / Memory</strong>
                          <div style={{ marginTop: "0.3rem", color: "var(--ink-3)" }}>
                            {serviceMetrics.cpu_percent}% CPU · {serviceMetrics.memory_mb} MB · {serviceMetrics.window}
                          </div>
                          {renderMetricSparkline(serviceMetrics.cpu_series, "linear-gradient(180deg, #38bdf8, #0f172a)")}
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Error Rate</strong>
                          <div style={{ marginTop: "0.3rem", color: "var(--ink-3)" }}>
                            {serviceMetrics.log_error_rate.toFixed(2)}/min · p95 {serviceMetrics.latency_ms_p95} ms
                          </div>
                          {renderMetricSparkline(serviceMetrics.error_rate_series, "linear-gradient(180deg, #f97316, #7c2d12)")}
                          <div style={{ marginTop: "0.5rem" }}>
                            <button
                              className={`btn btn-sm ${serviceMetrics.log_error_rate >= 0.4 ? "btn-primary" : "btn-secondary"}`}
                              onClick={() => { setSelectedService(selectedService); loadDiagnostics(selectedService); setActiveView("diagnostics"); setDiagTab("tail"); }}
                            >
                              {serviceMetrics.log_error_rate >= 0.4 ? "Investigate logs" : "Open logs"}
                            </button>
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Queue / Restarts</strong>
                          <div style={{ marginTop: "0.3rem", color: "var(--ink-3)" }}>
                            depth {serviceMetrics.queue_depth} · restarts {serviceMetrics.restart_count}
                          </div>
                          {renderMetricSparkline(serviceMetrics.queue_depth_series, "linear-gradient(180deg, #10b981, #064e3b)")}
                        </div>
                      </div>
                      </div>
                    )}

                    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1rem" }}>
                      <div>
                        <strong style={{ display: "block", marginBottom: "0.5rem" }}>Dependency readiness</strong>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px", background: "rgba(255,255,255,0.02)" }}>
                          <div style={{ fontSize: "0.9rem", color: "var(--ink-3)" }}>{serviceSummary.dependency.message}</div>
                          {serviceSummary.dependency.missing.length > 0 && (
                            <div style={{ marginTop: "0.5rem" }}>
                              <small style={{ color: "var(--ink-4)" }}>Missing cards</small>
                              <div className="tags" style={{ marginTop: "0.25rem" }}>
                                {serviceSummary.dependency.missing.map((item) => <span key={item}>{item}</span>)}
                              </div>
                            </div>
                          )}
                          {serviceSummary.dependency.stopped.length > 0 && (
                            <div style={{ marginTop: "0.5rem" }}>
                              <small style={{ color: "var(--ink-4)" }}>Stopped targets</small>
                              <div className="tags" style={{ marginTop: "0.25rem" }}>
                                {serviceSummary.dependency.stopped.map((item) => <span key={item}>{item}</span>)}
                              </div>
                            </div>
                          )}
                        </div>

                        <strong style={{ display: "block", margin: "1rem 0 0.5rem" }}>Recent service events</strong>
                        <div className="timeline">
                          {serviceSummary.recent_events.map((event) => (
                            <article key={event.id}>
                              <span className={`status ${event.level === "error" ? "error" : event.level === "warning" ? "warning" : "running"}`}>{event.category}</span>
                              <strong>{event.message}</strong>
                              <small>{formatLocalTimestamp(event.created_at)}</small>
                            </article>
                          ))}
                          {serviceSummary.recent_events.length === 0 && (
                            <p style={{ color: "var(--ink-4)" }}>No service-scoped events recorded yet.</p>
                          )}
                        </div>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Latest monitoring</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceSummary.latest_monitoring ? `${serviceSummary.latest_monitoring.name} · ${serviceSummary.latest_monitoring.value}` : "No monitoring sweep yet"}
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Latest deployment job</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceSummary.latest_job ? `${serviceSummary.latest_job.action} · ${serviceSummary.latest_job.status}` : "No deployment job yet"}
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Latest release</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceSummary.latest_release ? `${serviceSummary.latest_release.version} · ${serviceSummary.latest_release.status}` : "No release history yet"}
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Latest runbook</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceSummary.latest_runbook ? `${serviceSummary.latest_runbook.runbook_key} · ${serviceSummary.latest_runbook.status}` : "No runbook execution yet"}
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Active incidents</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceSummary.active_incidents.length > 0
                              ? serviceSummary.active_incidents.map((incident) => incident.title).join(", ")
                              : "No open incidents"}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div style={{ marginTop: "1rem", display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: "1rem" }}>
                      <div>
                        <div className="panel-title" style={{ marginBottom: "0.65rem" }}>
                          <h2>Release & Rollback Timeline</h2>
                          <span>{serviceReleaseTimeline?.rollback_available ? "rollback available" : "no pending rollback"}</span>
                        </div>
                        <div className="timeline">
                          {(serviceReleaseTimeline?.items ?? []).map((item) => (
                            <article key={item.release.id}>
                              <span className={`status ${item.rollback_executed ? "warning" : "running"}`}>
                                {item.release.status}
                              </span>
                              <strong>{item.release.version}</strong>
                              <p>
                                {item.release.strategy} · <code>{item.release.image}</code>
                              </p>
                              <small>{formatLocalTimestamp(item.release.created_at)}</small>
                              <div style={{ marginTop: "0.35rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                                {item.notes.map((note) => (
                                  <span key={`${item.release.id}-${note}`} className="pill" style={{ fontSize: "0.7rem" }}>{note}</span>
                                ))}
                              </div>
                              <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => loadReleases(selectedService)} disabled={!selectedService}>
                                  View releases
                                </button>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => rollbackRelease(item.release)}
                                  disabled={item.rollback_executed}
                                >
                                  {item.rollback_executed ? "Rollback applied" : "Rollback to previous image"}
                                </button>
                              </div>
                              {item.related_events.length > 0 && (
                                <div style={{ marginTop: "0.5rem" }}>
                                  <small style={{ color: "var(--ink-4)" }}>Correlated events</small>
                                  <div style={{ marginTop: "0.25rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                                    {item.related_events.map((event) => (
                                      <small key={event.id} style={{ color: "var(--ink-3)" }}>
                                        {event.category}: {event.message}
                                      </small>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </article>
                          ))}
                          {(serviceReleaseTimeline?.items.length ?? 0) === 0 && (
                            <p style={{ color: "var(--ink-4)" }}>No release timeline yet. Create a release to start change tracking.</p>
                          )}
                        </div>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Current image</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            <code>{serviceReleaseTimeline?.current_image ?? serviceSummary.image}</code>
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Latest rollback job</strong>
                          <div style={{ marginTop: "0.35rem", color: "var(--ink-3)" }}>
                            {serviceReleaseTimeline?.latest_rollback_job
                              ? `${serviceReleaseTimeline.latest_rollback_job.action} · ${serviceReleaseTimeline.latest_rollback_job.status}`
                              : "No rollback executed yet"}
                          </div>
                        </div>
                        <div style={{ padding: "0.85rem", border: "1px solid var(--line-2)", borderRadius: "12px" }}>
                          <strong>Recent change feed</strong>
                          <div style={{ marginTop: "0.4rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            {(serviceReleaseTimeline?.recent_change_events ?? []).slice(0, 5).map((event) => (
                              <div key={event.id}>
                                <small style={{ color: "var(--ink-4)" }}>{event.category}</small>
                                <div style={{ color: "var(--ink-3)" }}>{event.message}</div>
                              </div>
                            ))}
                            {(serviceReleaseTimeline?.recent_change_events.length ?? 0) === 0 && (
                              <div style={{ color: "var(--ink-4)" }}>No correlated release/config/drift events yet.</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="node-detail" style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
                <h3>Select a node</h3>
                <p style={{ color: "var(--ink-4)" }}>Select a host node from the list on the left to configure specs and services.</p>
              </div>
            )}
          </div>
        )}

        {clusterSubTab === "topology" && (
          <GlassCard className="wide" style={{ padding: "1.5rem" }}>
            <div className="panel-title" style={{ marginBottom: "1rem" }}>
              <h2>Cluster Topology Dependency</h2>
              <span>Subsystems &amp; deployment sequence</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.5rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {Object.entries(topology?.subsystems ?? {}).map(([subsystem, keys]) => (
                  <div 
                    key={subsystem}
                    onClick={() => { setSelectedSubsystem(subsystem); planSubsystem(subsystem); }}
                    style={{
                      cursor: "pointer",
                      padding: "1rem",
                      borderRadius: "12px",
                      border: selectedSubsystem === subsystem ? "1px solid var(--navy)" : "1px solid var(--line)",
                      background: selectedSubsystem === subsystem ? "rgba(99, 102, 241, 0.08)" : "transparent"
                    }}
                  >
                    <strong>{subsystem}</strong>
                    <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
                      {keys.slice(0, 3).map(k => <span key={k} className="pill" style={{ scale: "0.8" }}>{k}</span>)}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ borderLeft: "1px solid var(--line)", paddingLeft: "1.5rem" }}>
                {selectedSubsystem ? (
                  <div>
                    <h3>{selectedSubsystem} rollout plan</h3>
                    {subsystemPlan ? (
                      <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                        <p style={{ color: "var(--ink-3)" }}>{subsystemPlan.summary}</p>
                        <div className="timeline">
                          {subsystemPlan.steps.map((step, idx) => (
                            <article key={`${step.service_key}-${idx}`} style={{ display: "flex", flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                              <div>
                                <strong>Step {idx + 1}: {step.name}</strong>
                                <small style={{ display: "block", color: "var(--ink-4)" }}>Action: {step.action} · Container: {step.container_name}</small>
                              </div>
                              <span className={`pill ${step.status === "healthy" || step.status === "running" ? "pill-ok" : "pill-warn"}`}>{step.status}</span>
                            </article>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <button className="btn btn-primary" style={{ marginTop: "1rem" }} onClick={() => planSubsystem(selectedSubsystem)}>Generate Rollout Plan</button>
                    )}
                  </div>
                ) : (
                  <p style={{ color: "var(--ink-4)" }}>Select a subsystem from the left to visualize its topological bootstrap order.</p>
                )}
              </div>
            </div>
          </GlassCard>
        )}

        {clusterSubTab === "policy" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
            <GlassCard style={{ padding: "1.5rem" }}>
              <div className="panel-title" style={{ marginBottom: "1rem" }}>
                <h2>Policy Violations &amp; Risk</h2>
                <button className="btn btn-secondary btn-sm" onClick={runPolicyScan}>Scan policies</button>
              </div>
              <div className="timeline">
                {findings.map((f) => (
                  <article key={f.id} style={{ borderLeft: `3px solid ${f.severity === "high" ? "var(--err)" : "var(--warn)"}` }}>
                    <span className="pill" style={{ scale: "0.8", alignSelf: "flex-start" }}>{f.severity}</span>
                    <strong>{f.rule_id}</strong>
                    <p style={{ fontSize: "0.85rem", margin: "4px 0" }}>{f.message}</p>
                    <small style={{ color: "var(--navy)" }}>Remediation: {f.remediation}</small>
                  </article>
                ))}
                {findings.length === 0 && <p>No policy violations found in this cluster. Run a policy scan.</p>}
              </div>
            </GlassCard>

            <GlassCard style={{ padding: "1.5rem" }}>
              <div className="panel-title" style={{ marginBottom: "1rem" }}>
                <h2>Relational Force-Delete Approvals</h2>
                <span>Governed lifecycle safeties</span>
              </div>
              <div className="timeline">
                {forceApprovals.map((approval) => (
                  <article key={approval.id}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <strong>Approval Request #{approval.id}</strong>
                      <span className={`pill ${approval.status === "approved" ? "pill-ok" : "pill-warn"}`}>{approval.status}</span>
                    </div>
                    <p style={{ fontSize: "0.85rem", margin: "4px 0" }}><strong>Reason:</strong> {approval.reason}</p>
                    <small style={{ color: "var(--ink-4)" }}>Requested by {approval.requested_by} · {formatExpiry(approval.expires_at)}</small>
                  </article>
                ))}
                {forceApprovals.length === 0 && <p>No active force-delete approvals requested.</p>}
              </div>
            </GlassCard>
          </div>
        )}

        {clusterSubTab === "audit" && (
          <GlassCard className="wide" style={{ padding: "1.5rem" }}>
            <div className="panel-title" style={{ marginBottom: "1.5rem" }}>
              <h2>Operations &amp; Audit Logs Feed</h2>
              <button className="btn btn-secondary btn-sm" onClick={createAuditExport}>Export Audit Trail</button>
            </div>
            {clusterOperations ? (
              <>
                <div className="checks" style={{ marginBottom: "1rem" }}>
                  <div>
                    <span className="status running">events</span>
                    <strong>{clusterOperations.total_events}</strong>
                    <small>recent ops</small>
                  </div>
                  <div>
                    <span className="status running">change</span>
                    <strong>{clusterOperations.change_events}</strong>
                    <small>change events</small>
                  </div>
                  <div>
                    <span className="status warning">recovery</span>
                    <strong>{clusterOperations.recovery_events}</strong>
                    <small>incident/runbook</small>
                  </div>
                  <div>
                    <span className="status error">govern</span>
                    <strong>{clusterOperations.governance_events}</strong>
                    <small>approvals/gates</small>
                  </div>
                </div>
                <div className="timeline">
                  {clusterOperations.items.map((item) => (
                    <article key={`cluster-op-${item.id}`}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
                        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                          <span className={`status ${item.action_family === "governance" ? "error" : item.action_family === "recovery" ? "warning" : "running"}`}>
                            {item.action_family}
                          </span>
                          <strong>{item.message}</strong>
                        </div>
                        <span style={{ fontFamily: "var(--mono)", fontSize: "0.75rem", color: "var(--ink-4)" }}>
                          {formatLocalTimestamp(item.created_at)}
                        </span>
                      </div>
                      <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "var(--ink-3)" }}>
                        {item.service_name ? `${item.service_name}${item.service_key ? ` (${item.service_key})` : ""}` : "cluster-scope"} · {item.node_name ?? "node n/a"} · category {item.category}
                      </p>
                      <small style={{ color: "var(--ink-4)" }}>
                        Level: <span className={`status-dot ${item.level}`} style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", margin: "0 4px" }}></span>{item.level}
                      </small>
                      {item.service_id && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <button className="btn btn-secondary btn-sm" onClick={() => focusServiceInCluster(item.service_id!)}>Open service context</button>
                        </div>
                      )}
                    </article>
                  ))}
                  {clusterOperations.items.length === 0 && (
                    <p style={{ color: "var(--ink-4)" }}>No cluster operations recorded yet.</p>
                  )}
                </div>
              </>
            ) : (
              <p style={{ color: "var(--ink-4)" }}>Loading cluster operations feed...</p>
            )}
          </GlassCard>
        )}
      </div>
    );
  }

  function renderConfigManagerView() {
    // Config Manager with side-by-side tree and diff navigator (08-config-manager.html reference)
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Configuration <em>Manager</em></h1>
            <p className="sub">Inspect version history, restore older snapshots, or compare configuration drifts side-by-side.</p>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "1.5rem", minHeight: "600px" }}>
          {/* Left hierarchy navigator */}
          <GlassCard style={{ padding: "1rem" }}>
            {renderTreeNavigator(async (service) => {
              await loadConfig(service, configSource);
            }, selectedService?.id ?? null)}
          </GlassCard>

          {/* Right main workspace panel */}
          {selectedService ? (
            <GlassCard style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>{selectedService.name} config</h3>
                  <small style={{ color: "var(--ink-4)" }}>Key: <code>{selectedService.service_key}</code> · Strategy: {getConfigStrategy(capabilities, selectedService)}</small>
                  {config && (
                    <div className="tags" style={{ marginTop: "0.45rem" }}>
                      <span>{config.config_source_label || config.content_source}</span>
                      <span>{config.drift_state}</span>
                      <span>{config.snapshot_count} checkpoints</span>
                      {config.active_checkpoint && <span>active v{config.active_checkpoint.version}</span>}
                      {config.config_path && <span><code>{config.config_path}</code></span>}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button className="btn btn-secondary btn-sm" onClick={captureSnapshot}>Capture snapshot</button>
                  <button className="btn btn-secondary btn-sm" onClick={detectConfigDrift}>Detect drift</button>
                  <button className="btn btn-primary btn-sm" onClick={applyCurrentConfig}>Apply config</button>
                </div>
              </div>

              {/* Workspaces tabs */}
              <div className="cluster-tabs">
                <div className={`tab ${configTab === "current" ? "active" : ""}`} onClick={() => setConfigTab("current")}>Current Config</div>
                <div className={`tab ${configTab === "timeline" ? "active" : ""}`} onClick={() => setConfigTab("timeline")}>Checkpoint Timeline</div>
                <div className={`tab ${configTab === "compare" ? "active" : ""}`} onClick={() => setConfigTab("compare")}>Compare / Diff</div>
                <div className={`tab ${configTab === "migration" ? "active" : ""}`} onClick={() => setConfigTab("migration")}>Ansible migration</div>
              </div>

              {/* Sub-tabs views */}
              {configTab === "current" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
                  <textarea 
                    value={config?.content ?? ""} 
                    onChange={(e) => setConfig(config ? { ...config, content: e.target.value } : null)}
                    style={{
                      flex: 1,
                      minHeight: "360px",
                      background: "#020408",
                      color: "#38bdf8",
                      fontFamily: "var(--mono)",
                      fontSize: "0.85rem",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "10px",
                      padding: "1rem",
                      outline: "none",
                      resize: "vertical"
                    }}
                  />
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button 
                      className="btn btn-secondary btn-sm" 
                      onClick={async () => {
                        if (!selectedService || !config) return;
                        const validation = await api<{ ok: boolean; message: string }>(`/api/services/${selectedService.id}/config/validate`, {
                          method: "POST",
                          body: JSON.stringify({ content: config.content }),
                        });
                        setNotice(validation.message);
                      }}
                    >
                      Validate YAML Syntax
                    </button>
                  </div>
                </div>
              )}

              {configTab === "timeline" && (
                <div className="timeline">
                  {(configTimelinePage?.items ?? []).map((event) => (
                    <article key={event.id}>
                      <span className="pill" style={{ scale: "0.8", alignSelf: "flex-start" }}>{event.action}</span>
                      <strong>{event.message}</strong>
                      <small style={{ color: "var(--ink-4)" }}>by {event.actor} · {formatLocalTimestamp(event.created_at)}</small>
                    </article>
                  ))}
                  {(!configTimelinePage || configTimelinePage.items.length === 0) && <p>No checkpoints found for this configuration.</p>}
                </div>
              )}

              {configTab === "compare" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                    <span>Compare snapshot</span>
                    <select value={compareSnapshotLeft || ""} onChange={(e) => setCompareSnapshotLeft(Number(e.target.value) || null)}>
                      <option value="">Choose version...</option>
                      {(snapshotPage?.items ?? []).map(s => <option key={s.id} value={s.id}>v{s.version} - {s.name}</option>)}
                    </select>
                    <span>with</span>
                    <select value={compareSnapshotRight || ""} onChange={(e) => setCompareSnapshotRight(Number(e.target.value) || null)}>
                      <option value="">Choose version...</option>
                      {(snapshotPage?.items ?? []).map(s => <option key={s.id} value={s.id}>v{s.version} - {s.name}</option>)}
                    </select>
                    <button className="btn btn-primary btn-sm" onClick={compareSelectedSnapshots}>Compare Diff</button>
                  </div>

                  {snapshotCompare && (
                    <div style={{ padding: "0.9rem 1rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                      <strong>{snapshotCompare.summary}</strong>
                      <div style={{ color: "var(--ink-4)", marginTop: "0.25rem", fontSize: "0.85rem" }}>
                        Left: v{snapshotCompare.left_snapshot.version} {snapshotCompare.left_snapshot.name} · Right: v{snapshotCompare.right_snapshot.version} {snapshotCompare.right_snapshot.name}
                      </div>
                    </div>
                  )}

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    <div style={{ background: "#020408", padding: "1rem", borderRadius: "10px", minHeight: "200px" }}>
                      <small style={{ color: "var(--ink-4)", display: "block", marginBottom: "0.5rem" }}>Baseline snapshot</small>
                      <pre style={{ color: "#a7f3d0", fontSize: "0.8rem", overflowX: "auto" }}>
                        {snapshotCompare?.left_snapshot.content ?? "Select snapshots to inspect the left side."}
                      </pre>
                    </div>
                    <div style={{ background: "#020408", padding: "1rem", borderRadius: "10px", minHeight: "200px" }}>
                      <small style={{ color: "var(--ink-4)", display: "block", marginBottom: "0.5rem" }}>Compare target</small>
                      <pre style={{ color: "#fbcfe8", fontSize: "0.8rem", overflowX: "auto" }}>
                        {snapshotCompare?.right_snapshot.content ?? "Select snapshots to inspect the right side."}
                      </pre>
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--line)", borderRadius: "12px", padding: "1rem" }}>
                    <strong>Field differences</strong>
                    <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                      {(snapshotCompare?.differences ?? []).map((difference) => (
                        <div key={`${difference.field}-${JSON.stringify(difference.expected)}-${JSON.stringify(difference.actual)}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                            <strong>{difference.field}</strong>
                            <span className="pill pill-warn">{difference.severity}</span>
                          </div>
                          <div style={{ marginTop: "0.45rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                            <div>
                              <small style={{ color: "var(--ink-4)" }}>Left</small>
                              <pre style={{ marginTop: "0.2rem", background: "rgba(239, 68, 68, 0.08)", color: "#f87171", padding: "0.6rem", borderRadius: "8px", fontSize: "0.78rem", overflowX: "auto" }}>
                                {JSON.stringify(difference.expected, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <small style={{ color: "var(--ink-4)" }}>Right</small>
                              <pre style={{ marginTop: "0.2rem", background: "rgba(16, 185, 129, 0.08)", color: "#34d399", padding: "0.6rem", borderRadius: "8px", fontSize: "0.78rem", overflowX: "auto" }}>
                                {JSON.stringify(difference.actual, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      ))}
                      {snapshotCompare && snapshotCompare.differences.length === 0 && (
                        <div style={{ color: "var(--ink-4)" }}>The selected snapshots are identical.</div>
                      )}
                      {!snapshotCompare && (
                        <div style={{ color: "var(--ink-4)" }}>Select two snapshots and run Compare Diff to see exact field-level changes.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {configTab === "migration" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "0.75rem", alignItems: "end" }}>
                    <label className="field" style={{ margin: 0 }}>
                      <span>Baseline checkpoint</span>
                      <select value={compareSnapshotLeft || ""} onChange={(e) => setCompareSnapshotLeft(Number(e.target.value) || null)}>
                        <option value="">Choose baseline...</option>
                        {(snapshotPage?.items ?? []).map(s => <option key={`migration-left-${s.id}`} value={s.id}>v{s.version} - {s.name}</option>)}
                      </select>
                    </label>
                    <label className="field" style={{ margin: 0 }}>
                      <span>Target checkpoint</span>
                      <select value={compareSnapshotRight || ""} onChange={(e) => setCompareSnapshotRight(Number(e.target.value) || null)}>
                        <option value="">Choose target...</option>
                        {(snapshotPage?.items ?? []).map(s => <option key={`migration-right-${s.id}`} value={s.id}>v{s.version} - {s.name}</option>)}
                      </select>
                    </label>
                    <button className="btn btn-primary btn-sm" onClick={prepareConfigMigration}>Prepare</button>
                  </div>
                  {migrationArtifactId && (
                    <div className="tags">
                      <span>artifact {migrationArtifactId}</span>
                      <span>{migrationValidation || "validation pending"}</span>
                      {migrationApplyResult?.backup_snapshot_id && <span>backup snapshot #{migrationApplyResult.backup_snapshot_id}</span>}
                    </div>
                  )}
                  <textarea
                    className="input"
                    value={migrationContent || config?.content || ""}
                    onChange={(e) => setMigrationContent(e.target.value)}
                    style={{
                      minHeight: "360px",
                      background: "#020408",
                      color: "#a78bfa",
                      fontFamily: "var(--mono)",
                      fontSize: "0.85rem",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "10px",
                      padding: "1rem",
                      outline: "none",
                      resize: "vertical",
                    }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                    <div className="tags">
                      {(config?.peers ?? []).slice(0, 4).map((peer) => (
                        <span key={`config-peer-${peer.service_id}`}>{peer.node_name}: {peer.status}</span>
                      ))}
                      {(config?.peers ?? []).length === 0 && <span>no rollout peers</span>}
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button className="btn btn-secondary btn-sm" onClick={validateMigrationYaml}>Validate YAML</button>
                      <button className="btn btn-primary btn-sm" onClick={applyPreparedMigration}>Apply migration</button>
                      <button className="btn btn-secondary btn-sm" onClick={restorePreparedMigration}>Restore backup</button>
                    </div>
                  </div>
                </div>
              )}
            </GlassCard>
          ) : (
            <GlassCard style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
              <h3>Select a card</h3>
              <p style={{ color: "var(--ink-4)" }}>Select a node service card from the navigator tree to view and manage configs.</p>
            </GlassCard>
          )}
        </div>
      </div>
    );
  }

  function renderAiChat() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", minHeight: "450px" }}>
        {diagnosticsAnalysis && (
          <>
            <div style={{ padding: "1rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                <div>
                  <strong>Diagnostics analysis</strong>
                  <div style={{ color: "var(--ink-3)", marginTop: "0.3rem" }}>{diagnosticsAnalysis.overview}</div>
                </div>
                <span className={`pill ${diagnosticsAnalysis.overall_severity === "error" ? "pill-error" : diagnosticsAnalysis.overall_severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                  {diagnosticsAnalysis.overall_severity}
                </span>
              </div>
              {diagnosticsAnalysis.next_steps.length > 0 && (
                <div style={{ marginTop: "0.75rem" }}>
                  <small style={{ color: "var(--ink-4)" }}>Recommended next steps</small>
                  <div className="tags" style={{ marginTop: "0.35rem" }}>
                    {diagnosticsAnalysis.next_steps.map((step) => <span key={step}>{step}</span>)}
                  </div>
                </div>
              )}
              {diagnosticsAnalysis.historical_correlation.length > 0 && (
                <div style={{ marginTop: "0.9rem" }}>
                  <small style={{ color: "var(--ink-4)" }}>Historical correlation</small>
                  <div style={{ marginTop: "0.35rem", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                    {diagnosticsAnalysis.historical_correlation.map((entry) => (
                      <div key={entry} style={{ color: "var(--ink-3)", fontSize: "0.85rem" }}>{entry}</div>
                    ))}
                  </div>
                </div>
              )}
              {diagnosticsAnalysis.change_evidence.length > 0 && (
                <div style={{ marginTop: "0.9rem" }}>
                  <small style={{ color: "var(--ink-4)" }}>Likely change evidence</small>
                  <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                    {diagnosticsAnalysis.change_evidence.map((item, index) => (
                      <div
                        key={`${item.kind}-${item.created_at}-${index}`}
                        style={{
                          padding: "0.7rem 0.8rem",
                          border: "1px solid var(--line-2)",
                          borderRadius: "10px",
                          background: "rgba(255,255,255,0.02)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                          <strong>{item.title}</strong>
                          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
                            <span className={`pill ${item.severity === "error" ? "pill-error" : item.severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                              {item.kind}
                            </span>
                            <span className="pill" style={{ fontSize: "0.72rem" }}>{item.confidence}% confidence</span>
                          </div>
                        </div>
                        <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{item.summary}</div>
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                          {item.detail} · {formatLocalTimestamp(item.created_at)}
                        </div>
                        {item.drift_fields && item.drift_fields.length > 0 && (
                          <div style={{ marginTop: "0.35rem" }}>
                            <small style={{ color: "var(--ink-4)" }}>Changed keys</small>
                            <div className="tags" style={{ marginTop: "0.25rem" }}>
                              {item.drift_fields.map((field) => <span key={`${item.title}-${field}`}>{field}</span>)}
                            </div>
                          </div>
                        )}
                        {item.drift_preview && item.drift_preview.length > 0 && (
                          <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            <small style={{ color: "var(--ink-4)" }}>Drift preview</small>
                            {item.drift_preview.map((preview, previewIndex) => (
                              <div
                                key={`${item.title}-preview-${preview.field ?? previewIndex}`}
                                style={{
                                  padding: "0.55rem 0.65rem",
                                  borderRadius: "8px",
                                  border: "1px solid var(--line)",
                                  background: "rgba(255,255,255,0.03)",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                                  <strong style={{ fontSize: "0.82rem" }}>{preview.field ?? "changed field"}</strong>
                                  {preview.severity && (
                                    <span className={`pill ${preview.severity === "error" ? "pill-error" : preview.severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                                      {preview.severity}
                                    </span>
                                  )}
                                </div>
                                <div style={{ color: "var(--ink-4)", fontSize: "0.78rem", marginTop: "0.2rem" }}>
                                  Expected: {String(preview.expected ?? "n/a")}
                                </div>
                                <div style={{ color: "var(--ink-4)", fontSize: "0.78rem", marginTop: "0.1rem" }}>
                                  Actual: {String(preview.actual ?? "n/a")}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {item.baseline_snapshot_id && (
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                            Baseline snapshot: #{item.baseline_snapshot_id}
                          </div>
                        )}
                        {typeof item.snapshot_version === "number" && (
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                            Snapshot version: v{item.snapshot_version}{item.snapshot_id ? ` · snapshot #${item.snapshot_id}` : ""}
                            {item.actor ? ` · actor ${item.actor}` : ""}
                          </div>
                        )}
                        <div style={{ marginTop: "0.55rem", display: "flex", justifyContent: "flex-end" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => openDiagnosticsChangeEvidence(item)}
                          >
                            {item.target_view === "release" ? "Open release context" : item.target_view === "config-compare" ? "Open config compare" : "Open config timeline"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {diagnosticsAnalysis.recent_incidents.length > 0 && (
                <div style={{ marginTop: "0.9rem" }}>
                  <small style={{ color: "var(--ink-4)" }}>Recent incidents in this diagnostics context</small>
                  <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                    {diagnosticsAnalysis.recent_incidents.map((incident) => (
                      <div
                        key={`diag-incident-${incident.id}`}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: "0.75rem",
                          alignItems: "center",
                          padding: "0.6rem 0.75rem",
                          border: "1px solid var(--line-2)",
                          borderRadius: "10px",
                        }}
                        >
                          <div>
                            <strong>{incident.title}</strong>
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                            #{incident.id} · {incident.severity} · {incident.status} · {formatLocalTimestamp(incident.created_at)}
                          </div>
                          <div style={{ color: "var(--ink-3)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                            Match: {incident.match_reason}
                            {incident.latest_runbook_key ? ` · Last runbook: ${incident.latest_runbook_key} (${incident.latest_runbook_status})` : ""}
                          </div>
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                            Suggested now: {incident.suggested_runbook_key}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => runDiagnosticsInsightAction({
                              action_id: "open-existing-incident",
                              label: `Review incident #${incident.id}`,
                              description: incident.summary,
                              service_key: diagnosticsAnalysis.source_service_key,
                              incident_id: incident.id,
                              runbook_key: null,
                              target_view: "monitoring",
                              recommended: false,
                            })}
                          >
                            Review
                          </button>
                          {incident.status === "open" && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => runDiagnosticsInsightAction({
                                action_id: "run-incident-runbook",
                                label: incident.suggested_runbook_key === "dependency-recovery"
                                  ? "Run dependency recovery"
                                  : incident.suggested_runbook_key === "config-rollback"
                                  ? "Run config rollback"
                                  : "Run restart runbook",
                                description: incident.remediation,
                                service_key: diagnosticsAnalysis.source_service_key,
                                incident_id: incident.id,
                                runbook_key: incident.suggested_runbook_key,
                                target_view: "monitoring",
                                recommended: false,
                              })}
                            >
                              Runbook
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="timeline">
              {diagnosticsAnalysis.insights.map((insight) => (
                <article key={insight.insight_id}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                      <span className={`status ${insight.severity === "error" ? "error" : insight.severity === "warning" ? "warning" : "running"}`}>
                        {insight.severity}
                      </span>
                      <strong>{insight.title}</strong>
                    </div>
                    <span className="pill" style={{ fontSize: "0.72rem" }}>{insight.confidence}% confidence</span>
                  </div>
                  <p>{insight.summary}</p>
                  <small>{insight.rationale}</small>
                  {insight.evidence_refs.length > 0 && (
                    <div style={{ marginTop: "0.5rem" }}>
                      <small style={{ color: "var(--ink-4)" }}>Evidence</small>
                      <div className="tags" style={{ marginTop: "0.25rem" }}>
                        {insight.evidence_refs.map((ref) => <span key={`${insight.insight_id}-${ref}`}>{ref}</span>)}
                      </div>
                    </div>
                  )}
                  {insight.supporting_evidence.length > 0 && (
                    <div style={{ marginTop: "0.65rem" }}>
                      <small style={{ color: "var(--ink-4)" }}>Open supporting evidence</small>
                      <div style={{ marginTop: "0.35rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                        {insight.supporting_evidence.map((evidence) => (
                          <button
                            key={`${insight.insight_id}-${evidence.evidence_id}`}
                            className="btn btn-secondary btn-sm"
                            style={{ justifyContent: "space-between" }}
                            onClick={() => openDiagnosticsSupportingEvidence(evidence)}
                          >
                            <span>{evidence.label}</span>
                            <span style={{ color: "var(--ink-4)", fontSize: "0.76rem" }}>{evidence.target_view}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {insight.actions.length > 0 && (
                    <div style={{ marginTop: "0.65rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      {insight.actions.map((action) => (
                        <button
                          key={`${insight.insight_id}-${action.action_id}-${action.service_key ?? "self"}`}
                          className={`btn btn-sm ${action.recommended ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => runDiagnosticsInsightAction(action)}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: "1rem", border: "1px solid var(--line)", borderRadius: "12px" }}>
          {analyticsMessages.map((msg, idx) => (
            <div key={idx} style={{ display: "flex", flexDirection: "column", alignSelf: msg.sender === "user" ? "flex-end" : "flex-start", maxWidth: "80%" }}>
              <div style={{
                background: msg.sender === "user" ? "var(--navy)" : "rgba(255, 255, 255, 0.05)",
                color: "#ffffff",
                padding: "0.75rem 1rem",
                borderRadius: msg.sender === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                fontSize: "0.9rem",
                lineHeight: "1.4"
              }}>
                {msg.text}
              </div>
              <span style={{ fontSize: "0.7rem", color: "var(--ink-4)", alignSelf: msg.sender === "user" ? "flex-end" : "flex-start", marginTop: "4px" }}>
                {msg.timestamp}
              </span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: "0.5rem", padding: "0.25rem 0 0" }}>
          <input
            type="text"
            className="input-text"
            style={{ flex: 1, background: "rgba(0, 0, 0, 0.2)", color: "#ffffff", border: "1px solid var(--line)", borderRadius: "6px", padding: "0.5rem 0.75rem" }}
            placeholder="Ask the SRE AI Analyst about logs, cpu usage, or service errors..."
            value={analyticsInput}
            onChange={(e) => setAnalyticsInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSendAnalyticsChat(); }}
          />
          <button className="btn btn-primary" onClick={handleSendAnalyticsChat}>Send</button>
        </div>
      </div>
    );
  }

  function renderDiagnosticsView() {
    // Diagnostics & live terminal logs (09-diagnostics.html reference)
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Diagnostics &amp; <em>Logs</em></h1>
            <p className="sub">Real-time Loki stream container console, file diagnostics, and SRE incident analytics chat.</p>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "1.5rem", minHeight: "600px" }}>
          {/* Left tree navigator */}
          <GlassCard style={{ padding: "1rem" }}>
            {renderTreeNavigator(async (service) => {
              await loadDiagnostics(service);
            }, selectedService?.id ?? null)}
          </GlassCard>

          {/* Right main workspace panel */}
          {selectedService ? (
            <GlassCard style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>{selectedService.name} diagnostics</h3>
                  <small style={{ color: "var(--ink-4)" }}>Target container: <code>{capabilities?.container_name}</code> · Status: <span className={`pill ${selectedService.status === "healthy" || selectedService.status === "running" ? "pill-ok" : "pill-warn"}`}>{selectedService.status}</span></small>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => loadDiagnostics(selectedService)}>Refresh logs</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => openIncident(selectedService)}>Open SRE incident</button>
                </div>
              </div>

              {/* Sub-tabs selectors */}
              <div className="cluster-tabs">
                <div className={`tab ${diagTab === "tail" ? "active" : ""}`} onClick={() => setDiagTab("tail")}>Live Tail Console</div>
                <div className={`tab ${diagTab === "files" ? "active" : ""}`} onClick={() => setDiagTab("files")}>Log Files</div>
                <div className={`tab ${diagTab === "analytics" ? "active" : ""}`} onClick={() => setDiagTab("analytics")}>SRE AI Incident Analyst</div>
              </div>

              {/* Tabs views */}
              {diagTab === "tail" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <select value={tailLines} onChange={(e) => setTailLines(Number(e.target.value))}>
                        <option value={100}>Tail 100 lines</option>
                        <option value={250}>Tail 250 lines</option>
                        <option value={500}>Tail 500 lines</option>
                      </select>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
                        <input type="checkbox" checked={autoPollLogs} onChange={(e) => setAutoPollLogs(e.target.checked)} />
                        Auto-poll logs
                      </label>
                    </div>
                    {diagnosticsLive && (
                      <small style={{ color: "var(--ink-4)" }}>Loaded {diagnosticsLive.lines.length} lines of stream telemetry</small>
                    )}
                  </div>

                  <div 
                    className="console"
                    style={{
                      flex: 1,
                      minHeight: "360px",
                      background: "#020408",
                      color: "#34d399",
                      fontFamily: "var(--mono)",
                      fontSize: "0.85rem",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "10px",
                      padding: "1rem",
                      overflowY: "auto",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.25rem"
                    }}
                  >
                    {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).map((line, index) => {
                      let timeStr = "";
                      try {
                        timeStr = new Date(line.timestamp).toISOString().replace("T", " ").substring(0, 19);
                      } catch {
                        timeStr = String(line.timestamp);
                      }
                      const levelUpper = (line.level || "INFO").toUpperCase().padEnd(5);
                      let levelColor = "#38bdf8";
                      if (levelUpper.includes("ERR")) levelColor = "#f87171";
                      else if (levelUpper.includes("WARN")) levelColor = "#fbbf24";
                      else if (levelUpper.includes("DEBUG")) levelColor = "#a78bfa";

                      return (
                        <div key={index} style={{ display: "flex", gap: "0.75rem", fontFamily: "var(--mono)", fontSize: "0.82rem", borderBottom: "1px solid rgba(255,255,255,0.02)", padding: "2px 0" }}>
                          <span style={{ color: "var(--ink-4)", flexShrink: 0 }}>{timeStr}</span>
                          <span style={{ color: levelColor, fontWeight: "bold", flexShrink: 0 }}>{levelUpper}</span>
                          <code style={{ color: "#e2e8f0", wordBreak: "break-all", textAlign: "left" }}>{line.message}</code>
                        </div>
                      );
                    })}
                    {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).length === 0 && (
                      <div style={{ color: "var(--ink-4)", textAlign: "center", padding: "2rem" }}>
                        No logs streamed yet. Trigger some container traffic or click Refresh.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {diagTab === "files" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div style={{ background: "rgba(255,255,255,0.02)", padding: "1rem", borderRadius: "10px", border: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                      <h4>File Accessibility checks</h4>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={runLogBackfill}
                        disabled={!diagnostics?.readiness.backfill_requirements?.ready}
                      >
                        Backfill to Loki
                      </button>
                    </div>
                    {diagnostics?.readiness.backfill_requirements && (
                      <div className="tags" style={{ marginTop: "0.55rem" }}>
                        <span>{diagnostics.readiness.backfill_requirements.loki_configured ? "Loki configured" : "Loki missing"}</span>
                        <span>{diagnostics.readiness.backfill_requirements.file_log_paths_present ? "file paths configured" : "file paths missing"}</span>
                        {diagnostics.readiness.backfill_requirements.requires_become && <span>requires sudo/become</span>}
                        {diagnostics.readiness.backfill_requirements.missing.map((item) => <span key={`backfill-missing-${item}`}>{item}</span>)}
                      </div>
                    )}
                    {diagnostics ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem" }}>
                        {diagnostics.readiness.paths_checked.map((p, idx) => (
                          <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                            <span><code>{p.path}</code></span>
                            <span className={`pill ${p.readable ? "pill-ok" : "pill-error"}`}>{p.readable ? "readable" : "restricted"}</span>
                          </div>
                        ))}
                      </div>
                    ) : <p>Loading checks...</p>}
                  </div>

                  <h4>Archived Log files list</h4>
                  <table className="lf-table" style={{ marginTop: "0.5rem" }}>
                    <thead>
                      <tr>
                        <th>File name path</th>
                        <th style={{ width: "120px" }}>Size</th>
                        <th style={{ width: "120px" }}>Line count</th>
                        <th style={{ width: "100px" }}>State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {archives.map((arch) => (
                        <tr 
                          key={arch.id} 
                          style={{ cursor: "pointer" }}
                          onClick={() => setSelectedArchive(arch)}
                        >
                          <td className="fn">
                            <span className="ico" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "24px", height: "18px", background: "var(--bg-sunken)", color: "var(--ink-3)", borderRadius: "4px", marginRight: "8px", fontSize: "8px", fontWeight: "bold" }}>LOG</span>
                            <code>{arch.path}</code>
                          </td>
                          <td className="size">{Math.round(arch.size_bytes / 1024)} KB</td>
                          <td className="lines">{arch.line_count}</td>
                          <td>
                            <span className={`pill ${arch.readable === "yes" ? "pill-ok" : "pill-warn"}`}>
                              {arch.readable}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {archives.length === 0 && (
                        <tr>
                          <td colSpan={4} style={{ padding: "1.5rem", textAlign: "center", color: "var(--ink-4)" }}>No log archive folders scanned.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {diagTab === "analytics" && renderAiChat()}
            </GlassCard>
          ) : (
            <GlassCard style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
              <h3>Select a card</h3>
              <p style={{ color: "var(--ink-4)" }}>Select a node service card from the navigator tree to open log consoles.</p>
            </GlassCard>
          )}
        </div>
      </div>
    );
  }

  function renderMonitoringView() {
    // SRE monitoring checklist, active incidents, SLO metrics (10-performance.html reference)
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>SRE Observability &amp; <em>Monitoring</em></h1>
            <p className="sub">Service checks sweeps, SLO targets evaluation, maintenance schedules, and active incident runbooks.</p>
          </div>
          <div className="actions">
            <button className="btn btn-primary" onClick={runMonitoringSweep}>Trigger Health Check</button>
            <button className="btn btn-secondary" onClick={evaluateSlo}>Evaluate SLOs</button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1.5rem" }}>
          {/* Left panel: SLOs & Health Checks */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>SLO Performance Dashboard</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {slos.map((s) => (
                  <div key={s.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: "10px" }}>
                    <div>
                      <strong>{s.name}</strong>
                      <small style={{ display: "block", color: "var(--ink-4)" }}>Observed {s.observed}% · Target {s.target}%</small>
                    </div>
                    <span className={`pill ${s.status === "burning" ? "pill-error" : "pill-ok"}`}>{s.status}</span>
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>Active Health checks ({checks.length})</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                {checks.map((c) => (
                  <div key={c.id} style={{ display: "flex", gap: "0.5rem", padding: "0.5rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line-2)", borderRadius: "8px" }}>
                    <span className={`status-dot ${c.status}`} style={{ width: "8px", height: "8px", borderRadius: "50%", alignSelf: "center", flexShrink: 0 }}></span>
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{c.name}</div>
                      <small style={{ color: "var(--ink-4)", display: "block" }}>{c.value}</small>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* Right panel: Active Incidents & Maintenance */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>Active Incidents</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {incidents.map((incident) => (
                  <div key={incident.id} style={{ padding: "1rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(255,255,255,0.02)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <strong>{incident.title}</strong>
                      <span className={`pill ${incident.severity === "sev1" ? "pill-error" : "pill-warn"}`}>{incident.severity}</span>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--ink-3)", margin: "4px 0" }}>{incident.summary}</p>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => runIncidentRunbook(incident)}>Runbook</button>
                      <button className="btn btn-primary btn-sm" onClick={() => resolveIncident(incident)}>Resolve</button>
                    </div>
                  </div>
                ))}
                {incidents.length === 0 && <p style={{ color: "var(--ink-4)" }}>No active SRE incidents reported. All systems green.</p>}
              </div>
            </GlassCard>

            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>Scheduled Maintenance</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {maintenance.map((m) => (
                  <div key={m.id} style={{ padding: "0.75rem", border: "1px solid var(--line-2)", borderRadius: "10px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <strong>{m.title}</strong>
                      <span className="pill pill-ok">{m.status}</span>
                    </div>
                    <small style={{ display: "block", color: "var(--ink-4)", marginTop: "4px" }}>Start: {formatLocalTimestamp(m.starts_at)}</small>
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.5rem" }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => completeMaintenance(m)}>Complete</button>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    );
  }

  function renderDrawers() {
    return (
      <>
        {/* SERVICE CATALOG DRAWER */}
        {catalogDrawerVisible && (
          <>
            <div className="drawer-backdrop" style={{ display: "block" }} onClick={() => setCatalogDrawerVisible(false)}></div>
            <aside className="drawer wide" style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1.5rem", right: 0 }}>
              <div className="drawer-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 style={{ fontSize: "1.5rem", fontFamily: "var(--display)" }}>Service catalog</h2>
                  <div className="sub" style={{ fontSize: "0.85rem", color: "var(--ink-4)" }}>Choose a service card to onboard it onto a node, then continue into config or deployment control.</div>
                </div>
                <button className="icon-btn" onClick={() => setCatalogDrawerVisible(false)}><svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
              </div>

              <div className="catalog-list" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto", flex: 1 }}>
                {catalog.map((card) => (
                  <div 
                    key={card.service_key} 
                    className="catalog-item"
                    onClick={() => openCatalogOnboarding(card)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "1rem",
                      padding: "1rem",
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--line)",
                      borderRadius: "12px",
                      cursor: "pointer",
                      transition: "all 0.2s"
                    }}
                  >
                    <div className="ico" style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--navy-100)", color: "var(--navy)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>
                      {card.name[0]}
                    </div>
                    <div className="info" style={{ flex: 1 }}>
                      <div className="nm" style={{ fontWeight: 600 }}>{card.name}</div>
                      <div className="desc" style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginTop: "2px" }}>{card.description || card.image}</div>
                      <div className="tags" style={{ display: "flex", gap: "0.25rem", marginTop: "4px" }}>
                        <span className="tag" style={{ fontSize: "0.7rem", scale: "0.9" }}>{card.subsystem}</span>
                        <span className="tag" style={{ fontSize: "0.7rem", scale: "0.9" }}>{card.kind}</span>
                        {card.configurable && <span className="tag" style={{ fontSize: "0.7rem", scale: "0.9" }}>config</span>}
                        {card.dependencies.length > 0 && <span className="tag" style={{ fontSize: "0.7rem", scale: "0.9" }}>{card.dependencies.length} deps</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </aside>
          </>
        )}

        {catalogOnboarding.visible && catalogOnboarding.card && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 110 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "640px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <h3 style={{ marginBottom: "0.25rem" }}>{catalogOnboarding.mode === "edit" ? "Configure Service Card" : "Onboard Service Card"}</h3>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>
                  {catalogOnboarding.mode === "edit" ? "Update" : "Register"} <strong>{catalogOnboarding.card.name}</strong> on a node, then continue into the right operator workflow.
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: "0.85rem" }}>
                <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                    <strong>{catalogOnboarding.card.name}</strong>
                    <div className="tags">
                      <span>{catalogOnboarding.card.kind}</span>
                      <span>{catalogOnboarding.card.subsystem}</span>
                    </div>
                  </div>
                  <div style={{ color: "var(--ink-3)", fontSize: "0.84rem", marginTop: "0.35rem" }}>
                    {catalogOnboarding.card.description || catalogOnboarding.card.image}
                  </div>
                  <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.4rem" }}>
                    Image <code>{catalogOnboarding.card.image}</code>
                  </div>
                  <div style={{ marginTop: "0.6rem" }}>
                    <small style={{ color: "var(--ink-4)" }}>Dependencies</small>
                    <div className="tags" style={{ marginTop: "0.25rem" }}>
                      {catalogOnboarding.card.dependencies.length > 0
                        ? catalogOnboarding.card.dependencies.map((item) => <span key={`catalog-onboard-dep-${item}`}>{item}</span>)
                        : <span>standalone</span>}
                    </div>
                  </div>
                  {catalogOnboarding.card.tags.length > 0 && (
                    <div style={{ marginTop: "0.6rem" }}>
                      <small style={{ color: "var(--ink-4)" }}>Traits</small>
                      <div className="tags" style={{ marginTop: "0.25rem" }}>
                        {catalogOnboarding.card.tags.map((item) => <span key={`catalog-onboard-tag-${item}`}>{item}</span>)}
                        {catalogOnboarding.card.configurable && <span>config-manager</span>}
                        {catalogOnboarding.card.log_paths.length > 0 && <span>{catalogOnboarding.card.log_paths.length} log path(s)</span>}
                      </div>
                    </div>
                  )}
                  <div style={{ marginTop: "0.7rem", padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                    <small style={{ color: "var(--ink-4)" }}>Service defaults & install preview</small>
                    <div className="tags" style={{ marginTop: "0.35rem" }}>
                      <span>{catalogOnboarding.card.ports.length} published port(s)</span>
                      <span>{catalogOnboarding.card.volumes.length} volume mount(s)</span>
                      <span>{catalogOnboarding.card.config_files.length} config file(s)</span>
                      <span>{Object.keys(catalogOnboarding.card.env || {}).length} env default(s)</span>
                    </div>
                    {Object.keys(catalogOnboarding.card.env || {}).length > 0 && (
                      <div style={{ marginTop: "0.45rem" }}>
                        <small style={{ color: "var(--ink-4)" }}>Environment defaults</small>
                        <div className="tags" style={{ marginTop: "0.25rem" }}>
                          {Object.entries(catalogOnboarding.card.env).slice(0, 6).map(([key, value]) => (
                            <span key={`catalog-env-${key}`}>{key}={String(value)}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {catalogOnboarding.card.config_files.length > 0 && (
                      <div style={{ marginTop: "0.45rem" }}>
                        <small style={{ color: "var(--ink-4)" }}>Config files</small>
                        <div className="tags" style={{ marginTop: "0.25rem" }}>
                          {catalogOnboarding.card.config_files.slice(0, 4).map((item) => <span key={`catalog-config-${item}`}>{item}</span>)}
                        </div>
                      </div>
                    )}
                    {catalogOnboarding.card.command && (
                      <pre style={{ margin: "0.45rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.72rem" }}>
                        <code>{catalogOnboarding.card.command}</code>
                      </pre>
                    )}
                  </div>
                </div>

                <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                  <div className="field">
                    <label>Target node</label>
                    <select
                      value={catalogOnboarding.nodeId}
                      disabled={catalogOnboarding.mode === "edit"}
                      onChange={async (e) => {
                        const nextNodeId = Number(e.target.value);
                        setCatalogOnboarding((current) => ({ ...current, nodeId: nextNodeId, error: "" }));
                        if (catalogOnboarding.card) {
                          try {
                            const schema = await loadInstallSchemaFor(catalogOnboarding.card, nextNodeId);
                            setCatalogOnboarding((current) => ({
                              ...current,
                              installSchema: schema,
                              installFieldValues: installSchemaValues(schema),
                            }));
                          } catch (error: any) {
                            setCatalogOnboarding((current) => ({ ...current, error: error.message || "Failed to load install schema." }));
                          }
                        }
                      }}
                    >
                      {(selectedCluster
                        ? nodes.filter((item) => item.cluster_id === selectedCluster.id)
                        : nodes
                      ).map((node) => (
                        <option key={`catalog-node-${node.id}`} value={node.id}>
                          {node.name} · {node.environment} · {node.host}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>Service display name</label>
                    <input
                      className="input"
                      value={catalogOnboarding.customName}
                      placeholder="Leave blank to use catalog name"
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, customName: e.target.value }))}
                    />
                  </div>
                  {catalogOnboarding.installSchema && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
                      {Array.from(new Set(catalogOnboarding.installSchema.fields.map((field) => field.section))).map((section) => (
                        <div key={`install-section-${section}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                          <strong style={{ display: "block", marginBottom: "0.55rem", fontSize: "0.85rem", color: "var(--ink-3)" }}>{section}</strong>
                          <div style={{ display: "grid", gap: "0.6rem" }}>
                            {(catalogOnboarding.installSchema?.fields ?? [])
                              .filter((field) => field.section === section && field.key !== "name")
                              .map((field) => (
                                <label key={`install-field-${field.key}`} className="field" style={{ margin: 0 }}>
                                  <span>{field.label}{field.required ? " *" : ""}</span>
                                  {field.field_type === "boolean" ? (
                                    <input
                                      type="checkbox"
                                      checked={Boolean(catalogOnboarding.installFieldValues[field.key])}
                                      onChange={(e) => setCatalogOnboarding((current) => ({
                                        ...current,
                                        installFieldValues: { ...current.installFieldValues, [field.key]: e.target.checked },
                                      }))}
                                    />
                                  ) : field.field_type === "select" ? (
                                    <select
                                      value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                      onChange={(e) => setCatalogOnboarding((current) => ({
                                        ...current,
                                        installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                      }))}
                                    >
                                      <option value="">Select...</option>
                                      {field.options.map((option) => <option key={`${field.key}-${option}`} value={option}>{option}</option>)}
                                    </select>
                                  ) : field.field_type === "list" ? (
                                    <textarea
                                      className="input"
                                      style={{ minHeight: "72px", fontFamily: "var(--mono)", fontSize: "0.76rem" }}
                                      value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                      onChange={(e) => setCatalogOnboarding((current) => ({
                                        ...current,
                                        installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                      }))}
                                    />
                                  ) : (
                                    <input
                                      className="input"
                                      type={field.field_type === "number" ? "number" : "text"}
                                      value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                      onChange={(e) => setCatalogOnboarding((current) => ({
                                        ...current,
                                        installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                      }))}
                                    />
                                  )}
                                  {field.help_text && <small style={{ color: "var(--ink-4)" }}>{field.help_text}</small>}
                                </label>
                              ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="field">
                    <label>Continue into</label>
                    <select
                      value={catalogOnboarding.nextAction}
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, nextAction: e.target.value as "overview" | "config" | "deploy" }))}
                    >
                      <option value="deploy">Deployment control</option>
                      <option value="overview">Service overview</option>
                      {catalogOnboarding.card.configurable && <option value="config">Config manager</option>}
                    </select>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>
                    Recommended path: register the card, review dependency plan, then deploy through the Ansible-backed deployment control.
                  </div>
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Advanced contract overrides (JSON)</label>
                    <textarea
                      className="input"
                      style={{ minHeight: "96px", fontFamily: "var(--mono)", fontSize: "0.78rem" }}
                      value={catalogOnboarding.overridesText}
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, overridesText: e.target.value }))}
                      placeholder='{"ports":["8090:8080"],"config_files":["/path/to/config.yaml"]}'
                    />
                    <div style={{ marginTop: "0.35rem", color: "var(--ink-4)", fontSize: "0.78rem" }}>
                      Optional overrides are merged after the typed fields and reused by deployment/config workflows.
                    </div>
                  </div>
                </div>
              </div>

              {catalogOnboarding.registeredService && (
                <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                    <strong>Registration summary</strong>
                    <span className="pill pill-ok">service card registered</span>
                  </div>
                  <div style={{ marginTop: "0.35rem", color: "var(--ink-3)", fontSize: "0.85rem" }}>
                    {catalogOnboarding.registeredService.name} is now registered on{" "}
                    {nodes.find((node) => node.id === catalogOnboarding.nodeId)?.name ?? `node-${catalogOnboarding.nodeId}`}.
                  </div>
                  <div className="tags" style={{ marginTop: "0.45rem" }}>
                    <span>{catalogOnboarding.registeredService.service_key}</span>
                    <span>{catalogOnboarding.registeredService.kind}</span>
                    <span><code>{catalogOnboarding.registeredService.container_name}</code></span>
                    <span>{catalogOnboarding.card.dependencies.length} dependencies</span>
                  </div>
                  <div style={{ marginTop: "0.7rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.7rem" }}>
                    <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                      <small style={{ color: "var(--ink-4)" }}>Install review</small>
                      <div className="tags" style={{ marginTop: "0.35rem" }}>
                        <span>{catalogOnboarding.card.ports.length} published port(s)</span>
                        <span>{catalogOnboarding.card.volumes.length} volume mount(s)</span>
                        <span>{catalogOnboarding.card.config_files.length} config file(s)</span>
                        <span>{catalogOnboarding.card.log_paths.length} log path(s)</span>
                      </div>
                      {catalogOnboarding.card.command && (
                        <pre style={{ margin: "0.45rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.72rem" }}>
                          <code>{catalogOnboarding.card.command}</code>
                        </pre>
                      )}
                    </div>
                    <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                      <small style={{ color: "var(--ink-4)" }}>Recommended next move</small>
                      <div style={{ marginTop: "0.35rem", color: "var(--ink-3)", fontSize: "0.84rem" }}>
                        {catalogOnboarding.card.dependencies.length > 0
                          ? "Open deployment control to review dependency-first rollout and Ansible execution order."
                          : catalogOnboarding.card.configurable
                          ? "Open config manager to review defaults before the first deploy."
                          : "You can go straight to deployment control for the first rollout."}
                      </div>
                      {catalogOnboarding.card.health_command && (
                        <div style={{ marginTop: "0.45rem", color: "var(--ink-4)", fontSize: "0.78rem" }}>
                          Health check: <code>{catalogOnboarding.card.health_command}</code>
                        </div>
                      )}
                    </div>
                  </div>
                  <div style={{ marginTop: "0.7rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={async () => {
                        await loadServiceSummary(catalogOnboarding.registeredService!.id);
                        setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                        setNotice(`Reviewed ${catalogOnboarding.registeredService!.name} in service overview.`);
                      }}
                    >
                      Stay in overview
                    </button>
                    {catalogOnboarding.card.configurable && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={async () => {
                          await loadConfig(catalogOnboarding.registeredService!, configSource);
                          setActiveView("config");
                          setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                          setNotice(`Opened config manager for ${catalogOnboarding.registeredService!.name}.`);
                        }}
                      >
                        Open config
                      </button>
                    )}
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={async () => {
                        const service = catalogOnboarding.registeredService!;
                        setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                        await openDeploymentModal(service);
                      }}
                    >
                      Open deployment control
                    </button>
                  </div>
                </div>
              )}

              {catalogOnboarding.error && <p style={{ color: "var(--err)", fontSize: "0.82rem", margin: 0 }}>{catalogOnboarding.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={confirmCatalogOnboarding} disabled={catalogOnboarding.creating}>
                  {catalogOnboarding.creating ? "Saving..." : catalogOnboarding.mode === "edit" ? "Save configuration" : "Register Service Card"}
                </button>
              </div>
            </GlassCard>
          </div>
        )}

        {/* NODE PROVISIONING STEPPER DRAWER */}
        {stepperDrawerVisible && (
          <>
            <div className="drawer-backdrop" style={{ display: "block" }} onClick={() => setStepperDrawerVisible(false)}></div>
            <aside className="drawer" style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1.5rem", right: 0 }}>
              <div className="drawer-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2 style={{ fontSize: "1.5rem", fontFamily: "var(--display)" }}>Provision new node</h2>
                <button className="icon-btn" onClick={() => setStepperDrawerVisible(false)}><svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
              </div>

              <div className="stepper" style={{ display: "flex", gap: "0.25rem", margin: "1rem 0" }}>
                {[1, 2, 3, 4, 5, 6].map(num => (
                  <div key={num} className={`step ${stepperStep === num ? "active" : ""}`} style={{ flex: 1, height: "4px", background: stepperStep >= num ? "var(--navy)" : "var(--line)" }}></div>
                ))}
              </div>

              <div className="drawer-body" style={{ flex: 1, overflowY: "auto" }}>
                {stepperStep === 1 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 1: Cloud Provider</h3>
                    <div className="field">
                      <label>Node name</label>
                      <input type="text" className="input" placeholder="e.g. aws-node-mumbai" value={nodeEditor.draft.name} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} />
                    </div>
                    <div className="field">
                      <label>Cloud Provider</label>
                      <select value={nodePreset} onChange={(e) => applyNodePreset(e.target.value as any)}>
                        <option value="local-default">Local default (standalone)</option>
                        <option value="aws-general">Amazon Web Services (EC2)</option>
                        <option value="aws-gpu">AWS Accelerated GPU</option>
                      </select>
                    </div>
                  </div>
                )}

                {stepperStep === 2 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 2: Hardware Profile</h3>
                    <div className="field">
                      <label>vCPU Cores</label>
                      <input type="number" className="input" defaultValue={16} />
                    </div>
                    <div className="field">
                      <label>RAM (GB)</label>
                      <input type="number" className="input" defaultValue={128} />
                    </div>
                    <div className="field">
                      <label>Disk SSD Size (GB)</label>
                      <input type="number" className="input" defaultValue={500} />
                    </div>
                  </div>
                )}

                {stepperStep === 3 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 3: Configuration</h3>
                    <div className="field">
                      <label>SSH Host/IP</label>
                      <input type="text" className="input" value={nodeEditor.draft.host} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, host: e.target.value } }))} />
                    </div>
                    <div className="field">
                      <label>SSH Username</label>
                      <input type="text" className="input" value={nodeEditor.draft.ssh_user} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_user: e.target.value } }))} />
                    </div>
                    <div className="field">
                      <label>SSH Private Key Path</label>
                      <input type="text" className="input" placeholder="e.g. ~/.ssh/id_rsa" value={nodeEditor.draft.ssh_key_path} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_key_path: e.target.value } }))} />
                    </div>
                  </div>
                )}

                {stepperStep === 4 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 4: Network & Storage</h3>
                    <div className="field">
                      <label>Docker Network namespace</label>
                      <input type="text" className="input" value={nodeEditor.draft.docker_network} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, docker_network: e.target.value } }))} />
                    </div>
                    <div className="field">
                      <label>Volume Root Directory</label>
                      <input type="text" className="input" value={nodeEditor.draft.volume_root} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, volume_root: e.target.value } }))} />
                    </div>
                  </div>
                )}

                {stepperStep === 5 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 5: Firewall policies</h3>
                    <div className="field">
                      <label>Allowed ingress ports</label>
                      <input type="text" className="input" defaultValue="22, 80, 443, 8080" />
                    </div>
                  </div>
                )}

                {stepperStep === 6 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 6: Review &amp; Launch</h3>
                    <div style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "10px", fontSize: "0.85rem" }}>
                      <div><strong>Node name:</strong> {nodeEditor.draft.name || "N/A"}</div>
                      <div><strong>Host IP:</strong> {nodeEditor.draft.host}</div>
                      <div><strong>SSH User:</strong> {nodeEditor.draft.ssh_user}</div>
                      <div><strong>Volume Root:</strong> {nodeEditor.draft.volume_root}</div>
                      <div><strong>Docker Net:</strong> {nodeEditor.draft.docker_network}</div>
                    </div>
                  </div>
                )}

                {stepperStep === 7 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3>Step 7: Playbook Validation Console</h3>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                      <span className={`pill ${onboardingStatus === "success" ? "pill-ok" : onboardingStatus === "failed" ? "pill-error" : "pill-warn"}`}>
                        {onboardingStatus === "success" ? "Onboarding Successful" : onboardingStatus === "failed" ? "Onboarding Failed" : "Executing Ansible Playbook..."}
                      </span>
                      {onboardingStatus !== "success" && onboardingStatus !== "failed" && (
                        <div className="spinner-micro"></div>
                      )}
                    </div>
                    
                    <p style={{ fontSize: "0.85rem", color: "var(--ink-3)" }}>
                      Streaming Ansible orchestration logs below:
                    </p>

                    <pre style={{
                      margin: 0,
                      padding: "1rem",
                      borderRadius: "10px",
                      background: "#010307",
                      color: onboardingStatus === "failed" ? "var(--err)" : "#34d399",
                      overflowX: "auto",
                      fontSize: "0.75rem",
                      fontFamily: "var(--mono)",
                      border: onboardingStatus === "failed" ? "1px solid var(--err-bg)" : "1px solid var(--navy-500)",
                      boxShadow: "0 0 15px rgba(99, 102, 241, 0.15)",
                      whiteSpace: "pre-wrap",
                      textAlign: "left",
                      maxHeight: "300px",
                      overflowY: "auto"
                    }}>
                      <code>{onboardingOutput || onboardingError || "Initializing host connection via SSH..."}</code>
                    </pre>
                  </div>
                )}
              </div>

              <div className="drawer-foot" style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
                <button className="btn btn-secondary" disabled={stepperStep === 1 || stepperStep === 7} onClick={() => setStepperStep(prev => prev - 1)}>Back</button>
                {stepperStep < 6 ? (
                  <button className="btn btn-primary" onClick={() => setStepperStep(prev => prev + 1)}>Next</button>
                ) : stepperStep === 6 ? (
                  <button className="btn btn-primary" onClick={async () => {
                    const createdNode = await saveNodeEditor();
                    if (createdNode) {
                      setOnboardingStatus("running");
                      setOnboardingOutput("Initializing host connection via SSH...");
                      setOnboardingError("");
                      setStepperStep(7);
                      try {
                        const job = await api<{ id: number; status: string; output: string; error: string }>("/api/nodes/" + createdNode.id + "/validate", {
                          method: "POST",
                        });
                        setOnboardingJobId(job.id);
                        setOnboardingStatus(job.status);
                        setOnboardingOutput(job.output || "");
                        setOnboardingError(job.error || "");
                        pollOnboardingJob(createdNode.id, job.id);
                      } catch (err: any) {
                        setOnboardingStatus("failed");
                        setOnboardingError(err.message || "Failed to trigger node validation.");
                      }
                    }
                  }}>Launch Node</button>
                ) : (
                  <button className="btn btn-primary" onClick={() => {
                    setStepperDrawerVisible(false);
                    setStepperStep(1);
                  }}>Finish</button>
                )}
              </div>
            </aside>
          </>
        )}
      </>
    );
  }

  function renderModals() {
    return (
      <>
        {/* RENAME MODAL */}
        {renameModal.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "400px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3>Rename Snapshot</h3>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>Enter a unique snapshot name for this service card configuration.</p>
              <input
                className="input"
                value={renameModal.value}
                onChange={(e) => setRenameModal(prev => ({ ...prev, value: e.target.value }))}
                placeholder="Snapshot name"
              />
              {renameModal.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{renameModal.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setRenameModal({ visible: false, snapshotId: 0, value: "", error: "" })}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={renameSnapshot}>Save Name</button>
              </div>
            </GlassCard>
          </div>
        )}

        {/* CLUSTER EDITOR MODAL */}
        {clusterEditor.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "450px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3>{clusterEditor.mode === "create" ? "Add Cluster" : "Edit Cluster"}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div className="field">
                  <label>Cluster name</label>
                  <input className="input" value={clusterEditor.draft.name} onChange={(e) => setClusterEditor(prev => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} placeholder="e.g. prod-mumbai-1" />
                </div>
                <div className="field">
                  <label>Region</label>
                  <input className="input" value={clusterEditor.draft.region} onChange={(e) => setClusterEditor(prev => ({ ...prev, draft: { ...prev.draft, region: e.target.value } }))} placeholder="e.g. ap-south-1 (Mumbai)" />
                </div>
                <div className="field">
                  <label>Environment</label>
                  <select value={clusterEditor.draft.environment} onChange={(e) => setClusterEditor(prev => ({ ...prev, draft: { ...prev.draft, environment: e.target.value } }))}>
                    <option value="development">Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                  </select>
                </div>
              </div>
              {clusterEditor.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{clusterEditor.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setClusterEditor(prev => ({ ...prev, visible: false }))}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={saveClusterEditor}>Save Cluster</button>
              </div>
            </GlassCard>
          </div>
        )}

        {/* NODE EDITOR MODAL */}
        {nodeEditor.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "480px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3>{nodeEditor.mode === "create" ? "Add Node" : "Edit Node"}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "60vh", overflowY: "auto", paddingRight: "4px" }}>
                <div className="field">
                  <label>Node name</label>
                  <input className="input" value={nodeEditor.draft.name} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>SSH Host/IP</label>
                  <input className="input" value={nodeEditor.draft.host} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, host: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>SSH Username</label>
                  <input className="input" value={nodeEditor.draft.ssh_user} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_user: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>SSH Key Path</label>
                  <input className="input" value={nodeEditor.draft.ssh_key_path} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_key_path: e.target.value } }))} placeholder="e.g. ~/.ssh/id_rsa" />
                </div>
                <div className="field">
                  <label>Volume Root Directory</label>
                  <input className="input" value={nodeEditor.draft.volume_root} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, volume_root: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>Docker Network</label>
                  <input className="input" value={nodeEditor.draft.docker_network} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, docker_network: e.target.value } }))} />
                </div>
              </div>
              {nodeEditor.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{nodeEditor.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setNodeEditor(prev => ({ ...prev, visible: false }))}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={saveNodeEditor}>Save Node</button>
              </div>
            </GlassCard>
          </div>
        )}

        {deploymentModal.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "860px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "85vh", overflowY: "auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "flex-start" }}>
                <div>
                  <h3 style={{ marginBottom: "0.25rem" }}>Deployment Control</h3>
                  <p style={{ margin: 0, fontSize: "0.9rem" }}>
                    Review dependency order, Ansible execution steps, and deploy {deploymentModal.serviceName} on {deploymentModal.nodeName}.
                  </p>
                </div>
                <span className={`pill ${deploymentModal.preflight?.ok ? "pill-ok" : "pill-warn"}`}>
                  {deploymentModal.preflight?.ok ? "ready" : "needs dependencies"}
                </span>
              </div>

              {deploymentModal.loading ? (
                <p style={{ margin: 0, color: "var(--ink-4)" }}>Loading deployment plan and dependency state...</p>
              ) : (
                <>
                  {deploymentModal.preflight && (
                    <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: "0.85rem" }}>
                      <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.9rem", background: "rgba(255,255,255,0.03)" }}>
                        <strong>Dependency preflight</strong>
                        <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.35rem" }}>{deploymentModal.preflight.message}</div>
                        {deploymentModal.preflight.required.length > 0 && (
                          <div style={{ marginTop: "0.5rem" }}>
                            <small style={{ color: "var(--ink-4)" }}>Required cards</small>
                            <div className="tags" style={{ marginTop: "0.25rem" }}>
                              {deploymentModal.preflight.required.map((item) => <span key={`req-${item}`}>{item}</span>)}
                            </div>
                          </div>
                        )}
                        {deploymentModal.preflight.missing.length > 0 && (
                          <div style={{ marginTop: "0.5rem" }}>
                            <small style={{ color: "var(--ink-4)" }}>Missing</small>
                            <div className="tags" style={{ marginTop: "0.25rem" }}>
                              {deploymentModal.preflight.missing.map((item) => <span key={`miss-${item}`}>{item}</span>)}
                            </div>
                          </div>
                        )}
                        {deploymentModal.preflight.stopped.length > 0 && (
                          <div style={{ marginTop: "0.5rem" }}>
                            <small style={{ color: "var(--ink-4)" }}>Stopped</small>
                            <div className="tags" style={{ marginTop: "0.25rem" }}>
                              {deploymentModal.preflight.stopped.map((item) => <span key={`stop-${item}`}>{item}</span>)}
                            </div>
                          </div>
                        )}
                      </div>

                      <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.9rem", background: "rgba(255,255,255,0.03)" }}>
                        <strong>Execution policy</strong>
                        <label style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", marginTop: "0.6rem" }}>
                          <input
                            type="checkbox"
                            checked={deploymentModal.autoInstallDependencies}
                            onChange={(e) => setDeploymentModal((current) => ({ ...current, autoInstallDependencies: e.target.checked }))}
                          />
                          <span style={{ fontSize: "0.88rem", color: "var(--ink-3)" }}>
                            Auto-install or start missing infrastructure cards before deploying the main service.
                          </span>
                        </label>
                        <div style={{ marginTop: "0.75rem", fontSize: "0.82rem", color: "var(--ink-4)" }}>
                          This mirrors a dependency-first deployment flow while keeping the target deploy under Ansible control.
                        </div>
                      </div>
                    </div>
                  )}

                  {plan && deploymentModal.serviceId && selectedService?.id === deploymentModal.serviceId && (
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                        <strong>Ordered deployment plan</strong>
                        <span className={`pill ${plan.ok ? "pill-ok" : "pill-warn"}`}>{plan.ok ? "already healthy" : `${plan.blocked_by.length} action item(s)`}</span>
                      </div>
                      <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{plan.summary}</div>
                      <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.65rem" }}>
                        {plan.steps.map((step) => (
                          <div key={`deploy-step-${step.order}-${step.service_key}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.8rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                              <div style={{ display: "flex", gap: "0.55rem", alignItems: "center", flexWrap: "wrap" }}>
                                <span className="pill" style={{ fontSize: "0.72rem" }}>Step {step.order}</span>
                                <strong>{step.name}</strong>
                                <span className={`pill ${step.action === "skip" ? "pill-ok" : "pill-warn"}`}>{step.action}</span>
                              </div>
                              <small style={{ color: "var(--ink-4)" }}>{step.kind} · {step.subsystem}</small>
                            </div>
                            <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                              Status {step.status} · container <code>{step.container_name}</code>
                            </div>
                            {step.depends_on && step.depends_on.length > 0 && (
                              <div style={{ marginTop: "0.4rem" }}>
                                <small style={{ color: "var(--ink-4)" }}>Depends on</small>
                                <div className="tags" style={{ marginTop: "0.2rem" }}>
                                  {step.depends_on.map((item) => <span key={`${step.service_key}-dep-${item}`}>{item}</span>)}
                                </div>
                              </div>
                            )}
                            {step.ansible_command && (
                              <div style={{ marginTop: "0.45rem" }}>
                                <small style={{ color: "var(--ink-4)" }}>Ansible command preview</small>
                                <pre style={{ margin: "0.25rem 0 0", padding: "0.65rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.76rem" }}>
                                  <code>{step.ansible_command}</code>
                                </pre>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {deploymentModal.result && (
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                        <strong>Execution result</strong>
                        <span className={`pill ${deploymentModal.result.ok ? "pill-ok" : "pill-warn"}`}>{deploymentModal.result.ok ? "completed" : "attention needed"}</span>
                      </div>
                      <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{deploymentModal.result.summary}</div>
                      {deploymentModal.result.dependency_actions.length > 0 && (
                        <div style={{ marginTop: "0.65rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Dependency actions</small>
                          <div style={{ marginTop: "0.3rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                            {deploymentModal.result.dependency_actions.map((action) => (
                              <div key={`dep-action-${action.job_id}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.7rem" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                                  <strong>{action.service_key}</strong>
                                  <span className="pill">{action.job_status}</span>
                                </div>
                                <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>{action.message}</div>
                                <pre style={{ margin: "0.35rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.74rem" }}>
                                  <code>{action.command}</code>
                                </pre>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {deploymentModal.result.target_job && (
                        <div style={{ marginTop: "0.7rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Target deploy job</small>
                          <div style={{ marginTop: "0.3rem", border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                              <strong>{deploymentModal.serviceName}</strong>
                              <span className={`pill ${deploymentModal.result.target_job.status === "success" ? "pill-ok" : "pill-warn"}`}>{deploymentModal.result.target_job.status}</span>
                            </div>
                            <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                              Job #{deploymentModal.result.target_job.id} · {deploymentModal.result.target_job.action}
                            </div>
                            <pre style={{ margin: "0.35rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.74rem" }}>
                              <code>{deploymentModal.result.target_job.command}</code>
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}

              {deploymentModal.error && <p style={{ color: "var(--err)", fontSize: "0.82rem", margin: 0 }}>{deploymentModal.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setDeploymentModal((current) => ({ ...current, visible: false, error: "" }))}>Close</button>
                {deploymentModal.serviceId && (
                  <>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={async () => {
                        const service = services.find((item) => item.id === deploymentModal.serviceId);
                        if (service) {
                          await openDeploymentModal(service);
                        }
                      }}
                      disabled={deploymentModal.loading || deploymentModal.executing}
                    >
                      Refresh plan
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={async () => {
                        const service = services.find((item) => item.id === deploymentModal.serviceId);
                        if (service) {
                          await installMissingDependencies(service);
                        }
                      }}
                      disabled={deploymentModal.loading || deploymentModal.executing}
                    >
                      Deploy dependencies first
                    </button>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={executeDeploymentModal}
                      disabled={deploymentModal.loading || deploymentModal.executing}
                    >
                      {deploymentModal.executing ? "Executing..." : "Execute plan"}
                    </button>
                  </>
                )}
              </div>
            </GlassCard>
          </div>
        )}

        {releaseApprovalModal.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "560px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3>Release Safety Gate</h3>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>
                {releaseApprovalModal.serviceName} needs an explicit release approval before this change can be deployed.
              </p>
              {releaseApprovalModal.safety && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", background: "rgba(0,0,0,0.2)", padding: "0.85rem", borderRadius: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Severity</span>
                    <span className={`pill ${releaseApprovalModal.safety.severity === "high" ? "pill-error" : "pill-warn"}`}>
                      {releaseApprovalModal.safety.severity}
                    </span>
                  </div>
                  {releaseApprovalModal.safety.reasons.map((reason) => (
                    <small key={reason} style={{ color: "var(--warn)" }}>• {reason}</small>
                  ))}
                  <small style={{ color: "var(--ink-4)" }}>{releaseApprovalModal.safety.recommended_action}</small>
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div className="field">
                  <label>Target version</label>
                  <input className="input" value={releaseApprovalModal.version} readOnly />
                </div>
                <div className="field">
                  <label>Target image</label>
                  <input className="input" value={releaseApprovalModal.image} readOnly />
                </div>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>Approval reason</label>
                  <input
                    className="input"
                    value={releaseApprovalModal.reason}
                    placeholder="Explain the rollout window and risk mitigation"
                    onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, reason: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Requested by</label>
                  <input
                    className="input"
                    value={releaseApprovalModal.requestedBy}
                    onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, requestedBy: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Approval id</label>
                  <input
                    className="input"
                    value={releaseApprovalModal.approvalId}
                    placeholder="Populated after request"
                    onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, approvalId: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Approver</label>
                  <input
                    className="input"
                    value={releaseApprovalModal.approver}
                    onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, approver: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Decision note</label>
                  <input
                    className="input"
                    value={releaseApprovalModal.decisionNote}
                    onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, decisionNote: e.target.value }))}
                  />
                </div>
              </div>
              {releaseApprovalModal.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{releaseApprovalModal.error}</p>}
              <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>
                Recent approvals for this service: {releaseApprovals.filter((item) => item.service_id === releaseApprovalModal.serviceId).slice(0, 3).map((item) => `#${item.id} ${item.status}`).join(", ") || "none"}
              </div>
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setReleaseApprovalModal((current) => ({ ...current, visible: false, error: "" }))}>Cancel</button>
                <button className="btn btn-secondary btn-sm" onClick={createReleaseApprovalRequest}>Request Approval</button>
                <button className="btn btn-secondary btn-sm" onClick={approveReleaseApprovalRequest}>Approve</button>
                <button className="btn btn-secondary btn-sm" onClick={revokeReleaseApprovalRequest}>Revoke</button>
                <button className="btn btn-primary btn-sm" onClick={confirmApprovedRelease}>Deploy Approved Release</button>
              </div>
            </GlassCard>
          </div>
        )}

        {/* DELETE CONFIRMATION MODAL */}
        {deleteModal.visible && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "500px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3>Lifecycle Safety Review</h3>
              <p style={{ margin: 0 }}>You are deleting the following infrastructure resource:</p>
              <div style={{ background: "rgba(0,0,0,0.2)", padding: "0.75rem", borderRadius: "8px", fontSize: "0.9rem" }}>
                <strong>Type:</strong> {deleteModal.targetType.toUpperCase()}<br/>
                <strong>Name:</strong> {deleteModal.targetName}<br/>
                <strong>ID:</strong> {deleteModal.targetId}
              </div>

              {deleteModal.impact && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Severity:</span>
                    <span className={`pill ${deleteModal.impact.severity === "safe" ? "pill-ok" : "pill-error"}`}>{deleteModal.impact.severity}</span>
                  </div>
                  {deleteModal.impact.warnings.map((w, idx) => (
                    <small key={idx} style={{ color: "var(--warn)", display: "block" }}>⚠ {w}</small>
                  ))}
                  {deleteModal.impact.dependents.map((dep, idx) => (
                    <small key={idx} style={{ color: "var(--err)", display: "block" }}>❌ Dependents: {dep}</small>
                  ))}
                  <p style={{ fontStyle: "italic", fontSize: "0.85rem", margin: "4px 0" }}>{deleteModal.impact.recommended_action}</p>
                </div>
              )}

              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setDeleteModal(prev => ({ ...prev, visible: false }))}>Cancel</button>
                {deleteModal.impact?.can_delete_without_force ? (
                  <button className="btn btn-primary btn-sm btn-danger" onClick={confirmDelete}>Confirm Deletion</button>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", width: "100%", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input type="checkbox" checked={deleteModal.force} onChange={(e) => setDeleteModal(prev => ({ ...prev, force: e.target.checked }))} />
                      <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Override safety rules (Force Delete)</label>
                    </div>

                    {!deleteModal.forceApprovalId ? (
                      <>
                        <input 
                          className="input" 
                          placeholder="Enter audit reason (min 12 chars)" 
                          value={deleteModal.forceReason}
                          onChange={(e) => setDeleteModal(prev => ({ ...prev, forceReason: e.target.value }))}
                        />
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.25rem" }}>
                          <button 
                            className="btn btn-secondary btn-sm" 
                            disabled={deleteModal.forceReason.length < 12}
                            onClick={requestForceDeleteApproval}
                          >
                            Request Approval
                          </button>
                        </div>
                      </>
                    ) : (
                      <div style={{ background: "rgba(255,255,255,0.03)", padding: "1rem", borderRadius: "12px", border: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Approval Request #{deleteModal.forceApprovalId}</span>
                          <span className={`pill ${deleteModal.approvalStatus === "approved" ? "pill-ok" : deleteModal.approvalStatus === "rejected" ? "pill-error" : "pill-warn"}`}>
                            {deleteModal.approvalStatus}
                          </span>
                        </div>

                        <div className="field">
                          <label>Second-Person Approver</label>
                          <input 
                            className="input" 
                            placeholder="e.g. platform-admin" 
                            value={deleteModal.approver} 
                            onChange={(e) => setDeleteModal(prev => ({ ...prev, approver: e.target.value }))}
                          />
                        </div>

                        <div className="field">
                          <label>Decision Note</label>
                          <input 
                            className="input" 
                            placeholder="e.g. Approved for emergency cleanup" 
                            value={deleteModal.decisionNote} 
                            onChange={(e) => setDeleteModal(prev => ({ ...prev, decisionNote: e.target.value }))}
                          />
                        </div>

                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.25rem" }}>
                          <button className="btn btn-secondary btn-sm" onClick={rejectForceDeleteApproval}>Reject</button>
                          <button className="btn btn-primary btn-sm" onClick={approveForceDeleteApproval}>Approve</button>
                        </div>
                      </div>
                    )}

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem", borderTop: "1px solid var(--line-2)", paddingTop: "0.75rem" }}>
                      <button 
                        className="btn btn-primary btn-sm btn-danger" 
                        disabled={!deleteModal.force || deleteModal.forceReason.length < 12 || deleteModal.approvalStatus !== "approved"}
                        onClick={confirmDelete}
                      >
                        Force Uninstall
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </GlassCard>
          </div>
        )}

        {/* LOG ARCHIVE PREVIEW MODAL */}
        {selectedArchive && (
          <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "700px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>Log Archive Preview</h3>
                <button className="icon-btn" style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer" }} onClick={() => setSelectedArchive(null)}>
                  <svg className="ic" viewBox="0 0 24 24" style={{ width: "18px", height: "18px" }}><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </button>
              </div>

              <div style={{ background: "rgba(0,0,0,0.2)", padding: "0.75rem", borderRadius: "8px", fontSize: "0.85rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div><strong>Path:</strong> <code>{selectedArchive.path}</code></div>
                <div><strong>Discovered:</strong> {selectedArchive.discovered_at ? new Date(selectedArchive.discovered_at).toLocaleString() : "N/A"}</div>
                <div><strong>Size:</strong> {Math.round(selectedArchive.size_bytes / 1024)} KB</div>
                <div><strong>Lines:</strong> {selectedArchive.line_count}</div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <h4 style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)" }}>File Sample Data</h4>
                <div 
                  className="console"
                  style={{
                    height: "220px",
                    background: "#020408",
                    color: "#34d399",
                    fontFamily: "var(--mono)",
                    fontSize: "0.8rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "8px",
                    padding: "0.75rem",
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.25rem",
                    textAlign: "left"
                  }}
                >
                  {generateMockLogs(selectedArchive).map((line, index) => {
                    const timeStr = new Date(line.timestamp).toISOString().replace("T", " ").substring(0, 19);
                    const levelUpper = line.level.padEnd(5);
                    let levelColor = "#38bdf8";
                    if (levelUpper.includes("ERR")) levelColor = "#f87171";
                    else if (levelUpper.includes("WARN")) levelColor = "#fbbf24";
                    else if (levelUpper.includes("DEBUG")) levelColor = "#a78bfa";

                    return (
                      <div key={index} style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.01)", padding: "2px 0" }}>
                        <span style={{ color: "var(--ink-4)", flexShrink: 0 }}>{timeStr}</span>
                        <span style={{ color: levelColor, fontWeight: "bold", flexShrink: 0 }}>{levelUpper}</span>
                        <code style={{ color: "#e2e8f0", wordBreak: "break-all" }}>{line.message}</code>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedArchive(null)}>Close Preview</button>
                <button 
                  className="btn btn-primary btn-sm" 
                  disabled={!diagnostics?.readiness.backfill_requirements?.ready}
                  onClick={() => {
                    runLogBackfill();
                    setSelectedArchive(null);
                  }}
                >
                  Trigger Loki Backfill
                </button>
              </div>
            </GlassCard>
          </div>
        )}
      </>
    );
  }

  return (
    <Layout 
      activeView={activeView === "dashboard" ? "clusters" : activeView} 
      onViewChange={setActiveView}
      clusterContext={selectedCluster?.name}
      nodeContext={selectedNode?.name}
      serviceContext={selectedService?.name}
    >
      <main style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {notice && (
          <section className="notice" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>💡 {notice}</span>
            <button style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", fontSize: "0.75rem" }} onClick={() => setNotice("")}>Dismiss</button>
          </section>
        )}

        {(activeView === "dashboard" || activeView === "clusters") && renderClustersView()}
        {activeView === "config" && renderConfigManagerView()}
        {activeView === "diagnostics" && renderDiagnosticsView()}
        {activeView === "monitoring" && renderMonitoringView()}
      </main>

      {renderDrawers()}
      {renderModals()}
    </Layout>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <article>
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
