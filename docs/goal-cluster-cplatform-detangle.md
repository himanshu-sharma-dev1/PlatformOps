# GOAL: Cluster code-path detangle + cPlatform edge parity

**Status:** IN PROGRESS  
**Updated:** 2026-07-15  

## Mandate (clarified)

1. **Detangle = code flow, not UI.** Topology / Policy / Audit / Reliability stay in the **sidebar and App views**.
2. Cluster inventory, job poll, deploy, discover, and bootstrap **must not depend on** Topology/Policy/SRE/Audit bulk APIs.
3. **Observability is first-class** on the cluster DevOps surface (pipeline load + cluster-detail band + Observability stack page).
4. Match **every meaningful cPlatform `clusterDetail.js` edge case** on the cluster page (take as long as needed).

## Code-path split

| Loader | APIs | When |
|--------|------|------|
| `refreshClusterInventory()` | catalog, clusters, nodes, services, events, dashboard summary, **observability pipeline** | Always for cluster ops, bootstrap, job poll |
| `refreshAdvancedInventory()` | topology, policy findings, incidents, runbooks, SLO, capacity, secrets, maintenance, audit, lifecycle | Only when Advanced page opens or `refresh({ full: true })` |
| `refresh()` | cluster core + advanced **only if** active view is topology/policy/audit/reliability | Default mutations on cluster stay cluster-core |

## UI (kept)

- Platform: Clusters, Config Manager, Users  
- Observability: Monitoring, Performance, Diagnostics, Observability stack  
- Advanced (muted secondary): Topology, Policy, Audit, Reliability  
- Cluster detail: **Observability band** (`N/M pipeline-ready` + Manage stack)

## cPlatform edge cases shipped / restored this pass

| Edge | cPlatform source | PO implementation |
|------|------------------|-------------------|
| `withPending` double-submit coalesce | `withPending` | `clusterUx.withPending` on discover / deploy / install-card |
| Node workspace race token | `workspaceLoadToken` | `selectNode` `_nodeWorkspaceToken` |
| Unreachable node gate | node row click | `canSelectNode` + toast + `is-unreachable` CSS |
| State tone / pill | `getStateTone` | `getStateTone` + service card pills |
| Expose/port labels | `buildServiceCardHtml` | `serviceExposeLabel` on svc cards |
| Dependency blocker modal | `showDependencyBlocker` | `buildDependencyBlockerState` + ModalsHost items + Install CTAs |
| Deploy preflight missing deps | deploy flow | raised on open/execute deployment modal |
| Events panel “N events” | `renderEvents` | `ClusterEventsPanel` + `formatClusterEventRow` |
| Button busy / spinner | `setButtonLoading` | `buttonLoadingClass` + actionBusy |
| Installing shimmer | deploying card | `isServiceInstalling` + `.svc-card.installing` |
| Obs pipeline soft-fail | — | obs pipeline failure does not block inventory |
| Job poll no advanced APIs | — | uses `refreshClusterInventory` |
| Bootstrap no advanced APIs | — | uses `refreshClusterInventory` |
| Sidebar collapse | detail layout | `sidebar-collapsed` class restored |
| Late cluster summary ignore | selection change | `selectCluster` checks `selectedCluster.id` |

## Still open (continue until identical)

- Install drawer 2-step stepper labels pixel-match cP  
- Node provision drawer step labels full cP cloud vs bare-metal  
- Manual UAT: `docs/manual-test-suite-cluster-page.md`

## Added 2026-07-15 (grind pass)

- Service detail summary cards (Status / Port / Events) + overview KV extras  
- Live status summary cards + 6-col deps table (node + service)  
- Catalog drag → service-stack drop + filterCatalogItems  
- Service card Edit (schema) + adopted meta  
- openServiceEditor prefill from config_json (`mergeInstallFieldValues`)  
- Install schema hide host_port when expose off  
- Cluster list env/region facet chips (`filterClustersAdvanced`)

## Non-goals

- Deleting Advanced source files or backend APIs  
- Pixel-perfect CSS variable identity with cPlatform  
- Models / train / infer product work  
