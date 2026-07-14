// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
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
    try {
      s.setNotice(`Discovering infrastructure on node ${nodeId}\u2026`);
      const result = await api(`/api/nodes/${nodeId}/discover`, { method: "POST" });
      const summary =
        result?.summary ||
        result?.message ||
        `Discover: scanned ${result?.containers_scanned ?? "?"} · adopted ${result?.adopted_count ?? 0}`;
      s.setNotice(summary);
      await s.refresh();
      await s.loadNodeJobHistory(nodeId);
      await s.refreshNodeLiveStatus(nodeId);
    } catch (e) {
      s.setNotice(e?.message || "Discover failed");
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

  async refresh() {
    const [
      catalogNext,
      clustersNext,
      nodesNext,
      servicesNext,
      topologyNext,
      eventsNext,
      checksNext,
      findingsNext,
      incidentsNext,
      runbooksNext,
      slosNext,
      dashboardSummaryNext,
      observabilityNext,
      capacityNext,
      secretsNext,
      maintenanceNext,
      auditExportsNext,
      coverageNext,
      lifecycleAuditNext,
      forceApprovalsNext,
      releaseApprovalsNext
    ] = await Promise.all([
      api("/api/catalog/services"),
      api("/api/clusters"),
      api("/api/nodes"),
      api("/api/services"),
      api("/api/topology"),
      api(s.buildEventsPath()),
      api("/api/monitoring/checks"),
      api("/api/policy/findings"),
      api("/api/incidents"),
      api("/api/runbooks/executions"),
      api("/api/slo/reports"),
      api("/api/dashboard/summary"),
      api("/api/observability/pipeline"),
      api("/api/capacity/reports"),
      api("/api/secrets"),
      api("/api/maintenance"),
      api("/api/audit/exports"),
      api("/api/capabilities/coverage"),
      api("/api/lifecycle/audit?hours=72"),
      api("/api/lifecycle/force-approvals?limit=30"),
      api("/api/release-approvals?limit=30")
    ]);
    s.setCatalog(catalogNext);
    s.setClusters(clustersNext);
    s.setNodes(nodesNext);
    s.setServices(servicesNext);
    s.setTopology(topologyNext);
    s.setEvents(eventsNext);
    s.setChecks(checksNext);
    s.setFindings(findingsNext);
    s.setIncidents(incidentsNext);
    s.setRunbooks(runbooksNext);
    s.setSlos(slosNext);
    s.setDashboardSummary(dashboardSummaryNext);
    s.setObservabilityPipeline(observabilityNext);
    s.setCapacity(capacityNext);
    s.setSecrets(secretsNext);
    s.setMaintenance(maintenanceNext);
    s.setAuditExports(auditExportsNext);
    s.setCoverage(coverageNext);
    s.setLifecycleAudit(lifecycleAuditNext);
    s.setForceApprovals(forceApprovalsNext);
    s.setReleaseApprovals(releaseApprovalsNext);
    if (s.selectedCluster) {
      const syncedCluster = clustersNext.find((cluster) => cluster.id === s.selectedCluster.id);
      if (syncedCluster) s.setSelectedCluster(syncedCluster);
      else s.setSelectedCluster(null);
    }
    if (s.selectedNode) {
      const syncedNode = nodesNext.find((node) => node.id === s.selectedNode.id);
      if (syncedNode) s.setSelectedNode(syncedNode);
      else s.setSelectedNode(null);
    }
    if (s.selectedService) {
      const syncedService = servicesNext.find((service) => service.id === s.selectedService.id);
      if (syncedService) s.setSelectedService(syncedService);
      else {
        s.setSelectedService(null);
        s.setServiceSummary(null);
        s.setServiceReleaseTimeline(null);
      }
    }
    if (clustersNext.length > 0 && !s.selectedCluster) {
      const defaultCluster = clustersNext[0];
      s.setSelectedCluster(defaultCluster);
      api(`/api/clusters/${defaultCluster.id}/summary`).then(s.setClusterSummary).catch(console.error);
      s.loadClusterOperations(defaultCluster.id).catch(console.error);
    } else if (s.selectedCluster) {
      api(`/api/clusters/${s.selectedCluster.id}/summary`).then(s.setClusterSummary).catch(console.error);
      s.loadClusterOperations(s.selectedCluster.id).catch(console.error);
    } else {
      s.setClusterOperations(null);
    }
    if (nodesNext.length > 0 && !s.selectedNode) {
      const defaultNode = nodesNext[0];
      s.setSelectedNode(defaultNode);
      api(`/api/nodes/${defaultNode.id}/summary`).then(s.setNodeSummary).catch(console.error);
      s.loadNodeConnection(defaultNode.id).catch(console.error);
      s.loadNodeMetrics(defaultNode.id).catch(console.error);
      s.loadNodeOnboarding(defaultNode.id).catch(console.error);
    } else if (s.selectedNode) {
      api(`/api/nodes/${s.selectedNode.id}/summary`).then(s.setNodeSummary).catch(console.error);
      s.loadNodeConnection(s.selectedNode.id).catch(console.error);
      s.loadNodeMetrics(s.selectedNode.id).catch(console.error);
      s.loadNodeOnboarding(s.selectedNode.id).catch(console.error);
    } else {
      s.setNodeConnection(null);
      s.setNodeMetrics(null);
      s.setNodeOnboarding(null);
    }
    api("/api/dtrain/overview").then(s.setDtrainOverview).catch(console.error);
    if (!s.selectedService && servicesNext.length) {
      s.setSelectedService(servicesNext[0]);
      s.loadServiceCapabilities(servicesNext[0].id);
      s.loadServiceSummary(servicesNext[0].id);
      s.loadServiceReleaseTimeline(servicesNext[0].id);
      s.loadServiceMetrics(servicesNext[0].id);
    } else if (s.selectedService) {
      s.loadServiceCapabilities(s.selectedService.id);
      s.loadServiceSummary(s.selectedService.id);
      s.loadServiceReleaseTimeline(s.selectedService.id);
      s.loadServiceMetrics(s.selectedService.id);
    } else {
      s.setServiceSummary(null);
      s.setServiceReleaseTimeline(null);
      s.setServiceMetrics(null);
    }
  },

  async selectCluster(cluster) {
    setSelectedCluster(cluster);
    s.setSelectedService(null);
    s.setServiceSummary(null);
    s.setServiceMetrics(null);
    s.setServiceReleaseTimeline(null);
    try {
      const summary = await api(`/api/clusters/${cluster.id}/summary`);
      s.setClusterSummary(summary);
      const clusterNodes = s.nodes.filter((n) => n.cluster_id === cluster.id);
      if (clusterNodes.length > 0) {
        const keep = s.selectedNode && clusterNodes.some((n) => n.id === s.selectedNode.id) ? s.selectedNode : clusterNodes[0];
        await s.selectNode(keep);
      } else {
        s.setSelectedNode(null);
        s.setNodeSummary(null);
        s.setNodeConnection(null);
        s.setNodeJobHistory(null);
        s.setNodeMetrics(null);
        s.setNodeOnboarding(null);
      }
    } catch (error) {
      s.setNotice(`Failed to load cluster summary: ${error.message}`);
    }
  },

  async selectNode(node) {
    setSelectedNode(node);
    try {
      const summary = await api(`/api/nodes/${node.id}/summary`);
      s.setNodeSummary(summary);
      await s.loadNodeConnection(node.id);
      await s.loadNodeJobHistory(node.id);
      await s.loadNodeMetrics(node.id);
      await s.loadNodeOnboarding(node.id);
    } catch (error) {
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
