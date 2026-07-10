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
          <div className="topbar-right">
            <span className="env-pill">Live</span>
          </div>
        </header>
        <main className="content-area">{children}</main>
      </div>
    </div>
  );
}
