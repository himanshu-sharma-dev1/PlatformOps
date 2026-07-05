# Legacy cPlatform: Diagnostics Page & Log Analyst Feature Inventory

This document provides a highly detailed, technical breakdown of both the user-facing UI features (workspaces, pagination tables, AI chat) and the backend systems (Loki LogQL queries, pagination caching, SSH commands, custom sparkline rendering) that power the legacy `cPlatform` **Diagnostics & Logs (`09-diagnostics.html`)** page.

---

## 1. Global Diagnostics Dashboard & Metrics

Calculates real-time performance and ingestion rates of the cluster's logging pipeline by querying Loki and executing remote SSH checks.

### 1.1 KPI Header Panels & Navigation
- **Ingestion Header Panels**:
  - **Live Ingestion Rate**: Displays Loki's total throughput (e.g., `1.2K/s` or `450/s`) globally.
    - *Query*: `sum(rate({service_name=~".+"}[1h]))`
    - *API*: Calls Loki's `/loki/api/v1/query` endpoint.
  - **Hourly Error Rate**: Displays cumulative count of errors in the current hour compared to the previous hour.
    - *Query*: `sum(count_over_time({service_name=~".+"} |~ "(?i)error|exception|fail|fatal|crit"[1h]))`
    - *API*: Searches all log lines for warning/error keywords across a sliding 1-hour window.
  - **Archived Storage Size**:
    - *Ssh command*: Runs a shell command on the primary cluster node:
      `find /home/ubuntu/Backup_Platform/iktara/ -type f \( -ipath "*/logs/*" -o -ipath "*/observability/loki/*" \) -exec du -b {} + 2>/dev/null | awk '{sum+=$1} END {print sum}'`
    - *Fallback projection*: If SSH fails, projects storage by multiplying the current Log Rate by an average of 75 bytes per log line over a 90-day retention span.
- **Service Navigator Rail (Left Pane)**:
  - Nested tree structure (`Cluster > Node > Service`) to quickly select target applications.
  - Search bar (`#nav-filter-input`) to filter services by name.
  - Node connection indicators (green/red status).
  - Error flag tags (little red dots next to service names that have active warning/error events).

---

## 2. Service Diagnostics Checklist (Workspace Pane 1)

Loads a deep-dive health checklist and event stream for the selected service instance.

- **Heuristic Health Assessment**:
  - Evaluates CPU/Memory consumption, disk usage, and container uptime.
  - Highlights anomalies such as excessive restart counts (restarts > 0) or error rate spikes (error rate > 0.4).
- **Target Selection**:
  - Toggle between different targets/containers within a service group (e.g. for a `dtrain` service group, toggle between `dtrain-worker` and `dtrain-controller`).
- **Events Log**:
  - Displays a historical audit table of the service (redeployments, configuration snapshots, crashes, manual restarts).

---

## 3. Live Log Tailing & Source Selection (Workspace Pane 2)

A real-time console that tails stdout/stderr streams from the target container.

### 3.1 Dynamic Log Source Selector
The Log Selector dropdown (`#log-source-select`) allows operators to toggle between four distinct ingest modes:
- **Container Live**: Tunnels straight to container `stdout`/`stderr` on the node using Ansible `docker logs -f` triggers.
- **Container History (Loki)**: Queries historical stdout/stderr logs from the centralized Loki instance using target tags (e.g., `{container_name="app-instance"}`).
- **File Logs (Live)**: Directly reads from the service's raw `.log` files (located at paths like `/iktara/logs/<service>/app.log` on the host node filesystem) via remote SSH tail processes.
- **File History (Loki)**: Queries historical records of specific log files that have been pushed to Loki via Promtail. Requires explicit `loki_labels` configured in the service target's metadata.

### 3.2 Tailing Controls & Filters
- **Real-Time Stream**: Connects to the host server and streams new logs dynamically.
- **Toggles & Controls**:
  - **Auto-scroll lock**: Pauses the console from scrolling to the bottom, allowing operators to inspect lines without getting pushed down by incoming logs.
  - **Clear Console**: Empties the current display buffer.
  - **Tail Limit Selector**: Adjusts the console display buffer (e.g., 100, 250, 500, or 1000 lines).
- **Console Log Level Filters**:
  - Dynamic filter chips: **Info**, **Warn**, **Error**, **Debug**.
  - Clicking a chip dynamically toggles log lines matching that level off/on.
- **Text & Regex Search Bar (`#live-search-input`)**:
  - Evaluates incoming log lines against regular expressions or text.
  - Highlights matched lines and displays delta stats (e.g., `Loaded 250 lines · delta filter 12 lines`).

---

## 4. Sparkline Chart Renderer (CSS-Based Stacked Chart)

The Tail Console Metrics Strip features a dynamic **Event Rate Sparkline** (`#metric-sparkline`) populated using pure HTML/CSS elements and a square-root scaling algorithm.

- **Binning Pipeline**:
  - Divides the loaded log dataset chronologically into **18 distinct bins** (`count = 18`).
  - Iterates through log timestamps. If timestamps are missing or uniform, falls back to equal index division.
  - Groups logs in each bin by level: `INFO`, `WARN`, and `ERR`/`ERROR`.
- **Square-Root Scaling**:
  - Spikes in normal `INFO` log lines can drown out warnings/errors. To prevent this, the renderer calculates bar height using a square-root ratio:
    $$Height = 4px + \text{round}\left( \frac{\sqrt{TotalBinLines}}{\sqrt{MaxBinLines}} \times 28px \right)$$
- **Stacked CSS Gradients**:
  - Instead of drawing separate charts, each individual sparkline bar is styled dynamically with a CSS `linear-gradient` showing stacked colored segments:
    - **Info (Teardrop Blue)**: `var(--info)`
    - **Warn (Caution Orange)**: `var(--warn)`
    - **Error (Critical Red)**: `var(--err)`
  - *Example inline style*: `background: linear-gradient(to top, var(--info) 70%, var(--warn) 90%, var(--err) 100%);`

---

## 5. Loki History Pagination & Cursor Engine

Because Loki's query engine does not support SQL-style `OFFSET`/`LIMIT` pagination, the log analyst implements a stateful **Cursor Pagination Engine** to allow seamless page-by-page log browsing.

- **Total Page Calculation**:
  - Calls `_count_loki_selector_entries` which hits Loki's `/loki/api/v1/query` endpoint with `count_over_time` filters.
  - Computes total pages: `history_total_pages = (total_lines + page_size - 1) // page_size`.
- **Anchor-Timestamp Cursors**:
  - Pagination uses base64-encoded cursor tokens containing the page anchor's millisecond timestamp (`anchor_ts`), direction (`older`/`newer`), and query tags.
  - When fetching the **Older** page, the API passes the timestamp of the *first* log line of the current page as an end boundary: `end_ns = anchor_ns - 1`, setting direction to `backward`.
  - When fetching the **Newer** page, the API passes the timestamp of the *last* log line of the current page as a start boundary: `start_ns = anchor_ns + 1`, setting direction to `forward`.
- **Stateful Page Cache (`LOKI_HISTORY_PAGE_CACHE`)**:
  - Keeps a 45-second TTL cache of page cursors mapping back to page numbers.
  - When a user requests Page 4, the backend locates the nearest cached cursor (e.g. Page 2), runs query requests sequentially from that checkpoint, populates cursors for pages 3 and 4, caches the new page cursors, and returns Page 4.

---

## 6. Log Files & Dynamic Archiving (Workspace Pane 3)

Provides file system access to historical log files and zipped archives stored on the node.

- **Log Archives Table**:
  - Lists all log files located in the service's designated volume directories (e.g., `app.log`, `app.log.2026-07-04.gz`).
  - Columns: Filename, Subpath, covered Date Range, File Size, Total Lines.
  - **Event flags**: Identifies and badges log files containing critical exceptions or warning counts (e.g., `5 Warnings`, `2 Errors`).
- **Archive Filter Bar**:
  - Toggle between **All archives** and **Gzipped only** (.gz files).
- **Dynamic Ingestion (Log Backfill)**:
  - If Loki doesn't contain history for a file (Loki series missing), hitting "Backfill" (`service_log_backfill` action) forces Promtail to scrape and backfill the target file.
- **Action Buttons per File**:
  - **View Log**: Opens a side modal reading the first 300 lines of the file (`service_view_log_file` API) without downloading it.
  - **Download Log**: Directly downloads the raw file (`service_download_log_file` API) over HTTP (`FileResponse` content type).
  - **Bulk Download**: 
    - Checkboxes next to each file to select multiple archives.
    - Triggers the `service_download_bulk_logs` API, which creates a temporary ZIP archive on the server.
    - SSHs into the node to retrieve target files, appends them into the zip file, and downloads it.

---

## 7. AI Log Analytics Chat (Workspace Pane 4)

An interactive conversational AI engine (`service_log_analytics_chat` API) designed to help operators troubleshoot errors.

- **Operator Prompts**:
  - Input field for entering natural language queries (e.g., "Explain why the database connection timed out at 10 PM").
  - Preset quick queries: "Verify database connection failures", "Check API latency degradation".
- **Time Window Filter**:
  - Restricts AI context to logs from the current session, the last 24 hours, or the last 7 days.
- **AI Workspace & Context Scoping**:
  - Extracts keywords from user questions to identify target error tags.
  - Binds logs from the selected source (`container_live`, `container_history`, `file_live`, etc.) and time window (current, 24h, 7d) as prompt context.
  - Feeds the mapped log stream and context to the LLM.
  - Returns structured markdown outlining root causes, stack traces, and recommended runbooks.
- **Chat Memory**:
  - Encodes the chat history array in payload requests to maintain continuity during follow-up questions.
