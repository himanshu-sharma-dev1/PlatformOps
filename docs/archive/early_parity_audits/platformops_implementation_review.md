# PlatformOps Implementation Review & Parity Audit Report

This report evaluates the distilled FastAPI + React SPA PlatformOps architecture against the legacy Django cPlatform enterprise monolith. It catalogues implemented API endpoints and React views, identifies architectural gaps, highlights stubbed/incomplete logic, and provides a comparative feature summary.

---

## 1. Executive Summary

PlatformOps represents a strategic refactoring of the legacy `cPlatform` enterprise operations center. It replaces a heavy, multi-module Django monolith with a lightweight control plane:
- **Backend**: A distilled **FastAPI** service (`apps/api/`) designed for low-latency operational control, utilizing SQLAlchemy 2.0 and SQLite for local state management, while delegating heavy task execution to background Ansible and Terraform playbooks.
- **Frontend**: A cohesive **React SPA** (`apps/web/`) styled with a clean glass-morphism dark-mode UI, replacing server-side rendered Jinja2 Django templates. State and navigation are managed via a centralized React Context Provider (`PlatformProvider.tsx`).

The goal of PlatformOps is to achieve **absolute feature parity** with the telemetry, lifecycle management, configuration tracking, and SRE operations of the legacy `cPlatform` environment. While the overall translation is highly functional, a number of specific stubs, simulations, routing bugs, and minor UX omissions remain. This audit serves as a roadmap to resolve these final integration gaps.

---

## 2. Backend API Endpoint Catalog

Below is the exhaustive catalog of all FastAPI endpoints implemented in PlatformOps, grouped by router source file under `/home/ubuntu/PlatformOps/apps/api/platformops/`.

### `main.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 64 | `GET` | `/api/health` | `health` | Returns basic API status check dictionary. |
| 73 | `GET` | `/{full_path:path}` | `serve_frontend` | Serves frontend static files (`index.html`) from `/app/dist` for non-API routes. |

### `routers/auth_users.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 26 | `GET` | `/api/llm/status` | `api_llm_status` | Invokes `llm_status()` to check AI copilot readiness. |
| 31 | `POST` | `/api/auth/login` | `api_login` | Validates user password against database records. |
| 39 | `POST` | `/api/auth/logout` | `api_logout` | Destroys current token session details in DB. |
| 47 | `GET` | `/api/auth/me` | `api_me` | Retrieves active user account profile. |
| 52 | `POST` | `/api/auth/last-visited` | `api_last_visited` | Updates user's UI telemetry last-visited timestamp. |
| 61 | `GET` | `/api/auth/invite/{token}` | `api_invite_preview` | Previews details of a pending registration invite token. |
| 66 | `POST` | `/api/auth/invite/{token}/accept` | `api_invite_accept` | Accepts token, registers user profile and sets password. |
| 74 | `GET` | `/api/users` | `api_list_users` | Admin route. Returns all active/pending users. |
| 79 | `POST` | `/api/users` | `api_create_user` | Admin route. Direct user registration in database. |
| 98 | `PUT` | `/api/users/{user_id}` | `api_update_user` | Admin route. Modifies user details, role, or status. |
| 119 | `DELETE` | `/api/users/{user_id}` | `api_delete_user` | Admin route. Deletes a user profile from DB. |
| 127 | `POST` | `/api/users/invite` | `api_invite_user` | Admin route. Generates user invite token and records it. |
| 147 | `POST` | `/api/users/invite/resend` | `api_resend_invites` | Admin route. Resends pending invitation tokens. |
| 156 | `POST` | `/api/users/invite/revoke` | `api_revoke_invite` | Admin route. Revokes a pending invitation token. |

### `routers/catalog_topology.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/catalog/services` | `list_catalog` | Returns all available templates from service catalog YAML. |
| 16 | `GET` | `/api/catalog/services/{service_key}/install-schema` | `get_service_install_schema` | Returns JSON configurations required to provision a service on a node. |
| 28 | `GET` | `/api/topology` | `get_topology` | Builds global view of clusters, nodes, and deployed services. |
| 33 | `GET` | `/api/events` | `get_events` | Queries operational events, filtering by category, severity, node/service ID. |
| 54 | `GET` | `/api/capabilities/coverage` | `capabilities_coverage` | Computes capability matrix (backup, rollback, configs) coverage rates. |
| 59 | `GET` | `/api/dtrain/overview` | `get_dtrain_overview_endpoint` | Summarizes distributed ML training tasks and resource uses. |

### `routers/clusters.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `POST` | `/api/clusters` | `create_cluster` | Creates a new logical cluster card. |
| 42 | `GET` | `/api/clusters` | `list_clusters` | Lists all clusters with repository and registry info. |
| 48 | `PUT` | `/api/clusters/{cluster_id}` | `update_cluster` | Updates cluster settings, masking secrets. |
| 77 | `DELETE` | `/api/clusters/{cluster_id}` | `delete_cluster` | Deletes cluster. Blocks if active nodes are present unless forced with approval ID. |
| 162 | `GET` | `/api/clusters/{cluster_id}/lifecycle-impact` | `get_cluster_lifecycle_impact_endpoint` | Evaluates what nodes and services will be deleted if cluster is removed. |
| 170 | `GET` | `/api/clusters/{cluster_id}/summary` | `get_cluster_summary_endpoint` | Returns high-level metrics (online nodes, CPU/RAM utilization) for cluster. |
| 178 | `GET` | `/api/clusters/{cluster_id}/operations` | `get_cluster_operations_endpoint` | Lists historical audit logs for operations in this cluster. |
| 186 | `POST` | `/api/clusters/test-repo` | `test_cluster_repo_connection_endpoint` | Handshakes with Git repository server to test authentication. |
| 199 | `POST` | `/api/clusters/test-registry` | `test_cluster_registry_connection_endpoint` | Tests login credentials against remote container registry. |

### `routers/diagnostics.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/diagnostics/ingestion-stats` | `diagnostics_ingestion_stats` | Returns Loki log query rate, current hour errors, and archive size. |
| 16 | `GET` | `/api/diagnostics/logs` | `get_diagnostics_logs` | Queries Loki range log records for a given service container name. |

### `routers/glitchtip.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `POST` | `/PlatformIO/Monitoring/Health/` | `monitoring_health` | Combines container running status with exception queries from GlitchTip. |
| 51 | `POST` | `/PlatformIO/Monitoring/Issues/` | `monitoring_issues` | Fetches active exception issues list (crashes, warning levels) from GlitchTip. |
| 68 | `POST` | `/PlatformIO/Monitoring/Issues/EventDetails/` | `monitoring_issue_event_details` | Obtains specific stacktrace, lines of code, and headers for an exception. |
| 80 | `POST` | `/PlatformIO/Monitoring/IssueAction/` | `monitoring_issue_action` | Resolves, ignores, or deletes exception issues in GlitchTip. |
| 90 | `POST` | `/PlatformIO/Monitoring/Performance/` | `monitoring_performance` | Returns average latency, throughput, and error rates of transactions (APM). |
| 107 | `POST` | `/PlatformIO/Monitoring/Keys/` | `monitoring_keys` | Lists integration DSN keys required by the SDK for connection. |
| 120 | `POST` | `/PlatformIO/Monitoring/Uptime/` | `monitoring_uptime_list_endpoint` | Returns ping monitors configured for testing availability. |
| 133 | `POST` | `/PlatformIO/Monitoring/Uptime/Add/` | `monitoring_uptime_add` | Adds a new synthetic endpoint ping check. |
| 154 | `POST` | `/PlatformIO/Monitoring/Uptime/Delete/` | `monitoring_uptime_delete` | Removes a synthetic endpoint monitor checklist. |
| 163, 164 | `POST`, `GET` | `/PlatformIO/Monitoring/IntegrationStatus/` | `monitoring_integration_status` | Checks Sentry-compatible endpoint connection state. |
| 170 | `POST` | `/PlatformIO/Monitoring/PatchObservability/` | `monitoring_patch_observability` | Triggers playbook to deploy Promtail and re-target Loki metrics. |

### `routers/misc.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 15 | `GET` | `/api/services/{service_id}/diagnostics/archives/{archive_id}/view` | `diagnostics_archive_view` | Reads first 300 lines of a compressed log archive to show in a UI modal. |

### `routers/monitoring.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/metrics/node` | `get_node_metrics` | Queries Prometheus for global CPU, memory, and root filesystem disk utilization. |
| 35 | `GET` | `/api/metrics/processes` | `get_process_metrics` | Queries Prometheus for top 10 CPU-consuming named processes globally. |
| 52 | `GET` | `/api/dashboard/summary` | `dashboard_summary` | Renders total stats of clusters, nodes, services, and online nodes. |
| 57 | `POST` | `/api/monitoring/sweep` | `monitoring_sweep` | Triggers database update loop of all telemetry checks. |
| 62 | `GET` | `/api/monitoring/checks` | `monitoring_checks` | Lists latest database records of uptime/service status checks. |

### `routers/nodes.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/nodes/{node_id}/deployment-plan/{service_key}` | `get_deployment_plan` | Previews configuration/playbook layout before deployment. |
| 19 | `POST` | `/api/nodes/{node_id}/observability/bootstrap` | `bootstrap_observability` | Installs Alloy, Promtail, and node_exporter on target node. |
| 27 | `GET` | `/api/nodes/{node_id}/artifacts/inventory` | `node_inventory` | Returns auto-generated Ansible INI file layout for the node host. |
| 33 | `GET` | `/api/nodes/{node_id}/artifacts/compose` | `node_compose` | Renders auto-generated compose configurations for the node's services. |
| 43 | `POST` | `/api/nodes/{node_id}/capacity` | `node_capacity` | Schedules a capacity report generation job. |
| 48 | `GET` | `/api/nodes` | `list_nodes` | Lists registered host nodes, optionally filtered by cluster ID. |
| 73 | `POST` | `/api/nodes` | `create_node` | Adds a node compute host to DB and saves SSH key. |
| 92 | `PUT` | `/api/nodes/{node_id}` | `update_node` | Modifies node IP, port, docker networks, and SSH credentials. |
| 121 | `POST` | `/api/nodes/{node_id}/validate` | `validate_node_endpoint` | Triggers background Ansible job to test SSH connectivity. |
| 126 | `DELETE` | `/api/nodes/{node_id}` | `delete_node` | Deletes node. Blocks if services are deployed unless forced with approval. |
| 207 | `GET` | `/api/nodes/{node_id}/lifecycle-impact` | `get_node_lifecycle_impact_endpoint` | Evaluates services that will be uninstalled if the node is deleted. |
| 215 | `GET` | `/api/nodes/{node_id}/subsystems/{subsystem}/rollout-plan` | `get_subsystem_rollout_plan_endpoint` | Sorts services topologically to create a rollout sequence. |
| 223 | `POST` | `/api/nodes/{node_id}/subsystems/{subsystem}/deploy` | `deploy_subsystem_endpoint` | Triggers sequential rollout playbook execution for a subsystem. |
| 231 | `GET` | `/api/nodes/{node_id}/summary` | `get_node_summary_endpoint` | Summarizes services counts, docker network config, and disk root. |
| 239 | `GET` | `/api/nodes/{node_id}/metrics` | `get_node_metrics_endpoint` | Queries Prometheus range and instant metrics (CPU/RAM/Net) for node. |
| 247 | `GET` | `/api/nodes/{node_id}/connection` | `get_node_connection_endpoint` | Renders SSH validation check results. |
| 255 | `GET` | `/api/nodes/{node_id}/jobs` | `get_node_jobs_endpoint` | Lists historical deployment jobs executed on the host node. |
| 263 | `GET` | `/api/nodes/{node_id}/onboarding-readiness` | `get_node_onboarding_endpoint` | Triggers facts checks to verify docker daemon. |
| 271 | `POST` | `/api/nodes/{node_id}/onboarding-remediate` | `remediate_node_onboarding_endpoint` | Triggers Ansible remediation playbook (Docker installation, folder setups). |
| 283 | `POST` | `/api/nodes/{node_id}/launch-vm` | `launch_node_vm_endpoint` | Uses AWS/GCP Terraform playbooks in background to spin up virtual machine hosts. |
| 296 | `POST` | `/api/nodes/{node_id}/teardown-vm` | `teardown_node_vm_endpoint` | Uses Terraform destroy in background to decommission cloud instances. |
| 307 | `POST` | `/api/nodes/{node_id}/discover` | `discover_infrastructure_endpoint` | SSH check that executes `docker ps` to search and adopt running services. |
| 318 | `GET` | `/api/nodes/{node_id}/check-port-and-name` | `check_port_and_name_endpoint` | Checks node for name or port availability to avoid container collisions. |

### `routers/observability.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/observability/pipeline` | `observability_pipeline` | Returns Loki and Prometheus pipeline status reports. |
| 19 | `POST` | `/api/observability/deploy` | `deploy_observability` | Runs local playbook to deploy compose observability stack. |
| 30 | `POST` | `/api/observability/teardown` | `teardown_observability` | Tears down local compose observability stack. |
| 41 | `GET` | `/api/observability/status` | `get_observability_status` | Uses local docker compose checks to inspect running containers. |
| 71 | `POST` | `/api/observability/deploy` | `deploy_observability_endpoint` | **COLLISION OVERRIDE**: Deploys observability agents on a remote node ID. |

### `routers/services.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/services/placement/recommendations/{service_key}` | `get_placement_recommendations` | Calculates ideal node layout using CPU constraints and anti-affinity rules. |
| 38 | `POST` | `/api/services/placement/deploy/{service_key}` | `deploy_from_placement` | Auto-deploys a service to recommended node. |
| 69 | `GET` | `/api/services` | `list_services` | Lists registered service instances, optionally filtered by node ID. |
| 78 | `POST` | `/api/services` | `create_service` | Adds a service registration (checking naming/port availability first). |
| 92 | `PATCH` | `/api/services/{service_id}` | `update_service` | Updates service description and overrides config settings in DB. |
| 106 | `POST` | `/api/services/{service_id}/preflight` | `preflight` | Evaluates if upstream dependencies are installed and running. |
| 111 | `POST` | `/api/services/{service_id}/dependencies/install-missing` | `install_service_dependencies` | Sequentially installs missing upstream services. |
| 116 | `POST` | `/api/services/{service_id}/deploy` | `deploy` | Runs background Ansible deployment playbook for service. |
| 121 | `POST` | `/api/services/{service_id}/deployment/execute` | `execute_service_deployment` | Integrates preflight, dependency installations, and deployment commands. |
| 134 | `POST` | `/api/services/{service_id}/delete` | `delete` | Blocks deletion if critical dependent services exist, unless approved. |
| 220 | `POST` | `/api/services/{service_id}/backup` | `backup_service` | Generates a tarball backup of service volumes. |
| 225 | `GET` | `/api/services/{service_id}/releases` | `service_releases` | Lists historical deployment release versions. |
| 230 | `GET` | `/api/services/{service_id}/releases/safety` | `service_release_safety` | Runs semantic upgrade risk checks. |
| 237 | `GET` | `/api/services/{service_id}/releases/timeline` | `service_release_timeline` | Compiles chronological release charts. |
| 246 | `POST` | `/api/release-approvals` | `create_release_approval_endpoint` | Submits approval requests for new version rollouts. |
| 258 | `GET` | `/api/release-approvals` | `list_release_approvals` | Lists pending/completed release approvals. |
| 265 | `POST` | `/api/release-approvals/{approval_id}/decision` | `decide_release_approval_endpoint` | Registers approver decision (approve/deny). |
| 278 | `POST` | `/api/release-approvals/{approval_id}/revoke` | `revoke_release_approval_endpoint` | Revokes an approval. |
| 285 | `POST` | `/api/services/{service_id}/releases` | `release_service` | Deploys new release version (requires approved release tokens). |
| 301 | `POST` | `/api/releases/{release_id}/rollback` | `rollback_service_release` | Reverts container to the prior version state. |
| 309 | `GET` | `/api/jobs/{job_id}` | `get_job` | Returns execution status of background Ansible/Terraform tasks. |
| 317 | `GET` | `/api/jobs/{job_id}/logs` | `get_job_logs` | Prints raw stdout/stderr output lines for a job. |
| 325 | `GET` | `/api/services/{service_id}/diagnostics` | `diagnostics` | Heuristic evaluation (CPU, restarts, Lokirate) for service. |
| 351 | `GET` | `/api/services/{service_id}/diagnostics/analysis` | `diagnostics_analysis` | Summarizes service issues and matches them with recommended runbooks. |
| 377 | `GET` | `/api/services/{service_id}/diagnostics/targets` | `diagnostics_targets` | Lists related containers/sidecars in the diagnostics path. |
| 382 | `GET` | `/api/services/{service_id}/diagnostics/live` | `diagnostics_live` | Renders DB `OperationalEvent` lists (caching last positions). |
| 415 | `GET` | `/api/services/{service_id}/diagnostics/archives` | `diagnostics_archives` | Indexes available log backups/files in the service directory. |
| 420 | `GET` | `/api/services/{service_id}/diagnostics/archives/{archive_id}/download` | `diagnostics_archive_download` | Streams a single archived log file download. |
| 447 | `POST` | `/api/services/{service_id}/diagnostics/archives/bulk-download` | `diagnostics_archives_bulk_download` | Zips and streams download of multiple log archives. |
| 484 | `GET` | `/api/services/{service_id}/diagnostics/file-tail` | `diagnostics_file_tail` | Remote SSH `tail` of custom application log paths. |
| 494 | `GET` | `/api/services/{service_id}/diagnostics/file-history` | `diagnostics_file_history` | Queries Loki log histories under file path selectors. |
| 513 | `GET` | `/api/services/{service_id}/diagnostics/container-history` | `diagnostics_container_history` | Queries Loki logs for specific docker container selectors. |
| 542 | `POST` | `/api/services/{service_id}/diagnostics/chat` | `diagnostics_chat` | Feeds logs context to LLM copilot for debugging chat. |
| 570 | `POST` | `/api/services/{service_id}/diagnostics/backfill` | `diagnostics_backfill` | Instructs Promtail to index log directories into Loki. |
| 575 | `GET` | `/api/services/{service_id}/config` | `config_workspace_endpoint` | Builds workspace config schemas and content. |
| 584 | `GET` | `/api/services/{service_id}/config/timeline` | `config_timeline` | Lists configuration change histories. |
| 610 | `GET` | `/api/services/{service_id}/config/snapshots` | `list_config_snapshots_endpoint` | Lists configuration snapshots/backups. |
| 630 | `POST` | `/api/services/{service_id}/config/drift` | `config_drift` | Triggers a file comparison with DB to report config differences. |
| 635 | `POST` | `/api/services/{service_id}/config/snapshots` | `snapshot_config` | Saves editor config text as a named snapshot. |
| 650 | `GET` | `/api/services/{service_id}/config/snapshots/{snapshot_id}` | `get_snapshot_detail` | Returns raw YAML text for a snapshot. |
| 659 | `GET` | `/api/services/{service_id}/config/compare` | `compare_snapshots` | Compares line-by-line diff values for two snapshots. |
| 677 | `POST` | `/api/services/{service_id}/config/snapshots/{snapshot_id}/rename` | `rename_snapshot` | Renames a snapshot label. |
| 694 | `POST` | `/api/services/{service_id}/config/snapshots/{snapshot_id}/restore` | `restore_snapshot` | Rolls back remote VM file to snapshot contents. |
| 704 | `POST` | `/api/services/{service_id}/config/validate` | `validate_config_endpoint` | Parses YAML schema config text to ensure syntax validity. |
| 711 | `POST` | `/api/services/{service_id}/config/apply` | `apply_config_endpoint` | Triggers background deployment apply (soft reload or hard restart). |
| 716 | `POST` | `/api/services/{service_id}/config/direct-apply` | `apply_config_direct_endpoint` | Instantly commits config file content to node. |
| 734 | `POST` | `/api/services/{service_id}/config/migration/prepare` | `prepare_config_migration_endpoint` | Generates a set of migration steps from snapshot comparison. |
| 749 | `POST` | `/api/services/{service_id}/config/migration/apply` | `apply_config_migration_endpoint` | Applies prepared migration actions to service config. |
| 767 | `POST` | `/api/services/{service_id}/config/migration/restore` | `restore_config_migration_endpoint` | Rolls back applied migration edits. |
| 784 | `POST` | `/api/services/{service_id}/config/sync-peer` | `sync_peer_config_endpoint` | Pushes active configuration to peer nodes in the same service group. |
| 825 | `GET` | `/api/services/{service_id}/capabilities` | `get_service_capabilities_endpoint` | Returns capability flags for service. |
| 833 | `GET` | `/api/services/{service_id}/metrics` | `get_service_metrics_endpoint` | Queries PromQL metrics (CPU, Memory, DB status, queues) for service. |
| 841 | `GET` | `/api/services/{service_id}/summary` | `get_service_summary_endpoint` | Combines releases, checks, and capabilities summaries. |
| 849 | `GET` | `/api/services/{service_id}/lifecycle-impact` | `get_service_lifecycle_impact_endpoint` | Identifies downstream dependents that block service deletion. |

### `routers/sre.py`
| Line # | HTTP Method | Endpoint Path | Function Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| 11 | `GET` | `/api/lifecycle/audit` | `lifecycle_audit` | Renders audits of events and approvals over a sliding hour window. |
| 16 | `POST` | `/api/lifecycle/force-approvals` | `create_force_approval` | Registers requests to force-delete services/nodes with warnings. |
| 31 | `GET` | `/api/lifecycle/force-approvals` | `list_force_approvals` | Lists pending and active force-delete approvals. |
| 49 | `POST` | `/api/lifecycle/force-approvals/{approval_id}/decision` | `decide_force_approval` | Saves administrator decision on force-delete approvals. |
| 66 | `POST` | `/api/lifecycle/force-approvals/{approval_id}/revoke` | `revoke_force_approval` | Revokes active force-delete approval windows. |
| 83 | `POST` | `/api/policy/scan` | `policy_scan` | Triggers a scan for system violations. |
| 88 | `GET` | `/api/policy/findings` | `policy_findings` | Lists all active SRE policy scan violations. |
| 93 | `POST` | `/api/slo/evaluate` | `slo_evaluate` | Scrapes Prometheus availability metrics to evaluate SLOs. |
| 98 | `GET` | `/api/slo/reports` | `slo_reports` | Retrieves historical database records of SLO metrics. |
| 103 | `POST` | `/api/incidents` | `open_incident` | Registers a new incident ticket. |
| 117 | `GET` | `/api/incidents` | `incidents` | Returns all open and resolved incidents list. |
| 122 | `POST` | `/api/incidents/{incident_id}/resolve` | `close_incident` | Resolves an incident ticket. |
| 127 | `POST` | `/api/incidents/{incident_id}/runbook/{runbook_key}` | `incident_runbook` | Executes automated SRE troubleshooting runbooks. |
| 135 | `GET` | `/api/runbooks/executions` | `runbook_executions` | Returns logs of runbook actions. |
| 140 | `GET` | `/api/capacity/reports` | `capacity_reports` | Lists overall node hardware capacity usage calculations. |
| 145 | `POST` | `/api/secrets` | `create_secret` | Registers service/node secret metadata. |
| 159 | `GET` | `/api/secrets` | `secrets` | Lists registered secrets and rotation timeline indicators. |
| 164 | `POST` | `/api/secrets/{secret_id}/rotate` | `rotate_secret` | Triggers secret rotation playbook execution. |
| 169 | `POST` | `/api/maintenance` | `create_maintenance` | Schedules a maintenance window to override SRE alarm rules. |
| 184 | `GET` | `/api/maintenance` | `maintenance_windows` | Lists active/upcoming maintenance intervals. |
| 189 | `POST` | `/api/maintenance/{maintenance_id}/complete` | `maintenance_complete` | Closes active maintenance windows early. |
| 194 | `POST` | `/api/audit/exports` | `audit_export` | Compiles and writes out an operations audit report spreadsheet file. |
| 199 | `GET` | `/api/audit/exports` | `audit_exports` | Lists compiled audit spreadsheets ready for download. |

---

## 3. Backend Gaps and Stubbed Implementations

An in-depth analysis of the backend source files revealed 11 specific implementation gaps, stubs, and coding defects:

1. **Loki Archived Storage Size KPI is hardcoded to 0**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/orchestrator/diagnostics/impl.py:1409` (specifically line 1417 inside `get_ingestion_stats()`).
   - **Details**: The design specifications (`diagnostics-page-detailed-features.md`) require executing a remote SSH shell command on the primary node to search and calculate the size of files in log directories. If this fails, the backend must calculate a projected size based on ingestion rate, record sizes, and a 90-day retention period. Instead, the backend initializes `archive_size_bytes = 0` and returns it directly without any calculation or remote check.

2. **Container stdout/stderr Live Logs are simulated via database events**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/orchestrator/diagnostics/impl.py:228` (specifically lines 228–250 inside `service_live_logs()`).
   - **Details**: The "Container Live" console tailing is supposed to run real-time `docker logs -f` streams from the docker hosts. Instead, the endpoint queries local database records from the `OperationalEvent` table filtered by category (`diagnostics`, `monitoring`, `deployment`, `config`, `lifecycle`) and returns them formatted as lines.

3. **Log Event Rate Sparkline Binning & Square-Root scaling is missing**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/orchestrator/diagnostics/impl.py` or `/home/ubuntu/PlatformOps/apps/api/platformops/routers/diagnostics.py`.
   - **Details**: The specifications require dividing the historical log dataset into 18 chronological bins, segmenting them by level (INFO/WARN/ERROR), and calculating relative heights using a square-root ratio: $Height = 4px + \text{round}\left( \frac{\sqrt{TotalBinLines}}{\sqrt{MaxBinLines}} \times 28px \right)$. The backend has no logic for this, shifting all data manipulation and math rendering to the frontend.

4. **Loki Log Cursor Pagination Pagination is backward-only**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/orchestrator/diagnostics/impl.py:331` (specifically lines 328, 350 inside `service_container_history()`).
   - **Details**: The query parameters sent to Loki are hardcoded to `"direction": "backward"`. Furthermore, the next cursor token payload is hardcoded to `{"anchor_ts_ns": int(last_ts_ns) - 1, "direction": "older", "page": page + 1}`, offering no implementation to traverse "Newer" pages (forward search) based on base64 cursor tokens.

5. **Loki Page Cache lacks sequential traversal capabilities**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/orchestrator/diagnostics/impl.py` (referencing `_LOKI_PAGE_CACHE`).
   - **Details**: The cache is implemented as a simple static dictionary lookup. It does not implement multi-step sequential query recovery to reconstruct missing intermediate cursors when users skip pages (e.g. going from page 1 to 4).

6. **Top Processes endpoint is global and lacks memory/sorting capabilities**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/routers/monitoring.py:35` (specifically lines 35-50 inside `get_process_metrics()`).
   - **Details**: Selecting a node is supposed to query the host OS for its running processes with sorting options (by CPU% or Memory%). Instead, the endpoint queries Prometheus globally for the top 10 CPU-consuming processes: `topk(10, rate(namedprocess_namegroup_cpu_seconds_total[5m]))`. It does not accept a node ID, does not track memory utilization, and does not support sorting.

7. **Missing Ingress/Egress Stream & Batch Dataflows**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/models.py`, `schemas.py`, and `routers/`.
   - **Details**: As noted in `GEMINI.md`, the legacy `cPlatform` tracks SFTP/S3 batch scheduling and MQTT stream ingestion. PlatformOps has NiFi/Airflow cards but completely lacks database schemas, models, or FastAPI CRUD endpoints to configure and run these stream schedulers.

8. **Missing Model Registry Comparative endpoints**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/routers/` and `models.py`.
   - **Details**: No database models or endpoints are implemented to register ML model weights, loss curves, accuracies, or comparison tools. Only basic DTrain training job statuses are simulated.

9. **SSH Keys are stored unencrypted on disk rather than in Vault**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/routers/ops_common.py:364` (specifically line 370 inside `_save_ssh_private_key()`).
   - **Details**: Rather than integrating with a secure HashiCorp Vault credential registry as required for remote node onboarding, SSH keys are stored in unencrypted `.pem` files on the local filesystem under `data/runtime/ssh_keys/node_{id}.pem`.

10. **FastAPI Route Collision in Observability Router**:
    - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/routers/observability.py`.
    - **Details**: Both `deploy_observability()` (line 19) and `deploy_observability_endpoint(node_id: int)` (line 71) are decorated with the exact same HTTP POST path `/api/observability/deploy`. This causes a routing conflict in FastAPI where the remote node deployment route overrides the local compose stack deployment route.

11. **Pydantic Validation Bug caused by missing import in `schemas.py`**:
    - **Path/Location**: `/home/ubuntu/PlatformOps/apps/api/platformops/schemas.py:164` (specifically lines 164–165).
    - **Details**: The fields `preflight` and `summary` in `ServiceInstallSchemaOut` are typed as `Optional[PreflightOut]` and `Optional[str]`. However, `Optional` is never imported from `typing` (only `Any` is imported). This missing import causes a `PydanticUserError` on Python 3.10+ environments when calling `/api/catalog/services/{service_key}/install-schema`, returning a 500 Internal Server Error.

---

## 4. Frontend Views and Components Catalog

The React frontend utilizes a centralized layout shell routing system, delegation views, and inline custom SVG vector charts.

### A. Root Layout & Navigation Shell
*   **Vite Entrypoint**: `/home/ubuntu/PlatformOps/apps/web/src/main.tsx`
    *   *Line 6*: Mounts the `<App />` root component.
*   **App Root Shell**: `/home/ubuntu/PlatformOps/apps/web/src/App.tsx`
    *   *Lines 19–68*: Implements the main layout wrap `AuthenticatedShell`, embedding draw hosts, alert banners, and active view state router gates.
    *   *Lines 70–85*: Renders the fallback Sign-In credentials form.
    *   *Lines 87–104*: Renders the User Invitation registration bridge screen.
*   **Breadcrumbs Nav Header**: `/home/ubuntu/PlatformOps/apps/web/src/components/Layout.tsx`
    *   *Lines 27–80*: Renders breadcrumbs with cluster/node/service context pill headers.
*   **Sidebar Nav Component**: `/home/ubuntu/PlatformOps/apps/web/src/components/Sidebar.tsx`
    *   *Lines 8–142*: Defines navigation arrays split into Platform (Clusters, Config Manager, Users), Observability (Monitoring, Performance, Diagnostics, Observability Stack), and Advanced (Topology, Policy, Audit, Reliability).
    *   *Lines 144–188*: Renders sidebar navigation buttons and the operational status footbar.

### B. Workspace Navigation Views
All lightweight wrapper views in `apps/web/src/views/` delegate execution and rendering straight to `PlatformProvider.tsx` context handlers:
*   `ClustersView.tsx` (Line 5) $\rightarrow$ Delegates to `renderClustersView()` at `PlatformProvider.tsx:4844`
*   `ConfigView.tsx` (Line 5) $\rightarrow$ Delegates to `renderConfigManagerView()` at `PlatformProvider.tsx:5239`
*   `DiagnosticsView.tsx` (Line 5) $\rightarrow$ Delegates to `renderDiagnosticsView()` at `PlatformProvider.tsx:6193`
*   `MonitoringView.tsx` (Line 5) $\rightarrow$ Delegates to `renderMonitoringView()` at `PlatformProvider.tsx:7206`
*   `PerformanceView.tsx` (Line 5) $\rightarrow$ Delegates to `renderPerformanceView()` at `PlatformProvider.tsx:8496`
*   `ObservabilityView.tsx` (Line 5) $\rightarrow$ Delegates to `renderObservabilityStackView()` at `PlatformProvider.tsx:8780`
*   `TopologyView.tsx` (Line 5) $\rightarrow$ Delegates to `renderTopologyView()` at `PlatformProvider.tsx:8893`
*   `PolicyView.tsx` (Line 5) $\rightarrow$ Delegates to `renderPolicyView()` at `PlatformProvider.tsx:8969`
*   `AuditView.tsx` (Line 5) $\rightarrow$ Delegates to `renderAuditView()` at `PlatformProvider.tsx:9021`
*   `ReliabilityView.tsx` (Line 5) $\rightarrow$ Delegates to `renderReliabilityView()` at `PlatformProvider.tsx:9078`
*   `UsersView.tsx` (Line 5) $\rightarrow$ Delegates to `renderUsersView()` at `PlatformProvider.tsx:9176`
*   `GlitchTipWorkspace.tsx` (Line 5) $\rightarrow$ Delegates to `renderGlitchTipWorkspace()` at `PlatformProvider.tsx:6747`
*   `LogAnalystChat.tsx` (Line 5) $\rightarrow$ Delegates to `renderAiChat()` at `PlatformProvider.tsx:5825`
*   `DrawersHost.tsx` (Line 5) $\rightarrow$ Delegates to `renderDrawers()` at `PlatformProvider.tsx:7281`
*   `ModalsHost.tsx` (Line 5) $\rightarrow$ Delegates to `renderModals()` at `PlatformProvider.tsx:7827`

### C. Shared Rendering Components & Visualizations
*   **GlassCard Container**: `/home/ubuntu/PlatformOps/apps/web/src/components/GlassCard.tsx`
    *   *Lines 12–26*: Reusable container applying a backdrop glass blur with border styling mapping to card types (`application`, `infrastructure`, `helper`).
*   **SVG Time Series Vector Chart**: `/home/ubuntu/PlatformOps/apps/web/src/components/charts.tsx`
    *   *Lines 52–138*: Renders `<SvgTimeSeriesChart>` using pure SVG polygons, hover trackers, and crosshair coordinates.
*   **Metric Sparkline**: `/home/ubuntu/PlatformOps/apps/web/src/components/charts.tsx`
    *   *Lines 178–197*: Implements `<renderMetricSparkline>` representing status bar percentages.
*   **Circular Progress Gauge**: `/home/ubuntu/PlatformOps/apps/web/src/components/charts.tsx`
    *   *Lines 219–270*: Implements `<renderCircularGauge>` creating concentric radial tracks.
*   *Note*: The charting components are fully duplicated inline within `/apps/web/src/platform/PlatformProvider.tsx` (lines 1086–1285).
*   **TreeNavigator component**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx`
    *   *Lines 4719–4825*: Implements `renderTreeNavigator` which processes active node, cluster, and service lists into an expandable vertical tree structure.

---

## 5. Frontend Parity Gaps

A comparison of `PlatformProvider.tsx` and related components against cPlatform design specifications highlights the following frontend parity gaps:

1. **Missing GlitchTip Exception User Context Metadata**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:6859` (specifically inside expanded exception drawer JSX block lines 6859–6931).
   - **Details**: The design specifications require displaying client browser versions, OS, IP addresses, HTTP request methods, query parameters, and headers when viewing exception details. The implementation only renders the Event ID, date, stacktrace frame grids, and breadcrumb messages, completely omitting user device/network metadata.

2. **Missing "Delete" Triage Action for GlitchTip Exception Issues**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:6933` (specifically lines 6933-6934).
   - **Details**: The design specification requires three primary exception issue triage controls: *Resolve*, *Ignore*, and *Delete*. The component only renders buttons for "Mark Resolved" and "Ignore / Mute".

3. **Missing "Timeout" Field in Add Uptime Monitor Form**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:6971` (specifically lines 6971–7015).
   - **Details**: When configuring a synthetic uptime check ping, the user must specify a Timeout threshold. The form renders Name, URL, Type, and Interval inputs, but is missing the Timeout input field.

4. **No Column Header Click Sorting in APM Transactions Table**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:7089` (specifically lines 7089–7097).
   - **Details**: Headers of the APM HTTP transaction table must support column clicks (`toggleTransactionTableHeaderSort`) to sort transactions dynamically. Instead, the headers `<th>` are static text elements, and sorting can only be changed via a separate dropdown select box (`txSort` on line 7082).

5. **Missing APM Span Trace Details Deep-Link**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx`.
   - **Details**: No links or redirect buttons are implemented to deep-link users from the APM list directly into the native GlitchTip APM trace explorer dashboard.

6. **Missing Telemetry Scrape Agent Status Indicators**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:8546` (specifically lines 8546–8552).
   - **Details**: The telemetry performance view header KPI strip lists Clusters, Nodes, Online nodes, and GPUs, but displays no status indicators or scrape validation tags for `node_exporter` or `service_exporter`.

7. **Missing Tree Service Warning Outlines**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:4807` (specifically line 4807 in `renderTreeNavigator`).
   - **Details**: Services on the navigator tree that have breached threshold limits (restarts, queue depth, error spikes) must display orange/red warning outlines. The current implementation only renders a simple solid status dot based on `service.status`.

8. **Missing CPU Model & RAM GB Capacity Indicators**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:8600` (specifically lines 8600–8603).
   - **Details**: The CPU Utilization KPI tile is missing the CPU Model descriptor, and the Memory KPI tile displays raw percentages without actual capacity indicators (e.g. GB Used / Total GB) or sparklines.

9. **Single-Line Chart Rendering instead of True Multi-Line Charting**:
   - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:8753` (specifically lines 8753–8765).
   - **Details**: The custom contract chart renderer is supposed to map multiple related series onto a single chart grid using `renderMultiLineChart`. The code loops through charts and draws a separate single-line `<SvgTimeSeriesChart>` block for each data series.

10. **Missing Explicit View Database Fallback Load Button**:
    - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:5314` (specifically lines 5314–5328).
    - **Details**: The Config Manager displays a yellow informational warning banner stating that the system fell back to database copies because the host configuration file was unavailable. However, it lacks an interactive button (`btnViewFallback`) to allow operators to explicitly trigger or force-load the database fallback configuration copy at will.

11. **Missing Diff Direction Selector (`#cmp-direction`)**:
    - **Path/Location**: `/home/ubuntu/PlatformOps/apps/web/src/platform/PlatformProvider.tsx:5575` (specifically lines 5575–5589).
    - **Details**: The config snapshot compare view renders left/right snapshot selectors and a compare button, but does not provide an interactive toggle (`#cmp-direction`) to switch the diff compare direction (Forward: A $\rightarrow$ B, or Backward: B $\rightarrow$ A).

---

## 6. Comparative Summary Table

| Feature Dimension | Implemented in PlatformOps | Gaps / Missing Capabilities |
| :--- | :--- | :--- |
| **Authentication & User Management** | Login, Logout, Active Profile `/api/auth/me`, invitation token creation & resending. | Unencrypted local filesystem storage of SSH key files instead of secure HashiCorp Vault. |
| **Infrastructure CRUD** | Clusters and Nodes lifecycle, connection testing, lifecycle impact evaluations. | Host node process monitoring is global and cannot filter by selected node; memory tracking is missing. |
| **Service Provisioning** | Catalog service YAML templates, dependency preflight checks, placement recommendations. | Ingress/Egress FTP/SFTP/S3 schedulers and MQTT stream pipelines are missing (no DB models or endpoints). |
| **Logs Telemetry** | Historical Loki queries, file tailing via SSH ad-hoc, compressed log archives viewing/downloading. | Loki Archived Storage Size KPI is hardcoded to 0; live container logs are simulated using DB operational events; Loki cursor pagination is backward-only. |
| **GlitchTip Workspace** | Health dashboard, issues list, event details stacktraces, issue action resolution, ping uptime CRUD. | Exception drawer misses client OS/browser context; missing "Delete" triage action; uptime monitor form misses "Timeout" field; APM transactions table headers do not support click sorting. |
| **Performance Visualizations** | Custom metric definitions, pure inline SVG time series charts, sparklines, circular progress gauges. | Scrape agent indicators (`node_exporter`/`service_exporter`) are missing; memory tiles lack GB capacity values; charting maps series to separate single-line charts rather than overlaying them on a multi-line chart. |
| **Config Manager Workspace** | Drift detection, snapshot CRUD, diff compare tool, YAML validation, apply changes, migration sequences. | Missing explicit database fallback force-load button (`btnViewFallback`); compare tool lacks diff direction selector (`#cmp-direction`). |
| **SRE Operations** | Incidents management, policy scanning and findings, SLO evaluations, secrets rotation, maintenance windows. | None (high level of functional parity achieved in SRE workflows). |
