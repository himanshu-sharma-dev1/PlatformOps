# Legacy cPlatform: Performance Page Feature Inventory

This document provides a highly detailed breakdown of the user interface features, interactive controls, charting mechanisms, and telemetry collection pipelines that power the legacy `cPlatform` **Performance & System Monitoring (`SystemMonitoring.html`)** workspace.

---

## 1. Hardware & System Telemetry Header Panels

Provides an aggregated meta-strip displaying the health and composition of the entire cluster infrastructure.

- **KPI Cluster Headers**:
  - **Cluster Count**: Total logical clusters registered.
  - **Node Count**: Total physical/virtual compute instances mapped.
  - **Node Online Count**: Number of nodes successfully responding to SSH/Pings.
  - **GPU Node Count**: Specific metric showcasing how many nodes in the cluster have active GPU resources (calculated dynamically via backend SQL checks).
- **Exporter Indicators**:
  - Displays the active scrape agents running on targets: `node_exporter` (for hardware telemetry) and `service_exporter` (for application/container metrics).

---

## 2. Interactive Navigation Tree

The targets rail (`#treeList`) provides a nested navigation structure to inspect performance metrics at different levels.

- **Hierarchical Layout**:
  - Organizes items under a **Cluster > Node > Service** tree structure.
- **Dynamic Search Filtering (`#treeSearch`)**:
  - Interactive text input filters the node list or service nodes in real time.
- **Node & Service Status Badging**:
  - Inline indicators display node-online badges (green/red) and service warning indicators (orange/red warning rings if thresholds are breached).

---

## 3. Node Hardware Performance Panel (`renderNode`)

Inspecting a physical host node loads the hardware metrics dashboard, displaying resource consumption and operating system performance.

- **Core Resource Cards (`metricCard` / `#metric-sparkline`)**:
  - **CPU Utilization**: Percentage, CPU model info, and real-time sparkline.
  - **Memory Footprint**: GB used / Total GB, percentage, and sparkline.
  - **Disk Utilization**: Volume root usage, percentage, and sparkline.
  - **Network Throughput**: Rx (Received) / Tx (Transmitted) traffic rates in Mbps.
- **Custom SVG Chart Renderer (`renderChart`)**:
  - Draws dynamic linear charts using raw inline SVG vector `<path>` elements:
    - `pathFromSeries`: Generates stroke lines for metric series.
    - `areaFromSeries`: Generates gradient filled area charts beneath the stroke lines.
  - **Hover Tooltips (`wireChartHover`)**:
    - Standard hover overlays display precise timestamp values and metric labels.
- **Top Processes Panel (`topProcesses`)**:
  - Queries the targeted host node and lists running operating system processes.
  - Exposes sorting controls: Sort by **CPU %** or **Memory %** consumption.
- **Mounted Disk Volumes (`mountedVolumes`)**:
  - Lists host storage partitions. Shows mount path, partition file systems, total disk size, used size, and a progress bar mapping utilization percentage.

---

## 4. Service Telemetry Panel (`renderService` / `renderInfraService`)

Inspecting a service node loads application-level metric counters scraped directly from container runtimes.

- **Database Performance (e.g., PostgreSQL, Redis)**:
  - **Connection Pools**: Counts active vs idle database connections.
  - **Read/Write Operations**: Counts read queries, transaction commits, rollbacks.
  - **Cache Hit Ratio**: Calculates buffer cache hit percentages.
  - **Transaction Locks**: Monitors active locks (exclusive, shared) to identify query bottlenecks.
- **Broker & Queue Telemetry (e.g., RabbitMQ)**:
  - **Message Throughput**: Ingestion rate and delivery rate (messages/s).
  - **Queue Backlogs**: Number of queued messages (ready vs unacknowledged).
  - **Consumer Connections**: Tracks active consumers connected to queues.
- **Dynamic Custom Charts (`renderDynamicServiceCharts`)**:
  - Scrapes metrics defined inside the service contract schema.
  - Dynamically builds multi-line charts (`renderMultiLineChart`) displaying customized telemetry curves (e.g., Request Latency, Job execution time).

---

## 5. Telemetry Control Bar

Controls data range scopes and polling behaviors.

- **Time Range Picker Group (`#rangeGroup`)**:
  - Selection buttons allow filtering telemetry over: **1 hour**, **6 hours**, **24 hours**, **7 days**, **1 month**, or **3 months**.
- **Auto-Refresh Toggle (`#refreshToggle`)**:
  - Inline button toggles background polling.
  - When enabled, automatically fetches fresh data arrays every **30 seconds** from the Prometheus server to update charts.
