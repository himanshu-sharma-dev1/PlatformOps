from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base
from platformops.models import Cluster, ConfigSnapshot, Node, ServiceInstance


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
    cluster = Cluster(name="config-cluster")
    db.add(cluster)
    db.commit()
    node = Node(
        cluster_id=cluster.id,
        name="dind-node",
        host="localhost",
        environment="local",
        volume_root="/runtime/node-1",
        facts_json=json.dumps({"connection_mode": "local"}),
    )
    db.add(node)
    db.commit()
    service = ServiceInstance(
        node_id=node.id,
        service_key="redis-core",
        name="Redis Core",
        kind="infrastructure",
        container_name="node-1-redis-core",
        image="redis:7-alpine",
        config_json=json.dumps({"operator_metadata": {"keep": True}}),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _runtime(monkeypatch: pytest.MonkeyPatch, initial: str, *, fail: str = ""):
    from platformops.orchestrator import docker_runtime

    state = {"content": initial, "restarts": 0, "writes": 0}

    def exec_container(_container, args):
        if args[0] == "cat":
            return True, state["content"], ""
        if args[-1] == "PING":
            return (False, "", "simulated PING failure") if fail == "ping" and state["content"] != initial else (True, "PONG\n", "")
        if args[-2:] == ["GET", "maxmemory"]:
            return (False, "", "simulated CONFIG failure") if fail == "config" else (True, "maxmemory\n1048576\n", "")
        if args[-2:] == ["GET", "appendonly"]:
            return True, "appendonly\nno\n", ""
        raise AssertionError(args)

    def write(_container, _path, content):
        state["writes"] += 1
        if fail == "write" and state["writes"] == 1:
            return False, "simulated write failure"
        state["content"] = content
        return True, ""

    def restart(_container, **_kwargs):
        state["restarts"] += 1
        if fail == "restart" and state["restarts"] == 1:
            return False, "simulated restart failure"
        return True, ""

    monkeypatch.setattr(docker_runtime, "exec_container", exec_container)
    monkeypatch.setattr(docker_runtime, "write_container_file", write)
    monkeypatch.setattr(docker_runtime, "restart_container", restart)
    return state


def test_redis_validation_accepts_raw_syntax_and_rejects_yaml(redis_service):
    from platformops.orchestrator.config import validate_config

    assert validate_config("# retained\nmaxmemory 1mb\nappendonly no\n", redis_service)["ok"] is True
    invalid = validate_config("maxmemory: 1mb\n", redis_service)
    assert invalid["ok"] is False
    assert "invalid Redis directive" in invalid["message"]


def test_verified_redis_apply_persists_only_after_runtime_checks(db, redis_service, monkeypatch):
    from platformops.orchestrator.config import apply_config_direct

    desired = "# keep comment\nmaxmemory 1mb\nappendonly no\n"
    state = _runtime(monkeypatch, "maxmemory 2mb\nappendonly no\n")
    result = apply_config_direct(db, redis_service, content=desired, apply_mode="restart")

    assert result["job"].status == "success"
    from platformops.schemas import ConfigDirectApplyOut
    assert ConfigDirectApplyOut.model_validate(result).after_snapshot is not None
    assert state["content"] == desired
    assert result["after_snapshot"].content == desired
    stored = json.loads(redis_service.config_json)
    assert stored["rendered_config_content"] == desired
    assert stored["operator_metadata"] == {"keep": True}


@pytest.mark.parametrize("failure", ["write", "restart", "ping", "config"])
def test_failed_apply_has_no_false_persistence_or_post_snapshot(db, redis_service, monkeypatch, failure):
    from platformops.orchestrator.config import apply_config_direct

    original = "maxmemory 2mb\nappendonly no\n"
    desired = "maxmemory 1mb\nappendonly no\n"
    state = _runtime(monkeypatch, original, fail=failure)
    result = apply_config_direct(db, redis_service, content=desired, apply_mode="restart")

    assert result["job"].status == "failed"
    from platformops.schemas import ConfigDirectApplyOut
    assert ConfigDirectApplyOut.model_validate(result).after_snapshot is None
    assert result["after_snapshot"] is None
    assert "rendered_config_content" not in json.loads(redis_service.config_json)
    assert [item.source for item in db.scalars(select(ConfigSnapshot)).all()] == ["pre-apply"]
    if failure != "write":
        assert state["content"] == original
        assert "rollback=verified" in result["job"].error


def test_redis_compare_drift_and_migration_are_format_aware(db, redis_service, monkeypatch, tmp_path):
    from platformops.orchestrator import config
    from platformops.orchestrator.config import compare_config_snapshots, detect_drift, prepare_config_migration

    monkeypatch.setattr(config, "_migration_artifact_path", lambda _service_id, artifact_id: tmp_path / f"{artifact_id}.json")

    left = ConfigSnapshot(service_id=redis_service.id, version=1, name="left", source="manual", content="# base\nmaxmemory 2mb\nappendonly no\n")
    right = ConfigSnapshot(service_id=redis_service.id, version=2, name="right", source="manual", content="# target\nmaxmemory 1mb\nappendonly no\n")
    db.add_all([left, right])
    db.commit()
    compare = compare_config_snapshots(db, redis_service, left_snapshot=left, right_snapshot=right)
    assert [item["field"] for item in compare["differences"]] == ["maxmemory"]

    prepared = prepare_config_migration(db, redis_service, left_snapshot=left, right_snapshot=right)
    assert prepared["final_content"].startswith("# target\n")
    assert "maxmemory 1mb" in prepared["final_content"]
    assert prepared["validation"]["ok"] is True

    _runtime(monkeypatch, right.content)
    report = detect_drift(db, redis_service)
    assert report.status == "in-sync"


def test_capabilities_require_a_real_runtime_file_target(db, redis_service):
    from platformops.orchestrator.config import apply_config_direct, config_capabilities_for_service

    redis_service.service_key = "unknown-helper"
    redis_service.config_json = json.dumps({"environment": {"ONLY_METADATA": "1"}})
    assert config_capabilities_for_service(redis_service)["apply_enabled"] is False
    with pytest.raises(ValueError, match="No editable runtime config surface"):
        apply_config_direct(db, redis_service, content="key: value\n", apply_mode="restart")


def test_restore_uses_verified_apply_and_creates_no_false_post_snapshot(db, redis_service, monkeypatch):
    from platformops.orchestrator.config import restore_config_snapshot

    original = "maxmemory 2mb\nappendonly no\n"
    target = ConfigSnapshot(service_id=redis_service.id, version=1, name="restore-target", source="manual", content="maxmemory 1mb\nappendonly no\n")
    db.add(target)
    db.commit()
    _runtime(monkeypatch, original, fail="ping")

    job = restore_config_snapshot(db, redis_service, target)
    assert job.status == "failed"
    assert all(item.source != "post-apply" for item in db.scalars(select(ConfigSnapshot)).all())


def _remote_runtime(monkeypatch: pytest.MonkeyPatch, service: ServiceInstance, initial: str, *, fail_ping: bool = False):
    from platformops.orchestrator import config, docker_runtime

    service.node.host = "redis.remote.example"
    service.node.facts_json = json.dumps({"connection_mode": "ssh"})
    state = {"content": initial, "writes": 0, "restarts": 0}

    monkeypatch.setattr(docker_runtime, "exec_container", lambda *_a, **_k: pytest.fail("remote apply fell back to local Docker"))
    monkeypatch.setattr(docker_runtime, "write_container_file", lambda *_a, **_k: pytest.fail("remote apply wrote local Docker"))
    monkeypatch.setattr(docker_runtime, "restart_container", lambda *_a, **_k: pytest.fail("remote apply restarted local Docker"))
    monkeypatch.setattr(config, "_remote_read_container_file", lambda *_a: (state["content"], None))

    def write(_node, _container, _path, content):
        state["writes"] += 1
        state["content"] = content
        return True, ""

    def restart(_node, _container, **_kwargs):
        state["restarts"] += 1
        return True, ""

    def execute(_node, _container, args):
        if args[-1] == "PING":
            return (False, "", "remote PING failed") if fail_ping and state["content"] != initial else (True, "PONG\n", "")
        if args[-2:] == ["GET", "maxmemory"]:
            return True, "maxmemory\n1048576\n", ""
        if args[-2:] == ["GET", "appendonly"]:
            return True, "appendonly\nno\n", ""
        raise AssertionError(args)

    monkeypatch.setattr(config, "_remote_write_container_file", write)
    monkeypatch.setattr(config, "_remote_restart_container", restart)
    monkeypatch.setattr(config, "_remote_exec_container", execute)
    return state


def test_remote_apply_uses_target_bound_transaction_without_local_fallback(db, redis_service, monkeypatch):
    from platformops.orchestrator.config import apply_config_direct

    desired = "maxmemory 1mb\nappendonly no\n"
    state = _remote_runtime(monkeypatch, redis_service, "maxmemory 2mb\nappendonly no\n")
    result = apply_config_direct(db, redis_service, content=desired, apply_mode="restart")

    assert result["job"].status == "success"
    assert state == {"content": desired, "writes": 1, "restarts": 1}
    assert result["after_snapshot"].content == desired


def test_remote_verification_failure_rolls_back_exact_bytes(db, redis_service, monkeypatch):
    from platformops.orchestrator.config import apply_config_direct

    original = "# original\nmaxmemory 2mb\nappendonly no\n"
    state = _remote_runtime(monkeypatch, redis_service, original, fail_ping=True)
    result = apply_config_direct(db, redis_service, content="maxmemory 1mb\nappendonly no\n", apply_mode="restart")

    assert result["job"].status == "failed"
    assert result["after_snapshot"] is None
    assert state["content"] == original
    assert state["writes"] == 2
    assert state["restarts"] == 2
    assert "rollback=verified" in result["job"].error


def test_remote_ansible_uses_explicit_inventory_and_configured_ssh_args(
    redis_service, monkeypatch, tmp_path
):
    import subprocess
    from types import SimpleNamespace
    from platformops.orchestrator import config

    key_path = tmp_path / "remote-key"
    key_path.write_text("test-only-key", encoding="utf-8")
    redis_service.node.host = "platformops-ssh-target"
    redis_service.node.ssh_user = "ops-user"
    redis_service.node.ssh_key_path = str(key_path)
    redis_service.node.facts_json = json.dumps(
        {"connection_mode": "ssh", "ssh_port": 2222, "ssh_options": "-o StrictHostKeyChecking=no"}
    )
    captured = {}

    def run(command, **_kwargs):
        captured["command"] = command
        result_dir = Path(command[command.index("--tree") + 1])
        (result_dir / "platformops-ssh-target").write_text(
            json.dumps({"rc": 0, "stdout": base64.b64encode(b"maxmemory 2mb\n").decode()}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    content, error = config._remote_read_container_file(
        redis_service.node, redis_service.container_name, "/usr/local/etc/redis/redis.conf"
    )
    assert error is None
    assert content == "maxmemory 2mb\n"
    command = captured["command"]
    assert command[0:2] == ["ansible", "platformops-ssh-target"]
    assert command[command.index("-i") + 1] == "platformops-ssh-target,"
    assert command[command.index("-u") + 1] == "ops-user"
    assert command[command.index("-e") + 1] == "ansible_port=2222"
    assert command[command.index("--private-key") + 1] == str(key_path)
    assert command[command.index("--ssh-common-args") + 1] == "-o StrictHostKeyChecking=no"


def test_remote_bad_key_and_unsafe_host_never_fall_back_to_local_docker(
    redis_service, monkeypatch
):
    import subprocess
    from platformops.orchestrator import config, docker_runtime

    redis_service.node.host = "remote.example.test"
    redis_service.node.ssh_key_path = "/missing/secret-key"
    redis_service.node.facts_json = json.dumps({"connection_mode": "ssh"})
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("Ansible ran with a missing key"))
    monkeypatch.setattr(docker_runtime, "exec_container", lambda *_a, **_k: pytest.fail("remote read fell back locally"))
    content, error = config._read_remote_config_content(redis_service)
    assert content is None
    assert error == "Configured remote SSH key is not readable."
    assert "/missing/secret-key" not in error

    redis_service.node.host = "remote.example.test;touch-bad"
    redis_service.node.ssh_key_path = ""
    content, error = config._read_remote_config_content(redis_service)
    assert content is None
    assert "safe IPv4 address or DNS name" in error


def test_remote_existing_bad_key_failure_is_redacted_and_never_falls_back(
    redis_service, monkeypatch, tmp_path
):
    import subprocess
    from types import SimpleNamespace
    from platformops.orchestrator import config, docker_runtime

    bad_key = tmp_path / "bad-key"
    bad_key.write_text("not-a-real-private-key", encoding="utf-8")
    redis_service.node.host = "remote.example.test"
    redis_service.node.ssh_key_path = str(bad_key)
    redis_service.node.facts_json = json.dumps({"connection_mode": "ssh"})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=4,
            stdout="",
            stderr=f"Identity file {bad_key} authentication failed",
        ),
    )
    monkeypatch.setattr(
        docker_runtime,
        "exec_container",
        lambda *_a, **_k: pytest.fail("bad remote key fell back to local Docker"),
    )
    content, error = config._read_remote_config_content(redis_service)
    assert content is None
    assert "authentication failed" in error
    assert str(bad_key) not in error
    assert "***" in error


def test_remote_write_and_restart_shell_avoid_jinja_and_cover_stopped_bind_rollback(
    redis_service, monkeypatch
):
    import subprocess
    from platformops.orchestrator import config

    calls = []

    def ansible(_node, module, module_args, **_kwargs):
        calls.append((module, module_args))
        return True, "", ""

    monkeypatch.setattr(config, "_ansible_ad_hoc", ansible)
    ok, error = config._remote_write_container_file(
        redis_service.node,
        redis_service.container_name,
        "/usr/local/etc/redis/redis.conf",
        "maxmemory 2mb\n",
    )
    assert ok is True, error
    assert [call[0] for call in calls] == ["copy", "shell"]
    write_shell = calls[-1][1]
    assert "{{" not in write_shell and "}}" not in write_shell
    assert 'if [ "$running" = true ]' in write_shell
    assert 'elif [ -n "$mount_source" ]' in write_shell
    assert "docker exec -u 0" in write_shell
    assert "docker run --rm --user 0:0" in write_shell
    assert "/platformops-target" in write_shell
    assert subprocess.run(["sh", "-n", "-c", write_shell]).returncode == 0

    calls.clear()
    ok, error = config._remote_restart_container(redis_service.node, redis_service.container_name)
    assert ok is True, error
    restart_shell = calls[-1][1]
    assert "{{" not in restart_shell and "}}" not in restart_shell
    assert "json.load(sys.stdin)" in restart_shell
    assert "State" in restart_shell and "Status" in restart_shell
    assert subprocess.run(["sh", "-n", "-c", restart_shell]).returncode == 0
