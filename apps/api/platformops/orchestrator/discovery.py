from __future__ import annotations

import json
import subprocess
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import get_service_contract
from ..jobs import create_job, finish_job
from ..models import Node, ServiceInstance
from ..settings import settings
from .common import _ansible_base_command, record_event


def _infer_service_key(container_name: str, image: str) -> str | None:
    """Match a running container to a catalog service_key, or None if no match."""
    name_l = (container_name or "").lower()
    image_l = (image or "").lower()
    hay = f"{name_l} {image_l}"

    # Prefer catalog cards when available
    try:
        from .service import catalog_cards

        cards = catalog_cards()
    except Exception:
        cards = []

    for card in cards:
        key = (card.get("service_key") or card.get("key") or "").lower()
        display = (card.get("name") or card.get("display_name") or "").lower()
        if key and (key in name_l or key.replace("-", "") in name_l.replace("-", "") or key in image_l):
            return card.get("service_key") or card.get("key")
        if display and display in name_l:
            return card.get("service_key") or card.get("key")

    # Static infra heuristics
    heuristics = [
        ("postgres-core", ["postgres", "postgresql"]),
        ("redis-core", ["redis"]),
        ("rabbitmq-core", ["rabbitmq"]),
        ("loki-core", ["loki"]),
        ("prometheus-core", ["prometheus"]),
        ("alloy-core", ["alloy"]),
        ("clickhouse-core", ["clickhouse"]),
        ("node-exporter", ["node-exporter", "node_exporter"]),
    ]
    for key, tokens in heuristics:
        if any(t in hay for t in tokens):
            return key
    return None


def _parse_containers_payload(raw: str) -> list[dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return []
    # Try JSON array first
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
        if isinstance(data, dict):
            return [data]
    except Exception:
        pass
    # Line-delimited JSON objects
    containers = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                containers.append(obj)
        except Exception:
            continue
    return containers


def _docker_ps_local() -> tuple[list[dict[str, Any]], str | None]:
    try:
        proc = subprocess.run(
            [
                "docker",
                "ps",
                "--format",
                '{"id":"{{.ID}}","names":"{{.Names}}","image":"{{.Image}}","ports":"{{.Ports}}","status":"{{.Status}}"}',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return [], (proc.stderr or proc.stdout or "docker ps failed").strip()
        containers = _parse_containers_payload(proc.stdout)
        # docker --format one object per line
        if not containers and proc.stdout.strip():
            containers = _parse_containers_payload("\n".join(f"{{{ln}}}" if not ln.strip().startswith("{") else ln for ln in proc.stdout.splitlines()))
        # Fix format: each line is already a JSON object without array
        if not containers:
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    containers.append(json.loads(line))
                except Exception:
                    continue
        return containers, None
    except FileNotFoundError:
        return [], "docker CLI not available"
    except Exception as exc:
        return [], str(exc)


def _docker_ps_remote(node: Node) -> tuple[list[dict[str, Any]], str | None]:
    try:
        inventory = node.host
        user = node.ssh_user or "ubuntu"
        key_arg = ["--private-key", node.ssh_key_path] if node.ssh_key_path else []
        cmd = [
            "ansible",
            inventory,
            "-m",
            "shell",
            "-a",
            'docker ps --format \'{"id":"{{.ID}}","names":"{{.Names}}","image":"{{.Image}}","ports":"{{.Ports}}","status":"{{.Status}}"}\'',
            "-u",
            user,
            *key_arg,
        ]
        # Fix ansible template conflict: use printf style without jinja
        cmd = [
            "ansible",
            inventory,
            "-m",
            "shell",
            "-a",
            "docker ps --format '{{json .}}'",
            "-u",
            user,
            *key_arg,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(settings.project_root),
        )
        if proc.returncode != 0:
            return [], (proc.stderr or proc.stdout or "ansible docker ps failed").strip()[:500]
        # Strip ansible headers
        lines = []
        for line in proc.stdout.splitlines():
            s = line.strip()
            if not s or s.startswith(inventory) or "SUCCESS" in s or "CHANGED" in s or s.startswith(">>"):
                # sometimes "host | SUCCESS | ..." then later lines
                if ">>" in s:
                    s = s.split(">>", 1)[-1].strip()
                else:
                    continue
            if s.startswith("{"):
                lines.append(s)
        containers = []
        for line in lines:
            try:
                containers.append(json.loads(line))
            except Exception:
                continue
        # Alternative: full playbook output
        if not containers:
            containers = _parse_containers_payload(proc.stdout)
        return containers, None
    except FileNotFoundError:
        return [], "ansible CLI not available"
    except Exception as exc:
        return [], str(exc)


def discover_infrastructure(db: Session, node: Node) -> dict:
    """Discover running Docker containers on a node and adopt catalog matches (real only)."""
    command = f"{_ansible_base_command(node, 'service_infra_discovery_playbook.yml')}"
    job = create_job(db, action="discover-infra", command=command, node_id=node.id)

    # Prefer local docker when node is local / localhost
    is_local = (
        settings.local_mode
        or (node.environment or "").lower() == "local"
        or (node.host or "") in {"localhost", "127.0.0.1", "0.0.0.0", ""}
    )

    if is_local:
        containers, err = _docker_ps_local()
    else:
        containers, err = _docker_ps_remote(node)

    if err is not None and not containers:
        finish_job(db, job, ok=False, output="", error=err)
        return {
            "status": "error",
            "error": err,
            "containers_scanned": 0,
            "adopted_count": 0,
            "adopted_services": [],
            "containers": [],
        }

    adopted_instances: list[ServiceInstance] = []
    adopted_names: list[str] = []
    scanned: list[dict[str, Any]] = []

    for container in containers:
        names = container.get("names") or container.get("Names") or container.get("name") or ""
        # docker json format may use Names as /name
        if isinstance(names, list):
            names = names[0] if names else ""
        names = str(names).lstrip("/")
        image = container.get("image") or container.get("Image") or ""
        ports = container.get("ports") or container.get("Ports") or ""
        status = container.get("status") or container.get("Status") or ""
        cid = container.get("id") or container.get("ID") or container.get("Id") or ""

        scanned.append(
            {
                "id": cid,
                "names": names,
                "image": image,
                "ports": ports,
                "status": status,
            }
        )

        service_key = _infer_service_key(names, image)
        if not service_key:
            continue

        existing = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == node.id,
                ServiceInstance.container_name == names,
            )
        )
        if existing:
            existing.status = "running" if "up" in status.lower() else existing.status
            existing.image = image or existing.image
            db.commit()
            continue

        contract = {}
        try:
            contract = get_service_contract(service_key) or {}
        except Exception:
            contract = {}

        from .ids import allocate_service_external_id

        kind = contract.get("kind") or "infrastructure"
        display = contract.get("display_name") or contract.get("name") or names
        external_id = allocate_service_external_id(
            db,
            discovered_names=[c.get("names") or c.get("Names") or "" for c in scanned],
        )
        svc = ServiceInstance(
            external_id=external_id,
            node_id=node.id,
            service_key=service_key,
            name=f"Adopted {display}",
            kind=kind,
            container_name=names,
            image=image,
            status="running" if "up" in status.lower() else "unknown",
            config_json=json.dumps(
                {
                    "adopted": True,
                    "ports": ports,
                    "discovery_id": cid,
                    "install_mode": "manual",
                }
            ),
        )
        db.add(svc)
        db.commit()
        db.refresh(svc)
        adopted_instances.append(svc)
        adopted_names.append(svc.name)

    finish_job(
        db,
        job,
        ok=True,
        output=json.dumps({"containers": scanned, "adopted": adopted_names}, indent=2),
    )
    record_event(
        db,
        category="discovery",
        level="info",
        message=f"Discovered {len(scanned)} containers on {node.name}; adopted {len(adopted_instances)}",
        node_id=node.id,
        metadata={"scanned": len(scanned), "adopted": len(adopted_instances)},
    )
    return {
        "status": "success",
        "containers_scanned": len(scanned),
        "adopted_count": len(adopted_instances),
        "adopted_services": adopted_names,
        "containers": scanned,
        "error": err,
    }
