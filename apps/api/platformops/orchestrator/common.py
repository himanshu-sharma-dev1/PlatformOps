from __future__ import annotations

import json
import os
import socket
import subprocess
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..catalog import (
    format_contract_value,
    get_service_contract,
    rendered_contract,
)
from ..models import (
    BackupRun,
    CapacityReport,
    DeploymentJob,
    DeploymentPlanRecord,
    DriftReport,
    IncidentRecord,
    LogArchive,
    MaintenanceWindow,
    MonitoringCheck,
    Node,
    OperationalEvent,
    PolicyFinding,
    ReleaseApproval,
    ReleaseRecord,
    RunbookExecution,
    SecretRecord,
    SloReport,
)
from ..settings import settings
from ..security import redact_secrets, redact_text

RUNNING_STATUSES = {"running", "healthy", "success"}


def detach_resource_references(
    db: Session,
    *,
    service_ids: list[int] | tuple[int, ...] = (),
    node_ids: list[int] | tuple[int, ...] = (),
) -> None:
    """Detach nullable resource links before deleting inventory rows.

    Operational history must survive force-deleting a service or node.  The
    history tables deliberately make their service/node links nullable, so
    retain each row and clear only the links that would otherwise violate a
    foreign key during the resource cascade.  This is intentionally a small
    application-level cleanup rather than a schema migration.
    """

    normalized_services = sorted({int(value) for value in service_ids if value is not None})
    normalized_nodes = sorted({int(value) for value in node_ids if value is not None})

    nullable_history_models = (
        DeploymentJob,
        IncidentRecord,
        MaintenanceWindow,
        MonitoringCheck,
        OperationalEvent,
        PolicyFinding,
        RunbookExecution,
        SecretRecord,
        SloReport,
    )
    if normalized_services:
        # These rows are owned by the service and cannot outlive its
        # non-nullable foreign key.  Delete them before the service's
        # snapshots/row are cascaded; operational/history rows above remain.
        for model in (BackupRun, DriftReport, LogArchive, ReleaseApproval, ReleaseRecord):
            db.execute(delete(model).where(model.service_id.in_(normalized_services)))
        for model in nullable_history_models:
            db.execute(
                update(model)
                .where(model.service_id.in_(normalized_services))
                .values(service_id=None)
            )
    if normalized_nodes:
        # Node reports/plans are likewise resource-owned and use non-nullable
        # node references, so remove them before the node cascade.
        for model in (CapacityReport, DeploymentPlanRecord):
            db.execute(delete(model).where(model.node_id.in_(normalized_nodes)))
        for model in nullable_history_models:
            db.execute(
                update(model)
                .where(model.node_id.in_(normalized_nodes))
                .values(node_id=None)
            )


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
    # Resolve the actual target from the explicit connection mode/host.  The
    # legacy implementation used ``environment == local`` here, which allowed
    # a node with a non-loopback host but a ``local`` environment label to run
    # lifecycle mutations against the API container's Docker daemon.
    try:
        from .discovery import resolve_connection_mode

        connection_mode = resolve_connection_mode(node)
    except Exception:
        connection_mode = "local" if (node.host or "").strip().lower() in {
            "",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        } else "ssh"
    is_local = connection_mode == "local"
    inventory = "localhost," if is_local else f"{node.host},"
    user_arg = "" if is_local else f" -u {node.ssh_user}"
    key_arg = f" --private-key {node.ssh_key_path}" if node.ssh_key_path else ""
    connection = " -c local" if is_local else ""
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
        message=redact_secrets(message),
        service_id=service_id,
        node_id=node_id,
        metadata_json=json.dumps(redact_secrets(metadata or {})),
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
    secret_token = repo_token or ""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {"connected": True, "message": f"Successfully verified Git remote branch '{repo_branch}'."}
        else:
            err = redact_text(result.stderr.strip() or "Connection test failed.", secrets=(secret_token,))
            raise ValueError(f"Git remote check failed: {err}")
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Connection handshake timed out (10s).") from exc
    except Exception as exc:
        safe_error = redact_text(str(exc), secrets=(secret_token,))
        raise ValueError(f"Git execution failed: {safe_error}") from exc


def test_registry_connection(
    registry_type: str, registry_url: str, registry_user: str | None = None, registry_password: str | None = None
) -> dict:
    # Basic check for Docker Registry or other types
    if registry_type == "local":
        return {"connected": True, "message": "Local registry connection ok."}

    url = registry_url.strip() or "registry-1.docker.io"
    # Basic ping check
    host = url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 443))
        return {"connected": True, "message": f"Successfully established TLS handshake with registry {host}."}
    except Exception as exc:
        raise ValueError(f"Failed to connect to container registry host {host}: {exc}") from exc
