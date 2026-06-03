# Reliability Operations

PlatformOps includes day-2 reliability workflows so the project demonstrates platform operations beyond deployment.

## Incidents

Incidents can be opened for services or nodes and tracked through resolution.

APIs:

```text
POST /api/incidents
GET /api/incidents
POST /api/incidents/{incident_id}/resolve
```

UI:

- Use `Incident` on an installed card.
- Use `Resolve` in the Reliability Ops panel.

## Runbooks

Runbooks provide repeatable operational actions. Current runbooks:

- `restart-service`
- `dependency-recovery`
- `config-rollback`

APIs:

```text
POST /api/incidents/{incident_id}/runbook/{runbook_key}
GET /api/runbooks/executions
```

UI:

- Use `Runbook` on an open incident.

## SLO Evaluation

SLO reports evaluate service readiness and dependency preflight state.

API:

```text
POST /api/slo/evaluate
GET /api/slo/reports
```

UI:

- Use `SLO eval` in the Monitoring panel.
- Results appear in the SLO & Capacity panel.

## Capacity Reports

Capacity reports estimate reserved CPU, memory, and storage from the running service graph.

API:

```text
POST /api/nodes/{node_id}/capacity
GET /api/capacity/reports
```

UI:

- Use `Capacity report` in Node Map.

## Verification

`make check` verifies:

- Incident open and resolve.
- Runbook execution.
- SLO report generation.
- Capacity report generation.
