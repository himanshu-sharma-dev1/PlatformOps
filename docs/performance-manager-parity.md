# Performance Monitoring Parity Analysis: cPlatform vs PlatformOps

This document analyzes the parity between the legacy `cPlatform` Performance page (`SystemMonitoring.html`) and the modern `PlatformOps` orchestrator backend for hardware metrics and application-level counters.

---

## 1. Core Architecture & Philosophy

### Legacy `cPlatform`
- **Philosophy**: Metric collection relies on Prometheus `node_exporter` and `service_exporter` installed directly on the cluster nodes.
- **UI Layout**: Uses a two-column navigator split (Tree on the left, detail graphs on the right) matching the config/diagnostics pattern.
- **Time Ranges**: Provides selectable metric windows (1h, 6h, 24h, 7d, 1M, 3M) with a 30s auto-refresh interval.

### Modern `PlatformOps`
- **Philosophy**: Intended to be backed by a self-deployed observability plane (`Alloy` -> `Prometheus`).
- **Data Model**: The API exposes `get_node_metrics(window)` and `get_service_metrics(window)`.

---

## 2. Metric Collection Mechanism (The Major Gap)

### Legacy `cPlatform`
- Metrics in the UI were intended to be powered by actual PromQL queries against the live Prometheus server scraping the instances.

### Modern `PlatformOps`
- **Current State**: The `get_node_metrics` and `get_service_metrics` APIs inside `orchestrator.py` are currently **100% Mocked**.
- **Mocking Logic**:
  - `get_node_metrics()` calculates fake CPU, memory, and disk percentages using arbitrary formulas based on the number of services assigned to a node (e.g., `base_cpu = min(92.0, 24.0 + service_count * 6.5)`).
  - Time series data is generated using a fake `_metric_series()` function which adds synthetic "swing" noise over a sinusoidal curve.
- **Parity Gap**: To achieve your goal of **"server level no mock"**, these API endpoints must be completely rewritten to stop generating fake numbers and instead execute a real PromQL HTTP query against the live Prometheus endpoint deployed by the observability plane.

---

## 3. Playbooks and Provisioning

### Legacy `cPlatform`
- Required administrators to manually install `node_exporter` on the remote hosts to gather hardware telemetry.

### Modern `PlatformOps`
- **The Intended Flow**: `bootstrap_observability_plane()` is meant to deploy `Alloy` via an Ansible playbook. Alloy is a modern OpenTelemetry collector that replaces the need for standalone `node_exporter`.
- **Parity Gap**: We need to verify that `install_observability.yml` actually runs the Alloy container configured to scrape the host machine's `/proc` and `/sys` directories for accurate CPU/Memory metrics.

---

## 4. Implementation Gaps & Features Needing Testing

To guarantee that PlatformOps' performance suite works on a real server setup (like the `dtrain` test), the following gaps must be addressed immediately:

### 4.1 Rip Out Mock Metrics
- **The Gap**: The backend metrics API (`get_node_metrics` and `get_service_metrics`) must be rewritten.
- **The Fix**: Integrate a Python Prometheus HTTP client (or simple `requests.get`) inside `orchestrator.py`. The API must query the live Prometheus endpoint (e.g., `http://<node_ip>:9090/api/v1/query_range`) and format the resulting PromQL JSON payload into the `cpu_series`, `memory_series`, and `disk_series` arrays expected by the frontend.

### 4.2 Observability Integration
- **The Gap**: The UI needs a way to know the IP address of the Prometheus server. Since Prometheus is deployed onto a specific cluster node via `bootstrap_observability_plane()`, the orchestrator must dynamically resolve the IP of the node hosting the `infraprometheus` service to route the metric queries correctly.

### 4.3 Automated Tests
1. **PromQL Integration**: Write a test verifying that `get_node_metrics` correctly handles empty responses or timeouts from Prometheus.
2. **Alloy Host-Mounting**: Ensure that the `docker-compose` generated for Alloy correctly mounts the host OS directories so that the metrics accurately reflect the physical server, not just the inside of the Alloy container.
