# Project Diary

Record only durable decisions, discarded approaches, and reusable lessons.

## Durable Decisions and Lessons

- **2026-08-22 — Django Direct Consolidation**: Pivoted directly to the native Django architecture rather than maintaining partial reimplementations. This achieved full functional parity across all 6 core pages (`Users`, `Clusters`, `ConfigManager`, `Performance`, `Monitoring`, `Diagnostics`) while pruning 39 dead view functions and 14 obsolete ML/dataflow models.
- **2026-08-22 — Zero Monorepo Dependency**: Inlined `CommonUtils` and removed `MCPClient` and `CutilJS` dependencies. Built a dedicated standalone Docker image (`platformops/web:1.0.0`) based on `python:3.11-slim-bookworm` with Terraform 1.8.5 and OpenSSH client.
- **2026-08-22 — Unified Image Standard (`platformops/*:1.0.0`)**: Standardized all 14 stack containers under the `platformops/*:1.0.0` namespace to prevent image drift and ensure consistent referencing across environments.
- **2026-08-22 — Operational Isolation Boundary**: PlatformOps operates strictly on `platformops_network` with non-colliding host ports (`9020`, `9090`, `9100`, `9256`, `8025`, `1025`, `8008`). All 17 cPlatform containers continue running undisturbed on their separate network.
- **2026-08-22 — Infrastructure Preservation Guardrail**: Never run automated bootstrap scripts that wipe or overwrite user-configured nodes, clusters, or services in the database. `NODE1001` and user credentials are permanent production assets.
- **2026-08-22 — Host Volume Standard**: Bound `/home/ubuntu/Backup_Platform` into `platformops_web` to serve as the unified root for node and service volumes, deployment playbooks, and configuration snapshots.
- **2026-08-22 — Resilient Config Handlers**: Implemented safe configuration reloading in `PlatformSettings.update_config()` and bounded external service config push calls with a 5-second timeout to prevent blocking or worker exit code 255.
