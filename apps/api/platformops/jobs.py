from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .models import DeploymentJob, JobStatus


def create_job(
    db: Session,
    *,
    action: str,
    command: str,
    service_id: int | None = None,
    node_id: int | None = None,
) -> DeploymentJob:
    job = DeploymentJob(
        action=action,
        command=command,
        service_id=service_id,
        node_id=node_id,
        status=JobStatus.queued.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def finish_job(db: Session, job: DeploymentJob, *, ok: bool, output: str = "", error: str = "") -> DeploymentJob:
    job.status = JobStatus.success.value if ok else JobStatus.failed.value
    job.output = output
    job.error = error
    job.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def run_local_job(
    db: Session, job: DeploymentJob, *, cwd: Path | None = None, timeout_seconds: int = 60
) -> DeploymentJob:
    job.status = JobStatus.running.value
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    try:
        result = subprocess.run(
            job.command,
            cwd=str(cwd) if cwd else None,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return finish_job(db, job, ok=False, error=str(exc))

    return finish_job(
        db,
        job,
        ok=result.returncode == 0,
        output=result.stdout,
        error=result.stderr,
    )
