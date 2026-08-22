# PlatformOps

A streamlined, production-grade DevOps and SRE control plane featuring the native cPlatform UI, dynamic schema-driven form engines, and robust orchestration workflows across **6 core operational pages**, free of machine learning, dataflow pipeline, or proxy application bloat.

---

## 🎯 Scope: 6 Core Pages

1. **Users & RBAC** (`/PlatformIO/Users/`): Multi-tenant user provisioning, invitations, and role-based permissions (`System_Admin`, `Operational`).
2. **Clusters, Nodes & Services** (`/PlatformIO/ClusterView/`, `/PlatformIO/ClusterConfig/`): Cluster topology, SSH host registration, catalog-driven service provisioning, and Ansible deployment orchestration.
3. **Config Manager** (`/PlatformIO/ConfigManager/`): Live runtime configuration editor, snapshot timeline, diff comparison, and one-click rollback engine.
4. **Performance Monitoring** (`/PlatformIO/SystemMonitoring/`): Host resource utilization, Prometheus node/service telemetry, and circular metric gauges.
5. **Monitoring & SRE** (`/PlatformIO/Monitoring/`): Service health monitoring, uptime tracking, and GlitchTip error tracking/APM integration.
6. **Diagnostics & Logging** (`/PlatformIO/Diagnostics/`): Real-time container log streaming, Loki log history query engine, and diagnostic archive exports.

---

## 🏗️ Architecture & Isolation

PlatformOps runs as a standalone Django application (`apps.platformops`) powered by Gunicorn inside an isolated Docker network (`platformops_network`).

### Service Stack (`docker-compose.yml`)
- **Web App**: `platformops_web` (Gunicorn on host port **`9020:8000`**)
- **Database**: `platformops_db` (`iktaraai/services:postgres-1.0.0` on internal port `5432`)
- **Cache & Message Broker**: `platformops_redis` (`iktaraai/services:redis-1.0.0` on `6379`) and `platformops_rabbitmq` (`cplatform-rabbitmq:latest` on `5672`)
- **Telemetry Ingestion & Error Tracking**:
  - `platformops_loki`: Loki 3.2.1 for log aggregation (`http://platformops_loki:3100`)
  - `platformops_alloy`: Alloy 1.5.1 for telemetry forwarding
  - `platformops_glitchtip_web` & `platformops_glitchtip_worker`: GlitchTip 6.1.9 for error tracking and APM
  - `platformops_glitchtip_postgres` & `platformops_glitchtip_valkey`: Dedicated GlitchTip backing storage

> **Complete Isolation Guarantee:** The PlatformOps stack runs strictly on `platformops_network` with dedicated volumes and ports, with zero cross-talk, shared volumes, or interference with cPlatform containers on `cplatform_iktara_cPlatform`.

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
- **Default Login Landing**: `/PlatformIO/ClusterView/`

### Verifying Stack Health
```bash
docker compose ps
```

The legacy `compose-up` target is a separate compatibility stack on port 9002;
do not use it for isolated MVP verification or against the live cPlatform
deployment.

## Verification
Run the repository checks and frontend build:
```bash
make check
cd apps/web && npm run build
```
`make check` is non-mutating and includes compilation, shipped unit tests, and
the isolated static verifier. See [the MVP handoff](docs/mvp-status.md) for
environment prerequisites and known test limitations.
