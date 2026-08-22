"""Independent MONPERF-T1 contract checks.

These tests use only mocked HTTP/Docker boundaries.  They do not contact the
live cPlatform stack, a host Docker socket, or the configured application DB.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
import requests

from platformops.orchestrator.monitoring import impl


class _Response:
    def __init__(self, payload, status_code: int = 200, headers: dict[str, str] | None = None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_remote_redis_probe_uses_selected_ssh_target_without_local_fallback(monkeypatch: pytest.MonkeyPatch):
    service = SimpleNamespace(
        service_key="redis-core",
        container_name="remote-redis",
        node=SimpleNamespace(host="redis.example.test", ssh_user="ops", ssh_key_path="/tmp/key"),
        node_id=7,
    )
    db = SimpleNamespace(get=lambda *_args: service.node)
    import platformops.orchestrator.service.impl as service_impl

    monkeypatch.setattr(
        service_impl,
        "get_service_live_status",
        lambda *_args, **_kwargs: {"running": True, "state": "running", "source": "docker_inspect_ssh"},
    )
    monkeypatch.setattr(service_impl, "_node_uses_local_docker", lambda *_args, **_kwargs: False)
    calls: list[tuple[object, str, list[str]]] = []
    monkeypatch.setattr(
        impl,
        "_remote_container_exec",
        lambda node, name, args: (calls.append((node, name, args)) or (True, "PONG\n", "")),
    )

    import platformops.orchestrator.docker_runtime as docker_runtime

    monkeypatch.setattr(
        docker_runtime,
        "exec_container",
        lambda *_args, **_kwargs: pytest.fail("local Docker was queried for a remote target"),
    )

    result = impl._direct_service_probe(db, service)

    assert result["status"] == "ok"
    assert result["source"] == "redis_ping_ssh"
    assert result["value"] == "PONG"
    assert calls == [(service.node, "remote-redis", ["redis-cli", "--raw", "PING"])]


def test_prometheus_range_malformed_tail_does_not_hide_valid_samples(monkeypatch: pytest.MonkeyPatch):
    now = time.time()
    payload = {
        "status": "success",
        "data": {"result": [{"values": [[now - 15, "2.5"], ["bad-timestamp", "bad-value"]]}]},
    }
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Response(payload))

    observed = impl._prom_observe("redis_commands_processed_total", range_window="15m")

    assert observed["state"] == "available"
    assert observed["value"] == 2.5
    assert len(observed["series"]) == 1
    assert observed["latest_sample_at"] is not None


def test_uptime_add_rejects_invalid_url_before_external_mutation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(impl.settings, "glitchtip_base_url", "http://glitchtip.test")
    monkeypatch.setattr(impl.settings, "glitchtip_org_slug", "test-org")
    monkeypatch.setattr(impl.settings, "glitchtip_token", "disposable-token")
    calls: list[tuple[object, ...]] = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response({"id": "should-not-be-created"}, status_code=201)

    monkeypatch.setattr(requests, "post", post)

    result = impl.add_monitoring_uptime_result(
        service_name="redis-core",
        name="invalid-target",
        url="not-a-url",
        interval=60,
    )

    assert result["success"] is False
    assert result["availability"] in {"error", "unavailable"}
    assert calls == []


def test_glitchtip_configured_http_error_is_typed_without_token_leak(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(impl.settings, "glitchtip_base_url", "http://glitchtip.test")
    monkeypatch.setattr(impl.settings, "glitchtip_org_slug", "test-org")
    monkeypatch.setattr(impl.settings, "glitchtip_token", "disposable-token")
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Response({}, status_code=401))

    result = impl.get_monitoring_integration_status()

    assert result["configured"] is True
    assert result["availability"] == "error"
    assert result["reachable"] is False
    assert "disposable-token" not in str(result)
    assert result["error"] == "GlitchTip HTTP 401"


def test_glitchtip_issue_cursor_and_normalized_payload_are_preserved(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(impl.settings, "glitchtip_base_url", "http://glitchtip.test")
    monkeypatch.setattr(impl.settings, "glitchtip_org_slug", "test-org")
    monkeypatch.setattr(impl.settings, "glitchtip_token", "disposable-token")
    calls: list[dict] = []

    def get(*_args, **kwargs):
        calls.append(kwargs)
        return _Response(
            [{"id": 17, "title": "RedisError: controlled", "level": "error", "count": 2}],
            headers={'Link': '<http://glitchtip.test/next?cursor=abc>; rel="next"'},
        )

    monkeypatch.setattr(requests, "get", get)

    result = impl.query_monitoring_issues(SimpleNamespace(), "redis-core", "24h", cursor="previous")

    assert result["availability"] == "available"
    assert result["issues"] == [
        {
            "id": "17",
            "title": "RedisError: controlled",
            "level": "error",
            "count": "2",
            "userCount": "",
            "culprit": "",
            "type": "RedisError",
            "first_seen": "",
            "last_seen": "",
            "permalink": "",
            "status": "",
        }
    ]
    assert result["next_cursor"] == "abc"
    assert calls[0]["headers"]["Authorization"] == "Bearer disposable-token"
    assert "disposable-token" not in str(result)


def test_unknown_issue_action_is_rejected_without_external_mutation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(impl.settings, "glitchtip_base_url", "http://glitchtip.test")
    monkeypatch.setattr(impl.settings, "glitchtip_org_slug", "test-org")
    monkeypatch.setattr(impl.settings, "glitchtip_token", "disposable-token")
    monkeypatch.setattr(requests, "put", lambda *_args, **_kwargs: pytest.fail("unsupported action called GlitchTip"))

    result = impl.execute_monitoring_issue_action_result("17", "not-supported")

    assert result["success"] is False
    assert result["availability"] == "error"
    assert "Unsupported issue action" in result["error"]


def test_service_metrics_timestamp_includes_measured_redis_observations(monkeypatch: pytest.MonkeyPatch):
    service = SimpleNamespace(
        id=33,
        name="Redis target",
        service_key="redis-core",
        container_name="redis-target",
        node_id=7,
        config_json="{}",
    )
    db = SimpleNamespace(get=lambda *_args: service)

    def observe(_query: str, *, range_window: str | None = None, timeout: float = 8.0):
        if range_window:
            # cAdvisor is absent, but the Redis exporter range is measured.
            return {
                "state": "missing" if "container_cpu" in _query else "available",
                "reachable": True,
                "value": None if "container_cpu" in _query else 3.0,
                "series": [] if "container_cpu" in _query else [{"timestamp": 3.0, "label": "2026-08-22T00:00:03Z", "value": 3.0}],
                "latest_sample_at": None if "container_cpu" in _query else "2026-08-22T00:00:03Z",
                "error": None if "container_cpu" not in _query else "metric series not found",
            }
        if "container_" in _query:
            return {"state": "missing", "reachable": True, "value": None, "series": [], "latest_sample_at": None, "error": "metric series not found"}
        return {"state": "available", "reachable": True, "value": 1.0, "series": [{"timestamp": 4.0, "label": "2026-08-22T00:00:04Z", "value": 1.0}], "latest_sample_at": "2026-08-22T00:00:04Z", "error": None}

    monkeypatch.setattr(impl, "_prom_observe", observe)

    result = impl.get_service_metrics(db, service.id, window="15m")

    assert result["db_metrics"]["active_connections"] == 1.0
    assert result["commands_series"]
    assert result["latest_sample_at"] == "2026-08-22T00:00:04Z"
