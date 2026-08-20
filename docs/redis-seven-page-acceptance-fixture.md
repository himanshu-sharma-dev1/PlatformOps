# Golden Redis fixture for seven-page cPlatform parity

## 1. Purpose

Use one deployed Redis service as the canonical subject-under-test for the
complete current-page parity program. The same cluster, node, service row,
container, config file, log stream, metrics labels, events, and runtime identity
must flow through Clusters, Config Manager, Monitoring, Performance,
Diagnostics, and Observability.

Users is tested in the same isolated environment, but Redis cannot prove user
invitations or authorization. Users uses disposable accounts and Mailpit while
sharing the same run ID and evidence bundle.

This avoids page-specific fake fixtures and proves that the pages are coherent
views of one real managed service.

## 2. What “one service” means

### Single product target

Exactly one managed application/infrastructure service is the parity target:

- catalog key: `redis-core`;
- image: pinned `redis:7-alpine` digest for authoritative runs;
- PlatformOps service row: one per run;
- DinD container: `node-{node_id}-redis-core`;
- one writable runtime config;
- one deterministic log source;
- one stable set of Prometheus labels.

Do not create separate demo services for Config, Diagnostics, Monitoring,
Performance, or Observability.

### Supporting test infrastructure

These components do not violate the one-service rule because they are evidence
transport or test harness dependencies, not page targets:

- PlatformOps API/frontend, PostgreSQL, RabbitMQ, and private DinD;
- Prometheus and a Redis exporter for Redis metrics;
- node exporter for node-level metrics;
- Loki and Alloy for log ingestion;
- optional disposable GlitchTip for Monitoring integration behavior;
- Mailpit for Users invitation delivery;
- a load/log injector controlled by the test harness.

Supporting components must never appear as alternative selected services or be
counted as cPlatform feature completion.

## 3. Isolation contract

- Compose project: `platformops-isolated`.
- PlatformOps API: `http://127.0.0.1:9020`.
- Mailpit UI/API: `http://127.0.0.1:9010`.
- Managed Docker endpoint: `tcp://docker-engine:2375`.
- Never use cPlatform port `9002`, its network, volumes, containers, database,
  or host Docker socket.
- Every run uses a unique identifier such as
  `parity-redis-YYYYMMDDTHHMMSSZ-<short-sha>`.
- All created names, snapshots, users, invites, jobs, log markers, and evidence
  files include the run ID.
- Authoritative runs start from a fresh project volume or a fixture reset whose
  deletion targets were explicitly enumerated and reviewed.

## 4. Canonical fixture identity

The harness creates and records one immutable identity bundle:

```json
{
  "run_id": "parity-redis-<timestamp>-<sha>",
  "cluster_name": "parity-redis-<run>-cluster",
  "node_name": "parity-redis-<run>-node",
  "service_key": "redis-core",
  "service_name": "Parity Redis <run>",
  "container_name": "node-<node-id>-redis-core",
  "config_path": "/usr/local/etc/redis/redis.conf",
  "log_path": "/var/log/redis/redis.log",
  "metrics_job": "redis-parity-<run>"
}
```

All page requests use database IDs from this bundle. Names are display values,
not join keys.

## 5. Redis runtime profile

## 5.1 Writable configuration

The current catalog points at a repository configuration path mounted read-only.
That is suitable for deployment but cannot prove live apply/restore. The
acceptance fixture must materialize a run-specific writable copy under the
node volume and mount that copy into the container.

Required behavior:

1. seed a deterministic baseline file before deployment;
2. persist the exact host/runtime paths in service configuration;
3. mount the runtime file read-only to Redis only if PlatformOps applies changes
   to the host-side writable file; otherwise use a writable mount with explicit
   ownership;
4. apply through PlatformOps, not by editing the file in the harness;
5. restart/reload through the same PlatformOps job contract;
6. verify with both file inspection and `redis-cli CONFIG GET`;
7. restore the baseline through PlatformOps and repeat verification.

Baseline controls should be safe and externally observable:

```text
appendonly yes
loglevel notice
logfile /var/log/redis/redis.log
maxmemory 64mb
maxmemory-policy allkeys-lru
save 60 1000
```

The semantic config test changes `maxmemory` and `loglevel`, then restores them.
Do not change networking/auth in the happy path because that could make later
pages unreachable. Network/auth changes belong to isolated failure cases with
guaranteed recovery.

## 5.2 Deterministic health

The authoritative health probe is `redis-cli ping` returning `PONG`. Record:

- PlatformOps persisted status;
- PlatformOps live-status response;
- monitoring sweep/check row;
- direct DinD container state/health;
- direct Redis PING result;
- timestamps and target IDs for every observation.

Health failure injection stops the one Redis container through the controlled
fixture harness. PlatformOps must observe unhealthy/missing state. Recovery
starts the same container and proves the status returns to healthy without
creating another service row.

## 5.3 Deterministic logs

Redis startup/restart provides genuine readiness messages. The fixture also
needs unique markers for cursor/archive/Loki assertions.

Use a fixture-owned log injector that writes clearly labeled test records to
the configured Redis log file or sends them through the same container log path.
Markers must state that they are test evidence, for example:

```text
PARITY_REDIS run=<run-id> seq=0001 level=notice event=baseline
PARITY_REDIS run=<run-id> seq=0002 level=warning event=controlled-warning
PARITY_REDIS run=<run-id> seq=0003 unicode=नमस्ते oversized=false
```

The injector is not a PlatformOps feature and cannot be used to claim log
generation parity. It only creates deterministic service evidence. Include:

- ordered markers across at least three pages;
- a Unicode marker;
- one long line near the supported limit;
- enough lines for forward/backward pagination;
- a rotation boundary;
- one marker after rotation;
- no secrets or credentials.

## 5.4 Deterministic load and metrics

Generate Redis commands for a bounded interval using `redis-benchmark` or a
small harness client. Use a known mix of SET/GET/INCR and fixed concurrency.
Record start/end timestamps, command count, concurrency, and key prefix.

Redis exporter must expose, at minimum:

- `redis_up`;
- connected clients;
- used memory;
- commands processed or commands/sec;
- keyspace hits/misses;
- evictions where intentionally exercised.

Node exporter provides node CPU/memory/disk/network evidence. Prometheus scrape
labels must include the canonical run/service/node identity so a second stale
target cannot satisfy assertions.

Placeholder PlatformOps fields remain unavailable unless a real PromQL/data
source exists. Never convert absence into numeric zero.

## 6. Page-by-page fixture matrix

| Page | Redis evidence | Required action/proof | Supporting infrastructure |
|---|---|---|---|
| Clusters | one service row and DinD container | create cluster/node/service, preflight, deploy, terminal job, inspect, status, redis PING, logs, delete | DinD |
| Config | one writable `redis.conf` | baseline snapshot, validate, apply, terminal job, inspect file, `CONFIG GET`, drift, compare, restore | DinD filesystem |
| Monitoring | one health target | healthy sweep, stop Redis, observe degraded/missing, recover same container, optional GlitchTip action flow | optional GlitchTip |
| Performance | one Redis metric target | generate bounded load, non-empty PromQL, compare direct query, distinguish unavailable/zero | redis exporter, node exporter, Prometheus |
| Diagnostics | one Redis log source | bounded tail, cursor history, rotation, archive, download, backfill, Loki marker query | Alloy, Loki, log injector |
| Observability | same target and evidence paths | readiness/freshness from real container, scrape, and logs; precise degradation/recovery | exporters, Prometheus, Alloy, Loki |
| Users | no Redis behavioral claim | invite/mail/accept/login/role/revoke/resend/token terminal states | Mailpit |

Every page must assert that returned `cluster_id`, `node_id`, `service_id`,
container name, and run label match the canonical identity bundle.

## 7. Authoritative scenario order

Run sequentially to prevent one page's failure injection from invalidating the
next page unexpectedly.

## Phase 0 — Preflight and evidence directory

1. Record Git commit, dirty state, Compose config hash, image IDs/digests,
   timestamp, host tools, and test configuration.
2. Run `make isolated-verify` and Compose config validation.
3. Assert ports `9020`/`9010` and reject `9002`/old isolated defaults.
4. Verify no container/network/volume belongs to cPlatform.
5. Create an evidence directory outside committed source, scoped to the run ID.
6. Create the identity manifest before any mutations.

Exit: environment and targets are uniquely identified and safe.

## Phase 1 — Users identity baseline

1. Authenticate as bootstrap admin.
2. Create one active disposable operator and one invited user.
3. Prove Mailpit delivery and token preview/accept/login.
4. Exercise role/status update, revoke/resend, old/new token behavior.
5. Keep the active operator available for later authorization checks.

Exit: Users behavior is proven independently and the test has a non-bootstrap
operator for page authorization checks.

## Phase 2 — Cluster → Node → Redis

1. Create canonical cluster.
2. Create canonical local-DinD node with explicit runtime endpoint.
3. Validate connection and collect facts.
4. Register `redis-core` with writable config/log paths.
5. Run dependency preflight and verify no fabricated missing dependency.
6. Submit deployment and poll terminal success.
7. Verify database external ID, direct DinD inspect, image digest, mounts,
   command, container state, `redis-cli ping`, and readiness log.
8. Refresh service/node status and confirm all identifiers.

Exit: one real Redis service is healthy and canonical for remaining phases.

## Phase 3 — Config lifecycle

1. Read live config and compare it to seeded baseline.
2. Create named baseline snapshot.
3. Validate a safe semantic change.
4. Apply and poll terminal success.
5. Verify file content, `CONFIG GET maxmemory`, service restart/reload evidence,
   post-snapshot, timeline, and operational event.
6. Create controlled out-of-band drift in the fixture file, detect it, then
   restore the controlled state so the product remains authoritative.
7. Compare snapshots.
8. Restore baseline, poll success, and verify file plus `CONFIG GET` rollback.
9. Run invalid YAML and forced apply/restart failure cases, then recover.

Exit: live apply/drift/compare/restore are proven without replacing Redis.

## Phase 4 — Diagnostics lifecycle

1. Inject ordered run markers and confirm bounded tail.
2. Paginate forward/backward and assert no gaps/duplicates.
3. Exercise Unicode, long line, time range, and rotation boundary.
4. Index archive, list, view, and download; compare checksums/markers.
5. Backfill to Loki, poll terminal job, and query exact run markers.
6. Verify ingestion statistics and empty/unavailable distinctions.
7. Exercise missing file, invalid path, and disappearing-container errors.
8. Run configured analyst evidence or assert honest unavailable state.

Exit: the same Redis logs are traceable from runtime to archive to Loki.

## Phase 5 — Monitoring failure and recovery

1. Run healthy sweep and correlate PING/container/check evidence.
2. Stop Redis through the controlled fixture interface.
3. Poll until PlatformOps reports the accurate degraded/missing state.
4. Confirm Config/Diagnostics/Performance do not fabricate success while down.
5. Start the same container; verify identity did not change unexpectedly.
6. Poll recovery and confirm a new health check/event.
7. If GlitchTip profile is enabled, exercise issue/key/uptime actions scoped to
   this service and clean them up.

Exit: health degradation and recovery propagate across pages coherently.

## Phase 6 — Performance load

1. Capture idle baseline and direct Prometheus queries.
2. Run bounded workload with run-prefixed keys.
3. Query PlatformOps node and service metrics for the exact window.
4. Compare non-empty series, labels, units, timestamps, and approximate trends
   to direct Prometheus results.
5. Stop exporter while Redis remains healthy; verify telemetry unavailable is
   distinct from service unhealthy and from measured zero.
6. Restart exporter and verify freshness/recovery.
7. Delete workload keys and record cleanup count.

Exit: real Redis/node telemetry is proven and correctly scoped.

## Phase 7 — Observability integration

1. Verify one integrated view references the canonical Redis target.
2. Assert real Redis container status, Prometheus target/sample freshness, Loki
   readiness/recent marker, and exact degraded reasons.
3. Stop Alloy or exporter individually and verify only the responsible signal
   degrades.
4. Recover components and verify readiness returns.
5. Confirm navigation opens the same Redis in Monitoring, Performance, and
   Diagnostics.
6. Do not require or credit unrelated PlatformOps-only SRE functions.

Exit: Observability correlates existing cPlatform-derived behavior rather than
claiming a separate product stack.

## Phase 8 — Full cleanup and negative residue check

1. Delete Redis through PlatformOps and poll terminal cleanup.
2. Verify the one DinD container, run-specific config/log/data directories,
   snapshots, archives, checks, jobs eligible for cleanup, and workload keys.
3. Delete node and cluster in supported order.
4. Delete disposable users/invites and confirm tokens cannot be reused.
5. Delete optional GlitchTip monitors/projects created by the run.
6. Query by run ID across tables, events, Mailpit, Loki labels, and containers;
   record intentional retained audit evidence separately.
7. Assert no cPlatform resource changed.

Exit: no operational fixture residue remains; only explicitly retained sanitized
test evidence exists.

## 8. Failure matrix

Every authoritative run includes at least these failures:

| Boundary | Injection | Expected PlatformOps result | Recovery proof |
|---|---|---|---|
| Deploy | invalid image/tag | failed terminal job; no running status | corrected deploy succeeds |
| Remote target | unreachable endpoint | honest connection error; no local fallback | canonical DinD target works |
| Config validation | invalid directive/YAML | rejected before mutation | baseline unchanged |
| Config apply | unwritable/detached target | failed terminal job; pre-snapshot retained | writable target restore succeeds |
| Runtime health | stop Redis | monitoring degraded and PING fails | same Redis recovers |
| Logs | missing/rotated path | bounded not-found/rotation behavior | new marker becomes visible |
| Loki | stop Loki/Alloy | unavailable, not empty success | marker query recovers |
| Prometheus/exporter | stop exporter | telemetry unavailable, Redis still healthy | fresh samples return |
| GlitchTip | disabled/unreachable | optional integration unavailable | disposable profile works |
| Mail | stop Mailpit/SMTP | invite delivery failure is visible | resend delivers once restored |
| Authorization | non-admin mutation | forbidden, no side effect/event success | admin action succeeds |
| Cleanup | delete parent with children | exact lifecycle impact/block/order | supported cleanup completes |

## 9. Evidence bundle

Produce one manifest plus phase artifacts:

```text
<run-id>/
  manifest.json
  phase-0-preflight.json
  phase-1-users.json
  phase-2-cluster-redis.json
  phase-3-config.json
  phase-4-diagnostics.json
  phase-5-monitoring.json
  phase-6-performance.json
  phase-7-observability.json
  phase-8-cleanup.json
  docker-inspect-redacted.json
  jobs-redacted.json
  events-redacted.json
  prometheus-queries.json
  loki-queries.json
  mailpit-redacted.json
  final-summary.json
```

Each phase records requests, status codes, entity IDs, job IDs and terminal
states, timestamps, direct-runtime probes, assertions, cleanup actions, and
redacted errors. Never store tokens, passwords, private keys, raw authorization
headers, or unrelated logs.

`final-summary.json` reports per action—not per page percentage—Mapped,
Implemented, Contract-tested, Runtime-proven, or Parity-complete.

## 10. Regression structure

Split the eventual harness into reusable layers while keeping one orchestrated
run:

- fixture lifecycle and identity manifest;
- API client/auth and terminal-job polling;
- direct DinD/Redis evidence adapter;
- config file/runtime assertions;
- deterministic log/load injectors;
- Prometheus/Loki/Mailpit/GlitchTip evidence adapters;
- page scenario modules;
- residue/cleanup auditor.

Page modules may run independently during development against a fixture
checkpoint, but milestone acceptance always runs the complete sequence from a
fresh fixture. A checkpoint run cannot be reported as a full pass.

## 11. Definition of fixture success

- One and only one managed Redis service is used across the six operational
  pages.
- Every response/evidence item matches the canonical IDs and run labels.
- Config changes and restore are visible in both file and Redis runtime.
- Logs are traceable through tail, history, archive, backfill, and Loki.
- Monitoring sees real stop/recovery without service replacement.
- Performance shows real labeled load and honest telemetry loss.
- Observability correlates those real signals without non-cPlatform credit.
- Users invite/auth behavior passes through Mailpit in the same run.
- All required actions reach terminal states and all expected failures remain
  truthful.
- Cleanup proves no operational residue and no cPlatform change.
