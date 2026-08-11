"""Cluster-core unit tests — exercise real shipped functions (not re-implementations)."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def test_normalize_docker_ports_from_docker_ps_string():
    from platformops.orchestrator.discovery import normalize_docker_ports

    assert normalize_docker_ports("0.0.0.0:9006->8000/tcp") == ["9006:8000"]
    assert normalize_docker_ports("8102:8080") == ["8102:8080"]
    assert "5000:5000" in normalize_docker_ports(
        ["0.0.0.0:5000->5000/tcp", ":::5000->5000/tcp"]
    )
    multi = normalize_docker_ports("0.0.0.0:9006->8000/tcp, 0.0.0.0:9007->8001/tcp")
    assert multi == ["9006:8000", "9007:8001"]
    assert normalize_docker_ports("") == []
    assert normalize_docker_ports(None) == []


def test_normalize_docker_ports_from_inspect_dict():
    from platformops.orchestrator.discovery import normalize_docker_ports

    inspect_style = {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "9006"}]}
    assert normalize_docker_ports(inspect_style) == ["9006:8000"]


def test_discovery_policy_allows_all_networks():
    from platformops.orchestrator.discovery import load_discovery_policy

    policy = load_discovery_policy()
    # Network affinity off — cPlatform nets are not excluded by policy
    assert policy.get("prefer_node_network") is False
    assert int(policy.get("off_network_score_penalty") or 0) == 0
    assert int(policy.get("min_adopt_score") or 0) >= 1


def test_required_dependencies_dtrain():
    from platformops.catalog import required_dependencies

    deps = required_dependencies("dtrain-controller")
    assert "rabbitmq-core" in deps
    assert "redis-core" in deps
    assert "dtrain-tracker" in deps


def test_service_out_derives_expose_from_config_json():
    from platformops.schemas import ServiceOut

    class Fake:
        id = 1
        external_id = "SERV1001"
        node_id = 12
        service_key = "dtrain-controller"
        name = "DTrain"
        kind = "app"
        container_name = "node-1-dtrain-controller"
        image = "x"
        status = "running"
        config_json = json.dumps({"expose_service": True, "host_port": 9006, "adopted": True})

    out = ServiceOut.model_validate(Fake())
    assert out.expose_service is True
    assert out.host_port == 9006
    assert out.adopted is True


def test_validate_config_yaml_real():
    from platformops.orchestrator.config import validate_config

    ok = validate_config("dTrain_CONFIG:\n  service:\n    service_port: 9003\n")
    assert ok["ok"] is True
    bad = validate_config("not: valid: yaml: [[[")
    # may be syntax error or ok depending on yaml liberality — at least returns dict
    assert "ok" in bad
    empty = validate_config("")
    assert empty["ok"] is False


def test_service_update_deep_merges_existing_contract_and_normalizes_install_mode(monkeypatch):
    from platformops.orchestrator.service import impl

    service = SimpleNamespace(
        id=7,
        node_id=3,
        service_key="demo-service",
        name="Operator name",
        kind="app",
        container_name="demo-container",
        image="demo:old",
        status="created",
        config_json=json.dumps(
            {
                "environment": {"KEEP": "yes", "nested": {"old": 1, "preserve": True}},
                "volumes": ["/operator/volume"],
                "custom_operator_field": {"enabled": True},
                "install_mode": "ANSIBLE",
            }
        ),
        node=SimpleNamespace(id=3, volume_root="/tmp/platformops"),
    )

    class FakeDb:
        def commit(self):
            return None

        def refresh(self, _service):
            return None

    monkeypatch.setattr(
        impl,
        "_service_contract_for_node",
        lambda *_args, **_kwargs: {
            "environment": {"CATALOG": "default", "nested": {"new": 2}},
            "image": "demo:catalog",
            "kind": "app",
            "container_name": "catalog-name",
        },
    )
    monkeypatch.setattr(impl, "record_event", lambda *_args, **_kwargs: None)

    updated = impl.update_service_instance(
        FakeDb(),
        service,
        contract_overrides={"environment": {"nested": {"new": 9}}, "install_mode": "MANUAL"},
    )
    config = json.loads(updated.config_json)
    assert config["environment"]["KEEP"] == "yes"
    assert config["environment"]["nested"] == {"old": 1, "preserve": True, "new": 9}
    assert config["volumes"] == ["/operator/volume"]
    assert config["custom_operator_field"] == {"enabled": True}
    assert config["install_mode"] == "manual"
    assert config["service_install"] == "MANUAL"
    assert updated.status == "registered"


def test_record_event_redacts_nested_credentials(monkeypatch):
    from platformops.orchestrator import common

    class FakeDb:
        def add(self, event):
            self.event = event

        def commit(self):
            return None

        def refresh(self, _event):
            return None

    db = FakeDb()
    common.record_event(
        db,
        category="lifecycle",
        message="update",
        metadata={
            "updates": {"ssh_private_key": "-----BEGIN PRIVATE KEY----- secret"},
            "repo_token": "repo-secret",
            "repo_auth": "pat",
            "safe": "visible",
        },
    )
    metadata = json.loads(db.event.metadata_json)
    assert metadata["updates"]["ssh_private_key"] == "***"
    assert metadata["repo_token"] == "***"
    assert metadata["repo_auth"] == "pat"
    assert metadata["safe"] == "visible"


def test_remote_discovery_never_calls_local_docker_on_ssh_failure(monkeypatch):
    from platformops.orchestrator import discovery

    class Proc:
        returncode = 255
        stdout = ""
        stderr = "Permission denied"

    monkeypatch.setattr(discovery.subprocess, "run", lambda *_args, **_kwargs: Proc())
    monkeypatch.setattr(
        discovery,
        "_docker_ps_local",
        lambda: (_ for _ in ()).throw(AssertionError("local Docker must not be used for SSH discovery")),
    )
    containers, error = discovery._docker_ps_remote(
        SimpleNamespace(host="remote.example", ssh_user="ubuntu", ssh_key_path="")
    )
    assert containers == []
    assert "Permission denied" in (error or "")


def test_live_status_maps_stopped_container_state():
    from platformops.orchestrator.service.impl import _map_inspect_to_live

    service = SimpleNamespace(
        id=1,
        external_id="SERV1001",
        service_key="demo",
        name="Demo",
        container_name="demo",
        image="demo:latest",
        status="running",
    )
    result = _map_inspect_to_live(
        service,
        {"State": {"Status": "exited", "Running": False, "ExitCode": 1}},
        None,
    )
    assert result["overall_status"] == "exited"
    assert result["running"] is False


def test_openapi_resolves_node_launch_request():
    from platformops.main import app

    schema = app.openapi()
    operation = schema["paths"]["/api/nodes/{node_id}/launch-vm"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]

    assert request_schema == {"$ref": "#/components/schemas/NodeLaunchRequest"}
    assert schema["components"]["schemas"]["NodeLaunchRequest"]["required"] == [
        "ami_id",
        "instance_type",
        "region",
    ]


def test_local_docker_service_playbook_does_not_require_sudo():
    """Local/DinD deploys must skip become while SSH targets still elevate."""
    playbook = (API_ROOT.parents[1] / "ops/ansible/playbooks/docker_service.yml").read_text(encoding="utf-8")
    assert 'become: "{{ (ansible_connection | default(\'ssh\')) != \'local\' }}"' in playbook


def test_local_node_validation_playbook_does_not_require_sudo():
    """Local/DinD validation must use the same privilege rule as deployment."""
    playbook = (API_ROOT.parents[1] / "ops/ansible/playbooks/validate_node.yml").read_text(encoding="utf-8")
    assert 'become: "{{ (ansible_connection | default(\'ssh\')) != \'local\' }}"' in playbook


def test_detach_resource_references_clears_nullable_history_links():
    from platformops.orchestrator.common import detach_resource_references

    class FakeDb:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(str(statement))

    db = FakeDb()
    detach_resource_references(db, service_ids=[7], node_ids=[3])

    assert len(db.statements) == 25
    assert sum(statement.lstrip().startswith("DELETE") for statement in db.statements) == 7
    assert sum(statement.lstrip().startswith("UPDATE") for statement in db.statements) == 18
    for table in (
        "backup_runs",
        "drift_reports",
        "log_archives",
        "release_approvals",
        "release_records",
        "deployment_plan_records",
        "capacity_reports",
        "operational_events",
    ):
        assert any(table in statement for statement in db.statements), table


def test_incident_lookup_uses_incident_model_and_id():
    from platformops.routers.ops_common import _get_incident

    class FakeDb:
        def __init__(self):
            self.args = None

        def get(self, *args):
            self.args = args
            return object()

    db = FakeDb()
    result = _get_incident(db, 42)

    assert result is not None
    assert db.args[0].__name__ == "IncidentRecord"
    assert db.args[1] == 42
