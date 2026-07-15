import React from "react";

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

const NAV: Array<{
  group: string;
  muted?: boolean;
  items: Array<{ id: string; label: string; icon: React.ReactNode }>;
}> = [
  {
    group: "Platform",
    items: [
      {
        id: "clusters",
        label: "Clusters",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M19.1 4.9l-2.8 2.8M7.7 16.3l-2.8 2.8" />
          </svg>
        ),
      },
      {
        id: "config",
        label: "Config Manager",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
          </svg>
        ),
      },
      {
        id: "users",
        label: "Users",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
          </svg>
        ),
      },
    ],
  },
  {
    group: "Observability",
    items: [
      {
        id: "monitoring",
        label: "Monitoring",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
        ),
      },
      {
        id: "performance",
        label: "Performance",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M3 3v18h18" />
            <path d="M7 14l4-4 4 3 5-7" />
          </svg>
        ),
      },
      {
        id: "diagnostics",
        label: "Diagnostics",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
          </svg>
        ),
      },
      {
        id: "observability",
        label: "Observability stack",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        ),
      },
    ],
  },
  {
    // Kept in UI; cluster inventory refresh does NOT load these APIs (code detangled)
    group: "Advanced",
    muted: true,
    items: [
      {
        id: "topology",
        label: "Topology",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <circle cx="6" cy="6" r="2" />
            <circle cx="18" cy="6" r="2" />
            <circle cx="12" cy="18" r="2" />
            <path d="M8 7l3 9M16 7l-3 9M8 6h8" />
          </svg>
        ),
      },
      {
        id: "policy",
        label: "Policy",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z" />
          </svg>
        ),
      },
      {
        id: "audit",
        label: "Audit",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
            <rect x="9" y="3" width="6" height="4" rx="1" />
            <path d="M9 12h6M9 16h4" />
          </svg>
        ),
      },
      {
        id: "reliability",
        label: "Reliability",
        icon: (
          <svg className="ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M12 9v4M12 17h.01" />
            <path d="M10.3 3.3L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.3a2 2 0 00-3.4 0z" />
          </svg>
        ),
      },
    ],
  },
];

export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  const view = activeView === "dashboard" ? "clusters" : activeView;

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo">P</div>
        <div>
          <div className="name">PlatformOps</div>
          <div className="brand-sub">Control plane</div>
        </div>
      </div>

      <nav className="sb-nav" aria-label="Primary">
        {NAV.map((section) => (
          <div key={section.group} className={`sb-section ${section.muted ? "sb-section-muted" : ""}`}>
            <div className="sb-group">
              {section.group}
              {section.muted ? <span className="sb-group-hint"> secondary</span> : null}
            </div>
            {section.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`sb-item ${view === item.id ? "active" : ""}`}
                onClick={() => onViewChange(item.id)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sb-foot">
        <div className="avatar">OP</div>
        <div className="who">
          Operator
          <div className="role">Live environment</div>
        </div>
      </div>
    </aside>
  );
}
