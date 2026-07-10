import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderDiagnosticsView). */
export function DiagnosticsView() {
  const p = usePlatform();
  if (typeof (p as any).renderDiagnosticsView !== "function") {
    return <div className="notice">View {'DiagnosticsView'} is unavailable.</div>;
  }
  return <>{(p as any).renderDiagnosticsView()}</>;
}
