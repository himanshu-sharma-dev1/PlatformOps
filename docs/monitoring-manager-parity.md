# Monitoring Page Parity Analysis: cPlatform vs PlatformOps

> **Historical/design analysis — superseded for current-state claims:** Use [the selected-page functional parity record](selected-page-functional-parity.md) for the current PlatformOps contract. The comparisons below preserve legacy context and may be stale; verify implementation details against the current source before relying on them.

This document analyzes the parity between the legacy `cPlatform` Monitoring page and the modern `PlatformOps` orchestrator backend for service health, uptime, and telemetry tracking.

---

## 1. Core Architecture & Philosophy

### Legacy `cPlatform`
- **Philosophy**: Heavily reliant on an external 3rd-party SaaS (or self-hosted external tool) called **GlitchTip** (a Sentry fork).
- **Functionality**: `Monitoring.html` checks `GT_CONFIGURED`. If connected, it uses GlitchTip's API to fetch error tracking and uptime metrics.
- **UI Layout**: Uses a two-column view. Left: Service Navigator Tree. Right: Dynamic injection of GlitchTip error panes and uptime stats.

### Modern `PlatformOps`
- **Philosophy**: Native control-plane observability alongside optional GlitchTip integration routes.
- **Functionality**: PlatformOps natively tracks health and telemetry without relying solely on an external Sentry-like tool. It introduces a `MonitoringCheck` model to store historical uptime/health sweeps directly in the orchestrator database.
- **Parity Status**: The backend includes `MonitoringCheck` plus Alloy/Loki/Prometheus observability services, while the current Monitoring view still uses GlitchTip integration for issues, uptime, and transactions. Complete replacement of GlitchTip is not established here.

---

## 2. Health Sweeps & Uptime

### Legacy `cPlatform`
- **Mechanics**: Uptime is largely calculated by the external tool, and the cluster page merely reflects the last known state.

### Modern `PlatformOps`
- **Mechanics**: Implements a native `run_monitoring_sweep(db)` API. 
- **Execution**: The sweep visits all `ServiceInstance` rows and commits a `MonitoringCheck`. With `PLATFORMOPS_LOCAL_MODE=false`, it invokes `ops/ansible/playbooks/service_status.py` to inspect the declared container and records the observed state, updating the service status when the script returns a usable result. In local mode, it deliberately uses persisted `service.status` as a compatibility path; the declared `healthcheck` is included as detail but is not executed by this function.
- **Current limitation**: The non-local path is a synchronous container-status inspection, not a background worker or a demonstrated HTTP `/health` probe. The local path is not live health checking. The sweep also currently includes infrastructure and application services alike.

---

## 3. Observability Plane & Telemetry

### Legacy `cPlatform`
- Telemetry routing is manually managed inside the containers to point to GlitchTip.

### Modern `PlatformOps`
- **Mechanics**: PlatformOps includes a native `bootstrap_observability_plane()` API. This orchestrates an entire logging and metrics pipeline on the target node.
- **Live Logs**: Introduces `service_live_logs()` which returns a bounded raw `stdout/stderr` tail via the local runtime or remote Ansible command; it is not a continuous stream.
- **Log Indexing**: Uses `LogArchive` models and `index_log_archives()` to catalog log files on the host system.

---

## 4. Diagnostics & Remediation

### Legacy `cPlatform`
- **Mechanics**: Relies on a human operator reading GlitchTip stack traces to figure out what went wrong.

### Modern `PlatformOps`
- **Mechanics**: Introduces intelligent diagnostics via `service_diagnostics_analysis()`. 
- **Remediation**: Maps known failure states to Runbooks (e.g., `_recommended_runbook_for_diagnostics_context()`), offering actionable remediation steps directly to the platform engineer.

---

## 5. Implementation Gaps & Features Needing Testing

To guarantee that PlatformOps' monitoring suite can completely replace the legacy GlitchTip integration on a real server setup (like the `dtrain` test), the following gaps must be addressed:

### 5.1 True Active Health Checking (No Mocks)
- **Current state**: `run_monitoring_sweep()` has two paths. Non-local mode executes `service_status.py` and records Docker inspection state; local mode reads persisted `service.status` for compatibility. Neither path demonstrates execution of the configured `healthcheck` command itself.
- **Remaining verification**: Exercise the non-local path against a real node and confirm the status script's Docker access and failure reporting. Treat local-mode results as compatibility data, not a live probe.

### 5.2 Infrastructure Service Filtering
- **The Gap**: In `cPlatform`, system infrastructure containers (`infrarabbitmq`, `infraprometheus`, etc. mapped via `INFRA_SERVICE_GROUPNAME_MAP`) are explicitly filtered out of application monitoring loops. PlatformOps currently sweeps all services indiscriminately, which would clutter the main dashboard with background tasks.
- **The Fix**: Add an `is_infrastructure` flag or filter logic in the monitoring sweep to toggle displaying system vs. application health.

### 5.3 GlitchTip / Sentry Fallback
- **The Gap**: While Loki and Prometheus handle logs and metrics beautifully, they do not automatically group application stack traces like GlitchTip did in the legacy UI.
- **Current status**: PlatformOps retains GlitchTip integration routes and a remote-only observability patch route; this does not establish automatic stack-trace grouping in the native `MonitoringCheck` data model. If grouping is a strict requirement, verify the configured GlitchTip path or add an explicit replacement.

### 5.4 UI Parity
- **Current status**: A React `MonitoringView` exists and remains GlitchTip-focused with 24h/7d controls. The inventory/action layer loads `latest_monitoring_checks()` and can run a sweep, but the view does not establish a `MonitoringCheck` timeline graph equivalent.

### 5.5 Untested Features (Requires Immediate Testing)
1. **Remote bounded log tail**: Does the `service_live_logs()` API successfully connect and return the remote Docker tail without hanging the FastAPI server?
2. **Diagnostics Generation**: Ensure `service_diagnostics_analysis()` successfully correlates real readiness, telemetry, and Loki/file evidence; its metrics path can legitimately return unavailable/empty data.
