# Release And Policy Governance

PlatformOps includes a release and policy layer so the demo behaves like a real internal platform instead of a deploy-only console.

## Release Records

Each service can create release records with:

- Version.
- Image.
- Strategy.
- Notes.
- Previous image.
- Status and completion timestamp.

APIs:

```text
GET /api/services/{service_id}/releases
POST /api/services/{service_id}/releases
POST /api/releases/{release_id}/rollback
```

UI:

- Use `Release` on an installed card to create a release.
- Use `History` to load release records.
- Use `Rollback` in the Release Governance panel.

## Drift Detection

Drift detection compares the current rendered service configuration with the latest config snapshot.

API:

```text
POST /api/services/{service_id}/config/drift
```

UI:

- Open a card with `Config`.
- Use `Detect drift`.
- The Config Manager panel shows drift status and JSON differences.

## Policy Scan

The policy scanner evaluates the current node/service graph for platform hygiene issues:

- Unresolved dependencies.
- Missing file log paths.
- Infrastructure cards exposing host ports.
- Stateful services missing backup strategy.
- Config files without volume mounts.

APIs:

```text
POST /api/policy/scan
GET /api/policy/findings
```

UI:

- Use `Policy scan` in the Monitoring panel.
- Findings appear in the Policy Findings panel.

## Why This Matters

These features demonstrate platform engineering concerns beyond deployment:

- Release auditability.
- Rollback readiness.
- Config drift governance.
- Operational policy enforcement.
- Risk visibility before a production change.
