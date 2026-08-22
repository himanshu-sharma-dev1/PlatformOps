// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createAuthActions(s: any) {
  return {
  async loadPlatformUsers(options: any = {}) {
    s.setUsersLoading?.(true);
    s.setUsersError?.("");
    try {
      const list = await api("/api/users");
      s.setPlatformUsers(list);
      return list;
    } catch (e) {
      const message = e?.message || "Failed to load users";
      s.setUsersError?.(message);
      s.setNotice(message);
      if (options.throwOnError) throw e;
      return null;
    } finally {
      s.setUsersLoading?.(false);
    }
  },

  async loadInvitePreview(token: string) {
    const normalized = String(token || "").trim();
    if (!normalized) {
      s.setInviteAccept({ token: "", preview: { state: "invalid", invite: null }, error: "Invitation link is missing a token." });
      s.setAuthReady(true);
      return null;
    }
    s.setInviteAccept((current: any) => ({
      ...(current || {}), token: normalized, preview: null, error: "", previewBusy: true,
    }));
    try {
      const preview = await api(`/api/auth/invite/${encodeURIComponent(normalized)}`);
      s.setInviteAccept((current: any) => ({
        ...(current || {}),
        token: normalized,
        fullName: current?.fullName || preview?.invite?.user_name || "",
        password: current?.password || "",
        confirmPassword: current?.confirmPassword || "",
        agreed: Boolean(current?.agreed),
        busy: false,
        previewBusy: false,
        error: "",
        preview,
      }));
      s.setAuthReady(true);
      return preview;
    } catch (e) {
      s.setInviteAccept((current: any) => ({
        ...(current || {}), token: normalized, previewBusy: false,
        preview: { state: "error", invite: null }, error: e?.message || "Unable to load invitation",
      }));
      s.setAuthReady(true);
      return null;
    }
  },

  async handleLogin() {
    s.setLoginBusy(true);
    s.setLoginError("");
    try {
      const res = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: String(s.loginForm.email || "").trim(),
          password: s.loginForm.password
        })
      });
      if (!res?.token) {
        throw new Error("Login response missing token");
      }
      setAuthToken(res.token);
      s.setAuthUser(res.user);
      const last = res.user?.session_info?.last_visited;
      if (last?.view) s.setActiveView(String(last.view));
      // Load inventory only after token is stored
      await s.refresh?.().catch(() => {});
    } catch (e) {
      s.setLoginError(e?.message || "Login failed");
      setAuthToken("");
      s.setAuthUser(null);
    } finally {
      s.setLoginBusy(false);
    }
  },

  async handleLogout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
    }
    setAuthToken("");
    s.setAuthUser(null);
    s.setPlatformUsers?.([]);
    s.setInviteAccept?.(null);
    s.setActiveView?.("clusters");
  }
  };
}
