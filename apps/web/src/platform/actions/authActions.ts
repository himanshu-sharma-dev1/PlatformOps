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
  }
  };
}
