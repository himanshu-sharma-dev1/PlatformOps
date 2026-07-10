import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderConfigManagerView). */
export function ConfigView() {
  const p = usePlatform();
  if (typeof (p as any).renderConfigManagerView !== "function") {
    return <div className="notice">View {'ConfigView'} is unavailable.</div>;
  }
  return <>{(p as any).renderConfigManagerView()}</>;
}
