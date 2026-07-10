// @ts-nocheck
import { useCallback, useEffect, useRef, useState } from "react";

/** cPlatform-style toast: kind + auto-dismiss. setNotice stays compatible. */
export function useUiState() {
  const [liveStatusTick, setLiveStatusTick] = useState(0 as any);
  const [uptimeFormVisible, setUptimeFormVisible] = useState(false as any);
  const [uptimeForm, setUptimeForm] = useState({ name: "", monitor_type: "Ping", url: "", interval: 60, expected_status: 200 } as any);
  const [notice, setNoticeRaw] = useState("" as any);
  const [toast, setToast] = useState(null as any);
  const toastTimer = useRef(null as any);

  const dismissToast = useCallback(() => {
    if (toastTimer.current) {
      clearTimeout(toastTimer.current);
      toastTimer.current = null;
    }
    setToast(null);
    setNoticeRaw("");
  }, []);

  const showToast = useCallback((message: string, kind: "ok" | "err" | "warn" = "ok", ttlMs = 3200) => {
    const msg = String(message || "").trim();
    if (!msg) {
      dismissToast();
      return;
    }
    if (toastTimer.current) {
      clearTimeout(toastTimer.current);
      toastTimer.current = null;
    }
    const entry = { message: msg, kind, id: Date.now() };
    setToast(entry);
    setNoticeRaw(msg);
    if (ttlMs > 0) {
      toastTimer.current = setTimeout(() => {
        setToast((current) => (current && current.id === entry.id ? null : current));
        setNoticeRaw((current) => (current === msg ? "" : current));
        toastTimer.current = null;
      }, ttlMs);
    }
  }, [dismissToast]);

  const setNotice = useCallback((messageOrUpdater: any) => {
    if (typeof messageOrUpdater === "function") {
      setNoticeRaw((prev) => {
        const next = messageOrUpdater(prev);
        const msg = String(next || "").trim();
        if (!msg) {
          setToast(null);
          return "";
        }
        const kind = /fail|error|denied|blocked|invalid|not found|refused/i.test(msg)
          ? "err"
          : /warn|assessing|loading|discovering|running|queued|…|pending/i.test(msg)
            ? "warn"
            : "ok";
        setToast({ message: msg, kind, id: Date.now() });
        return msg;
      });
      return;
    }
    const msg = String(messageOrUpdater || "").trim();
    if (!msg) {
      dismissToast();
      return;
    }
    const kind = /fail|error|denied|blocked|invalid|not found|refused/i.test(msg)
      ? "err"
      : /warn|assessing|loading|discovering|running|queued|…|pending/i.test(msg)
        ? "warn"
        : "ok";
    showToast(msg, kind as any);
  }, [dismissToast, showToast]);

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  const [eventCategoryFilter, setEventCategoryFilter] = useState("all" as any);
  const [eventLevelFilter, setEventLevelFilter] = useState("all" as any);
  const [eventSearch, setEventSearch] = useState("" as any);
  const [eventLimit, setEventLimit] = useState(120 as any);
  const [deleteModal, setDeleteModal] = useState({
    visible: false,
    targetType: "service",
    targetId: 0,
    targetName: "",
    impact: null,
    force: false,
    forceReason: "",
    forceApprovalId: "",
    requestedBy: "platform-operator",
    approver: "platform-admin",
    decisionNote: "",
    approvalStatus: "none",
  } as any);
  const [renameModal, setRenameModal] = useState({
    visible: false,
    snapshotId: 0,
    value: "",
    error: "",
  } as any);
  const [releaseApprovalModal, setReleaseApprovalModal] = useState({
    visible: false,
    serviceId: 0,
    serviceName: "",
    version: "",
    image: "",
    safety: null,
    reason: "",
    requestedBy: "platform-operator",
    approvalId: "",
    approver: "platform-admin",
    decisionNote: "",
    error: "",
  } as any);
  const [deploymentModal, setDeploymentModal] = useState({
    visible: false,
    serviceId: null,
    serviceName: "",
    nodeName: "",
    preflight: null,
    autoInstallDependencies: true,
    loading: false,
    executing: false,
    error: "",
    result: null,
  } as any);
  const [analyticsMessages, setAnalyticsMessages] = useState([
    {
      sender: "assistant",
      text: "Hello! I am Iktara Log Analyst. Select a service, then ask about log anomalies, restarts, dependency failures, or deployment errors. Answers come from live logs + LLM (Groq/Mistral) — never synthetic metrics.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ] as any);
  const [analyticsInput, setAnalyticsInput] = useState("" as any);
  const [analyticsBusy, setAnalyticsBusy] = useState(false as any);
  const [llmStatus, setLlmStatus] = useState(null as any);
  const [stepperDrawerVisible, setStepperDrawerVisible] = useState(false as any);
  const [stepperStep, setStepperStep] = useState(1 as any);
  const [catalogDrawerVisible, setCatalogDrawerVisible] = useState(false as any);
  const [treeSearchQuery, setTreeSearchQuery] = useState("" as any);
  const [nodeSearchQuery, setNodeSearchQuery] = useState("" as any);
  const [activeView, setActiveView] = useState("clusters" as any);
  return {
    liveStatusTick, setLiveStatusTick,
    uptimeFormVisible, setUptimeFormVisible,
    uptimeForm, setUptimeForm,
    notice, setNotice,
    toast, setToast,
    showToast, dismissToast,
    eventCategoryFilter, setEventCategoryFilter,
    eventLevelFilter, setEventLevelFilter,
    eventSearch, setEventSearch,
    eventLimit, setEventLimit,
    deleteModal, setDeleteModal,
    renameModal, setRenameModal,
    releaseApprovalModal, setReleaseApprovalModal,
    deploymentModal, setDeploymentModal,
    analyticsMessages, setAnalyticsMessages,
    analyticsInput, setAnalyticsInput,
    analyticsBusy, setAnalyticsBusy,
    llmStatus, setLlmStatus,
    stepperDrawerVisible, setStepperDrawerVisible,
    stepperStep, setStepperStep,
    catalogDrawerVisible, setCatalogDrawerVisible,
    treeSearchQuery, setTreeSearchQuery,
    nodeSearchQuery, setNodeSearchQuery,
    activeView, setActiveView,
  };
}
