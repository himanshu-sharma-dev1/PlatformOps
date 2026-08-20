# PlatformOps: Config Manager Technical Specification

**Canonical Path:** `docs/features/config-manager-detailed-features.md`
**Related Parity Action Matrix:** [`docs/selected-page-functional-parity.md`](../selected-page-functional-parity.md) §2
**Authoritative E2E Test Fixture:** [`docs/redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md) (Phase 4)

---

## 1. Architectural Overview & Workspaces

The PlatformOps Config Manager workspace (`apps/web/src/views/ConfigView.tsx`) provides centralized configuration lifecycle governance for deployed services across the cluster. It supports direct YAML editing, automated pre/post snapshots, drift detection, JSON-artifact migration rollouts, and peer node fleet synchronization.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Config Manager Workspace                        │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Left Service Tree │ Main Workspace Tabs:                                    │
│ - Cluster Nodes   │ 1. [Current Config] — YAML editor, validate, apply      │
│ - Service Leaf    │ 2. [Timeline]       — Chronological checkpoints & audit │
│   (e.g. redis-core│ 3. [Compare / Diff] — Side-by-side diff comparison      │
│     SERV1000)     │ 4. [Migrate]        — Multi-node JSON rollout pipeline  │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 2. REST API Inventory (`apps/api/platformops/routers/services.py`)

All endpoints require authentication and are backed by the domain orchestrator in `apps/api/platformops/orchestrator/config.py`.

| Method | Endpoint Path | Description | Orchestrator Implementation |
|---|---|---|---|
| `GET` | `/api/services/{id}/config` | Loads service configuration workspace (`current_yaml`, `host_config_path`, `runtime_config_path`, `apply_enabled`, `snapshots`) | `config.config_workspace` (`config.py:200-281`) |
| `GET` | `/api/services/{id}/config/timeline` | Returns paginated checkpoint timeline with filters (`action`, `actor`, `search`, `created_after`, `created_before`) | `config.config_timeline` (`config.py:59-142`) |
| `GET` | `/api/services/{id}/config/snapshots` | Returns paginated snapshot list with source filters (`all`, `manual`, `pre-apply`, `post-apply`) | `config.list_config_snapshots` (`config.py:705-736`) |
| `POST` | `/api/services/{id}/config/snapshots` | Captures a manual snapshot with custom name and description | `config.create_config_snapshot` (`config.py:738-792`) |
| `GET` | `/api/services/{id}/config/snapshots/{snapshot_id}` | Retrieves full YAML content of a specific snapshot | `config.get_config_snapshot` (`config.py:668-675`) |
| `POST` | `/api/services/{id}/config/snapshots/{snapshot_id}/rename` | Renames snapshot version label with duplicate conflict resolution (`-v1`, `-v2`) | `config.rename_config_snapshot` (`config.py:793-835`) |
| `GET` | `/api/services/{id}/config/compare` | Compares two snapshots, returning line-by-line additions, deletions, and field diffs | `config.compare_config_snapshots` (`config.py:156-197`) |
| `POST` | `/api/services/{id}/config/drift` | Detects drift between latest saved snapshot and live filesystem/container configuration | `config.detect_drift` (`config.py:284-367`) |
| `POST` | `/api/services/{id}/config/validate` | Validates YAML syntax and service schema constraints | `config.validate_config` (`config.py:892-920`) |
| `POST` | `/api/services/{id}/config/direct-apply` | Synchronously applies YAML to host/container with pre/post snapshots and live reload | `config.apply_config_direct` (`config.py:594-614`) |
| `POST` | `/api/services/{id}/config/apply` | Asynchronous deployment job path executing Ansible `service_config_apply.sh` | `config.apply_config_async` (`config.py:922-995`) |
| `POST` | `/api/services/{id}/config/migration/prepare` | Prepares multi-node migration artifact JSON stored on disk | `config.prepare_config_migration` (`config.py:539-585`) |
| `POST` | `/api/services/{id}/config/migration/apply` | Executes staged migration artifact and captures backup snapshot | `config.apply_config_migration` (`config.py:616-642`) |
| `POST` | `/api/services/{id}/config/migration/restore` | Rolls back migration artifact to previous backup state | `config.restore_config_migration` (`config.py:644-674`) |
| `POST` | `/api/services/{id}/config/sync-peer` | Propagates validated configuration to sibling cluster peer nodes | `config.sync_peer_config` (`config.py:675-703`) |

---

## 3. Core Subsystem Mechanics

### 3.1 Direct Apply & Multi-Strategy Deployment Pipeline
When `POST /api/services/{id}/config/direct-apply` is executed:
1. **Validation Gate**: Syntactic YAML parsing and schema validation via `validate_config()`.
2. **Pre-Apply Snapshot**: Automatically records `source="pre-apply"` checkpoint in SQLite/PostgreSQL.
3. **Multi-Strategy Write**:
   - In local/DinD environments: Writes declared host volume path, runs `docker exec mkdir -p`, and copies file directly into the container filesystem via `docker cp`.
   - Live Reload / Restart: Executes `docker restart` or reload signal.
   - Non-local fallback: Emits Ansible execution script `service_config_apply.sh`.
4. **Database Sync**: Updates `rendered_config_content` in `service.config_json`.
5. **Post-Apply Snapshot**: Automatically records `source="post-apply"` checkpoint.

### 3.2 JSON Migration Artifact Pipeline
Migration operations are tracked through deterministic JSON artifacts:
* **Artifact Path:** `data/runtime/config-migrations/{service_id}/{artifact_id}.json`
* **Artifact ID Format:** `{timestamp}-{left_snapshot_id}-{right_snapshot_id}`
* **Schema:** Stores `left_snapshot_id`, `right_snapshot_id`, `final_yaml`, `differences`, `applied_at`, `backup_snapshot_id`, and `resolved_config_path`.
* **Rollback:** `POST /migration/restore` inspects `backup_snapshot_id` from the artifact and deterministically restores prior runtime state without requiring manual snapshot selection.

### 3.3 Peer Node Fleet Synchronization
For distributed deployments (e.g. multi-node Redis/Postgres clusters):
* `POST /api/services/{id}/config/sync-peer` validates that the target peer node hosts the identical `service_key`.
* Reads active configuration from source instance and applies it to the peer instance.
* Captures dedicated pre/post snapshots on the peer node.
* Rendered in `ConfigView.tsx:525-565` (**Fleet Rollout Strategy** table).

### 3.4 Floating Compare Bar
* Checkbox selection on two snapshots in the Timeline table activates a sticky bottom dock (`ConfigView.tsx:569-635`).
* Allows immediate navigation to side-by-side diffing or direct migration preparation.

---

## 4. Authoritative Verification via Golden Fixture (Redis Target)

Authoritative Config verification follows Phase 4 of `docs/redis-seven-page-acceptance-fixture.md`:
1. **Writable Config Staging**: Redis catalog configuration is mounted at a run-specific writable path (e.g. `/tmp/platformops/redis/redis.conf`).
2. **Direct Apply**: Apply `maxmemory 256mb` $\to$ verify pre-apply snapshot $\to$ assert HTTP 200.
3. **Live Runtime Proof**: Verify update via both host file inspection and `redis-cli CONFIG GET maxmemory` returning `268435456`.
4. **Drift Injection**: Alter runtime config directly via `redis-cli CONFIG SET maxmemory 512mb` $\to$ trigger `POST /config/drift` $\to$ assert `drift_detected: true`.
5. **Diff & Restore**: Compare drift against baseline $\to$ trigger `POST /config/snapshots/{id}/restore` $\to$ assert return to `256mb`.
