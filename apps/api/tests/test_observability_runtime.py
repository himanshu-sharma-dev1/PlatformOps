"""Small runtime-facing tests for the selected observability endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def test_query_regex_literal_keeps_hyphens_and_escapes_re2_meta_characters():
    from platformops.query import escape_query_regex_literal

    assert escape_query_regex_literal("mvp-dind-node") == "mvp-dind-node"
    assert escape_query_regex_literal("node.1[0]") == r"node\\.1\\[0\\]"
    # Backslashes and quotes need the additional PromQL/LogQL string layer.
    assert escape_query_regex_literal('x\\y"z') == r"x\\\\y\"z"


def test_observability_status_reports_unavailable_engine_without_500(monkeypatch: pytest.MonkeyPatch):
    from platformops.routers import observability

    class FailingDocker:
        @staticmethod
        def from_env():
            raise RuntimeError("engine unavailable")

    monkeypatch.setattr(observability, "docker", FailingDocker)

    result = observability.get_observability_status()

    assert result["containers"] == []
    assert result["available"] is False
    assert "engine unavailable" in result["error"]


def test_observability_status_maps_compose_containers(monkeypatch: pytest.MonkeyPatch):
    from platformops.routers import observability

    class FakeAPI:
        def containers(self, **_kwargs):
            return [
                {
                    "Id": "b" * 64,
                    "Names": ["/platformops-obs-loki"],
                    "State": "running",
                    "Status": "Up 2 minutes",
                    "Labels": {
                        "com.docker.compose.project": "platformops-obs",
                        "com.docker.compose.service": "loki",
                    },
                },
                {
                    "Id": "a" * 64,
                    "Names": ["/platformops-obs-prometheus"],
                    "State": "exited",
                    "Status": "Exited (1) 10 seconds ago",
                    "Labels": {
                        "com.docker.compose.project": "platformops-obs",
                        "com.docker.compose.service": "prometheus",
                    },
                },
            ]

    class FakeClient:
        api = FakeAPI()

        def close(self):
            return None

    class FakeDocker:
        @staticmethod
        def from_env():
            return FakeClient()

    monkeypatch.setattr(observability, "docker", FakeDocker)

    result = observability.get_observability_status()

    assert result["available"] is True
    assert result["error"] is None
    assert [item["Name"] for item in result["containers"]] == [
        "platformops-obs-loki",
        "platformops-obs-prometheus",
    ]
    assert result["containers"][0]["Service"] == "loki"
    assert result["containers"][1]["State"] == "exited"
