# ADR 0006: Frontend Refactoring & Cluster Dashboard UX

## Status
Accepted (2026-07-15)

## Context
The current Cluster page combines the list and detail views, but immediately drops the operator into the first Node's split-view upon opening a cluster. Additionally:
- There is no browser-responsive layout for smaller screens.
- There is no Light Theme support.
- Service cards have generic letter icons and duplicate action buttons (e.g., Deploy, Patch, and Uninstall are present on both the card and the detail drawer).
- Unreachable nodes do not gracefully inform the operator on click.

We need a clean, structured visual design and navigation refactoring.

## Decision
We will implement the following changes:

1. **Routing & Landing (Cluster Dashboard)**:
   - When a Cluster is selected, the view will default to `selectedNode = null`, rendering a **Cluster Dashboard**.
   - The Cluster Dashboard will feature a high-fidelity grid of all Nodes (showing environment, IP, status, and service count), a cluster-wide operational event log, and catalog shortcuts.
   - Clicking a Node on the dashboard (or selecting it from the sidebar) will set `selectedNode` and navigate to the **Node Split View** (showing the selected node's services, metrics, and details).
   - A breadcrumb or "Back to Dashboard" button in the Node view will reset `selectedNode` to `null` to return.

2. **Light & Dark Theme Toggle**:
   - Create a theme toggle button in the topbar (`Layout.tsx`).
   - Use browser preference detection (`window.matchMedia('(prefers-color-scheme: dark)')`) as the default, allowing the operator to toggle and persist their choice in `localStorage`.
   - Update `styles.css` with a `.light-theme` class that re-defines the `:root` color tokens for light mode.

3. **Service Card Cleanup & Tooltips**:
   - Remove redundant action buttons (`Deploy`, `Patch`, and `Uninstall`) from the service card row.
   - Keep only 3 quick-action buttons on the card: `Details` (opens drawer), `Logs` (navigates to diagnostics), and `Config` (navigates to config manager).
   - Add explicit tooltips (using native `title` tags) to these buttons explaining their exact action (e.g. "View service details & lifecycle controls").

4. **Custom SVG Service Icons**:
   - Replace the first-letter icons on service cards with high-fidelity, theme-aligned SVGs for the core services: PostgreSQL, Redis, RabbitMQ, ClickHouse, Prometheus/Otel, Loki, AIOrchestrator, and dTrain.
   - Render a generic cube/terminal fallback SVG for adopted or custom services.

5. **Unreachable Node Interaction**:
   - If a node's status is `unreachable`, clicking it from the dashboard or sidebar will trigger a prompt toast showing the connection state and failure details rather than opening a broken detail panel.

## Consequences
- **Pros**: Cleaner visual layout, professional navigation structure, proper theme flexibility, and robust error UX.
- **Cons**: Requires minor adjustments to the active view states in the React components.
