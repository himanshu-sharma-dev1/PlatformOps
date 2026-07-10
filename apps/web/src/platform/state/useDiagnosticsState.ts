// @ts-nocheck
import { useState } from "react";
export function useDiagnosticsState() {
  const [diagnostics, setDiagnostics] = useState(null as any);
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState(null as any);
  const [diagnosticsLive, setDiagnosticsLive] = useState(null as any);
  const [tailLines, setTailLines] = useState(150 as any);
  const [historyPageSize, setHistoryPageSize] = useState(100 as any);
  const [logsPollMs, setLogsPollMs] = useState(2500 as any);
  const [autoPollLogs, setAutoPollLogs] = useState(false as any);
  const [diagnosticsTargetKey, setDiagnosticsTargetKey] = useState("" as any);
  const [diagnosticsTargets, setDiagnosticsTargets] = useState([] as any);
  const [diagFilePath, setDiagFilePath] = useState("" as any);
  const [diagnosticsSourceServiceId, setDiagnosticsSourceServiceId] = useState(null as any);
  const [archives, setArchives] = useState([] as any);
  const [ingestionStats, setIngestionStats] = useState(null as any);
  const [archiveGzipOnly, setArchiveGzipOnly] = useState(false as any);
  const [archivePreviewLines, setArchivePreviewLines] = useState([] as any);
  const [archivePreviewLoading, setArchivePreviewLoading] = useState(false as any);
  const [diagLogSource, setDiagLogSource] = useState("container_live" as any);
  const [logLevelFilters, setLogLevelFilters] = useState({ INFO: true, WARN: true, ERROR: true, DEBUG: true } as any);
  const [logSearchQuery, setLogSearchQuery] = useState("" as any);
  const [logAutoScroll, setLogAutoScroll] = useState(true as any);
  const [selectedArchiveIds, setSelectedArchiveIds] = useState([] as any);
  const [historyPage, setHistoryPage] = useState(1 as any);
  const [historyCursor, setHistoryCursor] = useState("" as any);
  const [historyTotalPages, setHistoryTotalPages] = useState(0 as any);
  const [diagTab, setDiagTab] = useState("summary" as any);
  const [selectedArchive, setSelectedArchive] = useState(null as any);
  return {
    diagnostics, setDiagnostics,
    diagnosticsAnalysis, setDiagnosticsAnalysis,
    diagnosticsLive, setDiagnosticsLive,
    tailLines, setTailLines,
    historyPageSize, setHistoryPageSize,
    logsPollMs, setLogsPollMs,
    autoPollLogs, setAutoPollLogs,
    diagnosticsTargetKey, setDiagnosticsTargetKey,
    diagnosticsTargets, setDiagnosticsTargets,
    diagFilePath, setDiagFilePath,
    diagnosticsSourceServiceId, setDiagnosticsSourceServiceId,
    archives, setArchives,
    ingestionStats, setIngestionStats,
    archiveGzipOnly, setArchiveGzipOnly,
    archivePreviewLines, setArchivePreviewLines,
    archivePreviewLoading, setArchivePreviewLoading,
    diagLogSource, setDiagLogSource,
    logLevelFilters, setLogLevelFilters,
    logSearchQuery, setLogSearchQuery,
    logAutoScroll, setLogAutoScroll,
    selectedArchiveIds, setSelectedArchiveIds,
    historyPage, setHistoryPage,
    historyCursor, setHistoryCursor,
    historyTotalPages, setHistoryTotalPages,
    diagTab, setDiagTab,
    selectedArchive, setSelectedArchive,
  };
}
