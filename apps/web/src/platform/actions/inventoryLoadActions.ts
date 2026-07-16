// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
import { withPending } from "../ux/clusterUx";
export function createInventoryLoadActions(s: any) {
  return {
  async loadServiceCapabilities(serviceId) {
    try {
      const caps = await api(`/api/services/${serviceId}/capabilities`);
      s.setCapabilities(caps);
    } catch (e) {
      s.setCapabilities(null);
    }
  },

  async loadServiceSummary(serviceId) {
    try {
      const summary = await api(`/api/services/${serviceId}/summary`);
      s.setServiceSummary(summary);
    } catch (_error) {
      s.setServiceSummary(null);
    }
  },

  async loadServiceReleaseTimeline(serviceId) {
    try {
      const timeline = await api(`/api/services/${serviceId}/releases/timeline?limit=8`);
      s.setServiceReleaseTimeline(timeline);
    } catch (_error) {
      s.setServiceReleaseTimeline(null);
    }
  },

  async loadNodeConnection(nodeId) {
    // (Part A) always refresh live probe when opening connection
    try {
      const connection = await api(`/api/nodes/${nodeId}/connection`);
      s.setNodeConnection(connection);
    } catch (_error) {
      s.setNodeConnection(null);
    }
  },

  async loadNodeOnboarding(nodeId) {
    try {
      const report = await api(`/api/nodes/${nodeId}/onboarding-readiness`);
      s.setNodeOnboarding(report);
    } catch (_error) {
      s.setNodeOnboarding(null);
    }
  },

  async loadNodeJobHistory(nodeId) {
    try {
      const history = await api(`/api/nodes/${nodeId}/jobs?limit=10`);
      s.setNodeJobHistory(history);
    } catch (_error) {
      s.setNodeJobHistory(null);
    }
  },

  async pollOnboardingJob(nodeId, jobId) {
    try {
      const history = await api(`/api/nodes/${nodeId}/jobs?limit=5`);
      const targetJob = history.items.find((j) => j.id === jobId);
      if (targetJob) {
        s.setOnboardingOutput(targetJob.output || "");
        s.setOnboardingError(targetJob.error || "");
        s.setOnboardingStatus(targetJob.status);
        if (targetJob.status === "running" || targetJob.status === "queued") {
          setTimeout(() => s.pollOnboardingJob(nodeId, jobId), 800);
        } else {
          await s.refresh();
        }
      } else {
        setTimeout(() => s.pollOnboardingJob(nodeId, jobId), 800);
      }
    } catch (e) {
      setTimeout(() => s.pollOnboardingJob(nodeId, jobId), 1500);
    }
  },

  async loadClusterOperations(clusterId) {
    try {
      const operations = await api(`/api/clusters/${clusterId}/operations?limit=40`);
      s.setClusterOperations(operations);
    } catch (_error) {
      s.setClusterOperations(null);
    }
  },

  async runOnboardingRemediation(action) {
    if (!s.selectedNode) {
      s.setNotice("Select a node first.");
      return;
    }
    try {
      s.setOnboardingActionBusy(action);
      const result = await api(`/api/nodes/${s.selectedNode.id}/onboarding-remediate`, {
        method: "POST",
        body: JSON.stringify({ action })
      });
      if (result.validation_job) {
        s.setJob({
          id: result.validation_job.id,
          action: "validate-node",
          status: result.validation_job.status,
          command: result.validation_job.command,
          output: result.validation_job.output,
          error: result.validation_job.error
        });
      }
      s.setNotice(result.message);
      await s.refresh();
      if (s.selectedNode) {
        await s.loadNodeConnection(s.selectedNode.id);
        await s.loadNodeOnboarding(s.selectedNode.id);
        await s.loadNodeJobHistory(s.selectedNode.id);
      }
    } catch (error) {
      s.setNotice(`Onboarding remediation failed: ${error.message}`);
    } finally {
      s.setOnboardingActionBusy("");
    }
  },

  async discoverNodeInfra(nodeId) {
    // cP withPending + button busy: coalesce double-clicks on Discover
    return withPending(`discover-node:${nodeId}`, async () => {
      s.setActionBusy?.((b) => ({ ...b, discover: true }));
      try {
        s.setNotice(`Discovering infrastructure on node ${nodeId}\u2026`);
        const result = await api(`/api/nodes/${nodeId}/discover`, { method: "POST" });
        const summary =
          result?.summary ||
          result?.message ||
          `Discover: scanned ${result?.containers_scanned ?? "?"} · adopted ${result?.adopted_count ?? 0}`;
        s.showToast?.(summary, "ok") || s.setNotice(summary);
        await (s.refreshClusterInventory || s.refresh)();
        await s.loadNodeJobHistory(nodeId);
        await s.refreshNodeLiveStatus(nodeId);
        // Signal open Events tab/drawers to re-fetch scoped events
        s.setEventsRefreshKey?.((k) => Number(k || 0) + 1);
      } catch (e) {
        s.showToast?.(e?.message || "Discover failed", "err") || s.setNotice(e?.message || "Discover failed");
      } finally {
        s.setActionBusy?.((b) => ({ ...b, discover: false }));
      }
    });
  },

  async loadScopedEvents(options = {}) {
    try {
      const params = new URLSearchParams();
      params.set("limit", String(options.limit || 80));
      if (options.node_id != null) params.set("node_id", String(options.node_id));
      if (options.service_id != null) params.set("service_id", String(options.service_id));
      if (options.category) params.set("category", String(options.category));
      const items = await api(`/api/events?${params.toString()}`);
      return Array.isArray(items) ? items : items?.items || [];
    } catch (e) {
      s.setNotice(e?.message || "Failed to load events");
      return [];
    }
  },

  async loadServiceLiveStatus(serviceId) {
    if (!serviceId) return null;
    try {
      const item = await api(`/api/services/${serviceId}/live-status`);
      const map = { ...(s.serviceLiveById || {}) };
      map[serviceId] = item;
      s.setServiceLiveById(map);
      return item;
    } catch (e) {
      return null;
    }
  },

  async refreshNodeLiveStatus(nodeId, opts) {
    if (!nodeId) return null;
    try {
      const via = opts?.via ? `?via=${encodeURIComponent(opts.via)}` : "";
      const report = await api(`/api/nodes/${nodeId}/live-status${via}`);
      s.setNodeLiveStatus(report);
      const map = { ...(s.serviceLiveById || {}) };
      for (const item of report.items || []) {
        if (item?.service_id != null) map[item.service_id] = item;
      }
      s.setServiceLiveById(map);
      return report;
    } catch (e) {
      // Keep last-known; do not invent healthy
      return null;
    }
  },

  async cleanupNodeInventory(nodeId, options) {
    if (!nodeId) {
      s.setNotice("Select a node first.");
      return null;
    }
    const dryRun = options?.dryRun !== false;
    const modes = options?.modes || ["all"];
    try {
      s.setNotice(dryRun ? "Previewing inventory cleanup…" : "Cleaning inventory…");
      const result = await api(`/api/nodes/${nodeId}/inventory/cleanup`, {
        method: "POST",
        body: JSON.stringify({
          modes,
          dry_run: dryRun,
          protect_orchestrator: options?.protectOrchestrator !== false,
        }),
      });
      s.setNotice(result.summary || (dryRun ? `Would remove ${result.candidate_count}` : `Removed ${result.removed_count}`));
      if (!dryRun) {
        await s.refresh();
        await s.refreshNodeLiveStatus(nodeId);
        await s.loadNodeJobHistory(nodeId);
      }
      return result;
    } catch (e) {
      s.setNotice(e?.message || "Inventory cleanup failed");
      return null;
    }
  },

  async launchNodeVm(nodeId) {
    try {
      s.setNotice(`Launching VM for node ${nodeId}\u2026`);
      const job2 = await api(`/api/nodes/${nodeId}/launch-vm`, { method: "POST" });
      s.setJob(job2);
      s.setNotice(`Launch VM job #${job2.id}: ${job2.status}${job2.error ? ` \u2014 ${job2.error}` : ""}`);
      await s.refresh();
      await s.loadNodeJobHistory(nodeId);
    } catch (e) {
      s.setNotice(e?.message || "Launch VM failed");
    }
  },

  async teardownNodeVm(nodeId) {
    if (!window.confirm("Teardown cloud VM for this node via Terraform?")) return;
    try {
      const job2 = await api(`/api/nodes/${nodeId}/teardown-vm`, { method: "POST" });
      s.setJob(job2);
      s.setNotice(`Teardown VM job #${job2.id}: ${job2.status}${job2.error ? ` \u2014 ${job2.error}` : ""}`);
      await s.refresh();
      await s.loadNodeJobHistory(nodeId);
    } catch (e) {
      s.setNotice(e?.message || "Teardown failed");
    }
  },

  getOnboardingActionLabel(action) {
    if (action === "apply-aws-general-preset") return "Apply AWS General Preset";
    if (action === "apply-aws-gpu-preset") return "Apply AWS GPU Preset";
    if (action === "apply-local-preset") return "Apply Local Preset";
    if (action === "run-validation") return "Run Validation";
    return action;
  },

  buildEventsPath() {
    const params = new URLSearchParams();
    params.set("limit", String(s.eventLimit));
    if (s.eventCategoryFilter !== "all") params.set("category", s.eventCategoryFilter);
    if (s.eventLevelFilter !== "all") params.set("level", s.eventLevelFilter);
    if (s.eventSearch.trim()) params.set("search", s.eventSearch.trim());
    return `/api/events?${params.toString()}`;
  },

  /**
   * Cluster / inventory core only — no Topology/Policy/SRE/Audit bulk APIs.
   * Used by cluster page, deploy, discover, and auth bootstrap so cluster UX
   * is not coupled to advanced product modules.
   */
  async refreshClusterInventory() {
    // Cluster core + observability only. Never Topology/Policy/SRE/Audit bulk APIs.
    const [
      catalogNext,
      clustersNext,
      nodesNext,
      servicesNext,
      eventsNext,
      dashboardSummaryNext,
      observabilityNext,
    ] = await Promise.all([
      api("/api/catalog/services"),
      api("/api/clusters"),
      api("/api/nodes"),
      api("/api/services"),
      api(`/api/events?limit=${String(s.eventLimit || 120)}`),
      api("/api/dashboard/summary").catch(() => s.dashboardSummary || null),
      // Observability is part of cluster DevOps surface; soft-fail so inventory still loads
      api("/api/observability/pipeline").catch(() => s.observabilityPipeline || null),
    ]);
    s.setCatalog(catalogNext);
    s.setClusters(clustersNext);
    s.setNodes(nodesNext);
    s.setServices(servicesNext);
    s.setEvents(eventsNext);
    if (dashboardSummaryNext != null) s.setDashboardSummary(dashboardSummaryNext);
    if (observabilityNext != null) s.setObservabilityPipeline(observabilityNext);

    // Sync selection: drop stale ids only — do not auto-pick first service (cPlatform-like)
    if (s.selectedCluster) {
      const syncedCluster = clustersNext.find((cluster) => cluster.id === s.selectedCluster.id);
      if (syncedCluster) s.setSelectedCluster(syncedCluster);
      else s.setSelectedCluster(null);
    }
    if (s.selectedNode) {
      const syncedNode = nodesNext.find((node) => node.id === s.selectedNode.id);
      if (syncedNode) s.setSelectedNode(syncedNode);
      else {
        s.setSelectedNode(null);
        s.setNodeConnection?.(null);
        s.setNodeMetrics?.(null);
        s.setNodeOnboarding?.(null);
      }
    }
    if (s.selectedService) {
      const syncedService = servicesNext.find((service) => service.id === s.selectedService.id);
      if (syncedService) s.setSelectedService(syncedService);
      else {
        s.setSelectedService(null);
        s.setServiceSummary?.(null);
        s.setServiceReleaseTimeline?.(null);
      }
    }
    if (s.selectedCluster) {
      api(`/api/clusters/${s.selectedCluster.id}/summary`).then(s.setClusterSummary).catch(console.error);
      s.loadClusterOperations?.(s.selectedCluster.id)?.catch?.(console.error);
    }
    if (s.selectedNode) {
      api(`/api/nodes/${s.selectedNode.id}/summary`).then(s.setNodeSummary).catch(console.error);
      s.loadNodeConnection?.(s.selectedNode.id)?.catch?.(console.error);
      s.loadNodeJobHistory?.(s.selectedNode.id)?.catch?.(console.error);
    }
    return {
      clusters: clustersNext,
      nodes: nodesNext,
      services: servicesNext,
    };
  },

  /**
   * Advanced product modules only — Topology / Policy / Reliability / Audit / SRE lists.
   * Loaded when those pages open or when full refresh is requested. Never required for cluster ops.
   */
  async refreshAdvancedInventory() {
    const [
      topologyNext,
      checksNext,
      findingsNext,
      incidentsNext,
      runbooksNext,
      slosNext,
      capacityNext,
      secretsNext,
      maintenanceNext,
      auditExportsNext,
      coverageNext,
      lifecycleAuditNext,
      forceApprovalsNext,
      releaseApprovalsNext,
    ] = await Promise.all([
      api("/api/topology").catch(() => s.topology || null),
      api("/api/monitoring/checks").catch(() => s.checks || []),
      api("/api/policy/findings").catch(() => s.findings || []),
      api("/api/incidents").catch(() => s.incidents || []),
      api("/api/runbooks/executions").catch(() => s.runbooks || []),
      api("/api/slo/reports").catch(() => s.slos || []),
      api("/api/capacity/reports").catch(() => s.capacity || null),
      api("/api/secrets").catch(() => s.secrets || []),
      api("/api/maintenance").catch(() => s.maintenance || []),
      api("/api/audit/exports").catch(() => s.auditExports || []),
      api("/api/capabilities/coverage").catch(() => s.coverage || null),
      api("/api/lifecycle/audit?hours=72").catch(() => s.lifecycleAudit || null),
      api("/api/lifecycle/force-approvals?limit=30").catch(() => s.forceApprovals || []),
      api("/api/release-approvals?limit=30").catch(() => s.releaseApprovals || []),
    ]);
    if (topologyNext != null) s.setTopology?.(topologyNext);
    s.setChecks?.(checksNext);
    s.setFindings?.(findingsNext);
    s.setIncidents?.(incidentsNext);
    s.setRunbooks?.(runbooksNext);
    s.setSlos?.(slosNext);
    s.setCapacity?.(capacityNext);
    s.setSecrets?.(secretsNext);
    s.setMaintenance?.(maintenanceNext);
    s.setAuditExports?.(auditExportsNext);
    s.setCoverage?.(coverageNext);
    s.setLifecycleAudit?.(lifecycleAuditNext);
    s.setForceApprovals?.(forceApprovalsNext);
    s.setReleaseApprovals?.(releaseApprovalsNext);
  },

  /**
   * Default refresh: cluster core always.
   * Advanced modules (topology/policy/sre/audit) ONLY when those pages are open or options.full.
   * Cluster ops path never blocks on advanced bulk loads.
   */
  async refresh(options = {}) {
    const view = s.activeView || "clusters";
    const advancedViews = ["topology", "policy", "audit", "reliability"];
    const full =
      options.full === true ||
      options.mode === "full" ||
      advancedViews.includes(view);
    await s.refreshClusterInventory();
    if (full) {
      await s.refreshAdvancedInventory();
    }
    // Optional dTrain overview (cluster-adjacent, not topology)
    if (typeof s.setDtrainOverview === "function") {
      api("/api/dtrain/overview").then(s.setDtrainOverview).catch(() => {});
    }
  },

  async selectCluster(cluster) {
    if (!cluster) return;
    s.setSelectedCluster(cluster);
    s.setSelectedService(null);
    s.setServiceSummary?.(null);
    s.setServiceMetrics?.(null);
    s.setServiceReleaseTimeline?.(null);
    // cP edge: drop stale node if it is not in this cluster
    const clusterNodes = (s.nodes || []).filter((n) => n.cluster_id === cluster.id);
    const keep = s.selectedNode && clusterNodes.some((n) => n.id === s.selectedNode.id) ? s.selectedNode : null;
    if (!keep) {
      s.setSelectedNode(null);
      s.setNodeSummary?.(null);
      s.setNodeConnection?.(null);
      s.setNodeJobHistory?.(null);
      s.setNodeMetrics?.(null);
      s.setNodeOnboarding?.(null);
      s.setNodeLiveStatus?.(null);
    }
    try {
      const summary = await api(`/api/clusters/${cluster.id}/summary`);
      // Ignore late responses if selection changed
      if (s.selectedCluster?.id !== cluster.id) return;
      s.setClusterSummary(summary);
      if (keep) {
        await s.selectNode(keep);
      } else {
        // cP edge: open first reachable node so detail pane is not empty forever
        const firstReachable = clusterNodes.find(
          (n) => String(n.status || "").toLowerCase() !== "unreachable"
        );
        if (firstReachable) {
          await s.selectNode(firstReachable);
        }
      }
      s.loadClusterOperations?.(cluster.id)?.catch?.(() => {});
    } catch (error) {
      s.setNotice(`Failed to load cluster summary: ${error.message}`);
    }
  },

  async selectNode(node) {
    if (!node) {
      s.setSelectedNode(null);
      return;
    }
    // cP edge: workspace race token — ignore late loads when user switches nodes quickly
    const token = (s._nodeWorkspaceToken = Number(s._nodeWorkspaceToken || 0) + 1);
    s.setSelectedNode(node);
    try {
      const summary = await api(`/api/nodes/${node.id}/summary`);
      if (token !== s._nodeWorkspaceToken || s.selectedNode?.id !== node.id) return;
      s.setNodeSummary(summary);
      await Promise.all([
        s.loadNodeConnection?.(node.id),
        s.loadNodeJobHistory?.(node.id),
        s.loadNodeMetrics?.(node.id),
        s.loadNodeOnboarding?.(node.id),
      ]);
      if (token !== s._nodeWorkspaceToken || s.selectedNode?.id !== node.id) return;
    } catch (error) {
      if (token !== s._nodeWorkspaceToken) return;
      s.setNotice(`Failed to load node summary: ${error.message}`);
    }
  },

  async focusServiceInCluster(serviceId) {
    const service = s.services.find((item) => item.id === serviceId);
    if (!service) {
      s.setNotice("Service not found in current topology.");
      return;
    }
    const node = s.nodes.find((item) => item.id === service.node_id);
    const cluster = node ? s.clusters.find((item) => item.id === node.cluster_id) : null;
    if (cluster) {
      s.setSelectedCluster(cluster);
    }
    if (node) {
      await s.selectNode(node);
    }
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
  },

  servicePortsLabel(service) {
    try {
      const cfg = JSON.parse(service.config_json || "{}");
      const ports = cfg.ports || cfg.published_ports || cfg.host_ports || [];
      if (Array.isArray(ports) && ports.length > 0) {
        return ports.map((p) => typeof p === "string" || typeof p === "number" ? String(p) : p.host || p.published || p.port || "").filter(Boolean).slice(0, 3).join(", ");
      }
    } catch {
    }
    return "\u2014";
  }
  };
}
