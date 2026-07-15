/**
 * Pure cPlatform-style UX helpers for cluster list + detail.
 * No React deps — unit-testable from Node via esbuild bundle.
 * PlatformOps tokens stay in CSS; these encode interaction structure only.
 */

export type ToastKind = "ok" | "err" | "warn";
export type TestConnState = "idle" | "testing" | "ok" | "err";
export type EventsLoadState = "not_loaded" | "loading" | "loaded" | "empty" | "error";

/** Infer toast kind from free-text notice (mirrors useUiState heuristics). */
export function inferToastKind(message: string): ToastKind {
  const msg = String(message || "");
  if (!msg.trim()) return "ok";
  if (/fail|error|denied|blocked|invalid|not found|refused/i.test(msg)) return "err";
  if (/warn|assessing|loading|discovering|running|queued|…|pending|testing/i.test(msg)) return "warn";
  return "ok";
}

/** Button loading class list for primary async actions. */
export function buttonLoadingClass(baseClass: string, loading: boolean): string {
  const base = String(baseClass || "btn").trim();
  if (!loading) return base.replace(/\s*btn-loading\b/g, "").replace(/\s+/g, " ").trim();
  return base.includes("btn-loading") ? base : `${base} btn-loading`.trim();
}

/** Spinner markup string used inside loading buttons (cPlatform setButtonLoading). */
export function buttonSpinnerHtml(label = "Working…"): string {
  const safe = String(label || "Working…");
  return `<span class="btn-spinner" aria-hidden="true"></span><span class="btn-loading-label">${safe}</span>`;
}

/** Toggle drawer/panel busy class. */
export function busyClassName(baseClass: string, busy: boolean): string {
  const base = String(baseClass || "").trim();
  const parts = base.split(/\s+/).filter(Boolean).filter((c) => c !== "is-busy");
  if (busy) parts.push("is-busy");
  return parts.join(" ");
}

/** Loading shell marker class for Overview / Live / Events panes. */
export function loadingShellClass(loading: boolean): string {
  return loading ? "detail-loading-shell is-loading" : "detail-loading-shell";
}

/** Events status line transitions (cPlatform renderEvents status). */
export function eventsStatusLine(state: EventsLoadState, count = 0, errorMsg = ""): string {
  switch (state) {
    case "not_loaded":
      return "Not loaded";
    case "loading":
      return "Loading events…";
    case "empty":
      return "Loaded 0 · no events yet";
    case "error":
      return errorMsg ? `Error: ${errorMsg}` : "Failed to load events";
    case "loaded":
      return `Loaded ${count}`;
    default:
      return "Not loaded";
  }
}

/** Derive events state from fetch lifecycle. */
export function deriveEventsLoadState(opts: {
  started?: boolean;
  loading?: boolean;
  error?: string | null;
  items?: unknown[] | null;
}): EventsLoadState {
  if (opts.loading) return "loading";
  if (opts.error) return "error";
  if (!opts.started) return "not_loaded";
  const n = Array.isArray(opts.items) ? opts.items.length : 0;
  return n === 0 ? "empty" : "loaded";
}

/** Live filter catalog cards by search + category chip. */
export function filterCatalogItems<T extends { name?: string; description?: string; kind?: string; subsystem?: string; tags?: string[]; service_key?: string }>(
  items: T[],
  search: string,
  category: string
): T[] {
  const q = String(search || "").trim().toLowerCase();
  const cat = String(category || "all").trim().toLowerCase();
  return (items || []).filter((item) => {
    if (cat && cat !== "all") {
      const kind = String(item.kind || "").toLowerCase();
      const sub = String(item.subsystem || "").toLowerCase();
      const tags = (item.tags || []).map((t) => String(t).toLowerCase());
      const hit =
        kind === cat ||
        sub === cat ||
        tags.includes(cat) ||
        (cat === "infra" && (kind === "infrastructure" || sub.includes("infra") || tags.includes("infra"))) ||
        (cat === "app" && (kind === "application" || kind === "app" || sub.includes("app")));
      if (!hit) return false;
    }
    if (!q) return true;
    const hay = [item.name, item.description, item.kind, item.subsystem, item.service_key, ...(item.tags || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

/** Live filter cluster cards by name/region/environment. */
export function filterClusters<T extends { name?: string; region?: string; environment?: string }>(
  clusters: T[],
  search: string
): T[] {
  const q = String(search || "").trim().toLowerCase();
  if (!q) return clusters || [];
  return (clusters || []).filter((c) => {
    const hay = [c.name, c.region, c.environment].filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q);
  });
}

/** Map test connection API result to inline state + message. */
export function testConnectionResult(res: { connected?: boolean; message?: string } | null, err?: string | null): {
  state: TestConnState;
  message: string;
} {
  if (err) return { state: "err", message: String(err) };
  if (!res) return { state: "idle", message: "" };
  if (res.connected) return { state: "ok", message: res.message || "Connection OK" };
  return { state: "err", message: res.message || "Connection failed" };
}

/** Whether a service card should show installing shimmer. */
export function isServiceInstalling(
  service: { id?: number | string; status?: string } | null | undefined,
  job: { status?: string; action?: string; service_id?: number | string } | null | undefined
): boolean {
  const st = String(service?.status || "").toLowerCase();
  if (st === "installing" || st === "deploying" || st === "provisioning") return true;
  if (!job) return false;
  const jst = String(job.status || "").toLowerCase();
  if (jst !== "running" && jst !== "queued") return false;
  const action = String(job.action || "").toLowerCase();
  if (!/deploy|install|configure|onboard|apply/.test(action)) return false;
  if (job.service_id != null && service?.id != null) {
    return String(job.service_id) === String(service.id);
  }
  // Job in flight for deploy-ish action with no service_id — treat as cluster-wide busy cue.
  return true;
}

/** Action blocker: require node + optional catalog path before deploy. */
export function shouldBlockDeploy(opts: {
  hasNode: boolean;
  hasService?: boolean;
  reason?: string;
}): { blocked: boolean; message: string; secondary: string } {
  if (!opts.hasNode) {
    return {
      blocked: true,
      message: opts.reason || "Provision a node before deploying services.",
      secondary: "Open provision",
    };
  }
  if (opts.hasService === false) {
    return {
      blocked: true,
      message: opts.reason || "Select a service or open the catalog to install one first.",
      secondary: "Open catalog",
    };
  }
  return { blocked: false, message: "", secondary: "" };
}

/** Detail toolbar action order (cPlatform). */
export const DETAIL_TOOLBAR_ORDER = ["overview", "edit", "events", "discover", "launch", "delete"] as const;

/** Info drawer tabs (node + service). */
export const INFO_DRAWER_TABS = ["overview", "events", "live"] as const;

/** Cluster editor wizard steps. */
export const CLUSTER_EDITOR_STEPS = ["Identity", "Repository", "Image store", "Review"] as const;

/** Repo provider cards (cP provider-grid). */
export const CLUSTER_REPO_PROVIDERS = [
  { id: "github", label: "GH", name: "GitHub" },
  { id: "gitlab", label: "GL", name: "GitLab" },
  { id: "bitbucket", label: "BB", name: "Bitbucket" },
  { id: "local", label: "SH", name: "Self-hosted / local" },
] as const;

/** Image registry provider cards. */
export const CLUSTER_REGISTRY_PROVIDERS = [
  { id: "dockerhub", label: "DH", name: "Docker Hub" },
  { id: "ecr", label: "ECR", name: "AWS ECR" },
  { id: "gcr", label: "GCR", name: "Google GCR" },
  { id: "local", label: "LOC", name: "Local registry" },
] as const;

/** Repo auth tabs (cP auth-tabs). */
export const CLUSTER_REPO_AUTH_TABS = [
  { id: "pat", label: "Personal access token" },
  { id: "ssh", label: "SSH key" },
  { id: "none", label: "Public / none" },
] as const;

/** cP service install drawer steps (data-svc-step). */
export const SVC_INSTALL_STEPS = ["Setup", "Config"] as const;

/** cP node provision drawer steps (data-step). */
export const NODE_PROVISION_STEPS = [
  "Cloud",
  "Hardware",
  "Config",
  "Network",
  "Firewall",
  "Review",
] as const;

/** Cloud provider cards on node provision step 1. */
export const NODE_CLOUD_PROVIDERS = [
  { id: "aws", label: "AWS", name: "Amazon Web Services", desc: "EC2 / SSH host", preset: "aws-general" },
  { id: "gcp", label: "GCP", name: "Google Cloud", desc: "Compute Engine / SSH", preset: "local-default" },
  { id: "dc", label: "DC", name: "Data Centre", desc: "Bare metal · existing host", preset: "local-default" },
] as const;

/** Launch stub copy (deferred Terraform/cloud launch). */
export const LAUNCH_STUB_MESSAGE =
  "Cloud Launch is not configured in this environment. Node provisioning uses the Provision node drawer (SSH / bare-metal path). Full VM/Terraform launch remains deferred.";

/**
 * Whether open Events surfaces should re-fetch after a mutation tick advances.
 * Used by ClustersView after discover / deploy / delete.
 */
export function shouldRefreshOpenEvents(opts: {
  eventsRefreshKey: number;
  prevKey?: number;
  detailTab?: string;
  serviceEventsOpen?: boolean;
  nodeEventsOpen?: boolean;
}): boolean {
  const key = Number(opts.eventsRefreshKey || 0);
  const prev = Number(opts.prevKey ?? 0);
  if (!key || key === prev) return false;
  if (opts.detailTab === "events") return true;
  if (opts.serviceEventsOpen) return true;
  if (opts.nodeEventsOpen) return true;
  return false;
}

/** CSS class for primary Deploy / Execute controls while async work runs. */
export function deployButtonClass(baseClass: string, busy: boolean): string {
  return buttonLoadingClass(baseClass, busy);
}

/**
 * cPlatform-style event row (renderEvents): "Title: message (date time)".
 * Accepts PlatformOps OperationalEventOut + legacy cP field names.
 */
export function formatClusterEventRow(ev: Record<string, unknown> | null | undefined): {
  title: string;
  message: string;
  when: string;
  level: string;
  category: string;
} {
  if (!ev || typeof ev !== "object") {
    return { title: "Event", message: "", when: "", level: "info", category: "event" };
  }
  const rawMsg = String(
    ev.event_msg || ev.message || ev.msg || ev.Event_Msg || ""
  );
  let title = String(
    ev.event_title ||
      ev.event_type ||
      ev.title ||
      ev.category ||
      ev.level ||
      ev.event_trigger ||
      ev.Event_Trigger ||
      ""
  );
  let message = rawMsg;
  if (!title && rawMsg.includes("-")) {
    const i = rawMsg.indexOf("-");
    title = rawMsg.slice(0, i).trim();
    message = rawMsg.slice(i + 1).trim();
  }
  if (!title) title = "Event";
  const date = String(ev.create_date || ev.event_date || ev.date || ev.Event_Date || "");
  const time = String(ev.create_time || ev.event_time || ev.time || ev.Event_Time || "");
  let when = "";
  if (date || time) {
    when = `${date} ${time}`.trim();
  } else if (ev.created_at) {
    try {
      when = new Date(String(ev.created_at)).toLocaleString();
    } catch {
      when = String(ev.created_at);
    }
  }
  return {
    title,
    message: message || rawMsg || "—",
    when,
    level: String(ev.level || "info").toLowerCase(),
    category: String(ev.category || title || "event"),
  };
}

/** Status text matching cPlatform events panel: "N events" / "0 events". */
export function eventsCountLabel(count: number, loading = false): string {
  if (loading) return "Loading events…";
  return `${count} events`;
}

/**
 * Advanced modules kept in UI but detangled from the cluster code path.
 * Cluster refresh / job poll / deploy must never require these bulk APIs.
 * Observability is intentionally NOT here — it is part of cluster DevOps.
 */
export const CODE_DETANGLED_MODULES = ["topology", "policy", "audit", "reliability"] as const;

/** @deprecated alias — code-path detangle only (UI still shows Advanced). */
export const DETANGLED_VIEWS = CODE_DETANGLED_MODULES;

/** Views that load cluster core inventory (incl. observability pipeline). */
export const CLUSTER_CORE_VIEWS = [
  "clusters",
  "dashboard",
  "config",
  "diagnostics",
  "monitoring",
  "performance",
  "observability",
  "users",
] as const;

/** cPlatform getStateTone — map free-text state to pill tone. */
export function getStateTone(stateLabel: string | null | undefined): "ok" | "warn" | "err" | "muted" {
  const n = String(stateLabel || "").toLowerCase().trim();
  if (!n || n === "unknown" || n === "not deployed" || n === "not_found") return "muted";
  if (
    n === "running" ||
    n === "healthy" ||
    n === "ready" ||
    n === "deployed" ||
    n === "active" ||
    n === "ok" ||
    n.includes("deployed")
  ) {
    return "ok";
  }
  if (
    n === "installing" ||
    n === "deploying" ||
    n === "provisioning" ||
    n === "queued" ||
    n === "configuring" ||
    n === "pending" ||
    n.includes("progress")
  ) {
    return "warn";
  }
  if (
    n === "error" ||
    n === "failed" ||
    n === "unhealthy" ||
    n === "unreachable" ||
    n === "dead" ||
    n === "exited" ||
    n.includes("error") ||
    n.includes("fail")
  ) {
    return "err";
  }
  return "muted";
}

/** Node list row status class (cPlatform nstat). */
export function nodeRowStatusClass(status: string | null | undefined): string {
  const n = String(status || "").toLowerCase();
  if (n === "healthy" || n === "running" || n === "ready") return "ready";
  if (n === "unreachable") return "unreachable";
  if (n === "degraded" || n === "warning") return "degraded";
  if (n === "error" || n === "failed") return "error";
  return n || "unknown";
}

/**
 * cPlatform withPending — coalesce concurrent identical in-flight requests.
 * Module-level so deploy/delete/discover share dedupe across action modules.
 */
const pendingRequests = new Map<string, Promise<unknown>>();

export async function withPending<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const k = String(key || "");
  if (!k) return fn();
  const existing = pendingRequests.get(k);
  if (existing) return existing as Promise<T>;
  const promise = (async () => {
    try {
      return await fn();
    } finally {
      pendingRequests.delete(k);
    }
  })();
  pendingRequests.set(k, promise);
  return promise;
}

/** Clear pending map (tests only). */
export function __resetPendingForTests(): void {
  pendingRequests.clear();
}

/** Race guard: ignore stale async workspace loads after node switch. */
export function isStaleWorkspaceToken(current: number, expected: number): boolean {
  return Number(current) !== Number(expected);
}

/**
 * Parse MISSING_DEPENDENCIES / preflight-style blocker payloads (cPlatform showDependencyBlocker).
 */
export function parseMissingDependencies(details: any): {
  missing: Array<{ service_type?: string; display_name?: string; service_key?: string; reason?: string; state?: string }>;
  nodeId: string | number | null;
  code: string;
} {
  const d = details && typeof details === "object" ? details : {};
  const nested = d.details && typeof d.details === "object" ? d.details : d;
  const missing =
    nested.missing_dependencies ||
    nested.missing ||
    nested.dependencies ||
    d.missing_dependencies ||
    [];
  return {
    missing: Array.isArray(missing) ? missing : [],
    nodeId: nested.node_id ?? d.node_id ?? null,
    code: String(nested.code || d.code || ""),
  };
}

/** Whether an error/preflight result should open the dependency action blocker. */
export function shouldShowDependencyBlocker(errOrResult: any): boolean {
  if (!errOrResult) return false;
  const code = String(
    errOrResult?.code ||
      errOrResult?.details?.code ||
      errOrResult?.error_code ||
      ""
  ).toUpperCase();
  if (code === "MISSING_DEPENDENCIES" || code === "DEPENDENCY_BLOCKED") return true;
  const parsed = parseMissingDependencies(errOrResult);
  if (parsed.missing.length > 0) return true;
  const msg = String(errOrResult?.message || errOrResult?.error || errOrResult || "");
  return /missing dependenc|dependency.?blocked|install.?dependenc/i.test(msg);
}

/** Build action-blocker props from missing-deps payload. */
export function buildDependencyBlockerState(details: any, fallbackMessage = "Deployment blocked: missing dependencies"): {
  visible: true;
  eyebrow: string;
  title: string;
  message: string;
  items: Array<{ name: string; meta: string; service_key?: string }>;
  secondaryLabel: string;
  secondaryAction: "catalog";
  primaryLabel: string;
  primaryAction: "install-first-missing" | "catalog";
} {
  const { missing, nodeId } = parseMissingDependencies(details);
  const nodeLabel = nodeId != null ? String(nodeId) : "selected node";
  return {
    visible: true,
    eyebrow: "Missing dependencies",
    title: "Deployment blocked",
    message:
      `${fallbackMessage}. Deploy the required infrastructure cards on ${nodeLabel} before starting this application service.`,
    items: missing.map((item) => ({
      name: item.display_name || item.service_type || item.service_key || "Dependency",
      meta: `${item.service_type || item.service_key || "infrastructure"} · ${item.reason || item.state || "not ready"}`,
      service_key: item.service_key || item.service_type,
    })),
    secondaryLabel: "Open catalog",
    secondaryAction: "catalog",
    primaryLabel: missing.length ? "Install first missing" : "Open catalog",
    primaryAction: missing.length ? "install-first-missing" : "catalog",
  };
}

/** Service card expose/port label (cPlatform buildServiceCardHtml). */
export function serviceExposeLabel(service: {
  expose_service?: boolean;
  host_port?: string | number;
  config_json?: string | Record<string, unknown>;
} | null | undefined): { portText: string; uptimeText: string } {
  if (!service) return { portText: "internal", uptimeText: "no host port" };
  let expose = Boolean(service.expose_service);
  let hostPort = service.host_port != null ? String(service.host_port).trim() : "";
  try {
    const cfg =
      typeof service.config_json === "string"
        ? JSON.parse(service.config_json || "{}")
        : service.config_json || {};
    if (cfg && typeof cfg === "object") {
      if ((cfg as any).expose_service != null) expose = Boolean((cfg as any).expose_service);
      if ((cfg as any).host_port != null && !hostPort) hostPort = String((cfg as any).host_port).trim();
    }
  } catch {
    /* ignore */
  }
  if (expose && hostPort) {
    return { portText: `:${hostPort}`, uptimeText: `host port ${hostPort}` };
  }
  return { portText: "internal", uptimeText: "no host port" };
}

/** Unreachable / invalid node selection guard (cPlatform). */
export function canSelectNode(node: { status?: string; name?: string } | null | undefined): {
  ok: boolean;
  notice: string;
} {
  if (!node) return { ok: false, notice: "No node selected." };
  if (String(node.status || "").toLowerCase() === "unreachable") {
    return {
      ok: false,
      notice: `Node ${node.name || "unknown"} is unreachable. Probe or check connection settings.`,
    };
  }
  return { ok: true, notice: "" };
}

/** cPlatform renderDetailSummaryCards payload. */
export function buildServiceSummaryCards(opts: {
  status?: string;
  serviceType?: string;
  port?: string | number | null;
  eventsCount?: number;
  loading?: boolean;
}): Array<{ label: string; value: string; sub?: string }> {
  const loading = Boolean(opts.loading);
  return [
    {
      label: "Status",
      value: loading ? "Loading…" : String(opts.status || "Unknown"),
      sub: opts.serviceType || "",
    },
    {
      label: "Port",
      value: loading ? "Loading…" : opts.port != null && String(opts.port) !== "" ? String(opts.port) : "NA",
      sub: "Exposed port",
    },
    {
      label: "Events",
      value: loading ? "…" : String(opts.eventsCount ?? 0),
      sub: "Recent history",
    },
  ];
}

/** Normalize live-status dependency rows (cPlatform renderDependenciesTable). */
export function normalizeLiveDependencies(
  live: {
    dependencies?: Array<Record<string, unknown>>;
    items?: Array<Record<string, unknown>>;
    container_name?: string;
    overall_status?: string;
    restart_count?: number | string;
    image?: string;
    name?: string;
  } | null | undefined,
  fallbackService?: { container_name?: string; name?: string; image?: string } | null
): Array<{
  name: string;
  target: string;
  source: string;
  state: string;
  runningSince: string;
  restarts: string;
}> {
  const deps = live?.dependencies;
  if (Array.isArray(deps) && deps.length > 0) {
    return deps.map((item) => {
      const target =
        item.target_host ||
        item.container_ip ||
        item.service_name ||
        item.host ||
        item.port ||
        item.container_name ||
        "External";
      return {
        name: String(item.name || item.service_name || item.service_key || "Dependency"),
        target: String(target),
        source: String(item.source_type || item.source || "Unknown"),
        state: String(item.state || item.overall_status || "Unknown"),
        runningSince: String(item.running_since || item.started_at || "External"),
        restarts:
          item.restart_count != null && item.restart_count !== ""
            ? String(item.restart_count)
            : "Not tracked",
      };
    });
  }
  // Fallback: main container as single row when no deps payload
  if (live || fallbackService) {
    return [
      {
        name: String(live?.name || fallbackService?.name || "Main container"),
        target: String(live?.container_name || fallbackService?.container_name || "—"),
        source: "container",
        state: String(live?.overall_status || "Unknown"),
        runningSince: "—",
        restarts:
          live?.restart_count != null && live.restart_count !== ""
            ? String(live.restart_count)
            : "Not tracked",
      },
    ];
  }
  return [];
}

/** Merge install schema values with existing service config (edit prefill). */
export function mergeInstallFieldValues(
  schemaValues: Record<string, unknown>,
  service: {
    name?: string;
    config_json?: string | Record<string, unknown>;
    expose_service?: boolean;
    host_port?: string | number;
    install_mode?: string;
  } | null | undefined
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...(schemaValues || {}) };
  if (!service) return next;
  let cfg: Record<string, unknown> = {};
  try {
    cfg =
      typeof service.config_json === "string"
        ? JSON.parse(service.config_json || "{}")
        : (service.config_json as Record<string, unknown>) || {};
  } catch {
    cfg = {};
  }
  // Prefer flat config keys that match schema field keys
  for (const key of Object.keys(next)) {
    if (cfg[key] !== undefined && cfg[key] !== null) next[key] = cfg[key];
  }
  // Common cP static fields
  if (cfg.expose_service != null) next.expose_service = cfg.expose_service;
  else if (service.expose_service != null) next.expose_service = service.expose_service;
  if (cfg.host_port != null) next.host_port = cfg.host_port;
  else if (service.host_port != null) next.host_port = service.host_port;
  if (cfg.service_install != null) next.service_install = cfg.service_install;
  if (cfg.install_mode != null) next.install_mode = cfg.install_mode;
  else if (service.install_mode != null) next.install_mode = service.install_mode;
  if (cfg.service_version != null) next.service_version = cfg.service_version;
  if (cfg.service_port != null) next.service_port = cfg.service_port;
  return next;
}

/** Detect adopted / discovered inventory services. */
export function isAdoptedService(service: {
  origin?: string;
  source?: string;
  adopted?: boolean;
  tags?: string[];
  discovery?: string;
} | null | undefined): boolean {
  if (!service) return false;
  if (service.adopted === true) return true;
  const origin = String(service.origin || service.source || service.discovery || "").toLowerCase();
  if (origin.includes("adopt") || origin.includes("discover")) return true;
  const tags = (service.tags || []).map((t) => String(t).toLowerCase());
  return tags.includes("adopted") || tags.includes("discovered");
}

/** Filter clusters by search + optional environment/region chips. */
export function filterClustersAdvanced<
  T extends { name?: string; region?: string; environment?: string }
>(
  clusters: T[],
  opts: { search?: string; environment?: string; region?: string }
): T[] {
  let list = filterClusters(clusters, opts.search || "");
  const env = String(opts.environment || "all").toLowerCase();
  const region = String(opts.region || "all").toLowerCase();
  if (env && env !== "all") {
    list = list.filter((c) => String(c.environment || "").toLowerCase() === env);
  }
  if (region && region !== "all") {
    list = list.filter((c) => String(c.region || "").toLowerCase() === region);
  }
  return list;
}

/** Unique sorted facet values for cluster chips. */
export function clusterFacetValues(
  clusters: Array<{ environment?: string; region?: string }>,
  facet: "environment" | "region"
): string[] {
  const set = new Set<string>();
  for (const c of clusters || []) {
    const v = String(c[facet] || "").trim();
    if (v) set.add(v);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

/** Catalog drag payload id. */
export const CATALOG_DRAG_MIME = "application/x-platformops-catalog-key";
