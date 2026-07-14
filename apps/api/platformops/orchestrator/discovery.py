"""Infrastructure discover/adopt — catalog-scored only (no host name denylists)."""

from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import get_service_contract, service_catalog
from ..jobs import create_job, finish_job
from ..models import Node, ServiceInstance
from ..settings import settings
from .common import _ansible_base_command, record_event
from .ids import allocate_service_external_id


@lru_cache(maxsize=4)
def load_discovery_policy() -> dict[str, Any]:
    from ..catalog import _read_yaml

    path = settings.resolve(settings.discovery_catalog_path)
    try:
        raw = _read_yaml(path)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    pol = raw.get("discovery") if isinstance(raw.get("discovery"), dict) else raw
    return {
        "min_adopt_score": int(pol.get("min_adopt_score", 30)),
        "ambiguity_margin": int(pol.get("ambiguity_margin", 8)),
        "prefer_node_network": bool(pol.get("prefer_node_network", True)),
        "node_network_score_boost": int(pol.get("node_network_score_boost", 25)),
        "off_network_score_penalty": int(pol.get("off_network_score_penalty", 10)),
        "require_image_family_match": bool(pol.get("require_image_family_match", False)),
        "require_labels": dict(pol.get("require_labels") or {}),
        "exclude_label_equals": dict(pol.get("exclude_label_equals") or {}),
    }


def clear_discovery_policy_cache() -> None:
    load_discovery_policy.cache_clear()
    try:
        service_catalog.cache_clear()
    except Exception:
        pass


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _image_tokens(image: str) -> set[str]:
    raw = (image or "").lower().split("/")[-1]
    raw = raw.split(":")[0]
    parts = re.split(r"[^a-z0-9]+", raw)
    return {_normalize_token(p) for p in parts if _normalize_token(p) and len(_normalize_token(p)) > 2}


def _discovery_meta(service_key: str) -> dict[str, Any]:
    contract = get_service_contract(service_key) or {}
    meta = contract.get("discovery") if isinstance(contract.get("discovery"), dict) else {}
    return meta or {}


def _catalog_allows_multi_instance(service_key: str) -> bool:
    meta = _discovery_meta(service_key)
    if "multi_instance" in meta:
        return bool(meta.get("multi_instance"))
    # Default: infrastructure may run multiple; apps single unless specified
    contract = get_service_contract(service_key) or {}
    return (contract.get("kind") or "") == "infrastructure"


def score_container_against_catalog(
    container_name: str,
    image: str,
    *,
    service_key: str,
    networks: list[str] | None = None,
    labels: dict[str, str] | None = None,
    node_network: str | None = None,
    policy: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """Score one catalog key for a container. Pure function for discover + cleanup re-score."""
    pol = policy or load_discovery_policy()
    contract = get_service_contract(service_key) or {}
    if not contract:
        return 0, "unknown_key"
    meta = _discovery_meta(service_key)
    display = str(contract.get("display_name") or contract.get("name") or service_key)
    card_image = str(contract.get("image") or "")
    hints = [str(h).lower() for h in (meta.get("hints") or []) if h]

    name_l = (container_name or "").lower()
    image_l = (image or "").lower()
    hay = f"{name_l} {image_l}"
    key_l = (service_key or "").lower()
    display_l = display.lower()
    score = 0
    basis: list[str] = []

    # Label policy: exclude
    labels = labels or {}
    for lk, lv in (pol.get("exclude_label_equals") or {}).items():
        if str(labels.get(lk, "")) == str(lv):
            return 0, f"exclude_label:{lk}"

    # Label policy: require
    for lk, lv in (pol.get("require_labels") or {}).items():
        if str(labels.get(lk, "")) != str(lv):
            return 0, f"missing_label:{lk}"

    key_compact = key_l.replace("-", "").replace("_", "")
    name_compact = name_l.replace("-", "").replace("_", "")
    if key_l and key_l in name_l:
        score += 40
        basis.append("name:key")
    elif key_compact and len(key_compact) > 4 and key_compact in name_compact:
        score += 30
        basis.append("name:key_compact")

    if display_l and len(display_l) > 3 and display_l in name_l:
        score += 20
        basis.append("name:display")

    expected = _image_tokens(card_image)
    actual = _image_tokens(image)
    image_match = bool(expected and actual and expected & actual)
    if image_match:
        score += 35
        basis.append("image_family")
    elif pol.get("require_image_family_match") and card_image:
        return 0, "image_family_required"

    for hint in hints:
        if hint and hint in hay:
            score += 18
            basis.append(f"hint:{hint}")
            break

    # Container name template from catalog: node-{node_id}-service_key
    if service_key and service_key in name_l:
        score += 5

    # Network affinity (node policy, not global name ban)
    nets = [str(n).lower() for n in (networks or []) if n]
    node_net = (node_network or "").strip().lower()
    if pol.get("prefer_node_network") and node_net:
        if any(node_net == n or node_net in n for n in nets):
            score += int(pol.get("node_network_score_boost", 25))
            basis.append("network:node")
        elif nets:
            score -= int(pol.get("off_network_score_penalty", 10))
            basis.append("network:off")

    if score > 0 and key_l in image_l and "image_family" not in basis:
        score += 8
        basis.append("image:key_weak")

    return score, ",".join(basis) if basis else "none"


def best_catalog_match(
    container_name: str,
    image: str,
    *,
    networks: list[str] | None = None,
    labels: dict[str, str] | None = None,
    node_network: str | None = None,
    policy: dict[str, Any] | None = None,
) -> tuple[str | None, int, str]:
    pol = policy or load_discovery_policy()
    min_score = int(pol.get("min_adopt_score", 30))
    margin = int(pol.get("ambiguity_margin", 8))

    candidates: list[tuple[int, str, str]] = []
    for service_key in service_catalog().keys():
        meta = _discovery_meta(service_key)
        key_min = int(meta.get("min_score", min_score))
        score, basis = score_container_against_catalog(
            container_name,
            image,
            service_key=service_key,
            networks=networks,
            labels=labels,
            node_network=node_network,
            policy=pol,
        )
        if score >= key_min:
            candidates.append((score, service_key, basis))

    if not candidates:
        return None, 0, "no_match"

    candidates.sort(key=lambda x: (-x[0], -len(x[1]), x[1]))
    best = candidates[0]
    if len(candidates) > 1:
        second = candidates[1]
        if best[0] - second[0] < margin and second[0] >= min_score:
            # Prefer more specific key (longer) when tied
            if len(best[1]) >= len(second[1]) + 3:
                return best[1], best[0], best[2]
            return None, best[0], f"ambiguous:{best[1]}|{second[1]}"
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


def normalize_docker_ports(ports: Any) -> list[str]:
    """Convert docker ps / inspect port strings into Ansible published_ports form host:container.

    Examples:
      "0.0.0.0:9006->8000/tcp" -> ["9006:8000"]
      "8102:8080" -> ["8102:8080"]
      ["0.0.0.0:5000->5000/tcp", ":::5000->5000/tcp"] -> ["5000:5000"]
    """
    import re

    if ports is None or ports == "" or ports == []:
        return []
    if isinstance(ports, dict):
        # docker inspect style: {"8000/tcp": [{"HostPort": "9006"}]}
        out: list[str] = []
        for cport, bindings in ports.items():
            c = str(cport).split("/")[0]
            if not bindings:
                continue
            if isinstance(bindings, list):
                for b in bindings:
                    if isinstance(b, dict) and b.get("HostPort"):
                        out.append(f"{b['HostPort']}:{c}")
                    elif isinstance(b, str) and b:
                        out.append(f"{b}:{c}")
            elif isinstance(bindings, str):
                out.append(f"{bindings}:{c}")
        # de-dupe preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        return uniq

    raw_items: list[str]
    if isinstance(ports, list):
        raw_items = [str(p) for p in ports if p is not None and str(p).strip()]
    else:
        # docker ps may join multiple mappings with commas
        raw_items = [p.strip() for p in re.split(r"[,;]", str(ports)) if p.strip()]

    out = []
    seen = set()
    # Patterns: 0.0.0.0:9006->8000/tcp  |  :::5000->5000/tcp  |  9006:8000  |  8000/tcp
    arrow = re.compile(
        r"(?:(?:\d+\.\d+\.\d+\.\d+)|\[?::\]?|localhost)?:?(\d+)->(\d+)(?:/\w+)?"
    )
    colon = re.compile(r"^(\d+):(\d+)(?:/\w+)?$")
    bare = re.compile(r"^(\d+)(?:/\w+)?$")
    for item in raw_items:
        s = item.strip()
        if not s:
            continue
        m = arrow.search(s)
        if m:
            mapping = f"{m.group(1)}:{m.group(2)}"
        else:
            m2 = colon.match(s)
            if m2:
                mapping = f"{m2.group(1)}:{m2.group(2)}"
            else:
                m3 = bare.match(s)
                if m3:
                    mapping = f"{m3.group(1)}:{m3.group(1)}"
                else:
                    # last resort: if already host:container-ish keep digits:digits
                    m4 = re.search(r"(\d+)\D+(\d+)", s)
                    if m4 and "->" in s:
                        mapping = f"{m4.group(1)}:{m4.group(2)}"
                    else:
                        continue
        if mapping not in seen:
            seen.add(mapping)
            out.append(mapping)
    return out


def _normalize_container_record(container: dict[str, Any]) -> dict[str, Any]:
    names = container.get("names") or container.get("Names") or container.get("name") or ""
    if isinstance(names, list):
        names = names[0] if names else ""
    names = str(names).lstrip("/")
    image = container.get("image") or container.get("Image") or ""
    ports_raw = container.get("ports") or container.get("Ports") or ""
    ports = normalize_docker_ports(ports_raw)
    status = container.get("status") or container.get("Status") or ""
    cid = container.get("id") or container.get("ID") or container.get("Id") or ""

    networks: list[str] = []
    labels: dict[str, str] = {}
    raw_nets = container.get("Networks") or container.get("networks") or ""
    if isinstance(raw_nets, dict):
        networks = list(raw_nets.keys())
    elif isinstance(raw_nets, str) and raw_nets.strip():
        networks = [n.strip() for n in raw_nets.replace(",", " ").split() if n.strip()]
    raw_labels = container.get("Labels") or container.get("labels") or {}
    if isinstance(raw_labels, dict):
        labels = {str(k): str(v) for k, v in raw_labels.items()}
    elif isinstance(raw_labels, str) and raw_labels:
        # docker --format labels as comma key=value
        for part in raw_labels.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                labels[k.strip()] = v.strip()

    return {
        "id": cid,
        "names": names,
        "image": image,
        "ports": ports,
        "status": status,
        "networks": networks,
        "labels": labels,
    }


def _docker_ps_local() -> tuple[list[dict[str, Any]], str | None]:
    try:
        # Include Networks + Labels for policy scoring (not name denylists)
        proc = subprocess.run(
            [
                "docker",
                "ps",
                "--format",
                '{"id":"{{.ID}}","names":"{{.Names}}","image":"{{.Image}}","ports":"{{.Ports}}","status":"{{.Status}}","networks":"{{.Networks}}","labels":"{{.Labels}}"}',
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
        from pathlib import Path

        inventory = node.host
        user = node.ssh_user or "ubuntu"
        key = (node.ssh_key_path or "").strip()
        if key and not Path(key).is_file():
            return _docker_ps_local()
        key_arg = ["--private-key", key] if key else []
        # Prefer ansible shell json lines
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
        ]
        if key:
            cmd.extend(["-i", key])
        cmd.append(f"{user}@{inventory}")
        cmd.append(
            "docker ps --format "
            "'{\"id\":\"{{.ID}}\",\"names\":\"{{.Names}}\",\"image\":\"{{.Image}}\","
            "\"ports\":\"{{.Ports}}\",\"status\":\"{{.Status}}\",\"networks\":\"{{.Networks}}\","
            "\"labels\":\"{{.Labels}}\"}'"
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            local, local_err = _docker_ps_local()
            if local:
                return local, None
            return [], (proc.stderr or proc.stdout or "remote docker ps failed").strip()[:500]
        containers = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                containers.append(json.loads(line))
            except Exception:
                continue
        return containers, None
    except FileNotFoundError:
        return _docker_ps_local()
    except Exception as exc:
        return [], str(exc)


def resolve_connection_mode(node: Node) -> str:
    """Return local|ssh from node facts/env (no hardcoded public IPs)."""
    facts: dict[str, Any] = {}
    try:
        facts = json.loads(node.facts_json or "{}")
        if not isinstance(facts, dict):
            facts = {}
    except Exception:
        facts = {}
    mode = str(facts.get("connection_mode") or getattr(node, "connection_mode", None) or "auto").lower()
    host = (node.host or "").strip().lower()
    if mode in {"local", "ssh"}:
        return mode
    # auto
    if host in {"localhost", "127.0.0.1", "0.0.0.0", ""}:
        return "local"
    if (node.ssh_key_path or "").strip():
        return "ssh"
    if (node.environment or "").lower() == "local":
        return "local"
    return "ssh" if host else "local"


def discover_infrastructure(db: Session, node: Node) -> dict:
    """Discover containers and adopt catalog matches by score only."""
    clear_discovery_policy_cache()
    policy = load_discovery_policy()
    min_score = int(policy.get("min_adopt_score", 30))

    command = f"{_ansible_base_command(node, 'service_infra_discovery_playbook.yml')}"
    job = create_job(db, action="discover-infra", command=command, node_id=node.id)

    mode = resolve_connection_mode(node)
    if mode == "local":
        containers, err = _docker_ps_local()
    else:
        containers, err = _docker_ps_remote(node)
        if err and not containers:
            containers, err2 = _docker_ps_local()
            if containers:
                err = None
                mode = "local-fallback"

    if err is not None and not containers:
        finish_job(db, job, ok=False, output="", error=err)
        return {
            "status": "error",
            "error": err,
            "containers_scanned": 0,
            "adopted_count": 0,
            "skipped_count": 0,
            "updated_count": 0,
            "unmatched_count": 0,
            "adopted_services": [],
            "unmatched": [],
            "containers": [],
            "summary": f"Discover failed: {err}",
            "connection_mode": mode,
            "policy": {"min_adopt_score": min_score},
        }

    adopted_instances: list[ServiceInstance] = []
    adopted_names: list[str] = []
    scanned: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    skipped = 0
    updated = 0

    existing_rows = list(
        db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all()
    )
    by_container = {str(s.container_name or "").lstrip("/"): s for s in existing_rows if (s.status or "") != "deleted"}
    keys_present: dict[str, int] = {}
    for s in existing_rows:
        if (s.status or "") == "deleted":
            continue
        keys_present[s.service_key] = keys_present.get(s.service_key, 0) + 1

    node_network = (node.docker_network or "").strip()

    for container in containers:
        rec = _normalize_container_record(container)
        names = rec["names"]
        image = rec["image"]
        ports = rec["ports"]
        status = rec["status"]
        cid = rec["id"]
        networks = rec["networks"]
        labels = rec["labels"]

        entry: dict[str, Any] = {
            "id": cid,
            "names": names,
            "image": image,
            "ports": ports,
            "status": status,
            "networks": networks,
        }
        scanned.append(entry)

        if not names:
            skipped += 1
            entry["decision"] = "skipped_empty_name"
            continue

        existing = by_container.get(names)
        if existing:
            new_status = "running" if "up" in str(status).lower() else existing.status
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

        service_key, score, basis = best_catalog_match(
            names,
            image,
            networks=networks,
            labels=labels,
            node_network=node_network,
            policy=policy,
        )
        entry["score"] = score
        entry["match_basis"] = basis

        if not service_key:
            unmatched.append({**entry, "reason": basis, "score": score})
            entry["decision"] = "unmatched"
            continue

        # multi_instance from catalog discovery meta
        if not _catalog_allows_multi_instance(service_key) and keys_present.get(service_key, 0) > 0:
            skipped += 1
            entry["decision"] = "skipped_single_instance"
            entry["service_key"] = service_key
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
        # Persist catalog config surfaces so Config Manager apply works after adopt
        cfg_payload = {
            "adopted": True,
            "ports": ports,
            "discovery_id": cid,
            "install_mode": "manual",
            "match_score": score,
            "match_basis": basis,
            "networks": networks,
            "kind": kind,
            "image": image or contract.get("image") or "",
            "config_files": contract.get("config_files") or [],
            "runtime_config_path": contract.get("runtime_config_path") or "",
            "environment": contract.get("environment") or {},
            "volumes": contract.get("volumes") or [],
            "healthcheck": contract.get("healthcheck") or {},
        }
        svc = ServiceInstance(
            external_id=external_id,
            node_id=node.id,
            service_key=service_key,
            name=f"Adopted {display}",
            kind=kind,
            container_name=names,
            image=image or contract.get("image") or "",
            status="running" if "up" in str(status).lower() else "unknown",
            config_json=json.dumps(cfg_payload),
        )
        db.add(svc)
        db.commit()
        db.refresh(svc)
        adopted_instances.append(svc)
        adopted_names.append(f"{svc.name} ({svc.external_id})")
        keys_present[service_key] = keys_present.get(service_key, 0) + 1
        by_container[names] = svc
        entry["decision"] = "adopted"
        entry["service_key"] = service_key
        entry["external_id"] = external_id

    summary = (
        f"Scanned {len(scanned)} · adopted {len(adopted_instances)} · "
        f"updated {updated} · skipped {skipped} · unmatched {len(unmatched)} "
        f"(min_score={min_score}, mode={mode})"
    )
    finish_job(
        db,
        job,
        ok=True,
        output=json.dumps(
            {
                "summary": summary,
                "policy": policy,
                "connection_mode": mode,
                "containers": scanned,
                "adopted": adopted_names,
                "unmatched": unmatched[:50],
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
            "min_score": min_score,
            "mode": mode,
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
        "unmatched": unmatched[:50],
        "containers": scanned,
        "error": err,
        "summary": summary,
        "message": summary,
        "connection_mode": mode,
        "policy": {"min_adopt_score": min_score, "ambiguity_margin": policy.get("ambiguity_margin")},
    }


def rescore_service_instance(node: Node, service: ServiceInstance) -> tuple[int, str]:
    """Re-score an inventory row against catalog (for cleanup policy)."""
    return score_container_against_catalog(
        service.container_name or "",
        service.image or "",
        service_key=service.service_key,
        networks=[],
        labels={},
        node_network=node.docker_network,
        policy=load_discovery_policy(),
    )
