# Tasks: PlatformOps DevOps/SRE Control Plane Implementation

This checklist details the steps to refine the DevOps/SRE control plane, upgrade the UI/UX layout to a premium dark SRE console, and fully implement onboarding, playbook execution, log file browsing, and interactive runbooks.

## Todo List

### Phase 1: Debrand "Iktara" & Update References (Completed)
- [x] **Sidebar Logo & Branding**: Update logo and emblem to PlatformOps.
- [x] **Topbar Breadcrumbs**: Update to PlatformOps breadcrumb path.
- [x] **Volume Root Presets (Frontend/Backend)**: Mapped all volume defaults to `/platformops` (and GPU nodes to `/platformops-gpu`).

### Phase 2: Refine UI Styling & Modern Layout (Completed)
- [x] **Slick CSS Design System**: Upgrade `styles.css` with a premium dark-mode theme, tailored HSL color tokens, backdrop-filter glassmorphism, custom scrollbars, and neon glows on active tabs.
- [x] **Clean Sidebar & View Selector**: Keep sidebar navigation clean and focused on DevOps (Clusters, Config Mgr, Monitoring, Diagnostics) without MLOps/Dataflow clutter.
- [x] **Responsive Panels**: Standardize padding, gap metrics, and container responsiveness for the clusters list, node details, and diagnostic cards.

### Phase 3: Node Onboarding & Playbook Console (Completed)
- [x] **Node Onboarding Stepper**: Ensure host onboarding Drawer/Form exposes fields for `ssh_key_path` and `volume_root`, and submits properly to the backend.
- [x] **Live Ansible Playbook Terminal**: Implement a styled monospace log terminal in the UI that streams simulated onboarding/validation playbooks (e.g., node validate, docker setup).

### Phase 4: Polish Config Manager & Safety Policies (Completed)
- [x] **Policy Findings Panel**: Style compliance violations dynamically, rendering links to remediation actions.
- [x] **Force-Delete Approvals Workflow**: Create a beautiful modal for force-deletes, showing the two-person validation state.
- [x] **Diff Viewer UI Colors**: Swap Expected (Left) config diff color to light red (`var(--err-bg)`) and Actual (Right) diff color to light green (`var(--ok-bg)`) to align with standard diff expectations.

### Phase 5: Enhance Diagnostics & SRE Runbook Dashboard (Completed)
- [x] **Live Logs Console**: Restyle the cursored Loki live tail terminal log lines with level-based color codes.
- [x] **Interactive Runbook Terminal**: Wire the SRE AI Analyst incidents view to trigger and display step-by-step SRE runbook executions (restart service, volume flush).
- [x] **Log Archive Interactive Browser**:
  - [x] Bind row `onClick` in the "Log Files" sub-tab to set `selectedArchive`.
  - [x] Render the archives table using the `.lf-table` class from the design system.
  - [x] Implement the `Log Archive Preview Modal` displaying path, size, discovered timestamp, simulated logs payload, and backfill trigger action.

### Phase 6: Build Verification & Testing (Completed)
- [x] **Verification Harness**: Run `make check` inside the project root to verify python schema files compile and pass integration checks.
- [x] **Production Compilation**: Verify that `npm run build` succeeds on the React package with no errors.

### Phase 7: UI Mockup Refinements & Revamp
- [x] **Branding Logo Style**: Update `.sidebar .brand .logo` in `styles.css` to feature a neon indigo outline border, translucent background, and text shadow glow to match the shell mockup.
- [x] **Dashboard Telemetry Cards Enhancements**: Integrate inline progress bars (Nodes, Observability) and live colored sparklines (Running Services, Open Incidents, Burning SLOs) inside the dashboard metrics cards in `main.tsx`.
- [x] **Circular SLO Gauges**: Implement SVG-based `CircularGauge` component in `main.tsx` and render a row of circular/arc gauges with glowing status rings in the SRE Monitoring dashboard.
- [x] **SRE AI Chat UI Revamp**: Update chat bubbles in `renderAiChat` with distinct avatars/labels, layout alignment, interactive suggestion capsules, and terminal-style query inputs.
- [x] **Production Verification**: Run `npm run build` and ensure zero TypeScript errors or CSS bundling warnings.

## Review & Summary
- **Config Manager Color Swap**: Modified the comparison pre-formatted content tags in `main.tsx` to display Expected values (Left) in light red (`rgba(239, 68, 68, 0.08)`) text `#f87171` and Actual values (Right) in light green (`rgba(16, 185, 129, 0.08)`) text `#34d399` to align with the visual standard for deletions/additions.
- **Log Files Explorer Table Refactor**: Applied the premium design system table layout `.lf-table` class structure and styled table nodes (`.fn`, `.size`, `.lines`) to the Diagnostics sub-tab log archives. Hooked `onClick` to bind row elements to `selectedArchive`.
- **Log Archive Preview Modal**: Created a glassmorphism modal component triggered by selecting an archive. It outputs file size, discovered date, and path metrics. Displays a simulated tail stream using a new React helper `generateMockLogs`. Also features a "Trigger Loki Backfill" button running the `/api/services/{id}/diagnostics/backfill` backend pipeline.
- **TypeScript Type Sync**: Updated `type LogArchive` in `apps/web/src/main.tsx` to include `discovered_at?: string;` property matching the backend pydantic serializer schema, achieving a clean build.
- **Execution Verification**: Verified compiled integrity and tested deployment compatibility; both backend verification (`make check`) and production frontend build (`npm run build`) succeeded with 0 errors.
- **UI Mockup Refinements & Revamp (Phase 7)**:
  - **Sidebar Branding Glow**: Modified the brand logo icon container CSS in `styles.css` to render as a hollow neon border, transparent container background, and a glowing text-shadow, creating the glowing 'P' look.
  - **Telemetry Cards Bars & Sparklines**: Refactored the dashboard grid telemetry cards inside `main.tsx` to render inline progress indicators for Nodes and Observability, and colored green, orange, and red sparkline metrics for Running Services, Open Incidents, and Burning SLOs.
  - **Circular SVG-based SLO Performance Gauges**: Added a `renderCircularGauge` component using standard React SVG markup to construct glowing ring gauges, replacing the plain list with a premium, multi-gauge dashboard layout inside SRE Monitoring.
  - **SRE AI Analyst Chat Console**: Revamped the SRE Incident AI chatbot UI by placing distinct robot and operator avatar nodes, container styling, quick suggestion capsule triggers (Run lock runbook, Inspect volume, Show config, Check logs), and a monospace input bar styled as a terminal command prompt (`$`).
  - **Successful Compilation**: Executed build suite checks and verified zero TypeScript warnings or bundling errors during production generation (`npm run build`).
