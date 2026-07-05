# Cluster Parity Analysis: cPlatform vs PlatformOps

This document details the parity between the legacy `cPlatform` cluster functionality and the modern `PlatformOps` orchestrator, focusing heavily on server-level operations, provisioning, live status, port mappings, node/service CRUD, and the ability to self-deploy the observability stack.

---

## 1. Cluster Identity & CRUD Operations

### Legacy `cPlatform`
- **Data Model**: Tracks `cluster_name`, `cluster_type` (Primary/Secondary), `cluster_variant` (Kubernetes, Standalone, Edge), `repo_type`, and `image_store_type` (Local, Dockerhub, ECR).
- **Provisioning Logic (`ClusterConfig.py`)**:
  - The API relies on a rigid "Primary" vs "Secondary" paradigm.
  - When a Primary cluster is created, it automatically triggers `_bootstrap_primary_cluster`. This provisions a mock Node with IP `0.0.0.0` and immediately schedules the `AIOrchestrator` service to it.
- **UI**: Handled via `02-clusters.html` drawer. It requires a 4-step wizard to map identity, repository, and image store credentials.

### Modern `PlatformOps`
- **Data Model**: Tracks `name`, `region`, and `environment` (`models.Cluster`).
- **Provisioning Logic**: 
  - PlatformOps abstracts away "Primary/Secondary". All clusters are logical groupings of Nodes.
  - Nodes have detailed configurations for real server-level deployment: `ssh_user`, `ssh_key_path`, `docker_network`, `volume_root`.
- **Parity Gap / Needs**: PlatformOps is missing the explicit `image_store` metadata at the cluster level. However, PlatformOps handles real deployments via SSH/Ansible, meaning it doesn't mock the IP address but actively targets real hosts.

---

## 2. Node CRUD, VM Provisioning & Resource Aggregation

### Legacy `cPlatform`
- **Cloud VM Provisioning (`TerraformMgmt.py`)**: 
  - Allows direct provisioning and teardown of VM instances on AWS and GCP.
  - Integrates with Terraform under the hood. It dynamically generates tf files (`generate_tf_template` / `generate_tf_template_gcp`), sets up key files, credentials, and executes `initiate_provision_instance` / `destroy_instance`.
- **Node Features**: Nodes track GPU status, IP address, and auth credentials. 
- **Aggregation**: The `cluster_get_config_info_v2()` API dynamically calculates `total_vcpus` and `total_memory` for the cluster by aggregating JSON payload values (`node_provision_config->>'vcpu'`) using RawSQL.

### Modern `PlatformOps`
- **Cloud VM Provisioning**: Completely missing. PlatformOps assumes the target nodes are already provisioned (e.g., in `local` or `aws` environments) and only handles docker-based service deployment and SSH connectivity.
- **Node Features**: Nodes are represented in `models.Node` with `facts_json` storing hardware telemetry.
- **Aggregation**: PlatformOps offloads this to a dedicated `CapacityReport` model which snapshots capacity over time, allowing for historical tracking rather than just real-time SQL aggregation.
- **Server-Level Operations**: PlatformOps executes `generate_inventory()` and uses `ansible_runner` to genuinely ping and deploy to Nodes via SSH keys. It supports `NodeEnvironment.aws` vs `NodeEnvironment.local`.

---

## 3. Service Mapping & Port Allocation

### Legacy `cPlatform`
- **Logic**: `NodeConfig.node_get_service_list()` maps which services belong to which nodes.
- **Live Status & Monitoring Tree**: `cluster_get_monitoring_tree()` fetches services but explicitly *excludes* infrastructure services (`infrarabbitmq`, `infranodeexporter`, `infraprometheus`, etc.) to keep the UI clean.
- **Port Mapping**: Handled statically within the Django configurations, largely rendered as UI elements in `clusterDetail.js`.

### Modern `PlatformOps`
- **Logic**: Managed via `ServiceInstance` and deeply integrated into a topological dependency graph (`topology(db)`).
- **Port & Config Management**: 
  - PlatformOps uses `ConfigSnapshot` versions mapped to `ServiceInstance`s to mount real `config.yaml` files.
  - `generate_compose(node)` generates a real `docker-compose.yml` dynamically based on the topological requirements, exposing the correct ports automatically.
- **Parity Achievement**: PlatformOps exceeds cPlatform by resolving dependencies. If an app needs Postgres, Postgres is scheduled first on the same (or remote) node.

---

## 4. Live Status & Observability Pipeline

### Legacy `cPlatform`
- The cluster dashboard statically queries uptime and health through periodic refreshes. 

### Modern `PlatformOps`
- **Self-Deploying Observability**: PlatformOps treats the observability stack as a first-class citizen. Features like `bootstrap_observability_plane` deploy Alloy, Loki, and Prometheus.
- **Live Logs**: `service_live_logs()` provides real-time streaming of container logs from the servers.
- **Diagnostics**: `service_diagnostics_analysis()` and `DriftReport` check whether the live container matches the expected `ConfigSnapshot`.

---

## 5. DTrain Container Deployment Plan

To satisfy the requirement of testing "server level no mock no local just server working things" using a **dtrain** container, PlatformOps handles this via:

1. **Topology & Subsystems**: `dtrain` is recognized as a subsystem. 
2. **Placement**: PlatformOps' `placement_recommendations()` will evaluate available real nodes (using SSH metrics, not mocks) to place the `dtrain-worker` and `dtrain-controller`.
3. **Execution**: `execute_deployment_plan` will trigger an Ansible playbook targeting the Node, pulling the `dtrain` image, and executing it using the generated Docker compose config on the server.

### Next Steps for Real Server Testing
1. Provision a real EC2 / VM Node in PlatformOps.
2. Trigger the `bootstrap_observability_plane` to deploy the monitoring stack to it.
3. Add the `dtrain` service to the catalog and map it to the Node.
4. Execute the deployment job and verify live logs via `service_live_logs()`.

---

## 6. Implementation Gaps & Features Needing Testing

While PlatformOps provides a vastly superior architecture for server-level operations and topological deployments, several features remain unimplemented or untested and must be prioritized before this is considered a production-grade resume project.

### 6.1 Backend API / Data Model Gaps
- **Infrastructure Auto-Discovery & Adoption (CRITICAL)**: 
  - *Legacy Feature*: Hitting the "Discover" button (`discoverInfraBtn`) ran an Ansible playbook (`service_infra_discovery_playbook.yml`) and script on the remote host, checking running Docker containers, matching them to known service schemas, and "adopting" them (`adopted=True`) into the database.
  - *PlatformOps Gap*: PlatformOps is completely missing the `discover_infrastructure` backend logic. It cannot auto-discover pre-existing container runtimes on a node. We need to implement an auto-discovery endpoint and supporting Ansible playbook/script.
- **Terraform Cloud VM Provisioning**:
  - *Legacy Feature*: Integrates directly with AWS and GCP to provision and tear down instances programmatically via dynamic Terraform template generation.
  - *PlatformOps Gap*: Totally absent. PlatformOps requires nodes to be manually provisioned and added to the database. To achieve parity, a Terraform module/endpoint is required to provision/de-provision VMs.
- **User Invitation & Role Management**:
  - *Legacy Feature*: Supports dynamic invite flows (`invite_user`, `revoke_invite`, `resend_invite`, and accept invite via email tokens).
  - *PlatformOps Gap*: Completely missing. PlatformOps lacks any dynamic workspace onboarding or verification framework.
- **Dynamic Last Visited Session Tracking (`track_visit`)**:
  - *Legacy Feature*: Captures navigation events (`UserMgmnt.user_update_last_visited`) and automatically returns the operator to their last active cluster/node/service workspace.
  - *PlatformOps Gap*: Missing. Workspaces are not persisted on a per-user session level.
- **Image Store Type Tracking**: The `Cluster` and `ServiceInstance` models currently do not track registry types (`Dockerhub`, `ECR`, `Local`) or explicit registry credentials. This needs to be added to the `Cluster` model or a new `RegistryCredential` model to fully support private image pulls (like a private `dtrain` container).
- **GPU Resource Tracking**: While `cPlatform` explicitly tracks GPU status for nodes, the `Node` model in PlatformOps relies on a generic `facts_json` field. We need explicit API logic to parse GPU limits/availability from `facts_json` during `placement_recommendations()`.

### 6.2 Missing Playbooks (Ansible / Server-Level Execution)
- **Deployment Playbooks**: The API builds Ansible inventory and commands via `generate_inventory()` and `_ansible_base_command()`, but the actual `.yml` playbooks inside `ops/ansible/playbooks/` have not been verified. If they are missing or incomplete, the backend `execute_deployment_plan` will fail to execute anything on the real server.
- **Observability Bootstrap Playbook**: The `bootstrap_observability_plane` API needs a corresponding `install_observability.yml` playbook that genuinely installs Docker, pulls Alloy/Loki/Prometheus, and configures the `docker-compose` on the remote node.

### 6.3 Missing UI Integration
- **Observability Plane Trigger**: The React frontend (`apps/web/src/main.tsx`) lacks a button or workflow to trigger the `bootstrap_observability_plane` API when a new cluster/node is added.
- **Node Action Parity**: The React frontend is missing options present in the legacy UI's node pane:
  - **Launch Node**: Triggers initial validation and SSH ping setup.
  - **Edit Node**: Modal to change credentials or Docker configs on the fly.
  - **Node Events**: Modal to query `get_node_job_history()` directly from the Node detail card.
- **Drift & Diagnostic Reports View**: The API generates `DriftReport` and `MonitoringCheck` records, but the UI has not yet implemented the dedicated views to visualize these reports for users.

### 6.4 Untested Features (Requires Immediate Testing)
Since the `apps/api/tests/` folder is empty, the following core features are technically "untested" and cannot be guaranteed to work on a real server:
1. **Topological Deployment Logic**: Does `placement_auto_deploy` correctly order dependencies (e.g., deploying `redis` before `dtrain-worker`)?
2. **Config Snapshot Mounting**: Does `apply_config` correctly map the `config_json` from the database into the runtime `docker-compose.yml` payload generated by `generate_compose()`?
3. **Log Archives & Telemetry**: Do `service_live_logs()` and `index_log_archives()` successfully read from the deployed container's stdout/stderr streams across SSH without timing out?

