"""Shared LLM client — parity with cPlatform ServiceDiagnostics._execute_llm_request."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import requests

from ..settings import settings

logger = logging.getLogger("platformops.llm")

_MISTRAL_KEY_ENV = "PLATFORMOPS_MISTRAL_API_KEY"
_MISTRAL_KEY_FILE_ENV = "PLATFORMOPS_MISTRAL_API_KEY_FILE"
_MAX_SECRET_BYTES = 64 * 1024


def _mistral_runtime_key() -> str:
    """Resolve Mistral credentials only from an injected runtime secret.

    The dedicated value environment variable and its file-reference variant
    are deliberately read from ``os.environ`` instead of BaseSettings.  This
    prevents a checked-in dotenv file or a generic LLM/Groq key from silently
    becoming the Mistral credential source.
    """

    direct = os.environ.get(_MISTRAL_KEY_ENV, "").strip()
    if direct:
        return direct
    secret_path = os.environ.get(_MISTRAL_KEY_FILE_ENV, "").strip()
    if not secret_path:
        return ""
    try:
        path = Path(secret_path)
        if not path.is_file() or path.stat().st_size > _MAX_SECRET_BYTES:
            logger.warning("Mistral runtime secret file is missing, invalid, or too large")
            return ""
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        logger.warning("Mistral runtime secret file could not be read")
        return ""


def is_llm_configured() -> bool:
    provider = (settings.llm_provider or "mistral").lower()
    if provider == "groq":
        return bool(settings.groq_api_key or settings.llm_api_key)
    if provider == "mistral":
        return bool(_mistral_runtime_key())
    return bool(settings.llm_url)


def resolve_provider_config() -> dict[str, Any]:
    provider = (settings.llm_provider or "mistral").lower()
    if provider == "groq":
        api_key = settings.groq_api_key or settings.llm_api_key
        return {
            "provider": "groq",
            "api_key": api_key,
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "model": settings.groq_model or "llama-3.1-8b-instant",
        }
    if provider == "mistral":
        api_key = _mistral_runtime_key()
        return {
            "provider": "mistral",
            "api_key": api_key,
            "url": settings.llm_url or "https://api.mistral.ai/v1/chat/completions",
            "model": settings.llm_model or "mistral-small-2506",
        }
    return {
        "provider": "local",
        "api_key": settings.llm_api_key,
        "url": settings.llm_url or "http://localhost:11434/v1/chat/completions",
        "model": settings.llm_model or "llama3.1:latest",
    }


def execute_llm_request(
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.2,
) -> str | None:
    cfg = resolve_provider_config()
    provider = cfg["provider"]
    api_key = cfg["api_key"]
    url = cfg["url"]
    model = cfg["model"]

    if provider in ("groq", "mistral") and not api_key:
        logger.warning("LLM provider %s configured without API key", provider)
        return None

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        body["response_format"] = response_format
    if provider == "local":
        body["options"] = {"num_ctx": int(settings.llm_num_ctx or 16384)}

    timeout = int(settings.llm_timeout or (120 if provider == "local" else 60))
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        # Provider bodies and request objects can contain reflected sensitive
        # input.  Keep the diagnostic useful without logging them or headers.
        logger.warning("LLM request failed (provider=%s model=%s)", provider, model)
        return None


def safe_json_loads(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def contains_mistral_runtime_secret(value: Any) -> bool:
    """Return whether a response value contains the injected Mistral secret."""

    secret = _mistral_runtime_key()
    return bool(secret and secret in str(value))


def llm_status() -> dict[str, Any]:
    cfg = resolve_provider_config()
    return {
        "configured": is_llm_configured(),
        "provider": cfg["provider"],
        "model": cfg["model"],
        "has_api_key": bool(cfg["api_key"]),
    }
