# Manual Test Suite — PlatformOps Cluster Page (Browser-first)

**Purpose:** Walk every DevOps path you care about after the two goals (functional full-parity + cPlatform UX structure).  
**Who:** You (operator), browser + optional DevTools Network tab.  
**When:** After FE rebuild / hard refresh, or any deploy/config change.

**Related goals**
- Functional: `docs/goal-cluster-page-full-parity.md` (COMPLETE)
- UX structure: `docs/goal-cluster-page-cplatform-ux-clone.md`
- API smoke (optional backup): `python3 scripts/cluster_api_smoke.py`

---

## 0. Prep (5 minutes)

### 0.1 Stack

| Item | Value |
|------|--------|
| URL | **http://127.0.0.1:9002** (or your host) |
| Login | **Username/email field:** `admin` · **Password:** `admin` |
| Primary cluster | **ops-cluster-verify** (id 10) |
| Primary node (proven) | **verify-node-1** · `65.2.63.24` · env `aws` |
| Secondary node | **node-54-183-53-93** · `54.183.53.93` · env `aws` |
| Default docker network | `platformops_prod_network` |

### 0.2 Browser setup

1. Open a **private/incognito** window (clean state) **or** hard-refresh: `Ctrl+Shift+R` / `Cmd+Shift+R`.
2. Open **DevTools → Network**. Filter: `Fetch/XHR`. Keep it open for every section.
3. Optional: **Console** — note red errors (copy for bugs).
4. Score sheet: print or copy the **Scorecard** at the bottom; mark **PASS / FAIL / SKIP** + notes.

### 0.3 Pass criteria (every case)

| Check | Meaning |
|-------|---------|
| **UI** | Control exists, clickable, correct drawer/modal/tab opens |
| **Network** | Expected API called (status 200/4xx as designed, not silent 401/500) |
| **Effect** | Toast / job status / list content / container state matches reality |
| **No fake success** | Failed jobs show err toast; live shows not_found/error honestly |

### 0.4 Safety

| Do freely | Avoid unless intentional |
|-----------|---------------------------|
| Discover, Validate, Probe, Live refresh, open drawers, test-repo/registry | Delete **cluster** with real nodes |
| Deploy / config on a **test service** you can rebuild | Uninstall **AIOrchestrator** while other services exist (expect **block**) |
| Clean inventory **dry-run** | Force-delete production data without note |

---

## 1. Login & shell (T01–T04)

| ID | Steps | Expected | Network (approx) | P/F |
|----|-------|----------|------------------|-----|
| **T01** | Open `/`. See login. | No auto API spam flood of `401` every second on login screen | Minimal/no unauth poll storm | |
| **T02** | Email=`admin`, password=`admin` → Sign in | Lands on Clusters (or dashboard → Clusters) | `POST /api/auth/login` **200** + token | |
| **T03** | Wrong password once | Error message; stay on login | 401/403; no crash | |
| **T04** | Correct login again | Clusters list loads | `GET /api/clusters`, `/api/nodes`, `/api/services`, catalog | |

**If T01 fails:** unauth poll regression — stop and fix before other tests.

---

## 2. Cluster list & wizard UX (T10–T19)

| ID | Steps | Expected | Network | P/F |
|----|-------|----------|---------|-----|
| **T10** | Clusters list | Cards with name, env pill, region, node/service/running counts | `GET /api/clusters` (+ nodes/services) | |
| **T11** | Type in **Search clusters** | Cards filter live; dashed **Add cluster** still visible | Client-only | |
| **T12** | Click **Create Cluster** (header or dashed card) | **Right drawer** opens (not only centered modal); steps Identity → Repository → Image store → Review | — | |
| **T13** | Step 1: name `manual-test-cl`, region, env, optional description → Next | Advances; name required if empty (error) | — | |
| **T14** | Step 2: leave empty repo URL → **Test repository** | Button spinner; inline result **testing/ok/err**; toast | `POST /api/clusters/test-repo` (may 400 if no git — still “wired”) | |
| **T15** | Step 3: registry → **Test registry** | Spinner + inline result; toast | `POST /api/clusters/test-registry` | |
| **T16** | Step 4 Review → **Create cluster** | Drawer busy/spinner; closes; toast ok; new card appears | `POST /api/clusters` **200** | |
| **T17** | Card **Settings** on existing cluster | Same drawer, **EDIT** badge; secrets “Replace secret” | `PUT` only on save | |
| **T18** | Edit: change description or region → Save | Toast ok; card updates | `PUT /api/clusters/{id}` | |
| **T19** | **Open cluster** on `ops-cluster-verify` | Detail shell: band + 2-col node list / detail | selection + loads | |

**Cleanup optional:** delete `manual-test-cl` later via Delete (only if empty of nodes).

---

## 3. Cluster detail shell & toolbar (T20–T28)

Use **ops-cluster-verify**.

| ID | Steps | Expected | Network | P/F |
|----|-------|----------|---------|-----|
| **T20** | Left **Nodes** list | Shows **verify-node-1** and **node-54-183-53-93** (selectable) | `GET /api/nodes` | |
| **T21** | Search nodes box | Filters node rows | Client-only | |
| **T22** | Click **verify-node-1** | Right pane fills; row active | May load connection/onboarding | |
| **T23** | Toolbar order | **Overview · Edit · Events · Discover · Launch · Delete** (+ Validate/Probe/Live as extras) | — | |
| **T24** | Spec sheet | vCPU / Mem / Storage / GPU / OS / Status from facts | — | |
| **T25** | **Overview** toolbar button | Opens **node info drawer** Overview \| Events \| Live | events/live optional fetch | |
| **T26** | **Events** toolbar | Node info drawer Events tab; status line “Loading…/Loaded N” | `GET /api/events?node_id=…` | |
| **T27** | **Launch** | **Stub drawer** “not configured” + link to provision | No Terraform | |
| **T28** | **All clusters** back | Returns to list | — | |

**Known bug check:** If `verify-node-1` missing from list, hard-refresh (seed filter fix must be in current dist).

---

## 4. Node actions — validate / discover / probe / live (T30–T39)

Select **verify-node-1** (`65.2.63.24`). SSH/PEM must work.

| ID | Steps | Expected | Network / effect | P/F |
|----|-------|----------|------------------|-----|
| **T30** | **Validate** | Button spinner; toast warn then ok/err; Jobs tab gets entry | `POST /api/nodes/{id}/validate` → job poll | |
| **T31** | Open **Jobs** tab | Real job list with status pills | `GET /api/nodes/{id}/jobs` | |
| **T32** | **Discover** | Spinner; toast with scanned/adopted counts | `POST /api/nodes/{id}/discover` **200** | |
| **T33** | After Discover | Service stack updates (new adopted cards if any) | refresh services | |
| **T34** | **Probe** | Connection banner: ssh/docker state | `GET /api/nodes/{id}/connection` | |
| **T35** | **Live SSH** / Refresh live | Wait (can be **10–20s**); running counts update | `GET …/live-status` | |
| **T36** | **Live status** tab | Main grid of containers + **dependencies table** | live-status | |
| **T37** | Loading shells | While loading, pulse/dot shell visible (not blank freeze) | — | |
| **T38** | **Clean inventory** → cancel | Dry-run preview; cancel does not delete | cleanup dryRun | |
| **T39** | Select **node-54-183-53-93** | Same chrome; Probe/Validate/Discover (may fail if host unreachable — **err toast required**, not hang forever) | same APIs | |

**Pass rule for T39:** Honest failure is PASS; silent hang is FAIL.

---

## 5. Service cards & service drawer (T40–T49)

On **verify-node-1** with services present (e.g. dTrain).

| ID | Steps | Expected | Network | P/F |
|----|-------|----------|---------|-----|
| **T40** | Service cards | Name, kind, SERV#### or external_id, ports, image, status pill | live map | |
| **T41** | Click card body | **Wide info drawer** Overview \| Events \| Live Status | events + live | |
| **T42** | Overview | Container, image, kind, status, ports; expose checkbox + host port | — | |
| **T43** | Toggle expose + port → Save network | Toast; drawer updates | `PATCH /api/services/{id}` | |
| **T44** | **Events** tab | Status line + list or empty honest | `GET /api/events?service_id=` | |
| **T45** | **Live Status** tab → Refresh | overall/state/restarts/checked; deps table | `GET …/live-status` | |
| **T46** | Foot: **Close** | Drawer closes | — | |
| **T47** | Foot: **Edit** | Install/config drawer (schema) | install-schema | |
| **T48** | Foot: **Patch** | Spinner; toast ok/err (only success if `success:true`) | PatchObservability | |
| **T49** | Card icons: Logs, Config, Deploy, Uninstall | Navigate / open correct surface | diagnostics / config / deploy modal / delete modal | |

---

## 6. Catalog → install → deploy (T50–T59)

| ID | Steps | Expected | Network | P/F |
|----|-------|----------|---------|-----|
| **T50** | **Add service** | Catalog drawer right; search + category chips | `GET /api/catalog/services` | |
| **T51** | Search `dtrain` or `redis` | List filters | client | |
| **T52** | Click a **non-critical** catalog card | Catalog closes; **Install/configure drawer** opens (dForm fields) | install-schema | |
| **T53** | Target node = verify-node-1; set MANUAL or ANSIBLE; fill required fields | Schema sections render | — | |
| **T54** | Register / Save | Busy spinner; toast; service appears on stack | `POST /api/services` or PATCH | |
| **T55** | If ANSIBLE + Deploy next action | Deployment modal opens with plan/preflight | plan + preflight | |
| **T56** | Deployment modal: **Execute plan** | Button **spinner + disabled**; modal shows executing | execute/deploy APIs | |
| **T57** | Wait for job terminal | Toast ok; Jobs tab shows success/fail honestly | `GET /api/jobs/{id}` | |
| **T58** | Card shows **installing** shimmer while job running (if status/job in flight) | Visual cue | — | |
| **T59** | Deploy without node selected (if possible) or blocked path | **Action blocker** modal (single overlay, not double) | blocker only | |

**Suggested safe first deploy:** small infra card (e.g. redis) if not already present — not a second AIOrchestrator.

---

## 7. Config apply (real) (T60–T64)

Pick a **configurable** service (dTrain controller preferred if present).

| ID | Steps | Expected | Network / effect | P/F |
|----|-------|----------|------------------|-----|
| **T60** | Card **Config** icon | Config page opens for that service | config workspace APIs | |
| **T61** | Load / view content | Editor shows real content or empty with message | `GET …/config` | |
| **T62** | Make a **small safe** change (comment or known key) → Apply / direct-apply | Job success toast | apply/direct-apply **200** success | |
| **T63** | Confirm on host (optional CLI) | File on node volume updated | e.g. docker exec cat config | |
| **T64** | Back to Clusters → same service Live | Still running after apply | live-status | |

**If no dTrain:** use any service with `configurable` and document skip if apply disabled.

---

## 8. Events after mutations (T70–T73)

| ID | Steps | Expected | P/F |
|----|-------|----------|-----|
| **T70** | Open node **Events** tab (loaded) | Status “Loaded N” | |
| **T71** | Keep Events open → run **Discover** | Events list/status **refreshes** (tick) | |
| **T72** | Service drawer Events open → **Deploy** small change or re-execute if safe | Events refresh after mutation | |
| **T73** | Toasts | ok / err / warn colors; auto-dismiss ~3s | |

---

## 9. Delete & guards (T80–T84)

| ID | Steps | Expected | Network | P/F |
|----|-------|----------|---------|-----|
| **T80** | Uninstall a **throwaway** service (not AIOrchestrator) | Confirm modal; impact; job or success toast | delete + impact | |
| **T81** | Try uninstall **AIOrchestrator** (if present with dependents) | **Blocked** — 409 / toast err; **not** deleted | lifecycle | |
| **T82** | Delete empty test cluster only | Works if no nodes / impact allows | DELETE cluster | |
| **T83** | Delete node with services | Impact modal; blocked or force path clear | impact API | |
| **T84** | Single action-blocker only | Never two stacked dim overlays | — | |

---

## 10. Provision node drawer (T90–T93)

| ID | Steps | Expected | P/F |
|----|-------|----------|-----|
| **T90** | **Provision node** | Stepper drawer (multi-step) | |
| **T91** | Fill name/host/PEM path or paste PEM → through steps to Review | Review shows values | |
| **T92** | Optional: **do not** Launch on prod unless intentional | Cancel closes cleanly | |
| **T93** | Launch path (optional full) | Validation job console step | |

---

## 11. UX structure checklist (quick) (T100–T108)

| ID | Check | P/F |
|----|-------|-----|
| **T100** | Create/edit = **right drawer**, 4 steps | |
| **T101** | Button loading on Discover / Validate / Save / Test / Deploy execute | |
| **T102** | Drawer body `busy` during submit | |
| **T103** | Pane loading shell on Events/Live first load | |
| **T104** | Typed toasts ok/err/warn | |
| **T105** | Catalog search + chips | |
| **T106** | Shared info drawer node + service | |
| **T107** | Launch = stub only | |
| **T108** | Config deep-link only (no full rebuild required) | |

---

## 12. Negative / chaos tests (T110–T115)

| ID | Steps | Expected | P/F |
|----|-------|----------|-----|
| **T110** | Disconnect network mid-Discover | Err toast; UI recoverable | |
| **T111** | Double-click Deploy execute | No double job storm (busy disables) | |
| **T112** | Open 3 drawers/modals sequence | Only one primary overlay; z-index sane | |
| **T113** | Login, wait 5 min on Clusters | Live poll continues **with** token; no 401 spam | |
| **T114** | Hard refresh mid-cluster detail | Session restores or re-login; no blank crash | |
| **T115** | Invalid PEM node Probe | Clear fail; not infinite spinner | |

---

## 13. Optional API backup (same machine)

If browser looks wrong, confirm backend still green:

```bash
cd /home/ubuntu/PlatformOps
python3 scripts/cluster_api_smoke.py
# expect exit 0: discover, live, dTrain apply, deploy, patch, AIOrchestrator 409
```

```bash
cd /home/ubuntu/PlatformOps/apps/web && npm run test:ux   # UX helper unit tests
```

---

## 14. Recommended order (≈ 60–90 min full pass)

| Block | Time | Focus |
|-------|------|--------|
| 1. Prep + Login | 5m | T01–T04 |
| 2. List + wizard | 10m | T10–T19 |
| 3. Detail + nodes | 10m | T20–T28, T30–T37 |
| 4. Services + drawer | 10m | T40–T49 |
| 5. Catalog + deploy | 15m | T50–T59 |
| 6. Config apply | 10m | T60–T64 |
| 7. Events + deletes | 10m | T70–T73, T80–T84 |
| 8. UX + chaos | 10m | T100–T115 |

**Smoke-only (15 min):** T01–T02, T10, T19–T22, T30, T32, T35, T40–T45, T50–T52, T56–T57 (if already registered), T81, T100–T107.

---

## 15. Scorecard (copy for your run)

| Date | Tester | Build/dist hash or time | |
|------|--------|-------------------------|---|
| | | | |

| Suite | Pass | Fail | Skip | Notes |
|-------|------|------|------|-------|
| Login | | | | |
| Cluster list/wizard | | | | |
| Detail shell | | | | |
| Node actions | | | | |
| Service drawer | | | | |
| Catalog/deploy | | | | |
| Config | | | | |
| Events refresh | | | | |
| Deletes/guards | | | | |
| UX structure | | | | |
| Chaos | | | | |

**Overall:** ☐ GO (ready for feature work) · ☐ NO-GO (list failing IDs)

### Top failures to log

| ID | What you saw | Network status | Screenshot? |
|----|--------------|----------------|-------------|
| | | | |

---

## 16. What to do after testing

| Result | Next action |
|--------|-------------|
| **All smoke PASS** | Stop open-ended clone; start **your** product features on PlatformOps |
| **FAIL only on secondary node (54.x)** | PEM/network/security group — not platform core |
| **FAIL Discover/Deploy on verify-node** | Backend/SSH — use `cluster_api_smoke.py` + job output |
| **FAIL only UX (spinner/drawer)** | FE-only fix; rebuild `apps/web` + hard refresh |
| **FAIL login/401 poll** | Auth/session gate — fix before everything else |

---

## 17. Quick map: goal → test IDs

| Goal area | Test IDs |
|-----------|----------|
| Full functional parity (A–G) | T10–T19, T20–T39, T40–T64, T80–T84 |
| UX clone (drawers, busy, toasts, catalog, launch stub) | T12–T15, T25–T27, T37, T50–T52, T56, T59, T100–T108 |
| Multi-node reality | T20, T39 |
| Integrity (no fake success) | T30, T57, T62, T81, T115 |

---

*End of suite. Run smoke-only before demos; full suite after any cluster/deploy/config change.*
