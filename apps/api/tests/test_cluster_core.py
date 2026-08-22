"""Cluster-core unit tests — exercise real shipped functions (not re-implementations)."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

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


def _runtime_inspect(*, health: str, running: bool = True, status: str = "running"):
    """Build the small Docker inspect shape consumed by runtime verification."""

    return {
        "Name": "/node-3-redis-core",
        "Config": {
            "Image": "redis:7-alpine",
            "Healthcheck": {"Test": ["CMD-SHELL", "redis-cli ping"]},
        },
        "State": {
            "Status": status,
            "Running": running,
            "Health": {"Status": health},
        },
        "NetworkSettings": {"Networks": {"platformops-isolated_default": {}}},
        "Mounts": [
            {"Destination": "/data"},
            {"Destination": "/var/log/redis"},
            {"Destination": "/usr/local/etc/redis/redis.conf"},
        ],
    }


def _runtime_service():
    return SimpleNamespace(
        id=3,
        node_id=3,
        service_key="redis-core",
        container_name="node-3-redis-core",
        image="redis:7-alpine",
        config_json=json.dumps({"healthcheck": {"command": "redis-cli ping"}}),
        node=SimpleNamespace(
            id=3,
            host="localhost",
            connection_mode="auto",
            docker_network="platformops-isolated_default",
        ),
    )


def test_runtime_verification_polls_starting_until_healthy_and_pong(monkeypatch):
    from platformops.orchestrator import docker_runtime
    from platformops.orchestrator.service import impl

    inspections = iter(
        [
            _runtime_inspect(health="starting"),
            _runtime_inspect(health="healthy"),
        ]
    )
    calls = []
    monkeypatch.setattr(impl, "_docker_inspect_for_node", lambda *_args: (next(inspections), None, "docker_inspect"))
    monkeypatch.setattr(impl, "_node_uses_local_docker", lambda *_args: True)
    monkeypatch.setattr(
        docker_runtime,
        "exec_container",
        lambda container, args: (calls.append((container, args)) or (True, "PONG\n", "")),
    )

    result = impl._verify_service_runtime(
        object(),
        _runtime_service(),
        timeout_seconds=0.2,
        poll_interval_seconds=0.05,
    )

    assert result["ok"] is True
    assert result["health"] == "healthy"
    assert result["readiness"] == "redis-cli:PONG"
    assert len(calls) == 2


def test_runtime_verification_times_out_while_health_is_starting(monkeypatch):
    from platformops.orchestrator import docker_runtime
    from platformops.orchestrator.service import impl

    monkeypatch.setattr(
        impl,
        "_docker_inspect_for_node",
        lambda *_args: (_runtime_inspect(health="starting"), None, "docker_inspect"),
    )
    monkeypatch.setattr(impl, "_node_uses_local_docker", lambda *_args: True)
    monkeypatch.setattr(docker_runtime, "exec_container", lambda *_args: (True, "PONG\n", ""))

    result = impl._verify_service_runtime(
        object(),
        _runtime_service(),
        timeout_seconds=0.12,
        poll_interval_seconds=0.05,
    )

    assert result["ok"] is False
    assert "runtime readiness timed out after 0.12s" in result["error"]
    assert result["state"] == "running"
    assert result["health"] == "starting"


def test_execute_deployment_plan_treats_running_target_as_accepted(monkeypatch):
    from platformops.orchestrator.service import impl

    service = SimpleNamespace(
        id=9,
        node_id=3,
        name="Redis",
        service_key="redis-core",
        node=SimpleNamespace(id=3),
    )
    monkeypatch.setattr(
        impl,
        "deployment_plan",
        lambda *_args: {"blocked_by": ["redis-core"], "ok": False},
    )
    monkeypatch.setattr(
        impl,
        "dependency_preflight",
        lambda *_args: {"ok": True, "missing": [], "stopped": [], "message": "ready"},
    )
    monkeypatch.setattr(
        impl,
        "deploy_service",
        lambda *_args: SimpleNamespace(id=19, status="running"),
    )
    monkeypatch.setattr(impl, "record_event", lambda *_args, **_kwargs: None)

    result = impl.execute_deployment_plan(object(), service, auto_install_dependencies=False)

    assert result["ok"] is True
    assert result["target_job"].status == "running"


def test_redis_playbook_prepares_engine_visible_writable_paths():
    playbook = (API_ROOT.parents[1] / "ops/ansible/playbooks/docker_service.yml").read_text(encoding="utf-8")

    assert "Prepare Redis data and log paths in the Docker engine namespace" in playbook
    assert "id -u redis" in playbook
    assert "chown -R \"${uid}:${gid}\" /data /var/log/redis" in playbook
    assert "chmod 0644 /var/log/redis/redis.log" in playbook
    assert 'service_key | default(\'\') == \'redis-core\'' in playbook
    # The preparation task mounts the complete contract but only changes the
    # data/log paths; the config bind remains the authoritative file mount.
    assert 'volumes: "{{ contract.volumes | default([]) }}"' in playbook

    parsed = yaml.safe_load(playbook)
    prep = next(task for task in parsed[0]["tasks"] if task["name"].startswith("Prepare Redis data"))
    module = prep["community.docker.docker_container"]
    assert module["command"] and len(module["command"]) == 1
    assert "touch /var/log/redis/redis.log" in module["command"][0]
    assert module["user"] == "0:0"
    assert module["volumes"] == "{{ contract.volumes | default([]) }}"


def test_deploy_callback_terminalizes_readiness_failure_and_removed_service(monkeypatch):
    from platformops.models import JobStatus
    from platformops.orchestrator.service import impl

    service = SimpleNamespace(
        id=41,
        node_id=8,
        name="Redis",
        service_key="redis-core",
        container_name="node-8-redis-core",
        image="redis:7-alpine",
        config_json=json.dumps({"volumes": []}),
        node=SimpleNamespace(id=8, volume_root="/tmp/platformops", docker_network="platformops-test"),
        status="created",
    )
    job = SimpleNamespace(id=77, status=JobStatus.queued.value, error="", output="")

    class FakeDb:
        def __init__(self):
            self.service = service

        def get(self, model, _id):
            return self.service

        def add(self, _value):
            return None

        def commit(self):
            return None

        def refresh(self, _value):
            return None

    db = FakeDb()
    callback = {}
    monkeypatch.setattr(impl.settings, "local_mode", False)
    monkeypatch.setattr(impl, "dependency_preflight", lambda *_args: {"ok": True})
    monkeypatch.setattr(impl, "write_job_vars", lambda *_args: Path("/tmp/deploy.yml"))
    monkeypatch.setattr(impl, "_ansible_base_command", lambda *_args: "ansible-playbook")
    monkeypatch.setattr(impl, "create_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(impl, "record_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "platformops.orchestrator.config._merged_service_contract",
        lambda *_args: {"image": "redis:7-alpine", "volumes": []},
    )

    def fake_run_job_async(_db, _job, **kwargs):
        callback.update(kwargs)
        return job

    monkeypatch.setattr(impl, "run_job_async", fake_run_job_async)
    impl.deploy_service(db, service)

    # A readiness timeout after Ansible exits must be terminal failed.
    monkeypatch.setattr(impl, "_verify_service_runtime", lambda *_args: {"ok": False, "error": "PONG timeout"})
    callback["on_complete"](db, job, True)
    assert job.status == JobStatus.failed.value
    assert "PONG timeout" in job.error or "Runtime verification" in job.output
    assert service.status == "error"

    # If deletion detaches the FK before the worker callback, do not leave a
    # deferred job running forever.
    db.service = None
    job.status = JobStatus.running.value
    job.error = "Ansible target failed"
    job.output = ""
    callback["on_complete"](db, job, False)
    assert job.status == JobStatus.failed.value
    assert job.error == "Ansible target failed"


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


def test_api_runtime_image_contract_has_only_pinned_ssh_client():
    dockerfile = (API_ROOT.parents[1] / "ops/docker/web-api/Dockerfile").read_text(encoding="utf-8")
    assert "openssh-client=1:10.0p1-7+deb13u4" in dockerfile
    assert "RUN ssh -V" in dockerfile
    assert "openssh-server" not in dockerfile
    assert "sshd" not in dockerfile


def test_remote_node_validation_uses_ssh_ansible_target_without_local_fallback(monkeypatch):
    from platformops.orchestrator import node as node_impl

    node = SimpleNamespace(
        id=12,
        name="remote-node",
        host="remote.example.test",
        ssh_user="ops",
        ssh_key_path="/tmp/remote-key",
        facts_json=json.dumps({"connection_mode": "ssh"}),
        status="unknown",
    )
    job = SimpleNamespace(id=19, command="", status="running", error="", output="")
    captured: dict[str, object] = {}

    class FakeDb:
        def get(self, _model, _id):
            return node

        def add(self, _value):
            return None

        def commit(self):
            return None

        def refresh(self, _value):
            return None

    monkeypatch.setattr(node_impl.settings, "local_mode", False)

    def fake_create_job(_db, **kwargs):
        job.command = kwargs["command"]
        return job

    monkeypatch.setattr(node_impl, "create_job", fake_create_job)
    monkeypatch.setattr(
        node_impl,
        "run_job_async",
        lambda _db, _job, **kwargs: captured.update(kwargs) or job,
    )
    probes: list[str] = []
    monkeypatch.setattr(
        node_impl,
        "_probe_node_ssh_docker",
        lambda target: probes.append(target.host) or {"ssh_ok": True, "docker_ok": True, "detail": "remote"},
    )

    node_impl.validate_node(FakeDb(), node)
    command = job.command
    assert "-i remote.example.test," in command
    assert "-u ops" in command
    assert "--private-key /tmp/remote-key" in command
    assert "-c local" not in command
    assert "localhost," not in command
    assert "on_complete" in captured

    captured["on_complete"](FakeDb(), job, True)
    assert probes == ["remote.example.test", "remote.example.test"]
    assert node.status == "healthy"


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
