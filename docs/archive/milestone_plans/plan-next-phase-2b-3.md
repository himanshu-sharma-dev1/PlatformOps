# Next plan: Phase 2b → 3 → 4 → 5

> **Superseded for “what next”:** see **`docs/plan-next-cplatform-production.md`**.  
> Phase 2b is **done** (`cdf41b8`). Next work is **cPlatform production readiness only** (Clusters → Config → Diagnostics → Performance/Monitoring → multiuser polish → happy-path runbook). PlatformOps-only product orphans (Secrets vault panel, Placement product UI, DTrain panel, etc.) are **out of scope**.

**As of:** post-`cdf41b8` (decomposition done; older rows below are historical)  
**Login:** `admin` / `admin`  
**Out of scope unless asked:** changing product nav IA; secrets rotation policy beyond env loading

---

## 0. Current baseline (do not re-litigate)

| Layer | State |
|-------|--------|
| **Views** | Real JSX in `views/*` + `TreeNavigator` |
| **Provider** | ~15 lines; composes controller |
| **Controller** | `usePlatformController.tsx` still owns **all** state + actions |
| **Domain hooks** | **Seams only** — each re-exports full controller |
| **API** | Routers + auth middleware; `services.py` still ~856 lines |
| **Orchestrator** | Packages (`diagnostics/`, `monitoring/`, …) with large `impl.py` |

**Goal of next work:** make the architecture *real* (hooks own state), then finish product orphans, then prove a real-server path.

---

## Phase 2b — Real data-layer split (highest priority)

### Objective
Peel `usePlatformController.tsx` into **true** domain hooks that own their `useState` + methods. Controller becomes a **composer** (`{ ...auth, ...inventory, ... }`), not a 5k-line bag.

### Target shape

```
platform/
  context.tsx
  PlatformProvider.tsx          # thin
  usePlatformController.tsx     # compose hooks only (<150 lines target)
  hooks/
    useAuthSession.ts           # owns auth state + login/logout/last-visited
    useInventory.ts             # clusters/nodes/services + refresh/select*
    useConfigWorkspace.ts       # config/snapshots/migrate/peer
    useDiagnostics.ts           # diagnostics/live/archives/chat loaders
    useMonitoring.ts            # GlitchTip issues/uptime/APM/keys
    usePerformance.ts           # node/service metrics, process sort, windows
    useSreAdvanced.ts           # topology/policy/audit/SLO/incidents/maintenance
    useUiChrome.ts              # notice, drawers, modals, tabs, search filters
    types.ts                    # shared PlatformApi partial types
```

### Extraction order (dependency-safe)

| Step | Hook | Owns (examples) | Depends on |
|------|------|-----------------|------------|
| **2b.1** | `useUiChrome` | `notice`, `activeView`, drawer/modal flags, `configTab`, `diagTab`, filters | nothing |
| **2b.2** | `useAuthSession` | `authUser`, `loginForm`, `handleLogin/Logout`, invite accept state, last-visited POST | ui (notice) optional |
| **2b.3** | `useInventory` | `clusters/nodes/services/catalog`, `refresh`, `selectCluster/Node`, create/edit/delete, jobs | auth token via `api()`, ui notice |
| **2b.4** | `useConfigWorkspace` | `config`, snapshots, drift, migrate, peer sync, loaders/appliers | inventory (`selectedService`) |
| **2b.5** | `useDiagnostics` | diagnostics analysis/live/archives/backfill/chat loaders | inventory selection |
| **2b.6** | `useMonitoring` | GlitchTip loads, issues, uptime, APM, keys, windows | inventory service name |
| **2b.7** | `usePerformance` | metrics windows, process sort, auto-refresh | inventory node/service |
| **2b.8** | `useSreAdvanced` | topology plan/deploy, policy scan, audit export, SLO, incidents, maintenance, capacity | inventory |
| **2b.9** | Composer | `usePlatformController` merges returns; drop dead `render*` stubs | all hooks |
| **2b.10** | Types | Replace `PlatformApi = any` with intersection of hook return types; remove `@ts-nocheck` from views gradually | — |

### Rules for each hook PR/step

1. **Move state first**, then the functions that only touch that state.  
2. **Do not** leave a dual copy of `useState` in the controller.  
3. After each step: `npm run build` + smoke login + one page from that domain.  
4. Views should **not** need changes if the merged `platformApi` field names stay stable.  
5. Prefer returning a single object per hook; composer spreads into one context value (same `usePlatform()` API).

### Done when

- [x] `usePlatformController.tsx` is a thin composer (~250 lines: state bag + action factories + effects only)  
- [x] Each domain owns real state under `platform/state/*` + actions under `platform/actions/*` (hooks re-export domain seams)  
- [x] No `render*` stubs left in controller  
- [x] Build green; admin/admin login; Clusters smoke (API)

### Estimated effort

~3–5 focused days if done strictly step-by-step without feature work mixed in.

---

## Phase 3 — Product completeness (API-backed UI orphans)

Keep **main nav clean**; put extras in Advanced or service drawers.

| Priority | Feature | Where | Backend already |
|----------|---------|-------|-----------------|
| P0 | **Releases timeline + rollback** | Service actions on Clusters / drawer | `/api/services/{id}/releases*`, approvals |
| P0 | **Secrets list + rotate** | Advanced or Config side panel | `/api/secrets*` |
| P1 | **Capacity reports** | Reliability page section | `/api/nodes/{id}/capacity`, reports |
| P1 | **Placement planner** | Catalog deploy / deploy modal | placement recommend/deploy |
| P1 | **Artifacts viewer** | Node detail expand | inventory/compose artifacts |
| P2 | **Live docker status refresh** | Service pill on node | status playbooks / discover |
| P2 | **DTrain overview panel** | Advanced or Clusters ML card | `/api/dtrain/overview` |

### Done when

- [ ] Each orphan has a discoverable UI path and empty/error states when data missing (real-only)  
- [ ] No new main-nav top-level items unless product requires  

---

## Phase 4 — Real-server demo path (proof)

1. **Inventory hygiene:** prefer one operator cluster/node (`primary` / `primary-node`); hide or purge e2e noise.  
2. **Discover → adopt** on primary-node; verify services appear.  
3. **Deploy** one catalog app (preflight → deps → deploy).  
4. **Config** capture / apply / drift.  
5. **Diagnostics** live logs + Log Analyst question.  
6. **Monitoring** GlitchTip issues/uptime if project mapped.  
7. **Gate** Launch/Teardown VM unless `environment === aws` + terraform ready.

### Done when

- [ ] One written runbook “happy path” from login → deploy → logs → config works on this host  
- [ ] Failures surface real API errors (no fake success)  

---

## Phase 5 — Hardening

| Item | Action |
|------|--------|
| **Roles on mutate** | Middleware today = any authenticated user; add `require_admin` (or role checks) for delete/force/lifecycle/users |
| **Secrets** | Keep keys only in `.env`; audit repo for accidental tokens; rotate if ever pushed |
| **Tests** | Pytest per router package; one scripted smoke (login, clusters, config load, chat) |
| **API size** | Split `routers/services.py` (~856) into `services_core`, `services_config`, `services_releases` |
| **Orchestrator impl** | Split mega `impl.py` (diagnostics chat/archives/live; monitoring glitchtip vs prom) |
| **UI quality** | Drop `@ts-nocheck` view-by-view; shared `types/` DTOs aligned with schemas |

---

## Suggested execution sequence (what to do *next* in order)

### Sprint A — Phase 2b.1–2b.4 (structure)
1. `useUiChrome`  
2. `useAuthSession`  
3. `useInventory`  
4. `useConfigWorkspace`  
5. Composer slim-down partial  

### Sprint B — Phase 2b.5–2b.10 (finish data layer)
6. Diagnostics / Monitoring / Performance / SRE hooks  
7. Delete stubs; type `PlatformApi`  
8. Build + full nav smoke  

### Sprint C — Phase 3 P0 UIs
9. Releases drawer  
10. Secrets panel  

### Sprint D — Phase 4 demo path
11. Clean inventory + discover + one service e2e  

### Sprint E — Phase 5 as needed
12. Role gates + tests + services router split  

---

## Non-goals (for this next plan)

- New main-nav product areas (Dataflow, MLOps registry)  
- Re-folding Advanced into Monitoring  
- Fake metrics / demo seed nodes  

---

## Risk notes

| Risk | Mitigation |
|------|------------|
| Hook split breaks shared setters | Keep single context value; stable field names |
| Circular deps between inventory & config | Config receives `selectedService` from inventory via composer args |
| Build regressions mid-extract | One hook per commit; always `npm run build` |
| Push protection | Never commit API keys; use `.env` only |

---

## Immediate next action (when you say “implement”)

**Start Sprint A / Phase 2b.1–2b.3:**  
`useUiChrome` → `useAuthSession` → `useInventory`, slim composer, build + smoke.

Do **not** mix Releases UI until 2b auth+inventory are real hooks.

---

## Success metric for “next phase complete”

1. Controller composer ≤ ~150 lines  
2. Seven domain hooks with real ownership  
3. All views still work unchanged at the `usePlatform()` boundary  
4. P0 Releases + Secrets UI exist  
5. Documented happy-path demo on primary node  
