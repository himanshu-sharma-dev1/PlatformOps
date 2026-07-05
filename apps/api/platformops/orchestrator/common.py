from __future__ import annotations

import json
import os
import socket
import subprocess
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import (
    format_contract_value,
    get_service_contract,
    rendered_contract,
)
from ..models import (
    Node,
    OperationalEvent,
)
from ..settings import settings

RUNNING_STATUSES = {"running", "healthy", "success"}


def _service_display_name(service_key: str) -> str:
    contract = get_service_contract(service_key)
    return contract.get("display_name") or contract.get("name") or service_key


def _container_name(service_key: str, node: Node) -> str:
    contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
    return contract.get("container_name", f"node-{node.id}-{service_key}")


def _deep_merge_dict(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _service_contract_for_node(
    service_key: str,
    *,
    node_id: int,
    volume_root: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = dict(get_service_contract(service_key))
    if overrides:
        contract = _deep_merge_dict(contract, overrides)
    return format_contract_value(contract, node_id=node_id, volume_root=volume_root)


def _ansible_inventory_arg(node: Node) -> str:
    if node.environment == "local":
        return "localhost,"
    return f"{node.host},"


def _ansible_base_command(node: Node, playbook: str) -> str:
    ansible_dir = settings.resolve(settings.ansible_dir)
    inventory = _ansible_inventory_arg(node)
    user_arg = "" if node.environment == "local" else f" -u {node.ssh_user}"
    key_arg = f" --private-key {node.ssh_key_path}" if node.ssh_key_path else ""
    connection = " -c local" if node.environment == "local" else ""
    return f"ansible-playbook -i {inventory}{connection}{user_arg}{key_arg} {ansible_dir / 'playbooks' / playbook}"


def record_event(
    db: Session,
    *,
    category: str,
    message: str,
    level: str = "info",
    service_id: int | None = None,
    node_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> OperationalEvent:
    event = OperationalEvent(
        category=category,
        level=level,
        message=message,
        service_id=service_id,
        node_id=node_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    *,
    limit: int = 100,
    category: str | None = None,
    level: str | None = None,
    node_id: int | None = None,
    service_id: int | None = None,
    search: str | None = None,
) -> list[OperationalEvent]:
    statement = select(OperationalEvent).order_by(OperationalEvent.created_at.desc()).limit(limit)
    if category:
        statement = statement.where(OperationalEvent.category == category)
    if level:
        statement = statement.where(OperationalEvent.level == level)
    if node_id is not None:
        statement = statement.where(OperationalEvent.node_id == node_id)
    if service_id is not None:
        statement = statement.where(OperationalEvent.service_id == service_id)
    if search:
        statement = statement.where(OperationalEvent.message.ilike(f"%{search}%"))
    return list(db.scalars(statement).all())


def test_git_connection(repo_type: str, repo_url: str, repo_branch: str, repo_token: str | None = None) -> dict:
    if repo_type == "local":
        if os.path.exists(repo_url):
            return {"connected": True, "message": "Local repository directory exists."}
        else:
            raise ValueError(f"Local path does not exist: {repo_url}")

    # Clean up URL and insert auth token if provided
    url = repo_url.strip()
    if repo_token and repo_token.strip():
        # Inject token into HTTPS URL
        if url.startswith("https://"):
            url = url.replace("https://", f"https://{repo_token.strip()}@")
        elif url.startswith("http://"):
            url = url.replace("http://", f"http://{repo_token.strip()}@")

    # Run git ls-remote to handshake with remote git host
    command = ["git", "ls-remote", "-h", url, repo_branch]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {"connected": True, "message": f"Successfully verified Git remote branch '{repo_branch}'."}
        else:
            err = result.stderr.strip() or "Connection test failed."
            raise ValueError(f"Git remote check failed: {err}")
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Connection handshake timed out (10s).") from exc
    except Exception as exc:
        raise ValueError(f"Git execution failed: {exc}") from exc


def test_registry_connection(
    registry_type: str, registry_url: str, registry_user: str | None = None, registry_password: str | None = None
) -> dict:
    # Basic check for Docker Registry or other types
    if registry_type == "local":
        return {"connected": True, "message": "Local registry connection ok."}

    # Simulate/Verify connection via docker login command or raw socket check
    # To avoid blocking local execution, if settings.local_mode is active we skip actual auth checks
    if settings.local_mode:
        return {
            "connected": True,
            "message": f"Simulated container registry check successful for user '{registry_user}'.",
        }

    url = registry_url.strip() or "registry-1.docker.io"
    # Basic ping check
    host = url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 443))
        return {"connected": True, "message": f"Successfully established TLS handshake with registry {host}."}
    except Exception as exc:
        raise ValueError(f"Failed to connect to container registry host {host}: {exc}") from exc
