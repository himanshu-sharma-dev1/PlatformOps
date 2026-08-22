from __future__ import annotations

import io
import hashlib
import json
import re
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


def _stateful_runtime(monkeypatch: pytest.MonkeyPatch, states: dict[str, str]):
    """A target-bound Redis double that exposes the observable runtime contract."""
    from platformops.orchestrator import docker_runtime

    counts = {"writes": [], "restarts": [], "reloads": [], "config_get": []}

    def exec_container(container: str, args: list[str]):
        content = states[container]
        if args[0] == "cat":
            return True, content, ""
        if args[-1] == "PING":
            return True, "PONG\n", ""
        if args[-2:-1] == ["GET"]:
            directive = args[-1]
            counts["config_get"].append(directive)
            values = {}
            for line in content.splitlines():
                parts = line.split(None, 1)
                if len(parts) == 2:
                    values[parts[0].lower()] = parts[1].strip()
            value = values.get(directive.lower(), "")
            if directive.lower() == "maxmemory":
                match = re.fullmatch(r"(\d+)([kmgt])?b?", value.lower().strip())
                if match:
                    value = str(int(match.group(1)) * {None: 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[match.group(2)])
            return True, f"{directive}\n{value}\n", ""
        raise AssertionError(args)

    def write_container_file(container: str, _path: str, content: str):
        counts["writes"].append(content)
        states[container] = content
        return True, ""

    def restart_container(container: str, **_kwargs):
        counts["restarts"].append(container)
        return True, ""

    def reload_container(container: str, **_kwargs):
        counts["reloads"].append(container)
        return True, ""

    monkeypatch.setattr(docker_runtime, "exec_container", exec_container)
    monkeypatch.setattr(docker_runtime, "write_container_file", write_container_file)
    monkeypatch.setattr(docker_runtime, "restart_container", restart_container)
    monkeypatch.setattr(docker_runtime, "reload_container", reload_container)
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
    rename_metadata = json.loads(rename_event.metadata_json)
    assert {
        key: rename_metadata[key]
        for key in ("action", "actor", "snapshot_id", "old_name", "new_name", "version")
    } == {
        "action": "renamed",
        "actor": "bob",
        "snapshot_id": second.id,
        "old_name": "baseline-v1",
        "new_name": "changed",
        "version": 2,
    }
    assert rename_metadata["content_hash"] == hashlib.sha256(baseline.encode()).hexdigest()


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


def test_workspace_checkpoint_source_capabilities_and_snapshot_pages(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    baseline = "# baseline\nmaxmemory 2mb\nappendonly no\n"
    _fake_runtime(monkeypatch, {redis_service.container_name: baseline})
    first = config.create_config_snapshot(db, redis_service, name="baseline", requested_by="alice")
    second = config.create_config_snapshot(db, redis_service, name="changed", requested_by="alice", content_override=baseline.replace("2mb", "4mb"))
    third = config.create_config_snapshot(db, redis_service, name="backup", requested_by="bob", content_override=baseline)

    latest = config.config_workspace(db, redis_service, source="latest_snapshot")
    assert latest["content_source"] == "latest_snapshot"
    assert latest["content"] == third.content
    assert latest["config_capabilities"]["snapshot_enabled"] is True
    assert latest["config_capabilities"]["peer_sync_enabled"] is False
    assert latest["target_identity"] == {
        "service_id": redis_service.id,
        "service_key": "redis-core",
        "service_name": redis_service.name,
        "node_id": redis_service.node_id,
        "node_name": redis_service.node.name,
        "node_host": "localhost",
        "connection_mode": "local",
        "container_name": redis_service.container_name,
        "runtime_config_path": latest["config_path"],
    }
    with pytest.raises(ValueError, match="Invalid config source"):
        config.config_workspace(db, redis_service, source="database")

    page = config.list_config_snapshots_page(db, redis_service, limit=2, offset=1)
    assert page["total"] == 3
    assert [item.version for item in page["items"]] == [2, 1]
    assert page["has_more"] is False
    assert config.list_config_snapshots_page(db, redis_service, source_filter="pre-apply")["total"] == 0
    search = config.list_config_snapshots_page(db, redis_service, search="back")
    assert [item.id for item in search["items"]] == [third.id]
    assert config.get_config_snapshot_detail(db, first)["content_hash"] == hashlib.sha256(first.content.encode()).hexdigest()


def test_timeline_is_deterministic_and_supports_action_actor_search_and_pagination(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    baseline = "maxmemory 2mb\nappendonly no\n"
    desired = "maxmemory 4mb\nappendonly no\nloglevel warning\n"
    _stateful_runtime(monkeypatch, {redis_service.container_name: baseline})
    first = config.create_config_snapshot(db, redis_service, name="baseline", requested_by="alice")
    target = config.create_config_snapshot(db, redis_service, name="target", requested_by="alice", content_override=desired)
    config.rename_config_snapshot(db, target, name="renamed-target", requested_by="bob")
    result = config.apply_config_direct(db, redis_service, content=desired, apply_mode="restart", requested_by="alice")
    assert result["job"].status == "success"

    latest = config.get_config_timeline_page(db, redis_service, limit=1, offset=0)
    assert latest["total"] >= 5
    assert latest["has_more"] is True
    assert latest["items"][0]["action"] == "captured"
    assert latest["items"][0]["actor"] == "alice"
    applied = config.get_config_timeline_page(db, redis_service, action_filter="applied", actor_filter="alice")
    assert applied["total"] == 1
    assert applied["items"][0]["action"] == "applied"
    renamed = config.get_config_timeline_page(db, redis_service, action_filter="renamed", actor_filter="bob", search="Renamed")
    assert renamed["total"] == 1
    assert renamed["items"][0]["metadata"]["snapshot_id"] == target.id
    second = config.get_config_timeline_page(db, redis_service, limit=1, offset=1)
    assert second["items"][0]["id"] < latest["items"][0]["id"]
    assert set(("captured", "renamed", "applied")).issubset(set(latest["available_actions"]))
    assert first.id != target.id


def test_redis_validation_preserves_comments_order_and_rejects_boundaries(
    redis_service: ServiceInstance,
):
    from platformops.orchestrator import config

    valid = "# retained\nmaxmemory 2mb\nsave 60 1000\nappendonly no\nsave 300 10\n"
    assert config.validate_config(valid, redis_service)["ok"] is True
    assert config.validate_config("maxmemory 2mb\nmaxmemory 4mb\n", redis_service)["ok"] is False
    assert config.validate_config("maxmemory nope\n", redis_service)["ok"] is False
    assert config.validate_config("appendonly maybe\n", redis_service)["ok"] is False
    assert config.validate_config("maxmemory\n", redis_service)["ok"] is False
    assert config.validate_config("maxmemory 2mb\n\x00", redis_service)["ok"] is False
    assert config.validate_config("x" * (1_048_576 + 1), redis_service)["ok"] is False

    merged = config._merge_redis_config_text(
        "# left comment\nmaxmemory 2mb\nappendonly no\nsave 60 1000\n",
        "# right comment\nloglevel warning\nmaxmemory 4mb\n",
    )
    assert merged == "# right comment\nloglevel warning\nmaxmemory 4mb\nappendonly no\nsave 60 1000\n"


def test_stale_hash_rejects_concurrent_target_without_writes_or_false_snapshot(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    current = "maxmemory 2mb\nappendonly no\n"
    counts = _stateful_runtime(monkeypatch, {redis_service.container_name: current})
    stale_hash = hashlib.sha256(b"maxmemory 4mb\nappendonly no\n").hexdigest()
    with pytest.raises(ValueError, match="Stale config target"):
        config.apply_config_direct(
            db,
            redis_service,
            content="maxmemory 1mb\nappendonly no\n",
            apply_mode="restart",
            expected_content_hash=stale_hash,
            requested_by="alice",
        )
    assert counts["writes"] == []
    assert db.scalars(select(ConfigSnapshot)).all() == []
    event = db.scalars(select(OperationalEvent).order_by(OperationalEvent.id.desc())).first()
    assert event is not None
    metadata = json.loads(event.metadata_json)
    assert metadata["action"] == "apply_stale"
    assert metadata["expected_content_hash"] == stale_hash
    with pytest.raises(ValueError, match="SHA-256"):
        config.apply_config_direct(db, redis_service, content=current, apply_mode="restart", expected_content_hash="sha409")


def test_reload_and_restart_are_distinct_and_verify_exact_redis_runtime_values(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    import platformops.catalog as catalog
    from platformops.orchestrator import config

    monkeypatch.setattr(
        catalog,
        "rendered_contract",
        lambda *_args, **_kwargs: {
            "kind": "application",
            "runtime_config_path": "/usr/local/etc/redis/redis.conf",
        },
    )
    original = "# exact\nmaxmemory 2mb\nappendonly no\nloglevel notice\n"
    desired = "# exact\nmaxmemory 4mb\nappendonly no\nloglevel warning\n"
    counts = _stateful_runtime(monkeypatch, {redis_service.container_name: original})
    reload_result = config.apply_config_direct(db, redis_service, content=desired, apply_mode="reload")
    assert reload_result["job"].status == "success"
    assert reload_result["requested_apply_mode"] == "reload"
    assert reload_result["effective_apply_mode"] == "reload"
    assert counts["reloads"] == [redis_service.container_name]
    assert counts["restarts"] == []
    assert counts["config_get"] == ["appendonly", "loglevel", "maxmemory"]
    assert counts["writes"] == [desired]
    assert reload_result["after_snapshot"].content == desired

    restart_result = config.apply_config_direct(db, redis_service, content=original, apply_mode="restart")
    assert restart_result["job"].status == "success"
    assert counts["restarts"] == [redis_service.container_name]
    assert counts["writes"][-1] == original


def test_persistence_failure_rolls_back_runtime_and_keeps_db_state(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import config

    original = "maxmemory 2mb\nappendonly no\n"
    desired = "maxmemory 4mb\nappendonly no\n"
    counts = _stateful_runtime(monkeypatch, {redis_service.container_name: original})
    monkeypatch.setattr(config, "_persist_verified_config", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db unavailable")))
    result = config.apply_config_direct(db, redis_service, content=desired, apply_mode="restart", requested_by="alice")
    assert result["job"].status == "failed"
    assert "Persisted config state update failed" in result["job"].error
    assert "rollback=verified" in result["job"].error
    assert counts["writes"] == [desired, original]
    assert counts["restarts"] == [redis_service.container_name, redis_service.container_name]
    assert json.loads(redis_service.config_json) == {"operator_metadata": {"keep": True}}
    assert [item.source for item in db.scalars(select(ConfigSnapshot)).all()] == ["pre-apply"]
    event = db.scalars(select(OperationalEvent).order_by(OperationalEvent.id.desc())).first()
    assert event is not None
    assert json.loads(event.metadata_json)["stage"] == "persist"


def test_restore_and_migration_artifact_selected_ranked_ops_apply_and_rollback(
    db: Session, redis_service: ServiceInstance, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from platformops.orchestrator import config

    monkeypatch.setattr(config, "_migration_artifact_path", lambda _service_id, artifact_id: tmp_path / f"{artifact_id}.json")
    left_content = "# left\nmaxmemory 2mb\nappendonly no\n"
    right_content = "# right\nmaxmemory 4mb\nappendonly no\nloglevel warning\n"
    state = {redis_service.container_name: left_content}
    _stateful_runtime(monkeypatch, state)
    left = ConfigSnapshot(service_id=redis_service.id, version=1, name="left", source="manual", content=left_content)
    right = ConfigSnapshot(service_id=redis_service.id, version=2, name="right", source="manual", content=right_content)
    db.add_all([left, right])
    db.commit()
    prepared = config.prepare_config_migration(db, redis_service, left_snapshot=left, right_snapshot=right)
    artifact_path = tmp_path / f"{prepared['artifact_id']}.json"
    assert artifact_path.exists()
    assert prepared["validation"]["ok"] is True
    assert prepared["selected_configs"]["selected_1"]["snapshot"]["id"] == left.id
    assert prepared["selected_configs"]["selected_2"]["config_dict"]["maxmemory"] == "4mb"
    assert prepared["ranked_configs"]["rank_1"]["snapshot"]["id"] == right.id
    assert {item["op"] for item in prepared["migration_ops"]} >= {"replace", "add"}
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["selected_configs"] == prepared["selected_configs"]
    assert artifact["ranked_configs"] == prepared["ranked_configs"]
    assert artifact["migration_ops"] == prepared["migration_ops"]

    applied = config.apply_config_migration(db, redis_service, artifact_id=prepared["artifact_id"], apply_mode="restart")
    assert applied["job"].status == "success"
    assert state[redis_service.container_name] == prepared["final_content"]
    updated_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert updated_artifact["backup_snapshot_id"] == applied["backup_snapshot_id"]
    assert updated_artifact["applied_at"]

    restored = config.restore_config_migration(
        db,
        redis_service,
        artifact_id=prepared["artifact_id"],
        apply_mode="restart",
        expected_content_hash=hashlib.sha256(state[redis_service.container_name].encode()).hexdigest(),
    )
    assert restored["job"].status == "success"
    assert state[redis_service.container_name] == left_content
    assert restored["restored_snapshot_id"] == applied["backup_snapshot_id"]
