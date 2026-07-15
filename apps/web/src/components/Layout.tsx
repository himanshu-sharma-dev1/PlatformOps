import React from "react";
import { Sidebar } from "./Sidebar";

interface LayoutProps {
  children: React.ReactNode;
  activeView: string;
  onViewChange: (view: string) => void;
  clusterContext?: string | null;
  nodeContext?: string | null;
  serviceContext?: string | null;
}

const VIEW_META: Record<string, { group: string; title: string }> = {
  clusters: { group: "Platform", title: "Clusters" },
  config: { group: "Platform", title: "Config Manager" },
  users: { group: "Platform", title: "Users" },
  monitoring: { group: "Observability", title: "Monitoring" },
  performance: { group: "Observability", title: "Performance" },
  diagnostics: { group: "Observability", title: "Diagnostics" },
  observability: { group: "Observability", title: "Observability stack" },
  topology: { group: "Advanced", title: "Topology" },
  policy: { group: "Advanced", title: "Policy" },
  audit: { group: "Advanced", title: "Audit" },
  reliability: { group: "Advanced", title: "Reliability" },
};

export function Layout({
  children,
  activeView,
  onViewChange,
  clusterContext,
  nodeContext,
  serviceContext,
}: LayoutProps) {
  const view = activeView === "dashboard" ? "clusters" : activeView;
  const meta = VIEW_META[view] || VIEW_META.clusters;

  const [theme, setTheme] = React.useState(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("platformops-theme");
      if (stored) return stored;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return "dark";
  });

  React.useEffect(() => {
    if (theme === "light") {
      document.body.classList.add("light-theme");
    } else {
      document.body.classList.remove("light-theme");
    }
    localStorage.setItem("platformops-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  return (
    <div className="app-container">
      <Sidebar activeView={view} onViewChange={onViewChange} />
      <div className="main-wrapper">
        <header className="topbar">
          <div className="crumb">
            <button type="button" className="crumb-root" onClick={() => onViewChange("clusters")}>
              PlatformOps
            </button>
            <span className="sep">/</span>
            <span className="crumb-group">{meta.group}</span>
            <span className="sep">/</span>
            <button type="button" className="crumb-link" onClick={() => onViewChange(view)}>
              {meta.title}
            </button>
            {clusterContext ? (
              <>
                <span className="sep">/</span>
                <span className="crumb-ctx">{clusterContext}</span>
              </>
            ) : null}
            {nodeContext ? (
              <>
                <span className="sep">/</span>
                <span className="crumb-ctx">{nodeContext}</span>
              </>
            ) : null}
            {serviceContext ? (
              <>
                <span className="sep">/</span>
                <span className="crumb-ctx">{serviceContext}</span>
              </>
            ) : null}
          </div>
          <div className="topbar-right" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              type="button"
              className="theme-toggle-btn"
              onClick={toggleTheme}
              style={{
                background: "none",
                border: "none",
                color: "var(--ink-3)",
                cursor: "pointer",
                padding: 4,
                display: "flex",
                alignItems: "center"
              }}
              title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
            >
              {theme === "light" ? (
                <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
              ) : (
                <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
              )}
            </button>
            <span className="env-pill">Live</span>
          </div>
        </header>
        <main className="content-area">{children}</main>
      </div>
    </div>
  );
}
