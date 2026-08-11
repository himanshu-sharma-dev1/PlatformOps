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

try:  # Docker SDK is present in the runtime image, but keep status non-fatal if it is not.
    import docker  # type: ignore  # noqa: E402
except ImportError:  # pragma: no cover - exercised only by incomplete local installs
    docker = None  # type: ignore[assignment]


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
    """Return real status for the managed Compose project.

    The control-plane image talks to its configured Docker engine through the
    Python SDK.  The Docker CLI/Compose plugin is intentionally not required
    for this read-only page, and an unavailable engine is represented as an
    error payload instead of becoming an API 500.
    """

    if docker is None:
        return {
            "containers": [],
            "available": False,
            "error": "Docker SDK is not installed in the API runtime.",
        }

    client = None
    try:
        client = docker.from_env()
        raw_containers = client.api.containers(
            all=True,
            filters={"label": "com.docker.compose.project=platformops-obs"},
        )
        containers = []
        for item in raw_containers:
            labels = item.get("Labels") or {}
            names = item.get("Names") or []
            name = str(names[0]).lstrip("/") if names else str(item.get("Id") or "")[:12]
            containers.append(
                {
                    "ID": item.get("Id", ""),
                    "Name": name,
                    "Service": labels.get("com.docker.compose.service", ""),
                    "Project": labels.get("com.docker.compose.project", "platformops-obs"),
                    "State": item.get("State", ""),
                    "Status": item.get("Status", ""),
                }
            )
        containers.sort(key=lambda item: item["Name"])
        return {"containers": containers, "available": True, "error": None}
    except Exception as exc:
        return {"containers": [], "available": False, "error": str(exc)}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


@router.post("/api/nodes/{node_id}/observability/deploy", response_model=JobOut)
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


