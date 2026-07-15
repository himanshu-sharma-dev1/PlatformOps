/**
 * Unit tests for shipped cluster UX helpers.
 * Bundles apps/web/src/platform/ux/clusterUx.ts via esbuild, then asserts real exports.
 * Run: node scripts/test_cluster_ux.mjs
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import assert from "node:assert/strict";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = join(__dirname, "..");
const require = createRequire(join(webRoot, "package.json"));
const esbuild = require("esbuild");

const outDir = process.env.SCRATCH_DIR || join(webRoot, "../../..", "tmp-cluster-ux-test");
mkdirSync(outDir, { recursive: true });
const outFile = join(outDir, "clusterUx.bundle.mjs");

await esbuild.build({
  entryPoints: [join(webRoot, "src/platform/ux/clusterUx.ts")],
  bundle: true,
  format: "esm",
  platform: "node",
  outfile: outFile,
  logLevel: "silent",
});

const ux = await import(pathToFileURL(outFile).href);

let passed = 0;
async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS  ${name}`);
  } catch (e) {
    console.error(`  FAIL  ${name}`);
    console.error(e);
    process.exitCode = 1;
  }
}

console.log("clusterUx unit tests (shipped module)\n");

async function main() {
await check("inferToastKind err", () => {
  assert.equal(ux.inferToastKind("Deploy failed: timeout"), "err");
  assert.equal(ux.inferToastKind("access denied"), "err");
});
await check("inferToastKind warn", () => {
  assert.equal(ux.inferToastKind("Discovering infrastructure…"), "warn");
  assert.equal(ux.inferToastKind("testing connection"), "warn");
});
await check("inferToastKind ok", () => {
  assert.equal(ux.inferToastKind("Created cluster prod"), "ok");
});

await check("buttonLoadingClass", () => {
  assert.equal(ux.buttonLoadingClass("btn btn-primary", true), "btn btn-primary btn-loading");
  assert.ok(!ux.buttonLoadingClass("btn btn-primary btn-loading", false).includes("btn-loading"));
});

await check("buttonSpinnerHtml", () => {
  const html = ux.buttonSpinnerHtml("Saving…");
  assert.ok(html.includes("btn-spinner"));
  assert.ok(html.includes("Saving…"));
});

await check("busyClassName", () => {
  assert.equal(ux.busyClassName("drawer-body", true), "drawer-body is-busy");
  assert.equal(ux.busyClassName("drawer-body is-busy", false), "drawer-body");
});

await check("loadingShellClass", () => {
  assert.ok(ux.loadingShellClass(true).includes("is-loading"));
  assert.ok(!ux.loadingShellClass(false).includes("is-loading"));
});

await check("eventsStatusLine transitions", () => {
  assert.equal(ux.eventsStatusLine("not_loaded"), "Not loaded");
  assert.equal(ux.eventsStatusLine("loading"), "Loading events…");
  assert.equal(ux.eventsStatusLine("loaded", 7), "Loaded 7");
  assert.equal(ux.eventsStatusLine("empty"), "Loaded 0 · no events yet");
  assert.match(ux.eventsStatusLine("error", 0, "timeout"), /timeout/);
});

await check("deriveEventsLoadState", () => {
  assert.equal(ux.deriveEventsLoadState({ loading: true }), "loading");
  assert.equal(ux.deriveEventsLoadState({ started: true, items: [] }), "empty");
  assert.equal(ux.deriveEventsLoadState({ started: true, items: [{}] }), "loaded");
  assert.equal(ux.deriveEventsLoadState({ started: false }), "not_loaded");
  assert.equal(ux.deriveEventsLoadState({ error: "x" }), "error");
});

await check("filterCatalogItems search + category", () => {
  const items = [
    { name: "dTrain", kind: "application", subsystem: "ml", tags: ["app"], service_key: "dtrain" },
    { name: "Postgres", kind: "infrastructure", subsystem: "data", tags: ["infra"], service_key: "pg" },
    { name: "Redis", kind: "infrastructure", subsystem: "cache", tags: [], service_key: "redis" },
  ];
  assert.equal(ux.filterCatalogItems(items, "dtr", "all").length, 1);
  assert.equal(ux.filterCatalogItems(items, "", "infra").length, 2);
  assert.equal(ux.filterCatalogItems(items, "redis", "infra").length, 1);
  assert.equal(ux.filterCatalogItems(items, "zzz", "all").length, 0);
});

await check("filterClusters", () => {
  const clusters = [
    { name: "prod-mumbai", region: "ap-south-1", environment: "production" },
    { name: "dev-local", region: "local", environment: "development" },
  ];
  assert.equal(ux.filterClusters(clusters, "mumbai").length, 1);
  assert.equal(ux.filterClusters(clusters, "dev").length, 1);
  assert.equal(ux.filterClusters(clusters, "").length, 2);
});

await check("testConnectionResult", () => {
  assert.equal(ux.testConnectionResult({ connected: true, message: "ok" }).state, "ok");
  assert.equal(ux.testConnectionResult({ connected: false }).state, "err");
  assert.equal(ux.testConnectionResult(null, "boom").state, "err");
});

await check("isServiceInstalling", () => {
  assert.equal(ux.isServiceInstalling({ id: 1, status: "installing" }, null), true);
  assert.equal(
    ux.isServiceInstalling({ id: 9 }, { status: "running", action: "deploy", service_id: 9 }),
    true
  );
  assert.equal(
    ux.isServiceInstalling({ id: 9 }, { status: "success", action: "deploy", service_id: 9 }),
    false
  );
  assert.equal(ux.isServiceInstalling({ id: 1, status: "running" }, null), false);
});

await check("shouldBlockDeploy", () => {
  assert.equal(ux.shouldBlockDeploy({ hasNode: false }).blocked, true);
  assert.equal(ux.shouldBlockDeploy({ hasNode: true, hasService: false }).blocked, true);
  assert.equal(ux.shouldBlockDeploy({ hasNode: true, hasService: true }).blocked, false);
});

await check("constants present", () => {
  assert.deepEqual([...ux.DETAIL_TOOLBAR_ORDER], ["overview", "edit", "events", "discover", "launch", "delete"]);
  assert.deepEqual([...ux.INFO_DRAWER_TABS], ["overview", "events", "live"]);
  assert.equal(ux.CLUSTER_EDITOR_STEPS.length, 4);
  assert.ok(String(ux.LAUNCH_STUB_MESSAGE).includes("not configured"));
});

await check("shouldRefreshOpenEvents after mutation tick", () => {
  assert.equal(
    ux.shouldRefreshOpenEvents({ eventsRefreshKey: 0, prevKey: 0, detailTab: "events" }),
    false
  );
  assert.equal(
    ux.shouldRefreshOpenEvents({ eventsRefreshKey: 2, prevKey: 1, detailTab: "overview" }),
    false
  );
  assert.equal(
    ux.shouldRefreshOpenEvents({ eventsRefreshKey: 2, prevKey: 1, detailTab: "events" }),
    true
  );
  assert.equal(
    ux.shouldRefreshOpenEvents({ eventsRefreshKey: 3, prevKey: 2, serviceEventsOpen: true }),
    true
  );
  assert.equal(
    ux.shouldRefreshOpenEvents({ eventsRefreshKey: 4, prevKey: 3, nodeEventsOpen: true }),
    true
  );
});

await check("deployButtonClass loading", () => {
  assert.ok(ux.deployButtonClass("btn btn-primary btn-sm", true).includes("btn-loading"));
  assert.ok(!ux.deployButtonClass("btn btn-primary btn-sm", false).includes("btn-loading"));
});

await check("formatClusterEventRow cPlatform style", () => {
  const row = ux.formatClusterEventRow({
    category: "deploy",
    level: "info",
    message: "Deploy finished",
    created_at: "2026-07-15T12:00:00Z",
  });
  assert.equal(row.title, "deploy");
  assert.ok(row.message.includes("Deploy"));
  assert.equal(ux.eventsCountLabel(3), "3 events");
  assert.equal(ux.eventsCountLabel(0, true), "Loading events…");
});

await check("CODE_DETANGLED_MODULES excludes advanced; observability is cluster-core", () => {
  assert.ok(ux.CODE_DETANGLED_MODULES.includes("topology"));
  assert.ok(ux.CODE_DETANGLED_MODULES.includes("policy"));
  assert.ok(ux.CODE_DETANGLED_MODULES.includes("audit"));
  assert.ok(ux.CODE_DETANGLED_MODULES.includes("reliability"));
  assert.ok(!ux.CODE_DETANGLED_MODULES.includes("observability"));
  assert.ok(ux.DETANGLED_VIEWS.includes("topology"));
  assert.ok(ux.CLUSTER_CORE_VIEWS.includes("observability"));
  assert.ok(ux.CLUSTER_CORE_VIEWS.includes("clusters"));
});

await check("getStateTone + nodeRowStatusClass", () => {
  assert.equal(ux.getStateTone("running"), "ok");
  assert.equal(ux.getStateTone("DEPLOYING"), "warn");
  assert.equal(ux.getStateTone("unreachable"), "err");
  assert.equal(ux.getStateTone(""), "muted");
  assert.equal(ux.nodeRowStatusClass("healthy"), "ready");
  assert.equal(ux.nodeRowStatusClass("unreachable"), "unreachable");
});

await check("withPending coalesces concurrent calls", async () => {
  ux.__resetPendingForTests();
  let runs = 0;
  const slow = () =>
    new Promise((resolve) => {
      runs += 1;
      setTimeout(() => resolve(runs), 30);
    });
  const [a, b] = await Promise.all([ux.withPending("k1", slow), ux.withPending("k1", slow)]);
  assert.equal(a, 1);
  assert.equal(b, 1);
  assert.equal(runs, 1);
  const c = await ux.withPending("k1", slow);
  assert.equal(c, 2);
});

await check("isStaleWorkspaceToken", () => {
  assert.equal(ux.isStaleWorkspaceToken(1, 1), false);
  assert.equal(ux.isStaleWorkspaceToken(2, 1), true);
});

await check("parseMissingDependencies + blocker", () => {
  const parsed = ux.parseMissingDependencies({
    code: "MISSING_DEPENDENCIES",
    missing_dependencies: [{ display_name: "Redis", service_type: "redis", reason: "not on node" }],
    node_id: 12,
  });
  assert.equal(parsed.missing.length, 1);
  assert.equal(parsed.nodeId, 12);
  assert.equal(ux.shouldShowDependencyBlocker({ code: "MISSING_DEPENDENCIES" }), true);
  assert.equal(ux.shouldShowDependencyBlocker({ message: "ok" }), false);
  const blocker = ux.buildDependencyBlockerState(
    { missing_dependencies: [{ display_name: "Redis", service_key: "redis" }], node_id: "n1" },
    "blocked"
  );
  assert.equal(blocker.visible, true);
  assert.equal(blocker.items[0].name, "Redis");
  assert.equal(blocker.secondaryAction, "catalog");
});

await check("serviceExposeLabel + canSelectNode", () => {
  assert.equal(ux.serviceExposeLabel({ expose_service: true, host_port: 8080 }).portText, ":8080");
  assert.equal(ux.serviceExposeLabel({ expose_service: false }).portText, "internal");
  assert.equal(ux.canSelectNode({ status: "unreachable", name: "x" }).ok, false);
  assert.equal(ux.canSelectNode({ status: "ready", name: "x" }).ok, true);
});

await check("buildServiceSummaryCards + normalizeLiveDependencies", () => {
  const cards = ux.buildServiceSummaryCards({ status: "running", serviceType: "redis", port: 6379, eventsCount: 3 });
  assert.equal(cards.length, 3);
  assert.equal(cards[0].value, "running");
  assert.equal(cards[2].value, "3");
  const deps = ux.normalizeLiveDependencies({
    dependencies: [{ name: "pg", target_host: "10.0.0.1", state: "running", restart_count: 0 }],
  });
  assert.equal(deps.length, 1);
  assert.equal(deps[0].name, "pg");
  const fallback = ux.normalizeLiveDependencies({ overall_status: "running", container_name: "c1" }, { name: "svc" });
  assert.equal(fallback[0].target, "c1");
});

await check("mergeInstallFieldValues + isAdoptedService + filterClustersAdvanced", () => {
  const merged = ux.mergeInstallFieldValues(
    { expose_service: false, host_port: "", service_version: "1" },
    { config_json: JSON.stringify({ expose_service: true, host_port: 9000, service_version: "2" }) }
  );
  assert.equal(merged.expose_service, true);
  assert.equal(String(merged.host_port), "9000");
  assert.equal(merged.service_version, "2");
  assert.equal(ux.isAdoptedService({ origin: "discover" }), true);
  assert.equal(ux.isAdoptedService({ status: "running" }), false);
  const list = [
    { name: "a", environment: "production", region: "us-east-1" },
    { name: "b", environment: "development", region: "local" },
  ];
  assert.equal(ux.filterClustersAdvanced(list, { environment: "production" }).length, 1);
  assert.equal(ux.clusterFacetValues(list, "region").includes("local"), true);
  assert.ok(ux.CATALOG_DRAG_MIME.includes("catalog"));
});

const summary = `\n${passed} checks passed\n`;
console.log(summary);
writeFileSync(join(outDir, "ux-unit-tests-summary.txt"), summary, "utf8");
}

await main();
if (process.exitCode) process.exit(process.exitCode);
