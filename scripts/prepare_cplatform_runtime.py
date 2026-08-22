#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import socket
from pathlib import Path

import yaml

REQUIRED_SOURCE_PATHS = [
    "MCPClient",
    "CutilJS",
    "ModelStore",
    "CommonUtils",
]


def detect_host_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()
    return normalized or "source"


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def resolve_contract_value(raw_value: str, *, service_volume: str, machine_volume: str, service_name: str) -> str:
    resolved = str(raw_value or "")
    replacements = {
        "{{ service_volume }}": service_volume.rstrip("/"),
        "{{ machine_volume }}": machine_volume.rstrip("/"),
        "{{ service }}": service_name.strip(),
    }
    for token, replacement in replacements.items():
        resolved = resolved.replace(token, replacement)
    if resolved.startswith("//"):
        resolved = "/" + resolved.lstrip("/")
    return resolved


def path_is_covered_by_volume(candidate_path: str, volume_sources: list[str]) -> bool:
    normalized_candidate = str(candidate_path or "").rstrip("/")
    if not normalized_candidate:
        return False
    for volume_path in volume_sources:
        normalized_volume = str(volume_path or "").rstrip("/")
        if not normalized_volume:
            continue
        if normalized_candidate == normalized_volume:
            return True
        if normalized_candidate.startswith(normalized_volume + "/"):
            return True
    return False


def resolve_host_volume_sources(volume_values, service_volume: str, machine_volume: str, service_name: str) -> list[str]:
    sources: list[str] = []
    for value in volume_values or []:
        if not isinstance(value, str) or ":" not in value:
            continue
        host_path = resolve_contract_value(
            value.split(":", 1)[0],
            service_volume=service_volume,
            machine_volume=machine_volume,
            service_name=service_name,
        ).strip()
        if host_path:
            sources.append(host_path)
    return sources


def _validate_file_log_paths(
    *,
    service_name: str,
    target_name: str,
    file_log_paths: list[str],
    host_volume_sources: list[str],
    machine_volume: str,
    service_volume: str,
) -> None:
    if not file_log_paths:
        raise SystemExit(
            f"Observability contract error for {service_name}:{target_name}: "
            "file_logs.enabled=true requires at least one entry in file_logs.paths"
        )

    machine_root = machine_volume.rstrip("/")
    service_root = service_volume.rstrip("/")
    for resolved in file_log_paths:
        if not resolved.startswith("/"):
            raise SystemExit(
                f"Observability contract error for {service_name}:{target_name}: "
                f"path '{resolved}' must be an absolute host path"
            )
        if not (
            resolved == machine_root
            or resolved.startswith(machine_root + "/")
            or resolved == service_root
            or resolved.startswith(service_root + "/")
        ):
            raise SystemExit(
                f"Observability contract error for {service_name}:{target_name}: "
                f"path '{resolved}' is outside allowed machine/service roots"
            )
        if not path_is_covered_by_volume(resolved, host_volume_sources):
            raise SystemExit(
                f"Observability contract error for {service_name}:{target_name}: "
                f"path '{resolved}' is not covered by target volume mounts"
            )


def collect_contract_sources(
    repo_root: Path,
    machine_volume: str,
    environment: str,
    *,
    host_mount_prefix: str = "/host-volume",
) -> list[dict[str, object]]:
    config_path = repo_root / "PlatformOps/config/service_install.yaml"
    with config_path.open() as handle:
        contracts = (yaml.safe_load(handle) or {}).get("services", {}) or {}

    service_volume = machine_volume.rstrip("/")
    host_mount_prefix = str(host_mount_prefix).rstrip("/") or "/host-volume"
    collected: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    default_tail_from_end = env_bool("CPLATFORM_ALLOY_FILE_TAIL_FROM_END", True)

    cplatform_source = {
        "id": "cplatform_logs",
        "glob": f"{host_mount_prefix}/app/logs/*.log*",
        "service_name": "PlatformOps",
        "service_type": "AIOrchestrator",
        "environment": environment,
        "tail_from_end": default_tail_from_end,
    }
    collected.append(cplatform_source)
    seen.add((cplatform_source["glob"], cplatform_source["service_name"], cplatform_source["service_type"]))

    for service_name, service_contract in contracts.items():
        docker_info = (service_contract or {}).get("Docker_Info", {}) or {}
        for target_name, target_contract in docker_info.items():
            observability = (target_contract or {}).get("Observability", {}) or {}
            file_logs = observability.get("file_logs") or {}
            if not file_logs.get("enabled"):
                continue

            labels = dict(file_logs.get("loki_labels") or {})
            resolved_paths = [
                resolve_contract_value(
                    raw_path,
                    service_volume=service_volume,
                    machine_volume=machine_volume,
                    service_name=service_name,
                )
                for raw_path in (file_logs.get("paths") or [])
            ]
            host_volume_sources = resolve_host_volume_sources(
                (target_contract or {}).get("Volumes") or [],
                service_volume=service_volume,
                machine_volume=machine_volume,
                service_name=service_name,
            )
            _validate_file_log_paths(
                service_name=service_name,
                target_name=target_name,
                file_log_paths=resolved_paths,
                host_volume_sources=host_volume_sources,
                machine_volume=machine_volume,
                service_volume=service_volume,
            )

            for resolved in resolved_paths:
                if not resolved.startswith(machine_volume.rstrip("/") + "/") and resolved != machine_volume.rstrip("/"):
                    continue
                relative = resolved[len(machine_volume.rstrip("/")):].lstrip("/")
                host_visible = f"{host_mount_prefix}/{relative}" if relative else host_mount_prefix
                glob_path = f"{host_visible}/*.log*"
                key = (glob_path, labels.get("service_name") or target_name, labels.get("service_type") or target_name)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(
                    {
                        "id": slugify(f"{service_name}_{target_name}_{relative}"),
                        "glob": glob_path,
                        "service_name": labels.get("service_name") or target_name,
                        "service_type": labels.get("service_type") or target_name,
                        "environment": environment,
                        "tail_from_end": default_tail_from_end,
                    }
                )
    return collected


def render_alloy_config(
    *,
    repo_root: Path,
    machine_volume: str,
    node_id: str,
    node_ip: str,
    environment: str,
    host_mount_prefix: str = "/host-volume",
) -> str:
    file_sources = collect_contract_sources(
        repo_root,
        machine_volume,
        environment,
        host_mount_prefix=host_mount_prefix,
    )
    docker_drop_older_than = os.getenv("CPLATFORM_ALLOY_DOCKER_DROP_OLDER_THAN", "24h")
    docker_drop_longer_than = os.getenv("CPLATFORM_ALLOY_DOCKER_DROP_LONGER_THAN", "256KB")

    file_match_blocks = []
    source_blocks = []
    for source in file_sources:
        file_match_blocks.append(
            f'''local.file_match "{source["id"]}" {{
  path_targets = [{{
    __path__     = "{source["glob"]}",
    service_name = "{source["service_name"]}",
    service_type = "{source["service_type"]}",
    environment  = "{source["environment"]}",
    source_type  = "file",
  }}]
}}'''
        )
        source_blocks.append(
            f'''loki.source.file "{source["id"]}" {{
  targets       = local.file_match.{source["id"]}.targets
  forward_to    = [loki.process.file_guard.receiver]
  tail_from_end = {"true" if source["tail_from_end"] else "false"}
}}'''
        )

    return f'''loki.write "default" {{
  endpoint {{
    url = "http://loki:3100/loki/api/v1/push"
  }}
}}

loki.process "docker_enrich" {{
  forward_to = [loki.write.default.receiver]

  stage.drop {{
    older_than          = "{docker_drop_older_than}"
    drop_counter_reason = "bootstrap_too_old"
  }}

  stage.drop {{
    longer_than         = "{docker_drop_longer_than}"
    drop_counter_reason = "bootstrap_too_long"
  }}

  stage.static_labels {{
    values = {{
      environment = "{environment}",
      node_id     = "{node_id}",
      node_ip     = "{node_ip}",
      source_type = "docker_container",
    }}
  }}
}}

loki.process "file_guard" {{
  forward_to = [loki.write.default.receiver]

  stage.drop {{
    longer_than         = "{docker_drop_longer_than}"
    drop_counter_reason = "file_too_long"
  }}
}}

discovery.docker "containers" {{
  host = "unix:///var/run/docker.sock"
}}

discovery.relabel "docker_logs" {{
  targets = discovery.docker.containers.targets

  rule {{
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container_name"
    replacement   = "$1"
  }}

  rule {{
    source_labels = ["__meta_docker_container_id"]
    target_label  = "container_id"
  }}

  rule {{
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "compose_service"
  }}

  rule {{
    replacement  = "{environment}"
    target_label = "environment"
  }}

  rule {{
    replacement  = "{node_id}"
    target_label = "node_id"
  }}

  rule {{
    replacement  = "{node_ip}"
    target_label = "node_ip"
  }}

  rule {{
    replacement  = "docker_container"
    target_label = "source_type"
  }}
}}

{chr(10).join(file_match_blocks)}

{chr(10).join(source_blocks)}

loki.source.docker "containers" {{
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.docker_logs.output
  forward_to = [loki.process.docker_enrich.receiver]
}}
'''


def validate_required_source_paths(repo_root: Path) -> None:
    missing = [str(repo_root / relative_path) for relative_path in REQUIRED_SOURCE_PATHS if not (repo_root / relative_path).exists()]
    if missing:
        raise SystemExit(f"Missing required source paths: {', '.join(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare generated runtime assets for PlatformOps compose bootstrap.")
    parser.add_argument("--output", default="", help="Where to write the generated Alloy config.")
    parser.add_argument("--emit-config", action="store_true", help="Print rendered Alloy config to stdout.")
    parser.add_argument("--repo-root", default="", help="Repo root containing PlatformOps/config/service_install.yaml.")
    parser.add_argument("--machine-volume", default="", help="Host machine volume root override.")
    parser.add_argument("--node-id", default="", help="Node id label override.")
    parser.add_argument("--node-ip", default="", help="Node ip label override.")
    parser.add_argument("--environment", default="", help="Environment label override.")
    parser.add_argument(
        "--host-mount-prefix",
        default="/host-volume",
        help="Container-visible mount prefix where machine volume is mounted.",
    )
    parser.add_argument(
        "--skip-source-path-check",
        action="store_true",
        help="Skip repo sibling source path checks while rendering Alloy config.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    if not args.skip_source_path_check:
        validate_required_source_paths(repo_root)

    machine_volume = (args.machine_volume or os.getenv("CPLATFORM_MACHINE_VOLUME", "/home/ubuntu/Backup_Platform")).rstrip("/")
    node_id = args.node_id or os.getenv("CPLATFORM_PRIMARY_NODE_ID", "NODE1001")
    node_ip = args.node_ip or os.getenv("CPLATFORM_PRIMARY_NODE_IP", detect_host_ip())
    environment = args.environment or os.getenv("CPLATFORM_OBSERVABILITY_ENVIRONMENT", "validation")
    rendered_config = render_alloy_config(
        repo_root=repo_root,
        machine_volume=machine_volume,
        node_id=node_id,
        node_ip=node_ip,
        environment=environment,
        host_mount_prefix=args.host_mount_prefix,
    )

    if args.emit_config:
        print(rendered_config, end="")
        return

    output_path = Path(args.output) if args.output else repo_root / "platform/observability/generated/config.alloy"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_config)
    print(output_path)


if __name__ == "__main__":
    main()
