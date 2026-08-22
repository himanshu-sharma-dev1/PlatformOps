"""Independent CLU-T1 contract checks for the cluster inventory surface.

These tests use an in-memory database and deterministic runtime doubles.  They
must not contact the configured API database, Docker socket, or SSH targets.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import Cluster, Node, OperationalEvent, ServiceInstance  # noqa: E402
from platformops.schemas import ClusterCreate, NodeCreate  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _node(db: Session, *, name: str = "node-1", host: str = "localhost", facts: dict | None = None) -> Node:
    cluster = Cluster(name=f"cluster-{name}")
    db.add(cluster)
    db.commit()
    node = Node(
        cluster_id=cluster.id,
        name=name,
        host=host,
        environment="local" if host == "localhost" else "aws",
        volume_root="/tmp/clu-t1",
        docker_network="clu-t1-private",
        facts_json=json.dumps(facts or {"connection_mode": "local"}),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def test_cluster_defaults_trim_input_and_reject_case_insensitive_collision(db: Session):
    from fastapi import HTTPException
    from platformops.routers import clusters

    first = clusters.create_cluster(ClusterCreate(name="  Production  "), db)
    assert first.name == "Production"
    assert first.region == "local"
    assert first.environment == "development"
    assert first.cluster_type == "standalone"
    assert first.repo_type == "github"
    assert first.repo_branch == "main"
    assert first.repo_auth == "pat"
    assert first.registry_type == "dockerhub"
    assert first.registry_auth == "password"

    with pytest.raises(HTTPException) as collision:
        clusters.create_cluster(ClusterCreate(name=" production "), db)
    assert collision.value.status_code == 409
    assert collision.value.detail == "Cluster name already exists"

    with pytest.raises(HTTPException) as invalid:
        clusters.create_cluster(ClusterCreate(name="   "), db)
    assert invalid.value.status_code == 422
    assert invalid.value.detail == "Cluster name is required"


def test_node_defaults_trim_input_and_scope_case_insensitive_collision(monkeypatch: pytest.MonkeyPatch, db: Session):
    from fastapi import HTTPException
    from platformops.routers import nodes

    cluster = Cluster(name="node-contract-cluster")
    other = Cluster(name="other-cluster")
    db.add_all([cluster, other])
    db.commit()
    # Node creation normally bootstraps the control-plane card.  This test is
    # only about node payload/default/collision behavior.
    monkeypatch.setattr(nodes, "_bootstrap_ai_orchestrator_if_needed", lambda *_args: None)

    created = nodes.create_node(NodeCreate(cluster_id=cluster.id, name="  Edge-1  "), db)
    assert created.name == "Edge-1"
    assert created.host == "localhost"
    assert created.ssh_user == "ubuntu"
    assert created.docker_network == "platformops_prod_network"
    assert json.loads(created.facts_json)["connection_mode"] == "auto"

    with pytest.raises(HTTPException) as collision:
        nodes.create_node(NodeCreate(cluster_id=cluster.id, name="edge-1"), db)
    assert collision.value.status_code == 409
    assert collision.value.detail == "Node name already exists in this cluster"

    other_node = nodes.create_node(NodeCreate(cluster_id=other.id, name="edge-1"), db)
    assert other_node.cluster_id == other.id

    with pytest.raises(HTTPException) as missing_host:
        nodes.create_node(NodeCreate(cluster_id=cluster.id, name="no-host", host=""), db)
    assert missing_host.value.status_code == 422
    assert missing_host.value.detail == "Node host is required"


def test_redis_contract_identity_and_deep_merge_preserve_runtime_fields(db: Session):
    from platformops.orchestrator.service.impl import create_service_instance, update_service_instance

    node = _node(db)
    service = create_service_instance(
        db,
        node=node,
        service_key="redis-core",
        name="Redis Core",
        contract_overrides={
            "install_mode": "MANUAL",
            "environment": {"KEEP": "yes", "nested": {"left": 1}},
            "operator_metadata": {"owner": {"team": "noc"}},
            "volumes": ["/tmp/clu-t1/extra:/extra"],
        },
    )
    before = json.loads(service.config_json)
    assert service.external_id.startswith("SERV")
    assert service.service_key == "redis-core"
    assert service.container_name == f"node-{node.id}-redis-core"
    assert service.image == "redis:7-alpine"
    assert before["command"] == "redis-server /usr/local/etc/redis/redis.conf"
    assert before["runtime_config_path"] == "/usr/local/etc/redis/redis.conf"
    assert before["healthcheck"] == {"command": "redis-cli ping"}
    assert "/data" in {item.split(":", 1)[-1].split(":", 1)[0] for item in before["volumes"]}
    assert "/var/log/redis" in {item.split(":", 1)[-1].split(":", 1)[0] for item in before["volumes"]}
    assert "/usr/local/etc/redis/redis.conf" in {
        item.split(":", 1)[-1].split(":", 1)[0] for item in before["volumes"]
    }
    assert before["install_mode"] == "manual"
    assert before["service_install"] == "MANUAL"

    updated = update_service_instance(
        db,
        service,
        contract_overrides={
            "environment": {"nested": {"right": 2}, "NEW": "value"},
            "operator_metadata": {"owner": {"service": "redis"}},
        },
    )
    after = json.loads(updated.config_json)
    assert after["environment"] == {"KEEP": "yes", "nested": {"left": 1, "right": 2}, "NEW": "value"}
    assert after["operator_metadata"] == {"owner": {"team": "noc", "service": "redis"}}
    assert after["volumes"] == before["volumes"]
    assert after["runtime_config_path"] == before["runtime_config_path"]
    assert after["healthcheck"] == before["healthcheck"]
    assert updated.external_id == service.external_id
    assert updated.container_name == service.container_name


def test_service_identity_override_and_case_insensitive_name_collision_are_deterministic(db: Session):
    from platformops.orchestrator.service.impl import create_service_instance

    node = _node(db, name="identity-node")
    with pytest.raises(ValueError, match="identity fields: container_name"):
        create_service_instance(
            db,
            node=node,
            service_key="redis-core",
            contract_overrides={"container_name": "not-canonical"},
        )
    assert db.scalar(select(ServiceInstance).where(ServiceInstance.node_id == node.id)) is None

    create_service_instance(db, node=node, service_key="redis-core", name="Redis A")
    with pytest.raises(ValueError, match="already in use"):
        create_service_instance(db, node=node, service_key="redis-core", name=" redis a ")


def test_dependency_preflight_reports_required_order_and_missing_or_stopped_states(db: Session):
    from platformops.catalog import required_dependencies
    from platformops.orchestrator.service.impl import dependency_preflight

    node = _node(db, name="deps-node")
    target = ServiceInstance(
        node_id=node.id,
        service_key="dtrain-controller",
        name="dTrain",
        kind="app",
        container_name="dtrain",
        image="example:dtrain",
        status="created",
        config_json="{}",
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    required = required_dependencies("dtrain-controller")
    result = dependency_preflight(db, target)
    assert result["ok"] is False
    assert result["required"] == required
    assert result["missing"] == required
    assert result["stopped"] == []
    assert result["message"] == (
        "Install or start these infrastructure cards first: RabbitMQ Core, Redis Core, DTrain Experiment Tracker."
    )

    redis = ServiceInstance(
        external_id="SERV-DEPS-REDIS",
        node_id=node.id,
        service_key="redis-core",
        name="Redis",
        kind="infrastructure",
        container_name="redis",
        image="redis:7-alpine",
        status="created",
        config_json="{}",
    )
    db.add(redis)
    db.commit()
    result = dependency_preflight(db, target)
    assert result["ok"] is False
    assert result["missing"] == [key for key in required if key != "redis-core"]
    assert result["stopped"] == ["redis-core"]


def _runtime_inspect(*, image: str = "redis:7-alpine", health: str = "healthy", name: str = "/node-1-redis-core"):
    return {
        "Name": name,
        "Config": {"Image": image, "Healthcheck": {"Test": ["CMD-SHELL", "redis-cli ping"]}},
        "State": {"Status": "running", "Running": True, "Health": {"Status": health}},
        "NetworkSettings": {"Networks": {"clu-t1-private": {}}},
        "Mounts": [
            {"Destination": "/data"},
            {"Destination": "/var/log/redis"},
            {"Destination": "/usr/local/etc/redis/redis.conf"},
        ],
    }


def _runtime_service(node: Node):
    return SimpleNamespace(
        id=1,
        node_id=node.id,
        service_key="redis-core",
        container_name=f"node-{node.id}-redis-core",
        image="redis:7-alpine",
        config_json=json.dumps({"healthcheck": {"command": "redis-cli ping"}}),
        node=node,
    )


def test_runtime_success_requires_healthy_and_direct_pong_and_rejects_wrong_identity(db: Session, monkeypatch):
    from platformops.orchestrator import docker_runtime
    from platformops.orchestrator.service import impl

    node = _node(db, name="runtime-node")
    service = _runtime_service(node)
    monkeypatch.setattr(impl, "_node_uses_local_docker", lambda *_args: True)
    monkeypatch.setattr(impl, "_docker_inspect_for_node", lambda *_args: (_runtime_inspect(), None, "docker_inspect"))
    monkeypatch.setattr(docker_runtime, "exec_container", lambda *_args: (True, "NOPE\n", ""))
    failed = impl._verify_service_runtime(object(), service, timeout_seconds=0.11, poll_interval_seconds=0.05)
    assert failed["ok"] is False
    assert failed["readiness"] == "redis-cli:pending"
    assert "readiness=redis-cli:pending" in failed["error"]

    monkeypatch.setattr(
        impl,
        "_docker_inspect_for_node",
        lambda *_args: (_runtime_inspect(image="redis:6-alpine"), None, "docker_inspect"),
    )
    mismatch = impl._verify_service_runtime(object(), service, timeout_seconds=0.2, poll_interval_seconds=0.05)
    assert mismatch["ok"] is False
    assert mismatch["error"] == "runtime image mismatch: expected redis:7-alpine, observed redis:6-alpine"


def test_remote_runtime_inspection_uses_ssh_target_without_local_fallback(db: Session, monkeypatch):
    from platformops.orchestrator.service import impl

    node = _node(db, name="remote-runtime", host="remote.example")
    node.facts_json = json.dumps({"connection_mode": "ssh"})
    db.commit()
    calls: list[str] = []
    monkeypatch.setattr(impl, "_docker_inspect_remote", lambda *_args: (calls.append("ssh") or ({"Name": "/x"}, None)))
    monkeypatch.setattr(impl, "_docker_inspect_local", lambda *_args: pytest.fail("local Docker fallback used"))

    inspect, error, source = impl._docker_inspect_for_node(node, "x")
    assert inspect == {"Name": "/x"}
    assert error is None
    assert source == "docker_inspect_ssh"
    assert calls == ["ssh"]


def test_runtime_events_are_redacted_and_scoped_to_canonical_service(db: Session):
    from platformops.orchestrator.common import record_event

    node = _node(db, name="audit-node")
    service = ServiceInstance(
        node_id=node.id,
        service_key="redis-core",
        name="Redis Core",
        kind="infrastructure",
        container_name="node-1-redis-core",
        image="redis:7-alpine",
        status="running",
        config_json="{}",
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    event = record_event(
        db,
        category="deployment",
        service_id=service.id,
        node_id=node.id,
        message=f"deploy {service.external_id or service.id}",
        metadata={"service_id": service.id, "container_name": service.container_name, "token": "secret"},
    )
    stored = json.loads(event.metadata_json)
    assert event.service_id == service.id
    assert event.node_id == node.id
    assert stored["service_id"] == service.id
    assert stored["container_name"] == service.container_name
    assert stored["token"] == "***"
    assert db.scalar(select(OperationalEvent).where(OperationalEvent.service_id == service.id)) is event
