# Part A — Cluster page hardening (analysis → plan → implement)

**Status:** complete (A1–A10 implemented + verified)  
**Parent:** `docs/plan-cluster-page-production.md`  
**Date:** 2026-07-10

---

## 1. Analysis (code-backed)

| # | Gap | Root cause | Evidence |
|---|-----|------------|----------|
| A1 | Validate job "Callback error: Instance Node not bound" | `on_complete` closed over ORM `node`; after request session ends, accessing attributes can fail | `orchestrator/node.py` `validate_node` + `tasks.run_job_async` |
| A2 | Validate **wipes** operator facts | `bg_node.facts_json = json.dumps(facts)` replaces whole dict | Same callback |
| A3 | Connection report stuck on `facts-only` | No live SSH probe; only last validate job status | `get_node_connection_report` |
| A4 | Live status local-only | `_docker_inspect_local` only | `service/impl.py` live status |
| A5 | Port check DB-only | `check_port_and_name_availability` ignores live docker ports | same file |
| A6 | Cluster create not true wizard | All 4 tabs always "active"; single scroll form | `ModalsHost.tsx` |
| A7 | High-fi UI incomplete | Structure exists; density/status/connection chrome incomplete | `ClustersView` + CSS |
| A8 | Image not rebuilt | API code docker-cp'd into container | compose Dockerfile |
| A9 | Discover / inventory noise | Historical over-adopt; optional cleanup endpoint or docs | Phase 4 improved re-run |
| A10 | Full ansible deploy all types | Catalog-dependent; not blocked by Part A core | defer except smoke path |

---

## 2. Implementation order

1. **A1+A2** Fix validate callback + merge facts + capture node_id  
2. **A3** Live SSH probe in connection report (+ TCP docker optional)  
3. **A4** Remote docker inspect for live status  
4. **A5** Live port collision check  
5. **A6** Cluster 4-step wizard  
6. **A7** Cluster detail UX: connection badge, live counts, denser actions  
7. **A8** Rebuild web-api image if feasible  
8. Smoke + commit + push  

---

## 3. Acceptance

- Validate node job completes **without** callback error; status healthy/unreachable  
- Operator facts (cpu/mem) preserved after validate  
- Connection report can show **ssh-ok** / **validated** after real probe  
- Live status works with source `docker_inspect` or `docker_inspect_ssh`  
- Port check reports live host port collisions when docker available  
- Create cluster walks steps 1→4  
- FE build green; API health 200  
- Inventory cleanup dry-run + apply (noise/foreign/stale/duplicates)  
- Detail tabs: overview / services / events / jobs  
- Live status via `?via=ssh`  
- ANSIBLE deploy job path uses detached-safe service_id  

## 4. Rest of Part A (completed)

| Item | Implementation |
|------|----------------|
| A9 inventory noise | `POST /api/nodes/{id}/inventory/cleanup` + Clean inventory UI |
| A7 high-fi tabs | overview/services/events/jobs + node row live counts |
| A4 remote force | `GET .../live-status?via=ssh` + Live SSH button |
| A10 deploy safety | deploy_service captures service_id before async callback |
