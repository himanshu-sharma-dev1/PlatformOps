from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
from ..schemas import DiagnosticsBackfillOut
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["services"])

@router.get("/api/services/placement/recommendations/{service_key}", response_model=PlacementRecommendationOut)
def get_placement_recommendations(
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: str | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    parsed_avoid: list[int] = []
    if avoid_node_ids:
        parsed_avoid = [int(value.strip()) for value in avoid_node_ids.split(",") if value.strip()]
    try:
        return placement_recommendations(
            db,
            service_key=service_key,
            prefer_node_id=prefer_node_id,
            avoid_node_ids=parsed_avoid,
            anti_affinity_service_key=anti_affinity_service_key,
            require_healthy=require_healthy,
            spread_subsystem=spread_subsystem,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/services/placement/deploy/{service_key}", response_model=PlacementDeployOut)
def deploy_from_placement(
    service_key: str,
    prefer_node_id: int | None = None,
    avoid_node_ids: str | None = None,
    anti_affinity_service_key: str | None = None,
    require_healthy: bool = False,
    spread_subsystem: bool = False,
    auto_install_dependencies: bool = True,
    allow_capacity_risk: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    parsed_avoid: list[int] = []
    if avoid_node_ids:
        parsed_avoid = [int(value.strip()) for value in avoid_node_ids.split(",") if value.strip()]
    try:
        return placement_auto_deploy(
            db,
            service_key=service_key,
            prefer_node_id=prefer_node_id,
            avoid_node_ids=parsed_avoid,
            anti_affinity_service_key=anti_affinity_service_key,
            require_healthy=require_healthy,
            spread_subsystem=spread_subsystem,
            auto_install_dependencies=auto_install_dependencies,
            allow_capacity_risk=allow_capacity_risk,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/services", response_model=list[ServiceOut])
def list_services(node_id: int | None = None, db: Session = Depends(get_db)) -> list[ServiceInstance]:
    statement = select(ServiceInstance).order_by(ServiceInstance.created_at.desc())
    if node_id is not None:
        statement = statement.where(ServiceInstance.node_id == node_id)
    return list(db.scalars(statement).all())


@router.post("/api/services", response_model=ServiceOut)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)) -> ServiceInstance:
    node = _get_node(db, payload.node_id)
    overrides = dict(payload.contract_overrides or {})
    if payload.install_mode is not None:
        overrides["install_mode"] = payload.install_mode
    try:
        return create_service_instance(
            db,
            node=node,
            service_key=payload.service_key,
            name=payload.name,
            contract_overrides=overrides,
        )
    except ValueError as exc:
        message = str(exc)
        status = 409 if "already in use" in message else 422 if "identity fields" in message else 400
        raise HTTPException(status_code=status, detail=message) from exc


@router.patch("/api/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, payload: ServiceUpdate, db: Session = Depends(get_db)) -> ServiceInstance:
    service = _get_service(db, service_id)
    overrides = dict(payload.contract_overrides or {})
    if payload.install_mode is not None:
        overrides["install_mode"] = payload.install_mode
    try:
        return update_service_instance(
            db,
            service,
            name=payload.name,
            contract_overrides=overrides,
        )
    except ValueError as exc:
        message = str(exc)
        status = 409 if "already in use" in message else 422 if "identity fields" in message else 400
        raise HTTPException(status_code=status, detail=message) from exc


@router.post("/api/services/{service_id}/preflight", response_model=PreflightOut)
def preflight(service_id: int, db: Session = Depends(get_db)) -> dict:
    return dependency_preflight(db, _get_service(db, service_id))


@router.post("/api/services/{service_id}/dependencies/install-missing", response_model=DependencyInstallResultOut)
def install_service_dependencies(service_id: int, db: Session = Depends(get_db)) -> dict:
    return install_missing_dependencies(db, _get_service(db, service_id))


@router.post("/api/services/{service_id}/deploy", response_model=JobOut)
def deploy(service_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    service = _get_service(db, service_id)
    if config_capabilities_for_service(service).get("apply_enabled"):
        prepared, error = prepare_config_runtime_target(service)
        if not prepared:
            raise HTTPException(status_code=409, detail=f"Runtime config target preparation failed: {error}")
    try:
        return deploy_service(db, service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/deployment/execute", response_model=DeploymentExecuteOut)
def execute_service_deployment(
    service_id: int,
    payload: DeploymentExecuteIn,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    if config_capabilities_for_service(service).get("apply_enabled"):
        prepared, error = prepare_config_runtime_target(service)
        if not prepared:
            raise HTTPException(status_code=409, detail=f"Runtime config target preparation failed: {error}")
    try:
        return execute_deployment_plan(
            db,
            service,
            auto_install_dependencies=payload.auto_install_dependencies,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/delete", response_model=JobOut)
def delete(
    service_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> DeploymentJob:
    service = _get_service(db, service_id)
    impact = lifecycle_impact(db, "service", service_id)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete service '{service.name}' blocked: has dependents or is critical infrastructure",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="service",
            target_id=service_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete service '{service.name}' blocked by policy gates",
                service_id=service_id,
                node_id=service.node_id,
                metadata={"service_id": service_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="service",
            target_id=service_id,
            approval_id=force_approval_id,
        )
        if not approval_check["allowed"]:
            blocked = {
                **impact,
                "policy": {
                    **policy,
                    "approval": approval_check,
                    "violations": policy["violations"] + approval_check["violations"],
                },
                "recommended_action": "Get an approved force-delete request for this service before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Force deleted service '{service.name}' despite warnings",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id, "impact": impact, "policy": policy},
        )
    else:
        record_event(
            db,
            category="lifecycle",
            level="info",
            message=f"Deleted service '{service.name}' successfully",
            service_id=service_id,
            node_id=service.node_id,
            metadata={"service_id": service_id},
        )
    try:
        deleted = delete_service(db, service)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if force and force_approval_id is not None and not impact["can_delete_without_force"]:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return deleted


@router.get("/api/services/{service_id}/live-status", response_model=ServiceLiveStatusOut)
def service_live_status_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_live_status(db, _get_service(db, service_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/backup", response_model=BackupRunOut)
def backup_service(service_id: int, db: Session = Depends(get_db)) -> BackupRun:
    return run_backup(db, _get_service(db, service_id))


@router.get("/api/services/{service_id}/releases", response_model=list[ReleaseRecordOut])
def service_releases(service_id: int, limit: int = 100, db: Session = Depends(get_db)) -> list[ReleaseRecord]:
    return list_releases(db, _get_service(db, service_id), limit=limit)


@router.get("/api/services/{service_id}/releases/safety", response_model=ReleaseSafetyOut)
def service_release_safety(
    service_id: int, version: str, image: str | None = None, db: Session = Depends(get_db)
) -> dict:
    return assess_release_safety(db, _get_service(db, service_id), version=version, image=image)


@router.get("/api/services/{service_id}/releases/timeline", response_model=ServiceReleaseTimelineOut)
def service_release_timeline(service_id: int, limit: int = 8, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_release_timeline(db, service_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/release-approvals", response_model=ReleaseApprovalOut)
def create_release_approval_endpoint(payload: ReleaseApprovalCreate, db: Session = Depends(get_db)) -> ReleaseApproval:
    return create_release_approval(
        db,
        service=_get_service(db, payload.service_id),
        target_version=payload.target_version,
        target_image=payload.target_image,
        reason=payload.reason,
        requested_by=payload.requested_by,
        ttl_hours=payload.ttl_hours,
    )


@router.get("/api/release-approvals", response_model=list[ReleaseApprovalOut])
def list_release_approvals(
    service_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)
) -> list[ReleaseApproval]:
    return latest_release_approvals(db, service_id=service_id, limit=limit)


@router.post("/api/release-approvals/{approval_id}/decision", response_model=ReleaseApprovalOut)
def decide_release_approval_endpoint(
    approval_id: int, payload: ReleaseApprovalDecision, db: Session = Depends(get_db)
) -> ReleaseApproval:
    return decide_release_approval(
        db,
        _get_release_approval(db, approval_id),
        approver=payload.approver,
        status=payload.status,
        decision_note=payload.decision_note,
    )


@router.post("/api/release-approvals/{approval_id}/revoke", response_model=ReleaseApprovalOut)
def revoke_release_approval_endpoint(
    approval_id: int, payload: ReleaseApprovalRevoke, db: Session = Depends(get_db)
) -> ReleaseApproval:
    return revoke_release_approval(db, _get_release_approval(db, approval_id), actor=payload.actor, note=payload.note)


@router.post("/api/services/{service_id}/releases", response_model=ReleaseRecordOut)
def release_service(service_id: int, payload: ReleaseCreate, db: Session = Depends(get_db)) -> ReleaseRecord:
    try:
        return create_release(
            db,
            _get_service(db, service_id),
            version=payload.version,
            image=payload.image,
            strategy=payload.strategy,
            notes=payload.notes,
            approval_id=payload.approval_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=json.loads(str(exc))) from exc


@router.post("/api/releases/{release_id}/rollback", response_model=JobOut)
def rollback_service_release(release_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    try:
        return rollback_release(db, _get_release(db, release_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    job = db.get(DeploymentJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/jobs/{job_id}/logs")
def get_job_logs(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    job = db.get(DeploymentJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"output": job.output, "error": job.error, "command": job.command}


@router.get("/api/services/{service_id}/diagnostics", response_model=DiagnosticsOut)
def diagnostics(service_id: int, target_service_key: str | None = None, db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    if not target_service_key or target_service_key == service.service_key:
        return service_diagnostics(db, service, source_service=service)

    target = db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id == service.node_id,
            ServiceInstance.service_key == target_service_key,
        )
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
        )
    allowed_targets = {item["service_key"] for item in diagnostics_targets_for_service(db, service)}
    if target_service_key not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Target '{target_service_key}' is not part of diagnostics context for '{service.service_key}'.",
        )
    return service_diagnostics(db, target, source_service=service)


@router.get("/api/services/{service_id}/diagnostics/analysis", response_model=DiagnosticsAnalysisOut)
def diagnostics_analysis(service_id: int, target_service_key: str | None = None, db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    if not target_service_key or target_service_key == service.service_key:
        return service_diagnostics_analysis(db, service, source_service=service)

    target = db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id == service.node_id,
            ServiceInstance.service_key == target_service_key,
        )
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
        )
    allowed_targets = {item["service_key"] for item in diagnostics_targets_for_service(db, service)}
    if target_service_key not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Target '{target_service_key}' is not part of diagnostics context for '{service.service_key}'.",
        )
    return service_diagnostics_analysis(db, target, source_service=service)


@router.get("/api/services/{service_id}/diagnostics/targets", response_model=list[DiagnosticsTargetOut])
def diagnostics_targets(service_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return diagnostics_targets_for_service(db, _get_service(db, service_id))


@router.get("/api/services/{service_id}/diagnostics/live", response_model=DiagnosticsLiveOut)
def diagnostics_live(
    service_id: int,
    target_service_key: str | None = None,
    tail_lines: int = 150,
    page_size: int = 100,
    cursor: int = 0,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    target = service
    if target_service_key and target_service_key != service.service_key:
        resolved = db.scalar(
            select(ServiceInstance).where(
                ServiceInstance.node_id == service.node_id,
                ServiceInstance.service_key == target_service_key,
            )
        )
        if resolved is None:
            raise HTTPException(
                status_code=404,
                detail=f"Diagnostics target '{target_service_key}' is not installed on node {service.node_id}.",
            )
        target = resolved
    return service_live_logs(
        db,
        target,
        tail_lines=tail_lines,
        page_size=page_size,
        cursor=cursor,
        start=start,
        end=end,
    )


@router.get("/api/services/{service_id}/diagnostics/archives", response_model=list[LogArchiveOut])
def diagnostics_archives(service_id: int, db: Session = Depends(get_db)) -> list[LogArchive]:
    return index_log_archives(db, _get_service(db, service_id))


@router.get("/api/services/{service_id}/diagnostics/archives/{archive_id}/download")
def diagnostics_archive_download(
    service_id: int,
    archive_id: int,
    db: Session = Depends(get_db),
) -> Response:
    service = _get_service(db, service_id)
    result = download_log_archive(db, service, archive_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    path = result.get("path")
    checksum = result.get("checksum_sha256") or ""
    if path and Path(path).is_file():
        return FileResponse(
            path,
            media_type=result.get("content_type") or "application/octet-stream",
            filename=result.get("filename") or Path(path).name,
            headers={"X-Checksum-Sha256": checksum},
        )
    content = result.get("content") or ""
    return Response(
        content=content,
        media_type=result.get("content_type") or "text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{result.get("filename") or f"archive-{archive_id}.log"}"',
            "X-Checksum-Sha256": checksum,
        },
    )


@router.post("/api/services/{service_id}/diagnostics/archives/bulk-download")
def diagnostics_archives_bulk_download(
    service_id: int,
    payload: LogArchiveBulkDownloadRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    service = _get_service(db, service_id)
    result = bulk_download_log_archives(db, service, payload.archive_ids)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in result.get("files") or []:
            name = item.get("filename") or f"archive-{item.get('archive_id')}.log"
            path = item.get("path")
            if path and Path(path).is_file():
                zf.write(path, arcname=name)
            else:
                zf.writestr(name, item.get("content") or "")
    buf.seek(0)
    zip_filename = result.get("zip_filename") or f"{service.name}_logs.zip"
    record_event(
        db,
        category="diagnostics",
        level="info",
        message=f"Bulk downloaded {result.get('file_count', 0)} archives for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={"archive_ids": payload.archive_ids, "zip_filename": zip_filename},
    )
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@router.get("/api/services/{service_id}/diagnostics/file-tail", response_model=DiagnosticsFileTailOut)
def diagnostics_file_tail(
    service_id: int,
    log_path: str = "",
    tail_lines: int = 100,
    db: Session = Depends(get_db),
) -> dict:
    return service_file_tail(db, _get_service(db, service_id), log_path=log_path, tail_lines=tail_lines)


@router.get("/api/services/{service_id}/diagnostics/file-history", response_model=DiagnosticsFileHistoryOut)
def diagnostics_file_history(
    service_id: int,
    log_path: str = "",
    page: int = 1,
    page_size: int = 50,
    cursor: str = "",
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return service_file_history(
        db,
        _get_service(db, service_id),
        log_path=log_path,
        page=page,
        page_size=page_size,
        cursor=cursor,
        start=start,
        end=end,
    )


@router.get("/api/services/{service_id}/diagnostics/container-history", response_model=DiagnosticsFileHistoryOut)
def diagnostics_container_history(
    service_id: int,
    page: int = 1,
    page_size: int = 100,
    cursor: str = "",
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    result = service_container_history(
        db,
        _get_service(db, service_id),
        page=page,
        page_size=page_size,
        cursor=cursor,
        start=start,
        end=end,
    )
    # Align with DiagnosticsFileHistoryOut (log_path optional semantics)
    return {
        "lines": result.get("lines") or [],
        "source": result.get("source") or "container_history",
        "log_path": result.get("container_name") or "",
        "page": result.get("page") or page,
        "page_size": result.get("page_size") or page_size,
        "total_count": result.get("total_count") or 0,
        "total_pages": result.get("total_pages") or 1,
        "next_cursor": result.get("next_cursor"),
        "previous_cursor": result.get("previous_cursor"),
        "start": result.get("start") or start,
        "end": result.get("end") or end,
        "error": result.get("error"),
    }


@router.post("/api/services/{service_id}/diagnostics/chat", response_model=DiagnosticsChatOut)
def diagnostics_chat(
    service_id: int,
    payload: DiagnosticsChatRequest,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    result = service_log_analytics_chat(
        db,
        service,
        question=payload.question.strip(),
        window=payload.window or "current",
        history=payload.history,
    )
    record_event(
        db,
        category="diagnostics",
        level="info",
        message=f"AI log chat for {service.name}",
        service_id=service.id,
        node_id=service.node_id,
        metadata={
            "window": payload.window,
            "question_len": len(payload.question),
            "analyst_mode": result.get("_audit_mode", "deterministic_fallback"),
        },
    )
    result.pop("_audit_mode", None)
    return result


@router.post("/api/services/{service_id}/diagnostics/backfill", response_model=DiagnosticsBackfillOut)
def diagnostics_backfill(service_id: int, db: Session = Depends(get_db)) -> DiagnosticsBackfillOut:
    result = backfill_service_logs(db, _get_service(db, service_id))
    return DiagnosticsBackfillOut.model_validate(result)


@router.get("/api/services/{service_id}/config", response_model=ConfigWorkspaceOut)
def config_workspace_endpoint(service_id: int, source: str = "live", db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    try:
        return build_config_workspace(db, service, source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/config/timeline", response_model=ConfigTimelinePageOut)
def config_timeline(
    service_id: int,
    limit: int = 20,
    offset: int = 0,
    action: str = "all",
    actor: str = "all",
    search: str = "",
    created_after: str = "",
    created_before: str = "",
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    return get_config_timeline_page(
        db,
        service,
        limit=limit,
        offset=offset,
        action_filter=action,
        actor_filter=actor,
        search=search,
        created_after=created_after,
        created_before=created_before,
    )


@router.get("/api/services/{service_id}/config/snapshots", response_model=ConfigSnapshotPageOut)
def list_config_snapshots_endpoint(
    service_id: int,
    limit: int = 20,
    offset: int = 0,
    source: str = "all",
    search: str = "",
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    return list_config_snapshots_page(
        db,
        service,
        limit=limit,
        offset=offset,
        source_filter=source,
        search=search,
    )


@router.post("/api/services/{service_id}/config/drift", response_model=DriftReportOut)
def config_drift(service_id: int, db: Session = Depends(get_db)) -> DriftReport:
    return detect_drift(db, _get_service(db, service_id))


@router.post("/api/services/{service_id}/config/snapshots", response_model=ConfigSnapshotOut)
def snapshot_config(service_id: int, payload: ConfigSnapshotCreate, db: Session = Depends(get_db)) -> ConfigSnapshot:
    service = _get_service(db, service_id)
    try:
        return create_config_snapshot(
            db,
            service,
            name=payload.name,
            source=payload.source,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/config/snapshots/{snapshot_id}", response_model=ConfigSnapshotDetailOut)
def get_snapshot_detail(service_id: int, snapshot_id: int, db: Session = Depends(get_db)) -> dict:
    _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    if snapshot.service_id != service_id:
        raise HTTPException(status_code=404, detail="Config snapshot not found for service")
    return get_config_snapshot_detail(db, snapshot)


@router.get("/api/services/{service_id}/config/compare", response_model=ConfigSnapshotCompareOut)
def compare_snapshots(
    service_id: int, left_snapshot_id: int, right_snapshot_id: int, db: Session = Depends(get_db)
) -> dict:
    service = _get_service(db, service_id)
    left_snapshot = _get_snapshot(db, left_snapshot_id)
    right_snapshot = _get_snapshot(db, right_snapshot_id)
    try:
        return compare_config_snapshots(
            db,
            service,
            left_snapshot=left_snapshot,
            right_snapshot=right_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/snapshots/{snapshot_id}/rename", response_model=ConfigSnapshotOut)
def rename_snapshot(
    service_id: int,
    snapshot_id: int,
    payload: ConfigSnapshotRename,
    db: Session = Depends(get_db),
) -> ConfigSnapshot:
    _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    if snapshot.service_id != service_id:
        raise HTTPException(status_code=404, detail="Config snapshot not found for service")
    if payload.expected_version is not None and snapshot.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Stale snapshot version; reload the checkpoint list before renaming.")
    try:
        return rename_config_snapshot(db, snapshot, name=payload.name, requested_by=payload.requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/snapshots/{snapshot_id}/restore", response_model=JobOut)
def restore_snapshot(
    service_id: int,
    snapshot_id: int,
    payload: ConfigSnapshotRestore | None = Body(default=None),
    db: Session = Depends(get_db),
) -> DeploymentJob:
    service = _get_service(db, service_id)
    snapshot = _get_snapshot(db, snapshot_id)
    try:
        return restore_config_snapshot(
            db,
            service,
            snapshot,
            requested_by=payload.requested_by if payload else "platform-operator",
            expected_content_hash=payload.expected_content_hash if payload else "",
        )
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/validate", response_model=ConfigValidateOut)
def validate_config_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> dict:
    service = _get_service(db, service_id)
    result = validate_config(payload.content, service=service)
    return {"ok": result["ok"], "message": result["message"]}


@router.post("/api/services/{service_id}/config/apply", response_model=JobOut)
def apply_config_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> DeploymentJob:
    try:
        return apply_config_direct(
            db,
            _get_service(db, service_id),
            content=payload.content,
            apply_mode=payload.apply_mode,
            requested_by=payload.requested_by,
            expected_content_hash=payload.expected_content_hash,
        )["job"]
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/direct-apply", response_model=ConfigDirectApplyOut)
def apply_config_direct_endpoint(service_id: int, payload: ConfigApply, db: Session = Depends(get_db)) -> dict:
    try:
        return apply_config_direct(
            db,
            _get_service(db, service_id),
            content=payload.content,
            apply_mode=payload.apply_mode,
            requested_by=payload.requested_by,
            expected_content_hash=payload.expected_content_hash,
        )
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/migration/prepare", response_model=ConfigMigrationPrepareOut)
def prepare_config_migration_endpoint(
    service_id: int,
    payload: ConfigMigrationPrepareRequest,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    left_snapshot = _get_snapshot(db, payload.left_snapshot_id)
    right_snapshot = _get_snapshot(db, payload.right_snapshot_id)
    try:
        return prepare_config_migration(db, service, left_snapshot=left_snapshot, right_snapshot=right_snapshot)
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/migration/apply", response_model=ConfigMigrationApplyOut)
def apply_config_migration_endpoint(
    service_id: int,
    payload: ConfigMigrationApplyRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return apply_config_migration(
            db,
            _get_service(db, service_id),
            artifact_id=payload.artifact_id,
            edited_yaml=payload.edited_yaml,
            apply_mode=payload.apply_mode,
            expected_content_hash=payload.expected_content_hash,
        )
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/migration/restore", response_model=ConfigMigrationApplyOut)
def restore_config_migration_endpoint(
    service_id: int,
    payload: ConfigMigrationRestoreRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return restore_config_migration(
            db,
            _get_service(db, service_id),
            artifact_id=payload.artifact_id,
            apply_mode=payload.apply_mode,
            expected_content_hash=payload.expected_content_hash,
        )
    except ValueError as exc:
        status = 409 if "Stale config target" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/api/services/{service_id}/config/sync-peer", response_model=ConfigSyncPeerOut)
def sync_peer_config_endpoint(
    service_id: int,
    payload: ConfigSyncPeer,
    db: Session = Depends(get_db),
) -> dict:
    service = _get_service(db, service_id)
    try:
        return sync_peer_config(
            db,
            service,
            peer_id=payload.peer_id,
            apply_mode=payload.apply_mode,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/capabilities", response_model=ServiceCapabilities)
def get_service_capabilities_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_capabilities(db, service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/metrics", response_model=ServiceMetricsOut)
def get_service_metrics_endpoint(service_id: int, window: str = "1h", db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_metrics(db, service_id, window=window)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/summary", response_model=ServiceSummaryOut)
def get_service_summary_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_service_summary(db, service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/services/{service_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_service_lifecycle_impact_endpoint(service_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "service", service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
