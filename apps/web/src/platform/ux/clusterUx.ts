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
