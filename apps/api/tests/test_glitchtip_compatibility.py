"""Focused GlitchTip 6.x compatibility contracts."""
from __future__ import annotations

import json

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


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impl.settings, "glitchtip_base_url", "http://glitchtip.test")
    monkeypatch.setattr(impl.settings, "glitchtip_org_slug", "test-org")
    monkeypatch.setattr(impl.settings, "glitchtip_token", "disposable-token")
    monkeypatch.setattr(impl.settings, "glitchtip_project_map", {"redis-core": "redis-project"})


def test_integration_status_uses_capability_probe_when_api_root_fails(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    calls: list[str] = []

    def get(url, **kwargs):
        calls.append(url)
        if url.endswith("/api/0/"):
            return _Response({}, status_code=500)
        return _Response([], status_code=200)

    monkeypatch.setattr(requests, "get", get)

    result = impl.get_monitoring_integration_status()

    assert result["availability"] == "available"
    assert result["reachable"] is True
    assert calls == ["http://glitchtip.test/api/0/organizations/test-org/projects/"]


@pytest.mark.parametrize("status_code", [401, 500])
def test_integration_status_capability_http_error_is_truthful(
    monkeypatch: pytest.MonkeyPatch, status_code: int
):
    _configure(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Response({}, status_code=status_code))

    result = impl.get_monitoring_integration_status()

    assert result["configured"] is True
    assert result["availability"] == "error"
    assert result["status"] == "error"
    assert result["reachable"] is False
    assert result["error"] == f"GlitchTip HTTP {status_code}"
    assert "disposable-token" not in str(result)


def test_integration_status_transport_error_redacts_token(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)

    def get(*_args, **_kwargs):
        raise RuntimeError("adapter failed for disposable-token")

    monkeypatch.setattr(requests, "get", get)

    result = impl.get_monitoring_integration_status()

    assert result["availability"] == "error"
    assert result["reachable"] is False
    assert "disposable-token" not in result["error"]


def test_uptime_add_resolves_slug_to_numeric_project_id(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    get_calls: list[tuple[object, dict]] = []
    post_calls: list[tuple[object, dict]] = []

    def get(url, **kwargs):
        get_calls.append((url, kwargs))
        return _Response({"id": "42", "slug": "redis-project"})

    def post(url, **kwargs):
        post_calls.append((url, kwargs))
        return _Response({"id": 8, "projectId": 42}, status_code=201)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)

    result = impl.add_monitoring_uptime_result(
        service_name="redis-core",
        name="redis reachability",
        url="http://redis.example.test/health",
        interval=60,
    )

    assert result["success"] is True
    assert result["project_id"] == 42
    assert post_calls[0][1]["json"]["project"] == "42"
    assert "/projects/test-org/redis-project/" in str(get_calls[0][0])


def test_transaction_groups_use_numeric_project_and_paginated_payload(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    calls: list[tuple[str, dict]] = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if "/projects/" in url:
            return _Response({"id": 42, "slug": "redis-project"})
        return _Response(
            {"items": [{"id": 91, "project": 42, "transaction": "GET /health", "count": 1}]},
            headers={"Link": '<http://glitchtip.test/next?cursor=abc>; rel="next"'},
        )

    monkeypatch.setattr(requests, "get", get)

    result = impl.get_monitoring_performance_result("redis-core")

    assert result["availability"] == "available"
    assert result["project_id"] == 42
    assert result["transactions"][0]["transaction"] == "GET /health"
    assert result["next_cursor"] == "abc"
    assert calls[1][1]["params"]["project"] == "42"


def test_transaction_ingest_uses_numeric_envelope_endpoint_and_reports_pending(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    get_calls: list[str] = []
    post_calls: list[tuple[str, dict]] = []

    def get(url, **kwargs):
        get_calls.append(url)
        if "/projects/" in url and "/keys/" not in url:
            return _Response({"id": 42, "slug": "redis-project"})
        if "/keys/" in url:
            return _Response([{"public": "11111111-1111-1111-1111-111111111111", "projectId": 42}])
        return _Response({"items": []})

    def post(url, **kwargs):
        post_calls.append((url, kwargs))
        envelope = kwargs["data"]
        assert "disposable-token" not in envelope
        lines = envelope.splitlines()
        assert json.loads(lines[1])["type"] == "transaction"
        assert json.loads(lines[2])["transaction"] == "GET /health"
        return _Response({}, status_code=200)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)

    result = impl.ingest_monitoring_transaction_result(
        service_name="redis-core",
        transaction="GET /health",
        poll_attempts=1,
    )

    assert result["success"] is True
    assert result["availability"] == "accepted_pending"
    assert result["accepted_pending"] is True
    assert post_calls[0][0].endswith("/api/42/envelope/")
    assert any("/projects/test-org/redis-project/" in url for url in get_calls)


def test_transaction_ingest_materialized_group_is_available(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)

    def get(url, **kwargs):
        if "/projects/" in url and "/keys/" not in url:
            return _Response({"id": 42, "slug": "redis-project"})
        if "/keys/" in url:
            return _Response([{"public": "11111111-1111-1111-1111-111111111111"}])
        return _Response({"items": [{"project": 42, "transaction": "GET /health", "count": 1}]})

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: _Response({}, status_code=200))

    result = impl.ingest_monitoring_transaction_result(
        service_name="redis-core",
        transaction="GET /health",
        poll_attempts=1,
    )

    assert result["availability"] == "available"
    assert result["accepted_pending"] is False
    assert result["transactions"][0]["project"] == 42
