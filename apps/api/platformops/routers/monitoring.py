from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["monitoring"])

@router.get("/api/metrics/node")
def get_node_metrics():
    try:
        queries = {
            "cpu": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "memory": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100",
            "disk": '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100',
        }
        results = {}
        for key, q in queries.items():
            params = urllib.parse.urlencode({"query": q})
            url = f"http://platformops-obs-prometheus:9090/api/v1/query?{params}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                if data["data"]["result"]:
                    results[key] = data["data"]["result"][0]["value"][1]
                else:
                    results[key] = 0
        return results
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/metrics/processes")
def get_process_metrics():
    try:
        q = "topk(10, rate(namedprocess_namegroup_cpu_seconds_total[5m]))"
        params = urllib.parse.urlencode({"query": q})
        url = f"http://platformops-obs-prometheus:9090/api/v1/query?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            results = []
            for item in data["data"]["result"]:
                results.append({"name": item["metric"].get("groupname", "unknown"), "cpu": item["value"][1]})
            return {"processes": results}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_summary(db)


@router.post("/api/monitoring/sweep", response_model=list[MonitoringCheckOut])
def monitoring_sweep(db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return run_monitoring_sweep(db)


@router.get("/api/monitoring/checks", response_model=list[MonitoringCheckOut])
def monitoring_checks(limit: int = 200, db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return latest_monitoring_checks(db, limit=limit)


