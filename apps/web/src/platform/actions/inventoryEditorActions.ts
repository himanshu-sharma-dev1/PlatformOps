// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
import { withPending, serviceDeleteBusyKey } from "../ux/clusterUx";
export function createInventoryEditorActions(s: any) {
  return {
  openClusterCreate() {
    s.setClusterEditor({
      visible: true,
      mode: "create",
      clusterId: null,
      step: 1,
      saving: false,
      replaceRepoSecret: true,
      replaceRegistrySecret: true,
      repoTest: { state: "idle", message: "" },
      registryTest: { state: "idle", message: "" },
      draft: {
        name: "",
        region: "local",
        environment: "development",
        description: "",
        repo_type: "github",
        repo_url: "",
        repo_branch: "main",
        repo_path: "",
        repo_auth: "pat",
        repo_token: "",
        registry_type: "dockerhub",
        registry_url: "",
        registry_namespace: "",
        registry_auth: "password",
        registry_user: "",
        registry_password: "",
      },
      error: ""
    });
  },

  openClusterEdit(cluster) {
    s.setClusterEditor({
      visible: true,
      mode: "edit",
      clusterId: cluster.id,
      step: 1,
      saving: false,
      replaceRepoSecret: false,
      replaceRegistrySecret: false,
      repoTest: { state: "idle", message: "" },
      registryTest: { state: "idle", message: "" },
      draft: {
        name: cluster.name,
        region: cluster.region,
        environment: cluster.environment,
        description: cluster.description || "",
        repo_type: cluster.repo_type || "github",
        repo_url: cluster.repo_url || "",
        repo_branch: cluster.repo_branch || "main",
        repo_path: cluster.repo_path || "",
        repo_auth: cluster.repo_auth || "pat",
        repo_token: "",
        registry_type: cluster.registry_type || "dockerhub",
        registry_url: cluster.registry_url || "",
        registry_namespace: cluster.registry_namespace || "",
        registry_auth: cluster.registry_auth || "password",
        registry_user: cluster.registry_user || "",
        registry_password: "",
      },
      error: ""
    });
  },

  setClusterEditorStep(step) {
    const next = Math.max(1, Math.min(4, Number(step) || 1));
    s.setClusterEditor((current) => ({ ...current, step: next, error: "" }));
  },

  advanceClusterEditorStep() {
    const step = s.clusterEditor.step || 1;
    const draft = s.clusterEditor.draft || {};
    if (step === 1) {
      if (!String(draft.name || "").trim()) {
        s.setClusterEditor((c) => ({ ...c, error: "Cluster name is required." }));
        return;
      }
    }
    if (step < 4) {
      s.setClusterEditor((c) => ({ ...c, step: step + 1, error: "" }));
    }
  },

  async saveClusterEditor() {
    const mode = s.clusterEditor.mode || "create";
    const id = s.clusterEditor.clusterId || "new";
    // cP withPending on create/save cluster
    return withPending(`save-cluster:${mode}:${id}`, async () => {
      try {
        const draft = s.clusterEditor.draft;
        const name = draft.name.trim();
        if (!name) {
          s.setClusterEditor((current) => ({ ...current, error: "Cluster name is required.", step: 1, saving: false }));
          return;
        }
        s.setClusterEditor((current) => ({ ...current, saving: true, error: "" }));
        s.setActionBusy?.((b) => ({ ...b, save: true }));
        if (s.clusterEditor.mode === "create") {
          const created = await api("/api/clusters", {
            method: "POST",
            body: JSON.stringify({
              name,
              region: draft.region.trim() || "local",
              environment: draft.environment.trim() || "development",
              repo_type: draft.repo_type,
              repo_url: draft.repo_url,
              repo_branch: draft.repo_branch || "main",
              repo_token: draft.repo_token,
              registry_type: draft.registry_type,
              registry_url: draft.registry_url,
              registry_user: draft.registry_user,
              registry_password: draft.registry_password
            })
          });
          s.setClusterEditor((current) => ({ ...current, visible: false, error: "", saving: false }));
          s.setActionBusy?.((b) => ({ ...b, save: false }));
          s.showToast?.(`Created cluster ${created.name}`, "ok") || s.setNotice(`Created cluster ${created.name}`);
          s.setSelectedCluster(created);
          await (s.refreshClusterInventory || s.refresh)();
          return;
        }
        if (!s.clusterEditor.clusterId) {
          s.setClusterEditor((current) => ({ ...current, saving: false }));
          s.setActionBusy?.((b) => ({ ...b, save: false }));
          return;
        }
        const payload = {
          name,
          region: draft.region.trim() || "local",
          environment: draft.environment.trim() || "development",
          repo_type: draft.repo_type,
          repo_url: draft.repo_url,
          repo_branch: draft.repo_branch || "main",
          registry_type: draft.registry_type,
          registry_url: draft.registry_url,
          registry_user: draft.registry_user
        };
        if (draft.repo_token && (s.clusterEditor.replaceRepoSecret || s.clusterEditor.mode === "create")) {
          payload.repo_token = draft.repo_token;
        }
        if (draft.registry_password && (s.clusterEditor.replaceRegistrySecret || s.clusterEditor.mode === "create")) {
          payload.registry_password = draft.registry_password;
        }
        const updated = await api(`/api/clusters/${s.clusterEditor.clusterId}`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
        s.setClusterEditor((current) => ({ ...current, visible: false, error: "", saving: false }));
        s.setActionBusy?.((b) => ({ ...b, save: false }));
        s.setSelectedCluster(updated);
        s.showToast?.(`Updated cluster ${updated.name}`, "ok") || s.setNotice(`Updated cluster ${updated.name}`);
        await (s.refreshClusterInventory || s.refresh)();
      } catch (error) {
        s.setClusterEditor((current) => ({
          ...current,
          error: error.message || "Failed to save cluster.",
          saving: false
        }));
        s.setActionBusy?.((b) => ({ ...b, save: false }));
        s.showToast?.(error.message || "Failed to save cluster.", "err");
      }
    });
  },

  async testClusterRepoConnection() {
    const d = s.clusterEditor.draft;
    s.setClusterEditor((c) => ({ ...c, repoTest: { state: "testing", message: "testing…" } }));
    s.setActionBusy?.((b) => ({ ...b, "test-repo": true }));
    try {
      const res = await api("/api/clusters/test-repo", {
        method: "POST",
        body: JSON.stringify({
          repo_type: d.repo_type,
          repo_url: d.repo_url,
          repo_branch: d.repo_branch || "main",
          repo_token: d.repo_token || null
        })
      });
      const ok = Boolean(res.connected);
      const message = res.message || (ok ? "Repository connection OK" : "Repository check finished");
      s.setClusterEditor((c) => ({
        ...c,
        repoTest: { state: ok ? "ok" : "err", message }
      }));
      s.showToast?.(message, ok ? "ok" : "err") || s.setNotice(message);
    } catch (e) {
      const message = e?.message || "Repository connection failed";
      s.setClusterEditor((c) => ({ ...c, repoTest: { state: "err", message } }));
      s.showToast?.(message, "err") || s.setNotice(message);
    } finally {
      s.setActionBusy?.((b) => ({ ...b, "test-repo": false }));
    }
  },

  async testClusterRegistryConnection() {
    const d = s.clusterEditor.draft;
    s.setClusterEditor((c) => ({ ...c, registryTest: { state: "testing", message: "testing…" } }));
    s.setActionBusy?.((b) => ({ ...b, "test-registry": true }));
    try {
      const res = await api("/api/clusters/test-registry", {
        method: "POST",
        body: JSON.stringify({
          registry_type: d.registry_type,
          registry_url: d.registry_url,
          registry_user: d.registry_user || null,
          registry_password: d.registry_password || null
        })
      });
      const ok = Boolean(res.connected);
      const message = res.message || (ok ? "Registry connection OK" : "Registry check finished");
      s.setClusterEditor((c) => ({
        ...c,
        registryTest: { state: ok ? "ok" : "err", message }
      }));
      s.showToast?.(message, ok ? "ok" : "err") || s.setNotice(message);
    } catch (e) {
      const message = e?.message || "Registry connection failed";
      s.setClusterEditor((c) => ({ ...c, registryTest: { state: "err", message } }));
      s.showToast?.(message, "err") || s.setNotice(message);
    } finally {
      s.setActionBusy?.((b) => ({ ...b, "test-registry": false }));
    }
  },

  async checkPortAndNameAvailability(nodeId, containerName, port) {
    const params = new URLSearchParams();
    if (containerName) params.set("name", containerName);
    if (port != null && !Number.isNaN(Number(port))) params.set("port", String(port));
    return api(
      `/api/nodes/${nodeId}/check-port-and-name?${params.toString()}`
    );
  },

  applyNodePreset(preset) {
    s.setNodePreset(preset);
    s.setNodeEditor((current) => {
      if (!current.visible) return current;
      if (preset === "aws-general") {
        return {
          ...current,
          draft: {
            ...current.draft,
            environment: "aws",
            ssh_user: "ubuntu",
            host: current.draft.host === "localhost" ? "ec2-public-host" : current.draft.host,
            volume_root: current.draft.volume_root.startsWith("/tmp/") ? "/platformops" : current.draft.volume_root,
            docker_network: current.draft.docker_network?.includes("platformops") ? "platformops_prod_network" : current.draft.docker_network
          }
        };
      }
      if (preset === "aws-gpu") {
        return {
          ...current,
          draft: {
            ...current.draft,
            environment: "aws",
            ssh_user: "ubuntu",
            host: current.draft.host === "localhost" || !current.draft.host ? "ec2-gpu-host" : current.draft.host,
            volume_root: current.draft.volume_root.startsWith("/tmp/") ? "/platformops-gpu" : current.draft.volume_root,
            docker_network: "platformops_prod_network",
            gpu: current.draft.gpu === "none" ? "nvidia" : current.draft.gpu,
          }
        };
      }
      return {
        ...current,
        draft: {
          ...current.draft,
          environment: "local",
          ssh_user: "ubuntu",
          volume_root: current.draft.volume_root.startsWith("/platformops") ? "/tmp/platformops" : current.draft.volume_root,
          docker_network: "platformops_prod_network",
        }
      };
    });
  },

  _nodeFactsPayload(draft) {
    return {
      cpu_cores: Number(draft.cpu_cores) || 0,
      memory_gb: Number(draft.memory_gb) || 0,
      storage_gb: Number(draft.storage_gb) || 0,
      gpu: String(draft.gpu ?? "none"),
      os: String(draft.os ?? "linux"),
    };
  },

  _parseNodeFacts(node) {
    try {
      const raw = typeof node?.facts_json === "string" ? JSON.parse(node.facts_json || "{}") : (node?.facts_json || {});
      return {
        cpu_cores: raw.cpu_cores ?? raw.vcpu ?? 4,
        memory_gb: raw.memory_gb ?? raw.memory ?? 16,
        storage_gb: raw.storage_gb ?? raw.storage ?? 100,
        gpu: raw.gpu ?? "none",
        os: raw.os ?? "linux",
      };
    } catch {
      return { cpu_cores: 4, memory_gb: 16, storage_gb: 100, gpu: "none", os: "linux" };
    }
  },

  openNodeCreate() {
    const baseClusterId = s.selectedCluster?.id ?? s.clusters[0]?.id ?? 0;
    // Node create uses the provision drawer only (not the legacy modal)
    s.setNodeEditor({
      visible: false,
      mode: "create",
      nodeId: null,
      draft: {
        cluster_id: baseClusterId,
        name: "",
        host: "",
        ssh_user: "ubuntu",
        ssh_key_path: "",
        ssh_private_key: "",
        environment: "local",
        volume_root: "/tmp/platformops",
        docker_network: "platformops_prod_network",
        status: "unknown",
        cpu_cores: 4,
        memory_gb: 16,
        storage_gb: 100,
        gpu: "none",
        os: "linux",
        provider: "dc",
        ingress_ports: "22, 80, 443, 8080",
      },
      error: ""
    });
    s.setNodePreset("local-default");
    s.setStepperStep?.(1);
    s.setStepperDrawerVisible?.(true);
  },

  openNodeEdit(node) {
    // Prefer methods from this factory when available
    let parsed = {
      cpu_cores: 4, memory_gb: 16, storage_gb: 100, gpu: "none", os: "linux",
    };
    try {
      const raw = typeof node?.facts_json === "string" ? JSON.parse(node.facts_json || "{}") : (node?.facts_json || {});
      parsed = {
        cpu_cores: raw.cpu_cores ?? raw.vcpu ?? 4,
        memory_gb: raw.memory_gb ?? raw.memory ?? 16,
        storage_gb: raw.storage_gb ?? raw.storage ?? 100,
        gpu: raw.gpu ?? "none",
        os: raw.os ?? "linux",
      };
    } catch { /* keep defaults */ }
    const env = String(node.environment || "").toLowerCase();
    const provider = env.includes("aws") || env === "cloud" ? "aws" : env.includes("gcp") || env.includes("google") ? "gcp" : "dc";
    const preset =
      provider === "aws"
        ? String(node.docker_network || "").includes("gpu") || String(parsed.gpu || "").toLowerCase() !== "none"
          ? "aws-gpu"
          : "aws-general"
        : "local-default";
    // Node edit uses the provision drawer only (not the legacy modal)
    s.setNodeEditor({
      visible: false,
      mode: "edit",
      nodeId: node.id,
      draft: {
        cluster_id: node.cluster_id,
        name: node.name,
        host: node.host,
        ssh_user: node.ssh_user,
        ssh_key_path: node.ssh_key_path ?? "",
        ssh_private_key: "",
        environment: node.environment,
        volume_root: node.volume_root,
        docker_network: node.docker_network || "platformops_prod_network",
        status: node.status,
        provider,
        ingress_ports: "22, 80, 443, 8080",
        ...parsed,
      },
      error: ""
    });
    s.setNodePreset(preset);
    // cP edge: Edit node opens the same provision drawer (EDIT badge)
    s.setStepperStep?.(1);
    s.setStepperDrawerVisible?.(true);
  },

  async saveNodeEditor() {
    const mode = s.nodeEditor.mode || "create";
    const id = s.nodeEditor.nodeId || "new";
    // cP withPending add-node / save-node
    return withPending(`save-node:${mode}:${id}`, async () => {
      s.setActionBusy?.((b) => ({ ...b, saveNode: true }));
      try {
        const draft = s.nodeEditor.draft;
        const name = draft.name.trim();
        if (!draft.cluster_id) {
          s.setNodeEditor((current) => ({ ...current, error: "Select a parent cluster." }));
          return null;
        }
        if (!name) {
          s.setNodeEditor((current) => ({ ...current, error: "Node name is required." }));
          return null;
        }
        if (!String(draft.host || "").trim()) {
          s.setNodeEditor((current) => ({ ...current, error: "SSH host/IP is required." }));
          return null;
        }
        const facts = {
          cpu_cores: Number(draft.cpu_cores) || 0,
          memory_gb: Number(draft.memory_gb) || 0,
          storage_gb: Number(draft.storage_gb) || 0,
          gpu: String(draft.gpu ?? "none"),
          os: String(draft.os ?? "linux"),
        };
        if (s.nodeEditor.mode === "create") {
          const created = await api("/api/nodes", {
            method: "POST",
            body: JSON.stringify({
              cluster_id: draft.cluster_id,
              name,
              host: draft.host.trim(),
              ssh_user: draft.ssh_user.trim() || "ubuntu",
              ssh_key_path: draft.ssh_key_path.trim(),
              ssh_private_key: draft.ssh_private_key.trim() || void 0,
              environment: draft.environment.trim() || "local",
              volume_root: draft.volume_root.trim() || "/tmp/platformops",
              docker_network: draft.docker_network.trim() || "platformops_prod_network",
              facts,
            })
          });
          s.setNodeEditor((current) => ({ ...current, visible: false, error: "" }));
          s.setSelectedNode(created);
          s.showToast?.(`Created node ${created.name}`, "ok") || s.setNotice(`Created node ${created.name}`);
          await (s.refreshClusterInventory || s.refresh)();
          return created;
        }
        if (!s.nodeEditor.nodeId) return null;
        const updated = await api(`/api/nodes/${s.nodeEditor.nodeId}`, {
          method: "PUT",
          body: JSON.stringify({
            cluster_id: draft.cluster_id,
            name,
            host: draft.host.trim(),
            ssh_user: draft.ssh_user.trim() || "ubuntu",
            ssh_key_path: draft.ssh_key_path.trim(),
            ssh_private_key: draft.ssh_private_key.trim() || void 0,
            environment: draft.environment.trim() || "local",
            volume_root: draft.volume_root.trim() || "/tmp/platformops",
            docker_network: draft.docker_network.trim() || "platformops_prod_network",
            status: draft.status.trim() || "unknown",
            facts,
          })
        });
        s.setNodeEditor((current) => ({ ...current, visible: false, error: "" }));
        s.setSelectedNode(updated);
        s.showToast?.(`Updated node ${updated.name}`, "ok") || s.setNotice(`Updated node ${updated.name}`);
        await (s.refreshClusterInventory || s.refresh)();
        return updated;
      } catch (error) {
        s.setNodeEditor((current) => ({ ...current, error: error.message || "Failed to save node." }));
        s.showToast?.(error.message || "Failed to save node.", "err");
        return null;
      } finally {
        s.setActionBusy?.((b) => ({ ...b, saveNode: false }));
      }
    });
  },

  async requestDelete(type, id, name, options) {
    const assessKey = `assess-delete-${type}:${id}`;
    return withPending(assessKey, async () => {
      s.setActionBusy?.((b) => ({ ...b, [assessKey]: true, assessDelete: true }));
      try {
        s.setNotice(`Assessing deletion impact for ${name}...`);
        const segment = type === "service" ? "services" : type === "node" ? "nodes" : "clusters";
        const impact = await api(`/api/${segment}/${id}/lifecycle-impact`);
        // cP showNodeDeleteBlocker: when node still has services, surface itemized action blocker first
        const blockedServices =
          type === "node"
            ? impact?.services || impact?.child_services || impact?.blocking_services || []
            : type === "cluster"
              ? impact?.nodes || impact?.blocking_nodes || []
              : [];
        const hardBlock = Boolean(impact?.blocked || impact?.requires_force) && !options?.seedForce;
        if (hardBlock && Array.isArray(blockedServices) && blockedServices.length > 0 && type === "node") {
          s.setActionBlocker?.({
            visible: true,
            eyebrow: "Node has services",
            title: "Node deletion blocked",
            message:
              (impact?.message || "Delete the services first.") +
              ` Remove the mapped services from ${name} before deleting the node.`,
            items: blockedServices.map((svc) => ({
              name: svc.service_name || svc.name || svc.service_id || svc.id || "Service",
              meta: `${svc.service_type || svc.service_key || "service"} · ${svc.deploy_status || svc.status || "mapped"}`,
            })),
            secondaryLabel: "Close",
            secondaryAction: null,
            primaryLabel: "Review impact",
            primaryAction: null,
          });
        }
        s.setDeleteModal({
          visible: true,
          targetType: type,
          targetId: id,
          targetName: name,
          impact,
          force: Boolean(options?.seedForce),
          forceReason: options?.suggestedReason ?? "",
          forceApprovalId: "",
          requestedBy: "platform-operator",
          approver: "platform-admin",
          decisionNote: "",
          approvalStatus: "none"
        });
        s.setNotice("");
      } catch (error) {
        s.showToast?.(`Failed to load deletion safety assessment: ${error.message}`, "err")
          || s.setNotice(`Failed to load deletion safety assessment: ${error.message}`);
      } finally {
        s.setActionBusy?.((b) => ({ ...b, [assessKey]: false, assessDelete: false }));
      }
    });
  },

  async confirmDelete() {
    const { targetType, targetId, targetName, force, forceReason, forceApprovalId } = s.deleteModal;
    if (force && forceReason.trim().length < 12) {
      s.setNotice("Force delete requires a reason of at least 12 characters.");
      return;
    }
    // cP withPending delete-service / delete-node / delete-cluster
    const pendingKey = `delete-${targetType}:${targetId}`;
    const deleteKey = targetType === "service" ? serviceDeleteBusyKey(targetId) : `delete-${targetType}:${targetId}`;
    return withPending(pendingKey, async () => {
      s.setActionBusy?.((b) => ({ ...b, [deleteKey]: true, delete: true }));
      try {
        const reasonParam = force ? `&force_reason=${encodeURIComponent(forceReason.trim())}` : "";
        const approvalParam = force ? `&force_approval_id=${encodeURIComponent(forceApprovalId || "")}` : "";
        let endpoint = "";
        if (targetType === "service") {
          endpoint = `/api/services/${targetId}/delete?force=${force}${reasonParam}${approvalParam}`;
        } else if (targetType === "node") {
          endpoint = `/api/nodes/${targetId}?force=${force}${reasonParam}${approvalParam}`;
        } else if (targetType === "cluster") {
          endpoint = `/api/clusters/${targetId}?force=${force}${reasonParam}${approvalParam}`;
        }
        const result = await api(endpoint, { method: targetType === "service" ? "POST" : "DELETE" });
        if (targetType === "service") {
          s.setJob(result);
          s.showToast?.(`Delete service ${targetName} job started: ${result.status}`, "warn")
            || s.setNotice(`Delete service ${targetName} job started: ${result.status}`);
        } else {
          s.showToast?.(`Deleted ${targetType} ${targetName} successfully.`, "ok")
            || s.setNotice(`Deleted ${targetType} ${targetName} successfully.`);
        }
        s.setDeleteModal((prev) => ({ ...prev, visible: false }));
        // cP closeInfoDetailDrawer when deleted target was open
        if (targetType === "service" && s.selectedService?.id === targetId) {
          s.setSelectedService(null);
          s.setCapabilities(null);
        }
        if (targetType === "node" && s.selectedNode?.id === targetId) {
          s.setSelectedNode(null);
        }
        if (targetType === "cluster" && s.selectedCluster?.id === targetId) {
          s.setSelectedCluster(null);
          s.setSelectedNode(null);
          s.setSelectedService(null);
        }
        // Signal detail drawers to close (ClustersView watches this)
        s.setDetailCloseSignal?.((n) => ({
          seq: Number((n && n.seq) || 0) + 1,
          type: targetType,
          id: targetId,
        }));
        await (s.refreshClusterInventory || s.refresh)();
        // Re-fetch Events if open after delete mutation
        s.setEventsRefreshKey?.((k) => Number(k || 0) + 1);
      } catch (error) {
        s.showToast?.(`Delete failed: ${error.message}`, "err") || s.setNotice(`Delete failed: ${error.message}`);
      } finally {
        s.setActionBusy?.((b) => ({ ...b, [deleteKey]: false, delete: false }));
      }
    });
  },

  async requestForceDeleteApproval() {
    const { targetType, targetId, forceReason, requestedBy } = s.deleteModal;
    if (forceReason.trim().length < 12) {
      s.setNotice("Approval request reason must be at least 12 characters.");
      return;
    }
    const approval = await api("/api/lifecycle/force-approvals", {
      method: "POST",
      body: JSON.stringify({
        target_type: targetType,
        target_id: targetId,
        reason: forceReason.trim(),
        requested_by: requestedBy.trim() || "platform-operator",
        ttl_hours: 4
      })
    });
    s.setDeleteModal((prev) => ({ ...prev, forceApprovalId: String(approval.id), approvalStatus: approval.status }));
    s.setNotice(`Approval request created: #${approval.id} (${approval.status})`);
    await s.refresh();
  },

  async approveForceDeleteApproval() {
    const approvalId = Number(s.deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setNotice("Enter a valid approval id before approving.");
      return;
    }
    const approval = await api(`/api/lifecycle/force-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: s.deleteModal.approver.trim() || "platform-admin",
        decision_note: s.deleteModal.decisionNote.trim(),
        status: "approved"
      })
    });
    s.setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: true }));
    s.setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await s.refresh();
  },

  async rejectForceDeleteApproval() {
    const approvalId = Number(s.deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setNotice("Enter a valid approval id before rejecting.");
      return;
    }
    const approval = await api(`/api/lifecycle/force-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({
        approver: s.deleteModal.approver.trim() || "platform-admin",
        decision_note: s.deleteModal.decisionNote.trim(),
        status: "rejected"
      })
    });
    s.setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: false }));
    s.setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await s.refresh();
  },

  async revokeForceDeleteApproval() {
    const approvalId = Number(s.deleteModal.forceApprovalId);
    if (!approvalId || Number.isNaN(approvalId)) {
      s.setNotice("Enter a valid approval id before revoking.");
      return;
    }
    const approval = await api(`/api/lifecycle/force-approvals/${approvalId}/revoke`, {
      method: "POST",
      body: JSON.stringify({
        actor: s.deleteModal.approver.trim() || "platform-admin",
        note: s.deleteModal.decisionNote.trim()
      })
    });
    s.setDeleteModal((prev) => ({ ...prev, approvalStatus: approval.status, force: false }));
    s.setNotice(`Approval #${approval.id} is now ${approval.status}`);
    await s.refresh();
  }
  };
}
