# Config Manager Parity Analysis: cPlatform vs PlatformOps

> **Historical/design analysis — superseded for current-state claims:** Use [the selected-page functional parity record](selected-page-functional-parity.md) for the current PlatformOps contract. The comparisons below preserve legacy context and may be stale; verify implementation details against the current source before relying on them.

This document analyzes the parity between the legacy `cPlatform` runtime configuration manager and the modern `PlatformOps` orchestrator API for managing configs. The goal is to ensure a unified configuration flow that works flawlessly on real servers (without mocks).

---

## 1. Navigator & Runtime Inventory

### Legacy `cPlatform`
- **Feature**: Provides a three-tier tree (`Cluster > Node > Service`) to select active services for config editing.
- **State**: The navigator dynamically shows green/red dots depending on the live status of the service (pinged via DB/cache).

### Modern `PlatformOps`
- **Feature**: `PlatformOps` natively builds a hierarchical topology graph via the `topology(db)` API. 
- **Historical status**: The topology API exposes cluster/node/service relationships, subsystem labels, and dependency edges. Completeness of the current UI parity is tracked in the superseding record rather than established by this analysis.

---

## 2. Config Editor & Live Editing

### Legacy `cPlatform`
- **Editor Features**: Uses a textarea for YAML editing. Supports "Validate YAML", "Load DB Fallback", and "Apply Configuration".
- **Application Method**: Offers "Graceful Reload" or "Hard Restart".

### Modern `PlatformOps`
- **Editor Features**: Backed by the `ServiceInstance.config_json` model. 
- **Application Method**: `apply_config_direct()` validates YAML, captures a `pre-apply` snapshot, calls the config writer, updates `rendered_config_content`, and captures a `post-apply` snapshot. The writer attempts declared host paths and/or `docker cp`; if a container copy lands, the direct path currently invokes `docker restart` for both `reload` and `restart` modes. A non-local Ansible helper is the fallback when direct writes do not land.
- **Current limitation**: The direct-apply wrapper returns both snapshots even when the returned job must be inspected for a failed write; the post-apply record is not itself proof that the remote runtime changed. The generic `/config/apply` route calls `apply_config()` and does not use this pre/post wrapper.

---

## 3. Checkpoint History (Snapshots)

### Legacy `cPlatform`
- **History View**: Shows a timeline of active, renamed, and backup checkpoints.

### Modern `PlatformOps`
- **Data Model**: Uses `ConfigSnapshot` tied to a `ServiceInstance`.
- **APIs**: Includes `create_config_snapshot`, `restore_config_snapshot`, `rename_config_snapshot`, and `get_config_timeline_page`.
- **Parity Status**: Snapshot and timeline APIs exist. `apply_config_direct()` versions pre/post captures, but the generic apply route does not automatically create the same pair; do not assume that every apply has a snapshot without checking the route and job result.

---

## 4. Compare & Drift Detection

### Legacy `cPlatform`
- **Compare View**: The UI computes dynamic diffs (Slot A vs Slot B) between two checkpoints.

### Modern `PlatformOps`
- **Compare View**: Supported by `compare_config_snapshots()` in the API. It parses YAML and reports differing top-level keys (including changed nested values); this implementation does not emit recursive field paths.
- **Drift Detection**: `detect_drift(db, service)` is implemented and records a `DriftReport`. It tries declared host paths, a local container runtime, or a remote Ansible command according to the node connection mode, then compares the readable content with the latest snapshot. Runtime results still depend on node/container access.

---

## 5. Migration & Fleet Rollout

### Legacy `cPlatform`
- **Migration View**: UI for preparing migrations from Source to Target checkpoints.

### Modern `PlatformOps`
- **APIs**: `prepare_config_migration` and `apply_config_migration` merge and apply snapshots for the selected service. A multi-service or subsystem-wide config rollout is not shown in the current config implementation.

---

## 6. Implementation Gaps & Features Needing Testing

To guarantee that PlatformOps' configuration manager operates seamlessly on a real server (e.g., for `dtrain` container testing), the following gaps must be addressed:

### 6.1 Backend API / Validation Gaps
- **Peer Config Sync / Fleet-wide Rollout**:
  - *Legacy Feature*: Config Manager automatically fetches and lists "peers" (other nodes running the same service type) to facilitate preparing and rolling out a configuration payload across the entire fleet/peer group.
  - *PlatformOps Gap*: The config workspace now lists same-key peers and `sync_peer_config` applies to one selected peer. A single fleet-wide rollout operation is not shown in the current config orchestrator.
- **Rollback Protection Checkpointing**:
  - *Legacy Feature*: Running `direct_apply_config` automatically captures a `service_run_config_checkpoint` *before* rewriting the remote container config. If the new config fails validation, the system can instantly roll back.
  - *PlatformOps Status*: `apply_config_direct` now captures `source="pre-apply"` before writing and `source="post-apply"` afterward. The source does not show an automatic rollback on a failed job, and the post-apply snapshot must not be treated as proof of remote success.
- **Schema Validation**: *Historical requirement*: `cPlatform` validates YAML in the UI; a strict JSON/YAML schema check before remote writes remains a desired contract for PlatformOps.
  - *PlatformOps Status*: YAML parsing/root-dictionary validation exists, and service-aware required-field checks are available when `validate_config` receives a service. Direct apply calls validation without that service argument, so a strict service schema guarantee is not established.
- **Graceful vs Hard Restart Logic**: `apply_mode` is accepted and passed to the Ansible fallback, but the direct Docker path currently uses `docker restart` for both `reload` and `restart`; distinct soft-reload semantics are not established.

### 6.2 Missing Playbooks (Server-Level Execution)
- **Generic deployment path**: `execute_deployment_plan` still relies on Ansible; its behavior is separate from the direct-apply host-path/`docker cp` writer. Verify that each path securely transfers the intended payload and maps it to the declared runtime file.
- **Current status**: Direct apply first attempts host-path writes and `docker cp`; the remote Ansible helper is a fallback. `detect_drift` already has local-runtime and remote Ansible read paths, but remote file access and failure behavior still require a real-node check.

### 6.3 Untested Features (Requires Immediate Testing)
The `apps/api/tests/` folder is populated (including YAML-validation and parity tests), but the visible suite does not prove remote direct-apply snapshots or remote drift behavior. These core features still need a real-node check:
1. **Config Push Flow**: Does creating a `ConfigSnapshot` and applying it actually result in a modified configuration file inside the running remote container?
2. **Snapshot Restoration**: Does `restore_config_snapshot` successfully rollback the container to the older configuration version without downtime?
3. **Drift Reports**: Can `detect_drift` successfully detect if a user manually SSH'd into the node and altered the `config.yaml` file, returning a `DriftReport`?
