import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderPolicyView). */
export function PolicyView() {
  const p = usePlatform();
  if (typeof (p as any).renderPolicyView !== "function") {
    return <div className="notice">View {'PolicyView'} is unavailable.</div>;
  }
  return <>{(p as any).renderPolicyView()}</>;
}
