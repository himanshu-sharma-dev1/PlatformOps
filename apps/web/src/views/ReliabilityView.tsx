import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderReliabilityView). */
export function ReliabilityView() {
  const p = usePlatform();
  if (typeof (p as any).renderReliabilityView !== "function") {
    return <div className="notice">View {'ReliabilityView'} is unavailable.</div>;
  }
  return <>{(p as any).renderReliabilityView()}</>;
}
