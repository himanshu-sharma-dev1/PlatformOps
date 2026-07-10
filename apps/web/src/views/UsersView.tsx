import React from "react";
import { usePlatform } from "../platform/usePlatform";

/** Page module — delegates to platform controller (renderUsersView). */
export function UsersView() {
  const p = usePlatform();
  if (typeof (p as any).renderUsersView !== "function") {
    return <div className="notice">View {'UsersView'} is unavailable.</div>;
  }
  return <>{(p as any).renderUsersView()}</>;
}
