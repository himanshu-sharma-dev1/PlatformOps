// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createMonitoringActions(s: any) {
  return {
  async loadGlitchTipIntegrationStatus() {
    try {
      const res = await fetch("/PlatformIO/Monitoring/IntegrationStatus/");
      const data = await res.json();
      s.setGtIntegrationStatus(data);
    } catch (e) {
      console.error("Failed to fetch GlitchTip status:", e);
    }
  },

  async loadGlitchTipDataForService(serviceName, window2 = s.gtWindow) {
    if (!serviceName) return;
    try {
      const resIssues = await fetch("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName, window: "24h" })
      });
      const dataIssues = await resIssues.json();
      if (dataIssues.success) {
        s.setGtIssues(dataIssues.issues || []);
        s.setGtIssuesCursor(dataIssues.cursor || dataIssues.next_cursor || null);
        s.setGtIssuesHasMore(Boolean(dataIssues.has_more || dataIssues.cursor || dataIssues.next_cursor || (dataIssues.issues || []).length >= 25));
      }
      const resUptime = await fetch("/PlatformIO/Monitoring/Uptime/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataUptime = await resUptime.json();
      if (dataUptime.success) s.setGtUptimeMonitors(dataUptime.monitors || []);
      const resKeys = await fetch("/PlatformIO/Monitoring/Keys/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataKeys = await resKeys.json();
      if (dataKeys.success) s.setGtKeys(dataKeys.keys || []);
      const resPerf = await fetch("/PlatformIO/Monitoring/Performance/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName })
      });
      const dataPerf = await resPerf.json();
      if (dataPerf.success) s.setGtTransactions(dataPerf.transactions || []);
    } catch (e) {
      console.error("Failed to load GlitchTip data for service:", e);
    }
  },

  async loadMoreGtIssues() {
    const svc = s.services.find((s) => s.id === s.gtSelectedServiceId) || s.selectedService;
    if (!svc) return;
    try {
      const res = await fetch("/PlatformIO/Monitoring/Issues/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: svc.name, window: s.gtWindow, cursor: s.gtIssuesCursor })
      });
      const data = await res.json();
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
    setGtSelectedIssueId(issueId);
    s.setGtEventDetails(null);
    try {
      const res = await fetch("/PlatformIO/Monitoring/Issues/EventDetails/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue_id: issueId })
      });
      const data = await res.json();
      if (data.success) {
        setGtEventDetails(data.event);
      } else {
        s.setNotice(`Failed to load event details: ${data.error}`);
      }
    } catch (e) {
      console.error("Failed to load event details:", e);
    }
  },

  async runIssueAction(issueId, action, serviceName) {
    try {
      const res = await fetch("/PlatformIO/Monitoring/IssueAction/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue_id: issueId, action })
      });
      const data = await res.json();
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
      const res = await fetch("/PlatformIO/Monitoring/Uptime/Add/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: serviceName,
          name: s.uptimeForm.name,
          monitor_type: s.uptimeForm.monitor_type,
          url: s.uptimeForm.url,
          interval: parseInt(s.uptimeForm.interval || 60),
          expected_status: parseInt(s.uptimeForm.expected_status || 200)
        })
      });
      const data = await res.json();
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
      const res = await fetch("/PlatformIO/Monitoring/Uptime/Delete/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monitor_id: monitorId })
      });
      const data = await res.json();
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
    s.setNotice("Running observability runtime patch (GlitchTip/Sentry inject)…");
    try {
      const headers = { "Content-Type": "application/json" };
      try {
        const token = getAuthToken?.() || (typeof localStorage !== "undefined" ? localStorage.getItem("platformops.auth.token") : "");
        if (token) headers.Authorization = `Bearer ${token}`;
      } catch (_e) { /* ignore */ }
      const res = await fetch("/PlatformIO/Monitoring/PatchObservability/", {
        method: "POST",
        headers,
        body: JSON.stringify({ service_id: serviceId })
      });
      const data = await res.json().catch(() => ({}));
      // Only treat explicit success:true as success — HTTP 200 with success:false is a failure.
      if (data && data.success === true) {
        s.setNotice(data.message || data.result?.message || `Observability patch finished for ${serviceName || serviceId}.`);
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
        (!res.ok ? `HTTP ${res.status}` : "Patch reported success=false");
      s.setNotice(`Observability patch failed: ${typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)}`);
      return data;
    } catch (e) {
      console.error("Failed to run observability patch:", e);
      s.setNotice(e?.message || "Observability patch failed");
      return null;
    }
  },

  async runMonitoringSweep() {
    const nextChecks = await api("/api/monitoring/sweep", { method: "POST" });
    s.setChecks(nextChecks);
    s.setNotice(`Recorded ${nextChecks.length} monitoring checks`);
    await s.refresh();
  }
  };
}
