#!/usr/bin/env python3
"""Phase 1: extract all render* JSX from PlatformProvider into views/components."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"


def extract_function(src: str, name: str) -> tuple[str, int, int]:
    m = re.search(rf"\n  function {name}\(", src)
    if not m:
        raise SystemExit(f"missing {name}")
    start = m.start() + 1
    brace = src.find("{", start)
    depth = 0
    i = brace
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1], start, i + 1
        i += 1
    raise SystemExit(f"unbalanced {name}")


def dedent_body(inner: str, spaces: int = 2) -> str:
    lines = inner.splitlines()
    out = []
    for ln in lines:
        if ln.startswith(" " * spaces):
            out.append(ln[spaces:])
        else:
            out.append(ln)
    return "\n".join(out)


def main() -> None:
    provider_path = ROOT / "platform" / "PlatformProvider.tsx"
    text = provider_path.read_text()

    mapping = {
        "renderConfigManagerView": ("views/ConfigView.tsx", "ConfigView"),
        "renderAiChat": ("views/LogAnalystChat.tsx", "LogAnalystChat"),
        "renderDiagnosticsView": ("views/DiagnosticsView.tsx", "DiagnosticsView"),
        "renderGlitchTipWorkspace": ("views/GlitchTipWorkspace.tsx", "GlitchTipWorkspace"),
        "renderMonitoringView": ("views/MonitoringView.tsx", "MonitoringView"),
        "renderDrawers": ("views/DrawersHost.tsx", "DrawersHost"),
        "renderModals": ("views/ModalsHost.tsx", "ModalsHost"),
        "renderPerformanceView": ("views/PerformanceView.tsx", "PerformanceView"),
        "renderObservabilityStackView": ("views/ObservabilityView.tsx", "ObservabilityView"),
        "renderTopologyView": ("views/TopologyView.tsx", "TopologyView"),
        "renderPolicyView": ("views/PolicyView.tsx", "PolicyView"),
        "renderAuditView": ("views/AuditView.tsx", "AuditView"),
        "renderReliabilityView": ("views/ReliabilityView.tsx", "ReliabilityView"),
        "renderUsersView": ("views/UsersView.tsx", "UsersView"),
        "renderTreeNavigator": ("components/TreeNavigator.tsx", "TreeNavigator"),
    }

    api_fields: set[str] = set()
    api_m = re.search(r"const platformApi = \{([\s\S]*?)\} as PlatformApi", text)
    if api_m:
        for line in api_m.group(1).splitlines():
            line = line.strip().rstrip(",")
            if line and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", line):
                api_fields.add(line)
    for a, b in re.findall(r"const \[(\w+), (set\w+)\] = useState", text):
        api_fields.add(a)
        api_fields.add(b)
    for n in re.findall(r"\n  (?:async )?function (\w+)\(", text):
        api_fields.add(n)

    ranges: list[tuple[int, int, str, str, str, str]] = []
    for method, (rel, comp) in mapping.items():
        body, start, end = extract_function(text, method)
        ranges.append((start, end, method, rel, comp, body))

    chart_set = {
        "isSeedDemoName",
        "formatExpiry",
        "renderSVGTimeSeriesChart",
        "SvgTimeSeriesChart",
        "renderMetricSparkline",
        "renderMetricWindowPicker",
        "renderCircularGauge",
        "renderUptimeAvailabilityBlocks",
        "uptimeLatencySeries",
    }

    for start, end, method, rel, comp, body in ranges:
        inner = body[body.find("{") + 1 : body.rfind("}")]
        inner = dedent_body(inner, 2)
        ids = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", inner))
        used = sorted((ids & api_fields) - {method})

        imports = [
            "// @ts-nocheck",
            'import React from "react";',
            'import { GlassCard } from "../components/GlassCard";',
            'import { usePlatform } from "../platform/usePlatform";',
        ]
        chart_helpers = [h for h in sorted(chart_set) if h in ids]
        if chart_helpers:
            imports.append(f'import {{ {", ".join(chart_helpers)} }} from "../components/charts";')

        if method == "renderTreeNavigator":
            bind_lines = [f"  const {u} = (p as any).{u};" for u in used]
            binds = "\n".join(bind_lines)
            file_body = "\n".join(imports) + f"""

/**
 * Imperative tree navigator (legacy call shape).
 * treeNavigator(onSelectService, activeServiceId?, options?)
 */
export function treeNavigator(onSelectService: any, activeServiceId: any = null, options: any = {{}}) {{
  const p = usePlatform() as any;
{binds}
{inner}
}}

export function TreeNavigator(props: {{
  onSelectService: any;
  activeServiceId?: any;
  options?: any;
}}) {{
  return treeNavigator(props.onSelectService, props.activeServiceId ?? null, props.options ?? {{}});
}}
"""
        else:
            inner2 = inner
            inner2 = inner2.replace("renderGlitchTipWorkspace()", "<GlitchTipWorkspace />")
            inner2 = inner2.replace("{renderGlitchTipWorkspace()}", "{<GlitchTipWorkspace />}")
            inner2 = inner2.replace("renderAiChat()", "<LogAnalystChat />")
            inner2 = inner2.replace("{renderAiChat()}", "{<LogAnalystChat />}")
            inner2 = inner2.replace("renderTreeNavigator(", "treeNavigator(")

            extra: list[str] = []
            if "GlitchTipWorkspace" in inner2:
                extra.append('import { GlitchTipWorkspace } from "./GlitchTipWorkspace";')
            if "LogAnalystChat" in inner2:
                extra.append('import { LogAnalystChat } from "./LogAnalystChat";')
            if "treeNavigator(" in inner2:
                # path differs for views vs components — views use ../components
                if rel.startswith("views/"):
                    extra.append('import { treeNavigator } from "../components/TreeNavigator";')
                else:
                    extra.append('import { treeNavigator } from "./TreeNavigator";')

            bind_lines = [f"  const {u} = p.{u};" for u in used]
            binds = "\n".join(bind_lines)
            file_body = "\n".join(imports + extra) + f"""

/** {comp} — Phase 1 extracted page JSX. */
export function {comp}() {{
  const p = usePlatform() as any;
{binds}

{inner2}
}}
"""

        out_path = ROOT / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file_body)
        print(f"wrote {rel} ({file_body.count(chr(10)) + 1} lines, {len(used)} binds)")

    # Stub methods in provider (reverse order by start)
    new_text = text
    for start, end, method, rel, comp, body in sorted(ranges, key=lambda x: -x[0]):
        stub = f"  function {method}(..._args: any[]) {{\n    return null;\n  }}"
        new_text = new_text[:start] + stub + new_text[end:]

    provider_path.write_text(new_text)
    print("provider lines", new_text.count("\n") + 1)


if __name__ == "__main__":
    main()
