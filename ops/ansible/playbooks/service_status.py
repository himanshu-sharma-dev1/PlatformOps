import argparse
import base64
import json
import re
import shlex
import subprocess
from urllib.parse import urlparse


def _run_command(command):
    return subprocess.run(command, capture_output=True, text=True)


ROLE_HINTS = {
    "Airflow-Scheduler": ["airflow-scheduler"],
    "Airflow-Worker": ["airflow-worker"],
    "Airflow-DagProcessor": ["airflow-dagprocessor"],
    "Airflow-Triggerer": ["airflow-triggerer"],
    "AirflowInit": ["airflow-init", "airflowinit"],
    "ClickHouse": ["clickhouse"],
    "RabbitMQ": ["rabbitmq"],
    "PostgreSQL": ["postgres", "postgresql"],
    "Redis": ["redis"],
    "redis": ["redis"],
}


def _get_container_ip(networks, network_name):
    if network_name in networks:
        return networks.get(network_name, {}).get("IPAddress", "") or ""

    for details in networks.values():
        ip_addr = details.get("IPAddress", "") or ""
        if ip_addr:
            return ip_addr
    return ""


def _is_port_listening(container_name, port):
    if not port:
        return True
    try:
        port_num = int(str(port).strip())
    except (TypeError, ValueError):
        return False

    check_cmd = (
        "ss -ltn 2>/dev/null || "
        "netstat -ltn 2>/dev/null || "
        "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null || true"
    )
    process = _run_command(["docker", "exec", container_name, "sh", "-lc", check_cmd])
    if process.returncode != 0:
        return False

    output = process.stdout or ""
    patterns = [
        rf":{port_num}\b",
        rf"\b{port_num:04X}\b",
    ]
    return any(re.search(pattern, output, re.IGNORECASE) for pattern in patterns)


def _build_container_status(container_name, inspect_data, network_name):
    state_info = inspect_data.get("State", {}) or {}
    network_info = inspect_data.get("NetworkSettings", {}).get("Networks", {}) or {}

    return {
        "name": container_name,
        "state": state_info.get("Status", "unknown"),
        "image": inspect_data.get("Config", {}).get("Image", "") or "",
        "container_ip": _get_container_ip(network_info, network_name),
        "created_at": inspect_data.get("Created", "") or "",
        "running_since": state_info.get("StartedAt", "") or "",
        "restart_count": inspect_data.get("RestartCount", 0) or 0,
        "exit_code": state_info.get("ExitCode"),
        "oom_killed": bool(state_info.get("OOMKilled", False)),
    }


def _get_host_ports(inspect_data):
    ports = inspect_data.get("NetworkSettings", {}).get("Ports", {}) or {}
    host_ports = set()

    for port_bindings in ports.values():
        if not port_bindings:
            continue
        for binding in port_bindings:
            host_port = (binding or {}).get("HostPort")
            if host_port:
                host_ports.add(str(host_port))
    return host_ports


def _get_network_containers(network_name):
    inspect_process = _run_command(["docker", "network", "inspect", network_name])
    if inspect_process.returncode != 0:
        return {}

    try:
        data = json.loads(inspect_process.stdout)[0]
    except (json.JSONDecodeError, IndexError, KeyError):
        return {}

    containers = data.get("Containers", {}) or {}
    ip_map = {}
    for details in containers.values():
        container_name = details.get("Name", "") or ""
        ipv4 = details.get("IPv4Address", "") or ""
        ip_addr = ipv4.split("/")[0] if ipv4 else ""
        if container_name and ip_addr:
            ip_map[ip_addr] = container_name
    return ip_map


def _is_local_network_target(target_host):
    return isinstance(target_host, str) and target_host.startswith("180.75.0.")


def _inspect_container(container_name):
    inspect_process = _run_command(["docker", "inspect", container_name])
    if inspect_process.returncode != 0:
        return None
    try:
        return json.loads(inspect_process.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        return None


def _list_container_names():
    process = _run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    if process.returncode != 0:
        return []
    return [line.strip() for line in (process.stdout or "").splitlines() if line.strip()]


def _inspect_env_map(inspect_data):
    env_map = {}
    for item in inspect_data.get("Config", {}).get("Env", []) or []:
        if "=" in item:
            key, value = item.split("=", 1)
            env_map[key] = value
    return env_map


def _read_container_env_file(container_name, env_path):
    if not env_path:
        return {}

    process = _run_command([
        "docker", "exec", container_name, "sh", "-lc",
        f"cat {shlex.quote(env_path)} 2>/dev/null || true",
    ])
    env_map = {}
    for line in (process.stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key.strip()] = value.strip()
    return env_map


def _resolve_container(container_name, dependency_role=None, target_port=None):
    if container_name:
        inspect_data = _inspect_container(container_name)
        if inspect_data is not None:
            return container_name, inspect_data

    role_hints = ROLE_HINTS.get(dependency_role or "", [])
    candidates = []
    for candidate_name in _list_container_names():
        inspect_data = _inspect_container(candidate_name)
        if inspect_data is None:
            continue

        image_name = str(inspect_data.get("Config", {}).get("Image", "") or "").lower()
        container_name_l = candidate_name.lower()
        host_ports = _get_host_ports(inspect_data)

        score = 0
        hint_match = False
        if target_port and str(target_port) in host_ports:
            score += 10
        for hint in role_hints:
            if hint in container_name_l:
                score += 4
                hint_match = True
            if hint in image_name:
                score += 4
                hint_match = True

        if dependency_role and not hint_match:
            continue

        if score > 0:
            candidates.append((score, candidate_name, inspect_data))

    if not candidates:
        return "", None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    _, resolved_name, resolved_inspect = candidates[0]
    return resolved_name, resolved_inspect


def _parse_broker_dependency(broker_url):
    if not broker_url:
        return None

    parsed = urlparse(broker_url)
    if not parsed.hostname:
        return None

    return {
        "name": "RabbitMQ",
        "target_host": parsed.hostname,
        "target_port": parsed.port or 5672,
    }


def _append_dependency(dependencies, name, target_host, target_port):
    if not target_host:
        return

    dependency = {
        "name": name,
        "target_host": str(target_host),
        "target_port": int(target_port) if str(target_port).isdigit() else target_port,
    }
    key = (dependency["name"], dependency["target_host"], str(dependency["target_port"]))
    if key not in dependencies["_keys"]:
        dependencies["_keys"].add(key)
        dependencies["items"].append(dependency)


def _decode_declared_dependencies(dependencies_b64):
    if not dependencies_b64:
        return []

    try:
        decoded = base64.b64decode(dependencies_b64).decode()
        payload = json.loads(decoded)
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    normalized = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip()
        if not role:
            continue
        normalized.append(
            {
                "name": role,
                "declared_role": role,
                "declared_ip": str(item.get("ip", "") or "").strip(),
                "declared_port": item.get("port"),
            }
        )
    return normalized


def _get_runtime_dependencies(container_name, inspect_data):
    inspect_env = _inspect_env_map(inspect_data)
    env_file_map = _read_container_env_file(container_name, inspect_env.get("DJANGO_ENV_FILE", ""))

    dependency_data = {"items": [], "_keys": set()}
    broker_dependency = _parse_broker_dependency(env_file_map.get("celery_broker"))
    if broker_dependency:
        _append_dependency(
            dependency_data,
            broker_dependency["name"],
            broker_dependency["target_host"],
            broker_dependency["target_port"],
        )

    _append_dependency(
        dependency_data,
        "PostgreSQL",
        env_file_map.get("postgres_server_ip"),
        env_file_map.get("postgres_server_port"),
    )
    _append_dependency(
        dependency_data,
        "Redis",
        env_file_map.get("redis_server_ip"),
        env_file_map.get("redis_server_port"),
    )
    _append_dependency(
        dependency_data,
        "ClickHouse",
        env_file_map.get("clickhouse_host"),
        env_file_map.get("clickhouse_port"),
    )

    return dependency_data["items"]


def _dependency_key(name):
    return str(name or "").strip().lower()


def _build_dependency_row(name, target_host="", target_port=None, source_type="Declared Contract"):
    is_local_target = _is_local_network_target(target_host)
    normalized_port = int(target_port) if str(target_port).isdigit() else target_port
    return {
        "name": name,
        "target_host": target_host,
        "target_port": normalized_port,
        "declared_role": name,
        "declared_ip": target_host,
        "declared_port": normalized_port,
        "source_type": source_type,
        "container_name": "",
        "state": "missing" if is_local_target else ("External" if target_host else "missing"),
        "image": "",
        "container_ip": "",
        "created_at": "",
        "running_since": "",
        "restart_count": 0,
        "exit_code": None,
        "oom_killed": False,
    }


def _overlay_container_status(dep_info, dep_container_name, dep_inspect, network_name):
    dep_info.update(_build_container_status(dep_container_name, dep_inspect, network_name))
    dep_info["source_type"] = "Local Container"
    dep_info["container_name"] = dep_container_name
    if dep_info.get("name") == "AirflowInit" and dep_info.get("state") == "exited" and str(dep_info.get("exit_code")) == "0":
        dep_info["satisfied"] = True
        dep_info["satisfied_reason"] = "Airflow init completed successfully"
    return dep_info


def _merge_dependencies(declared_dependencies, runtime_dependencies, network_containers, network_name):
    merged = []
    merged_map = {}

    for dependency in declared_dependencies:
        dep_info = _build_dependency_row(
            dependency["name"],
            dependency.get("declared_ip", ""),
            dependency.get("declared_port"),
            source_type="Declared Contract",
        )
        dep_info["declared_role"] = dependency.get("declared_role", dependency["name"])
        dep_info["declared_ip"] = dependency.get("declared_ip", "")
        dep_info["declared_port"] = dependency.get("declared_port")
        merged.append(dep_info)
        merged_map[_dependency_key(dep_info["name"])] = dep_info

    for dependency in runtime_dependencies:
        dep_key = _dependency_key(dependency.get("name"))
        dep_info = merged_map.get(dep_key)
        if dep_info is None:
            dep_info = _build_dependency_row(
                dependency.get("name", ""),
                dependency.get("target_host", ""),
                dependency.get("target_port"),
                source_type="Discovered Runtime",
            )
            merged.append(dep_info)
            merged_map[dep_key] = dep_info

        runtime_host = dependency.get("target_host", "")
        runtime_port = dependency.get("target_port")
        if runtime_host:
            dep_info["target_host"] = runtime_host
        if runtime_port not in [None, ""]:
            dep_info["target_port"] = int(runtime_port) if str(runtime_port).isdigit() else runtime_port

    for dep_info in merged:
        current_target = dep_info.get("target_host", "")
        declared_ip = dep_info.get("declared_ip", "")
        dep_container_name = network_containers.get(current_target, "") or network_containers.get(declared_ip, "")
        if dep_container_name:
            dep_inspect = _inspect_container(dep_container_name)
            if dep_inspect is not None:
                _overlay_container_status(dep_info, dep_container_name, dep_inspect, network_name)
                continue

        if current_target and not _is_local_network_target(current_target):
            if dep_info["source_type"] == "Declared Contract":
                dep_info["source_type"] = "External"
            dep_info["state"] = "External"

    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container-name", default="")
    parser.add_argument("--main-port", default="")
    parser.add_argument("--network-name", default="cplatform_iktara_cPlatform")
    parser.add_argument("--dependencies-b64", default="")
    parser.add_argument("--dependency-role", default="")
    parser.add_argument("--target-port", default="")
    args = parser.parse_args()

    status = {
        "main_container": {
            "name": args.container_name,
            "state": "missing",
            "image": "",
            "container_ip": "",
            "created_at": "",
            "running_since": "",
            "restart_count": 0,
            "exit_code": None,
            "oom_killed": False,
            "expected_port_listening": False,
        },
        "dependencies": [],
    }

    resolved_container_name, inspect_data = _resolve_container(
        args.container_name,
        args.dependency_role,
        args.target_port,
    )
    if inspect_data is None:
        if args.dependency_role:
            status["error"] = f"Unable to resolve container for role {args.dependency_role}"
        print(json.dumps(status))
        return

    status["main_container"] = _build_container_status(resolved_container_name, inspect_data, args.network_name)
    status["main_container"]["expected_port_listening"] = _is_port_listening(resolved_container_name, args.main_port)

    network_containers = _get_network_containers(args.network_name)
    declared_dependencies = _decode_declared_dependencies(args.dependencies_b64)
    runtime_dependencies = _get_runtime_dependencies(resolved_container_name, inspect_data)
    status["dependencies"] = _merge_dependencies(
        declared_dependencies,
        runtime_dependencies,
        network_containers,
        args.network_name,
    )

    print(json.dumps(status))


if __name__ == "__main__":
    main()
