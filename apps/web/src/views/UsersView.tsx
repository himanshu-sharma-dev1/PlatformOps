// @ts-nocheck
import React, { useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { api } from "../api/client";

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
  const [search, setSearch] = useState("");
  const [editingUser, setEditingUser] = useState<any>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [page, setPage] = useState(1);
  const pageSize = 10;

  if (authUser?.user_role !== "System_Admin") {
    return (
      <GlassCard style={{ padding: "1.5rem" }}>
        <h1>Users</h1>
        <p className="sub">System_Admin access is required.</p>
      </GlassCard>
    );
  }

  const active = platformUsers.filter((u) => u.status === "active");
  const pending = platformUsers.filter((u) => u.status === "pending");
  const disabled = platformUsers.filter((u) => u.status === "disabled");
  const filteredRows = (() => {
    const source = usersTab === "pending" ? pending : usersTab === "disabled" ? disabled : active;
    const needle = search.trim().toLowerCase();
    if (!needle) return source;
    return source.filter((u) => [u.user_name, u.user_email, u.user_role, u.user_number]
      .some((value) => String(value || "").toLowerCase().includes(needle)));
  })();
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const rows = filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const exportUsers = () => {
    const cells = [["Name", "Email", "Role", "Phone", "Status", "Logins"], ...platformUsers.map((u) => [
      u.user_name, u.user_email, u.user_role, u.user_number, u.status, String(u.login_count || 0),
    ])];
    const csv = cells.map((row) => row.map((value) => `"${String(value || "").replaceAll('"', '""')}"`).join(",")).join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "platformops-users.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const openEditor = (user: any) => {
    setEditingUser(user);
    setEditForm({
      user_name: user.user_name || "",
      user_number: user.user_number || "",
      user_role: user.user_role || "Operational",
      status: user.status || "active",
      password: "",
    });
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Users</h1>
          <p className="sub">cPlatform multiuser parity — roles, invites, and operator sessions.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={exportUsers}>Export</button>
          <button className="btn btn-secondary btn-sm" onClick={() => loadPlatformUsers()}>Refresh</button>
          <button className="btn btn-secondary btn-sm" onClick={() => handleLogout()}>Sign out ({authUser?.user_name || authUser?.user_email})</button>
        </div>
      </div>
      <div className="cluster-tabs">
        <div className={`tab ${usersTab === "active" ? "active" : ""}`} onClick={() => { setUsersTab("active"); setPage(1); }}>Active ({active.length})</div>
        <div className={`tab ${usersTab === "pending" ? "active" : ""}`} onClick={() => { setUsersTab("pending"); setPage(1); }}>Pending invites ({pending.length})</div>
        <div className={`tab ${usersTab === "disabled" ? "active" : ""}`} onClick={() => { setUsersTab("disabled"); setPage(1); }}>Disabled ({disabled.length})</div>
      </div>
      <input className="input" aria-label="Search users" placeholder="Search name, email, role, or phone" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
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
                  <td><span className="pill pill-muted">{u.user_role}</span></td>
                  <td><span className={`pill ${u.status === "active" ? "pill-ok" : "pill-warn"}`}>{u.status}</span></td>
                  <td>{u.login_count} · {u.last_login}</td>
                  <td style={{ textAlign: "right" }}>
                    {u.status === "pending" && u.invite_link ? (
                      <button className="btn btn-secondary btn-xs" onClick={() => { navigator.clipboard?.writeText(u.invite_link || ""); setNotice("Invite link copied"); }}>Copy invite</button>
                    ) : null}
                    {u.status === "pending" ? (
                      <>
                        <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} onClick={async () => {
                          const result = await api<any>("/api/users/invite/resend", {
                            method: "POST",
                            body: JSON.stringify({ emails: [u.user_email] })
                          });
                          setNotice(`Invite resent (${result.sent_count ?? 0} sent)`);
                          await loadPlatformUsers();
                        }}>Resend</button>
                        <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} onClick={async () => {
                          await api("/api/users/invite/revoke", { method: "POST", body: JSON.stringify({ user_email: u.user_email }) });
                          await loadPlatformUsers();
                        }}>Revoke</button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-secondary btn-xs" onClick={() => openEditor(u)}>Edit</button>
                        <button className="btn btn-danger btn-xs" style={{ marginLeft: 4 }} onClick={async () => {
                          if (!window.confirm(`Delete ${u.user_email}?`)) return;
                          await api(`/api/users/${u.user_id}`, { method: "DELETE" });
                          await loadPlatformUsers();
                        }}>Delete</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6} style={{ color: "var(--ink-4)", padding: "1rem 0" }}>No users in this tab.</td></tr>
              )}
            </tbody>
          </table>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
            <span style={{ color: "var(--ink-4)", fontSize: "0.78rem" }}>{filteredRows.length} matching user(s)</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-secondary btn-xs" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</button>
              <span style={{ padding: "0.25rem" }}>{currentPage}/{pageCount}</span>
              <button className="btn btn-secondary btn-xs" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</button>
            </div>
          </div>
        </GlassCard>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {editingUser ? (
            <GlassCard style={{ padding: "1.25rem" }}>
              <h3 style={{ marginTop: 0 }}>Edit {editingUser.user_email}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input className="input" placeholder="Name" value={editForm.user_name} onChange={(e) => setEditForm({ ...editForm, user_name: e.target.value })} />
                <input className="input" value={editingUser.user_email} readOnly />
                <input className="input" placeholder="Phone (optional)" value={editForm.user_number} onChange={(e) => setEditForm({ ...editForm, user_number: e.target.value })} />
                <select className="input" value={editForm.user_role} onChange={(e) => setEditForm({ ...editForm, user_role: e.target.value })}>
                  <option value="System_Admin">System_Admin</option>
                  <option value="Operational">Operational</option>
                  <option value="Management">Management</option>
                </select>
                <select className="input" value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
                  <option value="active">Active</option>
                  <option value="disabled">Disabled</option>
                  <option value="pending">Pending</option>
                </select>
                <input className="input" type="password" placeholder="New password (leave blank to keep)" value={editForm.password} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} />
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={async () => {
                    const payload = { ...editForm };
                    if (!payload.password) delete payload.password;
                    await api(`/api/users/${editingUser.user_id}`, { method: "PUT", body: JSON.stringify(payload) });
                    setNotice(`Updated ${editingUser.user_email}`);
                    setEditingUser(null);
                    await loadPlatformUsers();
                  }}>Save changes</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => setEditingUser(null)}>Cancel</button>
                </div>
              </div>
            </GlassCard>
          ) : null}
          <GlassCard style={{ padding: "1.25rem" }}>
            <h3 style={{ marginTop: 0 }}>Invite user</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <input className="input" placeholder="Name" value={inviteForm.user_name} onChange={(e) => setInviteForm({ ...inviteForm, user_name: e.target.value })} />
              <input className="input" type="email" placeholder="Email" value={inviteForm.user_email} onChange={(e) => setInviteForm({ ...inviteForm, user_email: e.target.value })} />
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
              <input className="input" type="email" placeholder="Email" value={userForm.user_email} onChange={(e) => setUserForm({ ...userForm, user_email: e.target.value })} />
              <input className="input" type="password" placeholder="Password" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
              <input className="input" placeholder="Phone (optional)" value={userForm.user_number} onChange={(e) => setUserForm({ ...userForm, user_number: e.target.value })} />
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
