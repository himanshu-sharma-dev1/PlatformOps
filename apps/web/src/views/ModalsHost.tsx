// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import {
  CLUSTER_EDITOR_STEPS,
  CLUSTER_REPO_PROVIDERS,
  CLUSTER_REGISTRY_PROVIDERS,
  CLUSTER_REPO_AUTH_TABS,
  buttonLoadingClass,
} from "../platform/ux/clusterUx";

/** ModalsHost — Phase 1 extracted page JSX. */
export function ModalsHost() {
  const p = usePlatform() as any;
  const approveForceDeleteApproval = p.approveForceDeleteApproval;
  const approveReleaseApprovalRequest = p.approveReleaseApprovalRequest;
  const archivePreviewLines = p.archivePreviewLines;
  const archivePreviewLoading = p.archivePreviewLoading;
  const archives = p.archives;
  const autoInstallDependencies = p.autoInstallDependencies;
  const clusterEditor = p.clusterEditor;
  const confirmApprovedRelease = p.confirmApprovedRelease;
  const confirmDelete = p.confirmDelete;
  const createReleaseApprovalRequest = p.createReleaseApprovalRequest;
  const deleteModal = p.deleteModal;
  const deploymentModal = p.deploymentModal;
  const diagnostics = p.diagnostics;
  const downloadArchive = p.downloadArchive;
  const executeDeploymentModal = p.executeDeploymentModal;
  const installMissingDependencies = p.installMissingDependencies;
  const job = p.job;
  const nodeEditor = p.nodeEditor;
  const openDeploymentModal = p.openDeploymentModal;
  const plan = p.plan;
  const rejectForceDeleteApproval = p.rejectForceDeleteApproval;
  const releaseApprovalModal = p.releaseApprovalModal;
  const releaseApprovals = p.releaseApprovals;
  const renameModal = p.renameModal;
  const renameSnapshot = p.renameSnapshot;
  const requestForceDeleteApproval = p.requestForceDeleteApproval;
  const revokeReleaseApprovalRequest = p.revokeReleaseApprovalRequest;
  const runLogBackfill = p.runLogBackfill;
  const saveClusterEditor = p.saveClusterEditor;
  const saveNodeEditor = p.saveNodeEditor;
  const selectedArchive = p.selectedArchive;
  const selectedService = p.selectedService;
  const services = p.services;
  const setClusterEditor = p.setClusterEditor;
  const setDeleteModal = p.setDeleteModal;
  const setDeploymentModal = p.setDeploymentModal;
  const setNodeEditor = p.setNodeEditor;
  const setReleaseApprovalModal = p.setReleaseApprovalModal;
  const setRenameModal = p.setRenameModal;
  const setSelectedArchive = p.setSelectedArchive;
  const testClusterRegistryConnection = p.testClusterRegistryConnection;
  const testClusterRepoConnection = p.testClusterRepoConnection;
  const actionBusy = (p.actionBusy || {}) as Record<string, boolean>;
  const deleteBusy = Boolean(actionBusy.delete);
  const installDepsBusy = Boolean(actionBusy.installDeps);
  const actionBlocker = p.actionBlocker;
  const setActionBlocker = p.setActionBlocker;
  const setCatalogDrawerVisible = p.setCatalogDrawerVisible;
  const setStepperDrawerVisible = p.setStepperDrawerVisible;
  const openNodeCreate = p.openNodeCreate;


  return (
    <>
      {/* Action blocker — cPlatform actionBlockerModal (deps / provision / catalog) */}
      {actionBlocker?.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 120 }} data-ux="action-blocker">
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "460px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            {actionBlocker.eyebrow ? (
              <div style={{ fontSize: "0.7rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-4)", fontWeight: 600 }}>
                {actionBlocker.eyebrow}
              </div>
            ) : null}
            <h3 style={{ margin: 0 }}>{actionBlocker.title || "Action blocked"}</h3>
            <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)" }}>{actionBlocker.message}</p>
            {Array.isArray(actionBlocker.items) && actionBlocker.items.length > 0 ? (
              <div className="action-blocker-list" style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 220, overflow: "auto" }}>
                {actionBlocker.items.map((item: any, idx: number) => (
                  <div
                    key={`${item.name}-${idx}`}
                    className="action-modal-item"
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 10,
                      alignItems: "center",
                      border: "1px solid var(--line)",
                      borderRadius: 10,
                      padding: "0.65rem 0.75rem",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{item.name || "Item"}</div>
                      {item.meta ? <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>{item.meta}</div> : null}
                    </div>
                    {item.service_key ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setActionBlocker?.({ visible: false, message: "", items: [] });
                          setCatalogDrawerVisible?.(true);
                          // Best-effort: store key for catalog focus if controller supports it
                          if (typeof p.setSelectedPlacementServiceKey === "function" && item.service_key) {
                            p.setSelectedPlacementServiceKey(item.service_key);
                          }
                        }}
                      >
                        Install
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  const act = actionBlocker.secondaryAction;
                  setActionBlocker?.({ visible: false, message: "", secondaryLabel: "", secondaryAction: null, items: [] });
                  if (act === "catalog") setCatalogDrawerVisible?.(true);
                  if (act === "provision") {
                    openNodeCreate?.();
                    setStepperDrawerVisible?.(true);
                  }
                }}
              >
                {actionBlocker.secondaryLabel || "Close"}
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  const act = actionBlocker.primaryAction || actionBlocker.secondaryAction;
                  const keys = actionBlocker.missingServiceKeys || actionBlocker.items?.map((i: any) => i.service_key).filter(Boolean) || [];
                  setActionBlocker?.({ visible: false, message: "", secondaryLabel: "", secondaryAction: null, items: [] });
                  if (act === "install-first-missing" && keys[0] && typeof p.openDependencyTarget === "function" && p.selectedService) {
                    await p.openDependencyTarget(keys[0], "ensure");
                    return;
                  }
                  if (act === "catalog" || act === "install-first-missing") {
                    setCatalogDrawerVisible?.(true);
                    return;
                  }
                  if (act === "provision") {
                    openNodeCreate?.();
                    setStepperDrawerVisible?.(true);
                  }
                }}
              >
                {actionBlocker.primaryLabel || "Dismiss"}
              </button>
            </div>
          </GlassCard>
        </div>
      )}

      {/* RENAME MODAL */}
      {renameModal.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "400px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h3>Rename Snapshot</h3>
            <p style={{ margin: 0, fontSize: "0.9rem" }}>Enter a unique snapshot name for this service card configuration.</p>
            <input
              className="input"
              value={renameModal.value}
              onChange={(e) => setRenameModal(prev => ({ ...prev, value: e.target.value }))}
              placeholder="Snapshot name"
            />
            {renameModal.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{renameModal.error}</p>}
            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setRenameModal({ visible: false, snapshotId: 0, value: "", error: "" })}>Cancel</button>
              <button className="btn btn-primary btn-sm" onClick={renameSnapshot}>Save Name</button>
            </div>
          </GlassCard>
        </div>
      )}

      {/* CLUSTER EDITOR — right drawer 4-step wizard (cPlatform UX structure, PO skin) */}
      {clusterEditor.visible && (() => {
        const step = clusterEditor.step || 1;
        const setStep = p.setClusterEditorStep || ((n: number) => setClusterEditor((prev: any) => ({ ...prev, step: n, error: "" })));
        const advance = p.advanceClusterEditorStep || (() => setClusterEditor((prev: any) => ({ ...prev, step: Math.min(4, (prev.step || 1) + 1), error: "" })));
        const labels = [...CLUSTER_EDITOR_STEPS];
        const saving = Boolean(clusterEditor.saving);
        const actionBusy = p.actionBusy || {};
        const repoTest = clusterEditor.repoTest || { state: "idle", message: "" };
        const registryTest = clusterEditor.registryTest || { state: "idle", message: "" };
        const draft = clusterEditor.draft || {};
        const setDraft = (patch: any) => setClusterEditor((prev: any) => ({ ...prev, draft: { ...prev.draft, ...patch }, error: "" }));
        const close = () => setClusterEditor((prev: any) => ({ ...prev, visible: false, saving: false }));
        const repoAuth = draft.repo_auth || "pat";
        return (
        <>
          <div className="drawer-backdrop open" style={{ display: "block", zIndex: 55 }} onClick={close} />
          <aside className={`drawer open cluster-editor-drawer ${saving ? "is-busy" : ""}`} style={{ display: "flex", flexDirection: "column", zIndex: 60, width: "min(560px, 100vw)" }} data-ux="cluster-editor-drawer">
            <div className="drawer-head">
              <div>
                <h2 style={{ margin: 0, fontSize: "1.35rem", fontFamily: "var(--display)" }}>
                  {clusterEditor.mode === "create" ? "Create cluster " : "Cluster settings "}
                  {clusterEditor.mode === "edit" ? <span className="edit-badge">EDIT</span> : null}
                </h2>
                <div className="sub">Step {step} of 4 · {labels[step - 1]}</div>
              </div>
              <button type="button" className="icon-btn" onClick={close} aria-label="Close">
                <svg className="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div className="stepper" data-ux="cluster-editor-stepper">
              {labels.map((label, idx) => {
                const n = idx + 1;
                const cls = n === step ? "step active" : n < step ? "step done" : "step";
                return (
                  <div key={label} className={cls} data-step={n} onClick={() => setStep(n)} role="button" tabIndex={0}>
                    <span className="n">{n}</span>
                    {label}
                  </div>
                );
              })}
            </div>
            <div className={`drawer-body ${saving ? "is-busy" : ""}`} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              {step === 1 && (
                <div className="step-pane active" data-step-pane="1">
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Identity</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                    <div className="field">
                      <label>Cluster name <span className="req">*</span></label>
                      <input className="input" value={draft.name} onChange={(e) => setDraft({ name: e.target.value })} placeholder="e.g. prod-mumbai-1" />
                    </div>
                    <div className="field">
                      <label>Region</label>
                      <input className="input" value={draft.region} onChange={(e) => setDraft({ region: e.target.value })} placeholder="e.g. ap-south-1" />
                    </div>
                  </div>
                  <div className="field">
                    <label>Environment</label>
                    <select value={draft.environment} onChange={(e) => setDraft({ environment: e.target.value })}>
                      <option value="development">Development</option>
                      <option value="staging">Staging</option>
                      <option value="production">Production</option>
                      <option value="standalone">Standalone</option>
                      <option value="edge">Edge</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Description (optional)</label>
                    <input className="input" value={draft.description || ""} onChange={(e) => setDraft({ description: e.target.value })} placeholder="Short purpose note" />
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="step-pane active" data-step-pane="2">
                  <p className="hint" style={{ marginTop: 0 }}>
                    Where infrastructure-as-code for this cluster lives. The platform pulls from here when provisioning nodes or deploying services.
                  </p>
                  <div className="section-head-sm">Provider</div>
                  <div className="provider-grid" data-ux="repo-provider-grid">
                    {CLUSTER_REPO_PROVIDERS.map((prov) => (
                      <div
                        key={prov.id}
                        className={`provider-card ${draft.repo_type === prov.id ? "selected" : ""}`}
                        data-repo={prov.id}
                        onClick={() => setDraft({ repo_type: prov.id })}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="ico">{prov.label}</div>
                        <div className="nm">{prov.name}</div>
                      </div>
                    ))}
                  </div>
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Repository URL</label>
                    <input className="input" value={draft.repo_url} onChange={(e) => setDraft({ repo_url: e.target.value })} placeholder="https://github.com/org/repo.git" />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                    <div className="field">
                      <label>Branch</label>
                      <input className="input" value={draft.repo_branch} onChange={(e) => setDraft({ repo_branch: e.target.value })} />
                    </div>
                    <div className="field">
                      <label>Path (optional)</label>
                      <input className="input" value={draft.repo_path || ""} onChange={(e) => setDraft({ repo_path: e.target.value })} placeholder="clusters/prod/" />
                    </div>
                  </div>
                  <div className="section-head-sm">Authentication</div>
                  <div className="auth-tabs" data-ux="repo-auth-tabs">
                    {CLUSTER_REPO_AUTH_TABS.map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        className={`auth-tab ${repoAuth === tab.id ? "active" : ""}`}
                        onClick={() => setDraft({ repo_auth: tab.id })}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                  {repoAuth === "pat" && (
                    <div className="field">
                      <label>Personal access token</label>
                      {clusterEditor.mode === "edit" && (
                        <div className="secret-replace-row">
                          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem", margin: 0 }}>
                            <input
                              type="checkbox"
                              checked={Boolean(clusterEditor.replaceRepoSecret)}
                              onChange={(e) => setClusterEditor((prev) => ({ ...prev, replaceRepoSecret: e.target.checked }))}
                            />
                            Replace secret
                          </label>
                          {!clusterEditor.replaceRepoSecret && <span style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Keeping existing token</span>}
                        </div>
                      )}
                      <input
                        className="input"
                        type="password"
                        disabled={clusterEditor.mode === "edit" && !clusterEditor.replaceRepoSecret}
                        value={draft.repo_token}
                        onChange={(e) => setDraft({ repo_token: e.target.value })}
                        placeholder={clusterEditor.mode === "edit" && !clusterEditor.replaceRepoSecret ? "••••••••" : "ghp_… optional"}
                      />
                      <div className="hint">Stored for pull operations. Leave blank on edit unless Replace secret is checked.</div>
                    </div>
                  )}
                  {repoAuth === "ssh" && (
                    <div className="field">
                      <label>Private SSH key</label>
                      {clusterEditor.mode === "edit" && (
                        <div className="secret-replace-row">
                          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem", margin: 0 }}>
                            <input
                              type="checkbox"
                              checked={Boolean(clusterEditor.replaceRepoSecret)}
                              onChange={(e) => setClusterEditor((prev) => ({ ...prev, replaceRepoSecret: e.target.checked }))}
                            />
                            Replace secret
                          </label>
                        </div>
                      )}
                      <textarea
                        className="input"
                        style={{ minHeight: 88, fontFamily: "var(--mono)", fontSize: "0.75rem" }}
                        disabled={clusterEditor.mode === "edit" && !clusterEditor.replaceRepoSecret}
                        value={draft.repo_token}
                        onChange={(e) => setDraft({ repo_token: e.target.value })}
                        placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                      />
                    </div>
                  )}
                  {repoAuth === "none" && (
                    <p className="hint">No authentication — public repos / read-only operations only.</p>
                  )}
                  <div>
                    <button
                      type="button"
                      className={`btn btn-secondary btn-sm ${actionBusy["test-repo"] || repoTest.state === "testing" ? "btn-loading" : ""}`}
                      disabled={actionBusy["test-repo"] || repoTest.state === "testing"}
                      onClick={testClusterRepoConnection}
                    >
                      {(actionBusy["test-repo"] || repoTest.state === "testing") && <span className="btn-spinner" />}
                      Test connection
                    </button>
                    {repoTest.state !== "idle" && (
                      <div className={`test-conn-result ${repoTest.state}`} data-ux="repo-test-result">{repoTest.message}</div>
                    )}
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="step-pane active" data-step-pane="3">
                  <p className="hint" style={{ marginTop: 0 }}>
                    Where container images are stored. Nodes pull from here when services are deployed.
                  </p>
                  <div className="section-head-sm">Registry</div>
                  <div className="provider-grid" data-ux="registry-provider-grid">
                    {CLUSTER_REGISTRY_PROVIDERS.map((prov) => (
                      <div
                        key={prov.id}
                        className={`provider-card ${draft.registry_type === prov.id ? "selected" : ""}`}
                        data-registry={prov.id}
                        onClick={() => setDraft({ registry_type: prov.id })}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="ico">{prov.label}</div>
                        <div className="nm">{prov.name}</div>
                      </div>
                    ))}
                  </div>
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Registry URL</label>
                    <input className="input" value={draft.registry_url} onChange={(e) => setDraft({ registry_url: e.target.value })} placeholder="registry-1.docker.io" />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                    <div className="field">
                      <label>Namespace / org</label>
                      <input className="input" value={draft.registry_namespace || ""} onChange={(e) => setDraft({ registry_namespace: e.target.value })} placeholder="optional" />
                    </div>
                    <div className="field">
                      <label>Username</label>
                      <input className="input" value={draft.registry_user} onChange={(e) => setDraft({ registry_user: e.target.value })} />
                    </div>
                  </div>
                  <div className="field">
                    <label>Password / access key</label>
                    {clusterEditor.mode === "edit" && (
                      <div className="secret-replace-row">
                        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem", margin: 0 }}>
                          <input
                            type="checkbox"
                            checked={Boolean(clusterEditor.replaceRegistrySecret)}
                            onChange={(e) => setClusterEditor((prev) => ({ ...prev, replaceRegistrySecret: e.target.checked }))}
                          />
                          Replace secret
                        </label>
                        {!clusterEditor.replaceRegistrySecret && <span style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Keeping existing password</span>}
                      </div>
                    )}
                    <input
                      className="input"
                      type="password"
                      disabled={clusterEditor.mode === "edit" && !clusterEditor.replaceRegistrySecret}
                      value={draft.registry_password}
                      onChange={(e) => setDraft({ registry_password: e.target.value })}
                      placeholder={clusterEditor.mode === "edit" && !clusterEditor.replaceRegistrySecret ? "••••••••" : ""}
                    />
                  </div>
                  <div>
                    <button
                      type="button"
                      className={`btn btn-secondary btn-sm ${actionBusy["test-registry"] || registryTest.state === "testing" ? "btn-loading" : ""}`}
                      disabled={actionBusy["test-registry"] || registryTest.state === "testing"}
                      onClick={testClusterRegistryConnection}
                    >
                      {(actionBusy["test-registry"] || registryTest.state === "testing") && <span className="btn-spinner" />}
                      Test connection
                    </button>
                    {registryTest.state !== "idle" && (
                      <div className={`test-conn-result ${registryTest.state}`} data-ux="registry-test-result">{registryTest.message}</div>
                    )}
                  </div>
                </div>
              )}

              {step === 4 && (
                <div className="step-pane active" data-step-pane="4" style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "1rem", background: "rgba(0,0,0,0.12)", fontSize: "0.88rem", display: "flex", flexDirection: "column", gap: 8 }}>
                  <div className="section-head-sm" style={{ marginTop: 0 }}>Identity</div>
                  <div><strong>Name:</strong> {draft.name || "—"}</div>
                  <div><strong>Region / env:</strong> {draft.region || "—"} · {draft.environment}</div>
                  {draft.description ? <div><strong>Description:</strong> {draft.description}</div> : null}
                  <div className="section-head-sm">Repository</div>
                  <div><strong>Provider:</strong> {draft.repo_type} · auth {repoAuth}</div>
                  <div><strong>URL:</strong> {draft.repo_url || "(none)"} @ {draft.repo_branch}{draft.repo_path ? ` · path ${draft.repo_path}` : ""}</div>
                  <div className="section-head-sm">Image store</div>
                  <div><strong>Registry:</strong> {draft.registry_type} · {draft.registry_url || "(default)"}{draft.registry_namespace ? ` / ${draft.registry_namespace}` : ""}</div>
                  <p className="hint" style={{ marginBottom: 0 }}>
                    Confirm and {clusterEditor.mode === "create" ? "create" : "save"}. Secrets on edit only update when Replace secret is checked.
                  </p>
                </div>
              )}
              {clusterEditor.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{clusterEditor.error}</p>}
            </div>
            <div className="drawer-foot" style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
              <button className="btn btn-ghost btn-sm" onClick={close} disabled={saving}>Cancel</button>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" disabled={step <= 1 || saving} onClick={() => setStep(step - 1)}>← Back</button>
                {step < 4 ? (
                  <button className="btn btn-primary btn-sm" disabled={saving} onClick={advance}>Continue →</button>
                ) : (
                  <button
                    className={`btn btn-primary btn-sm ${saving ? "btn-loading" : ""}`}
                    disabled={saving}
                    onClick={saveClusterEditor}
                    data-ux="cluster-editor-save"
                  >
                    {saving && <span className="btn-spinner" />}
                    {clusterEditor.mode === "create" ? "Create cluster" : "Save settings"}
                  </button>
                )}
              </div>
            </div>
          </aside>
        </>
        );
      })()}

      {/* Legacy node modal disabled — provision drawer is the only node editor (cP parity).
          Keep block inert: nodeEditor.visible is always false from openNodeCreate/Edit. */}
      {false && nodeEditor.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "480px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h3>{nodeEditor.mode === "create" ? "Add Node" : "Edit Node"}</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "60vh", overflowY: "auto", paddingRight: "4px" }}>
              <div className="field">
                <label>Node name</label>
                <input className="input" value={nodeEditor.draft.name} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, name: e.target.value } }))} />
              </div>
              <div className="field">
                <label>SSH Host/IP</label>
                <input className="input" value={nodeEditor.draft.host} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, host: e.target.value } }))} />
              </div>
              <div className="field">
                <label>SSH Username</label>
                <input className="input" value={nodeEditor.draft.ssh_user} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_user: e.target.value } }))} />
              </div>
              <div className="field">
                <label>SSH Key Path (Optional if key pasted below)</label>
                <input className="input" value={nodeEditor.draft.ssh_key_path} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_key_path: e.target.value } }))} placeholder="e.g. ~/.ssh/id_rsa" />
              </div>
              <div className="field">
                <label>SSH Private Key Content (PEM format)</label>
                <textarea 
                  className="input" 
                  style={{ 
                    minHeight: "100px", 
                    fontFamily: "var(--mono)", 
                    fontSize: "0.75rem", 
                    background: "rgba(0,0,0,0.2)", 
                    border: "1px solid var(--line)", 
                    color: "#fff",
                    padding: "0.5rem",
                    borderRadius: "6px",
                    resize: "vertical"
                  }} 
                  value={nodeEditor.draft.ssh_private_key || ""} 
                  onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, ssh_private_key: e.target.value } }))} 
                  placeholder="-----BEGIN OPENSSH PRIVATE KEY-----\n..." 
                />
              </div>
              <div className="field">
                <label>Volume Root Directory</label>
                <input className="input" value={nodeEditor.draft.volume_root} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, volume_root: e.target.value } }))} />
              </div>
              <div className="field">
                <label>Docker Network</label>
                <input className="input" value={nodeEditor.draft.docker_network} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, docker_network: e.target.value } }))} placeholder="platformops_prod_network" />
              </div>
              <h4 style={{ margin: "0.35rem 0 0", fontSize: "0.9rem" }}>Hardware profile (stored in facts)</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem" }}>
                <div className="field">
                  <label>vCPU cores</label>
                  <input type="number" className="input" value={nodeEditor.draft.cpu_cores ?? ""} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, cpu_cores: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>Memory (GB)</label>
                  <input type="number" className="input" value={nodeEditor.draft.memory_gb ?? ""} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, memory_gb: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>Storage (GB)</label>
                  <input type="number" className="input" value={nodeEditor.draft.storage_gb ?? ""} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, storage_gb: e.target.value } }))} />
                </div>
                <div className="field">
                  <label>GPU</label>
                  <input className="input" value={nodeEditor.draft.gpu ?? "none"} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, gpu: e.target.value } }))} placeholder="none / nvidia / count" />
                </div>
              </div>
              <div className="field">
                <label>OS</label>
                <input className="input" value={nodeEditor.draft.os ?? "linux"} onChange={(e) => setNodeEditor(prev => ({ ...prev, draft: { ...prev.draft, os: e.target.value } }))} />
              </div>
            </div>
            {nodeEditor.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{nodeEditor.error}</p>}
            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setNodeEditor(prev => ({ ...prev, visible: false }))}>Cancel</button>
              <button className="btn btn-primary btn-sm" onClick={saveNodeEditor}>Save Node</button>
            </div>
          </GlassCard>
        </div>
      )}

      {deploymentModal.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "860px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "85vh", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "flex-start" }}>
              <div>
                <h3 style={{ marginBottom: "0.25rem" }}>Deployment Control</h3>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>
                  Review dependency order, Ansible execution steps, and deploy {deploymentModal.serviceName} on {deploymentModal.nodeName}.
                </p>
              </div>
              <span className={`pill ${deploymentModal.preflight?.ok ? "pill-ok" : "pill-warn"}`}>
                {deploymentModal.preflight?.ok ? "ready" : "needs dependencies"}
              </span>
            </div>

            {deploymentModal.loading ? (
              <p style={{ margin: 0, color: "var(--ink-4)" }}>Loading deployment plan and dependency state...</p>
            ) : (
              <>
                {deploymentModal.preflight && (
                  <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: "0.85rem" }}>
                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.9rem", background: "rgba(255,255,255,0.03)" }}>
                      <strong>Dependency preflight</strong>
                      <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.35rem" }}>{deploymentModal.preflight.message}</div>
                      {deploymentModal.preflight.required.length > 0 && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Required cards</small>
                          <div className="tags" style={{ marginTop: "0.25rem" }}>
                            {deploymentModal.preflight.required.map((item) => <span key={`req-${item}`}>{item}</span>)}
                          </div>
                        </div>
                      )}
                      {deploymentModal.preflight.missing.length > 0 && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Missing</small>
                          <div className="tags" style={{ marginTop: "0.25rem" }}>
                            {deploymentModal.preflight.missing.map((item) => <span key={`miss-${item}`}>{item}</span>)}
                          </div>
                        </div>
                      )}
                      {deploymentModal.preflight.stopped.length > 0 && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Stopped</small>
                          <div className="tags" style={{ marginTop: "0.25rem" }}>
                            {deploymentModal.preflight.stopped.map((item) => <span key={`stop-${item}`}>{item}</span>)}
                          </div>
                        </div>
                      )}
                    </div>

                    <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.9rem", background: "rgba(255,255,255,0.03)" }}>
                      <strong>Execution policy</strong>
                      <label style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", marginTop: "0.6rem" }}>
                        <input
                          type="checkbox"
                          checked={deploymentModal.autoInstallDependencies}
                          onChange={(e) => setDeploymentModal((current) => ({ ...current, autoInstallDependencies: e.target.checked }))}
                        />
                        <span style={{ fontSize: "0.88rem", color: "var(--ink-3)" }}>
                          Auto-install or start missing infrastructure cards before deploying the main service.
                        </span>
                      </label>
                      <div style={{ marginTop: "0.75rem", fontSize: "0.82rem", color: "var(--ink-4)" }}>
                        This mirrors a dependency-first deployment flow while keeping the target deploy under Ansible control.
                      </div>
                    </div>
                  </div>
                )}

                {plan && deploymentModal.serviceId && selectedService?.id === deploymentModal.serviceId && (
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                      <strong>Ordered deployment plan</strong>
                      <span className={`pill ${plan.ok ? "pill-ok" : "pill-warn"}`}>{plan.ok ? "already healthy" : `${plan.blocked_by.length} action item(s)`}</span>
                    </div>
                    <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{plan.summary}</div>
                    <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.65rem" }}>
                      {plan.steps.map((step) => (
                        <div key={`deploy-step-${step.order}-${step.service_key}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.8rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                            <div style={{ display: "flex", gap: "0.55rem", alignItems: "center", flexWrap: "wrap" }}>
                              <span className="pill" style={{ fontSize: "0.72rem" }}>Step {step.order}</span>
                              <strong>{step.name}</strong>
                              <span className={`pill ${step.action === "skip" ? "pill-ok" : "pill-warn"}`}>{step.action}</span>
                            </div>
                            <small style={{ color: "var(--ink-4)" }}>{step.kind} · {step.subsystem}</small>
                          </div>
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                            Status {step.status} · container <code>{step.container_name}</code>
                          </div>
                          {step.depends_on && step.depends_on.length > 0 && (
                            <div style={{ marginTop: "0.4rem" }}>
                              <small style={{ color: "var(--ink-4)" }}>Depends on</small>
                              <div className="tags" style={{ marginTop: "0.2rem" }}>
                                {step.depends_on.map((item) => <span key={`${step.service_key}-dep-${item}`}>{item}</span>)}
                              </div>
                            </div>
                          )}
                          {step.ansible_command && (
                            <div style={{ marginTop: "0.45rem" }}>
                              <small style={{ color: "var(--ink-4)" }}>Ansible command preview</small>
                              <pre style={{ margin: "0.25rem 0 0", padding: "0.65rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.76rem" }}>
                                <code>{step.ansible_command}</code>
                              </pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {deploymentModal.result && (
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "0.95rem", background: "rgba(255,255,255,0.03)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                      <strong>Execution result</strong>
                      <span className={`pill ${deploymentModal.result.ok ? "pill-ok" : "pill-warn"}`}>{deploymentModal.result.ok ? "completed" : "attention needed"}</span>
                    </div>
                    <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{deploymentModal.result.summary}</div>
                    {deploymentModal.result.dependency_actions.length > 0 && (
                      <div style={{ marginTop: "0.65rem" }}>
                        <small style={{ color: "var(--ink-4)" }}>Dependency actions</small>
                        <div style={{ marginTop: "0.3rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                          {deploymentModal.result.dependency_actions.map((action) => (
                            <div key={`dep-action-${action.job_id}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.7rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                                <strong>{action.service_key}</strong>
                                <span className="pill">{action.job_status}</span>
                              </div>
                              <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>{action.message}</div>
                              <pre style={{ margin: "0.35rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.74rem" }}>
                                <code>{action.command}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {deploymentModal.result.target_job && (
                      <div style={{ marginTop: "0.7rem" }}>
                        <small style={{ color: "var(--ink-4)" }}>Target deploy job</small>
                        <div style={{ marginTop: "0.3rem", border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                            <strong>{deploymentModal.serviceName}</strong>
                            <span className={`pill ${deploymentModal.result.target_job.status === "success" ? "pill-ok" : "pill-warn"}`}>{deploymentModal.result.target_job.status}</span>
                          </div>
                          <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                            Job #{deploymentModal.result.target_job.id} · {deploymentModal.result.target_job.action}
                          </div>
                          <pre style={{ margin: "0.35rem 0 0", padding: "0.6rem", borderRadius: "8px", background: "rgba(15, 23, 42, 0.92)", color: "#e2e8f0", overflowX: "auto", fontSize: "0.74rem" }}>
                            <code>{deploymentModal.result.target_job.command}</code>
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {deploymentModal.error && <p style={{ color: "var(--err)", fontSize: "0.82rem", margin: 0 }}>{deploymentModal.error}</p>}
            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setDeploymentModal((current) => ({ ...current, visible: false, error: "" }))}>Close</button>
              {deploymentModal.serviceId && (
                <>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={async () => {
                      const service = services.find((item) => item.id === deploymentModal.serviceId);
                      if (service) {
                        await openDeploymentModal(service);
                      }
                    }}
                    disabled={deploymentModal.loading || deploymentModal.executing}
                  >
                    Refresh plan
                  </button>
                  <button
                    className={buttonLoadingClass("btn btn-secondary btn-sm", installDepsBusy)}
                    onClick={async () => {
                      const service = services.find((item) => item.id === deploymentModal.serviceId);
                      if (service) {
                        await installMissingDependencies(service);
                      }
                    }}
                    disabled={deploymentModal.loading || deploymentModal.executing || installDepsBusy}
                    data-ux="btn-install-deps"
                  >
                    {installDepsBusy && <span className="btn-spinner" />}
                    Deploy dependencies first
                  </button>
                  <button
                    className={`btn btn-primary btn-sm ${deploymentModal.executing || deploymentModal.loading ? "btn-loading" : ""}`}
                    onClick={executeDeploymentModal}
                    disabled={deploymentModal.loading || deploymentModal.executing}
                    data-ux="btn-deploy-execute"
                  >
                    {(deploymentModal.executing || deploymentModal.loading) && <span className="btn-spinner" />}
                    {deploymentModal.executing ? "Executing…" : deploymentModal.loading ? "Loading…" : "Execute plan"}
                  </button>
                </>
              )}
            </div>
          </GlassCard>
        </div>
      )}

      {releaseApprovalModal.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "560px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h3>Release Safety Gate</h3>
            <p style={{ margin: 0, fontSize: "0.9rem" }}>
              {releaseApprovalModal.serviceName} needs an explicit release approval before this change can be deployed.
            </p>
            {releaseApprovalModal.safety && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", background: "rgba(0,0,0,0.2)", padding: "0.85rem", borderRadius: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Severity</span>
                  <span className={`pill ${releaseApprovalModal.safety.severity === "high" ? "pill-error" : "pill-warn"}`}>
                    {releaseApprovalModal.safety.severity}
                  </span>
                </div>
                {releaseApprovalModal.safety.reasons.map((reason) => (
                  <small key={reason} style={{ color: "var(--warn)" }}>• {reason}</small>
                ))}
                <small style={{ color: "var(--ink-4)" }}>{releaseApprovalModal.safety.recommended_action}</small>
              </div>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="field">
                <label>Target version</label>
                <input className="input" value={releaseApprovalModal.version} readOnly />
              </div>
              <div className="field">
                <label>Target image</label>
                <input className="input" value={releaseApprovalModal.image} readOnly />
              </div>
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label>Approval reason</label>
                <input
                  className="input"
                  value={releaseApprovalModal.reason}
                  placeholder="Explain the rollout window and risk mitigation"
                  onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, reason: e.target.value }))}
                />
              </div>
              <div className="field">
                <label>Requested by</label>
                <input
                  className="input"
                  value={releaseApprovalModal.requestedBy}
                  onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, requestedBy: e.target.value }))}
                />
              </div>
              <div className="field">
                <label>Approval id</label>
                <input
                  className="input"
                  value={releaseApprovalModal.approvalId}
                  placeholder="Populated after request"
                  onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, approvalId: e.target.value }))}
                />
              </div>
              <div className="field">
                <label>Approver</label>
                <input
                  className="input"
                  value={releaseApprovalModal.approver}
                  onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, approver: e.target.value }))}
                />
              </div>
              <div className="field">
                <label>Decision note</label>
                <input
                  className="input"
                  value={releaseApprovalModal.decisionNote}
                  onChange={(e) => setReleaseApprovalModal((current) => ({ ...current, decisionNote: e.target.value }))}
                />
              </div>
            </div>
            {releaseApprovalModal.error && <p style={{ color: "var(--err)", fontSize: "0.8rem", margin: 0 }}>{releaseApprovalModal.error}</p>}
            <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>
              Recent approvals for this service: {releaseApprovals.filter((item) => item.service_id === releaseApprovalModal.serviceId).slice(0, 3).map((item) => `#${item.id} ${item.status}`).join(", ") || "none"}
            </div>
            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setReleaseApprovalModal((current) => ({ ...current, visible: false, error: "" }))}>Cancel</button>
              <button className="btn btn-secondary btn-sm" onClick={createReleaseApprovalRequest}>Request Approval</button>
              <button className="btn btn-secondary btn-sm" onClick={approveReleaseApprovalRequest}>Approve</button>
              <button className="btn btn-secondary btn-sm" onClick={revokeReleaseApprovalRequest}>Revoke</button>
              <button className="btn btn-primary btn-sm" onClick={confirmApprovedRelease}>Deploy Approved Release</button>
            </div>
          </GlassCard>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {deleteModal.visible && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "500px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h3>Lifecycle Safety Review</h3>
            <p style={{ margin: 0 }}>You are deleting the following infrastructure resource:</p>
            <div style={{ background: "rgba(0,0,0,0.2)", padding: "0.75rem", borderRadius: "8px", fontSize: "0.9rem" }}>
              <strong>Type:</strong> {deleteModal.targetType.toUpperCase()}<br/>
              <strong>Name:</strong> {deleteModal.targetName}<br/>
              <strong>ID:</strong> {deleteModal.targetId}
            </div>

            {deleteModal.impact && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Severity:</span>
                  <span className={`pill ${deleteModal.impact.severity === "safe" ? "pill-ok" : "pill-error"}`}>{deleteModal.impact.severity}</span>
                </div>
                {deleteModal.impact.warnings.map((w, idx) => (
                  <small key={idx} style={{ color: "var(--warn)", display: "block" }}>⚠ {w}</small>
                ))}
                {deleteModal.impact.dependents.map((dep, idx) => (
                  <small key={idx} style={{ color: "var(--err)", display: "block" }}>❌ Dependents: {dep}</small>
                ))}
                <p style={{ fontStyle: "italic", fontSize: "0.85rem", margin: "4px 0" }}>{deleteModal.impact.recommended_action}</p>
              </div>
            )}

            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button className="btn btn-secondary btn-sm" disabled={deleteBusy} onClick={() => setDeleteModal(prev => ({ ...prev, visible: false }))}>Cancel</button>
              {deleteModal.impact?.can_delete_without_force ? (
                <button
                  className={buttonLoadingClass("btn btn-primary btn-sm btn-danger", deleteBusy)}
                  disabled={deleteBusy}
                  onClick={confirmDelete}
                >
                  {deleteBusy && <span className="btn-spinner" />}
                  Confirm Deletion
                </button>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", width: "100%", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input type="checkbox" checked={deleteModal.force} onChange={(e) => setDeleteModal(prev => ({ ...prev, force: e.target.checked }))} />
                    <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Override safety rules (Force Delete)</label>
                  </div>

                  {!deleteModal.forceApprovalId ? (
                    <>
                      <input 
                        className="input" 
                        placeholder="Enter audit reason (min 12 chars)" 
                        value={deleteModal.forceReason}
                        onChange={(e) => setDeleteModal(prev => ({ ...prev, forceReason: e.target.value }))}
                      />
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.25rem" }}>
                        <button 
                          className="btn btn-secondary btn-sm" 
                          disabled={deleteModal.forceReason.length < 12}
                          onClick={requestForceDeleteApproval}
                        >
                          Request Approval
                        </button>
                      </div>
                    </>
                  ) : (
                    <div style={{ background: "rgba(255,255,255,0.03)", padding: "1rem", borderRadius: "12px", border: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Approval Request #{deleteModal.forceApprovalId}</span>
                        <span className={`pill ${deleteModal.approvalStatus === "approved" ? "pill-ok" : deleteModal.approvalStatus === "rejected" ? "pill-error" : "pill-warn"}`}>
                          {deleteModal.approvalStatus}
                        </span>
                      </div>

                      <div className="field">
                        <label>Second-Person Approver</label>
                        <input 
                          className="input" 
                          placeholder="e.g. platform-admin" 
                          value={deleteModal.approver} 
                          onChange={(e) => setDeleteModal(prev => ({ ...prev, approver: e.target.value }))}
                        />
                      </div>

                      <div className="field">
                        <label>Decision Note</label>
                        <input 
                          className="input" 
                          placeholder="e.g. Approved for emergency cleanup" 
                          value={deleteModal.decisionNote} 
                          onChange={(e) => setDeleteModal(prev => ({ ...prev, decisionNote: e.target.value }))}
                        />
                      </div>

                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.25rem" }}>
                        <button className="btn btn-secondary btn-sm" onClick={rejectForceDeleteApproval}>Reject</button>
                        <button className="btn btn-primary btn-sm" onClick={approveForceDeleteApproval}>Approve</button>
                      </div>
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem", borderTop: "1px solid var(--line-2)", paddingTop: "0.75rem" }}>
                    <button 
                      className={buttonLoadingClass("btn btn-primary btn-sm btn-danger", deleteBusy)}
                      disabled={deleteBusy || !deleteModal.force || deleteModal.forceReason.length < 12 || deleteModal.approvalStatus !== "approved"}
                      onClick={confirmDelete}
                    >
                      {deleteBusy && <span className="btn-spinner" />}
                      Force Uninstall
                    </button>
                  </div>
                </div>
              )}
            </div>
          </GlassCard>
        </div>
      )}

      {/* LOG ARCHIVE PREVIEW MODAL */}
      {selectedArchive && (
        <div className="modal-overlay" style={{ display: "flex", zIndex: 100 }}>
          <GlassCard className="modal" style={{ padding: "1.5rem", maxWidth: "700px", width: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Log Archive Preview</h3>
              <button className="icon-btn" style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer" }} onClick={() => setSelectedArchive(null)}>
                <svg className="ic" viewBox="0 0 24 24" style={{ width: "18px", height: "18px" }}><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>

            <div style={{ background: "rgba(0,0,0,0.2)", padding: "0.75rem", borderRadius: "8px", fontSize: "0.85rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <div><strong>Path:</strong> <code>{selectedArchive.path}</code></div>
              <div><strong>Discovered:</strong> {selectedArchive.discovered_at ? new Date(selectedArchive.discovered_at).toLocaleString() : "N/A"}</div>
              <div><strong>Size:</strong> {Math.round(selectedArchive.size_bytes / 1024)} KB</div>
              <div><strong>Lines:</strong> {selectedArchive.line_count}</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <h4 style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)" }}>File Sample Data</h4>
              <div 
                className="console"
                style={{
                  height: "220px",
                  background: "#020408",
                  color: "#34d399",
                  fontFamily: "var(--mono)",
                  fontSize: "0.8rem",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  padding: "0.75rem",
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.25rem",
                  textAlign: "left"
                }}
              >
                {(archivePreviewLoading ? [{ level: "INFO", message: "Loading file…", timestamp: new Date().toISOString() }] : archivePreviewLines).map((line, index) => {
                  const timeStr = new Date(line.timestamp || Date.now()).toISOString().replace("T", " ").substring(0, 19);
                  const levelUpper = (line.level || "INFO").padEnd(5);
                  let levelColor = "#38bdf8";
                  if (levelUpper.includes("ERR")) levelColor = "#f87171";
                  else if (levelUpper.includes("WARN")) levelColor = "#fbbf24";
                  else if (levelUpper.includes("DEBUG")) levelColor = "#a78bfa";

                  return (
                    <div key={index} style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.01)", padding: "2px 0" }}>
                      <span style={{ color: "var(--ink-4)", flexShrink: 0 }}>{timeStr}</span>
                      <span style={{ color: levelColor, fontWeight: "bold", flexShrink: 0 }}>{levelUpper}</span>
                      <code style={{ color: "#e2e8f0", wordBreak: "break-all" }}>{line.message}</code>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", borderTop: "1px solid var(--line)", paddingTop: "1rem", flexWrap: "wrap" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedArchive(null)}>Close Preview</button>
              {selectedService && selectedArchive && (
                <button
                  className="btn btn-secondary btn-sm"
                  type="button"
                  onClick={() => downloadArchive(selectedArchive.id)}
                >
                  Download
                </button>
              )}
              <button 
                className="btn btn-primary btn-sm" 
                disabled={!diagnostics?.readiness.backfill_requirements?.ready}
                onClick={() => {
                  runLogBackfill();
                  setSelectedArchive(null);
                }}
              >
                Trigger Loki Backfill
              </button>
            </div>
          </GlassCard>
        </div>
      )}
    </>
  );

}
