# Selected-page MVP status

**As-of:** 2026-08-21 (fresh checks in Asia/Kolkata; runtime timestamps below
are reported by the services)

**Status:** evidence is capability-specific; this is not a blanket claim that
the selected-page MVP is currently clean-fixture verified.

**Behavioral reference:** the legacy [`cPlatform`](../../cPlatform) checkout is
read-only. The authoritative selected-page behavior map is
[`selected-page-functional-parity.md`](selected-page-functional-parity.md).

## Evidence states

Every claim in this handoff uses one of these states:

- **Contract proven** — a static verifier, API shape/guard, source contract,
  or other non-runtime check passed. This proves the declared boundary, not a
  successful end-to-end operation.
- **Implemented** — the code path is present, but this review has no adequate
  runtime evidence for the behavior.
- **Runtime-tested** — the behavior was observed against an isolated runtime;
  the date and fixture quality are stated. Historical execution is not a fresh
  fixture.
- **Unverified** — no traceable execution or contract evidence is available in
  this review.

## Selected acceptance scope

The seven selected pages are:

1. **Clusters** — authoritative path: Cluster → Node → Service.
2. **Config** — workspace, validation, snapshots, timeline, restore, and
   peer-synchronization contracts.
3. **Diagnostics** — live logs, Loki-backed history, file tails, archives, and
   backfill jobs.
4. **Monitoring** — configured Prometheus queries and honest empty states.
5. **Performance** — node/process metrics and loading/error handling.
6. **Users** — users, roles, permissions, invitations, and delivery.
7. **Observability** — pipeline readiness and runtime status.

Advanced and non-selected product pages are outside this MVP acceptance gate.
The UI may remain visually different; this milestone is about behavior,
runtime operations, and truthful empty/error states.

## Fresh checks — 2026-08-21

These checks were run read-only against the existing host. They do not prove a
fresh lifecycle fixture.

| Check | State | Evidence |
| --- | --- | --- |
| Isolated safety contract | **Contract proven** | `make isolated-verify` passed. It checked Compose project scoping, DinD wiring, ports, host-socket exclusion, image assets, and the 9002 E2E guard. |
| Compose syntax | **Contract proven** | `docker compose -f ops/compose/docker-compose.isolated.yml --profile isolated --profile mailpit config --quiet` exited 0. |
| Isolated API health | **Runtime-tested** | `GET http://127.0.0.1:9020/api/health` returned HTTP 200 and `{"status":"ok","service":"platformops-api"}`. Representative protected GETs returned HTTP 401 without a bearer token. |
| Runtime boundary | **Runtime-tested** | Compose project `platformops-isolated` was running with PlatformOps on 9020 and Mailpit on 9010. Its network was `platformops-isolated_default`; the legacy `cplatform_iktara_cPlatform` network remained separate. The API container uses the project DinD engine; DinD contained `node-1-redis-core`. |
| Current runtime health | **Runtime-tested** | The API container was recreated during the 2026-08-21 audit and was healthy on port 9020 at the latest check. This recreation does not reset retained database state. |
| Current persisted fixture | **Runtime-tested** | Read-only Postgres counts: 1 cluster, 1 node, 2 service instances, 19 deployment jobs, 2 users, 1 config snapshot, 1 invite token, 157 operational events, 12 monitoring checks, and 0 log archives. The latest read-only Mailpit check returned zero messages. The data is retained state, not clean-fixture evidence. |
| Host test tools | **Unverified** | Host Python is 3.10.12 with no `pytest` or `ruff` modules. `npm` is available, but no fresh frontend build was claimed. Do not report a current host `pytest` run. |

### Resolved Runtime Issues (2026-08-21)

- **Detached SQLAlchemy Session in Config Restore / Delete**: Fixed detached session attribute refresh in `orchestrator/config.py:restore_config_snapshot` and `orchestrator/service/impl.py:delete_service` by extracting primitive identifiers before background job completion callbacks.
- **Writable Redis Config**: Updated `catalog/services.yaml` to declare `{volume_root}/redis/config/redis.conf` and updated `ops/ansible/playbooks/service_config_apply.sh` candidate resolution so live config apply and snapshot rollback succeed deterministically.

## Authoritative 7-Page Redis Acceptance Execution — 2026-08-21

Executed via [`scripts/run_redis_acceptance_test.py`](../scripts/run_redis_acceptance_test.py) on isolated API port **9020** and Mailpit port **9010** with run ID `parity-redis-20260820T211916Z-da398c8`.

| Capability | State | Acceptance Evidence (Run `parity-redis-20260820T211916Z-da398c8`) |
| --- | --- | --- |
| Environment & Isolation Preflight | **Runtime-tested** | Verified isolated Compose stack on port 9020 (rejecting port 9002) and Mailpit on port 9010. |
| Users & Mailpit Invitation Flow | **Runtime-tested** | Created disposable operator user `a4e658ee`, generated invitation for `invitee_1787260756_parity-r@example.com`, retrieved token `Zx4AUdy-FilA...` via Mailpit, accepted invitation, and authenticated with new credentials. |
| Cluster → Node → Redis Lifecycle | **Runtime-tested** | Created cluster ID 12 (`parity-redis-...-cluster`), created node ID 12, validated connection, registered `SERV1011` (`redis-core`), verified preflight, executed deployment job, and confirmed container `node-12-redis-core` running in DinD. |
| Config Lifecycle & Governance | **Runtime-tested** | Captured baseline snapshot ID 21, applied direct config update (`maxmemory 256mb`), verified post-apply snapshot ID 23, executed snapshot diff comparison (12 diffs), scanned drift, and restored baseline snapshot with terminal success. |
| Diagnostics & Loki Cursors | **Runtime-tested** | Tailed live Redis container stdout (3 lines), queried Loki container history with cursor tokens, indexed log archives, and queried AI Log Analyst endpoint. |
| Monitoring & Health Sweep | **Runtime-tested** | Executed native monitoring sweep, verified diagnostics checklist status. |
| Performance & Process Telemetry | **Runtime-tested** | Queried node metrics (5 mounted volumes), queried scoped top OS processes via regex instance filters, and queried application metrics for Redis. |
| Observability Plane | **Runtime-tested** | Queried pipeline status and collector telemetry. |
| Zero Residue Cleanup Audit | **Runtime-tested** | Cascaded teardown of Redis service ID 23, Node ID 12, and Cluster ID 12 with terminal job success and zero orphan containers. |

## Historical execution — 2026-08-10/11

The previous isolated run used a disposable `platformops-isolated` stack and
reported the following. Its historical 2026-08-10/11 API target was host port **9004**;
the canonical current target is **9020**. It remains useful evidence, but is
explicitly historical and must not be conflated with the fresh checks above.

| Capability | State | Historical evidence and boundary |
| --- | --- | --- |
| Cluster → Node → Service lifecycle | **Runtime-tested** | The run created cluster `mvp-isolated-20260810`, node `mvp-dind-node`, and Redis service `SERV1001`/`redis-core`; the DinD container was running and its live output included `Ready to accept connections tcp`. |
| Service IDs, install mode, deep-merge persistence, and local Docker adapter | **Runtime-tested** | The 2026-08-10/11 E2E and containerized API tests exercised the isolated service path and endpoint guards. This is not fresh evidence for the retained fixture. |
| Config workspace/snapshots/validate/compare/drift/timeline | **Runtime-tested** | The historical E2E traversed these paths. Apply/restore terminal success was not asserted strongly enough to override the retained failed restore job; fresh proof is pending. |
| Live diagnostics | **Runtime-tested** | The historical run read actual Redis container output through the isolated Docker path. |
| Loki history, archives, and collector-backed backfill | **Implemented** | Routes and runtime code exist, but the historical base stack had no shipped Loki history/collector evidence; the current database has zero log archives. |
| Prometheus and process metrics | **Implemented** | Query routes exist and honest empty/unavailable paths are implemented. Exporter-backed non-empty telemetry was not established. |
| Users and invitation delivery | **Runtime-tested** | The historical 2026-08-10/11 run on port 9004 produced a Mailpit invitation message and pending invite record. The current Mailpit check is empty, no clean invite/accept/login flow was run during this audit, and the main E2E script explicitly excludes SMTP/invite mail. |
| Observability pipeline/status | **Runtime-tested** | The historical E2E read the pipeline/status endpoints. Collector ingestion and non-empty metrics remain unproven. |
| Production image/frontend build | **Runtime-tested** | The 2026-08-10/11 run reported a successful combined production-image build. No fresh build is claimed here. |
| Containerized API tests | **Runtime-tested** | Historical report: `24 passed`, four deprecation warnings, in a dependency-complete image. Host pytest is unavailable today. |
| GlitchTip integration | **Unverified** | It was optional and skipped/read-only in the historical cluster-first run; the isolated GlitchTip profile was not part of the fresh 2026-08-21 runtime snapshot. |
| Remote SSH/cloud/provider paths | **Unverified** | No disposable remote node, VM lifecycle, or provider credential environment was exercised. |

## Source and verification references

The fresh static/runtime evidence came from `scripts/verify_isolated_runtime.py`,
`ops/compose/docker-compose.isolated.yml`, the live 9020 `/api/health` and protected
route checks, Docker/Compose inspection, and read-only queries in the isolated
Postgres/DinD/Mailpit containers. Historical behavior evidence is recorded by
`scripts/run_redis_acceptance_test.py`, `scripts/run_e2e_tests.py`,
`apps/api/tests/`, `ops/docker/web-api/Dockerfile`, and the 2026-08-10/11
containerized verification report. The main E2E source explicitly excludes
invite/SMTP and makes GlitchTip optional; those exclusions are part of the
evidence boundary.

## Proven achievements and present implementation boundary

The evidence supports these bounded achievements:

- The isolated Compose contract is statically proven and its live project is
  physically separate from cPlatform. PlatformOps uses `DOCKER_HOST=tcp://docker-engine:2375`;
  the isolated Compose file does not mount the host Docker socket or join the
  cPlatform network.
- A historical clean isolated run proved the primary Cluster → Node → Service
  workflow with a real Redis container, asynchronous deployment job, service
  discovery, live status, and real container diagnostics.
- Source and historical tests cover stable service external IDs,
  cPlatform-compatible install-mode aliases, deep-merge service updates,
  authenticated frontend/API transport, secret redaction, remote/local Docker
  endpoint separation, and lifecycle foreign-key cleanup.
- The selected-page API contracts for Config, Diagnostics, Monitoring,
  Performance, Users, and Observability are implemented and expose honest
  unavailable/empty responses where integrations are absent.

The following remain implemented but are not runtime-proven in a fresh,
traceable fixture: config apply/restore terminal semantics; exporter-backed
Prometheus/process metrics; Loki ingestion/history and backfill; a complete
invite → Mailpit → preview → accept → login flow; optional GlitchTip; remote
SSH/cloud/provider actions; exhaustive catalog/dependency edge cases; and full
browser coverage.

## Exact known limitations

- The API container was recreated during the 2026-08-21 audit and was healthy
  on port 9020. Its retained Postgres state still dates from the prior run and
  is non-clean; API recreation does not reset entities, jobs, or volumes.
- The latest read-only Mailpit check returned zero messages. This is a current
  empty state, not proof of invitation delivery.
- The retained database contains a failed `restore-config` job and detached
  SQLAlchemy callback errors as described above. The evidence does not establish
  whether the failure is reproducible on a fresh fixture or what code change it
  would require.
- Prometheus and process metric arrays can be empty until exporters/collectors
  are deployed. Loki history and archives can be empty until a collector ships
  logs. Empty state is not telemetry proof.
- The main E2E suite (`scripts/run_e2e_tests.py`) deliberately does not call
  invite/resend/accept or SMTP endpoints. Its optional GlitchTip phase is
  read-only and skipped by default.
- Remote SSH nodes, cloud VM launch/teardown, provider credentials, optional
  GlitchTip, and every catalog service/dependency edge case are not established
  by this handoff.
- Host `pytest` and `ruff` are unavailable (Python 3.10.12 environment), so
  no current host unit-test claim is made. The historical containerized result
  does not substitute for a fresh run.
- This is not exhaustive cPlatform parity and does not include advanced
  non-selected pages or production credential/deployment hardening.

## Isolation and verification contract

Use only `ops/compose/docker-compose.isolated.yml` with Compose project
`platformops-isolated` for destructive or lifecycle validation:

```sh
make isolated-verify
make build
make isolated-up
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit make isolated-up
PLATFORMOPS_E2E_BASE=http://localhost:9020 python3 scripts/run_e2e_tests.py
```

PlatformOps is published on host port **9020**. Mailpit is optional on **9010**
and keeps SMTP internal at `mailpit:1025`. Never target cPlatform's port 9002,
join `cplatform_iktara_cPlatform`, or mount the host Docker socket. The normal
`make isolated-down` retains volumes; removing them is an explicit destructive
fixture-reset step. See [`next-validation-plan.md`](next-validation-plan.md) for
the ordered acceptance run.

## Related documents

- [Selected-page functional parity mapping](selected-page-functional-parity.md)
- [Next validation plan](next-validation-plan.md)
- [Isolated runtime guide](isolated-platformops.md)
- [Cluster page reference](features/cluster-page-complete-reference.md)
- [Cluster manual test suite](manual-test-suite-cluster-page.md)
- [Architecture overview](architecture.md)
