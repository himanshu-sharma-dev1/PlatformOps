// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { isSeedDemoName } from "../components/charts";
import { GlitchTipWorkspace } from "./GlitchTipWorkspace";
import { treeNavigator } from "../components/TreeNavigator";

/** MonitoringView — Phase 1 extracted page JSX. */
export function MonitoringView() {
  const p = usePlatform() as any;
  const clusters = p.clusters;
  const gtAutoRefresh = p.gtAutoRefresh;
  const gtSelectedServiceId = p.gtSelectedServiceId;
  const gtWindow = p.gtWindow;
  const loadGlitchTipDataForService = p.loadGlitchTipDataForService;
  const loadGlitchTipIntegrationStatus = p.loadGlitchTipIntegrationStatus;
  const nodes = p.nodes;
  const refresh = p.refresh;
  const renderGlitchTipWorkspace = p.renderGlitchTipWorkspace;
  const renderTreeNavigator = p.renderTreeNavigator;
  const selectedService = p.selectedService;
  const services = p.services;
  const setGtAutoRefresh = p.setGtAutoRefresh;
  const setGtSelectedServiceId = p.setGtSelectedServiceId;
  const setGtWindow = p.setGtWindow;
  const setSelectedService = p.setSelectedService;


  const opNodes = nodes.filter((n) => !isSeedDemoName(n.name));
  const online = opNodes.filter((n) => ["healthy", "online", "ready", "running"].includes((n.status || "").toLowerCase())).length;
  let gpuCount = 0;
  opNodes.forEach((n) => {
    try {
      const f = JSON.parse(n.facts_json || "{}");
      if (f.gpu || f.gpu_model || f.gpu_exporter === "enabled" || f.gpu_available) gpuCount += 1;
    } catch { /* ignore */ }
  });
  const appServices = services.filter((s) => s.kind !== "infrastructure");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Monitoring</h1>
          <p className="sub">GlitchTip issues, uptime, APM transactions, and SDK keys. Select an application service from the tree.</p>
        </div>
        <div className="actions" style={{ flexWrap: "wrap" }}>
          {(["24h", "7d"] as const).map((w) => (
            <button key={w} type="button" className={`btn btn-sm ${gtWindow === w ? "btn-primary" : "btn-secondary"}`} onClick={() => {
              setGtWindow(w);
              const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
              if (svc) loadGlitchTipDataForService(svc.name, w);
            }}>{w === "24h" ? "Last 24h" : "Last 7d"}</button>
          ))}
          <button type="button" className={`btn btn-sm ${gtAutoRefresh ? "btn-primary" : "btn-secondary"}`} onClick={() => setGtAutoRefresh((v) => !v)}>
            {gtAutoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          </button>
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => {
            loadGlitchTipIntegrationStatus();
            const svc = services.find((s) => s.id === gtSelectedServiceId) || selectedService;
            if (svc) loadGlitchTipDataForService(svc.name, gtWindow);
          }}>Refresh now</button>
        </div>
      </div>

      <div className="stat-strip">
        <div className="stat-tile"><div className="stat-label">Clusters</div><div className="stat-value">{clusters.filter((c) => !isSeedDemoName(c.name)).length}</div></div>
        <div className="stat-tile"><div className="stat-label">Nodes</div><div className="stat-value">{opNodes.length}</div></div>
        <div className="stat-tile"><div className="stat-label">Online</div><div className="stat-value">{online}</div></div>
        <div className="stat-tile"><div className="stat-label">GPU nodes</div><div className="stat-value">{gpuCount}</div></div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem", minHeight: "560px" }}>
        <GlassCard style={{ padding: "1rem" }}>
          {treeNavigator(
            async (service) => {
              setSelectedService(service);
              setGtSelectedServiceId(service.id);
              await loadGlitchTipDataForService(service.name, gtWindow);
              loadGlitchTipIntegrationStatus();
            },
            gtSelectedServiceId ?? selectedService?.id ?? null,
            { appServicesOnly: true, hideSeedDemo: true },
          )}
        </GlassCard>
        <div>
          {gtSelectedServiceId || selectedService ? (
            <GlitchTipWorkspace />
          ) : (
            <GlassCard style={{ padding: "2.5rem", textAlign: "center" }}>
              <h3 style={{ marginBottom: "0.5rem" }}>Select a service</h3>
              <p style={{ color: "var(--ink-4)" }}>
                {appServices.length === 0 ? "No application services registered." : "Choose an application service from the hierarchy."}
              </p>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );

}
