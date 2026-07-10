// @ts-nocheck
import { useState } from "react";
export function useUiState() {
  const [liveStatusTick, setLiveStatusTick] = useState(0 as any);
  const [uptimeFormVisible, setUptimeFormVisible] = useState(false as any);
  const [uptimeForm, setUptimeForm] = useState({ name: "", monitor_type: "Ping", url: "", interval: 60, expected_status: 200 } as any);
  const [notice, setNotice] = useState("" as any);
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
