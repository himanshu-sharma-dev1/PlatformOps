// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import {
  filterCatalogItems,
  CATALOG_DRAG_MIME,
  CATALOG_CATEGORY_CHIPS,
  SVC_INSTALL_STEPS,
  NODE_PROVISION_STEPS,
  NODE_CLOUD_PROVIDERS,
  buttonLoadingClass,
  installButtonLabel,
  resolveInstallMode,
  busyClassName,
  buildNodeReviewRows,
} from "../platform/ux/clusterUx";
import { api } from "../api/client";

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
        const chips = CATALOG_CATEGORY_CHIPS;
        return (
        <>
          <div className="drawer-backdrop open" style={{ display: "block" }} onClick={() => setCatalogDrawerVisible(false)} />
          <aside className="drawer catalog-drawer open" style={{ display: "flex", flexDirection: "column", right: 0 }} data-ux="catalog-drawer">
            <div className="drawer-head">
              <div>
                <h2 style={{ fontSize: "1.5rem", fontFamily: "var(--display)", margin: 0 }}>Service catalog</h2>
                <div className="sub">
                  {filtered.length} of {(catalog || []).length} cards · click or drag onto the service stack
                </div>
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


      {catalogOnboarding.visible && catalogOnboarding.card && (() => {
        const step = Number(catalogOnboarding.step || 1);
        const isEdit = catalogOnboarding.mode === "edit";
        const card = catalogOnboarding.card;
        const nodeName =
          nodes.find((n) => n.id === catalogOnboarding.nodeId)?.name ||
          `node-${catalogOnboarding.nodeId}`;
        const letter = String(card.name || card.service_key || "S").charAt(0).toUpperCase();
        const goStep = (n: number) => setCatalogOnboarding((c) => ({ ...c, step: n, error: "" }));
        return (
        <>
          <div className="drawer-backdrop open" style={{ display: "block", zIndex: 105 }} onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))} />
          <aside
            className={`drawer svc-config-drawer open ${catalogOnboarding.creating ? "is-busy" : ""}`}
            style={{ display: "flex", flexDirection: "column", zIndex: 110, width: "min(640px, 100vw)" }}
            data-ux="svc-config-drawer"
            data-step={step}
          >
            <div className="drawer-head">
              <div>
                <h2 style={{ margin: 0, fontSize: "1.25rem", fontFamily: "var(--display)" }}>
                  {isEdit ? "Edit service " : "Configure service "}
                  {isEdit ? <span className="edit-badge" data-ux="svc-edit-badge">EDIT</span> : null}
                </h2>
                <div className="sub">
                  {isEdit ? "Update" : "Install"} <strong>{card.name}</strong> · dForm · MANUAL/ANSIBLE · expose
                </div>
              </div>
              <button type="button" className="icon-btn" onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))} aria-label="Close">
                <svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>

            {/* cP data-svc-step stepper */}
            <div className="stepper" data-ux="svc-install-stepper">
              {SVC_INSTALL_STEPS.map((label, idx) => {
                const n = idx + 1;
                const cls = n === step ? "step active" : n < step ? "step done" : "step";
                return (
                  <div
                    key={label}
                    className={cls}
                    data-svc-step={n}
                    onClick={() => {
                      // allow going back freely; forward only if setup complete
                      if (n <= step || (n === 2 && catalogOnboarding.nodeId)) goStep(n);
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <span className="n">{n}</span>
                    {label}
                  </div>
                );
              })}
            </div>

            <div className="svc-config-banner">
              <div className="ico" id="cfgIco">{letter}</div>
              <div className="info">
                <div className="nm" id="cfgName">{card.name}</div>
                <div className="meta" id="cfgMeta">
                  {isEdit ? "editing on" : "to be installed on"} {nodeName}
                  {" · "}
                  {card.service_key || card.kind || "service"}
                </div>
              </div>
            </div>

            <div className={`drawer-body ${catalogOnboarding.creating ? "is-busy" : ""}`} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* STEP 1 — Setup */}
              {step === 1 && (
                <div className="step-pane active" data-svc-step-content="1">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Identity</div>
                  <div className="field">
                    <label>Service name</label>
                    <input
                      className="input"
                      id="svc-name"
                      value={catalogOnboarding.customName}
                      placeholder="Leave blank to use catalog name"
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, customName: e.target.value }))}
                    />
                    <div className="hint">Used as the service display and runtime name. Must remain unique within the cluster.</div>
                  </div>
                  <div className="field">
                    <label>Target node</label>
                    <select
                      value={catalogOnboarding.nodeId}
                      disabled={isEdit}
                      onChange={async (e) => {
                        const nextNodeId = Number(e.target.value);
                        setCatalogOnboarding((current) => ({ ...current, nodeId: nextNodeId, error: "" }));
                        if (card) {
                          try {
                            const schema = await loadInstallSchemaFor(card, nextNodeId);
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
                    <label>Continue into</label>
                    <select
                      value={catalogOnboarding.nextAction}
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, nextAction: e.target.value as "overview" | "config" | "deploy" }))}
                    >
                      <option value="deploy">Deployment control (ANSIBLE)</option>
                      <option value="overview">Register only (good for MANUAL)</option>
                      {card.configurable && <option value="config">Config manager</option>}
                    </select>
                  </div>
                  <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "0.85rem", background: "rgba(255,255,255,0.02)" }}>
                    <small style={{ color: "var(--ink-4)" }}>Catalog defaults</small>
                    <div className="tags" style={{ marginTop: 6 }}>
                      <span>{card.kind}</span>
                      <span>{card.subsystem}</span>
                      <span>{(card.ports || []).length} port(s)</span>
                      <span>{(card.dependencies || []).length} dep(s)</span>
                      {card.image ? <span><code>{card.image}</code></span> : null}
                    </div>
                    {card.description ? (
                      <p style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "var(--ink-3)" }}>{card.description}</p>
                    ) : null}
                  </div>
                </div>
              )}

              {/* STEP 2 — Config */}
              {step === 2 && (
                <div className="step-pane active" data-svc-step-content="2">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Install schema</div>
                  {catalogOnboarding.installSchema ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {Array.from(new Set(catalogOnboarding.installSchema.fields.map((field) => field.section))).map((section) => (
                        <div key={`install-section-${section}`} style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.75rem" }}>
                          <strong style={{ display: "block", marginBottom: "0.55rem", fontSize: "0.85rem", color: "var(--ink-3)" }}>{section}</strong>
                          <div style={{ display: "grid", gap: "0.6rem" }}>
                            {(catalogOnboarding.installSchema?.fields ?? [])
                              .filter((field) => field.section === section && field.key !== "name")
                              .filter((field) => {
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
                                      style={{ minHeight: 72, fontFamily: "var(--mono)", fontSize: "0.76rem" }}
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
                  ) : (
                    <p style={{ color: "var(--ink-4)", fontSize: "0.85rem" }}>Loading install schema…</p>
                  )}
                  {catalogOnboarding.installSchema?.summary ? (
                    <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>{catalogOnboarding.installSchema.summary}</div>
                  ) : null}
                  <div className="field" style={{ marginTop: "0.5rem" }}>
                    <label>Advanced contract overrides (JSON)</label>
                    <textarea
                      className="input"
                      style={{ minHeight: 96, fontFamily: "var(--mono)", fontSize: "0.78rem" }}
                      value={catalogOnboarding.overridesText}
                      onChange={(e) => setCatalogOnboarding((current) => ({ ...current, overridesText: e.target.value }))}
                      placeholder='{"ports":["8090:8080"]}'
                    />
                  </div>
                </div>
              )}

              {catalogOnboarding.registeredService && (
                <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                    <strong>Registration summary</strong>
                    <span className="pill pill-ok">service card registered</span>
                  </div>
                  <div style={{ marginTop: "0.35rem", color: "var(--ink-3)", fontSize: "0.85rem" }}>
                    {catalogOnboarding.registeredService.name} on {nodeName}.
                  </div>
                  <div style={{ marginTop: "0.7rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={async () => {
                        await loadServiceSummary(catalogOnboarding.registeredService!.id);
                        setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
                      }}
                    >
                      Stay in overview
                    </button>
                    {card.configurable && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={async () => {
                          await loadConfig(catalogOnboarding.registeredService!, configSource);
                          setActiveView("config");
                          setCatalogOnboarding((current) => ({ ...current, visible: false, registeredService: null }));
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
                <div style={{ padding: "0.75rem", borderRadius: 10, background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.25)", color: "rgb(248, 113, 113)", fontSize: "0.82rem" }}>
                  <strong>Conflict detected:</strong> {catalogOnboarding.validationConflict}
                </div>
              )}
              {catalogOnboarding.validating && (
                <p style={{ color: "var(--ink-4)", fontSize: "0.78rem", margin: 0 }}>Checking port and name availability...</p>
              )}
              {catalogOnboarding.error && <p style={{ color: "var(--err)", fontSize: "0.82rem", margin: 0 }}>{catalogOnboarding.error}</p>}
            </div>

            <div className="drawer-foot" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }} data-ux="svc-config-foot">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setCatalogOnboarding((current) => ({ ...current, visible: false, error: "", registeredService: null }))}
              >
                Cancel
              </button>
              {step > 1 ? (
                <button type="button" className="btn btn-secondary btn-sm" id="prevSvcStep" onClick={() => goStep(step - 1)}>
                  ← Back
                </button>
              ) : null}
              {step < 2 ? (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  id="nextSvcStep"
                  onClick={() => {
                    if (!catalogOnboarding.nodeId) {
                      setCatalogOnboarding((c) => ({ ...c, error: "Choose a valid target node." }));
                      return;
                    }
                    goStep(2);
                  }}
                >
                  Continue →
                </button>
              ) : (
                <button
                  type="button"
                  className={`btn btn-primary btn-sm ${catalogOnboarding.creating ? "btn-loading" : ""}`}
                  id={isEdit ? "svcSaveBtn" : "installSvc"}
                  onClick={confirmCatalogOnboarding}
                  disabled={catalogOnboarding.creating || catalogOnboarding.validating || Boolean(catalogOnboarding.validationConflict)}
                  data-ux="catalog-onboard-submit"
                >
                  {catalogOnboarding.creating && <span className="btn-spinner" />}
                  {installButtonLabel({
                    mode: isEdit ? "edit" : "add",
                    installMode: resolveInstallMode(catalogOnboarding.installFieldValues),
                    creating: catalogOnboarding.creating,
                  })}
                </button>
              )}
            </div>
          </aside>
        </>
        );
      })()}

      {/* NODE PROVISIONING STEPPER DRAWER — cP Cloud/Hardware/Config/Network/Firewall/Review */}
      {stepperDrawerVisible && (() => {
        const isEdit = nodeEditor?.mode === "edit";
        const draft = nodeEditor?.draft || {};
        const provider = draft.provider || (nodePreset?.startsWith("aws") ? "aws" : "dc");
        const setDraft = (patch) => setNodeEditor((prev) => ({ ...prev, draft: { ...prev.draft, ...patch }, error: "" }));
        const stepLabels = NODE_PROVISION_STEPS;
        const showSteps = stepperStep <= 6;
        return (
        <>
          <div className="drawer-backdrop open" style={{ display: "block" }} onClick={() => { if (stepperStep !== 7) setStepperDrawerVisible(false); }} />
          <aside
            className={busyClassName(`drawer open ${nodeEditor?.error ? "" : ""}`, Boolean((p.actionBusy || {}).saveNode))}
            style={{ display: "flex", flexDirection: "column", gap: "0", right: 0, width: "min(560px, 100vw)" }}
            data-ux="node-provision-drawer"
            data-busy={(p.actionBusy || {}).saveNode ? "true" : "false"}
          >
            <div className="drawer-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: "1.35rem", fontFamily: "var(--display)", margin: 0 }}>
                {isEdit ? "Edit node " : "Provision new node "}
                {isEdit ? <span className="edit-badge" data-ux="node-edit-badge">EDIT</span> : null}
              </h2>
              <button className="icon-btn" onClick={() => { setStepperDrawerVisible(false); setStepperStep(1); }} aria-label="Close">
                <svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>

            {showSteps && (
              <div className="stepper" data-ux="node-provision-stepper" style={{ flexWrap: "wrap" }}>
                {stepLabels.map((label, idx) => {
                  const n = idx + 1;
                  const cls = n === stepperStep ? "step active" : n < stepperStep ? "step done" : "step";
                  return (
                    <div
                      key={label}
                      className={cls}
                      data-step={n}
                      onClick={() => { if (n < stepperStep || (n <= stepperStep + 1 && n <= 6)) setStepperStep(n); }}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="n">{n}</span>
                      {label}
                    </div>
                  );
                })}
              </div>
            )}

            <div className="drawer-body" style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
              {stepperStep === 1 && (
                <div className="step-pane active" data-step-content="1">
                  <div className="field">
                    <label>Node name</label>
                    <input type="text" className="input" placeholder="e.g. node-13" value={draft.name || ""} onChange={(e) => setDraft({ name: e.target.value })} />
                    <div className="hint">Must be unique within the cluster. Used in inventory and DNS labels.</div>
                  </div>
                  <div className="section-head-sm">Provider</div>
                  <div className="cloud-picker" data-ux="cloud-picker">
                    {NODE_CLOUD_PROVIDERS.map((cloud) => (
                      <div
                        key={cloud.id}
                        className={`cloud-card ${provider === cloud.id ? "selected" : ""}`}
                        data-cloud={cloud.id}
                        onClick={() => {
                          setDraft({ provider: cloud.id, environment: cloud.id === "dc" ? "local" : cloud.id });
                          applyNodePreset?.(cloud.preset);
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="ico">{cloud.label}</div>
                        <div className="nm">{cloud.name}</div>
                        <div className="desc">{cloud.desc}</div>
                      </div>
                    ))}
                  </div>
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Preset profile</label>
                    <select value={nodePreset} onChange={(e) => applyNodePreset(e.target.value as any)}>
                      <option value="local-default">Local / bare metal default</option>
                      <option value="aws-general">AWS general (EC2)</option>
                      <option value="aws-gpu">AWS accelerated GPU</option>
                    </select>
                  </div>
                  {selectedCluster ? (
                    <div className="hint">Parent cluster: <strong>{selectedCluster.name}</strong></div>
                  ) : (
                    <div className="field">
                      <label>Parent cluster</label>
                      <select
                        value={draft.cluster_id || ""}
                        onChange={(e) => setDraft({ cluster_id: Number(e.target.value) })}
                      >
                        <option value="">Select cluster…</option>
                        {(p.clusters || []).map((c) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}

              {stepperStep === 2 && (
                <div className="step-pane active" data-step-content="2">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Compute</div>
                  <div className="field">
                    <label>vCPU cores</label>
                    <input type="number" className="input" min={1} value={draft.cpu_cores ?? 4} onChange={(e) => setDraft({ cpu_cores: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Memory (GB)</label>
                    <input type="number" className="input" min={1} value={draft.memory_gb ?? 16} onChange={(e) => setDraft({ memory_gb: e.target.value })} />
                  </div>
                  <div className="section-head-sm">Storage</div>
                  <div className="field">
                    <label>Primary SSD (GB)</label>
                    <input type="number" className="input" min={20} value={draft.storage_gb ?? 100} onChange={(e) => setDraft({ storage_gb: e.target.value })} />
                  </div>
                  <div className="section-head-sm">GPU (optional)</div>
                  <div className="field">
                    <label>GPU type</label>
                    <input type="text" className="input" value={draft.gpu ?? "none"} onChange={(e) => setDraft({ gpu: e.target.value })} placeholder="none · A10G · A100" />
                  </div>
                </div>
              )}

              {stepperStep === 3 && (
                <div className="step-pane active" data-step-content="3">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>SSH access</div>
                  <div className="field">
                    <label>SSH host / IP</label>
                    <input type="text" className="input" value={draft.host || ""} onChange={(e) => setDraft({ host: e.target.value })} placeholder="e.g. 65.2.63.24" />
                  </div>
                  <div className="field">
                    <label>SSH username</label>
                    <input type="text" className="input" value={draft.ssh_user || ""} onChange={(e) => setDraft({ ssh_user: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>SSH secret reference</label>
                    <input type="text" className="input" placeholder="env://PLATFORMOPS_NODE_KEY" value={draft.ssh_secret_ref || ""} onChange={(e) => setDraft({ ssh_secret_ref: e.target.value })} />
                    <div className="hint">Use an operator-managed env:// or file:// reference. Secret material is never stored.</div>
                  </div>
                  <div className="field">
                    <label>Mounted key path (optional)</label>
                    <input type="text" className="input" placeholder="/run/secrets/node-key" value={draft.ssh_key_path || ""} onChange={(e) => setDraft({ ssh_key_path: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Host key SHA256 fingerprint</label>
                    <input type="text" className="input" placeholder="SHA256:…" value={draft.host_key_fingerprint || ""} onChange={(e) => setDraft({ host_key_fingerprint: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Known-hosts file reference</label>
                    <input type="text" className="input" placeholder="file:///run/secrets/known_hosts" value={draft.known_hosts_ref || ""} onChange={(e) => setDraft({ known_hosts_ref: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>One-shot SSH password (optional)</label>
                    <input type="password" className="input" autoComplete="new-password" value={draft.ssh_password || ""} onChange={(e) => setDraft({ ssh_password: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>One-shot PEM private key (optional)</label>
                    <textarea
                      className="input"
                      style={{ minHeight: 90, fontFamily: "var(--mono)", fontSize: "0.75rem" }}
                      value={draft.ssh_private_key || ""}
                      onChange={(e) => setDraft({ ssh_private_key: e.target.value })}
                      placeholder="-----BEGIN RSA PRIVATE KEY-----"
                    />
                    <div className="hint">Used only for this request; it is discarded and never persisted. Prefer a secret reference for later jobs.</div>
                  </div>
                </div>
              )}

              {stepperStep === 4 && (
                <div className="step-pane active" data-step-content="4">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Network & storage paths</div>
                  <div className="field">
                    <label>Docker network namespace</label>
                    <input type="text" className="input" value={draft.docker_network || ""} onChange={(e) => setDraft({ docker_network: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Volume root directory</label>
                    <input type="text" className="input" value={draft.volume_root || ""} onChange={(e) => setDraft({ volume_root: e.target.value })} />
                  </div>
                </div>
              )}

              {stepperStep === 5 && (
                <div className="step-pane active" data-step-content="5">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Firewall policies</div>
                  <div className="field">
                    <label>Allowed ingress ports</label>
                    <input
                      type="text"
                      className="input"
                      value={draft.ingress_ports || "22, 80, 443, 8080"}
                      onChange={(e) => setDraft({ ingress_ports: e.target.value })}
                    />
                    <div className="hint">Recorded on the node card for operator reference (host firewall apply is environment-specific).</div>
                  </div>
                </div>
              )}

              {stepperStep === 6 && (
                <div className="step-pane active" data-step-content="6">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Review</div>
                  <div
                    className="node-review-grid"
                    data-ux="node-review"
                    style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: 10, fontSize: "0.85rem", display: "grid", gap: 8 }}
                  >
                    {buildNodeReviewRows(
                      { ...draft, provider },
                      { isEdit }
                    ).map((row) => (
                      <div key={row.id} id={row.id} style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 8 }}>
                        <span style={{ color: "var(--ink-4)" }}>{row.label}</span>
                        <strong style={{ fontWeight: 600, wordBreak: "break-word" }}>{row.value}</strong>
                      </div>
                    ))}
                  </div>
                  <p className="hint" style={{ marginTop: 8 }}>
                    {isEdit
                      ? 'Pressing "Save" updates node inventory (SSH / facts).'
                      : 'Pressing "Provision" registers the node then runs validation playbook.'}
                  </p>
                </div>
              )}

              {stepperStep === 7 && (
                <div className="step-pane active" data-step-content="7">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Playbook validation console</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <span className={`pill ${onboardingStatus === "success" ? "pill-ok" : onboardingStatus === "failed" ? "pill-error" : "pill-warn"}`}>
                      {onboardingStatus === "success" ? "Onboarding successful" : onboardingStatus === "failed" ? "Onboarding failed" : "Executing Ansible playbook…"}
                    </span>
                  </div>
                  <pre style={{
                    margin: 0, padding: "1rem", borderRadius: 10, background: "#010307",
                    color: onboardingStatus === "failed" ? "var(--err)" : "#34d399",
                    overflowX: "auto", fontSize: "0.75rem", fontFamily: "var(--mono)",
                    border: onboardingStatus === "failed" ? "1px solid var(--err-bg)" : "1px solid var(--navy-500)",
                    whiteSpace: "pre-wrap", maxHeight: 300, overflowY: "auto",
                  }}>
                    <code>{onboardingOutput || onboardingError || "Initializing host connection via SSH..."}</code>
                  </pre>
                </div>
              )}

              {nodeEditor?.error ? (
                <p style={{ color: "var(--err)", fontSize: "0.85rem", margin: 0 }}>{nodeEditor.error}</p>
              ) : null}
            </div>

            <div className="drawer-foot" style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--line)", padding: "0.85rem 1.25rem" }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={stepperStep === 1 || stepperStep === 7}
                onClick={() => setStepperStep((prev) => prev - 1)}
              >
                ← Back
              </button>
              {stepperStep < 6 ? (
                <button className="btn btn-primary btn-sm" onClick={() => setStepperStep((prev) => prev + 1)}>Continue →</button>
              ) : stepperStep === 6 ? (
                <button
                  className={buttonLoadingClass("btn btn-primary btn-sm", Boolean((p.actionBusy || {}).saveNode))}
                  disabled={Boolean((p.actionBusy || {}).saveNode)}
                  data-ux="node-provision-submit"
                  onClick={async () => {
                    const createdNode = await saveNodeEditor();
                    if (!createdNode) return;
                    if (isEdit) {
                      setStepperDrawerVisible(false);
                      setStepperStep(1);
                      setNotice?.(`Saved node ${createdNode.name || draft.name}`);
                      return;
                    }
                    setOnboardingStatus("running");
                    setOnboardingOutput("Initializing host connection via SSH...");
                    setOnboardingError("");
                    setStepperStep(7);
                    try {
                      const job = await api("/api/nodes/" + createdNode.id + "/validate", { method: "POST" });
                      setOnboardingJobId(job.id);
                      setOnboardingStatus(job.status);
                      setOnboardingOutput(job.output || "");
                      setOnboardingError(job.error || "");
                      pollOnboardingJob(createdNode.id, job.id);
                    } catch (err: any) {
                      setOnboardingStatus("failed");
                      setOnboardingError(err.message || "Failed to trigger node validation.");
                    }
                  }}
                >
                  {(p.actionBusy || {}).saveNode && <span className="btn-spinner" />}
                  {isEdit ? "Save" : "Provision"}
                </button>
              ) : (
                <button className="btn btn-primary btn-sm" onClick={() => { setStepperDrawerVisible(false); setStepperStep(1); }}>Finish</button>
              )}
            </div>
          </aside>
        </>
        );
      })()}
    </>
  );

}
