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
        bg_node.status = "healthy" if ok else "unreachable"
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
        existing["last_validate_ok"] = bool(ok)
        if ok:
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
            level="info" if ok else "warning",
            message=f"Node validation {'succeeded' if ok else 'failed'} for '{bg_node.name}'",
            node_id=node_id,
            metadata={"job_id": bg_job.id, "ok": ok},
        )

    return run_job_async(db, job, cwd=settings.project_root, on_complete=on_complete)


def _is_local_docker_host(node: Node) -> bool:
    host = (node.host or "").strip().lower()
    return (
        settings.local_mode
        or (node.environment or "").lower() == "local"
        or host in {"localhost", "127.0.0.1", "0.0.0.0", "", "65.2.63.24"}
    )


def _probe_node_ssh_docker(node: Node) -> dict[str, Any]:
    """Real connectivity probe: local docker path or remote SSH. Never invents success."""
    import subprocess

    result: dict[str, Any] = {
        "ssh_ok": None,
        "docker_ok": None,
        "detail": "",
        "probed_at": datetime.utcnow().isoformat() + "Z",
    }
    if _is_local_docker_host(node):
        # Local: TCP/SSH optional; docker CLI is the real gate for live status
        try:
            proc = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            result["ssh_ok"] = True  # control plane can reach local runtime
            result["docker_ok"] = proc.returncode == 0
            result["detail"] = (proc.stdout or proc.stderr or "").strip()[:200]
            if proc.returncode != 0:
                result["detail"] = (proc.stderr or proc.stdout or "docker info failed").strip()[:200]
        except FileNotFoundError:
            result["ssh_ok"] = True
            result["docker_ok"] = False
            result["detail"] = "docker CLI not available on control plane"
        except Exception as exc:
            result["ssh_ok"] = False
            result["docker_ok"] = False
            result["detail"] = str(exc)[:200]
        return result

    host = (node.host or "").strip()
    user = (node.ssh_user or "ubuntu").strip()
    key = (node.ssh_key_path or "").strip()
    if not host:
        result["ssh_ok"] = False
        result["detail"] = "missing host"
        return result
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=8",
    ]
    if key:
        cmd.extend(["-i", key])
    cmd.append(f"{user}@{host}")
    cmd.append("echo SSH_OK; docker info --format '{{.ServerVersion}}' 2>/dev/null || echo DOCKER_MISSING")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
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
    except Exception as exc:
        result["ssh_ok"] = False
        result["detail"] = str(exc)[:200]
    return result


def cleanup_node_inventory(
    db: Session,
    node_id: int,
    *,
    modes: list[str] | None = None,
    dry_run: bool = True,
    protect_orchestrator: bool = True,
) -> dict[str, Any]:
    """
    Clean noisy / wrong discover adoptions from DB only (does not stop containers).

    modes:
      - noise: control-plane / cPlatform stack containers (skip markers)
      - foreign: glitchtip/signoz/cplatform/foreign SERV* names
      - stale: docker inspect not_found / unknown with no live container
      - duplicates: keep one best row per service_key (prefer running, lower id)
      - all: noise+foreign+stale+duplicates
    """
    from .discovery import SKIP_NAME_MARKERS
    from .service.impl import _docker_inspect_for_node

    node = db.get(Node, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    selected = {m.strip().lower() for m in (modes or ["all"]) if m and str(m).strip()}
    if "all" in selected or not selected:
        selected = {"noise", "foreign", "stale", "duplicates"}

    services = list(
        db.scalars(
            select(ServiceInstance).where(
                ServiceInstance.node_id == node_id,
                ServiceInstance.status != "deleted",
            )
        ).all()
    )

    # Container-name oriented (do NOT match product image registry iktaraai/*)
    foreign_name_markers = (
        "cplatform_",
        "cplatform-",
        "signoz",
        "glitchtip",
        "serv1025",
        "serv1029",
        "serv1003",
        "serv1004",
        "serv1026",
        "serv1028",
        "serv1031",
    )
    # Never treat platform product keys as foreign noise
    protect_keys = {
        "ai-orchestrator",
        "AIOrchestrator",
        "dtrain-controller",
        "dtrain-worker",
        "dtrain-tracker",
    }
    candidates: dict[int, dict[str, Any]] = {}

    def mark(svc: ServiceInstance, reason: str) -> None:
        if protect_orchestrator and svc.service_key in protect_keys:
            return
        if svc.service_key in protect_keys and reason.startswith("foreign"):
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

    # noise / foreign by container name only (not image registry strings)
    for svc in services:
        cname = (svc.container_name or "").lower()
        sname = (svc.name or "").lower()
        name_hay = f"{cname} {sname}"
        if "noise" in selected and any(m in cname for m in SKIP_NAME_MARKERS):
            mark(svc, "noise")
        if "foreign" in selected and any(m in name_hay for m in foreign_name_markers):
            mark(svc, "foreign")

    # stale via live inspect
    if "stale" in selected:
        for svc in services:
            if svc.id in candidates:
                continue
            _inspect, err, _src = _docker_inspect_for_node(node, svc.container_name or "")
            if err == "not_found" or (svc.status or "").lower() in {"not_found", "unknown"} and err:
                if err == "not_found":
                    mark(svc, "stale_not_found")

    # duplicates: more than one service_key
    if "duplicates" in selected:
        by_key: dict[str, list[ServiceInstance]] = {}
        for svc in services:
            by_key.setdefault(svc.service_key, []).append(svc)
        for key, group in by_key.items():
            if len(group) <= 1:
                continue
            # Prefer running + lowest id as keeper
            def rank(s: ServiceInstance) -> tuple:
                running = 0 if (s.status or "").lower() in {"running", "healthy"} else 1
                return (running, s.id)

            ordered = sorted(group, key=rank)
            for drop in ordered[1:]:
                mark(drop, f"duplicate_of_{ordered[0].external_id or ordered[0].id}")

    removed: list[dict[str, Any]] = []
    if not dry_run:
        for sid, meta in list(candidates.items()):
            svc = db.get(ServiceInstance, sid)
            if not svc:
                continue
            # Inventory-only remove: mark deleted + detach from active lists
            svc.status = "deleted"
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
            f"on node {node.name} (modes={','.join(sorted(selected))})"
        ),
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
    if node.environment != "local" and not (node.ssh_key_path or "").strip() and not _is_local_docker_host(node):
        recommendations.append("Configure an SSH private key path before validating remote connectivity.")
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
        "pass" if (is_local or (node.ssh_key_path or "").strip()) else "fail",
        "SSH key path configured." if (node.ssh_key_path or "").strip() else "No SSH key path configured.",
        "Attach an SSH key path for remote nodes (for example ~/.ssh/<key>.pem).",
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
        not remote_host_ok or not (node.ssh_key_path or "").strip() or not (node.ssh_user or "").strip()
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
