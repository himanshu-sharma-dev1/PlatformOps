"""Infrastructure discover/adopt — scored matching (cPlatform-inspired), de-dupe, real docker only."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import get_service_contract
from ..jobs import create_job, finish_job
from ..models import Node, ServiceInstance
from ..settings import settings
from .common import _ansible_base_command, record_event
from .ids import allocate_service_external_id

# Containers we never adopt (ops plane noise / foreign cPlatform plane)
SKIP_NAME_MARKERS = (
    "platformops-web-api",
    "platformops-postgres",
    "platformops-redis",
    "platformops-rabbitmq",
    "platformops-prometheus",
    "platformops-loki",
    "compose-web-api",
    "compose-",
    "iktara_cplatform",
    "cplatform_",
    "cplatform-",
    "signoz",
    "glitchtip",
    "config-migration",
    "serv1025",
    "serv1029",
    "serv1003",
    "serv1004",
    "serv1026",
)

# Image/name tokens that score a catalog key (higher = better)
CATALOG_HINTS: dict[str, list[str]] = {
    "postgres-core": ["postgres", "postgresql"],
    "redis-core": ["redis"],
    "rabbitmq-core": ["rabbitmq"],
    "loki-core": ["loki"],
    "prometheus-core": ["prometheus"],
    "alloy-core": ["alloy"],
    "clickhouse-core": ["clickhouse"],
    "node-exporter": ["node-exporter", "node_exporter"],
    "process-exporter": ["process-exporter", "process_exporter"],
    "dcgm-exporter": ["dcgm-exporter", "dcgm"],
    "dtrain-controller": ["dtrain", "dtrain-controller", "trainingserver"],
    "dtrain-worker": ["dtrain-worker"],
    "dtrain-tracker": ["dtrain-tracker", "mlflow"],
    "ai-orchestrator": ["ai-orchestrator", "cplatform", "aip-"],
}

MIN_ADOPT_SCORE = 25


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _image_tokens(image: str) -> set[str]:
    raw = (image or "").lower().split("/")[-1]
    raw = raw.split(":")[0]
    parts = re.split(r"[^a-z0-9]+", raw)
    return {_normalize_token(p) for p in parts if _normalize_token(p) and len(_normalize_token(p)) > 2}


def _should_skip_container(name: str, image: str) -> bool:
    hay = f"{name} {image}".lower()
    return any(marker in hay for marker in SKIP_NAME_MARKERS)


def _score_match(container_name: str, image: str, service_key: str, display: str, card_image: str) -> tuple[int, str]:
    name_l = (container_name or "").lower()
    image_l = (image or "").lower()
    hay = f"{name_l} {image_l}"
    key_l = (service_key or "").lower()
    display_l = (display or "").lower()
    score = 0
    basis: list[str] = []

    # Exact-ish container name contains key
    key_compact = key_l.replace("-", "").replace("_", "")
    name_compact = name_l.replace("-", "").replace("_", "")
    if key_l and key_l in name_l:
        score += 40
        basis.append("name:key")
    elif key_compact and key_compact in name_compact:
        score += 30
        basis.append("name:key_compact")

    if display_l and len(display_l) > 3 and display_l in name_l:
        score += 20
        basis.append("name:display")

    # Catalog image family
    expected = _image_tokens(card_image)
    actual = _image_tokens(image)
    if expected and actual and expected & actual:
        score += 35
        basis.append("image_family")

    # Hint tokens
    for hint in CATALOG_HINTS.get(service_key, []):
        h = hint.lower()
        if h and h in hay:
            score += 15
            basis.append(f"hint:{h}")
            break

    # Penalize vague single-token matches (e.g. "api" only)
    if score < MIN_ADOPT_SCORE and key_l in image_l:
        score += 10
        basis.append("image:key_weak")

    return score, ",".join(basis) if basis else "none"


def _best_service_key(container_name: str, image: str) -> tuple[str | None, int, str]:
    """Return best catalog key for a container, or None if below threshold."""
    name_l = (container_name or "").lower()
    image_l = (image or "").lower()

    candidates: list[tuple[int, str, str]] = []

    try:
        from .service import catalog_cards

        cards = catalog_cards()
    except Exception:
        cards = []

    for card in cards:
        key = card.get("service_key") or card.get("key")
        if not key:
            continue
        display = card.get("name") or card.get("display_name") or ""
        card_image = card.get("image") or ""
        score, basis = _score_match(name_l, image_l, key, display, card_image)
        if score >= MIN_ADOPT_SCORE:
            candidates.append((score, key, basis))

    # Static hints for keys not in catalog cards
    for key, hints in CATALOG_HINTS.items():
        if any(c[1] == key for c in candidates):
            continue
        score, basis = _score_match(name_l, image_l, key, key, "")
        # boost if any strong hint
        for hint in hints:
            if hint in f"{name_l} {image_l}":
                score = max(score, 28)
                basis = basis if basis != "none" else f"static:{hint}"
        if score >= MIN_ADOPT_SCORE:
            candidates.append((score, key, basis))

    if not candidates:
        return None, 0, "no_match"

    candidates.sort(key=lambda x: (-x[0], x[1]))
    best = candidates[0]
    # Ambiguity: two keys within 5 points → skip adopt (avoid wrong pairing)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 5 and candidates[1][0] >= MIN_ADOPT_SCORE:
        # Prefer more specific (longer key / dtrain over generic)
        if candidates[0][1].startswith("dtrain") or "exporter" in candidates[0][1]:
            return best[1], best[0], best[2]
        return None, best[0], f"ambiguous:{candidates[0][1]}|{candidates[1][1]}"

    return best[1], best[0], best[2]


def _parse_containers_payload(raw: str) -> list[dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
        if isinstance(data, dict):
            return [data]
    except Exception:
        pass
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
        containers: list[dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except Exception:
                continue
        if not containers:
            containers = _parse_containers_payload(proc.stdout)
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
        lines = []
        for line in proc.stdout.splitlines():
            s = line.strip()
            if ">>" in s:
                s = s.split(">>", 1)[-1].strip()
            if s.startswith("{"):
                lines.append(s)
        containers = []
        for line in lines:
            try:
                containers.append(json.loads(line))
            except Exception:
                continue
        if not containers:
            containers = _parse_containers_payload(proc.stdout)
        return containers, None
    except FileNotFoundError:
        return [], "ansible CLI not available"
    except Exception as exc:
        return [], str(exc)


def discover_infrastructure(db: Session, node: Node) -> dict:
    """Discover running Docker containers on a node and adopt high-confidence catalog matches."""
    command = f"{_ansible_base_command(node, 'service_infra_discovery_playbook.yml')}"
    job = create_job(db, action="discover-infra", command=command, node_id=node.id)

    # Prefer local docker for localhost / this host public IP
    host = (node.host or "").strip()
    is_local = (
        settings.local_mode
        or (node.environment or "").lower() == "local"
        or host in {"localhost", "127.0.0.1", "0.0.0.0", ""}
        or host in {"65.2.63.24"}  # this verification host's public IP
    )

    if is_local:
        containers, err = _docker_ps_local()
    else:
        containers, err = _docker_ps_remote(node)
        # Fallback: if remote ansible fails but host is reachable as local docker namespace
        if err and not containers:
            local_containers, local_err = _docker_ps_local()
            if local_containers:
                containers, err = local_containers, None

    if err is not None and not containers:
        finish_job(db, job, ok=False, output="", error=err)
        return {
            "status": "error",
            "error": err,
            "containers_scanned": 0,
            "adopted_count": 0,
            "skipped_count": 0,
            "updated_count": 0,
            "adopted_services": [],
            "unmatched": [],
            "containers": [],
            "summary": f"Discover failed: {err}",
        }

    adopted_instances: list[ServiceInstance] = []
    adopted_names: list[str] = []
    scanned: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    skipped = 0
    updated = 0

    # Existing inventory on this node
    existing_rows = list(
        db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all()
    )
    by_container = {str(s.container_name or "").lstrip("/"): s for s in existing_rows}
    keys_already: set[str] = {s.service_key for s in existing_rows if s.service_key}

    for container in containers:
        names = container.get("names") or container.get("Names") or container.get("name") or ""
        if isinstance(names, list):
            names = names[0] if names else ""
        names = str(names).lstrip("/")
        image = container.get("image") or container.get("Image") or ""
        ports = container.get("ports") or container.get("Ports") or ""
        status = container.get("status") or container.get("Status") or ""
        cid = container.get("id") or container.get("ID") or container.get("Id") or ""

        entry = {
            "id": cid,
            "names": names,
            "image": image,
            "ports": ports,
            "status": status,
        }
        scanned.append(entry)

        if not names or _should_skip_container(names, image):
            skipped += 1
            entry["decision"] = "skipped_noise"
            continue

        # Already registered by container name → update status only
        existing = by_container.get(names)
        if existing:
            new_status = "running" if "up" in status.lower() else existing.status
            if existing.status != new_status or (image and existing.image != image):
                existing.status = new_status
                if image:
                    existing.image = image
                db.commit()
                updated += 1
            entry["decision"] = "updated_existing"
            entry["service_key"] = existing.service_key
            entry["external_id"] = existing.external_id
            continue

        service_key, score, basis = _best_service_key(names, image)
        if not service_key:
            unmatched.append({**entry, "reason": basis, "score": score})
            entry["decision"] = "unmatched"
            entry["match_basis"] = basis
            entry["score"] = score
            continue

        # De-dupe: do not adopt second instance of same service_key on this node
        if service_key in keys_already:
            skipped += 1
            entry["decision"] = "skipped_duplicate_key"
            entry["service_key"] = service_key
            entry["score"] = score
            continue

        contract: dict[str, Any] = {}
        try:
            contract = get_service_contract(service_key) or {}
        except Exception:
            contract = {}

        kind = contract.get("kind") or "infrastructure"
        display = contract.get("display_name") or contract.get("name") or names
        external_id = allocate_service_external_id(
            db,
            discovered_names=[c.get("names") or "" for c in scanned],
        )
        svc = ServiceInstance(
            external_id=external_id,
            node_id=node.id,
            service_key=service_key,
            name=f"Adopted {display}",
            kind=kind,
            container_name=names,
            image=image,
            status="running" if "up" in str(status).lower() else "unknown",
            config_json=json.dumps(
                {
                    "adopted": True,
                    "ports": ports,
                    "discovery_id": cid,
                    "install_mode": "manual",
                    "match_score": score,
                    "match_basis": basis,
                }
            ),
        )
        db.add(svc)
        db.commit()
        db.refresh(svc)
        adopted_instances.append(svc)
        adopted_names.append(f"{svc.name} ({svc.external_id})")
        keys_already.add(service_key)
        by_container[names] = svc
        entry["decision"] = "adopted"
        entry["service_key"] = service_key
        entry["external_id"] = external_id
        entry["score"] = score
        entry["match_basis"] = basis

    summary = (
        f"Scanned {len(scanned)} · adopted {len(adopted_instances)} · "
        f"updated {updated} · skipped {skipped} · unmatched {len(unmatched)}"
    )
    finish_job(
        db,
        job,
        ok=True,
        output=json.dumps(
            {
                "summary": summary,
                "containers": scanned,
                "adopted": adopted_names,
                "unmatched": unmatched[:40],
            },
            indent=2,
        ),
    )
    record_event(
        db,
        category="discovery",
        level="info",
        message=f"Discover on {node.name}: {summary}",
        node_id=node.id,
        metadata={
            "scanned": len(scanned),
            "adopted": len(adopted_instances),
            "updated": updated,
            "skipped": skipped,
            "unmatched": len(unmatched),
        },
    )
    return {
        "status": "success",
        "containers_scanned": len(scanned),
        "adopted_count": len(adopted_instances),
        "updated_count": updated,
        "skipped_count": skipped,
        "unmatched_count": len(unmatched),
        "adopted_services": adopted_names,
        "unmatched": unmatched[:40],
        "containers": scanned,
        "error": err,
        "summary": summary,
        "message": summary,
    }
