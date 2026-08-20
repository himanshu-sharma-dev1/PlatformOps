# Isolated PlatformOps runtime

This is the recommended runtime for the selected-page MVP. For the complete
scope, verified workflow, and honest limitations, see the
[MVP status](mvp-status.md). The ordered fresh-fixture run is in the
[next validation plan](next-validation-plan.md).

The isolated verification stack is defined by
`ops/compose/docker-compose.isolated.yml`. It is deliberately separate from
the legacy `docker-compose.local.yml` stack that uses host port 9002 and the
live cPlatform network.

The isolated project has these boundaries:

- The combined production image builds `apps/web` with Node and serves its
  output from `/app/dist` in the FastAPI container.
- PlatformOps is published only on `http://localhost:9020` (use the host
  address instead of `localhost` when accessing a remote machine).
- Postgres, Redis, RabbitMQ, Prometheus, Loki, and the Docker engine have no
  host port mappings. Compose creates their network and named volumes within
  the `platformops-isolated` project.
- Docker operations use the real `docker-engine` DinD service over
  `tcp://docker-engine:2375`; no host `docker.sock` is mounted.
- Mailpit is opt-in (`PLATFORMOPS_ENABLE_MAILPIT=1`) and publishes only its web
  UI on port 9010. SMTP stays internal at `mailpit:1025`.
- The GlitchTip-compatible endpoint is opt-in
  (`PLATFORMOPS_ENABLE_GLITCHTIP=1`) and has no host port mapping.

The existing cPlatform stack is not stopped or modified. It remains on its own
network and port allocation; do not attach isolated containers to
`cplatform_iktara_cPlatform` and do not use the legacy host Docker socket.

## Static verification

Run the read-only verifier before any runtime operation:

```sh
make isolated-verify
```

It parses the Compose/config YAML and checks project scoping, host-port
boundaries, DinD wiring, the production image stages, and the E2E live-stack
guard. It does not contact Docker, start services, create networks, or delete
data.

## Build and run

Prerequisites are Docker Engine with Compose v2, permission to run a
privileged DinD container, free host port 9020 (and 9010 when Mailpit is
enabled), and network access for image pulls/build dependencies.

```sh
make build
make isolated-up
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit make isolated-up
make isolated-down
```

When Mailpit is enabled, open `http://localhost:9010` to inspect invitation
messages. The SMTP server is internal to Compose at `mailpit:1025`; only the
Mailpit web UI is published.

The API bootstrap defaults in this development stack are `admin` / `admin`.
Set the `PLATFORMOPS_BOOTSTRAP_ADMIN_*` variables before using it outside a
local verification environment. The bootstrap administrator is created only
when no administrator exists and is not reset on every restart.

`isolated-down` retains project volumes. Do not add `--volumes` casually: data
removal is intentionally outside the standard non-destructive targets.

The lifecycle E2E suite defaults to the isolated endpoint:

```sh
PLATFORMOPS_E2E_BASE=http://localhost:9020 python3 scripts/run_e2e_tests.py
```

It rejects port 9002 unconditionally. The canonical isolated target for this
runtime is `http://localhost:9020`; do not point the lifecycle suite at the
legacy 9002 stack.

## MVP smoke path

After the stack is healthy, use the Clusters page to create/open a cluster,
add a local node, create the catalog `redis-core` service, run dependency
preflight, deploy it, and open its live status/logs. The verified reference
data is documented in [mvp-status.md](mvp-status.md). The service is deployed
inside the isolated DinD engine and its live stream contains real Redis output.

Prometheus/process metrics and Loki history are intentionally empty until
exporters or collectors are deployed. Direct local container logs and the
selected-page APIs still work; the UI should report unavailable/empty
telemetry rather than inventing values.
