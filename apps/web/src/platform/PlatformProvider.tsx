import React from "react";
import { PlatformContext } from "./context";
import { usePlatformController } from "./usePlatformController";

export function PlatformProvider({ children }: { children?: React.ReactNode }) {
  const platformApi = usePlatformController();
  return (
    <PlatformContext.Provider value={platformApi}>
      {children}
    </PlatformContext.Provider>
  );
}

export { usePlatform } from "./context";
export type { PlatformApi } from "./context";
