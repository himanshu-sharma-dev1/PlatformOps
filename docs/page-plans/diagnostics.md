# Diagnostics page — complete cPlatform parity plan

## Mission

Trace the canonical Redis evidence from real runtime logs through bounded tail,
file/container history, cursor pagination, archive operations, backfill, Loki,
and configured analysis—without fabricated logs, diagnoses, or empty-success
claims.

## Source authority

- `/PlatformIO/Diagnostics/` and ClusterConfig diagnostics/live-log/backfill/
  event branches.
- `cPlatformIO/views.py:1502-1551,3713-3901` and
  `ServiceDiagnostics.py` functions called by those branches.
- Diagnostics template/JavaScript behavior for files, history, archives,
  download, bulk operations, chat, filters, and refresh.
- PlatformOps matrix §3; `DiagnosticsView.tsx`, `diagnosticsActions.ts`,
  services/diagnostics routers and diagnostics orchestrator.

## Verified acceptance status — 2026-08-22 (DOC-1)

The strict `parity-redis-20260822T111500-accept18b` and independent
`parity-redis-20260822T035500Z-e2et1` runs both passed phases 0–8. Evidence is
stored at `/tmp/platformops-redis-acceptance/<run-id>/`.

| Action group | State | Boundary |
|---|---|---|
| Deterministic Redis marker, file/container tail/history, rotated archive, archive SHA, single/bulk ZIP download, Loki query and terminal backfill | Parity-complete for the bounded log slice | Every claim is tied to the canonical run marker and service `2` |
| Ingestion stats and configured/unconfigured analyst behavior | Runtime-proven | The analyst result was an honest unavailable state when unconfigured |
| Cursor edge cases, path/Unicode/size/disappearing-container matrix and all archive variants | Contract-tested / Implemented as applicable | Do not infer exhaustive legacy diagnostics parity |

The runtime marker and archive artifacts contain no credentials; artifact scans
reported zero secrets.

## Remaining full-page gaps after bounded acceptance

- The accepted runs require deterministic markers, rotated archives, exact
  archive SHA, single/bulk ZIP, Loki query and terminal backfill; empty required
  evidence is not accepted.
- Cursor gap/duplicate variants, all path/size/disappearing-container cases,
  mixed archive failures and configured analyst grounding remain action-level
  gaps.
- Unconfigured analyst behavior is reported honestly, not as a successful chat.

## Work package D0 — contract freeze

- [ ] Trace global KPIs, service summary/readiness, target selection, live tail,
  file tail/history, container history, file list, archive view/download/bulk,
  backfill, and chat branches.
- [ ] Record defaults/limits, cursor semantics, line structure, ordering,
  timestamps, source names, archive IDs/paths, content types, and errors.
- [ ] Mark bounded HTTP tail/poll correctly; do not call it streaming unless
  cPlatform requires and PlatformOps implements SSE/WebSocket behavior.
- [ ] Classify PlatformOps-native analysis/actions outside direct parity.

## Work package D1 — deterministic Redis evidence

- [ ] Configure one canonical writable Redis log path.
- [ ] Require genuine startup/readiness log.
- [ ] Inject run-labeled ordered markers through fixture support tooling:
  normal, warning, Unicode, near-limit long line, enough pages, pre/post rotate.
- [ ] Record marker hashes/count/order/timestamps without secrets.
- [ ] Verify no marker from another run/service satisfies assertions.

## Work package D2 — target, summary, and live tail

- [ ] Load canonical diagnostic target/capabilities and assert IDs/container/
  log paths/capability truth.
- [ ] Compare service readiness/checklist with direct Redis/DinD state.
- [ ] Tail exact N lines and assert order, truncation, Unicode, timestamps, and
  run markers.
- [ ] Test alternate target selection and stale response cancellation without
  registering another managed service.
- [ ] Handle container missing/stopped, Docker unavailable, no logs, malformed
  output, unauthorized, and invalid line limit truthfully.

## Work package D3 — file and container history

- [ ] File list returns only safe configured paths with accurate metadata.
- [ ] File tail supports line/time limits and rejects traversal/unapproved path.
- [ ] Container/file history implements stable forward/backward cursors,
  direction, page size, time range, and source.
- [ ] Walk all pages and assert every marker exactly once in expected order.
- [ ] Rotate log between requests and prove defined continuation behavior.
- [ ] Distinguish Loki unavailable, no matching data, expired cursor, and true
  end-of-history.

## Work package D4 — archives and downloads

- [ ] Trigger/index archive creation from deterministic Redis logs.
- [ ] List and filter with correct size/path/time/source metadata.
- [ ] View exact marker content and enforce maximum lines/bytes.
- [ ] Download one archive with correct content type/name/checksum.
- [ ] Bulk download selected archives and validate ZIP members/checksums; reject
  unauthorized/wrong-service/missing IDs.
- [ ] Test retention/expiry, deleted source, symlink/path traversal, Unicode
  filename, partial bulk failure, and empty selection.

## Work package D5 — backfill and global ingestion

- [ ] Submit Redis archive backfill and poll terminal job.
- [ ] Record progress/count/deduplication/partial failures and operational event.
- [ ] Query Loki for exact run markers and compare count/order/timestamps.
- [ ] Repeat backfill and prove documented idempotency/no duplicate inflation.
- [ ] Validate global ingestion KPIs against direct archive/Loki counts.
- [ ] Stop Loki/Alloy and require unavailable—not zero-success—then recover and
  verify fresh marker ingestion.

## Work package D6 — analyst/chat

- [ ] With no provider configured, require explicit unavailable response and UI
  action; never generated analysis.
- [ ] With disposable configured analyst, send a query scoped to canonical
  Redis/time window and require cited marker/evidence IDs.
- [ ] Validate conversation/history, evidence links, suggested actions, and
  safe action confirmation only where cPlatform requires them.
- [ ] Reject prompt/output secret leakage and cross-service evidence.
- [ ] Test timeout, malformed provider response, empty answer, unsupported
  action, and recovery.

## Authoritative Diagnostics harness changes

- Deterministically create markers and archives; empty required results fail.
- Walk and validate cursors, downloads, ZIPs, checksums, rotation, and paths.
- Submit/poll backfill and require direct Loki marker evidence.
- Run configured/unconfigured analyst cases with grounding assertions.
- Persist artifact IDs and clean archives/run files/labels.

## Required evidence

Marker manifest, direct container/file logs, capabilities/summary, tail/history
pages/cursors, archive metadata/files/checksums, ZIP listing, backfill job/log/
event, Loki queries, ingestion comparisons, analyst grounding/unavailable
responses, failures/recovery, and cleanup.

## Final Diagnostics acceptance

Prove every deterministic Redis marker across runtime → tail/history → archive →
backfill → Loki → grounded analysis, including rotation/failures/recovery and
cleanup. Re-run Cluster/Config/Monitoring selection/status regressions.

Diagnostics is complete only when all required §3 rows are Parity-complete;
empty archives or HTTP-only chat cannot pass.
