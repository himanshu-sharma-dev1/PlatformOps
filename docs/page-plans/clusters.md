# Clusters page — complete cPlatform parity plan

## Mission

Make Clusters the authoritative owner of the canonical Cluster → Node → Redis
identity used by every other scoped page. Complete legacy cluster/node/service
behavior without expanding PlatformOps-native governance or cloud features.

## Source authority

- cPlatform routes: `/PlatformIO/ClusterView/`, `/PlatformIO/ClusterConfig/`.
- cPlatform view branches: `cPlatformIO/views.py:1375-1902`.
- Required helpers: `ClusterConfig`, `NodeConfig`, `ServiceConfig`, node/service
  event helpers, referenced templates, and cluster JavaScript.
- PlatformOps mapping: `selected-page-functional-parity.md` §1.
- Primary PlatformOps paths: `ClustersView.tsx`, inventory editor/deploy/load
  actions, `routers/clusters.py`, `routers/nodes.py`, `routers/services.py`, and
  service/node/discovery orchestrators.

## Scope classification

### Required cPlatform parity

- cluster list/select/create/edit/delete and deletion blockers;
- node add/edit/delete, info, launch where genuinely supported, discovery, and
  live service status;
- service add/edit/delete/deploy, dependency handling, live status, logs,
  config/diagnostics navigation, and events;
- exact validation/default/error and lifecycle behavior behind those actions.

### Regression-only native features

Repo/registry test buttons, dashboard summary endpoint, onboarding remediation,
inventory cleanup, approval governance, backup endpoint, and native topology
must not expand unless cPlatform source proves a counterpart. Keep them from
regressing required paths, but do not count them toward parity.

## Current evidence problems to resolve first

- Matrix rows still label edit/delete/lifecycle/job logs and multiple node paths
  merely Implemented or Unverified.
- The Redis harness creates/deploys and calls live status, but does not require
  exact container name/image/mount/config/health/log/persisted external ID.
- Node validation is skipped silently when a non-200 response occurs.
- Preflight logs `ok` without asserting it or its missing dependency set.
- No UI/browser reachability is proven by the harness.
- Cleanup checks status codes but does not query database/container/files for
  residue.
- Failure deployment, remote-to-local fallback, edit deep merge, collision
  checks, discovery/adoption, and lifecycle blockers are not covered.

## Work package C0 — contract freeze

- [ ] Enumerate every `user-action` branch and helper outcome in both legacy
  views.
- [ ] Capture sanitized create/edit/delete payload fixtures for cluster, node,
  and Redis service.
- [ ] Record defaults, aliases, field omission semantics, validation messages,
  blockers, and success/error payloads.
- [ ] Separate native additions from parity rows.
- [ ] Update matrix source pointers and create regression fixtures before code.

Exit: every legacy action has exactly one target path or a documented missing
path; no ambiguous “nearest equivalent” is counted complete.

## Work package C1 — cluster inventory and editor

- [ ] Prove list/select retains valid selection and clears invalid children.
- [ ] Create with all cPlatform fields and defaults.
- [ ] Edit every field, including blank-secret preservation and explicit secret
  replacement.
- [ ] Validate duplicate names, malformed fields, unknown IDs, unauthorized
  access, and concurrent stale edits.
- [ ] Match lifecycle preview, child blockers, confirmation, delete result, and
  retained history.
- [ ] Make rendered counts/status derive from the same authoritative data; fix
  or remove unused summary fetches.

Tests: schema/contract, persistence round-trip, secret redaction, optimistic
stale state, UI create/edit/error/confirmation, and transactional delete.

## Work package C2 — node lifecycle

- [ ] Add/edit all legacy host, SSH, volume, resource, OS/GPU, environment, and
  monitoring fields without dropping unknown valid metadata.
- [ ] Make info/connection/facts/status payloads match source semantics.
- [ ] Node validation must return and poll a terminal job; non-200 is a failure,
  not a skipped phase.
- [ ] Discovery/adoption must target the configured endpoint and never fall back
  to local DinD after SSH/provider failure.
- [ ] Exercise duplicate port/name collision before submission and at mutation
  time to prevent races.
- [ ] Wire node launch only for a cPlatform-supported provider. If no disposable
  provider is available, keep the row Unverified rather than using a UI stub.
- [ ] Match delete blockers and order when services exist.

Tests: local DinD success, unreachable remote target, invalid key, discovery
empty/malformed/partial, race collision, node with active Redis blocker, force
or supported cascade, and residue audit.

## Work package C3 — Redis service registration

- [ ] Register exactly one `redis-core` service using the canonical run ID.
- [ ] Assert catalog defaults, install-mode aliases, command, writable config
  mount, data/log mounts, health check, and container identity.
- [ ] Edit each supported field and prove deep merge preserves volumes,
  environment, health, metadata, adoption, and runtime config path.
- [ ] Preflight must assert `ok`, exact dependency list/order, and no phantom
  missing dependency.
- [ ] Test dependency failure/repair paths without adding another managed
  product target.
- [ ] Ensure service IDs and external/container identity remain stable through
  edit/redeploy.

Tests: catalog schema, deep-merge properties, redaction, duplicate name/port,
unsupported override, preflight pass/fail, and UI onboarding reachability.

## Work package C4 — deploy, status, logs, events

- [ ] Submit deployment, poll terminal state, and fail on timeout/unknown state.
- [ ] Directly inspect private DinD and assert pinned image digest, exact name,
  command, network, writable config mount, data/log mounts, running/health.
- [ ] Run `redis-cli ping` and require `PONG`.
- [ ] Require readiness output from the configured runtime log path.
- [ ] Assert database external ID/status and UI status match direct runtime.
- [ ] Assert job logs and operational events reference the canonical IDs/run.
- [ ] Verify Config/Diagnostics/Monitoring/Performance deep-links preserve the
  same selected service.
- [ ] Deploy an invalid image/command and require terminal failure, evidence,
  no phantom running state, and recovery through corrected deploy.

## Work package C5 — lifecycle and cleanup

- [ ] Exercise service lifecycle preview/blockers and supported delete.
- [ ] Poll delete job terminal success and verify container removal.
- [ ] Verify snapshots/archives/checks/history treatment matches FK contract.
- [ ] Delete node and cluster in the cPlatform-supported order.
- [ ] Query every run-labeled row and direct DinD/file path after cleanup.
- [ ] Prove cPlatform container/network/volume/database inventory is unchanged.

## Required Redis evidence

`cluster.json`, `node.json`, `service.json`, preflight response, deployment job
and logs, direct Docker inspect, Redis PING, readiness log, status responses,
events, lifecycle previews, delete jobs, and residue query. Every artifact must
carry the same run/cluster/node/service/container identity and be redacted.

## Final Clusters acceptance

Run the UI and API happy path plus invalid deployment, unreachable remote,
collision, blocker, and cleanup scenarios. Advance a row only when contract,
persistence, UI, runtime, failure, recovery, and cleanup all pass against the
current HEAD-built image.

Clusters is complete only when every required §1 matrix row is
Parity-complete. Native-only rows remain explicitly non-parity and do not block
or inflate completion.
