# Diagnostics Page Parity Analysis: cPlatform vs PlatformOps

This document analyzes the parity between the legacy `cPlatform` Diagnostics & Logs page (`09-diagnostics.html`) and the modern `PlatformOps` orchestrator backend. The legacy UI triggered 9 distinct diagnostic `fetch` APIs which must be fulfilled by `PlatformOps` to reach full production-grade parity.

---

## 1. Global Diagnostic Metrics

### Legacy `cPlatform`
- **API Action**: `global_diagnostics_metrics`
- **Functionality**: Provided a high-level summary of active services, log streaming rates (e.g., "1.2K/s"), and hourly error rates across the entire cluster.

### Modern `PlatformOps`
- **PlatformOps API**: Addressed via a combination of `capability_coverage_report()`, `lifecycle_audit_report()`, and `latest_monitoring_checks()`.
- **Parity Gap**: There is no direct `get_global_diagnostics_metrics()` endpoint in `orchestrator.py` that calculates live log throughput (log rate/s). This requires querying the Loki observability plane globally, which is currently unimplemented.

---

## 2. Service Diagnostics & Analysis

### Legacy `cPlatform`
- **API Action**: `service_diagnostics`
- **Functionality**: Fetches diagnostic health, recent error events, and status for a specific service.

### Modern `PlatformOps`
- **PlatformOps API**: Mapped directly to `service_diagnostics()` and `service_diagnostics_analysis()`. 
- **Parity Status**: **Exceeds Parity**. PlatformOps introduces advanced heuristic analysis that maps failure modes to actionable Runbooks (`_recommended_runbook_for_diagnostics_context`), greatly improving the operator experience over the legacy system.

---

## 3. Live Log Tailing

### Legacy `cPlatform`
- **API Action**: `service_live_logs`
- **Functionality**: Streams real-time `stdout/stderr` from a container to the web UI. Supports client-side filtering by log levels (INFO, WARN, ERR, DEBUG) and dynamic regex/text matching (via `live-search-input`).

### Modern `PlatformOps`
- **PlatformOps API**: Mapped directly to `service_live_logs()`.
- **Implementation Mechanism**: The orchestrator is designed to SSH into the remote node and run a `docker logs -f` or query `Loki` for the active stream.
- **Parity Gap (Testing Needed)**: 
  - We need to verify how `service_live_logs()` prevents HTTP connection blocking/hanging. A true live-tail requires WebSockets or Server-Sent Events (SSE) from the FastAPI backend, but the current backend test suite is empty so this networking behavior is unverified.
  - The PlatformOps API needs endpoints or query-params to filter streams by log level and regex patterns directly in the backend (ideally utilizing Loki's native LogQL filters) rather than fetching all logs and filtering them on the client.

---

## 4. Log Files & Archiving

### Legacy `cPlatform`
- **API Actions**: 
  - `service_list_log_files`
  - `service_view_log_file`
  - `service_download_log_file`
  - `service_download_bulk_logs`
- **Functionality**: Allowed downloading or viewing historical log files directly from the UI.

### Modern `PlatformOps`
- **PlatformOps API**: Handled via the `LogArchive` data model and the `index_log_archives()` endpoint.
- **Parity Gap**: 
  - `index_log_archives()` exists, but there are no explicit functions in `orchestrator.py` for downloading or viewing the raw contents of those archives.
  - To achieve full parity, PlatformOps must implement the file transfer endpoints: `download_log_archive(archive_id)` and `read_log_archive_lines(archive_id, lines=100)`.

---

## 5. Log Backfill & Analytics Chat

### Legacy `cPlatform`
- **API Actions**: 
  - `service_log_backfill` (Forces Loki/Promtail to ingest older logs).
  - `service_log_analytics_chat` (AI-driven chat to query logs).

### Modern `PlatformOps`
- **PlatformOps API**: `backfill_service_logs(db, service)` exists to handle the backfill logic.
- **Parity Gap**: 
  - The `service_log_analytics_chat` AI functionality is not natively present in `orchestrator.py`. While `service_diagnostics_analysis()` provides static AI insights, a conversational `/chat` endpoint scoped to a specific `ServiceInstance`'s logs is missing and must be ported over from the legacy codebase.

---

## 6. Actionable Implementation Gaps (Server-Level)

To make the Diagnostics pipeline work flawlessly on a real server:

1. **Loki Integration**: Verify that `bootstrap_observability_plane()` correctly installs and configures Promtail on the remote nodes to push logs to the centralized Loki instance. If this fails, neither live-tail nor diagnostics will work.
2. **WebSocket Support**: Convert `service_live_logs` to use `fastapi.websockets` to prevent the UI from polling excessively or timing out.
3. **File Download APIs**: Implement FastAPI `FileResponse` routes to serve the static `LogArchive` paths for the download actions.
4. **Global Log Rate PromQL**: Write a PromQL query inside a new `global_diagnostics_metrics()` endpoint to calculate Loki's total ingestion rate for the dashboard.
5. **Telemetry Runtime Hot-Patching**:
   - *Legacy Feature*: `service_runtime_patch` allowed dynamically patching telemetry values (e.g. DSN, traces sample rate, env name) on active containers via Ansible playbook executions (`service_runtime_patch_playbook.yml`) without complete container rebuilds.
   - *PlatformOps Gap*: PlatformOps has no capability to hot-patch active environments without rebuilding/redeploying.
6. **Log Cursor Pagination**:
   - *Legacy Feature*: Supported temporal query variables like `history_cursor`, `history_direction`, `history_page`, and `page_size` to navigate back and forth chronologically through log historical records.
   - *PlatformOps Gap*: The log streamer only returns a current tail of the logs, lacking pagination controls.
