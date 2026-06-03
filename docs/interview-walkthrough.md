# PlatformOps: Interview Technical Walkthrough Guide

This walkthrough guide is designed to guide an interviewer through the architecture, design patterns, and DevOps configurations of the `PlatformOps` control plane, highlighting the direct engineering translation from enterprise internal developer platform (IDP) systems.

---

## 1. Architectural Overview & Context
- **The Core Problem**: Managing service lifecycle dependencies, node constraints, and operational observability pipelines across heterogeneous server clusters.
- **The Inspiration**: Distilled directly from enterprise-grade orchestrators (e.g. `cPlatform`), migrating complex database relationships and placement decisions from custom config files to a dynamic FastAPI + React control plane.
- **Backend Architecture**: Fast, lightweight API utilizing **SQLAlchemy ORM** to manage relational tables (`Cluster`, `Node`, `ServiceInstance`, `IncidentRecord`, `MaintenanceWindow`, `SloReport`, `CapacityReport`, etc.) and a topological sorting runner that simulates DAG-based plane initializations.

---

## 2. Deep-Dive Showcase Points

### A. Dependency-Aware Lifecycle Governance
*File Reference: [`platformops/orchestrator.py`](file:///Users/himanshusharma/PlatformOps/apps/api/platformops/orchestrator.py)*
- **Real-Time Impact Assessments**: When deleting a resource (Service, Node, or Cluster), the backend runs a recursive dependency graph lookup. If active downstream dependencies are found, the delete is blocked with a detailed explanation of the blockages.
- **Governance Gateways**: Force-delete flags (`force=true`) are guarded. To forcefully override blocks on stateful infrastructure components (like PostgreSQL/Redis cores), the system validates:
  1. An active **Maintenance Window** configuration.
  2. An approved two-person authorized **Force-Delete Policy Request** (one-time consume pattern).

### B. Subsystem-Level Topological Rollouts
*File Reference: [`platformops/orchestrator.py`](file:///Users/himanshusharma/PlatformOps/apps/api/platformops/orchestrator.py)*
- **DAG Sequencer**: Computes the correct execution order of multiple cards in planes (e.g., `vector-plane`, `distributed-training-plane`) using topological sorting.
- **Placement Advisor**: Employs a multi-heuristic evaluation algorithm (scoring nodes based on CPU risks, memory reservations, storage capacity, and dependency checks) to recommend the optimal host node for new deployments.

### C. Observability Pipeline & Health Signals
*File Reference: [`platformops/orchestrator.py`](file:///Users/himanshusharma/PlatformOps/apps/api/platformops/orchestrator.py)*
- **Agent Pipelines**: Simulates log routing configurations via the Alloy pipeline. It monitors `alloy-core` daemonset state on each node alongside exporter endpoints and raises structured incident events for connectivity delays.

---

## 3. DevOps Packaging & Infrastructure Map

### A. Containerization & Build Strategy
*File Reference: [`Dockerfile`](file:///Users/himanshusharma/PlatformOps/ops/docker/web-api/Dockerfile)*
- **Multi-Stage Build**: Leverages a separate Python builder image to run compiler installations, keeping the runtime runner container extremely lightweight (`3.12-slim`).
- **Security Compliance**: Enforces **Non-Root Execution** under a dedicated `appuser` (UID `10000`, GID `10001`) and locks down write accesses to localized directories.
- **Docker Compose Dev Experience**: [docker-compose.local.yml](file:///Users/himanshusharma/PlatformOps/ops/compose/docker-compose.local.yml) sets up a mock local cluster (Postgres, Redis, RabbitMQ, Prometheus, Loki) and maps persistent volumes for local SQLite database directories.

### B. Infrastructure as Code (Terraform)
*File Reference: [`ops/terraform/aws/main.tf`](file:///Users/himanshusharma/PlatformOps/ops/terraform/aws/main.tf)*
- **Network Layout**: Defines virtual isolation (VPC, Subnet, Route Tables, Internet Gateway).
- **Security Groups**: Sets explicit ingress policies for port `8000` (API backend) and `80` (React Web Console).
- **Compute Provisioning**: Boots an Ubuntu EC2 host node with standard GP3 storage, demonstrating production-level node provisioning.

### C. Kubernetes Orchestration (Helm)
*File Reference: [`ops/helm/platformops/`](file:///Users/himanshusharma/PlatformOps/ops/helm/platformops/)*
- **Helm 3 Standards**: Features dynamic template values, helper naming macros, and persistent volume claim configurations (`pvc.yaml`).
- **Probes & Security**: Configures Kubernetes `livenessProbe` and `readinessProbe` queries checking FastAPI OpenAPI endpoints to ensure healthy pod routing.
