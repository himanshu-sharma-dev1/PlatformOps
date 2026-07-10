// @ts-nocheck
import React from "react";
import { GlassCard } from "../components/GlassCard";
import { usePlatform } from "../platform/usePlatform";

/** AuditView — Phase 1 extracted page JSX. */
export function AuditView() {
  const p = usePlatform() as any;
  const auditExports = p.auditExports;
  const createAuditExport = p.createAuditExport;
  const events = p.events;
  const formatLocalTimestamp = p.formatLocalTimestamp;
  const lifecycleAudit = p.lifecycleAudit;
  const refresh = p.refresh;


  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div className="page-head">
        <div className="titles">
          <h1>Audit</h1>
          <p className="sub">Operations timeline and exportable audit trails. Secondary to primary platform workflows.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refresh()}>Refresh events</button>
          <button className="btn btn-primary btn-sm" onClick={createAuditExport}>Export audit trail</button>
        </div>
      </div>
      <div className="stat-strip">
        <div className="stat-tile"><div className="stat-label">Events</div><div className="stat-value">{events.length}</div></div>
        <div className="stat-tile"><div className="stat-label">Exports</div><div className="stat-value">{auditExports.length}</div></div>
        <div className="stat-tile"><div className="stat-label">Lifecycle (72h)</div><div className="stat-value">{lifecycleAudit?.total_lifecycle_events ?? "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Blocked deletes</div><div className="stat-value">{lifecycleAudit?.blocked_deletions ?? "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Forced deletes</div><div className="stat-value">{lifecycleAudit?.forced_deletions ?? "—"}</div></div>
        <div className="stat-tile"><div className="stat-label">Safe deletes</div><div className="stat-value">{lifecycleAudit?.safe_deletions ?? "—"}</div></div>
      </div>
      {lifecycleAudit && (
        <GlassCard style={{ padding: "1rem 1.25rem" }}>
          <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", fontSize: "0.85rem", color: "var(--ink-3)" }}>
            <span>Last blocked: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_blocked_at ? formatLocalTimestamp(lifecycleAudit.last_blocked_at) : "—"}</strong></span>
            <span>Last forced: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_forced_at ? formatLocalTimestamp(lifecycleAudit.last_forced_at) : "—"}</strong></span>
            <span>Last safe delete: <strong style={{ color: "var(--ink-1)" }}>{lifecycleAudit.last_safe_delete_at ? formatLocalTimestamp(lifecycleAudit.last_safe_delete_at) : "—"}</strong></span>
          </div>
        </GlassCard>
      )}
      <GlassCard style={{ padding: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Recent operational events</h2>
        <div className="timeline" style={{ maxHeight: 480, overflow: "auto" }}>
          {events.slice(0, 80).map((ev) => (
            <article key={ev.id}>
              <span className={`pill ${ev.level === "error" ? "pill-error" : ev.level === "warning" ? "pill-warn" : "pill-ok"}`}>{ev.category || "event"}</span>
              <strong>{ev.message}</strong>
              <small style={{ color: "var(--ink-4)" }}>{formatLocalTimestamp(ev.created_at)}</small>
            </article>
          ))}
          {events.length === 0 && <p style={{ color: "var(--ink-4)" }}>No events loaded.</p>}
        </div>
      </GlassCard>
      {auditExports.length > 0 && (
        <GlassCard style={{ padding: "1.25rem" }}>
          <h3 style={{ marginTop: 0 }}>Exports</h3>
          {auditExports.map((ex) => (
            <div key={ex.id} style={{ fontSize: "0.85rem", padding: "0.4rem 0", borderBottom: "1px solid var(--line-2)" }}>
              <code>{ex.artifact_path}</code> · {ex.status} · {ex.export_type}
            </div>
          ))}
        </GlassCard>
      )}
    </div>
  );

}
