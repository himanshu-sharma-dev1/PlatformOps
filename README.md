# PlatformOps

[![CI Status](https://github.com/cplatform/platformops/actions/workflows/ci.yml/badge.svg)](https://github.com/cplatform/platformops/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![Terraform](https://img.shields.io/badge/Terraform-1.5.0+-7B42BC.svg?style=flat&logo=terraform)](https://www.terraform.io)
[![Helm](https://img.shields.io/badge/Helm-3-0F1689.svg?style=flat&logo=helm)](https://helm.sh)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python)](https://www.python.org)

A FastAPI/React DevOps and SRE control plane being ported from the legacy
`cPlatform` implementation. The current delivery is a functional selected-page
MVP: the UI can remain visually different while the operator workflows use
real isolated Docker/Ansible operations and cPlatform-compatible behavior.

See [the MVP status handoff](docs/mvp-status.md) for the evidence-scoped
acceptance status and limitations, the [selected-page functional parity
mapping](docs/selected-page-functional-parity.md) for authoritative behavior
coverage, and the [next validation plan](docs/next-validation-plan.md) for the
ordered fresh-fixture acceptance run. The [isolated runtime
guide](docs/isolated-platformops.md) contains the Compose lifecycle details.

> **Current runtime:** PlatformOps uses host port **9020**. Optional Mailpit
> uses **9010**. The existing cPlatform deployment and its network are kept
> untouched.

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

### 6. DevOps & infrastructure packaging
- **Combined production image:** the [web/API Dockerfile](ops/docker/web-api/Dockerfile) builds the React bundle and serves it from the FastAPI image.
- **Isolated runtime:** [docker-compose.isolated.yml](ops/compose/docker-compose.isolated.yml) provides project-scoped PostgreSQL, Redis, RabbitMQ, Prometheus, Loki, Mailpit, and a private DinD engine.
- **Infrastructure templates:** Terraform is available under [ops/terraform/aws/](ops/terraform/aws/) and a Helm chart under [ops/helm/platformops/](ops/helm/platformops/); these are packaging/templates, not part of the selected-page runtime acceptance gate.
- **Developer workflows:** the [Makefile](Makefile) provides compile, unit, build, isolated verification, and isolated lifecycle targets.

## Quick Start

### Recommended isolated MVP

```bash
make isolated-verify
make build
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit make isolated-up
```

Open `http://127.0.0.1:9020` and sign in with the development bootstrap
credentials `admin` / `admin`. Mailpit is available at
`http://127.0.0.1:9010`. Stop the stack with `make isolated-down`; its named
volumes are retained.

### Local development

For backend hot reload, install the Python dependencies and run
`make api`. For the Vite development server:

```bash
cd apps/web
npm install
npm run dev
```

The local development server is normally available at `http://localhost:5173`.
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
