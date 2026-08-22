// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";

const ANALYST_TAGS = new Set(["P", "H4", "UL", "OL", "LI", "STRONG", "EM", "B", "I", "CODE", "SPAN", "BR"]);

function sanitizeAnalystHtml(value: string): string {
  if (typeof DOMParser === "undefined") return "";
  const document = new DOMParser().parseFromString(value || "", "text/html");
  for (const element of Array.from(document.body.querySelectorAll("*"))) {
    if (!ANALYST_TAGS.has(element.tagName)) {
      element.replaceWith(...Array.from(element.childNodes));
      continue;
    }
    const cited = element.tagName === "SPAN" && element.classList.contains("cited");
    for (const attribute of Array.from(element.attributes)) element.removeAttribute(attribute.name);
    if (cited) element.setAttribute("class", "cited");
  }
  return document.body.innerHTML;
}

/** LogAnalystChat — Phase 1 extracted page JSX. */
export function LogAnalystChat() {
  const p = usePlatform() as any;
  const analyticsBusy = p.analyticsBusy;
  const analyticsInput = p.analyticsInput;
  const analyticsMessages = p.analyticsMessages;
  const config = p.config;
  const diagnostics = p.diagnostics;
  const diagnosticsAnalysis = p.diagnosticsAnalysis;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const handleSendAnalyticsChat = p.handleSendAnalyticsChat;
  const incidents = p.incidents;
  const llmStatus = p.llmStatus;
  const openDiagnosticsChangeEvidence = p.openDiagnosticsChangeEvidence;
  const openDiagnosticsSupportingEvidence = p.openDiagnosticsSupportingEvidence;
  const runDiagnosticsInsightAction = p.runDiagnosticsInsightAction;
  const sendDirectAnalyticsQuery = p.sendDirectAnalyticsQuery;
  const setAnalyticsInput = p.setAnalyticsInput;


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", minHeight: "450px" }}>
      {diagnosticsAnalysis && (
        <>
          <div style={{ padding: "1rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(255,255,255,0.03)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
              <div>
                <strong>Diagnostics analysis</strong>
                <div style={{ color: "var(--ink-3)", marginTop: "0.3rem" }}>{diagnosticsAnalysis.overview}</div>
              </div>
              <span className={`pill ${diagnosticsAnalysis.overall_severity === "error" ? "pill-error" : diagnosticsAnalysis.overall_severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                {diagnosticsAnalysis.overall_severity}
              </span>
            </div>
            {diagnosticsAnalysis.next_steps.length > 0 && (
              <div style={{ marginTop: "0.75rem" }}>
                <small style={{ color: "var(--ink-4)" }}>Recommended next steps</small>
                <div className="tags" style={{ marginTop: "0.35rem" }}>
                  {diagnosticsAnalysis.next_steps.map((step) => <span key={step}>{step}</span>)}
                </div>
              </div>
            )}
            {diagnosticsAnalysis.historical_correlation.length > 0 && (
              <div style={{ marginTop: "0.9rem" }}>
                <small style={{ color: "var(--ink-4)" }}>Historical correlation</small>
                <div style={{ marginTop: "0.35rem", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                  {diagnosticsAnalysis.historical_correlation.map((entry) => (
                    <div key={entry} style={{ color: "var(--ink-3)", fontSize: "0.85rem" }}>{entry}</div>
                  ))}
                </div>
              </div>
            )}
            {diagnosticsAnalysis.change_evidence.length > 0 && (
              <div style={{ marginTop: "0.9rem" }}>
                <small style={{ color: "var(--ink-4)" }}>Likely change evidence</small>
                <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {diagnosticsAnalysis.change_evidence.map((item, index) => (
                    <div
                      key={`${item.kind}-${item.created_at}-${index}`}
                      style={{
                        padding: "0.7rem 0.8rem",
                        border: "1px solid var(--line-2)",
                        borderRadius: "10px",
                        background: "rgba(255,255,255,0.02)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                        <strong>{item.title}</strong>
                        <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
                          <span className={`pill ${item.severity === "error" ? "pill-error" : item.severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                            {item.kind}
                          </span>
                          <span className="pill" style={{ fontSize: "0.72rem" }}>{item.confidence}% confidence</span>
                        </div>
                      </div>
                      <div style={{ color: "var(--ink-3)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{item.summary}</div>
                      <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                        {item.detail} · {formatLocalTimestamp(item.created_at)}
                      </div>
                      {item.drift_fields && item.drift_fields.length > 0 && (
                        <div style={{ marginTop: "0.35rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Changed keys</small>
                          <div className="tags" style={{ marginTop: "0.25rem" }}>
                            {item.drift_fields.map((field) => <span key={`${item.title}-${field}`}>{field}</span>)}
                          </div>
                        </div>
                      )}
                      {item.drift_preview && item.drift_preview.length > 0 && (
                        <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                          <small style={{ color: "var(--ink-4)" }}>Drift preview</small>
                          {item.drift_preview.map((preview, previewIndex) => (
                            <div
                              key={`${item.title}-preview-${preview.field ?? previewIndex}`}
                              style={{
                                padding: "0.55rem 0.65rem",
                                borderRadius: "8px",
                                border: "1px solid var(--line)",
                                background: "rgba(255,255,255,0.03)",
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                                <strong style={{ fontSize: "0.82rem" }}>{preview.field ?? "changed field"}</strong>
                                {preview.severity && (
                                  <span className={`pill ${preview.severity === "error" ? "pill-error" : preview.severity === "warning" ? "pill-warn" : "pill-ok"}`}>
                                    {preview.severity}
                                  </span>
                                )}
                              </div>
                              <div style={{ color: "var(--ink-4)", fontSize: "0.78rem", marginTop: "0.2rem" }}>
                                Expected: {String(preview.expected ?? "n/a")}
                              </div>
                              <div style={{ color: "var(--ink-4)", fontSize: "0.78rem", marginTop: "0.1rem" }}>
                                Actual: {String(preview.actual ?? "n/a")}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {item.baseline_snapshot_id && (
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          Baseline snapshot: #{item.baseline_snapshot_id}
                        </div>
                      )}
                      {typeof item.snapshot_version === "number" && (
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          Snapshot version: v{item.snapshot_version}{item.snapshot_id ? ` · snapshot #${item.snapshot_id}` : ""}
                          {item.actor ? ` · actor ${item.actor}` : ""}
                        </div>
                      )}
                      <div style={{ marginTop: "0.55rem", display: "flex", justifyContent: "flex-end" }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => openDiagnosticsChangeEvidence(item)}
                        >
                          {item.target_view === "release" ? "Open release context" : item.target_view === "config-compare" ? "Open config compare" : "Open config timeline"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {diagnosticsAnalysis.recent_incidents.length > 0 && (
              <div style={{ marginTop: "0.9rem" }}>
                <small style={{ color: "var(--ink-4)" }}>Recent incidents in this diagnostics context</small>
                <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {diagnosticsAnalysis.recent_incidents.map((incident) => (
                    <div
                      key={`diag-incident-${incident.id}`}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: "0.75rem",
                        alignItems: "center",
                        padding: "0.6rem 0.75rem",
                        border: "1px solid var(--line-2)",
                        borderRadius: "10px",
                      }}
                      >
                        <div>
                          <strong>{incident.title}</strong>
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                          #{incident.id} · {incident.severity} · {incident.status} · {formatLocalTimestamp(incident.created_at)}
                        </div>
                        <div style={{ color: "var(--ink-3)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                          Match: {incident.match_reason}
                          {incident.latest_runbook_key ? ` · Last runbook: ${incident.latest_runbook_key} (${incident.latest_runbook_status})` : ""}
                        </div>
                        <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: "0.2rem" }}>
                          Suggested now: {incident.suggested_runbook_key}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => runDiagnosticsInsightAction({
                            action_id: "open-existing-incident",
                            label: `Review incident #${incident.id}`,
                            description: incident.summary,
                            service_key: diagnosticsAnalysis.source_service_key,
                            incident_id: incident.id,
                            runbook_key: null,
                            target_view: "monitoring",
                            recommended: false,
                          })}
                        >
                          Review
                        </button>
                        {incident.status === "open" && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => runDiagnosticsInsightAction({
                              action_id: "run-incident-runbook",
                              label: incident.suggested_runbook_key === "dependency-recovery"
                                ? "Run dependency recovery"
                                : incident.suggested_runbook_key === "config-rollback"
                                ? "Run config rollback"
                                : "Run restart runbook",
                              description: incident.remediation,
                              service_key: diagnosticsAnalysis.source_service_key,
                              incident_id: incident.id,
                              runbook_key: incident.suggested_runbook_key,
                              target_view: "monitoring",
                              recommended: false,
                            })}
                          >
                            Runbook
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="timeline">
            {diagnosticsAnalysis.insights.map((insight) => (
              <article key={insight.insight_id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                    <span className={`status ${insight.severity === "error" ? "error" : insight.severity === "warning" ? "warning" : "running"}`}>
                      {insight.severity}
                    </span>
                    <strong>{insight.title}</strong>
                  </div>
                  <span className="pill" style={{ fontSize: "0.72rem" }}>{insight.confidence}% confidence</span>
                </div>
                <p>{insight.summary}</p>
                <small>{insight.rationale}</small>
                {insight.evidence_refs.length > 0 && (
                  <div style={{ marginTop: "0.5rem" }}>
                    <small style={{ color: "var(--ink-4)" }}>Evidence</small>
                    <div className="tags" style={{ marginTop: "0.25rem" }}>
                      {insight.evidence_refs.map((ref) => <span key={`${insight.insight_id}-${ref}`}>{ref}</span>)}
                    </div>
                  </div>
                )}
                {insight.supporting_evidence.length > 0 && (
                  <div style={{ marginTop: "0.65rem" }}>
                    <small style={{ color: "var(--ink-4)" }}>Open supporting evidence</small>
                    <div style={{ marginTop: "0.35rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                      {insight.supporting_evidence.map((evidence) => (
                        <button
                          key={`${insight.insight_id}-${evidence.evidence_id}`}
                          className="btn btn-secondary btn-sm"
                          style={{ justifyContent: "space-between" }}
                          onClick={() => openDiagnosticsSupportingEvidence(evidence)}
                        >
                          <span>{evidence.label}</span>
                          <span style={{ color: "var(--ink-4)", fontSize: "0.76rem" }}>{evidence.target_view}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {insight.actions.length > 0 && (
                  <div style={{ marginTop: "0.65rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {insight.actions.map((action) => (
                      <button
                        key={`${insight.insight_id}-${action.action_id}-${action.service_key ?? "self"}`}
                        className={`btn btn-sm ${action.recommended ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => runDiagnosticsInsightAction(action)}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </>
      )}

      <div style={{ flex: 1, overflowY: "auto", padding: "1.2rem", display: "flex", flexDirection: "column", gap: "1.2rem", border: "1px solid var(--line)", borderRadius: "12px", background: "rgba(0, 0, 0, 0.15)", minHeight: "280px", maxHeight: "400px" }}>
        {analyticsMessages.map((msg, idx) => {
          const isUser = msg.sender === "user";
          return (
            <div key={idx} style={{ display: "flex", gap: "0.75rem", alignSelf: isUser ? "flex-end" : "flex-start", maxWidth: "80%" }}>
              {!isUser && (
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "rgba(99, 102, 241, 0.08)", border: "1px solid var(--navy-500)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", alignSelf: "flex-start", flexShrink: 0 }}>🤖</div>
              )}
              <div style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                <div style={{
                  background: isUser ? "var(--navy-700)" : "var(--bg-card)",
                  border: isUser ? "1px solid var(--navy-500)" : msg.error ? "1px solid rgba(239,68,68,0.45)" : "1px solid var(--line)",
                  boxShadow: isUser ? "0 0 10px rgba(99, 102, 241, 0.15)" : "none",
                  color: "#ffffff",
                  padding: "0.8rem 1rem",
                  borderRadius: isUser ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                  fontSize: "0.88rem",
                  lineHeight: "1.45",
                  maxWidth: "100%",
                }}>
                  {msg.error && !msg.text ? (
                    <span style={{ color: "var(--err)" }}>{msg.error}</span>
                  ) : (
                    <div dangerouslySetInnerHTML={{ __html: sanitizeAnalystHtml((msg.text || "").replace(/\n/g, "<br/>")) }} />
                  )}
                  {msg.error && msg.text ? (
                    <div style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--err)" }}>{msg.error}</div>
                  ) : null}
                  {!isUser && msg.evidence && msg.evidence.length > 0 && (
                    <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 8 }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--ink-4)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Evidence</div>
                      {msg.evidence.slice(0, 4).map((ev, evi) => (
                        <div key={evi} style={{ fontFamily: "var(--mono)", fontSize: "0.72rem", color: "var(--ink-3)", marginBottom: 3 }}>
                          <span style={{ color: /err/i.test(ev.lvl || "") ? "var(--err)" : /warn/i.test(ev.lvl || "") ? "var(--warn)" : "var(--ink-4)" }}>{ev.lvl || "INFO"}</span>
                          {" "}
                          <span className="cited" style={{ color: "var(--navy-100)" }}>{ev.t || ""}</span>
                          {" — "}
                          {(ev.msg || "").slice(0, 180)}
                        </div>
                      ))}
                    </div>
                  )}
                  {!isUser && msg.chart_data && msg.chart_data.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--ink-4)", marginBottom: 4 }}>Error-rate spark</div>
                      <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 36 }}>
                        {msg.chart_data.map((v, ci) => {
                          const max = Math.max(...msg.chart_data!, 1);
                          const h = 4 + Math.round((Number(v) / max) * 28);
                          return <div key={ci} title={String(v)} style={{ flex: 1, height: h, background: "var(--navy-500)", borderRadius: "2px 2px 0 0", opacity: 0.85 }} />;
                        })}
                      </div>
                    </div>
                  )}
                </div>
                <span style={{ fontSize: "0.68rem", color: "var(--ink-4)", marginTop: "4px" }}>
                  {msg.timestamp}{msg.analyst_source ? ` · ${msg.analyst_source}` : ""}
                </span>
              </div>
              {isUser && (
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "rgba(255, 255, 255, 0.05)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", alignSelf: "flex-start", flexShrink: 0 }}>👤</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Suggestion Chips — dynamic from last LLM reply when available */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", padding: "0.25rem 0", alignItems: "center" }}>
        <span className="pill" style={{ fontSize: "0.7rem" }}>
          {llmStatus?.configured ? `LLM ${llmStatus.provider || ""}` : "Deterministic analyst fallback"}
        </span>
        {(
          (analyticsMessages.slice().reverse().find((m) => m.sender === "assistant" && m.suggestions && m.suggestions.length)?.suggestions)
          || [
            "Summarize recent errors in the logs",
            "What is the most likely root cause?",
            "Which dependency looks unhealthy?",
            "Suggest next remediation steps",
          ]
        ).map((s, idx) => (
          <button
            key={idx}
            className="btn btn-secondary btn-sm"
            disabled={analyticsBusy}
            style={{ borderRadius: "20px", fontSize: "0.72rem", padding: "4px 10px", borderColor: "rgba(99,102,241,0.25)", background: "rgba(99,102,241,0.05)" }}
            onClick={() => sendDirectAnalyticsQuery(s)}
          >
            {s.length > 48 ? s.slice(0, 48) + "…" : s}
          </button>
        ))}
      </div>

      {/* Terminal Monospace Input */}
      <div style={{ display: "flex", gap: "0.5rem", padding: "0.4rem 0.6rem", background: "rgba(0, 0, 0, 0.3)", border: "1px solid var(--line)", borderRadius: "8px", alignItems: "center" }}>
        <span style={{ fontFamily: "var(--mono)", color: "var(--navy-500)", fontWeight: "bold", fontSize: "0.95rem", paddingLeft: "0.25rem" }}>$</span>
        <input
          type="text"
          className="input-text"
          style={{ flex: 1, background: "transparent", color: "#ffffff", border: "none", outline: "none", fontFamily: "var(--mono)", fontSize: "0.85rem", padding: "0.25rem" }}
          placeholder="Type command... target: to ks>"
          value={analyticsInput}
          onChange={(e) => setAnalyticsInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSendAnalyticsChat(); }}
        />
        <button className="btn btn-primary btn-sm" style={{ padding: "4px 10px" }} disabled={analyticsBusy || !analyticsInput.trim()} onClick={handleSendAnalyticsChat}>{analyticsBusy ? "Thinking…" : "Execute"}</button>
      </div>
    </div>
  );

}
