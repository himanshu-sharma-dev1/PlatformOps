import React, { useState } from "react";
import type { MetricPoint, MetricWindow } from "../types";

export function formatExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "no expiry";
  const expiry = new Date(expiresAt).getTime();
  const now = Date.now();
  const deltaMs = expiry - now;
  if (deltaMs <= 0) return "expired";
  const totalMinutes = Math.floor(deltaMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${minutes}m remaining`;
}


export function renderSVGTimeSeriesChart(
  series: MetricPoint[],
  opts?: { color?: string; unit?: string; height?: number },
): React.ReactNode {
  const color = opts?.color || "#60a5fa";
  const height = opts?.height ?? 80;
  const width = 320;
  if (!series || series.length === 0) {
    return <div style={{ color: "var(--ink-4)", fontSize: "0.8rem", padding: "0.5rem 0" }}>No series data</div>;
  }
  const values = series.map((p) => Number(p.value) || 0);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = Math.max(max - min, 1e-6);
  const coords = series.map((p, i) => {
    const x = (i / Math.max(series.length - 1, 1)) * (width - 8) + 4;
    const y = height - 8 - ((Number(p.value) - min) / span) * (height - 16);
    return { x, y, p };
  });
  const pts = coords.map((c) => `${c.x},${c.y}`);
  const area = `4,${height - 4} ${pts.join(" ")} ${width - 4},${height - 4}`;
  return (
    <SvgTimeSeriesChart
      series={series}
      coords={coords}
      pts={pts}
      area={area}
      color={color}
      height={height}
      width={width}
      unit={opts?.unit || ""}
    />
  );
}

export function SvgTimeSeriesChart({
  series,
  coords,
  pts,
  area,
  color,
  height,
  width,
  unit,
}: {
  series: MetricPoint[];
  coords: Array<{ x: number; y: number; p: MetricPoint }>;
  pts: string[];
  area: string;
  color: string;
  height: number;
  width: number;
  unit: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const active = hover != null ? coords[hover] : null;
  return (
    <div style={{ position: "relative", width: "100%" }}>
      {active && (
        <div
          style={{
            position: "absolute",
            left: `calc(${(active.x / width) * 100}% - 40px)`,
            top: Math.max(0, active.y - 28),
            zIndex: 2,
            pointerEvents: "none",
            background: "rgba(2,4,8,0.92)",
            border: "1px solid var(--line-2)",
            borderRadius: 6,
            padding: "2px 6px",
            fontSize: "0.72rem",
            color: "var(--ink-1)",
            whiteSpace: "nowrap",
          }}
        >
          {active.p.label}: <strong>{active.p.value}{unit}</strong>
        </div>
      )}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        style={{ display: "block" }}
        onMouseLeave={() => setHover(null)}
      >
        <polygon points={area} fill={color} opacity={0.12} />
        <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2" />
        {active && (
          <>
            <line x1={active.x} y1={4} x2={active.x} y2={height - 4} stroke={color} strokeOpacity={0.35} strokeDasharray="3 3" />
            <circle cx={active.x} cy={active.y} r={4.5} fill={color} stroke="#020408" strokeWidth={1.5} />
          </>
        )}
        {coords.map((c, i) => (
          <circle
            key={`${c.p.label}-${i}`}
            cx={c.x}
            cy={c.y}
            r={hover === i ? 4 : 2.5}
            fill={color}
            style={{ cursor: "crosshair" }}
            onMouseEnter={() => setHover(i)}
          >
            <title>{`${c.p.label}: ${c.p.value}${unit}`}</title>
          </circle>
        ))}
        {/* hit targets for sparse series */}
        {coords.map((c, i) => (
          <rect
            key={`hit-${i}`}
            x={Math.max(0, c.x - (width / Math.max(series.length, 1)) / 2)}
            y={0}
            width={Math.max(8, width / Math.max(series.length, 1))}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>
    </div>
  );
}

export function renderUptimeAvailabilityBlocks(checks: any[]): React.ReactNode {
  const blocks = (checks || []).slice(0, 48);
  if (blocks.length === 0) {
    return <div style={{ fontSize: "0.8rem", color: "var(--ink-4)" }}>No check history yet.</div>;
  }
  return (
    <div style={{ display: "flex", gap: 2, flexWrap: "wrap", marginTop: 8 }}>
      {blocks.map((c, i) => {
        const up = c.isUp === true || c.status === "ok" || c.status === "up" || String(c.statusCode || "").startsWith("2");
        return (
          <div
            key={i}
            title={`${up ? "UP" : "DOWN"} · ${c.startCheck || c.dateCreated || c.timestamp || ""}`}
            style={{
              width: 10,
              height: 22,
              borderRadius: 2,
              background: up ? "var(--ok)" : "var(--err)",
              opacity: 0.85,
            }}
          />
        );
      })}
    </div>
  );
}

export function uptimeLatencySeries(checks: any[]): MetricPoint[] {
  return (checks || [])
    .map((c: any, i: number) => {
      const ms = Number(c.durationMs ?? c.duration ?? c.responseTime ?? c.latency_ms ?? NaN);
      if (!Number.isFinite(ms)) return null;
      const label = c.startCheck || c.dateCreated || `#${i + 1}`;
      return { label: String(label).slice(0, 19), value: ms } as MetricPoint;
    })
    .filter(Boolean) as MetricPoint[];
}

export function renderMetricSparkline(series: MetricPoint[], color: string) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: "44px", marginTop: "0.5rem" }}>
      {series.map((point) => (
        <div
          key={`${point.label}-${point.value}`}
          title={`${point.label}: ${point.value}`}
          style={{
            flex: 1,
            minWidth: "8px",
            height: `${Math.max(12, Math.min(100, point.value))}%`,
            borderRadius: "4px 4px 0 0",
            background: color,
            opacity: 0.85,
          }}
        />
      ))}
    </div>
  );
}

export function renderMetricWindowPicker(
  value: MetricWindow,
  onChange: (window: MetricWindow) => void,
): React.ReactNode {
  return (
    <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
      {(["1h", "6h", "24h", "7d", "1M", "3M"] as MetricWindow[]).map((window) => (
        <button
          key={window}
          type="button"
          className={`btn btn-sm ${value === window ? "btn-primary" : "btn-secondary"}`}
          onClick={() => onChange(window)}
        >
          {window}
        </button>
      ))}
    </div>
  );
}

export function renderCircularGauge(value: number, target: number, label: string, color: string) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(value, 100) / 100) * circumference;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", flex: 1, minWidth: "120px" }}>
      <div style={{ position: "relative", width: "80px", height: "80px" }}>
        <svg style={{ transform: "rotate(-90deg)", width: "80px", height: "80px" }}>
          {/* Background Circle */}
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke="rgba(255, 255, 255, 0.05)"
            strokeWidth="6"
            fill="transparent"
          />
          {/* Foreground Circle */}
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke={color}
            strokeWidth="6"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.5s ease-in-out" }}
          />
        </svg>
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "80px",
          height: "80px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          lineHeight: 1
        }}>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>{value}%</span>
          <span style={{ fontSize: "0.6rem", color: "var(--ink-4)", marginTop: "3px" }}>target {target}%</span>
        </div>
      </div>
      <strong style={{ fontSize: "0.8rem", color: "var(--ink-2)", textAlign: "center" }}>{label}</strong>
    </div>
  );
}



export function isSeedDemoName(name: string | null | undefined): boolean {
  const n = (name || "").toLowerCase();
  if (!n) return false;
  return (
    n.startsWith("e2e-") ||
    n.startsWith("verify-node-") ||
    n.startsWith("parity-cl-") ||
    n.includes("e2e-cluster") ||
    n.includes("e2e-node") ||
    n.includes("seed_demo") ||
    n.includes("seed-demo")
  );
}

