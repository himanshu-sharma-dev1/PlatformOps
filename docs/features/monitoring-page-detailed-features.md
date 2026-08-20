# PlatformOps: Service Monitoring & GlitchTip Technical Specification

**Canonical Path:** `docs/features/monitoring-page-detailed-features.md`
**Related Parity Action Matrix:** [`docs/selected-page-functional-parity.md`](../selected-page-functional-parity.md) §4
**Authoritative E2E Test Fixture:** [`docs/redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md) (Phase 6 & 8)

---

## 1. Architectural Overview & Workspaces

The PlatformOps Service Monitoring surface consists of two coordinating layers:
1. **Application Workspace (`apps/web/src/views/MonitoringView.tsx`)**: Service hierarchy navigation rail with infrastructure filtering (`s.kind !== "infrastructure"`), integration status badges, and time window controls.
2. **GlitchTip Workspace (`apps/web/src/views/GlitchTipWorkspace.tsx`)**: Sentry-compatible APM, issue triage, uptime monitors, and DSN key management.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Service Monitoring Workspace                        │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Left Service Tree │ Main Workspace Tabs:                                    │
│ - Cluster Nodes   │ 1. [Issues]       — Stack traces, breadcrumbs, triage   │
│ - App Service     │ 2. [Uptime]       — Synthetic pings & 48-block timeline │
│   (e.g. redis-core│ 3. [Performance]  — APM latency, throughput, failures   │
│     SERV1000)     │ 4. [SDK Keys]     — DSN tokens & code integration guide │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 2. REST API Inventory

Backed by routers `apps/api/platformops/routers/glitchtip.py` (cPlatform compatibility layer) and `apps/api/platformops/routers/monitoring.py` (native SRE sweeps).

| Method | Endpoint Path | Description | Implementation Reference |
|---|---|---|---|
| `GET`/`POST` | `/PlatformIO/Monitoring/IntegrationStatus/` | Returns GlitchTip connectivity state (`configured`, `healthy`, `endpoint_url`) | `routers/glitchtip.py:163-168` |
| `POST` | `/PlatformIO/Monitoring/Health/` | Returns issue aggregates, open/resolved counts, and uptime health | `routers/glitchtip.py:11-49` |
| `POST` | `/PlatformIO/Monitoring/Issues/` | Lists issues with filters (`service_name`, `window`, `cursor`) | `routers/glitchtip.py:51-66` |
| `POST` | `/PlatformIO/Monitoring/Issues/EventDetails/` | Retrieves deep exception stack trace, code lines, and local variables | `routers/glitchtip.py:68-78` |
| `POST` | `/PlatformIO/Monitoring/IssueAction/` | Triages issue (`resolve`, `ignore`, `delete`) | `routers/glitchtip.py:80-88` |
| `POST` | `/PlatformIO/Monitoring/Performance/` | Fetches APM transaction throughput and latency metrics | `routers/glitchtip.py:90-105` |
| `POST` | `/PlatformIO/Monitoring/Keys/` | Retrieves client DSN tokens and language SDK setup code | `routers/glitchtip.py:107-118` |
| `POST` | `/PlatformIO/Monitoring/Uptime/` | Lists synthetic uptime check targets and latency data | `routers/glitchtip.py:120-136` |
| `POST` | `/PlatformIO/Monitoring/Uptime/Add/` | Registers new synthetic HTTP healthcheck monitor | `routers/glitchtip.py:138-149` |
| `POST` | `/PlatformIO/Monitoring/Uptime/Delete/` | Removes synthetic uptime healthcheck monitor | `routers/glitchtip.py:151-161` |
| `POST` | `/PlatformIO/Monitoring/PatchObservability/` | Injects Sentry/GlitchTip runtime SDK into service container | `routers/glitchtip.py:170-176` |
| `POST` | `/api/monitoring/sweep` | Executes native SRE sweep across services and stores `MonitoringCheck` | `routers/monitoring.py:118-121` |
| `GET` | `/api/monitoring/checks` | Queries stored `MonitoringCheck` audit records | `routers/monitoring.py:123-125` |

---

## 3. Core Subsystem Mechanics

### 3.1 Exception Stack Trace & Context Inspector
When an issue is selected in `GlitchTipWorkspace.tsx:155-242`:
* **Code Frame Highlighting**: Renders source code surrounding the crash with line numbers and red-border highlight on the exact failing line (`context_line`).
* **Runtime Local Variables Table (`frame.vars`)**: Inspects variable states in memory at the moment of exception execution.
* **Breadcrumbs Timeline**: Step-by-step user actions, database queries, and log statements leading up to the error.
* **Triage Controls**: Instant actions ("Mark Resolved", "Ignore / Mute") updating state and refreshing metrics.

### 3.2 48-Unit Uptime Availability Blocks & SVG Latency Chart
* **Availability Timeline**: Renders 48 horizontal color-coded status blocks (green for OK 2xx, red for failure/downtime) representing chronological checks.
* **Response Latency Series**: Renders dynamic SVG line/area time-series chart with vertical hover crosshairs and millisecond tooltips (`charts.tsx:140-176`).

### 3.3 APM Performance Transaction Sorter
In `GlitchTipWorkspace.tsx:378-420`, HTTP transaction traces can be dynamically sorted:
* **Latency**: Sorted by average duration descending (`avgDuration`).
* **Throughput**: Sorted by transaction volume descending (`count`).
* **Failure Rate**: Sorted by error rate percentage descending (`failureRate`).

### 3.4 Infrastructure Service Filtering
* `MonitoringView.tsx:76-85` filters the navigation tree with `s.kind !== "infrastructure"` and `{ appServicesOnly: true }`.
* Prevents internal infrastructure daemons (e.g. RabbitMQ, ClickHouse, Prometheus, Loki) from cluttering application-level monitoring.

---

## 4. Authoritative Verification via Golden Fixture (Redis Target)

Authoritative Monitoring verification follows Phase 6 & 8 of `docs/redis-seven-page-acceptance-fixture.md`:
1. **Health & Uptime**: Register synthetic health check pointing to `redis-core` $\to$ assert green availability blocks and valid latency chart.
2. **Failure Injection**: Inject `docker pause` on Redis container $\to$ trigger monitoring sweep $\to$ assert health transitions to Degraded/Down and red block appears in uptime timeline.
3. **Recovery**: Unpause/restart container $\to$ assert recovery to healthy state.
