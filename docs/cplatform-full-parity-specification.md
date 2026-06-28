# Architectural Parity Specification: cPlatform to PlatformOps

This document outlines the architectural patterns, feature parity mappings, and implementation state for the 5 key management pages of the DevOps/SRE control plane: **Cluster Config**, **Config Manager**, **GlitchTip/Monitoring**, **System Monitoring**, and **Diagnostics**.

---

## 1. Cluster Config & Node Management

### 🏗️ System Architecture
* **cPlatform**: Implemented in Django templates (`02-clusters.html`, `04-cluster-detail.html`) and `clusterDetail.js`. Uses a dual-pane layout: a left-side node navigator and service topology stack, and a right-side sliding catalog drawer.
* **PlatformOps**: Deployed as a unified backend service (`apps/api`) and a React SPA (`apps/web`). Utilizes direct CRUD endpoints and lifecycle dependency checking.

### 📋 Feature Parity List
1. **Cluster Management (CRUD)**
   - **Add/Edit/Delete Cluster**: Fully wired in the backend (`/api/clusters`). cPlatform checks if a cluster contains registered nodes and blocks deletion with `CLUSTER_HAS_NODES`; PlatformOps replicates this validation in `lifecycle_impact()`.
2. **Node Onboarding & Provisioning**
   - **Add Node**: Prompts for hostname/IP, SSH credentials, and base storage root. cPlatform immediately fires `service_discover_infrastructure_request` to adopt existing containers.
   - **Launch/Validate Node**: Executes validation playbooks (`validate_node.yml`) on the host to check docker readiness and configuration paths.
   - **Delete/Exit Node**: Denied if active services are mapped. Rebuilt in PlatformOps via node lifecycle checks.
3. **Drag-and-Drop Service Mapping Workflow**
   - **Service Catalog**: Sidebar displaying 39 predefined services grouped by layer (App, Infrastructure, Helper).
   - **Drag-to-Assign Workspace**: Users drag a catalog chip onto a node stack. This opens the "Add Service" drawer pre-filled with the service's volume mounts, exposed ports, dependencies, and container defaults.
   - **Service Deployment (`deploy_service`)**: Executes Ansible tasks (`docker_service.yml`) to construct, configure, and boot docker containers on the target node.

### 🔍 Current Wiring State
* **Wired**: Backend Cluster/Node CRUD, SSH connection test checks, lifecycle deletion safety assessments, and service placement recommendations.
* **Mock/Missing**: Drag-and-drop catalog mapping UI (current UI uses a simple creation drawer), and remote container adoption scripts.

---

## 2. Config Manager

### 🏗️ System Architecture
* **cPlatform**: Rendered in `08-config-manager.html` with inline JS. Manages service configurations as XML/YAML records. Supports variable inheritance and checkpoint differences.
* **PlatformOps**: Implements snapshots (`config_snapshots`) and drift reports directly in the SQLite schema using SQLAlchemy relationships.

### 📋 Feature Parity List
1. **Checkpoints & Snapshots**
   - **Create Snapshot**: Saves a named, versioned YAML configuration state to the database.
   - **Rollback/Restore Checkpoint**: Re-applies a snapshot state. Supported in rolling (graceful container restart) or recreate modes.
   - **Drift Detection**: Runs side-by-side diff comparing the live container's configurations with database states.
2. **YAML Validation & Editing**
   - **Monaco/YAML Editor**: Features real-time schema validation and linting.
3. **Configuration Variables Migration Workspace**
   - **Prepare Migration**: Maps variable differences between two configuration versions, detecting added, modified, or deleted keys.
   - **Migration Merge Engine**: Automatically generates a ranked merger sequence, combining values and outputting the merged production-ready YAML.

### 🔍 Current Wiring State
* **Wired**: Snapshots CRUD, checkpoint rollbacks, basic diff reports, drift detection, and prepare/execute migration API endpoints.
* **Mock/Missing**: Variable migration merging UI in React (the backend endpoint is functional, but the frontend lacks the visual variables mapping workspace).

---

## 3. GlitchTip Integration & Monitoring

### 🏗️ System Architecture
* **cPlatform**: Built in `Monitoring.html` and `ServiceMonitoring.js`. Acts as a secure proxy to a white-labeled GlitchTip ("YantrAI") instance running on port `9008`.
* **PlatformOps**: Currently lacks GlitchTip integrations. Employs Loki, Alloy, and Prometheus for logging and metrics tracking.

### 📋 Feature Parity List
1. **Error Tracking & Issue Workspace**
   - **Active Issue List**: Fetches project exception logs (title, seen counts, status, severity, permalink).
   - **Resolve/Ignore Actions**: Alters issue states directly from the control plane UI.
   - **Traceback Inspector**: Fetches the latest event details from GlitchTip. Renders UUID, tags, system metadata, traceback frames (including local variables per frame and context code lines), and breadcrumbs logs (SQL queries, Redis keys, HTTP requests).
2. **Uptime Monitors**
   - **Uptime Dashboard**: Renders TCP/HTTP monitor statuses (Online, Offline).
   - **Incidents Transition Log**: Lists state changes (transitions with downtime reason).
   - **Response Time SVG Chart**: Renders a custom response time bar chart showing latency distributions with hover tooltips and P95 clamping.
   - **Monitor CRUD**: Creation form (URL, monitor type, interval, expected HTTP code, and expected body).
3. **Sentry Runtime Patching (`patch_observability`)**
   - **Dynamic Injection**: Executes Ansible scripts to run `pip install sentry-sdk` inside active containers.
   - **Bootstrap Ingest**: Injects `sitecustomize.py` to auto-initialize the Sentry client, tagging errors with `node_ip`, `service_id`, and `container_name`.

### 🔍 Current Wiring State
* **Wired**: None.
* **Mock/Missing**: GlitchTip database containers, token seeding script, GlitchTip API proxies, uptime monitor configurations, traceback inspector panel, and `service_runtime_patch` playbooks.

---

## 4. System Monitoring & Exporter Telemetry

### 🏗️ System Architecture
* **cPlatform**: Configured via Prometheus metrics servers scraping `node_exporter` (9100) and `process_exporter` (9256) across the fleet.
* **PlatformOps**: Bundled in `platformops-obs-prometheus` container. Uses hardcoded queries fetching telemetry from the local host.

### 📋 Feature Parity List
1. **Target Tree Navigation**
   - Collapsible cluster-to-node tree structure, displaying live hardware metrics (CPU, RAM, Disk) for the selected node.
2. **Interactive Resource Dials**
   - Renders CPU core loads, memory allocation, and disk volume capacity.
3. **Top Processes & Filesystems**
   - **Named Process Group Table**: Renders CPU consumption grouped by process name.
   - **Mounted Volumes Table**: Logs disk read/write rates and space utilization for active mount points.
4. **Historical Telemetry Charts**
   - Inline SVG charts displaying historical resource trends (1h, 6h, 24h, 7d, 1M, 3M) with custom tooltips.

### 🔍 Current Wiring State
* **Wired**: React circular dials, process tables (CPU only), local Prometheus container, and Prometheus node/process routers.
* **Mock/Missing**: Sibling nodes metric collection (requires scraping labels like `instance="<node_ip>:9100"`), multi-node Prometheus target injection playbooks, filesystem volumes table, and SVG resource trend charts.

---

## 5. Diagnostics & Logs Workspace

### 🏗️ System Architecture
* **cPlatform**: Built in `09-diagnostics.html`. Consolidates real-time Loki streams, log backfilling, lifecycle audit events, and Groq AI chatbots.
* **PlatformOps**: Leverages FastAPI endpoints (`/api/diagnostics/logs`, `/api/services/{id}/diagnostics`) connected to internal Lokis and Groq LLMs.

### 📋 Feature Parity List
1. **Target Selector Toolbar**
   - Switch between dependency container logs (PostgreSQL, RabbitMQ, ClickHouse, optionCopilot) at the top of the pane.
2. **Diagnostics Summary Panel**
   - **Root Cause Card**: AI-generated root cause diagnostic summary.
   - **Evidence Log**: Displays warning/error messages matching the anomaly time window.
   - **Active Issue Groups**: Grouped logs indicating diagnostic confidence levels.
3. **Live Logs & Historical Console**
   - **Real-Time Loki Stream**: Live container logs stream.
   - **Historical Console Search**: Search and filter by level (error, warning, info, debug) and timestamp.
4. **Log Backfill & Archive Manager**
   - **Backfill Logs**: Triggers a Python backfiller that parses file log lines and streams them to Loki with matching timestamps.
   - **Log Archives**: Generates, lists, and downloads compressed logs bundles (`.tar.gz`).
5. **AI Diagnostics Chatbot**
   - Integrates Groq Llama models for interactively answering operations questions about the service's status and logs.

### 🔍 Current Wiring State
* **Wired**: Targets selector toolbar, Summary tab, Loki container live tailing, and local LLM AI diagnostics router.
* **Mock/Missing**: Log backfill execution triggers, log archives catalog, and the interactive logs-based AI chatbot panel.
