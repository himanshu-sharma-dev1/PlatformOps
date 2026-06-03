# Lifecycle Governance & Safety Review

PlatformOps implements a rigorous, dependency-aware lifecycle safety plane to protect cluster infrastructure, nodes, and application dependencies from destructive accidental actions.

## 1. Safety Review Engine

Every service, node, and cluster deletion request passes through a real-time safety impact checker. The endpoint evaluates the target resource and returns a structured payload:

```json
{
  "target_type": "service",
  "target_id": 12,
  "target_name": "postgres-core",
  "severity": "blocked",
  "can_delete_without_force": false,
  "dependents": ["rag (rag)", "analytics (ans)"],
  "active_children": [],
  "warnings": [
    "Critical infrastructure card 'postgres-core' is protected because multiple services depend on it."
  ],
  "recommended_action": "Protected infrastructure. Use Force Delete only if absolutely necessary."
}
```

## 2. Guardrail Logic Rules

- **Protected Infrastructure**: Critical core cards (`postgres-core`, `redis-core`, `rabbitmq-core`, `clickhouse-core`, `milvus-core`, `etcd-core`, `minio-core`, `prometheus-core`, `loki-core`, `airflow-postgres`, `airflow-redis`, `dtrain-tracker`) are protected because many applications depend on them. Deletion without `force=true` is blocked.
- **Active Dependents**: If an active application card depends on the target service (on the same node), deletion is blocked.
- **Node Protection**: Node deletion is blocked if active services are installed on it.
- **Cluster Protection**: Cluster deletion is blocked if active nodes or services are associated with it.
- **App Isolation**: Application cards (e.g. `rag`, `Text2SQL`, `asr`) can be deleted without warning or blocking if no other services depend on them, and their deletion does not cascade to or delete shared backing infrastructure cards.

## 3. Force Delete & Cascades

When `force=true` is supplied:
- **Policy Gates**: Force delete requires a reason (`force_reason`) with at least 12 characters. High-risk targets also require an active maintenance window.
- **Approval Workflow**: High-risk force delete paths also require an approved force-delete approval record (`force_approval_id`).
- **Two-Person Rule**: Requester cannot approve their own force-delete request.
- **Revocation Support**: Pending/approved requests can be explicitly revoked by a governance actor before use.
- **Service Deletions**: Protected infra or services with active dependents require both a strong reason and active maintenance window before force delete is allowed.
- **Node & Cluster Deletions**: If active children exist, force delete also requires active maintenance-window coverage for the affected scope.
- **Node & Cluster Cascades**: A force delete cascades down, removing all children (services on a node, nodes/services on a cluster) and logs a lifecycle event documenting the exact counts of purged children.

If policy gates fail, API returns `409` with structured lifecycle impact plus policy violations:

```json
{
  "severity": "blocked",
  "recommended_action": "Open a maintenance window and provide a stronger reason before forcing deletion.",
  "policy": {
    "allowed": false,
    "violations": [
      "Force delete requires a reason of at least 12 characters.",
      "Force delete requires an active maintenance window for this service or node."
    ]
  }
}
```

## 4. Force-Delete Approval API

PlatformOps exposes an explicit approval workflow for lifecycle governance:

- `POST /api/lifecycle/force-approvals`
- `POST /api/lifecycle/force-approvals/{approval_id}/decision`
- `GET /api/lifecycle/force-approvals`

Approval states:

- `pending`
- `approved`
- `rejected`
- `expired`
- `used`
- `revoked`

Approved records are consumed (marked `used`) after a successful force-delete action, preventing replay.
