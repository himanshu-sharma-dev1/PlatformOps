# PlatformOps selected-page MVP handoff

**Status:** verified isolated MVP

**Reference implementation:** the legacy `cPlatform` checkout (read-only)

**Last runtime verification:** 2026-08-10

This document describes the current, working delivery scope. It is the
operational handoff for the FastAPI/React port; the older feature inventories
and parity plans in `docs/features/` and `docs/plan-*.md` remain useful design
references, but they are not a claim that every advanced surface is part of
this MVP acceptance gate.

## Goal and scope

PlatformOps is the stripped-down FastAPI/React control plane being ported from
`cPlatform`. The current goal is functional parity for the selected operator
pages, with the existing PlatformOps UI retained for now. Correct behavior,
real runtime operations, and truthful empty/error states matter more than
pixel-perfect styling in this milestone.

The selected pages are:

- **Clusters** — the primary acceptance path and the most feature-rich page.
- **Config** — workspace, validation, snapshots, timeline, restore, and peer
  synchronization contracts.
- **Diagnostics** — live logs, Loki-backed history, file tails, archives, and
  backfill jobs.
- **Monitoring** — configured Prometheus queries and honest empty states.
- **Performance** — node/process metrics and loading/error handling.
- **Users** — users, roles, permissions, invitations, and invitation delivery.
- **Observability** — pipeline readiness and real runtime status.

Advanced or product-specific pages outside this acceptance gate are deferred.
The UI can be refined after the behavior is complete.

## Runtime and isolation contract

Use `ops/compose/docker-compose.isolated.yml` for the verification/runtime
stack. It is a separate Compose project named `platformops-isolated`:

```text
PlatformOps UI/API   http://<host>:9004
Mailpit UI           http://<host>:9010  (optional)
```

The legacy cPlatform deployment is not stopped, reconfigured, joined, or
used as a dependency. In particular, the isolated stack does not join the
`cplatform_iktara_cPlatform` network and does not mount the host Docker socket.

The isolated services are:

- PlatformOps combined frontend/API image
- PostgreSQL
- Redis
- RabbitMQ
- Prometheus
- Loki
- a project-owned privileged Docker-in-Docker daemon (`docker-engine`)
- optional Mailpit for invitation email tests
- optional GlitchTip-compatible services

The API talks to the private Docker daemon through
`DOCKER_HOST=tcp://docker-engine:2375`. Containers deployed from the Cluster
page therefore live inside the isolated engine and cannot collide with the
legacy cPlatform containers. Dependency services have no host port mappings;
Compose-scoped networks and named volumes retain their data under the
`platformops-isolated` project.

## Build, start, and stop

Prerequisites are Docker Engine with Compose v2, permission to run a
privileged DinD container, free host ports 9004 (and 9010 when Mailpit is
enabled), and network access for image/dependency pulls.

From the repository root:

```sh
# Read-only contract check; does not contact Docker or mutate data.
make isolated-verify

# Build the combined Node frontend + Python/FastAPI image.
make build

# Start the base isolated stack.
make isolated-up

# Start Mailpit as well and route SMTP invites to it.
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit make isolated-up
```

Open `http://127.0.0.1:9004` (or the host address on a remote machine). The
MVP bootstrap defaults are:

```text
username: admin
password: admin
```

These are development defaults. Set
`PLATFORMOPS_BOOTSTRAP_ADMIN_EMAIL`,
`PLATFORMOPS_BOOTSTRAP_ADMIN_PASSWORD`, and
`PLATFORMOPS_BOOTSTRAP_ADMIN_NAME` before using the stack outside a local
verification environment. Startup creates the bootstrap administrator only
when no administrator exists; it does not reset an existing administrator on
every restart.

To stop the isolated services while retaining their project volumes:

```sh
make isolated-down
```

The normal stop target intentionally does not remove data. Volume removal is
an explicit, separately reviewed Docker Compose operation.

## Verified Cluster → Node → Service workflow

The acceptance workflow was executed against the isolated runtime and left in
place for UI inspection:

| Resource | Verified value | Result |
| --- | --- | --- |
| Cluster | `mvp-isolated-20260810` | created and persisted |
| Node | `mvp-dind-node` | local node mapped to the isolated Docker engine |
| Network | `platformops_mvp_network` | private service network |
| Service | `MVP Redis` / `redis-core` | created with stable external ID `SERV1001` |
| Image | `redis:7-alpine` | deployed by the Ansible service path |
| Snapshot | `MVP deployed baseline` | created and listed in Config |

The tested operator sequence is:

1. Create or open the isolated cluster.
2. Add the local node and inspect its facts and connection state.
3. Create a catalog-backed Redis service on that node.
4. Run dependency preflight.
5. Deploy the service and follow the persisted asynchronous job.
6. Refresh live status and discover containers through the isolated Docker
   SDK connection.
7. Open live diagnostics and read actual Redis container output.
8. Open Config, validate YAML, create a snapshot, and inspect its timeline.

The deployed Redis container reported `running: true`, and its live stream
included the real Redis readiness line `Ready to accept connections tcp`.
Node discovery, connection probing, service status, job history, and service
logs all came from the isolated runtime rather than simulated database events.

## What is working in the selected-page MVP

- Authenticated UI/API calls, including raw requests and downloads.
- Cluster and node data persistence, including the fields displayed by the
  editor and masked secret handling.
- Stable service external IDs and cPlatform-compatible install-mode handling.
- Deep service configuration updates that preserve unedited nested values.
- Local Docker SDK operations for inspect, list/discovery, logs, exec, restart,
  and connection/version probing.
- Local Ansible deployment without requiring `sudo` inside the API container;
  remote SSH paths retain privilege escalation where applicable.
- Persisted asynchronous jobs and job output for deployment actions.
- Config workspace, validation, snapshots, paging, restore, and peer-sync
  request contracts.
- Real local service logs, target-aware diagnostics, Loki cursors, archive
  enumeration/download paths, and asynchronous backfill jobs.
- Configured Prometheus and Loki query paths with node scoping and safe query
  literals.
- Users, role/permission persistence, invites, resend/revoke/accept paths,
  and SMTP delivery to Mailpit when enabled.
- Observability pipeline/readiness reporting and Docker-SDK runtime status;
  no fake local-mode success is returned when an operation is unavailable.
- Production frontend build inside the combined API image.

## Honest empty states and remaining parity

This is an MVP milestone, not a claim of exhaustive cPlatform parity across
every catalog card and infrastructure provider.

- Prometheus and process metric arrays are empty until exporters/collectors
  are deployed on the target node.
- Loki history is empty until a log collector ships container/file streams to
  Loki; current local live logs still work directly from the container.
- GlitchTip is optional and was not enabled in the verified base stack.
- Remote SSH-node, cloud VM launch/teardown, and provider-credential paths
  still need real-environment verification.
- Every catalog service type, dependency graph, config apply/restore edge
  case, and advanced selected-page action still needs exhaustive parity
  testing against cPlatform.
- The complete pytest suite was not run on the host because its Python
  environment did not contain pytest and SQLAlchemy together. Run it in a
  dependency-complete environment or test image.
- Advanced non-selected pages and production credential rotation/deployment
  hardening are outside this MVP handoff.

The implementation deliberately reports these conditions as unavailable or
empty rather than manufacturing telemetry, logs, deployments, or external
service success.

## Verification strategy

The repository provides separate non-mutating and runtime checks:

```sh
# Static Compose/Dockerfile/E2E isolation contract.
make isolated-verify

# Python compilation, shipped unit tests, and isolated static checks.
make check

# Frontend TypeScript/Vite production build.
cd apps/web && npm run build

# Lifecycle E2E defaults to port 9004 and refuses the live 9002 target.
cd ../..
python3 scripts/run_e2e_tests.py
```

`make check` does not seed or drop a database. The explicit `make seed` target
is separate and mutating. Before runtime work, confirm that 9004/9010 are
available and use only the `platformops-isolated` Compose project.

## Related documents

- [Isolated runtime guide](isolated-platformops.md) — Compose boundaries and
  lifecycle commands.
- [Cluster page reference](features/cluster-page-complete-reference.md) —
  detailed cPlatform behavior inventory.
- [Cluster manual test suite](manual-test-suite-cluster-page.md) — browser/API
  regression checklist (review its legacy port defaults before running it).
- [Architecture overview](architecture.md) — broader PlatformOps structure.
