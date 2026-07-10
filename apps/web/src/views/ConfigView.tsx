// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { treeNavigator } from "../components/TreeNavigator";

/** ConfigView — Phase 1 extracted page JSX. */
export function ConfigView() {
  const p = usePlatform() as any;
  const applyCurrentConfig = p.applyCurrentConfig;
  const applyPreparedMigration = p.applyPreparedMigration;
  const artifact = p.artifact;
  const capabilities = p.capabilities;
  const captureSnapshot = p.captureSnapshot;
  const checkpointFilter = p.checkpointFilter;
  const checkpointSearch = p.checkpointSearch;
  const compareSelectedSnapshots = p.compareSelectedSnapshots;
  const compareSnapshotLeft = p.compareSnapshotLeft;
  const compareSnapshotRight = p.compareSnapshotRight;
  const config = p.config;
  const configApplyMode = p.configApplyMode;
  const configEditMode = p.configEditMode;
  const configSource = p.configSource;
  const configTab = p.configTab;
  const configTimelinePage = p.configTimelinePage;
  const detectConfigDrift = p.detectConfigDrift;
  const drift = p.drift;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const getConfigStrategy = p.getConfigStrategy;
  const loadConfig = p.loadConfig;
  const migrationApplyResult = p.migrationApplyResult;
  const migrationArtifactId = p.migrationArtifactId;
  const migrationContent = p.migrationContent;
  const migrationValidation = p.migrationValidation;
  const nodes = p.nodes;
  const openRenameSnapshot = p.openRenameSnapshot;
  const prepareConfigMigration = p.prepareConfigMigration;
  const renderTreeNavigator = p.renderTreeNavigator;
  const restorePreparedMigration = p.restorePreparedMigration;
  const selectedService = p.selectedService;
  const selectedSnapshotPreview = p.selectedSnapshotPreview;
  const services = p.services;
  const setCheckpointFilter = p.setCheckpointFilter;
  const setCheckpointSearch = p.setCheckpointSearch;
  const setCompareSnapshotLeft = p.setCompareSnapshotLeft;
  const setCompareSnapshotRight = p.setCompareSnapshotRight;
  const setConfig = p.setConfig;
  const setConfigApplyMode = p.setConfigApplyMode;
  const setConfigEditMode = p.setConfigEditMode;
  const setConfigTab = p.setConfigTab;
  const setMigrationContent = p.setMigrationContent;
  const setNotice = p.setNotice;
  const setSelectedSnapshotPreview = p.setSelectedSnapshotPreview;
  const setSnapshotCompare = p.setSnapshotCompare;
  const snapshotCompare = p.snapshotCompare;
  const snapshotPage = p.snapshotPage;
  const syncPeerConfig = p.syncPeerConfig;
  const validateMigrationYaml = p.validateMigrationYaml;
  const viewSnapshot = p.viewSnapshot;


  // Config Manager with side-by-side tree and diff navigator (08-config-manager.html reference)
  const isCustomName = (name: string) => !/^v\d+-\d{8}-\d{6}/.test(name);
  const filteredSnapshots = (snapshotPage?.items ?? [])
    .filter((snap, idx) => {
      if (checkpointFilter === "active") return idx === 0;
      if (checkpointFilter === "renamed") return isCustomName(snap.name);
      if (checkpointFilter === "backup") return idx > 0;
      return true;
    })
    .filter(snap => {
      if (!checkpointSearch) return true;
      return snap.name.toLowerCase().includes(checkpointSearch.toLowerCase());
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Config Manager</h1>
          <p className="sub">Edit live service configuration, capture checkpoints, compare versions, and apply or restore changes.</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "1.5rem", minHeight: "600px" }}>
        {/* Left hierarchy navigator */}
        <GlassCard style={{ padding: "1rem" }}>
          {treeNavigator(async (service) => {
            await loadConfig(service, configSource);
          }, selectedService?.id ?? null)}
        </GlassCard>

        {/* Right main workspace panel */}
        {selectedService ? (
          <GlassCard style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem", position: "relative" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>{selectedService.name} config</h3>
                <small style={{ color: "var(--ink-4)" }}>Key: <code>{selectedService.service_key}</code> · Strategy: {getConfigStrategy(capabilities, selectedService)}</small>
                {config && (
                  <div className="tags" style={{ marginTop: "0.45rem" }}>
                    <span>{config.config_source_label || config.content_source}</span>
                    <span>{config.drift_state}</span>
                    <span>{config.snapshot_count} checkpoints</span>
                    {config.active_checkpoint && <span>active v{config.active_checkpoint.version}</span>}
                    {config.config_path && <span><code>{config.config_path}</code></span>}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <button className="btn btn-secondary btn-sm" onClick={captureSnapshot}>Capture snapshot</button>
                <button className="btn btn-secondary btn-sm" onClick={detectConfigDrift}>Detect drift</button>
                <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadConfig(selectedService, "live")}>Refresh live</button>
                <button type="button" className={`btn btn-sm ${configEditMode ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigEditMode((v) => !v)}>{configEditMode ? "Editing" : "Edit mode"}</button>
                <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                  <small style={{ color: "var(--ink-4)" }}>Apply:</small>
                  <button type="button" className={`btn btn-xs ${configApplyMode === "reload" ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigApplyMode("reload")}>Reload</button>
                  <button type="button" className={`btn btn-xs ${configApplyMode === "restart" ? "btn-primary" : "btn-secondary"}`} onClick={() => setConfigApplyMode("restart")}>Restart</button>
                </div>
                <button className="btn btn-primary btn-sm" onClick={applyCurrentConfig}>Apply config</button>
              </div>
            </div>

            {/* Workspaces tabs */}
            <div className="cluster-tabs">
              <div className={`tab ${configTab === "current" ? "active" : ""}`} onClick={() => setConfigTab("current")}>Current Config</div>
              <div className={`tab ${configTab === "timeline" ? "active" : ""}`} onClick={() => setConfigTab("timeline")}>Checkpoint Timeline</div>
              <div className={`tab ${configTab === "compare" ? "active" : ""}`} onClick={() => setConfigTab("compare")}>Compare / Diff</div>
              <div className={`tab ${configTab === "migration" ? "active" : ""}`} onClick={() => setConfigTab("migration")}>Migrate</div>
            </div>

            {/* Sub-tabs views */}
            {configTab === "current" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>

                {(config?.content_source === "live_fallback" || config?.content_source === "latest_snapshot" || (config?.config_source_label || "").toLowerCase().includes("checkpoint") || (config?.config_source_label || "").toLowerCase().includes("fallback")) && (
                  <div style={{
                    padding: "0.75rem 1rem",
                    borderRadius: 10,
                    border: "1px solid rgba(234, 179, 8, 0.35)",
                    background: "rgba(234, 179, 8, 0.08)",
                    fontSize: "0.85rem",
                  }}>
                    <strong>Database / checkpoint fallback</strong>
                    <div style={{ color: "var(--ink-3)", marginTop: 4 }}>
                      Live file may be unavailable. Showing <code>{config?.config_source_label || config?.content_source}</code>.
                      You can still edit, validate, and apply when a node target is ready.
                    </div>
                  </div>
                )}

                {config?.active_checkpoint && (
                  <div style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "0.75rem 1rem",
                    background: config.drift_state === "in_sync" ? "rgba(16, 185, 129, 0.06)" : "rgba(239, 68, 68, 0.06)",
                    border: config.drift_state === "in_sync" ? "1px solid rgba(16, 185, 129, 0.15)" : "1px solid rgba(239, 68, 68, 0.15)",
                    borderRadius: "10px",
                    fontSize: "0.85rem",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ color: config.drift_state === "in_sync" ? "#34d399" : "#f87171" }}>●</span>
                      <span>
                        Active Checkpoint: <strong>v{config.active_checkpoint.version}</strong> · {config.active_checkpoint.name}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span className={`pill ${config.drift_state === "in_sync" ? "pill-ok" : "pill-error"}`}>
                        {config.drift_state === "in_sync" ? "In Sync" : "Drifted"}
                      </span>
                      <button className="btn btn-secondary btn-xs" onClick={() => config.active_checkpoint && viewSnapshot(config.active_checkpoint.id)}>
                        View Active
                      </button>
                    </div>
                  </div>
                )}

                {selectedSnapshotPreview && (
                  <div style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <h4 style={{ margin: 0, fontSize: "0.95rem" }}>Snapshot View - {selectedSnapshotPreview.name}</h4>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button className="btn btn-secondary btn-xs" onClick={() => {
                          if (config) {
                            setConfig({ ...config, content: selectedSnapshotPreview.content });
                            setSelectedSnapshotPreview(null);
                            setNotice(`Loaded snapshot v${selectedSnapshotPreview.version} content into active editor`);
                          }
                        }}>
                          Load into Editor
                        </button>
                        <button className="btn btn-secondary btn-xs" onClick={() => setSelectedSnapshotPreview(null)}>Close</button>
                      </div>
                    </div>
                    <pre style={{
                      background: "#020408",
                      color: "#38bdf8",
                      fontFamily: "var(--mono)",
                      fontSize: "0.8rem",
                      padding: "1rem",
                      borderRadius: "8px",
                      maxHeight: "240px",
                      overflowY: "auto",
                      margin: 0
                    }}>
                      {selectedSnapshotPreview.content}
                    </pre>
                  </div>
                )}

                <textarea 
                  value={config?.content ?? ""} 
                  readOnly={!configEditMode}
                  onChange={(e) => setConfig(config ? { ...config, content: e.target.value } : null)}
                  style={{
                    flex: 1,
                    minHeight: "360px",
                    background: "#020408",
                    color: configEditMode ? "#38bdf8" : "#94a3b8",
                    fontFamily: "var(--mono)",
                    fontSize: "0.85rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "10px",
                    padding: "1rem",
                    outline: "none",
                    resize: "vertical",
                    opacity: configEditMode ? 1 : 0.9,
                  }}
                />
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button 
                    className="btn btn-secondary btn-sm" 
                    onClick={async () => {
                      if (!selectedService || !config) return;
                      const validation = await api<{ ok: boolean; message: string }>(`/api/services/${selectedService.id}/config/validate`, {
                        method: "POST",
                        body: JSON.stringify({ content: config.content }),
                      });
                      setNotice(validation.message);
                    }}
                  >
                    Validate YAML Syntax
                  </button>
                </div>
              </div>
            )}

            {configTab === "timeline" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                {/* Search and Filters toolbar */}
                <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className={`chip ${checkpointFilter === "all" ? "on" : ""}`} onClick={() => setCheckpointFilter("all")}>All Checkpoints</button>
                    <button className={`chip ${checkpointFilter === "active" ? "on" : ""}`} onClick={() => setCheckpointFilter("active")}>Active</button>
                    <button className={`chip ${checkpointFilter === "renamed" ? "on" : ""}`} onClick={() => setCheckpointFilter("renamed")}>Renamed</button>
                    <button className={`chip ${checkpointFilter === "backup" ? "on" : ""}`} onClick={() => setCheckpointFilter("backup")}>Backups</button>
                  </div>
                  <input 
                    type="text" 
                    className="input" 
                    placeholder="Filter checkpoints by name..." 
                    value={checkpointSearch}
                    onChange={(e) => setCheckpointSearch(e.target.value)}
                    style={{ maxWidth: "240px", fontSize: "0.8rem", padding: "0.35rem 0.65rem", background: "rgba(255,255,255,0.04)" }}
                  />
                </div>

                {/* Active Snapshot Preview Card */}
                {selectedSnapshotPreview && (
                  <div style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <h4 style={{ margin: 0, fontSize: "0.95rem" }}>Snapshot View - {selectedSnapshotPreview.name}</h4>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button className="btn btn-secondary btn-xs" onClick={() => {
                          if (config) {
                            setConfig({ ...config, content: selectedSnapshotPreview.content });
                            setNotice(`Loaded snapshot v${selectedSnapshotPreview.version} content into active editor`);
                            setConfigTab("current");
                          }
                        }}>
                          Load into Editor
                        </button>
                        <button className="btn btn-secondary btn-xs" onClick={() => setSelectedSnapshotPreview(null)}>Close Preview</button>
                      </div>
                    </div>
                    <pre style={{
                      background: "#020408",
                      color: "#38bdf8",
                      fontFamily: "var(--mono)",
                      fontSize: "0.8rem",
                      padding: "1rem",
                      borderRadius: "8px",
                      maxHeight: "300px",
                      overflowY: "auto",
                      margin: 0
                    }}>
                      {selectedSnapshotPreview.content}
                    </pre>
                  </div>
                )}

                {/* Checkpoints List */}
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {filteredSnapshots.map((snap) => {
                    const originalIdx = (snapshotPage?.items ?? []).findIndex(s => s.id === snap.id);
                    const isRenamed = isCustomName(snap.name);
                    return (
                      <div key={`checkpoint-item-${snap.id}`} style={{
                        border: "1px solid var(--line)",
                        borderRadius: "12px",
                        padding: "1rem",
                        background: originalIdx === 0 ? "rgba(99,102,241,0.04)" : "rgba(255,255,255,0.01)",
                        transition: "all 0.2s ease"
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                              <strong style={{ fontSize: "0.95rem" }}>{snap.name}</strong>
                              <span className="pill" style={{ scale: 0.85 }}>v{snap.version}</span>
                              {isRenamed && <span className="pill pill-warn" style={{ scale: 0.85 }}>Renamed</span>}
                              <span className={`pill ${originalIdx === 0 ? "pill-primary" : "pill-secondary"}`} style={{ scale: 0.85 }}>
                                {originalIdx === 0 ? "Active" : "Backup"}
                              </span>
                            </div>
                            <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                              Captured {formatLocalTimestamp(snap.created_at)} · Source: {snap.source}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            <button className="btn btn-secondary btn-xs" onClick={() => viewSnapshot(snap.id)}>View</button>
                            <button className="btn btn-secondary btn-xs" onClick={() => openRenameSnapshot(snap.id, snap.name)}>Rename</button>
                            <div 
                              onClick={() => {
                                if (compareSnapshotLeft === snap.id) {
                                  setCompareSnapshotLeft(null);
                                } else if (compareSnapshotRight === snap.id) {
                                  setCompareSnapshotRight(null);
                                } else if (!compareSnapshotLeft) {
                                  setCompareSnapshotLeft(snap.id);
                                } else {
                                  setCompareSnapshotRight(snap.id);
                                }
                              }} 
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.35rem",
                                cursor: "pointer",
                                fontSize: "0.75rem",
                                color: (compareSnapshotLeft === snap.id || compareSnapshotRight === snap.id) ? "var(--primary)" : "var(--ink-3)",
                                border: "1px solid var(--line-2)",
                                borderRadius: "6px",
                                padding: "0.25rem 0.5rem",
                                userSelect: "none"
                              }}
                            >
                              <input 
                                type="checkbox" 
                                checked={compareSnapshotLeft === snap.id || compareSnapshotRight === snap.id} 
                                readOnly
                                style={{ cursor: "pointer", pointerEvents: "none", margin: 0 }}
                              />
                              Compare {(compareSnapshotLeft === snap.id) ? "A" : (compareSnapshotRight === snap.id) ? "B" : ""}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {filteredSnapshots.length === 0 && (
                    <div style={{ color: "var(--ink-4)", fontStyle: "italic", textAlign: "center", padding: "1.5rem" }}>
                      No checkpoints found matching the active filter.
                    </div>
                  )}
                </div>

                {/* Configuration Event Log (Timeline Events) */}
                {configTimelinePage && configTimelinePage.items.length > 0 && (
                  <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1.5rem" }}>
                    <h4 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.75rem" }}>Configuration Event Log</h4>
                    <div className="timeline">
                      {configTimelinePage.items.map((event) => (
                        <article key={event.id}>
                          <span className="pill" style={{ scale: "0.8", alignSelf: "flex-start" }}>{event.action}</span>
                          <strong>{event.message}</strong>
                          <small style={{ color: "var(--ink-4)" }}>by {event.actor} · {formatLocalTimestamp(event.created_at)}</small>
                        </article>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {configTab === "compare" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                  <span>Compare snapshot</span>
                  <select value={compareSnapshotLeft || ""} onChange={(e) => setCompareSnapshotLeft(Number(e.target.value) || null)}>
                    <option value="">Choose version...</option>
                    {(snapshotPage?.items ?? []).map(s => <option key={s.id} value={s.id}>v{s.version} - {s.name}</option>)}
                  </select>
                  <span>with</span>
                  <select value={compareSnapshotRight || ""} onChange={(e) => setCompareSnapshotRight(Number(e.target.value) || null)}>
                    <option value="">Choose version...</option>
                    {(snapshotPage?.items ?? []).map(s => <option key={s.id} value={s.id}>v{s.version} - {s.name}</option>)}
                  </select>
                  <button className="btn btn-primary btn-sm" onClick={compareSelectedSnapshots}>Compare Diff</button>
                </div>

                {snapshotCompare && (
                  <div style={{ padding: "0.9rem 1rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
                    <strong>{snapshotCompare.summary}</strong>
                    <div style={{ color: "var(--ink-4)", marginTop: "0.25rem", fontSize: "0.85rem" }}>
                      Left: v{snapshotCompare.left_snapshot.version} {snapshotCompare.left_snapshot.name} · Right: v{snapshotCompare.right_snapshot.version} {snapshotCompare.right_snapshot.name}
                    </div>
                  </div>
                )}

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div style={{ background: "#020408", padding: "1rem", borderRadius: "10px", minHeight: "200px" }}>
                    <small style={{ color: "var(--ink-4)", display: "block", marginBottom: "0.5rem" }}>Baseline snapshot</small>
                    <pre style={{ color: "#a7f3d0", fontSize: "0.8rem", overflowX: "auto" }}>
                      {snapshotCompare?.left_snapshot.content ?? "Select snapshots to inspect the left side."}
                    </pre>
                  </div>
                  <div style={{ background: "#020408", padding: "1rem", borderRadius: "10px", minHeight: "200px" }}>
                    <small style={{ color: "var(--ink-4)", display: "block", marginBottom: "0.5rem" }}>Compare target</small>
                    <pre style={{ color: "#fbcfe8", fontSize: "0.8rem", overflowX: "auto" }}>
                      {snapshotCompare?.right_snapshot.content ?? "Select snapshots to inspect the right side."}
                    </pre>
                  </div>
                </div>

                <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--line)", borderRadius: "12px", padding: "1rem" }}>
                  <strong>Field differences</strong>
                  <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                    {(snapshotCompare?.differences ?? []).map((difference) => (
                      <div key={`${difference.field}-${JSON.stringify(difference.expected)}-${JSON.stringify(difference.actual)}`} style={{ border: "1px solid var(--line-2)", borderRadius: "10px", padding: "0.75rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                          <strong>{difference.field}</strong>
                          <span className="pill pill-warn">{difference.severity}</span>
                        </div>
                        <div style={{ marginTop: "0.45rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                          <div>
                            <small style={{ color: "var(--ink-4)" }}>Left</small>
                            <pre style={{ marginTop: "0.2rem", background: "rgba(239, 68, 68, 0.08)", color: "#f87171", padding: "0.6rem", borderRadius: "8px", fontSize: "0.78rem", overflowX: "auto" }}>
                              {JSON.stringify(difference.expected, null, 2)}
                            </pre>
                          </div>
                          <div>
                            <small style={{ color: "var(--ink-4)" }}>Right</small>
                            <pre style={{ marginTop: "0.2rem", background: "rgba(16, 185, 129, 0.08)", color: "#34d399", padding: "0.6rem", borderRadius: "8px", fontSize: "0.78rem", overflowX: "auto" }}>
                              {JSON.stringify(difference.actual, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    ))}
                    {snapshotCompare && snapshotCompare.differences.length === 0 && (
                      <div style={{ color: "var(--ink-4)" }}>The selected snapshots are identical.</div>
                    )}
                    {!snapshotCompare && (
                      <div style={{ color: "var(--ink-4)" }}>Select two snapshots and run Compare Diff to see exact field-level changes.</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {configTab === "migration" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "0.75rem", alignItems: "end" }}>
                  <label className="field" style={{ margin: 0 }}>
                    <span>Baseline checkpoint</span>
                    <select value={compareSnapshotLeft || ""} onChange={(e) => setCompareSnapshotLeft(Number(e.target.value) || null)}>
                      <option value="">Choose baseline...</option>
                      {(snapshotPage?.items ?? []).map(s => <option key={`migration-left-${s.id}`} value={s.id}>v{s.version} - {s.name}</option>)}
                    </select>
                  </label>
                  <label className="field" style={{ margin: 0 }}>
                    <span>Target checkpoint</span>
                    <select value={compareSnapshotRight || ""} onChange={(e) => setCompareSnapshotRight(Number(e.target.value) || null)}>
                      <option value="">Choose target...</option>
                      {(snapshotPage?.items ?? []).map(s => <option key={`migration-right-${s.id}`} value={s.id}>v{s.version} - {s.name}</option>)}
                    </select>
                  </label>
                  <button className="btn btn-primary btn-sm" onClick={prepareConfigMigration}>Prepare</button>
                </div>
                {migrationArtifactId && (
                  <div className="tags">
                    <span>artifact {migrationArtifactId}</span>
                    <span>{migrationValidation || "validation pending"}</span>
                    {migrationApplyResult?.backup_snapshot_id && <span>backup snapshot #{migrationApplyResult.backup_snapshot_id}</span>}
                  </div>
                )}
                <textarea
                  className="input"
                  value={migrationContent || config?.content || ""}
                  onChange={(e) => setMigrationContent(e.target.value)}
                  style={{
                    minHeight: "360px",
                    background: "#020408",
                    color: "#a78bfa",
                    fontFamily: "var(--mono)",
                    fontSize: "0.85rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "10px",
                    padding: "1rem",
                    outline: "none",
                    resize: "vertical",
                  }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button className="btn btn-secondary btn-sm" onClick={validateMigrationYaml}>Validate YAML</button>
                    <button className="btn btn-primary btn-sm" onClick={applyPreparedMigration}>Apply migration</button>
                    <button className="btn btn-secondary btn-sm" onClick={restorePreparedMigration}>Restore backup</button>
                  </div>
                </div>

                {/* Fleet Rollout Strategy Section */}
                <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1.5rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>Fleet Rollout Strategy</h3>
                    <small style={{ color: "var(--ink-4)" }}>Peer nodes sharing the same type</small>
                  </div>
                  <p style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginBottom: "1rem" }}>
                    The following sibling node instances in the cluster run the same service type. You can deploy the current validated configuration to peer nodes in a controlled sequence.
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.75rem" }}>
                    {(config?.peers ?? []).map((peer) => (
                      <div key={`migrate-peer-${peer.service_id}`} style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "1rem",
                        border: "1px solid var(--line-2)",
                        borderRadius: "12px",
                        background: "rgba(255,255,255,0.02)"
                      }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{peer.node_name} / {peer.name}</div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginTop: "0.2rem" }}>
                            service_id: {peer.service_id} · Status: {peer.status}
                          </div>
                        </div>
                        <button 
                          className="btn btn-secondary btn-sm" 
                          onClick={() => syncPeerConfig(peer.service_id, peer.node_name)}
                        >
                          Sync validated config
                        </button>
                      </div>
                    ))}
                    {(config?.peers ?? []).length === 0 && (
                      <div style={{ color: "var(--ink-4)", fontSize: "0.85rem", fontStyle: "italic", textAlign: "center", padding: "1rem" }}>
                        No sibling peer node instances of this type exist in the cluster.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Floating Compare Bar */}
            {(compareSnapshotLeft || compareSnapshotRight) && (
              <div style={{
                position: "sticky",
                bottom: "0",
                background: "rgba(10, 15, 30, 0.95)",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: "16px",
                padding: "1rem 1.5rem",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                boxShadow: "0 -8px 32px rgba(0,0,0,0.5)",
                zIndex: 100,
                marginTop: "1.5rem"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span className="pill pill-primary" style={{ scale: "0.9" }}>A</span>
                    <span style={{ fontSize: "0.85rem" }}>
                      {compareSnapshotLeft 
                        ? `v${(snapshotPage?.items ?? []).find(s => s.id === compareSnapshotLeft)?.version || compareSnapshotLeft}`
                        : "--"}
                    </span>
                  </div>
                  <span style={{ color: "var(--ink-4)" }}>➔</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span className="pill pill-secondary" style={{ scale: "0.9" }}>B</span>
                    <span style={{ fontSize: "0.85rem" }}>
                      {compareSnapshotRight 
                        ? `v${(snapshotPage?.items ?? []).find(s => s.id === compareSnapshotRight)?.version || compareSnapshotRight}`
                        : "--"}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => {
                    setCompareSnapshotLeft(null);
                    setCompareSnapshotRight(null);
                    setSnapshotCompare(null);
                  }}>
                    Clear Selection
                  </button>
                  <button 
                    className="btn btn-primary btn-sm" 
                    disabled={!compareSnapshotLeft || !compareSnapshotRight}
                    onClick={async () => {
                      setConfigTab("compare");
                      await compareSelectedSnapshots();
                    }}
                  >
                    Compare Checkpoints
                  </button>
                  <button 
                    className="btn btn-primary btn-sm" 
                    disabled={!compareSnapshotLeft || !compareSnapshotRight}
                    onClick={async () => {
                      setConfigTab("migration");
                      await prepareConfigMigration();
                    }}
                  >
                    Prepare Migration
                  </button>
                </div>
              </div>
            )}
          </GlassCard>
        ) : (
          <GlassCard style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
            <h3>Select a card</h3>
            <p style={{ color: "var(--ink-4)" }}>Select a node service card from the navigator tree to view and manage configs.</p>
          </GlassCard>
        )}
      </div>
    </div>
  );

}
