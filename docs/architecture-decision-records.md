# Architecture Decision Records (ADRs)

This document consolidates the key architecture decision records governing PlatformOps design, backend lifecycle management, infrastructure security, and frontend interactions.

---

## Table of Contents
1. [ADR 0001: SSH Private Key Storage Simplicity](#adr-0001-ssh-private-key-storage-simplicity)
2. [ADR 0002: Service Patching State Transition](#adr-0002-service-patching-state-transition)
3. [ADR 0003: Real-Time Port/Name Collision Validation in Onboarding UX](#adr-0003-real-time-portname-collision-validation-in-onboarding-ux)
4. [ADR 0004: Cascading Node Deletion Safeguards](#adr-0004-cascading-node-deletion-safeguards)
5. [ADR 0005: Adopted Service Port Preservation on Redeployment](#adr-0005-adopted-service-port-preservation-on-redeployment)
6. [ADR 0006: Frontend Refactoring & Cluster Dashboard UX](#adr-0006-frontend-refactoring--cluster-dashboard-ux)

---

## ADR 0001: SSH Private Key Storage Simplicity

### Status
Accepted (2026-07-15)

### Context
When provisioning a new `Node` on the Cluster page, the API needs access to the private SSH key to execute Ansible playbooks and establish SSH/Docker connection probes. 

In `cPlatform`, keys were handled via an enterprise Vault registry. For `PlatformOps`, we need to balance security with ease of deployment and local execution.

### Decision
We will keep the current **file-persist path** (unencrypted on disk at `data/runtime/ssh_keys/node_{id}.pem`) for simplicity. We will not integrate an external Vault or database-level encryption at this stage.

### Consequences
- **Pros**: Zero external dependencies (no Vault server to configure), simplified debugging, and straightforward Ansible inventory generation.
- **Cons**: Private keys are stored in plaintext on the host filesystem. Access must be secured using OS-level file permissions (e.g., `chmod 600` on the directories and files).

---

## ADR 0002: Service Patching State Transition

### Status
Accepted (2026-07-15)

### Context
When applying a runtime observability patch (injecting Sentry/GlitchTip SDK parameters into a service), an asynchronous Ansible playbook runs to modify host environment files and restart the docker container. 

During this interval, operators need clear feedback in the Clusters interface that the service is undergoing modification to prevent redundant actions (like trying to deploy or config-apply simultaneously).

### Decision
We will introduce a temporary `patching` status. 
- When the patch job starts, the backend will update the `ServiceInstance.status` to `patching`.
- The frontend will map the `patching` status to a distinct visual indicator (e.g., a pulsing blue/yellow status pill).
- Upon job completion, the standard 5-second polling interval will query the actual container status via `docker inspect` and naturally transition it back to `running` or `stopped`.

### Consequences
- **Pros**: Clearer operator visibility and explicit locks against concurrent operations on the service while it is being patched.
- **Cons**: Minor database mutations during transient operations, requiring status-pill style adjustments on the frontend.

---

## ADR 0003: Real-Time Port/Name Collision Validation in Onboarding UX

### Status
Accepted (2026-07-15)

### Context
When provisioning or adopting a containerized service from the catalog, port or container name collisions can block deployment or cause Docker runtime failures. 

While the backend validates name and port conflicts upon service registration and deployment, waiting until form submission to notify the operator leads to a poor user experience (forcing them to re-enter values or re-open the onboarding wizard).

### Decision
We will implement proactive, debounced real-time validation in the frontend catalog onboarding drawer (`DrawersHost.tsx` or service creation fields).
- As the operator types a container name or host port, the UI will wait for a short debounce period (e.g., 300ms) and trigger an asynchronous query to `/api/nodes/{id}/check-port-and-name`.
- If a conflict is discovered (either in the DB inventory or live on the target host), an inline red warning text will appear below the input field detailing the conflict.
- The "Create Service" submission button will be disabled until all validation conflicts are resolved.

### Consequences
- **Pros**: Prevents invalid database state submissions, improves operator speed, and provides instant feedback.
- **Cons**: Minor increase in API request traffic (mitigated by input debouncing).

---

## ADR 0004: Cascading Node Deletion Safeguards

### Status
Accepted (2026-07-15)

### Context
The `AIOrchestrator` service contains a strict delete guard blocking direct removal while other services exist in the cluster. However, during node decommissioning, the operator is deleting the host compute resource (`Node`). 

We need to decide if the node-level deletion should respect the individual service guards or cascade through them when forced.

### Decision
We will keep the current behavior: a **cascaded force-delete of the Node always cleans up all hosted services on that node, including `AIOrchestrator`**, without forcing the operator to migrate the orchestrator first.

This aligns with physical reality: if the compute node is destroyed or decommissioned, its hosted containers are gone regardless. The control plane relies on the operator's force-delete authorization to perform this total host teardown.

### Consequences
- **Pros**: Clean, non-blocking node decommissioning workflows.
- **Cons**: If the operator force-deletes a node containing the cluster's sole `AIOrchestrator`, the cluster will be left without a control plane service. It is the operator's responsibility to re-bootstrap it on a surviving node.

---

## ADR 0005: Adopted Service Port Preservation on Redeployment

### Status
Accepted (2026-07-15)

### Context
When a service instance is adopted via node infrastructure discovery, the host port mapping is extracted from the running docker container and stored in the database's `ServiceInstance.config_json` payload. 

If the operator subsequently redeploys this adopted service using the Ansible orchestrator, we must decide whether to reset the container to standard catalog defaults or preserve its discovered/custom host port mappings.

### Decision
We will **honor discovered overrides on redeploy**. The Ansible deployment variables will default to the host port configurations recorded during adoption rather than resetting to catalog defaults.

### Consequences
- **Pros**: Prevents host port collisions during redeploys, avoids breaking external clients already bound to the discovered ports, and respects the existing configuration of the target machine.
- **Cons**: Discovered/non-standard port overrides are carried forward indefinitely, potentially diverging from the standard catalog layout guidelines.

---

## ADR 0006: Frontend Refactoring & Cluster Dashboard UX

### Status
Accepted (2026-07-15)

### Context
The original Cluster page combined list and detail views without dedicated dashboard overviews or responsive styling:
- There was no browser-responsive layout for smaller screens.
- There was no Light Theme support.
- Service cards had generic letter icons and duplicate action buttons (e.g., Deploy, Patch, and Uninstall were present on both the card and the detail drawer).
- Unreachable nodes did not gracefully inform the operator on click.

### Decision
We will implement the following frontend architecture:

1. **Routing & Landing (Cluster Dashboard)**:
   - When a Cluster is selected, the view defaults to `selectedNode = null`, rendering a **Cluster Dashboard**.
   - The Cluster Dashboard features a grid of all Nodes (showing environment, IP, status, and service count), a cluster-wide operational event log, and catalog shortcuts.
   - Clicking a Node on the dashboard (or selecting it from the sidebar) sets `selectedNode` and navigates to the **Node Split View** (showing services, metrics, and details).
   - Breadcrumbs reset `selectedNode` to `null` to return to the dashboard.

2. **Light & Dark Theme Toggle**:
   - Theme toggle button in the topbar (`Layout.tsx`).
   - Browser preference detection (`window.matchMedia('(prefers-color-scheme: dark)')`) as the default, persisted in `localStorage`.
   - Dedicated `.light-theme` CSS class re-defining color tokens.

3. **Service Card Quick Actions & Tooltips**:
   - Replaced duplicate deploy/uninstall controls with 3 quick-action buttons on service cards: `Details` (drawer), `Logs` (diagnostics navigation), and `Config` (config manager navigation).
   - Explicit `title` tooltips explaining target actions.

4. **Custom SVG Service Icons**:
   - Replaced generic letter icons with high-fidelity SVGs for core services (PostgreSQL, Redis, RabbitMQ, ClickHouse, Prometheus/Otel, Loki, AIOrchestrator, and dTrain), falling back to generic container SVGs for custom services.

5. **Unreachable Node Interaction**:
   - Unreachable nodes display an inline notification toast detailing connection states rather than opening broken panels.

### Consequences
- **Pros**: Clean visual layout, structured navigation, theme flexibility, and robust error UX.
- **Cons**: Requires active view state tracking in React context.
