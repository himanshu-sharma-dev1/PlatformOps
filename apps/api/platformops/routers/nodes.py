from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["nodes"])

@router.get("/api/nodes/{node_id}/deployment-plan/{service_key}", response_model=DeploymentPlanOut)
def get_deployment_plan(node_id: int, service_key: str, db: Session = Depends(get_db)) -> dict:
    try:
        return deployment_plan(db, _get_node(db, node_id), service_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/observability/bootstrap", response_model=ObservabilityBootstrapOut)
def bootstrap_observability(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return bootstrap_observability_plane(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/artifacts/inventory", response_model=GeneratedArtifactOut)
def node_inventory(node_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    node = _get_node(db, node_id)
    return {"name": f"{node.name}-inventory.ini", "content_type": "text/ini", "content": generate_inventory(node)}


@router.get("/api/nodes/{node_id}/artifacts/compose", response_model=GeneratedArtifactOut)
def node_compose(node_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    node = _get_node(db, node_id)
    return {
        "name": f"{node.name}-docker-compose.yml",
        "content_type": "application/x-yaml",
        "content": generate_compose(db, node),
    }


@router.post("/api/nodes/{node_id}/capacity", response_model=CapacityReportOut)
def node_capacity(node_id: int, db: Session = Depends(get_db)) -> CapacityReport:
    return generate_capacity_report(db, _get_node(db, node_id))


@router.get("/api/nodes", response_model=list[NodeOut])
def list_nodes(cluster_id: int | None = None, db: Session = Depends(get_db)) -> list[Node]:
    statement = select(Node).order_by(Node.created_at.desc())
    if cluster_id is not None:
        statement = statement.where(Node.cluster_id == cluster_id)
    return list(db.scalars(statement).all())


def _save_ssh_private_key(node_id: int, private_key_content: str) -> str:
    import os
    import stat

    from ..settings import settings

    keys_dir = settings.resolve(settings.runtime_dir) / "ssh_keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key_file = keys_dir / f"node_{node_id}.pem"

    content = private_key_content.strip() + "\n"
    key_file.write_text(content, encoding="utf-8")

    os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
    return str(key_file)


def _facts_json_from_payload(facts: dict | None) -> str:
    import json as _json

    base = {
        "cpu_cores": 0,
        "memory_gb": 0,
        "storage_gb": 0,
        "gpu": "none",
        "os": "linux",
    }
    if isinstance(facts, dict):
        for key in base:
            if key in facts and facts[key] is not None:
                base[key] = facts[key]
        # allow extra keys from operator
        for key, value in facts.items():
            if key not in base:
                base[key] = value
    return _json.dumps(base)


@router.post("/api/nodes", response_model=NodeOut)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)) -> Node:
    _get_cluster(db, payload.cluster_id)
    private_key = payload.ssh_private_key
    node_data = payload.model_dump(exclude={"ssh_private_key", "facts"})
    if not node_data.get("docker_network"):
        node_data["docker_network"] = "platformops_prod_network"
    node_data["facts_json"] = _facts_json_from_payload(payload.facts)
    if not node_data.get("status"):
        node_data["status"] = "unknown"
    node = Node(**node_data)
    db.add(node)
    db.commit()
    db.refresh(node)

    if private_key:
        key_path = _save_ssh_private_key(node.id, private_key)
        node.ssh_key_path = key_path
        db.commit()
        db.refresh(node)

    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Created node '{node.name}'",
        node_id=node.id,
        metadata={"node_id": node.id, "host": node.host, "docker_network": node.docker_network},
    )

    # cPlatform parity: bootstrap AIOrchestrator on first node of a cluster
    try:
        _bootstrap_ai_orchestrator_if_needed(db, node)
    except Exception as exc:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"AIOrchestrator bootstrap skipped: {exc}",
            node_id=node.id,
            metadata={"error": str(exc)},
        )

    db.refresh(node)
    return node


def _bootstrap_ai_orchestrator_if_needed(db: Session, node: Node) -> None:
    """Register AIOrchestrator on first node if cluster has none (cPlatform primary bootstrap)."""
    from ..orchestrator.service.impl import create_service_instance

    cluster_nodes = list(db.scalars(select(Node).where(Node.cluster_id == node.cluster_id)).all())
    node_ids = [n.id for n in cluster_nodes]
    if not node_ids:
        return
    existing = db.scalar(
        select(ServiceInstance).where(
            ServiceInstance.node_id.in_(node_ids),
            ServiceInstance.service_key.in_(["ai-orchestrator", "AIOrchestrator", "cplatform"]),
        )
    )
    if existing:
        return
    # Only auto-bootstrap when this is the first (or only) node
    if len(cluster_nodes) > 1 and node.id != min(node_ids):
        return
    create_service_instance(
        db,
        node=node,
        service_key="ai-orchestrator",
        name="AIOrchestrator",
        contract_overrides={"install_mode": "manual", "adopted": False, "bootstrap": True},
    )


@router.put("/api/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)) -> Node:
    node = _get_node(db, node_id)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return node
    if "cluster_id" in updates:
        _get_cluster(db, updates["cluster_id"])

    private_key = updates.pop("ssh_private_key", None)
    facts = updates.pop("facts", None)
    if private_key is not None:
        key_path = _save_ssh_private_key(node.id, private_key)
        node.ssh_key_path = key_path
    if facts is not None:
        import json as _json

        try:
            current = _json.loads(node.facts_json or "{}")
        except Exception:
            current = {}
        if not isinstance(current, dict):
            current = {}
        current.update(facts)
        node.facts_json = _json.dumps(current)

    for key, value in updates.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)
    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Updated node '{node.name}'",
        node_id=node.id,
        metadata={"node_id": node.id, "updates": payload.model_dump(exclude_none=True)},
    )
    return node


@router.post("/api/nodes/{node_id}/validate", response_model=JobOut)
def validate_node_endpoint(node_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    return validate_node(db, _get_node(db, node_id))


@router.delete("/api/nodes/{node_id}")
def delete_node(
    node_id: int,
    force: bool = False,
    force_reason: str | None = None,
    force_approval_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    node = _get_node(db, node_id)
    impact = lifecycle_impact(db, "node", node_id)
    policy = None
    if force and not impact["can_delete_without_force"]:
        policy = evaluate_force_delete_policy(
            db,
            target_type="node",
            target_id=node_id,
            impact=impact,
            force_reason=force_reason,
        )
        if not policy["allowed"]:
            blocked = {**impact, "policy": policy, "recommended_action": policy["recommended_action"]}
            record_event(
                db,
                category="lifecycle",
                level="warning",
                message=f"Force delete node '{node.name}' blocked by policy gates",
                node_id=node_id,
                metadata={"node_id": node_id, "impact": impact, "policy": policy},
            )
            raise HTTPException(status_code=409, detail=blocked)
        approval_check = validate_force_delete_approval(
            db,
            target_type="node",
            target_id=node_id,
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
                "recommended_action": "Get an approved force-delete request for this node before retrying.",
            }
            raise HTTPException(status_code=409, detail=blocked)
    if not force and not impact["can_delete_without_force"]:
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message=f"Delete node '{node.name}' blocked: has active services",
            node_id=node_id,
            metadata={"node_id": node_id, "impact": impact},
        )
        raise HTTPException(status_code=409, detail=impact)

    services = db.scalars(select(ServiceInstance).where(ServiceInstance.node_id == node.id)).all()
    service_count = len(services)
    for s in services:
        db.delete(s)
    db.delete(node)
    db.commit()

    record_event(
        db,
        category="lifecycle",
        level="warning" if force else "info",
        message=f"Deleted node '{node.name}' (cascaded {service_count} services)"
        if force
        else f"Deleted empty node '{node.name}'",
        node_id=node_id,
        metadata={"node_id": node_id, "service_count": service_count, "force": force, "policy": policy},
    )
    if force and force_approval_id is not None:
        approval = _get_force_delete_approval(db, force_approval_id)
        mark_force_delete_approval_used(db, approval)
    return {"status": "deleted", "cascaded_services": service_count}


@router.get("/api/nodes/{node_id}/lifecycle-impact", response_model=LifecycleImpact)
def get_node_lifecycle_impact_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return lifecycle_impact(db, "node", node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/subsystems/{subsystem}/rollout-plan", response_model=SubsystemRolloutPlan)
def get_subsystem_rollout_plan_endpoint(node_id: int, subsystem: str, db: Session = Depends(get_db)) -> dict:
    try:
        return get_subsystem_rollout_plan(db, node_id, subsystem)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/subsystems/{subsystem}/deploy")
def deploy_subsystem_endpoint(node_id: int, subsystem: str, db: Session = Depends(get_db)) -> dict:
    try:
        return deploy_subsystem(db, node_id, subsystem)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/summary", response_model=NodeSummary)
def get_node_summary_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_summary(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/metrics", response_model=NodeMetricsOut)
def get_node_metrics_endpoint(node_id: int, window: str = "1h", db: Session = Depends(get_db)) -> dict:
    try:
        return orchestrator_get_node_metrics(db, node_id, window=window)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/connection", response_model=NodeConnectionOut)
def get_node_connection_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_connection_report(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/jobs", response_model=NodeJobHistoryOut)
def get_node_jobs_endpoint(node_id: int, limit: int = 12, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_job_history(db, node_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/onboarding-readiness", response_model=NodeOnboardingOut)
def get_node_onboarding_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return get_node_onboarding_report(db, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/onboarding-remediate", response_model=NodeOnboardingRemediationOut)
def remediate_node_onboarding_endpoint(
    node_id: int,
    payload: NodeOnboardingRemediationRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return remediate_node_onboarding(db, node_id, action=payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/launch-vm", response_model=JobOut)
def launch_node_vm_endpoint(node_id: int, payload: NodeLaunchRequest, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    try:
        return launch_node_vm(
            db, node, ami_id=payload.ami_id, instance_type=payload.instance_type, region=payload.region
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/teardown-vm", response_model=JobOut)
def teardown_node_vm_endpoint(node_id: int, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    try:
        return teardown_node_vm(db, node)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/discover")
def discover_infrastructure_endpoint(node_id: int, db: Session = Depends(get_db)) -> dict:
    node = db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    try:
        return discover_infrastructure(db, node)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/check-port-and-name")
def check_port_and_name_endpoint(
    node_id: int, port: int | None = None, name: str | None = None, db: Session = Depends(get_db)
) -> dict:
    return check_port_and_name_availability(db, node_id=node_id, port=port, name=name)


