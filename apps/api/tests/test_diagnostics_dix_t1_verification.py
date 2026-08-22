"""Independent DIX-T1 verification for diagnostics analyst boundaries.

These tests deliberately use an in-memory database and provider doubles.  They
do not edit or depend on the isolated runtime's persistent state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import Cluster, Node, ServiceInstance  # noqa: E402
from platformops.orchestrator.diagnostics import impl  # noqa: E402
from platformops.orchestrator import llm  # noqa: E402
from platformops.settings import settings  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _service(db: Session) -> ServiceInstance:
    cluster = Cluster(name="dix-t1-cluster")
    db.add(cluster)
    db.commit()
    node = Node(cluster_id=cluster.id, name="local", host="localhost", environment="local")
    db.add(node)
    db.commit()
    service = ServiceInstance(
        node_id=node.id,
        service_key="redis-core",
        name="Redis Core",
        kind="infrastructure",
        container_name="redis-dix-t1",
        status="running",
        config_json="{}",
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _chat_doubles(monkeypatch: pytest.MonkeyPatch, line: dict[str, Any]) -> None:
    monkeypatch.setattr(impl, "service_diagnostics", lambda *_a, **_k: {"readiness": {}})
    monkeypatch.setattr(impl, "service_diagnostics_analysis", lambda *_a, **_k: {})
    monkeypatch.setattr(impl, "service_live_logs", lambda *_a, **_k: {"lines": [line], "error": None})
    monkeypatch.setattr(
        "platformops.orchestrator.monitoring.impl.query_monitoring_issues",
        lambda *_a, **_k: {"issues": []},
    )


def test_configured_answer_cannot_reflect_cross_service_marker(
    monkeypatch: pytest.MonkeyPatch, db: Session,
):
    """Grounding applies to the complete answer, not just evidence rows."""

    service = _service(db)
    line = {
        "timestamp": "2025-01-01T00:00:01Z",
        "level": "WARN",
        "message": "run=canonical marker-warning",
        "source": "container_stdout",
    }
    _chat_doubles(monkeypatch, line)
    monkeypatch.setattr("platformops.orchestrator.llm.is_llm_configured", lambda: True)
    monkeypatch.setattr(
        "platformops.orchestrator.llm.execute_llm_request",
        lambda *_a, **_k: json.dumps(
            {
                "answer": "The other-service-marker indicates a restart.",
                "evidence": [{"t": "00:00:01", "lvl": "WARN", "msg": line["message"]}],
                "chart_data": list(range(10)),
                "suggestions": ["Inspect logs", "Check Redis", "Review events"],
            }
        ),
    )

    result = impl.service_log_analytics_chat(db, service, "Analyze canonical")

    assert result["_audit_mode"] == "deterministic_fallback"
    assert "other-service-marker" not in json.dumps(result)
    assert result["evidence"] == [{"t": "00:00:01", "lvl": "WARN", "msg": line["message"]}]


def test_deterministic_fallback_does_not_echo_runtime_mistral_key(
    monkeypatch: pytest.MonkeyPatch, db: Session,
):
    """A provider key must not become API-visible merely because a log echoes it."""

    service = _service(db)
    secret = "dix-t1-runtime-secret"
    line = {
        "timestamp": "2025-01-01T00:00:01Z",
        "level": "ERROR",
        "message": f"provider rejected password={secret}",
        "source": "container_stdout",
    }
    _chat_doubles(monkeypatch, line)
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY", secret)
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY_FILE", raising=False)
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr("platformops.orchestrator.llm.is_llm_configured", lambda: False)

    result = impl.service_log_analytics_chat(db, service, "Analyze current errors")

    assert result["_audit_mode"] == "deterministic_fallback"
    assert secret not in json.dumps(result)


def test_mistral_request_uses_configured_model_timeout_and_json_protocol(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[dict[str, Any]] = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"answer":"ok"}'}}]}

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "llm_url", "http://fake-mistral.invalid/v1/chat/completions")
    monkeypatch.setattr(settings, "llm_model", "mistral-dix-t1")
    monkeypatch.setattr(settings, "llm_timeout", 7)
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY", "dix-t1-key")
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY_FILE", raising=False)
    monkeypatch.setattr(llm.requests, "post", fake_post)

    result = llm.execute_llm_request(
        [{"role": "user", "content": "diagnose canonical marker"}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    assert result == '{"answer":"ok"}'
    assert calls == [
        {
            "url": "http://fake-mistral.invalid/v1/chat/completions",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer dix-t1-key"},
            "json": {
                "model": "mistral-dix-t1",
                "messages": [{"role": "user", "content": "diagnose canonical marker"}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            "timeout": 7,
        }
    ]


def test_diagnostics_ui_keeps_stale_guard_and_sanitized_fallback_label():
    actions = (API_ROOT.parent / "web/src/platform/actions/diagnosticsActions.ts").read_text(encoding="utf-8")
    chat = (API_ROOT.parent / "web/src/views/LogAnalystChat.tsx").read_text(encoding="utf-8")

    assert "let diagnosticsRequestSequence = 0;" in actions
    assert "if (requestSequence !== diagnosticsRequestSequence) return;" in actions
    load_start = actions.index("  async loadDiagnostics(service, options) {")
    load_end = actions.index("\n\n  async focusDiagnosticsTarget", load_start)
    load_body = actions[load_start:load_end]
    assert "const requestSequence = ++diagnosticsRequestSequence;" in load_body
    assert load_body.count("requestSequence !== diagnosticsRequestSequence") >= 2
    assert 'analyst_source: result.provider || "deterministic fallback"' in actions
    assert "const ANALYST_TAGS = new Set" in chat
    assert "dangerouslySetInnerHTML={{ __html: sanitizeAnalystHtml" in chat
    assert "element.removeAttribute(attribute.name)" in chat
