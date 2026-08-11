// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
import { withPending } from "../ux/clusterUx";
export function createMonitoringActions(s: any) {
  return {
  async loadGlitchTipIntegrationStatus() {
    try {
      const data = await api("/PlatformIO/Monitoring/IntegrationStatus/");
      s.setGtIntegrationStatus(data);
    } catch (e) {
      console.error("Failed to fetch GlitchTip status:", e);
    }
  },

  async loadGlitchTipDataForService(serviceName, window2 = s.gtWindow) {
    if (!serviceName) return;
    try {
      const dataIssues = await api("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        body: JSON.stringify({ service_name: serviceName, window: window2 })
      });
      if (dataIssues.success) {
        s.setGtIssues(dataIssues.issues || []);
        s.setGtIssuesCursor(dataIssues.cursor || dataIssues.next_cursor || null);
        s.setGtIssuesHasMore(Boolean(dataIssues.has_more || dataIssues.cursor || dataIssues.next_cursor || (dataIssues.issues || []).length >= 25));
      }
      const dataUptime = await api("/PlatformIO/Monitoring/Uptime/", {
        method: "POST",
        body: JSON.stringify({ service_name: serviceName })
      });
      if (dataUptime.success) s.setGtUptimeMonitors(dataUptime.monitors || []);
      const dataKeys = await api("/PlatformIO/Monitoring/Keys/", {
        method: "POST",
        body: JSON.stringify({ service_name: serviceName })
      });
      if (dataKeys.success) s.setGtKeys(dataKeys.keys || []);
      const dataPerf = await api("/PlatformIO/Monitoring/Performance/", {
        method: "POST",
        body: JSON.stringify({ service_name: serviceName })
      });
      if (dataPerf.success) s.setGtTransactions(dataPerf.transactions || []);
    } catch (e) {
      console.error("Failed to load GlitchTip data for service:", e);
    }
  },

  async loadMoreGtIssues() {
    const svc = s.services.find((s) => s.id === s.gtSelectedServiceId) || s.selectedService;
    if (!svc) return;
    try {
      const data = await api("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        body: JSON.stringify({ service_name: svc.name, window: s.gtWindow, cursor: s.gtIssuesCursor })
      });
      if (data.success) {
        const more = data.issues || [];
        s.setGtIssues((prev) => [...prev, ...more]);
        s.setGtIssuesCursor(data.cursor || data.next_cursor || null);
        s.setGtIssuesHasMore(Boolean(data.has_more || data.cursor || data.next_cursor));
      }
    } catch (e) {
      s.setNotice(e?.message || "Failed to load more issues");
    }
  },

  async loadEventDetails(issueId) {
    s.setGtSelectedIssueId(issueId);
    s.setGtEventDetails(null);
    try {
      const data = await api("/PlatformIO/Monitoring/Issues/EventDetails/", {
        method: "POST",
        body: JSON.stringify({ issue_id: issueId })
      });
      if (data.success) {
        s.setGtEventDetails(data.event);
      } else {
        s.setNotice(`Failed to load event details: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to load event details:", e);
    }
  },

  async runIssueAction(issueId, action, serviceName) {
    try {
      const data = await api("/PlatformIO/Monitoring/IssueAction/", {
        method: "POST",
        body: JSON.stringify({ issue_id: issueId, action })
      });
      if (data.success) {
        s.setNotice(`Issue status updated to ${action}`);
        await s.loadGlitchTipDataForService(serviceName);
        if (s.gtSelectedIssueId === issueId) {
          s.setGtSelectedIssueId(null);
          s.setGtEventDetails(null);
        }
      } else {
        s.setNotice(`Action failed: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to update issue action:", e);
    }
  },

  async runAddMonitor(serviceName) {
    if (!s.uptimeForm.name || !s.uptimeForm.url) {
      s.setNotice("Name and URL are required to add monitor");
      return;
    }
    try {
      const data = await api("/PlatformIO/Monitoring/Uptime/Add/", {
        method: "POST",
        body: JSON.stringify({
          service_name: serviceName,
          name: s.uptimeForm.name,
          monitor_type: s.uptimeForm.monitor_type,
          url: s.uptimeForm.url,
          interval: parseInt(s.uptimeForm.interval || 60),
          expected_status: parseInt(s.uptimeForm.expected_status || 200)
        })
      });
      if (data.success) {
        s.setNotice("Uptime monitor added successfully");
        s.setUptimeFormVisible(false);
        s.setUptimeForm({ name: "", monitor_type: "Ping", url: "", interval: 60, expected_status: 200 });
        await s.loadGlitchTipDataForService(serviceName);
      } else {
        s.setNotice(`Failed to add monitor: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to add monitor:", e);
      s.setNotice(e?.message || "Failed to add monitor");
    }
  },

  async runDeleteMonitor(monitorId, serviceName) {
    if (!window.confirm("Are you sure you want to delete this uptime monitor?")) return;
    try {
      const data = await api("/PlatformIO/Monitoring/Uptime/Delete/", {
        method: "POST",
        body: JSON.stringify({ monitor_id: monitorId })
      });
      if (data.success) {
        s.setNotice("Uptime monitor deleted successfully");
        await s.loadGlitchTipDataForService(serviceName);
      } else {
        s.setNotice(`Failed to delete monitor: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to delete monitor:", e);
    }
  },

  async runPatchObservability(serviceId, serviceName) {
    // cP withPending + setRuntimePatchButtonBusy
    return withPending(`runtime-patch:${serviceId}`, async () => {
      s.setActionBusy?.((b) => ({ ...b, patch: true, [`patch:${serviceId}`]: true }));
      s.setNotice("Running observability runtime patch (GlitchTip/Sentry inject)…");
      try {
        const data = await api("/PlatformIO/Monitoring/PatchObservability/", {
          method: "POST",
          body: JSON.stringify({ service_id: serviceId })
        });
        const checkedAt = new Date().toISOString();
        // Only treat explicit success:true as success — HTTP 200 with success:false is a failure.
        if (data && data.success === true) {
          const msg = data.message || data.result?.message || `Observability patch finished for ${serviceName || serviceId}.`;
          s.showToast?.(msg, "ok") || s.setNotice(msg);
          // Publish status for open service drawer (cP runtimePatchStatusText)
          s.setRuntimePatchStatus?.({
            serviceId,
            last_status: "success",
            last_checked_at: checkedAt,
            last_message: msg,
            last_environment: data.environment || data.result?.environment || "",
          });
          if (serviceName && s.loadGlitchTipDataForService) {
            await s.loadGlitchTipDataForService(serviceName).catch(() => {});
          }
          if (s.refreshNodeLiveStatus && s.selectedNode?.id) {
            await s.refreshNodeLiveStatus(s.selectedNode.id).catch(() => {});
          }
          return data;
        }
        const errMsg =
          (data && (data.error || data.detail || data.result?.error)) ||
          "Patch reported success=false";
        const fail = `Observability patch failed: ${typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)}`;
        s.showToast?.(fail, "err") || s.setNotice(fail);
        s.setRuntimePatchStatus?.({
          serviceId,
          last_status: "failed",
          last_checked_at: checkedAt,
          last_message: typeof errMsg === "string" ? errMsg : "failed",
          last_environment: "",
        });
        return data;
      } catch (e) {
        console.error("Failed to run observability patch:", e);
        s.showToast?.(e?.message || "Observability patch failed", "err") || s.setNotice(e?.message || "Observability patch failed");
        s.setRuntimePatchStatus?.({
          serviceId,
          last_status: "error",
          last_checked_at: new Date().toISOString(),
          last_message: e?.message || "request failed",
          last_environment: "",
        });
        return null;
      } finally {
        s.setActionBusy?.((b) => ({ ...b, patch: false, [`patch:${serviceId}`]: false }));
      }
    });
  },

  async runMonitoringSweep() {
    const nextChecks = await api("/api/monitoring/sweep", { method: "POST" });
    s.setChecks(nextChecks);
    s.setNotice(`Recorded ${nextChecks.length} monitoring checks`);
    await s.refresh();
  }
  };
}
