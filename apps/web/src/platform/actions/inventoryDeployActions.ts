// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createInventoryDeployActions(s: any) {
  return {
  async installCard(card) {
    const node = s.selectedNode || s.nodes[0];
    if (!node) {
      s.setNotice("Register a node on a cluster before continuing.");
      return;
    }
    const service = await api("/api/services", {
      method: "POST",
      body: JSON.stringify({ node_id: node.id, service_key: card.service_key })
    });
    s.setSelectedService(service);
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    s.setNotice(`Added ${service.name} to ${node.name}`);
    await s.refresh();
  },

  assignContractValue(target, key, value) {
    const parts = key.split(".");
    let cursor = target;
    parts.slice(0, -1).forEach((part) => {
      if (!cursor[part] || typeof cursor[part] !== "object" || Array.isArray(cursor[part])) {
        cursor[part] = {};
      }
      cursor = cursor[part];
    });
    cursor[parts[parts.length - 1]] = value;
  },

  parseInstallFieldValue(field, value) {
    if (field.key === "name") return value;
    if (field.field_type === "boolean") return Boolean(value);
    if (field.field_type === "number") {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : value;
    }
    if (field.field_type === "list") {
      if (Array.isArray(value)) return value;
      return String(value ?? "").split("\n").map((item) => item.trim()).filter(Boolean);
    }
    return value;
  },

  installSchemaValues(schema) {
    if (!schema) return {};
    return Object.fromEntries(schema.fields.map((field) => {
      const value = field.field_type === "list" && Array.isArray(field.value) ? field.value.join("\n") : field.value ?? "";
      return [field.key, value];
    }));
  },

  buildInstallOverrides() {
    const overrides = {};
    const schema = s.catalogOnboarding.installSchema;
    if (schema) {
      schema.fields.forEach((field) => {
        if (field.key === "name" || field.key === "service_name") return;
        const value = s.parseInstallFieldValue(field, s.catalogOnboarding.installFieldValues[field.key]);
        s.assignContractValue(overrides, field.key, value);
      });
    }
    // Normalize cPlatform MANUAL/ANSIBLE into install_mode
    const rawMode =
      overrides.service_install ||
      overrides.install_mode ||
      s.catalogOnboarding.installFieldValues?.service_install ||
      s.catalogOnboarding.installFieldValues?.install_mode;
    if (rawMode != null) {
      const mode = String(rawMode).toLowerCase();
      overrides.install_mode = mode.includes("manual") ? "manual" : "ansible";
      overrides.service_install = mode.includes("manual") ? "MANUAL" : "ANSIBLE";
    }
    const trimmedOverrides = s.catalogOnboarding.overridesText.trim();
    if (trimmedOverrides) {
      const parsed = JSON.parse(trimmedOverrides);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Overrides must be a JSON object.");
      }
      Object.assign(overrides, parsed);
    }
    return overrides;
  },

  async loadInstallSchemaFor(card, nodeId, service) {
    const params = new URLSearchParams({ node_id: String(nodeId) });
    if (service) params.set("service_id", String(service.id));
    const schema = await api(`/api/catalog/services/${card.service_key}/install-schema?${params.toString()}`);
    return schema;
  },

  async openCatalogOnboarding(card) {
    const fallbackNode = s.selectedNode ?? (s.selectedCluster ? s.nodes.find((item) => item.cluster_id === s.selectedCluster.id) ?? s.nodes[0] : s.nodes[0]);
    if (!fallbackNode) {
      s.setActionBlocker?.({
        visible: true,
        message: "Provision a node first before onboarding a service card.",
        secondaryLabel: "Open provision",
        secondaryAction: "provision",
      });
      s.setNotice("Provision a node first before onboarding a service card.");
      return;
    }
    const defaultOverrides = {};
    const schema = await s.loadInstallSchemaFor(card, fallbackNode.id);
    // cPlatform chain: close catalog → open install/config drawer
    s.setCatalogDrawerVisible?.(false);
    s.setCatalogOnboarding({
      visible: true,
      mode: "create",
      card,
      editingService: null,
      installSchema: schema,
      installFieldValues: s.installSchemaValues(schema),
      nodeId: fallbackNode.id,
      customName: "",
      nextAction: card.configurable ? "config" : "deploy",
      overridesText: JSON.stringify(defaultOverrides, null, 2),
      creating: false,
      error: "",
      registeredService: null
    });
  },

  async openServiceEditor(service) {
    const card = s.catalog.find((item) => item.service_key === service.service_key);
    if (!card) {
      s.setNotice(`Catalog definition for ${service.service_key} is not available.`);
      return;
    }
    const schema = await s.loadInstallSchemaFor(card, service.node_id, service);
    s.setCatalogOnboarding({
      visible: true,
      mode: "edit",
      card,
      editingService: service,
      installSchema: schema,
      installFieldValues: s.installSchemaValues(schema),
      nodeId: service.node_id,
      customName: service.name,
      nextAction: "overview",
      overridesText: "",
      creating: false,
      error: "",
      registeredService: null
    });
  },

  async confirmCatalogOnboarding() {
    const card = s.catalogOnboarding.card;
    if (!card) {
      s.setCatalogOnboarding((current) => ({ ...current, error: "No catalog card selected." }));
      return;
    }
    const node = s.nodes.find((item) => item.id === s.catalogOnboarding.nodeId);
    if (!node) {
      s.setCatalogOnboarding((current) => ({ ...current, error: "Choose a valid target node." }));
      return;
    }
    let contractOverrides = {};
    try {
      contractOverrides = s.buildInstallOverrides();
    } catch (error) {
      s.setCatalogOnboarding((current) => ({ ...current, error: `Invalid install configuration: ${error.message}` }));
      return;
    }
    s.setCatalogOnboarding((current) => ({ ...current, creating: true, error: "" }));
    try {
      try {
        const desiredName = (s.catalogOnboarding.customName.trim() || card.name || card.service_key).toLowerCase().replace(/\s+/g, "-");
        const portRaw = contractOverrides.port ?? contractOverrides.host_port ?? contractOverrides.published_port;
        const portNum = portRaw != null ? Number(portRaw) : null;
        const avail = await s.checkPortAndNameAvailability(node.id, desiredName, portNum);
        const blocked = avail.available === false || avail.ok === false;
        if (blocked) {
          s.setCatalogOnboarding((current) => ({
            ...current,
            creating: false,
            error: avail.message || avail.detail || "Port or container name conflicts with an existing service on this node."
          }));
          return;
        }
      } catch {
      }
      const existing = s.services.find((service2) => service2.node_id === node.id && service2.service_key === card.service_key);
      const targetService = s.catalogOnboarding.editingService;
      const payload = {
        node_id: node.id,
        service_key: card.service_key,
        name: s.catalogOnboarding.customName.trim() || void 0,
        contract_overrides: contractOverrides
      };
      const service = targetService ? await api(`/api/services/${targetService.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: s.catalogOnboarding.customName.trim() || void 0,
          contract_overrides: contractOverrides
        })
      }) : existing ?? await api("/api/services", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      s.setSelectedNode(node);
      s.setSelectedService(service);
      await s.loadServiceCapabilities(service.id);
      await s.loadServiceSummary(service.id);
      await s.loadServiceReleaseTimeline(service.id);
      await s.loadServiceMetrics(service.id);
      if (!existing) {
        await s.refresh();
      }
      s.setCatalogOnboarding((current) => ({ ...current, creating: false, error: "", registeredService: service }));
      s.setCatalogDrawerVisible(false);
      await s.loadNodeJobHistory(node.id);
      await s.refreshNodeLiveStatus?.(node.id);
      const installMode = String(
        contractOverrides.install_mode ||
          contractOverrides.service_install ||
          ""
      ).toLowerCase();
      const isManual = installMode.includes("manual");
      // MANUAL: register only (cPlatform). ANSIBLE: open deploy when requested.
      if (s.catalogOnboarding.nextAction === "config") {
        await s.loadConfig(service, s.configSource);
        s.setActiveView("config");
        s.setCatalogOnboarding((current) => ({ ...current, visible: false }));
        s.setNotice(`Registered ${service.name}${service.external_id ? ` (${service.external_id})` : ""} on ${node.name} and opened config manager.`);
        return;
      }
      if (s.catalogOnboarding.nextAction === "deploy" && !isManual) {
        await s.openDeploymentModal(service);
        s.setCatalogOnboarding((current) => ({ ...current, visible: false }));
        s.setNotice(`Registered ${service.name}${service.external_id ? ` (${service.external_id})` : ""} on ${node.name} and opened deployment control.`);
        return;
      }
      s.setCatalogOnboarding((current) => ({ ...current, visible: false }));
      const modeLabel = isManual ? "MANUAL (registered, no ansible deploy)" : "";
      s.setNotice(
        targetService
          ? `Updated ${service.name} install configuration.`
          : existing
            ? `Selected existing ${service.name} on ${node.name}.`
            : `Registered ${service.name}${service.external_id ? ` (${service.external_id})` : ""} on ${node.name}${modeLabel ? ` · ${modeLabel}` : ""}.`
      );
    } catch (error) {
      s.setCatalogOnboarding((current) => ({
        ...current,
        creating: false,
        error: error.message || "Failed to onboard service card."
      }));
    }
  },

  async updateServiceExpose(service, { expose_service, host_port, name }) {
    if (!service?.id) {
      s.setNotice("Select a service first.");
      return null;
    }
    try {
      const contract_overrides = {};
      if (expose_service !== undefined) contract_overrides.expose_service = Boolean(expose_service);
      if (host_port !== undefined && host_port !== null && String(host_port).trim() !== "") {
        contract_overrides.host_port = Number(host_port) || host_port;
      }
      // Port collision when exposing
      if (contract_overrides.expose_service && contract_overrides.host_port != null) {
        try {
          const check = await api(
            `/api/nodes/${service.node_id}/check-port-and-name?port=${encodeURIComponent(String(contract_overrides.host_port))}&name=${encodeURIComponent(service.container_name || "")}`
          );
          if (check && check.available === false) {
            s.setNotice(check.message || `Port ${contract_overrides.host_port} is not available on this node.`);
            return null;
          }
        } catch (_e) {
          /* non-fatal: backend may still validate */
        }
      }
      const updated = await api(`/api/services/${service.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name ?? undefined,
          contract_overrides,
        }),
      });
      s.setSelectedService(updated);
      s.setNotice(
        `Updated ${updated.name}: expose=${contract_overrides.expose_service ?? "unchanged"}` +
          (contract_overrides.host_port != null ? ` host_port=${contract_overrides.host_port}` : "")
      );
      await s.refresh();
      return updated;
    } catch (error) {
      s.setNotice(error?.message || "Failed to update service");
      return null;
    }
  },

  async openDeploymentModal(service) {
    if (!service) {
      s.setActionBlocker?.({
        visible: true,
        message: "Select a service or open the catalog to install one first.",
        secondaryLabel: "Open catalog",
        secondaryAction: "catalog",
      });
      return;
    }
    const node = s.nodes.find((item) => item.id === service.node_id);
    if (!node) {
      s.setActionBlocker?.({
        visible: true,
        message: "Provision a node before deploying services.",
        secondaryLabel: "Open provision",
        secondaryAction: "provision",
      });
      return;
    }
    s.setSelectedService(service);
    s.setActionBusy?.((b) => ({ ...b, deploy: true }));
    s.setDeploymentModal({
      visible: true,
      serviceId: service.id,
      serviceName: service.name,
      nodeName: node?.name ?? `node-${service.node_id}`,
      preflight: null,
      autoInstallDependencies: true,
      loading: true,
      executing: false,
      error: "",
      result: null
    });
    try {
      const [nextPlan, preflight] = await Promise.all([
        api(`/api/nodes/${service.node_id}/deployment-plan/${service.service_key}`),
        api(
          `/api/services/${service.id}/preflight`,
          { method: "POST" }
        )
      ]);
      s.setPlan(nextPlan);
      s.setDeploymentModal((current) => ({
        ...current,
        loading: false,
        preflight
      }));
      s.setActionBusy?.((b) => ({ ...b, deploy: false }));
    } catch (error) {
      s.setActionBusy?.((b) => ({ ...b, deploy: false }));
      s.setDeploymentModal((current) => ({
        ...current,
        loading: false,
        error: error.message || "Failed to open deployment control."
      }));
    }
  },

  async executeDeploymentModal() {
    if (!s.deploymentModal.serviceId) {
      s.setDeploymentModal((current) => ({ ...current, error: "No service selected for deployment." }));
      return;
    }
    const service = s.services.find((item) => item.id === s.deploymentModal.serviceId);
    if (!service) {
      s.setDeploymentModal((current) => ({ ...current, error: "Selected service is no longer available." }));
      return;
    }
    s.setActionBusy?.((b) => ({ ...b, deploy: true }));
    s.setDeploymentModal((current) => ({ ...current, executing: true, error: "" }));
    try {
      // Prefer full execute plan; fall back to plain deploy if execute fails
      let result;
      try {
        result = await api(`/api/services/${service.id}/deployment/execute`, {
          method: "POST",
          body: JSON.stringify({ auto_install_dependencies: s.deploymentModal.autoInstallDependencies })
        });
      } catch (execErr) {
        const job2 = await api(`/api/services/${service.id}/deploy`, { method: "POST" });
        result = {
          summary: `Deploy job #${job2.id}: ${job2.status}`,
          plan: s.plan,
          preflight_after: s.deploymentModal.preflight,
          target_job: job2,
        };
      }
      s.setPlan(result.plan || s.plan);
      s.setDeploymentModal((current) => ({
        ...current,
        executing: false,
        preflight: result.preflight_after || current.preflight,
        result
      }));
      if (result.target_job) {
        s.setJob(result.target_job);
      }
      s.showToast?.(result.summary || "Deployment started", "ok") || s.setNotice(result.summary || "Deployment started");
      await s.refresh();
      await s.loadNodeJobHistory(service.node_id);
      await s.loadServiceSummary(service.id);
      await s.refreshNodeLiveStatus?.(service.node_id);
      s.setEventsRefreshKey?.((k) => Number(k || 0) + 1);
    } catch (error) {
      s.showToast?.(error.message || "Deployment execution failed.", "err");
      s.setDeploymentModal((current) => ({
        ...current,
        executing: false,
        error: error.message || "Deployment execution failed."
      }));
      s.setNotice(error.message || "Deployment execution failed.");
    } finally {
      s.setActionBusy?.((b) => ({ ...b, deploy: false }));
    }
  },

  async installMissingDependencies(service) {
    try {
      const result = await api(`/api/services/${service.id}/dependencies/install-missing`, {
        method: "POST"
      });
      const actionCount = result.dependency_actions.length;
      const nextPlan = await api(`/api/nodes/${service.node_id}/deployment-plan/${service.service_key}`);
      const preflight = await api(
        `/api/services/${service.id}/preflight`,
        { method: "POST" }
      );
      s.setPlan(nextPlan);
      s.setDeploymentModal((current) => current.serviceId === service.id ? {
        ...current,
        preflight,
        result: current.result ? {
          ...current.result,
          plan: nextPlan,
          preflight_after: preflight,
          dependency_actions: result.dependency_actions,
          summary: result.summary
        } : null
      } : current);
      s.setNotice(`${result.summary} (${actionCount} actions)`);
      await s.refresh();
      await s.loadNodeJobHistory(service.node_id);
      await s.loadServiceSummary(service.id);
    } catch (error) {
      s.setNotice(`Dependency install failed: ${error.message}`);
    }
  },

  async openDependencyTarget(serviceKey, mode) {
    if (!s.selectedService) {
      s.setNotice("Select a service first.");
      return;
    }
    const nodeId = s.selectedService.node_id;
    let target = s.services.find((service) => service.node_id === nodeId && service.service_key === serviceKey);
    if (!target && mode === "ensure") {
      target = await api("/api/services", {
        method: "POST",
        body: JSON.stringify({ node_id: nodeId, service_key: serviceKey })
      });
      s.setNotice(`Created dependency card ${target.name} on node.`);
      await s.refresh();
    }
    if (!target) {
      s.setNotice(`Dependency card ${serviceKey} is not installed on this node.`);
      return;
    }
    if (mode === "config") {
      s.setSelectedService(target);
      await s.loadServiceCapabilities(target.id);
      await s.loadConfig(target, s.configSource);
      return;
    }
    if (mode === "diagnostics") {
      await s.loadDiagnostics(s.selectedService, { targetServiceKey: serviceKey, preserveSelection: true });
      return;
    }
    s.setSelectedService(target);
    await s.loadServiceCapabilities(target.id);
    await s.loadServiceSummary(target.id);
    await s.loadServiceReleaseTimeline(target.id);
    await s.loadServiceMetrics(target.id);
    s.setNotice(`Selected dependency card ${target.name}`);
  },

  async ensureMissingDependencyCards() {
    if (!s.selectedService || !s.diagnostics?.readiness.dependency_targets) {
      s.setNotice("Load diagnostics first to evaluate dependency cards.");
      return;
    }
    const missingTargets = s.diagnostics.readiness.dependency_targets.filter((target) => !target.on_node);
    if (missingTargets.length === 0) {
      s.setNotice("All dependency cards are already present on this node.");
      return;
    }
    for (const target of missingTargets) {
      await api("/api/services", {
        method: "POST",
        body: JSON.stringify({ node_id: s.selectedService.node_id, service_key: target.service_key })
      });
    }
    s.setNotice(`Ensured ${missingTargets.length} missing dependency card(s).`);
    await s.refresh();
    await s.loadDiagnostics(s.selectedService);
  },

  async backupService(service) {
    const backup = await api(`/api/services/${service.id}/backup`, { method: "POST" });
    s.setNotice(`Backup ${backup.status}: ${backup.artifact_path}`);
    await s.refresh();
  }
  };
}
