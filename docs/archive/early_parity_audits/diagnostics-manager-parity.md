# Diagnostics Page Parity Analysis: cPlatform vs PlatformOps

> **Historical/design analysis — superseded for current-state claims:** Use [the selected-page functional parity record](selected-page-functional-parity.md) for the current PlatformOps contract. The comparisons below preserve legacy context and may be stale; verify implementation details against the current source before relying on them.

This document analyzes the parity between the legacy `cPlatform` Diagnostics & Logs page (`09-diagnostics.html`) and the modern `PlatformOps` orchestrator backend. The legacy UI triggered 9 distinct diagnostic `fetch` APIs which must be fulfilled by `PlatformOps` to reach full production-grade parity.

---

## 1. Global Diagnostic Metrics

### Legacy `cPlatform`
- **API Action**: `global_diagnostics_metrics`
- **Functionality**: Provided a high-level summary of active services, log streaming rates (e.g., "1.2K/s"), and hourly error rates across the entire cluster.

### Modern `PlatformOps`
- **PlatformOps API**: `GET /api/diagnostics/ingestion-stats` calls `get_ingestion_stats()`, querying Loki for current ingestion rate and error counts and reading measured readable archive size from `LogArchive` when a database session is supplied.
- **Current limitation**: This is not a same-name `get_global_diagnostics_metrics()` endpoint and its data is available only when Loki responds; it is the current global diagnostic-metrics equivalent, not an unimplemented capability.

---

## 2. Service Diagnostics & Analysis

### Legacy `cPlatform`
- **API Action**: `service_diagnostics`
- **Functionality**: Fetches diagnostic health, recent error events, and status for a specific service.

### Modern `PlatformOps`
- **PlatformOps API**: Mapped to `/api/services/{service_id}/diagnostics` and `/diagnostics/analysis`, backed by `service_diagnostics()` and `service_diagnostics_analysis()`.
- **Current status**: The analysis combines readiness, database records, telemetry, and bounded log evidence and emits runbook recommendations. Equivalence with the legacy response shape is not established by this historical document.

---

## 3. Live Log Tailing

### Legacy `cPlatform`
- **API Action**: `service_live_logs`
- **Functionality**: Streams real-time `stdout/stderr` from a container to the web UI. Supports client-side filtering by log levels (INFO, WARN, ERR, DEBUG) and dynamic regex/text matching (via `live-search-input`).

### Modern `PlatformOps`
- **PlatformOps API**: Mapped to `/api/services/{service_id}/diagnostics/live` and backed by `service_live_logs()`.
- **Implementation Mechanism**: The endpoint performs a bounded `docker logs --tail` through the local runtime or remote Ansible command and returns a finite tail. It is not a `docker logs -f` WebSocket/SSE stream and does not query Loki for this live-tail path.
- **Current limitation**: The integer cursor is retained for response compatibility and the implementation reports `has_more_history=false`; level/regex filtering is not exposed as backend query parameters. Separate container/file history endpoints provide Loki-backed cursor pagination.

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
- **PlatformOps API**: `index_log_archives()` rebuilds `LogArchive` rows from declared target paths. Current routes include archive listing, preview (`/archives/{archive_id}/view`), single download, and bulk ZIP download.
- **Current limitation**: Reads/downloads are available only when the declared host path or mounted container path is accessible; remote-node and archive-format behavior still require runtime verification.

---

## 5. Log Backfill & Analytics Chat

### Legacy `cPlatform`
- **API Actions**: 
  - `service_log_backfill` (Forces Loki/Promtail to ingest older logs).
  - `service_log_analytics_chat` (AI-driven chat to query logs).

### Modern `PlatformOps`
- **PlatformOps API**: `backfill_service_logs(db, service)` is exposed at `/api/services/{service_id}/diagnostics/backfill`; `service_log_analytics_chat()` is exposed at `/diagnostics/chat` and gathers diagnostics plus a bounded live tail before calling the configured LLM.
- **Current limitation**: Chat returns an explicit failure when the LLM provider/key is not configured or the request cannot be parsed; it is not guaranteed to produce an answer in every environment.

---

## 6. Actionable Implementation Gaps (Server-Level)

To make the Diagnostics pipeline work flawlessly on a real server:

1. **Loki Integration**: Verify that `bootstrap_observability_plane()` correctly installs and configures the remote log pipeline and that the configured Loki labels are queryable. If this fails, historical file/log features will report an honest unavailable state.
2. **Streaming semantics**: `service_live_logs` is currently a bounded HTTP tail. WebSocket/SSE support remains an optional parity gap if continuous server push is required.
3. **Archive access**: Listing, preview, single-download, and bulk-download routes exist; verify declared host/container paths and remote-node access on a real target.
4. **Global diagnostic metrics**: `/api/diagnostics/ingestion-stats` already issues Loki queries for ingestion rate and error counts. Validate its live response/label coverage rather than adding a duplicate endpoint; the query is LogQL, not PromQL.
5. **Telemetry Runtime Hot-Patching**:
   - *Legacy Feature*: `service_runtime_patch` allowed dynamically patching telemetry values (e.g. DSN, traces sample rate, env name) on active containers via Ansible playbook executions (`service_runtime_patch_playbook.yml`) without complete container rebuilds.
   - *PlatformOps Status*: `/PlatformIO/Monitoring/PatchObservability/` calls `patch_service_runtime_observability()` for remote nodes; local mode explicitly returns a failure because it has no real remote target. Runtime success still needs verification.
6. **Log Cursor Pagination**:
   - *Legacy Feature*: Supported temporal query variables like `history_cursor`, `history_direction`, `history_page`, and `page_size` to navigate back and forth chronologically through log historical records.
   - *PlatformOps Status*: The live-tail route returns only a bounded current tail, but `/diagnostics/container-history` and `/diagnostics/file-history` implement older/newer cursor pagination through Loki when reachable.
