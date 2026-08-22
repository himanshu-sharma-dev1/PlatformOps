import json
import subprocess


def _run(command):
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        return ""
    return process.stdout.strip()


def _split_csv(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _container_names():
    output = _run(["docker", "ps", "-a", "--format", "{{.Names}}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def _inspect_container(name):
    output = _run(["docker", "inspect", name])
    if not output:
        return None
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not payload:
        return None

    info = payload[0]
    config = info.get("Config", {}) or {}
    state = info.get("State", {}) or {}
    network_settings = info.get("NetworkSettings", {}) or {}
    networks = network_settings.get("Networks", {}) or {}
    first_network = next(iter(networks.values()), {}) if networks else {}
    ports = network_settings.get("Ports", {}) or {}
    host_ports = []
    for mappings in ports.values():
        for mapping in mappings or []:
            host_port = mapping.get("HostPort")
            if host_port:
                host_ports.append(host_port)

    exposed_ports = []
    for port_spec in (config.get("ExposedPorts") or {}).keys():
        exposed_ports.append(str(port_spec).split("/", 1)[0])

    return {
        "name": name,
        "image": config.get("Image", ""),
        "state": state.get("Status", ""),
        "running": bool(state.get("Running", False)),
        "container_ip": first_network.get("IPAddress", ""),
        "network_names": list(networks.keys()),
        "exposed_ports": sorted(set(exposed_ports)),
        "host_ports": sorted(set(host_ports)),
        "labels": config.get("Labels", {}) or {},
        "created_at": info.get("Created", ""),
        "running_since": state.get("StartedAt", ""),
        "restart_count": info.get("RestartCount", 0),
        "exit_code": state.get("ExitCode"),
        "oom_killed": bool(state.get("OOMKilled", False)),
        "command": " ".join(_split_csv(config.get("Cmd", ""))),
    }


def main():
    containers = []
    for name in _container_names():
        container = _inspect_container(name)
        if container:
            containers.append(container)
    print(json.dumps({"success": True, "error": "", "containers": containers}))


if __name__ == "__main__":
    main()
