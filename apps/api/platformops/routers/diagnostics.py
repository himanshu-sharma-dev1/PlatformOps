from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["diagnostics"])

@router.get("/api/diagnostics/ingestion-stats", response_model=IngestionStatsOut)
def diagnostics_ingestion_stats() -> dict:
    return get_ingestion_stats()


@router.get("/api/diagnostics/logs")
def get_diagnostics_logs(service: str, start: str = None, end: str = None, limit: int = 100):
    try:
        if not start:
            start = str(int((datetime.now() - timedelta(hours=1)).timestamp() * 1e9))
        if not end:
            end = str(int(datetime.now().timestamp() * 1e9))

        query = f'{{container_name=~".*{service}.*"}}'
        params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "limit": limit})
        url = f"http://platformops-obs-loki:3100/loki/api/v1/query_range?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        return {"error": str(e)}


