# Project Structure

## Directory Layout

- `apps/platformops/` contains the Django application (`cPlatformIO`).
  - `src/` contains core orchestrators (`ClusterConfig.py`, `NodeConfig.py`, `ServiceConfig.py`, `serviceInstall.py`, `ServiceDiagnostics.py`, `UserMgmnt.py`, `systemMonitoring.py`).
  - `forms/` contains dynamic form schemas (`dForm_Node_Schema.json`, `dFormService.json`, `dFormServiceConfig.json`, etc.).
  - `models.py`, `views.py`, `urls.py`, `apps.py` handle persistence, view dispatching, routing, and lifecycle events.
- `config/` contains Django project configuration:
  - `settings.py`: Standalone Django settings, dynamic module resolution, static/template paths.
  - `urls.py`: Root routing delegating to `apps/platformops/urls.py`.
  - `wsgi.py`: WSGI entrypoint for Gunicorn.
  - `local.env`: Environment variables for database, cache, broker, Loki, and GlitchTip connectivity.
  - `projectConfig.yaml`: Project name and default login redirects.
  - `observability/`: Proven configurations (`loki-config.yaml`, `config.alloy`, `glitchtip.env`, `glitchtip_runtime_map.yaml`, `patch_glitchtip_schema.py`).
- `packages/` contains vendored support packages:
  - `CommonUtils/`: Authentication, dynamic form parsing, telemetry, logging, and timer libraries.
  - `mcp_client/`: Agentic MCP client tools.
- `static/` & `templates_new/`:
  - `static/`: Static assets, vendor CSS/JS, and `cutil/` libraries.
  - `templates_new/`: Jinja/Django templates for the 6 core pages (`01-users.html`, `02-clusters.html`, `04-cluster-detail.html`, `08-config-manager.html`, `SystemMonitoring.html`, `Monitoring.html`, `09-diagnostics.html`), plus `navbar.html`, `sidebar.html`, and design tokens.
- `docker-compose.yml`: Standalone Compose manifest defining `postgres`, `redis`, `rabbitmq`, `loki`, `alloy`, `glitchtip_*`, and `web`.
- `agent_docs/`: Durable workflow and architectural documentation.

## Core Orchestration Modules

- `ClusterConfig.py`: Cluster topology management, inventory validation, and status rollup.
- `NodeConfig.py`: Node registration, SSH credential verification, and status monitoring.
- `ServiceConfig.py` & `serviceInstall.py`: Service catalog management, runtime configuration injection, container lifecycle management, and Ansible deployment orchestration.
- `ServiceDiagnostics.py`: Live container log streaming, Loki log history queries, and diagnostic snapshot archiving.
- `UserMgmnt.py`: Multi-tenant user provisioning, invitations, and RBAC authorization.
- `systemMonitoring.py`: Host and service performance metrics extraction via Prometheus.

## Main Interfaces and Integration Boundaries

- **Web Ingress**: Host port **`9020`** proxies to Gunicorn on internal port `8000`.
- **Database**: PostgreSQL on `platformops_network` (internal port `5432`).
- **Telemetry Ingestion**:
  - Prometheus queries directed to Prometheus exporter endpoints.
  - Loki logs queried via `http://platformops_loki:3100`.
  - GlitchTip errors and APM managed via `http://platformops_glitchtip_web:8000`.
- **Network Isolation**: All services communicate strictly over `platformops_network` with zero cross-talk to `cplatform_iktara_cPlatform`.
