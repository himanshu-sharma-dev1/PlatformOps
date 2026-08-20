# Cluster Page — cPlatform UX Structure Parity Spec

**Status:** IMPLEMENTED / LIVING UX SPECIFICATION
**Scope:** Cluster list + cluster detail only (not Config/Diagnostics/Monitoring product pages except entry points)
**Visual skin:** Keep **PlatformOps** fonts, colors, spacing tokens, glass cards where they already exist
**UX contract:** Implemented in `apps/web/src/views/ClustersView.tsx`, `apps/web/src/views/DrawersHost.tsx`, and `apps/web/src/views/ModalsHost.tsx` (drawers vs modals, spinners, loading shells, toast kinds, event panels, catalog flow, detail drawer tabs, button busy states)

**Related:**

| Doc | Role |
|-----|------|
| `docs/features/cluster-page-complete-reference.md` | Functional APIs + feature inventory |
| `docs/selected-page-functional-parity.md` | Master 7-page action inventory |
| `docs/redis-seven-page-acceptance-fixture.md` | Authoritative 7-page acceptance fixture |
| cPlatform sources (read-only) | `02-clusters.html`, `04-cluster-detail.html`, `clusterDetail.js`, `cluster.css`, `clusterDetail.css` |

---

## 0. Design principles (locked)

1. **Tokens stay PlatformOps** — `--navy-*`, `--ink-*`, GlassCard, existing button/pill classes; do **not** re-skin the whole app to cPlatform colors.
2. **Interaction is cPlatform** — same open/close targets, same step wizards as drawers (not ad-hoc page jumps), same busy/spinner patterns, same detail-drawer triad (Overview | Events | Live Status) for node **and** service.
3. **No fake UX** — loading states only while real API work runs; toasts reflect real outcomes (`ok` / `err` / `warn`).
4. **Build on existing FE** — `ClustersView`, `ModalsHost`, `DrawersHost`, platform actions; prefer refactor of structure over rewrite of business logic.
5. **Pixel clone means layout + density + motion**, not CSS variable identity: column split, drawer width, catalog slide-in, card stacking, footer action bars.

---

## 1. cPlatform source map (read-only)

| Asset | LOC (approx) | Role |
|-------|--------------|------|
| `templates_new/PlatformIO/02-clusters.html` | ~1.3k | Cluster list, search/filter chips, add/edit cluster **drawer** (4-step) |
| `templates_new/PlatformIO/04-cluster-detail.html` | ~3.3k | Detail shell, node list, node detail, service stack, all drawers/modals |
| `static/javascript/clusterDetail.js` | ~3.5k | State machine, drawers, toasts, spinners, live poll, events render |
| `static/css/cluster.css` | ~1.0k | List page layout + drawer chrome |
| `static/css/clusterDetail.css` | ~2.4k | Detail layout, catalog, toast, loading shells, busy states |

### 1.1 Shared UX primitives (cPlatform)

| Primitive | Behavior | CSS / JS |
|-----------|----------|----------|
| **Toast** | `#toast` + `#toastMsg`; `showToast(msg, kind)` with `ok`/`err`; auto-dismiss ~3.2s; class `show` | `.toast`, `.toast.ok`, `.toast.err` |
| **Button loading** | `setButtonLoading(btn, true, text)` → disable + spinner HTML + restore original | `.btn-loading`, `.btn-spinner` |
| **Busy surface** | `setBusyState(el, true)` → `.is-busy` on drawer body | blocks double-submit |
| **Inline loading shell** | `detail-loading-shell` + pulsing dot | while fetch in flight |
| **Drawer backdrop** | `.drawer-backdrop.open` + slide-in `.drawer.open` | 0.25–0.3s cubic-bezier |
| **Wide detail drawer** | `.drawer.wide.detail-drawer` for node/service info | tabs inside |
| **Catalog drawer** | Right slide-in independent of detail drawer | search + categories |
| **Action blocker modal** | Blocks invalid action with primary/secondary CTAs | e.g. “open catalog first” |

---

## 2. Cluster list page (`02-clusters`) — UX contract

### 2.1 Layout (cPlatform)

```
┌─────────────────────────────────────────────────────────────┐
│ Header: title + subtitle | [+ Add cluster]                  │
│ Stat strip: cluster count …                                 │
│ Toolbar: Search clusters | Type chip | Region chip | Filter │
│ Grid: cluster cards + dashed "Add cluster" card             │
└─────────────────────────────────────────────────────────────┘
         └── Add/Edit cluster = RIGHT DRAWER (not centered modal)
              Stepper 1 Identity → 2 Repository → 3 Image store → 4 Review
              Foot: Cancel | Back | Next | Create/Save
```

### 2.2 Interaction matrix — list

| User action | cPlatform UX | PlatformOps today | Gap |
|-------------|--------------|-------------------|-----|
| Add cluster | Opens **drawer** from right; stepper | `ModalsHost` centered **modal** | Use **drawer** chrome + same steps; keep PO tokens |
| Edit settings | Same drawer in edit mode + EDIT badge; secrets **Replace** | Modal edit | Match drawer + replace-secret pattern |
| Test repo / registry | Inline test button → result span `ok`/`err`/`testing` | Toast-only often | Add inline result + button spinner |
| Search clusters | Live filter list | Partial / none | Add client filter |
| Filter chips | Type / region / env | Missing | Optional chips |
| Open cluster | Navigate to detail | `selectCluster` in-app | Keep SPA selection; match density |
| Empty state | Dashed add card | Create button only | Add dashed card UX |
| Toast on save | Bottom/top toast ok | notice/toast-bar | Align position + kinds |

### 2.3 Wizard fields (structure parity)

Keep PO field set if already sufficient; **layout** must match step panes:

1. **Identity** — name, region select, env select, description
2. **Repository** — provider cards, URL, branch, path, auth tabs (PAT/SSH/none), Replace secret, Test connection
3. **Image store** — provider cards, URL, namespace, auth tabs, Test connection
4. **Review** — review rows + confirm

**Busy:** Create/Save uses `setButtonLoading`; drawer body `is-busy` during submit.

---

## 3. Cluster detail page (`04-cluster-detail`) — UX contract

### 3.1 Shell layout (cPlatform)

```
┌─ Header: back/title | Provision node | Settings | Delete cluster ─┐
│ Cluster band: identity badge + stats (nodes / services / running) │
├──────────────────┬────────────────────────────────────────────────┤
│ NODE LIST        │ NODE DETAIL                                     │
│ Search           │ Spec header (name, region, id)                  │
│ node-row list    │ Toolbar: Overview | Edit | Events | Discover    │
│ [+ Add node]     │           Launch | Delete                       │
│                  │ Spec sheet (vCPU/Mem/Disk/GPU/OS)               │
│                  │ Utilization bars (CPU/Mem/Disk/GPU…)            │
│                  │ Services head + [Catalog]                       │
│                  │ service-stack (svc-cards)                       │
└──────────────────┴────────────────────────────────────────────────┘
```

### 3.2 Interaction matrix — detail chrome

| Control | cPlatform | PO today | Target UX |
|---------|-----------|----------|-----------|
| Node select | `.node-row.active`, updates right pane without full page reload | Similar | Keep; add loading shell on switch |
| Overview | Focuses overview content | Tab `overview` | Align labels/placement to cP toolbar |
| Edit node | Opens **node drawer** (tabs: connection / events) | Edit modal/stepper | Drawer with tabs |
| Node Events | Opens detail drawer **Events** tab for node **or** events panel | In-page Events tab | Prefer **info detail drawer** for node+service (cP primary) |
| Discover | Button busy + toast result | Button + toast | + spinner on button |
| Launch | Opens provision / cloud launch UI | Weak / deferred | **Stub drawer** (“Launch not configured”) — not full Terraform |
| Delete node/cluster | Confirm + impact; busy | Delete modal | Keep modal; match button loading |
| Catalog | **Catalog drawer** slide-in | Drawer exists | Match search, categories, item cards, foot |
| Drag catalog → node | Drop opens **svc-config drawer** | Register flow | Optional DnD; at least click → config drawer |
| Service card click | Opens **info detail drawer** Overview | Service drawer (good start) | Match subhead, tabs, foot actions, deps table |
| Service Config icon | Config Manager navigation | Jump to config view | Keep deep-link; optional in-drawer shortcut |
| Service Edit | Edit install/schema | Partial expose | Full edit drawer path |
| Runtime patch | Footer button on service detail | Card + drawer | Keep; loading + status text in drawer |
| Live status | Detail tab + refresh | Live tab + drawer | Match loading shell + dependency table |
| Events | Drawer events panel with status text | Node tab + service drawer | Unified renderEvents pattern |
| Installing service | Card shimmer / progress | Job notice | Card-level installing state |

### 3.3 Info detail drawer (canonical)

**IDs (cPlatform):** `#infoDetailBack`, `#infoDetailDrawer`

| Region | Contents |
|--------|----------|
| Head | Title, close icon |
| Subhead | Status pill + meta id line |
| Tabs | Overview \| Events \| Live Status |
| Overview pane | Summary cards, `detail-grid` DL, extra rows, runtime patch status text |
| Events pane | “Recent events” + status (“Not loaded” / “Loaded N”) + scroll panel |
| Live pane | Checked-at, Refresh, summary, main container grid, **dependencies table** |
| Foot | Delete \| Close \| Launch (conditional) \| Patch Observability (service) \| Edit |

**Loading:** while fetching, Overview/Live show `detail-loading-shell` with pulse; Events shows loading message; `setDrawerActionLoading` disables foot buttons.

### 3.4 Catalog drawer

| Region | Contents |
|--------|----------|
| Head | Title + close |
| Search | Filter catalog items live |
| Categories | chips (infra / app / all) |
| List | `.catalog-item` cards with type, version, ports |
| Foot | Cancel / hint |

**Click item** → close catalog → open **service install / config drawer** (dForm fields, MANUAL/ANSIBLE, expose).

### 3.5 Node provision drawer

cPlatform multi-step (cloud vs bare metal, credentials, config, ports).
PO has stepper drawer — **align step labels, foot buttons, busy state**; keep PEM path fields.

### 3.6 Action blocker modal

When user tries deploy/config without prerequisites: modal with message + secondary “Open catalog” / primary dismiss.

### 3.7 Service card visual states

| State | cPlatform cue | Target |
|-------|---------------|--------|
| running | green pill / tile class | Keep PO pills + optional tile class |
| stopped/error | red/warn | Same |
| installing | shimmer bar | Add during deploy job |
| adopted | meta line “adopted · container” | Show on card meta |
| internal vs exposed | port or `internal` | Match expose badge |

---

## 4. Events UX (how events are configured & shown)

### 4.1 cPlatform model

| Scope | API user-action | UI surface |
|-------|-----------------|------------|
| Node | `node_event` | Node Events button / detail Events tab |
| Service | `service_event` | Service detail Events tab |
| Render | `renderEvents(panelId, statusId, list, emptyMsg)` | Status line + list articles |

Events are **fetched on open tab/drawer**, not only global dump. Empty and loading strings are first-class.

### 4.2 PlatformOps model (current)

| Scope | API | UI |
|-------|-----|-----|
| Node | `GET /api/events?node_id=` via `loadScopedEvents` | Events tab + `nodeEvents` state |
| Service | `GET /api/events?service_id=` | Service drawer Events tab |
| Global | `GET /api/events` on refresh | Audit / global |

### 4.3 Target UX parity for events

1. Opening **Events** always triggers scoped fetch + loading status text.
2. Status line: `Not loaded` → `Loading…` → `N events` / empty message.
3. Each row: level pill + message + timestamp (and optional trigger category).
4. Detail drawer and node Events button open the **same** event renderer.
5. After Discover/Deploy/Config/Delete, optionally **refresh** open events panel.
6. Do not invent fake events; only operational events from API.

---

## 5. Loading / spinner / toast matrix

| Situation | cPlatform | Target PO |
|-----------|-----------|-----------|
| Drawer open + fetch | loading shell in pane | Same component pattern |
| Button async action | spinner inside button | `btn-loading` utility (add if missing) |
| Discover | button loading + toast summary | Same |
| Deploy | modal may show steps; card installing | Deploy modal busy + card shimmer |
| Config apply (from cluster entry) | toast ok/err | Keep config page; toast on return |
| Live refresh | checked-at updates; brief busy | Disable refresh while in flight |
| Validation / jobs | job history updates | Jobs tab already; toast on start/end |
| Login / unauth | N/A | No poll without token (already fixed) |

**Toast kinds:** `ok` | `err` | `warn` — map all cluster actions; auto-dismiss ~3s; dismiss control.

---

## 6. PlatformOps gap summary (UX only)

| Area | Functional today | UX gap severity |
|------|------------------|-----------------|
| Cluster create/edit | Yes | High — modal vs drawer, secret replace, inline test results |
| Cluster list filters | Weak | Med |
| Detail 2-column layout | Partial | High — density, toolbar placement |
| Node toolbar set | Partial | High — cP button order + drawer opens |
| Info detail drawer | Service only (basic) | High — widen to node+service; deps table; foot actions |
| Catalog drawer | Yes | Med — categories, item density, install drawer chain |
| Install / svc-config drawer | Onboarding drawer | High — match post-catalog field sections |
| Events | Wired | Med — status lines + shared renderer |
| Live | Wired | Med — deps table + loading shell |
| Spinners / busy | Inconsistent | High — standardize setButtonLoading / is-busy |
| Toast | Exists | Low — unify position/kind usage |
| Installing card state | No | Med |
| Action blocker modal | Weak | Med |
| Drag-drop catalog | No | Low/Med |
| Launch VM | Stub button + drawer (locked) | Low |

---

## 7. Implementation workstreams (for the goal doc)

| WS | Name | Outcome |
|----|------|---------|
| **UX-0** | Interaction primitives | `setButtonLoading`, drawer busy, loading shell, toast kinds used everywhere |
| **UX-1** | Cluster list chrome | Search, chips optional, dashed add card, **create/edit as drawer** |
| **UX-2** | Detail shell layout | 2-column density, band, node list foot, toolbar order |
| **UX-3** | Info detail drawer | Shared node/service; Overview/Events/Live; foot actions; deps table |
| **UX-4** | Catalog + install drawer | Categories, search, install chain, expose/schema sections |
| **UX-5** | Events renderer | Shared component; status text; refresh after mutations |
| **UX-6** | Live + installing states | Loading shells; card shimmer during jobs |
| **UX-7** | Action blockers + confirms | Modal patterns matching cP |
| **UX-8** | Verification | Click-path matrix + screenshots checklist + no dead busy states |

---

## 8. Acceptance definition (UX goal)

For **cluster list + detail only**:

1. Every primary cPlatform control that we implement opens the **same class of surface** (drawer vs modal vs inline).
2. No primary action lacks busy/spinner feedback when async.
3. Node and service detail use **one** wide drawer with Overview | Events | Live Status.
4. Events always scoped-load with status line.
5. Catalog open/close/search/select matches cP flow (DnD optional).
6. PlatformOps visual tokens retained; layout density approaches cP clusterDetail.
7. Existing functional APIs continue to work (no regression of smoke: discover, deploy, config apply, AIOrchestrator guard).

**Out of scope for this UX goal:** pixel-identical colors/fonts; full Config Manager page rebuild; Launch VM unless product opts in.

---

## 9. File touch list (expected)

| Layer | Files |
|-------|--------|
| FE views | `ClustersView.tsx`, `ModalsHost.tsx` → prefer drawer hosts, `DrawersHost.tsx` |
| FE state/actions | `useUiState.ts`, `inventory*.ts`, shared `ButtonLoading` helper |
| CSS | `styles.css` (drawer motion, btn-spinner, detail-loading, catalog density) — **extend**, don’t replace tokens |
| Docs | this spec + goal file; update complete-reference § layout notes when done |

---

## 10. Traceability to cPlatform IDs (implementation checklist seed)

### List page
`addClusterBtn`, `clusterSearch`, `typeChip`, `regionChip`, `addClusterDrawer`, `drawerBack`, `test-repo-btn`, `test-img-btn`, `toast`

### Detail page
`newNodeBtn`, `clusterSettingsBtn`, `deleteClusterBtn`, `nodeSearch`, `nodeList`, `nodeDetail`, `nodeOverviewBtn`, `editActiveNodeBtn`, `nodeEventsBtn`, `discoverInfraBtn`, `launchNodeBtn`, `deleteNodeBtn`, `catalogBtn`, `serviceStack`, `infoDetailDrawer`, `detailTabs`, `detailLiveStatusRefreshBtn`, `detailDeleteBtn`, `detailEditBtn`, `btnRuntimePatchFooter`, `catalogDrawer`, `catalogSearch`, action blocker, `toast`

Map each to a PO React control or explicit “deferred”.

---

*End of UX parity spec.*
