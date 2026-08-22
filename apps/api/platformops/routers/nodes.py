from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import func

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


def _normalize_ingress_ports(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "")


def _node_name_collision(db: Session, *, cluster_id: int, name: str, exclude_id: int | None = None) -> Node | None:
    """Resolve names case-insensitively within their owning cluster."""

    statement = select(Node).where(Node.cluster_id == cluster_id, func.lower(Node.name) == name.casefold())
    if exclude_id is not None:
        statement = statement.where(Node.id != exclude_id)
    return db.scalar(statement)


@router.post("/api/nodes", response_model=NodeOut)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)) -> Node:
    cluster = _get_cluster(db, payload.cluster_id)
    node_name = str(payload.name or "").strip()
    if not node_name:
        raise HTTPException(status_code=422, detail="Node name is required")
    if _node_name_collision(db, cluster_id=cluster.id, name=node_name):
        raise HTTPException(status_code=409, detail="Node name already exists in this cluster")
    if not str(payload.host or "").strip():
        raise HTTPException(status_code=422, detail="Node host is required")
    # Private key/password fields are one-shot transport only.  They are
    # intentionally removed before constructing the ORM row; operators must
    # provide a reference (or an approved mounted key path) for later jobs.
    private_key = payload.ssh_private_key
    ephemeral_password = payload.ssh_password
    node_data = payload.model_dump(
        exclude={
            "ssh_private_key",
            "ssh_password",
            "secret_ref",
            "ssh_host_key_fingerprint",
            "ssh_known_hosts_ref",
            "facts",
            "az",
            "monitoring_port",
            "instance_id",
            "resource_id",
            "ami_id",
        }
    )
    if payload.secret_ref and not payload.ssh_secret_ref:
        node_data["ssh_secret_ref"] = payload.secret_ref
    if payload.ssh_host_key_fingerprint and not payload.host_key_fingerprint:
        node_data["host_key_fingerprint"] = payload.ssh_host_key_fingerprint
    if payload.ssh_known_hosts_ref and not payload.known_hosts_ref:
        node_data["known_hosts_ref"] = payload.ssh_known_hosts_ref
    node_data["name"] = node_name
    node_data["host"] = str(node_data.get("host") or "").strip()
    node_data["ssh_user"] = str(node_data.get("ssh_user") or "ubuntu").strip() or "ubuntu"
    if payload.az and not payload.availability_zone:
        node_data["availability_zone"] = payload.az
    if payload.monitoring_port is not None:
        node_data["monitor_port"] = payload.monitoring_port
    if payload.instance_id and not payload.cloud_instance_id:
        node_data["cloud_instance_id"] = payload.instance_id
    if payload.resource_id and not payload.cloud_resource_id:
        node_data["cloud_resource_id"] = payload.resource_id
    if payload.ami_id and not payload.cloud_image_id:
        node_data["cloud_image_id"] = payload.ami_id
    if node_data.get("region") == "local" and cluster.region and cluster.region != "local":
        node_data["region"] = cluster.region
    if node_data.get("provider") == "dc" and str(node_data.get("environment") or "").lower() in {"aws", "gcp"}:
        node_data["provider"] = str(node_data["environment"]).lower()
    if node_data.get("auth_mode") == "ssh_key" and not (
        node_data.get("ssh_key_path") or node_data.get("ssh_secret_ref") or private_key
    ):
        node_data["auth_mode"] = "none"
    from ..security import redact_secrets

    facts = redact_secrets(dict(payload.facts or {}))
    if not isinstance(facts, dict):
        facts = {}
    if ephemeral_password and not node_data.get("ssh_secret_ref"):
        # Keep only the fact that transport was requested; never record the
        # password itself or infer a reusable credential from it.
        facts["ephemeral_auth"] = "password"
    node_data["ingress_ports"] = _normalize_ingress_ports(node_data.get("ingress_ports"))
    if not node_data.get("docker_network"):
        node_data["docker_network"] = "platformops_prod_network"
    # connection_mode: auto|local|ssh (stored in facts; no hardcoded hosts)
    if "connection_mode" not in facts:
        facts["connection_mode"] = "auto"
    node_data["facts_json"] = _facts_json_from_payload(facts)
    if not node_data.get("status"):
        node_data["status"] = "unknown"
    node = Node(**node_data)
    db.add(node)
    db.commit()
    db.refresh(node)

    if ephemeral_password:
        import contextlib
        from pathlib import Path
        secrets_dir = Path("/app/data/secrets") if Path("/app/data").exists() else Path("data/secrets")
        secrets_dir.mkdir(parents=True, exist_ok=True)
        secret_file = secrets_dir / f"node_{node.id}.secret"
        secret_file.write_text(ephemeral_password, encoding="utf-8")
        with contextlib.suppress(Exception):
            os.chmod(secret_file, 0o600)
        node.ssh_secret_ref = f"file://{secret_file}"
        node.auth_mode = "password"
        from ..orchestrator.remote import bootstrap_node_authorized_keys, get_or_create_cluster_ssh_key
        key_path, _ = get_or_create_cluster_ssh_key()
        node.ssh_key_path = str(key_path)
        with contextlib.suppress(Exception):
            bootstrap_node_authorized_keys(node, ephemeral_password)
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
    if "name" in updates:
        updates["name"] = str(updates["name"] or "").strip()
        if not updates["name"]:
            raise HTTPException(status_code=422, detail="Node name is required")
        if _node_name_collision(db, cluster_id=int(updates.get("cluster_id", node.cluster_id)), name=updates["name"], exclude_id=node.id):
            raise HTTPException(status_code=409, detail="Node name already exists in this cluster")
    if "host" in updates:
        updates["host"] = str(updates["host"] or "").strip()
        if not updates["host"]:
            raise HTTPException(status_code=422, detail="Node host is required")
    if "ssh_user" in updates:
        updates["ssh_user"] = str(updates["ssh_user"] or "").strip() or "ubuntu"

    az = updates.pop("az", None)
    if az is not None and not updates.get("availability_zone"):
        updates["availability_zone"] = az
    monitoring_port = updates.pop("monitoring_port", None)
    if monitoring_port is not None and "monitor_port" not in updates:
        updates["monitor_port"] = monitoring_port
    instance_id = updates.pop("instance_id", None)
    if instance_id is not None and "cloud_instance_id" not in updates:
        updates["cloud_instance_id"] = instance_id
    resource_id = updates.pop("resource_id", None)
    if resource_id is not None and "cloud_resource_id" not in updates:
        updates["cloud_resource_id"] = resource_id
    ami_id = updates.pop("ami_id", None)
    if ami_id is not None and "cloud_image_id" not in updates:
        updates["cloud_image_id"] = ami_id
    if "ingress_ports" in updates:
        updates["ingress_ports"] = _normalize_ingress_ports(updates["ingress_ports"])
    if "provider" not in updates and str(updates.get("environment") or "").lower() in {"aws", "gcp"}:
        updates["provider"] = str(updates["environment"]).lower()

    private_key = updates.pop("ssh_private_key", None)
    ephemeral_password = updates.pop("ssh_password", None)
    secret_ref = updates.pop("secret_ref", None)
    ssh_host_key_fingerprint = updates.pop("ssh_host_key_fingerprint", None)
    ssh_known_hosts_ref = updates.pop("ssh_known_hosts_ref", None)
    if secret_ref is not None and "ssh_secret_ref" not in updates:
        updates["ssh_secret_ref"] = secret_ref
    if ssh_host_key_fingerprint is not None and "host_key_fingerprint" not in updates:
        updates["host_key_fingerprint"] = ssh_host_key_fingerprint
    if ssh_known_hosts_ref is not None and "known_hosts_ref" not in updates:
        updates["known_hosts_ref"] = ssh_known_hosts_ref
    # Blank credential fields mean "retain existing" in the cPlatform editor;
    # clearing a reference requires an explicit lifecycle action, never an
    # accidental empty form submission.
    for secret_field in ("ssh_secret_ref", "ssh_key_path"):
        if updates.get(secret_field) in ("", "***"):
            updates.pop(secret_field, None)
    facts = updates.pop("facts", None)
    # Never persist request-scoped key/password material.  A caller may use
    # these values for a one-shot probe, but subsequent jobs require the
    # persisted secret reference and host-key fingerprint.
    if private_key is not None or ephemeral_password is not None:
        import json as _json

        try:
            current = _json.loads(node.facts_json or "{}")
        except Exception:
            current = {}
        if not isinstance(current, dict):
            current = {}
        if private_key is not None:
            current["ephemeral_auth"] = "key"
        elif ephemeral_password is not None:
            current["ephemeral_auth"] = "password"
        node.facts_json = _json.dumps(current)
    if facts is not None:
        import json as _json

        try:
            current = _json.loads(node.facts_json or "{}")
        except Exception:
            current = {}
        if not isinstance(current, dict):
            current = {}
        from ..security import redact_secrets

        safe_facts = redact_secrets(facts)
        current.update(safe_facts if isinstance(safe_facts, dict) else {})
        node.facts_json = _json.dumps(current)

    for key, value in updates.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)

    if ephemeral_password:
        import contextlib
        from pathlib import Path
        secrets_dir = Path("/app/data/secrets") if Path("/app/data").exists() else Path("data/secrets")
        secrets_dir.mkdir(parents=True, exist_ok=True)
        secret_file = secrets_dir / f"node_{node.id}.secret"
        secret_file.write_text(ephemeral_password, encoding="utf-8")
        with contextlib.suppress(Exception):
            os.chmod(secret_file, 0o600)
        node.ssh_secret_ref = f"file://{secret_file}"
        node.auth_mode = "password"
        from ..orchestrator.remote import bootstrap_node_authorized_keys, get_or_create_cluster_ssh_key
        key_path, _ = get_or_create_cluster_ssh_key()
        node.ssh_key_path = str(key_path)
        with contextlib.suppress(Exception):
            bootstrap_node_authorized_keys(node, ephemeral_password)
        db.commit()
        db.refresh(node)

    record_event(
        db,
        category="lifecycle",
        level="info",
        message=f"Updated node '{node.name}'",
        node_id=node.id,
        metadata={
            "node_id": node.id,
            "updates": {
                key: value
                for key, value in payload.model_dump(exclude_none=True).items()
                if key not in {"ssh_private_key", "ssh_password"}
            },
        },
    )
    return node


@router.post("/api/nodes/{node_id}/validate", response_model=JobOut)
def validate_node_endpoint(node_id: int, db: Session = Depends(get_db)) -> DeploymentJob:
    node = _get_node(db, node_id)
    if node.host and node.host.lower() not in {"localhost", "127.0.0.1", "0.0.0.0"}:
        import contextlib
        from ..orchestrator.remote import bootstrap_node_authorized_keys, get_or_create_cluster_ssh_key
        key_path, _ = get_or_create_cluster_ssh_key()
        if not node.ssh_key_path:
            node.ssh_key_path = str(key_path)
            db.commit()
            db.refresh(node)
        with contextlib.suppress(Exception):
            bootstrap_node_authorized_keys(node)
    try:
        return validate_node(db, node)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    detach_resource_references(
        db,
        service_ids=[service.id for service in services],
        node_ids=[node.id],
    )
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
        # The node row is gone; keep the event and retain its identity in
        # metadata rather than violating the nullable audit FK.
        node_id=None,
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


@router.post("/api/nodes/{node_id}/connection/probe", response_model=NodeConnectionProbeOut)
def probe_node_connection_endpoint(
    node_id: int,
    payload: NodeConnectionProbeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Probe using request-scoped key/password material only.

    The route deliberately does not update the node, emit an event containing
    payload fields, or return command output that could contain a credential.
    Reusable jobs still require the node's reference-only credential and
    fingerprint fields.
    """

    node = _get_node(db, node_id)
    from ..security import redact_text

    secret_values = tuple(
        value for value in (payload.ssh_private_key, payload.ssh_password) if value
    )
    try:
        result = probe_node_connection(
            node,
            ephemeral_key=payload.ssh_private_key,
            ephemeral_password=payload.ssh_password,
        )
    except Exception as exc:
        # Transport/adapter exceptions are terminal target failures, not API
        # 500s.  Never echo the exception's request-scoped credential text.
        result = {
            "ssh_ok": False,
            "docker_ok": False,
            "connection_mode": "ssh",
            "probed_at": datetime.utcnow().isoformat() + "Z",
            "detail": str(exc) or "remote probe failed",
        }
    result["ssh_ok"] = bool(result.get("ssh_ok"))
    result["docker_ok"] = bool(result.get("docker_ok"))
    result["detail"] = redact_text(str(result.get("detail") or ""), secrets=secret_values)[:200]
    return result


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


@router.get("/api/nodes/{node_id}/live-status", response_model=NodeServicesLiveStatusOut)
def node_services_live_status_endpoint(
    node_id: int,
    via: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    _get_node(db, node_id)
    force_ssh = (via or "").lower() in {"ssh", "remote"}
    try:
        return get_node_services_live_status(db, node_id, force_ssh=force_ssh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/nodes/{node_id}/inventory/cleanup", response_model=NodeInventoryCleanupOut)
def cleanup_node_inventory_endpoint(
    node_id: int,
    payload: NodeInventoryCleanupIn | None = None,
    db: Session = Depends(get_db),
) -> dict:
    _get_node(db, node_id)
    body = payload or NodeInventoryCleanupIn()
    try:
        return cleanup_node_inventory(
            db,
            node_id,
            modes=body.modes,
            dry_run=body.dry_run,
            protect_orchestrator=body.protect_orchestrator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/nodes/{node_id}/check-port-and-name")
def check_port_and_name_endpoint(
    node_id: int, port: int | None = None, name: str | None = None, db: Session = Depends(get_db)
) -> dict:
    return check_port_and_name_availability(db, node_id=node_id, port=port, name=name)
