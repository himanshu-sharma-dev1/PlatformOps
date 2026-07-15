// @ts-nocheck — platform controller is loosely typed until full DTO extraction
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { isSeedDemoName } from "../components/charts";

/**
 * Clusters page — list + cluster detail (nodes, services, jobs, events).
 * JSX lives here; data/actions come from PlatformProvider via usePlatform().
 */
export function ClustersView() {
  const p = usePlatform() as any;
  const selectedCluster = p.selectedCluster as any;
  const setSelectedCluster = p.setSelectedCluster as (...a: any[]) => void;
  const selectedNode = p.selectedNode as any;
  const setSelectedService = p.setSelectedService as (...a: any[]) => void;
  const setActiveView = p.setActiveView as (...a: any[]) => void;
  const setDiagTab = p.setDiagTab as (...a: any[]) => void;
  const clusters = (p.clusters || []) as any[];
  const nodes = (p.nodes || []) as any[];
  const services = (p.services || []) as any[];
  const catalog = (p.catalog || []) as any[];
  const nodeSearchQuery = (p.nodeSearchQuery || "") as string;
  const setNodeSearchQuery = p.setNodeSearchQuery as (...a: any[]) => void;
  const openClusterCreate = p.openClusterCreate as (...a: any[]) => void;
  const openClusterEdit = p.openClusterEdit as (...a: any[]) => void;
  const selectCluster = p.selectCluster as (...a: any[]) => void;
  const selectNode = p.selectNode as (...a: any[]) => void;
  const openNodeCreate = p.openNodeCreate as (...a: any[]) => void;
  const openNodeEdit = p.openNodeEdit as (...a: any[]) => void;
  const openDeploymentModal = p.openDeploymentModal as (...a: any[]) => void;
  const requestDelete = p.requestDelete as (...a: any[]) => void;
  const validateNode = p.validateNode as (...a: any[]) => void;
  const discoverNodeInfra = p.discoverNodeInfra as (...a: any[]) => void;
  const setStepperDrawerVisible = p.setStepperDrawerVisible as (...a: any[]) => void;
  const setCatalogDrawerVisible = p.setCatalogDrawerVisible as (...a: any[]) => void;
  const loadDiagnostics = p.loadDiagnostics as (...a: any[]) => void;
  const loadConfig = p.loadConfig as (...a: any[]) => void;
  const nodeOnboarding = p.nodeOnboarding as any;
  const loadNodeOnboarding = p.loadNodeOnboarding as (...a: any[]) => void;
  const nodeConnection = p.nodeConnection as any;
  const loadNodeConnection = p.loadNodeConnection as (...a: any[]) => void;
  const nodeMetrics = p.nodeMetrics as any;
  const nodeJobHistory = p.nodeJobHistory as any;
  const events = (p.events || []) as any[];
  const observabilityPipeline = p.observabilityPipeline as any;
  const servicePortsLabel = p.servicePortsLabel as (...a: any[]) => string;
  const formatLocalTimestamp = p.formatLocalTimestamp as (...a: any[]) => string;
  const serviceLiveById = (p.serviceLiveById || {}) as Record<string, any>;
  const nodeLiveStatus = p.nodeLiveStatus as any;
  const refreshNodeLiveStatus = p.refreshNodeLiveStatus as (...a: any[]) => void;
  const cleanupNodeInventory = p.cleanupNodeInventory as (...a: any[]) => Promise<any>;
  const loadScopedEvents = p.loadScopedEvents as (...a: any[]) => Promise<any[]>;
  const loadServiceLiveStatus = p.loadServiceLiveStatus as (...a: any[]) => Promise<any>;
  const updateServiceExpose = p.updateServiceExpose as (...a: any[]) => Promise<any>;
  const runPatchObservability = p.runPatchObservability as (...a: any[]) => Promise<any>;
  const [detailTab, setDetailTab] = React.useState("overview" as string);
  const [cleanupBusy, setCleanupBusy] = React.useState(false);
  const [nodeEvents, setNodeEvents] = React.useState([] as any[]);
  const [nodeEventsBusy, setNodeEventsBusy] = React.useState(false);
  const [serviceDrawer, setServiceDrawer] = React.useState({
    visible: false,
    service: null as any,
    tab: "overview" as string,
    events: [] as any[],
    live: null as any,
    expose: false,
    hostPort: "" as string | number,
    busy: false,
  });

  const openServiceDrawer = React.useCallback(async (service: any, tab = "overview") => {
    if (!service) return;
    setSelectedService(service);
    let expose = Boolean(service.expose_service);
    let hostPort: string | number = service.host_port ?? "";
    try {
      const cfg = typeof service.config_json === "string" ? JSON.parse(service.config_json || "{}") : (service.config_json || {});
      if (cfg && typeof cfg === "object") {
        if (cfg.expose_service != null) expose = Boolean(cfg.expose_service);
        if (cfg.host_port != null) hostPort = cfg.host_port;
      }
    } catch (_e) { /* ignore */ }
    setServiceDrawer({
      visible: true,
      service,
      tab,
      events: [],
      live: serviceLiveById[service.id] || null,
      expose,
      hostPort,
      busy: true,
    });
    const [evts, live] = await Promise.all([
      loadScopedEvents?.({ service_id: service.id, limit: 40 }) || Promise.resolve([]),
      loadServiceLiveStatus?.(service.id) || Promise.resolve(null),
    ]);
    setServiceDrawer((prev) => ({
      ...prev,
      events: evts || [],
      live: live || prev.live,
      busy: false,
      service: service,
    }));
  }, [loadScopedEvents, loadServiceLiveStatus, serviceLiveById, setSelectedService]);

  if (!selectedCluster) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="page-head">
            <div className="titles">
              <h1>Clusters</h1>
              <p className="sub">Inventory, nodes, and catalog deploys — real hosts only, no demo clutter.</p>
            </div>
            <div className="actions">
              <button className="btn btn-primary" onClick={openClusterCreate}>
                <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
                Create Cluster
              </button>
            </div>
          </div>

          {(() => {
            const opClusters = clusters.filter((c) => !isSeedDemoName(c.name));
            const opNodes = nodes.filter((n) => !isSeedDemoName(n.name));
            const opNodeIds = new Set(opNodes.map((n) => n.id));
            const opServices = services.filter((s) => opNodeIds.has(s.node_id));
            return (
          <div className="stat-strip">
            <div className="stat-tile"><div className="stat-label">Clusters</div><div className="stat-value">{opClusters.length}</div></div>
            <div className="stat-tile"><div className="stat-label">Nodes</div><div className="stat-value">{opNodes.length}</div></div>
            <div className="stat-tile"><div className="stat-label">Services</div><div className="stat-value">{opServices.length}</div></div>
            <div className="stat-tile"><div className="stat-label">Running</div><div className="stat-value">{opServices.filter((s) => ["running", "healthy"].includes((s.status || "").toLowerCase())).length}</div></div>
          </div>
            );
          })()}

          {clusters.filter((c) => !isSeedDemoName(c.name)).length === 0 && (
            <GlassCard style={{ padding: "2.5rem", textAlign: "center" }}>
              <h3 style={{ marginBottom: "0.5rem" }}>No clusters yet</h3>
              <p style={{ color: "var(--ink-3)", marginBottom: "1.25rem" }}>Create a cluster to onboard nodes and deploy services.</p>
              <button className="btn btn-primary" onClick={openClusterCreate}>Create Cluster</button>
            </GlassCard>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1.25rem" }}>
            {clusters.filter((c) => !isSeedDemoName(c.name)).map((cluster) => {
              const clusterNodes = nodes.filter((n) => n.cluster_id === cluster.id && !isSeedDemoName(n.name));
              const clusterServices = services.filter((s) => clusterNodes.some((n) => n.id === s.node_id));
              const running = clusterServices.filter((s) => ["running", "healthy"].includes((s.status || "").toLowerCase())).length;
              const bad = clusterServices.some((s) => ["error", "failed", "unhealthy"].includes((s.status || "").toLowerCase()))
                || clusterNodes.some((n) => ["error", "unreachable", "failed"].includes((n.status || "").toLowerCase()));
              return (
                <GlassCard key={cluster.id} className="card" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem", cursor: "pointer" }} onClick={() => selectCluster(cluster)}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <span className="pill" style={{ background: "var(--navy-50)", color: "var(--navy-500)", fontSize: "0.7rem", fontWeight: 600 }}>{cluster.environment.toUpperCase()}</span>
                      <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginTop: "0.45rem", color: "var(--ink)" }}>{cluster.name}</h3>
                      <p style={{ fontSize: "0.8rem", color: "var(--ink-4)", fontFamily: "var(--mono)", marginTop: 2 }}>{cluster.region}</p>
                    </div>
                    {clusterNodes.length === 0 ? <span className="pill pill-muted">Empty</span>
                      : bad ? <span className="pill pill-error">Degraded</span>
                      : <span className="pill pill-ok">Active</span>}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)", padding: "0.85rem 0" }}>
                    <div style={{ textAlign: "center" }}><div style={{ fontWeight: 600 }}>{clusterNodes.length}</div><div style={{ fontSize: "0.72rem", color: "var(--ink-4)" }}>Nodes</div></div>
                    <div style={{ textAlign: "center" }}><div style={{ fontWeight: 600 }}>{clusterServices.length}</div><div style={{ fontSize: "0.72rem", color: "var(--ink-4)" }}>Services</div></div>
                    <div style={{ textAlign: "center" }}><div style={{ fontWeight: 600 }}>{running}</div><div style={{ fontSize: "0.72rem", color: "var(--ink-4)" }}>Running</div></div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                    <button className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); openClusterEdit(cluster); }}>Settings</button>
                    <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); selectCluster(cluster); }}>Open cluster</button>
                  </div>
                </GlassCard>
              );
            })}
          </div>

          <GlassCard style={{ padding: "1.25rem" }}>
            <div className="panel-title" style={{ marginBottom: "0.85rem" }}>
              <h2>Service catalog</h2>
              <button className="btn btn-secondary btn-sm" onClick={() => setCatalogDrawerVisible(true)}>Browse catalog</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.75rem" }}>
              {catalog.slice(0, 6).map((card) => (
                <article key={card.service_key} style={{ padding: "0.85rem", border: "1px solid var(--line)", borderRadius: 10 }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--navy-500)", textTransform: "uppercase", fontWeight: 600 }}>{card.kind}</div>
                  <h4 style={{ marginTop: 4 }}>{card.name}</h4>
                  <p style={{ fontSize: "0.8rem", color: "var(--ink-3)", marginTop: 4 }}>{card.description || card.image}</p>
                </article>
              ))}
            </div>
          </GlassCard>
        </div>
      );
    }

    const clusterNodes = nodes.filter((n) => n.cluster_id === selectedCluster.id);
    const clusterServices = services.filter((s) => clusterNodes.some((n) => n.id === s.node_id));
    const activeNode = selectedNode && clusterNodes.some((n) => n.id === selectedNode.id) ? selectedNode : null;
    const pipelineNodes = (observabilityPipeline?.nodes ?? []).filter((n) => clusterNodes.some((cn) => cn.id === n.node_id));
    const pipelineHealthy = pipelineNodes.filter((n) => n.pipeline_ready).length;
    const nodeServices = activeNode ? services.filter((s) => s.node_id === activeNode.id) : [];
    const runningCount = clusterServices.filter((s) => ["running", "healthy"].includes((s.status || "").toLowerCase())).length;
    const unhealthyCount = clusterServices.filter((s) => ["error", "failed", "unhealthy"].includes((s.status || "").toLowerCase())).length;

    let facts: any = {};
    if (activeNode) {
      try { facts = JSON.parse(activeNode.facts_json || "{}"); } catch { facts = {}; }
    }
    const vcpu = facts.vcpus ?? facts.vcpu ?? facts.cpu_cores ?? "—";
    const mem = facts.memory_gb ?? facts.memory ?? "—";
    const storage = facts.storage_gb ?? facts.disk_gb ?? "—";
    const gpu = facts.gpu_model ?? facts.gpu ?? (facts.gpu_exporter === "enabled" ? "GPU enabled" : facts.gpu_available ? "GPU" : "—");
    const os = facts.os ?? facts.distro ?? "—";

    return (
      <>
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="page-head">
          <div className="titles">
            <h1>{selectedCluster.name}</h1>
            <p className="sub">{selectedCluster.region} · {selectedCluster.environment}</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary" onClick={() => setSelectedCluster(null)}>All clusters</button>
            <button className="btn btn-secondary" onClick={() => openClusterEdit(selectedCluster)}>Cluster settings</button>
            <button className="btn btn-secondary" onClick={() => requestDelete("cluster", selectedCluster.id, selectedCluster.name)}>Delete cluster</button>
            <button className="btn btn-primary" onClick={() => { openNodeCreate(); setStepperDrawerVisible(true); }}>Provision node</button>
          </div>
        </div>

        <div className="cluster-band">
          <div className="identity">
            <div className="badge-cloud">{(selectedCluster.environment || "cluster").slice(0, 3).toUpperCase()}</div>
            <div className="id-text">
              <div className="name">{selectedCluster.name}</div>
              <div className="meta">{selectedCluster.region} · {selectedCluster.environment}</div>
            </div>
          </div>
          <div className="stats">
            <div className="stat"><div className="v">{clusterNodes.length}</div><div className="l">Nodes</div></div>
            <div className="stat"><div className="v">{clusterServices.length}</div><div className="l">Services</div></div>
            <div className="stat"><div className="v">{runningCount}</div><div className="l">Running</div></div>
            <div className="stat"><div className="v">{unhealthyCount}</div><div className="l">Unhealthy</div></div>
          </div>
          <div>
            {clusterNodes.length === 0 ? <span className="pill pill-muted">No nodes</span>
              : unhealthyCount > 0 ? <span className="pill pill-error">Degraded</span>
              : <span className="pill pill-ok">Active</span>}
          </div>
        </div>

        <GlassCard style={{ padding: "0.85rem 1.1rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: "0.7rem", letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--ink-4)", fontWeight: 600 }}>Observability</div>
            <div style={{ marginTop: 4, color: "var(--ink-2)", fontSize: "0.9rem" }}>
              {clusterNodes.length === 0
                ? "No nodes in this cluster"
                : observabilityPipeline
                  ? `${pipelineHealthy}/${pipelineNodes.length} pipeline-ready on this cluster`
                  : "Loading pipeline…"}
            </div>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setActiveView("observability")}>Manage stack</button>
        </GlassCard>

        <div className="cluster-split">
          <div className="node-list-wrap">
            <div className="node-list-head">
              <h3>Nodes</h3>
              <span style={{ fontFamily: "var(--mono)", fontSize: "10px", color: "var(--ink-4)" }}>{clusterNodes.length} total</span>
            </div>
            <div className="node-search">
              <svg className="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
              <input type="text" placeholder="Search nodes…" value={nodeSearchQuery} onChange={(e) => setNodeSearchQuery(e.target.value)} />
            </div>
            <div className="node-list">
              {clusterNodes
                .filter((n) => n.name.toLowerCase().includes(nodeSearchQuery.toLowerCase()))
                .map((node) => {
                  const isSelected = activeNode?.id === node.id;
                  const nodeSvcs = services.filter((s) => s.node_id === node.id && (s.status || "") !== "deleted");
                  const svcCount = nodeSvcs.length;
                  const liveRunning = isSelected && nodeLiveStatus?.node_id === node.id
                    ? nodeLiveStatus.running_count
                    : nodeSvcs.filter((s) => ["running", "healthy"].includes((s.status || "").toLowerCase())).length;
                  const nstat = ["healthy", "running"].includes((node.status || "").toLowerCase())
                    ? "ready"
                    : (node.status || "").toLowerCase() === "unreachable"
                      ? "unreachable"
                      : (node.status || "unknown");
                  return (
                    <div key={node.id} className={`node-row ${isSelected ? "active" : ""}`} onClick={() => { setDetailTab("overview"); setNodeEvents([]); selectNode(node); }}>
                      <div className={`nstat ${nstat}`}></div>
                      <div className="info">
                        <div className="nm">{node.name}</div>
                        <div className="sub"><span className="cloud">{node.environment.toUpperCase()}</span>{node.host}</div>
                      </div>
                      <div className="svc-count" title={`${liveRunning} running / ${svcCount} total`}>
                        {liveRunning}/{svcCount}
                      </div>
                    </div>
                  );
                })}
              {clusterNodes.length === 0 && (
                <div style={{ padding: "1.5rem", color: "var(--ink-4)", fontSize: "0.85rem" }}>No nodes. Provision a node to get started.</div>
              )}
            </div>
            <div className="node-list-foot">
              <button className="btn btn-secondary btn-sm" onClick={() => { openNodeCreate(); setStepperDrawerVisible(true); }}>
                <svg className="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
                Provision node
              </button>
            </div>
          </div>

          {activeNode ? (
            <div className="node-detail">
              <div className="node-spec-header">
                <div className="top-row">
                  <div>
                    <div className="title">{activeNode.name}</div>
                    <div className="subtitle">
                      <span className="cloud-tag">{activeNode.environment.toUpperCase()}</span>
                      <span>IP: {activeNode.host} · Net: <code>{activeNode.docker_network}</code> · Volume: <code>{activeNode.volume_root}</code></span>
                    </div>
                  </div>
                  <div className="actions">
                    <button className="btn btn-secondary btn-sm" onClick={() => validateNode(activeNode.id)}>Validate</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => discoverNodeInfra(activeNode.id)}>Discover</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => loadNodeConnection?.(activeNode.id)}>Probe</button>
                    <button className="btn btn-secondary btn-sm" title="Live status via SSH docker inspect" onClick={() => refreshNodeLiveStatus?.(activeNode.id, { via: "ssh" })}>Live SSH</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => openNodeEdit(activeNode)}>Edit</button>
                    <button className="btn btn-danger btn-sm" onClick={() => requestDelete("node", activeNode.id, activeNode.name)}>Delete</button>
                  </div>
                </div>

                <div className="detail-tabs" style={{ display: "flex", gap: 6, marginTop: "0.85rem", flexWrap: "wrap" }}>
                  {["overview", "services", "events", "live", "jobs"].map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      className={`tab ${detailTab === tab ? "active" : ""}`}
                      style={{
                        border: "1px solid var(--line)",
                        borderRadius: 8,
                        padding: "0.3rem 0.7rem",
                        background: detailTab === tab ? "var(--navy-50, rgba(30,58,95,0.12))" : "transparent",
                        fontWeight: detailTab === tab ? 600 : 500,
                        fontSize: "0.8rem",
                        cursor: "pointer",
                        textTransform: "capitalize",
                      }}
                      onClick={async () => {
                        setDetailTab(tab);
                        if (tab === "live" || tab === "services") {
                          refreshNodeLiveStatus?.(activeNode.id);
                        }
                        if (tab === "events") {
                          setNodeEventsBusy(true);
                          try {
                            const evts = await loadScopedEvents?.({ node_id: activeNode.id, limit: 60 });
                            setNodeEvents(Array.isArray(evts) ? evts : []);
                          } catch (_e) {
                            setNodeEvents([]);
                          } finally {
                            setNodeEventsBusy(false);
                          }
                        }
                      }}
                    >
                      {tab === "live" ? "Live status" : tab}
                    </button>
                  ))}
                </div>

                {nodeConnection && nodeConnection.node_id === activeNode.id && (
                  <div className="connection-banner" style={{
                    marginTop: "0.75rem",
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "0.5rem 1rem",
                    alignItems: "center",
                    padding: "0.55rem 0.75rem",
                    borderRadius: 10,
                    border: "1px solid var(--line)",
                    background: "var(--bg-elevated, rgba(255,255,255,0.03))",
                    fontSize: "0.82rem",
                  }}>
                    <span className={`pill ${
                      ["validated", "ssh-ok"].includes(nodeConnection.connection_state)
                        ? "pill-ok"
                        : nodeConnection.connection_state === "unreachable"
                          ? "pill-error"
                          : "pill-warn"
                    }`}>
                      {nodeConnection.connection_state}
                    </span>
                    {nodeConnection.live_probe && (
                      <span style={{ color: "var(--ink-3)" }}>
                        probe: ssh={String(nodeConnection.live_probe.ssh_ok)} · docker={String(nodeConnection.live_probe.docker_ok)}
                      </span>
                    )}
                    {(nodeConnection.recommendations || []).slice(0, 1).map((r: string, i: number) => (
                      <span key={i} style={{ color: "var(--ink-4)" }}>{r}</span>
                    ))}
                  </div>
                )}

                <div className="spec-sheet">
                  <div className="spec-cell"><div className="l">vCPU</div><div className="v">{vcpu}{typeof vcpu === "number" ? <span className="unit"> cores</span> : null}</div></div>
                  <div className="spec-cell"><div className="l">Memory</div><div className="v">{mem}{typeof mem === "number" ? <span className="unit"> GB</span> : null}</div></div>
                  <div className="spec-cell"><div className="l">Storage</div><div className="v">{storage}{typeof storage === "number" ? <span className="unit"> GB</span> : null}</div></div>
                  <div className="spec-cell"><div className="l">GPU</div><div className="v">{String(gpu)}</div></div>
                  <div className="spec-cell"><div className="l">OS</div><div className="v">{String(os)}</div></div>
                  <div className="spec-cell"><div className="l">Status</div><div className="v" style={{ textTransform: "capitalize" }}>{activeNode.status || "—"}</div></div>
                </div>
              </div>

              {detailTab === "overview" && (
              <>
              {nodeOnboarding && (
                <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: 12, padding: "0.85rem 1rem", background: "var(--bg-elevated)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                    <div>
                      <strong style={{ fontSize: "0.9rem" }}>Onboarding readiness</strong>
                      <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", marginTop: 2 }}>
                        {nodeOnboarding.overall_status} · pass {nodeOnboarding.pass_count} · warn {nodeOnboarding.warn_count} · fail {nodeOnboarding.fail_count}
                      </div>
                    </div>
                    <button className="btn btn-secondary btn-sm" onClick={() => loadNodeOnboarding(activeNode.id)}>Refresh</button>
                  </div>
                  {nodeOnboarding.fail_count > 0 && (
                    <ul style={{ margin: "0.6rem 0 0 1rem", color: "var(--ink-3)", fontSize: "0.82rem" }}>
                      {nodeOnboarding.checks.filter((c) => c.status === "fail").slice(0, 3).map((c) => (
                        <li key={c.check_id}>{c.title}: {c.detail}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {nodeMetrics && typeof nodeMetrics.cpu_percent === "number" ? (
                <div className="utilization" style={{ marginTop: "1rem" }}>
                  <div className="util">
                    <div className="top"><span className="name">CPU</span><span className="val">{nodeMetrics.cpu_percent}%</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${Math.min(100, nodeMetrics.cpu_percent)}%` }} /></div>
                    <div className="sub">Prometheus</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Memory</span><span className="val">{nodeMetrics.memory_percent}%</span></div>
                    <div className="bar"><div className="fill warn" style={{ width: `${Math.min(100, nodeMetrics.memory_percent)}%` }} /></div>
                    <div className="sub">{nodeMetrics.memory_percent}% used</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Disk</span><span className="val">{nodeMetrics.disk_percent}%</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${Math.min(100, nodeMetrics.disk_percent)}%` }} /></div>
                    <div className="sub">Filesystem</div>
                  </div>
                  <div className="util">
                    <div className="top"><span className="name">Network</span><span className="val">{nodeMetrics.network_rx_mbps} Mbps</span></div>
                    <div className="bar"><div className="fill" style={{ width: `${Math.min(100, Number(nodeMetrics.network_rx_mbps) || 0)}%` }} /></div>
                    <div className="sub">↓ {nodeMetrics.network_rx_mbps} · ↑ {nodeMetrics.network_tx_mbps}</div>
                  </div>
                </div>
              ) : (
                <div style={{ marginTop: "1rem", padding: "0.85rem", border: "1px solid var(--line)", borderRadius: 12, color: "var(--ink-3)", fontSize: "0.85rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <span>No live utilization for this node.</span>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setActiveView("performance")}>Open Performance</button>
                </div>
              )}
              </>
              )}

              {(detailTab === "overview" || detailTab === "services") && (
              <div className="services-section" style={{ marginTop: "1rem" }}>
                <div className="services-head">
                  <h3>
                    Services{" "}
                    <span className="ct">
                      {nodeLiveStatus && nodeLiveStatus.node_id === activeNode.id
                        ? `${nodeLiveStatus.running_count} running (live${nodeLiveStatus.source ? ` · ${nodeLiveStatus.source}` : ""})`
                        : `${nodeServices.filter((s) => ["running", "healthy"].includes((s.status || "").toLowerCase())).length} running`}
                    </span>
                  </h3>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn btn-secondary btn-sm" onClick={() => refreshNodeLiveStatus?.(activeNode.id)}>Refresh live</button>
                    <button
                      className="btn btn-secondary btn-sm"
                      disabled={cleanupBusy}
                      onClick={async () => {
                        setCleanupBusy(true);
                        try {
                          const preview = await cleanupNodeInventory?.(activeNode.id, { dryRun: true, modes: ["all"] });
                          if (!preview) return;
                          const n = preview.candidate_count || 0;
                          if (n === 0) {
                            return;
                          }
                          if (window.confirm(`${preview.summary}\n\nRemove ${n} inventory row(s)? (containers are not stopped)`)) {
                            await cleanupNodeInventory?.(activeNode.id, { dryRun: false, modes: ["all"] });
                          }
                        } finally {
                          setCleanupBusy(false);
                        }
                      }}
                    >
                      Clean inventory
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => setCatalogDrawerVisible(true)}>Add service</button>
                  </div>
                </div>
                <div className="service-stack">
                  {nodeServices.map((service) => {
                    const live = serviceLiveById[service.id] || serviceLiveById[String(service.id)];
                    const displayStatus = (live?.overall_status || service.status || "unknown").toLowerCase();
                    const pillClass = ["healthy", "running"].includes(displayStatus)
                      ? "pill-ok"
                      : ["error", "failed", "unhealthy", "exited", "dead", "not_found"].includes(displayStatus)
                        ? "pill-error"
                        : "pill-warn";
                    return (
                    <div
                      key={service.id}
                      className={`svc-card ${displayStatus}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => openServiceDrawer(service, "overview")}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === "Enter") openServiceDrawer(service, "overview"); }}
                    >
                      <div className="svc-icon">{(service.name || service.service_key || "?")[0]}</div>
                      <div className="svc-info">
                        <div className="nm" style={{ fontWeight: 600 }}>
                          {service.name}
                          {service.external_id ? (
                            <span style={{ marginLeft: 8, fontFamily: "var(--mono)", fontSize: "0.72rem", color: "var(--ink-4)", fontWeight: 500 }}>
                              {service.external_id}
                            </span>
                          ) : null}
                        </div>
                        <div className="meta">
                          kind {service.kind}
                          {service.service_key ? <> · key <code>{service.service_key}</code></> : null}
                          {service.container_name ? <> · docker <code>{service.container_name}</code></> : null}
                          {" · "}image <code>{service.image || live?.image || "—"}</code>
                          {live?.restart_count != null ? <> · restarts {live.restart_count}</> : null}
                        </div>
                      </div>
                      <div className="svc-ports"><span className="port">{servicePortsLabel(service)}</span></div>
                      <div className="svc-status">
                        <span
                          className={`pill ${pillClass}`}
                          title={
                            live
                              ? `Live docker: ${live.overall_status}${live.error ? ` — ${live.error}` : ""}${live.cache_hit ? " (cache)" : ""}`
                              : `Inventory status: ${service.status || "unknown"}`
                          }
                        >
                          {displayStatus}
                          {live ? "" : " · inv"}
                        </span>
                      </div>
                      <div className="svc-acts" onClick={(e) => e.stopPropagation()}>
                        <button className="icon-btn" title="Overview / Events / Live" onClick={() => openServiceDrawer(service, "overview")}>
                          <svg className="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                        </button>
                        <button className="icon-btn" title="Logs" onClick={() => { setSelectedService(service); loadDiagnostics(service); setActiveView("diagnostics"); setDiagTab("tail"); }}>
                          <svg className="ic" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>
                        </button>
                        <button className="icon-btn" title="Config" onClick={() => { setSelectedService(service); loadConfig(service); setActiveView("config"); }}>
                          <svg className="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
                        </button>
                        <button className="icon-btn" title="Deploy" onClick={() => openDeploymentModal(service)}>
                          <svg className="ic" viewBox="0 0 24 24"><path d="M12 2v20M17 5l-5-5-5 5"/></svg>
                        </button>
                        <button className="icon-btn" title="GlitchTip / observability patch" onClick={() => runPatchObservability?.(service.id, service.name)}>
                          <svg className="ic" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                        </button>
                        <button className="icon-btn danger" title="Uninstall" onClick={() => requestDelete("service", service.id, service.name)}>
                          <svg className="ic" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m1 0v14a2 2 0 01-2 2H8a2 2 0 01-2-2V6h12z"/></svg>
                        </button>
                      </div>
                    </div>
                    );
                  })}
                  {nodeServices.length === 0 && (
                    <div className="empty-state">
                      <h3>No services on this node</h3>
                      <p>Open the catalog to deploy or discover running containers.</p>
                    </div>
                  )}
                </div>
              </div>
              )}

              {detailTab === "events" && (
                <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: 12, padding: "1rem", background: "var(--bg-elevated)" }}>
                  <div className="panel-title" style={{ marginBottom: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <h2 style={{ margin: 0 }}>Node events</h2>
                      <span>{nodeEvents.length}</span>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={nodeEventsBusy}
                      onClick={async () => {
                        setNodeEventsBusy(true);
                        try {
                          const evts = await loadScopedEvents?.({ node_id: activeNode.id, limit: 60 });
                          setNodeEvents(Array.isArray(evts) ? evts : []);
                        } catch (_e) {
                          setNodeEvents([]);
                        } finally {
                          setNodeEventsBusy(false);
                        }
                      }}
                    >
                      {nodeEventsBusy ? "Loading…" : "Refresh events"}
                    </button>
                  </div>
                  <div className="timeline" style={{ maxHeight: 360, overflow: "auto" }}>
                    {nodeEventsBusy && nodeEvents.length === 0 && (
                      <p style={{ color: "var(--ink-4)", margin: 0 }}>Loading node events…</p>
                    )}
                    {nodeEvents.slice(0, 40).map((ev) => (
                      <article key={ev.id}>
                        <span className={`pill ${ev.level === "error" ? "pill-error" : ev.level === "warning" ? "pill-warn" : "pill-ok"}`}>{ev.category || "event"}</span>
                        <strong style={{ fontSize: "0.85rem" }}>{ev.message}</strong>
                        <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(ev.created_at)}</small>
                      </article>
                    ))}
                    {!nodeEventsBusy && nodeEvents.length === 0 && (
                      <p style={{ color: "var(--ink-4)", margin: 0 }}>No node-scoped events yet. Click Refresh events to load from API.</p>
                    )}
                  </div>
                </div>
              )}

              {detailTab === "live" && (
                <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: 12, padding: "1rem", background: "var(--bg-elevated)" }}>
                  <div className="panel-title" style={{ marginBottom: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <div>
                      <h2 style={{ margin: 0 }}>Live status</h2>
                      <small style={{ color: "var(--ink-4)" }}>
                        {nodeLiveStatus?.checked_at
                          ? `Checked ${formatLocalTimestamp(nodeLiveStatus.checked_at)} · source ${nodeLiveStatus.source || "—"}`
                          : "Not loaded yet"}
                      </small>
                    </div>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => refreshNodeLiveStatus?.(activeNode.id, { via: "ssh" })}>
                      Refresh live
                    </button>
                  </div>
                  {nodeLiveStatus && nodeLiveStatus.node_id === activeNode.id ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
                      <div style={{ fontSize: "0.85rem", color: "var(--ink-3)" }}>
                        {nodeLiveStatus.running_count}/{nodeLiveStatus.count} running
                      </div>
                      {(nodeLiveStatus.items || []).map((item: any) => (
                        <article
                          key={`live-${item.service_id}`}
                          style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.7rem 0.85rem", cursor: "pointer" }}
                          onClick={() => {
                            const svc = nodeServices.find((s) => s.id === item.service_id);
                            if (svc) openServiceDrawer(svc, "live");
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div>
                              <strong>{item.name || item.service_key}</strong>
                              {item.external_id ? <span style={{ marginLeft: 8, fontFamily: "var(--mono)", fontSize: "0.72rem", color: "var(--ink-4)" }}>{item.external_id}</span> : null}
                              <div style={{ fontSize: "0.78rem", color: "var(--ink-4)" }}>
                                <code>{item.container_name || "—"}</code>
                                {item.image ? <> · {item.image}</> : null}
                              </div>
                            </div>
                            <span className={`pill ${item.running ? "pill-ok" : "pill-error"}`}>{item.overall_status || item.state || "unknown"}</span>
                          </div>
                          {item.error ? <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--err)" }}>{item.error}</div> : null}
                          <div style={{ marginTop: 4, fontSize: "0.72rem", color: "var(--ink-4)" }}>
                            restarts {item.restart_count ?? "—"}
                            {item.started_at ? ` · started ${formatLocalTimestamp(item.started_at)}` : ""}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: "var(--ink-4)" }}>No live report yet. Click Refresh live.</p>
                  )}
                </div>
              )}

              {detailTab === "jobs" && (
                <div style={{ marginTop: "1rem", border: "1px solid var(--line)", borderRadius: 12, padding: "1rem", background: "var(--bg-elevated)" }}>
                  <div className="panel-title" style={{ marginBottom: "0.75rem" }}>
                    <h2>Jobs</h2>
                    <span>{nodeJobHistory ? `${nodeJobHistory.total_jobs} total` : "—"}</span>
                  </div>
                  {nodeJobHistory ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
                      {nodeJobHistory.items.slice(0, 20).map((item) => (
                        <article key={`tab-job-${item.id}`} style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.7rem 0.85rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                              <span className={`pill ${item.status === "success" ? "pill-ok" : item.status === "failed" ? "pill-error" : "pill-warn"}`}>{item.status}</span>
                              <strong>{item.action}</strong>
                            </div>
                            <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(item.created_at)}</small>
                          </div>
                          {item.error && <pre style={{ margin: "0.45rem 0 0", fontSize: "0.75rem", color: "var(--err)", whiteSpace: "pre-wrap" }}>{item.error}</pre>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: "var(--ink-4)" }}>Loading jobs…</p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="node-detail" style={{ padding: "3rem", textAlign: "center", justifyContent: "center" }}>
              <h3>Select a node</h3>
              <p style={{ color: "var(--ink-4)" }}>
                {clusterNodes.length === 0
                  ? "This cluster has no nodes yet. Use Provision node to add one."
                  : "Select a host from the list to manage services and jobs."}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Service detail drawer — Overview | Events | Live Status (cPlatform parity) */}
      {serviceDrawer.visible && serviceDrawer.service && (
        <>
          <div
            className="drawer-backdrop"
            style={{ display: "block", position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 80 }}
            onClick={() => setServiceDrawer((d) => ({ ...d, visible: false }))}
          />
          <aside
            style={{
              position: "fixed",
              top: 0,
              right: 0,
              width: "min(420px, 100vw)",
              height: "100vh",
              background: "var(--bg-elevated, #0f1419)",
              borderLeft: "1px solid var(--line)",
              zIndex: 90,
              display: "flex",
              flexDirection: "column",
              boxShadow: "-8px 0 32px rgba(0,0,0,0.25)",
            }}
          >
            <div style={{ padding: "1rem 1.1rem", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
              <div>
                <h3 style={{ margin: 0 }}>{serviceDrawer.service.name}</h3>
                <div style={{ fontSize: "0.78rem", color: "var(--ink-4)", marginTop: 4 }}>
                  {serviceDrawer.service.external_id || "—"} · <code>{serviceDrawer.service.service_key}</code>
                </div>
              </div>
              <button type="button" className="icon-btn" onClick={() => setServiceDrawer((d) => ({ ...d, visible: false }))} aria-label="Close">
                ✕
              </button>
            </div>
            <div style={{ display: "flex", gap: 6, padding: "0.65rem 1rem", borderBottom: "1px solid var(--line)", flexWrap: "wrap" }}>
              {["overview", "events", "live"].map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`btn btn-sm ${serviceDrawer.tab === tab ? "btn-primary" : "btn-secondary"}`}
                  onClick={async () => {
                    setServiceDrawer((d) => ({ ...d, tab, busy: true }));
                    if (tab === "events") {
                      const evts = await loadScopedEvents?.({ service_id: serviceDrawer.service.id, limit: 40 });
                      setServiceDrawer((d) => ({ ...d, events: evts || [], busy: false }));
                    } else if (tab === "live") {
                      const live = await loadServiceLiveStatus?.(serviceDrawer.service.id);
                      setServiceDrawer((d) => ({ ...d, live: live || d.live, busy: false }));
                    } else {
                      setServiceDrawer((d) => ({ ...d, busy: false }));
                    }
                  }}
                >
                  {tab === "live" ? "Live status" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "1rem 1.1rem" }}>
              {serviceDrawer.busy && <p style={{ color: "var(--ink-4)", fontSize: "0.85rem" }}>Loading…</p>}
              {serviceDrawer.tab === "overview" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                  <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "110px 1fr", gap: "0.4rem 0.75rem", fontSize: "0.85rem" }}>
                    <dt style={{ color: "var(--ink-4)" }}>Container</dt>
                    <dd style={{ margin: 0 }}><code>{serviceDrawer.service.container_name || "—"}</code></dd>
                    <dt style={{ color: "var(--ink-4)" }}>Image</dt>
                    <dd style={{ margin: 0 }}><code style={{ wordBreak: "break-all" }}>{serviceDrawer.service.image || serviceDrawer.live?.image || "—"}</code></dd>
                    <dt style={{ color: "var(--ink-4)" }}>Kind</dt>
                    <dd style={{ margin: 0 }}>{serviceDrawer.service.kind}</dd>
                    <dt style={{ color: "var(--ink-4)" }}>Status</dt>
                    <dd style={{ margin: 0 }}>{serviceDrawer.live?.overall_status || serviceDrawer.service.status || "—"}</dd>
                    <dt style={{ color: "var(--ink-4)" }}>Ports</dt>
                    <dd style={{ margin: 0 }}>{servicePortsLabel(serviceDrawer.service)}</dd>
                  </dl>
                  <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "0.85rem" }}>
                    <strong style={{ fontSize: "0.9rem" }}>Expose / host port</strong>
                    <p style={{ margin: "0.35rem 0 0.75rem", fontSize: "0.78rem", color: "var(--ink-4)" }}>
                      cPlatform-style network exposure for this service card.
                    </p>
                    <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem", marginBottom: 8 }}>
                      <input
                        type="checkbox"
                        checked={Boolean(serviceDrawer.expose)}
                        onChange={(e) => setServiceDrawer((d) => ({ ...d, expose: e.target.checked }))}
                      />
                      Expose service on host port
                    </label>
                    <input
                      className="input"
                      type="number"
                      placeholder="Host port"
                      value={serviceDrawer.hostPort}
                      disabled={!serviceDrawer.expose}
                      onChange={(e) => setServiceDrawer((d) => ({ ...d, hostPort: e.target.value }))}
                      style={{ width: "100%", marginBottom: 8 }}
                    />
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={async () => {
                        const updated = await updateServiceExpose?.(serviceDrawer.service, {
                          expose_service: serviceDrawer.expose,
                          host_port: serviceDrawer.expose ? serviceDrawer.hostPort : "",
                        });
                        if (updated) setServiceDrawer((d) => ({ ...d, service: updated }));
                      }}
                    >
                      Save network options
                    </button>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => { loadConfig(serviceDrawer.service); setActiveView("config"); }}>Config</button>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => openDeploymentModal(serviceDrawer.service)}>Deploy</button>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => runPatchObservability?.(serviceDrawer.service.id, serviceDrawer.service.name)}>Patch observability</button>
                    <button type="button" className="btn btn-danger btn-sm" onClick={() => requestDelete("service", serviceDrawer.service.id, serviceDrawer.service.name)}>Uninstall</button>
                  </div>
                </div>
              )}
              {serviceDrawer.tab === "events" && (
                <div className="timeline" style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
                  {(serviceDrawer.events || []).length === 0 && !serviceDrawer.busy && (
                    <p style={{ color: "var(--ink-4)", margin: 0 }}>No service events yet.</p>
                  )}
                  {(serviceDrawer.events || []).map((ev: any) => (
                    <article key={ev.id} style={{ border: "1px solid var(--line-2)", borderRadius: 10, padding: "0.65rem 0.75rem" }}>
                      <span className={`pill ${ev.level === "error" ? "pill-error" : ev.level === "warning" ? "pill-warn" : "pill-ok"}`}>{ev.category || "event"}</span>
                      <div style={{ fontSize: "0.85rem", marginTop: 4 }}>{ev.message}</div>
                      <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(ev.created_at)}</small>
                    </article>
                  ))}
                </div>
              )}
              {serviceDrawer.tab === "live" && (
                <div style={{ fontSize: "0.85rem" }}>
                  {serviceDrawer.live ? (
                    <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "120px 1fr", gap: "0.4rem 0.75rem" }}>
                      <dt style={{ color: "var(--ink-4)" }}>Overall</dt>
                      <dd style={{ margin: 0 }}><span className={`pill ${serviceDrawer.live.running ? "pill-ok" : "pill-error"}`}>{serviceDrawer.live.overall_status}</span></dd>
                      <dt style={{ color: "var(--ink-4)" }}>State</dt>
                      <dd style={{ margin: 0 }}>{serviceDrawer.live.state || "—"}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Running</dt>
                      <dd style={{ margin: 0 }}>{String(serviceDrawer.live.running)}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Restarts</dt>
                      <dd style={{ margin: 0 }}>{serviceDrawer.live.restart_count ?? "—"}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Started</dt>
                      <dd style={{ margin: 0 }}>{serviceDrawer.live.started_at ? formatLocalTimestamp(serviceDrawer.live.started_at) : "—"}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Checked</dt>
                      <dd style={{ margin: 0 }}>{serviceDrawer.live.checked_at ? formatLocalTimestamp(serviceDrawer.live.checked_at) : "—"}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Source</dt>
                      <dd style={{ margin: 0 }}>{serviceDrawer.live.source || "—"}</dd>
                      <dt style={{ color: "var(--ink-4)" }}>Error</dt>
                      <dd style={{ margin: 0, color: serviceDrawer.live.error ? "var(--err)" : undefined }}>{serviceDrawer.live.error || "—"}</dd>
                    </dl>
                  ) : (
                    <p style={{ color: "var(--ink-4)" }}>No live status yet.</p>
                  )}
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ marginTop: 12 }}
                    onClick={async () => {
                      setServiceDrawer((d) => ({ ...d, busy: true }));
                      const live = await loadServiceLiveStatus?.(serviceDrawer.service.id);
                      setServiceDrawer((d) => ({ ...d, live: live || d.live, busy: false }));
                    }}
                  >
                    Refresh live status
                  </button>
                </div>
              )}
            </div>
          </aside>
        </>
      )}
      </>
    );
}
