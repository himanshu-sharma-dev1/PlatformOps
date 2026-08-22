// @ts-nocheck
import React, { useEffect } from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { renderSVGTimeSeriesChart, renderUptimeAvailabilityBlocks, uptimeLatencySeries } from "../components/charts";

/** GlitchTipWorkspace — Phase 1 extracted page JSX. */
export function GlitchTipWorkspace() {
  const p = usePlatform() as any;
  const checks = p.checks;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const gtActiveMonitorTab = p.gtActiveMonitorTab;
  const gtEventDetails = p.gtEventDetails;
  const gtIntegrationStatus = p.gtIntegrationStatus;
  const gtIssues = p.gtIssues;
  const gtIssuesHasMore = p.gtIssuesHasMore;
  const gtKeys = p.gtKeys;
  const gtSdkLang = p.gtSdkLang;
  const gtSelectedIssueId = p.gtSelectedIssueId;
  const gtSelectedServiceId = p.gtSelectedServiceId;
  const gtWindow = p.gtWindow;
  const gtTransactions = p.gtTransactions;
  const gtUptimeMonitors = p.gtUptimeMonitors;
  const gtDataStatus = p.gtDataStatus || "idle";
  const gtDataError = p.gtDataError;
  const gtHealth = p.gtHealth;
  const incidents = p.incidents;
  const loadEventDetails = p.loadEventDetails;
  const loadGlitchTipDataForService = p.loadGlitchTipDataForService;
  const loadMoreGtIssues = p.loadMoreGtIssues;
  const runAddMonitor = p.runAddMonitor;
  const runDeleteMonitor = p.runDeleteMonitor;
  const runIssueAction = p.runIssueAction;
  const runPatchObservability = p.runPatchObservability;
  const services = p.services;
  const setGtActiveMonitorTab = p.setGtActiveMonitorTab;
  const setGtSdkLang = p.setGtSdkLang;
  const setGtSelectedIssueId = p.setGtSelectedIssueId;
  const setGtSelectedServiceId = p.setGtSelectedServiceId;
  const setNotice = p.setNotice;
  const setTxSort = p.setTxSort;
  const setUptimeForm = p.setUptimeForm;
  const setUptimeFormVisible = p.setUptimeFormVisible;
  const txSort = p.txSort;
  const uptimeForm = p.uptimeForm;
  const uptimeFormVisible = p.uptimeFormVisible;


  const selectedService = services.find((s) => s.id === gtSelectedServiceId) || services[0];
  
  const configured = gtIntegrationStatus?.configured;
  const reachable = gtIntegrationStatus?.reachable;
  const integrationState = gtIntegrationStatus?.availability || (configured && reachable ? "available" : "unavailable");
  
  const handleServiceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = parseInt(e.target.value);
    setGtSelectedServiceId(val);
    const svc = services.find((s) => s.id === val);
    if (svc) {
      loadGlitchTipDataForService(svc.name, gtWindow);
    }
  };

  useEffect(() => {
    if (gtSelectedServiceId || services.length === 0) return;
    const firstService = services[0];
    setGtSelectedServiceId(firstService.id);
    loadGlitchTipDataForService(firstService.name, gtWindow);
  }, [gtSelectedServiceId, services, gtWindow, loadGlitchTipDataForService, setGtSelectedServiceId]);
  
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(255, 255, 255, 0.02)", padding: "0.75rem 1rem", borderRadius: "12px", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span className={`status-dot ${integrationState === "available" ? "ok" : integrationState === "error" ? "error" : "warn"}`} style={{ width: "10px", height: "10px", borderRadius: "50%", display: "inline-block" }}></span>
            <strong style={{ fontSize: "0.9rem" }}>
              {integrationState === "available" ? "GlitchTip connected" : integrationState === "error" ? "GlitchTip error" : "GlitchTip unavailable"}
            </strong>
          </div>
          {configured && (
            <small style={{ color: "var(--ink-4)" }}>
              Base URL: <code>{gtIntegrationStatus?.base_url}</code> | Org: <code>{gtIntegrationStatus?.org}</code>
            </small>
          )}
          {gtHealth && (
            <small style={{ color: gtHealth.health === "ok" ? "var(--ok)" : gtHealth.health === "unavailable" ? "var(--ink-4)" : "var(--err)" }}>
              Target health: <strong>{gtHealth.health}</strong>{gtHealth.container_state ? ` · ${gtHealth.container_state}` : ""}
            </small>
          )}
        </div>
        
        <div style={{ fontSize: "0.85rem", color: "var(--ink-3)" }}>
            Target: <strong style={{ color: "var(--ink)" }}>{selectedService?.name || "—"}</strong>
            {selectedService ? <code style={{ marginLeft: 8 }}>{selectedService.service_key}</code> : null}
          </div>
      </div>

      {gtDataStatus !== "available" && gtDataStatus !== "idle" && (
        <GlassCard style={{ padding: "0.75rem 1rem", borderColor: gtDataStatus === "error" ? "var(--err)" : "var(--line)" }}>
          <strong>{gtDataStatus === "loading" ? "Loading direct GlitchTip data…" : `GlitchTip data: ${gtDataStatus}`}</strong>
          {gtDataError ? <span style={{ marginLeft: 8, color: "var(--ink-4)" }}>{gtDataError}</span> : null}
        </GlassCard>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 3fr", gap: "1.5rem" }}>
        <GlassCard style={{ padding: "1rem", height: "fit-content" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <button 
              onClick={() => setGtActiveMonitorTab("issues")}
              className={`btn ${gtActiveMonitorTab === "issues" ? "btn-primary" : "btn-secondary"}`}
              style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
            >
              Issues ({gtIssues.length})
            </button>
            <button 
              onClick={() => setGtActiveMonitorTab("uptime")}
              className={`btn ${gtActiveMonitorTab === "uptime" ? "btn-primary" : "btn-secondary"}`}
              style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
            >
              Uptime ({gtUptimeMonitors.length})
            </button>
            <button 
              onClick={() => setGtActiveMonitorTab("performance")}
              className={`btn ${gtActiveMonitorTab === "performance" ? "btn-primary" : "btn-secondary"}`}
              style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
            >
              Performance ({gtTransactions.length})
            </button>
            <button 
              onClick={() => setGtActiveMonitorTab("keys")}
              className={`btn ${gtActiveMonitorTab === "keys" ? "btn-primary" : "btn-secondary"}`}
              style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
            >
              Keys / SDK
            </button>
            <button 
              onClick={() => setGtActiveMonitorTab("patch")}
              className={`btn ${gtActiveMonitorTab === "patch" ? "btn-primary" : "btn-secondary"}`}
              style={{ justifyContent: "flex-start", padding: "0.75rem 1rem", fontSize: "0.85rem", textAlign: "left" }}
            >
              Runtime patch
            </button>
          </div>
        </GlassCard>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {gtActiveMonitorTab === "issues" && (
            <GlassCard style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Active Issues &amp; Tracebacks</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadGlitchTipDataForService(selectedService.name, gtWindow)}>Refresh</button>
              </div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {gtIssues.map((issue) => {
                  const isExpanded = gtSelectedIssueId === issue.id;
                  return (
                    <div key={issue.id} style={{ border: "1px solid var(--line-2)", borderRadius: "8px", background: "rgba(255,255,255,0.01)", overflow: "hidden" }}>
                      <div style={{ padding: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", background: "rgba(255,255,255,0.01)" }} onClick={() => isExpanded ? setGtSelectedIssueId(null) : loadEventDetails(issue.id)}>
                        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                          <span className="pill pill-error" style={{ textTransform: "uppercase", fontSize: "0.7rem" }}>{issue.level}</span>
                          <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{issue.title}</span>
                        </div>
                        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                          <span style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>Seen: <strong>{issue.count}</strong> times</span>
                          <span style={{ transition: "transform 0.2s", transform: isExpanded ? "rotate(90deg)" : "none" }}>▶</span>
                        </div>
                      </div>

                      {isExpanded && (
                        <div style={{ padding: "1rem", borderTop: "1px solid var(--line-2)", background: "rgba(0,0,0,0.15)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                          {gtEventDetails ? (
                            <>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", fontSize: "0.8rem" }}>
                                <div>
                                  <div style={{ color: "var(--ink-4)" }}>Event ID:</div>
                                  <code>{gtEventDetails.eventID}</code>
                                </div>
                                <div>
                                  <div style={{ color: "var(--ink-4)" }}>Date / Time:</div>
                                  <code>{formatLocalTimestamp(gtEventDetails.dateCreated)}</code>
                                </div>
                              </div>

                              {gtEventDetails.entries?.map((entry: any, index: number) => {
                                if (entry.type === "exception") {
                                  return (
                                    <div key={index} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                      <h4 style={{ fontSize: "0.9rem", color: "var(--err)", fontWeight: 600 }}>Stack Trace Exception</h4>
                                      {entry.data?.values?.map((val: any, valIdx: number) => (
                                        <div key={valIdx} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--err)" }}>{val.type}: {val.value}</div>
                                          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                                            {val.stacktrace?.frames?.map((frame: any, frameIdx: number) => (
                                              <div key={frameIdx} style={{ padding: "0.5rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line-2)", borderRadius: "6px", fontSize: "0.8rem" }}>
                                                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--ink-3)" }}>
                                                  <span>File: <code>{frame.filename}</code></span>
                                                  <span>Line: <strong>{frame.lineNo}</strong> in <code>{frame.function}</code></span>
                                                </div>
                                                {frame.context_line && (
                                                  <pre style={{ margin: "6px 0 0 0", padding: "4px", background: "rgba(0,0,0,0.3)", borderRadius: "4px", borderLeft: "3px solid var(--err)", color: "var(--ink-2)", overflowX: "auto" }}>
                                                    {frame.context_line}
                                                  </pre>
                                                )}
                                                {frame.vars && Object.keys(frame.vars).length > 0 && (
                                                  <div style={{ marginTop: "6px", fontSize: "0.75rem" }}>
                                                    <span style={{ color: "var(--ink-4)", fontWeight: 600 }}>Local variables:</span>
                                                    <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "4px" }}>
                                                      <tbody>
                                                        {Object.entries(frame.vars).map(([k, v]: [string, any]) => (
                                                          <tr key={k} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                                                            <td style={{ color: "var(--navy-100)", width: "30%", padding: "2px 4px" }}>{k}</td>
                                                            <td style={{ color: "var(--ink-3)", padding: "2px 4px" }}><code>{JSON.stringify(v)}</code></td>
                                                          </tr>
                                                        ))}
                                                      </tbody>
                                                    </table>
                                                  </div>
                                                )}
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  );
                                }
                                if (entry.type === "breadcrumbs") {
                                  return (
                                    <div key={index} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                      <h4 style={{ fontSize: "0.9rem", color: "var(--navy-100)", fontWeight: 600 }}>Breadcrumbs Timeline</h4>
                                      <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "250px", overflowY: "auto" }}>
                                        {entry.data?.values?.map((crumb: any, cIdx: number) => (
                                          <div key={cIdx} style={{ fontSize: "0.75rem", padding: "4px 8px", background: "rgba(255,255,255,0.02)", borderLeft: "3px solid var(--line-2)", display: "flex", gap: "1rem" }}>
                                            <span style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(crumb.timestamp)}</span>
                                            <span className="pill" style={{ fontSize: "0.65rem", padding: "2px 4px" }}>{crumb.category}</span>
                                            <span style={{ flex: 1 }}>{crumb.message}</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                }
                                return null;
                              })}
                              
                              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => runIssueAction(issue.id, "resolve", selectedService.name)}>Mark Resolved</button>
                                <button className="btn btn-secondary btn-sm" onClick={() => runIssueAction(issue.id, "ignore", selectedService.name)}>Ignore / Mute</button>
                              </div>
                            </>
                          ) : (
                            <div style={{ color: "var(--ink-4)", textAlign: "center", padding: "1rem" }}>Loading issue traceback event details...</div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {gtIssues.length > 0 && (
                  <div style={{ display: "flex", justifyContent: "center", padding: "0.75rem" }}>
                    <button type="button" className="btn btn-secondary btn-sm" disabled={!gtIssuesHasMore} onClick={loadMoreGtIssues}>
                      {gtIssuesHasMore ? "Load more issues" : "No more issues"}
                    </button>
                  </div>
                )}
                {gtIssues.length === 0 && (
                  <div style={{ textAlign: "center", padding: "2rem", color: "var(--ink-4)" }}>{gtDataStatus === "available" ? "No unresolved issues mapped to this project slug in GlitchTip." : "Issues are unavailable until the configured GlitchTip probe succeeds."}</div>
                )}
              </div>
            </GlassCard>
          )}

          {gtActiveMonitorTab === "uptime" && (
            <GlassCard style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600 }}>TCP / HTTP Uptime Monitors</h3>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button className="btn btn-primary btn-sm" onClick={() => setUptimeFormVisible(!uptimeFormVisible)}>
                    {uptimeFormVisible ? "Cancel" : "Add Monitor"}
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={() => selectedService && loadGlitchTipDataForService(selectedService.name, gtWindow)}>Refresh</button>
                </div>
              </div>

              {uptimeFormVisible && (
                <div style={{ border: "1px solid var(--line)", borderRadius: "10px", padding: "1rem", background: "rgba(0,0,0,0.1)", marginBottom: "1rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div>
                    <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Monitor Name *</label>
                    <input 
                      type="text" 
                      value={uptimeForm.name} 
                      onChange={(e) => setUptimeForm({ ...uptimeForm, name: e.target.value })}
                      style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Target URL *</label>
                    <input 
                      type="text" 
                      value={uptimeForm.url} 
                      onChange={(e) => setUptimeForm({ ...uptimeForm, url: e.target.value })}
                      style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Type</label>
                    <select 
                      value={uptimeForm.monitor_type} 
                      onChange={(e) => setUptimeForm({ ...uptimeForm, monitor_type: e.target.value })}
                      style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                    >
                      <option value="Ping">Ping TCP Connect</option>
                      <option value="GET">HTTP GET</option>
                      <option value="POST">HTTP POST</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Interval (sec)</label>
                    <input 
                      type="number" 
                      value={uptimeForm.interval} 
                      onChange={(e) => setUptimeForm({ ...uptimeForm, interval: e.target.value })}
                      style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--ink-1)", padding: "0.4rem", borderRadius: "6px" }}
                    />
                  </div>
                  <div style={{ gridColumn: "span 2", display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                    <button className="btn btn-primary" onClick={() => selectedService && runAddMonitor(selectedService.name)}>Submit</button>
                  </div>
                </div>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {gtUptimeMonitors.map((mon) => (
                  <div key={mon.id} style={{ border: "1px solid var(--line-2)", borderRadius: "8px", padding: "1rem", background: "rgba(255,255,255,0.01)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                          <span className={`status-dot ${mon.isUp ? "ok" : "error"}`} style={{ width: "8px", height: "8px", borderRadius: "50%" }}></span>
                          <strong style={{ fontSize: "0.95rem" }}>{mon.name}</strong>
                          <small style={{ color: "var(--ink-4)" }}>({mon.monitorType})</small>
                        </div>
                        <span style={{ fontSize: "0.8rem", color: "var(--ink-3)", display: "block", marginTop: "2px" }}>Target: <code>{mon.url}</code></span>
                      </div>
                      <button className="icon-btn btn-error" onClick={() => selectedService && runDeleteMonitor(mon.id, selectedService.name)}>
                        🗑️
                      </button>
                    </div>

                    {(() => {
                      const history = mon.checks || mon.incidents || [];
                      const latency = uptimeLatencySeries(history);
                      return (
                        <div style={{ marginTop: "0.85rem", borderTop: "1px solid rgba(255,255,255,0.03)", paddingTop: "0.65rem" }}>
                          <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>
                            Availability timeline
                          </span>
                          {renderUptimeAvailabilityBlocks(history)}
                          {latency.length > 0 && (
                            <div style={{ marginTop: "0.75rem" }}>
                              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>
                                Response latency (ms)
                              </span>
                              {renderSVGTimeSeriesChart(latency, { color: "#38bdf8", unit: " ms", height: 64 })}
                            </div>
                          )}
                          {mon.incidents && mon.incidents.length > 0 && (
                            <div style={{ marginTop: "0.75rem" }}>
                              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--ink-3)", display: "block", marginBottom: "4px" }}>Incidents history</span>
                              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "120px", overflowY: "auto" }}>
                                {mon.incidents.slice(0, 5).map((inc: any, iIdx: number) => (
                                  <div key={iIdx} style={{ fontSize: "0.75rem", display: "flex", justifyContent: "space-between", padding: "2px 4px", background: "rgba(255,255,255,0.02)" }}>
                                    <span style={{ color: inc.isUp ? "var(--ok)" : "var(--err)" }}>{inc.isUp ? "ONLINE" : "OFFLINE"}</span>
                                    <span style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(inc.startCheck)}</span>
                                    <span style={{ color: "var(--ink-3)" }}>{inc.reason || "status code check"}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                ))}
                {gtUptimeMonitors.length === 0 && (
                  <div style={{ textAlign: "center", padding: "2rem", color: "var(--ink-4)" }}>No uptime monitors active for this project.</div>
                )}
              </div>
            </GlassCard>
          )}

          {gtActiveMonitorTab === "performance" && (
            <GlassCard style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", gap: "0.75rem", flexWrap: "wrap" }}>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600, margin: 0 }}>API Transaction Endpoints (APM)</h3>
                <select value={txSort} onChange={(e) => setTxSort(e.target.value as any)} className="input" style={{ maxWidth: 180 }}>
                  <option value="latency">Sort: Latency</option>
                  <option value="throughput">Sort: Throughput</option>
                  <option value="failure">Sort: Failure rate</option>
                </select>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--line-2)", color: "var(--ink-4)", fontSize: "0.8rem", textAlign: "left" }}>
                      <th style={{ padding: "0.5rem" }}>Route Transaction</th>
                      <th style={{ padding: "0.5rem" }}>Throughput</th>
                      <th style={{ padding: "0.5rem" }}>Avg Latency</th>
                      <th style={{ padding: "0.5rem" }}>Failure %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...gtTransactions].sort((a, b) => {
                      if (txSort === "throughput") return (b.count || 0) - (a.count || 0);
                      if (txSort === "failure") return (b.failureRate || 0) - (a.failureRate || 0);
                      return (b.avgDuration || 0) - (a.avgDuration || 0);
                    }).map((tx, idx) => (
                      <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)", fontSize: "0.85rem" }}>
                        <td style={{ padding: "0.5rem", color: "var(--navy-100)" }}><code>{tx.transaction || tx.name || "—"}</code></td>
                        <td style={{ padding: "0.5rem" }}>{tx.count ?? "—"}</td>
                        <td style={{ padding: "0.5rem" }}>{Math.round(tx.avgDuration || 0)} ms</td>
                        <td style={{ padding: "0.5rem" }}>{tx.failureRate != null ? `${Number(tx.failureRate).toFixed(1)}%` : "—"}</td>
                      </tr>
                    ))}
                    {gtTransactions.length === 0 && (
                      <tr>
                        <td colSpan={4} style={{ padding: "1.5rem", textAlign: "center", color: "var(--ink-4)" }}>No performance telemetry collected for this window.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          )}

          {gtActiveMonitorTab === "keys" && (
            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}>DSN Keys &amp; SDK Quickstart</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {gtKeys.map((keyInfo, idx) => (
                  <div key={idx} style={{ padding: "1rem", border: "1px solid var(--line-2)", borderRadius: "8px", background: "rgba(255,255,255,0.01)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                      <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>DSN (Data Source Name)</div>
                      <button type="button" className="btn btn-secondary btn-xs" onClick={() => {
                        const dsn = keyInfo.dsn?.public || "";
                        if (dsn) navigator.clipboard?.writeText(dsn).then(() => setNotice("DSN copied")).catch(() => setNotice(dsn));
                      }}>Copy</button>
                    </div>
                    <pre style={{ margin: 0, padding: "8px", background: "rgba(0,0,0,0.3)", borderRadius: "6px", color: "var(--navy-100)", fontSize: "0.85rem", overflowX: "auto" }}>
                      {keyInfo.dsn?.public}
                    </pre>
                  </div>
                ))}
                
                {gtKeys.length === 0 && (
                  <p style={{ color: "var(--ink-4)" }}>No SDK keys returned from GlitchTip for this service.</p>
                )}

                <div style={{ marginTop: "1rem" }}>
                  <div style={{ display: "flex", gap: "0.35rem", marginBottom: "0.5rem" }}>
                    {(["python", "javascript", "go"] as const).map((lang) => (
                      <button key={lang} type="button" className={`btn btn-xs ${gtSdkLang === lang ? "btn-primary" : "btn-secondary"}`} onClick={() => setGtSdkLang(lang)}>{lang}</button>
                    ))}
                  </div>
                  <pre style={{ margin: 0, padding: "10px", background: "rgba(0,0,0,0.4)", borderRadius: "8px", fontSize: "0.8rem", color: "var(--ink-3)", overflowX: "auto" }}>
{(() => {
                    const dsn = gtKeys[0]?.dsn?.public;
                    if (!dsn) return "No DSN available — configure GlitchTip project keys first.";
                    if (gtSdkLang === "javascript") return `npm install @sentry/node

Sentry.init({
dsn: "${dsn}",
tracesSampleRate: 1.0,
});`;
                    if (gtSdkLang === "go") return `import "github.com/getsentry/sentry-go"

err := sentry.Init(sentry.ClientOptions{
Dsn: "${dsn}",
})`;
                    return `pip install sentry-sdk

import sentry_sdk
sentry_sdk.init(
  dsn="${dsn}",
  traces_sample_rate=1.0,
)`;
                  })()}
                  </pre>
                </div>
              </div>
            </GlassCard>
          )}

          {gtActiveMonitorTab === "patch" && (
            <GlassCard style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem" }}>sentry_sdk Injection &amp; Patching</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--ink-3)", marginBottom: "1rem" }}>
                Injects the <code>sentry_sdk</code> package dynamically into the selected service's Docker container, configures <code>sitecustomize.py</code>, and triggers a container restart to start piping exceptions.
              </p>
              <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                <button 
                  className="btn btn-primary" 
                  onClick={() => selectedService && runPatchObservability(selectedService.id, selectedService.name)}
                  disabled={!selectedService}
                >
                  Run runtime patch
                </button>
                <small style={{ color: "var(--ink-4)" }}>
                  Target container: <code>{selectedService?.container_name || "not selected"}</code>
                </small>
              </div>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );

}
