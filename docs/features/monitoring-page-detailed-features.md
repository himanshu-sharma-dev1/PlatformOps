# Legacy cPlatform: Service Monitoring Page Feature Inventory

This document provides a highly detailed breakdown of the user interface features, interactive controls, integration keys, error lists, and APM performance traces that power the legacy `cPlatform` **Service Monitoring (`Monitoring.html`)** workspace.

---

## 1. Monitoring Header & Connection Status

Controls global monitoring variables and validates integrations with the external error tracking platform.

- **GlitchTip Connection Badge (`#gtStatusBadge`)**:
  - Displays real-time connectivity status: **GlitchTip Connected** (green pulsing badge) or **GlitchTip Not Configured** (red caution badge) indicating if Sentry-compatible endpoints are active.
- **Header Action Controls**:
  - **Refresh Group**: Dropdown select list to toggle time ranges for error tracking: **Last 24 Hours** or **Last 7 Days**.
  - **Auto-Refresh Toggle (`#refreshToggle`)**: Schedules background telemetry sweeps every **30 seconds** (`startAutoRefresh`).
  - **Refresh Now (`#refreshNowBtn`)**: Forcefully queries endpoints immediately, bypassing cache.
- **Infrastructure Context Meta-Strip**:
  - Aggregates overall Cluster Count, Node Count, Node Online Count, and GPU Nodes Count for context.

---

## 2. Interactive Service Selection Rail

The Services tree panel (`#treeList`) filters out systems to navigate down to application levels.

- **Infrastructure Exclusions**:
  - Statically maps services and filters out database/logging nodes to show only application runtimes in primary views.
- **Search Filters (`#treeSearch`)**:
  - Text input filters items in the tree view in real time.

---

## 3. GlitchTip Workspace Tab 1: Issues (Exceptions & Stack Traces)

Fetches, displays, and triages exceptions, unhandled runtime crashes, and error logs collected from active services.

- **Exception Checklist**:
  - Lists issues showing: Exception Type (e.g. `ZeroDivisionError`), Message description, File location, occurrence count, unique users impacted, and relative time (e.g., "5 minutes ago").
- **Triage Action Controls (`executeIssueAction`)**:
  - **Resolve**: Marks the issue as closed. Removes it from active lists.
  - **Ignore**: Mutes future notifications for this specific error signature.
  - **Delete**: Clears the issue from history.
- **Infinite Pagination (`loadMoreIssues`)**:
  - Exposes a **Load More** button to paginate through historical issue registries.
- **Interactive Stack Trace Detail Drawer (`toggleIssueDetails` / `renderDetailedEvent`)**:
  - Expanding an issue reveals:
    - **Stack Trace Grid**: Filename, class functions, line numbers, and actual lines of code surrounding the exception with highlighted syntax.
    - **User Context Metadata**: Captures OS version, browser version, client IP address, request method (GET/POST), URL query params, and HTTP headers.

---

## 4. GlitchTip Workspace Tab 2: Uptime Monitors

Dynamic interface to schedule, verify, and maintain synthetic endpoint ping checks.

- **Add Monitor Form (`submitAddMonitor` / `toggleAddMonitorForm`)**:
  - Input field forms to add a new check:
    - **Monitor Name**: Descriptor label.
    - **Target URL**: The HTTP route to ping (e.g. `http://<node_ip>:8000/health`).
    - **Check Interval**: Interval timing (e.g. 60 seconds).
    - **Timeout**: Timeout threshold.
- **Availability Block Grid**:
  - Renders a horizontal timeline of status blocks (green for online, red for downtime) representing historical availability checks.
- **Response Latency Chart (`renderChart`)**:
  - Draws dynamic SVG line/area charts mapping response latency (in milliseconds) over time.
- **Delete Check (`executeDeleteMonitor`)**:
  - Removes synthetic monitoring checkpoints.

---

## 5. GlitchTip Workspace Tab 3: Performance APM (Transactions)

Displays Application Performance Monitoring (APM) traces, helping engineers analyze latency bottlenecks.

- **HTTP Transaction Table (`renderPerformanceTransactions`)**:
  - Lists HTTP endpoints (e.g., `POST /api/v1/infer`).
  - Columns: Endpoint URI, Average Latency (seconds), Throughput (transactions/minute), and Failure Rate %.
- **Table Sorters (`sortTransactionsFromSelect` / `toggleTransactionTableHeaderSort`)**:
  - Dropdown and column headers toggle sorting orders: Sort by **Throughput**, **Latency**, or **Failure Rate**.
- **Trace Details Link**:
  - Tunnels directly into GlitchTip's APM tool for deep span breakdown.

---

## 6. GlitchTip Workspace Tab 4: Keys & Integration SDK Guide

Provides developers with credentials and code snippets to link their custom applications to the monitoring stack.

- **DSN Token Manager (`loadNativeKeys`)**:
  - Lists Sentry-compatible DSN URLs and allows copying them to the clipboard (`copyToClipboard`).
- **SDK Integration Tabs (`switchGuideTab`)**:
  - Displays code snippets for easy integration in different languages:
    - **Python**: Shows `sentry_sdk.init(dsn="...")` setups.
    - **JavaScript/Node**: Displays framework init codes.
    - **Go**: Displays backend integrations.
