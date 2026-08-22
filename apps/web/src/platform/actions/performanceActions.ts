// @ts-nocheck
import { api } from "../../api/client";
export function createPerformanceActions(s: any) {
  let serviceGeneration = 0;
  let nodeGeneration = 0;
  let processGeneration = 0;
  return {
  async loadServiceMetrics(serviceId, window2 = s.serviceMetricsWindow) {
    const generation = ++serviceGeneration;
    s.setLoadingMetrics?.(true);
    s.setMetricsStatus?.("loading");
    s.setMetricsError?.(null);
    s.setServiceMetrics?.(null);
    try {
      const metrics = await api(`/api/services/${serviceId}/metrics?window=${encodeURIComponent(window2)}`);
      if (generation !== serviceGeneration || s.selectedService?.id !== serviceId) return;
      s.setServiceMetrics(metrics);
      s.setMetricsStatus?.(metrics.availability || (metrics.prometheus_reachable ? "available" : "unavailable"));
      s.setMetricsError?.(metrics.error || null);
    } catch (_error) {
      if (generation !== serviceGeneration || s.selectedService?.id !== serviceId) return;
      s.setServiceMetrics(null);
      s.setMetricsStatus?.("error");
      s.setMetricsError?.(_error?.message || "Prometheus request failed");
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetrics(nodeId, window2 = s.nodeMetricsWindow) {
    const generation = ++nodeGeneration;
    s.setLoadingMetrics?.(true);
    s.setMetricsStatus?.("loading");
    s.setMetricsError?.(null);
    s.setNodeMetrics?.(null);
    try {
      const metrics = await api(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(window2)}`);
      if (generation !== nodeGeneration || s.selectedNode?.id !== nodeId) return;
      s.setNodeMetrics(metrics);
      s.setMetricsStatus?.(metrics.availability || (metrics.prometheus_reachable ? "available" : "unavailable"));
      s.setMetricsError?.(metrics.error || null);
    } catch (_error) {
      if (generation !== nodeGeneration || s.selectedNode?.id !== nodeId) return;
      s.setNodeMetrics(null);
      s.setMetricsStatus?.("error");
      s.setMetricsError?.(_error?.message || "Prometheus request failed");
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetricsData(nodeId) {
    const generation = ++processGeneration;
    s.setLoadingMetrics?.(true);
    s.setProcessMetrics?.([]);
    try {
      if (nodeId) {
        const dataProc = await api(`/api/metrics/processes?node_id=${encodeURIComponent(nodeId)}&sort=${encodeURIComponent(s.perfProcessSort || "cpu")}`);
        if (generation !== processGeneration || s.selectedNode?.id !== nodeId) return;
        s.setMetricsError?.(dataProc?.error || null);
        if (dataProc && dataProc.processes) {
          s.setProcessMetrics((dataProc.processes || []).map((p) => ({
            name: p.name || p.group || "proc",
            cpu: p.cpu != null ? String(p.cpu) : p.cpu_seconds != null ? String(p.cpu_seconds) : void 0,
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : void 0
          })));
        }
      } else {
        s.setRealtimeNodeMetrics(null);
        s.setProcessMetrics([]);
        s.setMetricsStatus?.("unavailable");
        s.setMetricsError?.("A target node is required for process telemetry");
      }
    } catch (e) {
      if (generation === processGeneration && (!nodeId || s.selectedNode?.id === nodeId)) {
        s.setMetricsStatus?.("error");
        s.setMetricsError?.(e?.message || "Prometheus request failed");
      }
      console.error("Failed to fetch node metrics:", e);
    } finally {
      s.setLoadingMetrics?.(false);
    }
  }
  };
}
