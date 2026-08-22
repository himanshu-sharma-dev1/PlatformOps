// @ts-nocheck
import { api, apiBlob, getAuthToken, setAuthToken } from "../../api/client";

const historyCursorValue = (value: unknown): string => (
  value === undefined || value === null || value === "" || value === 0 || value === "0" ? "" : String(value)
);

let diagnosticsRequestSequence = 0;

export function createDiagnosticsActions(s: any) {
  return {
  async loadDiagnostics(service, options) {
    const requestSequence = ++diagnosticsRequestSequence;
    const previousTargetServiceKey = s.diagnosticsTargetKey;
    if (!options?.preserveSelection) {
      s.setSelectedService(service);
    }
    const targetServiceKey = options?.targetServiceKey ?? service.service_key;
    s.setDiagnosticsSourceServiceId(service.id);
    s.setDiagnosticsTargetKey(targetServiceKey);
    if (previousTargetServiceKey && previousTargetServiceKey !== targetServiceKey) {
      s.setSelectedArchiveIds?.([]);
      s.setSelectedArchive?.(null);
    }
    await s.loadServiceCapabilities(service.id);
    await s.loadServiceSummary(service.id);
    await s.loadServiceReleaseTimeline(service.id);
    await s.loadServiceMetrics(service.id);
    if (requestSequence !== diagnosticsRequestSequence) return;
    const params = new URLSearchParams();
    if (targetServiceKey) params.set("target_service_key", targetServiceKey);
    const diagnosticsPath = `/api/services/${service.id}/diagnostics${params.toString() ? `?${params.toString()}` : ""}`;
    const analysisPath = `/api/services/${service.id}/diagnostics/analysis${params.toString() ? `?${params.toString()}` : ""}`;
    const [nextDiagnostics, nextAnalysis, nextTargets] = await Promise.all([
      api(diagnosticsPath),
      api(analysisPath),
      api(`/api/services/${service.id}/diagnostics/targets`)
    ]);
    if (requestSequence !== diagnosticsRequestSequence) return;
    const targetServiceId = nextTargets.find((item) => item.service_key === nextDiagnostics.target_service_key)?.service_id ?? service.id;
    const nextArchives = await api(`/api/services/${targetServiceId}/diagnostics/archives`);
    if (requestSequence !== diagnosticsRequestSequence) return;
    s.setDiagnosticsTargets(nextTargets);
    s.setDiagnostics(nextDiagnostics);
    s.setDiagnosticsAnalysis(nextAnalysis);
    s.setArchives(nextArchives);
    await s.loadDiagnosticsLive(service, {
      cursor: 0,
      targetServiceKey: nextDiagnostics.target_service_key
    });
  },

  async focusDiagnosticsTarget(serviceKey) {
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    if (!sourceService) {
      s.setNotice("Select a service first to inspect diagnostics targets.");
      return;
    }
    await s.loadDiagnostics(sourceService, { targetServiceKey: serviceKey, preserveSelection: true });
  },

  async loadDiagnosticsLive(service, options) {
    const requestSequence = ++diagnosticsRequestSequence;
    const source = options?.source ?? s.diagLogSource;
    const targetServiceKey = options?.targetServiceKey ?? s.diagnosticsTargetKey;
    const targetId = (() => {
      if (!targetServiceKey || targetServiceKey === service.service_key) return service.id;
      const target = (s.diagnosticsTargets || []).find((item) => item.service_key === targetServiceKey);
      if (target?.service_id) return target.service_id;
      const t = s.services.find((item) => item.node_id === service.node_id && item.service_key === targetServiceKey);
      return t?.id ?? service.id;
    })();
    if (source === "container_history" || source === "file_history") {
      const page = options?.page ?? s.historyPage;
      const params2 = new URLSearchParams({
        page: String(page),
        page_size: String(s.historyPageSize || 100)
      });
      if (s.historyStart) params2.set("start", new Date(s.historyStart).toISOString());
      if (s.historyEnd) params2.set("end", new Date(s.historyEnd).toISOString());
      const hasCursor = options && Object.prototype.hasOwnProperty.call(options, "cursor");
      const cursor = hasCursor ? options.cursor : s.historyCursor;
      if (cursor !== undefined && cursor !== null && cursor !== "") params2.set("cursor", String(cursor));
      const filePath = s.diagFilePath || s.diagnostics?.readiness?.paths_checked?.[0]?.path || "";
      const path = source === "container_history" ? `/api/services/${targetId}/diagnostics/container-history?${params2}` : `/api/services/${targetId}/diagnostics/file-history?${params2}${filePath ? `&log_path=${encodeURIComponent(filePath)}` : ""}`;
      try {
        const hist = await api(path);
        if (requestSequence !== diagnosticsRequestSequence) return;
        const lines = (hist.lines || hist.entries || []).map(
          (l) => typeof l === "string" ? { message: l, level: "INFO", timestamp: (/* @__PURE__ */ new Date()).toISOString() } : l
        );
        const historyError = hist.error || null;
        s.setDiagnosticsLive({
          lines,
          source_state: source,
          next_cursor: hist.next_cursor ?? null,
          previous_cursor: hist.previous_cursor ?? null,
          total_available: hist.total_count ?? hist.total ?? lines.length,
          error: historyError,
          poll_interval_ms: s.logsPollMs
        });
        s.setHistoryTotalPages(hist.total_pages || hist.history_total_pages || 0);
        s.setHistoryCursor(historyCursorValue(hist.next_cursor));
        s.setHistoryPreviousCursor?.(historyCursorValue(hist.previous_cursor));
        if (!options?.silent) s.setNotice(historyError ? `${source}: ${historyError}` : `Loaded ${lines.length} history lines (${source})`);
      } catch (e) {
        if (!options?.silent) s.setNotice(e?.message || "History query failed");
        s.setDiagnosticsLive({ lines: [], source_state: source, next_cursor: null, previous_cursor: null, total_available: 0, poll_interval_ms: s.logsPollMs });
        s.setHistoryCursor("");
        s.setHistoryPreviousCursor?.("");
      }
      return;
    }
    if (source === "file_live") {
      const logPath = s.diagFilePath || s.diagnostics?.readiness?.paths_checked?.find((p) => p.readable)?.path || s.diagnostics?.readiness?.paths_checked?.[0]?.path || "";
      if (!logPath) {
        s.setDiagnosticsLive({ lines: [], source_state: "file_live", next_cursor: 0, total_available: 0, poll_interval_ms: s.logsPollMs });
        if (!options?.silent) s.setNotice("No file log paths configured for this service");
        return;
      }
      try {
        const data = await api(`/api/services/${targetId}/diagnostics/file-tail?log_path=${encodeURIComponent(logPath)}&tail_lines=${s.tailLines}`);
        if (requestSequence !== diagnosticsRequestSequence) return;
        const lines = (data.lines || data.entries || []).map(
          (l) => typeof l === "string" ? { message: l, level: "INFO", timestamp: (/* @__PURE__ */ new Date()).toISOString() } : l
        );
        s.setDiagnosticsLive({ lines, source_state: "file_live", next_cursor: lines.length, total_available: lines.length, error: data.error || null, poll_interval_ms: s.logsPollMs });
        if (!options?.silent) s.setNotice(data.error ? `File live: ${data.error}` : `File live: ${lines.length} lines from ${logPath}`);
      } catch (e) {
        if (!options?.silent) s.setNotice(e?.message || "File tail failed");
      }
      return;
    }
    const cursor = options?.cursor ?? 0;
    const params = new URLSearchParams({
      tail_lines: String(s.tailLines),
      page_size: String(s.historyPageSize),
      cursor: String(cursor)
    });
    if (targetServiceKey) params.set("target_service_key", targetServiceKey);
    const next = await api(`/api/services/${service.id}/diagnostics/live?${params.toString()}`);
    if (requestSequence !== diagnosticsRequestSequence) return;
    if (!options?.silent) {
      s.setNotice(
        next.error
          ? `Diagnostics unavailable: ${next.error}`
          : `Diagnostics ${next.source_state}: ${next.lines.length} lines \xB7 showing ${next.next_cursor}/${next.total_available}`
      );
    }
    s.setLogsPollMs(next.poll_interval_ms);
    if (options?.append && s.diagnosticsLive) {
      s.setDiagnosticsLive({
        ...next,
        lines: [...s.diagnosticsLive.lines, ...next.lines]
      });
      return;
    }
    s.setDiagnosticsLive(next);
  },

  async bulkDownloadArchives() {
    if (!s.selectedService || s.selectedArchiveIds.length === 0) {
      s.setNotice("Select one or more archives to download");
      return;
    }
    const sourceService = s.services.find((s) => s.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    const targetKey = s.diagnostics?.target_service_key ?? s.diagnosticsTargetKey;
    const target = targetKey
      ? (s.diagnosticsTargets || []).find((item) => item.service_key === targetKey)
        ?? s.services.find((item) => item.node_id === sourceService.node_id && item.service_key === targetKey)
      : sourceService;
    const sid = target?.service_id ?? target?.id ?? sourceService.id;
    try {
      const blob = await apiBlob(`/api/services/${sid}/diagnostics/archives/bulk-download`, {
        method: "POST",
        body: JSON.stringify({ archive_ids: s.selectedArchiveIds })
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `archives-${sid}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      s.setNotice(`Downloaded ${s.selectedArchiveIds.length} archives`);
    } catch (e) {
      s.setNotice(e?.message || "Bulk download failed");
    }
  },

  async downloadArchive(archiveId) {
    if (!s.selectedService) return;
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    const targetKey = s.diagnostics?.target_service_key ?? s.diagnosticsTargetKey;
    const target = targetKey
      ? (s.diagnosticsTargets || []).find((item) => item.service_key === targetKey)
        ?? s.services.find((service) => service.node_id === sourceService.node_id && service.service_key === targetKey)
      : sourceService;
    const sid = target?.service_id ?? target?.id ?? sourceService.id;
    try {
      const blob = await apiBlob(`/api/services/${sid}/diagnostics/archives/${archiveId}/download`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `archive-${archiveId}.log`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      s.setNotice(`Downloaded archive ${archiveId}`);
    } catch (e) {
      s.setNotice(e?.message || "Archive download failed");
    }
  },

  async runLogBackfill() {
    if (!s.selectedService) return;
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    const targetKey = s.diagnostics?.target_service_key ?? s.diagnosticsTargetKey;
    const target = targetKey
      ? (s.diagnosticsTargets || []).find((item) => item.service_key === targetKey)
        ?? s.services.find((service) => service.node_id === sourceService.node_id && service.service_key === targetKey)
      : sourceService;
    const result = await api(`/api/services/${target?.service_id ?? target?.id ?? sourceService.id}/diagnostics/backfill`, {
      method: "POST"
    });
    let terminalJob = result.job;
    s.setJob(terminalJob);
    const terminal = new Set(["success", "failed"]);
    const deadline = Date.now() + 60000;
    while (terminalJob && !terminal.has(terminalJob.status) && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      terminalJob = await api(`/api/jobs/${terminalJob.id}`);
      s.setJob(terminalJob);
    }
    const status = terminalJob?.status || "timeout";
    s.setNotice(`Log backfill job #${result.job.id} ${status}${terminalJob?.error ? `: ${terminalJob.error}` : ""}`);
    await s.loadDiagnostics(sourceService, { targetServiceKey: targetKey, preserveSelection: true });
  },

  async runDiagnosticsInsightAction(action) {
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    if (!sourceService) {
      s.setNotice("Select a service first to run diagnostics actions.");
      return;
    }
    if (action.action_id === "ensure-dependency-cards") {
      await s.ensureMissingDependencyCards();
      return;
    }
    if (action.action_id === "focus-dependency-diagnostics" && action.service_key) {
      s.setActiveView("diagnostics");
      s.setDiagTab("tail");
      await s.focusDiagnosticsTarget(action.service_key);
      return;
    }
    if (action.action_id === "open-config") {
      const matchedService = action.service_key ? s.services.find((item) => item.node_id === sourceService.node_id && item.service_key === action.service_key) : null;
      const targetService = matchedService ?? sourceService;
      s.setSelectedService(targetService);
      await s.loadConfig(targetService, s.configSource);
      s.setActiveView("config");
      return;
    }
    if (action.action_id === "open-release-context") {
      const matchedService = action.service_key ? s.services.find((item) => item.node_id === sourceService.node_id && item.service_key === action.service_key) : null;
      const targetService = matchedService ?? sourceService;
      s.setSelectedService(targetService);
      await s.loadServiceCapabilities(targetService.id);
      await s.loadServiceSummary(targetService.id);
      await s.loadServiceReleaseTimeline(targetService.id);
      await s.loadServiceMetrics(targetService.id);
      if (targetService.node_id !== s.selectedNode?.id) {
        const targetNode = s.nodes.find((item) => item.id === targetService.node_id);
        if (targetNode) {
          await s.selectNode(targetNode);
        }
      }
      s.setActiveView("clusters");
      s.setNotice(`Opened release context for ${targetService.name}.`);
      return;
    }
    if (action.action_id === "open-existing-incident" && action.incident_id) {
      s.setActiveView("monitoring");
      s.setNotice(`Review incident #${action.incident_id} in the monitoring panel.`);
      return;
    }
    if (action.action_id === "run-incident-runbook" && action.incident_id && action.runbook_key) {
      const incident = s.incidents.find((item) => item.id === action.incident_id);
      if (incident) {
        await s.runIncidentRunbook(incident, action.runbook_key);
      } else {
        const runbook = await api(`/api/incidents/${action.incident_id}/runbook/${action.runbook_key}`, {
          method: "POST"
        });
        s.setRunbooks((current) => [runbook, ...current]);
        s.setNotice(`Runbook ${runbook.runbook_key} ${runbook.status}`);
        await s.refresh();
      }
      s.setActiveView("monitoring");
      return;
    }
    if (action.action_id === "open-incident") {
      await s.openIncident(sourceService);
      s.setActiveView("monitoring");
      return;
    }
    s.setActiveView("diagnostics");
    s.setDiagTab(action.target_view === "files" ? "files" : "tail");
    if (action.service_key && action.service_key !== s.diagnosticsTargetKey) {
      await s.focusDiagnosticsTarget(action.service_key);
      return;
    }
    await s.loadDiagnostics(sourceService, { targetServiceKey: action.service_key ?? s.diagnosticsTargetKey, preserveSelection: true });
  },

  async openDiagnosticsSupportingEvidence(evidence) {
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    if (!sourceService) {
      s.setNotice("Select a service first to open supporting evidence.");
      return;
    }
    if (evidence.target_view === "release") {
      await s.runDiagnosticsInsightAction({
        action_id: "open-release-context",
        label: evidence.label,
        description: evidence.summary,
        service_key: sourceService.service_key,
        incident_id: null,
        runbook_key: null,
        target_view: "clusters",
        recommended: false
      });
      return;
    }
    if (evidence.target_view === "monitoring" && evidence.incident_id) {
      await s.runDiagnosticsInsightAction({
        action_id: "open-existing-incident",
        label: evidence.label,
        description: evidence.summary,
        service_key: s.diagnosticsAnalysis?.source_service_key ?? sourceService.service_key,
        incident_id: evidence.incident_id,
        runbook_key: null,
        target_view: "monitoring",
        recommended: false
      });
      return;
    }
    if (evidence.target_view === "config-compare" || evidence.target_view === "config-timeline") {
      await s.loadConfig(sourceService, s.configSource);
      s.setActiveView("config");
      if (evidence.target_view === "config-compare") {
        s.setConfigTab("compare");
        const leftSnapshotId = evidence.compare_left_snapshot_id ?? evidence.baseline_snapshot_id ?? null;
        const rightSnapshotId = evidence.compare_right_snapshot_id ?? null;
        if (leftSnapshotId && rightSnapshotId) {
          await s.compareSpecificSnapshots(sourceService, leftSnapshotId, rightSnapshotId);
        } else {
          s.setCompareSnapshotLeft(leftSnapshotId);
          s.setCompareSnapshotRight(rightSnapshotId);
          s.setNotice(`Opened compare context for ${evidence.label}.`);
        }
      } else {
        s.setConfigTab("timeline");
        s.setNotice(`Opened timeline context for ${evidence.label}.`);
      }
      return;
    }
    if (evidence.target_view === "files") {
      s.setActiveView("diagnostics");
      s.setDiagTab("files");
      await s.loadDiagnostics(sourceService, {
        targetServiceKey: evidence.service_key ?? s.diagnosticsTargetKey,
        preserveSelection: true
      });
      return;
    }
    s.setActiveView("diagnostics");
    s.setDiagTab("tail");
    if (evidence.service_key && evidence.service_key !== s.diagnosticsTargetKey) {
      await s.focusDiagnosticsTarget(evidence.service_key);
      return;
    }
    await s.loadDiagnostics(sourceService, {
      targetServiceKey: evidence.service_key ?? s.diagnosticsTargetKey,
      preserveSelection: true
    });
  },

  async openDiagnosticsChangeEvidence(evidence) {
    const sourceService = s.services.find((service) => service.id === s.diagnosticsSourceServiceId) ?? s.selectedService;
    if (!sourceService) {
      s.setNotice("Select a service first to open evidence context.");
      return;
    }
    if (evidence.target_view === "release") {
      await s.runDiagnosticsInsightAction({
        action_id: "open-release-context",
        label: "Review release timeline",
        description: evidence.summary,
        service_key: sourceService.service_key,
        incident_id: null,
        runbook_key: null,
        target_view: "clusters",
        recommended: false
      });
      return;
    }
    await s.loadConfig(sourceService, s.configSource);
    if (evidence.target_view === "config-compare") {
      s.setConfigTab("compare");
      const leftSnapshotId = evidence.compare_left_snapshot_id ?? evidence.baseline_snapshot_id ?? null;
      const rightSnapshotId = evidence.compare_right_snapshot_id ?? (s.snapshotPage?.items?.[0]?.id && s.snapshotPage.items[0].id !== leftSnapshotId ? s.snapshotPage.items[0].id : null);
      if (leftSnapshotId && rightSnapshotId) {
        await s.compareSpecificSnapshots(sourceService, leftSnapshotId, rightSnapshotId);
      } else {
        s.setCompareSnapshotLeft(leftSnapshotId);
        s.setCompareSnapshotRight(rightSnapshotId);
        s.setNotice("Opened config compare context from diagnostics evidence.");
      }
    } else {
      s.setConfigTab("timeline");
      s.setNotice("Opened config timeline context from diagnostics evidence.");
    }
    s.setActiveView("config");
  },

  async runLogAnalystChat(question) {
    const q = (question || "").trim();
    if (!q) return;
    if (!s.selectedService) {
      s.setAnalyticsMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "Select a service from the diagnostics tree first. Log Analyst needs a real service context.",
          timestamp: (/* @__PURE__ */ new Date()).toLocaleTimeString(),
          error: "no service selected"
        }
      ]);
      return;
    }
    const timestamp = (/* @__PURE__ */ new Date()).toLocaleTimeString();
    s.setAnalyticsMessages((prev) => [...prev, { sender: "user", text: q, timestamp }]);
    s.setAnalyticsBusy(true);
    try {
      const prior = s.analyticsMessages.slice(-12).map((m) => ({
        role: m.sender === "user" ? "user" : "assistant",
        content: m.text
      }));
      const result = await api(`/api/services/${s.selectedService.id}/diagnostics/chat`, {
        method: "POST",
        body: JSON.stringify({
          question: q,
          window: "current",
          history: prior
        })
      });
      if (!result.success) {
        s.setAnalyticsMessages((prev) => [
          ...prev,
          {
            sender: "assistant",
            text: result.answer || result.error || "Log Analyst could not complete this request.",
            timestamp: (/* @__PURE__ */ new Date()).toLocaleTimeString(),
            evidence: result.evidence || [],
            chart_data: result.chart_data || [],
            suggestions: result.suggestions || [],
            error: result.error || "request failed",
            analyst_source: result.provider || "deterministic fallback"
          }
        ]);
      } else {
        s.setAnalyticsMessages((prev) => [
          ...prev,
          {
            sender: "assistant",
            text: result.answer || "No response generated.",
            timestamp: (/* @__PURE__ */ new Date()).toLocaleTimeString(),
            evidence: result.evidence || [],
            chart_data: result.chart_data || [],
            suggestions: result.suggestions || [],
            analyst_source: result.provider || "deterministic fallback"
          }
        ]);
      }
    } catch (e) {
      s.setAnalyticsMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "",
          timestamp: (/* @__PURE__ */ new Date()).toLocaleTimeString(),
          error: e?.message || "Log Analyst request failed"
        }
      ]);
    } finally {
      s.setAnalyticsBusy(false);
    }
  },

  sendDirectAnalyticsQuery(query) {
    void s.runLogAnalystChat(query);
  },

  handleSendAnalyticsChat() {
    if (!s.analyticsInput.trim() || s.analyticsBusy) return;
    const userMsg = s.analyticsInput.trim();
    s.setAnalyticsInput("");
    void s.runLogAnalystChat(userMsg);
  }
  };
}
