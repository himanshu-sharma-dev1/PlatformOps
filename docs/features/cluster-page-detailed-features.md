# Legacy cPlatform: Cluster Page Feature Inventory

> **Superseding complete reference:** for PlatformOps ↔ cPlatform full surface map, REST APIs, hardcodes, flows, parity matrix, and backlog, use  
> **[`cluster-page-complete-reference.md`](./cluster-page-complete-reference.md)**.  
> This file remains a shorter cPlatform-oriented inventory checklist.

This document provides a highly detailed list of every single user interface feature, backend API, interactive control, and system operation supported by the legacy `cPlatform` **Cluster list (`02-clusters.html`)** and **Cluster Detail (`04-cluster-detail.html`)** pages.

---

## 1. Cluster Identity & Lifecycle Management (CRUD)

The legacy cluster page represents the primary workspace for a platform engineer. It governs logical cluster definitions and repository integrations.

### 1.1 Cluster List Page (`02-clusters.html`)
- **Interactive Cluster Grid**: Displays all active clusters as cards with metadata tags:
  - Cluster Name & Status (Active/Inactive).
  - Environment Variant: Standalone, Edge, Kubernetes.
  - Resource Totals: Dynamic aggregation of overall vCPUs, Memory (GB), and Node counts.
  - Running Services: Summary count of active service instances deployed in the cluster.
- **Create Cluster Drawer**: A 4-step wizard to register a new logical cluster:
  - **Step 1: Identity & Environment**: Fields for Cluster Name, Region (e.g. `us-east-1`, `local`), Environment, and Description.
  - **Step 2: Code Repository Mapping**:
    - Select Repository Type: GitHub, GitLab, Local filesystem path.
    - Fields: Repository URL, Target Branch, Access Tokens.
    - Interactive **Test Connection** button: Executes an asynchronous git handshake check (`#test-repo-btn`) and displays a success (`connected`) or failure (`auth failed`) badge.
  - **Step 3: Container Registry Configuration**:
    - Select Image Store: Dockerhub, ECR, Google Container Registry (GCR), Local Registry.
    - Fields: Registry URL, Username, Access Key/Password.
    - Interactive **Test Connection** button: Handshakes with the container registry (`#test-img-btn`) displaying status.
  - **Step 4: Summary & Bootstrap**: Confirms credentials before scheduling initial database entries.
- **Delete Cluster**: Instantly removes a cluster database record.
  - *Safeguard*: Checks if nodes are mapped to the cluster. If nodes are present, blocks deletion and throws a `CLUSTER_HAS_NODES` warning, requiring node teardown first.

### 1.2 Cluster Detail Page (`04-cluster-detail.html`)
- **Cluster Settings Drawer (`#editClusterDrawer`)**: Exposes options to modify existing repository branch mappings or update container registry credentials.
  - **Secrets Masking / Replacement**: Securely masks stored passwords or keys. Exposes a **Replace** button (`.replace-secret-btn`) which hides the masked label and displays an empty focused password input field for clean overwrite protection.

---

## 2. Node & Bare-Metal Server Management

Nodes represent the physical/virtual VM compute instances belonging to a cluster.

### 2.1 Node Specification Sheet
- Displays hardware specs per node:
  - **vCPU** count (e.g., 4 Core).
  - **Memory** (e.g., 16 GB).
  - **Storage** size (e.g., 500 GB SSD).
  - **Node IP Address** and SSH connection username.
  - **GPU Exporter Status**: Flag indicating if GPU resources are present/enabled.

### 2.2 Node Provisioning and Lifecycle
- **Add Node Drawer (`#newNodeDrawer`)**:
  - Allows manual node onboarding by specifying IP, username, port, and authentication type (Password auth or PEM private key file upload).
- **Dynamic Cloud VM Launch (`node_launch_request` / `#launchNodeBtn`)**:
  - Triggers dynamic virtual machine deployment on AWS/GCP using Terraform.
  - Prompts for VM parameters: Amazon Machine Image (AMI) / GCP Image, Instance Type (e.g., `t3.medium`), Key pair name, Storage size, and Region.
  - Asynchronously registers a cron task (`cutil_timer_crontab_start`) to invoke the Terraform script `TerraformMgmt.initiate_provision_instance` in the background, updating the Node's status step-by-step.
- **Delete/Teardown Node (`node_delete_request` / `#deleteNodeBtn`)**:
  - Deletes the database registration.
  - If the node was launched via cloud providers, initiates a background Terraform destroy command (`destroy_instance`) to decommission the AWS/GCP VM.
- **Node Events Timeline (`#nodeEventsBtn` / `node_event` API)**:
  - Asynchronously pulls and renders a historical timeline of infrastructure actions for the node: e.g. "Terraform provision initiated", "SSH key generated", "Ping validation successful".

---

## 3. Infrastructure Auto-Discovery ("Adopt" Mode)

The **Discover** action (`#discoverInfraBtn` / `discover_infrastructure` API) represents a major server-level integration feature.

- **Process Flow**:
  1. Hitting "Discover" executes an Ansible playbook (`service_infra_discovery_playbook.yml`) and Python script (`service_infra_discovery.py`) against the remote node via SSH.
  2. The script runs `docker ps` to find all active container runtimes.
  3. Returns a JSON payload containing container details: Image Name, Ports, Mount Volumes, Status, and Labels.
  4. The orchestrator compares these containers against the local `INFRASTRUCTURE_SERVICE_CATALOG` and `dFormService.json` schemas.
  5. Computes a similarity score. If it matches, the platform **"adopts"** the running container:
     - Automatically creates a `Service` instance in the database.
     - Sets `adopted=True`.
     - Maps exposed ports, data volume locations, and imports environment config profiles.
     - Bypasses deployment steps, marking it as instantly running in the system UI.

---

## 4. Service Instance Management & Orchestration

Governs applications, databases, and logging collectors scheduled on the cluster's nodes.

### 4.1 Service Catalog Integration
- **Service Catalog Drawer (`#catalogBtn`)**: Displays available services categorized as:
  - **Infrastructure Services**: Loki, Alloy, Prometheus, RabbitMQ, PostgreSQL, node_exporter.
  - **User Application Services**: Mapped dynamically from `dFormService.json` (such as the `dtrain` container, training controllers, or inference pipelines).
- **Exposed Port Collision Checker (`check_port_and_name_availibility`)**:
  - Dynamically queries active service ports and container names on the targeted Node to prevent port collision before registering a service.
- **Dynamic Config Schema Form Generation**:
  - When selecting a service, the drawer dynamically renders a configuration form using schemas (`dFormServiceConfig.json` / `dFormService.json`). Custom fields (like Max Connections, Shared Buffers, DB Usernames, API Ports) are generated on the fly.

### 4.2 Deployment & Live Controls
- **Deploy Service (`deploy_service` / `#deployServiceBtn`)**:
  - Launches a background Ansible execution (`service_deploy_playbook.yml`).
  - Sets up remote directories, copies templates, pulls docker images, binds container ports to host ports, sets up volumes, and starts the container.
- **Live Status Polling (`service_live_status`)**:
  - Periodically executes remote `docker inspect` queries via Ansible to fetch real-time container parameters (running state, uptime, restarts) and updates the status dots (green/yellow/red).
- **Uninstall Service (`delete_service`)**:
  - SSHs into the node, stops the container, deletes Docker volumes, and cleans up host configurations.
- **Service Events log (`service_event` API)**:
  - Logs specific events: e.g. "Deploy initiated", "Container restarted", "Configuration applied".
- **Diagnostics**:
  - Quick link to run diagnostics checks (`service_diagnostics`).
