// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { isSeedDemoName, renderMetricWindowPicker, renderSVGTimeSeriesChart } from "../components/charts";
import { treeNavigator } from "../components/TreeNavigator";

/** PerformanceView — Phase 1 extracted page JSX. */
export function PerformanceView() {
  const p = usePlatform() as any;
  const clusters = p.clusters;
  const loadNodeMetrics = p.loadNodeMetrics;
  const loadNodeMetricsData = p.loadNodeMetricsData;
  const loadServiceMetrics = p.loadServiceMetrics;
  const loadingMetrics = p.loadingMetrics;
  const metricsStatus = p.metricsStatus || "idle";
  const metricsError = p.metricsError;
  const nodeMetrics = p.nodeMetrics;
  const nodeMetricsWindow = p.nodeMetricsWindow;
  const nodes = p.nodes;
  const perfAutoRefresh = p.perfAutoRefresh;
  const perfProcessSort = p.perfProcessSort;
  const processMetrics = p.processMetrics;
  const selectedNode = p.selectedNode;
  const selectedService = p.selectedService;
  const serviceMetrics = p.serviceMetrics;
  const services = p.services;
  const setNodeMetricsWindow = p.setNodeMetricsWindow;
  const setPerfAutoRefresh = p.setPerfAutoRefresh;
  const setPerfProcessSort = p.setPerfProcessSort;
  const setSelectedNode = p.setSelectedNode;
  const setSelectedService = p.setSelectedService;
  const setServiceMetrics = p.setServiceMetrics;
  const setServiceMetricsWindow = p.setServiceMetricsWindow;


  const showNode = !!selectedNode && !isSeedDemoName(selectedNode.name);
  const showService = !!selectedService && services.some((s) => s.id === selectedService.id);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Performance</h1>
          <p className="sub">Prometheus metrics for nodes and services. Select from the hierarchy — empty when exporters have no data.</p>
        </div>
        <div className="actions">
          {renderMetricWindowPicker(nodeMetricsWindow, (w) => {
            setNodeMetricsWindow(w);
            setServiceMetricsWindow(w);
            if (selectedService) loadServiceMetrics(selectedService.id, w);
            else if (selectedNode) {
              loadNodeMetrics(selectedNode.id, w);
              loadNodeMetricsData(selectedNode.id);
            }
          })}
          <button
            type="button"
            className={`btn btn-sm ${perfAutoRefresh ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setPerfAutoRefresh((v) => !v)}
          >
            {perfAutoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            disabled={loadingMetrics}
            onClick={() => {
              if (selectedService) loadServiceMetrics(selectedService.id);
              if (selectedNode) {
                loadNodeMetrics(selectedNode.id);
                loadNodeMetricsData(selectedNode.id);
              }
            }}
          >
            {loadingMetrics ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {(() => {
        const opNodes = nodes.filter((n) => !isSeedDemoName(n.name));
        const online = opNodes.filter((n) => ["healthy", "online", "ready", "running"].includes((n.status || "").toLowerCase())).length;
        let gpu = 0;
        opNodes.forEach((n) => { try { const f = JSON.parse(n.facts_json || "{}"); if (f.gpu || f.gpu_model || f.gpu_exporter === "enabled") gpu += 1; } catch {} });
        return (
          <div className="stat-strip">
            <div className="stat-tile"><div className="stat-label">Clusters</div><div className="stat-value">{clusters.filter((c) => !isSeedDemoName(c.name)).length}</div></div>
            <div className="stat-tile"><div className="stat-label">Nodes</div><div className="stat-value">{opNodes.length}</div></div>
            <div className="stat-tile"><div className="stat-label">Online</div><div className="stat-value">{online}</div></div>
            <div className="stat-tile"><div className="stat-label">GPU nodes</div><div className="stat-value">{gpu}</div></div>
          </div>
        );
      })()}

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.25rem", minHeight: "560px" }}>
        <GlassCard style={{ padding: "1rem" }}>
          {treeNavigator(
            async (service) => {
              setSelectedService(service);
              const node = nodes.find((n) => n.id === service.node_id) || null;
              if (node) setSelectedNode(node);
              await loadServiceMetrics(service.id);
              if (node) {
                await loadNodeMetrics(node.id);
                await loadNodeMetricsData(node.id);
              }
            },
            selectedService?.id ?? null,
            {
              hideSeedDemo: true,
              activeNodeId: selectedNode?.id ?? null,
              onSelectNode: async (node) => {
                setSelectedNode(node);
                setSelectedService(null);
                setServiceMetrics(null);
                await loadNodeMetrics(node.id);
                await loadNodeMetricsData(node.id);
              },
            },
          )}
        </GlassCard>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {metricsStatus !== "idle" && (
            <GlassCard style={{ padding: "0.75rem 1rem", borderColor: metricsStatus === "available" ? "var(--line)" : "var(--err)" }}>
              <strong>{metricsStatus === "loading" ? "Loading measured telemetry…" : `Prometheus: ${metricsStatus}`}</strong>
              {metricsError ? <span style={{ marginLeft: 8, color: "var(--ink-4)" }}>{metricsError}</span> : null}
            </GlassCard>
          )}
          {!showNode && !showService && (
            <GlassCard style={{ padding: "2.5rem", textAlign: "center" }}>
              <h3 style={{ marginBottom: "0.5rem" }}>Select a node or service</h3>
              <p style={{ color: "var(--ink-4)" }}>Use the tree to inspect Prometheus utilization and process metrics.</p>
            </GlassCard>
          )}

          {showNode && (
            <GlassCard style={{ padding: "1.25rem" }}>
              <div className="panel-title" style={{ marginBottom: "1rem" }}>
                <h2>Node · {selectedNode!.name}</h2>
                <span>{selectedNode!.host}</span>
              </div>
              {nodeMetrics ? (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
                    <div><small style={{ color: "var(--ink-4)" }}>CPU</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.cpu_percent ?? "—"}{nodeMetrics?.cpu_percent != null ? "%" : ""}</div></div>
                    <div><small style={{ color: "var(--ink-4)" }}>Memory</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.memory_percent ?? "—"}{nodeMetrics?.memory_percent != null ? "%" : ""}</div></div>
                    <div><small style={{ color: "var(--ink-4)" }}>Disk</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.disk_percent ?? "—"}{nodeMetrics?.disk_percent != null ? "%" : ""}</div></div>
                    <div><small style={{ color: "var(--ink-4)" }}>Net Rx/Tx</small><div style={{ fontWeight: 700 }}>{nodeMetrics?.network_rx_mbps != null && nodeMetrics?.network_tx_mbps != null ? `${nodeMetrics.network_rx_mbps}/${nodeMetrics.network_tx_mbps} Mbps` : "—"}</div></div>
                  </div>
                  {nodeMetrics && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                      <div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>CPU</div>
                        {renderSVGTimeSeriesChart(nodeMetrics.cpu_series || [], { color: "#60a5fa", unit: "%" })}
                      </div>
                      <div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Memory</div>
                        {renderSVGTimeSeriesChart(nodeMetrics.memory_series || [], { color: "#a78bfa", unit: "%" })}
                      </div>
                      <div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Disk</div>
                        {renderSVGTimeSeriesChart(nodeMetrics.disk_series || [], { color: "#34d399", unit: "%" })}
                      </div>
                    </div>
                  )}
                  <div style={{ marginTop: "1rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <h4 style={{ margin: 0 }}>Top processes</h4>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button type="button" className={`btn btn-xs ${perfProcessSort === "cpu" ? "btn-primary" : "btn-secondary"}`} onClick={() => setPerfProcessSort("cpu")}>Sort CPU</button>
                        <button type="button" className={`btn btn-xs ${perfProcessSort === "memory" ? "btn-primary" : "btn-secondary"}`} onClick={() => setPerfProcessSort("memory")}>Sort Memory</button>
                      </div>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--ink-4)", marginBottom: 6 }}>
                      Exporters: node_exporter · processes (Prom)
                    </div>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                      <thead>
                        <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                          <th style={{ padding: "0.35rem 0" }}>Process</th>
                          <th style={{ textAlign: "right" }}>CPU</th>
                          <th style={{ textAlign: "right" }}>Mem</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...processMetrics].sort((a, b) => {
                          if (perfProcessSort === "memory") return (b.memory != null ? parseFloat(b.memory) : -Infinity) - (a.memory != null ? parseFloat(a.memory) : -Infinity);
                          return (b.cpu != null ? parseFloat(b.cpu) : -Infinity) - (a.cpu != null ? parseFloat(a.cpu) : -Infinity);
                        }).slice(0, 12).map((p, i) => (
                          <tr key={`${p.name}-${i}`} style={{ borderTop: "1px solid var(--line-2)" }}>
                            <td style={{ padding: "0.35rem 0" }}><code>{p.name}</code></td>
                            <td style={{ textAlign: "right" }}>{p.cpu != null ? parseFloat(p.cpu).toFixed(3) : "—"}</td>
                            <td style={{ textAlign: "right" }}>{p.memory != null ? parseFloat(p.memory).toFixed(1) : "—"}</td>
                          </tr>
                        ))}
                        {processMetrics.length === 0 && (
                          <tr><td colSpan={3} style={{ color: "var(--ink-4)", padding: "0.75rem 0" }}>No process metrics from exporter.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  
                  {(nodeMetrics?.mounted_volumes || []).length > 0 && (
                    <div style={{ marginTop: "1rem" }}>
                      <h4 style={{ marginBottom: "0.5rem" }}>Mounted volumes</h4>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                        <thead>
                          <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                            <th style={{ padding: "0.35rem 0" }}>Mount</th>
                            <th>FS</th>
                            <th>Used</th>
                            <th>Total</th>
                            <th>Usage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {nodeMetrics!.mounted_volumes!.map((v) => (
                            <tr key={v.mount} style={{ borderTop: "1px solid var(--line-2)" }}>
                              <td style={{ padding: "0.35rem 0" }}><code>{v.mount}</code></td>
                              <td>{v.fstype}</td>
                              <td>{v.used_gb} GB</td>
                              <td>{v.total_gb} GB</td>
                              <td>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 4 }}>
                                    <div style={{ width: `${Math.min(100, v.usage_pct)}%`, height: "100%", background: v.usage_pct > 85 ? "var(--err)" : "var(--ok)", borderRadius: 4 }} />
                                  </div>
                                  <span>{v.usage_pct}%</span>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                </>
              ) : (
                <p style={{ color: "var(--ink-4)" }}>No Prometheus metrics for this node yet.</p>
              )}
            </GlassCard>
          )}

          {showService && serviceMetrics && (
            <GlassCard style={{ padding: "1.25rem" }}>
              <div className="panel-title" style={{ marginBottom: "1rem" }}>
                <h2>Service · {serviceMetrics.service_name}</h2>
                <span>{serviceMetrics.service_key}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
                <div><small style={{ color: "var(--ink-4)" }}>CPU</small><div style={{ fontWeight: 700 }}>{serviceMetrics.cpu_percent ?? "—"}{serviceMetrics.cpu_percent != null ? "%" : ""}</div></div>
                <div><small style={{ color: "var(--ink-4)" }}>Memory</small><div style={{ fontWeight: 700 }}>{serviceMetrics.memory_mb ?? "—"}{serviceMetrics.memory_mb != null ? " MB" : ""}</div></div>
                <div><small style={{ color: "var(--ink-4)" }}>Restarts</small><div style={{ fontWeight: 700 }}>{serviceMetrics.restart_count ?? "—"}</div></div>
                <div><small style={{ color: "var(--ink-4)" }}>Queue</small><div style={{ fontWeight: 700 }}>{serviceMetrics.queue_depth ?? "—"}</div></div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>CPU</div>
                  {renderSVGTimeSeriesChart(serviceMetrics.cpu_series || [], { color: "#fbbf24", unit: "%" })}
                </div>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Errors / min</div>
                  {renderSVGTimeSeriesChart(serviceMetrics.error_rate_series || [], { color: "#f87171", unit: "" })}
                </div>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>Queue depth</div>
                  {renderSVGTimeSeriesChart(serviceMetrics.queue_depth_series || [], { color: "#34d399", unit: "" })}
                </div>
              </div>

              {serviceMetrics.db_metrics && (
                <div style={{ marginTop: "1rem" }}>
                  <h4 style={{ marginBottom: "0.5rem" }}>Database metrics</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", fontSize: "0.85rem" }}>
                    {Object.entries(serviceMetrics.db_metrics).map(([k, v]) => (
                      <div key={k} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8 }}>
                        <div style={{ color: "var(--ink-4)" }}>{k}</div>
                        <strong>{String(v)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {serviceMetrics.broker_metrics && (
                <div style={{ marginTop: "1rem" }}>
                  <h4 style={{ marginBottom: "0.5rem" }}>Broker metrics</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", fontSize: "0.85rem" }}>
                    {Object.entries(serviceMetrics.broker_metrics).map(([k, v]) => (
                      <div key={k} style={{ padding: "0.5rem", border: "1px solid var(--line-2)", borderRadius: 8 }}>
                        <div style={{ color: "var(--ink-4)" }}>{k}</div>
                        <strong>{String(v)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(serviceMetrics.custom_charts || []).map((chart) => (
                <div key={chart.title} style={{ marginTop: "1rem" }}>
                  <h4>{chart.title}{chart.unit ? ` (${chart.unit})` : ""}</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
                    {(chart.series || []).map((s) => (
                      <div key={s.name}>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-4)", marginBottom: 4 }}>{s.name}</div>
                        {renderSVGTimeSeriesChart(s.points || [], { color: "#38bdf8", unit: chart.unit || "", height: 72 })}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

            </GlassCard>
          )}
          {showService && !serviceMetrics && (
            <GlassCard style={{ padding: "1.25rem" }}>
              <p style={{ color: "var(--ink-4)" }}>No service metrics for {selectedService?.name}. Prometheus may be unreachable or exporters missing.</p>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );

}
