'''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : serviceInstall.py
* Description       : Functions related to Run and delete Ansible playbook and check system info
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-march-25                  YashKumar                        Created.
* 26-april-25                  Sumit Das                        Updated.
*
*********************************************************************************************************************'''
import os
import base64
from pathlib import Path
import yaml
import subprocess
import json
import re
import platform
import tempfile

from cPlatformIO.src import ServiceConfig, NodeConfig, ClusterConfig
from cPlatformIO.src.serviceEvent import service_event_add_request
from cPlatformIO.models import Service

from cPlatform.AppLogging import app_logger


def _extract_json_payload(process_output):
    patterns = [
        r"'Python script output': '(\{.*\})'",
        r'"Python script output": "(\{.*\})"',
    ]

    json_payload = None
    for pattern in patterns:
        matches = re.findall(pattern, process_output, re.DOTALL)
        if matches:
            json_payload = matches[-1]
            break

    if json_payload is None:
        return None

    json_payload = json_payload.replace("\\'", "'")
    json_payload = json_payload.replace('\\"', '"')

    try:
        return json.loads(json_payload)
    except json.JSONDecodeError:
        app_logger.debug(f"_extract_json_payload, invalid payload={json_payload}")
        return None


def _extract_b64_payload(process_output):
    patterns = [
        r"'payload_b64': '([^']+)'",
        r'"payload_b64": "([^"]+)"',
    ]

    encoded_payload = None
    for pattern in patterns:
        matches = re.findall(pattern, process_output, re.DOTALL)
        if matches:
            encoded_payload = matches[-1]
            break

    if not encoded_payload:
        return None

    try:
        decoded_payload = base64.b64decode(encoded_payload).decode()
        return json.loads(decoded_payload)
    except (ValueError, json.JSONDecodeError) as exc:
        app_logger.debug(f"_extract_b64_payload failed: {exc}")
        return None


def _extract_kv_from_output(process_output, key, default_value=""):
    if not process_output:
        return default_value
    direct_pattern = re.compile(rf"(?m)^{re.escape(key)}=(.+)$")
    quoted_pattern = re.compile(rf"{re.escape(key)}=([^\\n\\r'\" ]+.*?)(?:\\n|\\r|['\"]|$)")

    match = direct_pattern.search(process_output)
    if match:
        return match.group(1).strip()

    match = quoted_pattern.search(process_output)
    if match:
        return match.group(1).strip()

    return default_value

def _resolve_env_file_path(pt_dir, mapped_service_folder):
    candidates = [
        pt_dir / f"Subsytems/{mapped_service_folder}/platform/docker/{mapped_service_folder}/deployment.env",
        pt_dir / f"platform/docker/{mapped_service_folder}/deployment.env",
        pt_dir / f"platform/docker/{str(mapped_service_folder).lower()}/deployment.env",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _read_simple_env_file(path):
    values = {}
    candidate = Path(path)
    if not candidate.exists():
        return values
    with candidate.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_diagnostics_env_candidates(pt_dir):
    explicit = os.getenv("DIAGNOSTICS_ENV_FILE", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend([
        pt_dir / "platform/docker/cPlatform/diagnostics.env",
        pt_dir / "platform/docker/cPlatform/diagnostics.validation.env",
        pt_dir / "platform/docker/cPlatform/diagnostics.env.example",
    ])
    return candidates


def _get_runtime_setting(name, default=""):
    env_value = os.getenv(name, "")
    if env_value not in [None, ""]:
        return env_value

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    for candidate in _resolve_diagnostics_env_candidates(pt_dir):
        values = _read_simple_env_file(candidate)
        if values.get(name):
            return values[name]
    return default


def _slugify_fragment(value):
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()
    return normalized or "source"


def _resolve_contract_value(raw_value, service_volume, machine_volume, service_name):
    value = str(raw_value or "")
    replacements = {
        "{{ service_volume }}": str(service_volume or "/home/ubuntu/Backup_Platform").rstrip("/"),
        "{{ machine_volume }}": str(machine_volume or service_volume or "/home/ubuntu/Backup_Platform").rstrip("/"),
        "{{ service }}": str(service_name or "").strip(),
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    if value.startswith("//"):
        value = "/" + value.lstrip("/")
    return value


def _load_service_install_contracts():
    config_path = Path(__file__).resolve().parent.parents[1] / "config/service_install.yaml"
    with config_path.open() as fh:
        yaml_content = yaml.load(fh, Loader=yaml.FullLoader)
    return (yaml_content or {}).get("services", {})


def _load_glitchtip_runtime_map():
    map_path = Path(__file__).resolve().parent.parent.parent.parent / "platform/observability/glitchtip_runtime_map.yaml"
    if not map_path.exists():
        return {}, {"environment": "validation", "traces_sample_rate": "0.0"}

    with map_path.open() as handle:
        raw_cfg = yaml.load(handle, Loader=yaml.FullLoader) or {}

    services_cfg = raw_cfg.get("services", {}) if isinstance(raw_cfg.get("services", {}), dict) else {}
    defaults_cfg = raw_cfg.get("defaults", {}) if isinstance(raw_cfg.get("defaults", {}), dict) else {}
    return services_cfg, defaults_cfg


def _resolve_glitchtip_runtime_entry(service_type):
    services_cfg, defaults_cfg = _load_glitchtip_runtime_map()
    service_type_raw = str(service_type or "").strip()
    if not service_type_raw:
        return None

    lookup = {str(key).strip().lower(): value for key, value in services_cfg.items()}
    entry = lookup.get(service_type_raw.lower())
    if not isinstance(entry, dict):
        return None

    dsn = str(entry.get("dsn", "")).strip()
    if not dsn:
        return None

    return {
        "dsn": dsn,
        "environment": str(entry.get("environment", "") or defaults_cfg.get("environment", "validation")).strip() or "validation",
        "release": str(entry.get("release", "")).strip(),
        "traces_sample_rate": str(entry.get("traces_sample_rate", "") or defaults_cfg.get("traces_sample_rate", "0.0")).strip() or "0.0",
        "project_slug": str(entry.get("project_slug", "")).strip(),
    }


def _parse_env_bool(value, default=True):
    if value in [None, ""]:
        return default
    normalized = str(value).strip().lower()
    if normalized in ["1", "true", "yes", "on"]:
        return True
    if normalized in ["0", "false", "no", "off"]:
        return False
    return default


def _resolve_service_glitchtip_enabled(ser_ins):
    service_cfg = ser_ins.service_config if isinstance(ser_ins.service_config, dict) else {}
    observability_cfg = service_cfg.get("observability", {}) if isinstance(service_cfg.get("observability", {}), dict) else {}
    runtime_patch_cfg = observability_cfg.get("runtime_patch", {}) if isinstance(observability_cfg.get("runtime_patch", {}), dict) else {}

    for key in ["glitchtip_enabled", "enabled"]:
        if key in runtime_patch_cfg:
            return _parse_env_bool(runtime_patch_cfg.get(key), True)

    if "GLITCHTIP_ENABLED" in service_cfg:
        return _parse_env_bool(service_cfg.get("GLITCHTIP_ENABLED"), True)

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    config_path = Path(__file__).resolve().parent.parents[1] / "config/cPlatform_config.yaml"
    try:
        with config_path.open() as fh:
            platform_cfg = yaml.load(fh, Loader=yaml.FullLoader) or {}
    except Exception:
        platform_cfg = {}

    install_map = platform_cfg.get("SERVICE_INSTALL_MAPPING", {}) if isinstance(platform_cfg.get("SERVICE_INSTALL_MAPPING", {}), dict) else {}
    service_type_cfg = install_map.get(getattr(ser_ins, "service_type", ""), {}) if isinstance(install_map.get(getattr(ser_ins, "service_type", ""), {}), dict) else {}
    version_map = service_type_cfg.get("VERSION", {}) if isinstance(service_type_cfg.get("VERSION", {}), dict) else {}
    mapped_service_folder = version_map.get(getattr(ser_ins, "service_version", ""), getattr(ser_ins, "service_type", ""))

    env_path = _resolve_env_file_path(pt_dir, mapped_service_folder)
    env_values = _read_simple_env_file(env_path)
    return _parse_env_bool(env_values.get("GLITCHTIP_ENABLED"), True)


def _node_observability_root(node_instance):
    return f"{str(node_instance.node_volume or '/home/ubuntu/Backup_Platform').rstrip('/')}/iktara/observability-node"


def _node_alloy_compose_dir(node_instance):
    return f"{_node_observability_root(node_instance)}/alloy"


def _node_machine_volume_root(node_instance):
    return str(node_instance.node_volume or "/home/ubuntu/Backup_Platform").rstrip("/")


def _node_alloy_source_tail_from_end(service_name, target_name):
    normalized_service = str(service_name or "").strip()
    normalized_target = str(target_name or "").strip()
    if normalized_target in ["TrainingServer", "InferenceServer", "ClickHouse"]:
        return False
    if normalized_service in ["TrainingServer", "InferenceServer"] and normalized_target == normalized_service:
        return False
    return True


def _node_alloy_file_sources(node_instance, include_service_instance=None):
    contracts = _load_service_install_contracts()
    services = list(Service.objects.filter(Node=node_instance, deploy_status="DEPLOYED"))
    if include_service_instance and include_service_instance not in services:
        services.append(include_service_instance)

    base_root = _node_machine_volume_root(node_instance)
    seen = set()
    sources = []

    def _append_source(*, source_id, path, service_name, service_type, tail_from_end=True):
        key = (path, service_name, service_type)
        if key in seen:
            return
        seen.add(key)
        sources.append({
            "id": _slugify_fragment(source_id),
            "path": path,
            "service_name": service_name,
            "service_type": service_type,
            "environment": _get_runtime_setting("CPLATFORM_DIAGNOSTICS_ENVIRONMENT", "validation"),
            "node_id": node_instance.node_id,
            "node_ip": node_instance.node_ip,
            "tail_from_end": tail_from_end,
        })

    for service_instance in services:
        service_name = service_instance.service_type
        service_cfg = contracts.get(service_name, {}) or {}
        docker_info = (service_cfg.get("Docker_Info") or {})
        infra_contract = ServiceConfig.service_get_infrastructure_contract(service_name)
        if infra_contract:
            docker_info = {service_name: infra_contract}
        service_volume = (service_instance.service_volume or base_root).rstrip("/")
        if infra_contract and service_volume in ["", "/tmp"]:
            service_volume = base_root
        machine_volume = base_root

        for target_name, target_contract in docker_info.items():
            observability = (target_contract.get("Observability") or target_contract.get("observability") or {})
            file_logs_cfg = (observability.get("file_logs") or {})
            if not file_logs_cfg.get("enabled"):
                continue
            labels = dict(file_logs_cfg.get("loki_labels") or {})
            raw_paths = file_logs_cfg.get("paths") or []
            for raw_path in raw_paths:
                resolved_path = _resolve_contract_value(raw_path, service_volume, machine_volume, service_name)
                if not resolved_path.startswith(base_root + "/") and resolved_path != base_root:
                    continue
                relative_path = resolved_path[len(base_root):].lstrip("/")
                host_visible_path = f"/host-volume/{relative_path}" if relative_path else "/host-volume"
                _append_source(
                    source_id=f"{service_name}_{target_name}_{relative_path}",
                    path=f"{host_visible_path}/*.log*",
                    service_name=labels.get("service_name") or target_name,
                    service_type=labels.get("service_type") or target_name,
                    tail_from_end=_node_alloy_source_tail_from_end(service_name, target_name),
                )

    # Fallback coverage for mixed/manual deployments not fully represented in DB contracts.
    default_sources = [
        ("cplatform_logs", "/host-volume/iktara/cPlatform/logs/*.log*", "cPlatform", "AIOrchestrator", False),
        ("optioncopilot_logs", "/host-volume/iktara/optionCopilot/logs/*.log*", "optionCopilot", "optionCopilot", False),
        ("asr_logs", "/host-volume/iktara/asr/logs/*.log*", "ASR", "ASR", False),
        ("training_logs", "/host-volume/iktara/trainingServer/logs/*.log*", "dTrain", "TrainingServer", False),
        ("inference_logs", "/host-volume/iktara/InferenceServer/logs/*.log*", "dInfer", "InferenceServer", False),
        ("rabbitmq_logs", "/host-volume/iktara/rabbitmqLogs/*.log*", "RabbitMQ", "RabbitMQ", True),
        ("postgres_logs", "/host-volume/iktara/postgresLogs/*.log*", "PostgreSQL", "PostgreSQL", True),
        ("redis_logs", "/host-volume/iktara/redisLogs/*.log*", "redis", "redis", True),
        ("clickhouse_logs", "/host-volume/iktara/clickHouseLogs/*.log*", "ClickHouse", "ClickHouse", True),
    ]
    for source_id, path, service_name, service_type, tail_from_end in default_sources:
        _append_source(
            source_id=source_id,
            path=path,
            service_name=service_name,
            service_type=service_type,
            tail_from_end=tail_from_end,
        )
    return sources


def _node_alloy_config(node_instance, include_service_instance=None):
    sources = _node_alloy_file_sources(node_instance, include_service_instance=include_service_instance)
    central_loki_url = _get_runtime_setting(
        "CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL",
        _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", ""),
    ).strip().rstrip("/")
    docker_drop_older_than = _get_runtime_setting("CPLATFORM_ALLOY_DOCKER_DROP_OLDER_THAN", "24h")
    docker_drop_longer_than = _get_runtime_setting("CPLATFORM_ALLOY_DOCKER_DROP_LONGER_THAN", "256KB")

    file_match_blocks = []
    source_blocks = []
    for source in sources:
        file_match_blocks.append(
            f'''local.file_match "{source["id"]}" {{
  path_targets = [{{
    __path__     = "{source["path"]}",
    service_name = "{source["service_name"]}",
    service_type = "{source["service_type"]}",
    environment  = "{source["environment"]}",
    node_id      = "{source["node_id"]}",
    node_ip      = "{source["node_ip"]}",
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
    url = "{central_loki_url}/loki/api/v1/push"
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
      environment = "{_get_runtime_setting("CPLATFORM_DIAGNOSTICS_ENVIRONMENT", "validation")}",
      node_id     = "{node_instance.node_id}",
      node_ip     = "{node_instance.node_ip}",
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
    replacement  = "{_get_runtime_setting("CPLATFORM_DIAGNOSTICS_ENVIRONMENT", "validation")}"
    target_label = "environment"
  }}

  rule {{
    replacement  = "{node_instance.node_id}"
    target_label = "node_id"
  }}

  rule {{
    replacement  = "{node_instance.node_ip}"
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


def _node_hosts_control_plane(node_instance, include_service_instance=None):
    if include_service_instance and include_service_instance.Node_id == node_instance.node_id:
        if str(include_service_instance.service_type or "").strip() in ["AIOrchestrator", "cPlatform"]:
            return True
    return Service.objects.filter(Node=node_instance, service_type__in=["AIOrchestrator", "cPlatform"]).exists()


def sInstall_deploy_node_observability(node_ins, include_service_instance=None):
    if _node_hosts_control_plane(node_ins, include_service_instance=include_service_instance):
        return True, "Control-plane node uses the central cPlatform observability stack"

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_ins.node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/node_observability_playbook.yaml"
    if not inv_file.exists() or not playbook_path.exists():
        return False, "Node observability playbook prerequisites are missing"

    config_content = _node_alloy_config(node_ins, include_service_instance=include_service_instance)
    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "-e", f"node_id={node_ins.node_id}",
        "-e", f"node_ip={node_ins.node_ip}",
        "-e", f"machine_volume={_node_machine_volume_root(node_ins)}",
        "-e", f"observability_root={_node_observability_root(node_ins)}",
        "-e", f"observability_compose_dir={_node_alloy_compose_dir(node_ins)}",
        "-e", f"alloy_host_port={_get_runtime_setting('CPLATFORM_NODE_ALLOY_PORT', '12345')}",
        "-e", f"alloy_config_b64={base64.b64encode(config_content.encode()).decode()}",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, "Node observability deploy timed out"
    except FileNotFoundError:
        return False, "ansible-playbook is not available in this environment"
    if process.returncode != 0:
        return False, process.stderr.strip() or process.stdout.strip() or "Node observability deploy failed"
    return True, process.stdout.strip() or "Node observability deployed"


def sInstall_get_service_file_logs(ser_ins, node_id, log_paths, tail_lines=250, file_stream="all"):
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/service_file_logs_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_file_logs.py"
    if not inv_file.exists():
        return {"error": "Inventory file not found", "log_lines": [], "log_source": "node_file"}
    if not playbook_path.exists() or not script_path.exists():
        return {"error": "Service file logs helper not found", "log_lines": [], "log_source": "node_file"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"log_paths_b64={base64.b64encode(json.dumps(log_paths).encode()).decode()}",
        "--extra-vars", f"tail_lines={tail_lines}",
        "--extra-vars", f"file_stream={file_stream}",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"error": "Timed out fetching file logs from node", "log_lines": [], "log_source": "node_file"}
    if process.returncode != 0:
        app_logger.error(f"sInstall_get_service_file_logs failed, stderr={process.stderr}")
        return {"error": "Failed to fetch file logs from node", "log_lines": [], "log_source": "node_file"}

    payload = _extract_b64_payload(process.stdout)
    if payload is None:
        return {"error": "No valid JSON found in file log output", "log_lines": [], "log_source": "node_file"}
    payload.setdefault("log_source", "node_file")
    payload.setdefault("log_lines", [])
    payload.setdefault("error", "")
    return payload


def sInstall_list_service_log_files(ser_ins, node_id, log_paths):
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/service_file_archive_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_file_archive.py"
    if not inv_file.exists():
        return {"success": False, "files": [], "error": "Inventory file not found"}
    if not playbook_path.exists() or not script_path.exists():
        return {"success": False, "files": [], "error": "Service file archive helper not found"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", "mode=list",
        "--extra-vars", f"log_paths_b64={base64.b64encode(json.dumps(log_paths).encode()).decode()}",
        "--extra-vars", "limit=300",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"success": False, "files": [], "error": "Timed out listing file archives on node"}
    if process.returncode != 0:
        app_logger.error(f"sInstall_list_service_log_files failed, stderr={process.stderr}")
        return {"success": False, "files": [], "error": "Failed to list file archives on node"}

    payload = _extract_b64_payload(process.stdout)
    if payload is None:
        return {"success": False, "files": [], "error": "No valid JSON found in file archive output"}
    payload.setdefault("success", True)
    payload.setdefault("files", [])
    payload.setdefault("error", "")
    return payload


def sInstall_preview_service_log_file(ser_ins, node_id, remote_file_path, limit=300):
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/service_file_archive_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_file_archive.py"
    if not inv_file.exists():
        return {"success": False, "error": "Inventory file not found"}
    if not playbook_path.exists() or not script_path.exists():
        return {"success": False, "error": "Service file archive helper not found"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", "mode=preview",
        "--extra-vars", "log_paths_b64=W10=",
        "--extra-vars", f"file_path_b64={base64.b64encode(str(remote_file_path).encode()).decode()}",
        "--extra-vars", f"limit={int(limit)}",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out previewing file on node"}
    if process.returncode != 0:
        app_logger.error(f"sInstall_preview_service_log_file failed, stderr={process.stderr}")
        return {"success": False, "error": "Failed to preview file on node"}

    payload = _extract_b64_payload(process.stdout)
    if payload is None:
        return {"success": False, "error": "No valid JSON found in file preview output"}
    payload.setdefault("success", False)
    payload.setdefault("error", "")
    return payload


def sInstall_fetch_service_log_file(ser_ins, node_id, remote_file_path):
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/service_file_archive_fetch_playbook.yml"
    local_fetch_dir = pt_dir / "cPlatform/logs/service_archive_fetches"
    if not inv_file.exists():
        return {"success": False, "error": "Inventory file not found"}
    if not playbook_path.exists():
        return {"success": False, "error": "Service file archive fetch helper not found"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"remote_file_path={str(remote_file_path)}",
        "--extra-vars", f"local_fetch_dir={str(local_fetch_dir)}",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out fetching file from node"}
    if process.returncode != 0:
        app_logger.error(f"sInstall_fetch_service_log_file failed, stderr={process.stderr}")
        return {"success": False, "error": "Failed to fetch file from node"}

    fetched_path = _extract_kv_from_output(process.stdout, "Fetched to", "")
    if not fetched_path:
        match = re.search(r"'Fetched to': '([^']+)'", process.stdout)
        if match:
            fetched_path = match.group(1).strip()
    if not fetched_path:
        return {"success": False, "error": "Fetched file path was not returned"}
    fetched_file = Path(fetched_path)
    if not fetched_file.exists() or not fetched_file.is_file():
        return {"success": False, "error": "Fetched file is not available locally"}
    return {"success": True, "file_path": str(fetched_file), "file_name": Path(remote_file_path).name}


def sInstall_run_service_log_backfill(ser_ins, node_id, log_paths, loki_url, labels, allow_full_file=True):
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    playbook_path = pt_dir / "platform/ansible/playbook/service_log_backfill_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_log_backfill.py"

    if not inv_file.exists():
        return {"success": False, "error": "Inventory file not found", "pushed_entries": 0}
    if not playbook_path.exists() or not script_path.exists():
        return {"success": False, "error": "Service log backfill helper not found", "pushed_entries": 0}
    if not str(loki_url or "").strip():
        return {"success": False, "error": "Loki URL is not configured", "pushed_entries": 0}
    if not isinstance(labels, dict) or not labels:
        return {"success": False, "error": "Backfill labels are missing", "pushed_entries": 0}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"loki_url={str(loki_url).strip()}",
        "--extra-vars", f"log_paths_b64={base64.b64encode(json.dumps(log_paths).encode()).decode()}",
        "--extra-vars", f"labels_b64={base64.b64encode(json.dumps(labels).encode()).decode()}",
        "--extra-vars", f"allow_full_file={'true' if allow_full_file else 'false'}",
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out while running backfill on node", "pushed_entries": 0}

    if process.returncode != 0:
        app_logger.error(f"sInstall_run_service_log_backfill failed, stderr={process.stderr}")
        return {"success": False, "error": "Failed to execute backfill on node", "pushed_entries": 0}

    payload = _extract_b64_payload(process.stdout)
    if payload is None:
        return {"success": False, "error": "No valid JSON found in backfill output", "pushed_entries": 0}

    if "success" not in payload:
        payload["success"] = not bool(payload.get("error"))
    payload.setdefault("pushed_entries", 0)
    payload.setdefault("error", "")
    return payload

def sInstall_add_inv_file(node_id, auth_type, ip_address, username, password=None, key_file_path=None):
    app_logger.debug(f"sInstall_add_inv_file called with: "
                     f"node_id={node_id}, auth_type={auth_type}, ip_address={ip_address}, "
                     f"username={username}, password={repr(password)}, key_file_path={key_file_path}")



    inv_conf, inventory_info = {}, {}

    # Use password only if it's a non-empty, non-whitespace string
    if password and password.strip():
        inv_conf = {
            "hosts": {
                ip_address: {"ansible_user": username,"ansible_ssh_pass": password,"ansible_connection": "ssh",
                    "ansible_ssh_extra_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                    "ansible_become_password": password
                }
            },
            "vars": {}
        }
    elif key_file_path:
        inv_conf = {
            "hosts": {
                ip_address: {"ansible_user": username,"ansible_ssh_private_key_file": key_file_path,
                    "ansible_connection": "ssh", "ansible_ssh_extra_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                    "ansible_become": True
                }
            },
            "vars": {}
        }
    else:
        raise ValueError("Neither a valid password nor a key_file_path was provided.")

    inventory_info["aiworkbench"] = inv_conf

    # Determine path to save the inventory file
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_dir = pt_dir / "platform/ansible/inventory"
    inv_dir.mkdir(parents=True, exist_ok=True)

    inv_file = inv_dir / f"dynamicInventory{node_id}.yaml"
    print(f"[INFO] Inventory file created at: {inv_file}")

    # Write the inventory info to the YAML file
    with open(inv_file, 'w') as file:
        yaml.dump(inventory_info, file, default_flow_style=False)

    app_logger.debug(f"Inventory file successfully created at {inv_file}")
    return

def sInstall_del_inv_file(node_id):
    app_logger.debug(f"sInstall_del_inv_file, node_id = {node_id}")
    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"

    # Define path to deletion playbook
    del_playbook = pt_dir / "platform/ansible/playbook/service_delete_secondary.yaml"

    if not del_playbook.exists():
        app_logger.error(f"Deletion playbook not found: {del_playbook}")
        return False

    if inv_file.exists():

        # --- Run the deletion playbook before deleting the inventory file ---
        command = ["ansible-playbook", "-i", str(inv_file), str(del_playbook)]
        try:
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode != 0:
                app_logger.error(f"Error while deleting node service containers. stderr: {process.stderr}")
        except FileNotFoundError:
            app_logger.warning("ansible-playbook is not available; skipping node service container cleanup")

        app_logger.debug(f"Deleted node services successfully for node_id={node_id}")

        # --- Now delete the inventory file ---
        inv_file.unlink()
        app_logger.debug(f"Deleted inventory file for node_id={node_id}")
    else:
        app_logger.warning(f"Inventory file not found for node_id={node_id}")

    return True


def sInstall_get_node_info(ser_ins, node_id):
    app_logger.debug(f" sInstall_get_node_info,ser_ins, node_id = {ser_ins, node_id}")

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent

    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        log_message = f" Inventory file not found"
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_message)
        return None

    playbook_path = pt_dir / "platform/ansible/playbook/specs_playbook.yml"
    if not playbook_path.exists():
        log_message = f" Playbook not found"
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_message)
        return None

    script_path = pt_dir / "platform/ansible/scripts.py"
    # Run Ansible playbook
    command = ["ansible-playbook","-i", str(inv_file), str(playbook_path),
               "--extra-vars", f"script_src={script_path}"]

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:

        ServiceConfig.service_event_add_request(ser_ins, "ERROR", "System configuration check failed")
        return None

    # Regular expression pattern to extract the JSON output
    pattern = r"'Python script output': '(.*?}})"
    match = re.search(pattern, process.stdout)
    if match:
        extracted_json = match.group(1) # .replace("'", "\"")  Replace single quotes with double quotes
        extracted_json = extracted_json.replace("\\'", "'")
        extracted_json = extracted_json.replace("'", "\"")
        extracted_json = extracted_json.replace('\\"', '"')
        specs_dict = json.loads(extracted_json)

        system_info = {"System Info": specs_dict}         # Store specs_dict inside system_info dictionary
        app_logger.debug(f" sInstall_get_node_info,system_info = {system_info}")
        return system_info

    app_logger.debug(f" sInstall_get_node_info, No valid JSON found in output !")
    return None


def sInstall_get_service_live_status(
    ser_ins,
    node_id,
    main_port,
    dependency_info=None,
    container_name=None,
    dependency_role=None,
    target_port=None,
):
    app_logger.debug(f"sInstall_get_service_live_status, ser_ins={ser_ins}, node_id={node_id}, "
                     f"main_port={main_port}, container_name={container_name}")

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        return {"error": "Inventory file not found"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_status_playbook.yml"
    if not playbook_path.exists():
        return {"error": "Service status playbook not found"}

    script_path = pt_dir / "platform/ansible/service_status.py"
    if not script_path.exists():
        return {"error": "Service status script not found"}

    resolved_container_name = container_name if container_name is not None else ser_ins.service_id
    if str(getattr(ser_ins, "service_type", "") or "").strip() in ["AIOrchestrator", "cPlatform"]:
        resolved_container_name = "iktara_cPlatform"
    normalized_main_port = str(main_port).strip() if str(main_port).strip().isdigit() else ""
    normalized_target_port = str(target_port).strip() if str(target_port).strip().isdigit() else ""

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"container_name={resolved_container_name}",
        "--extra-vars", f"main_port={normalized_main_port}",
        "--extra-vars", f"dependency_role={dependency_role or ''}",
        "--extra-vars", f"target_port={normalized_target_port}",
        "--extra-vars",
        f"dependencies_b64={base64.b64encode(json.dumps(dependency_info or [], separators=(',', ':')).encode()).decode()}",
    ]

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        app_logger.error(f"sInstall_get_service_live_status failed, stderr={process.stderr}")
        return {"error": "Failed to fetch service status from node"}

    status_payload = _extract_json_payload(process.stdout)
    if status_payload is None:
        return {"error": "No valid JSON found in service status output"}
    return status_payload


def sInstall_discover_infrastructure_containers(node_id):
    app_logger.debug(f"sInstall_discover_infrastructure_containers, node_id={node_id}")

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        return {"success": False, "error": "Inventory file not found", "containers": []}

    playbook_path = pt_dir / "platform/ansible/playbook/service_infra_discovery_playbook.yml"
    if not playbook_path.exists():
        return {"success": False, "error": "Infrastructure discovery playbook not found", "containers": []}

    script_path = pt_dir / "platform/ansible/service_infra_discovery.py"
    if not script_path.exists():
        return {"success": False, "error": "Infrastructure discovery script not found", "containers": []}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
    ]

    try:
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            app_logger.error(f"sInstall_discover_infrastructure_containers failed, stderr={process.stderr}")
            return {"success": False, "error": "Failed to discover containers on node", "containers": []}
    except Exception as e:
        app_logger.error(f"sInstall_discover_infrastructure_containers execution failed: {e}")
        return {"success": False, "error": f"Failed to run discovery command: {e}", "containers": []}

    discovery_payload = _extract_b64_payload(process.stdout) or _extract_json_payload(process.stdout)
    if discovery_payload is None:
        return {"success": False, "error": "No valid JSON found in infrastructure discovery output", "containers": []}
    discovery_payload.setdefault("success", True)
    discovery_payload.setdefault("containers", [])
    discovery_payload.setdefault("error", "")
    return discovery_payload


def sInstall_get_service_config_snapshot(
    ser_ins,
    node_id,
    container_name=None,
    service_name=None,
    version=None,
    config_path=None,
    node_volume=None,
):
    app_logger.debug(
        "sInstall_get_service_config_snapshot, ser_ins=%s, node_id=%s, container_name=%s",
        ser_ins,
        node_id,
        container_name,
    )

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_dir = pt_dir / "platform/ansible/inventory"
    inv_file = inv_dir / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        fallback_file = inv_dir / f"dynamicInventoryNODE{node_id}.yaml"
        if fallback_file.exists():
            inv_file = fallback_file
        else:
            return {"success": False, "error": "Inventory file not found"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_config_snapshot_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_config_snapshot.sh"
    if not playbook_path.exists():
        return {"success": False, "error": "Service config snapshot playbook not found"}
    if not script_path.exists():
        return {"success": False, "error": "Service config snapshot script not found"}

    resolved_container_name = container_name if container_name is not None else ser_ins.service_id
    if str(service_name or "").strip() in ["AIOrchestrator", "cPlatform"]:
        resolved_container_name = "iktara_cPlatform"

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"container_name={resolved_container_name}",
        "--extra-vars", f"service_name={service_name or ''}",
        "--extra-vars", f"node_volume={node_volume or ''}",
        "--extra-vars", f"version={version or ''}",
        "--extra-vars", f"config_path={config_path or ''}",
    ]

    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out snapshotting service config"}
    if process.returncode != 0:
        app_logger.error(f"sInstall_get_service_config_snapshot failed, stdout={process.stdout}, stderr={process.stderr}")
        return {"success": False, "error": f"Failed to snapshot service config: {process.stderr}\n{process.stdout}"}

    stdout = process.stdout or ""
    stderr = process.stderr or ""
    if "skipping: no hosts matched" in stdout or "No inventory was parsed" in stderr:
        app_logger.error(
            "sInstall_get_service_config_snapshot inventory invalid, stdout=%s stderr=%s",
            stdout,
            stderr,
        )
        return {"success": False, "error": "Ansible inventory not parsed"}

    output = stdout
    snapshot_path = ""
    for line in output.splitlines():
        if "'Fetched to': '" in line:
            snapshot_path = line.split("'Fetched to': '")[1].split("'")[0]
            break
        if line.startswith("snapshot_path="):
            snapshot_path = line.split("=", 1)[1].strip()
            break

    return {
        "success": True,
        "snapshot_path": snapshot_path,
        "output": output.strip(),
    }


def sInstall_apply_service_config_migration(
    ser_ins,
    node_id,
    merged_config_yaml,
    apply_mode="reload",
    container_name=None,
    service_name=None,
    version=None,
    config_path=None,
    node_volume=None,
    artifact_id=None,
):
    app_logger.debug(
        "sInstall_apply_service_config_migration, ser_ins=%s, node_id=%s, container_name=%s, apply_mode=%s",
        ser_ins,
        node_id,
        container_name,
        apply_mode,
    )

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_dir = pt_dir / "platform/ansible/inventory"
    inv_file = inv_dir / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        fallback_file = inv_dir / f"dynamicInventoryNODE{node_id}.yaml"
        if fallback_file.exists():
            inv_file = fallback_file
        else:
            return {"success": False, "error": "Inventory file not found"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_config_apply_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_config_apply.sh"
    if not playbook_path.exists():
        return {"success": False, "error": "Service config apply playbook not found"}
    if not script_path.exists():
        return {"success": False, "error": "Service config apply script not found"}

    resolved_container_name = container_name if container_name is not None else ser_ins.service_id
    if str(service_name or "").strip() in ["AIOrchestrator", "cPlatform"]:
        resolved_container_name = "iktara_cPlatform"

    apply_mode = str(apply_mode or "reload").strip().lower()
    if apply_mode not in ["reload", "restart"]:
        return {"success": False, "error": f"Invalid apply_mode={apply_mode}"}

    tmp_yaml_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_yaml:
            tmp_yaml.write(merged_config_yaml or "")
            tmp_yaml_path = tmp_yaml.name

        command = [
            "ansible-playbook",
            "-i", str(inv_file),
            str(playbook_path),
            "--extra-vars", f"script_src={script_path}",
            "--extra-vars", f"migrated_config_src={tmp_yaml_path}",
            "--extra-vars", f"container_name={resolved_container_name}",
            "--extra-vars", f"service_name={service_name or ''}",
            "--extra-vars", f"node_volume={node_volume or ''}",
            "--extra-vars", f"version={version or ''}",
            "--extra-vars", f"config_path={config_path or ''}",
            "--extra-vars", f"apply_mode={apply_mode}",
            "--extra-vars", f"artifact_id={artifact_id or ''}",
        ]

        process = subprocess.run(command, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out while applying migrated config"}
    finally:
        if tmp_yaml_path and os.path.exists(tmp_yaml_path):
            try:
                os.remove(tmp_yaml_path)
            except Exception:
                pass

    if process.returncode != 0:
        app_logger.error(
            "sInstall_apply_service_config_migration failed, stdout=%s, stderr=%s",
            process.stdout,
            process.stderr,
        )
        return {
            "success": False,
            "error": f"Failed to apply migrated config: {process.stderr}\n{process.stdout}",
        }

    stdout = process.stdout or ""
    stderr = process.stderr or ""
    if "skipping: no hosts matched" in stdout or "No inventory was parsed" in stderr:
        app_logger.error(
            "sInstall_apply_service_config_migration inventory invalid, stdout=%s stderr=%s",
            stdout,
            stderr,
        )
        return {"success": False, "error": "Ansible inventory not parsed"}

    output = stdout.strip()
    apply_status = _extract_kv_from_output(output, "status", "")
    resolved_config_path = _extract_kv_from_output(output, "resolved_config_path", "")
    backup_path = _extract_kv_from_output(output, "backup_path", "")
    applied_mode = _extract_kv_from_output(output, "apply_mode", apply_mode)
    message = _extract_kv_from_output(output, "message", "")

    if apply_status not in ["applied", "restarted", "reloaded", "success"]:
        if not message:
            message = "Apply script did not report success"
        return {
            "success": False,
            "error": message,
            "output": output,
            "status": apply_status,
        }

    return {
        "success": True,
        "status": apply_status,
        "resolved_config_path": resolved_config_path,
        "backup_path": backup_path,
        "apply_mode": applied_mode,
        "message": message,
        "output": output,
    }


def sInstall_restore_service_config_migration(
    ser_ins,
    node_id,
    backup_path,
    resolved_config_path,
    apply_mode="reload",
    container_name=None,
    service_name=None,
    version=None,
    node_volume=None,
):
    app_logger.debug(
        "sInstall_restore_service_config_migration, ser_ins=%s, node_id=%s, container_name=%s, apply_mode=%s",
        ser_ins,
        node_id,
        container_name,
        apply_mode,
    )

    backup_path = str(backup_path or "").strip()
    resolved_config_path = str(resolved_config_path or "").strip()
    if not backup_path:
        return {"success": False, "error": "backup_path is required"}
    if not resolved_config_path:
        return {"success": False, "error": "resolved_config_path is required"}

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_dir = pt_dir / "platform/ansible/inventory"
    inv_file = inv_dir / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        fallback_file = inv_dir / f"dynamicInventoryNODE{node_id}.yaml"
        if fallback_file.exists():
            inv_file = fallback_file
        else:
            return {"success": False, "error": "Inventory file not found"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_config_restore_playbook.yml"
    script_path = pt_dir / "platform/ansible/service_config_apply.sh"
    if not playbook_path.exists():
        return {"success": False, "error": "Service config restore playbook not found"}
    if not script_path.exists():
        return {"success": False, "error": "Service config apply script not found"}

    resolved_container_name = container_name if container_name is not None else ser_ins.service_id
    if str(service_name or "").strip() in ["AIOrchestrator", "cPlatform"]:
        resolved_container_name = "iktara_cPlatform"

    apply_mode = str(apply_mode or "reload").strip().lower()
    if apply_mode not in ["reload", "restart"]:
        return {"success": False, "error": f"Invalid apply_mode={apply_mode}"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"container_name={resolved_container_name}",
        "--extra-vars", f"service_name={service_name or ''}",
        "--extra-vars", f"version={version or ''}",
        "--extra-vars", f"config_path={resolved_config_path}",
        "--extra-vars", f"apply_mode={apply_mode}",
        "--extra-vars", f"backup_path={backup_path}",
        "--extra-vars", f"node_volume={node_volume or ''}",
    ]

    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out while restoring migrated config"}

    if process.returncode != 0:
        app_logger.error(
            "sInstall_restore_service_config_migration failed, stdout=%s, stderr=%s",
            process.stdout,
            process.stderr,
        )
        return {
            "success": False,
            "error": f"Failed to restore migrated config: {process.stderr}\n{process.stdout}",
        }

    stdout = process.stdout or ""
    stderr = process.stderr or ""
    if "skipping: no hosts matched" in stdout or "No inventory was parsed" in stderr:
        app_logger.error(
            "sInstall_restore_service_config_migration inventory invalid, stdout=%s stderr=%s",
            stdout,
            stderr,
        )
        return {"success": False, "error": "Ansible inventory not parsed"}

    output = stdout.strip()
    restore_status = _extract_kv_from_output(output, "status", "")
    restored_config_path = _extract_kv_from_output(output, "resolved_config_path", resolved_config_path)
    applied_mode = _extract_kv_from_output(output, "apply_mode", apply_mode)
    message = _extract_kv_from_output(output, "message", "")

    if restore_status not in ["applied", "restarted", "reloaded", "success"]:
        if not message:
            message = "Restore script did not report success"
        return {
            "success": False,
            "error": message,
            "output": output,
            "status": restore_status,
        }

    return {
        "success": True,
        "status": restore_status,
        "resolved_config_path": restored_config_path,
        "backup_path": backup_path,
        "apply_mode": applied_mode,
        "message": message,
        "output": output,
    }


def sInstall_get_service_diagnostics(
    ser_ins,
    node_id,
    container_name=None,
    since_hours=None,
    tail_lines=250,
):
    app_logger.debug(
        f"sInstall_get_service_diagnostics, ser_ins={ser_ins}, node_id={node_id}, "
        f"container_name={container_name}, since_hours={since_hours}, tail_lines={tail_lines}"
    )

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        return {"error": "Inventory file not found", "log_lines": [], "log_source": "node_docker"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_diagnostics_playbook.yml"
    if not playbook_path.exists():
        return {"error": "Service diagnostics playbook not found", "log_lines": [], "log_source": "node_docker"}

    script_path = pt_dir / "platform/ansible/service_diagnostics.py"
    if not script_path.exists():
        return {"error": "Service diagnostics script not found", "log_lines": [], "log_source": "node_docker"}

    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"container_name={container_name if container_name is not None else ser_ins.service_id}",
        "--extra-vars", f"since_hours={since_hours or ''}",
        "--extra-vars", f"tail_lines={tail_lines}",
    ]

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        app_logger.error(f"sInstall_get_service_diagnostics failed, stderr={process.stderr}")
        return {"error": "Failed to fetch service diagnostics from node", "log_lines": [], "log_source": "node_docker"}

    diagnostics_payload = _extract_b64_payload(process.stdout)
    if diagnostics_payload is None:
        return {"error": "No valid JSON found in service diagnostics output", "log_lines": [], "log_source": "node_docker"}

    diagnostics_payload.setdefault("log_source", "node_docker")
    diagnostics_payload.setdefault("log_lines", [])
    diagnostics_payload.setdefault("error", "")
    return diagnostics_payload


def sInstall_run_service_runtime_patch(
    ser_ins,
    node_id,
    container_name=None,
    restart_service=True,
):
    app_logger.debug(
        "sInstall_run_service_runtime_patch, service_id=%s node_id=%s container_name=%s",
        getattr(ser_ins, "service_id", ""),
        node_id,
        container_name,
    )

    runtime_entry = _resolve_glitchtip_runtime_entry(getattr(ser_ins, "service_type", ""))
    if not runtime_entry:
        return {
            "success": False,
            "error": f"Missing GlitchTip DSN mapping for service type '{getattr(ser_ins, 'service_type', '')}'",
        }
    node_instance = getattr(ser_ins, "Node", None)
    node_ip = ServiceConfig._normalize_node_ip(getattr(node_instance, "node_ip", getattr(node_instance, "ip_address", "")))
    mapped_environment = str(runtime_entry.get("environment", "")).strip() or "validation"
    runtime_environment = str(node_ip).strip() or mapped_environment or "validation"
    glitchtip_enabled = _resolve_service_glitchtip_enabled(ser_ins)

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        return {"success": False, "error": "Inventory file not found"}

    playbook_path = pt_dir / "platform/ansible/playbook/service_runtime_patch_playbook.yml"
    if not playbook_path.exists():
        return {"success": False, "error": "Service runtime patch playbook not found"}

    script_path = pt_dir / "platform/ansible/service_runtime_patch.py"
    if not script_path.exists():
        return {"success": False, "error": "Service runtime patch script not found"}

    resolved_container_name = container_name if container_name is not None else ser_ins.service_id
    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(playbook_path),
        "--extra-vars", f"script_src={script_path}",
        "--extra-vars", f"container_name={resolved_container_name}",
        "--extra-vars", f"service_type={ser_ins.service_type}",
        "--extra-vars", f"service_name={ser_ins.service_name}",
        "--extra-vars", f"service_id={ser_ins.service_id}",
        "--extra-vars", f"sentry_dsn={runtime_entry.get('dsn')}",
        "--extra-vars", f"glitchtip_enabled={'true' if glitchtip_enabled else 'false'}",
        "--extra-vars", f"node_id={node_id}",
        "--extra-vars", f"node_ip={node_ip}",
        "--extra-vars", f"glitchtip_environment={runtime_environment}",
        "--extra-vars", f"glitchtip_release={runtime_entry.get('release') or ser_ins.service_name}",
        "--extra-vars", f"traces_sample_rate={runtime_entry.get('traces_sample_rate')}",
        "--extra-vars", f"restart_service={'true' if restart_service else 'false'}",
    ]

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        app_logger.error(
            "sInstall_run_service_runtime_patch failed, stdout=%s stderr=%s",
            process.stdout,
            process.stderr,
        )
        return {"success": False, "error": "Failed to execute runtime patch playbook"}

    payload = _extract_b64_payload(process.stdout)
    if payload is None:
        return {"success": False, "error": "No valid payload found in runtime patch output"}

    payload.setdefault("success", False)
    payload.setdefault("error", "")
    payload.setdefault("project_slug", runtime_entry.get("project_slug", ""))
    payload.setdefault("dsn", runtime_entry.get("dsn", ""))
    payload.setdefault("environment", runtime_environment)
    if not str(payload.get("environment", "")).strip():
        payload["environment"] = runtime_environment
    payload.setdefault("release", runtime_entry.get("release", "") or ser_ins.service_name)
    payload.setdefault("node_ip", node_ip)
    payload.setdefault("node_id", node_id)
    payload.setdefault("glitchtip_enabled", glitchtip_enabled)
    return payload


def sInstall_deploy_service(ser_ins, node_id, username, service_version):
    app_logger.debug(f" sInstall_deploy_service ser_ins, node_id, username= {ser_ins, node_id, username}")

    config_path = Path(__file__).resolve().parent.parents[1] / 'config/service_install.yaml'
    with open(config_path, 'r') as fh:
        service_config_dict = yaml.load(fh, Loader=yaml.FullLoader)

    config_path = Path(__file__).resolve().parent.parents[1] / 'config/cPlatform_config.yaml'
    with open(config_path, 'r') as fh:
        platform_config_dict = yaml.load(fh, Loader=yaml.FullLoader)

    service_config = service_config_dict["services"].get(ser_ins.service_type, {})
    docker_info = service_config.get("Docker_Info", {}).get(ser_ins.service_type, {})
    available_versions = docker_info.get("Image_Ver_List", [])
    node_ins=NodeConfig.node_get_instance(node_id)
    cluster_instance = ClusterConfig.cluster_get_instance(node_ins.Cluster.cluster_id)
    image_store_path = cluster_instance.image_store_path if cluster_instance.image_store_type == "Local" else ""

    infra_contract = ServiceConfig.service_get_infrastructure_contract(ser_ins.service_type)
    print(f"infra_contract=={infra_contract}")
    if infra_contract:
        service_version = infra_contract.get("Image_Ver", service_version or "1.0.0")
        available_versions = [service_version]
        docker_info = infra_contract

    if service_version not in available_versions:
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", "The Selected Version does not Exists !")
        return False

    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", "Ansible Inventory file not found !")
        return False

    ser_file = pt_dir / "platform/ansible/playbook/service_install_playbook.yaml"
    if infra_contract:
        ser_file = pt_dir / "platform/ansible/playbook/infrastructure_service_install_playbook.yaml"
    if not ser_file.exists():
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", 'Ansible Service Deploy Playbook not found !')
        return False

    # -------------------- ADDED: Priority → CPU shares mapping --------------------
    priority_map = {
        "Low": 512,
        "Medium": 1024,
        "High": 2048,
        "Veryhigh": 4096
    }
    priority = ser_ins.service_config.get("priority", "Medium")
    cpu_shares = priority_map.get(priority, 1024)



    # Ansible command to run playbook
    runtime_cfg = ser_ins.service_config if isinstance(ser_ins.service_config, dict) else {}
    service_port = runtime_cfg.get('service_port', ser_ins.service_port)
    memory = runtime_cfg.get('max_memory') or runtime_cfg.get('memory') or 4
    cpus = runtime_cfg.get('v_cpu') or runtime_cfg.get('no_of_cores') or 1
    ollama_models = f"{[runtime_cfg.get('llm_model'), runtime_cfg.get('embed_model')]}"

    if infra_contract:
        container_name = ServiceConfig.service_get_infrastructure_container_name(ser_ins.service_type, node_id)
        infra_service_volume = ser_ins.service_volume
        if str(infra_service_volume or "").rstrip("/") in ["", "/tmp"]:
            infra_service_volume = node_ins.node_volume
        replacement_map = {
            "{{ service_volume }}": str(infra_service_volume or "").rstrip("/"),
            "{{ machine_volume }}": str(node_ins.node_volume or "").rstrip("/"),
            "{{ service }}": str(ser_ins.service_type or ""),
        }

        def _resolve_infra_tokens(value):
            if isinstance(value, str):
                resolved = value
                for token, replacement in replacement_map.items():
                    resolved = resolved.replace(token, replacement)
                return resolved
            if isinstance(value, list):
                return [_resolve_infra_tokens(item) for item in value]
            if isinstance(value, dict):
                return {key: _resolve_infra_tokens(item) for key, item in value.items()}
            return value

        resolved_infra_contract = _resolve_infra_tokens(
            json.loads(json.dumps(infra_contract))
        )
        service_config = ser_ins.service_config or {}

        # Keep infrastructure cards bound to the existing cPlatform Docker
        # network by default, but allow a service edit/API request to choose a
        # different existing network or to leave the container IP empty for
        # Docker IPAM allocation.  The playbook receives the complete contract
        # via base64 so values containing punctuation cannot be split by the
        # Ansible command line.
        if "network_name" in service_config:
            resolved_infra_contract["Network_Name"] = str(
                service_config.get("network_name") or ""
            ).strip()
        if "network_subnet" in service_config:
            resolved_infra_contract["Network_Subnet"] = str(
                service_config.get("network_subnet") or ""
            ).strip()
        if "container_ip" in service_config:
            resolved_infra_contract["Int_IP_Addr"] = str(
                service_config.get("container_ip") or ""
            ).strip()

        env_vars = {
            k: str(v)
            for k, v in service_config.items()
            if k.isupper()
        }
        resolved_infra_contract["Environment"] = {
            **resolved_infra_contract.get("Environment", {}),
            **env_vars,
        }

        # Deployment logs are retained by cPlatform, so never print database
        # URLs, passwords, tokens, or other secret-bearing environment values.
        def _redact_runtime_value(key, value):
            return value

        safe_service_config = {
            key: _redact_runtime_value(key, value)
            for key, value in (ser_ins.service_config or {}).items()
        }
        safe_environment = {
            key: _redact_runtime_value(key, value)
            for key, value in (resolved_infra_contract.get("Environment") or {}).items()
        }
        print("SERVICE CONFIG =", safe_service_config)
        print("ENV =", safe_environment)
        command = [
            "ansible-playbook",
            "-i", str(inv_file),
            str(ser_file),
            "-e", f"infra_service_type={ser_ins.service_type}",
            "-e", f"infra_role={resolved_infra_contract.get('Role', ser_ins.service_type)}",
            "-e", f"infra_container_name={container_name}",
            "-e", f"infra_contract_b64={base64.b64encode(json.dumps(resolved_infra_contract).encode()).decode()}",
            "-e", f"service_volume={infra_service_volume}",
            "-e", f"machine_volume={node_ins.node_volume}",
            "-e", f"image_store_path={image_store_path}",
            "-e", f"expose_service={str(service_config.get('expose_service', False)).lower()}",
            "-e", f"host_port={service_config.get('host_port', '')}",
            "-e", f"nifi_bootstrap_enabled={str(service_config.get('nifi_bootstrap_enabled', resolved_infra_contract.get('Bootstrap_Enabled_By_Default', False))).lower()}",
        ]

        process = subprocess.run(command, capture_output=True, text=True)
        # ``command`` contains a base64-encoded infrastructure contract.  It
        # may include database URLs or other secrets, so never stringify the
        # CompletedProcess/argv into cPlatform logs.
        print(f"ansible infrastructure deployment returncode={process.returncode}")
        if process.returncode != 0:
            log_msg = f"Infrastructure container deploy failed Node: ({ser_ins.Node.node_ip}, Error= {process.stderr} !!"
            ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_msg)
            return False

        log_msg = f"Infrastructure container deployed successfully on Node: ({ser_ins.Node.node_ip}"
        ServiceConfig.service_event_add_request(ser_ins, "Install Service", log_msg)
        return True

    service_type_env = platform_config_dict["SERVICE_INSTALL_MAPPING"][ser_ins.service_type]["VERSION"][service_version]
    new_val = _resolve_env_file_path(pt_dir, service_type_env)

    # command = ["ansible-playbook", "-i", str(inv_file), str(ser_file), f"-e service_port={service_port}",
    # f"-e service_id={ser_ins.service_id}", f"-e username={username}", f"-e service={ser_ins.service_type}",
    # f"-e service_volume={ser_ins.service_volume}", f"-e machine_volume={node_ins.node_volume}",
    # f"-e version={service_version}", f"-e 'Ollama_Models={ollama_models}'", f"-e image_store_path={image_store_path}",
    # f"-e DJANGO_ENV_FILE={new_val}", f"-e memory={memory}", f"-e memory_swap={memory}", f"-e cpus={cpus}",
    # f"-e cpu_shares={cpu_shares}"]
    command = [
        "ansible-playbook",
        "-i", str(inv_file),
        str(ser_file),
        "-e", f"service_port={service_port}",
        "-e", f"node_id={node_id}",
        "-e", f"service_id={ser_ins.service_id}",
        "-e", f"username={username}",
        "-e", f"service={ser_ins.service_type}",
        "-e", f"service_volume={ser_ins.service_volume}",
        "-e", f"machine_volume={node_ins.node_volume}",
        "-e", f"version={service_version}",
        "-e", f"Ollama_Models={json.dumps(ollama_models)}",
        "-e", f"image_store_path={image_store_path}",
        "-e", f"DJANGO_ENV_FILE={new_val}",
        "-e", f"memory={memory}",
        "-e", f"memory_swap={memory}",
        "-e", f"cpus={cpus}",
        "-e", f"cpu_shares={cpu_shares}", ]

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        log_msg = f"Docker images Installation Failed Node: ({ser_ins.Node.node_ip}, Error= {process.stderr} !!"
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_msg)
        return False

    log_msg = f"Docker images installed and Run Successfully on Node: ({ser_ins.Node.node_ip}"
    ServiceConfig.service_event_add_request(ser_ins, "Install Service", log_msg)
    return True


def sInstall_remove_service(ser_ins, node_id,username):
    app_logger.debug(f" sInstall_remove_service, ser_ins, ip_address= {ser_ins, node_id}")


    pt_dir = Path(__file__).resolve().parent.parent.parent.parent
    inv_file = pt_dir / "platform/ansible/inventory" / f"dynamicInventory{node_id}.yaml"
    if not inv_file.exists():
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", "Ansible Inventory file not found !")
        return

    ser_file = pt_dir / "platform/ansible/playbook/service_delete_primary.yaml"
    if not ser_file.exists():
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", 'Ansible Service Remove Playbook not found !')
        return

    node_ins = NodeConfig.node_get_instance(node_id)
    container_name = ser_ins.service_id
    infra_contract = ServiceConfig.service_get_infrastructure_contract(ser_ins.service_type)
    if infra_contract:
        container_name = ServiceConfig.service_get_infrastructure_container_name(ser_ins.service_type, node_id)
    # Ansible command to run playbook
    command = ["ansible-playbook","-i", str(inv_file), str(ser_file), f"-e service={ser_ins.service_type}",
               f"-e service_volume={ser_ins.service_volume}", f"-e machine_volume={node_ins.node_volume}",
               f"-e node_id={node_id}", f"-e service_id={ser_ins.service_id}", f"-e container_name={container_name}", f"-e username={username}"]

    # Run the playbook
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        log_msg = f"Docker images Removal Failed Node: ({ser_ins.Node.node_ip}, Error= {process.stderr} !!"
        ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_msg)
        return

    log_msg = f"Docker images Removal Successfully on Node: ({ser_ins.Node.node_ip}"
    ServiceConfig.service_event_add_request(ser_ins, "ERROR", log_msg)
    return
