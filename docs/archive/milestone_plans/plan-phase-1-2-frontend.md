# Phase 1 + 2 — Frontend extraction & data layer

## Phase 1 — Extract all page JSX into view modules
Move each `render*View` / host body out of `PlatformProvider.tsx` into `views/*`:

| Module | Source method |
|--------|----------------|
| ClustersView | already extracted |
| ConfigView | renderConfigManagerView |
| DiagnosticsView | renderDiagnosticsView (+ LogAnalystChat, tree) |
| MonitoringView | renderMonitoringView + GlitchTipWorkspace |
| PerformanceView | renderPerformanceView |
| ObservabilityView | renderObservabilityStackView |
| Topology / Policy / Audit / Reliability | matching renders |
| UsersView | renderUsersView |
| DrawersHost / ModalsHost | renderDrawers / renderModals |
| TreeNavigator (shared) | renderTreeNavigator → components/TreeNavigator.tsx |

Provider keeps **state + actions only**; views use `usePlatform()`.

## Phase 2 — Data layer split
Split PlatformProvider into:

```
platform/
  types.ts              # re-export / local aliases if needed
  context.tsx           # PlatformContext + usePlatform
  PlatformProvider.tsx  # composes hooks, provides value
  hooks/
    useAuthSession.ts
    useInventory.ts     # clusters/nodes/services refresh
    useConfigWorkspace.ts
    useDiagnostics.ts
    useMonitoringGlitchtip.ts
    usePerformance.ts
    useSreAdvanced.ts   # topology/policy/audit/slo/incidents
    useUiChrome.ts      # drawers/modals/notices/tabs
```

Provider becomes composition + `useMemo` value object (no page JSX).

## Verification
- `npm run build`
- Login admin/admin, hit each main nav page
- API still auth-gated
