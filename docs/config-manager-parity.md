# Config Manager Parity Analysis: cPlatform vs PlatformOps

This document analyzes the parity between the legacy `cPlatform` runtime configuration manager and the modern `PlatformOps` orchestrator API for managing configs. The goal is to ensure a unified configuration flow that works flawlessly on real servers (without mocks).

---

## 1. Navigator & Runtime Inventory

### Legacy `cPlatform`
- **Feature**: Provides a three-tier tree (`Cluster > Node > Service`) to select active services for config editing.
- **State**: The navigator dynamically shows green/red dots depending on the live status of the service (pinged via DB/cache).

### Modern `PlatformOps`
- **Feature**: `PlatformOps` natively builds a hierarchical topology graph via the `topology(db)` API. 
- **Parity Gap / Status**: PlatformOps achieves this perfectly, extending it with subsystem groupings and deployment dependency checks.

---

## 2. Config Editor & Live Editing

### Legacy `cPlatform`
- **Editor Features**: Uses a textarea for YAML editing. Supports "Validate YAML", "Load DB Fallback", and "Apply Configuration".
- **Application Method**: Offers "Graceful Reload" or "Hard Restart".

### Modern `PlatformOps`
- **Editor Features**: Backed by the `ServiceInstance.config_json` model. 
- **Application Method**: `apply_config_direct()` updates the service contract, which modifies the runtime behavior of `generate_compose()`. 
- **Parity Gap**: In PlatformOps, applying a configuration means triggering an Ansible deployment (`execute_deployment_plan()`) that SSHs into the node, recreates the mapped config volume file, and executes a `docker compose up -d` (graceful reload). The API does not yet explicitly differentiate between graceful reload vs hard restart (like `docker compose restart`).

---

## 3. Checkpoint History (Snapshots)

### Legacy `cPlatform`
- **History View**: Shows a timeline of active, renamed, and backup checkpoints.

### Modern `PlatformOps`
- **Data Model**: Uses `ConfigSnapshot` tied to a `ServiceInstance`.
- **APIs**: Includes `create_config_snapshot`, `restore_config_snapshot`, `rename_config_snapshot`, and `get_config_timeline_page`.
- **Parity Status**: PlatformOps fully covers this requirement. Configs are versioned iteratively (v1, v2, v3, etc.) every time an apply happens.

---

## 4. Compare & Drift Detection

### Legacy `cPlatform`
- **Compare View**: The UI computes dynamic diffs (Slot A vs Slot B) between two checkpoints.

### Modern `PlatformOps`
- **Compare View**: Supported by `compare_config_snapshots()` in the API to generate deep structural diffs.
- **Drift Detection**: PlatformOps introduces a superior server-level feature: `detect_drift(db, service)`. This function is meant to SSH into the live server, pull the active container's config file, and compare it against the expected `ConfigSnapshot` to find out-of-band manual edits.

---

## 5. Migration & Fleet Rollout

### Legacy `cPlatform`
- **Migration View**: UI for preparing migrations from Source to Target checkpoints.

### Modern `PlatformOps`
- **APIs**: `prepare_config_migration` and `apply_config_migration` handle multi-service config rollouts at the subsystem level.

---

## 6. Implementation Gaps & Features Needing Testing

To guarantee that PlatformOps' configuration manager operates seamlessly on a real server (e.g., for `dtrain` container testing), the following gaps must be addressed:

### 6.1 Backend API / Validation Gaps
- **Peer Config Sync / Fleet-wide Rollout**:
  - *Legacy Feature*: Config Manager automatically fetches and lists "peers" (other nodes running the same service type) to facilitate preparing and rolling out a configuration payload across the entire fleet/peer group.
  - *PlatformOps Gap*: PlatformOps has basic single-service migration APIs but is missing dynamic peer node group detection and fleet-wide rollout mechanisms in the config orchestrator.
- **Rollback Protection Checkpointing**:
  - *Legacy Feature*: Running `direct_apply_config` automatically captures a `service_run_config_checkpoint` *before* rewriting the remote container config. If the new config fails validation, the system can instantly roll back.
  - *PlatformOps Gap*: The `apply_config_direct` API updates the database schema but does not perform a safe, pre-apply snapshot capture on the fly.
- **Strict Schema Validation**: `cPlatform` validates YAML purely in the UI frontend. `PlatformOps` must implement strict JSON/YAML schema validation in the backend (`apply_config` endpoint) before pushing config changes to the remote server to prevent runtime crashes.
- **Graceful vs Hard Restart Logic**: The `apply_config` orchestration needs a flag (`restart_policy`) passed down to the Ansible playbook to explicitly dictate a soft reload vs a hard restart.

### 6.2 Missing Playbooks (Server-Level Execution)
- **Apply Config Playbook**: The `execute_deployment_plan` relies on Ansible. We need to ensure that the playbook securely copies the `ConfigSnapshot` payload to the remote server (e.g., into `/tmp/platformops/services/<name>/config.yaml`) and correctly maps it via Docker compose.
- **Drift Detection Playbook**: The `detect_drift` logic is currently completely untested. It requires an Ansible playbook or SSH command sequence that explicitly reads the target file inside the remote node's filesystem to verify it hasn't been altered manually by an admin.

### 6.3 Untested Features (Requires Immediate Testing)
Since the `apps/api/tests/` folder is empty, these core features must be verified on a live server:
1. **Config Push Flow**: Does creating a `ConfigSnapshot` and applying it actually result in a modified configuration file inside the running remote container?
2. **Snapshot Restoration**: Does `restore_config_snapshot` successfully rollback the container to the older configuration version without downtime?
3. **Drift Reports**: Can `detect_drift` successfully detect if a user manually SSH'd into the node and altered the `config.yaml` file, returning a `DriftReport`?
