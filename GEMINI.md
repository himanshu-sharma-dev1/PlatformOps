# GEMINI.md — PlatformOps SRE Orchestrator

## 1. Project Overview

PlatformOps is a **production-grade SRE and DevOps control plane** built with FastAPI + React + SQLite. It distills the core infrastructure orchestration capabilities of the legacy `cPlatform` Django monolith into a modern, decoupled architecture.

**Primary Goal:** Achieve exact feature parity with cPlatform's SRE workspace pages — no more, no less.

**Tech Stack:**
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2
- **Frontend:** React 18, Vite, TypeScript (single-page `main.tsx`)
- **Automation:** Ansible playbooks + Python wrapper scripts
- **Observability:** GlitchTip (Sentry fork), Grafana Loki, Prometheus, Alloy, node_exporter, process-exporter
- **IaC:** Docker Compose, Terraform (mock), Helm 3

---

## 2. Directory Structure

```
PlatformOps/
├── apps/
│   ├── api/                          # FastAPI backend
│   │   └── platformops/
│   │       ├── main.py               # All route handlers (~2156 lines, ~97 endpoints)
│   │       ├── models.py             # SQLAlchemy 2.0 ORM models (~358 lines)
│   │       ├── schemas.py            # Pydantic request/response models (~1149 lines)
│   │       ├── settings.py           # Pydantic settings (GlitchTip URL, tokens, catalog paths)
│   │       ├── db.py                 # Database engine, session, Base
│   │       └── orchestrator/         # Business logic package (~7157 lines total)
│   │           ├── __init__.py       # Re-exports all public functions (~309 lines)
│   │           ├── common.py         # Shared helpers: record_event, list_events, ansible utils (~176 lines)
│   │           ├── config.py         # Config snapshots, drift, apply, restore, migration (~807 lines)
│   │           ├── diagnostics.py    # Live logs, log archives, backfill, AI analysis (~1219 lines)
│   │           ├── discovery.py      # Infrastructure auto-discovery via Docker PS (~69 lines)
│   │           ├── monitoring.py     # GlitchTip proxy, metrics, sweep, uptime, perf (~998 lines)
│   │           ├── node.py           # Node validation, onboarding, VM lifecycle (~602 lines)
│   │           ├── reports.py        # SRE: incidents, SLOs, policy, secrets, maintenance (~1722 lines)
│   │           └── service.py        # Catalog, topology, placement, deploy, compose gen (~1255 lines)
│   └── web/                          # React + Vite frontend
│       └── src/
│           ├── main.tsx              # Entire SPA rendering logic (~8316 lines)
│           └── components/
│               ├── Layout.tsx        # Shell layout wrapper
│               ├── Sidebar.tsx       # Navigation sidebar
│               └── GlassCard.tsx     # Reusable card component
├── catalog/
│   ├── services.yaml                 # Declarative service card contracts (40+ services)
│   ├── dependencies.yaml             # Dependency graph definitions
│   └── observability.yaml            # Observability stack definitions
├── docs/
│   ├── features/                     # Feature parity specification documents
│   │   ├── cluster-page-detailed-features.md
│   │   ├── config-manager-detailed-features.md
│   │   ├── monitoring-page-detailed-features.md
│   │   ├── diagnostics-page-detailed-features.md
│   │   └── performance-page-detailed-features.md
│   └── cplatform-distillation-audit.md
├── ops/
│   ├── ansible/playbooks/            # Ansible playbook YAML files
│   ├── compose/                      # docker-compose.local.yml, docker-compose.observability.yml
│   ├── docker/                       # Multi-stage Dockerfile
│   ├── terraform/aws/                # Mock Terraform config
│   └── helm/platformops/             # Helm 3 chart
├── scripts/
│   └── run_e2e_tests.py              # E2E test suite (62 functional targets)
├── data/                             # SQLite DB, runtime artifacts (gitignored)
├── Makefile                          # Dev shortcuts: make api, make check, make lint
└── .venv/                            # Python virtual environment
```

---

## 3. Architecture & Schema Mapping (cPlatform → PlatformOps)

| cPlatform Django Model | PlatformOps SQLAlchemy Table | Purpose |
|---|---|---|
| `Cluster` | `clusters` | Physical/cloud regions, environments, repository types |
| `Node` | `nodes` | Host IPs, volume roots, monitoring ports, GPU state, `facts_json` |
| `Service` | `service_instances` | Service registrations, `config_json`, ports, container status |
| `NodeEvent` + `ServiceEvent` | `operational_events` | Unified event feed with category/level/search |
| `ReportInfo` + `ReportLog` | `monitoring_checks` + `slo_reports` | Health sweeps, SLO evaluations |
| `DataFlowLogs` + `DataflowBatchConfig` | `log_archives` + `drift_reports` | Log file indexes, config drift tracking |

---

## 4. Orchestrator Module Responsibilities

| Module | Key Functions | What It Does |
|---|---|---|
| `common.py` | `record_event`, `list_events`, `test_git_connection`, `test_registry_connection` | Shared event logging, connection tests |
| `config.py` | `config_workspace`, `create_config_snapshot`, `apply_config`, `detect_drift`, `compare_config_snapshots`, `restore_config_snapshot`, `sync_peer_config` | Full config lifecycle management |
| `diagnostics.py` | `service_diagnostics`, `service_live_logs`, `service_diagnostics_analysis`, `index_log_archives`, `backfill_service_logs`, `deploy_observability_stack` | Log tailing, archive indexing, AI analysis |
| `discovery.py` | `discover_infrastructure` | Auto-discovers Docker containers on nodes, matches to catalog |
| `monitoring.py` | `run_monitoring_sweep`, `query_monitoring_issues`, `get_monitoring_performance`, `add_monitoring_uptime_check`, `patch_service_runtime_observability`, `get_node_metrics`, `get_service_metrics` | GlitchTip proxy, metrics, uptime, health sweeps |
| `node.py` | `validate_node`, `get_node_onboarding_report`, `remediate_node_onboarding`, `launch_node_vm`, `teardown_node_vm` | Node lifecycle, SSH validation |
| `reports.py` | `run_policy_scan`, `evaluate_slos`, `create_incident`, `execute_runbook`, `generate_capacity_report`, `schedule_maintenance`, `observability_pipeline_report`, `lifecycle_impact` | SRE governance, incidents, capacity, policy |
| `service.py` | `catalog_cards`, `topological_sort`, `placement_recommendations`, `deploy_service`, `generate_compose`, `dependency_preflight`, `bootstrap_observability_plane` | Service catalog, deployment, topology |

---

## 5. External Integrations

| System | Host | Port | Usage |
|---|---|---|---|
| **GlitchTip** (Sentry fork) | `54.183.53.93` | `9008` | Error tracking, uptime monitors, APM transactions, DSN keys |
| **Grafana Loki** | localhost | `9021` (read) / `9011` (write) | Log aggregation, LogQL queries |
| **Prometheus** | localhost | `9022` | Node/process metrics scraping |
| **Alloy** | localhost | `12345` | Log collection agent (Promtail replacement) |

Settings are configured via `apps/api/platformops/settings.py` using `pydantic_settings` with `PLATFORMOPS_` env prefix.

---

## 6. Feature Parity Status

| Page | Status | Feature Docs |
|---|---|---|
| **Cluster** | ✅ Done | `docs/features/cluster-page-detailed-features.md` |
| **Config Manager** | ✅ Done | `docs/features/config-manager-detailed-features.md` |
| **Monitoring** | 🔧 In Progress | `docs/features/monitoring-page-detailed-features.md` |
| **Diagnostics** | 🔧 In Progress | `docs/features/diagnostics-page-detailed-features.md` |
| **Performance** | 🔧 In Progress | `docs/features/performance-page-detailed-features.md` |

---

## 7. Legacy Reference Codebase

The **original cPlatform source** is checked out at `/home/ubuntu/cplatform_master` (master branch). This is a **read-only reference** — never make edits there. Key reference files:

- **Django views:** `cPlatform/cPlatformIO/views.py`
- **Service config logic:** `cPlatform/cPlatformIO/src/ServiceConfig.py`
- **Service diagnostics:** `cPlatform/cPlatformIO/src/ServiceDiagnostics.py`
- **Frontend templates:** `cPlatform/templates_new/PlatformIO/`
- **Frontend JS:** `cPlatform/static/javascript/`
- **Ansible playbooks:** `platform/ansible/playbook/`
- **Observability stack:** `platform/observability/`
- **Service catalog:** `cPlatform/config/service_install.yaml`
- **Sibling packages:** `CutilJS/`, `MCPClient/`, `CommonUtils/`, `ModelStore/`, `Subsytems/`

---

## 8. Development Workflow

### Start Backend API
```bash
cd /home/ubuntu/PlatformOps
source .venv/bin/activate
make check   # Seed DB
make api     # uvicorn on :8000
```

### Start Frontend
```bash
cd /home/ubuntu/PlatformOps/apps/web
npm install
npm run dev  # Vite on :5173
```

### Run E2E Tests
```bash
cd /home/ubuntu/PlatformOps
.venv/bin/python scripts/run_e2e_tests.py
```

### Verify Build
```bash
make check
cd apps/web && npm run build  # Must compile with zero errors
```

---

## 9. Coding Conventions

### Python (Backend)
- **Style:** 4-space indent, `snake_case` functions/variables, `PascalCase` classes.
- **Imports:** All orchestrator functions must be imported via `from .orchestrator import ...` in `main.py`.
- **Schemas:** All API responses must use Pydantic models from `schemas.py`. Use `Optional[...]` for fields that may be absent.
- **Events:** Every mutating operation must call `record_event(db, ...)` to create an audit trail in `operational_events`.
- **New orchestrator functions:** Add to the appropriate module (`monitoring.py`, `diagnostics.py`, etc.) and export via `__init__.py`.

### TypeScript/React (Frontend)
- **Structure:** The entire SPA lives in `main.tsx` with render functions per page (e.g., `renderMonitoringView()`, `renderGlitchTipWorkspace()`).
- **API calls:** Use `fetch()` with the FastAPI base URL. Handle loading/error states.
- **Components:** Reusable components go in `src/components/`. Keep them focused.

### Service Catalog
- **Location:** `catalog/services.yaml`
- **Adding a new service:** Add an entry with `key`, `display_name`, `kind`, `image`, `dependencies`, `ports`, `healthcheck`, `backup_strategy`, `log_paths`.
