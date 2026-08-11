// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createObservabilityActions(s: any) {
  return {
  async bootstrapObservability(nodeId) {
    try {
      s.setObservabilityBusyNodeId(nodeId);
      const result = await api(`/api/nodes/${nodeId}/observability/bootstrap`, {
        method: "POST"
      });
      s.setNotice(result.summary);
      await s.refresh();
      await s.loadNodeJobHistory(nodeId);
    } catch (error) {
      s.setNotice(`Observability bootstrap failed: ${error.message}`);
    } finally {
      s.setObservabilityBusyNodeId(null);
    }
  },

  async refreshObservabilityStackStatus() {
    s.setObsStackBusy("status");
    try {
      const data = await api("/api/observability/status");
      const containers = Array.isArray(data?.containers) ? data.containers : Array.isArray(data) ? data : [];
      s.setObsStackContainers(containers);
      s.setObsStackOutput("");
    } catch (e) {
      s.setObsStackOutput(e?.message || "Failed to load observability status");
    } finally {
      s.setObsStackBusy("");
    }
  },

  async runObservabilityStackAction(action) {
    if (action === "teardown" && !window.confirm("Teardown the observability stack? This stops managed stack containers.")) return;
    s.setObsStackBusy(action);
    s.setObsStackOutput("");
    try {
      const data = await api(`/api/observability/${action}`, { method: "POST" });
      const out = typeof data.output === "string" ? data.output : JSON.stringify(data, null, 2);
      s.setObsStackOutput(out || (data.success ? `${action} completed` : `${action} failed`));
      if (!data.success) s.setNotice(`Observability ${action} failed \u2014 see output`);
      else s.setNotice(`Observability ${action} finished`);
      await s.refreshObservabilityStackStatus();
      try {
        const pipe = await api("/api/observability/pipeline");
        s.setObservabilityPipeline(pipe);
      } catch {
      }
    } catch (e) {
      s.setObsStackOutput(e?.message || `${action} failed`);
    } finally {
      s.setObsStackBusy("");
    }
  }
  };
}
