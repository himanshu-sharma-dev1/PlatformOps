import React from "react";

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo">P</div>
        <div className="name">PlatformOps</div>
      </div>
      
      <div className="sb-group">Infrastructure</div>
      <button 
        className={`sb-item ${activeView === "clusters" ? "active" : ""}`}
        onClick={() => onViewChange("clusters")}
      >
        <svg className="ico" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 10v6m11-11h-6M7 12H1"/></svg>
        Clusters
      </button>
      <button 
        className={`sb-item ${activeView === "config" ? "active" : ""}`}
        onClick={() => onViewChange("config")}
      >
        <svg className="ico" viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
        Config Mgr
      </button>

      <div className="sb-group">Observability</div>
      <button 
        className={`sb-item ${activeView === "monitoring" ? "active" : ""}`}
        onClick={() => onViewChange("monitoring")}
      >
        <svg className="ico" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        Monitoring
      </button>
      <button 
        className={`sb-item ${activeView === "diagnostics" ? "active" : ""}`}
        onClick={() => onViewChange("diagnostics")}
      >
        <svg className="ico" viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        Diagnostics
      </button>

      <div className="sb-foot">
        <div className="avatar">SA</div>
        <div className="who">
          Sandhya Arora
          <div className="role">System admin</div>
        </div>
      </div>
    </aside>
  );
}
