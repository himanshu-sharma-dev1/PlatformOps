# Cluster Page Production Roadmap (cPlatform parity only)

**Status:** implementing — **decisions locked 2026-07-10**; Phases 1–3 partially landed (toast, node facts, SERV IDs, AIOrchestrator bootstrap, full dForm install-schema)  
**Scope:** **Clusters page only** — full cPlatform cluster list + detail parity, production-ready.  
**Out of scope for this plan:** Config Manager, Diagnostics, Monitoring, Performance, Users, Placement product, Secrets vault, Releases product, more FE decomposition for its own sake.  
**Baseline:** Phase 2b FE split done (`state/*` + `actions/*` + thin controller).  
**Integrity:** real-only — no fake success toasts, no mock healthy status.

---

## 0a. Locked product decisions (from owner)

| Decision | Choice |
|----------|--------|
| **Verification node** | **Remote-style SSH** to host **`65.2.63.24`** with key **`/home/ubuntu/NODE1001.pem`** (same material as mashupstack share `himanshu`). Treat as real remote node path (PEM paste/path), even if public IP is this host. Never commit the PEM into git; only path or upload into `runtime/ssh_keys/`. |
| **UI fidelity** | **High visual fidelity** to cPlatform cluster detail (`04-cluster-detail.html` + `clusterDetail.css` + `clusterDetail.js` layout/density). Port structure: node list left, node overview + actions, service stack, catalog drawer, provision drawer. Restyle with PlatformOps tokens only where necessary; match layout/interaction first. |
| **Service IDs** | **`external_id` column** + allocate `SERV####` with clash avoidance vs discovered/reserved names. |
| **Install forms** | **Full `dFormService.json` import for all service types** now — not a subset. FE renders from normalized dForm schema API. |
| **Cloud VM / Terraform** | **Deferred** — PEM real nodes only for v1 acceptance. Keep launch/teardown APIs; hide or advanced-gate in UI. |
| **Toasts** | **cPlatform-style** typed toast (`ok` / `err` / `warn`), auto-dismiss, used by all cluster actions. |
| **AIOrchestrator parity** | cPlatform bootstraps **AIOrchestrator** on primary cluster create and **blocks deleting it while other services exist**. PlatformOps must have an equivalent **platform control / AIOrchestrator** catalog + dForm entry, lifecycle rule, and bootstrap path on cluster create (or first node) — see §2.6. |

**Verification vehicle:** dTrain (+ deps as needed) and AIOrchestrator-class service on node docker network **`platformops_prod_network`** (isolated from `cplatform_iktara_cPlatform`).

---

## 0. Why this plan exists

cPlatform’s cluster surface (`02-clusters.html` + `04-cluster-detail.html` + `clusterDetail.js` ~3.5k LOC + `ServiceConfig.py`) is the operator home. PlatformOps already has **most backend endpoints** and a **rough Clusters UI**, but:

| Reality today | Effect |
|---------------|--------|
| Create cluster/node **exist in API + actions** | Often feel broken because modals/stepper UI are incomplete, half-bound, or hard to use |
| Node provision **stepper hardcodes CPU/RAM/disk** (`defaultValue` not in draft/API) | Spec sheet shows “—”; nothing stored for later metrics wiring |
| Service IDs are **integer PKs** only | cPlatform uses stable `SERV1xxx` strings that **skip collisions** with discovered container names |
| Install forms are **flattened catalog contract fields** | cPlatform uses **per-service dForm** schemas (`dFormService.json`) with MANUAL vs ANSIBLE |
| Discover is **simple name/image heuristics** | cPlatform uses scored match, reserved names, infra catalog, adopt flags |
| Live status is **not polled continuously on Clusters** | cPlatform caches `service_live_status` (~5s TTL) and paints green/yellow/red |
| Toasts are a **single string `notice` bar** | cPlatform `showToast(msg, kind)` with auto-dismiss + error styling |
| Docker network default `platformops_prod_network` | Correct isolation from `cplatform_iktara_cPlatform` — **keep this** |

This plan freezes **architecture + implementation order** so later work is **fill-in-the-gaps**, not redesign.

---

## 1. Source of truth (do not invent features)

| Source | Use for |
|--------|---------|
| `cplatform_master/cPlatform/templates_new/PlatformIO/02-clusters.html` | Cluster list + create wizard UX |
| `cplatform_master/cPlatform/templates_new/PlatformIO/04-cluster-detail.html` | Detail layout, drawers, service cards |
| `cplatform_master/cPlatform/static/javascript/clusterDetail.js` | State machine, toast, live status, drawers |
| `cplatform_master/cPlatform/cPlatformIO/src/ServiceConfig.py` | `SERV####` allocation, discover/adopt, live status, infra catalog |
| `cplatform_master/cPlatform/cPlatformIO/forms/dFormService.json` | Per-service parameter forms |
| `PlatformOps/docs/features/cluster-page-detailed-features.md` | Feature inventory checklist |
| `PlatformOps/catalog/services.yaml` + install-schema API | PlatformOps catalog contracts |
| Existing routers: `clusters.py`, `nodes.py`, `services.py` | Prefer extend, not rewrite |

**Verification vehicle:** deploy **dTrain** (images already present: `iktaraai/services:dTrain-*`, `platformops/dtrain-controller:local`) onto a node on **`platformops_prod_network`** (never join cPlatform’s docker network).

---

## 2. Target architecture (lock now — avoid rework)

### 2.1 Domain model (DB + API)

Keep SQLAlchemy models; **extend**, don’t replace:

```
Cluster
  id, name, region, environment
  repo_* , registry_*          # already present; mask secrets on read
  nodes[]

Node
  id, cluster_id, name, host, ssh_user, ssh_key_path
  environment, volume_root, docker_network, status
  facts_json                   # MUST store cpu/mem/storage/gpu/os (today often empty)
  services[]

ServiceInstance
  id (internal PK)
  external_id (NEW)            # e.g. SERV1001 — cPlatform-compatible display/key
  node_id, service_key, name, kind
  container_name, image, status
  config_json                  # full install contract + ports + adopted + install_mode
  adopted (derived from config or NEW bool column)
```

**ID allocation (port of cPlatform `_allocate_service_id`):**

- Format: `SERV` + integer starting at **1000** (or configurable base).
- On create **or** adopt: allocate next free ID that is **not** in:
  - existing `ServiceInstance.external_id` rows
  - discovered container names / reserved runtime names on that node
- Internal integer `id` remains FK for jobs/events; UI and docker labels prefer `external_id`.

**Port / name collision:** extend `check_port_and_name_availability` to inspect:

1. DB service contracts (host ports, container names)
2. Optional live `docker ps` ports when node reachable

**Docker network rule:** every new node defaults to `platformops_prod_network` (or explicit override). Never auto-use cPlatform network names.

### 2.2 Backend modules (orchestrator)

| Module | Responsibility | Status |
|--------|----------------|--------|
| `routers/clusters.py` | CRUD, summary, ops view, test-repo/registry | Mostly done |
| `routers/nodes.py` | CRUD, validate, discover, connection, onboarding, metrics, lifecycle | Mostly done; harden |
| `routers/services.py` | create/update/preflight/deps/deploy/delete/live | Mostly done; add live poll endpoint polish |
| `orchestrator/discovery.py` | docker ps + match + adopt | **Upgrade** to scored matching + external_id |
| `orchestrator/service/impl.py` | create, install schema, deploy, port check | **Upgrade** schema + ID + MANUAL/ANSIBLE |
| `orchestrator/node.py` | connection, onboarding, facts, jobs | Wire facts from provision + validate |
| NEW thin `orchestrator/ids.py` | `allocate_service_external_id`, reserved names | Port from cPlatform |

**Do not** invent a second cluster backend. Prefer one path: API → orchestrator → ansible/docker → job + event.

### 2.3 Frontend architecture (stable seams + high visual fidelity)

Keep Phase 2b seams; **cluster work stays in inventory domain**:

```
platform/state/useInventoryState.ts     # clusters, nodes, services, editors, catalog onboarding
platform/state/useUiState.ts            # toast stack, drawers, steppers
platform/actions/inventoryLoadActions.ts
platform/actions/inventoryEditorActions.ts
platform/actions/inventoryDeployActions.ts
views/ClustersView.tsx                  # list + detail — rebuild layout toward cPlatform
views/ModalsHost.tsx                    # cluster/node/delete modals
views/DrawersHost.tsx                   # catalog + provision + dForm service form
styles.css (+ optional cluster-detail.css port)  # high-fidelity layout from clusterDetail.css
shared toast layer                      # showToast(msg, kind) parity
```

**Visual / layout targets (from cPlatform `04-cluster-detail`):**

1. **Cluster list** page resembling `02-clusters` cards (env badge, aggregates, create CTA).  
2. **Detail split:** left **node list** with search + **svc count**; right **node header** (name, cloud tag, IP, volume) + **action row** (Validate, Discover, Edit, Events, Delete — Launch VM deferred/hidden).  
3. **Spec sheet row:** vCPU · Memory · Storage · GPU · OS · Status (from `facts_json` + live).  
4. **Services stack:** cards with icon, name, `external_id`, ports, live pill, actions (logs/config/deploy/uninstall).  
5. **Catalog drawer** (right): grouped services; open **dForm** install form.  
6. **Provision node drawer:** multi-step with **real** PEM + facts (no dead `defaultValue` fields).  

**State patterns to copy from cPlatform:**

| cPlatform pattern | PlatformOps equivalent |
|-------------------|------------------------|
| `state.detailServiceId` + caches | `selectedService` + `serviceLiveStatusById` map |
| `showToast(msg, kind)` | `pushToast({ message, kind: 'ok'\|'err'\|'warn', ttlMs })` |
| `serviceLiveStatusCache` TTL | poll while Clusters + node selected |
| Drawer open/close + form draft | `clusterEditor` / `nodeEditor` / `catalogOnboarding` / dForm draft |
| Block delete with message | lifecycle 409 → toast + modal detail |
| SVC count on node row | refresh after mutate/discover/live |

**UI goal:** **high visual fidelity** to cPlatform cluster detail (layout + density + interaction), PlatformOps branding tokens where colors clash. **Required:** no dead buttons; real success/error only.

### 2.4 Install form strategy — **full dFormService.json import**

cPlatform source: `cPlatform/cPlatformIO/forms/dFormService.json` (all service types, including AIOrchestrator, infra, dTrain, etc.).

PlatformOps approach (locked — full import):

1. Vendor/copy `dFormService.json` into `PlatformOps/catalog/dform/dFormService.json` (or symlink/import path at runtime).  
2. **Normalize** dForm properties → install-schema DTO:
   - `key`, `label`, `field_type`, `required`, `default`, `options`, `min`/`max`, `editable`, `visible_on`, colors for deploy status, etc.  
3. API: `GET /api/catalog/services/{service_key}/install-schema` returns **full dForm-derived fields** for that type (map cPlatform type names ↔ PlatformOps `service_key` via `settings` alias map + catalog).  
4. FE: dynamic form renderer (text, number, single_select, …) driven only by schema — **no hard-coded per-service React forms**.  
5. **MANUAL vs ANSIBLE** from `ServiceInstall` field (or equivalent).  
6. Catalog `services.yaml` still supplies image/volumes/deploy contract for ANSIBLE path; dForm supplies operator parameters stored in `config_json`.  
7. Unknown type without dForm entry: fail closed with clear error (do not invent fields).

### 2.6 AIOrchestrator / platform control parity

cPlatform behavior:

- On primary cluster create → `_bootstrap_primary_cluster` creates a default node shell and **`service_add_request(..., 'AIOrchestrator')`**.  
- **Cannot delete AIOrchestrator** while other services exist on the platform.  
- Special LOCAL/REMOTE install mode inference based on whether AIOrchestrator exists.

PlatformOps plan:

| Item | Action |
|------|--------|
| Catalog key | `ai-orchestrator` (aliases: `AIOrchestrator`, `cplatform` mapping already in settings) |
| dForm | Use full `AIOrchestrator` block from `dFormService.json` |
| Bootstrap | On **first cluster create** (or flag `bootstrap_orchestrator=true`): register AIOrchestrator service on first node **after** node exists — do **not** create fake `0.0.0.0` node. Prefer: create cluster empty → user adds real PEM node → optional “Bootstrap AIOrchestrator” **or** auto-add service row once first node is validated. **Default for parity:** auto-register AIOrchestrator (MANUAL by default) when first node is successfully created on a cluster that has none. |
| Lifecycle | `lifecycle_impact` / delete service: if service_key is ai-orchestrator and other services exist on same node/cluster → **409** with message matching cPlatform intent |
| Deploy | MANUAL register first; ANSIBLE only if image/contract defined and operator chooses |

This is **in scope** for the cluster page (not a separate product).

### 2.5 Live status

- API: use existing status/job paths; add or harden `GET /api/services/{id}/live-status` (or batch by node) that runs real docker inspect / `service_status` playbook when node reachable; **never invent healthy**.
- FE: while `activeView === clusters` and `selectedNode`, poll batch live status; paint pills; update `svc` counts.
- On poll failure: toast once (deduped) + show last-known with “stale” indicator.

---

## 3. Feature checklist (nothing missing vs cPlatform cluster)

### 3.1 Cluster list

| Feature | cPlatform | PlatformOps today | Work |
|---------|-----------|-------------------|------|
| Grid/cards with env, region, node/svc counts | Yes | Partial | Fix counts; hide seed/demo noise |
| Aggregate vCPU/mem when nodes have facts | Yes | Weak | After node facts stored |
| Create cluster wizard (identity → repo → registry → summary) | 4-step | Single modal with all fields | **Either** keep single form with sections **or** step wizard; both must hit same API |
| Test repo connection | Yes | API + button | Ensure button always visible + toast |
| Test registry connection | Yes | API + button | Same |
| Edit settings + secret mask/replace | Yes | Leave blank to keep | Match cPlatform “Replace” UX |
| Delete blocked if has nodes | Yes | lifecycle 409 | Surface impact in toast/modal |
| Open cluster → detail | Yes | Yes | Stabilize selection restore |

### 3.2 Node provision & lifecycle

| Feature | cPlatform | PlatformOps today | Work |
|---------|-----------|-------------------|------|
| Add node: host, user, PEM path **or** paste PEM | Yes | Partial (path + paste API) | Unify stepper + modal; file upload → private key save |
| CPU / GPU / Memory / Storage line | Yes | **Hardcoded UI defaults not saved** | Persist into `facts_json` on create/edit |
| docker_network + volume_root | Yes | Wired | Default platformops net |
| Validate / onboarding readiness | Yes | API exists | Stepper step 7 must always use real job output |
| Discover infra | Yes | Simplified | Upgrade scoring + external_id |
| Overview (spec sheet + status) | Yes | Partial | Real facts + connection report |
| Edit node | Yes | Modal | Include PEM replace, facts |
| Events timeline | Yes | Filtered events | Ensure node-scoped events always written |
| Delete blocked if services | Yes | lifecycle 409 | Clear UI message listing services |
| Launch/Teardown VM (Terraform) | Yes | Endpoints exist | **Phase C optional** — not required for “real PEM node” path |

### 3.3 Services

| Feature | cPlatform | PlatformOps today | Work |
|---------|-----------|-------------------|------|
| Catalog drawer (infra + app) | Yes | Yes | Group by kind/subsystem; infra first |
| Per-service parameter form | dForm rich | Flattened install-schema | Enrich schema; dynamic FE |
| MANUAL vs ANSIBLE install | Yes | Weak | Explicit field + code paths |
| Port expose + collision check | Yes | Basic DB check | Pre-submit call + optional live docker |
| Deploy / preflight / deps | Yes | Yes | End-to-end UI reliability |
| Live status dots | Yes | Static inventory status | Poll live |
| Uninstall with safety | Yes | force/policy | Honest 409 |
| Service events | Yes | Events bus | Link from card |
| Sidebar svc count per node | Yes | Yes | Refresh after every mutate/discover |
| external `SERV####` IDs | Yes | **Missing** | Allocate + display |

### 3.4 Discover / adopt

| Feature | cPlatform | PlatformOps today | Work |
|---------|-----------|-------------------|------|
| Ansible/local docker ps | Yes | Yes | Keep dual local/remote |
| Catalog + infra match score | High | Low | Port scoring logic |
| Adopt without redeploy | Yes | Yes if match | external_id + adopted flag |
| Skip already-registered containers | Yes | By container_name | Keep |
| Report scanned vs adopted | Yes | Yes | Better toast + drawer summary |

---

## 4. Implementation phases (ordered, verifiable)

Each phase ends with a **smoke checklist** and `npm run build` + API smoke. No phase claims done without real error paths tested.

### Phase 0 — Groundwork (docs + contracts only)

1. This document + feature inventory mapping table (done here).  
2. Architecture locked in §0a / §2 (IDs, toast, facts_json, network, full dForm, high-fi UI, AIOrchestrator).  
3. Verification target: SSH `ubuntu@65.2.63.24` + `/home/ubuntu/NODE1001.pem`; dTrain + AIOrchestrator on `platformops_prod_network`.  
4. Copy/reference `dFormService.json` path into PlatformOps catalog layout (on implement).  
5. **No product code** until plan approved.

**Exit:** plan approval.

---

### Phase 1 — Cluster identity & high-fidelity list/detail shell

**Backend**

- Confirm create/update/delete/list/summary/lifecycle-impact.
- Secret mask/replace already correct; add tests if missing.
- Ensure create always records lifecycle event.

**Frontend**

- **High-fidelity** list + detail shell (structure from cPlatform CSS/JS).  
- Create Cluster: wizard or sectioned modal; validation; typed toast; select new cluster.  
- Settings edit: replace-secret UX.  
- Delete cluster: lifecycle impact when blocked.  
- Typed toast system live for all cluster actions.  
- List cards: accurate node/service counts; empty state.

**Smoke**

1. Login `admin`/`admin` → Clusters  
2. Create cluster `ops-verify` → appears  
3. Edit name/region → persists  
4. Delete empty cluster → ok  
5. Re-create; detail shell navigable  

---

### Phase 2 — Real remote node provision (PEM + facts + network)

**Target node:** `65.2.63.24`, user `ubuntu` (confirm if different), key file `NODE1001.pem` / paste.

**Backend**

- `NodeCreate`/`NodeUpdate` accept facts: `cpu_cores`, `memory_gb`, `storage_gb`, `gpu`, `os` → `facts_json`.  
- PEM paste → `runtime/ssh_keys/node_{id}.pem` (chmod 600).  
- Default `docker_network=platformops_prod_network`.  
- `validate` / `connection` / `onboarding-readiness` real only.  
- After first successful node create on a cluster: **AIOrchestrator bootstrap** per §2.6 (MANUAL register default).

**Frontend**

- One provision path (drawer stepper aligned with cPlatform density).  
- Wire hardware fields into draft (fix dead defaults).  
- PEM: path **or** paste **or** file upload.  
- Pre-fill verification host/key path optional in dev docs only — not hardcode secrets in FE.  
- After create: validate + show real job log.  
- Actions: Overview / Edit / Events / Discover / Delete (Launch VM hidden).  
- Delete node blocked if services (including AIOrchestrator rule interactions).

**Smoke**

1. Add node `65.2.63.24` + PEM → row appears  
2. Spec sheet shows facts  
3. Validate via SSH succeeds or real error  
4. AIOrchestrator row present after bootstrap  
5. Delete empty secondary node works; node with services blocked  

---

### Phase 3 — SERV IDs + **full dForm** forms + MANUAL/ANSIBLE

**Backend**

- `external_id` column + backfill + `allocate_service_external_id`.  
- Import full `dFormService.json`; install-schema serves all types.  
- Type ↔ `service_key` alias map (include AIOrchestrator, dTrain, infra).  
- Port/name check before create (DB + optional live).  
- MANUAL vs ANSIBLE paths.  
- AIOrchestrator delete guard when siblings exist.

**Frontend**

- Catalog drawer high-fidelity; open dForm-driven form for **any** type.  
- Port check on submit; show `SERV####` on cards.  
- MANUAL vs ANSIBLE changes primary action.

**Smoke**

1. Open forms for multiple service types (not only one) — fields match dForm  
2. Register infra MANUAL → SERV id  
3. Port clash rejected  
4. ANSIBLE deploy job real output  
5. Cannot delete AIOrchestrator while other services exist  

---

### Phase 4 — Discover / adopt production path

**Backend**

- Scored matching (cPlatform ServiceConfig logic).  
- Adopt + external_id + adopted flag.  
- Structured report.

**Frontend**

- Discover → progress → toast → refresh svc counts.  
- Report unmatched containers.

**Smoke**

1. Against node `65.2.63.24` docker  
2. Adopt match; no duplicate on second discover  

---

### Phase 5 — Live status + events + lifecycle polish

**Backend**

- Live status with ~5s TTL cache.  
- Events always written.

**Frontend**

- Poll on Clusters + node selected.  
- Live pills; events panel; typed toasts only.

**Smoke**

1. Live green for running  
2. External stop → degraded/exited  
3. Lifecycle 409 messages clear  

---

### Phase 6 — dTrain + AIOrchestrator acceptance on platformops network

1. Cluster + remote PEM node ready.  
2. AIOrchestrator present (bootstrap or form).  
3. Discover/adopt deps or deploy from catalog.  
4. Deploy **dtrain-*** via ANSIBLE with local image tags.  
5. Live status honest.  
6. Write `docs/runbook-cluster-dtrain.md` with exact host/key path (no PEM body).  

**Exit criteria for “cluster page production-ready”:**

- [ ] Create cluster works (high-fi UI)  
- [ ] Add remote node with PEM works (`65.2.63.24` + NODE1001.pem)  
- [ ] Overview shows CPU/GPU/mem from facts  
- [ ] Node actions: overview/edit/events/discover/delete (safe)  
- [ ] Discover works; svc counts correct  
- [ ] Cannot delete node/cluster with children without force policy  
- [ ] Full dForm forms for all service types  
- [ ] MANUAL + ANSIBLE both work  
- [ ] Port expose collision check works  
- [ ] SERV IDs unique and stable  
- [ ] AIOrchestrator bootstrap + delete guard  
- [ ] Live status real  
- [ ] dTrain path on `platformops_prod_network`  
- [ ] Typed toasts production-grade  
- [ ] No dead buttons; Launch VM deferred/hidden  

---

## 5. Explicit non-goals (cluster plan)

| Non-goal | Why |
|----------|-----|
| Config Manager page work | Separate track |
| Diagnostics / Log Analyst | Separate track |
| GlitchTip / Performance pages | Separate track |
| Placement advisor product UI | Not required for cPlatform cluster path |
| Perfect drag-and-drop if catalog drawer works | Nice-to-have after forms solid |
| Terraform cloud VM as day-1 requirement | Real PEM nodes first; VM APIs stay for later phase |
| Changing docker network to share with cPlatform | Isolation is intentional |
| Fake seed data as “working demo” | Forbidden |

---

## 6. Risk register

| Risk | Mitigation |
|------|------------|
| SQLite schema change for `external_id` | Additive column + backfill `SERV{1000+id}` on boot |
| Full dFormService.json too large | Schema generator from catalog first; import dForm subset for dtrain/infra only |
| Stepper vs modal dual UI | One write path; deprecate dead controls |
| Local vs remote docker discover | Keep dual path; local_mode + host heuristics |
| Ansible missing on host | Real error toast; document install |
| dTrain image size / GPU | Use existing local tags; GPU optional in facts only |
| Scope creep into other pages | This doc is the gate |

---

## 7. Decisions — locked (see §0a)

Remaining optional detail (does not block start):

| Item | Current assumption |
|------|--------------------|
| SSH user on `65.2.63.24` | `ubuntu` |
| Auto-bootstrap AIOrchestrator | On first successful node create if cluster has none |
| PEM in repo | Never — only `/home/ubuntu/NODE1001.pem` or runtime upload |

---

## 8. File touch map (expected)

| Area | Files (primary) |
|------|-----------------|
| Docs | `docs/plan-cluster-page-production.md` (this), later `docs/runbook-cluster-dtrain.md` |
| Models/schemas | `models.py`, `schemas.py`, `db.py` backfill `external_id` |
| IDs + discover | NEW `orchestrator/ids.py`, `orchestrator/discovery.py` |
| dForm | `catalog/dform/dFormService.json`, schema normalizer, install-schema API |
| Service create/schema | `orchestrator/service/impl.py` (AIOrchestrator guards) |
| Routers | `clusters.py` bootstrap hooks, `nodes.py`, `services.py` live-status |
| FE state/actions | `useInventoryState.ts`, `useUiState.ts` toast, `inventory*Actions.ts` |
| FE views | `ClustersView.tsx` high-fi, `DrawersHost.tsx` dForm, `ModalsHost.tsx`, `App.tsx`/`styles.css` |
| CSS | port critical rules from `clusterDetail.css` / `cluster.css` |
| Catalog | `services.yaml` ai-orchestrator + dtrain image tags |

---

## 9. Relation to other plans

| Doc | Relation |
|-----|----------|
| `plan-next-cplatform-production.md` | Broader multi-surface plan; **Track A is replaced/detailed by this doc** |
| `features/cluster-page-detailed-features.md` | Inventory checklist; keep as reference |
| `cplatform-full-parity-specification.md` | Historical; cluster section superseded by this roadmap for execution |

---

## 10. Suggested commit cadence (when implementing)

1. `cluster: toast + cluster CRUD UX reliability`  
2. `cluster: node provision facts + PEM path`  
3. `cluster: external_id SERV allocation`  
4. `cluster: install form MANUAL/ANSIBLE + port check`  
5. `cluster: discover scoring + adopt`  
6. `cluster: live status poll`  
7. `cluster: dtrain e2e runbook`  

Author for commits: `himanshu-sharma-dev1 <himanshu-sharma-dev1@users.noreply.github.com>` per AGENTS.md.

---

*End of cluster production roadmap.*
