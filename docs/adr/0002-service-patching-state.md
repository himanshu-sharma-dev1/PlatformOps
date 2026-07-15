# ADR 0002: Service Patching State Transition

## Status
Accepted (2026-07-15)

## Context
When applying a runtime observability patch (injecting Sentry/GlitchTip SDK parameters into a service), an asynchronous Ansible playbook runs to modify host environment files and restart the docker container. 

During this interval, operators need clear feedback in the Clusters interface that the service is undergoing modification to prevent redundant actions (like trying to deploy or config-apply simultaneously).

## Decision
We will introduce a temporary `patching` status. 
- When the patch job starts, the backend will update the `ServiceInstance.status` to `patching`.
- The frontend will map the `patching` status to a distinct visual indicator (e.g., a pulsing blue/yellow status pill).
- Upon job completion, the standard 5-second polling interval will query the actual container status via `docker inspect` and naturally transition it back to `running` or `stopped`.

## Consequences
- **Pros**: Clearer operator visibility and explicit locks against concurrent operations on the service while it is being patched.
- **Cons**: Minor database mutations during transient operations, requiring status-pill style adjustments on the frontend.
