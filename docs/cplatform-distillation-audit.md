# Comprehensive Distillation Audit: cPlatform to PlatformOps

This document details the technical mapping, successfully ported features, and outstanding gaps between the enterprise-grade **cPlatform** Django codebase and the modern decoupled **PlatformOps** (FastAPI + React) orchestrator.

---

## 1. Core Architectural Evolution

| Dimension | cPlatform (Source Enterprise Monolith) | PlatformOps (Distilled Portfolio Orchestrator) |
| :--- | :--- | :--- |
| **Tech Stack** | Python Django, PostgreSQL, Celery, Jinja2 Templates | Python FastAPI, SQLAlchemy 2.0, SQLite, React + Vite SPA |
| **Orchestration** | Ansible Playbooks, Terraform, Docker API wrapper | simulated playbook CLI log, Compose generation, real local Compose fallback |
| **Subsystem Governance** | Imperative Django controller validation logic | Declarative YAML contracts (`catalog/services.yaml`) and topological sorting |

---

## 2. Relational Schema Mapping

Below is the exact mapping of cPlatform's Django ORM models to PlatformOps' SQLAlchemy 2.0 tables:

### 2.1 Core Infrastructure & Services
- **`Cluster`** maps to **`clusters`**: Models physical or cloud region groupings (e.g. `ap-south-1 (Mumbai)`), target environment (`Production`, `Staging`), and repository type (`NFSVolume`, `DistributedFS`).
- **`Node`** maps to **`nodes`**: Tracks host IPs, volume root folders (like `/platformops`), monitoring port parameters, and GPU availability state.
- **`Service`** maps to **`service_instances`**: Stores service installations, active configurations (`config_json`), target port configurations, and deployments statuses.

### 2.2 Operations & Telemetry
- **`NodeEvent`** & **`ServiceEvent`** map to **`operational_events`**: Consolidated into a unified structured event feed with level filters (`info`, `warning`, `error`).
- **`ReportInfo`** & **`ReportLog`** map to **`monitoring_checks`** & **`slo_reports`**: Expose metric sweeps, threshold alerts, and service level objectives.
- **`DataFlowLogs`** & **`DataflowBatchConfig`** map to **`log_archives`** & **`drift_reports`**: Capture changes in dataset configs and track historical files.

---

## 3. Ported DevOps Capabilities (Current State)

PlatformOps successfully distills the primary SRE and DevOps subsystems from cPlatform:

### 3.1 Dependency-Aware Lifecycle Governance
*   **cPlatform Design**: Service deletion removes containers, but node deletion checks `Service.objects.filter(Node=node)` to prevent deleting a node with active services.
*   **PlatformOps Parity**: Extends this into a fully-fledged SRE Deletion Safety Plane (`lifecycle_impact` in `orchestrator.py`):
    *   **Protected Infra**: Strictly blocks deleting stateful/core cards (e.g., `postgres-core`, `milvus-core`, `etcd-core`) if downstream microservices depend on them.
    *   **Force-Delete Gateways**: Force deletes require a reason of at least 12 characters, an active scheduled maintenance window (`MaintenanceWindow`), and an authorized two-person signature (`ForceDeleteApproval`).

### 3.2 Topological Rollout Sequences
*   **cPlatform Design**: Launcher scripts verify Docker prerequisites sequentially using distributed helper methods (`serviceInstall.py`).
*   **PlatformOps Parity**: Employs a topological dependency graph resolver (`_dependency_order` in `orchestrator.py`):
    *   Computes exact bootstrap orders (e.g. `etcd-core` & `minio-core` -> `milvus-core` -> `rag`).
    *   **Subsystem Isolation**: Enforces tenant boundary sorting, ensuring the Airflow workspace (`workflow-plane`) provisions separate databases (`airflow-postgres`, `airflow-redis`) instead of connecting to shared production databases.

### 3.3 Diagnostic Tailing & Backfills
*   **cPlatform Design**: Tails stdout/stderr files on nodes and backfills rotated log archives to Grafana Loki.
*   **PlatformOps Parity**: Integrates Grafana Alloy log collection pipeline parity:
    *   `/api/services/{id}/diagnostics/live` returns cursored live Loki logs.
    *   `/api/services/{id}/diagnostics/backfill` indexes historical `.log.gz` archives on disk.
    *   **SRE AI Analyst**: Simulates rule-based diagnostic analysis tracking errors and suggesting immediate remediation steps.

### 3.4 Distributed ML Training Control Plane (DTrain)
*   **cPlatform Design**: Allocates `ResourceRow` / `InferenceResource` limits and registers Celery workloads.
*   **PlatformOps Parity**: Simulates `dtrain-tracker` (MLFlow experiment dashboard), `dtrain-controller`, and `dtrain-worker` instances with real GPU metrics, job queues, and status simulations.

---

## 4. Identified Parity Gaps (Future Distillation Phases)

While the core infrastructure orchestrator is fully functional, several secondary modules from the original cPlatform codebase are currently represented as frontend UI placeholders (dimmed with `opacity: 0.6` in `Sidebar.tsx`) or lack specific backend CRUD operations:

### 4.1 Ingress/Egress Batch & Stream Dataflows
*   **cPlatform Capabilities**: CRUD endpoints for FTP, SFTP, S3, or Google Drive sources; scheduling periodicity (5m, 15m, HOURLY) and real-time ingestion pipelines (MQTT, CDC, CDC Stream).
*   **PlatformOps Current State**: Modeled as static infrastructure cards in `services.yaml` (`nifi-core`, `ans`, `airflow`), but lacks standalone CRUD APIs and interactive screens for "Batch I/O" and "Stream I/O" managers.
*   **Remediation Recommendation**: Build a dataset ingestion form interface that lets operators configure connection pools (FTP/S3) and maps them to NiFi/Airflow configuration variables.

### 4.2 Model Registry, Evaluation & Compare UI
*   **cPlatform Capabilities**: Algo category schemas (`Supervised`, `Anomaly`, `FraudAnalytics`, `TimeSeries_Forecast`), evaluation scoring, and model weight matrices comparison.
*   **PlatformOps Current State**: DTrain distributed training status is visible, but there is no centralized Model Registry, model version comparisons, or algorithm tuning forms.
*   **Remediation Recommendation**: Implement a model registry dashboard with evaluation charts comparing training accuracy, loss, and inference resource footprints.

### 4.3 Node Onboarding Credentials & Auth
*   **cPlatform Capabilities**: `NodeAuth` tracks credentials with encryption keys, private keys, and user details.
*   **PlatformOps Current State**: `Node` model contains fields for SSH users and key paths, but lacks a secure Vault credential manager or token invitation system.
*   **Remediation Recommendation**: Design a secure key registry drawer that securely mounts private SSH key files and runs an Ansible `ping` smoke test.

---

## 5. Next Steps

1.  **Refine UI Styling (Phase 2 of Plan)**: Polish grid alignment, glowing states, and interactive diagnostics screens to resolve remaining template anomalies.
2.  **Activate Dimmed Sidebar Panels**: Implement simple CRUD views for Dataflow and Model parameters to replace the template placeholders.
3.  **Ansible Playbook Integrations**: Integrate live dry-run command feeds to visually show operators the Ansible plays being executed during node validation.
