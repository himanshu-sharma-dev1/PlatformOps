import React, { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { PlatformProvider, usePlatform } from "./platform/usePlatform";
import { api, setAuthToken } from "./api/client";
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
import { resolveEscapeClose } from "./platform/ux/clusterUx";

function AuthenticatedShell() {
  const p = usePlatform() as any;

  // Login / invite gates still owned by controller flags if present
  if (p.authReady === false) {
    return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>Loading session…</div>;
  }
  if (p.inviteAccept) {
    return <InviteBridge />;
  }
  if (!p.authUser) {
    return <LoginBridge />;
  }

  const activeView = p.activeView === "dashboard" ? "clusters" : p.activeView;

  // Lazy-load advanced inventory when opening Advanced pages (cluster path never blocks on these)
  React.useEffect(() => {
    if (["topology", "policy", "audit", "reliability"].includes(activeView)) {
      p.refreshAdvancedInventory?.().catch(() => {});
    }
  }, [activeView]);

  // cP Escape close priority for shell-level drawers/modals (info detail handled in ClustersView)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // Let local ClustersView info drawers win if they set this flag
      if ((window as any).__poInfoDetailOpen) return;
      const surface = resolveEscapeClose({
        actionBlocker: Boolean(p.actionBlocker?.visible),
        svcConfig: Boolean(p.catalogOnboarding?.visible),
        nodeProvision: Boolean(p.stepperDrawerVisible),
        catalog: Boolean(p.catalogDrawerVisible),
        clusterEditor: Boolean(p.clusterEditor?.visible),
        launch: Boolean(p.launchDrawerVisible),
        deployment: Boolean(p.deploymentModal?.visible),
        deleteModal: Boolean(p.deleteModal?.visible),
      });
      if (!surface) return;
      e.preventDefault();
      if (surface === "action_blocker") {
        p.setActionBlocker?.({ visible: false, message: "", items: [] });
      } else if (surface === "svc_config") {
        p.setCatalogOnboarding?.((c: any) => ({ ...c, visible: false, error: "", registeredService: null }));
      } else if (surface === "node_provision") {
        p.setStepperDrawerVisible?.(false);
        p.setStepperStep?.(1);
      } else if (surface === "catalog") {
        p.setCatalogDrawerVisible?.(false);
      } else if (surface === "cluster_editor") {
        p.setClusterEditor?.((c: any) => ({ ...c, visible: false, saving: false }));
      } else if (surface === "launch") {
        p.setLaunchDrawerVisible?.(false);
      } else if (surface === "deployment") {
        p.setDeploymentModal?.((c: any) => ({ ...c, visible: false }));
      } else if (surface === "delete_modal") {
        p.setDeleteModal?.((c: any) => ({ ...c, visible: false }));
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const toastMsg = p.toast?.message || p.notice;
  const toastKind = p.toast?.kind || "ok";

  return (
    <Layout
      activeView={activeView}
      onViewChange={(view) => {
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
      {/* cP floating toast (bottom) — auto-dismiss via showToast */}
      {toastMsg ? (
        <div
          className={`toast-float toast-${toastKind} show`}
          role="status"
          data-ux="toast"
          onClick={() => (typeof p.dismissToast === "function" ? p.dismissToast() : p.setNotice(""))}
        >
          <span className="toast-float-msg">{toastMsg}</span>
          <button
            type="button"
            className="toast-dismiss"
            onClick={(e) => {
              e.stopPropagation();
              typeof p.dismissToast === "function" ? p.dismissToast() : p.setNotice("");
            }}
          >
            Dismiss
          </button>
        </div>
      ) : null}
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
  const invite = p.inviteAccept || {};
  const state = invite.preview?.state || "error";
  const update = (patch: any) => p.setInviteAccept({ ...invite, ...patch });
  const password = String(invite.password || "");
  const passwordRules = {
    length: password.length >= 12,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
    nocommon: password.length > 0 && !new Set([
      "password123", "qwerty123456", "iloveyou12345", "admin1234567",
      "123456789012", "yantrai123456", "welcome12345", "letmein12345",
      "changeme1234",
    ]).has(password.toLowerCase()),
  };
  const strength = Object.values(passwordRules).filter(Boolean).length;
  const canSubmit = state === "valid" && strength >= 5
    && password === invite.confirmPassword && Boolean(invite.fullName?.trim())
    && Boolean(invite.agreed) && !invite.busy;
  const stateMessages: Record<string, string> = {
    expired: "This invitation has expired. Ask an administrator to resend it.",
    used: "This invitation has already been accepted. Sign in with the account credentials.",
    revoked: "This invitation was cancelled by an administrator.",
    invalid: "This invitation link is invalid.",
    error: invite.error || "The invitation could not be loaded. Try again.",
    success: "Your account has been created. You can now sign in.",
  };
  const leaveInviteRoute = () => {
    p.setInviteAccept(null);
    // The invitation token is a one-time credential. Replace the hash rather
    // than assigning an empty hash, which leaves a misleading `/#` route.
    const cleanPath = window.location.pathname.replace(/\/invite\/accept\/[^/]+\/?$/, "") || "/";
    window.history.replaceState(null, document.title, `${cleanPath}${window.location.search}`);
  };
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div style={{ maxWidth: 480, width: "100%", padding: "2rem", border: "1px solid var(--line)", borderRadius: 16 }}>
        <h1>{state === "valid" ? "Accept invitation" : "Invitation status"}</h1>
        {state !== "valid" ? (
          <>
            <p>{stateMessages[state] || stateMessages.invalid}</p>
            {state === "error" ? (
              <button className="btn btn-secondary" onClick={() => p.loadInvitePreview?.(invite.token)} disabled={Boolean(invite.previewBusy)}>
                {invite.previewBusy ? "Retrying…" : "Try again"}
              </button>
            ) : null}
            <button className="btn btn-primary" onClick={leaveInviteRoute}>Go to sign in</button>
          </>
        ) : (
          <>
            <p>{invite.preview?.invite?.user_email}</p>
            <p style={{ color: "var(--ink-4)" }}>Invited by {invite.preview?.invite?.invited_by || "Administrator"} as {invite.preview?.invite?.user_role}</p>
            <input className="input" placeholder="Full name" value={invite.fullName || ""} onChange={(e) => update({ fullName: e.target.value, error: "" })} style={{ width: "100%", marginBottom: 12 }} />
            <input className="input" type="password" placeholder="Password" value={password} onChange={(e) => update({ password: e.target.value, error: "" })} style={{ width: "100%", marginBottom: 8 }} />
            <div style={{ fontSize: "0.75rem", color: strength >= 5 ? "var(--ok)" : "var(--ink-4)", marginBottom: 12 }}>
              12+ characters; uppercase, lowercase, number, symbol, and not a common password. ({strength}/6 rules)
            </div>
            <input className="input" type="password" placeholder="Confirm password" value={invite.confirmPassword || ""} onChange={(e) => update({ confirmPassword: e.target.value, error: "" })} style={{ width: "100%", marginBottom: 12 }} />
            <label style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <input type="checkbox" checked={Boolean(invite.agreed)} onChange={(e) => update({ agreed: e.target.checked })} />
              <span>I agree to the terms of service and privacy policy.</span>
            </label>
            {invite.error ? <div style={{ color: "var(--err)", marginBottom: 12 }}>{invite.error}</div> : null}
            <button className="btn btn-primary" disabled={!canSubmit} style={{ width: "100%" }} onClick={async () => {
              update({ busy: true, error: "" });
              try {
                const result = await api<any>(`/api/auth/invite/${invite.token}/accept`, {
                  method: "POST",
                  body: JSON.stringify({ full_name: invite.fullName.trim(), password })
                });
                if (!result?.token || !result?.user) {
                  throw new Error("Invitation response missing authentication session");
                }
                // Invite acceptance returns the same session envelope as
                // login. Persist it before leaving the public invite route so
                // the shell immediately renders the authenticated application.
                setAuthToken(result.token);
                p.setAuthUser(result.user);
                leaveInviteRoute();
                void p.refresh?.().catch?.(() => {});
              } catch (e: any) {
                update({ busy: false, error: e?.message || "Invitation acceptance failed" });
              }
            }}>{invite.busy ? "Creating account…" : "Accept invitation & sign in"}</button>
          </>
        )}
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
