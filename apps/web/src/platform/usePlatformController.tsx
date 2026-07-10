import React, { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { GlassCard } from "../components/GlassCard";
import "../styles.css";


const API = import.meta.env.VITE_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:9002");
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

type Cluster = {
  id: number;
  name: string;
  region: string;
  environment: string;
  repo_type?: string;
  repo_url?: string;
  repo_branch?: string;
  repo_token?: string;
  registry_type?: string;
  registry_url?: string;
  registry_user?: string;
  registry_password?: string;
};
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
  repo_type: string;
  repo_url: string;
  repo_branch: string;
  repo_token: string;
  registry_type: string;
  registry_url: string;
  registry_user: string;
  registry_password: string;
};
type NodeDraft = {
  cluster_id: number;
  name: string;
  host: string;
  ssh_user: string;
  ssh_key_path: string;
  ssh_private_key: string;
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
type MetricWindow = "1h" | "6h" | "24h" | "7d" | "1M" | "3M" | "1m" | "3m";
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
  mounted_volumes?: Array<{ mount: string; fstype: string; used_gb: number; total_gb: number; usage_pct: number }>;
  prometheus_reachable?: boolean;
  error?: string | null;
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
  db_metrics?: Record<string, number | string> | null;
  broker_metrics?: Record<string, number | string> | null;
  custom_charts?: Array<{ title: string; unit?: string; series?: Array<{ name: string; points: MetricPoint[] }> }>;
  prometheus_reachable?: boolean;
  error?: string | null;
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

type PlatformUser = {
  user_id: string;
  user_name: string;
  user_email: string;
  user_role: string;
  user_number: string;
  status: string;
  login_count: number;
  last_login: string;
  last_login_ts: number | string;
  created_at: string;
  session_info: Record<string, any>;
  invite_token?: string;
  invite_link?: string;
};

type AnalyticsChatMessage = {
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  evidence?: Array<{ t?: string; lvl?: string; msg?: string }>;
  chart_data?: number[];
  suggestions?: string[];
  error?: string;
};


const AUTH_TOKEN_KEY = "platformops.auth.token.v1";

function getAuthToken(): string {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

function setAuthToken(token: string) {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
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


function renderSVGTimeSeriesChart(
  series: MetricPoint[],
  opts?: { color?: string; unit?: string; height?: number },
): React.ReactNode {
  const color = opts?.color || "#60a5fa";
  const height = opts?.height ?? 80;
  const width = 320;
  if (!series || series.length === 0) {
    return <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", padding: "0.5rem 0" }}>No series data</div>;
  }
  const values = series.map((p) => Number(p.value) || 0);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = Math.max(max - min, 1e-6);
  const coords = series.map((p, i) => {
    const x = (i / Math.max(series.length - 1, 1)) * (width - 8) + 4;
    const y = height - 8 - ((Number(p.value) - min) / span) * (height - 16);
    return { x, y, p };
  });
  const pts = coords.map((c) => `${c.x},${c.y}`);
  const area = `4,${height - 4} ${pts.join(" ")} ${width - 4},${height - 4}`;
  return (
    <SvgTimeSeriesChart
      series={series}
      coords={coords}
      pts={pts}
      area={area}
      color={color}
      height={height}
      width={width}
      unit={opts?.unit || ""}
    />
  );
}

function SvgTimeSeriesChart({
  series,
  coords,
  pts,
  area,
  color,
  height,
  width,
  unit,
}: {
  series: MetricPoint[];
  coords: Array<{ x: number; y: number; p: MetricPoint }>;
  pts: string[];
  area: string;
  color: string;
  height: number;
  width: number;
  unit: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const active = hover != null ? coords[hover] : null;
  return (
    <div style={{ position: "relative", width: "100%" }}>
      {active && (
        <div
          style={{
            position: "absolute",
            left: `calc(${(active.x / width) * 100}% - 40px)`,
            top: Math.max(0, active.y - 28),
            zIndex: 2,
            pointerEvents: "none",
            background: "rgba(2,4,8,0.92)",
            border: "1px solid var(--line-2)",
            borderRadius: 6,
            padding: "2px 6px",
            fontSize: "0.72rem",
            color: "var(--ink-1)",
            whiteSpace: "nowrap",
          }}
        >
          {active.p.label}: <strong>{active.p.value}{unit}</strong>
        </div>
      )}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        style={{ display: "block" }}
        onMouseLeave={() => setHover(null)}
      >
        <polygon points={area} fill={color} opacity={0.12} />
        <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2" />
        {active && (
          <>
            <line x1={active.x} y1={4} x2={active.x} y2={height - 4} stroke={color} strokeOpacity={0.35} strokeDasharray="3 3" />
            <circle cx={active.x} cy={active.y} r={4.5} fill={color} stroke="#020408" strokeWidth={1.5} />
          </>
        )}
        {coords.map((c, i) => (
          <circle
            key={`${c.p.label}-${i}`}
            cx={c.x}
            cy={c.y}
            r={hover === i ? 4 : 2.5}
            fill={color}
            style={{ cursor: "crosshair" }}
            onMouseEnter={() => setHover(i)}
          >
            <title>{`${c.p.label}: ${c.p.value}${unit}`}</title>
          </circle>
        ))}
        {/* hit targets for sparse series */}
        {coords.map((c, i) => (
          <rect
            key={`hit-${i}`}
            x={Math.max(0, c.x - (width / Math.max(series.length, 1)) / 2)}
            y={0}
            width={Math.max(8, width / Math.max(series.length, 1))}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>
    </div>
  );
}

function renderUptimeAvailabilityBlocks(checks: any[]): React.ReactNode {
  const blocks = (checks || []).slice(0, 48);
  if (blocks.length === 0) {
    return <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>No check history yet.</div>;
  }
  return (
    <div style={{ display: "flex", gap: 2, flexWrap: "wrap", marginTop: 8 }}>
      {blocks.map((c, i) => {
        const up = c.isUp === true || c.status === "ok" || c.status === "up" || String(c.statusCode || "").startsWith("2");
        return (
          <div
            key={i}
            title={`${up ? "UP" : "DOWN"} · ${c.startCheck || c.dateCreated || c.timestamp || ""}`}
            style={{
              width: 10,
              height: 22,
              borderRadius: 2,
              background: up ? "var(--ok)" : "var(--err)",
              opacity: 0.85,
            }}
          />
        );
      })}
    </div>
  );
}

function uptimeLatencySeries(checks: any[]): MetricPoint[] {
  return (checks || [])
    .map((c: any, i: number) => {
      const ms = Number(c.durationMs ?? c.duration ?? c.responseTime ?? c.latency_ms ?? NaN);
      if (!Number.isFinite(ms)) return null;
      const label = c.startCheck || c.dateCreated || `#${i + 1}`;
      return { label: String(label).slice(0, 19), value: ms } as MetricPoint;
    })
    .filter(Boolean) as MetricPoint[];
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
      {(["1h", "6h", "24h", "7d", "1M", "3M"] as MetricWindow[]).map((window) => (
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

function renderCircularGauge(value: number, target: number, label: string, color: string) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(value, 100) / 100) * circumference;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", flex: 1, minWidth: "120px" }}>
      <div style={{ position: "relative", width: "80px", height: "80px" }}>
        <svg style={{ transform: "rotate(-90deg)", width: "80px", height: "80px" }}>
          {/* Background Circle */}
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke="rgba(255, 255, 255, 0.05)"
            strokeWidth="6"
            fill="transparent"
          />
          {/* Foreground Circle */}
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke={color}
            strokeWidth="6"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.5s ease-in-out" }}
          />
        </svg>
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "80px",
          height: "80px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          lineHeight: 1
        }}>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>{value}%</span>
          <span style={{ fontSize: "0.6rem", color: "var(--ink-4)", marginTop: "3px" }}>target {target}%</span>
        </div>
      </div>
      <strong style={{ fontSize: "0.8rem", color: "var(--ink-2)", textAlign: "center" }}>{label}</strong>
    </div>
  );
}



function isSeedDemoName(name: string | null | undefined): boolean {
  const n = (name || "").toLowerCase();
  if (!n) return false;
  return (
    n.startsWith("e2e-") ||
    n.startsWith("verify-node-") ||
    n.startsWith("parity-cl-") ||
    n.includes("e2e-cluster") ||
    n.includes("e2e-node") ||
    n.includes("seed_demo") ||
    n.includes("seed-demo")
  );
}



import type { PlatformApi } from "./context";

export function usePlatformController() {
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
  const [realtimeNodeMetrics, setRealtimeNodeMetrics] = useState<{ cpu: number; memory: number; disk: number } | null>(null);
  const [processMetrics, setProcessMetrics] = useState<{ name: string; cpu: string; memory?: string }[]>([]);
  const [perfProcessSort, setPerfProcessSort] = useState<"cpu" | "memory">("cpu");
  const [diagFilePath, setDiagFilePath] = useState<string>("");

  const [loadingMetrics, setLoadingMetrics] = useState<boolean>(false);
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
  const [checkpointFilter, setCheckpointFilter] = useState<"all" | "active" | "renamed" | "backup">("all");
  const [checkpointSearch, setCheckpointSearch] = useState<string>("");
  const [selectedSnapshotPreview, setSelectedSnapshotPreview] = useState<ConfigSnapshotDetail | null>(null);
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
  const [obsStackBusy, setObsStackBusy] = useState<string>("");
  const [obsStackContainers, setObsStackContainers] = useState<any[]>([]);
  const [obsStackOutput, setObsStackOutput] = useState<string>("");
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

  // GlitchTip / Observability States
  const [monitoringSubTab, setMonitoringSubTab] = useState<string>("glitchtip");
  const [gtSelectedServiceId, setGtSelectedServiceId] = useState<number | null>(null);
  const [gtIssues, setGtIssues] = useState<any[]>([]);
  const [gtSelectedIssueId, setGtSelectedIssueId] = useState<string | null>(null);
  const [gtEventDetails, setGtEventDetails] = useState<any | null>(null);
  const [gtUptimeMonitors, setGtUptimeMonitors] = useState<any[]>([]);
  const [gtKeys, setGtKeys] = useState<any[]>([]);
  const [gtTransactions, setGtTransactions] = useState<any[]>([]);
  const [gtIntegrationStatus, setGtIntegrationStatus] = useState<any>(null);
  const [gtActiveMonitorTab, setGtActiveMonitorTab] = useState<string>("issues");
  const [gtWindow, setGtWindow] = useState<"24h" | "7d">("24h");
  const [gtAutoRefresh, setGtAutoRefresh] = useState<boolean>(false);
  const [gtSdkLang, setGtSdkLang] = useState<"python" | "javascript" | "go">("python");
  const [txSort, setTxSort] = useState<"latency" | "throughput" | "failure">("latency");
  const [ingestionStats, setIngestionStats] = useState<any>(null);
  const [archiveGzipOnly, setArchiveGzipOnly] = useState(false);
  const [archivePreviewLines, setArchivePreviewLines] = useState<Array<{ timestamp?: string; level?: string; message?: string }>>([]);
  const [archivePreviewLoading, setArchivePreviewLoading] = useState(false);
  const [diagLogSource, setDiagLogSource] = useState<"container_live" | "container_history" | "file_live" | "file_history">("container_live");
  const [logLevelFilters, setLogLevelFilters] = useState<Record<string, boolean>>({ INFO: true, WARN: true, ERROR: true, DEBUG: true });
  const [logSearchQuery, setLogSearchQuery] = useState("");
  const [logAutoScroll, setLogAutoScroll] = useState(true);
  const [selectedArchiveIds, setSelectedArchiveIds] = useState<number[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyCursor, setHistoryCursor] = useState("");
  const [historyTotalPages, setHistoryTotalPages] = useState(0);
  const [gtIssuesCursor, setGtIssuesCursor] = useState<string | null>(null);
  const [gtIssuesHasMore, setGtIssuesHasMore] = useState(false);

  const [perfAutoRefresh, setPerfAutoRefresh] = useState(false);
  const [configEditMode, setConfigEditMode] = useState(false);
  const [configApplyMode, setConfigApplyMode] = useState<"reload" | "restart">("reload");
  const [liveStatusTick, setLiveStatusTick] = useState(0);

  const [uptimeFormVisible, setUptimeFormVisible] = useState<boolean>(false);
  const [uptimeForm, setUptimeForm] = useState<any>({ name: "", monitor_type: "Ping", url: "", interval: 60, expected_status: 200 });
  const [notice, setNotice] = useState<string>("");

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
    draft: {
      name: "",
      region: "local",
      environment: "development",
      repo_type: "github",
      repo_url: "",
      repo_branch: "main",
      repo_token: "",
      registry_type: "dockerhub",
      registry_url: "",
      registry_user: "",
      registry_password: "",
    },
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
      ssh_private_key: "",
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

  // cPlatform Layout Sub-Tab states (advanced topology/policy/audit live under Advanced nav, not cluster tabs)
  const [configTab, setConfigTab] = useState<"current" | "timeline" | "compare" | "migration">("current");
  const [diagTab, setDiagTab] = useState<"summary" | "tail" | "files" | "analytics">("summary");

  // SRE Incident Analytics Chat state (cPlatform Log Analyst)
  const [analyticsMessages, setAnalyticsMessages] = useState<AnalyticsChatMessage[]>([
    {
      sender: "assistant",
      text: "Hello! I am Iktara Log Analyst. Select a service, then ask about log anomalies, restarts, dependency failures, or deployment errors. Answers come from live logs + LLM (Groq/Mistral) — never synthetic metrics.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [analyticsInput, setAnalyticsInput] = useState<string>("");
  const [analyticsBusy, setAnalyticsBusy] = useState(false);
  const [llmStatus, setLlmStatus] = useState<{ configured?: boolean; provider?: string; model?: string; has_api_key?: boolean } | null>(null);
  const [authUser, setAuthUser] = useState<PlatformUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: "admin", password: "admin" });
  const [loginError, setLoginError] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [platformUsers, setPlatformUsers] = useState<PlatformUser[]>([]);
  const [usersTab, setUsersTab] = useState<"active" | "pending">("active");
  const [inviteForm, setInviteForm] = useState({ user_name: "", user_email: "", user_role: "Operational", user_number: "" });
  const [userForm, setUserForm] = useState({ user_name: "", user_email: "", user_role: "Operational", user_number: "", password: "" });
  const [inviteAccept, setInviteAccept] = useState<{ token: string; password: string; preview: any } | null>(null);

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

  async function refreshObservabilityStackStatus() {
    setObsStackBusy("status");
    try {
      const res = await fetch("/api/observability/status");
      const data = await res.json();
      const containers = Array.isArray(data?.containers) ? data.containers : Array.isArray(data) ? data : [];
      setObsStackContainers(containers);
      setObsStackOutput("");
    } catch (e: any) {
      setObsStackOutput(e?.message || "Failed to load observability status");
    } finally {
      setObsStackBusy("");
    }
  }

  async function runObservabilityStackAction(action: "deploy" | "teardown") {
    if (action === "teardown" && !window.confirm("Teardown the observability stack? This stops managed stack containers.")) return;
    setObsStackBusy(action);
    setObsStackOutput("");
    try {
      const res = await fetch(`/api/observability/${action}`, { method: "POST" });
      const data = await res.json();
      const out = typeof data.output === "string" ? data.output : JSON.stringify(data, null, 2);
      setObsStackOutput(out || (data.success ? `${action} completed` : `${action} failed`));
      if (!data.success) setNotice(`Observability ${action} failed — see output`);
      else setNotice(`Observability ${action} finished`);
      await refreshObservabilityStackStatus();
      try {
        const pipe = await api<ObservabilityPipeline>("/api/observability/pipeline");
        setObservabilityPipeline(pipe);
      } catch { /* ignore */ }
    } catch (e: any) {
      setObsStackOutput(e?.message || `${action} failed`);
    } finally {
      setObsStackBusy("");
    }
  }

  async function discoverNodeInfra(nodeId: number) {
    try {
      setNotice(`Discovering infrastructure on node ${nodeId}…`);
      const result = await api<any>(`/api/nodes/${nodeId}/discover`, { method: "POST" });
      setNotice(result?.summary || result?.message || `Discover finished for node ${nodeId}`);
      await refresh();
      await loadNodeJobHistory(nodeId);
    } catch (e: any) {
      setNotice(e?.message || "Discover failed");
    }
  }

  async function launchNodeVm(nodeId: number) {
    try {
      setNotice(`Launching VM for node ${nodeId}…`);
      const job = await api<Job>(`/api/nodes/${nodeId}/launch-vm`, { method: "POST" });
      setJob(job);
      setNotice(`Launch VM job #${job.id}: ${job.status}${job.error ? ` — ${job.error}` : ""}`);
      await refresh();
      await loadNodeJobHistory(nodeId);
    } catch (e: any) {
      setNotice(e?.message || "Launch VM failed");
    }
  }

  async function teardownNodeVm(nodeId: number) {
    if (!window.confirm("Teardown cloud VM for this node via Terraform?")) return;
    try {
      const job = await api<Job>(`/api/nodes/${nodeId}/teardown-vm`, { method: "POST" });
      setJob(job);
      setNotice(`Teardown VM job #${job.id}: ${job.status}${job.error ? ` — ${job.error}` : ""}`);
      await refresh();
      await loadNodeJobHistory(nodeId);
    } catch (e: any) {
      setNotice(e?.message || "Teardown failed");
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
    if (!selectedNode || !nodeJobHistory) return;
    const hasActiveJobs = nodeJobHistory.items.some(
      (job) => job.status === "queued" || job.status === "running"
    );
    if (!hasActiveJobs) return;

    const interval = window.setInterval(() => {
      loadNodeJobHistory(selectedNode.id).catch(console.error);
      refresh().catch(console.error);
    }, 2000);

    return () => window.clearInterval(interval);
  }, [selectedNode, nodeJobHistory, refresh, loadNodeJobHistory]);

  useEffect(() => {
    if (!job || (job.status !== "running" && job.status !== "queued")) return;
    const interval = window.setInterval(async () => {
      try {
        const refreshedJob = await api<Job>(`/api/jobs/${job.id}`);
        setJob(refreshedJob);
      } catch (err) {
        // ignore polling errors
      }
    }, 1500);
    return () => window.clearInterval(interval);
  }, [job]);

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

  async function loadNodeMetricsData(nodeId?: number) {
    setLoadingMetrics(true);
    try {
      if (nodeId) {
        const resNode = await fetch(`/api/nodes/${nodeId}/metrics`);
        const dataNode = await resNode.json();
        if (dataNode && !dataNode.error) {
          setRealtimeNodeMetrics({
            cpu: parseFloat(dataNode.cpu_percent || 0),
            memory: parseFloat(dataNode.memory_percent || 0),
            disk: parseFloat(dataNode.disk_percent || 0)
          });
        }
        const resProc = await fetch("/api/metrics/processes");
        const dataProc = await resProc.json();
        if (dataProc && dataProc.processes) {
          setProcessMetrics((dataProc.processes || []).map((p: any) => ({
            name: p.name || p.group || "proc",
            cpu: String(p.cpu ?? p.cpu_seconds ?? 0),
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : undefined,
          })));
        }
      } else {
        const [resNode, resProc] = await Promise.all([
          fetch("/api/metrics/node"),
          fetch("/api/metrics/processes")
        ]);
        const dataNode = await resNode.json();
        const dataProc = await resProc.json();
        
        if (dataNode && !dataNode.error) {
          setRealtimeNodeMetrics({
            cpu: parseFloat(dataNode.cpu || 0),
            memory: parseFloat(dataNode.memory || 0),
            disk: parseFloat(dataNode.disk || 0)
          });
        }
        if (dataProc && dataProc.processes) {
          setProcessMetrics((dataProc.processes || []).map((p: any) => ({
            name: p.name || p.group || "proc",
            cpu: String(p.cpu ?? p.cpu_seconds ?? 0),
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : undefined,
          })));
        }
      }
    } catch (e) {
      console.error("Failed to fetch node metrics:", e);
    } finally {
      setLoadingMetrics(false);
    }
  }

  async function loadGlitchTipIntegrationStatus() {
    try {
      const res = await fetch("/PlatformIO/Monitoring/IntegrationStatus/");
      const data = await res.json();
      setGtIntegrationStatus(data);
    } catch (e) {
      console.error("Failed to fetch GlitchTip status:", e);
    }
  }

  async function loadGlitchTipDataForService(serviceName: string, window: string = gtWindow) {
    if (!serviceName) return;
    try {
      const resIssues = await fetch("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName, window: "24h" })
      });
      const dataIssues = await resIssues.json();
      if (dataIssues.success) {
        setGtIssues(dataIssues.issues || []);
        setGtIssuesCursor(dataIssues.cursor || dataIssues.next_cursor || null);
        setGtIssuesHasMore(Boolean(dataIssues.has_more || dataIssues.cursor || dataIssues.next_cursor || (dataIssues.issues || []).length >= 25));
      }

      const resUptime = await fetch("/PlatformIO/Monitoring/Uptime/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataUptime = await resUptime.json();
      if (dataUptime.success) setGtUptimeMonitors(dataUptime.monitors || []);

      const resKeys = await fetch("/PlatformIO/Monitoring/Keys/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataKeys = await resKeys.json();
      if (dataKeys.success) setGtKeys(dataKeys.keys || []);

      const resPerf = await fetch("/PlatformIO/Monitoring/Performance/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataPerf = await resPerf.json();
      if (dataPerf.success) setGtTransactions(dataPerf.transactions || []);
    } catch (e) {
      console.error("Failed to load GlitchTip data for service:", e);
    }
  }


  async function loadMoreGtIssues() {
    const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
    if (!svc) return;
    try {
      const res = await fetch("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: svc.name, window: gtWindow, cursor: gtIssuesCursor }),
      });
      const data = await res.json();
      if (data.success) {
        const more = data.issues || [];
        setGtIssues((prev) => [...prev, ...more]);
        setGtIssuesCursor(data.cursor || data.next_cursor || null);
        setGtIssuesHasMore(Boolean(data.has_more || data.cursor || data.next_cursor));
      }
    } catch (e: any) {
      setNotice(e?.message || "Failed to load more issues");
    }
  }

  async function loadEventDetails(issueId: string) {
    setGtSelectedIssueId(issueId);
    setGtEventDetails(null);
    try {
      const res = await fetch("/PlatformIO/Monitoring/Issues/EventDetails/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue_id: issueId })
      });
      const data = await res.json();
      if (data.success) {
        setGtEventDetails(data.event);
      } else {
        setNotice(`Failed to load event details: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to load event details:", e);
    }
  }

  async function runIssueAction(issueId: string, action: string, serviceName: string) {
    try {
      const res = await fetch("/PlatformIO/Monitoring/IssueAction/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue_id: issueId, action })
      });
      const data = await res.json();
      if (data.success) {
        setNotice(`Issue status updated to ${action}`);
        await loadGlitchTipDataForService(serviceName);
        if (gtSelectedIssueId === issueId) {
          setGtSelectedIssueId(null);
          setGtEventDetails(null);
        }
      } else {
        setNotice(`Action failed: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to update issue action:", e);
    }
  }

  async function runAddMonitor(serviceName: string) {
    if (!uptimeForm.name || !uptimeForm.url) {
      setNotice("Name and URL are required to add monitor");
      return;
    }
    try {
      const res = await fetch("/PlatformIO/Monitoring/Uptime/Add/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: serviceName,
          name: uptimeForm.name,
          monitor_type: uptimeForm.monitor_type,
          url: uptimeForm.url,
          interval: parseInt(uptimeForm.interval || 60),
          expected_status: parseInt(uptimeForm.expected_status || 200)
        })
      });
      const data = await res.json();
      if (data.success) {
        setNotice("Uptime monitor added successfully");
        setUptimeFormVisible(false);
        setUptimeForm({ name: "", monitor_type: "Ping", url: "", interval: 60, expected_status: 200 });
        await loadGlitchTipDataForService(serviceName);
      } else {
        setNotice(`Failed to add monitor: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to add monitor:", e);
    }
  }

  async function runDeleteMonitor(monitorId: string, serviceName: string) {
    if (!window.confirm("Are you sure you want to delete this uptime monitor?")) return;
    try {
      const res = await fetch("/PlatformIO/Monitoring/Uptime/Delete/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monitor_id: monitorId })
      });
      const data = await res.json();
      if (data.success) {
        setNotice("Uptime monitor deleted successfully");
        await loadGlitchTipDataForService(serviceName);
      } else {
        setNotice(`Failed to delete monitor: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to delete monitor:", e);
    }
  }

  async function runPatchObservability(serviceId: number, serviceName: string) {
    setNotice("Running Sentry Observability Injection Patch...");
    try {
      const res = await fetch("/PlatformIO/Monitoring/PatchObservability/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_id: serviceId })
      });
      const data = await res.json();
      if (data.success) {
        setNotice("Sentry SDK injected and container restarted successfully.");
        await loadGlitchTipDataForService(serviceName);
      } else {
        setNotice(`Observability patch failed: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to run observability patch:", e);
    }
  }

  async function selectCluster(cluster: Cluster) {
    setSelectedCluster(cluster);
    setSelectedService(null);
    setServiceSummary(null);
    setServiceMetrics(null);
    setServiceReleaseTimeline(null);
    try {
      const summary = await api<ClusterSummary>(`/api/clusters/${cluster.id}/summary`);
      setClusterSummary(summary);
      const clusterNodes = nodes.filter((n) => n.cluster_id === cluster.id);
      if (clusterNodes.length > 0) {
        const keep = selectedNode && clusterNodes.some((n) => n.id === selectedNode.id) ? selectedNode : clusterNodes[0];
        await selectNode(keep);
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
      draft: {
      name: "",
      region: "local",
      environment: "development",
      repo_type: "github",
      repo_url: "",
      repo_branch: "main",
      repo_token: "",
      registry_type: "dockerhub",
      registry_url: "",
      registry_user: "",
      registry_password: "",
    },
      error: "",
    });
  }

  function openClusterEdit(cluster: Cluster) {
    setClusterEditor({
      visible: true,
      mode: "edit",
      clusterId: cluster.id,
      draft: {
        name: cluster.name,
        region: cluster.region,
        environment: cluster.environment,
        repo_type: cluster.repo_type || "github",
        repo_url: cluster.repo_url || "",
        repo_branch: cluster.repo_branch || "main",
        repo_token: "",
        registry_type: cluster.registry_type || "dockerhub",
        registry_url: cluster.registry_url || "",
        registry_user: cluster.registry_user || "",
        registry_password: "",
      },
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
          body: JSON.stringify({
            name,
            region: draft.region.trim() || "local",
            environment: draft.environment.trim() || "development",
            repo_type: draft.repo_type,
            repo_url: draft.repo_url,
            repo_branch: draft.repo_branch || "main",
            repo_token: draft.repo_token,
            registry_type: draft.registry_type,
            registry_url: draft.registry_url,
            registry_user: draft.registry_user,
            registry_password: draft.registry_password,
          }),
        });
        setClusterEditor((current) => ({ ...current, visible: false, error: "" }));
        setNotice(`Created cluster ${created.name}`);
        setSelectedCluster(created);
        await refresh();
        return;
      }
      if (!clusterEditor.clusterId) return;
      const payload: any = {
        name,
        region: draft.region.trim() || "local",
        environment: draft.environment.trim() || "development",
        repo_type: draft.repo_type,
        repo_url: draft.repo_url,
        repo_branch: draft.repo_branch || "main",
        registry_type: draft.registry_type,
        registry_url: draft.registry_url,
        registry_user: draft.registry_user,
      };
      if (draft.repo_token) payload.repo_token = draft.repo_token;
      if (draft.registry_password) payload.registry_password = draft.registry_password;
      const updated = await api<Cluster>(`/api/clusters/${clusterEditor.clusterId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setClusterEditor((current) => ({ ...current, visible: false, error: "" }));
      setSelectedCluster(updated);
      setNotice(`Updated cluster ${updated.name}`);
      await refresh();
    } catch (error: any) {
      setClusterEditor((current) => ({ ...current, error: error.message || "Failed to save cluster." }));
    }
  }


  async function testClusterRepoConnection() {
    const d = clusterEditor.draft;
    try {
      const res = await api<{ connected?: boolean; message?: string }>("/api/clusters/test-repo", {
        method: "POST",
        body: JSON.stringify({
          repo_type: d.repo_type,
          repo_url: d.repo_url,
          repo_branch: d.repo_branch || "main",
          repo_token: d.repo_token || null,
        }),
      });
      setNotice(res.message || (res.connected ? "Repository connection OK" : "Repository check finished"));
    } catch (e: any) {
      setNotice(e?.message || "Repository connection failed");
    }
  }

  async function testClusterRegistryConnection() {
    const d = clusterEditor.draft;
    try {
      const res = await api<{ connected?: boolean; message?: string }>("/api/clusters/test-registry", {
        method: "POST",
        body: JSON.stringify({
          registry_type: d.registry_type,
          registry_url: d.registry_url,
          registry_user: d.registry_user || null,
          registry_password: d.registry_password || null,
        }),
      });
      setNotice(res.message || (res.connected ? "Registry connection OK" : "Registry check finished"));
    } catch (e: any) {
      setNotice(e?.message || "Registry connection failed");
    }
  }

  async function checkPortAndNameAvailability(nodeId: number, containerName: string, port?: number | null) {
    const params = new URLSearchParams();
    if (containerName) params.set("name", containerName);
    if (port != null && !Number.isNaN(Number(port))) params.set("port", String(port));
    return api<{ available?: boolean; ok?: boolean; conflicts?: string[]; message?: string; detail?: string }>(
      `/api/nodes/${nodeId}/check-port-and-name?${params.toString()}`,
    );
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
        ssh_private_key: "",
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
        ssh_private_key: "",
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
            ssh_private_key: draft.ssh_private_key.trim() || undefined,
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
          ssh_private_key: draft.ssh_private_key.trim() || undefined,
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
      setNotice("Register a node on a cluster before continuing.");
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
      // Port / name collision check (cPlatform catalog safeguard)
      try {
        const desiredName = (catalogOnboarding.customName.trim() || card.name || card.service_key).toLowerCase().replace(/\s+/g, "-");
        const portRaw = (contractOverrides as any).port ?? (contractOverrides as any).host_port ?? (contractOverrides as any).published_port;
        const portNum = portRaw != null ? Number(portRaw) : null;
        const avail = await checkPortAndNameAvailability(node.id, desiredName, portNum);
        const blocked = avail.available === false || avail.ok === false;
        if (blocked) {
          setCatalogOnboarding((current) => ({
            ...current,
            creating: false,
            error: avail.message || avail.detail || "Port or container name conflicts with an existing service on this node.",
          }));
          return;
        }
      } catch {
        // Non-fatal if checker unavailable — continue onboarding
      }
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
        impact: "Scheduled maintenance window",
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
    options?: { cursor?: number; append?: boolean; silent?: boolean; targetServiceKey?: string; source?: typeof diagLogSource; page?: number },
  ) {
    const source = options?.source ?? diagLogSource;
    const targetServiceKey = options?.targetServiceKey ?? diagnosticsTargetKey;
    const targetId = (() => {
      if (!targetServiceKey || targetServiceKey === service.service_key) return service.id;
      const t = services.find((s) => s.node_id === service.node_id && s.service_key === targetServiceKey);
      return t?.id ?? service.id;
    })();

    if (source === "container_history" || source === "file_history") {
      const page = options?.page ?? historyPage;
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(historyPageSize || 100),
      });
      if (historyCursor) params.set("cursor", historyCursor);
      const filePath = diagFilePath || diagnostics?.readiness?.paths_checked?.[0]?.path || "";
      const path = source === "container_history"
        ? `/api/services/${targetId}/diagnostics/container-history?${params}`
        : `/api/services/${targetId}/diagnostics/file-history?${params}${filePath ? `&log_path=${encodeURIComponent(filePath)}` : ""}`;
      try {
        const hist = await api<any>(path);
        const lines = (hist.lines || hist.entries || []).map((l: any) =>
          typeof l === "string" ? { message: l, level: "INFO", timestamp: new Date().toISOString() } : l
        );
        setDiagnosticsLive({
          lines,
          source_state: source,
          next_cursor: hist.next_cursor ?? 0,
          total_available: hist.total ?? lines.length,
          poll_interval_ms: logsPollMs,
        } as any);
        setHistoryTotalPages(hist.total_pages || hist.history_total_pages || 0);
        if (hist.next_cursor) setHistoryCursor(String(hist.next_cursor));
        if (!options?.silent) setNotice(`Loaded ${lines.length} history lines (${source})`);
      } catch (e: any) {
        if (!options?.silent) setNotice(e?.message || "History query failed");
        setDiagnosticsLive({ lines: [], source_state: source, next_cursor: 0, total_available: 0, poll_interval_ms: logsPollMs } as any);
      }
      return;
    }

    if (source === "file_live") {
      const logPath = diagFilePath
        || diagnostics?.readiness?.paths_checked?.find((p: any) => p.readable)?.path
        || diagnostics?.readiness?.paths_checked?.[0]?.path
        || "";
      if (!logPath) {
        setDiagnosticsLive({ lines: [], source_state: "file_live", next_cursor: 0, total_available: 0, poll_interval_ms: logsPollMs } as any);
        if (!options?.silent) setNotice("No file log paths configured for this service");
        return;
      }
      try {
        const data = await api<any>(`/api/services/${targetId}/diagnostics/file-tail?log_path=${encodeURIComponent(logPath)}&tail_lines=${tailLines}`);
        const lines = (data.lines || data.entries || []).map((l: any) =>
          typeof l === "string" ? { message: l, level: "INFO", timestamp: new Date().toISOString() } : l
        );
        setDiagnosticsLive({ lines, source_state: "file_live", next_cursor: lines.length, total_available: lines.length, poll_interval_ms: logsPollMs } as any);
        if (!options?.silent) setNotice(`File live: ${lines.length} lines from ${logPath}`);
      } catch (e: any) {
        if (!options?.silent) setNotice(e?.message || "File tail failed");
      }
      return;
    }

    const cursor = options?.cursor ?? 0;
    const params = new URLSearchParams({
      tail_lines: String(tailLines),
      page_size: String(historyPageSize),
      cursor: String(cursor),
    });
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

  async function bulkDownloadArchives() {
    if (!selectedService || selectedArchiveIds.length === 0) {
      setNotice("Select one or more archives to download");
      return;
    }
    const sourceService = services.find((s) => s.id === diagnosticsSourceServiceId) ?? selectedService;
    const targetKey = diagnostics?.target_service_key ?? diagnosticsTargetKey;
    const target = targetKey
      ? services.find((s) => s.node_id === sourceService.node_id && s.service_key === targetKey)
      : sourceService;
    const sid = target?.id ?? sourceService.id;
    try {
      const res = await fetch(`/api/services/${sid}/diagnostics/archives/bulk-download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ archive_ids: selectedArchiveIds }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Bulk download failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `archives-${sid}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded ${selectedArchiveIds.length} archives`);
    } catch (e: any) {
      setNotice(e?.message || "Bulk download failed");
    }
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

  async function viewSnapshot(snapshotId: number) {
    try {
      const snapDetail = await api<ConfigSnapshotDetail>(`/api/services/${selectedService!.id}/config/snapshots/${snapshotId}`);
      setSelectedSnapshotPreview(snapDetail);
      setNotice(`Loaded snapshot v${snapDetail.version}`);
    } catch (err) {
      console.error(err);
      setNotice("Failed to load snapshot preview");
    }
  }

  async function syncPeerConfig(peerServiceId: number, peerName: string) {
    if (!config) return;
    const rolloutYaml = (migrationArtifactId && migrationContent) ? migrationContent : config.content;
    try {
      setNotice(`Syncing validated config to peer ${peerName}...`);
      const result = await api<{ job: Job; before_snapshot: ConfigSnapshotItem; after_snapshot: ConfigSnapshotItem }>(`/api/services/${peerServiceId}/config/direct-apply`, {
        method: "POST",
        body: JSON.stringify({ content: rolloutYaml, apply_mode: "reload" }),
      });
      setJob(result.job);
      setNotice(`Rollout sync to peer ${peerName} complete! Checkpoint v${result.before_snapshot.version} -> v${result.after_snapshot.version}`);
      await refresh();
    } catch (err) {
      console.error(err);
      setNotice(`Peer sync failed: ${err instanceof Error ? err.message : String(err)}`);
    }
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
      body: JSON.stringify({ content: config.content, apply_mode: configApplyMode }),
    });
    setJob(result.job);
    setNotice(`Config apply (${configApplyMode}) ${result.job.status}: checkpoint v${result.before_snapshot.version} -> v${result.after_snapshot.version}`);
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

  useEffect(() => {
    if (activeView === "node-metrics" || activeView === "performance") {
      loadNodeMetricsData();
    } else if (activeView === "monitoring") {
      loadGlitchTipIntegrationStatus();
      setMonitoringSubTab("glitchtip");
    } else if (activeView === "diagnostics") {
      api<any>("/api/diagnostics/ingestion-stats").then(setIngestionStats).catch(() => setIngestionStats(null));
    } else if (activeView === "observability") {
      refreshObservabilityStackStatus();
    }
  }, [activeView]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await api<any>("/api/llm/status");
        if (!cancelled) setLlmStatus(status);
      } catch {
        if (!cancelled) setLlmStatus({ configured: false });
      }
      const token = getAuthToken();
      if (!token) {
        if (!cancelled) {
          setAuthUser(null);
          setAuthReady(true);
        }
        return;
      }
      try {
        const me = await api<PlatformUser>("/api/auth/me");
        if (!cancelled) {
          setAuthUser(me);
          setAuthReady(true);
        }
      } catch {
        setAuthToken("");
        if (!cancelled) {
          setAuthUser(null);
          setAuthReady(true);
        }
      }
      // invite deep link: #/invite/<token>
      try {
        const hash = window.location.hash || "";
        const m = hash.match(/#\/invite\/([^/?#]+)/);
        if (m) {
          const tokenInv = m[1];
          const preview = await api<any>(`/api/auth/invite/${tokenInv}`);
          if (!cancelled) setInviteAccept({ token: tokenInv, password: "", preview });
        }
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!authUser) return;
    if (activeView === "users") {
      void loadPlatformUsers();
    }
    // persist last visited (best-effort)
    api("/api/auth/last-visited", {
      method: "POST",
      body: JSON.stringify({
        view: activeView,
        cluster_name: selectedCluster?.name || null,
        node_name: selectedNode?.name || null,
        service_name: selectedService?.name || null,
      }),
    }).catch(() => undefined);
  }, [activeView, authUser, selectedCluster?.id, selectedNode?.id, selectedService?.id]);

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

  async function runLogAnalystChat(question: string) {
    const q = (question || "").trim();
    if (!q) return;
    if (!selectedService) {
      setAnalyticsMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "Select a service from the diagnostics tree first. Log Analyst needs a real service context.",
          timestamp: new Date().toLocaleTimeString(),
          error: "no service selected",
        },
      ]);
      return;
    }
    const timestamp = new Date().toLocaleTimeString();
    setAnalyticsMessages((prev) => [...prev, { sender: "user", text: q, timestamp }]);
    setAnalyticsBusy(true);
    try {
      // Build multi-turn history from prior turns (exclude the message we just appended)
      const prior = analyticsMessages.slice(-12).map((m) => ({
        role: m.sender === "user" ? "user" : "assistant",
        content: m.text,
      }));
      const result = await api<{
        success: boolean;
        answer: string;
        evidence: Array<{ t?: string; lvl?: string; msg?: string }>;
        chart_data: number[];
        suggestions: string[];
        error?: string | null;
        provider?: string;
      }>(`/api/services/${selectedService.id}/diagnostics/chat`, {
        method: "POST",
        body: JSON.stringify({
          question: q,
          window: "current",
          history: prior,
        }),
      });
      if (!result.success) {
        setAnalyticsMessages((prev) => [
          ...prev,
          {
            sender: "assistant",
            text: result.answer || result.error || "Log Analyst could not complete this request.",
            timestamp: new Date().toLocaleTimeString(),
            evidence: result.evidence || [],
            chart_data: result.chart_data || [],
            suggestions: result.suggestions || [],
            error: result.error || "request failed",
          },
        ]);
      } else {
        setAnalyticsMessages((prev) => [
          ...prev,
          {
            sender: "assistant",
            text: result.answer || "No response generated.",
            timestamp: new Date().toLocaleTimeString(),
            evidence: result.evidence || [],
            chart_data: result.chart_data || [],
            suggestions: result.suggestions || [],
          },
        ]);
      }
    } catch (e: any) {
      setAnalyticsMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "",
          timestamp: new Date().toLocaleTimeString(),
          error: e?.message || "Log Analyst request failed",
        },
      ]);
    } finally {
      setAnalyticsBusy(false);
    }
  }

  function sendDirectAnalyticsQuery(query: string) {
    void runLogAnalystChat(query);
  }

  function handleSendAnalyticsChat() {
    if (!analyticsInput.trim() || analyticsBusy) return;
    const userMsg = analyticsInput.trim();
    setAnalyticsInput("");
    void runLogAnalystChat(userMsg);
  }

  async function loadPlatformUsers() {
    try {
      const list = await api<PlatformUser[]>("/api/users");
      setPlatformUsers(list);
    } catch (e: any) {
      setNotice(e?.message || "Failed to load users");
    }
  }

  async function handleLogin() {
    setLoginBusy(true);
    setLoginError("");
    try {
      const res = await api<{ token: string; user: PlatformUser }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: loginForm.email, password: loginForm.password }),
      });
      setAuthToken(res.token);
      setAuthUser(res.user);
      const last = res.user?.session_info?.last_visited;
      if (last?.view) setActiveView(String(last.view));
    } catch (e: any) {
      setLoginError(e?.message || "Login failed");
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    setAuthToken("");
    setAuthUser(null);
  }

  // Monitoring auto-refresh (30s)
  useEffect(() => {
    if (!gtAutoRefresh || activeView !== "monitoring") return;
    const id = window.setInterval(() => {
      const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
      if (svc) loadGlitchTipDataForService(svc.name, gtWindow);
      loadGlitchTipIntegrationStatus();
    }, 30000);
    return () => window.clearInterval(id);
  }, [gtAutoRefresh, activeView, gtSelectedServiceId, selectedService, gtWindow, services]);

  // Performance auto-refresh (30s)
  useEffect(() => {
    if (!perfAutoRefresh || activeView !== "performance") return;
    const id = window.setInterval(() => {
      if (selectedService) loadServiceMetrics(selectedService.id);
      if (selectedNode) {
        loadNodeMetrics(selectedNode.id);
        loadNodeMetricsData(selectedNode.id);
      }
    }, 30000);
    return () => window.clearInterval(id);
  }, [perfAutoRefresh, activeView, selectedService, selectedNode]);

  // Cluster live status soft refresh (45s) while on clusters
  useEffect(() => {
    if (activeView !== "clusters") return;
    const id = window.setInterval(() => {
      refresh().catch(() => undefined);
      setLiveStatusTick((x) => x + 1);
    }, 45000);
    return () => window.clearInterval(id);
  }, [activeView]);

  function renderTreeNavigator(..._args: any[]) {
    return null;
  }

  function renderClustersView() {
    // JSX moved to views/ClustersView.tsx — kept for any legacy call sites
    return null;
  }

  function servicePortsLabel(service: Service): string {
    try {
      const cfg = JSON.parse((service as any).config_json || "{}");
      const ports = cfg.ports || cfg.published_ports || cfg.host_ports || [];
      if (Array.isArray(ports) && ports.length > 0) {
        return ports
          .map((p: any) => (typeof p === "string" || typeof p === "number" ? String(p) : p.host || p.published || p.port || ""))
          .filter(Boolean)
          .slice(0, 3)
          .join(", ");
      }
    } catch {
      /* ignore */
    }
    return "—";
  }


  function renderConfigManagerView(..._args: any[]) {
    return null;
  }

  function renderAiChat(..._args: any[]) {
    return null;
  }

  function renderDiagnosticsView(..._args: any[]) {
    return null;
  }

  function renderGlitchTipWorkspace(..._args: any[]) {
    return null;
  }

  function renderMonitoringView(..._args: any[]) {
    return null;
  }

  function renderDrawers(..._args: any[]) {
    return null;
  }

  function renderModals(..._args: any[]) {
    return null;
  }

  
  function renderPerformanceView(..._args: any[]) {
    return null;
  }

  function renderObservabilityStackView(..._args: any[]) {
    return null;
  }



  function renderTopologyView(..._args: any[]) {
    return null;
  }

  function renderPolicyView(..._args: any[]) {
    return null;
  }

  function renderAuditView(..._args: any[]) {
    return null;
  }

  function renderReliabilityView(..._args: any[]) {
    return null;
  }

  function renderUsersView(..._args: any[]) {
    return null;
  }




  const platformApi = {
    catalog,
    setCatalog,
    clusters,
    setClusters,
    nodes,
    setNodes,
    services,
    setServices,
    selectedService,
    setSelectedService,
    serviceSummary,
    setServiceSummary,
    serviceReleaseTimeline,
    setServiceReleaseTimeline,
    serviceMetrics,
    setServiceMetrics,
    serviceMetricsWindow,
    setServiceMetricsWindow,
    dashboardSummary,
    setDashboardSummary,
    clusterOperations,
    setClusterOperations,
    job,
    setJob,
    diagnostics,
    setDiagnostics,
    diagnosticsAnalysis,
    setDiagnosticsAnalysis,
    diagnosticsLive,
    setDiagnosticsLive,
    tailLines,
    setTailLines,
    historyPageSize,
    setHistoryPageSize,
    logsPollMs,
    setLogsPollMs,
    autoPollLogs,
    setAutoPollLogs,
    diagnosticsTargetKey,
    setDiagnosticsTargetKey,
    diagnosticsTargets,
    setDiagnosticsTargets,
    realtimeNodeMetrics,
    setRealtimeNodeMetrics,
    processMetrics,
    setProcessMetrics,
    perfProcessSort,
    setPerfProcessSort,
    diagFilePath,
    setDiagFilePath,
    loadingMetrics,
    setLoadingMetrics,
    diagnosticsSourceServiceId,
    setDiagnosticsSourceServiceId,
    configTimelinePage,
    setConfigTimelinePage,
    configTimelineAction,
    setConfigTimelineAction,
    configTimelineActor,
    setConfigTimelineActor,
    configTimelineSearch,
    setConfigTimelineSearch,
    configTimelineCreatedAfter,
    setConfigTimelineCreatedAfter,
    configTimelineCreatedBefore,
    setConfigTimelineCreatedBefore,
    configTimelineLimit,
    setConfigTimelineLimit,
    config,
    setConfig,
    snapshotPage,
    setSnapshotPage,
    snapshotCompare,
    setSnapshotCompare,
    snapshotSourceFilter,
    setSnapshotSourceFilter,
    checkpointFilter,
    setCheckpointFilter,
    checkpointSearch,
    setCheckpointSearch,
    selectedSnapshotPreview,
    setSelectedSnapshotPreview,
    snapshotSearch,
    setSnapshotSearch,
    snapshotLimit,
    setSnapshotLimit,
    migrationArtifactId,
    setMigrationArtifactId,
    migrationContent,
    setMigrationContent,
    migrationValidation,
    setMigrationValidation,
    migrationApplyResult,
    setMigrationApplyResult,
    topology,
    setTopology,
    events,
    setEvents,
    checks,
    setChecks,
    plan,
    setPlan,
    placement,
    setPlacement,
    observabilityPipeline,
    setObservabilityPipeline,
    observabilityBusyNodeId,
    setObservabilityBusyNodeId,
    obsStackBusy,
    setObsStackBusy,
    obsStackContainers,
    setObsStackContainers,
    obsStackOutput,
    setObsStackOutput,
    artifact,
    setArtifact,
    archives,
    setArchives,
    releases,
    setReleases,
    drift,
    setDrift,
    findings,
    setFindings,
    incidents,
    setIncidents,
    runbooks,
    setRunbooks,
    slos,
    setSlos,
    capacity,
    setCapacity,
    secrets,
    setSecrets,
    maintenance,
    setMaintenance,
    auditExports,
    setAuditExports,
    monitoringSubTab,
    setMonitoringSubTab,
    gtSelectedServiceId,
    setGtSelectedServiceId,
    gtIssues,
    setGtIssues,
    gtSelectedIssueId,
    setGtSelectedIssueId,
    gtEventDetails,
    setGtEventDetails,
    gtUptimeMonitors,
    setGtUptimeMonitors,
    gtKeys,
    setGtKeys,
    gtTransactions,
    setGtTransactions,
    gtIntegrationStatus,
    setGtIntegrationStatus,
    gtActiveMonitorTab,
    setGtActiveMonitorTab,
    gtWindow,
    setGtWindow,
    gtAutoRefresh,
    setGtAutoRefresh,
    gtSdkLang,
    setGtSdkLang,
    txSort,
    setTxSort,
    ingestionStats,
    setIngestionStats,
    archiveGzipOnly,
    setArchiveGzipOnly,
    archivePreviewLines,
    setArchivePreviewLines,
    archivePreviewLoading,
    setArchivePreviewLoading,
    diagLogSource,
    setDiagLogSource,
    logLevelFilters,
    setLogLevelFilters,
    logSearchQuery,
    setLogSearchQuery,
    logAutoScroll,
    setLogAutoScroll,
    selectedArchiveIds,
    setSelectedArchiveIds,
    historyPage,
    setHistoryPage,
    historyCursor,
    setHistoryCursor,
    historyTotalPages,
    setHistoryTotalPages,
    gtIssuesCursor,
    setGtIssuesCursor,
    gtIssuesHasMore,
    setGtIssuesHasMore,
    perfAutoRefresh,
    setPerfAutoRefresh,
    configEditMode,
    setConfigEditMode,
    configApplyMode,
    setConfigApplyMode,
    liveStatusTick,
    setLiveStatusTick,
    uptimeFormVisible,
    setUptimeFormVisible,
    uptimeForm,
    setUptimeForm,
    notice,
    setNotice,
    selectedCluster,
    setSelectedCluster,
    selectedNode,
    setSelectedNode,
    nodeMetrics,
    setNodeMetrics,
    nodeMetricsWindow,
    setNodeMetricsWindow,
    clusterEditor,
    setClusterEditor,
    nodeEditor,
    setNodeEditor,
    nodePreset,
    setNodePreset,
    clusterSummary,
    setClusterSummary,
    nodeSummary,
    setNodeSummary,
    nodeJobHistory,
    setNodeJobHistory,
    nodeConnection,
    setNodeConnection,
    nodeOnboarding,
    setNodeOnboarding,
    onboardingActionBusy,
    setOnboardingActionBusy,
    dtrainOverview,
    setDtrainOverview,
    selectedSubsystem,
    setSelectedSubsystem,
    configSource,
    setConfigSource,
    selectedPlacementServiceKey,
    setSelectedPlacementServiceKey,
    operatorPreferences,
    setOperatorPreferences,
    preferNodeId,
    setPreferNodeId,
    avoidNodeIds,
    setAvoidNodeIds,
    antiAffinityKey,
    setAntiAffinityKey,
    requireHealthyNodes,
    setRequireHealthyNodes,
    spreadSubsystem,
    setSpreadSubsystem,
    autoInstallDependencies,
    setAutoInstallDependencies,
    allowPlacementCapacityRisk,
    setAllowPlacementCapacityRisk,
    subsystemPlan,
    setSubsystemPlan,
    capabilities,
    setCapabilities,
    coverage,
    setCoverage,
    lifecycleAudit,
    setLifecycleAudit,
    forceApprovals,
    setForceApprovals,
    releaseApprovals,
    setReleaseApprovals,
    eventCategoryFilter,
    setEventCategoryFilter,
    eventLevelFilter,
    setEventLevelFilter,
    eventSearch,
    setEventSearch,
    eventLimit,
    setEventLimit,
    deleteModal,
    setDeleteModal,
    renameModal,
    setRenameModal,
    releaseApprovalModal,
    setReleaseApprovalModal,
    deploymentModal,
    setDeploymentModal,
    configTab,
    setConfigTab,
    diagTab,
    setDiagTab,
    analyticsMessages,
    setAnalyticsMessages,
    analyticsInput,
    setAnalyticsInput,
    analyticsBusy,
    setAnalyticsBusy,
    llmStatus,
    setLlmStatus,
    authUser,
    setAuthUser,
    authReady,
    setAuthReady,
    loginForm,
    setLoginForm,
    loginError,
    setLoginError,
    loginBusy,
    setLoginBusy,
    platformUsers,
    setPlatformUsers,
    usersTab,
    setUsersTab,
    inviteForm,
    setInviteForm,
    userForm,
    setUserForm,
    inviteAccept,
    setInviteAccept,
    stepperDrawerVisible,
    setStepperDrawerVisible,
    stepperStep,
    setStepperStep,
    onboardingJobId,
    setOnboardingJobId,
    onboardingOutput,
    setOnboardingOutput,
    onboardingError,
    setOnboardingError,
    onboardingStatus,
    setOnboardingStatus,
    selectedArchive,
    setSelectedArchive,
    catalogDrawerVisible,
    setCatalogDrawerVisible,
    catalogOnboarding,
    setCatalogOnboarding,
    treeSearchQuery,
    setTreeSearchQuery,
    nodeSearchQuery,
    setNodeSearchQuery,
    compareSnapshotLeft,
    setCompareSnapshotLeft,
    compareSnapshotRight,
    setCompareSnapshotRight,
    activeView,
    setActiveView,
    loadServiceCapabilities,
    loadServiceSummary,
    loadServiceReleaseTimeline,
    loadServiceMetrics,
    loadNodeConnection,
    loadNodeOnboarding,
    loadNodeMetrics,
    loadNodeJobHistory,
    pollOnboardingJob,
    loadClusterOperations,
    runOnboardingRemediation,
    bootstrapObservability,
    refreshObservabilityStackStatus,
    runObservabilityStackAction,
    discoverNodeInfra,
    launchNodeVm,
    teardownNodeVm,
    getOnboardingActionLabel,
    loadConfigTimeline,
    buildEventsPath,
    refresh,
    loadNodeMetricsData,
    loadGlitchTipIntegrationStatus,
    loadGlitchTipDataForService,
    loadMoreGtIssues,
    loadEventDetails,
    runIssueAction,
    runAddMonitor,
    runDeleteMonitor,
    runPatchObservability,
    selectCluster,
    selectNode,
    focusServiceInCluster,
    openClusterCreate,
    openClusterEdit,
    saveClusterEditor,
    testClusterRepoConnection,
    testClusterRegistryConnection,
    checkPortAndNameAvailability,
    applyNodePreset,
    openNodeCreate,
    openNodeEdit,
    saveNodeEditor,
    installCard,
    assignContractValue,
    parseInstallFieldValue,
    installSchemaValues,
    buildInstallOverrides,
    loadInstallSchemaFor,
    openCatalogOnboarding,
    openServiceEditor,
    confirmCatalogOnboarding,
    openDeploymentModal,
    executeDeploymentModal,
    installMissingDependencies,
    openDependencyTarget,
    ensureMissingDependencyCards,
    requestDelete,
    confirmDelete,
    requestForceDeleteApproval,
    approveForceDeleteApproval,
    rejectForceDeleteApproval,
    revokeForceDeleteApproval,
    backupService,
    registerSecret,
    rotateSecret,
    scheduleMaintenance,
    completeMaintenance,
    createAuditExport,
    requestReleaseSafety,
    openReleaseApprovalModal,
    createReleaseApprovalRequest,
    approveReleaseApprovalRequest,
    revokeReleaseApprovalRequest,
    confirmApprovedRelease,
    releaseService,
    loadReleases,
    rollbackRelease,
    planService,
    planPlacement,
    deployFromPlacement,
    loadArtifact,
    runMonitoringSweep,
    runPolicyScan,
    evaluateSlo,
    generateCapacity,
    openIncident,
    runIncidentRunbook,
    resolveIncident,
    loadDiagnostics,
    focusDiagnosticsTarget,
    loadDiagnosticsLive,
    bulkDownloadArchives,
    runLogBackfill,
    loadConfigSnapshots,
    loadConfig,
    viewSnapshot,
    syncPeerConfig,
    compareSelectedSnapshots,
    compareSpecificSnapshots,
    detectConfigDrift,
    captureSnapshot,
    applyCurrentConfig,
    prepareConfigMigration,
    validateMigrationYaml,
    applyPreparedMigration,
    restorePreparedMigration,
    openRenameSnapshot,
    renameSnapshot,
    restoreSnapshot,
    planSubsystem,
    deploySubsystem,
    validateNode,
    getConfigStrategy,
    getBackupStrategy,
    formatLocalTimestamp,
    runDiagnosticsInsightAction,
    openDiagnosticsSupportingEvidence,
    openDiagnosticsChangeEvidence,
    runLogAnalystChat,
    sendDirectAnalyticsQuery,
    handleSendAnalyticsChat,
    loadPlatformUsers,
    handleLogin,
    handleLogout,
    renderTreeNavigator,
    servicePortsLabel,
    renderClustersView,
    renderConfigManagerView,
    renderAiChat,
    renderDiagnosticsView,
    renderGlitchTipWorkspace,
    renderMonitoringView,
    renderDrawers,
    renderModals,
    renderPerformanceView,
    renderObservabilityStackView,
    renderTopologyView,
    renderPolicyView,
    renderAuditView,
    renderReliabilityView,
    renderUsersView,
  } as PlatformApi;

  return platformApi;
}


