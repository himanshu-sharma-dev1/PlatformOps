# Seven-page acceptance handover — 2026-08-22 (DOC-1)

## Status

Strict executor run `parity-redis-20260822T111500-accept18b` and independent run
`parity-redis-20260822T035500Z-e2et1` both passed phases 0–8. Redacted evidence:

```text
/tmp/platformops-redis-acceptance/parity-redis-20260822T111500-accept18b/
/tmp/platformops-redis-acceptance/parity-redis-20260822T035500Z-e2et1/
```

Canonical local subject: cluster `1`, node `1`, service `2`, catalog key
`redis-core`, container `node-1-redis-core`.

| Page | State at the tested boundary |
|---|---|
| Clusters | Parity-complete for the bounded Redis lifecycle/invalid-deploy/cleanup action set; positive disposable SSH branch runtime-proven |
| Config Manager | Parity-complete for exact file bytes, `CONFIG GET`, apply, drift, compare and rollback |
| Users | Parity-complete only for API + Mailpit + browser invite/session; full admin UI browser coverage is not claimed |
| Monitoring | Runtime-proven for Redis stop/recovery and configured GlitchTip support |
| Performance | Parity-complete for bounded load/direct Prometheus/exporter-loss recovery; placeholder charts excluded |
| Diagnostics | Parity-complete for deterministic marker/archive SHA/ZIP/Loki/terminal backfill slice |
| Observability | Runtime-proven for direct aggregate signals and Alloy degraded/recovered; native controls are PlatformOps-only |

## Verified supporting checks

Backend `112 passed`; OpenAPI `142/166`; Node 20 production build plus `31
checks passed` UX run; Python compile, Ansible, isolated-runtime and diff checks
passed. Users used Browser + Mailpit. Config used exact bytes and `CONFIG GET`.
Diagnostics used exact Loki marker/archive SHA/ZIP/backfill. Monitoring used
stop/recovery and configured GlitchTip. Performance used bounded workload/direct
Prometheus/exporter-loss recovery. Observability used direct signals and Alloy
degraded/recovered. Cleanup reported zero owned resources; artifact scans found
zero secrets.

Positive private SSH used disposable node `2`/service `3`, target
`platformops-ssh-target`: exact config read/apply/rollback, inspect/PONG, bad-key
terminal failure with no local fallback, and ephemeral-key destruction. The
supplied credential for external `216.48.189.195` was rejected; no claim is made
for that host.

## Safety and residuals

Support services were private and isolated: no host Docker socket, cPlatform
network, or forbidden ports. Current GlitchTip is `6.1.9`. Protected cPlatform
membership/container identity/image/IP/ports/DB-row comparison was equal with no
acceptance references. A pre-existing `SERV1006` restart loop changed its
restart-count endpoint/MAC during observation; this external volatility is
disclosed and is not a blanket unchanged claim. Legacy action rows remain at
Mapped/Implemented/Contract-tested where the bounded runs did not exercise them.
