from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Node
from ..orchestrator import (
    deploy_observability_stack,
    observability_pipeline_report,
    observability_status_report,
    record_event,
)
from ..schemas import JobOut, ObservabilityPipelineOut, ObservabilityStatusOut

router = APIRouter(tags=["observability"])

@router.get("/api/observability/pipeline", response_model=ObservabilityPipelineOut)
def observability_pipeline(db: Session = Depends(get_db)) -> dict:
    return observability_pipeline_report(db)


@router.get("/api/observability/status", response_model=ObservabilityStatusOut)
def get_observability_status(
    service_id: int = Query(..., gt=0),
    marker: str = Query("", max_length=240),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return observability_status_report(db, service_id=service_id, marker=marker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Observability probe failed: {str(exc)[:300]}") from exc


@router.post("/api/nodes/{node_id}/observability/deploy", response_model=JobOut)
def deploy_observability_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    node = db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    try:
        job = deploy_observability_stack(db, node)
        payload = {
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
        record_event(db, category="observability_native", level="info", message="PlatformOps-native node observability deploy", node_id=node_id, metadata={"action": "deploy_node_observability", "job_id": job.id, "classification": "platformops_native_non_parity"})
        return payload
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
