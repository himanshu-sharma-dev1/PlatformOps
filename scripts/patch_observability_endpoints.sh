#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/patch_observability_endpoints.sh [--env <env-file>] [--ip <primary-node-ip>] [--glitchtip-port <port>] [--loki-ingest-port <port>] [--dry-run]

Description:
  Repo-relative endpoint patcher for selected observability files.
  Targets:
    - platform/observability/glitchtip.env
    - platform/observability/glitchtip_runtime_map.yaml
    - platform/observability/config.alloy
    - platform/docker/cPlatform/diagnostics.validation.env
    - platform/docker/cPlatform/deployment.env
    - platform/docker/cPlatform/deployment.validation.env
    - platform/docker/optionCopilot/deployment.env
    - platform/docker/airtelChurn/deployment.env
    - cPlatform/ProxyChurn/views.py

Options:
  --env <env-file>            Env file with values (default: scripts/observability_endpoints.env if present)
  --ip <ip>                   Primary/control-plane IP override
  --glitchtip-port <port>     GlitchTip host port override (default: 9008)
  --loki-ingest-port <port>   Loki ingest host port override (default: 9011)
  --dry-run                   Print what would change without writing files
  -h, --help                  Show help

Env keys supported:
  CPLATFORM_PRIMARY_NODE_IP
  CPLATFORM_GLITCHTIP_PORT
  CPLATFORM_LOKI_INGEST_PORT
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${SCRIPT_DIR}/observability_endpoints.env"
CLI_IP=""
CLI_GLITCHTIP_PORT=""
CLI_LOKI_INGEST_PORT=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    --ip)
      CLI_IP="$2"
      shift 2
      ;;
    --glitchtip-port)
      CLI_GLITCHTIP_PORT="$2"
      shift 2
      ;;
    --loki-ingest-port)
      CLI_LOKI_INGEST_PORT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

PRIMARY_IP="${CLI_IP:-${CPLATFORM_PRIMARY_NODE_IP:-}}"
GLITCHTIP_PORT="${CLI_GLITCHTIP_PORT:-${CPLATFORM_GLITCHTIP_PORT:-9008}}"
LOKI_INGEST_PORT="${CLI_LOKI_INGEST_PORT:-${CPLATFORM_LOKI_INGEST_PORT:-9011}}"

if [[ -z "$PRIMARY_IP" ]]; then
  if [[ -f "${REPO_ROOT}/platform/docker/cPlatform/diagnostics.validation.env" ]]; then
    PRIMARY_IP="$(grep -E '^CPLATFORM_PRIMARY_NODE_IP=' "${REPO_ROOT}/platform/docker/cPlatform/diagnostics.validation.env" | head -n1 | cut -d'=' -f2-)"
  fi
fi

if [[ -z "$PRIMARY_IP" ]]; then
  echo "Missing primary node IP. Set CPLATFORM_PRIMARY_NODE_IP in env file or pass --ip." >&2
  exit 2
fi

python3 - "$REPO_ROOT" "$PRIMARY_IP" "$GLITCHTIP_PORT" "$LOKI_INGEST_PORT" "$DRY_RUN" <<'PY'
import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
primary_ip = sys.argv[2].strip()
glitchtip_port = str(sys.argv[3]).strip()
loki_ingest_port = str(sys.argv[4]).strip()
dry_run = sys.argv[5] == "1"

files = [
    "platform/observability/glitchtip.env",
    "platform/observability/glitchtip_runtime_map.yaml",
    "platform/observability/config.alloy",
    "platform/docker/cPlatform/diagnostics.validation.env",
    "platform/docker/cPlatform/deployment.env",
    "platform/docker/cPlatform/deployment.validation.env",
    "platform/docker/optionCopilot/deployment.env",
    "platform/docker/airtelChurn/deployment.env",
    "cPlatform/ProxyChurn/views.py",
    "cPlatform/config/cPlatform_config.yaml",
    "cPlatform/cPlatformIO/src/ServiceDiagnostics.py",
    "newUITmp/mockups/11-monitoring.html",
]

changed = []


def rewrite(path: Path, text: str) -> str:
    rel = path.as_posix()
    out = text

    if rel.endswith("glitchtip.env"):
        lines = out.splitlines()
        file_changed = False
        has_domain = False
        for idx, line in enumerate(lines):
            if line.startswith("GLITCHTIP_DOMAIN="):
                new_val = f"GLITCHTIP_DOMAIN=http://{primary_ip}:{glitchtip_port}"
                if lines[idx] != new_val:
                    lines[idx] = new_val
                    file_changed = True
                has_domain = True
            elif line.startswith("GLITCHTIP_IFRAME_ANCESTORS="):
                new_val = f"GLITCHTIP_IFRAME_ANCESTORS=http://{primary_ip},http://{primary_ip}:80,https://{primary_ip},https://{primary_ip}:443"
                if lines[idx] != new_val:
                    lines[idx] = new_val
                    file_changed = True
            elif line.startswith("GLITCHTIP_IFRAME_CSRF_TRUSTED_ORIGINS="):
                new_val = f"GLITCHTIP_IFRAME_CSRF_TRUSTED_ORIGINS=http://{primary_ip},https://{primary_ip}"
                if lines[idx] != new_val:
                    lines[idx] = new_val
                    file_changed = True
        if not has_domain:
            lines.append(f"GLITCHTIP_DOMAIN=http://{primary_ip}:{glitchtip_port}")
            file_changed = True
        if file_changed:
            out = "\n".join(lines) + "\n"

    if rel.endswith("diagnostics.validation.env"):
        lines = out.splitlines()
        file_changed = False
        keys = {
            "CPLATFORM_PRIMARY_NODE_IP": primary_ip,
            "CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL": f"http://{primary_ip}:{loki_ingest_port}",
            "CPLATFORM_GLITCHTIP_BASE_URL": f"http://{primary_ip}:{glitchtip_port}",
        }
        existing = {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}
        for idx, line in enumerate(lines):
            for key, value in keys.items():
                if line.startswith(f"{key}="):
                    if line != f"{key}={value}":
                        lines[idx] = f"{key}={value}"
                        file_changed = True
        for key, value in keys.items():
            if key not in existing:
                lines.append(f"{key}={value}")
                file_changed = True
        if file_changed:
            out = "\n".join(lines) + "\n"

    if rel.endswith("deployment.env") or rel.endswith("deployment.validation.env") or rel.endswith("glitchtip_runtime_map.yaml"):
        out = re.sub(
            r'(^(?:#\s*)?(?:\s*dsn:\s*|GLITCHTIP_DSN=|SENTRY_DSN=)https?://[^@]+@)[^/:]+(?::\d+)?(/\S+)$',
            rf'\g<1>{primary_ip}:{glitchtip_port}\g<2>',
            out,
            flags=re.M,
        )

    if rel.endswith("config.alloy"):
        out = re.sub(r'(node_ip\s*=\s*)"[^"]+"', rf'\g<1>"{primary_ip}"', out)
        out = re.sub(r'(replacement\s*=\s*)"(?:[0-9]{1,3}\.){3}[0-9]{1,3}"(\s*\n\s*target_label\s*=\s*"node_ip")', rf'\g<1>"{primary_ip}"\g<2>', out)

    if rel.endswith("views.py"):
        out = re.sub(r'\("((?:[0-9]{1,3}\.){3}[0-9]{1,3})",\s*9000\)', lambda m: f'("{primary_ip}", 9000)' if m.group(1) != "127.0.0.1" else m.group(0), out)

    if rel.endswith("airtelChurn/deployment.env"):
        out = re.sub(r'^airflow_host=.*$', f'airflow_host={primary_ip}', out, flags=re.M)

    if rel.endswith("cPlatform_config.yaml"):
        out = re.sub(r'(prometheus_server_ip:\s*)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', rf'\g<1>{primary_ip}', out)
        out = re.sub(r'(master_host:\s*)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', rf'\g<1>{primary_ip}', out)
        out = re.sub(r'(service_ip:\s*)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', rf'\g<1>{primary_ip}', out)
        out = re.sub(r'(cplatform_url:\s*https?://)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', rf'\g<1>{primary_ip}', out)

    if rel.endswith("ServiceDiagnostics.py"):
        out = re.sub(r'(primary_node else\s*)"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"', rf'\g<1>"{primary_ip}"', out)

    if rel.endswith("11-monitoring.html"):
        out = re.sub(r'(src="http://)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/glitchtip/")', rf'\g<1>{primary_ip}\g<2>', out)

    return out

for rel in files:
    path = repo_root / rel
    if not path.exists():
        continue
    original = path.read_text(encoding="utf-8")
    updated = rewrite(path, original)
    if updated != original:
        changed.append(rel)
        if not dry_run:
            path.write_text(updated, encoding="utf-8")

print(f"repo_root={repo_root}")
print(f"primary_ip={primary_ip}")
print(f"glitchtip_port={glitchtip_port}")
print(f"loki_ingest_port={loki_ingest_port}")
print(f"dry_run={str(dry_run).lower()}")
if changed:
    print("changed_files:")
    for rel in changed:
        print(f"  - {rel}")
else:
    print("changed_files: none")
PY
