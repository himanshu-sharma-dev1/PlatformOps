"""Direct-probe and freshness tests for the Observability contract."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


class FakeDb:
    def __init__(self):
        self.service = SimpleNamespace(id=41, node_id=7, service_key="redis-core", external_id="SERV1041", name="redis-core", container_name="acceptance-redis-core")
        self.node = SimpleNamespace(id=7, cluster_id=3, name="acceptance-node", host="localhost", facts_json='{"connection_mode":"local"}')
        self.cluster = SimpleNamespace(id=3, name="acceptance-cluster")

    def get(self, _model, item_id):
        return {41: self.service, 7: self.node, 3: self.cluster}.get(item_id)


class FakeResponse:
    status_code = 200


def _patch_ready(monkeypatch: pytest.MonkeyPatch, *, marker_found: bool = True, sample_age: int = 0):
    from platformops.orchestrator.reports import impl

    now = datetime.now(UTC).timestamp() - sample_age
    monkeypatch.setattr(impl, "inspect_container", lambda _name: ({"State": {"Running": True, "Status": "running", "Health": {"Status": "healthy"}}}, None))
    monkeypatch.setattr(impl, "exec_container", lambda _name, _args: (True, "PONG\n", ""))

    def fake_json(url, *, params=None):
        if url.endswith("/api/v1/targets"):
            return {"status": "success", "data": {"activeTargets": [{"labels": {"service_id": "41", "container_name": "acceptance-redis-core"}, "health": "up", "lastScrape": datetime.now(UTC).isoformat(), "lastError": ""}]}}, None
        if url.endswith("/api/v1/query"):
            return {"status": "success", "data": {"result": [{"value": [now, "1"]}]}}, None
        if url.endswith("/loki/api/v1/query_range"):
            values = [[str(int(now * 1_000_000_000)), "OBS-RUN-123 Redis marker"]] if marker_found else []
            return {"status": "success", "data": {"result": [{"values": values}] if values else []}}, None
        raise AssertionError(url)

    monkeypatch.setattr(impl, "_obs_get_json", fake_json)
    monkeypatch.setattr(impl.requests, "get", lambda *_args, **_kwargs: FakeResponse())


def test_status_requires_direct_fresh_correlated_evidence(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_ready(monkeypatch)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")
    assert result["overall_state"] == "available"
    assert result["target"]["container_name"] == "acceptance-redis-core"
    assert result["signals"]["service"]["detail"]["pong"] is True
    assert result["signals"]["prometheus"]["detail"]["sample_value"] == 1.0
    assert result["signals"]["loki"]["detail"]["matches"] == 1
    assert result["signals"]["glitchtip"]["state"] == "not_configured"


def test_http_success_with_empty_marker_result_is_not_healthy(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_ready(monkeypatch, marker_found=False)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")
    assert result["overall_state"] == "degraded"
    assert result["signals"]["loki"]["state"] == "unavailable"
    assert result["signals"]["alloy"]["state"] == "degraded"


def test_stale_prometheus_sample_is_degraded(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_ready(monkeypatch, sample_age=300)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")
    assert result["overall_state"] == "degraded"
    assert result["signals"]["prometheus"]["state"] == "degraded"
    assert result["signals"]["prometheus"]["fresh"] is False


def test_container_probe_failure_is_error_not_db_health(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports import impl
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_ready(monkeypatch)
    monkeypatch.setattr(impl, "inspect_container", lambda _name: (None, "engine unavailable"))
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")
    assert result["overall_state"] == "error"
    assert "engine unavailable" in result["signals"]["service"]["error"]
