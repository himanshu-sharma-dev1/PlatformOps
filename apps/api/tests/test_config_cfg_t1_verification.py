from __future__ import annotations

import io
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base
from platformops.models import Cluster, ConfigSnapshot, Node, OperationalEvent, ServiceInstance


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def redis_service(db: Session) -> ServiceInstance:
    cluster = Cluster(name="cfg-t1-cluster")
    db.add(cluster)
    db.commit()
    node = Node(
        cluster_id=cluster.id,
        name="cfg-t1-node",
        host="localhost",
        environment="local",
        volume_root="/runtime/cfg-t1",
        facts_json=json.dumps({"connection_mode": "local"}),
    )
    db.add(node)
    db.commit()
    service = ServiceInstance(
        node_id=node.id,
        service_key="redis-core",
        name="CFG-T1 Redis",
        kind="infrastructure",
        container_name="cfg-t1-redis",
        image="redis:7-alpine",
        config_json=json.dumps({"operator_metadata": {"keep": True}}),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _fake_runtime(monkeypatch: pytest.MonkeyPatch, states: dict[str, str], *, mismatch: bool = False):
    from platformops.orchestrator import docker_runtime

    counts = {"writes": [], "restarts": []}

    def exec_container(container: str, args: list[str]):
        content = states[container]
        if args[0] == "cat":
            return True, content, ""
        if args[-1] == "PING":
            return True, "PONG\n", ""
        if args[-2:] == ["GET", "maxmemory"]:
            value = "999" if mismatch else "2097152"
            return True, f"maxmemory\n{value}\n", ""
        if args[-2:] == ["GET", "appendonly"]:
            return True, "appendonly\nno\n", ""
        raise AssertionError(args)

    def write_container_file(container: str, _path: str, content: str):
        counts["writes"].append(container)
        states[container] = content
        return True, ""

    def restart_container(container: str, **_kwargs):
        counts["restarts"].append(container)
        return True, ""

    monkeypatch.setattr(docker_runtime, "exec_container", exec_container)
    monkeypatch.setattr(docker_runtime, "write_container_file", write_container_file)
    monkeypatch.setattr(docker_runtime, "restart_container", restart_container)
    return counts


def test_workspace_preserves_live_bytes_hash_and_truthfully_reports_read_failure(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    content = "# keep CRLF bytes\r\nmaxmemory 2mb\r\nappendonly no\r\n"
    _fake_runtime(monkeypatch, {redis_service.container_name: content})
    workspace = config.config_workspace(db, redis_service)
    assert workspace["content"] == content
    assert workspace["content_source"] == "live"
    assert workspace["live_read_ok"] is True
    assert workspace["content_hash"] == hashlib.sha256(content.encode()).hexdigest()
    assert workspace["config_source_label"] == "Live config"

    from platformops.orchestrator import docker_runtime

    monkeypatch.setattr(
        docker_runtime,
        "exec_container",
        lambda _container, _args: (False, "", "permission denied: redis.conf"),
    )
    failed = config.config_workspace(db, redis_service)
    assert failed["content_source"] == "runtime_unavailable"
    assert failed["live_read_ok"] is False
    assert "permission denied" in failed["live_read_error"]
    assert "Runtime unavailable" in failed["config_source_label"]
    assert "Runtime read failed" in failed["message"]


def test_contract_override_is_deep_merged_and_snapshot_mutations_are_audited(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    import platformops.catalog as catalog
    from platformops.orchestrator import config

    contract = {
        "runtime_config_path": "/usr/local/etc/redis/redis.conf",
        "nested": {"keep": {"left": 1, "right": 2}, "replace": "catalog"},
    }
    monkeypatch.setattr(catalog, "rendered_contract", lambda *_args, **_kwargs: contract)
    redis_service.config_json = json.dumps({"nested": {"keep": {"right": 9, "new": 3}, "replace": "instance"}})
    merged = config._merged_service_contract(redis_service)
    assert merged["nested"] == {
        "keep": {"left": 1, "right": 9, "new": 3},
        "replace": "instance",
    }

    baseline = "# exact\r\nmaxmemory 2mb\r\nappendonly no\r\n"
    _fake_runtime(monkeypatch, {redis_service.container_name: baseline})
    first = config.create_config_snapshot(db, redis_service, name="baseline", requested_by="alice")
    second = config.create_config_snapshot(db, redis_service, name="baseline", requested_by="alice")
    assert first.version == 1
    assert second.version == 2
    assert second.name == "baseline-v1"
    assert first.content == baseline
    events = list(
        db.scalars(
            select(OperationalEvent)
            .where(OperationalEvent.category == "config", OperationalEvent.service_id == redis_service.id)
            .order_by(OperationalEvent.id)
        )
    )
    assert len(events) == 2
    assert [json.loads(event.metadata_json)["action"] for event in events] == ["captured", "captured"]
    assert all(json.loads(event.metadata_json)["actor"] == "alice" for event in events)

    renamed = config.rename_config_snapshot(db, second, name="changed", requested_by="bob")
    assert renamed.name == "changed"
    rename_event = db.scalars(select(OperationalEvent).order_by(OperationalEvent.id.desc())).first()
    assert rename_event is not None
    assert json.loads(rename_event.metadata_json) == {
        "action": "renamed",
        "actor": "bob",
        "snapshot_id": second.id,
        "old_name": "baseline-v1",
        "new_name": "changed",
        "version": 2,
    }


def test_peer_sync_is_same_key_only_and_applies_to_peer_target(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    peer_node = Node(
        cluster_id=redis_service.node.cluster_id,
        name="cfg-t1-peer-node",
        host="localhost",
        environment="local",
        volume_root="/runtime/cfg-t1-peer",
        facts_json=json.dumps({"connection_mode": "local"}),
    )
    db.add(peer_node)
    db.commit()
    peer = ServiceInstance(
        external_id="cfg-t1-peer",
        node_id=peer_node.id,
        service_key="redis-core",
        name="CFG-T1 Redis Peer",
        kind="infrastructure",
        container_name="cfg-t1-redis-peer",
        image="redis:7-alpine",
        config_json="{}",
    )
    db.add(peer)
    db.commit()
    db.refresh(peer)

    content = "maxmemory 2mb\nappendonly no\n"
    counts = _fake_runtime(
        monkeypatch,
        {redis_service.container_name: content, peer.container_name: "maxmemory 1mb\nappendonly no\n"},
    )
    result = config.sync_peer_config(db, redis_service, peer_id=peer.id, apply_mode="restart", requested_by="alice")
    assert result["job"].status == "success"
    assert result["after_snapshot"].content == content
    assert counts["writes"] == [peer.container_name]
    assert counts["restarts"] == [peer.container_name]

    wrong_key = ServiceInstance(
        external_id="cfg-t1-wrong-peer",
        node_id=peer_node.id,
        service_key="postgres-core",
        name="Wrong Peer",
        kind="infrastructure",
        container_name="cfg-t1-postgres-peer",
        image="postgres:16-alpine",
        config_json="{}",
    )
    db.add(wrong_key)
    db.commit()
    with pytest.raises(ValueError, match="same service type"):
        config.sync_peer_config(db, redis_service, peer_id=wrong_key.id)


def test_failed_verified_runtime_apply_records_failure_without_post_snapshot(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    original = "maxmemory 2mb\nappendonly no\n"
    desired = "maxmemory 1mb\nappendonly no\n"
    _fake_runtime(monkeypatch, {redis_service.container_name: original}, mismatch=True)
    result = config.apply_config_direct(db, redis_service, content=desired, apply_mode="restart", requested_by="alice")
    assert result["job"].status == "failed"
    assert result["after_snapshot"] is None
    assert [snapshot.source for snapshot in db.scalars(select(ConfigSnapshot)).all()] == ["pre-apply"]
    event = db.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.category == "config", OperationalEvent.service_id == redis_service.id)
        .order_by(OperationalEvent.id.desc())
    ).first()
    assert event is not None
    metadata = json.loads(event.metadata_json)
    assert metadata["action"] == "apply_failed"
    assert metadata["actor"] == "alice"
    assert metadata["rollback"] == "verified"


def test_atomic_runtime_config_stage_is_readable_by_non_root_service(
    monkeypatch: pytest.MonkeyPatch,
):
    """Redis restarts as an unprivileged user and must reopen the staged file."""
    from platformops.orchestrator import docker_runtime

    captured: dict[str, object] = {}

    class Container:
        attrs = {"State": {"Running": True}}

        def reload(self):
            return None

        def put_archive(self, path: str, payload: bytes):
            captured["path"] = path
            captured["payload"] = payload
            return True

        def exec_run(self, _args, **_kwargs):
            return SimpleNamespace(exit_code=0, output=b"")

    class Client:
        def __init__(self):
            self.containers = self

        def get(self, _name):
            return Container()

        def close(self):
            return None

    class Docker:
        def from_env(self):
            return Client()

    monkeypatch.setattr(docker_runtime, "_docker_module", lambda: Docker())
    ok, error = docker_runtime.write_container_file("redis", "/tmp/redis.conf", "maxmemory 1mb\n")
    assert ok is True, error
    archive = io.BytesIO(captured["payload"])
    with tarfile.open(fileobj=archive, mode="r:") as tar:
        member = tar.getmembers()[0]
    assert member.mode & 0o044, "staged config must be readable by the Redis service user"
