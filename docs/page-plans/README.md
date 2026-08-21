# Seven-page cPlatform parity execution index

## Governing goal

Complete scientifically verifiable cPlatform behavioral parity for only the
seven current PlatformOps pages. Do not add other cPlatform pages or count
PlatformOps-only features. The shared contract remains:

- [`../current-pages-cplatform-parity-plan.md`](../current-pages-cplatform-parity-plan.md)
- [`../redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md)
- [`../selected-page-functional-parity.md`](../selected-page-functional-parity.md)
- [`../mvp-status.md`](../mvp-status.md)

## Mandatory evidence reconciliation

Commit `0d0276b` introduced the Redis harness and records a green run with ID
`parity-redis-20260820T211916Z-da398c8`. That is useful evidence, but it cannot
be treated as final proof because:

- the run ID identifies `da398c8`, not current HEAD `0d0276b`;
- the authoritative action matrix still contains Implemented and Unverified
  rows;
- multiple harness phases accept warnings, empty data, or HTTP 200 as success;
- Monitoring does not actually stop/recover Redis;
- Performance does not generate load or compare direct Prometheus evidence;
- Config does not assert runtime `redis-cli CONFIG GET` values;
- Diagnostics does not require deterministic markers, archives, or Loki data;
- Users can fall back to a response token rather than proving Mailpit delivery;
- cleanup prints success without a complete residue query.

Therefore every page plan begins with contract reconciliation and ends with a
fresh HEAD-built evidence run. Never change documentation labels merely to
match the commit message.

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
- cPlatform resources are counted/hashed before and after and remain unchanged.

## Package definition of done

A page package is done only when all its required matrix rows are
Parity-complete, the UI action is reachable, direct runtime evidence exists,
negative and recovery cases pass, no prior page regresses, documentation points
to the tested commit/image/run, and cleanup is proven.
