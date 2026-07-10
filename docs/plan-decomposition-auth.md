# Plan: Decompose main.tsx / main.py / orchestrator + Auth boundary

**Scope:** Structure only (secrets/credentials left as-is per request).  
**Goal:** Working app after split; auth enforced on API (not UI-only).

---

## 1. Target architecture

### Frontend (`apps/web/src`)

```
main.tsx                 # createRoot entry only
App.tsx                  # auth gate + Layout + view switch
api/client.ts            # fetch + bearer token
types/index.ts           # shared DTOs / domain types
components/
  charts.tsx             # SVG series, sparklines, gauges, window picker
  GlassCard.tsx
  Layout.tsx
  Sidebar.tsx
platform/
  PlatformContext.tsx    # all shared state + loaders/actions (controller)
  usePlatform.ts         # hook re-export
views/
  ClustersView.tsx
  ConfigView.tsx
  DiagnosticsView.tsx    # includes Log Analyst
  MonitoringView.tsx
  PerformanceView.tsx
  ObservabilityView.tsx
  TopologyView.tsx
  PolicyView.tsx
  AuditView.tsx
  ReliabilityView.tsx
  UsersView.tsx
  Drawers.tsx
  Modals.tsx
auth/
  LoginScreen.tsx
  InviteAcceptScreen.tsx
```

**Pattern:** Fat controller context (`PlatformProvider`) holds state/actions once.  
Page files only render. No prop-drilling of 100 fields.

### Backend (`apps/api/platformops`)

```
deps.py                  # get_db, require_user, require_admin, bearer
routers/
  health.py              # public: /api/health, /api/llm/status
  auth.py                # public login/invite accept; authed me/logout
  users.py               # admin
  catalog.py
  clusters.py
  nodes.py
  services.py
  config_routes.py
  diagnostics.py
  monitoring.py          # + PlatformIO GlitchTip bridges
  observability.py
  sre.py                 # policy, slo, incidents, maintenance, audit, lifecycle, capacity, secrets
  topology.py
  dtrain.py
main.py                  # app factory, CORS, startup, include_router, SPA
orchestrator/
  diagnostics/           # package split (re-export for compat)
  monitoring/            # package split
  llm.py, users.py, ...  # unchanged public names where possible
```

### Auth boundary (required)

| Route class | Auth |
|-------------|------|
| `GET /api/health` | public |
| `POST /api/auth/login` | public |
| `GET/POST /api/auth/invite/*` | public |
| `GET /api/llm/status` | public (UI needs pre-login) |
| **All other `/api/*` and `/PlatformIO/*`** | **Bearer required** (`require_user`) |
| User admin CRUD/invite | `require_admin` |

Frontend: `api()` already sends `Authorization`. Login gate stays.

---

## 2. Implementation order

1. Backend `deps` + routers + auth on all protected routes (keep behavior).  
2. Orchestrator package splits with `__init__.py` re-exports (zero import break).  
3. Frontend extract types/api/charts.  
4. Frontend PlatformContext + views.  
5. Slim entrypoints.  
6. Rebuild web, rebuild/restart API container, smoke login + pages + 401 without token.

---

## 3. Compatibility rules

- Do not rename public API paths.  
- Orchestrator: `from platformops.orchestrator import service_log_analytics_chat` still works.  
- UI feature parity preserved.  
- Secrets/credentials **not** in this pass.

---

## 4. Verification

- `npm run build`  
- API startup + bootstrap admin  
- No token → 401 on `/api/clusters`  
- Login → 200 inventory  
- Invite admin routes still admin-only  
- Chat/diagnostics still work with token  

---

## 5. Completed (2026-07-10)

### Backend
- `main.py` ~77 lines (app factory + `AuthBoundaryMiddleware` + SPA)
- `deps.py` — `require_user` / `require_admin` / public path list
- `routers/` — domain routers: clusters, nodes, services, config-via-services, diagnostics, monitoring, glitchtip, observability, sre, catalog_topology, auth_users, ops aggregate
- `ops_common.py` — shared helpers (`_get_*`, `_mask_cluster`, …)
- Auth: **all** `/api/*` and `/PlatformIO/*` require bearer except health, login, invite, llm status

### Orchestrator packages
- `diagnostics/`, `monitoring/`, `reports/`, `service/` — each `impl.py` + re-export `__init__.py`

### Frontend
- `main.tsx` entry (~6 lines)
- `App.tsx` — auth gate + page switch
- `views/*View.tsx` — one module per page
- `api/client.ts`, `components/charts.tsx`, `types/`
- `platform/PlatformProvider.tsx` — shared controller (still large; views delegate via `usePlatform()`)

### Follow-up (not blocking)
- Move JSX bodies out of PlatformProvider into view files (controller stays data-only)
- Further split `services.py` router / `impl.py` packages by subdomain
- Secrets hygiene (explicitly deferred)
