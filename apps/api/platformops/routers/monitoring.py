from __future__ import annotations

import requests
from fastapi import APIRouter

from . import ops_common as _ops_common
from ..query import escape_query_regex_literal
from ..schemas import ProcessMetricsOut
from ..orchestrator.monitoring.impl import _metric_state, _probe_timestamp, _prom_observe
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["monitoring"])

@router.get("/api/metrics/node")
def get_node_metrics(node_id: int | None = None, db: Session = Depends(get_db)):
    if node_id is not None:
        return orchestrator_get_node_metrics(db, node_id, window="1h")
    observations = {
        "cpu": _prom_observe('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'),
        "memory": _prom_observe("(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"),
        "disk": _prom_observe('(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100'),
    }
    availability, error = _metric_state(list(observations.values()))
    return {
        "cpu": observations["cpu"].get("value") if observations["cpu"].get("state") == "available" else None,
        "memory": observations["memory"].get("value") if observations["memory"].get("state") == "available" else None,
        "disk": observations["disk"].get("value") if observations["disk"].get("state") == "available" else None,
        "prometheus_reachable": any(item.get("reachable") for item in observations.values()),
        "availability": availability,
        "source": "prometheus",
        "checked_at": _probe_timestamp(),
        "error": error,
    }


@router.get("/api/metrics/processes", response_model=ProcessMetricsOut)
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
        cpu_query = f"topk({safe_limit}, sum by (instance, groupname) (rate(namedprocess_namegroup_cpu_seconds_total{cpu_matcher}[5m])))"
        memory_query = f"topk({safe_limit}, sum by (instance, groupname) (namedprocess_namegroup_memory_bytes{memory_matcher}))"
        endpoint = f"{settings.prometheus_base_url.rstrip('/')}/api/v1/query"
        cpu_response = requests.get(endpoint, params={"query": cpu_query}, timeout=5)
        memory_response = requests.get(endpoint, params={"query": memory_query}, timeout=5)
        cpu_response.raise_for_status()
        memory_response.raise_for_status()

        cpu_payload = cpu_response.json()
        memory_payload = memory_response.json()
        if cpu_payload.get("status") != "success" or memory_payload.get("status") != "success":
            raise RuntimeError(str(cpu_payload.get("error") or memory_payload.get("error") or "Prometheus process query failed"))
        processes: dict[str, dict] = {}
        for item in cpu_payload.get("data", {}).get("result") or []:
            labels = item.get("metric", {})
            name = labels.get("groupname", "unknown")
            identity = labels.get("instance") or "unknown"
            key_name = f"{identity}:{name}"
            processes.setdefault(key_name, {"name": name, "cpu": None, "memory": None, "instance": identity})["cpu"] = float(
                item.get("value", [0, 0])[1]
            )
        for item in memory_payload.get("data", {}).get("result") or []:
            labels = item.get("metric", {})
            name = labels.get("groupname", "unknown")
            identity = labels.get("instance") or "unknown"
            key_name = f"{identity}:{name}"
            # Memory is returned in MiB and labelled by the response to avoid
            # presenting raw bytes as a percentage.
            processes.setdefault(key_name, {"name": name, "cpu": None, "memory": None, "instance": identity})["memory"] = round(
                float(item.get("value", [0, 0])[1]) / 1024 / 1024, 2
            )
        key = "memory" if sort == "memory" else "cpu"
        rows = sorted(processes.values(), key=lambda item: float(item[key]) if item.get(key) is not None else float("-inf"), reverse=True)[:safe_limit]
        node_name = node.name if node_id is not None else None
        for row in rows:
            row["node_id"] = node_id
            row["node_name"] = node_name
        availability = "available" if processes else "unavailable"
        return {
            "processes": rows,
            "node_id": node_id,
            "node_name": node_name,
            "sort": key,
            "memory_unit": "MiB",
            "source": "prometheus",
            "availability": availability,
            "checked_at": _probe_timestamp(),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "processes": [],
            "node_id": node_id,
            "sort": "memory" if sort == "memory" else "cpu",
            "memory_unit": "MiB",
            "source": "prometheus",
            "availability": "error",
            "checked_at": _probe_timestamp(),
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
