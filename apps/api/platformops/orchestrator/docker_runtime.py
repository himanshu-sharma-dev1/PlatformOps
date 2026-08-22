"""Small Docker SDK adapter for local-node runtime operations.

The API may run without a Docker CLI (or without the CLI using the same
engine).  The configured Docker SDK environment, including ``DOCKER_HOST``,
is the source of truth for local nodes.  Remote nodes must continue to use
their SSH/Ansible paths in the calling modules.
"""

from __future__ import annotations

import io
import hashlib
import shlex
import stat as stat_module
import tarfile
from pathlib import PurePosixPath
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


def _write_engine_bind_source(client: Any, host_path: str, content: str, helper_image: str) -> tuple[bool, str]:
    """Write through an engine-host bind source while its service is stopped."""

    target = PurePosixPath(host_path)
    helper = None
    stage_name = f".{target.name}.platformops-rollback"
    try:
        helper = client.containers.create(
            helper_image,
            entrypoint=["sleep"],
            command=["120"],
            volumes={str(target.parent): {"bind": "/platformops-target", "mode": "rw"}},
        )
        helper.start()
        payload = content.encode("utf-8")
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w") as archive:
            info = tarfile.TarInfo(name=stage_name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
        archive_buffer.seek(0)
        if not helper.put_archive("/platformops-target", archive_buffer.read()):
            return False, "Docker did not accept the bind-source rollback stage"
        destination = shlex.quote(f"/platformops-target/{target.name}")
        stage = shlex.quote(f"/platformops-target/{stage_name}")
        result = helper.exec_run(
            ["sh", "-c", f"test -f {destination} && cat {stage} > {destination} && rm -f {stage}"],
            stdout=True,
            stderr=True,
            demux=False,
        )
        output = getattr(result, "output", b"") or b""
        text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
        if int(getattr(result, "exit_code", 1)) != 0:
            return False, text.strip() or "engine-host bind-source write failed"
        return True, ""
    except Exception as exc:
        return False, str(exc)[:400]
    finally:
        if helper is not None:
            try:
                helper.remove(force=True)
            except Exception:
                pass


def write_container_file(container_name: str, path: str, content: str) -> tuple[bool, str]:
    """Atomically stage and write a text file through the configured engine."""

    if not container_name or not path.startswith("/"):
        return False, "container name and absolute target path are required"
    client = None
    bind_mount: dict[str, Any] | None = None
    helper_image = "redis:7-alpine"
    target_path = PurePosixPath(path)
    staged_name = f".{target_path.name}.platformops-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"
    try:
        client = _docker_module().from_env()
        container = client.containers.get(container_name)
        parent = str(target_path.parent)
        payload = content.encode("utf-8")
        container.reload()
        running = bool((container.attrs.get("State") or {}).get("Running"))
        bind_mount = next(
            (
                mount
                for mount in (container.attrs.get("Mounts") or [])
                if isinstance(mount, dict)
                and str(mount.get("Type") or "") == "bind"
                and str(mount.get("Destination") or "") == str(target_path)
            ),
            None,
        )
        bind_mounted_target = bind_mount is not None
        helper_image = str(
            ((container.attrs.get("Config") or {}).get("Image"))
            or getattr(getattr(container, "image", None), "tags", [""])[0]
            or "redis:7-alpine"
        )
        if not running and bind_mount is not None:
            return _write_engine_bind_source(client, str(bind_mount.get("Source") or ""), content, helper_image)
        archive_name = staged_name if running else target_path.name
        file_mode, file_uid, file_gid = 0o644, 0, 0
        try:
            stream, file_stat = container.get_archive(str(target_path))
            stat_mode = int((file_stat or {}).get("mode") or 0)
            if stat_mode and stat_module.S_ISDIR(stat_mode):
                return False, "runtime config target is a directory, not a regular file"
            archive_bytes = b"".join(stream)
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as existing:
                member = next((item for item in existing.getmembers() if item.isfile()), None)
                if member is None:
                    return False, "runtime config target is a directory, not a regular file"
                file_mode = member.mode & 0o777
                file_uid = member.uid
                file_gid = member.gid
        except Exception:
            # Some test doubles and older Docker APIs omit get_archive metadata.
            # 0644 is the safe service-readable fallback, never the old 0600.
            pass
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w") as archive:
            info = tarfile.TarInfo(name=archive_name)
            info.size = len(payload)
            info.mode = file_mode or 0o644
            info.uid = file_uid
            info.gid = file_gid
            archive.addfile(info, io.BytesIO(payload))
        archive_buffer.seek(0)
        if not container.put_archive(parent, archive_buffer.read()):
            return False, "Docker did not accept the staged config archive"
        if not running:
            return True, ""
        target = shlex.quote(str(target_path))
        stage = shlex.quote(str(target_path.parent / staged_name))
        replace_command = (
            f"cat {stage} > {target} && rm -f {stage}"
            if bind_mounted_target
            else f"chmod {oct(file_mode or 0o644)[2:]} {stage} && chown {file_uid}:{file_gid} {stage} && mv -f {stage} {target}"
        )
        result = container.exec_run(
            ["sh", "-c", replace_command],
            stdout=True,
            stderr=True,
            demux=False,
        )
        output = getattr(result, "output", b"") or b""
        text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
        if int(getattr(result, "exit_code", 1)) != 0:
            try:
                container.exec_run(["rm", "-f", str(target_path.parent / staged_name)])
            except Exception:
                pass
            if bind_mount is not None:
                return _write_engine_bind_source(client, str(bind_mount.get("Source") or ""), content, helper_image)
            return False, text.strip() or "container file write failed"
        return True, ""
    except Exception as exc:
        if client is not None and bind_mount is not None:
            fallback_ok, fallback_error = _write_engine_bind_source(
                client,
                str(bind_mount.get("Source") or ""),
                content,
                helper_image,
            )
            if fallback_ok:
                return True, ""
            return False, fallback_error or str(exc)[:400]
        if _is_not_found(exc):
            return False, "container not found"
        return False, str(exc)[:400]
    finally:
        if client is not None:
            _close(client)


def ensure_engine_host_file(
    host_path: str,
    content: str,
    *,
    helper_image: str = "redis:7-alpine",
) -> tuple[bool, str]:
    """Create a regular bind-source file in the configured Docker engine.

    This is required when the API and its DinD daemon do not share a host
    filesystem. Docker otherwise creates a directory at a missing file source.
    Existing regular files are preserved byte-for-byte.
    """

    target = PurePosixPath(host_path)
    if not host_path.startswith("/") or not target.name or target.name in {".", ".."}:
        return False, "absolute engine-host file path is required"
    client = None
    helper = None
    stage_name = f".{target.name}.platformops-initial"
    try:
        client = _docker_module().from_env()
        try:
            client.images.get(helper_image)
        except Exception:
            client.images.pull(helper_image)
        helper = client.containers.create(
            helper_image,
            entrypoint=["sleep"],
            command=["120"],
            volumes={str(target.parent): {"bind": "/platformops-target", "mode": "rw"}},
        )
        helper.start()
        payload = content.encode("utf-8")
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w") as archive:
            info = tarfile.TarInfo(name=stage_name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
        archive_buffer.seek(0)
        if not helper.put_archive("/platformops-target", archive_buffer.read()):
            return False, "Docker did not accept the engine-host config stage"
        destination = shlex.quote(f"/platformops-target/{target.name}")
        stage = shlex.quote(f"/platformops-target/{stage_name}")
        result = helper.exec_run(
            [
                "sh",
                "-c",
                f"if [ -f {destination} ]; then rm -f {stage}; exit 0; fi; "
                f"if [ -d {destination} ]; then rmdir {destination} || exit 1; fi; "
                f"chmod 644 {stage} && mv -f {stage} {destination}",
            ],
            stdout=True,
            stderr=True,
            demux=False,
        )
        output = getattr(result, "output", b"") or b""
        text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
        if int(getattr(result, "exit_code", 1)) != 0:
            return False, text.strip() or "engine-host config file creation failed"
        return True, ""
    except Exception as exc:
        return False, str(exc)[:400]
    finally:
        if helper is not None:
            try:
                helper.remove(force=True)
            except Exception:
                pass
        if client is not None:
            _close(client)


def restart_container(container_name: str, *, timeout: int = 30) -> tuple[bool, str]:
    """Restart a configured-engine container and verify it returns running."""

    client = None
    try:
        client = _docker_module().from_env()
        container = client.containers.get(container_name)
        container.restart(timeout=timeout)
        container.reload()
        state = (container.attrs.get("State") or {}).get("Status")
        if state != "running":
            return False, f"container state after restart is {state or 'unknown'}"
        return True, ""
    except Exception as exc:
        if _is_not_found(exc):
            return False, "container not found"
        return False, str(exc)[:400]
    finally:
        if client is not None:
            _close(client)


def reload_container(container_name: str) -> tuple[bool, str]:
    """Ask PID 1 to reload its configuration and verify the container is alive."""

    if not container_name:
        return False, "empty container name"
    ok, output, error = exec_container(container_name, ["kill", "-HUP", "1"])
    if not ok:
        return False, error or output.strip() or "container reload failed"
    attrs, inspect_error = inspect_container(container_name)
    if inspect_error:
        return False, inspect_error
    state = (attrs or {}).get("State") or {}
    if state.get("Running") is False or state.get("Status") not in {None, "running"}:
        return False, f"container state after reload is {state.get('Status') or 'unknown'}"
    return True, ""


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
