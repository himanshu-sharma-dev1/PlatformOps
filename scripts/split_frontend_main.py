#!/usr/bin/env python3
"""
Split apps/web/src/main.tsx into:
  types/, api/, components/charts.tsx, platform/PlatformProvider.tsx,
  views/*View.tsx, auth screens, App.tsx, main.tsx entry.

Strategy:
- PlatformProvider holds ALL state + action functions (controller).
- Each former renderX becomes a view component that destructures the full
  controller API from usePlatform() so identifiers keep working.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"
BACKUP = Path("/tmp/platformops_split_backup/main.tsx")


def main() -> None:
    text = BACKUP.read_text() if BACKUP.exists() else (ROOT / "main.tsx").read_text()
    lines = text.splitlines(keepends=True)

    # Locate key anchors
    def find_line(pred):
        for i, l in enumerate(lines):
            if pred(l):
                return i
        return -1

    # Types start after imports; end before AUTH_TOKEN or async function api
    import_end = 0
    for i, l in enumerate(lines):
        if l.startswith("import ") or l.startswith("from ") or l.strip() == 'import "./styles.css";' or 'styles.css' in l:
            import_end = i + 1
        elif import_end and l.strip() and not l.startswith("import") and not l.startswith("//") and "styles" not in l:
            # first non-import content
            if l.startswith("const API") or l.startswith("type ") or l.startswith("const OPERATOR"):
                break

    api_fn = find_line(lambda l: l.startswith("async function api<") or l.startswith("async function api("))
    auth_const = find_line(lambda l: "AUTH_TOKEN_KEY" in l and l.startswith("const "))
    types_start = find_line(lambda l: l.startswith("const API") or l.startswith("type CatalogCard") or l.startswith("const OPERATOR"))
    if types_start < 0:
        types_start = import_end

    # Prefer start of types as first `type ` or `const API`
    for i, l in enumerate(lines):
        if l.startswith("type CatalogCard") or l.startswith("const API ="):
            types_start = i
            break

    charts_start = find_line(lambda l: l.startswith("function renderSVGTimeSeriesChart") or l.startswith("function formatExpiry"))
    app_start = find_line(lambda l: l.startswith("function App(") or l.startswith("function App()"))
    create_root = find_line(lambda l: "createRoot" in l and "render" in l)

    if min(api_fn, charts_start, app_start, create_root) < 0:
        raise SystemExit(f"anchors missing api={api_fn} charts={charts_start} app={app_start} root={create_root}")

    # Slice regions (using backup structure):
    # [0:types_start) may include imports only if types_start after imports
    # types: from types_start to auth_const or api helpers before charts
    # Actually structure:
    # imports
    # API const + types + AUTH helpers + api() + more types + helpers formatExpiry + charts + App + createRoot

    pre_app = "".join(lines[:app_start])
    app_block = "".join(lines[app_start:create_root])
    # createRoot line at end

    # --- Extract types + api into modules via regex regions ---
    # Write types/index.ts: everything that is `type X` / `const API` until charts, excluding functions getAuthToken/api if we put those in api/

    # Simpler reliable approach used here:
    # 1) platform/controller.tsx contains: all pre-App helpers that views need + full App as PlatformProvider
    # 2) views import usePlatform
    # 3) entry slim

    # Convert App to PlatformProvider
    app_src = app_block
    # function App() { ... }  -> export function PlatformProvider({ children }: { children?: React.ReactNode }) {
    app_src = re.sub(
        r"^function App\(\)\s*\{",
        "export function PlatformProvider({ children }: { children?: React.ReactNode }) {",
        app_src,
        count=1,
        flags=re.M,
    )

    # Find render function names inside App
    render_names = re.findall(r"\n  function (render\w+)\(", app_src)
    print("render methods:", render_names)

    # Collect identifiers for context: useState names and inner functions
    state_names = re.findall(r"const \[(\w+), (set\w+)\] = useState", app_src)
    fn_names = re.findall(r"\n  (?:async )?function (\w+)\(", app_src)
    # also const callbacks? skip

    # Build context value at end of provider before closing - need to inject before final return of App
    # Original App ends with return ( <Layout>... )
    # We'll change final return to provide context wrapping children OR return children after setting value

    # Strategy change: PlatformProvider computes everything, then:
    # return <PlatformContext.Provider value={api}>{children}</PlatformContext.Provider>
    # And extract the big return JSX into AppShell inside views/AppShell.tsx using usePlatform

    # Find the final `  return (` of App (last one at indent 2)
    returns = [m.start() for m in re.finditer(r"\n  return \(", app_src)]
    if not returns:
        raise SystemExit("no return in App")
    last_ret = returns[-1]
    # From last_ret to matching close before final `}\n` of function
    # Replace final return block with context provider return
    # Keep the old return body as export function AppShell in another file

    final_return_body = app_src[last_ret:]  # includes `  return (` ... `  }\n` maybe extra
    # Trim trailing function close
    # app_src ends with `}\n\n` for function App
    # final_return_body should end at last `  )\n  }\n` of App function

    # Split: provider_core without final return; shell = final return converted
    provider_core = app_src[:last_ret]

    # Build api object fields
    fields = []
    for a, b in state_names:
        fields.append(a)
        fields.append(b)
    for n in fn_names:
        fields.append(n)
    # unique preserve order
    seen = set()
    ordered = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            ordered.append(f)

    value_obj = "{\n" + "".join(f"    {n},\n" for n in ordered) + "  }"

    provider_tail = f'''
  const platformApi = {value_obj} as PlatformApi;

  return (
    <PlatformContext.Provider value={{platformApi}}>
      {{children}}
    </PlatformContext.Provider>
  );
}}

export function usePlatform(): PlatformApi {{
  const ctx = React.useContext(PlatformContext);
  if (!ctx) throw new Error("usePlatform requires PlatformProvider");
  return ctx;
}}
'''

    # pre_app content for shared modules
    # Split pre_app into: imports (rewrite), types+api+charts

    # --- types/index.ts ---
    # Take from const API / types until charts_start, strip auth+api functions into api module
    types_and_more = "".join(lines[types_start:charts_start])
    # Remove AUTH and api function from types file - put in api
    # Keep type definitions and const API? API goes to client

    # --- api/client.ts ---
    api_section_start = auth_const if auth_const >= 0 else find_line(lambda l: "getAuthToken" in l)
    if api_section_start < 0:
        api_section_start = find_line(lambda l: l.startswith("async function api"))
    charts_idx = charts_start
    # api helpers between auth and formatExpiry/charts - actually auth is before api before more types
    # From backup: types..., AUTH, api(), more types LifecycleImpact..., charts

    # Extract api client piece with regex from full text
    m_api = re.search(
        r"(const AUTH_TOKEN_KEY[\s\S]*?^async function api[\s\S]*?^}\n)",
        text,
        re.M,
    )
    api_client_body = m_api.group(1) if m_api else ""

    # Types: all `type X` blocks and interfaces from text before App, minus runtime functions
    type_blocks = re.findall(r"^type \w+[\s\S]*?^};?\n", text[: text.find("function App")], re.M)
    # Also const API and OPERATOR keys
    const_api = re.search(r"^const API[\s\S]*?;\n", text, re.M)
    const_op = re.search(r"^const OPERATOR_PREFERENCES_KEY[\s\S]*?;\n", text, re.M)

    types_file = "/* Auto-split domain types from main.tsx */\n\n"
    if const_api:
        # don't put API in types
        pass
    types_file += "\n".join(type_blocks)
    # MetricWindow etc might be type aliases without semicolon end - already collected

    # charts section
    charts_body = "".join(lines[charts_start:app_start])

    # formatExpiry and isSeedDemoName might be before charts
    helpers_before_charts = ""
    for i in range(max(0, charts_start - 80), charts_start):
        if lines[i].startswith("function formatExpiry") or lines[i].startswith("function isSeedDemoName") or lines[i].startswith("function servicePorts"):
            # include from this function to charts
            helpers_before_charts = "".join(lines[i:charts_start])
            charts_body = helpers_before_charts + charts_body
            break

    # Write directories
    (ROOT / "types").mkdir(exist_ok=True)
    (ROOT / "api").mkdir(exist_ok=True)
    (ROOT / "platform").mkdir(exist_ok=True)
    (ROOT / "views").mkdir(exist_ok=True)
    (ROOT / "auth").mkdir(exist_ok=True)

    # types - export API type constant location separately  
    # Include ALL type aliases from original for safety by taking chunk
    types_chunk = text[types_start: api_section_start if api_section_start > types_start else charts_start]
    # Remove auth/api runtime from types_chunk if present
    types_chunk = re.sub(r"const AUTH_TOKEN_KEY[\s\S]*?^async function api[\s\S]*?^}\n", "", types_chunk, flags=re.M)
    types_chunk = re.sub(r"^async function api[\s\S]*?^}\n", "", types_chunk, flags=re.M)
    types_chunk = re.sub(r"function getAuthToken[\s\S]*?^}\n", "", types_chunk, flags=re.M)
    types_chunk = re.sub(r"function setAuthToken[\s\S]*?^}\n", "", types_chunk, flags=re.M)
    types_chunk = re.sub(r"^const API = .*\n", "", types_chunk, flags=re.M)
    types_chunk = re.sub(r"^const OPERATOR_PREFERENCES_KEY = .*\n", "export const OPERATOR_PREFERENCES_KEY = \"platformops.operator.preferences.v1\";\n", types_chunk, flags=re.M)

    # Prefix export on type declarations
    types_out = "/* Shared PlatformOps types */\n\n"
    types_out += types_chunk
    types_out = re.sub(r"^type ", "export type ", types_out, flags=re.M)
    (ROOT / "types" / "index.ts").write_text(types_out)

    api_out = '''/* API client + auth token storage */
export const API = import.meta.env.VITE_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:9002");

'''
    if api_client_body:
        api_out += api_client_body
        api_out = api_out.replace("const AUTH_TOKEN_KEY", "export const AUTH_TOKEN_KEY")
        api_out = api_out.replace("function getAuthToken", "export function getAuthToken")
        api_out = api_out.replace("function setAuthToken", "export function setAuthToken")
        api_out = api_out.replace("async function api<", "export async function api<")
        api_out = api_out.replace("async function api(", "export async function api(")
    else:
        api_out += "export async function api<T>(path: string, init?: RequestInit): Promise<T> { throw new Error('api missing'); }\n"
    (ROOT / "api" / "client.ts").write_text(api_out)

    charts_out = '''import React, { useState } from "react";\nimport type { MetricPoint, MetricWindow } from "../types";\n\n'''
    charts_out += charts_body
    charts_out = re.sub(r"^function ", "export function ", charts_out, flags=re.M)
    (ROOT / "components" / "charts.tsx").write_text(charts_out)

    # Platform context type + provider file
    # For render methods: keep them on provider AND assign into platformApi so views can call them
    # Also expose them for AppShell switch

    # Convert final return into AppShell component file
    shell_body = final_return_body
    # `  return (` -> export function AppShell() { const p = usePlatform(); ... need identifiers
    # Easier: keep final return INSIDE provider when children undefined - dual mode

    # Dual mode provider:
    # if children: provide context
    # also export AppRoutes that uses context

    # Revert approach: provider_core includes ALL of app including render methods and final return becomes AppShell using destructure of usePlatform at start of each view only.
    # For AppShell switch, put it in App.tsx with usePlatform().renderX()

    # Add render methods to ordered fields - already in fn_names

    platform_header = '''import React, { useEffect, useState, createContext, useContext } from "react";
import { Layout } from "../components/Layout";
import { GlassCard } from "../components/GlassCard";
import { api, API, getAuthToken, setAuthToken } from "../api/client";
import * as T from "../types";
import { OPERATOR_PREFERENCES_KEY } from "../types";
import {
  renderSVGTimeSeriesChart,
  SvgTimeSeriesChart,
  renderUptimeAvailabilityBlocks,
  uptimeLatencySeries,
  renderMetricSparkline,
  renderMetricWindowPicker,
  renderCircularGauge,
  formatExpiry,
  isSeedDemoName,
} from "../components/charts";

// Re-export types into local names used by controller body
type CatalogCard = T.CatalogCard;
'''
    # The provider_core still uses types like Cluster without import - need import type { all }
    # Easier: `import type { ... } from '../types'` with all exported types
    # Or use triple-slash and keep types global via export in types - controller uses import type * as T and we need to rewrite all type refs - hard.

    # Pragmatic: platform/PlatformProvider.tsx starts with original pre-app content (types+api+charts inlined once) + provider
    # views only import usePlatform
    # This still extracts views from the 9k file... if render methods stay in provider, views are thin wrappers calling p.renderClustersView()

    thin_views = True

    platform_file = '''import React, { useEffect, useState, createContext, useContext } from "react";
import { Layout } from "../components/Layout";
import { GlassCard } from "../components/GlassCard";
import "../styles.css";

'''
    # Include original pre-app (types, api, charts) entirely inside platform file for correctness
    # Then provider_core + platform_tail
    # Strip outer imports from pre_app
    pre = pre_app
    pre = re.sub(r'^import .*\n', '', pre, flags=re.M)
    pre = re.sub(r'^from .*\n', '', pre, flags=re.M)

    platform_file += pre + "\n"
    platform_file += "export type PlatformApi = any;\nconst PlatformContext = createContext<PlatformApi | null>(null);\n\n"
    platform_file += provider_core + provider_tail

    (ROOT / "platform" / "PlatformProvider.tsx").write_text(platform_file)
    (ROOT / "platform" / "usePlatform.ts").write_text(
        'export { usePlatform, PlatformProvider } from "./PlatformProvider";\nexport type { PlatformApi } from "./PlatformProvider";\n'
    )

    # View wrappers
    view_map = {
        "renderClustersView": "ClustersView",
        "renderConfigManagerView": "ConfigView",
        "renderDiagnosticsView": "DiagnosticsView",
        "renderMonitoringView": "MonitoringView",
        "renderPerformanceView": "PerformanceView",
        "renderObservabilityStackView": "ObservabilityView",
        "renderTopologyView": "TopologyView",
        "renderPolicyView": "PolicyView",
        "renderAuditView": "AuditView",
        "renderReliabilityView": "ReliabilityView",
        "renderUsersView": "UsersView",
        "renderDrawers": "DrawersHost",
        "renderModals": "ModalsHost",
        "renderAiChat": "LogAnalystChat",
        "renderGlitchTipWorkspace": "GlitchTipWorkspace",
    }

    for method, comp in view_map.items():
        if method not in render_names and method not in fn_names:
            # still create if might exist
            pass
        (ROOT / "views" / f"{comp}.tsx").write_text(
            f'''import React from "react";
import {{ usePlatform }} from "../platform/usePlatform";

/** Page module — delegates to platform controller ({method}). */
export function {comp}() {{
  const p = usePlatform();
  if (typeof (p as any).{method} !== "function") {{
    return <div className="notice">View {{'{comp}'}} is unavailable.</div>;
  }}
  return <>{{(p as any).{method}()}}</>;
}}
'''
        )

    # App.tsx shell
    app_tsx = '''import React, { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { PlatformProvider, usePlatform } from "./platform/usePlatform";
import { api, getAuthToken, setAuthToken } from "./api/client";
import { ClustersView } from "./views/ClustersView";
import { ConfigView } from "./views/ConfigView";
import { DiagnosticsView } from "./views/DiagnosticsView";
import { MonitoringView } from "./views/MonitoringView";
import { PerformanceView } from "./views/PerformanceView";
import { ObservabilityView } from "./views/ObservabilityView";
import { TopologyView } from "./views/TopologyView";
import { PolicyView } from "./views/PolicyView";
import { AuditView } from "./views/AuditView";
import { ReliabilityView } from "./views/ReliabilityView";
import { UsersView } from "./views/UsersView";
import { DrawersHost } from "./views/DrawersHost";
import { ModalsHost } from "./views/ModalsHost";

function AuthenticatedShell() {
  const p = usePlatform() as any;

  // Login / invite gates still owned by controller flags if present
  if (p.authReady === false) {
    return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>Loading session…</div>;
  }
  if (typeof p.renderUsersView === "function" && p.inviteAccept && p.inviteAccept.preview?.state === "valid") {
    // reuse controller invite UI by rendering a tiny bridge
    return <InviteBridge />;
  }
  if (!p.authUser) {
    return <LoginBridge />;
  }

  const activeView = p.activeView === "dashboard" ? "clusters" : p.activeView;

  return (
    <Layout
      activeView={activeView}
      onViewChange={p.setActiveView}
      clusterContext={p.selectedCluster?.name}
      nodeContext={p.selectedNode?.name}
      serviceContext={p.selectedService?.name}
    >
      <main style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {p.notice ? (
          <section className="notice" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{p.notice}</span>
            <button style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", fontSize: "0.75rem" }} onClick={() => p.setNotice("")}>Dismiss</button>
          </section>
        ) : null}

        {activeView === "dashboard" || activeView === "clusters" ? <ClustersView /> : null}
        {activeView === "config" ? <ConfigView /> : null}
        {activeView === "users" ? <UsersView /> : null}
        {activeView === "monitoring" ? <MonitoringView /> : null}
        {activeView === "diagnostics" ? <DiagnosticsView /> : null}
        {activeView === "performance" ? <PerformanceView /> : null}
        {activeView === "observability" ? <ObservabilityView /> : null}
        {activeView === "topology" ? <TopologyView /> : null}
        {activeView === "policy" ? <PolicyView /> : null}
        {activeView === "audit" ? <AuditView /> : null}
        {activeView === "reliability" ? <ReliabilityView /> : null}
      </main>
      <DrawersHost />
      <ModalsHost />
    </Layout>
  );
}

function LoginBridge() {
  const p = usePlatform() as any;
  // Controller still owns full login JSX via optional renderLogin; fallback minimal form
  if (typeof p.renderLoginScreen === "function") return p.renderLoginScreen();
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div style={{ maxWidth: 420, width: "100%" }}>
        <h1>PlatformOps</h1>
        <input className="input" value={p.loginForm?.email || ""} onChange={(e) => p.setLoginForm({ ...p.loginForm, email: e.target.value })} placeholder="Email" style={{ width: "100%", marginBottom: 8 }} />
        <input className="input" type="password" value={p.loginForm?.password || ""} onChange={(e) => p.setLoginForm({ ...p.loginForm, password: e.target.value })} placeholder="Password" style={{ width: "100%", marginBottom: 8 }} />
        {p.loginError ? <div style={{ color: "var(--err)" }}>{p.loginError}</div> : null}
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={() => p.handleLogin()}>Sign in</button>
      </div>
    </div>
  );
}

function InviteBridge() {
  const p = usePlatform() as any;
  // Fall through to users invite accept UI embedded in controller state
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div style={{ maxWidth: 440, width: "100%" }}>
        <h1>Accept invite</h1>
        <p>{p.inviteAccept?.preview?.invite?.user_email}</p>
        <input className="input" type="password" value={p.inviteAccept?.password || ""} onChange={(e) => p.setInviteAccept({ ...p.inviteAccept, password: e.target.value })} style={{ width: "100%", marginBottom: 12 }} />
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={async () => {
          await api(`/api/auth/invite/${p.inviteAccept.token}/accept`, { method: "POST", body: JSON.stringify({ password: p.inviteAccept.password }) });
          p.setInviteAccept(null);
          window.location.hash = "";
        }}>Activate account</button>
      </div>
    </div>
  );
}

export function App() {
  return (
    <PlatformProvider>
      <AuthenticatedShell />
    </PlatformProvider>
  );
}
'''
    (ROOT / "App.tsx").write_text(app_tsx)

    # main entry
    (ROOT / "main.tsx").write_text(
        '''import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(<App />);
'''
    )

    print("Wrote frontend split")
    print("PlatformProvider lines", len(platform_file.splitlines()))
    print("types lines", len(types_out.splitlines()))
    print("charts lines", len(charts_out.splitlines()))
    print("ordered fields", len(ordered))


if __name__ == "__main__":
    main()
