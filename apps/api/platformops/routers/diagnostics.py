from __future__ import annotations

from datetime import datetime, timedelta

import requests
from fastapi import APIRouter

from . import ops_common as _ops_common
from ..query import escape_query_regex_literal
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["diagnostics"])

@router.get("/api/diagnostics/ingestion-stats", response_model=IngestionStatsOut)
def diagnostics_ingestion_stats(db: Session = Depends(get_db)) -> dict:
    return get_ingestion_stats(db)


@router.get("/api/diagnostics/logs")
def get_diagnostics_logs(service: str, start: str = None, end: str = None, limit: int = 100):
    try:
        if not start:
            start = str(int((datetime.now() - timedelta(hours=1)).timestamp() * 1e9))
        if not end:
            end = str(int(datetime.now().timestamp() * 1e9))

        query = f'{{container_name=~".*{escape_query_regex_literal(service)}.*"}}'
        response = requests.get(
            f"{settings.loki_base_url.rstrip('/')}/loki/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "limit": max(1, min(limit, 5000))},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}
