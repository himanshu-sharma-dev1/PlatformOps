import React, { useEffect, useState, createContext, useContext } from "react";
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



export type PlatformApi = any;
const PlatformContext = createContext<PlatformApi | null>(null);

export function PlatformProvider({ children }: { children?: React.ReactNode }) {
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

  function renderTreeNavigator(
    onSelectService: (service: Service) => void,
    activeServiceId: number | null,
    options?: {
      onSelectNode?: (node: Node) => void;
      activeNodeId?: number | null;
      appServicesOnly?: boolean;
      hideSeedDemo?: boolean;
    },
  ) {
    const hideSeed = options?.hideSeedDemo !== false;
    const realClusters = clusters.filter((c) => !hideSeed || !isSeedDemoName(c.name));
    const q = treeSearchQuery.toLowerCase();

    return (
      <div className="tree-navigator" style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "100%", overflowY: "auto", paddingRight: "0.5rem" }}>
        <div className="tree-search">
          <input
            type="text"
            className="input"
            placeholder="Filter hierarchy…"
            value={treeSearchQuery}
            onChange={(e) => setTreeSearchQuery(e.target.value)}
            style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {realClusters.map((cluster) => {
            const clusterNodes = nodes.filter(
              (n) => n.cluster_id === cluster.id && (!hideSeed || !isSeedDemoName(n.name)),
            );
            const matchesSearch = !q || cluster.name.toLowerCase().includes(q);
            if (clusterNodes.length === 0 && !matchesSearch) return null;
            return (
              <div key={`tree-cluster-${cluster.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.25rem", padding: "0.25rem", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.04)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.4rem 0.6rem", cursor: "pointer" }} onClick={() => selectCluster(cluster)}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>{cluster.name}</span>
                  <span className="pill" style={{ fontSize: "0.7rem", scale: "0.9" }}>{cluster.environment}</span>
                </div>
                <div style={{ paddingLeft: "0.75rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                  {clusterNodes.map((node) => {
                    let nodeServices = services.filter((s) => s.node_id === node.id);
                    if (options?.appServicesOnly) {
                      nodeServices = nodeServices.filter((s) => s.kind !== "infrastructure");
                    }
                    const nodeMatches = !q || node.name.toLowerCase().includes(q) || matchesSearch;
                    if (nodeServices.length === 0 && !nodeMatches && !options?.onSelectNode) return null;
                    const nodeActive = options?.activeNodeId === node.id;
                    return (
                      <div key={`tree-node-${node.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            padding: "0.3rem 0.5rem",
                            cursor: "pointer",
                            borderRadius: "6px",
                            background: nodeActive ? "rgba(59,130,246,0.12)" : "transparent",
                            border: nodeActive ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
                          }}
                          onClick={() => {
                            if (options?.onSelectNode) options.onSelectNode(node);
                            else selectNode(node);
                          }}
                        >
                          <span style={{ fontSize: "0.8rem", color: nodeActive ? "var(--ink)" : "var(--ink-2)" }}>{node.name}</span>
                          <span className={`status-dot ${node.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }} />
                        </div>
                        <div style={{ paddingLeft: "0.85rem", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                          {nodeServices.map((service) => {
                            if (q && !service.name.toLowerCase().includes(q) && !nodeMatches) return null;
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
                                  background: isActive ? "rgba(59,130,246,0.15)" : "transparent",
                                  border: isActive ? "1px solid rgba(59,130,246,0.3)" : "none",
                                }}
                              >
                                <span style={{ fontSize: "0.75rem", color: isActive ? "var(--ink)" : "var(--ink-3)" }}>{service.name}</span>
                                <span className={`status-dot ${service.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }} />
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
          {realClusters.length === 0 && (
            <p style={{ color: "var(--ink-4)", fontSize: "0.85rem", padding: "0.5rem" }}>No operational clusters registered.</p>
          )}
        </div>
      </div>
    );
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

  function renderClustersView() {
    // JSX moved to views/ClustersView.tsx — kept for any legacy call sites
    return null;
  }


  function renderConfigManagerView() {
    // Config Manager with side-by-side tree and diff navigator (08-config-manager.html reference)
    const isCustomName = (name: string) => !/^v\d+-\d{8}-\d{6}/.test(name);
    const filteredSnapshots = (snapshotPage?.items ?? [])
      .filter((snap, idx) => {
        if (checkpointFilter === "active") return idx === 0;
        if (checkpointFilter === "renamed") return isCustomName(snap.name);
        if (checkpointFilter === "backup") return idx > 0;
        return true;
      })
      .filter(snap => {
        if (!checkpointSearch) return true;
        return snap.name.toLowerCase().includes(checkpointSearch.toLowerCase());
      });

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Config Manager</h1>
            <p className="sub">Edit live service configuration, capture checkpoints, compare versions, and apply or restore changes.</p>
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
            <GlassCard style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem", position: "relative" }}>
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
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                  <button className="btn btn-secondary btn-sm" onClick={captureSnapshot}>Capture snapshot</button>
                  <button className="btn btn-secondary btn-sm" onClick={detectConfigDrift}>Detect drift</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadConfig(selectedService, "live")}>Refresh live</button>
                  <button type="button" className={`btn btn-sm ${configEditMode ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigEditMode((v) => !v)}>{configEditMode ? "Editing" : "Edit mode"}</button>
                  <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                    <small style={{ color: "var(--ink-4)" }}>Apply:</small>
                    <button type="button" className={`btn btn-xs ${configApplyMode === "reload" ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigApplyMode("reload")}>Reload</button>
                    <button type="button" className={`btn btn-xs ${configApplyMode === "restart" ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigApplyMode("restart")}>Restart</button>
                  </div>
                  <button className="btn btn-primary btn-sm" onClick={applyCurrentConfig}>Apply config</button>
                </div>
              </div>

              {/* Workspaces tabs */}
              <div className="cluster-tabs">
                <div className={`tab ${configTab === "current" ? "active" : ""}`} onClick={() => setConfigTab("current")}>Current Config</div>
                <div className={`tab ${configTab === "timeline" ? "active" : ""}`} onClick={() => setConfigTab("timeline")}>Checkpoint Timeline</div>
                <div className={`tab ${configTab === "compare" ? "active" : ""}`} onClick={() => setConfigTab("compare")}>Compare / Diff</div>
                <div className={`tab ${configTab === "migration" ? "active" : ""}`} onClick={() => setConfigTab("migration")}>Migrate</div>
              </div>

              {/* Sub-tabs views */}
              {configTab === "current" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>

                  {(config?.content_source === "live_fallback" || config?.content_source === "latest_snapshot" || (config?.config_source_label || "").toLowerCase().includes("checkpoint") || (config?.config_source_label || "").toLowerCase().includes("fallback")) && (
                    <div style={{
                      padding: "0.75rem 1rem",
                      borderRadius: 10,
                      border: "1px solid rgba(234, 179, 8, 0.35)",
                      background: "rgba(234, 179, 8, 0.08)",
                      fontSize: "0.85rem",
                    }}>
                      <strong>Database / checkpoint fallback</strong>
                      <div style={{ color: "var(--ink-3)", marginTop: 4 }}>
                        Live file may be unavailable. Showing <code>{config?.config_source_label || config?.content_source}</code>.
                        You can still edit, validate, and apply when a node target is ready.
                      </div>
                    </div>
                  )}

                  {config?.active_checkpoint && (
                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "0.75rem 1rem",
                      background: config.drift_state === "in_sync" ? "rgba(16, 185, 129, 0.06)" : "rgba(239, 68, 68, 0.06)",
                      border: config.drift_state === "in_sync" ? "1px solid rgba(16, 185, 129, 0.15)" : "1px solid rgba(239, 68, 68, 0.15)",
                      borderRadius: "10px",
                      fontSize: "0.85rem",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ color: config.drift_state === "in_sync" ? "#34d399" : "#f87171" }}>●</span>
                        <span>
                          Active Checkpoint: <strong>v{config.active_checkpoint.version}</strong> · {config.active_checkpoint.name}
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span className={`pill ${config.drift_state === "in_sync" ? "pill-ok" : "pill-error"}`}>
                          {config.drift_state === "in_sync" ? "In Sync" : "Drifted"}
                        </span>
                        <button className="btn btn-secondary btn-xs" onClick={() => config.active_checkpoint && viewSnapshot(config.active_checkpoint.id)}>
                          View Active
                        </button>
                      </div>
                    </div>
                  )}

                  {selectedSnapshotPreview && (
                    <div style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <h4 style={{ margin: 0, fontSize: "0.95rem" }}>Snapshot View - {selectedSnapshotPreview.name}</h4>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button className="btn btn-secondary btn-xs" onClick={() => {
                            if (config) {
                              setConfig({ ...config, content: selectedSnapshotPreview.content });
                              setSelectedSnapshotPreview(null);
                              setNotice(`Loaded snapshot v${selectedSnapshotPreview.version} content into active editor`);
                            }
                          }}>
                            Load into Editor
                          </button>
                          <button className="btn btn-secondary btn-xs" onClick={() => setSelectedSnapshotPreview(null)}>Close</button>
                        </div>
                      </div>
                      <pre style={{
                        background: "#020408",
                        color: "#38bdf8",
                        fontFamily: "var(--mono)",
                        fontSize: "0.8rem",
                        padding: "1rem",
                        borderRadius: "8px",
                        maxHeight: "240px",
                        overflowY: "auto",
                        margin: 0
                      }}>
                        {selectedSnapshotPreview.content}
                      </pre>
                    </div>
                  )}

                  <textarea 
                    value={config?.content ?? ""} 
                    readOnly={!configEditMode}
                    onChange={(e) => setConfig(config ? { ...config, content: e.target.value } : null)}
                    style={{
                      flex: 1,
                      minHeight: "360px",
                      background: "#020408",
                      color: configEditMode ? "#38bdf8" : "#94a3b8",
                      fontFamily: "var(--mono)",
                      fontSize: "0.85rem",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "10px",
                      padding: "1rem",
                      outline: "none",
                      resize: "vertical",
                      opacity: configEditMode ? 1 : 0.9,
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
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  {/* Search and Filters toolbar */}
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button className={`chip ${checkpointFilter === "all" ? "on" : ""}`} onClick={() => setCheckpointFilter("all")}>All Checkpoints</button>
                      <button className={`chip ${checkpointFilter === "active" ? "on" : ""}`} onClick={() => setCheckpointFilter("active")}>Active</button>
                      <button className={`chip ${checkpointFilter === "renamed" ? "on" : ""}`} onClick={() => setCheckpointFilter("renamed")}>Renamed</button>
                      <button className={`chip ${checkpointFilter === "backup" ? "on" : ""}`} onClick={() => setCheckpointFilter("backup")}>Backups</button>
                    </div>
                    <input 
                      type="text" 
                      className="input" 
                      placeholder="Filter checkpoints by name..." 
                      value={checkpointSearch}
                      onChange={(e) => setCheckpointSearch(e.target.value)}
                      style={{ maxWidth: "240px", fontSize: "0.8rem", padding: "0.35rem 0.65rem", background: "rgba(255,255,255,0.04)" }}
                    />
                  </div>

                  {/* Active Snapshot Preview Card */}
                  {selectedSnapshotPreview && (
                    <div style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <h4 style={{ margin: 0, fontSize: "0.95rem" }}>Snapshot View - {selectedSnapshotPreview.name}</h4>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button className="btn btn-secondary btn-xs" onClick={() => {
                            if (config) {
                              setConfig({ ...config, content: selectedSnapshotPreview.content });
                              setNotice(`Loaded snapshot v${selectedSnapshotPreview.version} content into active editor`);
                              setConfigTab("current");
                            }
                          }}>
                            Load into Editor
                          </button>
                          <button className="btn btn-secondary btn-xs" onClick={() => setSelectedSnapshotPreview(null)}>Close Preview</button>
                        </div>
                      </div>
                      <pre style={{
                        background: "#020408",
                        color: "#38bdf8",
                        fontFamily: "var(--mono)",
                        fontSize: "0.8rem",
                        padding: "1rem",
                        borderRadius: "8px",
                        maxHeight: "300px",
                        overflowY: "auto",
                        margin: 0
                      }}>
                        {selectedSnapshotPreview.content}
                      </pre>
                    </div>
                  )}

                  {/* Checkpoints List */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {filteredSnapshots.map((snap) => {
                      const originalIdx = (snapshotPage?.items ?? []).findIndex(s => s.id === snap.id);
                      const isRenamed = isCustomName(snap.name);
                      return (
                        <div key={`checkpoint-item-${snap.id}`} style={{
                          border: "1px solid var(--line)",
                          borderRadius: "12px",
                          padding: "1rem",
                          background: originalIdx === 0 ? "rgba(99,102,241,0.04)" : "rgba(255,255,255,0.01)",
                          transition: "all 0.2s ease"
                        }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                                <strong style={{ fontSize: "0.95rem" }}>{snap.name}</strong>
                                <span className="pill" style={{ scale: 0.85 }}>v{snap.version}</span>
                                {isRenamed && <span className="pill pill-warn" style={{ scale: 0.85 }}>Renamed</span>}
                                <span className={`pill ${originalIdx === 0 ? "pill-primary" : "pill-secondary"}`} style={{ scale: 0.85 }}>
                                  {originalIdx === 0 ? "Active" : "Backup"}
                                </span>
                              </div>
                              <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                                Captured {formatLocalTimestamp(snap.created_at)} · Source: {snap.source}
                              </div>
                            </div>
                            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                              <button className="btn btn-secondary btn-xs" onClick={() => viewSnapshot(snap.id)}>View</button>
                              <button className="btn btn-secondary btn-xs" onClick={() => openRenameSnapshot(snap.id, snap.name)}>Rename</button>
                              <div 
                                onClick={() => {
                                  if (compareSnapshotLeft === snap.id) {
                                    setCompareSnapshotLeft(null);
                                  } else if (compareSnapshotRight === snap.id) {
                                    setCompareSnapshotRight(null);
                                  } else if (!compareSnapshotLeft) {
                                    setCompareSnapshotLeft(snap.id);
                                  } else {
                                    setCompareSnapshotRight(snap.id);
                                  }
                                }} 
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "0.35rem",
                                  cursor: "pointer",
                                  fontSize: "0.75rem",
                                  color: (compareSnapshotLeft === snap.id || compareSnapshotRight === snap.id) ? "var(--primary)" : "var(--ink-3)",
                                  border: "1px solid var(--line-2)",
                                  borderRadius: "6px",
                                  padding: "0.25rem 0.5rem",
                                  userSelect: "none"
                                }}
                              >
                                <input 
                                  type="checkbox" 
                                  checked={compareSnapshotLeft === snap.id || compareSnapshotRight === snap.id} 
                                  readOnly
                                  style={{ cursor: "pointer", pointerEvents: "none", margin: 0 }}
                                />
                                Compare {(compareSnapshotLeft === snap.id) ? "A" : (compareSnapshotRight === snap.id) ? "B" : ""}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    {filteredSnapshots.length === 0 && (
                      <div style={{ color: "var(--ink-4)", fontStyle: "italic", textAlign: "center", padding: "1.5rem" }}>
                        No checkpoints found matching the active filter.
                      </div>
                    )}
                  </div>

                  {/* Configuration Event Log (Timeline Events) */}
                  {configTimelinePage && configTimelinePage.items.length > 0 && (
                    <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1.5rem" }}>
                      <h4 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.75rem" }}>Configuration Event Log</h4>
                      <div className="timeline">
                        {configTimelinePage.items.map((event) => (
                          <article key={event.id}>
                            <span className="pill" style={{ scale: "0.8", alignSelf: "flex-start" }}>{event.action}</span>
                            <strong>{event.message}</strong>
                            <small style={{ color: "var(--ink-4)" }}>by {event.actor} · {formatLocalTimestamp(event.created_at)}</small>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
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
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button className="btn btn-secondary btn-sm" onClick={validateMigrationYaml}>Validate YAML</button>
                      <button className="btn btn-primary btn-sm" onClick={applyPreparedMigration}>Apply migration</button>
                      <button className="btn btn-secondary btn-sm" onClick={restorePreparedMigration}>Restore backup</button>
                    </div>
                  </div>

                  {/* Fleet Rollout Strategy Section */}
                  <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                      <h3 style={{ fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>Fleet Rollout Strategy</h3>
                      <small style={{ color: "var(--ink-4)" }}>Peer nodes sharing the same type</small>
                    </div>
                    <p style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginBottom: "1rem" }}>
                      The following sibling node instances in the cluster run the same service type. You can deploy the current validated configuration to peer nodes in a controlled sequence.
                    </p>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.75rem" }}>
                      {(config?.peers ?? []).map((peer) => (
                        <div key={`migrate-peer-${peer.service_id}`} style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "1rem",
                          border: "1px solid var(--line-2)",
                          borderRadius: "12px",
                          background: "rgba(255,255,255,0.02)"
                        }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{peer.node_name} / {peer.name}</div>
                            <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginTop: "0.2rem" }}>
                              service_id: {peer.service_id} · Status: {peer.status}
                            </div>
                          </div>
                          <button 
                            className="btn btn-secondary btn-sm" 
                            onClick={() => syncPeerConfig(peer.service_id, peer.node_name)}
                          >
                            Sync validated config
                          </button>
                        </div>
                      ))}
                      {(config?.peers ?? []).length === 0 && (
                        <div style={{ color: "var(--ink-4)", fontSize: "0.85rem", fontStyle: "italic", textAlign: "center", padding: "1rem" }}>
                          No sibling peer node instances of this type exist in the cluster.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Floating Compare Bar */}
              {(compareSnapshotLeft || compareSnapshotRight) && (
                <div style={{
                  position: "sticky",
                  bottom: "0",
                  background: "rgba(10, 15, 30, 0.95)",
                  backdropFilter: "blur(12px)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "16px",
                  padding: "1rem 1.5rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  boxShadow: "0 -8px 32px rgba(0,0,0,0.5)",
                  zIndex: 100,
                  marginTop: "1.5rem"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span className="pill pill-primary" style={{ scale: "0.9" }}>A</span>
                      <span style={{ fontSize: "0.85rem" }}>
                        {compareSnapshotLeft 
                          ? `v${(snapshotPage?.items ?? []).find(s => s.id === compareSnapshotLeft)?.version || compareSnapshotLeft}`
                          : "--"}
                      </span>
                    </div>
                    <span style={{ color: "var(--ink-4)" }}>➔</span>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span className="pill pill-secondary" style={{ scale: "0.9" }}>B</span>
                      <span style={{ fontSize: "0.85rem" }}>
                        {compareSnapshotRight 
                          ? `v${(snapshotPage?.items ?? []).find(s => s.id === compareSnapshotRight)?.version || compareSnapshotRight}`
                          : "--"}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button className="btn btn-secondary btn-sm" onClick={() => {
                      setCompareSnapshotLeft(null);
                      setCompareSnapshotRight(null);
                      setSnapshotCompare(null);
                    }}>
                      Clear Selection
                    </button>
                    <button 
                      className="btn btn-primary btn-sm" 
                      disabled={!compareSnapshotLeft || !compareSnapshotRight}
                      onClick={async () => {
                        setConfigTab("compare");
                        await compareSelectedSnapshots();
                      }}
                    >
                      Compare Checkpoints
                    </button>
                    <button 
                      className="btn btn-primary btn-sm" 
                      disabled={!compareSnapshotLeft || !compareSnapshotRight}
                      onClick={async () => {
                        setConfigTab("migration");
                        await prepareConfigMigration();
                      }}
                    >
                      Prepare Migration
                    </button>
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

        <div style={{ flex: 1, overflowY: "auto", padding: "1.2rem", display: "flex", flexDirection: "column", gap: "1.2rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(0, 0, 0, 0.15)", minHeight: "280px", maxHeight: "400px" }}>
          {analyticsMessages.map((msg, idx) => {
            const isUser = msg.sender === "user";
            return (
              <div key={idx} style={{ display: "flex", gap: "0.75rem", alignSelf: isUser ? "flex-end" : "flex-start", maxWidth: "80%" }}>
                {!isUser && (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "rgba(99, 102, 241, 0.08)", border: "1px solid var(--navy-500)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", alignSelf: "flex-start", flexShrink: 0 }}>🤖</div>
                )}
                <div style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                  <div style={{
                    background: isUser ? "var(--navy-700)" : "var(--bg-card)",
                    border: isUser ? "1px solid var(--navy-500)" : msg.error ? "1px solid rgba(239,68,68,0.45)" : "1px solid var(--line)",
                    boxShadow: isUser ? "0 0 10px rgba(99, 102, 241, 0.15)" : "none",
                    color: "#ffffff",
                    padding: "0.8rem 1rem",
                    borderRadius: isUser ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                    fontSize: "0.88rem",
                    lineHeight: "1.45",
                    maxWidth: "100%",
                  }}>
                    {msg.error && !msg.text ? (
                      <span style={{ color: "var(--err)" }}>{msg.error}</span>
                    ) : (
                      <div dangerouslySetInnerHTML={{ __html: (msg.text || "").replace(/\n/g, "<br/>") }} />
                    )}
                    {msg.error && msg.text ? (
                      <div style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--err)" }}>{msg.error}</div>
                    ) : null}
                    {!isUser && msg.evidence && msg.evidence.length > 0 && (
                      <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 8 }}>
                        <div style={{ fontSize: "0.7rem", color: "var(--ink-4)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Evidence</div>
                        {msg.evidence.slice(0, 4).map((ev, evi) => (
                          <div key={evi} style={{ fontFamily: "var(--mono)", fontSize: "0.72rem", color: "var(--ink-3)", marginBottom: 3 }}>
                            <span style={{ color: /err/i.test(ev.lvl || "") ? "var(--err)" : /warn/i.test(ev.lvl || "") ? "var(--warn)" : "var(--ink-4)" }}>{ev.lvl || "INFO"}</span>
                            {" "}
                            <span className="cited" style={{ color: "var(--navy-100)" }}>{ev.t || ""}</span>
                            {" — "}
                            {(ev.msg || "").slice(0, 180)}
                          </div>
                        ))}
                      </div>
                    )}
                    {!isUser && msg.chart_data && msg.chart_data.length > 0 && (
                      <div style={{ marginTop: 10 }}>
                        <div style={{ fontSize: "0.7rem", color: "var(--ink-4)", marginBottom: 4 }}>Error-rate spark</div>
                        <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 36 }}>
                          {msg.chart_data.map((v, ci) => {
                            const max = Math.max(...msg.chart_data!, 1);
                            const h = 4 + Math.round((Number(v) / max) * 28);
                            return <div key={ci} title={String(v)} style={{ flex: 1, height: h, background: "var(--navy-500)", borderRadius: "2px 2px 0 0", opacity: 0.85 }} />;
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: "0.68rem", color: "var(--ink-4)", marginTop: "4px" }}>
                    {msg.timestamp}
                  </span>
                </div>
                {isUser && (
                  <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "rgba(255, 255, 255, 0.05)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", alignSelf: "flex-start", flexShrink: 0 }}>👤</div>
                )}
              </div>
            );
          })}
        </div>

        {/* Suggestion Chips — dynamic from last LLM reply when available */}
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", padding: "0.25rem 0", alignItems: "center" }}>
          <span className="pill" style={{ fontSize: "0.7rem" }}>
            {llmStatus?.configured ? `LLM ${llmStatus.provider || ""}` : "LLM not configured"}
          </span>
          {(
            (analyticsMessages.slice().reverse().find((m) => m.sender === "assistant" && m.suggestions && m.suggestions.length)?.suggestions)
            || [
              "Summarize recent errors in the logs",
              "What is the most likely root cause?",
              "Which dependency looks unhealthy?",
              "Suggest next remediation steps",
            ]
          ).map((s, idx) => (
            <button
              key={idx}
              className="btn btn-secondary btn-sm"
              disabled={analyticsBusy}
              style={{ borderRadius: "20px", fontSize: "0.72rem", padding: "4px 10px", borderColor: "rgba(99,102,241,0.25)", background: "rgba(99,102,241,0.05)" }}
              onClick={() => sendDirectAnalyticsQuery(s)}
            >
              {s.length > 48 ? s.slice(0, 48) + "…" : s}
            </button>
          ))}
        </div>

        {/* Terminal Monospace Input */}
        <div style={{ display: "flex", gap: "0.5rem", padding: "0.4rem 0.6rem", background: "rgba(0, 0, 0, 0.3)", border: "1px solid var(--line)", borderRadius: "8px", alignItems: "center" }}>
          <span style={{ fontFamily: "var(--mono)", color: "var(--navy-500)", fontWeight: "bold", fontSize: "0.95rem", paddingLeft: "0.25rem" }}>$</span>
          <input
            type="text"
            className="input-text"
            style={{ flex: 1, background: "transparent", color: "#ffffff", border: "none", outline: "none", fontFamily: "var(--mono)", fontSize: "0.85rem", padding: "0.25rem" }}
            placeholder="Type command... target: to ks>"
            value={analyticsInput}
            onChange={(e) => setAnalyticsInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSendAnalyticsChat(); }}
          />
          <button className="btn btn-primary btn-sm" style={{ padding: "4px 10px" }} disabled={analyticsBusy || !analyticsInput.trim()} onClick={handleSendAnalyticsChat}>{analyticsBusy ? "Thinking…" : "Execute"}</button>
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
            <h1>Diagnostics</h1>
            <p className="sub">Service checklist, live logs, archive tools, and log analysis for the selected service.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary btn-sm" onClick={() => api<any>("/api/diagnostics/ingestion-stats").then(setIngestionStats).catch(() => setIngestionStats(null))}>Refresh KPIs</button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          <GlassCard style={{ padding: "1rem" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Live ingestion rate</div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>{ingestionStats?.ingestion_rate_display ?? "—"}</div>
            <small style={{ color: ingestionStats?.loki_reachable ? "var(--ok)" : "var(--ink-4)" }}>
              {ingestionStats?.loki_reachable ? "Loki reachable" : "Loki offline / no data"}
            </small>
          </GlassCard>
          <GlassCard style={{ padding: "1rem" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Hourly errors</div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>{ingestionStats?.error_count_current_hour ?? "—"}</div>
            <small style={{ color: "var(--ink-4)" }}>Δ {ingestionStats?.error_delta_pct ?? 0}% vs previous hour</small>
          </GlassCard>
          <GlassCard style={{ padding: "1rem" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Archive size</div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>
              {ingestionStats?.archive_size_bytes
                ? `${(Number(ingestionStats.archive_size_bytes) / (1024 * 1024 * 1024)).toFixed(2)} GB`
                : "—"}
            </div>
          </GlassCard>
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
                </div>
              </div>

              {/* Target Selector Bar */}
              {diagnosticsTargets.length > 0 && (
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", background: "rgba(255,255,255,0.02)", padding: "0.5rem 0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                  <small style={{ color: "var(--ink-4)" }}>Inspect Target Service:</small>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    {diagnosticsTargets.map((target) => {
                      const isSelected = diagnosticsTargetKey === target.service_key;
                      return (
                        <button
                          key={`diag-target-${target.service_key}`}
                          className={`btn ${isSelected ? "btn-primary" : "btn-secondary"} btn-xs`}
                          onClick={() => focusDiagnosticsTarget(target.service_key)}
                        >
                          {target.name} ({target.kind})
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Sub-tabs selectors */}
              <div className="cluster-tabs">
                <div className={`tab ${diagTab === "summary" ? "active" : ""}`} onClick={() => setDiagTab("summary")}>Summary</div>
                <div className={`tab ${diagTab === "tail" ? "active" : ""}`} onClick={() => setDiagTab("tail")}>Live tail</div>
                <div className={`tab ${diagTab === "files" ? "active" : ""}`} onClick={() => setDiagTab("files")}>Log files</div>
                <div className={`tab ${diagTab === "analytics" ? "active" : ""}`} onClick={() => setDiagTab("analytics")}>Log analyst</div>
              </div>

              {/* Tabs views */}
              {diagTab === "summary" && (
                <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.5rem" }}>
                  {/* Left Column: Diagnostics Summary, Top Evidence, Lifecycle Events */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                        <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Diagnostics Summary</h4>
                        <span className={`pill ${diagnostics?.status === "error" ? "pill-error" : "pill-ok"}`} style={{ scale: "0.9" }}>{diagnostics?.status || "—"}</span>
                      </div>
                      
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", fontSize: "0.85rem", marginBottom: "1rem" }}>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Primary Root Cause</span>
                          <strong>{diagnosticsAnalysis?.overview || "No anomalies detected"}</strong>
                        </div>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Target Scope</span>
                          <strong>{diagnostics?.target_service_key || "Self"}</strong>
                        </div>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Logs Coverage</span>
                          <strong>{diagnostics?.readiness.file_logs ? "Full logs coverage" : "Limited coverage"}</strong>
                        </div>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Source Provenance</span>
                          <strong>{diagnostics?.readiness.loki_url ? "Loki log pipeline" : "Local db logs"}</strong>
                        </div>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Runtime Status</span>
                          <strong>{diagnostics?.readiness.status || "—"}</strong>
                        </div>
                        <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                          <span style={{ color: "var(--ink-4)", display: "block" }}>Runtime Errors</span>
                          <strong style={{ color: diagnostics?.status === "error" ? "var(--err)" : "inherit" }}>
                            {diagnostics?.status === "error" ? "Anomalies found" : "None"}
                          </strong>
                        </div>
                      </div>
                    </div>

                    {/* Top Evidence / Warnings logs */}
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                      <h4 style={{ margin: 0, fontSize: "1rem", marginBottom: "0.75rem" }}>
                        Error and warning signatures
                      </h4>
                      <div style={{
                        background: "#020408",
                        padding: "0.75rem",
                        borderRadius: "8px",
                        border: "1px solid var(--line-2)",
                        maxHeight: "200px",
                        overflowY: "auto",
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.35rem"
                      }}>
                        {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? [])
                          .filter(l => l.level.toLowerCase().includes("err") || l.level.toLowerCase().includes("warn"))
                          .map((line, idx) => (
                            <div key={`evidence-${idx}`} style={{ fontSize: "0.78rem", display: "flex", gap: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.02)", paddingBottom: "2px" }}>
                              <span style={{ color: "var(--ink-4)" }}>{line.timestamp.substring(11, 19)}</span>
                              <span style={{ color: line.level.toLowerCase().includes("err") ? "var(--err)" : "var(--warn)", fontWeight: "bold" }}>
                                {line.level.toUpperCase()}
                              </span>
                              <span style={{ color: "#e2e8f0" }}>{line.message}</span>
                            </div>
                          ))}
                        {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).filter(l => l.level.toLowerCase().includes("err") || l.level.toLowerCase().includes("warn")).length === 0 && (
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "center", padding: "1rem" }}>
                            No warning or error signatures indexed for this timeline.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Recent Lifecycle Events */}
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                      <h4 style={{ margin: 0, fontSize: "1rem", marginBottom: "0.75rem" }}>
                        Recent lifecycle events
                      </h4>
                      <div className="timeline" style={{ maxHeight: "250px", overflowY: "auto", paddingRight: "0.5rem" }}>
                        {events.slice(0, 10).map((event) => (
                          <article key={event.id}>
                            <span className={`pill ${event.level === "error" ? "pill-error" : event.level === "warning" ? "pill-warn" : "pill-ok"}`} style={{ scale: "0.8", alignSelf: "flex-start" }}>
                              {event.category || "Event"}
                            </span>
                            <strong>{event.message}</strong>
                            <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(event.created_at)}</small>
                          </article>
                        ))}
                        {events.length === 0 && (
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "center", padding: "1rem" }}>
                            No recent lifecycle events recorded.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Issue Groups / Anomaly signatures */}
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div>
                      <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Issue Groups</h4>
                      <small style={{ color: "var(--warn)", fontWeight: 600 }}>Active anomaly signatures</small>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto", maxHeight: "600px" }}>
                      {(diagnosticsAnalysis?.insights ?? []).map((insight) => (
                        <div key={`insight-group-${insight.insight_id}`} style={{
                          padding: "0.9rem",
                          border: "1px solid var(--line-2)",
                          borderRadius: "10px",
                          background: insight.severity === "error" ? "rgba(239, 68, 68, 0.02)" : "rgba(251, 191, 36, 0.02)"
                        }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                            <strong style={{ fontSize: "0.88rem", color: insight.severity === "error" ? "var(--err)" : "var(--warn)" }}>
                              {insight.title}
                            </strong>
                            <span className="pill" style={{ scale: "0.8" }}>{insight.confidence}% confidence</span>
                          </div>
                          <p style={{ margin: "4px 0", fontSize: "0.82rem", color: "var(--ink-2)" }}>{insight.summary}</p>
                          <small style={{ color: "var(--ink-4)", display: "block" }}>{insight.rationale}</small>
                          {insight.actions.length > 0 && (
                            <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.35rem" }}>
                              {insight.actions.map(act => (
                                <button
                                  key={act.action_id}
                                  className={`btn btn-xs ${act.recommended ? "btn-primary" : "btn-secondary"}`}
                                  onClick={() => runDiagnosticsInsightAction(act)}
                                >
                                  {act.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                      {(diagnosticsAnalysis?.insights ?? []).length === 0 && (
                        <div style={{ color: "var(--ink-4)", fontStyle: "italic", textAlign: "center", padding: "2rem" }}>
                          No active issues or runtime anomalies identified.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {diagTab === "tail" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                      <select
                        value={diagLogSource}
                        onChange={async (e) => {
                          const src = e.target.value as typeof diagLogSource;
                          setDiagLogSource(src);
                          setHistoryPage(1);
                          setHistoryCursor("");
                          if (selectedService) await loadDiagnosticsLive(selectedService, { source: src, page: 1, cursor: 0 });
                        }}
                        className="input"
                        style={{ maxWidth: 200 }}
                      >
                        <option value="container_live">Container live</option>
                        <option value="container_history">Container history (Loki)</option>
                        <option value="file_live">File logs (live)</option>
                        <option value="file_history">File history (Loki)</option>
                      </select>

                      {(diagLogSource === "file_live" || diagLogSource === "file_history") && (
                        <select
                          className="input"
                          style={{ maxWidth: 260 }}
                          value={diagFilePath}
                          onChange={async (e) => {
                            setDiagFilePath(e.target.value);
                            if (selectedService) await loadDiagnosticsLive(selectedService, { source: diagLogSource, page: 1 });
                          }}
                        >
                          <option value="">Auto path</option>
                          {(diagnostics?.readiness?.paths_checked || []).map((p: any) => (
                            <option key={p.path} value={p.path}>{p.path}{p.readable ? "" : " (restricted)"}</option>
                          ))}
                        </select>
                      )}
                      <select value={tailLines} onChange={(e) => setTailLines(Number(e.target.value))}>
                        <option value={100}>Tail 100</option>
                        <option value={250}>Tail 250</option>
                        <option value={500}>Tail 500</option>
                        <option value={1000}>Tail 1000</option>
                      </select>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
                        <input type="checkbox" checked={autoPollLogs} onChange={(e) => setAutoPollLogs(e.target.checked)} disabled={diagLogSource !== "container_live"} />
                        Auto-poll
                      </label>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
                        <input type="checkbox" checked={logAutoScroll} onChange={(e) => setLogAutoScroll(e.target.checked)} />
                        Auto-scroll
                      </label>
                      <button type="button" className="btn btn-secondary btn-xs" onClick={() => setDiagnosticsLive((prev) => prev ? { ...prev, lines: [] } : prev)}>Clear</button>
                      {(diagLogSource === "container_history" || diagLogSource === "file_history") && (
                        <>
                          <button type="button" className="btn btn-secondary btn-xs" disabled={historyPage <= 1} onClick={async () => {
                            const p = Math.max(1, historyPage - 1);
                            setHistoryPage(p);
                            if (selectedService) await loadDiagnosticsLive(selectedService, { source: diagLogSource, page: p });
                          }}>Newer</button>
                          <button type="button" className="btn btn-secondary btn-xs" onClick={async () => {
                            const p = historyPage + 1;
                            setHistoryPage(p);
                            if (selectedService) await loadDiagnosticsLive(selectedService, { source: diagLogSource, page: p });
                          }}>Older</button>
                          <small style={{ color: "var(--ink-4)" }}>Page {historyPage}{historyTotalPages ? ` / ${historyTotalPages}` : ""}</small>
                        </>
                      )}
                    </div>
                    {diagnosticsLive && (
                      <small style={{ color: "var(--ink-4)" }}>
                        Loaded {diagnosticsLive.lines.length} lines · source {diagLogSource}
                      </small>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
                    {(["INFO", "WARN", "ERROR", "DEBUG"] as const).map((lvl) => (
                      <button
                        key={lvl}
                        type="button"
                        className={`btn btn-xs ${logLevelFilters[lvl] ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setLogLevelFilters((f) => ({ ...f, [lvl]: !f[lvl] }))}
                      >
                        {lvl}
                      </button>
                    ))}
                    <input
                      className="input"
                      style={{ maxWidth: 220, marginLeft: 8 }}
                      placeholder="Search / regex…"
                      value={logSearchQuery}
                      onChange={(e) => setLogSearchQuery(e.target.value)}
                    />
                  </div>
                  {/* Event rate sparkline */}
                  {diagnosticsLive && diagnosticsLive.lines.length > 0 && (
                    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 36, padding: "0 2px" }}>
                      {(() => {
                        const lines = diagnosticsLive.lines;
                        const bins = 18;
                        const size = Math.max(1, Math.ceil(lines.length / bins));
                        const counts = Array.from({ length: bins }, (_, i) => {
                          const slice = lines.slice(i * size, (i + 1) * size);
                          const info = slice.filter((l) => !/err|warn/i.test(l.level || "")).length;
                          const warn = slice.filter((l) => /warn/i.test(l.level || "")).length;
                          const err = slice.filter((l) => /err/i.test(l.level || "")).length;
                          return { info, warn, err, total: slice.length };
                        });
                        const maxT = Math.max(1, ...counts.map((c) => c.total));
                        return counts.map((c, i) => {
                          const h = 4 + Math.round(Math.sqrt(c.total) / Math.sqrt(maxT) * 28);
                          const ePct = c.total ? (c.err / c.total) * 100 : 0;
                          const wPct = c.total ? (c.warn / c.total) * 100 : 0;
                          const iPct = Math.max(0, 100 - ePct - wPct);
                          return (
                            <div
                              key={i}
                              title={`${c.total} lines`}
                              style={{
                                flex: 1,
                                height: h,
                                borderRadius: "2px 2px 0 0",
                                background: `linear-gradient(to top, var(--info) 0% ${iPct}%, var(--warn) ${iPct}% ${iPct + wPct}%, var(--err) ${iPct + wPct}% 100%)`,
                              }}
                            />
                          );
                        });
                      })()}
                    </div>
                  )}

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
                    {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).filter((line) => {
                      const lvl = (line.level || "INFO").toUpperCase();
                      const key = lvl.includes("ERR") ? "ERROR" : lvl.includes("WARN") ? "WARN" : lvl.includes("DEBUG") ? "DEBUG" : "INFO";
                      if (!logLevelFilters[key]) return false;
                      if (!logSearchQuery.trim()) return true;
                      try {
                        return new RegExp(logSearchQuery, "i").test(line.message || "");
                      } catch {
                        return (line.message || "").toLowerCase().includes(logSearchQuery.toLowerCase());
                      }
                    }).map((line, index) => {
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

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                    <h4 style={{ margin: 0 }}>Archived log files</h4>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.85rem", color: "var(--ink-3)" }}>
                        <input type="checkbox" checked={archiveGzipOnly} onChange={(e) => setArchiveGzipOnly(e.target.checked)} />
                        Gzipped only
                      </label>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={selectedArchiveIds.length === 0} onClick={bulkDownloadArchives}>
                        Bulk download ({selectedArchiveIds.length})
                      </button>
                    </div>
                  </div>
                  <table className="lf-table" style={{ marginTop: "0.5rem" }}>
                    <thead>
                      <tr>
                        <th style={{ width: 36 }}></th>
                        <th>File name path</th>
                        <th style={{ width: "120px" }}>Size</th>
                        <th style={{ width: "120px" }}>Line count</th>
                        <th style={{ width: "100px" }}>State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {archives.filter((arch) => !archiveGzipOnly || (arch.path || "").endsWith(".gz")).map((arch) => (
                        <tr 
                          key={arch.id} 
                          style={{ cursor: "pointer" }}
                          onClick={async () => {
                          setSelectedArchive(arch);
                          setArchivePreviewLines([]);
                          if (!selectedService) return;
                          setArchivePreviewLoading(true);
                          try {
                            let lines: any[] = [];
                            try {
                              const viewed = await api<any>(`/api/services/${selectedService.id}/diagnostics/archives/${arch.id}/view?max_lines=300`);
                              lines = viewed.lines || viewed.entries || viewed.content?.split?.("\n")?.map((m: string) => ({ message: m, level: "INFO", timestamp: new Date().toISOString() })) || [];
                            } catch {
                              const data = await api<any>(`/api/services/${selectedService.id}/diagnostics/file-tail?log_path=${encodeURIComponent(arch.path)}&tail_lines=300`);
                              lines = data.lines || data.entries || [];
                            }
                            setArchivePreviewLines(Array.isArray(lines) ? lines.map((l: any) => typeof l === "string" ? { message: l, level: "INFO", timestamp: new Date().toISOString() } : l) : []);
                          } catch {
                            setArchivePreviewLines([{ level: "WARN", message: "Unable to read file from node.", timestamp: new Date().toISOString() }]);
                          } finally {
                            setArchivePreviewLoading(false);
                          }
                        }}
                        >
                          <td onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={selectedArchiveIds.includes(arch.id)}
                              onChange={(e) => {
                                setSelectedArchiveIds((ids) =>
                                  e.target.checked ? [...ids, arch.id] : ids.filter((id) => id !== arch.id)
                                );
                              }}
                            />
                          </td>
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
                          <td colSpan={5} style={{ padding: "1.5rem", textAlign: "center", color: "var(--ink-4)" }}>No log archive folders scanned.</td>
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

  function renderGlitchTipWorkspace() {
    const selectedService = services.find((s) => s.id === gtSelectedServiceId) || services[0];
    
    const configured = gtIntegrationStatus?.configured;
    const reachable = gtIntegrationStatus?.reachable;
    
    const handleServiceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      const val = parseInt(e.target.value);
      setGtSelectedServiceId(val);
      const svc = services.find((s) => s.id === val);
      if (svc) {
        loadGlitchTipDataForService(svc.name);
      }
    };
    
    if (!gtSelectedServiceId && services.length > 0) {
      setGtSelectedServiceId(services[0].id);
      loadGlitchTipDataForService(services[0].name);
    }
    
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(255, 255, 255, 0.02)", padding: "0.75rem 1rem", borderRadius: "12px", border: "1px solid var(--line)" }}>
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className={`status-dot ${configured && reachable ? "ok" : "error"}`} style={{ width: "10px", height: "10px", borderRadius: "50%", display: "inline-block" }}></span>
              <strong style={{ fontSize: "0.9rem" }}>
                {configured && reachable ? "GlitchTip connected" : "GlitchTip offline"}
              </strong>
            </div>
            {configured && (
              <small style={{ color: "var(--ink-4)" }}>
                Base URL: <code>{gtIntegrationStatus?.base_url}</code> | Org: <code>{gtIntegrationStatus?.org}</code>
              </small>
            )}
          </div>
          
          <div style={{ fontSize: "0.85rem", color: "var(--ink-3)" }}>
              Target: <strong style={{ color: "var(--ink)" }}>{selectedService?.name || "—"}</strong>
              {selectedService ? <code style={{ marginLeft: 8 }}>{selectedService.service_key}</code> : null}
            </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 3fr", gap: "1.5rem" }}>
          <GlassCard style={{ padding: "1rem", height: "fit-content" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <button 
                onClick={() => setGtActiveMonitorTab("issues")}
                className={`btn ${gtActiveMonitorTab === "issues" ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
              >
                Issues ({gtIssues.length})
              </button>
              <button 
                onClick={() => setGtActiveMonitorTab("uptime")}
                className={`btn ${gtActiveMonitorTab === "uptime" ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
              >
                Uptime ({gtUptimeMonitors.length})
              </button>
              <button 
                onClick={() => setGtActiveMonitorTab("performance")}
                className={`btn ${gtActiveMonitorTab === "performance" ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
              >
                Performance ({gtTransactions.length})
              </button>
              <button 
                onClick={() => setGtActiveMonitorTab("keys")}
                className={`btn ${gtActiveMonitorTab === "keys" ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
              >
                Keys / SDK
              </button>
              <button 
                onClick={() => setGtActiveMonitorTab("patch")}
                className={`btn ${gtActiveMonitorTab === "patch" ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
              >
                Runtime patch
              </button>
            </div>
          </GlassCard>

          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {gtActiveMonitorTab === "issues" && (
              <GlassCard style={{ padding: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Active Issues &amp; Tracebacks</h3>
                  <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadGlitchTipDataForService(selectedService.name)}>Refresh</button>
                </div>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {gtIssues.map((issue) => {
                    const isExpanded = gtSelectedIssueId === issue.id;
                    return (
                      <div key={issue.id} style={{ border: "1px solid var(--line-2)", borderRadius: "8px", background: "rgba(255,255,255,0.01)", overflow: "hidden" }}>
                        <div style={{ padding: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", background: "rgba(255,255,255,0.01)" }} onClick={() => isExpanded ? setGtSelectedIssueId(null) : loadEventDetails(issue.id)}>
                          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                            <span className="pill pill-error" style={{ textTransform: "uppercase", fontSize: "0.7rem" }}>{issue.level}</span>
                            <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{issue.title}</span>
                          </div>
                          <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                            <span style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>Seen: <strong>{issue.count}</strong> times</span>
                            <span style={{ transition: "transform 0.2s", transform: isExpanded ? "rotate(90deg)" : "none" }}>▶</span>
                          </div>
                        </div>

                        {isExpanded && (
                          <div style={{ padding: "1rem", borderTop: "1px solid var(--line-2)", background: "rgba(0,0,0,0.15)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                            {gtEventDetails ? (
                              <>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", fontSize: "0.8rem" }}>
                                  <div>
                                    <div style={{ color: "var(--ink-4)" }}>Event ID:</div>
                                    <code>{gtEventDetails.eventID}</code>
                                  </div>
                                  <div>
                                    <div style={{ color: "var(--ink-4)" }}>Date / Time:</div>
                                    <code>{formatLocalTimestamp(gtEventDetails.dateCreated)}</code>
                                  </div>
                                </div>

                                {gtEventDetails.entries?.map((entry: any, index: number) => {
                                  if (entry.type === "exception") {
                                    return (
                                      <div key={index} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                        <h4 style={{ fontSize: "0.9rem", color: "var(--err)", fontWeight: 600 }}>Stack Trace Exception</h4>
                                        {entry.data?.values?.map((val: any, valIdx: number) => (
                                          <div key={valIdx} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                            <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--err)" }}>{val.type}: {val.value}</div>
                                            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                                              {val.stacktrace?.frames?.map((frame: any, frameIdx: number) => (
                                                <div key={frameIdx} style={{ padding: "0.5rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line-2)", borderRadius: "6px", fontSize: "0.8rem" }}>
                                                  <div style={{ display: "flex", justifyContent: "space-between", color: "var(--ink-3)" }}>
                                                    <span>File: <code>{frame.filename}</code></span>
                                                    <span>Line: <strong>{frame.lineNo}</strong> in <code>{frame.function}</code></span>
                                                  </div>
                                                  {frame.context_line && (
                                                    <pre style={{ margin: "6px 0 0 0", padding: "4px", background: "rgba(0,0,0,0.3)", borderRadius: "4px", borderLeft: "3px solid var(--err)", color: "var(--ink-2)", overflowX: "auto" }}>
                                                      {frame.context_line}
                                                    </pre>
                                                  )}
                                                  {frame.vars && Object.keys(frame.vars).length > 0 && (
                                                    <div style={{ marginTop: "6px", fontSize: "0.75rem" }}>
                                                      <span style={{ color: "var(--ink-4)", fontWeight: 600 }}>Local variables:</span>
                                                      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "4px" }}>
                                                        <tbody>
                                                          {Object.entries(frame.vars).map(([k, v]: [string, any]) => (
                                                            <tr key={k} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                                                              <td style={{ color: "var(--navy-100)", width: "30%", padding: "2px 4px" }}>{k}</td>
                                                              <td style={{ color: "var(--ink-3)", padding: "2px 4px" }}><code>{JSON.stringify(v)}</code></td>
                                                            </tr>
                                                          ))}
                                                        </tbody>
                                                      </table>
                                                    </div>
                                                  )}
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    );
                                  }
                                  if (entry.type === "breadcrumbs") {
                                    return (
                                      <div key={index} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                        <h4 style={{ fontSize: "0.9rem", color: "var(--navy-100)", fontWeight: 600 }}>Breadcrumbs Timeline</h4>
                                        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "250px", overflowY: "auto" }}>
                                          {entry.data?.values?.map((crumb: any, cIdx: number) => (
                                            <div key={cIdx} style={{ fontSize: "0.75rem", padding: "4px 8px", background: "rgba(255,255,255,0.02)", borderLeft: "3px solid var(--line-2)", display: "flex", gap: "1rem" }}>
                                              <span style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(crumb.timestamp)}</span>
                                              <span className="pill" style={{ fontSize: "0.65rem", padding: "2px 4px" }}>{crumb.category}</span>
                                              <span style={{ flex: 1 }}>{crumb.message}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    );
                                  }
                                  return null;
                                })}
                                
                                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                                  <button className="btn btn-secondary btn-sm" onClick={() => runIssueAction(issue.id, "resolve", selectedService.name)}>Mark Resolved</button>
                                  <button className="btn btn-secondary btn-sm" onClick={() => runIssueAction(issue.id, "ignore", selectedService.name)}>Ignore / Mute</button>
                                </div>
                              </>
                            ) : (
                              <div style={{ color: "var(--ink-4)", textAlign: "center", padding: "1rem" }}>Loading issue traceback event details...</div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {gtIssues.length > 0 && (
                    <div style={{ display: "flex", justifyContent: "center", padding: "0.75rem" }}>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={!gtIssuesHasMore} onClick={loadMoreGtIssues}>
                        {gtIssuesHasMore ? "Load more issues" : "No more issues"}
                      </button>
                    </div>
                  )}
                  {gtIssues.length === 0 && (
                    <div style={{ textAlign: "center", padding: "2rem", color: "var(--ink-4)" }}>No unresolved issues mapped to this project slug in GlitchTip.</div>
                  )}
                </div>
              </GlassCard>
            )}

            {gtActiveMonitorTab === "uptime" && (
              <GlassCard style={{ padding: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>TCP / HTTP Uptime Monitors</h3>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn btn-primary btn-sm" onClick={() => setUptimeFormVisible(!uptimeFormVisible)}>
                      {uptimeFormVisible ? "Cancel" : "Add Monitor"}
                    </button>
                    <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadGlitchTipDataForService(selectedService.name)}>Refresh</button>
                  </div>
                </div>

                {uptimeFormVisible && (
                  <div style={{ border: "1px solid var(--line)", borderRadius: "10px", padding: "1rem", background: "rgba(0,0,0,0.1)", marginBottom: "1rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    <div>
                      <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Monitor Name *</label>
                      <input 
                        type="text" 
                        value={uptimeForm.name} 
                        onChange={(e) => setUptimeForm({ ...uptimeForm, name: e.target.value })}
                        style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Target URL *</label>
                      <input 
                        type="text" 
                        value={uptimeForm.url} 
                        onChange={(e) => setUptimeForm({ ...uptimeForm, url: e.target.value })}
                        style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Type</label>
                      <select 
                        value={uptimeForm.monitor_type} 
                        onChange={(e) => setUptimeForm({ ...uptimeForm, monitor_type: e.target.value })}
                        style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                      >
                        <option value="Ping">Ping TCP Connect</option>
                        <option value="GET">HTTP GET</option>
                        <option value="POST">HTTP POST</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Interval (sec)</label>
                      <input 
                        type="number" 
                        value={uptimeForm.interval} 
                        onChange={(e) => setUptimeForm({ ...uptimeForm, interval: e.target.value })}
                        style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                      />
                    </div>
                    <div style={{ gridColumn: "span 2", display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                      <button className="btn btn-primary" onClick={() => selectedService && runAddMonitor(selectedService.name)}>Submit</button>
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {gtUptimeMonitors.map((mon) => (
                    <div key={mon.id} style={{ border: "1px solid var(--line-2)", borderRadius: "8px", padding: "1rem", background: "rgba(255,255,255,0.01)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            <span className={`status-dot ${mon.isUp ? "ok" : "error"}`} style={{ width: "8px", height: "8px", borderRadius: "50%" }}></span>
                            <strong style={{ fontSize: "0.95rem" }}>{mon.name}</strong>
                            <small style={{ color: "var(--ink-4)" }}>({mon.monitorType})</small>
                          </div>
                          <span style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginTop: "2px" }}>Target: <code>{mon.url}</code></span>
                        </div>
                        <button className="icon-btn btn-error" onClick={() => selectedService && runDeleteMonitor(mon.id, selectedService.name)}>
                          🗑️
                        </button>
                      </div>

                      {(() => {
                        const history = mon.checks || mon.incidents || [];
                        const latency = uptimeLatencySeries(history);
                        return (
                          <div style={{ marginTop: "0.85rem", borderTop: "1px solid rgba(255,255,255,0.03)", paddingTop: "0.65rem" }}>
                            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>
                              Availability timeline
                            </span>
                            {renderUptimeAvailabilityBlocks(history)}
                            {latency.length > 0 && (
                              <div style={{ marginTop: "0.75rem" }}>
                                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>
                                  Response latency (ms)
                                </span>
                                {renderSVGTimeSeriesChart(latency, { color: "#38bdf8", unit: " ms", height: 64 })}
                              </div>
                            )}
                            {mon.incidents && mon.incidents.length > 0 && (
                              <div style={{ marginTop: "0.75rem" }}>
                                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Incidents history</span>
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "120px", overflowY: "auto" }}>
                                  {mon.incidents.slice(0, 5).map((inc: any, iIdx: number) => (
                                    <div key={iIdx} style={{ fontSize: "0.75rem", display: "flex", justifyContent: "space-between", padding: "2px 4px", background: "rgba(255,255,255,0.02)" }}>
                                      <span style={{ color: inc.isUp ? "var(--ok)" : "var(--err)" }}>{inc.isUp ? "ONLINE" : "OFFLINE"}</span>
                                      <span style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(inc.startCheck)}</span>
                                      <span style={{ color: "var(--ink-3)" }}>{inc.reason || "status code check"}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  ))}
                  {gtUptimeMonitors.length === 0 && (
                    <div style={{ textAlign: "center", padding: "2rem", color: "var(--ink-4)" }}>No uptime monitors active for this project.</div>
                  )}
                </div>
              </GlassCard>
            )}

            {gtActiveMonitorTab === "performance" && (
              <GlassCard style={{ padding: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", gap: "0.75rem", flexWrap: "wrap" }}>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 600, margin: 0 }}>API Transaction Endpoints (APM)</h3>
                  <select value={txSort} onChange={(e) => setTxSort(e.target.value as any)} className="input" style={{ maxWidth: 180 }}>
                    <option value="latency">Sort: Latency</option>
                    <option value="throughput">Sort: Throughput</option>
                    <option value="failure">Sort: Failure rate</option>
                  </select>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--line-2)", color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Route Transaction</th>
                        <th style={{ padding: "0.5rem" }}>Throughput</th>
                        <th style={{ padding: "0.5rem" }}>Avg Latency</th>
                        <th style={{ padding: "0.5rem" }}>Failure %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...gtTransactions].sort((a, b) => {
                        if (txSort === "throughput") return (b.count || 0) - (a.count || 0);
                        if (txSort === "failure") return (b.failureRate || 0) - (a.failureRate || 0);
                        return (b.avgDuration || 0) - (a.avgDuration || 0);
                      }).map((tx, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)", fontSize: "0.85rem" }}>
                          <td style={{ padding: "0.5rem", color: "var(--navy-100)" }}><code>{tx.transaction || tx.name || "—"}</code></td>
                          <td style={{ padding: "0.5rem" }}>{tx.count ?? "—"}</td>
                          <td style={{ padding: "0.5rem" }}>{Math.round(tx.avgDuration || 0)} ms</td>
                          <td style={{ padding: "0.5rem" }}>{tx.failureRate != null ? `${Number(tx.failureRate).toFixed(1)}%` : "—"}</td>
                        </tr>
                      ))}
                      {gtTransactions.length === 0 && (
                        <tr>
                          <td colSpan={4} style={{ padding: "1.5rem", textAlign: "center", color: "var(--ink-4)" }}>No performance telemetry collected for this window.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            )}

            {gtActiveMonitorTab === "keys" && (
              <GlassCard style={{ padding: "1.5rem" }}>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>DSN Keys &amp; SDK Quickstart</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {gtKeys.map((keyInfo, idx) => (
                    <div key={idx} style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "8px", background: "rgba(255,255,255,0.01)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>DSN (Data Source Name)</div>
                        <button type="button" className="btn btn-secondary btn-xs" onClick={() => {
                          const dsn = keyInfo.dsn?.public || "";
                          if (dsn) navigator.clipboard?.writeText(dsn).then(() => setNotice("DSN copied")).catch(() => setNotice(dsn));
                        }}>Copy</button>
                      </div>
                      <pre style={{ margin: 0, padding: "8px", background: "rgba(0,0,0,0.3)", borderRadius: "6px", color: "var(--navy-100)", fontSize: "0.85rem", overflowX: "auto" }}>
                        {keyInfo.dsn?.public}
                      </pre>
                    </div>
                  ))}
                  
                  {gtKeys.length === 0 && (
                    <p style={{ color: "var(--ink-4)" }}>No SDK keys returned from GlitchTip for this service.</p>
                  )}

                  <div style={{ marginTop: "1rem" }}>
                    <div style={{ display: "flex", gap: "0.35rem", marginBottom: "0.5rem" }}>
                      {(["python", "javascript", "go"] as const).map((lang) => (
                        <button key={lang} type="button" className={`btn btn-xs ${gtSdkLang === lang ? "btn-primary" : "btn-secondary"}`} onClick={() => setGtSdkLang(lang)}>{lang}</button>
                      ))}
                    </div>
                    <pre style={{ margin: 0, padding: "10px", background: "rgba(0,0,0,0.4)", borderRadius: "8px", fontSize: "0.8rem", color: "var(--ink-3)", overflowX: "auto" }}>
{(() => {
                      const dsn = gtKeys[0]?.dsn?.public;
                      if (!dsn) return "No DSN available — configure GlitchTip project keys first.";
                      if (gtSdkLang === "javascript") return `npm install @sentry/node

Sentry.init({
  dsn: "${dsn}",
  tracesSampleRate: 1.0,
});`;
                      if (gtSdkLang === "go") return `import "github.com/getsentry/sentry-go"

err := sentry.Init(sentry.ClientOptions{
  Dsn: "${dsn}",
})`;
                      return `pip install sentry-sdk

import sentry_sdk
sentry_sdk.init(
    dsn="${dsn}",
    traces_sample_rate=1.0,
)`;
                    })()}
                    </pre>
                  </div>
                </div>
              </GlassCard>
            )}

            {gtActiveMonitorTab === "patch" && (
              <GlassCard style={{ padding: "1.5rem" }}>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem" }}>sentry_sdk Injection &amp; Patching</h3>
                <p style={{ fontSize: "0.85rem", color: "var(--ink-3)", marginBottom: "1rem" }}>
                  Injects the <code>sentry_sdk</code> package dynamically into the selected service's Docker container, configures <code>sitecustomize.py</code>, and triggers a container restart to start piping exceptions.
                </p>
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                  <button 
                    className="btn btn-primary" 
                    onClick={() => selectedService && runPatchObservability(selectedService.id, selectedService.name)}
                    disabled={!selectedService}
                  >
                    Run runtime patch
                  </button>
                  <small style={{ color: "var(--ink-4)" }}>
                    Target container: <code>{selectedService?.container_name || "not selected"}</code>
                  </small>
                </div>
              </GlassCard>
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderMonitoringView() {
    const opNodes = nodes.filter((n) => !isSeedDemoName(n.name));
    const online = opNodes.filter((n) => ["healthy", "online", "ready", "running"].includes((n.status || "").toLowerCase())).length;
    let gpuCount = 0;
    opNodes.forEach((n) => {
      try {
        const f = JSON.parse(n.facts_json || "{}");
        if (f.gpu || f.gpu_model || f.gpu_exporter === "enabled" || f.gpu_available) gpuCount += 1;
      } catch { /* ignore */ }
    });
    const appServices = services.filter((s) => s.kind !== "infrastructure");

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Monitoring</h1>
            <p className="sub">GlitchTip issues, uptime, APM transactions, and SDK keys. Select an application service from the tree.</p>
          </div>
          <div className="actions" style={{ flexWrap: "wrap" }}>
            {(["24h", "7d"] as const).map((w) => (
              <button key={w} type="button" className={`btn btn-sm ${gtWindow === w ? "btn-primary" : "btn-secondary"}`} onClick={() => {
                setGtWindow(w);
                const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
                if (svc) loadGlitchTipDataForService(svc.name, w);
              }}>{w === "24h" ? "Last 24h" : "Last 7d"}</button>
            ))}
            <button type="button" className={`btn btn-sm ${gtAutoRefresh ? "btn-primary" : "btn-secondary"}`} onClick={() => setGtAutoRefresh((v) => !v)}>
              {gtAutoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
            </button>
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => {
              loadGlitchTipIntegrationStatus();
              const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
              if (svc) loadGlitchTipDataForService(svc.name, gtWindow);
            }}>Refresh now</button>
          </div>
        </div>

        <div className="stat-strip">
          <div className="stat-tile"><div className="stat-label">Clusters</div><div className="stat-value">{clusters.filter((c) => !isSeedDemoName(c.name)).length}</div></div>
          <div className="stat-tile"><div className="stat-label">Nodes</div><div className="stat-value">{opNodes.length}</div></div>
          <div className="stat-tile"><div className="stat-label">Online</div><div className="stat-value">{online}</div></div>
          <div className="stat-tile"><div className="stat-label">GPU nodes</div><div className="stat-value">{gpuCount}</div></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem", minHeight: "560px" }}>
          <GlassCard style={{ padding: "1rem" }}>
            {renderTreeNavigator(
              async (service) => {
                setSelectedService(service);
                setGtSelectedServiceId(service.id);
                await loadGlitchTipDataForService(service.name, gtWindow);
                loadGlitchTipIntegrationStatus();
              },
              gtSelectedServiceId ?? selectedService?.id ?? null,
              { appServicesOnly: true, hideSeedDemo: true },
            )}
          </GlassCard>
          <div>
            {gtSelectedServiceId || selectedService ? (
              renderGlitchTipWorkspace()
            ) : (
              <GlassCard style={{ padding: "2.5rem", textAlign: "center" }}>
                <h3 style={{ marginBottom: "0.5rem" }}>Select a service</h3>
                <p style={{ color: "var(--ink-4)" }}>
                  {appServices.length === 0 ? "No application services registered." : "Choose an application service from the hierarchy."}
                </p>
              </GlassCard>
            )}
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
            <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "640px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "90vh", overflowY: "auto" }}>
              <h3>{clusterEditor.mode === "create" ? "Create Cluster" : "Cluster settings"}</h3>
              <div className="cluster-tabs" style={{ marginBottom: 0 }}>
                <div className="tab active">1. Identity</div>
                <div className="tab active">2. Repository</div>
                <div className="tab active">3. Registry</div>
                <div className="tab active">4. Review</div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="field">
                    <label>Cluster name</label>
                    <input className="input" value={clusterEditor.draft.name} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} placeholder="e.g. prod-mumbai-1" />
                  </div>
                  <div className="field">
                    <label>Region</label>
                    <input className="input" value={clusterEditor.draft.region} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, region: e.target.value } }))} placeholder="e.g. ap-south-1" />
                  </div>
                </div>
                <div className="field">
                  <label>Environment</label>
                  <select value={clusterEditor.draft.environment} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, environment: e.target.value } }))}>
                    <option value="development">Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                    <option value="standalone">Standalone</option>
                    <option value="edge">Edge</option>
                  </select>
                </div>

                <h4 style={{ margin: "0.5rem 0 0", fontSize: "0.95rem" }}>Code repository</h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="field">
                    <label>Repo type</label>
                    <select value={clusterEditor.draft.repo_type} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, repo_type: e.target.value } }))}>
                      <option value="github">GitHub</option>
                      <option value="gitlab">GitLab</option>
                      <option value="local">Local path</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Branch</label>
                    <input className="input" value={clusterEditor.draft.repo_branch} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, repo_branch: e.target.value } }))} />
                  </div>
                </div>
                <div className="field">
                  <label>Repository URL</label>
                  <input className="input" value={clusterEditor.draft.repo_url} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, repo_url: e.target.value } }))} placeholder="https://github.com/org/repo.git" />
                </div>
                <div className="field">
                  <label>Access token {clusterEditor.mode === "edit" ? "(leave blank to keep)" : ""}</label>
                  <input className="input" type="password" value={clusterEditor.draft.repo_token} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, repo_token: e.target.value } }))} placeholder={clusterEditor.mode === "edit" ? "••••••••" : "optional"} />
                </div>
                <div>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={testClusterRepoConnection}>Test repository connection</button>
                </div>

                <h4 style={{ margin: "0.5rem 0 0", fontSize: "0.95rem" }}>Container registry</h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="field">
                    <label>Registry type</label>
                    <select value={clusterEditor.draft.registry_type} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, registry_type: e.target.value } }))}>
                      <option value="dockerhub">Docker Hub</option>
                      <option value="ecr">ECR</option>
                      <option value="gcr">GCR</option>
                      <option value="local">Local registry</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Username</label>
                    <input className="input" value={clusterEditor.draft.registry_user} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, registry_user: e.target.value } }))} />
                  </div>
                </div>
                <div className="field">
                  <label>Registry URL</label>
                  <input className="input" value={clusterEditor.draft.registry_url} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, registry_url: e.target.value } }))} placeholder="registry-1.docker.io" />
                </div>
                <div className="field">
                  <label>Password / access key {clusterEditor.mode === "edit" ? "(leave blank to keep)" : ""}</label>
                  <input className="input" type="password" value={clusterEditor.draft.registry_password} onChange={(e) => setClusterEditor((prev) => ({ ...prev, draft: { ...prev.draft, registry_password: e.target.value } }))} placeholder={clusterEditor.mode === "edit" ? "••••••••" : ""} />
                </div>
                <div>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={testClusterRegistryConnection}>Test registry connection</button>
                </div>
              </div>
              {clusterEditor.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{clusterEditor.error}</p>}
              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setClusterEditor((prev) => ({ ...prev, visible: false }))}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={saveClusterEditor}>{clusterEditor.mode === "create" ? "Create cluster" : "Save settings"}</button>
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
                  <label>SSH Key Path (Optional if key pasted below)</label>
                  <input className="input" value={nodeEditor.draft.ssh_key_path} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_key_path: e.target.value } }))} placeholder="e.g. ~/.ssh/id_rsa" />
                </div>
                <div className="field">
                  <label>SSH Private Key Content (PEM format)</label>
                  <textarea 
                    className="input" 
                    style={{ 
                      minHeight: "100px", 
                      fontFamily: "var(--mono)", 
                      fontSize: "0.75rem", 
                      background: "rgba(0,0,0,0.2)", 
                      border: "1px solid var(--line)", 
                      color: "#fff",
                      padding: "0.5rem",
                      borderRadius: "6px",
                      resize: "vertical"
                    }} 
                    value={nodeEditor.draft.ssh_private_key || ""} 
                    onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_private_key: e.target.value } }))} 
                    placeholder="-----BEGIN OPENSSH PRIVATE KEY-----\n..." 
                  />
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
                  {(archivePreviewLoading ? [{ level: "INFO", message: "Loading file…", timestamp: new Date().toISOString() }] : archivePreviewLines).map((line, index) => {
                    const timeStr = new Date(line.timestamp || Date.now()).toISOString().replace("T", " ").substring(0, 19);
                    const levelUpper = (line.level || "INFO").padEnd(5);
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

              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", borderTop: "1px solid var(--line)", paddingTop: "1rem", flexWrap: "wrap" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedArchive(null)}>Close Preview</button>
                {selectedService && selectedArchive && (
                  <a
                    className="btn btn-secondary btn-sm"
                    href={`/api/services/${selectedService.id}/diagnostics/archives/${selectedArchive.id}/download`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                )}
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

  
  function renderPerformanceView() {
    const showNode = !!selectedNode && !isSeedDemoName(selectedNode.name);
    const showService = !!selectedService && services.some((s) => s.id === selectedService.id);

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Performance</h1>
            <p className="sub">Prometheus metrics for nodes and services. Select from the hierarchy — empty when exporters have no data.</p>
          </div>
          <div className="actions">
            {renderMetricWindowPicker(nodeMetricsWindow, (w) => {
              setNodeMetricsWindow(w);
              setServiceMetricsWindow(w);
              if (selectedService) loadServiceMetrics(selectedService.id, w);
              else if (selectedNode) {
                loadNodeMetrics(selectedNode.id, w);
                loadNodeMetricsData(selectedNode.id);
              }
            })}
            <button
              type="button"
              className={`btn btn-sm ${perfAutoRefresh ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setPerfAutoRefresh((v) => !v)}
            >
              {perfAutoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
            </button>
            <button
              className="btn btn-secondary btn-sm"
              disabled={loadingMetrics}
              onClick={() => {
                if (selectedService) loadServiceMetrics(selectedService.id);
                if (selectedNode) {
                  loadNodeMetrics(selectedNode.id);
                  loadNodeMetricsData(selectedNode.id);
                }
              }}
            >
              {loadingMetrics ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>

        {(() => {
          const opNodes = nodes.filter((n) => !isSeedDemoName(n.name));
          const online = opNodes.filter((n) => ["healthy", "online", "ready", "running"].includes((n.status || "").toLowerCase())).length;
          let gpu = 0;
          opNodes.forEach((n) => { try { const f = JSON.parse(n.facts_json || "{}"); if (f.gpu || f.gpu_model || f.gpu_exporter === "enabled") gpu += 1; } catch {} });
          return (
            <div className="stat-strip">
              <div className="stat-tile"><div className="stat-label">Clusters</div><div className="stat-value">{clusters.filter((c) => !isSeedDemoName(c.name)).length}</div></div>
              <div className="stat-tile"><div className="stat-label">Nodes</div><div className="stat-value">{opNodes.length}</div></div>
              <div className="stat-tile"><div className="stat-label">Online</div><div className="stat-value">{online}</div></div>
              <div className="stat-tile"><div className="stat-label">GPU nodes</div><div className="stat-value">{gpu}</div></div>
            </div>
          );
        })()}

        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem", minHeight: "560px" }}>
          <GlassCard style={{ padding: "1rem" }}>
            {renderTreeNavigator(
              async (service) => {
                setSelectedService(service);
                const node = nodes.find((n) => n.id === service.node_id) || null;
                if (node) setSelectedNode(node);
                await loadServiceMetrics(service.id);
                if (node) {
                  await loadNodeMetrics(node.id);
                  await loadNodeMetricsData(node.id);
                }
              },
              selectedService?.id ?? null,
              {
                hideSeedDemo: true,
                activeNodeId: selectedNode?.id ?? null,
                onSelectNode: async (node) => {
                  setSelectedNode(node);
                  setSelectedService(null);
                  setServiceMetrics(null);
                  await loadNodeMetrics(node.id);
                  await loadNodeMetricsData(node.id);
                },
              },
            )}
          </GlassCard>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {!showNode && !showService && (
              <GlassCard style={{ padding: "2.5rem", textAlign: "center" }}>
                <h3 style={{ marginBottom: "0.5rem" }}>Select a node or service</h3>
                <p style={{ color: "var(--ink-4)" }}>Use the tree to inspect Prometheus utilization and process metrics.</p>
              </GlassCard>
            )}

            {showNode && (
              <GlassCard style={{ padding: "1.25rem" }}>
                <div className="panel-title" style={{ marginBottom: "1rem" }}>
                  <h2>Node · {selectedNode!.name}</h2>
                  <span>{selectedNode!.host}</span>
                </div>
                {nodeMetrics || realtimeNodeMetrics ? (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
                      <div><small style={{ color: "var(--ink-4)" }}>CPU</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.cpu_percent ?? realtimeNodeMetrics?.cpu ?? "—"}%</div></div>
                      <div><small style={{ color: "var(--ink-4)" }}>Memory</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.memory_percent ?? realtimeNodeMetrics?.memory ?? "—"}%</div></div>
                      <div><small style={{ color: "var(--ink-4)" }}>Disk</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.disk_percent ?? realtimeNodeMetrics?.disk ?? "—"}%</div></div>
                      <div><small style={{ color: "var(--ink-4)" }}>Net Rx/Tx</small><div style={{ fontWeight: 700 }}>{nodeMetrics ? `${nodeMetrics.network_rx_mbps}/${nodeMetrics.network_tx_mbps}` : "—"} Mbps</div></div>
                    </div>
                    {nodeMetrics && (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                        <div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>CPU</div>
                          {renderSVGTimeSeriesChart(nodeMetrics.cpu_series || [], { color: "#60a5fa", unit: "%" })}
                        </div>
                        <div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Memory</div>
                          {renderSVGTimeSeriesChart(nodeMetrics.memory_series || [], { color: "#a78bfa", unit: "%" })}
                        </div>
                        <div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Disk</div>
                          {renderSVGTimeSeriesChart(nodeMetrics.disk_series || [], { color: "#34d399", unit: "%" })}
                        </div>
                      </div>
                    )}
                    <div style={{ marginTop: "1rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <h4 style={{ margin: 0 }}>Top processes</h4>
                        <div style={{ display: "flex", gap: 4 }}>
                          <button type="button" className={`btn btn-xs ${perfProcessSort === "cpu" ? "btn-primary" : "btn-secondary"}`} onClick={() => setPerfProcessSort("cpu")}>Sort CPU</button>
                          <button type="button" className={`btn btn-xs ${perfProcessSort === "memory" ? "btn-primary" : "btn-secondary"}`} onClick={() => setPerfProcessSort("memory")}>Sort Memory</button>
                        </div>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--ink-4)", marginBottom: 6 }}>
                        Exporters: node_exporter · processes (Prom)
                      </div>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                        <thead>
                          <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                            <th style={{ padding: "0.35rem 0" }}>Process</th>
                            <th style={{ textAlign: "right" }}>CPU</th>
                            <th style={{ textAlign: "right" }}>Mem</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...processMetrics].sort((a, b) => {
                            if (perfProcessSort === "memory") return parseFloat(b.memory || "0") - parseFloat(a.memory || "0");
                            return parseFloat(b.cpu) - parseFloat(a.cpu);
                          }).slice(0, 12).map((p, i) => (
                            <tr key={`${p.name}-${i}`} style={{ borderTop: "1px solid var(--line-2)" }}>
                              <td style={{ padding: "0.35rem 0" }}><code>{p.name}</code></td>
                              <td style={{ textAlign: "right" }}>{parseFloat(p.cpu).toFixed(3)}</td>
                              <td style={{ textAlign: "right" }}>{p.memory != null ? parseFloat(p.memory).toFixed(1) : "—"}</td>
                            </tr>
                          ))}
                          {processMetrics.length === 0 && (
                            <tr><td colSpan={3} style={{ color: "var(--ink-4)", padding: "0.75rem 0" }}>No process metrics from exporter.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                    
                    {(nodeMetrics?.mounted_volumes || []).length > 0 && (
                      <div style={{ marginTop: "1rem" }}>
                        <h4 style={{ marginBottom: "0.5rem" }}>Mounted volumes</h4>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                          <thead>
                            <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                              <th style={{ padding: "0.35rem 0" }}>Mount</th>
                              <th>FS</th>
                              <th>Used</th>
                              <th>Total</th>
                              <th>Usage</th>
                            </tr>
                          </thead>
                          <tbody>
                            {nodeMetrics!.mounted_volumes!.map((v) => (
                              <tr key={v.mount} style={{ borderTop: "1px solid var(--line-2)" }}>
                                <td style={{ padding: "0.35rem 0" }}><code>{v.mount}</code></td>
                                <td>{v.fstype}</td>
                                <td>{v.used_gb} GB</td>
                                <td>{v.total_gb} GB</td>
                                <td>
                                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 4 }}>
                                      <div style={{ width: `${Math.min(100, v.usage_pct)}%`, height: "100%", background: v.usage_pct > 85 ? "var(--err)" : "var(--ok)", borderRadius: 4 }} />
                                    </div>
                                    <span>{v.usage_pct}%</span>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                  </>
                ) : (
                  <p style={{ color: "var(--ink-4)" }}>No Prometheus metrics for this node yet.</p>
                )}
              </GlassCard>
            )}

            {showService && serviceMetrics && (
              <GlassCard style={{ padding: "1.25rem" }}>
                <div className="panel-title" style={{ marginBottom: "1rem" }}>
                  <h2>Service · {serviceMetrics.service_name}</h2>
                  <span>{serviceMetrics.service_key}</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
                  <div><small style={{ color: "var(--ink-4)" }}>CPU</small><div style={{ fontWeight: 700 }}>{serviceMetrics.cpu_percent}%</div></div>
                  <div><small style={{ color: "var(--ink-4)" }}>Memory</small><div style={{ fontWeight: 700 }}>{serviceMetrics.memory_mb} MB</div></div>
                  <div><small style={{ color: "var(--ink-4)" }}>Restarts</small><div style={{ fontWeight: 700 }}>{serviceMetrics.restart_count}</div></div>
                  <div><small style={{ color: "var(--ink-4)" }}>Queue</small><div style={{ fontWeight: 700 }}>{serviceMetrics.queue_depth}</div></div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>CPU</div>
                    {renderSVGTimeSeriesChart(serviceMetrics.cpu_series || [], { color: "#fbbf24", unit: "%" })}
                  </div>
                  <div>
                    <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Errors / min</div>
                    {renderSVGTimeSeriesChart(serviceMetrics.error_rate_series || [], { color: "#f87171", unit: "" })}
                  </div>
                  <div>
                    <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Queue depth</div>
                    {renderSVGTimeSeriesChart(serviceMetrics.queue_depth_series || [], { color: "#34d399", unit: "" })}
                  </div>
                </div>

                {serviceMetrics.db_metrics && (
                  <div style={{ marginTop: "1rem" }}>
                    <h4 style={{ marginBottom: "0.5rem" }}>Database metrics</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", fontSize: "0.85rem" }}>
                      {Object.entries(serviceMetrics.db_metrics).map(([k, v]) => (
                        <div key={k} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8 }}>
                          <div style={{ color: "var(--ink-4)" }}>{k}</div>
                          <strong>{String(v)}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {serviceMetrics.broker_metrics && (
                  <div style={{ marginTop: "1rem" }}>
                    <h4 style={{ marginBottom: "0.5rem" }}>Broker metrics</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", fontSize: "0.85rem" }}>
                      {Object.entries(serviceMetrics.broker_metrics).map(([k, v]) => (
                        <div key={k} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8 }}>
                          <div style={{ color: "var(--ink-4)" }}>{k}</div>
                          <strong>{String(v)}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(serviceMetrics.custom_charts || []).map((chart) => (
                  <div key={chart.title} style={{ marginTop: "1rem" }}>
                    <h4>{chart.title}{chart.unit ? ` (${chart.unit})` : ""}</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
                      {(chart.series || []).map((s) => (
                        <div key={s.name}>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>{s.name}</div>
                          {renderSVGTimeSeriesChart(s.points || [], { color: "#38bdf8", unit: chart.unit || "", height: 72 })}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

              </GlassCard>
            )}
            {showService && !serviceMetrics && (
              <GlassCard style={{ padding: "1.25rem" }}>
                <p style={{ color: "var(--ink-4)" }}>No service metrics for {selectedService?.name}. Prometheus may be unreachable or exporters missing.</p>
              </GlassCard>
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderObservabilityStackView() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Observability stack</h1>
            <p className="sub">Deploy, status-check, and tear down the Prometheus / Loki / Alloy control plane. Bootstrap collectors on individual nodes.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary" disabled={obsStackBusy === "status"} onClick={() => refreshObservabilityStackStatus()}>
              {obsStackBusy === "status" ? "Refreshing…" : "Refresh status"}
            </button>
            <button className="btn btn-primary" disabled={!!obsStackBusy} onClick={() => runObservabilityStackAction("deploy")}>
              {obsStackBusy === "deploy" ? "Deploying…" : "Deploy stack"}
            </button>
            <button className="btn btn-danger" disabled={!!obsStackBusy} onClick={() => runObservabilityStackAction("teardown")}>
              {obsStackBusy === "teardown" ? "Tearing down…" : "Teardown stack"}
            </button>
          </div>
        </div>

        {(() => {
          const plane = (observabilityPipeline?.nodes ?? []).filter((n) => !isSeedDemoName(n.node_name));
          const healthy = plane.filter((n) => n.pipeline_ready).length;
          return (
        <div className="stat-strip">
          <div className="stat-tile"><div className="stat-label">Pipeline nodes</div><div className="stat-value">{plane.length || "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Healthy</div><div className="stat-value">{plane.length ? healthy : "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Degraded</div><div className="stat-value">{plane.length ? plane.length - healthy : "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Stack containers</div><div className="stat-value">{obsStackContainers.length || "—"}</div></div>
        </div>
          );
        })()}

        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
            <h2>Compose status</h2>
            <span>{obsStackContainers.length ? `${obsStackContainers.length} containers` : "no data"}</span>
          </div>
          {obsStackContainers.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                  <th style={{ padding: "0.4rem 0" }}>Name</th>
                  <th>State</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {obsStackContainers.map((c: any, i: number) => (
                  <tr key={c.Name || c.name || i} style={{ borderTop: "1px solid var(--line-2)" }}>
                    <td style={{ padding: "0.45rem 0" }}><code>{c.Name || c.name || "—"}</code></td>
                    <td>{c.State || c.state || "—"}</td>
                    <td style={{ color: "var(--ink-3)" }}>{c.Status || c.status || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: "var(--ink-4)" }}>No stack status yet. Deploy the stack or refresh after compose is available.</p>
          )}
          {obsStackOutput && (
            <pre style={{ marginTop: "1rem", padding: "0.85rem", borderRadius: 10, background: "#010307", color: "#e2e8f0", fontSize: "0.75rem", maxHeight: 280, overflow: "auto", whiteSpace: "pre-wrap" }}>{obsStackOutput}</pre>
          )}
        </GlassCard>

        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
            <h2>Per-node plane</h2>
            <span>{observabilityPipeline ? `${observabilityPipeline.nodes.length} nodes` : "loading"}</span>
          </div>
          {observabilityPipeline ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "0.85rem" }}>
              {observabilityPipeline.nodes.map((node) => (
                <article key={node.node_id} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "0.9rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong>{node.node_name}</strong>
                    <span className={`pill ${node.pipeline_ready ? "pill-ok" : "pill-warn"}`}>{node.ingestion_state}</span>
                  </div>
                  <div className="tags" style={{ marginTop: 8 }}>
                    {Object.entries(node.components || {}).map(([k, v]) => (
                      <span key={k}>{k}: {String(v)}</span>
                    ))}
                  </div>
                  {(node.issues || []).length > 0 && (
                    <ul style={{ margin: "0.55rem 0 0 1rem", color: "var(--ink-3)", fontSize: "0.8rem" }}>
                      {node.issues.slice(0, 3).map((issue) => <li key={issue}>{issue}</li>)}
                    </ul>
                  )}
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ marginTop: 10 }}
                    disabled={observabilityBusyNodeId === node.node_id}
                    onClick={() => bootstrapObservability(node.node_id)}
                  >
                    {observabilityBusyNodeId === node.node_id ? "Bootstrapping…" : "Bootstrap plane"}
                  </button>
                </article>
              ))}
              {observabilityPipeline.nodes.length === 0 && (
                <p style={{ color: "var(--ink-4)" }}>No nodes registered for pipeline reporting.</p>
              )}
            </div>
          ) : (
            <p style={{ color: "var(--ink-4)" }}>Loading pipeline report…</p>
          )}
        </GlassCard>
      </div>
    );
  }



  function renderTopologyView() {
    const subsystems = Object.keys(topology?.subsystems || {});
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Topology</h1>
            <p className="sub">Advanced subsystem dependency map and rollout planning. Separate from the primary Clusters workspace.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary btn-sm" onClick={() => refresh()}>Refresh inventory</button>
          </div>
        </div>
        <div className="notice" style={{ fontSize: "0.85rem" }}>
          Secondary surface — use Clusters for day-to-day node/service operations.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem" }}>
          <GlassCard style={{ padding: "1rem" }}>
            <h3 style={{ marginTop: 0, marginBottom: "0.75rem" }}>Subsystems</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {subsystems.map((name) => (
                <button
                  key={name}
                  type="button"
                  className={`btn btn-sm ${selectedSubsystem === name ? "btn-primary" : "btn-secondary"}`}
                  style={{ justifyContent: "flex-start" }}
                  onClick={() => planSubsystem(name)}
                >
                  {name}
                  <span style={{ marginLeft: "auto", opacity: 0.7 }}>{(topology?.subsystems?.[name] || []).length}</span>
                </button>
              ))}
              {subsystems.length === 0 && <p style={{ color: "var(--ink-4)" }}>No subsystem graph loaded.</p>}
            </div>
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
              <h2>{selectedSubsystem || "Select subsystem"}</h2>
              {selectedSubsystem && (
                <button className="btn btn-primary btn-sm" onClick={() => deploySubsystem(selectedSubsystem)}>Deploy sequence</button>
              )}
            </div>
            {subsystemPlan ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <p style={{ color: "var(--ink-3)", margin: 0 }}>{subsystemPlan.summary}</p>
                {(subsystemPlan.steps || []).map((step: any, idx: number) => (
                  <div key={`${step.service_key}-${idx}`} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <div>
                      <strong>Step {idx + 1}: {step.name || step.service_key}</strong>
                      <div style={{ color: "var(--ink-4)", fontSize: "0.8rem" }}>{step.action} · {step.container_name}</div>
                    </div>
                    <span className={`pill ${["running", "healthy"].includes((step.status || "").toLowerCase()) ? "pill-ok" : "pill-warn"}`}>{step.status || "pending"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--ink-4)" }}>Select a subsystem to generate a dependency-ordered rollout plan for the current node.</p>
            )}
            {(topology?.edges || []).length > 0 && (
              <div style={{ marginTop: "1.25rem" }}>
                <h4>Dependency edges</h4>
                <div style={{ maxHeight: 220, overflow: "auto", fontSize: "0.8rem", color: "var(--ink-3)" }}>
                  {topology!.edges.slice(0, 40).map((e, i) => (
                    <div key={i} style={{ padding: "0.25rem 0", borderBottom: "1px solid var(--line-2)" }}>
                      {e.from_key || "∅"} → {e.to_key} <span className="pill" style={{ fontSize: "0.7rem" }}>{e.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    );
  }

  function renderPolicyView() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Policy</h1>
            <p className="sub">Secondary compliance scan across registered services. Does not replace Clusters day-to-day ops.</p>
          </div>
          <div className="actions">
            <button className="btn btn-primary btn-sm" onClick={runPolicyScan}>Scan policies</button>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.25rem" }}>
          <GlassCard style={{ padding: "1.25rem" }}>
            <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
              <h2>Open findings</h2>
              <span>{findings.length}</span>
            </div>
            <div className="timeline">
              {findings.map((f) => (
                <article key={f.id} style={{ borderLeft: `3px solid ${f.severity === "high" ? "var(--err)" : "var(--warn)"}` }}>
                  <span className="pill" style={{ fontSize: "0.7rem" }}>{f.severity}</span>
                  <strong>{f.rule_id}</strong>
                  <p style={{ fontSize: "0.85rem", margin: "4px 0" }}>{f.message}</p>
                  <small style={{ color: "var(--ink-3)" }}>Remediation: {f.remediation}</small>
                </article>
              ))}
              {findings.length === 0 && <p style={{ color: "var(--ink-4)" }}>No open findings. Run a policy scan to evaluate the inventory.</p>}
            </div>
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
              <h2>Force-delete approvals</h2>
              <span>{forceApprovals.length}</span>
            </div>
            {forceApprovals.map((a) => (
              <div key={a.id} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", marginBottom: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong>#{a.id}</strong>
                  <span className={`pill ${a.status === "approved" ? "pill-ok" : "pill-warn"}`}>{a.status}</span>
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--ink-3)", marginTop: 4 }}>{a.reason}</div>
                <small style={{ color: "var(--ink-4)" }}>{a.requested_by} · {formatExpiry(a.expires_at)}</small>
              </div>
            ))}
            {forceApprovals.length === 0 && <p style={{ color: "var(--ink-4)" }}>No force-delete approvals on file.</p>}
          </GlassCard>
        </div>
      </div>
    );
  }

  function renderAuditView() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Audit</h1>
            <p className="sub">Operations timeline and exportable audit trails. Secondary to primary platform workflows.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary btn-sm" onClick={() => refresh()}>Refresh events</button>
            <button className="btn btn-primary btn-sm" onClick={createAuditExport}>Export audit trail</button>
          </div>
        </div>
        <div className="stat-strip">
          <div className="stat-tile"><div className="stat-label">Events</div><div className="stat-value">{events.length}</div></div>
          <div className="stat-tile"><div className="stat-label">Exports</div><div className="stat-value">{auditExports.length}</div></div>
          <div className="stat-tile"><div className="stat-label">Lifecycle (72h)</div><div className="stat-value">{lifecycleAudit?.total_lifecycle_events ?? "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Blocked deletes</div><div className="stat-value">{lifecycleAudit?.blocked_deletions ?? "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Forced deletes</div><div className="stat-value">{lifecycleAudit?.forced_deletions ?? "—"}</div></div>
          <div className="stat-tile"><div className="stat-label">Safe deletes</div><div className="stat-value">{lifecycleAudit?.safe_deletions ?? "—"}</div></div>
        </div>
        {lifecycleAudit && (
          <GlassCard style={{ padding: "1rem 1.25rem" }}>
            <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", fontSize: "0.85rem", color: "var(--ink-3)" }}>
              <span>Last blocked: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_blocked_at ? formatLocalTimestamp(lifecycleAudit.last_blocked_at) : "—"}</strong></span>
              <span>Last forced: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_forced_at ? formatLocalTimestamp(lifecycleAudit.last_forced_at) : "—"}</strong></span>
              <span>Last safe delete: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_safe_delete_at ? formatLocalTimestamp(lifecycleAudit.last_safe_delete_at) : "—"}</strong></span>
            </div>
          </GlassCard>
        )}
        <GlassCard style={{ padding: "1.25rem" }}>
          <h2 style={{ marginTop: 0 }}>Recent operational events</h2>
          <div className="timeline" style={{ maxHeight: 480, overflow: "auto" }}>
            {events.slice(0, 80).map((ev) => (
              <article key={ev.id}>
                <span className={`pill ${ev.level === "error" ? "pill-error" : ev.level === "warning" ? "pill-warn" : "pill-ok"}`}>{ev.category || "event"}</span>
                <strong>{ev.message}</strong>
                <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(ev.created_at)}</small>
              </article>
            ))}
            {events.length === 0 && <p style={{ color: "var(--ink-4)" }}>No events loaded.</p>}
          </div>
        </GlassCard>
        {auditExports.length > 0 && (
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Exports</h3>
            {auditExports.map((ex) => (
              <div key={ex.id} style={{ fontSize: "0.85rem", padding: "0.4rem 0", borderBottom: "1px solid var(--line-2)" }}>
                <code>{ex.artifact_path}</code> · {ex.status} · {ex.export_type}
              </div>
            ))}
          </GlassCard>
        )}
      </div>
    );
  }

  function renderReliabilityView() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Reliability</h1>
            <p className="sub">Advanced SRE tooling: health sweeps, SLO evaluation, incidents, and maintenance. Not part of the primary GlitchTip Monitoring page.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary btn-sm" onClick={runMonitoringSweep}>Health sweep</button>
            <button className="btn btn-secondary btn-sm" onClick={evaluateSlo}>Evaluate SLOs</button>
            <button className="btn btn-primary btn-sm" onClick={() => openIncident()}>Open incident</button>
          </div>
        </div>
        <div className="notice" style={{ fontSize: "0.85rem" }}>
          Secondary surface — Monitoring remains the GlitchTip workspace for app errors/uptime/APM.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>SLO reports ({slos.length})</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", justifyContent: "space-around" }}>
              {slos.slice(0, 8).map((s) => {
                const color = s.status === "burning" ? "var(--err)" : s.status === "warning" ? "var(--warn)" : "var(--ok)";
                return renderCircularGauge(parseFloat(s.observed) || 0, parseFloat(s.target) || 100, s.name, color);
              })}
              {slos.length === 0 && <p style={{ color: "var(--ink-4)" }}>No SLO reports. Run Evaluate SLOs when Prometheus availability series exist.</p>}
            </div>
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Health checks ({checks.length})</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              {checks.slice(0, 20).map((c) => (
                <div key={c.id} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8, fontSize: "0.85rem" }}>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <span className={`status-dot ${c.status}`} style={{ width: 8, height: 8, borderRadius: "50%" }} />
                    <strong>{c.name}</strong>
                  </div>
                  <small style={{ color: "var(--ink-4)" }}>{c.value}</small>
                </div>
              ))}
              {checks.length === 0 && <p style={{ color: "var(--ink-4)" }}>No checks yet. Run Health sweep.</p>}
            </div>
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Incidents</h3>
            {incidents.map((inc) => (
              <div key={inc.id} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", marginBottom: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{inc.title}</strong>
                  <span className={`pill ${inc.severity === "sev1" ? "pill-error" : "pill-warn"}`}>{inc.severity}</span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--ink-3)", margin: "4px 0" }}>{inc.summary}</p>
                <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                  <button className="btn btn-secondary btn-xs" onClick={() => runIncidentRunbook(inc)}>Runbook</button>
                  <button className="btn btn-primary btn-xs" onClick={() => resolveIncident(inc)}>Resolve</button>
                </div>
              </div>
            ))}
            {incidents.length === 0 && <p style={{ color: "var(--ink-4)" }}>No open incidents.</p>}
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Maintenance</h3>
              <button className="btn btn-secondary btn-xs" onClick={async () => {
                const starts = new Date();
                const ends = new Date(Date.now() + 3600_000);
                await api("/api/maintenance", {
                  method: "POST",
                  body: JSON.stringify({
                    title: `Maintenance ${starts.toISOString().slice(0, 16)}`,
                    starts_at: starts.toISOString(),
                    ends_at: ends.toISOString(),
                    impact: "Scheduled maintenance window",
                  }),
                });
                setNotice("Maintenance window scheduled");
                await refresh();
              }}>Schedule 1h window</button>
            </div>
            {maintenance.map((m) => (
              <div key={m.id} style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.65rem", marginTop: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong>{m.title}</strong>
                  <span className="pill pill-ok">{m.status}</span>
                </div>
                <small style={{ color: "var(--ink-4)" }}>Start {formatLocalTimestamp(m.starts_at)}</small>
                <div style={{ textAlign: "right", marginTop: 4 }}>
                  <button className="btn btn-secondary btn-xs" onClick={() => completeMaintenance(m)}>Complete</button>
                </div>
              </div>
            ))}
            {maintenance.length === 0 && <p style={{ color: "var(--ink-4)" }}>No maintenance windows.</p>}
          </GlassCard>
        </div>
      </div>
    );
  }

  function renderUsersView() {
    const active = platformUsers.filter((u) => u.status === "active");
    const pending = platformUsers.filter((u) => u.status === "pending");
    const rows = usersTab === "active" ? active : pending;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>Users</h1>
            <p className="sub">cPlatform multiuser parity — roles, invites, and operator sessions.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary btn-sm" onClick={() => loadPlatformUsers()}>Refresh</button>
            <button className="btn btn-secondary btn-sm" onClick={() => handleLogout()}>Sign out ({authUser?.user_name || authUser?.user_email})</button>
          </div>
        </div>
        <div className="cluster-tabs">
          <div className={`tab ${usersTab === "active" ? "active" : ""}`} onClick={() => setUsersTab("active")}>Active ({active.length})</div>
          <div className={`tab ${usersTab === "pending" ? "active" : ""}`} onClick={() => setUsersTab("pending")}>Pending invites ({pending.length})</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.25rem" }}>
          <GlassCard style={{ padding: "1.25rem" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                  <th style={{ padding: "0.4rem 0" }}>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Logins</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.user_id} style={{ borderTop: "1px solid var(--line-2)" }}>
                    <td style={{ padding: "0.55rem 0" }}><strong>{u.user_name}</strong></td>
                    <td><code>{u.user_email}</code></td>
                    <td><span className="pill">{u.user_role}</span></td>
                    <td><span className={`pill ${u.status === "active" ? "pill-ok" : "pill-warn"}`}>{u.status}</span></td>
                    <td>{u.login_count} · {u.last_login}</td>
                    <td style={{ textAlign: "right" }}>
                      {u.status === "pending" && u.invite_link ? (
                        <button className="btn btn-secondary btn-xs" onClick={() => { navigator.clipboard?.writeText(u.invite_link || ""); setNotice("Invite link copied"); }}>Copy invite</button>
                      ) : null}
                      {u.status === "pending" ? (
                        <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} onClick={async () => {
                          await api("/api/users/invite/revoke", { method: "POST", body: JSON.stringify({ user_email: u.user_email }) });
                          await loadPlatformUsers();
                        }}>Revoke</button>
                      ) : (
                        <button className="btn btn-danger btn-xs" onClick={async () => {
                          if (!window.confirm(`Delete ${u.user_email}?`)) return;
                          await api(`/api/users/${u.user_id}`, { method: "DELETE" });
                          await loadPlatformUsers();
                        }}>Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={6} style={{ color: "var(--ink-4)", padding: "1rem 0" }}>No users in this tab.</td></tr>
                )}
              </tbody>
            </table>
          </GlassCard>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <GlassCard style={{ padding: "1.25rem" }}>
              <h3 style={{ marginTop: 0 }}>Invite user</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input className="input" placeholder="Name" value={inviteForm.user_name} onChange={(e) => setInviteForm({ ...inviteForm, user_name: e.target.value })} />
                <input className="input" placeholder="Username" value={inviteForm.user_email} onChange={(e) => setInviteForm({ ...inviteForm, user_email: e.target.value })} />
                <select className="input" value={inviteForm.user_role} onChange={(e) => setInviteForm({ ...inviteForm, user_role: e.target.value })}>
                  <option value="System_Admin">System_Admin</option>
                  <option value="Operational">Operational</option>
                  <option value="Management">Management</option>
                </select>
                <input className="input" placeholder="Phone (optional)" value={inviteForm.user_number} onChange={(e) => setInviteForm({ ...inviteForm, user_number: e.target.value })} />
                <button className="btn btn-primary btn-sm" onClick={async () => {
                  const created = await api<PlatformUser>("/api/users/invite", { method: "POST", body: JSON.stringify(inviteForm) });
                  setNotice(created.invite_link ? `Invite ready: ${created.invite_link}` : "Invite created");
                  setInviteForm({ user_name: "", user_email: "", user_role: "Operational", user_number: "" });
                  await loadPlatformUsers();
                  setUsersTab("pending");
                }}>Send invite</button>
              </div>
            </GlassCard>
            <GlassCard style={{ padding: "1.25rem" }}>
              <h3 style={{ marginTop: 0 }}>Add active user</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input className="input" placeholder="Name" value={userForm.user_name} onChange={(e) => setUserForm({ ...userForm, user_name: e.target.value })} />
                <input className="input" placeholder="Username" value={userForm.user_email} onChange={(e) => setUserForm({ ...userForm, user_email: e.target.value })} />
                <input className="input" type="password" placeholder="Password (min 8)" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
                <select className="input" value={userForm.user_role} onChange={(e) => setUserForm({ ...userForm, user_role: e.target.value })}>
                  <option value="System_Admin">System_Admin</option>
                  <option value="Operational">Operational</option>
                  <option value="Management">Management</option>
                </select>
                <button className="btn btn-primary btn-sm" onClick={async () => {
                  await api("/api/users", { method: "POST", body: JSON.stringify(userForm) });
                  setNotice("User created");
                  setUserForm({ user_name: "", user_email: "", user_role: "Operational", user_number: "", password: "" });
                  await loadPlatformUsers();
                }}>Create user</button>
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    );
  }

  if (!authReady) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "var(--ink-3)" }}>
        Loading session…
      </div>
    );
  }

  if (inviteAccept && inviteAccept.preview?.state === "valid") {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem" }}>
        <GlassCard style={{ padding: "2rem", maxWidth: 440, width: "100%" }}>
          <h1 style={{ marginTop: 0 }}>Accept invite</h1>
          <p style={{ color: "var(--ink-3)" }}>
            {inviteAccept.preview.invite?.user_name} · {inviteAccept.preview.invite?.user_email} · {inviteAccept.preview.invite?.user_role}
          </p>
          <input className="input" type="password" placeholder="Choose password (min 8)" value={inviteAccept.password} onChange={(e) => setInviteAccept({ ...inviteAccept, password: e.target.value })} style={{ width: "100%", marginBottom: 12 }} />
          <button className="btn btn-primary" style={{ width: "100%" }} onClick={async () => {
            try {
              await api(`/api/auth/invite/${inviteAccept.token}/accept`, { method: "POST", body: JSON.stringify({ password: inviteAccept.password }) });
              setNotice("Invite accepted — sign in");
              setInviteAccept(null);
              window.location.hash = "";
            } catch (e: any) {
              setLoginError(e?.message || "Accept failed");
            }
          }}>Activate account</button>
          {loginError && <p style={{ color: "var(--err)" }}>{loginError}</p>}
        </GlassCard>
      </div>
    );
  }

  if (!authUser) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem", background: "radial-gradient(ellipse at top, rgba(59,130,246,0.08), transparent 55%)" }}>
        <GlassCard style={{ padding: "2rem", maxWidth: 420, width: "100%" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div className="logo" style={{ width: 40, height: 40, borderRadius: 10, display: "grid", placeItems: "center", background: "var(--navy)", color: "#fff", fontWeight: 700 }}>P</div>
            <div>
              <h1 style={{ margin: 0, fontSize: "1.35rem" }}>PlatformOps</h1>
              <p style={{ margin: 0, color: "var(--ink-4)", fontSize: "0.85rem" }}>Sign in to the control plane</p>
            </div>
          </div>
          <label style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>Email</label>
          <input className="input" value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} style={{ width: "100%", marginBottom: 10 }} />
          <label style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>Password</label>
          <input className="input" type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} onKeyDown={(e) => { if (e.key === "Enter") handleLogin(); }} style={{ width: "100%", marginBottom: 14 }} />
          {loginError && <div style={{ color: "var(--err)", fontSize: "0.85rem", marginBottom: 10 }}>{loginError}</div>}
          <button className="btn btn-primary" style={{ width: "100%" }} disabled={loginBusy} onClick={() => handleLogin()}>
            {loginBusy ? "Signing in…" : "Sign in"}
          </button>
          <p style={{ color: "var(--ink-5)", fontSize: "0.75rem", marginTop: 14 }}>
            Bootstrap admin is seeded on first start. LLM: {llmStatus?.configured ? `${llmStatus.provider}` : "not configured"}.
          </p>
        </GlassCard>
      </div>
    );
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

  return (
    <PlatformContext.Provider value={platformApi}>
      {children}
    </PlatformContext.Provider>
  );
}

export function usePlatform(): PlatformApi {
  const ctx = React.useContext(PlatformContext);
  if (!ctx) throw new Error("usePlatform requires PlatformProvider");
  return ctx;
}
