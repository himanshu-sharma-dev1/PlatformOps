# PlatformOps: Performance & Telemetry Technical Specification

**Canonical Path:** `docs/features/performance-page-detailed-features.md`
**Related Parity Action Matrix:** [`docs/selected-page-functional-parity.md`](../selected-page-functional-parity.md) §5
**Authoritative E2E Test Fixture:** [`docs/redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md) (Phase 7)

---

## 1. Architectural Overview & Workspaces

The PlatformOps Performance workspace (`apps/web/src/views/PerformanceView.tsx`) provides infrastructure-wide hardware and application telemetry scraping backed by **Prometheus PromQL** time-series queries.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Performance & Telemetry Workspace                     │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Left Service Tree │ Main Telemetry Workspace:                               │
│ - Cluster Nodes   │ 1. [KPI Stat Strip]     — Clusters, Nodes, Online, GPUs │
│ - Target Leaf:    │ 2. [Hardware Metrics]   — CPU, Memory, Disk, Net Rx/Tx  │
│   - Node Level    │ 3. [Top OS Processes]   — CPU/Memory sorted table       │
│   - Service Level │ 4. [Mounted Volumes]    — Disk mount capacity bars      │
│     (e.g. redis)  │ 5. [Service Counters]   — Ops, Connections, Cache hit   │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 2. REST API Inventory

Backed by routers `apps/api/platformops/routers/monitoring.py` and `services.py:878-884`, querying the Prometheus time-series database.

| Method | Endpoint Path | Description | Implementation Reference |
|---|---|---|---|
| `GET` | `/api/metrics/node` | Cluster-wide node aggregate hardware metrics | `routers/monitoring.py:13-38` |
| `GET` | `/api/metrics/processes` | Scoped top OS processes for target node sorted by CPU/Memory | `routers/monitoring.py:40-111` |
| `GET` | `/api/nodes/{id}/metrics` | Detailed node CPU, memory, disk, network, and mounted volume stats | `routers/nodes.py:392-398` |
| `GET` | `/api/services/{id}/metrics` | Application-level metrics (database connections, hit ratios, queue depth) | `routers/services.py:878-884` |

---

## 3. Core Subsystem Mechanics

### 3.1 Scoped Process Exporter Regex Instance Matchers
To prevent cross-node metric contamination on shared networks:
* `GET /api/metrics/processes` derives node identity candidates (`node.host`, `node.name`).
* Escapes regex characters via `escape_query_regex_literal` and builds PromQL instance filters (`{instance=~".*({pattern}).*"}`).
* Queries `namedprocess_namegroup_cpu_seconds_total` and `namedprocess_namegroup_memory_bytes`, converts memory to MiB, and sorts dynamically.
* `PerformanceView.tsx:162-197` provides interactive "Sort CPU" and "Sort Memory" column sorting.

### 3.2 Mounted Disk Volume Scraping
* `_fetch_mounted_volumes(node)` executes `df -k` locally or via SSH probe (`impl.py:284-367`).
* Parses filesystem mount paths, partition formats, total GB, used GB, and capacity percentages.
* `PerformanceView.tsx:199-232` renders visual progress bars with alert coloring for partitions exceeding $> 85\%$ threshold.

### 3.3 Advanced SVG Charting Engine (`apps/web/src/components/charts.tsx`)
* **Vector Path Construction**: Computes coordinates mapping series values to `<svg viewBox="0 0 width height">`.
* **Area Gradient Fills**: Renders `<polygon>` elements filled with translucent gradients below primary `<polyline>` strokes.
* **Interactive Hover Crosshairs**: Vertical dashed guide lines (`<line strokeDasharray="3 3">`) with animated circle markers and floating tooltips.
* **Circular Animated Gauges (`renderCircularGauge`)**: Circular SVG gauges with glowing status rings showing utilization percentages.

### 3.4 Dynamic Catalog-Driven Custom Charts
* When inspecting services, `get_service_metrics` (`impl.py:537-640`) queries contract-defined metric expressions from `catalog/services.yaml`.
* Automatically plots multi-line time-series curves for database cache hit ratios, queue lengths, and active client connections.

---

## 4. Authoritative Verification via Golden Fixture (Redis Target)

Authoritative Performance verification follows Phase 7 of `docs/redis-seven-page-acceptance-fixture.md`:
1. **Workload Generation**: Run `redis-benchmark -q -n 1000 -c 10` against `redis-core` container.
2. **Metric Verification**:
   - Query `/api/nodes/{id}/metrics` $\to$ verify real PromQL CPU/Memory/Network curves.
   - Query `/api/metrics/processes?node_id={id}` $\to$ assert Redis process (`redis-server`) appears in top process table.
   - Query `/api/services/{id}/metrics` $\to$ assert Redis operations per second and connected clients.
3. **UI Chart Inspection**: Verify SVG time-series charts render with hover crosshairs and tooltips.
