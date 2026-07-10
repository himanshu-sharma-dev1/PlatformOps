// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { isSeedDemoName } from "../components/charts";

/** ObservabilityView — Phase 1 extracted page JSX. */
export function ObservabilityView() {
  const p = usePlatform() as any;
  const bootstrapObservability = p.bootstrapObservability;
  const nodes = p.nodes;
  const obsStackBusy = p.obsStackBusy;
  const obsStackContainers = p.obsStackContainers;
  const obsStackOutput = p.obsStackOutput;
  const observabilityBusyNodeId = p.observabilityBusyNodeId;
  const observabilityPipeline = p.observabilityPipeline;
  const refresh = p.refresh;
  const refreshObservabilityStackStatus = p.refreshObservabilityStackStatus;
  const runObservabilityStackAction = p.runObservabilityStackAction;


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Observability stack</h1>
          <p className="sub">Deploy, status-check, and tear down the Prometheus / Loki / Alloy control plane. Bootstrap collectors on individual nodes.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary" disabled={obsStackBusy === "status"} onClick={() => refreshObservabilityStackStatus()}>
            {obsStackBusy === "status" ? "Refreshing…" : "Refresh status"}
          </button>
          <button className="btn btn-primary" disabled={!!obsStackBusy} onClick={() => runObservabilityStackAction("deploy")}>
            {obsStackBusy === "deploy" ? "Deploying…" : "Deploy stack"}
          </button>
          <button className="btn btn-danger" disabled={!!obsStackBusy} onClick={() => runObservabilityStackAction("teardown")}>
            {obsStackBusy === "teardown" ? "Tearing down…" : "Teardown stack"}
          </button>
        </div>
      </div>

      {(() => {
        const plane = (observabilityPipeline?.nodes ?? []).filter((n) => !isSeedDemoName(n.node_name));
        const healthy = plane.filter((n) => n.pipeline_ready).length;
        return (
      <div className="stat-strip">
        <div className="stat-tile"><div className="stat-label">Pipeline nodes</div><div className="stat-value">{plane.length || "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Healthy</div><div className="stat-value">{plane.length ? healthy : "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Degraded</div><div className="stat-value">{plane.length ? plane.length - healthy : "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Stack containers</div><div className="stat-value">{obsStackContainers.length || "—"}</div></div>
      </div>
        );
      })()}

      <GlassCard style={{ padding: "1.25rem" }}>
        <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
          <h2>Compose status</h2>
          <span>{obsStackContainers.length ? `${obsStackContainers.length} containers` : "no data"}</span>
        </div>
        {obsStackContainers.length > 0 ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                <th style={{ padding: "0.4rem 0" }}>Name</th>
                <th>State</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {obsStackContainers.map((c: any, i: number) => (
                <tr key={c.Name || c.name || i} style={{ borderTop: "1px solid var(--line-2)" }}>
                  <td style={{ padding: "0.45rem 0" }}><code>{c.Name || c.name || "—"}</code></td>
                  <td>{c.State || c.state || "—"}</td>
                  <td style={{ color: "var(--ink-3)" }}>{c.Status || c.status || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: "var(--ink-4)" }}>No stack status yet. Deploy the stack or refresh after compose is available.</p>
        )}
        {obsStackOutput && (
          <pre style={{ marginTop: "1rem", padding: "0.85rem", borderRadius: 10, background: "#010307", color: "#e2e8f0", fontSize: "0.75rem", maxHeight: 280, overflow: "auto", whiteSpace: "pre-wrap" }}>{obsStackOutput}</pre>
        )}
      </GlassCard>

      <GlassCard style={{ padding: "1.25rem" }}>
        <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
          <h2>Per-node plane</h2>
          <span>{observabilityPipeline ? `${observabilityPipeline.nodes.length} nodes` : "loading"}</span>
        </div>
        {observabilityPipeline ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "0.85rem" }}>
            {observabilityPipeline.nodes.map((node) => (
              <article key={node.node_id} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "0.9rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{node.node_name}</strong>
                  <span className={`pill ${node.pipeline_ready ? "pill-ok" : "pill-warn"}`}>{node.ingestion_state}</span>
                </div>
                <div className="tags" style={{ marginTop: 8 }}>
                  {Object.entries(node.components || {}).map(([k, v]) => (
                    <span key={k}>{k}: {String(v)}</span>
                  ))}
                </div>
                {(node.issues || []).length > 0 && (
                  <ul style={{ margin: "0.55rem 0 0 1rem", color: "var(--ink-3)", fontSize: "0.8rem" }}>
                    {node.issues.slice(0, 3).map((issue) => <li key={issue}>{issue}</li>)}
                  </ul>
                )}
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginTop: 10 }}
                  disabled={observabilityBusyNodeId === node.node_id}
                  onClick={() => bootstrapObservability(node.node_id)}
                >
                  {observabilityBusyNodeId === node.node_id ? "Bootstrapping…" : "Bootstrap plane"}
                </button>
              </article>
            ))}
            {observabilityPipeline.nodes.length === 0 && (
              <p style={{ color: "var(--ink-4)" }}>No nodes registered for pipeline reporting.</p>
            )}
          </div>
        ) : (
          <p style={{ color: "var(--ink-4)" }}>Loading pipeline report…</p>
        )}
      </GlassCard>
    </div>
  );

}
