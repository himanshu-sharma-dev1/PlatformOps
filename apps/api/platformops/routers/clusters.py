from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["clusters"])


def _cluster_type(payload: ClusterCreate | ClusterUpdate) -> str | None:
    """Accept both cPlatform's ``type`` and the canonical ``cluster_type``."""

    value = getattr(payload, "type", None) or getattr(payload, "cluster_type", None)
    return str(value).strip() if value is not None else None


def _cluster_name_collision(db: Session, *, name: str, exclude_id: int | None = None) -> Cluster | None:
    statement = select(Cluster).where(func.lower(Cluster.name) == name.casefold())
    if exclude_id is not None:
        statement = statement.where(Cluster.id != exclude_id)
    return db.scalar(statement)

@router.post("/api/clusters", response_model=ClusterOut)
def create_cluster(payload: ClusterCreate, db: Session = Depends(get_db)) -> Cluster:
    cluster_name = str(payload.name or "").strip()
    if not cluster_name:
        raise HTTPException(status_code=422, detail="Cluster name is required")
    existing = _cluster_name_collision(db, name=cluster_name)
    if existing:
        raise HTTPException(status_code=409, detail="Cluster name already exists")
    cluster = Cluster(
        name=cluster_name,
        region=str(payload.region or "local").strip() or "local",
        environment=str(payload.environment or "development").strip() or "development",
        description=str(payload.description or ""),
        cluster_type=_cluster_type(payload) or "standalone",
        variant=str(payload.variant or "").strip(),
        role=str(payload.role or "").strip(),
        repo_type=payload.repo_type or "github",
        repo_url=payload.repo_url or "",
        repo_branch=payload.repo_branch or "main",
        repo_token=payload.repo_token or "",
        repo_path=payload.repo_path or "",
        repo_auth=payload.repo_auth or "pat",
        registry_type=payload.registry_type or "dockerhub",
        registry_url=payload.registry_url or "",
        registry_user=payload.registry_user or "",
        registry_password=payload.registry_password or "",
        registry_namespace=payload.registry_namespace or "",
        registry_auth=payload.registry_auth or "password",
        image_store=payload.image_store or "",
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Created cluster '{cluster.name}'",
        metadata={"cluster_id": cluster.id},
    )
    return _mask_cluster(cluster)


@router.get("/api/clusters", response_model=list[ClusterOut])
def list_clusters(db: Session = Depends(get_db)) -> list[Cluster]:
    clusters = list(db.scalars(select(Cluster).order_by(Cluster.created_at.desc())).all())
    return [_mask_cluster(c) for c in clusters]


@router.put("/api/clusters/{cluster_id}", response_model=ClusterOut)
def update_cluster(cluster_id: int, payload: ClusterUpdate, db: Session = Depends(get_db)) -> Cluster:
    cluster = _get_cluster(db, cluster_id)
    updates = payload.model_dump(exclude_none=True)
    if "type" in updates:
        # ``type`` is a public compatibility alias; persist one canonical
        # value and avoid sending an unknown ORM attribute to setattr below.
        updates["cluster_type"] = updates.pop("type")
    if not updates:
        return _mask_cluster(cluster)
    if "name" in updates:
        updates["name"] = str(updates["name"] or "").strip()
        if not updates["name"]:
            raise HTTPException(status_code=422, detail="Cluster name is required")
        existing = _cluster_name_collision(db, name=updates["name"], exclude_id=cluster.id)
        if existing:
            raise HTTPException(status_code=409, detail="Cluster name already exists")
    # Empty secret fields mean "keep existing" (cPlatform replace semantics)
    if updates.get("repo_token") in ("", "***"):
        updates.pop("repo_token", None)
    if updates.get("registry_password") in ("", "***"):
        updates.pop("registry_password", None)
    for key, value in updates.items():
        setattr(cluster, key, value)
    db.commit()
    db.refresh(cluster)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Updated cluster '{cluster.name}'",
        metadata={"cluster_id": cluster.id, "updates": {k: ("***" if "token" in k or "password" in k else v) for k, v in updates.items()}},
    )
    return _mask_cluster(cluster)


@router.delete("/api/clusters/{cluster_id}")
def delete_cluster(
    cluster_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cluster = _get_cluster(db, cluster_id)
    impact = lifecycle_impact(db, "cluster", cluster_id)
    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="cluster",
            target_id=cluster_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete cluster '{cluster.name}' blocked by policy gates",
                metadata={"cluster_id": cluster_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="cluster",
            target_id=cluster_id,
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
                "recommended_action": "Get an approved force-delete request for this cluster before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete cluster '{cluster.name}' blocked: contains active nodes/services",
            node_id=None,
            metadata={"cluster_id": cluster_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    nodes = db.scalars(select(Node).where(Node.cluster_id == cluster.id)).all()
    node_count = len(nodes)
    service_count = 0
    services_by_node: dict[int, list[ServiceInstance]] = {}
    for n in nodes:
        services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == n.id)).all()
        services_by_node[n.id] = services
        service_count += len(services)

    detach_resource_references(
        db,
        service_ids=[service.id for services in services_by_node.values() for service in services],
        node_ids=[node.id for node in nodes],
    )
    for n in nodes:
        services = services_by_node[n.id]
        for s in services:
            db.delete(s)
        db.delete(n)
    db.delete(cluster)
    db.commit()

    record_event(
        db,
        category="lifecycle",
        level="warning" if force else "info",
        message=f"Deleted cluster '{cluster.name}' (cascaded {node_count} nodes, {service_count} services)"
        if force
        else f"Deleted empty cluster '{cluster.name}'",
        node_id=None,
        metadata={"cluster_id": cluster_id, "node_count": node_count, "service_count": service_count, "force": force},
    )
    if force and force_approval_id is not None:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return {"status": "deleted", "cascaded_nodes": node_count, "cascaded_services": service_count}


@router.get("/api/clusters/{cluster_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_cluster_lifecycle_impact_endpoint(cluster_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "cluster", cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/clusters/{cluster_id}/summary", response_model=ClusterSummary)
def get_cluster_summary_endpoint(cluster_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_cluster_summary(db, cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/clusters/{cluster_id}/operations", response_model=ClusterOperationsOut)
def get_cluster_operations_endpoint(cluster_id: int, limit: int = 40, db: Session = Depends(get_db)) -> dict:
    try:
        return get_cluster_operations_view(db, cluster_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/clusters/test-repo")
def test_cluster_repo_connection_endpoint(payload: TestGitRepoRequest = Body(...)) -> dict:
    try:
        return test_git_connection(
            repo_type=payload.repo_type,
            repo_url=payload.repo_url,
            repo_branch=payload.repo_branch,
            repo_token=payload.repo_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/clusters/test-registry")
def test_cluster_registry_connection_endpoint(payload: TestRegistryRequest = Body(...)) -> dict:
    try:
        return test_registry_connection(
            registry_type=payload.registry_type,
            registry_url=payload.registry_url,
            registry_user=payload.registry_user,
            registry_password=payload.registry_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
