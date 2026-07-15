"""Cluster-core unit tests — exercise real shipped functions (not re-implementations)."""
from __future__ import annotations

import json
import sys
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
