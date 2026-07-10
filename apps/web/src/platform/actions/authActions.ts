// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createAuthActions(s: any) {
  return {
  async loadPlatformUsers() {
    try {
      const list = await api("/api/users");
      s.setPlatformUsers(list);
    } catch (e) {
      s.setNotice(e?.message || "Failed to load users");
    }
  },

  async handleLogin() {
    setLoginBusy(true);
    s.setLoginError("");
    try {
      const res = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: s.loginForm.email, password: s.loginForm.password })
      });
      setAuthToken(res.token);
      s.setAuthUser(res.user);
      const last = res.user?.session_info?.last_visited;
      if (last?.view) s.setActiveView(String(last.view));
    } catch (e) {
      setLoginError(e?.message || "Login failed");
    } finally {
      setLoginBusy(false);
    }
  },

  async handleLogout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
    }
    setAuthToken("");
    s.setAuthUser(null);
  }
  };
}
