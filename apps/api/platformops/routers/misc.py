from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["misc"])

@router.get(
    "/api/services/{service_id}/diagnostics/archives/{archive_id}/view",
    response_model=LogArchiveViewOut,
)
def diagnostics_archive_view(
    service_id: int,
    archive_id: int,
    max_lines: int = 300,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    result = view_log_archive(db, service, archive_id, max_lines=max_lines)
    if result.get("error"):
        detail = str(result["error"])
        status = 404 if detail == "Archive not found" or "not available on disk" in detail else 403 if "not allowed" in detail else 502
        raise HTTPException(status_code=status, detail=detail)
    return result

