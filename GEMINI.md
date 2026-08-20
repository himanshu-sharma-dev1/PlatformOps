# GEMINI.md — PlatformOps current-page cPlatform parity

## Mission and scope

PlatformOps is a FastAPI/React port of selected cPlatform operator behavior.
The active goal is exact end-to-end functional parity for only seven existing
pages: Clusters, Config Manager, Users, Monitoring, Performance, Diagnostics,
and Observability.

UI styling may remain different. Validation, defaults, persistence, jobs,
runtime side effects, errors, lifecycle, and operator reachability must match.

Do not add Batch I/O, Stream I/O, Model Train, Model Deploy, Model Compare,
Applications, DB-pull inference, or other cPlatform pages during this program.
Do not implement PlatformOps Advanced pages (Topology, Policy, Audit,
Reliability) as parity deliverables.

cPlatform has no standalone Observability Stack page. Only behavior derived
from cPlatform Monitoring, SystemMonitoring, Diagnostics, ClusterConfig, and
their helpers belongs in Observability parity. PlatformOps-only stack
management, incidents, SLOs, policy, secrets, maintenance, capacity, and
runbooks do not count toward completion.

## Sources of truth

Read in this order:

1. `docs/current-pages-cplatform-parity-plan.md` — phased implementation and
   acceptance plan.
2. `docs/selected-page-functional-parity.md` — authoritative action mapping and
   current gaps.
3. `docs/redis-seven-page-acceptance-fixture.md` — the single-service runtime
   fixture, scenario sequence, evidence bundle, failures, and cleanup contract.
4. `docs/mvp-status.md` — evidence ledger and runtime limitations.
5. `docs/next-validation-plan.md` — immediate proof sequence.
6. `docs/features/*.md` — detailed references when they agree with source.

The references at `/root/cPlatform` and `/home/ubuntu/cplatform_master` are
read-only. Current source wins over stale parity documents. Never edit either
reference checkout.

## Architecture

- React/TypeScript pages and shared state under `apps/web/src/` call `/api`.
- FastAPI routers under `apps/api/platformops/routers/` validate requests and
  delegate to orchestrators.
- SQLAlchemy models/jobs/events persist control-plane state.
- Orchestrators under `apps/api/platformops/orchestrator/` call Docker, Ansible,
  SSH, Prometheus, Loki, GlitchTip, and email adapters.
- Catalog assets under `catalog/` define service/dependency/form behavior.
- The production API image serves the compiled frontend.

Keep interfaces typed and modules cohesive. Put behavior in the appropriate
router, schema, model, and orchestrator module; do not rebuild a monolithic
`main.py`.

## Runtime safety

- Compose project: `platformops-isolated`.
- Current API: `http://127.0.0.1:9020`.
- Optional Mailpit: `http://127.0.0.1:9010`.
- Private DinD: `tcp://docker-engine:2375`.
- Never use live cPlatform port `9002`, its network, containers, volumes, state,
  or the host Docker socket.
- Remote SSH/provider failures must never fall back to local DinD.
- Destructive validation uses unique disposable records and proves cleanup.

## Completion model

Track every cPlatform action separately:

- **Mapped**: legacy route/view/helper/input/output/side effect identified.
- **Implemented**: reachable PlatformOps UI/API/persistence/orchestrator path.
- **Contract-tested**: validation, payloads, auth, events, and failures tested.
- **Runtime-proven**: real isolated side effect and terminal state observed.
- **Parity-complete**: every prior gate passes.

Do not use broad percentages or “done” labels. HTTP 200/202 and job creation are
not runtime proof. Poll terminal jobs and verify database, container/file,
email, Prometheus/Loki/GlitchTip, or cleanup evidence as appropriate.

## Non-regression rules

- Preserve unknown valid service configuration with deep merge.
- Redact passwords, tokens, private keys, connection strings, and sensitive log
  material from responses, events, jobs, and test artifacts.
- Every mutation records an operational event.
- Enforce authorization in the API, not only the UI.
- Keep cluster/node/service selection canonical across all seven pages.
- Represent missing integrations as unavailable, not empty success or sample
  data.
- Never weaken tests, assertions, terminal polling, or cleanup checks.
- Authoritative E2E uses one canonical `redis-core` target across Clusters,
  Config, Monitoring, Performance, Diagnostics, and Observability. Users uses
  the same run with Mailpit. Exporters, Prometheus, Loki/Alloy, GlitchTip, and
  Mailpit are evidence infrastructure, not additional feature targets.

After backend changes, run targeted tests, API compilation, backend tests,
`make isolated-verify`, and the affected isolated scenario. After frontend
changes, run targeted tests and `npm run build`. Before a milestone, run the
full seven-page suite from a fresh fixture. If host tools are missing, use the
production image and state the limitation honestly.

## Page execution order

1. Freeze the seven-page action manifest and baseline.
2. Complete Cluster → Node → Service and Users/invite reachability.
3. Prove Config apply/drift/restore against a real runtime file.
4. Complete Diagnostics tails/cursors/archives/backfill/Loki evidence.
5. Complete Monitoring health/GlitchTip and Performance exporters/PromQL.
6. Restrict Observability to cPlatform-derived integrated readiness.
7. Run the complete clean-fixture seven-page regression and cleanup audit.

## Known current gaps

- Retained isolated state is not a clean acceptance fixture.
- Config apply/restore lacks successful fresh runtime proof; a retained restore
  job failed with a detached-session error.
- Invite acceptance routing has depended on a nonexistent controller renderer
  and needs explicit reachability proof.
- Optional GlitchTip and populated Prometheus/Loki flows need disposable proof.
- Some Performance response fields are placeholders and must not be presented
  as measured telemetry.
- Observability contains PlatformOps-native behavior that must be separated
  from the cPlatform-derived parity gate.

## Git and documentation

Use commit identity:

```text
himanshu-sharma-dev1
himanshu-sharma-dev1@users.noreply.github.com
```

Preserve unrelated work. Update the action matrix and `docs/mvp-status.md` with
exact commands and evidence whenever a row advances. Do not overwrite
historical evidence; label it by date, commit, image, environment, and port.
