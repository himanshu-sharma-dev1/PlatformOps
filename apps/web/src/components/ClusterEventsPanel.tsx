// @ts-nocheck
import React from "react";
import { eventsCountLabel, formatClusterEventRow } from "../platform/ux/clusterUx";

/**
 * cPlatform-style events panel (renderEvents parity).
 * Used by node Events tab, service drawer Events, node info drawer.
 */
export function ClusterEventsPanel({
  events = [],
  loading = false,
  emptyMsg = "No events",
  max = 40,
  formatLocalTimestamp,
  statusId,
}: {
  events?: any[];
  loading?: boolean;
  emptyMsg?: string;
  max?: number;
  formatLocalTimestamp?: (v: any) => string;
  statusId?: string;
}) {
  const list = Array.isArray(events) ? events : [];
  const shown = list.slice(0, max);
  const status = eventsCountLabel(list.length, loading && list.length === 0);

  return (
    <div className="cp-events-panel" data-ux="cluster-events-panel">
      <div
        className="events-status-line"
        data-ux={statusId || "events-status"}
        style={{ marginBottom: 8 }}
      >
        {status}
      </div>
      {loading && list.length === 0 ? (
        <div className="detail-loading-shell is-loading">
          <span className="pulse-dot" /> Loading events…
        </div>
      ) : shown.length === 0 ? (
        <div style={{ color: "var(--ink-4)", fontSize: "0.85rem" }}>{emptyMsg}</div>
      ) : (
        <div className="cp-events-list" style={{ maxHeight: 360, overflow: "auto" }}>
          {shown.map((ev, idx) => {
            const row = formatClusterEventRow(ev);
            const when =
              row.when ||
              (ev.created_at && formatLocalTimestamp
                ? formatLocalTimestamp(ev.created_at)
                : row.when);
            const pillClass =
              row.level === "error" || row.level === "critical"
                ? "pill-error"
                : row.level === "warning" || row.level === "warn"
                  ? "pill-warn"
                  : "pill-ok";
            return (
              <div
                key={ev.id ?? `ev-${idx}`}
                className="cp-event-row"
                style={{
                  padding: "6px 0",
                  borderBottom: "1px dashed var(--line)",
                  fontSize: "0.85rem",
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span className={`pill ${pillClass}`} style={{ fontSize: "0.65rem" }}>
                    {row.category}
                  </span>
                  <strong style={{ fontWeight: 600 }}>{row.title}</strong>
                  {when ? (
                    <span style={{ color: "var(--ink-4)", fontSize: "0.75rem" }}>({when})</span>
                  ) : null}
                </div>
                <div style={{ color: "var(--ink-2)", marginTop: 2 }}>{row.message}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
