// @ts-nocheck
import { useState } from "react";
export function useMonitoringState() {
  const [monitoringSubTab, setMonitoringSubTab] = useState("glitchtip" as any);
  const [gtIssues, setGtIssues] = useState([] as any);
  const [gtSelectedIssueId, setGtSelectedIssueId] = useState(null as any);
  const [gtEventDetails, setGtEventDetails] = useState(null as any);
  const [gtUptimeMonitors, setGtUptimeMonitors] = useState([] as any);
  const [gtKeys, setGtKeys] = useState([] as any);
  const [gtTransactions, setGtTransactions] = useState([] as any);
  const [gtIntegrationStatus, setGtIntegrationStatus] = useState(null as any);
  const [gtActiveMonitorTab, setGtActiveMonitorTab] = useState("issues" as any);
  const [gtWindow, setGtWindow] = useState("24h" as any);
  const [gtAutoRefresh, setGtAutoRefresh] = useState(false as any);
  const [gtSdkLang, setGtSdkLang] = useState("python" as any);
  const [txSort, setTxSort] = useState("latency" as any);
  const [gtIssuesCursor, setGtIssuesCursor] = useState(null as any);
  const [gtIssuesHasMore, setGtIssuesHasMore] = useState(false as any);
  return {
    monitoringSubTab, setMonitoringSubTab,
    gtIssues, setGtIssues,
    gtSelectedIssueId, setGtSelectedIssueId,
    gtEventDetails, setGtEventDetails,
    gtUptimeMonitors, setGtUptimeMonitors,
    gtKeys, setGtKeys,
    gtTransactions, setGtTransactions,
    gtIntegrationStatus, setGtIntegrationStatus,
    gtActiveMonitorTab, setGtActiveMonitorTab,
    gtWindow, setGtWindow,
    gtAutoRefresh, setGtAutoRefresh,
    gtSdkLang, setGtSdkLang,
    txSort, setTxSort,
    gtIssuesCursor, setGtIssuesCursor,
    gtIssuesHasMore, setGtIssuesHasMore,
  };
}
