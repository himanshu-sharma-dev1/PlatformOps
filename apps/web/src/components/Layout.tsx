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

export function Layout({ children, activeView, onViewChange, clusterContext, nodeContext, serviceContext }: LayoutProps) {
  // Determine grouping based on view
  let groupName = "Platform";
  let viewName = "Dashboard";
  if (activeView === "config") {
    groupName = "Platform";
    viewName = "Config Manager";
  } else if (activeView === "monitoring") {
    groupName = "Platform";
    viewName = "Services";
  } else if (activeView === "diagnostics") {
    groupName = "Observability";
    viewName = "Diagnostics";
  } else if (activeView === "node-metrics") {
    groupName = "Observability";
    viewName = "Node Metrics";
  } else if (activeView === "observability-stack") {
    groupName = "Observability";
    viewName = "Observability Stack";
  }

  return (
    <div className="app-container">
      <Sidebar activeView={activeView === "dashboard" ? "clusters" : activeView} onViewChange={onViewChange} />
      <div className="main-wrapper">
        <header className="topbar">
          <div className="crumb">
            PlatformOps
            <span className="sep">/</span>
            <span>{groupName}</span>
            <span className="sep">/</span>
            <span 
              className="link" 
              onClick={() => {
                onViewChange(activeView === "config" || activeView === "diagnostics" || activeView === "monitoring" ? activeView : "clusters");
              }}
            >
              {viewName}
            </span>
            {clusterContext && (
              <>
                <span className="sep">/</span>
                <span>{clusterContext}</span>
              </>
            )}
            {nodeContext && (
              <>
                <span className="sep">/</span>
                <span>{nodeContext}</span>
              </>
            )}
            {serviceContext && (
              <>
                <span className="sep">/</span>
                <span>{serviceContext}</span>
              </>
            )}
          </div>
          <div className="topbar-right">
            <button className="icon-btn" title="Search">
              <svg className="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            </button>
            <button className="icon-btn" title="Notifications">
              <svg className="ic" viewBox="0 0 24 24"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></svg>
            </button>
            <button className="icon-btn" title="Help">
              <svg className="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01"/></svg>
            </button>
          </div>
        </header>
        <main className="content-area">
          {children}
        </main>
      </div>
    </div>
  );
}
