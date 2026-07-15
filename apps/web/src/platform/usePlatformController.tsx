// @ts-nocheck
import { useEffect } from "react";
import { api, getAuthToken, setAuthToken } from "../api/client";
import type { PlatformApi } from "./context";
import { usePlatformState } from "./usePlatformState";
import { createSharedActions } from "./actions/sharedActions";
import { createAuthActions } from "./actions/authActions";
import { createInventoryActions } from "./actions/inventoryActions";
import { createConfigActions } from "./actions/configActions";
import { createDiagnosticsActions } from "./actions/diagnosticsActions";
import { createMonitoringActions } from "./actions/monitoringActions";
import { createPerformanceActions } from "./actions/performanceActions";
import { createSreActions } from "./actions/sreActions";
import { createObservabilityActions } from "./actions/observabilityActions";

const OPERATOR_PREFERENCES_KEY = "platformops.operator.preferences.v1";

export function usePlatformController(): PlatformApi {
  const state = usePlatformState();
  const s: any = { ...state };

  Object.assign(
    s,
    createSharedActions(s),
    createAuthActions(s),
    createInventoryActions(s),
    createConfigActions(s),
    createDiagnosticsActions(s),
    createMonitoringActions(s),
    createPerformanceActions(s),
    createSreActions(s),
    createObservabilityActions(s),
  );

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(OPERATOR_PREFERENCES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        s.setOperatorPreferences(parsed);
        if (parsed.configSource) s.setConfigSource(parsed.configSource);
        if (parsed.selectedPlacementServiceKey) s.setSelectedPlacementServiceKey(parsed.selectedPlacementServiceKey);
        if (parsed.nodePreset) s.setNodePreset(parsed.nodePreset);
        if (parsed.nodeMetricsWindow) s.setNodeMetricsWindow(parsed.nodeMetricsWindow);
        if (parsed.serviceMetricsWindow) s.setServiceMetricsWindow(parsed.serviceMetricsWindow);
      }
    } catch (_error) {
    }
    // Only load inventory when a session token already exists (avoids 401 spam on login screen)
    if (getAuthToken()) {
      s.refresh().catch((error) => s.setNotice(error.message));
    }
  }, []);

  useEffect(() => {
    const next = {
      selectedClusterId: s.selectedCluster?.id ?? null,
      selectedNodeId: s.selectedNode?.id ?? null,
      selectedServiceId: s.selectedService?.id ?? null,
      selectedPlacementServiceKey: s.selectedPlacementServiceKey,
      configSource: s.configSource,
      nodePreset: s.nodePreset,
      nodeMetricsWindow: s.nodeMetricsWindow,
      serviceMetricsWindow: s.serviceMetricsWindow
    };
    s.setOperatorPreferences(next);
    try {
      window.localStorage.setItem(OPERATOR_PREFERENCES_KEY, JSON.stringify(next));
    } catch (_error) {
    }
  }, [s.selectedCluster, s.selectedNode, s.selectedService, s.selectedPlacementServiceKey, s.configSource, s.nodePreset, s.nodeMetricsWindow, s.serviceMetricsWindow]);

  useEffect(() => {
    if (!s.operatorPreferences) return;
    if (!s.selectedCluster && s.operatorPreferences.selectedClusterId) {
      const preferredCluster = s.clusters.find((cluster) => cluster.id === s.operatorPreferences.selectedClusterId);
      if (preferredCluster) {
        s.setSelectedCluster(preferredCluster);
      }
    }
    if (!s.selectedNode && s.operatorPreferences.selectedNodeId) {
      const preferredNode = s.nodes.find((node) => node.id === s.operatorPreferences.selectedNodeId);
      if (preferredNode) {
        s.setSelectedNode(preferredNode);
      }
    }
    if (!s.selectedService && s.operatorPreferences.selectedServiceId) {
      const preferredService = s.services.find((service) => service.id === s.operatorPreferences.selectedServiceId);
      if (preferredService) {
        s.setSelectedService(preferredService);
      }
    }
  }, [s.clusters, s.nodes, s.services, s.operatorPreferences, s.selectedCluster, s.selectedNode, s.selectedService]);

  useEffect(() => {
    if (!s.selectedNode) return;
    s.loadNodeMetrics(s.selectedNode.id, s.nodeMetricsWindow).catch(console.error);
  }, [s.selectedNode, s.nodeMetricsWindow]);

  // Clusters live status poll (real docker inspect; ~5s server cache)
  useEffect(() => {
    const onClusters = s.activeView === "clusters" || s.activeView === "dashboard";
    if (!onClusters || !s.selectedNode?.id || !s.authUser || !getAuthToken()) return;
    let cancelled = false;
    const tick = () => {
      if (cancelled || !getAuthToken()) return;
      s.refreshNodeLiveStatus?.(s.selectedNode.id).catch(() => {});
    };
    tick();
    const interval = window.setInterval(tick, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [s.activeView, s.selectedNode?.id, s.authUser]);

  useEffect(() => {
    if (!s.selectedService) return;
    s.loadServiceMetrics(s.selectedService.id, s.serviceMetricsWindow).catch(console.error);
  }, [s.selectedService, s.serviceMetricsWindow]);

  useEffect(() => {
    if (!s.selectedNode || !s.nodeJobHistory) return;
    const hasActiveJobs = s.nodeJobHistory.items.some(
      (job2) => job2.status === "queued" || job2.status === "running"
    );
    if (!hasActiveJobs) return;
    const interval = window.setInterval(() => {
      s.loadNodeJobHistory(s.selectedNode.id).catch(console.error);
      s.refresh().catch(console.error);
    }, 2e3);
    return () => window.clearInterval(interval);
  }, [s.selectedNode, s.nodeJobHistory, s.refresh, s.loadNodeJobHistory]);

  useEffect(() => {
    if (!s.job || s.job.status !== "running" && s.job.status !== "queued") return;
    const interval = window.setInterval(async () => {
      try {
        const refreshedJob = await api(`/api/jobs/${s.job.id}`);
        s.setJob(refreshedJob);
      } catch (err) {
      }
    }, 1500);
    return () => window.clearInterval(interval);
  }, [s.job]);

  useEffect(() => {
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    if (!s.autoPollLogs || !sourceService) return;
    const interval = window.setInterval(() => {
      s.loadDiagnosticsLive(sourceService, { cursor: 0, silent: true }).catch(() => {
      });
    }, Math.max(1e3, s.logsPollMs));
    return () => window.clearInterval(interval);
  }, [s.autoPollLogs, s.selectedService, s.diagnosticsSourceServiceId, s.services, s.logsPollMs, s.tailLines, s.historyPageSize, s.diagnosticsTargetKey]);

  useEffect(() => {
    if (s.activeView === "node-metrics" || s.activeView === "performance") {
      s.loadNodeMetricsData();
    } else if (s.activeView === "monitoring") {
      s.loadGlitchTipIntegrationStatus();
      s.setMonitoringSubTab("glitchtip");
    } else if (s.activeView === "diagnostics") {
      api("/api/diagnostics/ingestion-stats").then(s.setIngestionStats).catch(() => s.setIngestionStats(null));
    } else if (s.activeView === "observability") {
      s.refreshObservabilityStackStatus();
    }
  }, [s.activeView]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await api("/api/llm/status");
        if (!cancelled) s.setLlmStatus(status);
      } catch {
        if (!cancelled) s.setLlmStatus({ configured: false });
      }
      const token = getAuthToken();
      if (!token) {
        if (!cancelled) {
          s.setAuthUser(null);
          s.setAuthReady(true);
        }
        return;
      }
      try {
        const me = await api("/api/auth/me");
        if (!cancelled) {
          s.setAuthUser(me);
          s.setAuthReady(true);
        }
      } catch {
        setAuthToken("");
        if (!cancelled) {
          s.setAuthUser(null);
          s.setAuthReady(true);
        }
      }
      try {
        const hash = window.location.hash || "";
        const m = hash.match(/#\/invite\/([^/?#]+)/);
        if (m) {
          const tokenInv = m[1];
          const preview = await api(`/api/auth/invite/${tokenInv}`);
          if (!cancelled) s.setInviteAccept({ token: tokenInv, password: "", preview });
        }
      } catch {
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!s.authUser) return;
    if (s.activeView === "users") {
      void s.loadPlatformUsers();
    }
    api("/api/auth/last-visited", {
      method: "POST",
      body: JSON.stringify({
        view: s.activeView,
        cluster_name: s.selectedCluster?.name || null,
        node_name: s.selectedNode?.name || null,
        service_name: s.selectedService?.name || null
      })
    }).catch(() => void 0);
  }, [s.activeView, s.authUser, s.selectedCluster?.id, s.selectedNode?.id, s.selectedService?.id]);

  useEffect(() => {
    if (!s.gtAutoRefresh || s.activeView !== "monitoring") return;
    const id = window.setInterval(() => {
      const svc = s.services.find((s) => s.id === s.gtSelectedServiceId) || s.selectedService;
      if (svc) s.loadGlitchTipDataForService(svc.name, s.gtWindow);
      s.loadGlitchTipIntegrationStatus();
    }, 3e4);
    return () => window.clearInterval(id);
  }, [s.gtAutoRefresh, s.activeView, s.gtSelectedServiceId, s.selectedService, s.gtWindow, s.services]);

  useEffect(() => {
    if (!s.perfAutoRefresh || s.activeView !== "performance") return;
    const id = window.setInterval(() => {
      if (s.selectedService) s.loadServiceMetrics(s.selectedService.id);
      if (s.selectedNode) {
        s.loadNodeMetrics(s.selectedNode.id);
        s.loadNodeMetricsData(s.selectedNode.id);
      }
    }, 3e4);
    return () => window.clearInterval(id);
  }, [s.perfAutoRefresh, s.activeView, s.selectedService, s.selectedNode]);

  useEffect(() => {
    if (s.activeView !== "clusters" || !s.authUser || !getAuthToken()) return;
    const id = window.setInterval(() => {
      if (!getAuthToken()) return;
      s.refresh().catch(() => void 0);
      s.setLiveStatusTick((x) => x + 1);
    }, 45e3);
    return () => window.clearInterval(id);
  }, [s.activeView, s.authUser]);

  return s as PlatformApi;
}
