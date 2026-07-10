#!/usr/bin/env python3
"""Phase 2: PlatformProvider -> context + usePlatformController + thin provider."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "platform"


def main() -> None:
    src_path = ROOT / "PlatformProvider.tsx"
    src = src_path.read_text()

    (ROOT / "context.tsx").write_text(
        '''import React, { createContext, useContext } from "react";

export type PlatformApi = any;

export const PlatformContext = createContext<PlatformApi | null>(null);

export function usePlatform(): PlatformApi {
  const ctx = useContext(PlatformContext);
  if (!ctx) throw new Error("usePlatform requires PlatformProvider");
  return ctx;
}
'''
    )

    # Ensure PlatformApi type is available without local definition
    full = src
    full = re.sub(
        r"export type PlatformApi = any;\s*\nconst PlatformContext = createContext<PlatformApi \| null>\(null\);\s*\n+",
        'import type { PlatformApi } from "./context";\n\n',
        full,
        count=1,
    )
    full = re.sub(
        r"export type PlatformApi = any;\s*\n+",
        'import type { PlatformApi } from "./context";\n\n',
        full,
        count=1,
    )
    # Remove createContext/useContext from React import if present
    full = full.replace(", createContext, useContext", "")
    full = full.replace("createContext, useContext, ", "")
    full = full.replace("createContext, ", "")
    full = full.replace(", useContext", "")

    # Remove trailing usePlatform export (lives in context now)
    full = re.sub(
        r"\nexport function usePlatform\(\): PlatformApi \{[\s\S]*?\n\}\s*$",
        "\n",
        full,
    )

    # Convert PlatformProvider function into usePlatformController
    full = re.sub(
        r"export function PlatformProvider\(\{ children \}: \{ children\?: React\.ReactNode \}\) \{",
        "export function usePlatformController() {",
        full,
        count=1,
    )

    # Replace JSX provider return with return platformApi
    full = re.sub(
        r"  return \(\s*<PlatformContext\.Provider value=\{platformApi\}>\s*\{children\}\s*</PlatformContext\.Provider>\s*\);\s*\}",
        "  return platformApi;\n}\n",
        full,
        count=1,
    )

    # If PlatformContext still referenced, remove import of it from controller
    full = full.replace(
        'import { PlatformContext, type PlatformApi } from "./context";\n',
        'import type { PlatformApi } from "./context";\n',
    )

    if "from \"./context\"" not in full and "PlatformApi" in full:
        full = full.replace(
            "import React,",
            'import type { PlatformApi } from "./context";\nimport React,',
            1,
        )

    # Domain hook facades (composition helpers for readability / future splits)
    hooks_dir = ROOT / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "index.ts").write_text(
        '''/**
 * Phase 2 domain hooks.
 * Today the controller is still composed in usePlatformController for call-site stability.
 * These modules document seams and re-export slices for progressive extraction.
 */
export { usePlatformController as useOpsController } from "../usePlatformController";
'''
    )

    # Slice documentation hooks (thin wrappers around full controller for naming)
    for name, keys_doc in [
        ("useAuthSession", "authUser, loginForm, handleLogin, handleLogout, authReady"),
        ("useInventory", "clusters, nodes, services, refresh, selectCluster, selectNode"),
        ("useConfigWorkspace", "config, loadConfig, applyCurrentConfig, configTab"),
        ("useDiagnostics", "diagnostics, loadDiagnostics, diagnosticsLive, diagTab"),
        ("useMonitoring", "gtIssues, loadGlitchTipDataForService, gtActiveMonitorTab"),
        ("useSreAdvanced", "topology, findings, slos, incidents, maintenance"),
        ("useUiChrome", "notice, drawers/modals visibility flags"),
    ]:
        (hooks_dir / f"{name}.ts").write_text(
            f'''/**
 * Domain seam: {name}
 * Related controller fields: {keys_doc}
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import {{ usePlatformController }} from "../usePlatformController";

export function {name}() {{
  return usePlatformController();
}}
'''
        )

    (ROOT / "usePlatformController.ts").write_text(full)

    thin = '''import React from "react";
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
'''
    (ROOT / "PlatformProvider.tsx").write_text(thin)
    (ROOT / "usePlatform.ts").write_text(
        '''export { usePlatform, PlatformProvider } from "./PlatformProvider";
export type { PlatformApi } from "./context";
'''
    )

    print("usePlatformController lines", full.count("\n") + 1)
    print("return platformApi", "return platformApi" in full)
    print("usePlatformController fn", "export function usePlatformController" in full)
    print("thin provider written")


if __name__ == "__main__":
    main()
