# Monitoring Page Parity Analysis: cPlatform vs PlatformOps

This document analyzes the parity between the legacy `cPlatform` Monitoring page and the modern `PlatformOps` orchestrator backend for service health, uptime, and telemetry tracking.

---

## 1. Core Architecture & Philosophy

### Legacy `cPlatform`
- **Philosophy**: Heavily reliant on an external 3rd-party SaaS (or self-hosted external tool) called **GlitchTip** (a Sentry fork).
- **Functionality**: `Monitoring.html` checks `GT_CONFIGURED`. If connected, it uses GlitchTip's API to fetch error tracking and uptime metrics.
- **UI Layout**: Uses a two-column view. Left: Service Navigator Tree. Right: Dynamic injection of GlitchTip error panes and uptime stats.

### Modern `PlatformOps`
- **Philosophy**: Fully self-contained, native control plane observability. 
- **Functionality**: PlatformOps natively tracks health and telemetry without relying solely on an external Sentry-like tool. It introduces a `MonitoringCheck` model to store historical uptime/health sweeps directly in the orchestrator database.
- **Parity Status**: Major architectural shift. PlatformOps trades off the deep stack-trace error tracking of GlitchTip for a native, holistic infrastructure telemetry pipeline (Alloy, Loki, Prometheus).

---

## 2. Health Sweeps & Uptime

### Legacy `cPlatform`
- **Mechanics**: Uptime is largely calculated by the external tool, and the cluster page merely reflects the last known state.

### Modern `PlatformOps`
- **Mechanics**: Implements a native `run_monitoring_sweep(db)` API. 
- **Execution**: This sweeps across all `ServiceInstance`s, evaluates their runtime status, extracts their `healthcheck` configurations from `config_json`, and commits a `MonitoringCheck` record (e.g., `status="ok"`, `value="running"`).
- **Parity Gap**: PlatformOps currently calculates `MonitoringCheck` based on the database state of the service (`service.status in RUNNING_STATUSES`). To be perfectly production-grade on a real server, the sweep needs to trigger a background worker that genuinely pings the container's `/health` endpoint over the network or via Ansible shell commands.

---

## 3. Observability Plane & Telemetry

### Legacy `cPlatform`
- Telemetry routing is manually managed inside the containers to point to GlitchTip.

### Modern `PlatformOps`
- **Mechanics**: PlatformOps includes a native `bootstrap_observability_plane()` API. This orchestrates an entire logging and metrics pipeline on the target node.
- **Live Logs**: Introduces `service_live_logs()` which streams raw `stdout/stderr` from the container directly back to the control plane.
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
- **The Gap**: Currently, `run_monitoring_sweep()` creates a `MonitoringCheck` by just reading the database's `service.status`. This is effectively a mock. 
- **The Fix**: The sweep must execute an Ansible command (or a network HTTP request) to actually execute the `healthcheck` command defined in the service's `config_json` on the live node.

### 5.2 Infrastructure Service Filtering
- **The Gap**: In `cPlatform`, system infrastructure containers (`infrarabbitmq`, `infraprometheus`, etc. mapped via `INFRA_SERVICE_GROUPNAME_MAP`) are explicitly filtered out of application monitoring loops. PlatformOps currently sweeps all services indiscriminately, which would clutter the main dashboard with background tasks.
- **The Fix**: Add an `is_infrastructure` flag or filter logic in the monitoring sweep to toggle displaying system vs. application health.

### 5.3 GlitchTip / Sentry Fallback
- **The Gap**: While Loki and Prometheus handle logs and metrics beautifully, they do not automatically group application stack traces like GlitchTip did in the legacy UI.
- **The Fix**: If stack trace grouping is a strict requirement for parity, PlatformOps should integrate a native Sentry SDK webhook receiver, or retain the GlitchTip API connection specifically for the "Exceptions" view.

### 5.4 UI Parity
- **The Gap**: The legacy system had a dedicated `Monitoring.html` with 24h/7d filters. PlatformOps needs a React equivalent in `main.tsx` that queries the `latest_monitoring_checks()` API and renders a timeline graph.

### 5.5 Untested Features (Requires Immediate Testing)
1. **Live Log Streaming over SSH**: Does the `service_live_logs()` API successfully connect and tail the docker logs without hanging the FastAPI server?
2. **Diagnostics Generation**: Ensure `service_diagnostics_analysis()` successfully parses real Loki log payloads to detect anomalies.
