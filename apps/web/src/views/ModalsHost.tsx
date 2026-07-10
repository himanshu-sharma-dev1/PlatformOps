import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderModals). */
export function ModalsHost() {
  const p = usePlatform();
  if (typeof (p as any).renderModals !== "function") {
    return <div className="notice">View {'ModalsHost'} is unavailable.</div>;
  }
  return <>{(p as any).renderModals()}</>;
}
