import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderAiChat). */
export function LogAnalystChat() {
  const p = usePlatform();
  if (typeof (p as any).renderAiChat !== "function") {
    return <div className="notice">View {'LogAnalystChat'} is unavailable.</div>;
  }
  return <>{(p as any).renderAiChat()}</>;
}
