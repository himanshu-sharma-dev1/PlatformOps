# Monitoring page — complete cPlatform parity plan

## Mission

Match cPlatform service-scoped monitoring, health, issues, transactions, keys,
and uptime behavior while keeping native PlatformOps checks clearly separate.
Use the canonical Redis service for real health degradation and recovery; use a
disposable GlitchTip profile for external integration actions.

## Source authority

- `/PlatformIO/Monitoring/` and Issues, EventDetails, Performance, Health,
  IntegrationStatus, Uptime, IssueAction, and Keys routes.
- `cPlatformIO/views.py:2277-2840` and `ServiceMonitoring.js`.
- PlatformOps matrix §4; `MonitoringView.tsx`, `monitoringActions.ts`,
  `routers/glitchtip.py`, `routers/monitoring.py`, monitoring orchestrator.

## Verified acceptance status — 2026-08-22 (DOC-1)

The strict `parity-redis-20260822T111500-accept18b` and independent
`parity-redis-20260822T035500Z-e2et1` runs each passed phases 0–8. Artifacts are
in `/tmp/platformops-redis-acceptance/<run-id>/`.

| Action group | State | Boundary |
|---|---|---|
| Canonical Redis health sweep, actual stop, degraded observation, same-container recovery and new healthy evidence | Parity-complete for the bounded health slice | Local cluster `1`/node `1`/service `2`; no service replacement was credited |
| Configured GlitchTip integration status/health and compatibility boundary | Runtime-proven | Support GlitchTip was version `6.1.9`; individual external mutations/UI edge cases remain separately scoped |
| Issues, event details, actions, uptime, keys and transaction groups | Contract-tested; selected configured calls runtime-proven | Do not promote every external mutation to page parity without side-effect assertions |
| Native DB sweep/check history | Runtime-proven supporting evidence | It cannot replace cPlatform GlitchTip behavior |

The protected cPlatform comparison remained equal for the acceptance-owned
identity fields, while a pre-existing `SERV1006` restart loop changed its
restart-count endpoint/MAC during observation. This is disclosed external
volatility, not a blanket unchanged claim.

## Scope classification

### Required parity

Service selection/window/refresh; integration status; health; issues and
pagination; event details; issue action; uptime list/add/delete; transaction
groups; project keys; required runtime integration patch.

### Native regression-only behavior

Database monitoring sweep/check history is not the cPlatform GlitchTip contract.
It can support health evidence but cannot replace any required external action
or inflate page completion.

## Remaining full-page gaps after bounded acceptance

- The accepted runs stop the canonical Redis, assert degraded health, recover
  the same target and require newer healthy evidence.
- Configured GlitchTip support is exercised (version `6.1.9`); retain separate
  action-level gaps for individual external mutation side effects and browser
  auto-refresh/window/isolation behavior.
- Native DB checks remain supporting evidence and cannot replace cPlatform
  GlitchTip semantics.

## Work package M0 — contract freeze

- [ ] Record exact request fields, defaults, pagination, time windows, payloads,
  errors, and external timeouts for every monitoring subroute.
- [ ] Trace GlitchTip project/service selection, DSN/key behavior, issue actions,
  uptime ownership, and transaction queries through legacy helpers.
- [ ] Separate native sweep/check APIs from compatibility parity rows.
- [ ] Capture sanitized external response fixtures for deterministic adapter
  tests.

## Work package M1 — selection, refresh, and integration states

- [ ] Reuse canonical Redis cluster/node/service IDs.
- [ ] Match 24h/7d/default window, manual refresh, auto-refresh interval, cache
  restore, loading, empty, error, and retry.
- [ ] Cancel/ignore stale responses when target/window changes.
- [ ] Prove data for another service/project cannot leak into Redis selection.
- [ ] Distinguish unconfigured, unreachable, unauthorized, malformed response,
  configured-empty, and configured-with-data states.

## Work package M2 — real Redis health

- [ ] Establish healthy state with direct DinD inspect and Redis PING.
- [ ] Run native sweep and correlate its persisted check with canonical IDs.
- [ ] Stop the exact Redis container through the fixture harness.
- [ ] Poll direct state, live-status, compatibility health, native check, and UI
  until each accurately degrades within its contract window.
- [ ] Assert Config/Diagnostics/Performance do not fabricate healthy data while
  Redis is down.
- [ ] Restart the same container, require PONG, fresh check/event, and UI
  recovery without creating a new service row.
- [ ] Test missing container, Docker unavailable, timeout, and stale DB status.

## Work package M3 — GlitchTip issues and transactions

- [ ] Start explicitly disposable GlitchTip and record project/auth identity.
- [ ] Verify integration status and project keys.
- [ ] Ingest a controlled Redis-tagged error and transaction with run labels.
- [ ] List/filter/page issues; assert project, service, time window, ordering,
  count, next/previous semantics.
- [ ] Open exact event detail and compare identifiers/timestamps/tags.
- [ ] Execute every supported issue action and verify external state plus UI
  refresh; test invalid action/not-found/unauthorized/conflict.
- [ ] Query transaction groups and keep them distinct from native Prometheus
  Performance metrics.

## Work package M4 — uptime monitors and runtime patch

- [ ] List baseline uptime monitors.
- [ ] Add a Redis-relevant reachable target with exact validation/defaults.
- [ ] Prove duplicate, invalid URL, unreachable external API, unauthorized, and
  ownership behavior.
- [ ] Delete and verify external removal and refreshed UI.
- [ ] Patch runtime integration only if directly required by cPlatform; verify
  actual target config/environment and failure rollback rather than response
  text alone.

## Authoritative Monitoring harness changes

- Implement actual stop/degrade/start/recover operations and poll assertions.
- Persist before/during/after direct Docker/PING/live-status/check/UI evidence.
- Add an explicit configured GlitchTip phase; unavailable-only proof cannot
  advance external rows.
- Turn every unexpected non-200, timeout, empty required payload, or mismatch
  into failure.
- Clean all run-labeled monitors/issues/projects where API semantics permit and
  record intentional retained external events separately.

## Failure matrix

Redis stopped/missing; Docker unavailable; stale persisted health; GlitchTip
disabled/unreachable/401/429/500/malformed; issue gone during action; uptime
duplicate/invalid/delete race; patch partial failure; auto-refresh target switch.
Each case needs truthful UI/API state, no cross-target data, event evidence, and
recovery.

## Required evidence

Canonical IDs, direct container/PING states, sweep/check rows, health payloads,
UI traces, GlitchTip project/key/issue/event/action/transaction/uptime artifacts,
refresh timing, errors, recovery, and cleanup—all redacted and tied to current
HEAD/run.

## Final Monitoring acceptance

Prove Redis healthy → stopped → degraded everywhere → recovered, then prove the
full configured GlitchTip action family and unavailable/error behavior. Re-run
Clusters, Users, Config, and Diagnostics regression gates.

Monitoring is complete only when every required §4 row is Parity-complete;
native sweep success alone is insufficient.
