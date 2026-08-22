// @ts-nocheck
import React, { useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";
import { api } from "../api/client";

const ROLES = ["System_Admin", "Operational", "Management"];
const PERMISSIONS = [
  ["configure_pipelines", "Configure data pipelines"],
  ["deploy_models", "Deploy and modify models"],
  ["manage_clusters", "Manage clusters and applications"],
  ["manage_users", "Manage other users"],
];
const emptyInvite = { user_name: "", user_email: "", user_role: "Operational", user_number: "", permissions: [] };
const emptyUser = { user_name: "", user_email: "", user_role: "Operational", user_number: "", password: "", permissions: [] };

function permissionEditor(value: string[], onChange: (next: string[]) => void) {
  const selected = new Set(value || []);
  return (
    <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
      <legend style={{ color: "var(--ink-4)", fontSize: "0.78rem" }}>Permissions</legend>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {PERMISSIONS.map(([key, label]) => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: "0.8rem" }}>
            <input type="checkbox" checked={selected.has(key)} onChange={(event) => {
              const next = new Set(selected);
              if (event.target.checked) next.add(key); else next.delete(key);
              onChange(Array.from(next));
            }} />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** UsersView — cPlatform Users controls with explicit action states. */
export function UsersView() {
  const p = usePlatform() as any;
  const authUser = p.authUser;
  const allUsers = Array.isArray(p.platformUsers) ? p.platformUsers : [];
  const [search, setSearch] = useState("");
  const [editingUser, setEditingUser] = useState<any>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [page, setPage] = useState(1);
  const [busyAction, setBusyAction] = useState("");
  const [actionError, setActionError] = useState("");
  const [sortDescending, setSortDescending] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const pageSize = 10;

  if (authUser?.user_role !== "System_Admin") {
    return (
      <GlassCard style={{ padding: "1.5rem" }}>
        <h1>Users</h1>
        <p className="sub" role="alert">System_Admin access is required.</p>
      </GlassCard>
    );
  }

  const active = allUsers.filter((u) => u.status === "active");
  const pending = allUsers.filter((u) => u.status === "pending");
  const disabled = allUsers.filter((u) => u.status === "disabled");
  const source = p.usersTab === "pending" ? pending : p.usersTab === "disabled" ? disabled : active;
  const needle = search.trim().toLowerCase();
  const filteredRows = !needle ? source : source.filter((u) => [u.user_name, u.user_email, u.user_role, u.user_number]
    .some((value) => String(value || "").toLowerCase().includes(needle)));
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const sortedRows = [...filteredRows].sort((a, b) => {
    const left = Number(a.last_login_ts || 0);
    const right = Number(b.last_login_ts || 0);
    return sortDescending ? right - left : left - right;
  });
  const rows = sortedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const run = async (label: string, operation: () => Promise<any>, success: string | null = null) => {
    setBusyAction(label);
    setActionError("");
    try {
      const result = await operation();
      if (success) p.setNotice(success);
      return result;
    } catch (error) {
      const message = error?.message || "Request failed. Try again.";
      setActionError(message);
      p.setNotice(message);
      return null;
    } finally {
      setBusyAction("");
    }
  };

  const exportUsers = () => {
    const cells = [["Name", "Email", "Role", "Phone", "Status", "Logins"], ...allUsers.map((u) => [
      u.user_name, u.user_email, u.user_role, u.user_number, u.status, String(u.login_count || 0),
    ])];
    const csv = cells.map((row) => row.map((value) => `"${String(value || "").replaceAll('"', '""')}"`).join(",")).join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "platformops-users.csv";
    link.click();
    URL.revokeObjectURL(link.href);
    p.setNotice("Users exported");
  };

  const copyInvite = async (user: any) => {
    if (!user.invite_link) {
      setActionError("No active invitation link is available. Resend the invitation and try again.");
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(user.invite_link);
      } else {
        const field = document.createElement("textarea");
        field.value = user.invite_link;
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.focus(); field.select();
        if (!document.execCommand("copy")) throw new Error("Clipboard access was denied");
        field.remove();
      }
      p.setNotice("Invitation link copied");
    } catch (error) {
      setActionError(error?.message || "Clipboard access was denied. Try again.");
      p.setNotice("Unable to copy invitation link");
    }
  };

  const openEditor = (user: any) => {
    setActionError("");
    setEditingUser(user);
    setEditForm({
      user_name: user.user_name || "",
      user_number: user.user_number || "",
      user_role: user.user_role || "Operational",
      status: user.status || "active",
      password: "",
      permissions: user.permissions || [],
    });
  };

  const refresh = () => run("refresh", () => p.loadPlatformUsers({ throwOnError: true }), null);
  const toggleSelected = (userId: string, checked: boolean) => setSelectedIds((current) => {
    const next = new Set(current);
    if (checked) next.add(userId); else next.delete(userId);
    return next;
  });
  const selectVisible = (checked: boolean) => setSelectedIds((current) => {
    const next = new Set(current);
    rows.forEach((user) => checked ? next.add(user.user_id) : next.delete(user.user_id));
    return next;
  });
  const resendSelected = () => {
    const emails = allUsers.filter((user) => selectedIds.has(user.user_id) && user.status === "pending").map((user) => user.user_email);
    if (!emails.length) {
      setActionError("Select at least one pending invitation to resend.");
      return;
    }
    void run("bulk-resend", async () => {
      const result = await api<any>("/api/users/invite/resend", { method: "POST", body: JSON.stringify({ emails }) });
      setSelectedIds(new Set());
      await p.loadPlatformUsers({ throwOnError: true });
      return result;
    }, `Invitations resent (${emails.length})`);
  };
  const tab = p.usersTab || "active";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles"><h1>Users</h1><p className="sub">cPlatform multiuser parity — roles, invites, and operator sessions.</p></div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={exportUsers} disabled={Boolean(busyAction)}>Export</button>
          <button className="btn btn-secondary btn-sm" onClick={refresh} disabled={busyAction === "refresh"}>{busyAction === "refresh" ? "Refreshing…" : "Refresh"}</button>
          <button className="btn btn-secondary btn-sm" onClick={() => p.handleLogout()}>Sign out ({authUser?.user_name || authUser?.user_email})</button>
        </div>
      </div>

      {actionError ? <div role="alert" style={{ color: "var(--err)", padding: "0.6rem 0" }}>{actionError}</div> : null}
      {p.usersError ? <GlassCard style={{ padding: "1rem" }}><p role="alert" style={{ color: "var(--err)", marginTop: 0 }}>{p.usersError}</p><button className="btn btn-secondary btn-sm" onClick={refresh} disabled={busyAction === "refresh"}>Retry</button></GlassCard> : null}

      <div className="cluster-tabs" role="tablist" aria-label="User status">
        {[["active", active], ["pending", pending], ["disabled", disabled]].map(([key, values]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => { p.setUsersTab(key); setPage(1); }}>
            {key === "pending" ? "Pending invites" : key[0].toUpperCase() + key.slice(1)} ({values.length})
          </button>
        ))}
      </div>
      <input className="input" aria-label="Search users" placeholder="Search name, email, role, or phone" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
      {selectedIds.size ? <div className="bulk-bar" style={{ display: "flex", alignItems: "center", gap: 12 }}><span>{selectedIds.size} selected</span><button className="btn btn-secondary btn-xs" onClick={resendSelected} disabled={Boolean(busyAction)}>{busyAction === "bulk-resend" ? "Resending…" : "Resend invitations"}</button><button className="btn btn-secondary btn-xs" onClick={() => setSelectedIds(new Set())}>Clear</button></div> : null}

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "1.25rem" }}>
        <GlassCard style={{ padding: "1.25rem" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead><tr style={{ color: "var(--ink-4)", textAlign: "left" }}><th style={{ padding: "0.4rem 0" }}><input type="checkbox" aria-label="Select visible users" checked={rows.length > 0 && rows.every((user) => selectedIds.has(user.user_id))} onChange={(event) => selectVisible(event.target.checked)} /></th><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th><button type="button" className="btn btn-secondary btn-xs" onClick={() => setSortDescending((value) => !value)}>Last login {sortDescending ? "↓" : "↑"}</button></th><th /></tr></thead>
            <tbody>
              {p.usersLoading ? <tr><td colSpan={7} style={{ color: "var(--ink-4)", padding: "1rem 0" }}>Loading users…</td></tr> : null}
              {!p.usersLoading && rows.map((u) => (
                <tr key={u.user_id} style={{ borderTop: "1px solid var(--line-2)" }}>
                  <td style={{ padding: "0.55rem 0" }}><input type="checkbox" aria-label={`Select ${u.user_email}`} checked={selectedIds.has(u.user_id)} onChange={(event) => toggleSelected(u.user_id, event.target.checked)} /></td><td><strong>{u.user_name}</strong></td><td><code>{u.user_email}</code></td><td><span className="pill pill-muted">{u.user_role}</span></td>
                  <td><span className={`pill ${u.status === "active" ? "pill-ok" : u.status === "disabled" ? "pill-err" : "pill-warn"}`}>{u.status}</span></td><td>{u.login_count} · {u.last_login}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {u.status === "pending" ? <>
                      <button className="btn btn-secondary btn-xs" onClick={() => copyInvite(u)}>Copy invite</button>
                      <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} disabled={Boolean(busyAction)} onClick={() => void run(`resend-${u.user_id}`, async () => { const result = await api<any>("/api/users/invite/resend", { method: "POST", body: JSON.stringify({ emails: [u.user_email] }) }); await p.loadPlatformUsers({ throwOnError: true }); return result; }, "Invitation resent")}>{busyAction === `resend-${u.user_id}` ? "Resending…" : "Resend"}</button>
                      <button className="btn btn-secondary btn-xs" style={{ marginLeft: 4 }} disabled={Boolean(busyAction)} onClick={() => { if (!window.confirm(`Revoke the invitation for ${u.user_email}?`)) return; void run(`revoke-${u.user_id}`, async () => { const result = await api(`/api/users/invite/revoke`, { method: "POST", body: JSON.stringify({ user_email: u.user_email }) }); await p.loadPlatformUsers({ throwOnError: true }); return result; }, "Invitation revoked"); }}>{busyAction === `revoke-${u.user_id}` ? "Revoking…" : "Revoke"}</button>
                    </> : <>
                      <button className="btn btn-secondary btn-xs" onClick={() => openEditor(u)}>Edit</button>
                      <button className="btn btn-danger btn-xs" style={{ marginLeft: 4 }} disabled={Boolean(busyAction)} onClick={() => { if (!window.confirm(`Delete ${u.user_email}? This cannot be undone.`)) return; void run(`delete-${u.user_id}`, async () => { const result = await api(`/api/users/${u.user_id}`, { method: "DELETE" }); if (u.user_id === authUser.user_id) { await p.handleLogout(); return result; } await p.loadPlatformUsers({ throwOnError: true }); return result; }, "User deleted"); }}>{busyAction === `delete-${u.user_id}` ? "Deleting…" : "Delete"}</button>
                    </>}
                  </td>
                </tr>
              ))}
              {!p.usersLoading && rows.length === 0 ? <tr><td colSpan={7} style={{ color: "var(--ink-4)", padding: "1rem 0" }}>No users in this tab.</td></tr> : null}
            </tbody>
          </table>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}><span style={{ color: "var(--ink-4)", fontSize: "0.78rem" }}>{filteredRows.length} matching user(s)</span><div style={{ display: "flex", gap: 6 }}><button className="btn btn-secondary btn-xs" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</button><span style={{ padding: "0.25rem" }}>{currentPage}/{pageCount}</span><button className="btn btn-secondary btn-xs" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</button></div></div>
        </GlassCard>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {editingUser ? <GlassCard style={{ padding: "1.25rem" }}><h3 style={{ marginTop: 0 }}>Edit {editingUser.user_email}</h3><div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="input" aria-label="Edit name" placeholder="Name" value={editForm.user_name} onChange={(e) => setEditForm({ ...editForm, user_name: e.target.value })} /><input className="input" aria-label="Edit email" value={editingUser.user_email} readOnly /><input className="input" aria-label="Edit phone" placeholder="Phone (optional)" value={editForm.user_number} onChange={(e) => setEditForm({ ...editForm, user_number: e.target.value })} />
            <select className="input" aria-label="Edit role" value={editForm.user_role} onChange={(e) => setEditForm({ ...editForm, user_role: e.target.value })}>{ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select><select className="input" aria-label="Edit status" value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}><option value="active">Active</option><option value="disabled">Disabled</option><option value="pending">Pending</option></select>
            <input className="input" aria-label="New password" type="password" placeholder="New password (leave blank to keep)" value={editForm.password} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} />{permissionEditor(editForm.permissions, (permissions) => setEditForm({ ...editForm, permissions }))}
            <div style={{ display: "flex", gap: 8 }}><button className="btn btn-primary btn-sm" disabled={Boolean(busyAction)} onClick={() => void run(`edit-${editingUser.user_id}`, async () => { const payload = { ...editForm }; if (!payload.password) delete payload.password; await api(`/api/users/${editingUser.user_id}`, { method: "PUT", body: JSON.stringify(payload) }); const selfLostAdmin = editingUser.user_id === authUser.user_id && (payload.status !== "active" || payload.user_role !== "System_Admin"); setEditingUser(null); if (selfLostAdmin) { await p.handleLogout(); return; } await p.loadPlatformUsers({ throwOnError: true }); }, "User updated")}>{busyAction === `edit-${editingUser.user_id}` ? "Saving…" : "Save changes"}</button><button className="btn btn-secondary btn-sm" onClick={() => setEditingUser(null)} disabled={Boolean(busyAction)}>Cancel</button></div>
          </div></GlassCard> : null}

          <GlassCard style={{ padding: "1.25rem" }}><h3 style={{ marginTop: 0 }}>Invite user</h3><div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="input" aria-label="Invite name" placeholder="Name" value={p.inviteForm.user_name} onChange={(e) => p.setInviteForm({ ...p.inviteForm, user_name: e.target.value })} /><input className="input" aria-label="Invite email" type="email" placeholder="Email" value={p.inviteForm.user_email} onChange={(e) => p.setInviteForm({ ...p.inviteForm, user_email: e.target.value })} /><select className="input" aria-label="Invite role" value={p.inviteForm.user_role} onChange={(e) => p.setInviteForm({ ...p.inviteForm, user_role: e.target.value })}>{ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select><input className="input" aria-label="Invite phone" placeholder="Phone (optional)" value={p.inviteForm.user_number} onChange={(e) => p.setInviteForm({ ...p.inviteForm, user_number: e.target.value })} />
            {permissionEditor(p.inviteForm.permissions || [], (permissions) => p.setInviteForm({ ...p.inviteForm, permissions }))}<button className="btn btn-primary btn-sm" disabled={Boolean(busyAction)} onClick={() => void run("invite", async () => { const created = await api<any>("/api/users/invite", { method: "POST", body: JSON.stringify(p.inviteForm) }); p.setInviteForm(emptyInvite); await p.loadPlatformUsers({ throwOnError: true }); p.setUsersTab("pending"); return created; }, "Invitation sent")}>{busyAction === "invite" ? "Sending…" : "Send invite"}</button>
          </div></GlassCard>

          <GlassCard style={{ padding: "1.25rem" }}><h3 style={{ marginTop: 0 }}>Add active user</h3><div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="input" aria-label="Create name" placeholder="Name" value={p.userForm.user_name} onChange={(e) => p.setUserForm({ ...p.userForm, user_name: e.target.value })} /><input className="input" aria-label="Create email" type="email" placeholder="Email" value={p.userForm.user_email} onChange={(e) => p.setUserForm({ ...p.userForm, user_email: e.target.value })} /><input className="input" aria-label="Create password" type="password" placeholder="Password" value={p.userForm.password} onChange={(e) => p.setUserForm({ ...p.userForm, password: e.target.value })} /><input className="input" aria-label="Create phone" placeholder="Phone (optional)" value={p.userForm.user_number} onChange={(e) => p.setUserForm({ ...p.userForm, user_number: e.target.value })} /><select className="input" aria-label="Create role" value={p.userForm.user_role} onChange={(e) => p.setUserForm({ ...p.userForm, user_role: e.target.value })}>{ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select>
            {permissionEditor(p.userForm.permissions || [], (permissions) => p.setUserForm({ ...p.userForm, permissions }))}<button className="btn btn-primary btn-sm" disabled={Boolean(busyAction)} onClick={() => void run("create", async () => { await api("/api/users", { method: "POST", body: JSON.stringify(p.userForm) }); p.setUserForm(emptyUser); await p.loadPlatformUsers({ throwOnError: true }); }, "User created")}>{busyAction === "create" ? "Creating…" : "Create user"}</button>
          </div></GlassCard>
        </div>
      </div>
    </div>
  );
}
