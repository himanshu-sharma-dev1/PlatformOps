// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { renderCircularGauge } from "../components/charts";

/** ReliabilityView — Phase 1 extracted page JSX. */
export function ReliabilityView() {
  const p = usePlatform() as any;
  const checks = p.checks;
  const completeMaintenance = p.completeMaintenance;
  const evaluateSlo = p.evaluateSlo;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const incidents = p.incidents;
  const maintenance = p.maintenance;
  const notice = p.notice;
  const openIncident = p.openIncident;
  const refresh = p.refresh;
  const resolveIncident = p.resolveIncident;
  const runIncidentRunbook = p.runIncidentRunbook;
  const runMonitoringSweep = p.runMonitoringSweep;
  const setNotice = p.setNotice;
  const slos = p.slos;


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Reliability</h1>
          <p className="sub">Advanced SRE tooling: health sweeps, SLO evaluation, incidents, and maintenance. Not part of the primary GlitchTip Monitoring page.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={runMonitoringSweep}>Health sweep</button>
          <button className="btn btn-secondary btn-sm" onClick={evaluateSlo}>Evaluate SLOs</button>
          <button className="btn btn-primary btn-sm" onClick={() => openIncident()}>Open incident</button>
        </div>
      </div>
      <div className="notice" style={{ fontSize: "0.85rem" }}>
        Secondary surface — Monitoring remains the GlitchTip workspace for app errors/uptime/APM.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
        <GlassCard style={{ padding: "1.25rem" }}>
          <h3 style={{ marginTop: 0 }}>SLO reports ({slos.length})</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", justifyContent: "space-around" }}>
            {slos.slice(0, 8).map((s) => {
              const color = s.status === "burning" ? "var(--err)" : s.status === "warning" ? "var(--warn)" : "var(--ok)";
              return renderCircularGauge(parseFloat(s.observed) || 0, parseFloat(s.target) || 100, s.name, color);
            })}
            {slos.length === 0 && <p style={{ color: "var(--ink-4)" }}>No SLO reports. Run Evaluate SLOs when Prometheus availability series exist.</p>}
          </div>
        </GlassCard>
        <GlassCard style={{ padding: "1.25rem" }}>
          <h3 style={{ marginTop: 0 }}>Health checks ({checks.length})</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            {checks.slice(0, 20).map((c) => (
              <div key={c.id} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8, fontSize: "0.85rem" }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span className={`status-dot ${c.status}`} style={{ width: 8, height: 8, borderRadius: "50%" }} />
                  <strong>{c.name}</strong>
                </div>
                <small style={{ color: "var(--ink-4)" }}>{c.value}</small>
              </div>
            ))}
            {checks.length === 0 && <p style={{ color: "var(--ink-4)" }}>No checks yet. Run Health sweep.</p>}
          </div>
        </GlassCard>
        <GlassCard style={{ padding: "1.25rem" }}>
          <h3 style={{ marginTop: 0 }}>Incidents</h3>
          {incidents.map((inc) => (
            <div key={inc.id} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", marginBottom: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{inc.title}</strong>
                <span className={`pill ${inc.severity === "sev1" ? "pill-error" : "pill-warn"}`}>{inc.severity}</span>
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--ink-3)", margin: "4px 0" }}>{inc.summary}</p>
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <button className="btn btn-secondary btn-xs" onClick={() => runIncidentRunbook(inc)}>Runbook</button>
                <button className="btn btn-primary btn-xs" onClick={() => resolveIncident(inc)}>Resolve</button>
              </div>
            </div>
          ))}
          {incidents.length === 0 && <p style={{ color: "var(--ink-4)" }}>No open incidents.</p>}
        </GlassCard>
        <GlassCard style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>Maintenance</h3>
            <button className="btn btn-secondary btn-xs" onClick={async () => {
              const starts = new Date();
              const ends = new Date(Date.now() + 3600_000);
              await api("/api/maintenance", {
                method: "POST",
                body: JSON.stringify({
                  title: `Maintenance ${starts.toISOString().slice(0, 16)}`,
                  starts_at: starts.toISOString(),
                  ends_at: ends.toISOString(),
                  impact: "Scheduled maintenance window",
                }),
              });
              setNotice("Maintenance window scheduled");
              await refresh();
            }}>Schedule 1h window</button>
          </div>
          {maintenance.map((m) => (
            <div key={m.id} style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.65rem", marginTop: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{m.title}</strong>
                <span className="pill pill-ok">{m.status}</span>
              </div>
              <small style={{ color: "var(--ink-4)" }}>Start {formatLocalTimestamp(m.starts_at)}</small>
              <div style={{ textAlign: "right", marginTop: 4 }}>
                <button className="btn btn-secondary btn-xs" onClick={() => completeMaintenance(m)}>Complete</button>
              </div>
            </div>
          ))}
          {maintenance.length === 0 && <p style={{ color: "var(--ink-4)" }}>No maintenance windows.</p>}
        </GlassCard>
      </div>
    </div>
  );

}
