"""Focused parity/regression tests for the PlatformOps hardening work.

These tests deliberately use an isolated in-memory SQLite session.  Runtime
Docker, SSH, Loki, and the configured application database are never touched.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import Cluster, Node, ServiceInstance  # noqa: E402


@pytest.fixture
def db() -> Any:
    """Yield a temporary SQLite session, never the configured SessionLocal."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_node(
    db: Session,
    *,
    name: str = "test-node",
    host: str = "localhost",
    environment: str = "local",
    facts: dict[str, Any] | None = None,
) -> Node:
    cluster = Cluster(name=f"cluster-{name}")
    db.add(cluster)
    db.commit()
    node = Node(
        cluster_id=cluster.id,
        name=name,
        host=host,
        environment=environment,
        volume_root="/tmp/platformops-parity",
        facts_json=json.dumps(facts or {}),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def test_service_config_update_deep_merges_nested_fields_and_preserves_install_mode(db: Session):
    from platformops.orchestrator.service.impl import (
        create_service_instance,
        update_service_instance,
    )
    from platformops.schemas import ServiceOut

    node = _make_node(db)
    service = create_service_instance(
        db,
        node=node,
        service_key="rabbitmq-core",
        contract_overrides={
            "environment": {
                "RABBITMQ_DEFAULT_USER": "operator",
                "CUSTOM_KEEP": "keep-me",
            },
            "healthcheck": {"command": "custom-healthcheck"},
            "operator_metadata": {"nested": {"keep": True}},
            "install_mode": "MANUAL",
        },
    )
    before = json.loads(service.config_json)
    assert before["install_mode"] == "manual"
    assert before["service_install"] == "MANUAL"
    assert before["environment"]["RABBITMQ_DEFAULT_PASS"] == "platformops"
    assert before["healthcheck"]["command"] == "custom-healthcheck"

    updated = update_service_instance(
        db,
        service,
        contract_overrides={"environment": {"CUSTOM_NEW": "new-value"}},
    )
    after = json.loads(updated.config_json)

    # The update changes only the requested nested leaf. Catalog defaults and
    # unrelated operator fields remain available, including manual mode.
    assert after["environment"]["RABBITMQ_DEFAULT_USER"] == "operator"
    assert after["environment"]["CUSTOM_KEEP"] == "keep-me"
    assert after["environment"]["CUSTOM_NEW"] == "new-value"
    assert after["environment"]["RABBITMQ_DEFAULT_PASS"] == "platformops"
    assert after["healthcheck"]["command"] == "custom-healthcheck"
    assert after["operator_metadata"] == {"nested": {"keep": True}}
    assert after["install_mode"] == "manual"
    assert after["service_install"] == "MANUAL"
    assert ServiceOut.model_validate(updated).install_mode == "manual"


def test_nested_secret_redaction_masks_pem_token_password_without_mutating_input(db: Session):
    from platformops.orchestrator.common import record_event
    from platformops.security import redact_json_string, redact_secrets

    pem = "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----"
    payload = {
        "safe": "visible",
        "auth_mode": "ssh_key",
        "nested": {
            "api_token": "token-value",
            "database": {"password": "password-value"},
            "pem_material": pem,
        },
        "items": [{"client_secret": "client-secret-value", "label": "kept"}],
    }
    original = json.loads(json.dumps(payload))

    redacted = redact_secrets(payload)
    assert payload == original
    assert redacted["safe"] == "visible"
    assert redacted["auth_mode"] == "ssh_key"
    assert redacted["nested"]["api_token"] == "***"
    assert redacted["nested"]["database"]["password"] == "***"
    assert redacted["nested"]["pem_material"] == "***"
    assert redacted["items"][0]["client_secret"] == "***"
    assert redacted["items"][0]["label"] == "kept"

    event = record_event(db, category="test", message="safe event", metadata=payload)
    stored = json.loads(event.metadata_json)
    serialized = json.dumps(stored)
    for secret in ("token-value", "password-value", "private-material", "client-secret-value"):
        assert secret not in serialized
    assert stored["safe"] == "visible"
    assert stored["auth_mode"] == "ssh_key"
    assert json.loads(redact_json_string(json.dumps(payload)))["nested"]["api_token"] == "***"


def test_remote_discovery_never_falls_back_to_local_docker(db: Session, monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator import discovery

    node = _make_node(
        db,
        name="remote-node",
        host="remote.example.test",
        environment="aws",
        facts={"connection_mode": "ssh"},
    )
    remote_calls: list[int] = []

    def remote_scan(target: Node):
        remote_calls.append(target.id)
        return [], "simulated remote docker failure"

    def local_scan(_target: Node):
        pytest.fail("local Docker was queried after remote discovery failed")

    monkeypatch.setattr(discovery, "_docker_ps_remote", remote_scan)
    monkeypatch.setattr(discovery, "_docker_ps_local", local_scan)

    result = discovery.discover_infrastructure(db, node)
    assert remote_calls == [node.id]
    assert result["status"] == "error"
    assert result["connection_mode"] == "ssh"
    assert "simulated remote docker failure" in result["error"]
    assert result["containers_scanned"] == 0
    assert db.query(ServiceInstance).count() == 0


def test_cluster_and_node_expanded_schemas_round_trip_while_masking_secrets():
    from platformops.schemas import ClusterOut, NodeOut

    cluster = ClusterOut.model_validate(
        SimpleNamespace(
            id=11,
            name="prod",
            region="ap-south-1",
            environment="production",
            description="production cluster",
            cluster_type="kubernetes",
            type="ignored-alias",
            variant="gpu",
            role="primary",
            repo_type="github",
            repo_url="https://github.com/example/platform",
            repo_branch="release",
            repo_token="repo-token-value",
            repo_path="infra/",
            repo_auth="pat",
            registry_type="dockerhub",
            registry_url="registry.example.test",
            registry_user="platform",
            registry_password="registry-password-value",
            registry_namespace="platformops",
            registry_auth="password",
            image_store="dockerhub",
        )
    )
    assert cluster.description == "production cluster"
    assert cluster.cluster_type == "kubernetes"
    assert cluster.type == "kubernetes"
    assert cluster.variant == "gpu"
    assert cluster.role == "primary"
    assert cluster.repo_branch == "release"
    assert cluster.repo_token == "***"
    assert cluster.registry_password == "***"

    facts = json.dumps(
        {
            "cpu_cores": 8,
            "safe_fact": "visible",
            "nested": {
                "token": "node-token-value",
                "password": "node-password-value",
                "private_key": "-----BEGIN PRIVATE KEY-----\nnode-key\n-----END PRIVATE KEY-----",
            },
            "auth_mode": "ssh_key",
        }
    )
    node = NodeOut.model_validate(
        SimpleNamespace(
            id=12,
            cluster_id=11,
            name="node-1",
            host="10.0.0.10",
            ssh_user="ubuntu",
            ssh_key_path="/tmp/node.pem",
            environment="aws",
            provider="aws",
            region="ap-south-1",
            availability_zone="ap-south-1a",
            auth_mode="ssh_key",
            monitor_port=9100,
            ingress_ports="80, 443",
            cloud_id="aws",
            cloud_instance_id="i-123",
            cloud_resource_id="arn:aws:ec2:...",
            cloud_account_id="123456789",
            cloud_image_id="ami-123",
            volume_root="/srv/platformops",
            docker_network="platformops_prod_network",
            status="ready",
            facts_json=facts,
        )
    )
    assert node.provider == "aws"
    assert node.availability_zone == "ap-south-1a"
    assert node.cloud_instance_id == "i-123"
    assert node.facts_json
    masked_facts = json.loads(node.facts_json)
    assert masked_facts["safe_fact"] == "visible"
    assert masked_facts["auth_mode"] == "ssh_key"
    assert masked_facts["nested"] == {
        "token": "***",
        "password": "***",
        "private_key": "***",
    }
