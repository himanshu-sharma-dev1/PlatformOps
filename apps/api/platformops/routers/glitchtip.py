from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["glitchtip"])

@router.post("/PlatformIO/Monitoring/Health/")
def monitoring_health(payload: dict = Body(...), db: Session = Depends(get_db)):
    service_name = payload.get("service_name", "")
    window = payload.get("window", "24h")
    if not service_name:
        return {"success": False, "error": "service_name required"}

    service_instance = db.scalar(select(ServiceInstance).where(ServiceInstance.name == service_name))
    if not service_instance:
        return {"success": False, "error": f"Service not found: {service_name}"}

    container_state = service_instance.status
    running = container_state.lower() in RUNNING_STATUSES

    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    issues_result = query_monitoring_issues(db, service_name, window)
    issues = issues_result.get("issues", []) if isinstance(issues_result, dict) else (issues_result or [])

    error_count = sum(1 for i in issues if i.get("level") in ("error", "fatal"))
    warning_count = sum(1 for i in issues if i.get("level") == "warning")

    health = "ok"
    if not running or error_count:
        health = "error"
    elif warning_count:
        health = "warn"

    return {
        "success": True,
        "health": health,
        "running": running,
        "container_state": container_state,
        "issue_count": len(issues),
        "error_count": error_count,
        "warning_count": warning_count,
        "service_name": service_name,
        "project_slug": project_slug,
    }


@router.post("/PlatformIO/Monitoring/Issues/")
def monitoring_issues(payload: dict = Body(...), db: Session = Depends(get_db)):
    service_name = payload.get("service_name", "")
    window = payload.get("window", "24h")
    cursor = payload.get("cursor") or None
    if not service_name:
        return {"success": False, "error": "service_name required"}
    result = query_monitoring_issues(db, service_name, window, cursor=cursor)
    if isinstance(result, dict):
        return {
            "success": True,
            "issues": result.get("issues", []),
            "next_cursor": result.get("next_cursor"),
        }
    return {"success": True, "issues": result or [], "next_cursor": None}


@router.post("/PlatformIO/Monitoring/Issues/EventDetails/")
def monitoring_issue_event_details(payload: dict = Body(...)):
    issue_id = payload.get("issue_id")
    if not issue_id:
        return {"success": False, "error": "issue_id required"}
    try:
        event = get_monitoring_issue_event_details(issue_id)
        return {"success": True, "event": event}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/PlatformIO/Monitoring/IssueAction/")
def monitoring_issue_action(payload: dict = Body(...)):
    issue_id = payload.get("issue_id")
    action = payload.get("action", "resolved")
    if not issue_id:
        return {"success": False, "error": "issue_id required"}
    success = execute_monitoring_issue_action(issue_id, action)
    return {"success": success}


@router.post("/PlatformIO/Monitoring/Performance/")
def monitoring_performance(payload: dict = Body(...), db: Session = Depends(get_db)):
    service_name = payload.get("service_name", "")
    if not service_name:
        return {"success": False, "error": "service_name required"}

    service_instance = db.scalar(select(ServiceInstance).where(ServiceInstance.name == service_name))
    node_ip = service_instance.node.host if (service_instance and service_instance.node) else ""
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())

    try:
        transactions = get_monitoring_performance(service_name, node_ip)
        return {"success": True, "transactions": transactions, "project_slug": project_slug, "node_ip": node_ip}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/PlatformIO/Monitoring/Keys/")
def monitoring_keys(payload: dict = Body(...)):
    service_name = payload.get("service_name", "")
    if not service_name:
        return {"success": False, "error": "service_name required"}
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    try:
        keys = get_monitoring_keys(service_name)
        return {"success": True, "keys": keys, "project_slug": project_slug}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/PlatformIO/Monitoring/Uptime/")
def monitoring_uptime_list_endpoint(payload: dict = Body(...)):
    service_name = payload.get("service_name", "")
    if not service_name:
        return {"success": False, "error": "service_name required"}
    project_slug = settings.glitchtip_project_map.get(service_name, service_name.lower())
    try:
        monitors = get_monitoring_uptime_list(service_name)
        return {"success": True, "monitors": monitors, "project_slug": project_slug}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/PlatformIO/Monitoring/Uptime/Add/")
def monitoring_uptime_add(payload: dict = Body(...)):
    service_name = payload.get("service_name", "")
    name = payload.get("name", "")
    url = payload.get("url", "")
    interval = int(payload.get("interval", 60))
    expected_status = int(payload.get("expected_status", 200))

    if not service_name or not name or not url:
        return {"success": False, "error": "service_name, name, and url required"}

    res = add_monitoring_uptime_check(
        service_name=service_name,
        name=name,
        url=url,
        interval=interval,
        expected_status=expected_status,
    )
    return res


@router.post("/PlatformIO/Monitoring/Uptime/Delete/")
def monitoring_uptime_delete(payload: dict = Body(...)):
    monitor_id = payload.get("monitor_id")
    if not monitor_id:
        return {"success": False, "error": "monitor_id required"}
    success = delete_monitoring_uptime_check(monitor_id)
    return {"success": success}


@router.post("/PlatformIO/Monitoring/IntegrationStatus/")
@router.get("/PlatformIO/Monitoring/IntegrationStatus/")
def monitoring_integration_status():
    res = get_monitoring_integration_status()
    return res


@router.post("/PlatformIO/Monitoring/PatchObservability/")
def monitoring_patch_observability(payload: dict = Body(...), db: Session = Depends(get_db)):
    service_id = payload.get("service_id")
    if not service_id:
        return {"success": False, "error": "service_id required"}
    res = patch_service_runtime_observability(db, service_id)
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


