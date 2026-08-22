// @ts-nocheck
import { api } from "../../api/client";
export function createPerformanceActions(s: any) {
  let metricsGeneration = 0;
  return {
  async loadServiceMetrics(serviceId, window2 = s.serviceMetricsWindow) {
    const generation = ++metricsGeneration;
    s.setLoadingMetrics?.(true);
    s.setMetricsStatus?.("loading");
    s.setMetricsError?.(null);
    try {
      const metrics = await api(`/api/services/${serviceId}/metrics?window=${encodeURIComponent(window2)}`);
      if (generation !== metricsGeneration) return;
      s.setServiceMetrics(metrics);
      s.setMetricsStatus?.(metrics.availability || (metrics.prometheus_reachable ? "available" : "unavailable"));
      s.setMetricsError?.(metrics.error || null);
    } catch (_error) {
      if (generation !== metricsGeneration) return;
      s.setServiceMetrics(null);
      s.setMetricsStatus?.("error");
      s.setMetricsError?.(_error?.message || "Prometheus request failed");
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetrics(nodeId, window2 = s.nodeMetricsWindow) {
    const generation = ++metricsGeneration;
    s.setLoadingMetrics?.(true);
    s.setMetricsStatus?.("loading");
    s.setMetricsError?.(null);
    try {
      const metrics = await api(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(window2)}`);
      if (generation !== metricsGeneration) return;
      s.setNodeMetrics(metrics);
      s.setMetricsStatus?.(metrics.availability || (metrics.prometheus_reachable ? "available" : "unavailable"));
      s.setMetricsError?.(metrics.error || null);
    } catch (_error) {
      if (generation !== metricsGeneration) return;
      s.setNodeMetrics(null);
      s.setMetricsStatus?.("error");
      s.setMetricsError?.(_error?.message || "Prometheus request failed");
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetricsData(nodeId) {
    const generation = ++metricsGeneration;
    s.setLoadingMetrics?.(true);
    try {
      if (nodeId) {
        const [dataNode, dataProc] = await Promise.all([
          api(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(s.nodeMetricsWindow || "1h")}`),
          api(`/api/metrics/processes?node_id=${encodeURIComponent(nodeId)}`)
        ]);
        if (generation !== metricsGeneration) return;
        s.setMetricsStatus?.(dataNode?.availability || (dataNode?.prometheus_reachable ? "available" : "unavailable"));
        s.setMetricsError?.(dataNode?.error || dataProc?.error || null);
        if (dataNode && dataNode.availability !== "error") {
          s.setRealtimeNodeMetrics({
            cpu: dataNode.cpu_percent,
            memory: dataNode.memory_percent,
            disk: dataNode.disk_percent
          });
        }
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
      if (generation === metricsGeneration) {
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
