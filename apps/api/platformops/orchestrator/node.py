from __future__ import annotations

import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs import create_job, finish_job
from ..models import (
    CapacityReport,
    DeploymentJob,
    JobStatus,
    Node,
    ServiceInstance,
)
from ..settings import settings
from ..tasks import run_job_async
from .common import (
    _ansible_base_command,
    detach_resource_references,
    record_event,
)


def validate_node(db: Session, node: Node) -> DeploymentJob:
    # Capture primitives before request session closes (Part A: no detached ORM in callback)
    node_id = int(node.id)
    node_name = str(node.name or f"node-{node_id}")
    command = f"{_ansible_base_command(node, 'validate_node.yml')} --extra-vars node_name={node_name}"
    job = create_job(db, action="validate-node", command=command, node_id=node_id)

    if settings.local_mode:
        return finish_job(
            db,
            job,
            ok=False,
            error=(
                "Node validation requires a real Ansible target. "
                "Set PLATFORMOPS_LOCAL_MODE=false and configure SSH inventory for the node."
            ),
        )

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_node = bg_db.get(Node, node_id)
        if not bg_node:
            return
        probe: dict[str, Any] = {}
        probe_error = ""
        if ok:
            try:
                probe = _probe_node_ssh_docker(bg_node)
                if probe.get("ssh_ok") is False:
                    probe_error = str(probe.get("detail") or "SSH connection failed")
                elif probe.get("docker_ok") is False:
                    probe_error = str(probe.get("detail") or "Docker engine is unavailable on the target")
            except Exception as exc:
                probe_error = str(exc)
        verified_ok = bool(ok and not probe_error)
        if not verified_ok:
            bg_job.status = JobStatus.failed.value
            bg_job.error = (bg_job.error or "") or probe_error or "Ansible node validation failed"
            bg_job.output = (bg_job.output or "") + (f"\nTarget probe: {probe_error}" if probe_error else "")
        bg_node.status = "healthy" if verified_ok else "unreachable"
        # Merge validation facts into existing operator facts (cpu/mem/gpu must survive)
        existing: dict[str, Any] = {}
        try:
            parsed = json.loads(bg_node.facts_json or "{}")
            if isinstance(parsed, dict):
                existing = parsed
        except Exception:
            existing = {}
        existing["checked_at"] = datetime.utcnow().isoformat() + "Z"
        existing["mode"] = "production-ansible"
        existing["last_validate_ok"] = verified_ok
        if verified_ok:
            try:
                if bg_job.output and '"msg":' in (bg_job.output or ""):
                    import re

                    match = re.search(r'"msg":\s*(\{[^}]+\})', bg_job.output)
                    if match:
                        parsed_msg = json.loads(match.group(1))
                        if isinstance(parsed_msg, dict):
                            existing.update(parsed_msg)
            except Exception:
                pass
        # Optional quick SSH/docker probe facts (never wipe operator keys)
        try:
            probe = _probe_node_ssh_docker(bg_node)
            if probe.get("ssh_ok") is not None:
                existing["ssh_probe"] = "ok" if probe.get("ssh_ok") else "fail"
            if probe.get("docker_ok") is not None:
                existing["docker"] = "present" if probe.get("docker_ok") else existing.get("docker", "unknown")
            if probe.get("detail"):
                existing["ssh_probe_detail"] = str(probe["detail"])[:300]
        except Exception:
            pass
        bg_node.facts_json = json.dumps(existing)
        bg_db.add(bg_node)
        record_event(
            bg_db,
            category="lifecycle",
            level="info" if verified_ok else "warning",
            message=f"Node validation {'succeeded' if verified_ok else 'failed'} for '{bg_node.name}'",
            node_id=node_id,
            metadata={"job_id": bg_job.id, "ok": verified_ok, "probe": probe, "error": probe_error},
        )

    return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)


def _is_local_docker_host(node: Node) -> bool:
    """Use connection_mode auto|local|ssh — never hardcode public IPs."""
    from .discovery import resolve_connection_mode

    return resolve_connection_mode(node) == "local"


def _probe_node_ssh_docker(
    node: Node,
    *,
    ephemeral_key: str | None = None,
    ephemeral_password: str | None = None,
) -> dict[str, Any]:
    """Real connectivity probe: local docker path or remote SSH. Never invents success."""
    from .remote import RemoteAuthError, run_ssh

    result: dict[str, Any] = {
        "ssh_ok": None,
        "docker_ok": None,
        "detail": "",
        "probed_at": datetime.utcnow().isoformat() + "Z",
        "connection_mode": "local" if _is_local_docker_host(node) else "ssh",
    }
    if _is_local_docker_host(node):
        # Local: use the configured Docker SDK engine (including DOCKER_HOST).
        try:
            from .docker_runtime import engine_version

            version = engine_version()
            result["ssh_ok"] = True  # control plane can reach local runtime
            result["docker_ok"] = True
            result["detail"] = version[:200] or "Docker engine reachable"
        except Exception as exc:
            result["ssh_ok"] = True
            result["docker_ok"] = False
            result["detail"] = str(exc)[:200]
        return result

    host = (node.host or "").strip()
    if not host:
        result["ssh_ok"] = False
        result["detail"] = "missing host"
        return result
    try:
        proc = run_ssh(
            node,
            "echo SSH_OK; docker info --format '{{.ServerVersion}}' 2>/dev/null || echo DOCKER_MISSING",
            ephemeral_key=ephemeral_key,
            ephemeral_password=ephemeral_password,
            timeout=8,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        result["ssh_ok"] = proc.returncode == 0 and "SSH_OK" in out
        result["docker_ok"] = "DOCKER_MISSING" not in out and proc.returncode == 0 and bool(out.strip())
        if result["ssh_ok"] and "DOCKER_MISSING" in out:
            result["docker_ok"] = False
        result["detail"] = out.strip()[:300]
        if proc.returncode != 0:
            result["ssh_ok"] = False
            result["detail"] = (proc.stderr or proc.stdout or "ssh failed").strip()[:300]
    except FileNotFoundError:
        result["ssh_ok"] = False
        result["detail"] = "ssh client not available on control plane"
    except RemoteAuthError as exc:
        result["ssh_ok"] = False
        result["docker_ok"] = False
        result["detail"] = str(exc)
    except Exception as exc:
        result["ssh_ok"] = False
        result["detail"] = str(exc)[:200]
    return result


def probe_node_connection(
    node: Node,
    *,
    ephemeral_key: str | None = None,
    ephemeral_password: str | None = None,
) -> dict[str, Any]:
    """Probe a node with request-scoped auth, returning no credential material."""

    return _probe_node_ssh_docker(
        node,
        ephemeral_key=ephemeral_key,
        ephemeral_password=ephemeral_password,
    )


def cleanup_node_inventory(
    db: Session,
    node_id: int,
    *,
    modes: list[str] | None = None,
    dry_run: bool = True,
    protect_orchestrator: bool = True,
) -> dict[str, Any]:
    """
    Clean inventory by re-scoring against catalog policy (no name denylists).

    modes:
      - weak: catalog re-score below min_adopt_score for claimed service_key
      - stale: docker inspect not_found
      - duplicates: keep best row per service_key when multi_instance is false
      - all: weak+stale+duplicates
    Legacy modes noise/foreign map to weak.
    """
    from .discovery import (
        _catalog_allows_multi_instance,
        load_discovery_policy,
        score_container_against_catalog,
    )
    from .service.impl import _docker_inspect_for_node
    from ..catalog import get_service_contract

    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    selected = {m.strip().lower() for m in (modes or ["all"]) if m and str(m).strip()}
    if "noise" in selected or "foreign" in selected:
        selected.add("weak")
        selected.discard("noise")
        selected.discard("foreign")
    if "all" in selected or not selected:
        selected = {"weak", "stale", "duplicates"}

    policy = load_discovery_policy()
    min_score = int(policy.get("min_adopt_score", 30))

    services = list(
        db.scalars(
            select(ServiceInstance).where(
                ServiceInstance.node_id == node_id,
                ServiceInstance.status != "deleted",
            )
        ).all()
    )

    candidates: dict[int, dict[str, Any]] = {}

    def mark(svc: ServiceInstance, reason: str, extra: dict | None = None) -> None:
        contract = get_service_contract(svc.service_key) or {}
        meta = contract.get("discovery") if isinstance(contract.get("discovery"), dict) else {}
        if protect_orchestrator and meta.get("protected"):
            return
        entry = candidates.setdefault(
            svc.id,
            {
                "service_id": svc.id,
                "external_id": svc.external_id,
                "service_key": svc.service_key,
                "name": svc.name,
                "container_name": svc.container_name,
                "status": svc.status,
                "reasons": [],
            },
        )
        if reason not in entry["reasons"]:
            entry["reasons"].append(reason)
        if extra:
            entry.update(extra)

    if "weak" in selected:
        for svc in services:
            score, basis = score_container_against_catalog(
                svc.container_name or "",
                svc.image or "",
                service_key=svc.service_key,
                networks=[],
                labels={},
                node_network=node.docker_network,
                policy=policy,
            )
            key_min = min_score
            meta = (get_service_contract(svc.service_key) or {}).get("discovery") or {}
            if isinstance(meta, dict) and meta.get("min_score") is not None:
                key_min = int(meta["min_score"])
            if score < key_min:
                mark(svc, "weak_score", {"score": score, "match_basis": basis, "min_score": key_min})

    if "stale" in selected:
        for svc in services:
            _inspect, err, _src = _docker_inspect_for_node(node, svc.container_name or "")
            if err == "not_found":
                mark(svc, "stale_not_found")

    if "duplicates" in selected:
        by_key: dict[str, list[ServiceInstance]] = {}
        for svc in services:
            by_key.setdefault(svc.service_key, []).append(svc)
        for key, group in by_key.items():
            if len(group) <= 1:
                continue
            if _catalog_allows_multi_instance(key):
                continue

            def rank(s: ServiceInstance) -> tuple:
                sc, _ = score_container_against_catalog(
                    s.container_name or "",
                    s.image or "",
                    service_key=s.service_key,
                    networks=[],
                    labels={},
                    node_network=node.docker_network,
                    policy=policy,
                )
                running = 0 if (s.status or "").lower() in {"running", "healthy"} else 1
                return (-sc, running, s.id)

            ordered = sorted(group, key=rank)
            for drop in ordered[1:]:
                mark(drop, f"duplicate_of_{ordered[0].external_id or ordered[0].id}")

    removed: list[dict[str, Any]] = []
    if not dry_run:
        detach_resource_references(db, service_ids=[int(sid) for sid in candidates])
        for sid, meta in list(candidates.items()):
            svc = db.get(ServiceInstance, sid)
            if not svc:
                continue
            db.delete(svc)
            removed.append(meta)
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Inventory cleanup removed '{meta.get('name')}' ({','.join(meta.get('reasons') or [])})",
                node_id=node_id,
                metadata=meta,
            )
        db.commit()
    else:
        removed = list(candidates.values())

    return {
        "node_id": node_id,
        "dry_run": dry_run,
        "modes": sorted(selected),
        "candidate_count": len(candidates),
        "removed_count": 0 if dry_run else len(removed),
        "items": removed,
        "summary": (
            f"{'Would remove' if dry_run else 'Removed'} {len(removed)} inventory row(s) "
            f"on node {node.name} (modes={','.join(sorted(selected))}, min_score={min_score})"
        ),
        "policy": {"min_adopt_score": min_score},
    }



def get_node_job_history(db: Session, node_id: int, *, limit: int = 12) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")
    jobs = list(
        db.scalars(
            select(DeploymentJob)
            .where(DeploymentJob.node_id == node_id)
            .order_by(DeploymentJob.created_at.desc())
            .limit(limit)
        ).all()
    )
    all_jobs = list(db.scalars(select(DeploymentJob).where(DeploymentJob.node_id == node_id)).all())
    service_map = {
        service.id: service
        for service in db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node_id)).all()
    }
    deployment_jobs = 0
    config_jobs = 0
    validation_jobs = 0
    failed_jobs = 0
    for job in all_jobs:
        if job.status == JobStatus.failed.value:
            failed_jobs += 1
        if "config" in job.action:
            config_jobs += 1
        elif "validate" in job.action:
            validation_jobs += 1
        else:
            deployment_jobs += 1
    items: list[dict[str, Any]] = []
    for job in jobs:
        service = service_map.get(job.service_id) if job.service_id else None
        items.append(
            {
                "id": job.id,
                "action": job.action,
                "status": job.status,
                "command": job.command,
                "output": job.output,
                "error": job.error,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "ended_at": job.ended_at,
                "service_id": service.id if service else None,
                "service_name": service.name if service else None,
                "service_key": service.service_key if service else None,
            }
        )
    return {
        "node_id": node.id,
        "node_name": node.name,
        "total_jobs": len(all_jobs),
        "deployment_jobs": deployment_jobs,
        "config_jobs": config_jobs,
        "validation_jobs": validation_jobs,
        "failed_jobs": failed_jobs,
        "items": items,
    }


def get_node_summary(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    kind_counts = {"app": 0, "infrastructure": 0, "helper": 0}
    services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node_id)).all()
    service_count = 0
    for s in services:
        if s.status == "deleted":
            continue
        service_count += 1
        kind_counts[s.kind] = kind_counts.get(s.kind, 0) + 1

    cap_report = db.scalar(
        select(CapacityReport).where(CapacityReport.node_id == node_id).order_by(CapacityReport.created_at.desc())
    )
    capacity_status = cap_report.status if cap_report else "ok"

    return {
        "node_id": node_id,
        "service_count": service_count,
        "kind_counts": kind_counts,
        "docker_network": node.docker_network,
        "volume_root": node.volume_root,
        "capacity_status": capacity_status,
    }


def get_node_connection_report(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    facts: dict[str, Any] = {}
    facts_error: str | None = None
    raw_facts = (node.facts_json or "").strip()
    if raw_facts:
        try:
            parsed = json.loads(raw_facts)
            if isinstance(parsed, dict):
                facts = parsed
            else:
                facts_error = "Node facts payload is not a JSON object."
        except json.JSONDecodeError:
            facts_error = "Node facts payload is not valid JSON."

    last_validate_job = db.scalar(
        select(DeploymentJob)
        .where(
            DeploymentJob.node_id == node_id,
            DeploymentJob.action == "validate-node",
        )
        .order_by(DeploymentJob.created_at.desc())
    )
    validation_job = None
    if last_validate_job:
        validation_job = {
            "id": last_validate_job.id,
            "status": last_validate_job.status,
            "created_at": last_validate_job.created_at.isoformat() if last_validate_job.created_at else "",
            "ended_at": last_validate_job.ended_at.isoformat() if last_validate_job.ended_at else None,
            "error": (last_validate_job.error or "").strip(),
            "output": (last_validate_job.output or "").strip(),
            "command": last_validate_job.command,
        }

    checked_at_value = facts.get("checked_at") if isinstance(facts.get("checked_at"), str) else None
    if checked_at_value:
        last_checked_at = checked_at_value
    elif last_validate_job and last_validate_job.ended_at:
        last_checked_at = last_validate_job.ended_at.isoformat()
    else:
        last_checked_at = None

    # Live probe (best-effort; does not invent success)
    probe = _probe_node_ssh_docker(node)

    recommendations: list[str] = []
    if node.environment != "local" and not (
        (node.ssh_key_path or "").strip() or (getattr(node, "ssh_secret_ref", "") or "").strip()
    ) and not _is_local_docker_host(node):
        recommendations.append("Configure an SSH secret reference before validating remote connectivity.")
    if node.environment != "local" and node.host in {"localhost", "127.0.0.1"} and not _is_local_docker_host(node):
        recommendations.append("Set a remote host/IP for this non-local node.")
    if probe.get("ssh_ok") is False:
        recommendations.append("Live SSH/runtime probe failed. Check host, user, PEM path, and security groups.")
    if probe.get("ssh_ok") and probe.get("docker_ok") is False:
        recommendations.append("SSH reachable but Docker is not available on the target (or docker CLI missing).")
    if not facts and not probe.get("ssh_ok"):
        recommendations.append("Run Validate Node to collect host facts and confirm connectivity.")
    if node.status in {"unknown", "unreachable"} and not probe.get("ssh_ok"):
        recommendations.append("Node is not healthy. Re-run Validate Node and review validation output.")
    if last_validate_job and last_validate_job.status in {"failed", "cancelled"} and not probe.get("ssh_ok"):
        recommendations.append("Latest validation failed. Inspect the validation command output and SSH settings.")
    if probe.get("ssh_ok") and probe.get("docker_ok") and not recommendations:
        recommendations.append("Runtime probe OK. You can proceed with discover, deploy, and live status.")

    if last_validate_job and last_validate_job.status == "success":
        connection_state = "validated"
    elif last_validate_job and last_validate_job.status in {"running", "queued"}:
        connection_state = "validating"
    elif node.status == "unreachable" and not probe.get("ssh_ok"):
        connection_state = "unreachable"
    elif probe.get("ssh_ok") and probe.get("docker_ok"):
        connection_state = "ssh-ok"
    elif probe.get("ssh_ok"):
        connection_state = "ssh-ok-no-docker"
    elif facts:
        connection_state = "facts-only"
    else:
        connection_state = "not-validated"

    return {
        "node_id": node.id,
        "node_name": node.name,
        "host": node.host,
        "ssh_user": node.ssh_user,
        "ssh_key_path": node.ssh_key_path,
        "ssh_secret_ref": getattr(node, "ssh_secret_ref", "") or "",
        "host_key_fingerprint": getattr(node, "host_key_fingerprint", "") or "",
        "known_hosts_ref": getattr(node, "known_hosts_ref", "") or "",
        "environment": node.environment,
        "status": node.status,
        "connection_state": connection_state,
        "facts_available": bool(facts),
        "facts": facts,
        "facts_error": facts_error,
        "last_checked_at": last_checked_at or probe.get("probed_at"),
        "validation_job": validation_job,
        "recommendations": recommendations,
        "live_probe": probe,
    }


def get_node_onboarding_report(db: Session, node_id: int) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    connection = get_node_connection_report(db, node_id)
    facts = connection.get("facts", {}) if isinstance(connection.get("facts"), dict) else {}
    now_iso = datetime.utcnow().isoformat() + "Z"
    checks: list[dict[str, str]] = []

    def push_check(
        check_id: str, title: str, status: str, detail: str, remediation: str, severity: str = "low"
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "title": title,
                "status": status,
                "severity": severity,
                "detail": detail,
                "remediation": remediation,
            }
        )

    is_local = node.environment == "local"
    remote_host_ok = node.host not in {"localhost", "127.0.0.1"}

    push_check(
        "environment-profile",
        "Environment profile",
        "pass" if node.environment in {"local", "aws"} else "warn",
        f"Node environment is '{node.environment}'.",
        "Use 'aws' for remote EC2 nodes and 'local' for local simulation.",
        "low",
    )
    push_check(
        "host-config",
        "Target host",
        "pass" if (is_local or remote_host_ok) else "fail",
        f"Configured host: {node.host}",
        "Set node host to a reachable public/private IP or DNS name for remote nodes.",
        "high",
    )
    push_check(
        "ssh-user",
        "SSH user",
        "pass" if (node.ssh_user or "").strip() else "fail",
        f"SSH user: {(node.ssh_user or '').strip() or '(missing)'}",
        "Provide a valid SSH user (for AWS typically 'ubuntu' or ec2-user).",
        "high",
    )
    push_check(
        "ssh-key",
        "SSH private key",
        "pass"
        if (is_local or (node.ssh_key_path or "").strip() or (getattr(node, "ssh_secret_ref", "") or "").strip())
        else "fail",
        "SSH secret reference configured."
        if ((node.ssh_key_path or "").strip() or (getattr(node, "ssh_secret_ref", "") or "").strip())
        else "No SSH secret reference configured.",
        "Attach an operator-managed SSH secret reference for remote nodes.",
        "high" if not is_local else "low",
    )

    connection_state = connection.get("connection_state", "not-validated")
    validation_status = (
        connection.get("validation_job", {}).get("status")
        if isinstance(connection.get("validation_job"), dict)
        else None
    )
    if connection_state == "validated":
        validation_state = "pass"
    elif connection_state in {"validating", "facts-only"}:
        validation_state = "warn"
    else:
        validation_state = "fail"
    push_check(
        "connection-validation",
        "Connection validation",
        validation_state,
        f"Connection state: {connection_state}" + (f" · job={validation_status}" if validation_status else ""),
        "Run Validate Node and inspect SSH/network settings if validation fails.",
        "high" if validation_state == "fail" else "medium",
    )

    docker_fact = str(facts.get("docker", "")).strip().lower()
    docker_ready = docker_fact in {"expected", "present", "ok", "ready"} or connection_state == "validated"
    push_check(
        "docker-runtime",
        "Docker runtime",
        "pass" if docker_ready else "warn",
        f"Docker fact: {facts.get('docker', 'unknown')}",
        "Ensure Docker daemon is installed/running on target node before deployments.",
        "medium",
    )
    ansible_fact = str(facts.get("ansible", "")).strip().lower()
    ansible_ready = ansible_fact in {"ok", "command-recorded", "present", "ready"} or connection_state == "validated"
    push_check(
        "ansible-readiness",
        "Ansible readiness",
        "pass" if ansible_ready else "warn",
        f"Ansible fact: {facts.get('ansible', 'unknown')}",
        "Verify Ansible execution path and node credentials for orchestration playbooks.",
        "medium",
    )
    push_check(
        "volume-root",
        "Volume root path",
        "pass" if (node.volume_root or "").startswith("/") else "fail",
        f"Volume root: {node.volume_root}",
        "Use an absolute writable path (for example /platformops or /tmp/platformops).",
        "high",
    )
    push_check(
        "docker-network",
        "Docker network name",
        "pass" if bool((node.docker_network or "").strip()) else "fail",
        f"Docker network: {(node.docker_network or '').strip() or '(missing)'}",
        "Set a non-empty docker network identifier for service communication.",
        "high",
    )

    pass_count = sum(1 for item in checks if item["status"] == "pass")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    if fail_count > 0:
        overall_status = "fail"
    elif warn_count > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    next_actions = []
    for item in checks:
        if item["status"] in {"fail", "warn"} and item["remediation"] not in next_actions:
            next_actions.append(item["remediation"])
    for item in connection.get("recommendations", []):
        if item not in next_actions:
            next_actions.append(item)

    suggested_actions: list[str] = []
    needs_remote_profile = node.environment != "local" and (
        not remote_host_ok
        or not ((node.ssh_key_path or "").strip() or (getattr(node, "ssh_secret_ref", "") or "").strip())
        or not (node.ssh_user or "").strip()
    )
    if needs_remote_profile:
        suggested_actions.append(
            "apply-aws-gpu-preset" if "gpu" in (node.docker_network or "").lower() else "apply-aws-general-preset"
        )
    elif node.environment == "local" and (node.host.startswith("ec2-") or "aws" in (node.docker_network or "").lower()):
        suggested_actions.append("apply-local-preset")

    if connection_state != "validated" or node.status in {"unknown", "unreachable"}:
        suggested_actions.append("run-validation")

    if not suggested_actions:
        suggested_actions.append("run-validation")

    return {
        "node_id": node.id,
        "node_name": node.name,
        "environment": node.environment,
        "overall_status": overall_status,
        "checked_at": now_iso,
        "connection_state": connection_state,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "next_actions": next_actions[:8],
        "suggested_actions": suggested_actions,
    }


def remediate_node_onboarding(db: Session, node_id: int, *, action: str) -> dict[str, Any]:
    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    normalized = (action or "").strip().lower()
    if not normalized:
        raise ValueError("Remediation action is required.")

    updated_fields: dict[str, str] = {}
    validation_job: dict[str, Any] | None = None

    if normalized in {"apply-aws-general-preset", "apply-aws-gpu-preset", "apply-local-preset"}:
        before = {
            "environment": node.environment,
            "ssh_user": node.ssh_user,
            "host": node.host,
            "volume_root": node.volume_root,
            "docker_network": node.docker_network,
        }
        if normalized == "apply-aws-general-preset":
            node.environment = "aws"
            node.ssh_user = "ubuntu"
            if node.host in {"localhost", "127.0.0.1", ""}:
                node.host = "ec2-public-host"
            if node.volume_root.startswith("/tmp/"):
                node.volume_root = "/platformops"
            if node.docker_network == "platformops-net":
                node.docker_network = "platformops-net-aws"
        elif normalized == "apply-aws-gpu-preset":
            node.environment = "aws"
            node.ssh_user = "ubuntu"
            if node.host in {"localhost", "127.0.0.1", ""}:
                node.host = "ec2-gpu-host"
            if node.volume_root.startswith("/tmp/"):
                node.volume_root = "/platformops-gpu"
            if node.docker_network == "platformops-net":
                node.docker_network = "platformops-net-gpu"
        else:
            node.environment = "local"
            node.ssh_user = "ubuntu"
            if node.host.startswith("ec2-") or not node.host:
                node.host = "localhost"
            if node.volume_root.startswith("/platformops"):
                node.volume_root = "/tmp/platformops"
            if "aws" in node.docker_network or "gpu" in node.docker_network:
                node.docker_network = "platformops-net"

        for key, previous in before.items():
            current = getattr(node, key)
            if current != previous:
                updated_fields[key] = str(current)
        db.commit()
        db.refresh(node)
        record_event(
            db,
            category="lifecycle",
            level="info",
            message=f"Applied onboarding remediation '{normalized}' to node '{node.name}'",
            node_id=node.id,
            metadata={"action": normalized, "updated_fields": updated_fields},
        )
        message = (
            f"Applied {normalized}." if updated_fields else f"{normalized} already aligned; no node fields changed."
        )
        return {
            "node_id": node.id,
            "action": normalized,
            "ok": True,
            "message": message,
            "updated_fields": updated_fields,
            "validation_job": None,
        }

    if normalized == "run-validation":
        job = validate_node(db, node)
        validation_job = {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "error": (job.error or "").strip(),
            "output": (job.output or "").strip(),
            "command": job.command,
        }
        return {
            "node_id": node.id,
            "action": normalized,
            "ok": job.status == "success",
            "message": f"Validation job {job.id} finished with status {job.status}.",
            "updated_fields": {},
            "validation_job": validation_job,
        }

    raise ValueError(f"Unsupported remediation action '{action}'.")


def launch_node_vm(db: Session, node: Node, ami_id: str, instance_type: str, region: str) -> DeploymentJob:
    tf_dir = Path(settings.project_root) / "ops" / "terraform" / "aws"
    command = f"terraform init && terraform apply -auto-approve -var ami_id={ami_id} -var instance_type={instance_type} -var aws_region={region}"
    job = create_job(db, action="launch-vm", command=command, node_id=node.id)

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_node = bg_db.get(Node, node.id)
        if bg_node:
            if ok:
                bg_node.status = "healthy"
                bg_node.provider = "aws"
                bg_node.region = region
                bg_node.cloud_image_id = ami_id
                facts = {
                    "provider": "aws",
                    "instance_type": instance_type,
                    "region": region,
                    "ami_id": ami_id,
                    "vcpus": 2,
                    "memory_gb": 8,
                    "storage_gb": 20,
                    "gpu_exporter": "disabled",
                    "provisioned_at": datetime.utcnow().isoformat() + "Z",
                }
                bg_node.facts_json = json.dumps(facts)
            else:
                bg_node.status = "unreachable"
            bg_db.commit()

    if settings.local_mode:
        return finish_job(
            db,
            job,
            ok=False,
            output="",
            error="VM launch requires real Terraform (set PLATFORMOPS_LOCAL_MODE=false and configure ops/terraform/aws).",
        )

    if not tf_dir.exists():
        return finish_job(
            db,
            job,
            ok=False,
            output="",
            error=f"Terraform directory not found: {tf_dir}",
        )

    return run_job_async(db, job, cwd=str(tf_dir), on_complete=on_complete)


def teardown_node_vm(db: Session, node: Node) -> DeploymentJob:
    tf_dir = Path(settings.project_root) / "ops" / "terraform" / "aws"
    command = "terraform destroy -auto-approve"
    job = create_job(db, action="teardown-vm", command=command, node_id=node.id)

    def on_complete(bg_db: Session, bg_job: DeploymentJob, ok: bool):
        bg_node = bg_db.get(Node, node.id)
        if bg_node:
            if ok:
                service_ids = list(
                    bg_db.scalars(
                        select(ServiceInstance.id).where(ServiceInstance.node_id == bg_node.id)
                    ).all()
                )
                detach_resource_references(
                    bg_db,
                    service_ids=service_ids,
                    node_ids=[bg_node.id],
                )
                bg_db.delete(bg_node)
            else:
                bg_node.status = "error"
            bg_db.commit()

    if settings.local_mode:
        return finish_job(
            db,
            job,
            ok=False,
            output="",
            error="VM teardown requires real Terraform (set PLATFORMOPS_LOCAL_MODE=false).",
        )

    if not tf_dir.exists():
        return finish_job(
            db,
            job,
            ok=False,
            output="",
            error=f"Terraform directory not found: {tf_dir}",
        )

    return run_job_async(db, job, cwd=str(tf_dir), on_complete=on_complete)
