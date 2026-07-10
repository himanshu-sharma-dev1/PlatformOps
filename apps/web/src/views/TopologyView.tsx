import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderTopologyView). */
export function TopologyView() {
  const p = usePlatform();
  if (typeof (p as any).renderTopologyView !== "function") {
    return <div className="notice">View {'TopologyView'} is unavailable.</div>;
  }
  return <>{(p as any).renderTopologyView()}</>;
}
