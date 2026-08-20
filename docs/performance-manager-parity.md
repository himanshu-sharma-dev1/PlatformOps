# Performance Monitoring Parity Analysis: cPlatform vs PlatformOps

> **Historical/design analysis — superseded for current-state claims:** Use [the selected-page functional parity record](selected-page-functional-parity.md) for the current PlatformOps contract. The comparisons below preserve legacy context and may be stale; verify implementation details against the current source before relying on them.

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
- The legacy contract describes Prometheus exporters, but the shipped `SystemMonitoring.js` also contains an explicit static-demo path that synthesizes plausible time series; exporter-backed runtime behavior is therefore historical/intended rather than proven by this UI file.

### Modern `PlatformOps`
- **Current State**: `get_node_metrics()` and `get_service_metrics()` issue instant and range Prometheus HTTP queries through the configured `prometheus_base_url`. They return `prometheus_reachable=false` with empty series when queries cannot reach Prometheus; they do not use the former synthetic `_metric_series()` path for these endpoint results.
- **Measured node fields**: Node CPU, memory, disk, network RX/TX, and range series are mapped from PromQL; mounted volumes are collected separately from `df` on the local or declared remote node.
- **Measured and placeholder service fields**: Service CPU/memory, CPU range, restart indicator, optional database/broker metrics, and contract-defined custom charts query Prometheus when exporters provide matching series. `log_error_rate`, `queue_depth` (except RabbitMQ-specific query coverage), and `latency_ms_p95` remain zero/empty placeholders; the current `error_rate_series` is populated from a container CPU-system query, not an application log-error metric.
- **Parity Gap**: The remaining no-mock work is metric coverage and semantics: configure the correct endpoint/exporters and replace placeholder service fields with real application/error/latency/queue queries. An unreachable Prometheus response is surfaced as unavailable/empty data rather than synthesized values.

---

## 3. Playbooks and Provisioning

### Legacy `cPlatform`
- Required administrators to manually install `node_exporter` on the remote hosts to gather hardware telemetry.

### Modern `PlatformOps`
- **The Intended Flow**: `bootstrap_observability_plane()` is meant to deploy the Alloy/Loki/Prometheus observability stack through Ansible; the catalog/reporting code also recognizes exporter roles such as `node-exporter`.
- **Parity Gap**: Verify on a target node that the deployed stack and exporter labels match the PromQL selectors used by the metrics API and that host mounts/exporters expose host rather than container-only measurements.

---

## 4. Implementation Gaps & Features Needing Testing

To guarantee that PlatformOps' performance suite works on a real server setup (like the `dtrain` test), the following gaps must be addressed immediately:

### 4.1 Metric query coverage
- **Current state**: The backend already uses `requests.get` for Prometheus instant/range queries and maps responses into the node/service metric schemas.
- **Remaining work**: Replace zero/empty placeholder service fields and validate selector coverage against the deployed exporter labels. Do not infer a real metric solely from `prometheus_reachable=true`; individual query results can still be empty or defaulted.

### 4.2 Observability Integration
- **Endpoint selection**: The metrics implementation uses the configured `settings.prometheus_base_url`; it derives node identity matchers from node facts/host/name but does not dynamically resolve a Prometheus service IP in this module. The deployment's endpoint and exporter labels therefore remain an environment-level verification item.

### 4.3 Automated Tests
1. **PromQL Integration**: No focused test was found in `apps/api/tests/` for `get_node_metrics`/`get_service_metrics` response mapping, empty results, or Prometheus timeouts; add one before treating those contracts as covered.
2. **Alloy Host-Mounting**: Ensure that the generated observability compose/playbook mounts the host OS directories so that metrics reflect the physical server, not only the Alloy container.
