# GOAL: Cluster page = cPlatform DevOps surface (detangle extras)

**Status:** IN PROGRESS → execute until shell matches cPlatform product scope  
**Created:** 2026-07-15  

## Mandate

1. **Detangle** product pages that are **not** on cPlatform primary nav: Topology, Policy, Audit, Reliability, Observability-stack product page.
2. Keep **cluster-centric** DevOps: Clusters, Config Manager, Users, Monitoring, Performance, Diagnostics (entry points like cP).
3. **Events** on cluster detail match cPlatform `renderEvents` pattern (status “N events”, title/message/when rows).
4. Do **not** delete backend APIs — only remove from product shell so operators are not lost in PO-only features.
5. Stop inventing “Advanced SRE” product work on the cluster path.

## Done in this pass

- [x] Sidebar: remove Topology / Policy / Audit / Reliability / Observability stack from nav  
- [x] App shell: detangled views redirect to Clusters  
- [x] Remove Observability pipeline band from cluster detail  
- [x] Shared `ClusterEventsPanel` + `formatClusterEventRow` (cP-style) on node tab + drawers  
- [x] Unit tests for event formatting + DETANGLED_VIEWS  

## Still for you (manual)

- Run `docs/manual-test-suite-cluster-page.md` smoke  
- Confirm Events tab shows real rows after Discover on verify-node-1  

## Non-goals

- Deleting Topology/Policy/etc. source files (can re-enable later via config)  
- Pixel-perfect CSS clone  
- Models/train/infer  
