# Phase 2 Observability Stack

The supported product topology is:
- cPlatform machine:
  - `cPlatform/docker-compose.yaml`
  - central `loki`
  - central `alloy`
  - central `glitchtip`
- added nodes:
  - `alloy` only
  - push logs to the central Loki on the cPlatform machine

`entrypoint_script.sh` remains app bootstrap only. Multi-container topology is owned by compose and ansible.

## Components
- `loki`: retained log backend for `Current`, `24h`, and `7d` diagnostics
- `alloy`: docker and file log collector
- `glitchtip-web`: GlitchTip web UI and API
- `glitchtip-worker`: async worker and scheduled jobs for GlitchTip
- `glitchtip-postgres`: dedicated GlitchTip database
- `glitchtip-valkey`: queue/cache backend for GlitchTip

## NOC Metrics

The NOC Prometheus contract is kept with the infrastructure service catalog:

- NiFi is scraped at `/nifi-api/flow/metrics/prometheus`.
- `noc-kafka` scrapes `180.75.0.63:9308`, served by the optional pinned
  `danielqsj/kafka-exporter:v1.8.0` contract.
- The exporter connects to the broker at `180.75.0.31:9092` on the existing
  `cplatform_iktara_cPlatform` network.

See `platform/docker/kafka/README.md` for the disposable Compose example and
the service-install deployment notes.  The existing process-exporter
Prometheus job is intentionally unchanged.

## GlitchTip Branding Image
GlitchTip branding is packaged as a custom image, not runtime-mounted from cPlatform assets.

Default image tag:
- `iktaraai/services:glitchtip-iktara-6.1.9`

Build command from repo root:
- `platform/observability/build_glitchtip_iktara.sh`

Optional override:
- set `CPLATFORM_GLITCHTIP_IMAGE` before `docker compose up`

## Control-Plane Bootstrap
Use this flow for a fresh cPlatform machine:
1. clone the repo
2. place `MCPClient/` and `CutilJS/` as siblings at repo root
3. set host-specific diagnostics values directly in `platform/docker/cPlatform/diagnostics.validation.env` when needed
4. create the control-plane env files or let bootstrap copy them from examples:
   - `platform/docker/cPlatform/deployment.validation.env`
   - `platform/docker/cPlatform/diagnostics.validation.env`
5. run the host bootstrap command:
   - `sudo python3 scripts/bootstrap_cplatform_host.py`
6. build the cPlatform image using the existing image-build flow
7. start the stack and wait for health:
   - `sudo python3 scripts/bootstrap_cplatform_host.py --start-stack --wait-healthy`

The bootstrap command checks:
- required sibling repos exist
- env files exist and are shell-safe `KEY=value`
- host directories exist under `/home/ubuntu/Backup_Platform/iktara/...`
- Loki storage permissions are correct for UID/GID `10001`
- the fixed cPlatform Docker network is compatible
- required host ports are available
- compose renders successfully
- copied diagnostics envs get a remote-friendly Loki ingest URL for added nodes
- when `--wait-healthy` is used, startup is treated as staged and potentially slow rather than immediate failure

The bootstrap command should be run with permissions to prepare host directories and set Loki storage ownership to UID/GID `10001`.
Use `--health-timeout` if your image pulls, migrations, or first startup are known to take longer than the default `900s`.

## Env Files
The control-plane stack uses two explicit env files.

Django/app env:
- `platform/docker/cPlatform/deployment.validation.env`
- shell-safe `KEY=value` only
- uses compose service names for control-plane-local dependencies like:
  - `postgres_host=cplatform_db`
  - `celery_broker=amqp://admin:admin@rabbitmq:5672//`

Diagnostics env:
- `platform/docker/cPlatform/diagnostics.validation.env`
- points to in-compose central services like:
  - `CPLATFORM_DIAGNOSTICS_LOKI_URL=http://loki:3100`
  - `CPLATFORM_GLITCHTIP_BASE_URL=http://glitchtip-web:8000`
- uses a separate remote ingest URL for node Alloy:
  - `CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL`
  - keep the control-plane query URL internal as `http://loki:3100`
  - if diagnostics env sets `CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL`, bootstrap preserves that explicit value
  - bootstrap rewrites ingest URL from the example default to `http://<control-plane-host>:9011`
  - default external Loki host port is `9011`

`cPlatform/docker-compose.yaml` mounts both env files explicitly and sets:
- `DJANGO_ENV_FILE`
- `DIAGNOSTICS_ENV_FILE`

Do not rely on autodiscovery for the standard bootstrap path.

## Fixed Network Contract
The platform default remains the fixed Iktara bridge contract.

Defaults:
- network name: `cplatform_iktara_cPlatform`
- subnet: `180.75.0.0/24`
- gateway: `180.75.0.1`

These values are fixed for product mode and validated by bootstrap.

Bootstrap validates that:
- if the network does not exist, bootstrap creates it
- if it already exists, the subnet/gateway are compatible
- if it exists with the wrong subnet/gateway, bootstrap fails clearly before deployment

## First-Boot Alloy Policy
Central Alloy should be safe on a used host.

Current bootstrap policy:
- file sources default to `tail_from_end = true`
- docker sources drop entries older than `24h`
- docker sources drop oversized entries above `256KB`

This avoids first-boot floods of:
- `timestamp too old`
- `entry too far behind`
- `max entry size exceeded`

Historical replay is not automatic.
Use controlled backfill separately when needed.

## Remote Node Connectivity
Added-node Alloy should reach the control-plane Loki ingest endpoint directly.

Recommended host ports:
- cPlatform HTTP: `80`
- central Loki: `9011`
- central GlitchTip: `8001` or an allowed `900x` override if needed
- node Alloy: `12345` by default, override per node if occupied

Do not use SSH tunnels as the default product path.
The standard deployment model is direct node-to-control-plane connectivity to the published Loki host port.

If the environment only permits the cPlatform app port, expose Loki through the cPlatform Nginx front door:
- `http://<control-plane-host>:80/loki/ready`
- node Alloy ingest URL:
  - `http://<control-plane-host>:80/loki`

## Node Observability Rollout
Added nodes run Alloy only.

Use:
- `platform/ansible/playbook/observability_stack_playbook.yaml`

This playbook:
- creates required observability directories
- sets Loki storage ownership deterministically
- renders compose and GlitchTip config
- generates Alloy config from `cPlatform/config/service_install.yaml` observability contracts
- starts Loki, Alloy, and GlitchTip services
- waits for health checks

For remote nodes, `serviceInstall.sInstall_deploy_node_observability(...)` deploys node Alloy only.
The control-plane node skips that path and uses the central cPlatform compose stack instead.

## Host Storage
The automated bootstrap/playbook provisions these by default:
- `/home/ubuntu/Backup_Platform/iktara/cPlatform/logs`
- `/home/ubuntu/Backup_Platform/iktara/Repository`
- `/home/ubuntu/Backup_Platform/iktara/observability/loki`
- `/home/ubuntu/Backup_Platform/iktara/observability/alloy`
- `/home/ubuntu/Backup_Platform/iktara/observability/glitchtip/postgres`
- `/home/ubuntu/Backup_Platform/iktara/observability/glitchtip/valkey`

## Current Log Inputs
Central Alloy and node Alloy read:
- docker container logs through the Docker socket
- file logs from `Observability.file_logs` service contracts

Host path defaults remain:
- main service logs:
  - `/<service_volume>/iktara/<service>/logs`
- support-service logs:
  - `/<machine_volume>/iktara/<dependency>NameLogs`

Do not hand-edit Alloy paths for normal service rollout. Service deployment creates host paths, mounts them, and reconciles node Alloy.

## Operator Tooling
Under `scripts/`:
- `bootstrap_cplatform_host.py`
  - prepares a control-plane machine for compose bootstrap and can optionally run `compose up -d` plus staged health checks
- `observability_preflight.py`
  - validates diagnostics env wiring and observability contracts
- `observability_backfill.py`
  - backfills only the missing startup prefix of a file-log source into Loki

## Notes
- Keep this stack isolated from the main service databases and queues.
- Do not store observability data under `/home/ubuntu/Backup_Platform/iktara/Repository`.
- If GlitchTip is not configured yet, cPlatform diagnostics still works using live status, service events, node-side docker logs, and local file logs.
