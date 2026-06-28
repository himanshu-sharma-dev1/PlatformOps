from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import DeploymentJob, JobStatus


def _run_subprocess(
    job_id: int, command: str, cwd: Optional[Path], timeout: int, on_complete: Callable[[int, bool, str, str], None]
):
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        output_lines = []
        last_save_time = datetime.utcnow()

        with SessionLocal() as background_db:
            for line in iter(process.stdout.readline, ""):
                output_lines.append(line)

                # Save to DB every ~1 second to stream output
                now = datetime.utcnow()
                if (now - last_save_time).total_seconds() > 1.0:
                    bg_job = background_db.get(DeploymentJob, job_id)
                    if bg_job:
                        bg_job.output = "".join(output_lines)
                        background_db.commit()
                    last_save_time = now

        process.wait(timeout=timeout)
        on_complete(job_id, process.returncode == 0, "".join(output_lines), "")
    except Exception as exc:
        on_complete(job_id, False, "", str(exc))


def run_job_async(
    db: Session,
    job: DeploymentJob,
    *,
    cwd: Optional[Path] = None,
    timeout_seconds: int = 300,
    on_complete: Optional[Callable[[Session, DeploymentJob, bool], None]] = None,
) -> DeploymentJob:
    job.status = JobStatus.running.value
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    job_id = job.id

    def background_callback(j_id: int, ok: bool, out: str, err: str):
        with SessionLocal() as background_db:
            bg_job = background_db.get(DeploymentJob, j_id)
            if not bg_job:
                return
            bg_job.status = JobStatus.success.value if ok else JobStatus.failed.value
            bg_job.output = out
            bg_job.error = err
            bg_job.ended_at = datetime.utcnow()
            background_db.commit()

            if on_complete:
                try:
                    on_complete(background_db, bg_job, ok)
                    background_db.commit()
                except Exception as e:
                    bg_job.error = (bg_job.error or "") + f"\nCallback error: {e}"
                    background_db.commit()

    thread = threading.Thread(
        target=_run_subprocess, args=(job_id, job.command, cwd, timeout_seconds, background_callback), daemon=True
    )
    thread.start()

    return job
