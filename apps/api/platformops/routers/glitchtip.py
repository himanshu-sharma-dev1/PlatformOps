from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
from ..orchestrator.monitoring.impl import (
    _direct_service_probe,
    add_monitoring_uptime_result,
    delete_monitoring_uptime_result,
    execute_monitoring_issue_action_result,
    get_monitoring_keys_result,
    get_monitoring_performance_result,
    get_monitoring_uptime_result,
    ingest_monitoring_transaction_result,
)
from ..schemas import (
    IntegrationStatusOut,
    MonitoringCollectionOut,
    MonitoringEventOut,
    MonitoringHealthOut,
    MonitoringIssueActionRequest,
    MonitoringIssueEventRequest,
    MonitoringIssuesOut,
    MonitoringIssuesRequest,
    MonitoringMutationOut,
    MonitoringPatchRequest,
    MonitoringServiceRequest,
    MonitoringTransactionIngestRequest,
    MonitoringTransactionIngestOut,
    MonitoringTransactionsOut,
    MonitoringUptimeAddRequest,
    MonitoringUptimeDeleteRequest,
)
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["glitchtip"])

@router.post("/PlatformIO/Monitoring/Health/", response_model=MonitoringHealthOut)
def monitoring_health(payload: MonitoringServiceRequest, db: Session = Depends(get_db)):
    service_name = payload.service_name
    window = payload.window

    service_instance = db.scalar(select(ServiceInstance).where(ServiceInstance.name == service_name))
    if not service_instance:
        return {"success": False, "error": f"Service not found: {service_name}"}

    probe = _direct_service_probe(db, service_instance)
    container_state = str(probe.get("container_state") or probe.get("value") or "unknown")
    running = probe.get("status") == "ok"

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    issues_result = query_monitoring_issues(db, service_name, window)
    issues = issues_result.get("issues", []) if isinstance(issues_result, dict) else (issues_result or [])

    error_count = sum(1 for i in issues if i.get("level") in ("error", "fatal"))
    warning_count = sum(1 for i in issues if i.get("level") == "warning")

    # Direct container/PING evidence owns service health.  GlitchTip is a
    # separate integration dimension: an unconfigured or unreachable external
    # API must not hide a real Redis failure or turn a healthy Redis target
    # into a fabricated "unknown" state.
    health = "ok"
    if not running or error_count:
        health = "error"
    elif warning_count:
        health = "warn"
    probe_availability = "available" if probe.get("status") == "ok" else ("error" if probe.get("status") == "error" else "degraded")
    issues_available = isinstance(issues_result, dict) and issues_result.get("availability") == "available"
    combined_availability = probe_availability if not issues_available else "available"

    return {
        "success": True,
        "availability": combined_availability,
        "source": "docker+glitchtip",
        "checked_at": probe.get("checked_at"),
        "error": (issues_result.get("error") if isinstance(issues_result, dict) else None) or probe.get("error"),
        "health": health,
        "running": running,
        "container_state": container_state,
        "issue_count": len(issues),
        "error_count": error_count,
        "warning_count": warning_count,
        "service_name": service_name,
        "project_slug": project_slug,
        "probe": probe,
    }


@router.post("/PlatformIO/Monitoring/Issues/", response_model=MonitoringIssuesOut)
def monitoring_issues(payload: MonitoringIssuesRequest, db: Session = Depends(get_db)):
    service_name = payload.service_name
    window = payload.window
    cursor = payload.cursor
    result = query_monitoring_issues(db, service_name, window, cursor=cursor)
    return {"success": result.get("availability") == "available", "service_name": service_name, "window": window, **result}


@router.post("/PlatformIO/Monitoring/Issues/EventDetails/", response_model=MonitoringEventOut)
def monitoring_issue_event_details(payload: MonitoringIssueEventRequest):
    event = get_monitoring_issue_event_details(payload.issue_id)
    return {"success": event.get("availability") == "available", "event": event if event.get("availability") == "available" else None, **{k: event.get(k) for k in ("availability", "source", "checked_at", "error")}}


@router.post("/PlatformIO/Monitoring/IssueAction/", response_model=MonitoringMutationOut)
def monitoring_issue_action(payload: MonitoringIssueActionRequest, db: Session = Depends(get_db)):
    result = execute_monitoring_issue_action_result(payload.issue_id, payload.action)
    record_event(db, category="monitoring", level="info" if result.get("success") else "error", message="GlitchTip issue action", metadata={"action": result.get("action"), "issue_id": payload.issue_id, "success": result.get("success"), "availability": result.get("availability"), "error": result.get("error")})
    return result


@router.post("/PlatformIO/Monitoring/Performance/", response_model=MonitoringTransactionsOut)
def monitoring_performance(payload: MonitoringServiceRequest, db: Session = Depends(get_db)):
    service_name = payload.service_name

    service_instance = db.scalar(select(ServiceInstance).where(ServiceInstance.name == service_name))
    node_ip = service_instance.node.host if (service_instance and service_instance.node) else ""
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())

    result = get_monitoring_performance_result(service_name, node_ip)
    return {"success": result.get("availability") == "available", **result}


@router.post("/PlatformIO/Monitoring/Performance/Ingest/", response_model=MonitoringTransactionIngestOut)
def monitoring_performance_ingest(payload: MonitoringTransactionIngestRequest, db: Session = Depends(get_db)):
    return ingest_monitoring_transaction_result(
        service_name=payload.service_name,
        transaction=payload.transaction,
        environment=payload.environment,
        duration_ms=payload.duration_ms,
        tags=payload.tags,
        db=db,
    )


@router.post("/PlatformIO/Monitoring/Keys/", response_model=MonitoringCollectionOut)
def monitoring_keys(payload: MonitoringServiceRequest):
    result = get_monitoring_keys_result(payload.service_name)
    return {"success": result.get("availability") == "available", **result, "items": result.get("items", []), "keys": result.get("items", [])}


@router.post("/PlatformIO/Monitoring/Uptime/", response_model=MonitoringCollectionOut)
def monitoring_uptime_list_endpoint(payload: MonitoringServiceRequest):
    result = get_monitoring_uptime_result(payload.service_name)
    return {"success": result.get("availability") == "available", **result, "items": result.get("items", []), "monitors": result.get("items", [])}


@router.post("/PlatformIO/Monitoring/Uptime/Add/", response_model=MonitoringMutationOut)
def monitoring_uptime_add(payload: MonitoringUptimeAddRequest, db: Session = Depends(get_db)):
    return add_monitoring_uptime_result(service_name=payload.service_name, name=payload.name, url=payload.url, interval=payload.interval, expected_status=payload.expected_status, monitor_type=payload.monitor_type, timeout=payload.timeout, expected_body=payload.expected_body, db=db)


@router.post("/PlatformIO/Monitoring/Uptime/Delete/", response_model=MonitoringMutationOut)
def monitoring_uptime_delete(payload: MonitoringUptimeDeleteRequest, db: Session = Depends(get_db)):
    return delete_monitoring_uptime_result(payload.monitor_id, db=db)


@router.post("/PlatformIO/Monitoring/IntegrationStatus/", response_model=IntegrationStatusOut)
@router.get("/PlatformIO/Monitoring/IntegrationStatus/")
def monitoring_integration_status() -> dict:
    res = get_monitoring_integration_status()
    return res


@router.post("/PlatformIO/Monitoring/PatchObservability/", response_model=MonitoringMutationOut)
def monitoring_patch_observability(payload: MonitoringPatchRequest, db: Session = Depends(get_db)):
    res = patch_service_runtime_observability(db, payload.service_id)
    res.setdefault("availability", "available" if res.get("success") else "error")
    res.setdefault("source", "runtime_patch")
    record_event(db, category="monitoring", level="info" if res.get("success") else "error", message="Runtime observability patch", service_id=payload.service_id, metadata={"action": "patch_observability", "success": res.get("success"), "error": res.get("error")})
    return res


# --- CLUSTER PAGE EXTRA FEATURES & INTEGRATIONS ---


class TestGitRepoRequest(BaseModel):
    repo_type: str
    repo_url: str
    repo_branch: str
    repo_token: str | None = None


class TestRegistryRequest(BaseModel):
    registry_type: str
    registry_url: str
    registry_user: str | None = None
    registry_password: str | None = None


class NodeLaunchRequest(BaseModel):
    ami_id: str
    instance_type: str
    region: str
