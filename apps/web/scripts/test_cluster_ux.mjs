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
function check(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  PASS  ${name}`);
  } catch (e) {
    console.error(`  FAIL  ${name}`);
    console.error(e);
    process.exitCode = 1;
  }
}

console.log("clusterUx unit tests (shipped module)\n");

check("inferToastKind err", () => {
  assert.equal(ux.inferToastKind("Deploy failed: timeout"), "err");
  assert.equal(ux.inferToastKind("access denied"), "err");
});
check("inferToastKind warn", () => {
  assert.equal(ux.inferToastKind("Discovering infrastructure…"), "warn");
  assert.equal(ux.inferToastKind("testing connection"), "warn");
});
check("inferToastKind ok", () => {
  assert.equal(ux.inferToastKind("Created cluster prod"), "ok");
});

check("buttonLoadingClass", () => {
  assert.equal(ux.buttonLoadingClass("btn btn-primary", true), "btn btn-primary btn-loading");
  assert.ok(!ux.buttonLoadingClass("btn btn-primary btn-loading", false).includes("btn-loading"));
});

check("buttonSpinnerHtml", () => {
  const html = ux.buttonSpinnerHtml("Saving…");
  assert.ok(html.includes("btn-spinner"));
  assert.ok(html.includes("Saving…"));
});

check("busyClassName", () => {
  assert.equal(ux.busyClassName("drawer-body", true), "drawer-body is-busy");
  assert.equal(ux.busyClassName("drawer-body is-busy", false), "drawer-body");
});

check("loadingShellClass", () => {
  assert.ok(ux.loadingShellClass(true).includes("is-loading"));
  assert.ok(!ux.loadingShellClass(false).includes("is-loading"));
});

check("eventsStatusLine transitions", () => {
  assert.equal(ux.eventsStatusLine("not_loaded"), "Not loaded");
  assert.equal(ux.eventsStatusLine("loading"), "Loading events…");
  assert.equal(ux.eventsStatusLine("loaded", 7), "Loaded 7");
  assert.equal(ux.eventsStatusLine("empty"), "Loaded 0 · no events yet");
  assert.match(ux.eventsStatusLine("error", 0, "timeout"), /timeout/);
});

check("deriveEventsLoadState", () => {
  assert.equal(ux.deriveEventsLoadState({ loading: true }), "loading");
  assert.equal(ux.deriveEventsLoadState({ started: true, items: [] }), "empty");
  assert.equal(ux.deriveEventsLoadState({ started: true, items: [{}] }), "loaded");
  assert.equal(ux.deriveEventsLoadState({ started: false }), "not_loaded");
  assert.equal(ux.deriveEventsLoadState({ error: "x" }), "error");
});

check("filterCatalogItems search + category", () => {
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

check("filterClusters", () => {
  const clusters = [
    { name: "prod-mumbai", region: "ap-south-1", environment: "production" },
    { name: "dev-local", region: "local", environment: "development" },
  ];
  assert.equal(ux.filterClusters(clusters, "mumbai").length, 1);
  assert.equal(ux.filterClusters(clusters, "dev").length, 1);
  assert.equal(ux.filterClusters(clusters, "").length, 2);
});

check("testConnectionResult", () => {
  assert.equal(ux.testConnectionResult({ connected: true, message: "ok" }).state, "ok");
  assert.equal(ux.testConnectionResult({ connected: false }).state, "err");
  assert.equal(ux.testConnectionResult(null, "boom").state, "err");
});

check("isServiceInstalling", () => {
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

check("shouldBlockDeploy", () => {
  assert.equal(ux.shouldBlockDeploy({ hasNode: false }).blocked, true);
  assert.equal(ux.shouldBlockDeploy({ hasNode: true, hasService: false }).blocked, true);
  assert.equal(ux.shouldBlockDeploy({ hasNode: true, hasService: true }).blocked, false);
});

check("constants present", () => {
  assert.deepEqual([...ux.DETAIL_TOOLBAR_ORDER], ["overview", "edit", "events", "discover", "launch", "delete"]);
  assert.deepEqual([...ux.INFO_DRAWER_TABS], ["overview", "events", "live"]);
  assert.equal(ux.CLUSTER_EDITOR_STEPS.length, 4);
  assert.ok(String(ux.LAUNCH_STUB_MESSAGE).includes("not configured"));
});

check("shouldRefreshOpenEvents after mutation tick", () => {
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

check("deployButtonClass loading", () => {
  assert.ok(ux.deployButtonClass("btn btn-primary btn-sm", true).includes("btn-loading"));
  assert.ok(!ux.deployButtonClass("btn btn-primary btn-sm", false).includes("btn-loading"));
});

check("formatClusterEventRow cPlatform style", () => {
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

check("DETANGLED_VIEWS excludes advanced product pages", () => {
  assert.ok(ux.DETANGLED_VIEWS.includes("topology"));
  assert.ok(ux.DETANGLED_VIEWS.includes("policy"));
  assert.ok(ux.DETANGLED_VIEWS.includes("audit"));
  assert.ok(ux.DETANGLED_VIEWS.includes("reliability"));
});

const summary = `\n${passed} checks passed\n`;
console.log(summary);
writeFileSync(join(outDir, "ux-unit-tests-summary.txt"), summary, "utf8");
if (process.exitCode) process.exit(process.exitCode);
