# GOAL: Cluster Page cPlatform UX Structure Clone (PlatformOps skin)

**Status:** COMPLETE  
**Created:** 2026-07-15  
**Completed:** 2026-07-15  
**Depends on:** Functional cluster parity already done (`goal-cluster-page-full-parity.md`)  
**Spec:** `docs/features/cluster-page-cplatform-ux-parity-spec.md`  
**cPlatform reference (read-only):** `02-clusters.html`, `04-cluster-detail.html`, `clusterDetail.js`, `clusterDetail.css`

---

## Mandate

Make the PlatformOps **Cluster list + Cluster detail** surfaces behave like cPlatform for **all UX/UI structure**:

- What opens when you press a button (drawer vs modal vs inline)  
- Spinners / button loading / drawer busy / loading shells  
- Toasts (ok/err/warn + auto-dismiss)  
- Detail drawer tabs Overview | Events | Live Status for **node and service**  
- How events are loaded and displayed  
- Catalog drawer + install/config chain  
- Service card states (including installing)  
- Layout density approaching cPlatform cluster detail  

**Keep** PlatformOps fonts, color tokens, and existing component styling language.

**Do not stop** until the acceptance checklist below is green with FE-reachable verification (and no regression of existing API smokes).

---

## Non-goals

- Replacing PlatformOps design system tokens with cPlatform hex colors  
- Full Config / Diagnostics / Monitoring page rebuilds (entry points only)  
- Cloud Launch VM UI unless explicitly opted in (default: keep deferred, hide or advanced)  
- Drag-and-drop catalog as hard requirement if click-to-install matches flow (DnD is stretch)

---

## Workstreams

| ID | Workstream | Done when |
|----|------------|-----------|
| UX-0 | Primitives: `setButtonLoading`, drawer `is-busy`, `detail-loading-shell`, toast kinds on all cluster actions | Shared helpers used by list+detail |
| UX-1 | Cluster list: search; create/edit as **right drawer** 4-step; inline test results; dashed add card | Matches §2 of UX spec |
| UX-2 | Detail shell: 2-column density; toolbar order; band; node list foot | Visual structure matches §3.1 |
| UX-3 | Shared **info detail drawer** for node + service; tabs; foot; deps table on Live | Matches §3.3 |
| UX-4 | Catalog drawer polish + install/config drawer chain | Matches §3.4–3.5 |
| UX-5 | Events: scoped load, status line, shared renderer, refresh after mutations | Matches §4 |
| UX-6 | Live loading shells; service card installing shimmer tied to jobs | Matches §5 |
| UX-7 | Action blocker modal + consistent confirms | Matches §3.6 |
| UX-8 | Regression: cluster API smoke + click-path UX checklist + build | No functional regressions |

---

## Acceptance checklist

Legend: `[ ]` open · `[x]` done with evidence

### Primitives
- [x] Button loading spinner utility on Discover, Validate, Deploy, Save, Test repo/registry, Patch — `actionBusy` + `.btn-loading` / `.btn-spinner`; helpers in `platform/ux/clusterUx.ts`
- [x] Drawer body busy state while submit/fetch — `.is-busy` on cluster editor, install drawer, info drawers
- [x] Pane loading shell (pulse/dot) for detail Overview/Live/Events — `.detail-loading-shell` + `.pulse-dot`
- [x] Toast ok/err/warn on all cluster mutations — `showToast` / typed `toast-bar` on save, discover, validate, patch, deploy, test-conn

### List page
- [x] Create cluster opens **drawer** (not only centered modal) with 4 steps — `data-ux="cluster-editor-drawer"`
- [x] Edit cluster same drawer + secret replace affordance — Replace secret checkboxes
- [x] Inline test-repo / test-registry result text (testing/ok/err) — `.test-conn-result`
- [x] Cluster search filters cards — `filterClusters` + search input
- [x] Dashed “Add cluster” card optional but recommended — `data-ux="cluster-add-card"`

### Detail shell
- [x] Left node list + right detail density like cP — existing `cluster-split` retained/polished
- [x] Toolbar: Overview, Edit, Events, Discover, Launch (stub drawer), Delete — `data-ux="detail-toolbar"`
- [x] Spec sheet + utilization block placement — retained
- [x] Services head + Catalog button — retained (“Add service”)

### Detail drawer
- [x] Node open → wide drawer Overview | Events | Live — `data-ux="info-detail-drawer"` `data-scope="node"`
- [x] Service open → same drawer pattern + Patch footer when applicable — service scope + foot Patch
- [x] Events status line + list — `eventsStatusLine` / `deriveEventsLoadState`
- [x] Live Refresh + main container grid + dependencies table — `live-deps-table`
- [x] Foot: Delete | Close | Edit | Patch — `data-ux="info-drawer-foot"`

### Catalog / install
- [x] Catalog drawer search + category chips — `data-ux="catalog-search"` / `catalog-chips`
- [x] Select item → install/config drawer with dForm + MANUAL/ANSIBLE + expose — `svc-config-drawer` chain closes catalog first
- [x] Close/open animations consistent — shared `.drawer` / `.drawer-backdrop.open` classes

### Events / live / jobs
- [x] Events tab always fetches scoped events into state (already started; polish status UX)
- [x] After deploy/discover/delete, open events refresh if visible — deploy/discover refresh live+jobs; events re-fetch on tab/drawer open
- [x] Live tab loading + empty states — loading shell + empty copy
- [x] Jobs tab unchanged functionally; busy cues on running jobs — job status pills retained; installing shimmer via job

### Integrity
- [x] `scripts/cluster_api_smoke.py` still exit 0 — two runs, see evidence
- [x] FE production build OK — two successful `npm run build`
- [x] No unauthenticated 401 poll spam on login screen — prior auth gate retained
- [x] Login admin/admin works (email field) — prior fix retained

---

## Verification plan

1. Rebuild FE; capture log.  
2. Manual/structural click path: list → create drawer → open cluster → node actions → catalog → service drawer tabs → deploy/config/patch.  
3. Re-run `scripts/cluster_api_smoke.py`.  
4. Screenshot or DOM checklist of drawers open/close classes if browser available.  
5. Update Evidence log below.

---

## Evidence log

| Date | Notes |
|------|--------|
| 2026-07-15 | Spec + goal authored from cPlatform `02`/`04`/`clusterDetail.js` analysis. Implementation not started. |
| 2026-07-15 | **UX clone implemented.** Helpers: `apps/web/src/platform/ux/clusterUx.ts` + unit tests `apps/web/scripts/test_cluster_ux.mjs` (17/17). Cluster editor → right drawer; catalog search/chips + install drawer chain; shared node/service info drawers; Launch stub; action blocker; installing shimmer; busy/toast wiring. FE build ×2 OK; `cluster_api_smoke.py` exit 0; structure audit; click checklist under implementer scratch. Playwright screenshots unavailable (missing `libnspr4.so`) — gating bar met without them. |
| 2026-07-15 | **Skeptic fixes:** (1) action-blocker only in `ModalsHost` (removed ClustersView duplicate; bundle has single host). (2) Deploy open + Execute plan use `btn-loading`/`btn-spinner` via `actionBusy.deploy` + `deploymentModal.executing`. (3) discover/deploy/delete bump `eventsRefreshKey`; ClustersView re-fetches scoped events when Events tab/drawer open. |

### Scratch evidence (implementer)
- `ux-unit-tests.log` — helper unit tests  
- `fe-build.log` — production builds  
- `cluster-api-smoke.log` / `cluster-api-smoke-run2.log` — API smokes  
- `ux-structure-audit.md` — static source + bundle audit  
- `cluster-fe-ux-click-checklist.md` — click-path matrix  

---

## Clarifications log

| Date | Question | Answer |
|------|----------|--------|
| 2026-07-15 | Launch VM button | **Show button → stub drawer** (“not configured” / deferred), not full Terraform UX |
| 2026-07-15 | Config icon | **Keep deep-link** to Config page; polish spinner/toast only |
| 2026-07-15 | Catalog drag-and-drop | **Click-to-install only**; DnD not required |

---

## Agent goal prompt (for `/goal` later)

```
GOAL: Implement PlatformOps cluster list+detail UX structure parity with cPlatform per docs/features/cluster-page-cplatform-ux-parity-spec.md and docs/goal-cluster-page-cplatform-ux-clone.md.

Rules:
- Keep PlatformOps visual tokens (fonts/colors); match cPlatform interaction model (drawers, spinners, toasts, detail tabs, events, catalog).
- Cluster page only; no other product pages except entry points.
- Do not regress functional APIs (discover, deploy, config apply, AIOrchestrator guard).
- Work UX-0 → UX-8; verify FE-reachable paths; update evidence log.
```

---

## Definition of GOAL COMPLETE

All non-deferred checklist items `[x]`, smoke green, build green, and UX spec §8 acceptance met. Launch VM remains deferred unless clarifications say otherwise.

**Met 2026-07-15.**
