import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderObservabilityStackView). */
export function ObservabilityView() {
  const p = usePlatform();
  if (typeof (p as any).renderObservabilityStackView !== "function") {
    return <div className="notice">View {'ObservabilityView'} is unavailable.</div>;
  }
  return <>{(p as any).renderObservabilityStackView()}</>;
}
