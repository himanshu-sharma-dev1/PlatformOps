import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderAuditView). */
export function AuditView() {
  const p = usePlatform();
  if (typeof (p as any).renderAuditView !== "function") {
    return <div className="notice">View {'AuditView'} is unavailable.</div>;
  }
  return <>{(p as any).renderAuditView()}</>;
}
