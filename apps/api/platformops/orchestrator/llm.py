"""Shared LLM client — parity with cPlatform ServiceDiagnostics._execute_llm_request."""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from ..settings import settings

logger = logging.getLogger("platformops.llm")


def is_llm_configured() -> bool:
    provider = (settings.llm_provider or "mistral").lower()
    if provider == "groq":
        return bool(settings.groq_api_key or settings.llm_api_key)
    if provider == "mistral":
        return bool(settings.mistral_api_key or settings.llm_api_key or settings.groq_api_key)
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
        api_key = settings.mistral_api_key or settings.llm_api_key
        return {
            "provider": "mistral",
            "api_key": api_key,
            "url": settings.llm_url or "https://api.mistral.ai/v1/chat/completions",
            "model": settings.llm_model or "mistral-medium-2508",
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
    except Exception as exc:
        logger.warning("LLM request failed (provider=%s model=%s): %s", provider, model, exc)
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


def llm_status() -> dict[str, Any]:
    cfg = resolve_provider_config()
    return {
        "configured": is_llm_configured(),
        "provider": cfg["provider"],
        "model": cfg["model"],
        "has_api_key": bool(cfg["api_key"]),
    }
