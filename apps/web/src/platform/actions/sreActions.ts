// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createSreActions(s: any) {
  return {
  async registerSecret(service) {
    const secret = await api("/api/secrets", {
      method: "POST",
      body: JSON.stringify({
        service_id: service.id,
        key: `${service.service_key.toUpperCase().replace(/-/g, "_")}_TOKEN`,
        scope: "service",
        rotation_interval_days: 90
      })
    });
    s.setSecrets((current) => [secret, ...current]);
    s.setNotice(`Registered masked secret ${secret.key}`);
    await s.refresh();
  },

  async rotateSecret(secret) {
    const rotated = await api(`/api/secrets/${secret.id}/rotate`, { method: "POST" });
    s.setSecrets((current) => current.map((item) => item.id === rotated.id ? rotated : item));
    s.setNotice(`Rotated ${rotated.key}`);
    await s.refresh();
  },

  async scheduleMaintenance(service) {
    const starts = new Date(Date.now() + 60 * 60 * 1e3);
    const ends = new Date(Date.now() + 2 * 60 * 60 * 1e3);
    const window2 = await api("/api/maintenance", {
      method: "POST",
      body: JSON.stringify({
        service_id: service?.id ?? s.selectedService?.id ?? null,
        node_id: service?.node_id ?? s.selectedService?.node_id ?? s.selectedNode?.id ?? s.nodes[0]?.id ?? null,
        title: `Maintenance for ${service?.name ?? s.selectedService?.name ?? "platform"}`,
        starts_at: starts.toISOString(),
        ends_at: ends.toISOString(),
        impact: "Scheduled maintenance window"
      })
    });
    s.setMaintenance((current) => [window2, ...current]);
    s.setNotice(`Scheduled maintenance ${window2.id}`);
    await s.refresh();
  },

  async completeMaintenance(window2) {
    const completed = await api(`/api/maintenance/${window2.id}/complete`, { method: "POST" });
    s.setMaintenance((current) => current.map((item) => item.id === completed.id ? completed : item));
    s.setNotice(`Completed maintenance ${completed.id}`);
    await s.refresh();
  },

  async createAuditExport() {
    const exportRecord = await api("/api/audit/exports", { method: "POST" });
    s.setNotice(`Audit export ready: ${exportRecord.artifact_path}`);
    await s.refresh();
  },

  async requestReleaseSafety(service, version, image) {
    return api(
      `/api/services/${service.id}/releases/safety?version=${encodeURIComponent(version)}&image=${encodeURIComponent(image)}`
    );
  },

  openReleaseApprovalModal(service, version, image, safety) {
    s.setReleaseApprovalModal({
      visible: true,
      serviceId: service.id,
      serviceName: service.name,
      version,
      image,
      safety,
      reason: "",
      requestedBy: "platform-operator",
      approvalId: "",
      approver: "platform-admin",
      decisionNote: "",
      error: ""
    });
  },

  async createReleaseApprovalRequest() {
    const reason = s.releaseApprovalModal.reason.trim();
    if (reason.length < 12) {
      s.setReleaseApprovalModal((current) => ({ ...current, error: "Approval reason must be at least 12 characters." }));
      return;
    }
    const approval = await api("/api/release-approvals", {
      method: "POST",
      body: JSON.stringify({
        service_id: s.releaseApprovalModal.serviceId,
        target_version: s.releaseApprovalModal.version,
        target_image: s.releaseApprovalModal.image,
        reason,
        requested_by: s.releaseApprovalModal.requestedBy.trim() || "platform-operator",
        ttl_hours: 4
      })
    });
    s.setReleaseApprovalModal((current) => ({ ...current, approvalId: String(approval.id), error: "" }));
    s.setNotice(`Release approval #${approval.id} created (${approval.status}).`);
    await s.refresh();
  },

  async approveReleaseApprovalRequest() {
    const approvalId = Number(s.releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setReleaseApprovalModal((current) => ({ ...current, error: "Enter a valid approval id before approving." }));
      return;
    }
    const approval = await api(`/api/release-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: s.releaseApprovalModal.approver.trim() || "platform-admin",
        decision_note: s.releaseApprovalModal.decisionNote.trim(),
        status: "approved"
      })
    });
    s.setReleaseApprovalModal((current) => ({ ...current, error: "" }));
    s.setNotice(`Release approval #${approval.id} is now ${approval.status}.`);
    await s.refresh();
  },

  async revokeReleaseApprovalRequest() {
    const approvalId = Number(s.releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setReleaseApprovalModal((current) => ({ ...current, error: "Enter a valid approval id before revoking." }));
      return;
    }
    const approval = await api(`/api/release-approvals/${approvalId}/revoke`, {
      method: "POST",
      body: JSON.stringify({
        actor: s.releaseApprovalModal.approver.trim() || "platform-admin",
        note: s.releaseApprovalModal.decisionNote.trim()
      })
    });
    s.setReleaseApprovalModal((current) => ({ ...current, error: "" }));
    s.setNotice(`Release approval #${approval.id} is now ${approval.status}.`);
    await s.refresh();
  },

  async confirmApprovedRelease() {
    const approvalId = Number(s.releaseApprovalModal.approvalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setReleaseApprovalModal((current) => ({ ...current, error: "Provide an approved approval id before releasing." }));
      return;
    }
    const service = s.services.find((item) => item.id === s.releaseApprovalModal.serviceId);
    if (!service) {
      s.setReleaseApprovalModal((current) => ({ ...current, error: "Selected service is no longer available." }));
      return;
    }
    const release = await api(`/api/services/${service.id}/releases`, {
      method: "POST",
      body: JSON.stringify({
        version: s.releaseApprovalModal.version,
        image: s.releaseApprovalModal.image,
        strategy: "rolling",
        notes: "UI-triggered governed release",
        approval_id: approvalId
      })
    });
    s.setReleases((current) => [release, ...current]);
    s.setReleaseApprovalModal((current) => ({ ...current, visible: false, error: "" }));
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
    s.setNotice(`Governed release ${release.version} ${release.status}`);
    await s.refresh();
  },

  async releaseService(service) {
    const version = `v${(/* @__PURE__ */ new Date()).toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
    const safety = await s.requestReleaseSafety(service, version, service.image);
    if (safety.risky) {
      s.openReleaseApprovalModal(service, version, service.image, safety);
      s.setNotice(`Release for ${service.name} requires approval.`);
      return;
    }
    const release = await api(`/api/services/${service.id}/releases`, {
      method: "POST",
      body: JSON.stringify({
        version,
        image: service.image,
        strategy: "rolling",
        notes: "UI-triggered portfolio release"
      })
    });
    s.setReleases((current) => [release, ...current]);
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
    s.setNotice(`Release ${release.version} ${release.status}`);
    await s.refresh();
  },

  async loadReleases(service) {
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
    const nextReleases = await api(`/api/services/${service.id}/releases`);
    s.setReleases(nextReleases);
    s.setNotice(`Loaded ${nextReleases.length} releases for ${service.name}`);
  },

  async rollbackRelease(release) {
    const nextJob = await api(`/api/releases/${release.id}/rollback`, { method: "POST" });
    s.setJob(nextJob);
    s.setNotice(`Rollback ${nextJob.status}`);
    if (s.selectedService) {
      await s.loadServiceSummary(s.selectedService.id);
      await s.loadServiceReleaseTimeline(s.selectedService.id);
      await s.loadServiceMetrics(s.selectedService.id);
    }
    await s.refresh();
  },

  async planService(service) {
    const node = s.nodes.find((item) => item.id === service.node_id);
    if (!node) return;
    const nextPlan = await api(`/api/nodes/${node.id}/deployment-plan/${service.service_key}`);
    s.setPlan(nextPlan);
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
    s.setNotice(nextPlan.summary);
  },

  async planPlacement(serviceKey) {
    const targetKey = serviceKey || s.selectedPlacementServiceKey || s.selectedService?.service_key;
    if (!targetKey) {
      s.setNotice("Select a service key for placement recommendations.");
      return;
    }
    const params = new URLSearchParams();
    if (s.preferNodeId.trim()) params.set("prefer_node_id", s.preferNodeId.trim());
    if (s.avoidNodeIds.trim()) params.set("avoid_node_ids", s.avoidNodeIds.trim());
    if (s.antiAffinityKey.trim()) params.set("anti_affinity_service_key", s.antiAffinityKey.trim());
    if (s.requireHealthyNodes) params.set("require_healthy", "true");
    if (s.spreadSubsystem) params.set("spread_subsystem", "true");
    const nextPlacement = await api(
      `/api/services/placement/recommendations/${targetKey}?${params.toString()}`
    );
    s.setPlacement(nextPlacement);
    s.setSelectedPlacementServiceKey(targetKey);
    const best = nextPlacement.candidates[0];
    if (best) {
      s.setNotice(`Placement advisor: best node for ${targetKey} is ${best.node_name} (score ${best.score}).`);
    }
  },

  async deployFromPlacement(serviceKey) {
    const targetKey = serviceKey || s.selectedPlacementServiceKey || s.selectedService?.service_key;
    if (!targetKey) {
      s.setNotice("Select a service key for placement auto-deploy.");
      return;
    }
    const params = new URLSearchParams();
    if (s.preferNodeId.trim()) params.set("prefer_node_id", s.preferNodeId.trim());
    if (s.avoidNodeIds.trim()) params.set("avoid_node_ids", s.avoidNodeIds.trim());
    if (s.antiAffinityKey.trim()) params.set("anti_affinity_service_key", s.antiAffinityKey.trim());
    if (s.requireHealthyNodes) params.set("require_healthy", "true");
    if (s.spreadSubsystem) params.set("spread_subsystem", "true");
    if (!s.autoInstallDependencies) params.set("auto_install_dependencies", "false");
    if (s.allowPlacementCapacityRisk) params.set("allow_capacity_risk", "true");
    const result = await api(
      `/api/services/placement/deploy/${targetKey}?${params.toString()}`,
      { method: "POST" }
    );
    s.setNotice(result.summary);
    await s.refresh();
    const nextServices = await api(`/api/services?node_id=${result.node_id}`);
    const deployed = nextServices.find((service) => service.id === result.target_service_id);
    if (deployed) {
      s.setSelectedService(deployed);
      await s.loadServiceCapabilities(deployed.id);
      await s.loadServiceMetrics(deployed.id);
      await s.loadDiagnostics(deployed);
      await s.loadConfig(deployed);
    }
    await s.planPlacement(targetKey);
  },

  async loadArtifact(kind) {
    const node = s.selectedNode || s.nodes[0];
    if (!node) {
      s.setNotice("No node selected for artifact generation");
      return;
    }
    const nextArtifact = await api(`/api/nodes/${node.id}/artifacts/${kind}`);
    s.setArtifact(nextArtifact);
    s.setNotice(`Generated ${nextArtifact.name}`);
  },

  async runPolicyScan() {
    const nextFindings = await api("/api/policy/scan", { method: "POST" });
    s.setFindings(nextFindings);
    s.setNotice(`Policy scan found ${nextFindings.length} open findings`);
    await s.refresh();
  },

  async evaluateSlo() {
    const reports = await api("/api/slo/evaluate", { method: "POST" });
    s.setSlos(reports);
    s.setNotice(`Evaluated ${reports.length} SLO reports`);
    await s.refresh();
  },

  async generateCapacity() {
    const node = s.selectedNode || s.nodes[0];
    if (!node) {
      s.setNotice("No node available for capacity report");
      return;
    }
    const report = await api(`/api/nodes/${node.id}/capacity`, { method: "POST" });
    s.setCapacity((current) => [report, ...current]);
    s.setNotice(`Capacity ${report.status}: ${report.memory_reserved_mb} MB reserved`);
    await s.refresh();
  },

  async openIncident(service) {
    const payload = {
      service_id: service?.id ?? s.selectedService?.id ?? null,
      node_id: service?.node_id ?? s.selectedService?.node_id ?? s.selectedNode?.id ?? s.nodes[0]?.id ?? null,
      title: `Investigate ${service?.name ?? s.selectedService?.name ?? "platform"} health`,
      severity: "sev3",
      summary: "UI-triggered reliability review"
    };
    const incident = await api("/api/incidents", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    s.setIncidents((current) => [incident, ...current]);
    s.setNotice(`Opened incident ${incident.id}`);
    await s.refresh();
  },

  async runIncidentRunbook(incident, runbookKey = "restart-service") {
    const runbook = await api(`/api/incidents/${incident.id}/runbook/${runbookKey}`, {
      method: "POST"
    });
    s.setRunbooks((current) => [runbook, ...current]);
    s.setNotice(`Runbook ${runbook.runbook_key} ${runbook.status}`);
    await s.refresh();
  },

  async resolveIncident(incident) {
    const resolved = await api(`/api/incidents/${incident.id}/resolve`, { method: "POST" });
    s.setIncidents((current) => current.map((item) => item.id === resolved.id ? resolved : item));
    s.setNotice(`Resolved incident ${resolved.id}`);
    await s.refresh();
  },

  async planSubsystem(subsystemName) {
    const node = s.selectedNode || s.nodes[0];
    if (!node) {
      s.setNotice("Please select or seed a node first");
      return;
    }
    try {
      const planData = await api(`/api/nodes/${node.id}/subsystems/${subsystemName}/rollout-plan`);
      s.setSubsystemPlan(planData);
      s.setSelectedSubsystem(subsystemName);
      s.setNotice(`Generated rollout plan for ${subsystemName}`);
    } catch (error) {
      s.setNotice(`Subsystem planning failed: ${error.message}`);
    }
  },

  async deploySubsystem(subsystemName) {
    const node = s.selectedNode || s.nodes[0];
    if (!node) return;
    try {
      s.setNotice(`Triggering deployment for subsystem ${subsystemName}...`);
      const result = await api(`/api/nodes/${node.id}/subsystems/${subsystemName}/deploy`, { method: "POST" });
      s.setNotice(`Subsystem deployment triggered: ${result.summary || "Success"}`);
      await s.refresh();
      await s.planSubsystem(subsystemName);
    } catch (error) {
      s.setNotice(`Deployment failed: ${error.message}`);
    }
  },

  async validateNode(nodeId) {
    try {
      s.setNotice(`Running configuration validation for node ${nodeId}...`);
      const result = await api(`/api/nodes/${nodeId}/validate`, { method: "POST" });
      s.setJob(result);
      s.setNotice(`Node validation job #${result.id}: ${result.status}`);
      await s.refresh();
      await s.loadNodeJobHistory(nodeId);
      // Poll job briefly then refresh connection (facts merge + probe)
      if (result?.id) {
        for (let i = 0; i < 20; i++) {
          await new Promise((r) => setTimeout(r, 1500));
          try {
            const job2 = await api(`/api/jobs/${result.id}`);
            s.setJob(job2);
            if (job2.status === "success" || job2.status === "failed" || job2.status === "cancelled") {
              s.setNotice(
                job2.status === "success"
                  ? `Node validation succeeded (job #${job2.id})`
                  : `Node validation ${job2.status}${job2.error ? `: ${String(job2.error).slice(0, 160)}` : ""}`
              );
              break;
            }
          } catch {
            break;
          }
        }
      }
      await s.loadNodeConnection?.(nodeId);
      await s.loadNodeOnboarding?.(nodeId);
      await s.refresh();
    } catch (error) {
      s.setNotice(`Validation failed: ${error.message}`);
    }
  }
  };
}
