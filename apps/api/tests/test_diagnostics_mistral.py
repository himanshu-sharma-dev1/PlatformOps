"""Mistral protocol, failure fallback, grounding, and secret-boundary contracts."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.orchestrator import llm  # noqa: E402
from platformops.settings import settings  # noqa: E402


class _MistralHandler(BaseHTTPRequestHandler):
    payload: dict = {}
    authorization = ""
    response_content = ""
    status = 200

    def do_POST(self):  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        type(self).payload = json.loads(self.rfile.read(size))
        type(self).authorization = self.headers.get("Authorization", "")
        body = {
            "choices": [{"message": {"content": type(self).response_content}}]
        }
        encoded = json.dumps(body).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format, *_args):
        return


@pytest.fixture
def fake_mistral(monkeypatch: pytest.MonkeyPatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MistralHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "llm_url", f"http://127.0.0.1:{server.server_port}/v1/chat/completions")
    monkeypatch.setattr(settings, "llm_model", "mistral-small-2506")
    monkeypatch.setattr(settings, "llm_timeout", 2)
    _MistralHandler.payload = {}
    _MistralHandler.authorization = ""
    _MistralHandler.status = 200
    try:
        yield _MistralHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mistral_ignores_generic_and_persisted_key_sources(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "llm_api_key", "generic-key-must-not-be-used")
    monkeypatch.setattr(settings, "groq_api_key", "groq-key-must-not-be-used")
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY_FILE", raising=False)
    assert llm.is_llm_configured() is False
    assert llm.resolve_provider_config()["api_key"] == ""


def test_mistral_runtime_secret_file_and_protocol(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_mistral,
):
    marker = "synthetic-mistral-marker"
    secret_file = tmp_path / "mistral.secret"
    secret_file.write_text(marker, encoding="utf-8")
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY", raising=False)
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY_FILE", str(secret_file))
    fake_mistral.response_content = '{"answer":"grounded"}'

    content = llm.execute_llm_request(
        [{"role": "user", "content": "diagnose canonical marker"}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    assert content == '{"answer":"grounded"}'
    assert fake_mistral.authorization == f"Bearer {marker}"
    assert fake_mistral.payload["model"] == "mistral-small-2506"
    assert fake_mistral.payload["response_format"] == {"type": "json_object"}
    assert marker not in json.dumps(fake_mistral.payload)
    assert llm.llm_status() == {
        "configured": True, "provider": "mistral",
        "model": "mistral-small-2506", "has_api_key": True,
    }


def test_mistral_provider_http_failure_returns_no_content(
    monkeypatch: pytest.MonkeyPatch, fake_mistral,
):
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY", "synthetic-mistral-marker")
    monkeypatch.delenv("PLATFORMOPS_MISTRAL_API_KEY_FILE", raising=False)
    fake_mistral.status = 503
    assert llm.execute_llm_request([{"role": "user", "content": "diagnose"}]) is None


def test_mistral_timeout_is_redacted_and_returns_no_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
):
    import requests

    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY", "synthetic-mistral-timeout-marker")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("reflected synthetic-mistral-timeout-marker")))
    assert llm.execute_llm_request([{"role": "user", "content": "diagnose"}]) is None
    assert "synthetic-mistral-timeout-marker" not in caplog.text
