"""Independent CLX-T1 checks for cluster editor and strict remote transport.

All remote commands are mocked or target an in-memory database.  These tests
never contact the configured API database, a Docker socket, or a real host.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import Cluster, Node, OperationalEvent, ServiceInstance  # noqa: E402
from platformops.schemas import ClusterCreate, ClusterUpdate, NodeCreate, NodeUpdate  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def known_hosts(tmp_path: Path) -> tuple[Path, str]:
    from platformops.orchestrator.remote import _fingerprint

    key = base64.b64encode(b"clx-t1-deterministic-ed25519-key").decode("ascii")
    path = tmp_path / "known_hosts"
    path.write_text(f"platformops-ssh-target ssh-ed25519 {key}\n", encoding="utf-8")
    return path, _fingerprint(path.read_text(encoding="utf-8"))


def _cluster(db: Session, name: str = "clx-cluster") -> Cluster:
    row = Cluster(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _remote_node(db: Session, cluster: Cluster, known_hosts: tuple[Path, str]) -> Node:
    path, fingerprint = known_hosts
    row = Node(
        cluster_id=cluster.id,
        name="remote-node",
        host="platformops-ssh-target",
        environment="aws",
        provider="dc",
        auth_mode="ssh_key",
        ssh_secret_ref="env://CLX_T1_SSH_SECRET",
        host_key_fingerprint=fingerprint,
        known_hosts_ref=f"file://{path}",
        facts_json=json.dumps({"connection_mode": "ssh"}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_cluster_editor_round_trip_masks_and_retain_replace_secrets(db: Session):
    from platformops.routers import clusters

    created = clusters.create_cluster(
        ClusterCreate(
            name="  editor-cluster  ",
            description="all fields",
            cluster_type="kubernetes",
            variant="edge",
            role="worker",
            repo_url="https://example.invalid/repo",
            repo_token="repo-token-clx-t1",
            registry_user="operator",
            registry_password="registry-password-clx-t1",
        ),
        db,
    )
    assert created.name == "editor-cluster"
    assert created.repo_token == "***"
    assert created.registry_password == "***"
    row = db.scalar(select(Cluster).where(Cluster.name == "editor-cluster"))
    assert row is not None
    assert row.repo_token == "repo-token-clx-t1"
    assert row.registry_password == "registry-password-clx-t1"

    retained = clusters.update_cluster(
        row.id,
        ClusterUpdate(description="edited", repo_token="", registry_password="***"),
        db,
    )
    assert retained.description == "edited"
    db.refresh(row)
    assert row.repo_token == "repo-token-clx-t1"
    assert row.registry_password == "registry-password-clx-t1"

    replaced = clusters.update_cluster(
        row.id,
        ClusterUpdate(repo_token="repo-token-replaced", registry_password="registry-password-replaced"),
        db,
    )
    assert replaced.repo_token == "***"
    assert replaced.registry_password == "***"
    db.refresh(row)
    assert row.repo_token == "repo-token-replaced"
    assert row.registry_password == "registry-password-replaced"

    events = list(db.scalars(select(OperationalEvent)).all())
    assert all("repo-token-replaced" not in event.message for event in events)
    assert all("registry-password-replaced" not in event.metadata_json for event in events)


def test_node_editor_retains_reference_and_never_persists_request_credentials(
    db: Session, known_hosts: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    from platformops.routers import nodes

    cluster = _cluster(db)
    path, fingerprint = known_hosts
    secret = "EPHEMERAL-CLX-T1-PRIVATE-KEY"
    node = nodes.create_node(
        NodeCreate(
            cluster_id=cluster.id,
            name="remote-node",
            host="platformops-ssh-target",
            environment="aws",
            ssh_private_key=secret,
            host_key_fingerprint=fingerprint,
            known_hosts_ref=f"file://{path}",
            facts={"connection_mode": "ssh", "operator_note": "safe"},
        ),
        db,
    )
    assert node.ssh_key_path == ""
    assert secret not in node.facts_json
    assert node.ssh_secret_ref == ""
    assert node.host_key_fingerprint == fingerprint
    assert node.known_hosts_ref == f"file://{path}"

    nodes.update_node(node.id, NodeUpdate(ssh_key_path="", ssh_secret_ref=""), db)
    db.refresh(node)
    assert node.ssh_key_path == ""
    assert node.ssh_secret_ref == ""

    nodes.update_node(node.id, NodeUpdate(ssh_secret_ref="env://CLX_T1_SSH_SECRET"), db)
    db.refresh(node)
    assert node.ssh_secret_ref == "env://CLX_T1_SSH_SECRET"

    monkeypatch.setattr(nodes, "probe_node_connection", lambda *_a, **_kw: {
        "ssh_ok": False,
        "docker_ok": False,
        "detail": f"credential={secret}",
    })
    result = nodes.probe_node_connection_endpoint(
        node.id,
        SimpleNamespace(ssh_private_key=secret, ssh_password=None),
        db,
    )
    assert secret not in json.dumps(result)
    assert secret not in node.facts_json
    assert all(secret not in event.metadata_json for event in db.scalars(select(OperationalEvent)).all())


def test_strict_adapter_pins_fingerprint_and_cleans_key_and_password_files(
    known_hosts: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from platformops.orchestrator import remote

    path, fingerprint = known_hosts
    ephemeral = tmp_path / "ephemeral"
    monkeypatch.setenv("PLATFORMOPS_EPHEMERAL_DIR", str(ephemeral))
    monkeypatch.setenv("CLX_T1_SSH_SECRET", "REF-SECRET-DO-NOT-LEAK")
    node = SimpleNamespace(
        host="platformops-ssh-target",
        ssh_user="root",
        ssh_secret_ref="env://CLX_T1_SSH_SECRET",
        auth_mode="ssh_key",
        host_key_fingerprint=fingerprint,
        known_hosts_ref=f"file://{path}",
    )

    with remote.ssh_command(node, ["printf", "%s", "probe"]) as command:
        assert "StrictHostKeyChecking=yes" in command.argv
        assert f"UserKnownHostsFile={path}" in command.argv
        assert "REF-SECRET-DO-NOT-LEAK" not in " ".join(command.argv)
        assert all("REF-SECRET-DO-NOT-LEAK" not in value for value in command.env.values()) is False
        key_paths = [Path(command.argv[i + 1]) for i, value in enumerate(command.argv[:-1]) if value == "-i"]
        assert key_paths and key_paths[0].is_file()
        assert key_paths[0].read_text(encoding="utf-8").strip() == "REF-SECRET-DO-NOT-LEAK"
    assert not list(ephemeral.glob("*"))

    password = "REF-PASSWORD-DO-NOT-LEAK"
    node.auth_mode = "password"
    node.ssh_secret_ref = ""
    with remote.ssh_command(node, "true", ephemeral_password=password) as command:
        joined = " ".join(command.argv)
        assert "StrictHostKeyChecking=yes" in joined
        assert password not in joined
        assert "PasswordAuthentication=yes" in joined
        assert Path(command.env["PLATFORMOPS_SSH_PASSWORD_FILE"]).read_text(encoding="utf-8") == password
        assert password not in command.env.get("SSH_ASKPASS", "")
    assert not list(ephemeral.glob("*"))


def test_strict_adapter_rejects_bad_fingerprint_and_remote_probe_has_no_local_fallback(
    known_hosts: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    from platformops.orchestrator import remote
    from platformops.orchestrator.node import probe_node_connection

    path, fingerprint = known_hosts
    node = SimpleNamespace(
        host="platformops-ssh-target",
        ssh_user="root",
        ssh_key_path="",
        ssh_secret_ref="",
        auth_mode="ssh_key",
        host_key_fingerprint=fingerprint[:-1] + ("A" if fingerprint[-1] != "A" else "B"),
        known_hosts_ref=f"file://{path}",
        facts_json=json.dumps({"connection_mode": "ssh"}),
        environment="aws",
    )
    with pytest.raises(remote.RemoteAuthError, match="does not match"):
        with remote.ssh_command(node, "true"):
            pass

    monkeypatch.setattr(remote, "run_ssh", lambda *_a, **_kw: (_ for _ in ()).throw(
        remote.RemoteAuthError("configured host key fingerprint does not match known host")
    ))
    result = probe_node_connection(node)
    assert result["ssh_ok"] is False
    assert result["docker_ok"] is False
    assert "local" not in str(result.get("detail", "")).lower()


@pytest.mark.parametrize(
    ("failure", "detail"),
    [
        (SimpleNamespace(returncode=255, stdout="", stderr="Permission denied"), "permission denied"),
        (TimeoutError("connect timeout"), "timeout"),
    ],
)
def test_remote_credential_and_timeout_failures_are_terminal_without_local_fallback(
    known_hosts: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, failure, detail: str
):
    from platformops.orchestrator import remote
    from platformops.orchestrator.node import probe_node_connection

    path, fingerprint = known_hosts
    node = SimpleNamespace(
        host="platformops-ssh-target",
        ssh_user="root",
        ssh_key_path="",
        ssh_secret_ref="",
        auth_mode="ssh_key",
        host_key_fingerprint=fingerprint,
        known_hosts_ref=f"file://{path}",
        facts_json=json.dumps({"connection_mode": "ssh"}),
        environment="aws",
    )
    if isinstance(failure, BaseException):
        monkeypatch.setattr(remote, "run_ssh", lambda *_a, **_kw: (_ for _ in ()).throw(failure))
    else:
        monkeypatch.setattr(remote, "run_ssh", lambda *_a, **_kw: failure)
    result = probe_node_connection(node)
    assert result["ssh_ok"] is False
    assert result["docker_ok"] is False
    assert detail in str(result.get("detail", "")).lower()
    assert "local" not in str(result.get("detail", "")).lower()


def test_remote_discovery_rejects_provider_without_pinned_host_contract(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    from platformops.routers import nodes

    cluster = _cluster(db, "provider-clx-t1")
    node = Node(
        cluster_id=cluster.id,
        name="provider-node",
        host="provider-unavailable.invalid",
        environment="aws",
        provider="unsupported-provider",
        facts_json=json.dumps({"connection_mode": "ssh"}),
    )
    db.add(node)
    db.commit()
    with pytest.raises(HTTPException) as failed:
        nodes.discover_infrastructure_endpoint(node.id, db)
    assert failed.value.status_code == 400
    assert "fingerprint" in str(failed.value.detail).lower()


def test_service_contract_rejects_inline_secret_and_preserves_canonical_identity(db: Session):
    from platformops.orchestrator.service.impl import create_service_instance

    cluster = _cluster(db, "service-clx-t1")
    node = Node(cluster_id=cluster.id, name="node", host="localhost", volume_root="/tmp/clx-t1")
    db.add(node)
    db.commit()
    with pytest.raises(ValueError, match="inline secret material"):
        create_service_instance(
            db,
            node=node,
            service_key="redis-core",
            contract_overrides={"environment": {"password": "INLINE-CLX-T1"}},
        )
    assert db.scalar(select(ServiceInstance).where(ServiceInstance.node_id == node.id)) is None


def test_node_and_cluster_delete_blockers_report_order_and_allow_empty_delete(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    from platformops.routers import clusters, nodes

    cluster = _cluster(db, "delete-clx-t1")
    monkeypatch.setattr(nodes, "_bootstrap_ai_orchestrator_if_needed", lambda *_args: None)
    node = nodes.create_node(NodeCreate(cluster_id=cluster.id, name="node", host="localhost"), db)
    with pytest.raises(HTTPException) as blocked:
        clusters.delete_cluster(cluster.id, db=db)
    assert blocked.value.status_code == 409
    assert "active_children" in blocked.value.detail

    nodes.delete_node(node.id, db=db)
    result = clusters.delete_cluster(cluster.id, db=db)
    assert result == {"status": "deleted", "cascaded_nodes": 0, "cascaded_services": 0}
