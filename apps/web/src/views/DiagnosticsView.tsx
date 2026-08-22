// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { LogAnalystChat } from "./LogAnalystChat";
import { treeNavigator } from "../components/TreeNavigator";
import { api } from "../api/client";

/** DiagnosticsView — Phase 1 extracted page JSX. */
export function DiagnosticsView() {
  const p = usePlatform() as any;
  const archiveGzipOnly = p.archiveGzipOnly;
  const archives = p.archives;
  const autoPollLogs = p.autoPollLogs;
  const bulkDownloadArchives = p.bulkDownloadArchives;
  const capabilities = p.capabilities;
  const checks = p.checks;
  const coverage = p.coverage;
  const diagFilePath = p.diagFilePath;
  const diagLogSource = p.diagLogSource;
  const diagTab = p.diagTab;
  const downloadArchive = p.downloadArchive;
  const diagnostics = p.diagnostics;
  const diagnosticsAnalysis = p.diagnosticsAnalysis;
  const diagnosticsLive = p.diagnosticsLive;
  const diagnosticsTargetKey = p.diagnosticsTargetKey;
  const diagnosticsTargets = p.diagnosticsTargets;
  const events = p.events;
  const focusDiagnosticsTarget = p.focusDiagnosticsTarget;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const historyPage = p.historyPage;
  const historyPreviousCursor = p.historyPreviousCursor;
  const historyCursor = p.historyCursor;
  const historyTotalPages = p.historyTotalPages;
  const ingestionStats = p.ingestionStats;
  const loadDiagnostics = p.loadDiagnostics;
  const loadDiagnosticsLive = p.loadDiagnosticsLive;
  const logAutoScroll = p.logAutoScroll;
  const logLevelFilters = p.logLevelFilters;
  const logSearchQuery = p.logSearchQuery;
  const renderAiChat = p.renderAiChat;
  const renderTreeNavigator = p.renderTreeNavigator;
  const runDiagnosticsInsightAction = p.runDiagnosticsInsightAction;
  const runLogBackfill = p.runLogBackfill;
  const selectedArchiveIds = p.selectedArchiveIds;
  const selectedService = p.selectedService;
  const services = p.services;
  const setArchiveGzipOnly = p.setArchiveGzipOnly;
  const setArchivePreviewLines = p.setArchivePreviewLines;
  const setArchivePreviewLoading = p.setArchivePreviewLoading;
  const setAutoPollLogs = p.setAutoPollLogs;
  const setDiagFilePath = p.setDiagFilePath;
  const setDiagLogSource = p.setDiagLogSource;
  const setDiagTab = p.setDiagTab;
  const setDiagnosticsLive = p.setDiagnosticsLive;
  const setHistoryCursor = p.setHistoryCursor;
  const setHistoryPage = p.setHistoryPage;
  const setHistoryPreviousCursor = p.setHistoryPreviousCursor;
  const setIngestionStats = p.setIngestionStats;
  const setLogAutoScroll = p.setLogAutoScroll;
  const setLogLevelFilters = p.setLogLevelFilters;
  const setLogSearchQuery = p.setLogSearchQuery;
  const setSelectedArchive = p.setSelectedArchive;
  const setSelectedArchiveIds = p.setSelectedArchiveIds;
  const setTailLines = p.setTailLines;
  const tailLines = p.tailLines;


  // Diagnostics & live terminal logs (09-diagnostics.html reference)
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Diagnostics</h1>
          <p className="sub">Service checklist, live logs, archive tools, and log analysis for the selected service.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => api<any>("/api/diagnostics/ingestion-stats").then(setIngestionStats).catch(() => setIngestionStats(null))}>Refresh KPIs</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
        <GlassCard style={{ padding: "1rem" }}>
          <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Live ingestion rate</div>
          <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>{ingestionStats?.ingestion_rate_display ?? "—"}</div>
          <small style={{ color: ingestionStats?.loki_reachable ? "var(--ok)" : "var(--ink-4)" }}>
            {ingestionStats?.loki_reachable ? "Loki reachable" : "Loki offline / no data"}
          </small>
        </GlassCard>
        <GlassCard style={{ padding: "1rem" }}>
          <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Hourly errors</div>
          <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>{ingestionStats?.error_count_current_hour ?? "—"}</div>
          <small style={{ color: "var(--ink-4)" }}>Δ {ingestionStats?.error_delta_pct ?? 0}% vs previous hour</small>
        </GlassCard>
        <GlassCard style={{ padding: "1rem" }}>
          <div style={{ fontSize: "0.75rem", color: "var(--ink-4)" }}>Archive size</div>
          <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>
            {ingestionStats?.archive_size_bytes
              ? `${(Number(ingestionStats.archive_size_bytes) / (1024 * 1024 * 1024)).toFixed(2)} GB`
              : "—"}
          </div>
        </GlassCard>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "1.5rem", minHeight: "600px" }}>
        {/* Left tree navigator */}
        <GlassCard style={{ padding: "1rem" }}>
          {treeNavigator(async (service) => {
            await loadDiagnostics(service);
          }, selectedService?.id ?? null)}
        </GlassCard>

        {/* Right main workspace panel */}
        {selectedService ? (
          <GlassCard style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>{selectedService.name} diagnostics</h3>
                <small style={{ color: "var(--ink-4)" }}>Target container: <code>{capabilities?.container_name}</code> · Status: <span className={`pill ${selectedService.status === "healthy" || selectedService.status === "running" ? "pill-ok" : "pill-warn"}`}>{selectedService.status}</span></small>
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn btn-secondary btn-sm" onClick={() => loadDiagnostics(selectedService)}>Refresh logs</button>
              </div>
            </div>

            {/* Target Selector Bar */}
            {diagnosticsTargets.length > 0 && (
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", background: "rgba(255,255,255,0.02)", padding: "0.5rem 0.75rem", borderRadius: "10px", border: "1px solid var(--line-2)" }}>
                <small style={{ color: "var(--ink-4)" }}>Inspect Target Service:</small>
                <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                  {diagnosticsTargets.map((target) => {
                    const isSelected = diagnosticsTargetKey === target.service_key;
                    return (
                      <button
                        key={`diag-target-${target.service_key}`}
                        className={`btn ${isSelected ? "btn-primary" : "btn-secondary"} btn-xs`}
                        onClick={() => focusDiagnosticsTarget(target.service_key)}
                      >
                        {target.name} ({target.kind})
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Sub-tabs selectors */}
            <div className="cluster-tabs">
              <div className={`tab ${diagTab === "summary" ? "active" : ""}`} onClick={() => setDiagTab("summary")}>Summary</div>
              <div className={`tab ${diagTab === "tail" ? "active" : ""}`} onClick={() => setDiagTab("tail")}>Live tail</div>
              <div className={`tab ${diagTab === "files" ? "active" : ""}`} onClick={() => setDiagTab("files")}>Log files</div>
              <div className={`tab ${diagTab === "analytics" ? "active" : ""}`} onClick={() => setDiagTab("analytics")}>Log analyst</div>
            </div>

            {/* Tabs views */}
            {diagTab === "summary" && (
              <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.5rem" }}>
                {/* Left Column: Diagnostics Summary, Top Evidence, Lifecycle Events */}
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                      <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Diagnostics Summary</h4>
                      <span className={`pill ${diagnostics?.status === "error" ? "pill-error" : "pill-ok"}`} style={{ scale: "0.9" }}>{diagnostics?.status || "—"}</span>
                    </div>
                    
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", fontSize: "0.85rem", marginBottom: "1rem" }}>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Primary Root Cause</span>
                        <strong>{diagnosticsAnalysis?.overview || "No anomalies detected"}</strong>
                      </div>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Target Scope</span>
                        <strong>{diagnostics?.target_service_key || "Self"}</strong>
                      </div>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Logs Coverage</span>
                        <strong>{diagnostics?.readiness.file_logs ? "Full logs coverage" : "Limited coverage"}</strong>
                      </div>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Source Provenance</span>
                        <strong>{diagnostics?.readiness.loki_url ? "Loki log pipeline" : "Local db logs"}</strong>
                      </div>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Runtime Status</span>
                        <strong>{diagnostics?.readiness.status || "—"}</strong>
                      </div>
                      <div style={{ padding: "0.5rem", borderBottom: "1px solid var(--line-2)" }}>
                        <span style={{ color: "var(--ink-4)", display: "block" }}>Runtime Errors</span>
                        <strong style={{ color: diagnostics?.status === "error" ? "var(--err)" : "inherit" }}>
                          {diagnostics?.status === "error" ? "Anomalies found" : "None"}
                        </strong>
                      </div>
                    </div>
                  </div>

                  {/* Top Evidence / Warnings logs */}
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                    <h4 style={{ margin: 0, fontSize: "1rem", marginBottom: "0.75rem" }}>
                      Error and warning signatures
                    </h4>
                    <div style={{
                      background: "#020408",
                      padding: "0.75rem",
                      borderRadius: "8px",
                      border: "1px solid var(--line-2)",
                      maxHeight: "200px",
                      overflowY: "auto",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.35rem"
                    }}>
                      {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? [])
                        .filter(l => l.level.toLowerCase().includes("err") || l.level.toLowerCase().includes("warn"))
                        .map((line, idx) => (
                          <div key={`evidence-${idx}`} style={{ fontSize: "0.78rem", display: "flex", gap: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.02)", paddingBottom: "2px" }}>
                            <span style={{ color: "var(--ink-4)" }}>{line.timestamp.substring(11, 19)}</span>
                            <span style={{ color: line.level.toLowerCase().includes("err") ? "var(--err)" : "var(--warn)", fontWeight: "bold" }}>
                              {line.level.toUpperCase()}
                            </span>
                            <span style={{ color: "#e2e8f0" }}>{line.message}</span>
                          </div>
                        ))}
                      {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).filter(l => l.level.toLowerCase().includes("err") || l.level.toLowerCase().includes("warn")).length === 0 && (
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "center", padding: "1rem" }}>
                          No warning or error signatures indexed for this timeline.
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Recent Lifecycle Events */}
                  <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)" }}>
                    <h4 style={{ margin: 0, fontSize: "1rem", marginBottom: "0.75rem" }}>
                      Recent lifecycle events
                    </h4>
                    <div className="timeline" style={{ maxHeight: "250px", overflowY: "auto", paddingRight: "0.5rem" }}>
                      {events.slice(0, 10).map((event) => (
                        <article key={event.id}>
                          <span className={`pill ${event.level === "error" ? "pill-error" : event.level === "warning" ? "pill-warn" : "pill-ok"}`} style={{ scale: "0.8", alignSelf: "flex-start" }}>
                            {event.category || "Event"}
                          </span>
                          <strong>{event.message}</strong>
                          <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(event.created_at)}</small>
                        </article>
                      ))}
                      {events.length === 0 && (
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "center", padding: "1rem" }}>
                          No recent lifecycle events recorded.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Column: Issue Groups / Anomaly signatures */}
                <div style={{ border: "1px solid var(--line)", borderRadius: "12px", padding: "1.25rem", background: "rgba(255,255,255,0.01)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Issue Groups</h4>
                    <small style={{ color: "var(--warn)", fontWeight: 600 }}>Active anomaly signatures</small>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto", maxHeight: "600px" }}>
                    {(diagnosticsAnalysis?.insights ?? []).map((insight) => (
                      <div key={`insight-group-${insight.insight_id}`} style={{
                        padding: "0.9rem",
                        border: "1px solid var(--line-2)",
                        borderRadius: "10px",
                        background: insight.severity === "error" ? "rgba(239, 68, 68, 0.02)" : "rgba(251, 191, 36, 0.02)"
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                          <strong style={{ fontSize: "0.88rem", color: insight.severity === "error" ? "var(--err)" : "var(--warn)" }}>
                            {insight.title}
                          </strong>
                          <span className="pill" style={{ scale: "0.8" }}>{insight.confidence}% confidence</span>
                        </div>
                        <p style={{ margin: "4px 0", fontSize: "0.82rem", color: "var(--ink-2)" }}>{insight.summary}</p>
                        <small style={{ color: "var(--ink-4)", display: "block" }}>{insight.rationale}</small>
                        {insight.actions.length > 0 && (
                          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.35rem" }}>
                            {insight.actions.map(act => (
                              <button
                                key={act.action_id}
                                className={`btn btn-xs ${act.recommended ? "btn-primary" : "btn-secondary"}`}
                                onClick={() => runDiagnosticsInsightAction(act)}
                              >
                                {act.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                    {(diagnosticsAnalysis?.insights ?? []).length === 0 && (
                      <div style={{ color: "var(--ink-4)", fontStyle: "italic", textAlign: "center", padding: "2rem" }}>
                        No active issues or runtime anomalies identified.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {diagTab === "tail" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                    <select
                      value={diagLogSource}
                      onChange={async (e) => {
                        const src = e.target.value as typeof diagLogSource;
                        setDiagLogSource(src);
                        setHistoryPage(1);
                        setHistoryCursor("");
                        setHistoryPreviousCursor?.("");
                        if (selectedService) await loadDiagnosticsLive(selectedService, { source: src, page: 1, cursor: 0 });
                      }}
                      className="input"
                      style={{ maxWidth: 200 }}
                    >
                      <option value="container_live">Container live</option>
                      <option value="container_history">Container history (Loki)</option>
                      <option value="file_live">File logs (live)</option>
                      <option value="file_history">File history (Loki)</option>
                    </select>

                    {(diagLogSource === "file_live" || diagLogSource === "file_history") && (
                      <select
                        className="input"
                        style={{ maxWidth: 260 }}
                        value={diagFilePath}
                        onChange={async (e) => {
                          setDiagFilePath(e.target.value);
                          if (selectedService) await loadDiagnosticsLive(selectedService, { source: diagLogSource, page: 1 });
                        }}
                      >
                        <option value="">Auto path</option>
                        {(diagnostics?.readiness?.paths_checked || []).map((p: any) => (
                          <option key={p.path} value={p.path}>{p.path}{p.readable ? "" : " (restricted)"}</option>
                        ))}
                      </select>
                    )}
                    <select value={tailLines} onChange={(e) => setTailLines(Number(e.target.value))}>
                      <option value={100}>Tail 100</option>
                      <option value={250}>Tail 250</option>
                      <option value={500}>Tail 500</option>
                      <option value={1000}>Tail 1000</option>
                    </select>
                    <label style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
                      <input type="checkbox" checked={autoPollLogs} onChange={(e) => setAutoPollLogs(e.target.checked)} disabled={diagLogSource !== "container_live"} />
                      Auto-poll
                    </label>
                    <label style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
                      <input type="checkbox" checked={logAutoScroll} onChange={(e) => setLogAutoScroll(e.target.checked)} />
                      Auto-scroll
                    </label>
                    <button type="button" className="btn btn-secondary btn-xs" onClick={() => setDiagnosticsLive((prev) => prev ? { ...prev, lines: [] } : prev)}>Clear</button>
                    {(diagLogSource === "container_history" || diagLogSource === "file_history") && (
                      <>
                        <button type="button" className="btn btn-secondary btn-xs" disabled={historyPage <= 1 && !historyPreviousCursor} onClick={async () => {
                          const p = Math.max(1, historyPage - 1);
                          setHistoryPage(p);
                          if (selectedService) await loadDiagnosticsLive(selectedService, {
                            source: diagLogSource,
                            page: p,
                            cursor: historyPreviousCursor || undefined,
                          });
                        }}>Newer</button>
                        <button type="button" className="btn btn-secondary btn-xs" disabled={Boolean(historyTotalPages && historyPage >= historyTotalPages && !historyCursor)} onClick={async () => {
                          const p = historyPage + 1;
                          setHistoryPage(p);
                          if (selectedService) await loadDiagnosticsLive(selectedService, {
                            source: diagLogSource,
                            page: p,
                            cursor: historyCursor || undefined,
                          });
                        }}>Older</button>
                        <small style={{ color: "var(--ink-4)" }}>Page {historyPage}{historyTotalPages ? ` / ${historyTotalPages}` : ""}</small>
                      </>
                    )}
                  </div>
                  {diagnosticsLive && (
                    <>
                      <small style={{ color: "var(--ink-4)" }}>
                        Loaded {diagnosticsLive.lines.length} lines · source {diagLogSource}
                      </small>
                      {diagnosticsLive.error && (
                        <div role="alert" style={{ color: "var(--err)", fontSize: "0.85rem", marginTop: "0.35rem" }}>
                          Diagnostics unavailable: {diagnosticsLive.error}
                        </div>
                      )}
                    </>
                  )}
                </div>
                <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
                  {(["INFO", "WARN", "ERROR", "DEBUG"] as const).map((lvl) => (
                    <button
                      key={lvl}
                      type="button"
                      className={`btn btn-xs ${logLevelFilters[lvl] ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setLogLevelFilters((f) => ({ ...f, [lvl]: !f[lvl] }))}
                    >
                      {lvl}
                    </button>
                  ))}
                  <input
                    className="input"
                    style={{ maxWidth: 220, marginLeft: 8 }}
                    placeholder="Search / regex…"
                    value={logSearchQuery}
                    onChange={(e) => setLogSearchQuery(e.target.value)}
                  />
                </div>
                {/* Event rate sparkline */}
                {diagnosticsLive && diagnosticsLive.lines.length > 0 && (
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 36, padding: "0 2px" }}>
                    {(() => {
                      const lines = diagnosticsLive.lines;
                      const bins = 18;
                      const size = Math.max(1, Math.ceil(lines.length / bins));
                      const counts = Array.from({ length: bins }, (_, i) => {
                        const slice = lines.slice(i * size, (i + 1) * size);
                        const info = slice.filter((l) => !/err|warn/i.test(l.level || "")).length;
                        const warn = slice.filter((l) => /warn/i.test(l.level || "")).length;
                        const err = slice.filter((l) => /err/i.test(l.level || "")).length;
                        return { info, warn, err, total: slice.length };
                      });
                      const maxT = Math.max(1, ...counts.map((c) => c.total));
                      return counts.map((c, i) => {
                        const h = 4 + Math.round(Math.sqrt(c.total) / Math.sqrt(maxT) * 28);
                        const ePct = c.total ? (c.err / c.total) * 100 : 0;
                        const wPct = c.total ? (c.warn / c.total) * 100 : 0;
                        const iPct = Math.max(0, 100 - ePct - wPct);
                        return (
                          <div
                            key={i}
                            title={`${c.total} lines`}
                            style={{
                              flex: 1,
                              height: h,
                              borderRadius: "2px 2px 0 0",
                              background: `linear-gradient(to top, var(--info) 0% ${iPct}%, var(--warn) ${iPct}% ${iPct + wPct}%, var(--err) ${iPct + wPct}% 100%)`,
                            }}
                          />
                        );
                      });
                    })()}
                  </div>
                )}

                <div 
                  className="console"
                  style={{
                    flex: 1,
                    minHeight: "360px",
                    background: "#020408",
                    color: "#34d399",
                    fontFamily: "var(--mono)",
                    fontSize: "0.85rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "10px",
                    padding: "1rem",
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.25rem"
                  }}
                >
                  {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).filter((line) => {
                    const lvl = (line.level || "INFO").toUpperCase();
                    const key = lvl.includes("ERR") ? "ERROR" : lvl.includes("WARN") ? "WARN" : lvl.includes("DEBUG") ? "DEBUG" : "INFO";
                    if (!logLevelFilters[key]) return false;
                    if (!logSearchQuery.trim()) return true;
                    try {
                      return new RegExp(logSearchQuery, "i").test(line.message || "");
                    } catch {
                      return (line.message || "").toLowerCase().includes(logSearchQuery.toLowerCase());
                    }
                  }).map((line, index) => {
                    let timeStr = "";
                    try {
                      timeStr = new Date(line.timestamp).toISOString().replace("T", " ").substring(0, 19);
                    } catch {
                      timeStr = String(line.timestamp);
                    }
                    const levelUpper = (line.level || "INFO").toUpperCase().padEnd(5);
                    let levelColor = "#38bdf8";
                    if (levelUpper.includes("ERR")) levelColor = "#f87171";
                    else if (levelUpper.includes("WARN")) levelColor = "#fbbf24";
                    else if (levelUpper.includes("DEBUG")) levelColor = "#a78bfa";

                    return (
                      <div key={index} style={{ display: "flex", gap: "0.75rem", fontFamily: "var(--mono)", fontSize: "0.82rem", borderBottom: "1px solid rgba(255,255,255,0.02)", padding: "2px 0" }}>
                        <span style={{ color: "var(--ink-4)", flexShrink: 0 }}>{timeStr}</span>
                        <span style={{ color: levelColor, fontWeight: "bold", flexShrink: 0 }}>{levelUpper}</span>
                        <code style={{ color: "#e2e8f0", wordBreak: "break-all", textAlign: "left" }}>{line.message}</code>
                      </div>
                    );
                  })}
                  {(diagnosticsLive?.lines ?? diagnostics?.recent_logs ?? []).length === 0 && (
                    <div style={{ color: "var(--ink-4)", textAlign: "center", padding: "2rem" }}>
                      {diagnosticsLive?.error
                        ? "No diagnostic lines returned for this source. Resolve the reported error and refresh."
                        : "No logs streamed yet. Trigger some container traffic or click Refresh."}
                    </div>
                  )}
                </div>
              </div>
            )}

            {diagTab === "files" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ background: "rgba(255,255,255,0.02)", padding: "1rem", borderRadius: "10px", border: "1px solid var(--line)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                    <h4>File Accessibility checks</h4>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={runLogBackfill}
                      disabled={!diagnostics?.readiness.backfill_requirements?.ready}
                    >
                      Backfill to Loki
                    </button>
                  </div>
                  {diagnostics?.readiness.backfill_requirements && (
                    <div className="tags" style={{ marginTop: "0.55rem" }}>
                      <span>{diagnostics.readiness.backfill_requirements.loki_configured ? "Loki configured" : "Loki missing"}</span>
                      <span>{diagnostics.readiness.backfill_requirements.file_log_paths_present ? "file paths configured" : "file paths missing"}</span>
                      {diagnostics.readiness.backfill_requirements.requires_become && <span>requires sudo/become</span>}
                      {diagnostics.readiness.backfill_requirements.missing.map((item) => <span key={`backfill-missing-${item}`}>{item}</span>)}
                    </div>
                  )}
                  {diagnostics ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem" }}>
                      {diagnostics.readiness.paths_checked.map((p, idx) => (
                        <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                          <span><code>{p.path}</code></span>
                          <span className={`pill ${p.readable ? "pill-ok" : "pill-error"}`}>{p.readable ? "readable" : "restricted"}</span>
                        </div>
                      ))}
                    </div>
                  ) : <p>Loading checks...</p>}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                  <h4 style={{ margin: 0 }}>Archived log files</h4>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                    <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.85rem", color: "var(--ink-3)" }}>
                      <input type="checkbox" checked={archiveGzipOnly} onChange={(e) => setArchiveGzipOnly(e.target.checked)} />
                      Gzipped only
                    </label>
                    <button type="button" className="btn btn-secondary btn-sm" disabled={selectedArchiveIds.length === 0} onClick={bulkDownloadArchives}>
                      Bulk download ({selectedArchiveIds.length})
                    </button>
                  </div>
                </div>
                <table className="lf-table" style={{ marginTop: "0.5rem" }}>
                  <thead>
                    <tr>
                      <th style={{ width: 36 }}></th>
                      <th>File name path</th>
                      <th style={{ width: "120px" }}>Size</th>
                      <th style={{ width: "120px" }}>Line count</th>
                      <th style={{ width: "100px" }}>State</th>
                      <th style={{ width: "100px" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {archives.filter((arch) => !archiveGzipOnly || (arch.path || "").endsWith(".gz")).map((arch) => (
                      <tr 
                        key={arch.id} 
                        style={{ cursor: "pointer" }}
                        onClick={async () => {
                        setSelectedArchive(arch);
                        setArchivePreviewLines([]);
                        if (!selectedService) return;
                        setArchivePreviewLoading(true);
                        try {
                          let lines: any[] = [];
                          try {
                            const targetServiceId = diagnosticsTargets.find((target) => target.service_key === (diagnostics?.target_service_key ?? diagnosticsTargetKey))?.service_id ?? selectedService.id;
                            const viewed = await api<any>(`/api/services/${targetServiceId}/diagnostics/archives/${arch.id}/view?max_lines=300`);
                            lines = viewed.lines || viewed.entries || viewed.content?.split?.("\n")?.map((m: string) => ({ message: m, level: "INFO", timestamp: new Date().toISOString() })) || [];
                          } catch {
                            const targetServiceId = diagnosticsTargets.find((target) => target.service_key === (diagnostics?.target_service_key ?? diagnosticsTargetKey))?.service_id ?? selectedService.id;
                            const data = await api<any>(`/api/services/${targetServiceId}/diagnostics/file-tail?log_path=${encodeURIComponent(arch.path)}&tail_lines=300`);
                            lines = data.lines || data.entries || [];
                          }
                          setArchivePreviewLines(Array.isArray(lines) ? lines.map((l: any) => typeof l === "string" ? { message: l, level: "INFO", timestamp: new Date().toISOString() } : l) : []);
                        } catch {
                          setArchivePreviewLines([{ level: "WARN", message: "Unable to read file from node.", timestamp: new Date().toISOString() }]);
                        } finally {
                          setArchivePreviewLoading(false);
                        }
                      }}
                      >
                        <td onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedArchiveIds.includes(arch.id)}
                            onChange={(e) => {
                              setSelectedArchiveIds((ids) =>
                                e.target.checked ? [...ids, arch.id] : ids.filter((id) => id !== arch.id)
                              );
                            }}
                          />
                        </td>
                        <td className="fn">
                          <span className="ico" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "24px", height: "18px", background: "var(--bg-sunken)", color: "var(--ink-3)", borderRadius: "4px", marginRight: "8px", fontSize: "8px", fontWeight: "bold" }}>LOG</span>
                          <code>{arch.path}</code>
                        </td>
                        <td className="size">{Math.round(arch.size_bytes / 1024)} KB</td>
                        <td className="lines">{arch.line_count}</td>
                        <td>
                          <span className={`pill ${arch.readable === "yes" ? "pill-ok" : "pill-warn"}`}>
                            {arch.readable}
                          </span>
                        </td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <button type="button" className="btn btn-secondary btn-xs" onClick={() => downloadArchive(arch.id)}>
                            Download
                          </button>
                        </td>
                      </tr>
                    ))}
                    {archives.length === 0 && (
                      <tr>
                        <td colSpan={6} style={{ padding: "1.5rem", textAlign: "center", color: "var(--ink-4)" }}>No log archive folders scanned.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {diagTab === "analytics" && <LogAnalystChat />}

          </GlassCard>
        ) : (
          <GlassCard style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
            <h3>Select a card</h3>
            <p style={{ color: "var(--ink-4)" }}>Select a node service card from the navigator tree to open log consoles.</p>
          </GlassCard>
        )}
      </div>
    </div>
  );

}
