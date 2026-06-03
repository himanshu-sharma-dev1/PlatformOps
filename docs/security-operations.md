# Security Operations

PlatformOps includes a small security-operations layer so the demo shows more than deployment automation. It models the evidence trail an internal platform team would keep around secrets, maintenance, and audits without storing real secret material.

## Secret Registry

Service cards can register masked secret references through the `Secret` action in the dashboard or `POST /api/secrets`.

What is captured:

- Target service and node.
- Secret key name.
- Masked display value only.
- Scope, such as service or node.
- Rotation interval in days.
- Current status and last rotated timestamp.

The demo intentionally never stores raw secret values. Rotation changes the record status and timestamp, then writes an operational event so interviewers can see how the control plane preserves evidence.

## Maintenance Windows

Service cards can schedule maintenance through the `Maintain` action or `POST /api/maintenance`.

What is captured:

- Target service and node.
- Window title.
- Start and end timestamps.
- Impact note.
- Scheduled or completed status.

Maintenance entries are shown beside secrets and audit exports in the Security Ops panel. This makes planned change control visible next to deployment, incident, and release activity.

## Audit Exports

The `Audit export` action calls `POST /api/audit/exports` and creates a summary artifact record.

The export summary includes counts for:

- Services.
- Operational events.
- Open policy findings.
- Incidents.
- Releases.
- Secret records.
- Maintenance windows.

In local mode, PlatformOps records the artifact path and JSON summary without writing external compliance data. The point is to demonstrate how a DevOps control plane can produce audit-ready operational evidence from its own source of truth.

## Demo Talking Points

- PlatformOps treats security operations as part of the service lifecycle, not as a separate spreadsheet.
- Secrets are represented as references with masking and rotation evidence, not raw credential storage.
- Maintenance windows connect operational intent to the service graph.
- Audit exports summarize deployment, policy, release, incident, and secret state from one API.
- Every operation records an event, creating a timeline that can be reviewed after a change.
