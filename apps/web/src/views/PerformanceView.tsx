import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderPerformanceView). */
export function PerformanceView() {
  const p = usePlatform();
  if (typeof (p as any).renderPerformanceView !== "function") {
    return <div className="notice">View {'PerformanceView'} is unavailable.</div>;
  }
  return <>{(p as any).renderPerformanceView()}</>;
}
