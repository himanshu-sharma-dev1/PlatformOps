# PlatformOps

[![CI Status](https://github.com/cplatform/platformops/actions/workflows/ci.yml/badge.svg)](https://github.com/cplatform/platformops/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![Terraform](https://img.shields.io/badge/Terraform-1.5.0+-7B42BC.svg?style=flat&logo=terraform)](https://www.terraform.io)
[![Helm](https://img.shields.io/badge/Helm-3-0F1689.svg?style=flat&logo=helm)](https://helm.sh)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python)](https://www.python.org)

A portfolio-grade DevOps/SRE control plane and orchestrator built with FastAPI, React, SQLite, and Ansible. It models the core architectural patterns of modern internal developer platforms (IDPs), offering lifecycle governance, subsystem-level rollout sequencing, config management, and deep diagnostics.

## Key Subsystems & Features

### 1. Dependency-Aware Lifecycle Governance
- **Deletion Safety Modal**: Prevents accidental deletes of services, nodes, or clusters by running a real-time impact assessment.
- **Dependency Guardrail**: Deletion of critical infrastructure cards (e.g. `postgres-core`, `redis-core`, `rabbitmq-core`, etc.) or resources with active downstream dependents is strictly blocked unless `force=true` is provided.
- **Force-Delete Policy Gates**: `force=true` actions require a strong reason and, for risky targets, an active maintenance window before deletion is allowed.
- **Approval Governance**: Risky force deletes also require approved force-delete requests with two-person authorization and one-time consumption.
- **Cascade Deletion**: Node and cluster deletions require force flags if active nodes/services exist, cascading deletion cleanly and logging structured audit events.
- **App Isolation**: Application cards can be deleted safely without accidentally removing shared backing infrastructure dependencies.

### 2. Subsystem-Level Topological Rollout
- **Rollout Sequencer**: Generates sequential rollout steps sorted topologically based on dependencies for planes like `shared-data-plane`, `vector-plane`, `distributed-training-plane`, etc.
- **Dependency Order Integrity**: For example, `vector-plane` automatically schedules `etcd` and `MinIO` bootstrap before initializing `Milvus`.
- **Infrastructure Isolation**: Airflow workflow planes isolate their local `airflow-postgres` and `airflow-redis` resources from the global postgres-core/redis-core DB cards.
- **Placement Advisor**: Recommends the best node for a target service based on dependency readiness, node health, and projected CPU/memory/storage risk.
- **Placement Auto-Deploy**: Optionally executes a one-click deployment on the best-ranked node, including auto-install of missing dependencies before deploying the main card.

### 3. DTrain Distributed ML Training Control Plane
- **Training Showcase**: A specialized dashboard representing `dtrain-tracker`, `dtrain-controller`, and `dtrain-workers` status and readiness.
- **Simulation Metrics**: Returns GPU availability status and deterministic metrics tracking active, queued, completed, and failed training jobs.

### 4. Diagnostics, Config, and Backup Parity
- **Capability Metadata**: Exposes container target logs, log paths, sudo privilege requirements, and backup support for 40+ service cards.
- **Config Strategy**: Differentiates between Live config files, Catalog-generated configs, and deliberately configless helper cards.
- **Backup Strategy Policy**: Distinguishes database dumps, volume archives, object-store archives, config-only backups, and no backup required, warning on stateful cards lacking backup.
- **Alloy Log Pipeline**: Includes `alloy-core` as an observability infrastructure card for log collection pipeline parity in addition to Loki/Prometheus.
- **Observability Pipeline Board**: Surfaces per-node Alloy/Loki/Prometheus/exporter readiness, ingestion state, and latest diagnostics signal timestamps.

### 5. Parity Audit and Lifecycle Telemetry
- **Catalog Coverage Audit**: Aggregates diagnostics/config/backup readiness for every catalog service card with per-card issue reporting.
- **Lifecycle Audit Window**: Summarizes blocked, forced, and safe delete activity over a configurable time window from operational events.
- **Filtered Operations Feed**: Supports category/level/search filtering for faster troubleshooting and governance reviews.

### 6. DevOps & Infrastructure Parity (Portfolio Packaging)
- **Multi-Stage Containerization**: Custom, production-grade, secure multi-stage [Dockerfile](file:///Users/himanshusharma/PlatformOps/ops/docker/web-api/Dockerfile) built on `python:3.12-slim` that isolates dependency setups and executes under a non-root `appuser` (UID `10000`).
- **Local Services Orchestration**: A [docker-compose.local.yml](file:///Users/himanshusharma/PlatformOps/ops/compose/docker-compose.local.yml) stack linking PostgreSQL, Redis, RabbitMQ, Prometheus, Loki, and our custom `web-api` control plane with persistent storage volumes.
- **Infrastructure as Code (IaC)**: A mock but syntax-valid Terraform configuration located in [ops/terraform/aws/](file:///Users/himanshusharma/PlatformOps/ops/terraform/aws/) that provisions VPC, Subnet, Route Tables, Internet Gateways, Security Groups, and an Ubuntu EC2 instance representing the Control Plane orchestrator.
- **Kubernetes Orchestration (Helm)**: A complete Helm 3 chart in [ops/helm/platformops/](file:///Users/himanshusharma/PlatformOps/ops/helm/platformops/) defining dynamic deployments, ClusterIP services, persistent volume claims, security contexts, and resource constraints to deploy PlatformOps in cloud-native K8s clusters.
- **Developer Workflows**: Expanded [Makefile](file:///Users/himanshusharma/PlatformOps/Makefile) with shortcuts for automated linting, formatting check (via Ruff), docker build pipeline, and database teardown/cleanup actions.

## Quick Start

### Backend API Setup
```bash
# Sourcing the python environment
source /Users/himanshusharma/venv/bin/activate

# Seed database and startup API
make check
make api
```
The API will start reloading on `http://127.0.0.1:8000`.

### Frontend Web Console Setup
```bash
cd apps/web
npm install
npm run dev
```
Open `http://localhost:5173` to explore the dashboard.

## Verification
Run all tests and verify compilation:
```bash
make check
cd apps/web && npm run build
```
All verification steps must compile with zero errors or warnings.
