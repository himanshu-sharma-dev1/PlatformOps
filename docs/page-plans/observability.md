# Observability page — cPlatform-derived parity plan

## Mission

Turn the current Observability page into a truthful integrated readiness view
of behavior already required by cPlatform Monitoring, SystemMonitoring,
Diagnostics, service configuration, and ClusterConfig. Do not treat
PlatformOps-native stack management as cPlatform parity.

## Source authority and strict boundary

cPlatform has no standalone Observability page. Relevant source is distributed
across:

- `/PlatformIO/Monitoring/` and GlitchTip helpers;
- `/PlatformIO/SystemMonitoring/`, monitoring tree, node/service performance;
- `/PlatformIO/Diagnostics/`, log history/backfill;
- ClusterConfig deployment/config/runtime-patch actions.

PlatformOps matrix §7 currently lists several actions with “No direct
counterpart.” Those rows must be classified non-parity unless a source audit
finds a precise cPlatform action. Observability cannot be declared complete by
deploying or inspecting `platformops-obs` alone.

## Current evidence problems to resolve first

- The Redis harness only calls `GET /api/observability/status` and logs two
  fields; it does not assert values, readiness, freshness, target identity,
  degradation, recovery, or cross-page evidence.
- Pipeline status may be derived from database service state instead of direct
  collector probes.
- Native deploy/teardown/bootstrap actions have no direct cPlatform counterpart
  and currently inflate the page surface.
- No Redis exporter target, Prometheus sample, Loki marker, Alloy state, direct
  container status, or navigation consistency is proven.
- No component-specific failure injection is performed.
- Success may be reported when the telemetry pipeline is uninitialized.

## Desired page contract

For the canonical Redis service, one response/view must report:

- selected cluster/node/service IDs and container identity;
- direct service running/health status;
- Prometheus reachability, exact target health, last scrape/error, and latest
  Redis/node sample time;
- Loki readiness and latest run-labeled Redis marker time;
- Alloy/collector status and last ingestion evidence;
- optional GlitchTip configured/reachable state without pretending it is
  required in base mode;
- precise overall state: ready, degraded, unavailable, or not configured;
- per-signal reason, age/freshness, source, and navigation to the responsible
  Monitoring, Performance, or Diagnostics page.

No metric/log/health value may come solely from a persisted service status when
a real probe is required.

## Work package O0 — source derivation and classification

- [ ] Trace every current Observability UI control/API to a cPlatform-derived
  behavior or mark it native/non-parity.
- [ ] Remove native-only actions from the parity matrix, or visibly label and
  isolate them outside the completion gate.
- [ ] Define exact readiness fields, source probes, freshness thresholds,
  aggregation, degraded precedence, and unavailable semantics.
- [ ] Ensure optional GlitchTip does not block base readiness but accurately
  reports its own state.
- [ ] Update matrix/status before implementation so no no-counterpart row can be
  accidentally advanced.

## Work package O1 — canonical identity and navigation

- [ ] Consume the same selected Redis IDs used by every operational page.
- [ ] Reject stale/missing/unauthorized targets and clear invalid selection.
- [ ] Every readiness card carries target ID and evidence timestamp.
- [ ] Navigation opens the same Redis in Monitoring, Performance, Diagnostics,
  Config, or Clusters without name-based remapping.
- [ ] Back/refresh/direct-link behavior preserves only valid authorized state.

## Work package O2 — direct signal probes

- [ ] Service signal: direct DinD container inspect and Redis PING correlated to
  PlatformOps live status.
- [ ] Prometheus signal: API readiness plus exact Redis/node `/targets`, last
  scrape/error, and non-stale run-labeled sample.
- [ ] Loki signal: readiness plus exact recent run marker query.
- [ ] Alloy signal: container/health and evidence that the Redis marker reached
  Loki through the intended collector path.
- [ ] GlitchTip signal: configured/reachable/project identity where enabled.
- [ ] Report not-configured separately from unreachable, empty, stale, and
  healthy.

## Work package O3 — deployment/control boundary

- [ ] If collector bootstrap/deploy is required by a cPlatform ClusterConfig
  service action, route it through the same catalog/deployment job machinery and
  terminal-state evidence as Clusters.
- [ ] Do not maintain a second independent observability product lifecycle for
  parity.
- [ ] Native `platformops-obs` deploy/status/teardown may remain operationally
  available, but label it PlatformOps-native and exclude it from cPlatform
  completion and the golden parity score.
- [ ] Runtime GlitchTip patch stays part of Monitoring parity, not proof of
  Prometheus/Loki readiness.

## Work package O4 — degradation and recovery matrix

- [ ] Stop Redis: service health degrades; collector infrastructure may remain
  reachable; latest data becomes stale with explicit age.
- [ ] Stop Redis exporter: Performance signal degrades while Redis Monitoring
  health remains healthy.
- [ ] Stop Prometheus: metric signal unavailable; logs and Redis health remain.
- [ ] Stop Alloy: ingestion degrades; direct Redis health/metrics remain.
- [ ] Stop Loki: log query unavailable; collector/service/metrics states remain
  separately represented.
- [ ] Disable GlitchTip: optional integration unavailable without falsely
  degrading base telemetry readiness.
- [ ] Recover each component and require evidence timestamps newer than the
  recovery event.
- [ ] Test stale DB state, stale metrics/logs, malformed probe response, timeout,
  and partial multi-signal failure.

## Work package O5 — frontend truthfulness

- [ ] Render loading, ready, degraded, unavailable, not configured, stale, and
  partial states distinctly.
- [ ] Show source and last-evidence timestamp for each signal.
- [ ] Do not show green based solely on an API returning 200.
- [ ] Disable/label native-only controls so they cannot be mistaken for parity.
- [ ] Refresh atomically or identify independently stale cards; cancel stale
  requests after target changes.
- [ ] Verify navigation and recovery through browser tests.

## Authoritative Observability harness changes

- Query all direct evidence sources and assert the canonical Redis/run labels.
- Require ready values and freshness during happy path.
- Inject each component failure independently and assert the exact expected
  partial state, then recovery with new timestamps.
- Navigate to Monitoring/Performance/Diagnostics and correlate the same evidence
  through browser tests.
- Fail on uninitialized/degraded state during the happy-path ready assertion.
- Never credit native stack deploy/teardown/bootstrap rows lacking cPlatform
  counterparts.

## Required evidence

Canonical identity, direct Docker/PING, Prometheus target/sample, Loki marker,
Alloy status/path evidence, optional GlitchTip state, aggregated readiness
response, UI traces, navigation traces, per-component failure/recovery
timestamps, and cleanup. Each readiness claim must cite its direct artifact.

## Final Observability acceptance

With Redis, exporter, Prometheus, Alloy, and Loki healthy, prove ready and fresh
signals and cross-page correlation. Induce each independent failure, prove
precise partial degradation without collateral false states, recover, and prove
new evidence. Run the complete six operational page regression afterward.

Observability is complete when every cPlatform-derived row is Parity-complete,
every native-only row is explicitly excluded, and no database-only/HTTP-only
green state remains.
