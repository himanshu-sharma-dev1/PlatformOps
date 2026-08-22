# Project Core Technologies & Guardrails

## Languages and Runtimes

- **Backend Runtime**: Python 3.11 (`python:3.11-slim-bookworm`), Django 4.2+, Gunicorn 21.2.0 (3 sync workers).
- **System Tools**: Terraform 1.8.5, OpenSSH client, `sshpass`, PostgreSQL client (`libpq-dev`), `procps`.
- **Frontend / Templating**: Server-rendered Jinja2/Django HTML templates (`templates_new/`), Vanilla JavaScript, and inlined `cutil` libraries (`static/cutil/`).

## Core Frameworks and Inlined Libraries

- **Web Framework**: Django 4.2+ (`apps/platformops`), Django Celery Beat, Django Prometheus.
- **Inlined Utilities (`apps/platformops/lib/CommonUtils`)**:
  - `AppLogging`: Structured file and console logging.
  - `EmailMgr`: SMTP mail delivery interface for Mailpit.
  - `TimerMgr`: Interval and recurring task orchestration.
  - `RepoMgmt`: Local repository volume management.
  - `StatsMgr`: Prometheus metrics aggregation.
  - `ServiceConfig` & `serviceInstall`: Dynamic service definitions, DForm generation, and Ansible playbook deployment.
- **Dynamic Forms**: `apps/platformops/forms/` (`dFormService.json`, `dForm_Node_Schema.json`, `dFormServiceConfig.json`).

## Container Infrastructure (`docker-compose.yml`)

All containers use the unified **`platformops/*:1.0.0`** image standard:
- `platformops/web:1.0.0`: Custom standalone application image built from [`Dockerfile`](file:///root/PlatformOps/Dockerfile).
- `platformops/postgres:1.0.0`: PostgreSQL 17 primary database.
- `platformops/redis:1.0.0`: Redis cache and session broker.
- `platformops/rabbitmq:1.0.0`: RabbitMQ message broker.
- `platformops/mailpit:1.0.0`: Mailpit SMTP (1025) and Web UI (8025).
- `platformops/prometheus:1.0.0`: Prometheus telemetry server (9090).
- `platformops/node-exporter:1.0.0`: Node hardware metrics collector (9100).
- `platformops/process-exporter:1.0.0`: Process metrics collector (9256).
- `platformops/loki:1.0.0`: Loki log aggregation (3100).
- `platformops/alloy:1.0.0`: Alloy log collector (12345).
- `platformops/glitchtip:1.0.0`: GlitchTip APM & error tracking (8008).
- `platformops/glitchtip-postgres:1.0.0` & `platformops/glitchtip-valkey:1.0.0`: Backing storage for GlitchTip.

## Critical Guardrails & Operating Methods

1. **Never Overwrite Real User Infrastructure**:
   - `NODE1001` and user clusters in the database contain real host credentials and production mappings. Never run destructive reset scripts against active database volumes.
2. **Standard Volume Mount**:
   - `/home/ubuntu/Backup_Platform` is mounted for all service configs, logs, and deployment artifacts.
3. **Strict Port Allocation**:
   - PlatformOps ingress: Port `9020`.
   - Mailpit: `8025` / `1025`.
   - Prometheus: `9090`.
   - Node Exporter: `9100`.
   - Process Exporter: `9256`.
   - GlitchTip: `8008`.
   - No binding or conflict with cPlatform ports (`80`, `443`, `9002`, `9008`, `9012-9019`).
4. **Safe Configuration Updates**:
   - `PlatformSettings.update_config()` reloads runtime settings safely.
   - Outgoing service config pushes use a 5s timeout to guarantee worker responsiveness.
