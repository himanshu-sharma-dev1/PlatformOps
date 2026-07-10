// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createPerformanceActions(s: any) {
  return {
  async loadServiceMetrics(serviceId, window2 = s.serviceMetricsWindow) {
    try {
      const metrics = await api(`/api/services/${serviceId}/metrics?window=${encodeURIComponent(window2)}`);
      s.setServiceMetrics(metrics);
    } catch (_error) {
      s.setServiceMetrics(null);
    }
  },

  async loadNodeMetrics(nodeId, window2 = s.nodeMetricsWindow) {
    try {
      const metrics = await api(`/api/nodes/${nodeId}/metrics?window=${encodeURIComponent(window2)}`);
      s.setNodeMetrics(metrics);
    } catch (_error) {
      s.setNodeMetrics(null);
    }
  },

  async loadNodeMetricsData(nodeId) {
    setLoadingMetrics(true);
    try {
      if (nodeId) {
        const resNode = await fetch(`/api/nodes/${nodeId}/metrics`);
        const dataNode = await resNode.json();
        if (dataNode && !dataNode.error) {
          s.setRealtimeNodeMetrics({
            cpu: parseFloat(dataNode.cpu_percent || 0),
            memory: parseFloat(dataNode.memory_percent || 0),
            disk: parseFloat(dataNode.disk_percent || 0)
          });
        }
        const resProc = await fetch("/api/metrics/processes");
        const dataProc = await resProc.json();
        if (dataProc && dataProc.processes) {
          s.setProcessMetrics((dataProc.processes || []).map((p) => ({
            name: p.name || p.group || "proc",
            cpu: String(p.cpu ?? p.cpu_seconds ?? 0),
            memory: p.memory != null ? String(p.memory) : p.mem != null ? String(p.mem) : void 0
          })));
        }
      } else {
        const [resNode, resProc] = await Promise.all([
          fetch("/api/metrics/node"),
          fetch("/api/metrics/processes")
        ]);
        const dataNode = await resNode.json();
        const dataProc = await resProc.json();
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
      setLoadingMetrics(false);
    }
  }
  };
}
