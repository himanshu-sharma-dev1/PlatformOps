import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderDrawers). */
export function DrawersHost() {
  const p = usePlatform();
  if (typeof (p as any).renderDrawers !== "function") {
    return <div className="notice">View {'DrawersHost'} is unavailable.</div>;
  }
  return <>{(p as any).renderDrawers()}</>;
}
