#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.observability_utils import ObservabilityError, derive_diagnostics_env_path, load_env_file

DEFAULT_PORTS = {
    "cplatform_http": 80,
    "cplatform_https": 443,
    "loki": 9011,
    "glitchtip": 8001,
    "alloy": 12345,
    "rabbitmq_ui": 15674,
    "rabbitmq_mqtt": 8885,
}
DEFAULT_NETWORK_NAME = "cplatform_iktara_cPlatform"
DEFAULT_NETWORK_SUBNET = "180.75.0.0/24"
DEFAULT_NETWORK_GATEWAY = "180.75.0.1"
STATIC_IPS = [
    "180.75.0.5",
    "180.75.0.2",
    "180.75.0.4",
    "180.75.0.43",
    "180.75.0.44",
    "180.75.0.45",
    "180.75.0.46",
    "180.75.0.47",
    "180.75.0.48",
    "180.75.0.49",
    "180.75.0.50",
]
REQUIRED_SOURCE_PATHS = [
    "MCPClient",
    "CutilJS",
    "ModelStore",
    "CommonUtils",
]
LONG_RUNNING_SERVICES = [
    "cplatform_db",
    "rabbitmq",
    "cplatform",
    "loki",
    "alloy",
    "glitchtip-postgres",
    "glitchtip-valkey",
    "glitchtip-web",
    "glitchtip-worker",
]
ONE_SHOT_SERVICES = [
    "observability-bootstrap",
    "glitchtip-migrate",
]


def detect_host_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def advertised_control_plane_ip(env: dict[str, str]) -> str:
    explicit = str(env.get("CPLATFORM_PRIMARY_NODE_IP", "")).strip()
    if explicit and explicit not in {"127.0.0.1", "0.0.0.0", "localhost"}:
        return explicit
    return detect_host_ip()


def copy_if_missing(target: Path, example: Path) -> bool:
    if target.exists():
        return False
    if not example.exists():
        raise ObservabilityError(f"Missing example env file: {example}")
    shutil.copyfile(example, target)
    return True


def patch_primary_node_ip(env_path: Path, host_ip: str) -> None:
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    changed = False
    for idx, line in enumerate(lines):
        if line.startswith("CPLATFORM_PRIMARY_NODE_IP=") and line.split("=", 1)[1].strip() in {"", "127.0.0.1"}:
            lines[idx] = f"CPLATFORM_PRIMARY_NODE_IP={host_ip}"
            changed = True
    if changed:
        env_path.write_text("\n".join(lines) + "\n")


def derive_remote_loki_ingest_url(env: dict[str, str], host_ip: str, loki_host_port: int) -> str:
    explicit = str(env.get("CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL", "")).strip()
    if explicit:
        return explicit
    return f"http://{host_ip}:{loki_host_port}"


def patch_remote_loki_ingest_url(
    env_path: Path,
    target_url: str,
    *,
    detected_host_ip: str | None = None,
    host_port: int | None = None,
) -> None:
    if not env_path.exists():
        return

    internal_defaults = {
        "",
        "http://loki:3100",
        "http://127.0.0.1:3100",
        "http://localhost:3100",
    }
    if detected_host_ip and host_port:
        internal_defaults.add(f"http://{detected_host_ip}:{host_port}")
    lines = env_path.read_text().splitlines()
    changed = False

    for idx, line in enumerate(lines):
        if not line.startswith("CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL="):
            continue
        current_value = line.split("=", 1)[1].strip()
        if current_value in internal_defaults:
            lines[idx] = f"CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL={target_url}"
            changed = True
        break

    if changed:
        env_path.write_text("\n".join(lines) + "\n")


def ensure_directories(machine_volume: Path, loki_uid: int, loki_gid: int) -> list[str]:
    created = []
    paths = [
        machine_volume / "iktara/cPlatform/logs",
        machine_volume / "iktara/Repository",
        machine_volume / "iktara/observability/loki",
        machine_volume / "iktara/observability/alloy",
        machine_volume / "iktara/observability/glitchtip/postgres",
        machine_volume / "iktara/observability/glitchtip/valkey",
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))
    loki_root = machine_volume / "iktara/observability/loki"
    try:
        os.chown(loki_root, loki_uid, loki_gid)
    except PermissionError as exc:
        raise ObservabilityError(
            f"Unable to change ownership of {loki_root} to {loki_uid}:{loki_gid}; run bootstrap with permissions to prepare Loki storage"
        ) from exc
    for child in loki_root.rglob("*"):
        try:
            os.chown(child, loki_uid, loki_gid)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise ObservabilityError(
                f"Unable to change ownership of {child} to {loki_uid}:{loki_gid}; run bootstrap with permissions to prepare Loki storage"
            ) from exc
    return created


def bootstrap_ports() -> list[int]:
    return list(DEFAULT_PORTS.values())


def validate_ports(ports: list[int]) -> list[int]:
    busy = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                busy.append(port)
    return busy


def inspect_network(network_name: str):
    proc = subprocess.run(["docker", "network", "inspect", network_name], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)[0]


def validate_network(network_name: str, subnet: str, gateway: str) -> None:
    network = inspect_network(network_name)
    if network is None:
        return
    configs = network.get("IPAM", {}).get("Config") or []
    if not configs:
        raise ObservabilityError(f"Docker network {network_name} exists without IPAM config")
    actual_subnet = configs[0].get("Subnet")
    actual_gateway = configs[0].get("Gateway")
    if actual_subnet != subnet or actual_gateway != gateway:
        raise ObservabilityError(
            f"Docker network {network_name} exists with {actual_subnet}/{actual_gateway}, expected {subnet}/{gateway}"
        )


def ensure_network(network_name: str, subnet: str, gateway: str) -> None:
    network = inspect_network(network_name)
    if network is None:
        proc = subprocess.run(
            [
                "docker",
                "network",
                "create",
                "--driver",
                "bridge",
                "--subnet",
                subnet,
                "--gateway",
                gateway,
                network_name,
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise ObservabilityError(proc.stderr.strip() or proc.stdout.strip() or f"Unable to create Docker network {network_name}")
        return
    validate_network(network_name, subnet, gateway)


def validate_static_ips(subnet: str, ip_values: list[str]) -> None:
    network = ipaddress.ip_network(subnet, strict=False)
    for ip_value in ip_values:
        if not ip_value:
            continue
        if ipaddress.ip_address(ip_value) not in network:
            raise ObservabilityError(f"Static IP {ip_value} is outside configured subnet {subnet}")


def validate_required_source_paths(repo_root: Path) -> None:
    missing = [str(repo_root / relative_path) for relative_path in REQUIRED_SOURCE_PATHS if not (repo_root / relative_path).exists()]
    if missing:
        raise SystemExit(f"Missing required source paths: {', '.join(missing)}")


def compose_base_command(compose_file: Path) -> list[str]:
    command = ["docker", "compose"]
    command.extend(["-f", str(compose_file)])
    return command


def compose_config(compose_file: Path) -> None:
    proc = subprocess.run(compose_base_command(compose_file) + ["config", "-q"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ObservabilityError(proc.stderr.strip() or proc.stdout.strip() or "docker compose config failed")


def compose_up(compose_file: Path) -> None:
    proc = subprocess.run(compose_base_command(compose_file) + ["up", "-d"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ObservabilityError(proc.stderr.strip() or proc.stdout.strip() or "docker compose up failed")


def compose_ps(compose_file: Path) -> list[dict]:
    proc = subprocess.run(
        compose_base_command(compose_file) + ["ps", "--all", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ObservabilityError(proc.stderr.strip() or proc.stdout.strip() or "docker compose ps failed")
    payload = proc.stdout.strip()
    if not payload:
        return []
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        rows = []
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def service_states_by_name(rows: list[dict]) -> dict[str, dict]:
    states = {}
    for row in rows:
        service_name = row.get("Service") or row.get("Name")
        if service_name:
            states[service_name] = row
    return states


def service_state_value(row: dict | None) -> str:
    if not row:
        return "missing"
    return str(row.get("State") or row.get("Status") or "unknown").strip().lower()


def service_exit_code(row: dict | None) -> int | None:
    if not row:
        return None
    value = row.get("ExitCode")
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def http_probe(url: str, *, timeout: int = 5, accept_redirect: bool = False) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if accept_redirect and status in {301, 302, 303, 307, 308}:
                return True, f"status {status}"
            if status < 400:
                return True, f"status {status}"
            return False, f"status {status}"
    except urllib.error.HTTPError as exc:
        if accept_redirect and exc.code in {301, 302, 303, 307, 308}:
            return True, f"status {exc.code}"
        return False, f"status {exc.code}"
    except Exception as exc:  # pragma: no cover - network errors vary by environment
        return False, str(exc)


def build_health_checks() -> list[dict[str, object]]:
    return [
        {
            "name": "loki_ready",
            "url": f"http://127.0.0.1:{DEFAULT_PORTS['loki']}/ready",
            "accept_redirect": False,
        },
        {
            "name": "alloy_ready",
            "url": f"http://127.0.0.1:{DEFAULT_PORTS['alloy']}/-/ready",
            "accept_redirect": False,
        },
        {
            "name": "glitchtip_http",
            "url": f"http://127.0.0.1:{DEFAULT_PORTS['glitchtip']}/",
            "accept_redirect": True,
        },
        {
            "name": "cplatform_http",
            "url": f"http://127.0.0.1:{DEFAULT_PORTS['cplatform_http']}/",
            "accept_redirect": True,
        },
    ]


def wait_for_stack_health(
    compose_file: Path,
    *,
    timeout: int = 900,
    poll_interval: int = 5,
) -> dict[str, object]:
    deadline = time.time() + timeout
    last_pending: list[str] = []
    health_report: dict[str, str] = {}

    while time.time() < deadline:
        rows = compose_ps(compose_file)
        state_map = service_states_by_name(rows)
        pending: list[str] = []

        for service_name in LONG_RUNNING_SERVICES:
            row = state_map.get(service_name)
            state = service_state_value(row)
            if state == "running":
                continue
            if state in {"exited", "dead"}:
                raise ObservabilityError(f"{service_name} exited during startup")
            pending.append(f"{service_name}:{state}")

        for service_name in ONE_SHOT_SERVICES:
            row = state_map.get(service_name)
            state = service_state_value(row)
            exit_code = service_exit_code(row)
            if state in {"exited", "completed"} and exit_code in {0, None}:
                continue
            if state in {"exited", "dead"} and exit_code not in {0, None}:
                raise ObservabilityError(f"{service_name} failed during startup with exit code {exit_code}")
            pending.append(f"{service_name}:{state}")

        if not pending:
            probe_failures = []
            for check in build_health_checks():
                ok, detail = http_probe(str(check["url"]), accept_redirect=bool(check["accept_redirect"]))
                health_report[str(check["name"])] = detail
                if not ok:
                    probe_failures.append(f"{check['name']}:{detail}")
            if not probe_failures:
                return {
                    "container_states": {
                        name: service_state_value(state_map.get(name))
                        for name in LONG_RUNNING_SERVICES + ONE_SHOT_SERVICES
                    },
                    "health_checks": health_report,
                    "status": "healthy",
                }
            pending = probe_failures

        last_pending = pending
        time.sleep(poll_interval)

    raise ObservabilityError(
        f"Stack is still initializing after {timeout}s; pending checks: {', '.join(last_pending) if last_pending else 'unknown'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a cPlatform control-plane host for compose bootstrap.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--machine-volume", default="/home/ubuntu/Backup_Platform")
    parser.add_argument("--compose-file", default="cPlatform/docker-compose.yaml")
    parser.add_argument("--django-env", default="platform/docker/cPlatform/deployment.validation.env")
    parser.add_argument("--django-env-example", default="platform/docker/cPlatform/deployment.validation.env.example")
    parser.add_argument("--diagnostics-env", default="platform/docker/cPlatform/diagnostics.validation.env")
    parser.add_argument("--diagnostics-env-example", default="platform/docker/cPlatform/diagnostics.validation.env.example")
    parser.add_argument("--glitchtip-env", default="platform/observability/glitchtip.env")
    parser.add_argument("--glitchtip-env-example", default="platform/observability/glitchtip.env.example")
    parser.add_argument("--network-name", default=DEFAULT_NETWORK_NAME)
    parser.add_argument("--network-subnet", default=DEFAULT_NETWORK_SUBNET)
    parser.add_argument("--network-gateway", default=DEFAULT_NETWORK_GATEWAY)
    parser.add_argument("--loki-uid", type=int, default=10001)
    parser.add_argument("--loki-gid", type=int, default=10001)
    parser.add_argument("--skip-port-check", action="store_true")
    parser.add_argument("--start-stack", action="store_true")
    parser.add_argument("--wait-healthy", action="store_true")
    parser.add_argument("--health-timeout", type=int, default=900)
    parser.add_argument("--health-poll-interval", type=int, default=5)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    machine_volume = Path(args.machine_volume).resolve()
    compose_file = (repo_root / args.compose_file).resolve()
    django_env = (repo_root / args.django_env).resolve()
    django_env_example = (repo_root / args.django_env_example).resolve()
    diagnostics_env = (repo_root / args.diagnostics_env).resolve()
    diagnostics_env_example = (repo_root / args.diagnostics_env_example).resolve()
    glitchtip_env = (repo_root / args.glitchtip_env).resolve()
    glitchtip_env_example = (repo_root / args.glitchtip_env_example).resolve()

    validate_required_source_paths(repo_root)

    copied = []
    if copy_if_missing(django_env, django_env_example):
        copied.append(str(django_env))
    if copy_if_missing(diagnostics_env, diagnostics_env_example):
        copied.append(str(diagnostics_env))
    if copy_if_missing(glitchtip_env, glitchtip_env_example):
        copied.append(str(glitchtip_env))

    diagnostics_env_values = load_env_file(diagnostics_env, strict=True)

    detected_host_ip = detect_host_ip()
    host_ip = advertised_control_plane_ip(diagnostics_env_values)
    patch_primary_node_ip(diagnostics_env, host_ip)

    loki_host_port = DEFAULT_PORTS["loki"]
    remote_loki_ingest_url = derive_remote_loki_ingest_url(diagnostics_env_values, host_ip, loki_host_port)
    patch_remote_loki_ingest_url(
        diagnostics_env,
        remote_loki_ingest_url,
        detected_host_ip=detected_host_ip,
        host_port=loki_host_port,
    )

    load_env_file(django_env, strict=True)
    if derive_diagnostics_env_path(django_env).name != diagnostics_env.name and diagnostics_env.name not in {"diagnostics.validation.env", "diagnostics.env"}:
        raise SystemExit("Diagnostics env does not follow the expected naming contract")

    created_dirs = ensure_directories(machine_volume, args.loki_uid, args.loki_gid)
    ensure_network(args.network_name, args.network_subnet, args.network_gateway)

    if not args.skip_port_check:
        busy_ports = validate_ports(bootstrap_ports())
        if busy_ports:
            raise SystemExit(f"Required host ports already in use: {busy_ports}")

    validate_static_ips(args.network_subnet, STATIC_IPS)
    compose_config(compose_file)

    health_result = None
    if args.start_stack:
        compose_up(compose_file)
    if args.wait_healthy:
        health_result = wait_for_stack_health(
            compose_file,
            timeout=args.health_timeout,
            poll_interval=args.health_poll_interval,
        )

    print(json.dumps({
        "repo_root": str(repo_root),
        "machine_volume": str(machine_volume),
        "django_env": str(django_env),
        "diagnostics_env": str(diagnostics_env),
        "glitchtip_env": str(glitchtip_env),
        "copied_env_files": copied,
        "created_directories": created_dirs,
        "network_name": args.network_name,
        "network_subnet": args.network_subnet,
        "network_gateway": args.network_gateway,
        "ports": DEFAULT_PORTS,
        "remote_loki_ingest_url": remote_loki_ingest_url,
        "compose_file": str(compose_file),
        "started_stack": args.start_stack,
        "waited_for_health": args.wait_healthy,
        "health_timeout": args.health_timeout if args.wait_healthy else None,
        "health_result": health_result,
        "status": "ok",
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ObservabilityError as exc:
        raise SystemExit(str(exc))
