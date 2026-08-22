// @ts-nocheck
import React, { useEffect } from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";

/** ObservabilityView — Phase 1 extracted page JSX. */
export function ObservabilityView() {
  const p = usePlatform() as any;
  const status = p.observabilityStatus;
  const marker = p.observabilityMarker;
  const redis = (p.services || []).find((item: any) => item.id === p.selectedService?.id)
    || (p.services || []).find((item: any) => item.service_key === "redis-core");
  const refreshObservabilityStackStatus = p.refreshObservabilityStackStatus;
  useEffect(() => {
    refreshObservabilityStackStatus(redis?.id, marker);
  }, [redis?.id]);

  const signalEntries = Object.entries(status?.signals || {}) as Array<[string, any]>;
  const stateClass = (state: string) => state === "available" ? "pill-ok" : state === "error" || state === "unavailable" ? "pill-err" : "pill-warn";


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Observability readiness</h1>
          <p className="sub">Direct Redis, Prometheus, Alloy, Loki-marker, and optional GlitchTip evidence for the canonical selected service.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary" disabled={p.observabilityLoading || !redis} onClick={() => refreshObservabilityStackStatus(redis?.id, marker)}>
            {p.observabilityLoading ? "Probing…" : "Refresh direct probes"}
          </button>
        </div>
      </div>

      <div className="stat-strip">
        <div className="stat-tile"><div className="stat-label">Overall</div><div className="stat-value">{status?.overall_state || "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Service</div><div className="stat-value">{status?.target?.service_external_id || redis?.external_id || "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Container</div><div className="stat-value" style={{ fontSize: "0.9rem" }}>{status?.target?.container_name || redis?.container_name || "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Freshness gate</div><div className="stat-value">{status ? `${status.freshness_seconds}s` : "—"}</div></div>
      </div>

      <GlassCard style={{ padding: "1.25rem" }}>
        <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
          <h2>Run correlation</h2>
          <span>exact marker required</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="input" style={{ flex: 1 }} placeholder="Acceptance run marker, e.g. OBS-RUN-..." value={marker} onChange={(event) => p.setObservabilityMarker(event.target.value)} />
          <button className="btn btn-primary" disabled={!redis || !marker.trim() || p.observabilityLoading} onClick={() => refreshObservabilityStackStatus(redis?.id, marker)}>Correlate marker</button>
        </div>
        {p.observabilityError ? <p style={{ color: "var(--err)" }}>{p.observabilityError}</p> : null}
      </GlassCard>

      <GlassCard style={{ padding: "1.25rem" }}>
        <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
          <h2>Direct evidence</h2>
          <span>{status?.generated_at ? new Date(status.generated_at).toLocaleString() : "not probed"}</span>
        </div>
        {status ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "0.85rem" }}>
            {signalEntries.map(([name, signal]) => (
              <article key={name} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "0.9rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{name}</strong>
                  <span className={`pill ${stateClass(signal.state)}`}>{signal.state}</span>
                </div>
                <div style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--ink-3)" }}>Source: <code>{signal.source}</code></div>
                <div style={{ marginTop: 4, fontSize: "0.78rem", color: "var(--ink-3)" }}>Evidence: {signal.evidence_at ? new Date(signal.evidence_at).toLocaleString() : "none"}{signal.age_seconds != null ? ` (${Math.round(signal.age_seconds)}s old)` : ""}</div>
                {signal.error ? <p style={{ color: "var(--err)", fontSize: "0.8rem" }}>{signal.error}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <p style={{ color: "var(--ink-4)" }}>Select Redis and run the direct probes. HTTP success or empty data is never shown as healthy.</p>
        )}
        <div className="actions" style={{ marginTop: 14 }}>
          {[["monitoring", "Monitoring"], ["performance", "Performance"], ["diagnostics", "Diagnostics"], ["config", "Config"], ["clusters", "Clusters"]].map(([view, label]) => <button key={view} className="btn btn-secondary btn-sm" onClick={() => p.setActiveView(view)}>{label}</button>)}
        </div>
        <p style={{ marginTop: 14, color: "var(--ink-4)", fontSize: "0.76rem" }}>Support-stack deployment is PlatformOps-native infrastructure and is excluded from cPlatform parity.</p>
      </GlassCard>
    </div>
  );

}
