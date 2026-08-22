# Config Manager — complete cPlatform parity plan

## Mission

Prove the complete configuration lifecycle against the same deployed Redis
service: live read, validation, checkpoints, timeline, compare, drift, apply,
migration behavior required by cPlatform, restore, errors, recovery, and audit.

## Source authority

- `/PlatformIO/ConfigManager/` and ClusterConfig config actions.
- `cPlatformIO/views.py:1553-1693,3128-3483` and called ServiceConfig helpers.
- Templates/JavaScript for workspace, snapshots, migration, diff, and restore.
- PlatformOps mapping: `selected-page-functional-parity.md` §2.
- PlatformOps paths: `ConfigView.tsx`, `configActions.ts`, service config router
  family, `orchestrator/config.py`, and `service_config_apply.sh`.

## Verified acceptance status — 2026-08-22 (DOC-1)

Both `parity-redis-20260822T111500-accept18b` (strict executor) and
`parity-redis-20260822T035500Z-e2et1` (independent) passed phases 0–8. Artifacts
are in `/tmp/platformops-redis-acceptance/<run-id>/`.

| Action group | State | Boundary |
|---|---|---|
| Live workspace, baseline snapshot, validation, semantic apply, drift, compare, restore and rollback | Parity-complete for the bounded Redis fixture | Exact config bytes and `redis-cli CONFIG GET` were checked before/after; service `2` is the canonical local target |
| Terminal jobs, restart/reload and audit events | Runtime-proven | Apply and restore reached terminal success with recorded events |
| Invalid/unsupported and rollback failure handling | Contract-tested; bounded failure evidence retained | Do not infer all remote/provider failure variants |
| Migration, peer sync, rename/pagination and every legacy editor branch | Mapped / Implemented / Contract-tested as applicable | No blanket parity claim without a direct cPlatform counterpart and runtime proof |

The positive private SSH branch (node `2`, service `3`) also proved exact
remote config read/apply/rollback and SSH PONG. No external-host claim is made
for rejected credentials at `216.48.189.195`.

## Remaining full-page gaps after bounded acceptance

- The two 2026-08-22 runs prove exact live file bytes, `CONFIG GET`, terminal
  apply/restore, drift, compare, rollback and events for the canonical Redis.
- Full migration/peer semantics, rename/pagination edge cases, every editor
  branch, remote/provider failures and browser reachability remain action-level
  gaps and are not promoted to page-wide parity.

## Scope decision before implementation

Re-read cPlatform to decide whether PlatformOps peer sync or any migration
operation is a direct required counterpart. Native-only peer sync must remain
regression-only; do not create a second managed service just to test it. The
one-service Redis rule is authoritative.

## Work package G0 — contract and rendering freeze

- [ ] Enumerate workspace/checkpoint/view/rename/compare/drift/validate/apply/
  migration/restore actions and exact payloads.
- [ ] Record legacy YAML/config parsing, defaults, unknown fields, capability
  gates, restart/reload choice, and error wording/status.
- [ ] Define deterministic translation between PlatformOps editor content and
  real Redis configuration; never assert a YAML map is applied unless the
  renderer actually produces valid Redis directives.
- [ ] Classify peer sync/native operations outside parity.

## Work package G1 — live workspace and capabilities

- [ ] Load canonical Redis using ID and `source=live`.
- [ ] Assert source label, live path, content hash, schema, capabilities,
  current snapshot, drift state, and target identity.
- [ ] Capability flags must be enforced server-side; direct API calls cannot
  bypass disabled apply/restore/migration.
- [ ] Distinguish container, remote SSH, stored snapshot, DB fallback, missing
  file, permission failure, and unsupported target.
- [ ] UI loading/empty/error/retry and target changes must not display stale
  content from another service.

## Work package G2 — validation and snapshots

- [ ] Validate baseline Redis directives and reject invalid directive/value,
  malformed YAML where accepted, duplicate directives, oversized content, and
  unsafe path.
- [ ] Create named baseline snapshot with actor/source/hash/version.
- [ ] List and paginate snapshots deterministically.
- [ ] View/load a snapshot without mutating live state.
- [ ] Rename with duplicate/blank/unauthorized/not-found cases.
- [ ] Compare identical and changed snapshots; assert exact field/line diff and
  stable ordering.
- [ ] Verify timeline contains snapshot/apply/restore/failure events once each.

## Work package G3 — direct apply

- [ ] Seed writable run-specific `redis.conf` before deploy.
- [ ] Apply safe changes such as `maxmemory 128mb → 256mb` and loglevel.
- [ ] Require pre-apply snapshot before any write.
- [ ] Poll terminal job if asynchronous; capture command/output/error.
- [ ] Inspect mounted host file and container file byte-for-byte.
- [ ] Require `redis-cli CONFIG GET maxmemory` and `CONFIG GET loglevel` to
  reflect the change.
- [ ] Prove required restart/reload occurred and Redis returns `PONG` afterward.
- [ ] Assert persisted rendered content, post-snapshot, timeline, and event.
- [ ] Ensure validation/write/restart failure never advances current config.

## Work package G4 — drift and restore

- [ ] Establish no-drift baseline using exact live/stored hashes.
- [ ] Introduce controlled out-of-band change through the fixture harness and
  require drift=true with useful diff/source evidence.
- [ ] Remove/reconcile controlled drift without corrupting product state.
- [ ] Restore baseline snapshot and poll terminal success.
- [ ] Verify both files, `CONFIG GET`, Redis PING, persisted current content,
  new timeline/event, and post-restore drift=false.
- [ ] Test invalid snapshot, deleted service, detached session, unwritable file,
  restart failure, and recovery.

## Work package G5 — migration parity

- [ ] Match only migration preparation/apply/restore artifacts present in
  cPlatform source.
- [ ] Assert inputs, candidate/diff/final config/artifact fields exactly.
- [ ] Do not claim selected/ranked configurations or `migration_ops` unless
  implemented and required.
- [ ] Apply a supported migration to the same Redis target and verify live
  state; restore afterward.
- [ ] Exclude PlatformOps-only peer sync from completion unless source audit
  establishes a direct counterpart.

## Failure matrix

Invalid syntax/value; capability denied; snapshot missing/wrong service;
unwritable path; detached DB/session; apply command failure; restart timeout;
container missing; remote unavailable without local fallback; partial migration;
restore failure. Every failure must have no false success, a failed terminal
job/event where applicable, preserved pre-state, and a demonstrated recovery.

## Required evidence

Workspace payload, baseline and changed files/hashes, validation responses,
snapshots and diffs, apply/restore jobs/logs/events, direct mount inspection,
`CONFIG GET` outputs, PING, drift reports, timeline, migration artifacts, and
cleanup. Tie every artifact to the canonical service/run and current HEAD image.

## Final Config acceptance

Use the UI to perform snapshot → edit → validate → apply → compare → drift →
restore while independently verifying the file and Redis runtime. Run all
failure/recovery cases and the previously completed Clusters regression.

Config is complete only when every required §2 action is Parity-complete and no
native-only action or HTTP-only success inflates the result.
