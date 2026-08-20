# Next plan: cPlatform production readiness (only)

**As of:** post-`cdf41b8` (Phase 2b decomposition done)  
**Login:** `admin` / `admin`  
**Criterion:** work only on **cPlatform-parity capabilities** already in PlatformOps. Make them **production-ready and working on a real path**. Do **not** add PlatformOps-only product extras.

---

## 0. Baseline (do not re-litigate)

| Layer | State |
|-------|--------|
| **FE split** | Done — thin controller, domain state + actions |
| **Views** | Clusters, Config, Diagnostics, Monitoring, Performance, Users, Advanced (Topology/Policy/Audit/Reliability), Observability stack |
| **API** | Auth boundary, multiuser, LLM/Log Analyst, GlitchTip routes, inventory/config/diagnostics |
| **Integrity rule** | Real-only: no fake success, empty metrics when Prom/Loki empty, real API errors |

**Decomposition is closed.** Next work is **parity hardening + real-server proof**, not more file splitting or net-new product areas.

---

## 1. In scope = cPlatform core surfaces only

These match cPlatform’s main operator pages and the Phase A multiuser/Log Analyst port.

| # | cPlatform surface | PlatformOps surface | Goal |
|---|-------------------|---------------------|------|
| **1** | Cluster list + detail (`02-clusters`, `04-cluster-detail`) | **Clusters** + tree + catalog drawer | CRUD cluster/node/service, discover/adopt, deploy, lifecycle safety, live status |
| **2** | Config Manager (`08-config-manager`) | **Config Manager** | Live load, snapshot, drift, apply, compare, rename/restore, migration path that works end-to-end |
| **3** | Service Monitoring / GlitchTip (`Monitoring.html`) | **Monitoring** + GlitchTip workspace | Issues, event detail, resolve/ignore, uptime, patch observability — real when GlitchTip configured; honest empty when not |
| **4** | System Monitoring (`SystemMonitoring.html`) | **Performance** | Node CPU/mem/disk, process table, windows, auto-refresh; empty when exporters/Prom missing |
| **5** | Diagnostics & Log Analyst (`09-diagnostics`) | **Diagnostics** + Log Analyst chat | Targets, summary, live/history, archives/backfill, LLM chat with evidence (no canned answers) |
| **6** | Users / invite / roles | **Users** + login session | Admin invite/CRUD/roles; last-visited; sessions (already largely present — polish + smoke) |
| **7** | Observability plane (Prom/Loki/Alloy ops) | **Observability stack** | Bootstrap/status/deploy-teardown on node when used by diagnostics/monitoring |

### Explicitly **out of scope** for this plan (PlatformOps extras / not required for cPlatform prod path)

Do **not** prioritize as new work unless they block a core surface above:

| Exclude | Why |
|---------|-----|
| Standalone **Secrets vault** product panel | Not a primary cPlatform page; cluster registry password **mask/replace** in cluster editor is enough for parity |
| **Placement planner** as a separate product | cPlatform deploys onto chosen node/catalog flow; do not build a new advisor UI unless deploy path needs it |
| **DTrain overview** ML card | Secondary; only if validating a real dtrain deploy on the happy path |
| **Capacity reports** as its own Reliability feature push | Cluster/node resource display on Clusters/Performance is enough unless already broken |
| **Artifacts viewer** as a new panel | Nice-to-have; inventory/compose already generated under the hood |
| **Releases timeline** as a net-new product | Only if cPlatform release-approval is already half-wired **and** blocking Clusters deploy parity — otherwise defer |
| New main-nav product areas (Dataflow, MLOps registry, etc.) | Explicit non-goal |
| More FE decomposition for its own sake | Done |

---

## 2. Production-ready definition (every in-scope surface)

For each surface, “production-ready” means:

1. **Operator can complete the cPlatform workflow** without knowing internal APIs.  
2. **Real backend only** — failures show real errors; no mock success toasts.  
3. **Empty states are honest** when Prom/Loki/GlitchTip/LLM are down or unconfigured.  
4. **Smoke script / checklist** for that surface passes on this host.  
5. **No dead buttons** that look enabled but no-op or lie.

---

## 3. Work tracks (ordered)

### Track A — Clusters (cPlatform cluster/detail) — **first**

> **Detailed execution plan (architecture, phases 0–6, dTrain proof, ID allocation, toast UX):**  
> **`docs/plan-cluster-page-production.md`** — use that as the source of truth for Track A.  
> Do not implement other tracks until cluster phases 1–6 exit criteria pass.

**cPlatform workflows to make work for real (summary):**

| Step | Workflow | Production check |
|------|----------|------------------|
| A1 | Cluster create/edit/delete with lifecycle block when nodes exist | Real API errors; no delete of non-empty cluster without force path |
| A2 | Node add (SSH host, PEM path/paste, facts CPU/GPU/mem, volume_root, platformops docker network) | Connection report real; onboarding job output real; facts on overview |
| A3 | **Discover → adopt** (scored match + SERV#### IDs, no clashes) | Services appear in tree; status reflects docker |
| A4 | Catalog install forms (per-service params) + MANUAL or ANSIBLE deploy | Job status real; service running or real failure |
| A5 | Service lifecycle (port expose, delete impact, force approval if used) | Impact assessment blocks unsafe delete |
| A6 | Live status refresh on Clusters | Poll does not invent healthy |
| A7 | dTrain e2e on `platformops_prod_network` | Runbook passes on this host |

**Exit:** one operator cluster/node usable end-to-end with dTrain proof; hide e2e noise if it confuses demos.

---

### Track B — Config Manager (cPlatform config page)

| Step | Workflow | Production check |
|------|----------|------------------|
| B1 | Load live config for selected service | Real file/content or clear error |
| B2 | Capture snapshot; list; view; rename | Persist + reload |
| B3 | Drift detect live vs snapshot | Diff real or empty |
| B4 | Apply current / restore snapshot | Job + post-apply load |
| B5 | Compare two snapshots | Diff UI works |
| B6 | Migration prepare → validate → apply (if service supports) | Real validate errors; no fake merge success |

**Exit:** login → select service → capture → edit/apply → drift shows expected result.

---

### Track C — Diagnostics + Log Analyst (cPlatform diagnostics)

| Step | Workflow | Production check |
|------|----------|------------------|
| C1 | Target selector + summary analysis | Real analysis or empty issues |
| C2 | Live tail + history (Loki/container as configured) | Lines real or empty, not fabricated |
| C3 | Archives list / backfill | Job real; download if present |
| C4 | Log Analyst chat (Groq/Mistral) | `{answer, evidence, …}` only from API; LLM-down = real error |
| C5 | Ingestion stats when Loki up | Honest zeros if no ingest |

**Exit:** selected service → live logs → one real Log Analyst question with evidence or clear LLM/config error.

---

### Track D — Monitoring / GlitchTip (cPlatform Monitoring.html)

| Step | Workflow | Production check |
|------|----------|------------------|
| D1 | Integration status badge | Connected vs not configured (no green lie) |
| D2 | Issues list + load more + resolve/ignore | Real GlitchTip proxy when configured |
| D3 | Event/traceback detail | Real event payload or error |
| D4 | Uptime monitors list / add / delete | Real when configured |
| D5 | Patch observability (sentry inject) when used | Job real; skip if not configured |

**Exit:** with GlitchTip env set → issues workspace usable; without → clear not-configured UI (still production-honest).

---

### Track E — Performance (cPlatform SystemMonitoring)

| Step | Workflow | Production check |
|------|----------|------------------|
| E1 | Select node → CPU/mem/disk gauges + window | Prom data or empty |
| E2 | Process table sort CPU/memory | Real process list or empty |
| E3 | Select service → service metrics if wired | Empty not fake series |
| E4 | Auto-refresh on Performance view | No invented values |

**Exit:** primary node shows real exporter metrics **or** explicit empty when scrape missing.

---

### Track F — Multiuser / Users (cPlatform user system) — polish only

| Step | Workflow | Production check |
|------|----------|------------------|
| F1 | Login admin/admin; session; logout | Works |
| F2 | Users page: list, invite, role, disable (admin) | Role-appropriate |
| F3 | Invite accept deep link if used | Real token flow |
| F4 | Last-visited restore on login | Best-effort already — verify |

**Exit:** two-role smoke (admin + operational) if second user exists; else admin path only documented.

---

### Track G — Real-server happy path (proof) — after A–C minimum

Single written runbook (no new features):

1. Login  
2. Clusters: select primary node → discover/adopt or deploy one catalog service  
3. Config: capture + apply (or drift)  
4. Diagnostics: live logs + one Log Analyst question  
5. Performance: node metrics (or empty honest)  
6. Monitoring: only if GlitchTip configured  

**Exit criteria:** runbook file in `docs/` that passes on this host; failures are real API errors.

---

## 4. Explicit non-goals (this plan)

- New main-nav areas  
- PlatformOps-only product orphans (secrets vault panel, placement product UI, DTrain dashboard, capacity report product, artifacts panel, releases product)  
- Fake demo seeds presented as production health  
- Re-opening FE monolith split (done)  
- Broad `@ts-nocheck` cleanup (defer until after happy path)  
- Backend mega-router split (only if it blocks a cPlatform track)

---

## 5. Execution order (what to do next)

| Sprint | Focus | Why |
|--------|--------|-----|
| **1** | Track A Clusters production path (discover/deploy/lifecycle) | cPlatform home surface; everything else depends on selection |
| **2** | Track B Config | cPlatform config manager parity on real service |
| **3** | Track C Diagnostics + Log Analyst | cPlatform diagnostics production integrity |
| **4** | Track E Performance honesty + Track D Monitoring honesty | Metrics/errors real-only |
| **5** | Track F multiuser polish | cPlatform users already largely there |
| **6** | Track G happy-path runbook | Proof production-ready on this host |

Optional later (not this plan): role-gated mutates, pytest suite, router splits, types without `@ts-nocheck`.

---

## 6. Per-sprint working rules

1. Prefer **fixing existing UI/API** over new pages.  
2. If a button is half-wired, **finish or hide** — no dead chrome.  
3. After each track: `npm run build` + API smoke for that domain.  
4. Keep secrets in `.env` only.  
5. Prefer one clean cluster/node for demos; quarantine e2e noise.

---

## 7. Done when (success metric)

- [ ] Clusters: discover/adopt **or** catalog deploy works on real node  
- [ ] Config: capture → apply/restore → drift on that service  
- [ ] Diagnostics: live logs + Log Analyst real path  
- [ ] Performance/Monitoring: real data or honest empty  
- [ ] Users/login stable (admin/admin)  
- [ ] Written happy-path runbook passes once on this host  
- [ ] No new non-cPlatform product surfaces shipped  

---

## 8. Immediate next action (when you say “implement”)

**Sprint 1 / Track A only:**

1. Inventory hygiene (primary cluster/node vs e2e noise).  
2. Verify node connection + onboarding readiness.  
3. Discover → adopt **or** deploy one catalog service end-to-end.  
4. Fix any real failure in that path (API or UI).  
5. Smoke: login → clusters → service visible with real status.

Do **not** start Secrets/Releases/Placement/DTrain product UIs.

---

## 9. Relationship to older plan (`plan-next-phase-2b-3.md`)

| Old item | Disposition |
|----------|-------------|
| Phase 2b decomposition | **Done** — closed |
| Phase 3 “product orphans” (Releases, Secrets panel, Placement, Artifacts, DTrain UI) | **Dropped** from next work (not cPlatform production gate) |
| Phase 4 real-server demo | **Kept** as Track G (after A–C) |
| Phase 5 hardening | **Deferred** until happy path green |
