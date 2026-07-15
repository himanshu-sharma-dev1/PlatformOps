// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { filterCatalogItems, CATALOG_DRAG_MIME } from "../platform/ux/clusterUx";

/** DrawersHost — Phase 1 extracted page JSX. */
export function DrawersHost() {
  const p = usePlatform() as any;
  const applyNodePreset = p.applyNodePreset;
  const catalog = p.catalog;
  const catalogDrawerVisible = p.catalogDrawerVisible;
  const catalogOnboarding = p.catalogOnboarding;
  const [catalogSearch, setCatalogSearch] = React.useState("");
  const [catalogCategory, setCatalogCategory] = React.useState("all");
  const config = p.config;
  const configSource = p.configSource;
  const confirmCatalogOnboarding = p.confirmCatalogOnboarding;
  const installSchemaValues = p.installSchemaValues;
  const job = p.job;
  const loadConfig = p.loadConfig;
  const loadInstallSchemaFor = p.loadInstallSchemaFor;
  const loadServiceSummary = p.loadServiceSummary;
  const nodeEditor = p.nodeEditor;
  const nodePreset = p.nodePreset;
  const nodes = p.nodes;
  const onboardingError = p.onboardingError;
  const onboardingOutput = p.onboardingOutput;
  const onboardingStatus = p.onboardingStatus;
  const openCatalogOnboarding = p.openCatalogOnboarding;
  const openDeploymentModal = p.openDeploymentModal;
  const plan = p.plan;
  const pollOnboardingJob = p.pollOnboardingJob;
  const saveNodeEditor = p.saveNodeEditor;
  const selectedCluster = p.selectedCluster;
  const setActiveView = p.setActiveView;
  const setCatalogDrawerVisible = p.setCatalogDrawerVisible;
  const setCatalogOnboarding = p.setCatalogOnboarding;
  const setNodeEditor = p.setNodeEditor;
  const setNotice = p.setNotice;
  const setOnboardingError = p.setOnboardingError;
  const setOnboardingJobId = p.setOnboardingJobId;
  const setOnboardingOutput = p.setOnboardingOutput;
  const setOnboardingStatus = p.setOnboardingStatus;
  const setStepperDrawerVisible = p.setStepperDrawerVisible;
  const setStepperStep = p.setStepperStep;
  const stepperDrawerVisible = p.stepperDrawerVisible;
  const stepperStep = p.stepperStep;
  const buildInstallOverrides = p.buildInstallOverrides;
  const checkPortAndNameAvailability = p.checkPortAndNameAvailability;

  React.useEffect(() => {
    if (!catalogOnboarding.visible || !catalogOnboarding.card || !catalogOnboarding.nodeId) {
      return;
    }
    
    // Parse overrides to resolve port
    let portNum = null;
    let desiredName = "";
    try {
      const card = catalogOnboarding.card;
      desiredName = (catalogOnboarding.customName.trim() || card.name || card.service_key).toLowerCase().replace(/\s+/g, "-");
      
      const contractOverrides = buildInstallOverrides ? buildInstallOverrides() : {};
      const portRaw = contractOverrides.port ?? contractOverrides.host_port ?? contractOverrides.published_port;
      portNum = portRaw != null ? Number(portRaw) : null;
    } catch (e) {
      return;
    }
    
    setCatalogOnboarding(curr => ({ ...curr, validating: true, validationConflict: null }));
    
    const delayDebounceFn = setTimeout(async () => {
      try {
        const res = await checkPortAndNameAvailability(catalogOnboarding.nodeId, desiredName, portNum);
        const blocked = res.available === false || res.ok === false;
        setCatalogOnboarding(curr => ({
          ...curr,
          validating: false,
          validationConflict: blocked ? (res.message || res.detail || "Port or container name conflicts with an existing service on this node.") : null
        }));
      } catch (err) {
        setCatalogOnboarding(curr => ({ ...curr, validating: false }));
      }
    }, 450);
    
    return () => clearTimeout(delayDebounceFn);
  }, [
    catalogOnboarding.visible,
    catalogOnboarding.nodeId,
    catalogOnboarding.customName,
    catalogOnboarding.overridesText,
    JSON.stringify(catalogOnboarding.installFieldValues)
  ]);


  return (
    <>
      {/* SERVICE CATALOG DRAWER — search + category chips → install/config chain */}
      {catalogDrawerVisible && (() => {
        const filtered = filterCatalogItems(catalog || [], catalogSearch, catalogCategory);
        const chips = [
          { id: "all", label: "All" },
          { id: "infra", label: "Infra" },
          { id: "app", label: "App" },
          { id: "observability", label: "Observability" },
          { id: "data", label: "Data" },
        ];
        return (
        <>
          <div className="drawer-backdrop open" style={{ display: "block" }} onClick={() => setCatalogDrawerVisible(false)} />
          <aside className="drawer catalog-drawer open" style={{ display: "flex", flexDirection: "column", right: 0 }} data-ux="catalog-drawer">
            <div className="drawer-head">
              <div>
                <h2 style={{ fontSize: "1.5rem", fontFamily: "var(--display)", margin: 0 }}>Service catalog</h2>
                <div className="sub">Click or drag a card onto the service stack (dForm · MANUAL/ANSIBLE · expose)</div>
              </div>
              <button className="icon-btn" onClick={() => setCatalogDrawerVisible(false)} aria-label="Close catalog">
                <svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div className="catalog-search">
              <input
                className="input"
                type="search"
                placeholder="Search catalog…"
                value={catalogSearch}
                onChange={(e) => setCatalogSearch(e.target.value)}
                data-ux="catalog-search"
              />
            </div>
            <div className="catalog-categories" data-ux="catalog-chips">
              {chips.map((chip) => (
                <button
                  key={chip.id}
                  type="button"
                  className={`cat-chip ${catalogCategory === chip.id ? "active" : ""}`}
                  onClick={() => setCatalogCategory(chip.id)}
                  data-cat={chip.id}
                >
                  {chip.label}
                </button>
              ))}
            </div>
            <div className="catalog-list drawer-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto", flex: 1 }}>
              {filtered.map((card: any) => (
                <div
                  key={card.service_key}
                  className="catalog-item"
                  draggable
                  data-cat={String(card.kind || card.subsystem || "app").toLowerCase()}
                  data-service-key={card.service_key}
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "copy";
                    e.dataTransfer.setData(CATALOG_DRAG_MIME, card.service_key);
                    e.dataTransfer.setData("text/plain", card.service_key);
                    e.currentTarget.classList.add("dragging");
                  }}
                  onDragEnd={(e) => {
                    e.currentTarget.classList.remove("dragging");
                  }}
                  onClick={() => openCatalogOnboarding(card)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") openCatalogOnboarding(card); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    padding: "1rem",
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid var(--line)",
                    borderRadius: "12px",
                    cursor: "grab",
                    transition: "all 0.2s"
                  }}
                >
                  <div className="drag-h" title="Drag onto service stack" aria-hidden>⋮⋮</div>
                  <div className="ico" style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--navy-100)", color: "var(--navy)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>
                    {(card.name || "?")[0]}
                  </div>
                  <div className="info" style={{ flex: 1 }}>
                    <div className="nm" style={{ fontWeight: 600 }}>{card.name}</div>
                    <div className="desc" style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginTop: "2px" }}>{card.description || card.image}</div>
                    <div className="tags" style={{ display: "flex", gap: "0.25rem", marginTop: "4px", flexWrap: "wrap" }}>
                      <span className="tag" style={{ fontSize: "0.7rem" }}>{card.subsystem}</span>
                      <span className="tag" style={{ fontSize: "0.7rem" }}>{card.kind}</span>
                      {card.configurable && <span className="tag" style={{ fontSize: "0.7rem" }}>config</span>}
                      {(card.dependencies || []).length > 0 && <span className="tag" style={{ fontSize: "0.7rem" }}>{card.dependencies.length} deps</span>}
                      {(card.ports || []).length > 0 && <span className="tag" style={{ fontSize: "0.7rem" }}>{card.ports.length} port(s)</span>}
                    </div>
                  </div>
                </div>
              ))}
              {filtered.length === 0 && (
                <p style={{ color: "var(--ink-4)", fontSize: "0.85rem", margin: "1rem 0" }}>No catalog items match this filter.</p>
              )}
            </div>
            <div className="drawer-foot">
              <span style={{ fontSize: "0.78rem", color: "var(--ink-4)", marginRight: "auto" }}>{filtered.length} of {(catalog || []).length} cards · drag to node stack</span>
              <button className="btn btn-secondary btn-sm" onClick={() => setCatalogDrawerVisible(false)}>Close</button>
            </div>
          </aside>
        </>
        );
      })()}

      {catalogOnboarding.visible && catalogOnboarding.card && (
        <>
          <div className="drawer-backdrop open" style={{ display: "block", zIndex: 105 }} onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))} />
          <aside
            className={`drawer svc-config-drawer open ${catalogOnboarding.creating ? "is-busy" : ""}`}
            style={{ display: "flex", flexDirection: "column", zIndex: 110, width: "min(640px, 100vw)" }}
            data-ux="svc-config-drawer"
          >
            <div className="drawer-head">
              <div>
                <h2 style={{ margin: 0, fontSize: "1.25rem", fontFamily: "var(--display)" }}>
                  {catalogOnboarding.mode === "edit" ? "Configure service" : "Install / configure"}
                </h2>
                <div className="sub">
                  {catalogOnboarding.mode === "edit" ? "Update" : "Register"} <strong>{catalogOnboarding.card.name}</strong> · dForm · MANUAL/ANSIBLE · expose
                </div>
              </div>
              <button type="button" className="icon-btn" onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))} aria-label="Close">
                <svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div className={`drawer-body ${catalogOnboarding.creating ? "is-busy" : ""}`} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: "0.85rem" }}>
              <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                  <strong>{catalogOnboarding.card.name}</strong>
                  <div className="tags">
                    <span>{catalogOnboarding.card.kind}</span>
                    <span>{catalogOnboarding.card.subsystem}</span>
                  </div>
                </div>
                <div style={{ color: "var(--ink-3)", fontSize: "0.84rem", marginTop: "0.35rem" }}>
                  {catalogOnboarding.card.description || catalogOnboarding.card.image}
                </div>
                <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.4rem" }}>
                  Image <code>{catalogOnboarding.card.image}</code>
                </div>
                <div style={{ marginTop: "0.6rem" }}>
                  <small style={{ color: "var(--ink-4)" }}>Dependencies</small>
                  <div className="tags" style={{ marginTop: "0.25rem" }}>
                    {catalogOnboarding.card.dependencies.length > 0
                      ? catalogOnboarding.card.dependencies.map((item) => <span key={`catalog-onboard-dep-${item}`}>{item}</span>)
                      : <span>standalone</span>}
                  </div>
                </div>
                {catalogOnboarding.card.tags.length > 0 && (
                  <div style={{ marginTop: "0.6rem" }}>
                    <small style={{ color: "var(--ink-4)" }}>Traits</small>
                    <div className="tags" style={{ marginTop: "0.25rem" }}>
                      {catalogOnboarding.card.tags.map((item) => <span key={`catalog-onboard-tag-${item}`}>{item}</span>)}
                      {catalogOnboarding.card.configurable && <span>config-manager</span>}
                      {catalogOnboarding.card.log_paths.length > 0 && <span>{catalogOnboarding.card.log_paths.length} log path(s)</span>}
                    </div>
                  </div>
                )}
                <div style={{ marginTop: "0.7rem", padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                  <small style={{ color: "var(--ink-4)" }}>Service defaults & install preview</small>
                  <div className="tags" style={{ marginTop: "0.35rem" }}>
                    <span>{catalogOnboarding.card.ports.length} published port(s)</span>
                    <span>{catalogOnboarding.card.volumes.length} volume mount(s)</span>
                    <span>{catalogOnboarding.card.config_files.length} config file(s)</span>
                    <span>{Object.keys(catalogOnboarding.card.env || {}).length} env default(s)</span>
                  </div>
                  {Object.keys(catalogOnboarding.card.env || {}).length > 0 && (
                    <div style={{ marginTop: "0.45rem" }}>
                      <small style={{ color: "var(--ink-4)" }}>Environment defaults</small>
                      <div className="tags" style={{ marginTop: "0.25rem" }}>
                        {Object.entries(catalogOnboarding.card.env).slice(0, 6).map(([key, value]) => (
                          <span key={`catalog-env-${key}`}>{key}={String(value)}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {catalogOnboarding.card.config_files.length > 0 && (
                    <div style={{ marginTop: "0.45rem" }}>
                      <small style={{ color: "var(--ink-4)" }}>Config files</small>
                      <div className="tags" style={{ marginTop: "0.25rem" }}>
                        {catalogOnboarding.card.config_files.slice(0, 4).map((item) => <span key={`catalog-config-${item}`}>{item}</span>)}
                      </div>
                    </div>
                  )}
                  {catalogOnboarding.card.command && (
                    <pre style={{ margin: "0.45rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.72rem" }}>
                      <code>{catalogOnboarding.card.command}</code>
                    </pre>
                  )}
                </div>
              </div>

              <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                <div className="field">
                  <label>Target node</label>
                  <select
                    value={catalogOnboarding.nodeId}
                    disabled={catalogOnboarding.mode === "edit"}
                    onChange={async (e) => {
                      const nextNodeId = Number(e.target.value);
                      setCatalogOnboarding((current) => ({ ...current, nodeId: nextNodeId, error: "" }));
                      if (catalogOnboarding.card) {
                        try {
                          const schema = await loadInstallSchemaFor(catalogOnboarding.card, nextNodeId);
                          setCatalogOnboarding((current) => ({
                            ...current,
                            installSchema: schema,
                            installFieldValues: installSchemaValues(schema),
                          }));
                        } catch (error: any) {
                          setCatalogOnboarding((current) => ({ ...current, error: error.message || "Failed to load install schema." }));
                        }
                      }
                    }}
                  >
                    {(selectedCluster
                      ? nodes.filter((item) => item.cluster_id === selectedCluster.id)
                      : nodes
                    ).map((node) => (
                      <option key={`catalog-node-${node.id}`} value={node.id}>
                        {node.name} · {node.environment} · {node.host}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Service display name</label>
                  <input
                    className="input"
                    value={catalogOnboarding.customName}
                    placeholder="Leave blank to use catalog name"
                    onChange={(e) => setCatalogOnboarding((current) => ({ ...current, customName: e.target.value }))}
                  />
                </div>
                {catalogOnboarding.installSchema && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
                    {Array.from(new Set(catalogOnboarding.installSchema.fields.map((field) => field.section))).map((section) => (
                      <div key={`install-section-${section}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                        <strong style={{ display: "block", marginBottom: "0.55rem", fontSize: "0.85rem", color: "var(--ink-3)" }}>{section}</strong>
                        <div style={{ display: "grid", gap: "0.6rem" }}>
                          {(catalogOnboarding.installSchema?.fields ?? [])
                            .filter((field) => field.section === section && field.key !== "name")
                            .filter((field) => {
                              // cP syncInfraExposeControls: hide host_port when expose is off
                              if (field.key === "host_port" || field.key === "published_port") {
                                const expose =
                                  catalogOnboarding.installFieldValues?.expose_service ??
                                  catalogOnboarding.installFieldValues?.expose;
                                return Boolean(expose);
                              }
                              return true;
                            })
                            .map((field) => (
                              <label key={`install-field-${field.key}`} className="field" style={{ margin: 0 }} data-field-key={field.key}>
                                <span>{field.label}{field.required ? " *" : ""}</span>
                                {field.field_type === "boolean" ? (
                                  <input
                                    type="checkbox"
                                    name={field.key}
                                    checked={Boolean(catalogOnboarding.installFieldValues[field.key])}
                                    onChange={(e) => {
                                      const checked = e.target.checked;
                                      setCatalogOnboarding((current) => {
                                        const nextValues = {
                                          ...current.installFieldValues,
                                          [field.key]: checked,
                                        };
                                        // clear host port when unchecking expose
                                        if ((field.key === "expose_service" || field.key === "expose") && !checked) {
                                          nextValues.host_port = "";
                                          nextValues.published_port = "";
                                        }
                                        return { ...current, installFieldValues: nextValues };
                                      });
                                    }}
                                  />
                                ) : field.field_type === "select" ? (
                                  <select
                                    name={field.key}
                                    value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                    onChange={(e) => setCatalogOnboarding((current) => ({
                                      ...current,
                                      installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                    }))}
                                  >
                                    <option value="">Select...</option>
                                    {(field.options || []).map((option) => <option key={`${field.key}-${option}`} value={option}>{option}</option>)}
                                  </select>
                                ) : field.field_type === "list" ? (
                                  <textarea
                                    className="input"
                                    name={field.key}
                                    style={{ minHeight: "72px", fontFamily: "var(--mono)", fontSize: "0.76rem" }}
                                    value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                    onChange={(e) => setCatalogOnboarding((current) => ({
                                      ...current,
                                      installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                    }))}
                                  />
                                ) : (
                                  <input
                                    className="input"
                                    name={field.key}
                                    type={field.field_type === "number" ? "number" : "text"}
                                    value={String(catalogOnboarding.installFieldValues[field.key] ?? "")}
                                    onChange={(e) => setCatalogOnboarding((current) => ({
                                      ...current,
                                      installFieldValues: { ...current.installFieldValues, [field.key]: e.target.value },
                                    }))}
                                  />
                                )}
                                {field.help_text && <small style={{ color: "var(--ink-4)" }}>{field.help_text}</small>}
                              </label>
                            ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="field">
                  <label>Continue into</label>
                  <select
                    value={catalogOnboarding.nextAction}
                    onChange={(e) => setCatalogOnboarding((current) => ({ ...current, nextAction: e.target.value as "overview" | "config" | "deploy" }))}
                  >
                    <option value="deploy">Deployment control (ANSIBLE)</option>
                    <option value="overview">Register only (good for MANUAL)</option>
                    {catalogOnboarding.card.configurable && <option value="config">Config manager</option>}
                  </select>
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>
                  dForm fields below (when loaded). Set <strong>ServiceInstall</strong> to MANUAL to register without Ansible deploy, or ANSIBLE then continue into Deployment control.
                  {catalogOnboarding.installSchema?.summary ? (
                    <div style={{ marginTop: 4 }}>{catalogOnboarding.installSchema.summary}</div>
                  ) : null}
                </div>
                <div className="field" style={{ marginTop: "0.75rem" }}>
                  <label>Advanced contract overrides (JSON)</label>
                  <textarea
                    className="input"
                    style={{ minHeight: "96px", fontFamily: "var(--mono)", fontSize: "0.78rem" }}
                    value={catalogOnboarding.overridesText}
                    onChange={(e) => setCatalogOnboarding((current) => ({ ...current, overridesText: e.target.value }))}
                    placeholder='{"ports":["8090:8080"],"config_files":["/path/to/config.yaml"]}'
                  />
                  <div style={{ marginTop: "0.35rem", color: "var(--ink-4)", fontSize: "0.78rem" }}>
                    Optional overrides are merged after the typed fields and reused by deployment/config workflows.
                  </div>
                </div>
              </div>
            </div>

            {catalogOnboarding.registeredService && (
              <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                  <strong>Registration summary</strong>
                  <span className="pill pill-ok">service card registered</span>
                </div>
                <div style={{ marginTop: "0.35rem", color: "var(--ink-3)", fontSize: "0.85rem" }}>
                  {catalogOnboarding.registeredService.name} is now registered on{" "}
                  {nodes.find((node) => node.id === catalogOnboarding.nodeId)?.name ?? `node-${catalogOnboarding.nodeId}`}.
                </div>
                <div className="tags" style={{ marginTop: "0.45rem" }}>
                  <span>{catalogOnboarding.registeredService.service_key}</span>
                  <span>{catalogOnboarding.registeredService.kind}</span>
                  <span><code>{catalogOnboarding.registeredService.container_name}</code></span>
                  <span>{catalogOnboarding.card.dependencies.length} dependencies</span>
                </div>
                <div style={{ marginTop: "0.7rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.7rem" }}>
                  <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                    <small style={{ color: "var(--ink-4)" }}>Install review</small>
                    <div className="tags" style={{ marginTop: "0.35rem" }}>
                      <span>{catalogOnboarding.card.ports.length} published port(s)</span>
                      <span>{catalogOnboarding.card.volumes.length} volume mount(s)</span>
                      <span>{catalogOnboarding.card.config_files.length} config file(s)</span>
                      <span>{catalogOnboarding.card.log_paths.length} log path(s)</span>
                    </div>
                    {catalogOnboarding.card.command && (
                      <pre style={{ margin: "0.45rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.72rem" }}>
                        <code>{catalogOnboarding.card.command}</code>
                      </pre>
                    )}
                  </div>
                  <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                    <small style={{ color: "var(--ink-4)" }}>Recommended next move</small>
                    <div style={{ marginTop: "0.35rem", color: "var(--ink-3)", fontSize: "0.84rem" }}>
                      {catalogOnboarding.card.dependencies.length > 0
                        ? "Open deployment control to review dependency-first rollout and Ansible execution order."
                        : catalogOnboarding.card.configurable
                        ? "Open config manager to review defaults before the first deploy."
                        : "You can go straight to deployment control for the first rollout."}
                    </div>
                    {catalogOnboarding.card.health_command && (
                      <div style={{ marginTop: "0.45rem", color: "var(--ink-4)", fontSize: "0.78rem" }}>
                        Health check: <code>{catalogOnboarding.card.health_command}</code>
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ marginTop: "0.7rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={async () => {
                      await loadServiceSummary(catalogOnboarding.registeredService!.id);
                      setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                      setNotice(`Reviewed ${catalogOnboarding.registeredService!.name} in service overview.`);
                    }}
                  >
                    Stay in overview
                  </button>
                  {catalogOnboarding.card.configurable && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={async () => {
                        await loadConfig(catalogOnboarding.registeredService!, configSource);
                        setActiveView("config");
                        setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                        setNotice(`Opened config manager for ${catalogOnboarding.registeredService!.name}.`);
                      }}
                    >
                      Open config
                    </button>
                  )}
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={async () => {
                      const service = catalogOnboarding.registeredService!;
                      setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                      await openDeploymentModal(service);
                    }}
                  >
                    Open deployment control
                  </button>
                </div>
              </div>
            )}

            {catalogOnboarding.validationConflict && (
              <div style={{ padding: "0.75rem", borderRadius: "10px", background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.25)", color: "rgb(248, 113, 113)", fontSize: "0.82rem", display: "flex", flexDirection: "column", gap: 4, marginTop: "0.5rem" }}>
                <strong>Conflict detected:</strong>
                <span>{catalogOnboarding.validationConflict}</span>
              </div>
            )}
            {catalogOnboarding.validating && (
              <p style={{ color: "var(--ink-4)", fontSize: "0.78rem", margin: "0.5rem 0 0" }}>Checking port and name availability...</p>
            )}

            {catalogOnboarding.error && <p style={{ color: "var(--err)", fontSize: "0.82rem", margin: 0 }}>{catalogOnboarding.error}</p>}
            </div>
            <div className="drawer-foot" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))}>Cancel</button>
              <button
                className={`btn btn-primary btn-sm ${catalogOnboarding.creating ? "btn-loading" : ""}`}
                onClick={confirmCatalogOnboarding}
                disabled={catalogOnboarding.creating || catalogOnboarding.validating || Boolean(catalogOnboarding.validationConflict)}
                data-ux="catalog-onboard-submit"
              >
                {catalogOnboarding.creating && <span className="btn-spinner" />}
                {catalogOnboarding.creating ? "Saving…" : catalogOnboarding.mode === "edit" ? "Save configuration" : "Register Service Card"}
              </button>
            </div>
          </aside>
        </>
      )}

      {/* NODE PROVISIONING STEPPER DRAWER */}
      {stepperDrawerVisible && (
        <>
          <div className="drawer-backdrop" style={{ display: "block" }} onClick={() => setStepperDrawerVisible(false)}></div>
          <aside className="drawer" style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1.5rem", right: 0 }}>
            <div className="drawer-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: "1.5rem", fontFamily: "var(--display)" }}>Provision new node</h2>
              <button className="icon-btn" onClick={() => setStepperDrawerVisible(false)}><svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
            </div>

            <div className="stepper" style={{ display: "flex", gap: "0.25rem", margin: "1rem 0" }}>
              {[1, 2, 3, 4, 5, 6].map(num => (
                <div key={num} className={`step ${stepperStep === num ? "active" : ""}`} style={{ flex: 1, height: "4px", background: stepperStep >= num ? "var(--navy)" : "var(--line)" }}></div>
              ))}
            </div>

            <div className="drawer-body" style={{ flex: 1, overflowY: "auto" }}>
              {stepperStep === 1 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 1: Cloud Provider</h3>
                  <div className="field">
                    <label>Node name</label>
                    <input type="text" className="input" placeholder="e.g. aws-node-mumbai" value={nodeEditor.draft.name} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>Cloud Provider</label>
                    <select value={nodePreset} onChange={(e) => applyNodePreset(e.target.value as any)}>
                      <option value="local-default">Local default (standalone)</option>
                      <option value="aws-general">Amazon Web Services (EC2)</option>
                      <option value="aws-gpu">AWS Accelerated GPU</option>
                    </select>
                  </div>
                </div>
              )}

              {stepperStep === 2 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 2: Hardware Profile</h3>
                  <div className="field">
                    <label>vCPU Cores</label>
                    <input type="number" className="input" value={nodeEditor.draft.cpu_cores ?? 4} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, cpu_cores: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>RAM (GB)</label>
                    <input type="number" className="input" value={nodeEditor.draft.memory_gb ?? 16} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, memory_gb: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>Disk SSD Size (GB)</label>
                    <input type="number" className="input" value={nodeEditor.draft.storage_gb ?? 100} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, storage_gb: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>GPU</label>
                    <input type="text" className="input" value={nodeEditor.draft.gpu ?? "none"} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, gpu: e.target.value } }))} />
                  </div>
                </div>
              )}

              {stepperStep === 3 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 3: Configuration</h3>
                  <div className="field">
                    <label>SSH Host/IP</label>
                    <input type="text" className="input" value={nodeEditor.draft.host} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, host: e.target.value } }))} placeholder="e.g. 65.2.63.24" />
                  </div>
                  <div className="field">
                    <label>SSH Username</label>
                    <input type="text" className="input" value={nodeEditor.draft.ssh_user} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_user: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>SSH Private Key Path</label>
                    <input type="text" className="input" placeholder="e.g. /home/ubuntu/NODE1001.pem" value={nodeEditor.draft.ssh_key_path} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_key_path: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>Or paste PEM private key</label>
                    <textarea
                      className="input"
                      style={{ minHeight: 90, fontFamily: "var(--mono)", fontSize: "0.75rem" }}
                      value={nodeEditor.draft.ssh_private_key || ""}
                      onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_private_key: e.target.value } }))}
                      placeholder="-----BEGIN RSA PRIVATE KEY-----"
                    />
                  </div>
                </div>
              )}

              {stepperStep === 4 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 4: Network & Storage</h3>
                  <div className="field">
                    <label>Docker Network namespace</label>
                    <input type="text" className="input" value={nodeEditor.draft.docker_network} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, docker_network: e.target.value } }))} />
                  </div>
                  <div className="field">
                    <label>Volume Root Directory</label>
                    <input type="text" className="input" value={nodeEditor.draft.volume_root} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, volume_root: e.target.value } }))} />
                  </div>
                </div>
              )}

              {stepperStep === 5 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 5: Firewall policies</h3>
                  <div className="field">
                    <label>Allowed ingress ports</label>
                    <input type="text" className="input" defaultValue="22, 80, 443, 8080" />
                  </div>
                </div>
              )}

              {stepperStep === 6 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 6: Review &amp; Launch</h3>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "10px", fontSize: "0.85rem" }}>
                    <div><strong>Node name:</strong> {nodeEditor.draft.name || "N/A"}</div>
                    <div><strong>Host IP:</strong> {nodeEditor.draft.host || "—"}</div>
                    <div><strong>SSH User:</strong> {nodeEditor.draft.ssh_user}</div>
                    <div><strong>Key:</strong> {nodeEditor.draft.ssh_key_path || (nodeEditor.draft.ssh_private_key ? "(pasted PEM)" : "—")}</div>
                    <div><strong>vCPU / Mem / Disk:</strong> {nodeEditor.draft.cpu_cores ?? "—"} / {nodeEditor.draft.memory_gb ?? "—"} GB / {nodeEditor.draft.storage_gb ?? "—"} GB</div>
                    <div><strong>GPU:</strong> {nodeEditor.draft.gpu || "none"}</div>
                    <div><strong>Volume Root:</strong> {nodeEditor.draft.volume_root}</div>
                    <div><strong>Docker Net:</strong> {nodeEditor.draft.docker_network}</div>
                  </div>
                </div>
              )}

              {stepperStep === 7 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <h3>Step 7: Playbook Validation Console</h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <span className={`pill ${onboardingStatus === "success" ? "pill-ok" : onboardingStatus === "failed" ? "pill-error" : "pill-warn"}`}>
                      {onboardingStatus === "success" ? "Onboarding Successful" : onboardingStatus === "failed" ? "Onboarding Failed" : "Executing Ansible Playbook..."}
                    </span>
                    {onboardingStatus !== "success" && onboardingStatus !== "failed" && (
                      <div className="spinner-micro"></div>
                    )}
                  </div>
                  
                  <p style={{ fontSize: "0.85rem", color: "var(--ink-3)" }}>
                    Streaming Ansible orchestration logs below:
                  </p>

                  <pre style={{
                    margin: 0,
                    padding: "1rem",
                    borderRadius: "10px",
                    background: "#010307",
                    color: onboardingStatus === "failed" ? "var(--err)" : "#34d399",
                    overflowX: "auto",
                    fontSize: "0.75rem",
                    fontFamily: "var(--mono)",
                    border: onboardingStatus === "failed" ? "1px solid var(--err-bg)" : "1px solid var(--navy-500)",
                    boxShadow: "0 0 15px rgba(99, 102, 241, 0.15)",
                    whiteSpace: "pre-wrap",
                    textAlign: "left",
                    maxHeight: "300px",
                    overflowY: "auto"
                  }}>
                    <code>{onboardingOutput || onboardingError || "Initializing host connection via SSH..."}</code>
                  </pre>
                </div>
              )}
            </div>

            <div className="drawer-foot" style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
              <button className="btn btn-secondary" disabled={stepperStep === 1 || stepperStep === 7} onClick={() => setStepperStep(prev => prev - 1)}>Back</button>
              {stepperStep < 6 ? (
                <button className="btn btn-primary" onClick={() => setStepperStep(prev => prev + 1)}>Next</button>
              ) : stepperStep === 6 ? (
                <button className="btn btn-primary" onClick={async () => {
                  const createdNode = await saveNodeEditor();
                  if (createdNode) {
                    setOnboardingStatus("running");
                    setOnboardingOutput("Initializing host connection via SSH...");
                    setOnboardingError("");
                    setStepperStep(7);
                    try {
                      const job = await api<{ id: number; status: string; output: string; error: string }>("/api/nodes/" + createdNode.id + "/validate", {
                        method: "POST",
                      });
                      setOnboardingJobId(job.id);
                      setOnboardingStatus(job.status);
                      setOnboardingOutput(job.output || "");
                      setOnboardingError(job.error || "");
                      pollOnboardingJob(createdNode.id, job.id);
                    } catch (err: any) {
                      setOnboardingStatus("failed");
                      setOnboardingError(err.message || "Failed to trigger node validation.");
                    }
                  }
                }}>Launch Node</button>
              ) : (
                <button className="btn btn-primary" onClick={() => {
                  setStepperDrawerVisible(false);
                  setStepperStep(1);
                }}>Finish</button>
              )}
            </div>
          </aside>
        </>
      )}
    </>
  );

}
