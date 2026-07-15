import React, { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { PlatformProvider, usePlatform } from "./platform/usePlatform";
import { api } from "./api/client";
import { ClustersView } from "./views/ClustersView";
import { ConfigView } from "./views/ConfigView";
import { DiagnosticsView } from "./views/DiagnosticsView";
import { MonitoringView } from "./views/MonitoringView";
import { PerformanceView } from "./views/PerformanceView";
import { UsersView } from "./views/UsersView";
import { DrawersHost } from "./views/DrawersHost";
import { ModalsHost } from "./views/ModalsHost";
import { DETANGLED_VIEWS } from "./platform/ux/clusterUx";

/** Views kept in codebase but removed from cPlatform-aligned product shell. */
const DETANGLED = new Set<string>(DETANGLED_VIEWS as unknown as string[]);

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

  // Detangle: force cPlatform product surface (no topology/policy/audit/reliability/obs-stack as primary pages)
  let activeView = p.activeView === "dashboard" ? "clusters" : p.activeView;
  if (DETANGLED.has(activeView)) {
    activeView = "clusters";
  }

  return (
    <Layout
      activeView={activeView}
      onViewChange={(view) => {
        if (DETANGLED.has(view)) {
          p.setActiveView("clusters");
          return;
        }
        if (view === "clusters") {
          p.selectNode?.(null);
          p.setSelectedCluster(null);
          p.setSelectedService(null);
          p.setActiveView("clusters");
        } else if (view === "cluster-dashboard") {
          p.selectNode?.(null);
          p.setSelectedService(null);
          p.setActiveView("clusters");
        } else if (view === "node-dashboard") {
          p.setSelectedService(null);
          p.setActiveView("clusters");
        } else {
          p.setActiveView(view);
        }
      }}
      clusterContext={p.selectedCluster?.name}
      nodeContext={p.selectedNode?.name}
      serviceContext={p.selectedService?.name}
    >
      <main style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {(p.toast?.message || p.notice) ? (
          <section
            className={`toast-bar toast-${p.toast?.kind || "ok"}`}
            role="status"
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem" }}
          >
            <span>{p.toast?.message || p.notice}</span>
            <button
              type="button"
              className="toast-dismiss"
              onClick={() => (typeof p.dismissToast === "function" ? p.dismissToast() : p.setNotice(""))}
            >
              Dismiss
            </button>
          </section>
        ) : null}

        {activeView === "dashboard" || activeView === "clusters" ? <ClustersView /> : null}
        {activeView === "config" ? <ConfigView /> : null}
        {activeView === "users" ? <UsersView /> : null}
        {activeView === "monitoring" ? <MonitoringView /> : null}
        {activeView === "diagnostics" ? <DiagnosticsView /> : null}
        {activeView === "performance" ? <PerformanceView /> : null}
      </main>
      <DrawersHost />
      <ModalsHost />
    </Layout>
  );
}

function LoginBridge() {
  const p = usePlatform() as any;
  return (
    <div style={{
      minHeight: "100vh",
      display: "grid",
      placeItems: "center",
      padding: "2rem",
      background: "radial-gradient(ellipse at top, rgba(59,130,246,0.10), transparent 55%)",
    }}>
      <div style={{
        maxWidth: 420,
        width: "100%",
        padding: "2rem",
        border: "1px solid var(--line)",
        borderRadius: 16,
        background: "var(--bg-card, rgba(15,23,42,0.85))",
        boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, display: "grid", placeItems: "center",
            background: "var(--navy, #1e3a5f)", color: "#fff", fontWeight: 700,
          }}>P</div>
          <div>
            <h1 style={{ margin: 0, fontSize: "1.35rem" }}>PlatformOps</h1>
            <p style={{ margin: 0, color: "var(--ink-4)", fontSize: "0.85rem" }}>Control plane sign-in</p>
          </div>
        </div>
        <label style={{ fontSize: "0.78rem", color: "var(--ink-4)", display: "block", marginBottom: 4 }}>Username</label>
        <input
          className="input"
          autoComplete="username"
          value={p.loginForm?.email || ""}
          onChange={(e) => p.setLoginForm({ ...p.loginForm, email: e.target.value })}
          onKeyDown={(e) => { if (e.key === "Enter") p.handleLogin(); }}
          placeholder="admin"
          style={{ width: "100%", marginBottom: 12 }}
        />
        <label style={{ fontSize: "0.78rem", color: "var(--ink-4)", display: "block", marginBottom: 4 }}>Password</label>
        <input
          className="input"
          type="password"
          autoComplete="current-password"
          value={p.loginForm?.password || ""}
          onChange={(e) => p.setLoginForm({ ...p.loginForm, password: e.target.value })}
          onKeyDown={(e) => { if (e.key === "Enter") p.handleLogin(); }}
          placeholder="admin"
          style={{ width: "100%", marginBottom: 14 }}
        />
        {p.loginError ? <div style={{ color: "var(--err)", fontSize: "0.85rem", marginBottom: 10 }}>{p.loginError}</div> : null}
        <button className="btn btn-primary" style={{ width: "100%" }} disabled={p.loginBusy} onClick={() => p.handleLogin()}>
          {p.loginBusy ? "Signing in…" : "Sign in"}
        </button>
        <p style={{ color: "var(--ink-5)", fontSize: "0.75rem", marginTop: 14, marginBottom: 0 }}>
          Default: <code>admin</code> / <code>admin</code>
        </p>
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
