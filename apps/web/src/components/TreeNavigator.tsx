// @ts-nocheck
import React from "react";
import { usePlatform } from "../platform/usePlatform";
import { isSeedDemoName } from "./charts";

/**
 * Imperative tree navigator (legacy call shape).
 * treeNavigator(onSelectService, activeServiceId?, options?)
 */
export function treeNavigator(onSelectService, activeServiceId = null, options = {}) {
  const p = usePlatform() as any;
  const clusters = p.clusters;
  const nodes = p.nodes;
  const selectCluster = p.selectCluster;
  const selectNode = p.selectNode;
  const services = p.services;
  const setTreeSearchQuery = p.setTreeSearchQuery;
  const treeSearchQuery = p.treeSearchQuery;

  const hideSeed = options?.hideSeedDemo !== false;
  const realClusters = clusters.filter((c) => !hideSeed || !isSeedDemoName(c.name));
  const q = treeSearchQuery.toLowerCase();

  return (
    <div className="tree-navigator" style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "100%", overflowY: "auto", paddingRight: "0.5rem" }}>
      <div className="tree-search">
        <input
          type="text"
          className="input"
          placeholder="Filter hierarchy…"
          value={treeSearchQuery}
          onChange={(e) => setTreeSearchQuery(e.target.value)}
          style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}
        />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {realClusters.map((cluster) => {
          const clusterNodes = nodes.filter(
            (n) => n.cluster_id === cluster.id && (!hideSeed || !isSeedDemoName(n.name)),
          );
          const matchesSearch = !q || cluster.name.toLowerCase().includes(q);
          if (clusterNodes.length === 0 && !matchesSearch) return null;
          return (
            <div key={`tree-cluster-${cluster.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.25rem", padding: "0.25rem", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.04)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.4rem 0.6rem", cursor: "pointer" }} onClick={() => selectCluster(cluster)}>
                <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>{cluster.name}</span>
                <span className="pill" style={{ fontSize: "0.7rem", scale: "0.9" }}>{cluster.environment}</span>
              </div>
              <div style={{ paddingLeft: "0.75rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                {clusterNodes.map((node) => {
                  let nodeServices = services.filter((s) => s.node_id === node.id);
                  if (options?.appServicesOnly) {
                    nodeServices = nodeServices.filter((s) => s.kind !== "infrastructure");
                  }
                  const nodeMatches = !q || node.name.toLowerCase().includes(q) || matchesSearch;
                  if (nodeServices.length === 0 && !nodeMatches && !options?.onSelectNode) return null;
                  const nodeActive = options?.activeNodeId === node.id;
                  return (
                    <div key={`tree-node-${node.id}`} style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          padding: "0.3rem 0.5rem",
                          cursor: "pointer",
                          borderRadius: "6px",
                          background: nodeActive ? "rgba(59,130,246,0.12)" : "transparent",
                          border: nodeActive ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
                        }}
                        onClick={() => {
                          if (options?.onSelectNode) options.onSelectNode(node);
                          else selectNode(node);
                        }}
                      >
                        <span style={{ fontSize: "0.8rem", color: nodeActive ? "var(--ink)" : "var(--ink-2)" }}>{node.name}</span>
                        <span className={`status-dot ${node.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }} />
                      </div>
                      <div style={{ paddingLeft: "0.85rem", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                        {nodeServices.map((service) => {
                          if (q && !service.name.toLowerCase().includes(q) && !nodeMatches) return null;
                          const isActive = activeServiceId === service.id;
                          return (
                            <div
                              key={`tree-service-${service.id}`}
                              className={`tree-item service-item ${isActive ? "active" : ""}`}
                              onClick={() => onSelectService(service)}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                padding: "0.25rem 0.4rem",
                                cursor: "pointer",
                                borderRadius: "4px",
                                background: isActive ? "rgba(59,130,246,0.15)" : "transparent",
                                border: isActive ? "1px solid rgba(59,130,246,0.3)" : "none",
                              }}
                            >
                              <span style={{ fontSize: "0.75rem", color: isActive ? "var(--ink)" : "var(--ink-3)" }}>{service.name}</span>
                              <span className={`status-dot ${service.status}`} style={{ width: "6px", height: "6px", borderRadius: "50%", alignSelf: "center" }} />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {realClusters.length === 0 && (
          <p style={{ color: "var(--ink-4)", fontSize: "0.85rem", padding: "0.5rem" }}>No operational clusters registered.</p>
        )}
      </div>
    </div>
  );

}

export function TreeNavigator({ onSelectService, activeServiceId = null, options = {} }) {
  return treeNavigator(onSelectService, activeServiceId, options);
}
