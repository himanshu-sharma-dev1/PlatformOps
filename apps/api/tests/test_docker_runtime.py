"""Focused tests for local Docker SDK operations.

These tests use a fake SDK client so they never contact the host or an
isolated runtime engine.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


class _FakeContainer:
    attrs = {"Id": "abc", "State": {"Running": True}}

    def logs(self, **_kwargs):
        return b"2026-08-10T00:00:00Z redis ready\n"

    def exec_run(self, _args, **_kwargs):
        return SimpleNamespace(exit_code=0, output=b"config: value\n")


class _FakeContainers:
    def get(self, _name):
        return _FakeContainer()


class _FakeAPI:
    def containers(self, **_kwargs):
        return [
            {
                "Id": "abc",
                "Names": ["/redis"],
                "Image": "redis:7",
                "Ports": [{"PrivatePort": 6379, "PublicPort": 9011}],
                "Status": "Up 1 minute",
                "NetworkSettings": {"Networks": {"platformops_mvp": {}}},
                "Labels": {"com.example": "mvp"},
            }
        ]


class _FakeClient:
    containers = _FakeContainers()
    api = _FakeAPI()

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def version(self):
        return {"Version": "27.0.0"}


class _FakeDocker:
    def __init__(self):
        self.client = _FakeClient()

    def from_env(self):
        return self.client


@pytest.fixture
def fake_docker(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator import docker_runtime

    module = _FakeDocker()
    monkeypatch.setattr(docker_runtime, "_docker_module", lambda: module)
    return module


def test_local_sdk_inspect_logs_and_exec(fake_docker):
    from platformops.orchestrator.docker_runtime import (
        container_logs,
        engine_version,
        exec_container,
        inspect_container,
    )

    assert engine_version() == "27.0.0"
    inspect, error = inspect_container("redis")
    assert error is None
    assert inspect["State"]["Running"] is True

    output, error = container_logs("redis", tail=20)
    assert error is None
    assert b"redis ready" in output

    ok, output, error = exec_container("redis", ["cat", "/app/config/config.yaml"])
    assert ok is True
    assert output == "config: value\n"
    assert error == ""


def test_local_sdk_discovery_shape(fake_docker):
    from platformops.orchestrator.docker_runtime import list_containers

    containers, error = list_containers(all_containers=True)
    assert error is None
    assert containers == [
        {
            "id": "abc",
            "names": "redis",
            "image": "redis:7",
            "ports": ["0.0.0.0:9011->6379/tcp"],
            "status": "Up 1 minute",
            "networks": ["platformops_mvp"],
            "labels": {"com.example": "mvp"},
        }
    ]
