# Seven-page cPlatform parity execution index

## Governing goal

Complete scientifically verifiable cPlatform behavioral parity for only the
seven current PlatformOps pages. Do not add other cPlatform pages or count
PlatformOps-only features. The shared contract remains:

- [`../current-pages-cplatform-parity-plan.md`](../current-pages-cplatform-parity-plan.md)
- [`../redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md)
- [`../selected-page-functional-parity.md`](../selected-page-functional-parity.md)
- [`../mvp-status.md`](../mvp-status.md)
- [`current-other-pages-status-2026-08-21.md`](current-other-pages-status-2026-08-21.md)
  for the latest live status of the six non-Cluster pages and the current
  isolated support-stack topology.
- [`current-acceptance-handover-2026-08-22.md`](current-acceptance-handover-2026-08-22.md)
  for the concise verified handover and residual boundaries.

## Verified acceptance checkpoint — 2026-08-22 (DOC-1)

The strict executor run `parity-redis-20260822T111500-accept18b` and the
independent run `parity-redis-20260822T035500Z-e2et1` both passed phases 0–8.
Their redacted evidence bundles are under
`/tmp/platformops-redis-acceptance/<run-id>/` (the executor bundle includes
`manifest.json`, every `phase-*.json`, `direct-runtime.json`, and
`final-summary.json`). The current acceptance checkpoint supersedes the older
2026-08-20/21 green-banner warnings below; the detailed plans still retain
unexercised legacy actions and their earlier implementation guidance.

| Page | Bounded acceptance state | What is proven | What is not promoted |
|---|---|---|---|
| Clusters | Runtime-proven; parity-complete for the Redis fixture action set | canonical lifecycle, terminal jobs, direct runtime, PING/logs, invalid deploy, positive disposable SSH branch | every legacy/provider/UI action |
| Config Manager | Runtime-proven; parity-complete for the tested config action set | exact file bytes, `CONFIG GET`, apply, drift, compare, restore/rollback | migration/peer and all editor edge cases |
| Users | Runtime-proven for API + Mailpit + browser invite/session flow | invite delivery, preview/accept/login, token terminal paths, role/status | full browser automation of all admin controls |
| Monitoring | Runtime-proven for health recovery and configured GlitchTip boundary | stop/recovery and configured integration behavior | unexercised external mutation/UI edge cases |
| Performance | Runtime-proven for bounded telemetry slice | workload, direct Prometheus comparison, exporter-loss recovery | placeholder charts and unproven legacy metric semantics |
| Diagnostics | Runtime-proven for deterministic log/archive slice | Loki marker, archive checksum, ZIP, terminal backfill | full cursor/edge-case matrix and configured analyst |
| Observability | Runtime-proven for direct aggregate signals | direct signals plus Alloy degraded/recovered | standalone native controls; no legacy standalone page claim |

Use `Mapped`, `Implemented`, `Contract-tested`, `Runtime-proven`, and
`Parity-complete` per action group in the corresponding plan. A page-level
label above is bounded to the cited fixture and is not blanket parity for every
legacy control.

The canonical local subject is cluster `1`, node `1`, service `2`, catalog key
`redis-core`, container `node-1-redis-core`. Positive private SSH used disposable
node `2`/service `3` target `platformops-ssh-target`; the supplied credential
for external `216.48.189.195` was rejected, so no claim is made for that host.

## Page plans

| Order | Page | Detailed plan | Primary dependency |
|---|---|---|---|
| 1 | Clusters | [`clusters.md`](clusters.md) | canonical Redis identity and lifecycle |
| 2 | Users | [`users.md`](users.md) | auth and Mailpit; can run alongside early cluster work |
| 3 | Config Manager | [`config-manager.md`](config-manager.md) | deployed Redis with writable config |
| 4 | Diagnostics | [`diagnostics.md`](diagnostics.md) | Redis log path and Loki/Alloy |
| 5 | Monitoring | [`monitoring.md`](monitoring.md) | stable Redis health target; optional GlitchTip |
| 6 | Performance | [`performance.md`](performance.md) | Redis exporter, node exporter, Prometheus |
| 7 | Observability | [`observability.md`](observability.md) | proven Monitoring, Performance, Diagnostics signals |

## How an agent executes a page plan

1. Read the governing documents and the complete page plan.
2. Re-read the cited cPlatform source, templates, JavaScript, and helpers.
3. Reconcile every action row; add missing rows before implementation.
4. Record the pre-change contract fixture and regression baseline.
5. Implement one bounded action group across UI, API schema, persistence,
   orchestration, audit event, and runtime adapter.
6. Add success, validation, authorization, external failure, recovery, and
   cleanup tests before advancing the evidence label.
7. Run targeted tests plus the previously completed page regressions.
8. Run the page-specific Redis phase against a fresh or explicitly checkpointed
   canonical fixture.
9. Record direct evidence and update the matrix/status accurately.
10. At milestone completion, rebuild and run the entire ordered fixture from a
    fresh volume; a page-only checkpoint is not final acceptance.

## Cross-page no-drift gates

- One run ID and one cluster/node/Redis service identity across operational
  pages.
- Canonical IDs, never names, connect page state.
- No page-specific managed service is allowed.
- Every mutation has an operational event and terminal outcome.
- No missing integration is represented as successful empty data or zero.
- No warning path can produce a green authoritative run.
- Cleanup queries database tables, jobs, containers, files, Mailpit, optional
  GlitchTip, Prometheus targets, and Loki labels.
- Protected cPlatform membership/container identity/image/IP/ports/DB-row
  comparisons are recorded before/after; disclose unrelated external volatility
  (for example pre-existing `SERV1006` restart-loop endpoint/MAC changes) rather
  than claiming blanket unchanged state.

## Package definition of done

A page package is done only when all its required matrix rows are
Parity-complete, the UI action is reachable, direct runtime evidence exists,
negative and recovery cases pass, no prior page regresses, documentation points
to the tested commit/image/run, and cleanup is proven.
