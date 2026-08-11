"""Small Docker SDK adapter for local-node runtime operations.

The API may run without a Docker CLI (or without the CLI using the same
engine).  The configured Docker SDK environment, including ``DOCKER_HOST``,
is the source of truth for local nodes.  Remote nodes must continue to use
their SSH/Ansible paths in the calling modules.
"""

from __future__ import annotations

from typing import Any


def _docker_module() -> Any:
    try:
        import docker  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime image supplies it
        raise RuntimeError("Docker SDK is not installed") from exc
    return docker


def _close(client: Any) -> None:
    try:
        client.close()
    except Exception:
        pass


def _is_not_found(exc: Exception) -> bool:
    # Keep this adapter testable without importing Docker at module import
    # time.  Docker SDK raises docker.errors.NotFound for this case.
    return exc.__class__.__name__.lower() == "notfound"


def engine_version() -> str:
    """Return the configured local engine version or raise its real error."""

    client = None
    try:
        client = _docker_module().from_env()
        return str(client.version().get("Version") or "")
    finally:
        if client is not None:
            _close(client)


def inspect_container(container_name: str) -> tuple[dict[str, Any] | None, str | None]:
    """Inspect a container through the configured local Docker engine."""

    if not container_name:
        return None, "empty container name"
    client = None
    try:
        client = _docker_module().from_env()
        container = client.containers.get(container_name)
        attrs = container.attrs
        return (dict(attrs) if isinstance(attrs, dict) else None), None
    except Exception as exc:
        if _is_not_found(exc):
            return None, "not_found"
        return None, str(exc)[:400]
    finally:
        if client is not None:
            _close(client)


def container_logs(container_name: str, *, tail: int) -> tuple[bytes, str | None]:
    """Return a bounded timestamped container log tail."""

    if not container_name:
        return b"", "empty container name"
    client = None
    try:
        client = _docker_module().from_env()
        container = client.containers.get(container_name)
        output = container.logs(stdout=True, stderr=True, timestamps=True, tail=tail)
        if isinstance(output, str):
            output = output.encode()
        return bytes(output or b""), None
    except Exception as exc:
        if _is_not_found(exc):
            return b"", "container not found"
        return b"", str(exc)[:400]
    finally:
        if client is not None:
            _close(client)


def exec_container(container_name: str, args: list[str]) -> tuple[bool, str, str]:
    """Run a non-shell command in a local container."""

    if not container_name:
        return False, "", "empty container name"
    client = None
    try:
        client = _docker_module().from_env()
        container = client.containers.get(container_name)
        result = container.exec_run(args, stdout=True, stderr=True, demux=False)
        exit_code = int(getattr(result, "exit_code", 0) or 0)
        output = getattr(result, "output", b"") or b""
        if isinstance(output, bytes):
            text = output.decode("utf-8", errors="replace")
        else:
            text = str(output)
        if exit_code:
            return False, text, text.strip() or f"container command exited with code {exit_code}"
        return True, text, ""
    except Exception as exc:
        if _is_not_found(exc):
            return False, "", "container not found"
        return False, "", str(exc)[:400]
    finally:
        if client is not None:
            _close(client)


def list_containers(*, all_containers: bool = True) -> tuple[list[dict[str, Any]], str | None]:
    """List local-engine containers in the shape used by discovery."""

    client = None
    try:
        client = _docker_module().from_env()
        raw_items = client.api.containers(all=all_containers)
        containers: list[dict[str, Any]] = []
        for item in raw_items or []:
            network_settings = item.get("NetworkSettings") or {}
            networks = network_settings.get("Networks") or {}
            names = item.get("Names") or []
            ports: list[str] = []
            for port in item.get("Ports") or []:
                if not isinstance(port, dict):
                    ports.append(str(port))
                    continue
                private_port = port.get("PrivatePort")
                public_port = port.get("PublicPort")
                protocol = port.get("Type") or "tcp"
                if public_port:
                    host_ip = port.get("IP") or "0.0.0.0"
                    ports.append(f"{host_ip}:{public_port}->{private_port}/{protocol}")
                elif private_port:
                    ports.append(f"{private_port}/{protocol}")
            containers.append(
                {
                    "id": item.get("Id") or item.get("ID") or "",
                    "names": names[0].lstrip("/") if names else "",
                    "image": item.get("Image") or "",
                    "ports": ports,
                    "status": item.get("Status") or item.get("State") or "",
                    "networks": list(networks.keys()) if isinstance(networks, dict) else networks,
                    "labels": item.get("Labels") or {},
                }
            )
        return containers, None
    except Exception as exc:
        return [], str(exc)[:500]
    finally:
        if client is not None:
            _close(client)
