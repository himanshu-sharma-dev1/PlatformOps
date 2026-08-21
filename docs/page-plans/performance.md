# Performance page — complete cPlatform parity plan

## Mission

Match cPlatform node/service performance behavior using real, scoped Prometheus
telemetry for the canonical Redis target. No placeholder, response-key, HTTP
success, empty-series, or numeric-zero result can be presented as measured
performance.

## Source authority

- `/PlatformIO/SystemMonitoring/`, `/GetMonitoringTree/`,
  `/GetNodePerformance/`, `/GetServicePerformance/`.
- `cPlatformIO/views.py:2082-2265`, `SystemMonitoring.js`, `MachineStats`,
  `ServiceStats`, and Prometheus helpers.
- PlatformOps matrix §5; `PerformanceView.tsx`, `performanceActions.ts`,
  monitoring router/orchestrator PromQL paths.

## Current evidence problems to resolve first

- Redis harness issues no workload and does not query direct Prometheus.
- It treats HTTP 200 and response keys as success even when reachability is
  false, arrays are empty, or values are placeholders.
- It does not prove Redis exporter/node exporter targets, run labels,
  timestamps, units, windows, trends, or target isolation.
- `log_error_rate`, `queue_depth`, `latency_ms_p95`, and current error series are
  known placeholders/non-error telemetry.
- No collector-loss versus Redis-health distinction or recovery is tested.
- No frontend chart, refresh, auto-refresh, process sort, or stale request test
  exists in the golden run.

## Work package P0 — metric contract freeze

- [ ] Trace exact cPlatform metric fields, sources, formulas, units, windows,
  default range/step, null/zero behavior, and chart expectations.
- [ ] Map every PlatformOps response field to a real metric/query or classify it
  non-parity/unavailable.
- [ ] Record canonical PromQL, label selectors, aggregation, denominator, rate
  interval, and timestamp normalization.
- [ ] Define tolerances for comparing PlatformOps to direct Prometheus.
- [ ] Remove cPlatform-unrelated native fields from the parity gate.

## Work package P1 — telemetry fixture

- [ ] Deploy/configure Redis exporter and node exporter as supporting evidence
  infrastructure, not managed parity targets.
- [ ] Pin images and record `/targets` health, scrape interval, labels, and last
  scrape/error.
- [ ] Label series with canonical run, cluster, node, service, and container
  identity or provide a deterministic mapping that excludes stale targets.
- [ ] Establish idle baseline with direct queries.
- [ ] Generate bounded SET/GET/INCR workload using run-prefixed keys; record
  command count, concurrency, duration, timestamps, and expected trend.
- [ ] Clean workload keys and verify count afterward.

## Work package P2 — monitoring tree and selection

- [ ] Compare PlatformOps tree hierarchy and identifiers with cPlatform
  semantics.
- [ ] Select canonical node/Redis and retain selection across refresh.
- [ ] Changing parent clears invalid children and stale metrics.
- [ ] Direct links and unauthorized/not-found targets show truthful states.
- [ ] Run two labeled targets only as supporting stale/isolation fixtures if
  needed; never register a second managed product service.

## Work package P3 — node metrics

- [ ] Prove CPU, memory, disk, network, mounted volumes, and time series against
  direct Prometheus/host evidence for each required window.
- [ ] Validate units, percentages, rates, aggregation, step, sample ordering,
  missing samples, counter resets, and timezone/timestamp rendering.
- [ ] Verify process list fields and CPU/memory sorting, limit, node scope, empty
  and malformed series.
- [ ] Ensure local and remote node collectors cannot cross-contaminate.

## Work package P4 — Redis service metrics

- [ ] Map cPlatform-required service metrics to Redis exporter series where
  semantically valid.
- [ ] Prove memory, availability, commands/throughput, clients, hits/misses,
  restarts, and any required error/latency/queue values.
- [ ] Replace placeholder error/latency/queue fields with real queries, or mark
  them unavailable and suppress misleading charts if cPlatform behavior cannot
  be truthfully reproduced with Redis telemetry.
- [ ] Compare idle versus load windows and require a meaningful change in
  commands/memory while health remains stable.
- [ ] Validate true zero separately from absent series.

## Work package P5 — frontend behavior

- [ ] Match window choices, manual/auto refresh, loading, last-updated, chart
  labels, units, tooltips, empty/unavailable/error, and retry.
- [ ] Prevent overlapping refreshes and ignore stale responses after target or
  window changes.
- [ ] Do not render placeholder zeros as green/healthy measurements.
- [ ] Prove accessibility/keyboard behavior for controls and readable fallback
  when charts have no data.

## Work package P6 — failure and recovery

- [ ] Stop Redis exporter while Redis stays healthy: service telemetry becomes
  unavailable, Monitoring health remains healthy.
- [ ] Stop Prometheus: all query-backed metrics become explicitly unavailable.
- [ ] Restart and require fresh samples newer than recovery time.
- [ ] Test bad query, timeout, malformed vector/range, missing label, stale
  series, duplicate series, counter reset, and partial collector loss.
- [ ] Assert errors are redacted and no old values masquerade as current.

## Authoritative Performance harness changes

- Generate the bounded workload and record its manifest.
- Query Prometheus `/targets` and direct PromQL before/under/after load.
- Assert reachability, non-empty series, correct labels/timestamps, numerical
  tolerances, and expected trend—not merely keys.
- Implement exporter/Prometheus loss and recovery.
- Drive UI window/refresh/sort and capture browser assertions.
- Fail on placeholder values presented as measured data.

## Required evidence

Exporter target metadata, load manifest, direct PromQL requests/responses,
PlatformOps node/service/process responses, calculated comparisons/tolerances,
UI traces, failure/recovery timestamps, workload cleanup, and canonical IDs.

## Final Performance acceptance

Prove idle/load/recovery across every required metric/window, compare direct
sources, prove target isolation, and show honest unavailable versus true zero.
Re-run Clusters/Config/Diagnostics/Monitoring regressions.

Performance is complete only when all required §5 rows are Parity-complete and
no placeholder or empty-success path remains.
