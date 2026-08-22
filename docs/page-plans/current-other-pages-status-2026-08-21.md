# Non-Cluster pages — current functional status and execution handoff

> **Superseded status — 2026-08-22 (DOC-1).** The dated baseline and detailed
> gap notes below are retained as history. Use the verified checkpoint here and
> the per-page plans for current labels; do not treat the historical “not
> runtime-complete” statements as current evidence.

## Verified 2026-08-22 checkpoint

Strict executor run `parity-redis-20260822T111500-accept18b` and independent run
`parity-redis-20260822T035500Z-e2et1` both passed phases 0–8. Redacted evidence
is under `/tmp/platformops-redis-acceptance/<run-id>/`.

| Page | Current bounded state | Evidence and limits |
|---|---|---|
| Users | Runtime-proven invite/session slice; parity-complete only for that slice | Browser + Mailpit delivery, preview/accept/login and token terminal paths; no full Users-page browser automation |
| Config Manager | Runtime-proven; parity-complete for tested Redis config actions | Exact file bytes, `CONFIG GET`, apply, drift, compare, restore/rollback; migration/peer/editor gaps remain |
| Diagnostics | Runtime-proven deterministic log slice | Loki marker, archive SHA, ZIP and terminal backfill; exhaustive cursor/edge cases remain |
| Monitoring | Runtime-proven health and configured integration slice | Stop/recovery and configured GlitchTip; do not blanket-promote external mutation/UI gaps |
| Performance | Runtime-proven bounded telemetry slice | Workload/direct Prometheus and exporter-loss recovery; placeholders remain excluded |
| Observability | Runtime-proven direct aggregate signal slice | Alloy degraded/recovered; native standalone controls are PlatformOps-only, no standalone cPlatform page claim |

Canonical local identity: cluster `1`, node `1`, service `2`, `redis-core`,
`node-1-redis-core`. Positive private SSH: disposable node `2`/service `3`,
`platformops-ssh-target`, including exact config read/apply/rollback, inspect/PONG,
bad-key no-fallback failure and ephemeral-key destruction. The supplied external
`216.48.189.195` credential was rejected; no claim is made for that host.

Support was private/isolated (no host socket, cPlatform network or forbidden
ports), GlitchTip `6.1.9`; cleanup reported zero owned resources and artifact
scans zero secrets. Protected cPlatform membership/container identity/image/IP/
ports/DB-row comparison was equal with no acceptance references. A pre-existing
`SERV1006` restart loop changed restart-count endpoint/MAC during observation;
this external volatility means no blanket “unchanged” claim is valid.

## Purpose and scope

This is the dated status handoff for Config Manager, Users, Monitoring,
Performance, Diagnostics, and Observability. Clusters and Nodes are dependencies
of the shared fixture but are not reassessed here as product pages.

The requirement is cPlatform behavior function-for-function: preserve its
validation, defaults, persistence, side effects, errors, and lifecycle even
when that behavior is mocked, insecure, or operationally limited. Do not add
features merely because PlatformOps could implement a safer or broader design.
UI styling is not a parity gate.

Read this document with:

- [`README.md`](README.md) for execution order and cross-page gates;
- [`../selected-page-functional-parity.md`](../selected-page-functional-parity.md)
  for the action-by-action source map;
- [`../redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md)
  for the one-Redis acceptance contract;
- the complete page plan linked in each status section below.

## Historical audit boundary and 2026-08-21 baseline (retained)

- PlatformOps commit: `5658da2ba3bb1be369b7ad286947b23cca4ccdc6`.
- Read-only cPlatform reference: `/root/cPlatform`, commit `24dc6613b`.
- Current-HEAD audit image: `platformops:audit-5658da2`, image digest
  `sha256:5c7ebbcf1df190c30dc22466a5df58b91d7121f69dbef828aea370ed26631bde`.
- Isolated API: `http://localhost:9020`; private DinD remains the only Docker
  runtime used by PlatformOps.
- Current-HEAD Redis run:
  `parity-redis-20260821T174506Z-5658da2`.
- Python API compilation passed.
- Production Docker build, including the React production build, passed.
- Backend suite passed: `24 passed`, with four deprecation warnings.
- Cluster UX unit script passed under Node 20: `31 checks passed`.
- `scripts/verify_isolated_runtime.py` passed.

The Redis script printed a green banner, but that banner is not parity proof.
It accepted zero/empty/`None` evidence in four operational phases. Evidence
below records the actual values rather than the script's color.

The private DinD also contains pre-existing fixture residue: `node-8-redis-core`
through `node-15-redis-core` are in restart loops because their configured
`/usr/local/etc/redis/redis.conf` files are missing. `node-1-redis-core` is
running. The current-run cleanup did not detect or remove those older
containers, which proves that its “zero residue” assertion is scoped too
narrowly. Do not delete them without reviewing the matching database records;
first make cleanup correlate all prior fixture IDs and distinguish user-owned
targets from disposable audit residue.

## Runtime support stack started for this audit

The existing isolated stack remains on `platformops-isolated_default`. A
separate support network, `platformops-observability_private`
(`172.19.0.0/16`), now contains:

| Component | Image | Host endpoint | Proven state |
|---|---|---|---|
| Loki | `grafana/loki:3.2.1` | `http://localhost:9021` | `/ready` returned 200 and LogQL returned DinD Redis logs |
| Alloy | `grafana/alloy:v1.5.1` | `http://localhost:12346` | `/-/ready` returned 200 and Docker log transfer was recorded |
| GlitchTip web/worker | `iktaraai/services:glitchtip-iktara-6.1.9` | `http://localhost:9030` | migrations passed, web returned 200, worker processed scheduled tasks |
| GlitchTip PostgreSQL | `postgres:16-alpine` | private only | `pg_isready` passed |
| GlitchTip Valkey | `valkey/valkey:7.2` | private only | web and worker connected |

Port `9008` and the cPlatform GlitchTip container were not touched. Alloy is
dual-homed only to `platformops-observability_private` and
`platformops-isolated_default` so it can read the private DinD API at
`tcp://docker-engine:2375`; it is not attached to the cPlatform network and no
host Docker socket is mounted. Its runtime config is
`data/runtime/alloy-observability-private.alloy`.

This is temporary support infrastructure, not cPlatform parity. The checked-in
`docker-compose.observability.yml` is not a reproducible launch contract yet:
it still has obsolete `/home/ubuntu/PlatformOps` mounts, a missing external
network requirement, fixed addresses, a host Docker socket mount, and a port
collision with cPlatform GlitchTip. Repair that Compose definition only as a
bounded infrastructure task; do not count it as an Observability page action.

## Historical executive status (superseded)

| Page | Reachable implementation | Current real proof | Current verdict |
|---|---|---|---|
| Users | API CRUD/invite/session paths and page exist | create, invite, Mailpit token extraction, preview, accept, and invited login passed | Partial; acceptance UI and terminal token/admin cases are not proven |
| Config Manager | workspace, snapshot, diff, apply, drift, restore paths exist | Redis workspace, snapshots, diff, apply, and restore returned success | Partial; live file, `CONFIG GET`, job/event, drift, and rollback effects are not asserted |
| Diagnostics | live/history/archive/backfill/chat contracts exist | bounded live tail returned three lines | Not runtime-complete; Loki history and archives were both empty and advanced paths were not exercised |
| Monitoring | native sweep plus cPlatform GlitchTip compatibility contracts exist | sweep request completed | Not runtime-complete; no direct PING/check row, failure/recovery, or GlitchTip action was proven |
| Performance | node/service/process metric contracts and charts exist | endpoints returned their response shapes | Not runtime-complete; CPU was `None`, process rows were zero, and service telemetry was not proven non-placeholder |
| Observability | native stack controls and pipeline/status views exist | separate Loki/Alloy/GlitchTip support services are healthy | Not parity-complete; page response fields were `None`, direct signal correlation is absent, and native controls have no cPlatform counterpart |

The historical table above said no page was Parity-complete at that checkpoint.
The 2026-08-22 bounded status is the authoritative current position; “Runtime-
proven” remains action-scoped and is not a blanket page claim.

## Users

Complete plan: [`users.md`](users.md).

### What currently works

- Bootstrap administrator login.
- Disposable active-user creation.
- Invitation creation and Mailpit token extraction in the current run.
- Invite preview and acceptance APIs.
- Login with the accepted invite credentials.
- Admin list/create/update/delete and resend/revoke routes exist in source.

### Blocking gaps

- The invite browser branch is guarded by a nonexistent `renderUsersView`, so
  API success does not prove the emailed-link UI.
- Single-use, expiry, revoke/resend invalidation, invalid token, and already-used
  states are not asserted.
- Role/status edits, immediate authorization changes, non-admin denial,
  self-delete behavior, and full user/invite residue cleanup are not proved.

### First executable slice

Execute U0-U1: freeze the cPlatform invite contract, repair and browser-test the
invite route, require Mailpit delivery rather than response-token fallback, and
make every token terminal state a hard assertion. Then execute U2-U4 without
weakening the six-page regression baseline.

## Config Manager

Complete plan: [`config-manager.md`](config-manager.md).

### What currently works

- The Redis config workspace loads.
- Baseline and post-apply snapshots are created.
- Snapshot diff returns non-empty changes.
- Apply and restore paths return terminal success in the harness.

### Blocking gaps

- The harness sends YAML-like `maxmemory: 256mb` but does not prove how it maps
  to valid `redis.conf` syntax.
- It never inspects the mounted file or runs `redis-cli CONFIG GET`.
- Drift returns `None` and is still printed as pass.
- Job/event/restart evidence, pre/post hashes, failure rollback, timeline,
  snapshot view/rename/delete, validation errors, and supported migration
  behavior are not proved.

### First executable slice

Execute G0-G1 against the deployed Redis, then make G2-G4 assert file bytes,
Redis runtime values, terminal jobs, events, and rollback. Decide G5 from the
cPlatform source before implementing it; native-only peer behavior remains
outside parity.

## Diagnostics

Complete plan: [`diagnostics.md`](diagnostics.md).

### What currently works

- Target summary and bounded live container tail routes exist.
- The current Redis run returned three live log lines.
- History, archive, download, backfill, ingestion-stat, and analyst routes are
  present in source.
- The newly started Alloy-to-Loki path can ingest private DinD Redis logs; a
  direct LogQL query returned Redis container streams.

### Blocking gaps

- The authoritative run injected no deterministic marker and accepted zero Loki
  history lines, zero archive files, and zero indexed archives.
- Cursor direction, no-gap/no-duplicate paging, time bounds, rotation, Unicode,
  oversized lines, disappearing containers, safe paths, and checksums are not
  tested.
- Backfill is not polled to terminal state and no exact marker is verified in
  Loki.
- Analyst/chat configured and unavailable states are not grounded in cited log
  evidence.

### First executable slice

Execute D0-D2 with a run-labeled multiline Redis marker and strict cursor
assertions. Then implement/prove D3-D5 through a real archive and terminal Loki
backfill. Execute D6 only with a configured disposable provider or an explicit,
truthful unavailable contract.

## Monitoring

Complete plan: [`monitoring.md`](monitoring.md).

### What currently works

- Cluster/node/service selection and Monitoring UI/API paths exist.
- A native monitoring sweep request completes.
- cPlatform-compatible GlitchTip issue, detail, action, performance, key,
  uptime, health, and runtime-patch routes exist.
- A disposable GlitchTip web/worker is now running on the isolated support
  network, but PlatformOps has not yet been configured with a project token.

### Blocking gaps

- The harness phase called “failure and recovery” does not stop Redis.
- It does not assert Redis PING, direct container state, persisted check rows,
  events, timing, UI transitions, or recovered evidence.
- No GlitchTip project/token wiring, ingested issue/transaction, event detail,
  action, key, or uptime monitor side effect is proved.
- Optional-unavailable and successful-empty integration states are not reliably
  distinguished by acceptance.

### First executable slice

Execute M0-M2 first: make Redis health direct, target-scoped, persisted, and
provably fail/recover. Then provision a disposable GlitchTip organization,
project, and token and execute M3-M4 end-to-end. Keep GlitchTip Performance
transactions separate from the Prometheus Performance page.

## Performance

Complete plan: [`performance.md`](performance.md).

### What currently works

- Node/service selection, window controls, refresh paths, process table, and
  metric response schemas exist.
- Current endpoints respond without crashing.

### Blocking gaps

- Current Redis evidence reported `cpu=None`, zero process rows, and only the
  list of service response keys.
- No workload, exporter target, direct PromQL comparison, run label, freshness,
  units, aggregation, isolation, or counter-reset behavior is proved.
- `log_error_rate`, `queue_depth`, and `latency_ms_p95` are placeholders;
  `error_rate_series` is not currently true error telemetry.
- Collector loss/recovery and browser refresh/stale-request behavior are absent.

### First executable slice

Execute P0 before changing queries: freeze exact cPlatform semantics and remove
or label every unsupported metric. Execute P1-P4 with Redis exporter,
node/process exporters, deterministic load, and direct Prometheus comparisons.
Then execute P5-P6 for browser behavior, target isolation, collector failure,
and recovery.

## Observability

Complete plan: [`observability.md`](observability.md).

### What currently works

- Native deploy/status/teardown/bootstrap and pipeline report paths exist.
- The separate Loki, Alloy, and GlitchTip support services are actually running
  and healthy for future page acceptance.
- Alloy-to-Loki delivery from private DinD has direct log evidence.

### Blocking gaps

- cPlatform has no standalone Observability page. Native stack lifecycle cannot
  be counted as cPlatform parity.
- The current page/harness returned `status=None` and `loki=None` but still
  printed pass.
- Pipeline state can be inferred from database service status instead of direct
  container, Redis, Prometheus target/sample, Loki marker, and Alloy probes.
- Target identity, freshness, cross-page correlation, per-signal degradation,
  and recovery are not proved.

### First executable slice

Execute O0 first and classify every control as cPlatform-derived or native-only.
Then execute O1-O2 so the page aggregates direct evidence for the same Redis
IDs used elsewhere. O3 must route any genuine ClusterConfig collector action
through Cluster lifecycle jobs. Execute O4-O5 only after Monitoring,
Performance, and Diagnostics provide independently proven signals.

## Ordered implementation and regression handoff

1. Do not expand scope or create another managed target. Reuse one canonical
   Redis identity and supporting exporters/telemetry only.
2. Complete Users U0-U1 and Config G0-G1 contract/reachability slices.
3. Complete Config runtime correctness G2-G4.
4. Complete Diagnostics D0-D5 so Loki has deterministic evidence.
5. Complete Monitoring M0-M2, then optional GlitchTip M3-M4.
6. Complete Performance P0-P6 with real exporters and workload.
7. Complete Observability O0-O5 as a derived view, not a new parity product.
8. For every bounded slice: targeted contract tests, backend suite, production
   frontend build when affected, isolated verifier, page fixture, prior-page
   regression, terminal job polling, direct side-effect inspection, and cleanup.
9. At the milestone, rebuild from current HEAD and run the full ordered fixture
   from a fresh disposable state. Fail on warnings, empty required data,
   placeholder values, unreachable integrations represented as empty success,
   stale evidence, or residue from any run—not only the current run ID.

## Immediate acceptance-harness corrections

At the 2026-08-21 baseline, before any future green banner could be evidence,
the following assertions still needed to be fatal:

- deployed Redis must be `running` and answer `PING` after config apply/restore;
- Config must match file bytes plus `CONFIG GET` before and after restore;
- Diagnostics must return a run marker from live tail, history, archive, and
  Loki after a terminal backfill;
- Monitoring must prove an actual stop, failed health, restart, and recovered
  health with new evidence;
- Performance must require healthy exporter targets and non-empty run-scoped
  samples generated by load;
- Observability must require direct ready/fresh values for every mandatory
  signal and exact partial degradation during failure injection;
- Users must prove Mailpit delivery, browser acceptance, token terminal states,
  authorization changes, and cleanup;
- residue checks must include all parity fixture database rows, jobs, events,
  DinD containers, files, Mailpit messages, GlitchTip objects, Prometheus
  targets/labels, and Loki streams/labels from every prior audit run.

At that historical boundary the honest status of all six pages was implemented
but incomplete. The 2026-08-22 verified checkpoint above supersedes that
conclusion for the bounded action slices while retaining these gates as future
full-page coverage guidance.
