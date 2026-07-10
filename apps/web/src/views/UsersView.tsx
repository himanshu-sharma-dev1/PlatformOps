// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";

/** UsersView — Phase 1 extracted page JSX. */
export function UsersView() {
  const p = usePlatform() as any;
  const authUser = p.authUser;
  const handleLogout = p.handleLogout;
  const inviteForm = p.inviteForm;
  const loadPlatformUsers = p.loadPlatformUsers;
  const platformUsers = p.platformUsers;
  const setInviteForm = p.setInviteForm;
  const setNotice = p.setNotice;
  const setUserForm = p.setUserForm;
  const setUsersTab = p.setUsersTab;
  const userForm = p.userForm;
  const usersTab = p.usersTab;


  const active = platformUsers.filter((u) => u.status === "active");
  const pending = platformUsers.filter((u) => u.status === "pending");
  const rows = usersTab === "active" ? active : pending;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Users</h1>
          <p className="sub">cPlatform multiuser parity — roles, invites, and operator sessions.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => loadPlatformUsers()}>Refresh</button>
          <button className="btn btn-secondary btn-sm" onClick={() => handleLogout()}>Sign out ({authUser?.user_name || authUser?.user_email})</button>
        </div>
      </div>
      <div className="cluster-tabs">
        <div className={`tab ${usersTab === "active" ? "active" : ""}`} onClick={() => setUsersTab("active")}>Active ({active.length})</div>
        <div className={`tab ${usersTab === "pending" ? "active" : ""}`} onClick={() => setUsersTab("pending")}>Pending invites ({pending.length})</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.25rem" }}>
        <GlassCard style={{ padding: "1.25rem" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ color: "var(--ink-4)", textAlign: "left" }}>
                <th style={{ padding: "0.4rem 0" }}>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Logins</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.user_id} style={{ borderTop: "1px solid var(--line-2)" }}>
                  <td style={{ padding: "0.55rem 0" }}><strong>{u.user_name}</strong></td>
                  <td><code>{u.user_email}</code></td>
                  <td><span className="pill">{u.user_role}</span></td>
                  <td><span className={`pill ${u.status === "active" ? "pill-ok" : "pill-warn"}`}>{u.status}</span></td>
                  <td>{u.login_count} · {u.last_login}</td>
                  <td style={{ textAlign: "right" }}>
                    {u.status === "pending" && u.invite_link ? (
                      <button className="btn btn-secondary btn-xs" onClick={() => { navigator.clipboard?.writeText(u.invite_link || ""); setNotice("Invite link copied"); }}>Copy invite</button>
                    ) : null}
                    {u.status === "pending" ? (
                      <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} onClick={async () => {
                        await api("/api/users/invite/revoke", { method: "POST", body: JSON.stringify({ user_email: u.user_email }) });
                        await loadPlatformUsers();
                      }}>Revoke</button>
                    ) : (
                      <button className="btn btn-danger btn-xs" onClick={async () => {
                        if (!window.confirm(`Delete ${u.user_email}?`)) return;
                        await api(`/api/users/${u.user_id}`, { method: "DELETE" });
                        await loadPlatformUsers();
                      }}>Delete</button>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6} style={{ color: "var(--ink-4)", padding: "1rem 0" }}>No users in this tab.</td></tr>
              )}
            </tbody>
          </table>
        </GlassCard>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Invite user</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <input className="input" placeholder="Name" value={inviteForm.user_name} onChange={(e) => setInviteForm({ ...inviteForm, user_name: e.target.value })} />
              <input className="input" placeholder="Username" value={inviteForm.user_email} onChange={(e) => setInviteForm({ ...inviteForm, user_email: e.target.value })} />
              <select className="input" value={inviteForm.user_role} onChange={(e) => setInviteForm({ ...inviteForm, user_role: e.target.value })}>
                <option value="System_Admin">System_Admin</option>
                <option value="Operational">Operational</option>
                <option value="Management">Management</option>
              </select>
              <input className="input" placeholder="Phone (optional)" value={inviteForm.user_number} onChange={(e) => setInviteForm({ ...inviteForm, user_number: e.target.value })} />
              <button className="btn btn-primary btn-sm" onClick={async () => {
                const created = await api<PlatformUser>("/api/users/invite", { method: "POST", body: JSON.stringify(inviteForm) });
                setNotice(created.invite_link ? `Invite ready: ${created.invite_link}` : "Invite created");
                setInviteForm({ user_name: "", user_email: "", user_role: "Operational", user_number: "" });
                await loadPlatformUsers();
                setUsersTab("pending");
              }}>Send invite</button>
            </div>
          </GlassCard>
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Add active user</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <input className="input" placeholder="Name" value={userForm.user_name} onChange={(e) => setUserForm({ ...userForm, user_name: e.target.value })} />
              <input className="input" placeholder="Username" value={userForm.user_email} onChange={(e) => setUserForm({ ...userForm, user_email: e.target.value })} />
              <input className="input" type="password" placeholder="Password (min 8)" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
              <select className="input" value={userForm.user_role} onChange={(e) => setUserForm({ ...userForm, user_role: e.target.value })}>
                <option value="System_Admin">System_Admin</option>
                <option value="Operational">Operational</option>
                <option value="Management">Management</option>
              </select>
              <button className="btn btn-primary btn-sm" onClick={async () => {
                await api("/api/users", { method: "POST", body: JSON.stringify(userForm) });
                setNotice("User created");
                setUserForm({ user_name: "", user_email: "", user_role: "Operational", user_number: "", password: "" });
                await loadPlatformUsers();
              }}>Create user</button>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );

}
