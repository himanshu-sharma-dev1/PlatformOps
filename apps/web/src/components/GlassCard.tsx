import React from "react";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "infrastructure" | "helper" | "application";
  onClick?: () => void;
  hoverEffect?: boolean;
  style?: React.CSSProperties;
}

export function GlassCard({ children, className = "", variant = "default", onClick, hoverEffect = true, style }: GlassCardProps) {
  const baseClass = "card";
  const variantClass = variant !== "default" ? variant : "";
  const hoverClass = hoverEffect ? "" : "no-hover";
  
  return (
    <article
      className={`${baseClass} ${variantClass} ${hoverClass} ${className}`.trim()}
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default", ...style }}
    >
      {children}
    </article>
  );
}
