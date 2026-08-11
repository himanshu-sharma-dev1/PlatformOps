from __future__ import annotations

import requests
from fastapi import APIRouter

from . import ops_common as _ops_common
from ..query import escape_query_regex_literal
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
            response = requests.get(
                f"{settings.prometheus_base_url.rstrip('/')}/api/v1/query",
                params={"query": q},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("data", {}).get("result"):
                results[key] = data["data"]["result"][0]["value"][1]
            else:
                results[key] = 0
        results["prometheus_reachable"] = True
        return results
    except Exception as e:
        return {"error": str(e), "prometheus_reachable": False}


@router.get("/api/metrics/processes")
def get_process_metrics(
    node_id: int | None = None,
    sort: str = "cpu",
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Return real process-exporter CPU and memory metrics for one node.

    The endpoint retains the legacy global mode when ``node_id`` is omitted,
    but selected-node requests add an instance matcher so the UI never mixes
    processes from unrelated hosts.
    """
    try:
        safe_limit = max(1, min(int(limit), 100))
        instance_pattern = ""
        if node_id is not None:
            node = db.get(Node, node_id)
            if node is None:
                raise HTTPException(status_code=404, detail="Node not found")
            candidates = [str(node.host or ""), str(node.name or "")]
            pattern = "|".join(escape_query_regex_literal(value) for value in candidates if value)
            if pattern:
                instance_pattern = pattern

        cpu_matcher = f'{{instance=~".*({instance_pattern}).*"}}' if instance_pattern else ""
        memory_labels = ['memtype="resident"']
        if instance_pattern:
            memory_labels.append(f'instance=~".*({instance_pattern}).*"')
        memory_matcher = "{" + ",".join(memory_labels) + "}"
        cpu_query = f"topk({safe_limit}, sum by (groupname) (rate(namedprocess_namegroup_cpu_seconds_total{cpu_matcher}[5m])))"
        memory_query = f"topk({safe_limit}, sum by (groupname) (namedprocess_namegroup_memory_bytes{memory_matcher}))"
        endpoint = f"{settings.prometheus_base_url.rstrip('/')}/api/v1/query"
        cpu_response = requests.get(endpoint, params={"query": cpu_query}, timeout=5)
        memory_response = requests.get(endpoint, params={"query": memory_query}, timeout=5)
        cpu_response.raise_for_status()
        memory_response.raise_for_status()

        processes: dict[str, dict] = {}
        for item in cpu_response.json().get("data", {}).get("result") or []:
            name = item.get("metric", {}).get("groupname", "unknown")
            processes.setdefault(name, {"name": name, "cpu": 0.0, "memory": 0.0})["cpu"] = float(
                item.get("value", [0, 0])[1]
            )
        for item in memory_response.json().get("data", {}).get("result") or []:
            name = item.get("metric", {}).get("groupname", "unknown")
            # Memory is returned in MiB and labelled by the response to avoid
            # presenting raw bytes as a percentage.
            processes.setdefault(name, {"name": name, "cpu": 0.0, "memory": 0.0})["memory"] = round(
                float(item.get("value", [0, 0])[1]) / 1024 / 1024, 2
            )
        key = "memory" if sort == "memory" else "cpu"
        rows = sorted(processes.values(), key=lambda item: float(item[key]), reverse=True)[:safe_limit]
        return {
            "processes": rows,
            "node_id": node_id,
            "sort": key,
            "memory_unit": "MiB",
            "prometheus_reachable": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "processes": [],
            "node_id": node_id,
            "sort": "memory" if sort == "memory" else "cpu",
            "memory_unit": "MiB",
            "prometheus_reachable": False,
            "error": str(e),
        }


@router.get("/api/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_summary(db)


@router.post("/api/monitoring/sweep", response_model=list[MonitoringCheckOut])
def monitoring_sweep(db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return run_monitoring_sweep(db)


@router.get("/api/monitoring/checks", response_model=list[MonitoringCheckOut])
def monitoring_checks(limit: int = 200, db: Session = Depends(get_db)) -> list[MonitoringCheck]:
    return latest_monitoring_checks(db, limit=limit)
