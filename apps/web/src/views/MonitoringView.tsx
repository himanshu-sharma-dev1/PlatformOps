import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderMonitoringView). */
export function MonitoringView() {
  const p = usePlatform();
  if (typeof (p as any).renderMonitoringView !== "function") {
    return <div className="notice">View {'MonitoringView'} is unavailable.</div>;
  }
  return <>{(p as any).renderMonitoringView()}</>;
}
