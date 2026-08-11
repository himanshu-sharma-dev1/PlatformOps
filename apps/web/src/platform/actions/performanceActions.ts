// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createPerformanceActions(s: any) {
  return {
  async loadServiceMetrics(serviceId, window2 = s.serviceMetricsWindow) {
    s.setLoadingMetrics?.(true);
    try {
      const metrics = await api(`/api/services/${serviceId}/metrics?window=${encodeURIComponent(window2)}`);
      s.setServiceMetrics(metrics);
    } catch (_error) {
      s.setServiceMetrics(null);
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetrics(nodeId, window2 = s.nodeMetricsWindow) {
    s.setLoadingMetrics?.(true);
    try {
      const metrics = await api(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(window2)}`);
      s.setNodeMetrics(metrics);
    } catch (_error) {
      s.setNodeMetrics(null);
    } finally {
      s.setLoadingMetrics?.(false);
    }
  },

  async loadNodeMetricsData(nodeId) {
    s.setLoadingMetrics?.(true);
    try {
      if (nodeId) {
        const [dataNode, dataProc] = await Promise.all([
          api(`/api/nodes/${nodeId}/metrics`),
          api(`/api/metrics/processes?node_id=${encodeURIComponent(nodeId)}`)
        ]);
        if (dataNode && !dataNode.error) {
          s.setRealtimeNodeMetrics({
            cpu: parseFloat(dataNode.cpu_percent || 0),
            memory: parseFloat(dataNode.memory_percent || 0),
            disk: parseFloat(dataNode.disk_percent || 0)
          });
        }
        if (dataProc && dataProc.processes) {
          s.setProcessMetrics((dataProc.processes || []).map((p) => ({
            name: p.name || p.group || "proc",
            cpu: String(p.cpu ?? p.cpu_seconds ?? 0),
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : void 0
          })));
        }
      } else {
        const [dataNode, dataProc] = await Promise.all([
          api("/api/metrics/node"),
          api("/api/metrics/processes")
        ]);
        if (dataNode && !dataNode.error) {
          s.setRealtimeNodeMetrics({
            cpu: parseFloat(dataNode.cpu || 0),
            memory: parseFloat(dataNode.memory || 0),
            disk: parseFloat(dataNode.disk || 0)
          });
        }
        if (dataProc && dataProc.processes) {
          s.setProcessMetrics((dataProc.processes || []).map((p) => ({
            name: p.name || p.group || "proc",
            cpu: String(p.cpu ?? p.cpu_seconds ?? 0),
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : void 0
          })));
        }
      }
    } catch (e) {
      console.error("Failed to fetch node metrics:", e);
    } finally {
      s.setLoadingMetrics?.(false);
    }
  }
  };
}
