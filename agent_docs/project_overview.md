# Project Overview

## Purpose

PlatformOps is a standalone, production-hardened DevOps and SRE control plane
streamlined from the proven `cPlatform` core into a clean, 6-page standalone
application. It retains the native UI layout, schemas, and orchestration engines
while eliminating all unrelated machine learning, model training/inference, dataflow,
and customer proxy application bloat.

## Scope

The core page set consists of strictly 6 functional areas:
1. **Users**: Multi-tenant user management, invitations, and role-based access control (`System_Admin`, `Operational`).
2. **Clusters**: Cluster, Node, and Service configuration, SSH management, runtime status, and Ansible deployment orchestration.
3. **Config Manager**: Live runtime configuration management, snapshot capture, diff comparison, and rollback engines.
4. **Performance**: System monitoring and Prometheus metrics for host nodes and running services.
5. **Monitoring**: Service health monitoring, uptime tracking, and GlitchTip error/APM integration.
6. **Diagnostics**: Real-time container log streaming, Loki integration, and diagnostic snapshot archiving.

All non-core modules (batch/stream dataflow pipelines, ML model training/inference, and 10 legacy proxy apps) have been completely removed.

## Architecture

PlatformOps runs as a standalone Django application (`apps.platformops`) powered by Gunicorn. The core orchestration engines (`ClusterConfig`, `NodeConfig`, `ServiceConfig`, `serviceInstall`, `ServiceDiagnostics`, `UserMgmnt`, `systemMonitoring`) interface directly with Django ORM models and vendored utility libraries (`CommonUtils`, `MCPClient`, `CutilJS`).

The runtime is an isolated, self-contained Docker Compose stack on `platformops_network`:
- **Web Application**: `platformops_web` running on host port **`9020:8000`**.
- **Database**: `platformops_db` (`iktaraai/services:postgres-1.0.0` on internal port `5432`).
- **Cache / Broker**: `platformops_redis` (`iktaraai/services:redis-1.0.0` on internal port `6379`) and `platformops_rabbitmq` (`cplatform-rabbitmq:latest` on internal port `5672`).
- **Telemetry Support**: `platformops_loki` (Loki 3.2.1), `platformops_alloy` (Alloy 1.5.1), and `platformops_glitchtip_*` (GlitchTip Web, Worker, Postgres, Valkey).

The stack operates in complete isolation from cPlatform containers on `cplatform_iktara_cPlatform`.

## Main Workflows

- Authenticate via `/` with default credentials (`admin` / `admin`) and land directly on `/PlatformIO/ClusterView/`.
- Manage Clusters and Nodes, launch/deploy catalog services via Ansible or local Docker runtimes, and track real-time container states.
- Capture configuration snapshots, detect live drift, compare versions, and apply live updates or rollbacks via Config Manager.
- Query Prometheus metrics and circular resource gauges via Performance Monitoring.
- Track error issues, transaction groups, and uptime checks via GlitchTip Monitoring.
- Stream live container logs, query Loki log history, and generate diagnostic archive packages via Diagnostics.

## Major Decisions

- **Django Direct Pivot**: Streamlined cPlatform directly in Django rather than continuing partial FastAPI/React reimplementation, delivering 100% functional parity across all 6 core pages.
- **Dedicated Isolated Network**: Configured `platformops_network` with zero dependencies on `iktara_network` or `yantrai_network`, avoiding port and container name collisions.
- **Vendored Core Assets**: Embedded `CommonUtils-1.0.22`, `MCPClient`, and `CutilJS` directly into `/root/PlatformOps/packages/` and `/root/PlatformOps/static/`.
- **Complete Bloat Removal**: Pruned all model training/inference, batch/stream ingestion, and proxy demo apps from schemas, routes, models, views, and templates.
