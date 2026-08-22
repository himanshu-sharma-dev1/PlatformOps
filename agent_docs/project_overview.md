# Project Overview

## Purpose

PlatformOps is a fully independent, production-hardened DevOps and SRE control plane streamlined from the `cPlatform` core into a clean, standalone 6-page application. It delivers native infrastructure orchestration, runtime telemetry, dynamic configuration management, and issue tracking while completely eliminating legacy customer demo code, dataflow pipelines, and machine learning models.

## Scope

The application scope strictly covers **6 core operational areas**:
1. **Users**: Multi-tenant user management, invitation lifecycle via Mailpit SMTP, and role-based access control (`System_Admin`, `Operational`, `Developer`, `Viewer`).
2. **Clusters**: Cluster topology, Node management with password/SSH authentication, dynamic inventory generation, and Ansible/Docker container deployment.
3. **Config Manager**: Live runtime configuration discovery, snapshot checkpoints on `/home/ubuntu/Backup_Platform`, visual diffs, and safe rollback mechanics.
4. **Performance**: Host and container telemetry powered by Prometheus, Node Exporter, and Process Exporter.
5. **Monitoring**: Real-time service health, uptime tracking, and error/APM integration powered by GlitchTip.
6. **Diagnostics**: Real-time container log streaming, Loki log history queries, and diagnostic snapshot archiving.

## Architecture

PlatformOps runs as a standalone Django application (`apps.platformops`) powered by Gunicorn inside a dedicated Docker container (`platformops/web:1.0.0`).

### Container Stack (`platformops_network`)
All 14 services in the platform operate under the unified **`platformops/*:1.0.0`** image namespace on an isolated bridge network:
- **Core Web App**: `platformops_web` on host port **`9020:8000`**.
- **Core Database**: `platformops_db` (`platformops/postgres:1.0.0` on internal `5432`).
- **Cache & Queue**: `platformops_redis` (`platformops/redis:1.0.0`) and `platformops_rabbitmq` (`platformops/rabbitmq:1.0.0`).
- **Mail Integration**: `platformops_mailpit` on ports **`8025`** (UI) and **`1025`** (SMTP).
- **Performance Telemetry**: `platformops_prometheus` on port **`9090`**, `platformops_node_exporter` on port **`9100`**, and `platformops_process_exporter` on port **`9256`**.
- **Log Telemetry**: `platformops_loki` on internal port `3100` and `platformops_alloy` log collector.
- **Error Tracking**: `platformops_glitchtip_web` on host port **`8008`**, backed by `platformops_glitchtip_worker`, `platformops_glitchtip_postgres`, and `platformops_glitchtip_valkey`.

## Operational Guardrails & Working Principles

1. **Permanent Cluster & Node Preservation**:
   - Never wipe, reset, or overwrite user-configured nodes, clusters, or services with automated fixture scripts.
   - The user's active cluster, `NODE1001` (with real SSH credentials), `AIOrchestrator_SERV1002`, and adopted containers must remain permanent.
2. **Volume Consistency**:
   - Use `/home/ubuntu/Backup_Platform` as the primary node and service volume mount for deployments and configuration snapshots.
3. **Zero cPlatform Interference**:
   - PlatformOps must never bind to cPlatform ports (`80`, `443`, `9002`, `9008`, `9012`, `9013`, `9014`, `9015`, `9017`, `9018`, `9019`).
   - PlatformOps containers must communicate strictly over `platformops_network` without touching `cplatform_iktara_cPlatform`.
4. **Resilient Non-Blocking Operations**:
   - External service configuration pushes use a 5-second timeout to prevent blocking or worker exit code 255.
   - Settings reloads must safely refresh cached `PlatformSettings` without `AttributeError` or `TypeError`.
