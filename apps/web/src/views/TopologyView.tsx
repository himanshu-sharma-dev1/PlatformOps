// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";

/** TopologyView — Phase 1 extracted page JSX. */
export function TopologyView() {
  const p = usePlatform() as any;
  const deploySubsystem = p.deploySubsystem;
  const notice = p.notice;
  const plan = p.plan;
  const planSubsystem = p.planSubsystem;
  const refresh = p.refresh;
  const selectedSubsystem = p.selectedSubsystem;
  const subsystemPlan = p.subsystemPlan;
  const topology = p.topology;


  const subsystems = Object.keys(topology?.subsystems || {});
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Topology</h1>
          <p className="sub">Advanced subsystem dependency map and rollout planning. Separate from the primary Clusters workspace.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refresh()}>Refresh inventory</button>
        </div>
      </div>
      <div className="notice" style={{ fontSize: "0.85rem" }}>
        Secondary surface — use Clusters for day-to-day node/service operations.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem" }}>
        <GlassCard style={{ padding: "1rem" }}>
          <h3 style={{ marginTop: 0, marginBottom: "0.75rem" }}>Subsystems</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            {subsystems.map((name) => (
              <button
                key={name}
                type="button"
                className={`btn btn-sm ${selectedSubsystem === name ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "flex-start" }}
                onClick={() => planSubsystem(name)}
              >
                {name}
                <span style={{ marginLeft: "auto", opacity: 0.7 }}>{(topology?.subsystems?.[name] || []).length}</span>
              </button>
            ))}
            {subsystems.length === 0 && <p style={{ color: "var(--ink-4)" }}>No subsystem graph loaded.</p>}
          </div>
        </GlassCard>
        <GlassCard style={{ padding: "1.25rem" }}>
          <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
            <h2>{selectedSubsystem || "Select subsystem"}</h2>
            {selectedSubsystem && (
              <button className="btn btn-primary btn-sm" onClick={() => deploySubsystem(selectedSubsystem)}>Deploy sequence</button>
            )}
          </div>
          {subsystemPlan ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <p style={{ color: "var(--ink-3)", margin: 0 }}>{subsystemPlan.summary}</p>
              {(subsystemPlan.steps || []).map((step: any, idx: number) => (
                <div key={`${step.service_key}-${idx}`} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.75rem", display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <strong>Step {idx + 1}: {step.name || step.service_key}</strong>
                    <div style={{ color: "var(--ink-4)", fontSize: "0.8rem" }}>{step.action} · {step.container_name}</div>
                  </div>
                  <span className={`pill ${["running", "healthy"].includes((step.status || "").toLowerCase()) ? "pill-ok" : "pill-warn"}`}>{step.status || "pending"}</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "var(--ink-4)" }}>Select a subsystem to generate a dependency-ordered rollout plan for the current node.</p>
          )}
          {(topology?.edges || []).length > 0 && (
            <div style={{ marginTop: "1.25rem" }}>
              <h4>Dependency edges</h4>
              <div style={{ maxHeight: 220, overflow: "auto", fontSize: "0.8rem", color: "var(--ink-3)" }}>
                {topology!.edges.slice(0, 40).map((e, i) => (
                  <div key={i} style={{ padding: "0.25rem 0", borderBottom: "1px solid var(--line-2)" }}>
                    {e.from_key || "∅"} → {e.to_key} <span className="pill" style={{ fontSize: "0.7rem" }}>{e.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );

}
