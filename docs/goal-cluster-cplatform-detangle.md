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

- Manual UAT: `docs/manual-test-suite-cluster-page.md`  

## Added 2026-07-15 (grind pass 4)

- **Escape** closes surfaces in cP priority (blocker → info → svc config → node → catalog → cluster editor → launch → deploy → delete)  
- Floating bottom **toast** (cP-style) with auto-dismiss  
- Job terminal **toast** + events/inventory refresh when job leaves running  
- Empty services copy matches cP “No services installed on this node”  
- Open cluster auto-selects first reachable node (prior pass)  

## Added 2026-07-16 (grind pass 5)

- **Node search** matches name / host / env / id / status (`filterNodes`); empty state + Clear when no match  
- **filterNodeServices** drops `deleted` rows from stack + node svc counts  
- **Per-service deploy/delete busy** (`deploy:{id}` / `delete:{id}`) — no longer freezes every card’s deploy icon  
- **Close info drawers** on delete confirm (`detailCloseSignal`) + inventory sync if target gone  
- **confirmDelete** / **validateNode** use `withPending` + cluster-core refresh where applicable  
- Card `is-busy` during deploy/delete (cP `setBusyState`)  

## Added 2026-07-16 (grind pass 6)

- Cluster list **empty filter** state + Clear filters  
- Delete modal **Confirm/Force** button busy (`actionBusy.delete`)  
- Service/node info drawer foot **per-target busy** on Delete/Deploy  
- `requestDelete` assess path uses `withPending` + toast on impact failure  

## Ops / E2E note

- **E2E mailing out of scope:** `scripts/run_e2e_tests.py` never tests invite-email/SMTP/account mail.  
  - Default `SKIP_GLITCHTIP=1` (cluster-focused).  
  - `SKIP_GLITCHTIP_EXCEPTION_CAPTURE=1` by default so live exceptions (which can trigger GT alert mail) are not raised.  
  - Set `SKIP_GLITCHTIP=0` only for optional read-only GlitchTip checks.

## Added 2026-07-15 (grind pass 3)

- Cluster create/edit drawer: labeled stepper, provider cards, auth tabs (PAT/SSH/none), registry cards, review sections  
- Legacy node **modal removed** (provision drawer only; fixes dual-UI bug)  
- E2E: mailing removed from suite; GlitchTip phase optional/soft  

## Added 2026-07-15 (grind pass 2 — steppers)

- Service install drawer: **Setup → Config** stepper, banner, Continue/Install/Save foot  
- Edit service opens on **Config** step with EDIT badge  
- Node provision: labeled **Cloud / Hardware / Config / Network / Firewall / Review**  
- Cloud provider cards (AWS / GCP / DC bare metal)  
- **Edit node** now opens the same provision drawer (was broken — only set state)  
- Provision vs Save on final step; validation console remains step 7 for create  

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
