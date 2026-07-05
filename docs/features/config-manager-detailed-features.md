# Legacy cPlatform: Config Manager Page Feature Inventory

This document provides a highly detailed breakdown of the user interface features, interactive controls, backend APIs, comparison tools, and rollout mechanisms that power the legacy `cPlatform` **Config Manager (`08-config-manager.html`)** workspace.

---

## 1. Config Workspace & Code Editor Panel

The primary workspace contains a full-featured code editor for inspecting and editing raw configurations (YAML/JSON) directly on host server nodes.

- **Dynamic Workspace Setup (`get_service_workspace` API)**:
  - Resolves target information: container name, config file path (e.g., `/iktara/data/volume/vol1/config/<service>/config.yaml`), and editing capabilities.
- **Code Editor (`editorTextarea`)**:
  - **Edit Mode (`btnEdit` / `enterEditMode`)**: Locks the workspace and unlocks the editor pane for modifications.
  - **Save & Apply (`#editor-save-btn` / `direct_apply_config` API)**:
    - *Auto-Backup*: Captures an automated config checkpoint (`create_checkpoint`) before writing to file.
    - *Apply Actions*: Pushes changes to the node, synchronizes DB entries, and takes a final post-apply checkpoint.
- **Validation Engine (`btnValidate` / `service_config_snapshot_validate_yaml` API)**:
  - Submits editor content to the backend to perform YAML syntax parsing and schema checks. Displays inline validation results (Success / Error alerts).
- **Database Fallback Panel (`btnViewFallback`)**:
  - If the config file on the server is corrupted or unreadable, allows the user to view and load the fallback dict config (`database_fallback_config`) stored directly inside cPlatform's database.
- **Live Status & Drift Sync Actions**:
  - **Capture Checkpoint (`#ws-capture-cp-btn`)**: Instantly snapshots current configuration.
  - **Refresh Live (`#ws-refresh-live-btn`)**: Inspects the remote file directly to detect any out-of-band modifications (drift) against the active checkpoint.

---

## 2. Checkpoint History & Snapshot Management

Displays a chronological history table of all configuration checkpoints captured for the service instance.

- **Checkpoint Meta Fields**:
  - Shows version tags (v1, v2), timestamp, creator/operator email, and sync status.
- **Rename Snapshot Modal (`submitRenameSnapshot` / `rename_checkpoint` API)**:
  - Triggers a modal (`#cmRenameInput`) to rename snapshot version tags from timestamp basenames to custom labels (e.g., `Pre-deploy Backup`, `Production Stable`).
- **Snapshot Viewer (`#view-active-snap-btn` / `view_snapshot` API)**:
  - Side modal that loads read-only raw contents of any selected checkpoint.

---

## 3. Configuration Comparison & Diff Tool

Allows operators to perform visual, line-by-line diffs between any two checkpoints to track alterations.

```
                      ┌───────────────────┐
                      │ Checkpoint Table  │
                      └─────────┬─────────┘
                                │ (Select checkboxes)
                                ▼
                       ┌─────────────────┐
                       │   Diff Viewer   │
                       └─────────────────┘
```

- **Interactive Checkbox Selector (`.compare-picker`)**:
  - Checkboxes next to each snapshot let the user select two target versions.
- **Diff Direction Configurer (`#cmp-direction`)**:
  - Configures comparative direction (Forward: Source -> Target, or Backward: Target -> Source).
- **Compare Action (`#open-cmp-btn` / `compare_config_snapshots` API)**:
  - Generates a line-by-line diff highlight (added, modified, and deleted lines) dynamically in the UI workspace.

---

## 4. Subsystem Migration & Rollout Manager

Automates rolling out complex configuration changes, tracking dependencies, and executing rollbacks.

- **Prepare Migration (`#open-migrate-btn` / `prepare_migration` API)**:
  - Calculates delta changes between a source and target checkpoint.
  - Generates hierarchical config ranks (Rank 1 vs Rank 2 dependencies).
  - Lists calculated operations (`migration_ops` like key updates or removals) and creates a migration script/payload.
- **Migration Editor (`#migrationResultEditor`)**:
  - Inline code editor for the operator to tweak the calculated migration output before applying it.
- **Apply Rollout (`#btnApplyMigratedConfig` / `apply_migration` API)**:
  - Submits rollout configurations to the node.
  - Passes down `apply_mode` parameters to the Ansible script:
    - **Reload (Soft)**: Instructs the container to reload configs dynamically.
    - **Restart (Hard)**: Executes a full container rebuild/restart on the remote VM.
- **Rollback Recovery (`#btnRestoreMigratedConfig` / `restore_migration` API)**:
  - Performs a single-click rollback. Restores the exact YAML content of the source snapshot, copies it to the node, and reloads the service.

---

## 5. Peer Node Fleet Sync

Facilitates cluster-wide rollout of configurations to prevent configuration drift across load-balanced nodes.

- **Peer Node Grid**:
  - Lists peer nodes running the same service type (e.g., other PostgreSQL instances in the cluster) with Node Names and IP Addresses.
- **Sync Peer Configuration (`.sync-peer-btn`)**:
  - Copies the active config file to the peer node's volume directories and restarts/reloads the peer container in the cluster.
