// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { formatExpiry } from "../components/charts";

/** PolicyView — Phase 1 extracted page JSX. */
export function PolicyView() {
  const p = usePlatform() as any;
  const findings = p.findings;
  const forceApprovals = p.forceApprovals;
  const runPolicyScan = p.runPolicyScan;
  const services = p.services;


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Policy</h1>
          <p className="sub">Secondary compliance scan across registered services. Does not replace Clusters day-to-day ops.</p>
        </div>
        <div className="actions">
          <button className="btn btn-primary btn-sm" onClick={runPolicyScan}>Scan policies</button>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.25rem" }}>
        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
            <h2>Open findings</h2>
            <span>{findings.length}</span>
          </div>
          <div className="timeline">
            {findings.map((f) => (
              <article key={f.id} style={{ borderLeft: `3px solid ${f.severity === "high" ? "var(--err)" : "var(--warn)"}` }}>
                <span className="pill" style={{ fontSize: "0.7rem" }}>{f.severity}</span>
                <strong>{f.rule_id}</strong>
                <p style={{ fontSize: "0.85rem", margin: "4px 0" }}>{f.message}</p>
                <small style={{ color: "var(--ink-3)" }}>Remediation: {f.remediation}</small>
              </article>
            ))}
            {findings.length === 0 && <p style={{ color: "var(--ink-4)" }}>No open findings. Run a policy scan to evaluate the inventory.</p>}
          </div>
        </GlassCard>
        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
            <h2>Force-delete approvals</h2>
            <span>{forceApprovals.length}</span>
          </div>
          {forceApprovals.map((a) => (
            <div key={a.id} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", marginBottom: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>#{a.id}</strong>
                <span className={`pill ${a.status === "approved" ? "pill-ok" : "pill-warn"}`}>{a.status}</span>
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--ink-3)", marginTop: 4 }}>{a.reason}</div>
              <small style={{ color: "var(--ink-4)" }}>{a.requested_by} · {formatExpiry(a.expires_at)}</small>
            </div>
          ))}
          {forceApprovals.length === 0 && <p style={{ color: "var(--ink-4)" }}>No force-delete approvals on file.</p>}
        </GlassCard>
      </div>
    </div>
  );

}
