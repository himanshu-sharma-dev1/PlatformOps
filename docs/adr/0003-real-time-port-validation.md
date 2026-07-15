# ADR 0003: Real-Time Port/Name Collision Validation in Onboarding UX

## Status
Accepted (2026-07-15)

## Context
When provisioning or adopting a containerized service from the catalog, port or container name collisions can block deployment or cause Docker runtime failures. 

While the backend validates name and port conflicts upon service registration and deployment, waiting until form submission to notify the operator leads to a poor user experience (forcing them to re-enter values or re-open the onboarding wizard).

## Decision
We will implement proactive, debounced real-time validation in the frontend catalog onboarding drawer (`DrawersHost.tsx` or service creation fields).
- As the operator types a container name or host port, the UI will wait for a short debounce period (e.g., 300ms) and trigger an asynchronous query to `/api/nodes/{id}/check-port-and-name`.
- If a conflict is discovered (either in the DB inventory or live on the target host), an inline red warning text will appear below the input field detailing the conflict.
- The "Create Service" submission button will be disabled until all validation conflicts are resolved.

## Consequences
- **Pros**: Prevents invalid database state submissions, improves operator speed, and provides instant feedback.
- **Cons**: Minor increase in API request traffic (mitigated by input debouncing).
