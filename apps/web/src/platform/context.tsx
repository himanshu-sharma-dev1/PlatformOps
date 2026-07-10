import React, { createContext, useContext } from "react";

export type PlatformApi = any;

export const PlatformContext = createContext<PlatformApi | null>(null);

export function usePlatform(): PlatformApi {
  const ctx = useContext(PlatformContext);
  if (!ctx) throw new Error("usePlatform requires PlatformProvider");
  return ctx;
}
