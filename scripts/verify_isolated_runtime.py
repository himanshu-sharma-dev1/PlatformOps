#!/usr/bin/env python3
"""Static safety checks for the isolated PlatformOps runtime.

This verifier only reads YAML/text.  It does not call Docker, start services,
create networks, remove volumes, or contact the live cPlatform stack.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by a missing prerequisite
    raise SystemExit("PyYAML is required for isolated-verify (pip install PyYAML).") from exc


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "ops/compose/docker-compose.isolated.yml"
DOCKERFILE_PATH = ROOT / "ops/docker/web-api/Dockerfile"
DOCKERIGNORE_PATH = ROOT / ".dockerignore"
E2E_PATH = ROOT / "scripts/run_e2e_tests.py"
FRONTEND_CLIENT_PATH = ROOT / "apps/web/src/api/client.ts"
ISOLATED_CONFIG_DIR = ROOT / "ops/compose/isolated"


class VerificationError(RuntimeError):
    """A human-readable isolated-runtime contract failure."""


def fail(message: str) -> None:
    raise VerificationError(message)


def env_map(service: dict[str, Any]) -> dict[str, str]:
    raw = service.get("environment") or {}
    if isinstance(raw, dict):
        return {str(key): "" if value is None else str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        result: dict[str, str] = {}
        for item in raw:
            if "=" in str(item):
                key, value = str(item).split("=", 1)
                result[key] = value
            else:
                result[str(item)] = ""
        return result
    fail("Compose environment must be a mapping or list")


def walk_values(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key), nested
            yield from walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield "", nested
            yield from walk_values(nested)


def host_port(port_spec: Any) -> int | None:
    """Return the host port from short or long Compose syntax."""
    if isinstance(port_spec, dict):
        value = port_spec.get("published")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    text = str(port_spec).strip().strip('"').strip("'")
    # IPv6/host-IP forms are not expected in this file, but handling a leading
    # host address keeps this check useful if the format is later expanded.
    if ":" in text and text.count(":") > 1 and not text.startswith("["):
        return None
    if ":" not in text:
        return int(text) if text.isdigit() else None
    host, _container = text.rsplit(":", 1)
    host = host.rsplit(":", 1)[-1]
    host = host.rsplit("/", 1)[-1]
    try:
        return int(host)
    except ValueError:
        return None


def parse_yaml(path: Path) -> Any:
    if not path.is_file():
        fail(f"Missing isolated configuration: {path.relative_to(ROOT)}")
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        fail(f"Invalid YAML in {path.relative_to(ROOT)}: {exc}")


def verify_compose() -> None:
    config = parse_yaml(COMPOSE_PATH)
    if not isinstance(config, dict):
        fail("Isolated Compose document must be a mapping")
    if config.get("name") != "platformops-isolated":
        fail("Isolated Compose project name must be platformops-isolated")

    services = config.get("services")
    if not isinstance(services, dict):
        fail("Isolated Compose document has no services mapping")
    required = {"platformops", "postgres", "redis", "rabbitmq", "prometheus", "loki", "docker-engine"}
    missing = required.difference(services)
    if missing:
        fail(f"Isolated Compose is missing required services: {', '.join(sorted(missing))}")

    for name, raw_service in services.items():
        if not isinstance(raw_service, dict):
            fail(f"Service {name!r} must be a mapping")
        if "container_name" in raw_service:
            fail(f"Service {name!r} uses fixed container_name; Compose must scope names")
        if raw_service.get("profiles") and "isolated" not in raw_service["profiles"] and name not in {
            "mailpit",
            "glitchtip",
            "glitchtip-db",
            "glitchtip-redis",
        }:
            fail(f"Base service {name!r} is not in the isolated profile")

        for key, nested in walk_values(raw_service):
            if key in {"ipv4_address", "ipv6_address"}:
                fail(f"Service {name!r} uses a static network address")
            if key == "volumes":
                volume_values = nested if isinstance(nested, list) else [nested]
                for volume in volume_values:
                    if "/var/run/docker.sock" in str(volume):
                        fail(f"Service {name!r} mounts the host Docker socket")

        for port in raw_service.get("ports") or []:
            published = host_port(port)
            if name == "platformops" and published != 9020:
                fail(f"PlatformOps host port must be 9020, found {port!r}")
            if name == "mailpit" and published != 9010:
                fail(f"Mailpit UI host port must be 9010, found {port!r}")
            if name not in {"platformops", "mailpit"}:
                fail(f"Dependency {name!r} publishes host port {port!r}")

    platformops_env = env_map(services["platformops"])
    expected_env = {
        "DOCKER_HOST": "tcp://docker-engine:2375",
        "PLATFORMOPS_PROMETHEUS_BASE_URL": "http://prometheus:9090",
        "PLATFORMOPS_LOKI_BASE_URL": "http://loki:3100",
    }
    for key, expected in expected_env.items():
        if platformops_env.get(key) != expected:
            fail(f"PlatformOps environment {key} must be {expected!r}")
    if platformops_env.get("PLATFORMOPS_PUBLIC_BASE_URL") != "http://localhost:9020":
        fail("PlatformOps environment PLATFORMOPS_PUBLIC_BASE_URL must target http://localhost:9020")
    if platformops_env.get("DOCKER_TLS_CERTDIR") != "":
        fail("PlatformOps must disable DinD TLS when using the isolated 2375 endpoint")

    engine = services["docker-engine"]
    if engine.get("privileged") is not True:
        fail("docker-engine must be privileged to run an isolated real Docker daemon")
    if "depends_on" in engine:
        fail("docker-engine must be the dependency root, not depend on PlatformOps")

    networks = config.get("networks") or {}
    if not isinstance(networks, dict) or not networks:
        fail("Isolated Compose must define a project-scoped bridge network")
    for network_name, network in networks.items():
        if isinstance(network, dict) and network.get("external"):
            fail(f"Network {network_name!r} is external; isolated Compose must own its network")
        if isinstance(network, dict) and "name" in network:
            fail(f"Network {network_name!r} overrides the project-scoped name")

    volumes = config.get("volumes") or {}
    if not isinstance(volumes, dict) or not volumes:
        fail("Isolated Compose must define project-scoped named volumes")
    for volume_name, volume in volumes.items():
        if isinstance(volume, dict) and (volume.get("external") or "name" in volume):
            fail(f"Volume {volume_name!r} is not project-scoped")


def verify_dockerfile() -> None:
    text = DOCKERFILE_PATH.read_text(encoding="utf-8")
    if not re.search(r"^FROM\s+node:[^\s]+\s+AS\s+web-builder", text, flags=re.MULTILINE):
        fail("Production Dockerfile must have a Node frontend build stage")
    if "RUN npm run build" not in text:
        fail("Production Dockerfile must run the frontend build")
    if not re.search(r"COPY\s+--from=web-builder\s+/web/dist\s+/app/dist", text):
        fail("Production Dockerfile must copy the frontend bundle to /app/dist")
    if "/var/run/docker.sock" in text:
        fail("Production Dockerfile must not copy or mount a host Docker socket")
    dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8").splitlines()
    if "ops/compose/observability/glitchtip.env" not in {
        line.strip() for line in dockerignore if line.strip() and not line.lstrip().startswith("#")
    }:
        fail(".dockerignore must exclude the tracked observability/glitchtip.env credentials file")
    if "COPY ops/compose /app/ops/compose" not in text:
        fail("Production Dockerfile must keep the compose assets available to observability playbooks")
    if not re.search(r"COPY\s+ops/docker/web-api/docker\s+/usr/bin/docker", text):
        fail("Production Dockerfile must keep the Docker CLI available to runtime playbooks")
    ignored = {
        line.strip() for line in dockerignore if line.strip() and not line.lstrip().startswith("#")
    }
    if "ops/docker/web-api/docker" in ignored:
        fail(".dockerignore must not exclude the Docker CLI required by the runtime image")


def verify_e2e_guard() -> None:
    text = E2E_PATH.read_text(encoding="utf-8")
    if '"http://localhost:9020"' not in text:
        fail("E2E default target must be http://localhost:9020")
    if "LIVE_PLATFORMOPS_PORT = 9002" not in text or "port == LIVE_PLATFORMOPS_PORT" not in text:
        fail("E2E suite must reject the live PlatformOps port 9002")
    if '"not configured" in chat_error.lower()' not in text or "configured diagnostics chat failed" not in text:
        fail("E2E diagnostics chat must accept only an explicit unconfigured-LLM response")
    if '"target_type": "node"' not in text or "node_approval_id" not in text:
        fail("E2E node cleanup must create and use a node-scoped force approval")
    if "cleanup_window_start = datetime.utcnow()" not in text or '"node_id": node_id' not in text:
        fail("E2E node cleanup must create a current-time node maintenance window")
    if 'delete_status in ("success", "failed", "error")' not in text:
        fail("E2E cleanup must poll the service deletion job to a terminal status")
    if 'node_delete.get("status") == "deleted"' not in text or 'cluster_delete.get("status") == "deleted"' not in text:
        fail("E2E node and cluster cleanup must assert terminal deleted responses")


def verify_smoke_guards() -> None:
    frontend_sources = (
        (FRONTEND_CLIENT_PATH, "Frontend API client"),
    )
    for path, label in frontend_sources:
        text = path.read_text(encoding="utf-8")
        if '"http://localhost:9002"' in text:
            fail(f"{label} API fallback must not target the live port 9002")
        if '"http://localhost:9020"' not in text:
            fail(f"{label} API fallback must target the isolated port 9020")


def verify_supporting_yaml() -> None:
    for path in sorted(ISOLATED_CONFIG_DIR.glob("*.yml")):
        parse_yaml(path)


def main() -> int:
    try:
        verify_compose()
        verify_dockerfile()
        verify_e2e_guard()
        verify_smoke_guards()
        verify_supporting_yaml()
    except VerificationError as exc:
        print(f"isolated-verify: FAIL: {exc}", file=sys.stderr)
        return 1

    print("isolated-verify: PASS — Compose, image, and E2E safety contracts are valid.")
    print("Prerequisites for an actual run:")
    print("  - Docker Engine with Docker Compose v2 and permission to run privileged DinD.")
    print("  - Free host port 9020 for PlatformOps; Mailpit UI additionally uses 9010 when enabled.")
    print("  - Network access for image pulls and the Node/Python production image build.")
    print("  - Run `make build` before `make isolated-up` when the image is not already cached.")
    print("  - `make isolated-down` retains project volumes; remove them only by explicit review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
