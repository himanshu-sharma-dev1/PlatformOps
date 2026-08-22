from __future__ import annotations

import time
from types import SimpleNamespace

import requests

from platformops.orchestrator.monitoring import impl


class _Response:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_prometheus_true_zero_is_measured_not_unavailable(monkeypatch):
    now = time.time()

    def get(*_args, **kwargs):
        if "start" in kwargs.get("params", {}):
            return _Response({"status": "success", "data": {"result": [{"values": [[now - 5, "0"], [now, "0"]]}]}})
        return _Response({"status": "success", "data": {"result": [{"value": [now, "0"]}]}})

    monkeypatch.setattr(requests, "get", get)
    observed = impl._prom_observe("vector(0)")
    assert observed["state"] == "available"
    assert observed["value"] == 0


def test_prometheus_empty_vector_is_unavailable(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Response({"status": "success", "data": {"result": []}}))
    observed = impl._prom_observe("missing_metric")
    assert observed["state"] == "missing"
    assert observed["value"] is None


def test_redis_probe_requires_target_bound_ping(monkeypatch):
    service = SimpleNamespace(service_key="redis-core", container_name="redis-target", node=SimpleNamespace(host="localhost"), node_id=1)
    db = SimpleNamespace(get=lambda *_args: service.node)
    # The helper imports this symbol from service.impl at call time.
    import platformops.orchestrator.service.impl as service_impl

    monkeypatch.setattr(service_impl, "get_service_live_status", lambda *_args, **_kwargs: {"running": True, "state": "running", "source": "docker_inspect"})
    monkeypatch.setattr(service_impl, "_node_uses_local_docker", lambda *_args, **_kwargs: True)
    import platformops.orchestrator.docker_runtime as docker_runtime

    monkeypatch.setattr(docker_runtime, "exec_container", lambda *_args: (True, "PONG\n", ""))
    result = impl._direct_service_probe(db, service)
    assert result["status"] == "ok"
    assert result["value"] == "PONG"
    assert result["source"] == "redis_ping"


def test_glitchtip_unconfigured_is_explicit(monkeypatch):
    monkeypatch.setattr(impl.settings, "glitchtip_token", "")
    result = impl.get_monitoring_integration_status()
    assert result["availability"] == "unavailable"
    assert result["reachable"] is False
