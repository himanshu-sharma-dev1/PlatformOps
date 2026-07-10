// @ts-nocheck
import { useState } from "react";
export function usePerformanceState() {
  const [serviceMetrics, setServiceMetrics] = useState(null as any);
  const [serviceMetricsWindow, setServiceMetricsWindow] = useState("1h" as any);
  const [realtimeNodeMetrics, setRealtimeNodeMetrics] = useState(null as any);
  const [processMetrics, setProcessMetrics] = useState([] as any);
  const [perfProcessSort, setPerfProcessSort] = useState("cpu" as any);
  const [loadingMetrics, setLoadingMetrics] = useState(false as any);
  const [perfAutoRefresh, setPerfAutoRefresh] = useState(false as any);
  const [nodeMetrics, setNodeMetrics] = useState(null as any);
  const [nodeMetricsWindow, setNodeMetricsWindow] = useState("1h" as any);
  return {
    serviceMetrics, setServiceMetrics,
    serviceMetricsWindow, setServiceMetricsWindow,
    realtimeNodeMetrics, setRealtimeNodeMetrics,
    processMetrics, setProcessMetrics,
    perfProcessSort, setPerfProcessSort,
    loadingMetrics, setLoadingMetrics,
    perfAutoRefresh, setPerfAutoRefresh,
    nodeMetrics, setNodeMetrics,
    nodeMetricsWindow, setNodeMetricsWindow,
  };
}
