# PlatformOps

A streamlined, production-grade DevOps and SRE control plane featuring dynamic schema-driven form engines, robust infrastructure orchestration, real-time telemetry, and error tracking across **6 core operational pages**, fully independent of external monorepos or legacy bloat.

---

## 🎯 Scope: 6 Core Operational Pages

1. **Users & RBAC** (`/PlatformIO/Users/`): Multi-tenant user provisioning, invitations via Mailpit SMTP, and role-based permissions (`System_Admin`, `Operational`, `Developer`, `Viewer`).
2. **Clusters, Nodes & Services** (`/PlatformIO/ClusterView/`, `/PlatformIO/ClusterConfig/`): Cluster topology, SSH host registration, catalog-driven service provisioning, and Ansible deployment orchestration.
3. **Config Manager** (`/PlatformIO/ConfigManager/`): Live runtime configuration editor, snapshot timeline on `/home/ubuntu/Backup_Platform`, diff comparison, and rollback engine.
4. **Performance Monitoring** (`/PlatformIO/SystemMonitoring/`): Host resource utilization, Prometheus node and process telemetry, and circular metric gauges.
5. **Monitoring & SRE** (`/PlatformIO/Monitoring/`): Service health monitoring, uptime tracking, and GlitchTip error tracking/APM integration.
6. **Diagnostics & Logging** (`/PlatformIO/Diagnostics/`): Real-time container log streaming, Loki log history query engine, and diagnostic archive exports.

---

## 🏗️ Architecture & Isolation

PlatformOps runs as a standalone Django application (`apps.platformops`) powered by Gunicorn inside a dedicated Docker container (`platformops/web:1.0.0`).

### Unified Service Stack (`docker-compose.yml`)

All 14 services in the platform operate under the **`platformops/*:1.0.0`** image standard on the isolated bridge network `platformops_network`:

| Container Name | Image Tag | Purpose / Function | Port Mappings |
|---|---|---|---|
| `platformops_web` | `platformops/web:1.0.0` | Core Django Application (Gunicorn 3 workers) | `9020:8000` |
| `platformops_db` | `platformops/postgres:1.0.0` | PostgreSQL 17 primary database | Internal (`5432`) |
| `platformops_redis` | `platformops/redis:1.0.0` | Redis cache and session broker | Internal (`6379`) |
| `platformops_rabbitmq` | `platformops/rabbitmq:1.0.0` | RabbitMQ message broker for Celery tasks | Internal (`5672`) |
| `platformops_mailpit` | `platformops/mailpit:1.0.0` | Mailpit SMTP email delivery & Web UI | `8025` (UI), `1025` (SMTP) |
| `platformops_prometheus` | `platformops/prometheus:1.0.0` | Prometheus telemetry server | `9090:9090` |
| `platformops_node_exporter` | `platformops/node-exporter:1.0.0` | Host hardware & OS metrics collector | `9100:9100` |
| `platformops_process_exporter`| `platformops/process-exporter:1.0.0`| Process-level resource metrics collector | `9256:9256` |
| `platformops_loki` | `platformops/loki:1.0.0` | Loki centralized log aggregation store | Internal (`3100`) |
| `platformops_alloy` | `platformops/alloy:1.0.0` | Alloy telemetry & log shipper | Internal (`12345`) |
| `platformops_glitchtip_web` | `platformops/glitchtip:1.0.0` | GlitchTip APM & error tracking web UI | `8008:8000` |
| `platformops_glitchtip_worker`| `platformops/glitchtip:1.0.0` | GlitchTip background Celery worker | Internal |
| `platformops_glitchtip_postgres`| `platformops/glitchtip-postgres:1.0.0`| PostgreSQL backing GlitchTip | Internal |
| `platformops_glitchtip_valkey`| `platformops/glitchtip-valkey:1.0.0` | Valkey cache backing GlitchTip | Internal |

> **Zero Cross-Talk Guarantee:** PlatformOps runs strictly in `platformops_network`. It has zero dependency on, and causes zero interference with, any containers on `cplatform_iktara_cPlatform`.

---

## 🚀 Quick Start

### Starting the Stack
```bash
docker compose up -d
```

### Accessing PlatformOps
- **URL**: [http://localhost:9020/](http://localhost:9020/)
- **Default Username**: `admin`
- **Default Password**: `admin`
- **Mailpit UI**: [http://localhost:8025/](http://localhost:8025/)
- **Prometheus UI**: [http://localhost:9090/](http://localhost:9090/)
- **GlitchTip UI**: [http://localhost:8008/](http://localhost:8008/)

---

## 🧪 Testing & Verification

### Running Django Unit & Contract Tests
```bash
docker compose exec web python manage.py test cPlatformIO.tests
```

### Running the Live Acceptance Suite
```bash
python3 scripts/test_platformops_acceptance.py
```

### Running the Live End-to-End Service Flow
```bash
python3 scripts/test_live_service_flow.py
```
