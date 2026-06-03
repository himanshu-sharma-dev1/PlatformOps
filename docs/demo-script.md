# Interview Demo Script

This script guides you through demonstrating PlatformOps' control plane capabilities in an interview or portfolio review.

## 1. Startup Commands

```bash
# Terminal 1: Backend API
source /Users/himanshusharma/venv/bin/activate
make check
make api

# Terminal 2: React Dashboard
cd apps/web
npm run dev
```

Open your browser to `http://localhost:5173`.

## 2. Walkthrough Flow

### Step 1: Cluster & Node Exploration
- Point out the **Cluster Explorer** and **Node Map** at the top.
- Select `local-lab` cluster: Note the counts (Nodes, Service Cards, Healthy/Warning/Error counts).
- Select `local-mac` node: Explain that network, volume root, validation status, and service kind counts are loaded dynamically.
- Click **Validate Node**: Explain that the control plane records a configuration audit job and tracks validation logs.
- Show the breadcrumb path at the top (`local-lab → local-mac`).

### Step 2: Service Catalog & Dependency Preflight
- Explain the 39-card catalog split into infrastructure, application, and helper kinds.
- Try deploying the `rag` application card. Explain that it is blocked because dependencies like `postgres-core`, `redis-core`, `rabbitmq-core`, `milvus-core`, `etcd-core`, and `minio-core` are missing or stopped.
- Show the **Deployment Plan** panel for `rag` showing its ordered preflight.

### Step 3: Subsystem Orchestration & Isolation
- Navigate to the **Subsystems Orchestration** panel.
- Select `workflow-plane` (Airflow): Click **Generate Plan**. Note that the plan pulls in `airflow-postgres` and `airflow-redis` instead of the global `postgres-core`/`redis-core` database cards to ensure database isolation.
- Select `vector-plane`: Note the topological ordering where `etcd` and `MinIO` are scheduled before `Milvus`.
- Click **Deploy Subsystem** to trigger ordered sequential deployment jobs.

### Step 4: DTrain Control Plane Showcase
- Scroll to the **DTrain Control Plane** dashboard.
- Show the status cards for `dtrain-tracker`, `dtrain-controller`, and `dtrain-workers`.
- Note the dependency state (RabbitMQ & Redis readiness check).
- Explain the **Deterministic Simulation Metrics**: active/queued/completed training jobs, and the GPU availability accelerator pool indicator (`4/4 A100 GPUs Active`).

### Step 5: Lifecycle safety & Delete Modals
- Go to the Installed Cards list.
- Click the red **Delete** button next to `postgres-core`.
- Explain that the **Safety Review** modal intercepts the deletion: it displays that deletion is blocked because applications (like `rag`) depend on it, and it's protected core infrastructure.
- Check **Enable Force Delete** to show how SREs can override blocks when required, and highlight that force deletion will log a warning event to the timeline feed.
- Delete an application card (like `rag`) and show that shared backing databases (like `postgres-core`) remain active.

### Step 6: Config & Backup Governance
- Select a card and load its Config. Note the config strategy ("Live config file" or "Catalog-generated config").
- Validate config YAML and capture a snapshot. Show that we can detect drift and restore snapshots.
- Click **Backup**: Note the backup strategy warning popover ("database dumps", "volume archives", etc.) displayed before executing.
