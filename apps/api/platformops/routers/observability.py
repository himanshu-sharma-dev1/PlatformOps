from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["observability"])

@router.get("/api/observability/pipeline", response_model=ObservabilityPipelineOut)
def observability_pipeline(db: Session = Depends(get_db)) -> dict:
    return observability_pipeline_report(db)


import subprocess  # noqa: E402


@router.post("/api/observability/deploy")
def deploy_observability():
    result = subprocess.run(
        ["ansible-playbook", "-c", "local", "ops/ansible/playbooks/deploy_observability.yml"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    return {"success": result.returncode == 0, "output": result.stdout + result.stderr}


@router.post("/api/observability/teardown")
def teardown_observability():
    result = subprocess.run(
        ["ansible-playbook", "-c", "local", "ops/ansible/playbooks/teardown_observability.yml"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    return {"success": result.returncode == 0, "output": result.stdout + result.stderr}


@router.get("/api/observability/status")
def get_observability_status():
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "ops/compose/docker-compose.observability.yml",
            "-p",
            "platformops-obs",
            "ps",
            "--format",
            "json",
        ],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    containers = []
    for line in result.stdout.strip().splitlines():
        if line:
            containers.append(json.loads(line))
    return {"containers": containers}


import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


@router.post("/api/observability/deploy", response_model=JobOut)
def deploy_observability_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    node = db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    try:
        job = deploy_observability_stack(db, node)
        return {
            "id": job.id,
            "action": job.action,
            "status": job.status,
            "command": job.command,
            "output": job.output or "",
            "error": job.error or "",
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



