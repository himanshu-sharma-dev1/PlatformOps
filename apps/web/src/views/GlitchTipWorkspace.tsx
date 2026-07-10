import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderGlitchTipWorkspace). */
export function GlitchTipWorkspace() {
  const p = usePlatform();
  if (typeof (p as any).renderGlitchTipWorkspace !== "function") {
    return <div className="notice">View {'GlitchTipWorkspace'} is unavailable.</div>;
  }
  return <>{(p as any).renderGlitchTipWorkspace()}</>;
}
