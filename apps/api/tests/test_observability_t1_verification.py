"""Independent OBS-T1 contract checks for direct observability evidence.

The tests isolate Docker/Prometheus/Loki/Alloy at their public probe
boundaries.  They intentionally reject a green response for malformed or
non-canonical evidence.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeDb:
    def __init__(self):
        self.service = SimpleNamespace(
            id=41,
            node_id=7,
            service_key="redis-core",
            external_id="SERV1041",
            name="redis-core",
            container_name="acceptance-redis-core",
        )
        self.node = SimpleNamespace(
            id=7,
            cluster_id=3,
            name="acceptance-node",
            host="localhost",
            facts_json='{"connection_mode":"local"}',
        )
        self.cluster = SimpleNamespace(id=3, name="acceptance-cluster")

    def get(self, _model, item_id):
        return {41: self.service, 7: self.node, 3: self.cluster}.get(item_id)


class FakeResponse:
    status_code = 200


def _patch_evidence(
    monkeypatch: pytest.MonkeyPatch,
    *,
    loki_values: list[list[str]] | None = None,
    sample_timestamp: object | None = None,
):
    from platformops.orchestrator.reports import impl

    now = datetime.now(UTC).timestamp()
    timestamp = now if sample_timestamp is None else sample_timestamp
    monkeypatch.setattr(
        impl,
        "inspect_container",
        lambda _name: (
            {"State": {"Running": True, "Status": "running", "Health": {"Status": "healthy"}}},
            None,
        ),
    )
    monkeypatch.setattr(impl, "exec_container", lambda _name, _args: (True, "PONG\n", ""))

    def fake_json(url, *, params=None):
        if url.endswith("/api/v1/targets"):
            return {
                "status": "success",
                "data": {
                    "activeTargets": [
                        {
                            "labels": {"service_id": "41", "container_name": "acceptance-redis-core"},
                            "health": "up",
                            "lastScrape": datetime.now(UTC).isoformat(),
                            "lastError": "",
                        }
                    ]
                },
            }, None
        if url.endswith("/api/v1/query"):
            return {"status": "success", "data": {"result": [{"value": [timestamp, "1"]}]}}, None
        if url.endswith("/loki/api/v1/query_range"):
            values = loki_values if loki_values is not None else [[str(int(now * 1_000_000_000)), "OBS-RUN-123 Redis marker"]]
            return {"status": "success", "data": {"result": [{"values": values}]}}, None
        raise AssertionError(f"unexpected probe URL: {url}")

    monkeypatch.setattr(impl, "_obs_get_json", fake_json)
    monkeypatch.setattr(impl.requests, "get", lambda *_args, **_kwargs: FakeResponse())


def test_every_signal_has_typed_truth_and_freshness_fields(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(monkeypatch)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["overall_state"] == "available"
    assert result["target"]["service_id"] == 41
    assert result["target"]["container_name"] == "acceptance-redis-core"
    for name, signal in result["signals"].items():
        assert signal["state"] in {"available", "degraded", "unavailable", "error", "not_configured"}, name
        assert signal["source"], name
        assert signal["checked_at"], name
        assert "evidence_at" in signal and "age_seconds" in signal and "fresh" in signal, name
        assert "error" in signal or "reason" in signal, name


def test_loki_marker_match_is_not_a_prefix_match(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(
        monkeypatch,
        loki_values=[[str(int(datetime.now(UTC).timestamp() * 1_000_000_000)), "OBS-RUN-1234 Redis marker"]],
    )
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["signals"]["loki"]["state"] == "unavailable"
    assert result["signals"]["loki"]["detail"]["matches"] == 0
    assert result["overall_state"] == "degraded"


def test_malformed_prometheus_timestamp_is_a_typed_probe_error(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(monkeypatch, sample_timestamp="not-a-timestamp")
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["signals"]["prometheus"]["state"] == "error"
    assert result["signals"]["prometheus"]["error"]
    assert result["overall_state"] == "error"


def test_prometheus_transport_loss_is_unavailable_without_fabricating_service_loss(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports import impl
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(monkeypatch)

    def failed_json(url, *, params=None):
        if url.endswith("/api/v1/targets") or url.endswith("/api/v1/query"):
            return None, "connection refused"
        if url.endswith("/loki/api/v1/query_range"):
            now = datetime.now(UTC).timestamp()
            return {
                "status": "success",
                "data": {"result": [{"values": [[str(int(now * 1_000_000_000)), "OBS-RUN-123 Redis marker"]]}]},
            }, None
        raise AssertionError(url)

    monkeypatch.setattr(impl, "_obs_get_json", failed_json)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["signals"]["service"]["state"] == "available"
    assert result["signals"]["prometheus"]["state"] == "unavailable"
    assert result["signals"]["loki"]["state"] == "available"
    assert result["signals"]["alloy"]["state"] == "available"
    assert result["overall_state"] == "degraded"


def test_alloy_transport_loss_is_degraded_without_fabricating_loki_loss(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports import impl
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(monkeypatch)

    def failed_get(*_args, **_kwargs):
        raise OSError("alloy stopped")

    monkeypatch.setattr(impl.requests, "get", failed_get)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["signals"]["service"]["state"] == "available"
    assert result["signals"]["prometheus"]["state"] == "available"
    assert result["signals"]["loki"]["state"] == "available"
    assert result["signals"]["alloy"]["state"] == "degraded"
    assert result["overall_state"] == "degraded"


def test_loki_transport_loss_is_unavailable_and_keeps_redis_metrics_truthful(monkeypatch: pytest.MonkeyPatch):
    from platformops.orchestrator.reports import impl
    from platformops.orchestrator.reports.impl import observability_status_report

    _patch_evidence(monkeypatch)
    original_json = impl._obs_get_json

    def failed_loki(url, *, params=None):
        if url.endswith("/loki/api/v1/query_range"):
            return None, "loki stopped"
        return original_json(url, params=params)

    monkeypatch.setattr(impl, "_obs_get_json", failed_loki)
    result = observability_status_report(FakeDb(), service_id=41, marker="OBS-RUN-123")

    assert result["signals"]["service"]["state"] == "available"
    assert result["signals"]["prometheus"]["state"] == "available"
    assert result["signals"]["loki"]["state"] == "unavailable"
    assert result["signals"]["alloy"]["state"] == "degraded"
    assert result["overall_state"] == "degraded"


def test_support_compose_has_no_live_stack_or_host_socket_assets():
    compose_path = Path(__file__).parents[3] / "ops" / "compose" / "docker-compose.observability.yml"
    text = compose_path.read_text(encoding="utf-8")
    forbidden = ("/var/run/docker.sock", "cplatform_iktara_cPlatform", "9002:", "9008:", "ipv4_address")
    assert not any(value in text for value in forbidden)
    assert "PLATFORMOPS_OBS_DB_PASSWORD:?" in text
    assert "PLATFORMOPS_OBS_SECRET_KEY:?" in text
    assert "profiles: [\"glitchtip\"]" in text
