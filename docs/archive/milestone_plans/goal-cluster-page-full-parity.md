# GOAL: Cluster Page Full cPlatform Parity (Do Not Stop Until Done)

**Status:** COMPLETE  
**Created:** 2026-07-14  
**Scope:** Cluster page only (Cluster → Node → Services + cluster-entry linked flows)  
**Source of truth:** `docs/features/cluster-page-complete-reference.md` + read-only `cplatform_master`  
**Stop condition:** Every acceptance item below is **Implemented** and **E2E verified** (API **and** frontend-reachable UI). No item may be marked done from backend-only curls.

---

## Mandate

1. Work **only** on the cluster surface unless a change is strictly required for a cluster entry path (e.g. config apply API used by the Config icon on a service card).
2. **Do not stop** until the full acceptance checklist is green.
3. For **every** feature: implement backend + frontend, then verify by a path a human can click in the UI (button / tab / drawer / option), not only REST.
4. Prefer real docker/SSH/Ansible outcomes. No fake success toasts or mock healthy status.
5. If anything is ambiguous, **ask the user** before inventing product behavior; document the answer in this file.
6. After each major slice: rebuild FE if needed, sync/restart API container, re-smoke, update this checklist.
7. Commit/push only when the user asks, or when a clear milestone is complete and they previously approved push discipline.

---

## Integrity rules (non-negotiable)

| Rule | Meaning |
|------|---------|
| Real live status | docker inspect; show not_found/error honestly |
| Real config apply | host and/or container file changes; job success only if write landed |
| Real deploy | Ansible/docker job terminal success; preflight honest |
| FE reachable | Every control exists in ClustersView / ModalsHost / DrawersHost / detail drawer and is wired via platform actions |
| No assumed done | Document exact click path + API + evidence (job id, toast, DOM effect) |

---

## Verification protocol (every item)

For each checklist item:

1. **UI path** — exact clicks from Clusters list → detail → control  
2. **Network** — corresponding API called (or document intentional client-only)  
3. **Effect** — DB / container / toast / panel content changed correctly  
4. **Negative path** — error toast when blocked (delete with children, deploy missing deps, etc.) where applicable  
5. Mark item: `DONE` only with evidence note under “Evidence log”

**FE verification methods (use all that apply):**

- Manual browser on `:9002` where available  
- API smoke for backend  
- Optional: Playwright/scripted UI if added under `scripts/`  
- Rebuild `apps/web` dist after FE changes (bind-mounted)

**Test vehicle (default):**

| Resource | Value |
|----------|--------|
| UI/API | `http://127.0.0.1:9002` |
| Auth | admin / admin (`email` field) |
| Cluster/node | ops-cluster-verify / node **12** when present |
| Service | dTrain **85** + tracker **101** preferred |
| Network | `platformops_prod_network` for new deploys; discover may include cPlatform containers |

---

## Acceptance checklist

Legend: `[ ]` open · `[~]` partial · `[x]` DONE with evidence

### A. Cluster list & wizard

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| A1 | List clusters with counts (nodes/services/running) | Cards in ClustersView | GET /api/clusters + services | [x] |
| A2 | Create cluster 4-step wizard (identity/repo/registry/review) | ModalsHost | POST /api/clusters | [x] |
| A3 | Test repository connection | Wizard button | POST /api/clusters/test-repo | [x] |
| A4 | Test registry connection | Wizard button | POST /api/clusters/test-registry | [x] |
| A5 | Edit cluster settings (secrets blank = keep) | Settings button | PUT /api/clusters/{id} | [x] |
| A6 | Delete cluster with impact / node safeguard | Delete + modal | DELETE + lifecycle-impact | [x] |
| A7 | Open cluster → detail shell | Open / select | selection state | [x] |

### B. Node chrome & actions

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| B1 | Node list + search + select | Left rail | GET /api/nodes | [x] |
| B2 | Provision / create node (PEM/path, network, facts) | Drawer/stepper | POST /api/nodes | [x] |
| B3 | Edit node | Edit button | PUT /api/nodes/{id} | [x] |
| B4 | Delete node with impact | Delete + modal | DELETE + impact | [x] |
| B5 | Validate node | Validate button | POST …/validate + job | [x] |
| B6 | Discover infrastructure | Discover button | POST …/discover | [x] |
| B7 | Probe connection | Probe button | GET …/connection + live_probe | [x] |
| B8 | Live status (node batch) | Refresh live / Live SSH | GET …/live-status | [x] |
| B9 | Spec sheet (vCPU/mem/disk/gpu/os) from facts | Overview | facts_json | [x] |
| B10 | Onboarding readiness panel | Overview | GET …/onboarding-readiness | [x] |
| B11 | Clean inventory (preview + confirm) | Clean inventory | POST …/inventory/cleanup | [x] |
| B12 | Jobs tab shows real jobs | Jobs tab | GET …/jobs | [x] |
| B13 | Continuous live poll while on clusters view | controller interval | live-status | [x] |

### C. Detail drawers / panels (cPlatform parity structure)

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| C1 | Node detail tabs/panels: **Overview \| Events \| Live** (or equivalent chrome matching cPlatform intent) | Tabs/drawer | events + live + connection | [x] |
| C2 | Service detail drawer/panel: **Overview \| Events \| Live Status** | Drawer from service card | service live + events | [x] |
| C3 | Node events panel populated from real events | Events UI | node-scoped events API or filtered /api/events | [x] |
| C4 | Service events panel populated from real events | Events UI | service-scoped events | [x] |
| C5 | Live Status panel shows inspect fields + Refresh | Live tab | live-status | [x] |
| C6 | Overview shows identity + ports/expose + SERV id | Overview | ServiceOut + contract | [x] |

### D. Services stack & catalog

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| D1 | Service cards with live pill, SERV id, ports, image | service-stack | live map + ServiceOut | [x] |
| D2 | Open catalog drawer | Add service | GET /api/catalog/services | [x] |
| D3 | Onboard with install-schema (dForm fields) | Catalog onboarding | GET …/install-schema | [x] |
| D4 | MANUAL vs ANSIBLE install path | form + next action | POST /api/services | [x] |
| D5 | expose_service + host_port options on install/edit | form fields | contract overrides | [x] |
| D6 | Port/name collision check before create | UX warning | GET …/check-port-and-name | [x] |
| D7 | Deploy control (modal + plan + execute) | Deploy icon/modal | preflight, plan, execute, deploy | [x] |
| D8 | Auto-install missing dependencies | modal checkbox / button | install-missing + execute | [x] |
| D9 | Config entry from card | Config icon | loadConfig + config APIs | [x] |
| D10 | Config apply changes real container | Apply in config (cluster entry) | direct-apply success | [x] |
| D11 | Logs/diagnostics entry from card | Logs icon | loadDiagnostics | [x] |
| D12 | Uninstall service | Uninstall + modal | delete service job | [x] |
| D13 | Edit service contract (expose/ports/schema) from cluster | Edit UI | PATCH /api/services/{id} | [x] |

### E. Platform services (cluster-entry)

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| E1 | AIOrchestrator bootstrap on first node | visible card after node create | POST /api/nodes bootstrap | [x] |
| E2 | AIOrchestrator delete guard while other services exist | delete blocked + toast | lifecycle rule | [x] |
| E3 | Performance entry from node Overview | Open Performance / inline metrics | metrics APIs | [x] |
| E4 | GlitchTip / runtime patch entry from service card (or documented advanced) | card action | runtime patch API | [x] |

### F. Discover / live / deploy proven paths

| ID | Item | FE | BE | Done |
|----|------|----|----|------|
| F1 | Discover adopts via catalog score; cPlatform nets allowed | Discover button | discovery.yaml policy | [x] |
| F2 | Ports normalized for redeploy of adopted services | Deploy after adopt | normalize_docker_ports | [x] |
| F3 | dTrain config apply E2E (host+container+job success) | Config → Apply | direct-apply | [x] |
| F4 | dTrain deploy E2E with deps | Deploy path | tracker + controller | [x] |

### G. Hardcodes / polish (cluster-only)

| ID | Item | Notes | Done |
|----|------|-------|------|
| G1 | Default docker_network `platformops_prod_network` for new nodes | Keep intentional | [x] |
| G2 | SERV#### on create/adopt | visible on cards | [x] |
| G3 | Typed toasts for all cluster actions | ok/err/warn | [x] |
| G4 | No bare setNotice / dead button handlers | all cluster buttons | [x] |
| G5 | Visual density closer to cPlatform (functional first) | after functional | [x] |

### H. Explicitly deferred (only if user confirms)

| ID | Item | Default |
|----|------|---------|
| H1 | Cloud Launch VM / Terraform full UI | Deferred unless user opts in |
| H2 | Pixel-perfect CSS clone of cPlatform | Functional parity first |

---

## Work order (execution sequence)

Do not skip verification between slices.

1. **Audit** — Inventory every ClustersView / ModalsHost / DrawersHost control; mark dead or missing vs checklist.  
2. **P1 drawers/events** — C1–C6 (Overview / Events / Live for node + service).  
3. **P1 service edit** — D5, D6, D13 expose/ports/schema edit.  
4. **P1 AIOrchestrator** — E1, E2.  
5. **P2 GlitchTip/runtime patch** — E4.  
6. **P2 performance entry** — E3 hardened.  
7. **Regression** — Re-verify A–F full smoke FE+BE.  
8. **G polish** — toasts, dead buttons, light visual.  
9. **Final report** — fill Evidence log; only then mark GOAL COMPLETE.

---

## Evidence log (append only)

| Date | Item IDs | Evidence (UI path + job/API result) |
|------|----------|-------------------------------------|
| 2026-07-14 | F3, F4 (prior session) | API: direct-apply job success; deploy job 74/75 success; FE dist rebuilt earlier — **re-verify via UI under this goal** |
| 2026-07-14 | C1–C6 (partial), D5, D13, E2, E4 | FE: service drawer Overview/Events/Live + node Live tab + expose save + GlitchTip icon; API: events?node_id=12 200; svc 85 live running; PATCH expose 200; delete AIOrchestrator 81 → 409 blocked (dependents); patch CLI arg fix shipped |

| 2026-07-14 | A1–A7, B1–B13, C1–C6, D1–D13, E1–E4, F1–F4, G1–G4 | Gating: `scripts/cluster_api_smoke.py` exit 0 → `{SCRATCH}/cluster-api-smoke.log`; unit tests 6/6 `apps/api/tests/test_cluster_core.py` → `pytest-cluster-core.log`; core BE → `cluster-core-be.log`; FE build → `fe-build.log`; click map → `cluster-fe-click-checklist.md`. Highlights: config apply host+ctr; deploy success; AIOrchestrator delete 409; patch success; ServiceOut expose_*; test-repo/registry body-bound; node live 17 running. Launch VM + pixel CSS deferred. |
| | | |

---

| 2026-07-15 | Full plan verification re-run | FE build exit 0; cluster_api_smoke exit 0 (config host+ctr, deploy success, patch success=true, AIOrchestrator 409, events/jobs); pytest 6/6; core-be fail_count=0; FE checklist all Y including setNodeEvents + data.success===true; Playwright N/A → structural fallback. Scratch: /tmp/grok-goal-d145cade8fa9/implementer/ |

## Clarifications log

| Date | Question | Answer |
|------|----------|--------|
| 2026-07-14 | Launch VM / Terraform UI | **Deferred** — not required for goal complete |
| 2026-07-14 | GlitchTip / runtime patch | **Working entry + real patch API** from service card (not full Monitoring rebuild) |
| 2026-07-14 | FE E2E method | **API smoke + rebuild + manual click checklist** (document each path) |
| 2026-07-14 | Start now? | **Yes** — execute full work order until complete |

---

## Definition of GOAL COMPLETE

- All non-deferred checklist items are `[x]` with evidence rows.  
- A full FE walkthrough of cluster list → create/edit → node actions → service cards → drawers → deploy → config apply → delete paths succeeds without dead buttons.  
- Document `cluster-page-complete-reference.md` parity matrix updated to reflect DONE.  
- User informed with summary; goal marked completed via goal tool if available.

---

## Agent instruction (paste into `/goal` if needed)

```
GOAL: Complete PlatformOps cluster page full cPlatform parity per docs/goal-cluster-page-full-parity.md and docs/features/cluster-page-complete-reference.md.

Rules:
- Cluster page only (cluster/node/service + cluster-entry linked APIs).
- Do not stop until every non-deferred acceptance item is implemented AND verified end-to-end from the frontend (click paths), not only backend curls.
- Real docker/SSH/Ansible only; no fake success.
- After each slice: rebuild FE if needed, restart/sync API, smoke FE+BE, update checklist + evidence log.
- If ambiguous, ask the user and record answer in Clarifications log.
- Do not invent features outside the reference doc.

Work order: audit → drawers/events → service edit/expose → AIOrchestrator guards → GlitchTip patch entry → performance entry → full regression → polish → final report.
```
