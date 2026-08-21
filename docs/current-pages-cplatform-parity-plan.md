# Current-page cPlatform parity implementation plan

## 1. Goal and fixed scope

Complete end-to-end behavioral parity between PlatformOps and cPlatform for
only these seven existing pages:

1. Clusters
2. Config Manager
3. Users
4. Monitoring
5. Performance
6. Diagnostics
7. Observability

The goal is working operator behavior, not visual cloning, generalized
hardening, or product expansion. A capability is complete only when its UI
action, API contract, persistence, orchestration, real isolated side effect,
failure behavior, and regression coverage are demonstrated.

### Included

- Every cPlatform action belonging to one of these pages or required for that
  page's end-to-end behavior.
- Shared Cluster → Node → Service selection, catalog, deployment, status,
  configuration, logs, monitoring, and lifecycle behavior.
- Monitoring/SystemMonitoring/Diagnostics behavior needed by Observability.
- Compatibility routes only where an included browser contract or callback
  actually depends on the legacy path or payload.

### Excluded

- Batch I/O, Stream I/O, Model Train, Model Deploy, Model Compare,
  Applications, DB-pull inference, and their supporting workflows.
- Advanced pages: Topology, Policy, Audit, and Reliability as standalone
  products. Shared event/topology data may still support Clusters.
- PlatformOps-only incidents, SLOs, policy scans, secrets, maintenance,
  capacity, runbooks, or generic governance.
- PlatformOps-only observability-stack product features with no cPlatform
  counterpart. They may remain, but cannot count toward parity.
- Pixel parity, broad refactoring, production hardening, cloud expansion, and
  unrelated catalog products.

[`selected-page-functional-parity.md`](selected-page-functional-parity.md) is
the authoritative action inventory. This document defines delivery order and
acceptance.

All authoritative runtime acceptance uses the single subject described in
[`redis-seven-page-acceptance-fixture.md`](redis-seven-page-acceptance-fixture.md):
one canonical `redis-core` service across every operational page. Exporters,
Prometheus, Loki/Alloy, optional GlitchTip, and Mailpit are supporting evidence
infrastructure, not additional parity targets. Users uses the same run but is
proved with disposable accounts and Mailpit rather than Redis behavior.

Detailed execution plans live under [`page-plans/`](page-plans/README.md):

- [Clusters](page-plans/clusters.md)
- [Config Manager](page-plans/config-manager.md)
- [Users](page-plans/users.md)
- [Monitoring](page-plans/monitoring.md)
- [Performance](page-plans/performance.md)
- [Diagnostics](page-plans/diagnostics.md)
- [Observability](page-plans/observability.md)

The page files own implementation detail and page-specific acceptance. This
document owns shared scope, order, and cross-page gates. If they conflict, stop
and reconcile them against current cPlatform source before implementation.

## 2. Evidence and completion model

Track every action separately:

- **Mapped**: cPlatform route, view branch, helper, input, output, and side
  effect are identified.
- **Implemented**: PlatformOps UI/API/persistence/orchestrator paths exist.
- **Contract-tested**: validation, payloads, authorization, events, and failures
  are covered.
- **Runtime-proven**: a fresh disposable run demonstrates the real side effect
  and terminal state.
- **Parity-complete**: every preceding state passes and the action is reachable
  from the page.

Do not publish page percentages. HTTP 200/202 or job creation is not runtime
proof. Poll async jobs to terminal state and verify database plus container,
file, email, telemetry, or cleanup evidence.

## 3. Shared foundation

### Contract inventory

Before implementing an action, record its legacy route/method, discriminator,
fields, defaults, coercion, validation, status/payload, mutations, external
calls, timeouts, and UI loading/empty/error/retry/confirmation states. Capture
sanitized representative fixtures; never copy live secrets or customer data.

### API, persistence, and jobs

- Keep native APIs under `/api`; retain legacy paths only when required.
- Use Pydantic request/response schemas at every page boundary.
- Deep-merge service `config_json`; never discard unknown valid fields.
- Every mutation records actor, target, action, outcome, and redacted summary.
- Use transactions for multi-row lifecycle operations; preserve nullable
  history and delete non-nullable owned rows deterministically.
- Jobs persist queued/running/succeeded/failed/cancelled, timestamps, sanitized
  output/error, and external runtime IDs.

### Isolation and target correctness

- Use Compose project `platformops-isolated`, API `9020`, optional Mailpit
  `9010`, and private DinD `tcp://docker-engine:2375`.
- Never touch live cPlatform port `9002`, its containers/network/volumes/state,
  or the host Docker socket.
- `/root/cPlatform` and `/home/ubuntu/cplatform_master` are read-only.
- Remote SSH/provider failures never fall back to local DinD.
- Destructive tests use unique disposable records and prove cleanup.
- Do not create page-specific target services. Reuse the golden Redis identity,
  writable config, deterministic logs, failure controls, and metric labels for
  Clusters, Config, Monitoring, Performance, Diagnostics, and Observability.

### Cross-page selection

Clusters owns canonical cluster/node/service identifiers. Config, Diagnostics,
Monitoring, Performance, and Observability consume those identifiers rather
than conflicting name-only caches. Changing/deleting a parent clears invalid
children; reload restores only existing authorized IDs; API authorization is
not delegated to navigation visibility.

## 4. Page plans

## 4.1 Clusters

Legacy authority: `/PlatformIO/ClusterView/`, `/PlatformIO/ClusterConfig/`,
`cPlatformIO/views.py:1375-1902`, and called helpers.

### Cluster inventory

- Complete create/edit/list/detail/delete for legacy fields, defaults, repo and
  registry types, and explicit credential-replacement semantics.
- Test repo/registry connections with redacted errors and without replacing
  stored secrets accidentally.
- Make summary cards consume the authoritative summary or remove the unused
  fetch; never represent two different truths.
- Match lifecycle impact, confirmation, child blocking, and transactional
  cleanup.

### Node lifecycle

- Complete manual add/edit/delete for host, SSH, volume root, Docker network,
  resources, OS, GPU, and monitoring fields.
- Implement connection validation, facts, onboarding report, remediation,
  discovery, info, and real status with exact failure states.
- Implement provider launch/teardown only where cPlatform supports it and test
  against disposable infrastructure.
- Prove remote discovery/status/deploy never uses local DinD after failure.

### Service lifecycle

- Map every ClusterConfig service field to catalog/persistence.
- Complete add/edit/delete, install-mode aliases, preflight, dependency order,
  placement, missing-dependency actions, deploy/redeploy/execute, adoption,
  runtime patch, status, logs, and cleanup.
- Preserve environment, volumes, health checks, metadata, secrets, catalog
  values, external ID, and container identity across edits/redeploys.
- A deployment passes only after terminal success, Docker inspect, readiness
  log, persisted external ID/status, and truthful failure evidence.

### Cluster acceptance

Fresh fixture: create cluster → node → validate/onboard → catalog Redis service
→ preflight/dependencies → deploy → terminal success → inspect DinD image/name/
state → readiness log → status refresh → open all service-scoped pages → delete
service/node/cluster → verify row/job/event/container cleanup. Repeat with an
invalid target/image and assert failed terminal state and no phantom health.

## 4.2 Config Manager

Legacy authority: `/PlatformIO/ConfigManager/`, ClusterConfig config branches,
`views.py:1553-1693,3128-3483`, and config helpers.

### Workspace and validation

- Load target, live rendered config, schema, snapshots, timeline, drift, and
  supported actions consistently.
- Capability flags must be server-enforced or explicitly informational.
- Match YAML/schema validation, defaults, unknown-field behavior, environment
  substitution, and localized errors before creating a mutation job.

### Snapshots, drift, apply, migration, restore

- Create/name/list/view/compare/delete checkpoints where supported, with hash,
  source, actor, timestamp, target, and rendered content.
- Detect drift from the actual runtime file, not stored content alone.
- Direct apply: validate → pre-snapshot → write real file → required reload or
  restart → verify → persist → post-snapshot.
- On failure, preserve pre-snapshot/evidence and do not advance current config.
- Match actual migration preparation/output without inventing selection,
  ranking, or operations.
- Restore and peer sync must reach terminal state and prove destination file,
  service behavior, rollback/timeline, and partial-failure reporting.

### Config acceptance

Deploy a service with real YAML → snapshot → valid semantic change → terminal
apply → inspect container file → verify reload → introduce/detect drift →
restore → verify file/runtime rollback. Cover invalid YAML, unsupported action,
detached session, write failure, and restart failure.

## 4.3 Users

Legacy authority: `/PlatformIO/Users/`, `/invite/accept/<token>/`,
`views.py:888-923,1929-2005,3028-3059`, and `UserMgmnt.py`.

- Make Users and invite acceptance explicitly reachable; remove the invite
  bridge dependency on nonexistent `renderUsersView`.
- Match list/search/filter, create, edit, activate/deactivate, roles,
  permissions, and delete behavior actually exposed by cPlatform.
- Match invite create, Mailpit delivery, preview, accept, password validation,
  resend, revoke, expiry, already-used/revoked, and invalid-token states.
- Ensure login/session and authorization update immediately after activation or
  admin changes; enforce every admin action in the API.
- Redact passwords/tokens from events, logs, jobs, responses, and artifacts.

Acceptance: admin invites user → one matching Mailpit message → preview → set
password → token single-use → login → role/status edit changes authorization →
revoke/resend second invite invalidates old token → cleanup. Test non-admin and
every token terminal state.

## 4.4 Monitoring

Legacy authority: `/PlatformIO/Monitoring/` and Issues/EventDetails/
Performance/Health/IntegrationStatus/Uptime/IssueAction/Keys,
`views.py:2277-2840`, and `ServiceMonitoring.js`.

- Preserve cluster → node → service tree and scoped cached workspace.
- Native sweep inspects the configured target and persists evidence;
  compatibility health cannot silently rely on stale database status.
- Match GlitchTip integration state, issue list/filter/pagination, event
  details, keys, actions, transaction groups, and health.
- Match uptime list/add/delete, validation, duplicates, ownership, and external
  failures.
- Distinguish optional integration unavailable from successful empty data and
  prevent cross-service leakage during polling/refresh.

Acceptance: without GlitchTip, truthful unavailable states plus real container
health sweep. With disposable GlitchTip, create key/uptime, ingest controlled
error/transaction, list/filter/open/action, delete uptime, and clean up.

## 4.5 Performance

Legacy authority: `/PlatformIO/SystemMonitoring/`, `/GetMonitoringTree/`,
`/GetNodePerformance/`, `/GetServicePerformance/`, `views.py:2082-2265`, and
`SystemMonitoring.js`.

- Match selection, windows, refresh, units, labels, aggregation, and states.
- Validate PromQL for cPlatform-used CPU, memory, disk, network, process/
  container health, availability, throughput, latency, errors, and queues.
- Hide/remove/label `log_error_rate`, `queue_depth`, and `latency_ms_p95` until
  real telemetry backs them; zero is not proof of measurement.
- Normalize timestamps/sample ordering and distinguish no collector, no series,
  query error, and true zero.
- Prove target labels isolate nodes/services and add deterministic Prometheus
  response fixtures.

Acceptance: deploy exporters and controlled traffic → prove non-empty node and
service series across windows → compare units/aggregation with direct queries →
stop collector and verify unavailable → run two services to prove isolation and
counter-reset behavior.

## 4.6 Diagnostics

Legacy authority: `/PlatformIO/Diagnostics/`, ClusterConfig diagnostics/log/
backfill/event branches, `views.py:1502-1551,3713-3901`, and
`ServiceDiagnostics.py`.

- Match target/capability summary, source selection, bounded live tail, polling,
  limits, and download. Do not call bounded HTTP tails streaming.
- Complete file/container history with stable cursor, direction, page, time
  range, truncation, and rotation behavior.
- Complete archive index/list/view/download/bulk/retention/missing-file and safe
  path handling.
- Backfill to Loki with terminal job, idempotency, progress, partial failure,
  and known-marker query verification.
- Match ingestion statistics and distinguish empty Loki from unavailable Loki.
- Analysis/chat must return traceable evidence/action results only when the
  analyst is configured; never synthesize success or diagnoses.
- Redact secrets from logs, filenames, analysis, events, and errors.

Acceptance: generate known multiline logs → bounded tail → bidirectional
pagination without gaps/duplicates → archive/view/download → backfill → Loki
query known markers → configured analysis or honest unavailable → expire/delete
and clean up. Cover rotation, missing/invalid path, Unicode, oversized lines,
and disappearing containers.

## 4.7 Observability

cPlatform has no standalone Observability Stack page. Authority is distributed
across Monitoring, SystemMonitoring, Diagnostics, service observability config,
and ClusterConfig. This page is an integrated view of those behaviors only.

- Reframe readiness around selected target, required service records,
  Prometheus/Loki reachability, recent samples/logs, and navigation into
  Monitoring/Performance/Diagnostics.
- Retain bootstrap/deploy/teardown only if it implements a cPlatform service
  deployment/config action; reuse Cluster deployment jobs instead of a separate
  product lifecycle.
- Replace database-only readiness with container state, collector target
  health, Prometheus query, Loki readiness/query, and freshness probes.
- Do not require a fixed `platformops-obs` project when cPlatform behavior is
  node/service scoped.
- Exclude any feature without a cPlatform action from the parity gate; it may
  remain separately labeled non-parity.
- Degraded reasons must identify the missing signal and link to the responsible
  included page.

Acceptance: deploy telemetry through Cluster service workflow → prove actual
containers/targets → generate metrics/logs → confirm readiness/freshness → open
matching Performance/Diagnostics evidence → stop one collector and see precise
degradation → recover. No standalone non-cPlatform feature is needed to pass.

## 5. Delivery sequence

### Phase 0 — Scope and baseline

Freeze the seven-page action manifest; label all non-scope navigation/features;
capture API schemas, current checks, and known limitations; add a smoke that
logs in and opens all seven pages.

Materialize the golden Redis fixture manifest and verify that the catalog/runtime
contract supports a writable config file, deterministic log path, stable
container identity, Redis exporter labels, and complete cleanup.

Exit: every included action has source pointer, target contract, evidence state,
and acceptance; no Batch/Stream/Model/Advanced task exists.

### Phase 1 — Cluster foundation and Users reachability

Complete selection/lifecycle/data preservation and real Cluster → Node →
Service deploy/status/log flow; repair invite routing and prove full invite
lifecycle.

### Phase 2 — Config runtime correctness

Enforce capabilities; prove apply/drift/compare/restore and supported migration
paths against a real runtime file with terminal jobs.

### Phase 3 — Diagnostics evidence pipeline

Complete tails, cursors, archives, backfill, Loki proof, redaction, and honest
analyst states.

### Phase 4 — Monitoring and Performance

Complete real health, optional disposable GlitchTip, exporters, PromQL,
non-placeholder values, target isolation, and failure recovery.

### Phase 5 — Observability integration and full regression

Limit Observability to cPlatform-derived readiness; run all page scenarios from
a fresh fixture and verify total cleanup.

## 6. Regression gates

1. Contract tests: validation, auth, payloads, redaction, events, compatibility.
2. Persistence tests: deep merge, transactions, FKs, snapshots, jobs, tokens,
   cursors, and target isolation.
3. Adapter tests: Docker, SSH, Ansible, Prometheus, Loki, GlitchTip, SMTP, and
   analyst timeouts/malformed responses.
4. Frontend tests: every action reachable; loading/empty/error/retry;
   synchronized selection; confirmations; stale request cancellation.
5. Isolated E2E: real DinD/PostgreSQL/Mailpit and optional telemetry profiles.

The milestone E2E is the ordered golden Redis scenario in
`docs/redis-seven-page-acceptance-fixture.md`; separate page fixtures cannot
substitute for it.

Per package: targeted tests → API compilation/backend suite → frontend build if
changed → `make isolated-verify` → `git diff --check` → affected page E2E.
Before a milestone: full seven-page suite from a fresh image/fixture. Record
commit, image, commands, terminal jobs, side effects, and cleanup in
`docs/mvp-status.md`. If host tools are missing, test in the production image
and state limits honestly.

Never weaken assertions, skip terminal polling, reuse stale state as a fresh
pass, or mark an existing endpoint runtime-proven without its side effect.

## 7. Definition of complete

- All seven pages are authenticated-shell reachable.
- Every included cPlatform action has a reachable, tested PlatformOps path.
- One canonical Cluster/Node/Service target drives every scoped page.
- Mutations prove persistence, events, jobs, runtime side effects, and cleanup.
- External-unavailable cases are truthful and actionable.
- Full backend/frontend/isolated regressions pass on a fresh fixture.
- No required action remains merely Implemented or Unverified.
- No Batch/Stream/Model/Application/Advanced work was added.
- No PlatformOps-only feature was counted toward cPlatform parity.
