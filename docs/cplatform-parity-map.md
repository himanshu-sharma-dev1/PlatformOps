# cPlatform Capability Parity Map

PlatformOps is engineered to demonstrate the architectural design and operations of a production DevOps/SRE control plane (inspired by cPlatform) while remaining portfolio-safe. It does not copy private product logic.

## 1. Feature Map Parity

| Capability | cPlatform Design Pattern | PlatformOps Implementation |
| :--- | :--- | :--- |
| **Catalog Cards** | 39 distinct application, infrastructure, and helper cards. | Modeled in catalog YAML contracts under `catalog/services/`. |
| **Infrastructure Cards** | Backing data stores, vector libraries, and exporters are first-class cards. | Explicit deployable entities with log targets and backup strategies. |
| **Lifecycle Safety** | Safety gates for database, node, and cluster terminations. | GET `/api/.../lifecycle-impact` assessments blocking raw deletion. |
| **Subsystem Rollouts** | Rollout sequencing for whole planes. | Topological sort generated step plans with blocker indicators. |
| **Isolated Backings** | Subsystem isolation (e.g. Airflow maps isolated backings). | Airflow rollout plans enforce `airflow-postgres`/`airflow-redis` separation. |
| **DTrain Control Plane** | Multi-node distributed training controller. | DTrain dashboard fetching tracker, controller, worker, and GPU metrics. |
| **Capability Parity** | Logs, diagnostics, and config management profiles. | Exposes capability metadata detailing log targets and config strategy. |
| **Local Simulation Mode** | Simulates playbooks and writes inventory/compose artifacts. | Ansible command tracking and simulation, with real SSH EC2 fallback. |

## 2. Parity Details & Safety

- **Private Logic Boundary**: No proprietary code from the `cPlatform` repository is used or referenced. File paths, schemas, and API bindings are written from scratch.
- **Service Isolation**: Application deletion does not clean up shared backing infrastructure dependencies, matching the behavior of standard Kubernetes/Docker control planes.
- **Airflow Isolation**: Airflow rollout plans strictly keep workflow-plane backing databases separate from global databases to prevent workflow logs and tables from corrupting production databases.
