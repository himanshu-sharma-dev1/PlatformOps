"""Small, dependency-free helpers for keeping credentials out of API/audit data."""

from __future__ import annotations

import re
from typing import Any


# ``repo_auth``/``registry_auth``/``auth_mode`` are authentication *modes*, not
# credentials.  Keep those values visible while masking credential-bearing keys.
_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "private_key",
    "private-key",
    "secret",
    "api_key",
    "api-key",
    "access_key",
    "access-key",
    "client_secret",
    "client-secret",
    "credential",
    "authorization",
    "bearer",
    "pem",
)
_AUTH_MODE_KEYS = {"auth", "repo_auth", "registry_auth", "auth_mode", "auth_type"}
_PEM_MARKER = re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----")
_CREDENTIAL_TEXT = re.compile(
    r"(?ix)"
    r"(?P<key>password|passwd|token|secret|private[_ -]?key|credential|authorization|api[_ -]?key)"
    r"\s*(?P<separator>[:=])\s*(?:(?:bearer)\s+)?[^\s,;]+"
    r"|(?P<scheme>bearer)\s+[^\s,;]+"
)


def _redact_credential_match(match: re.Match[str]) -> str:
    key = match.group("key") or match.group("scheme") or "credential"
    separator = match.group("separator") or " "
    return f"{key}{separator}[REDACTED]"


def is_secret_key(key: object) -> bool:
    """Return whether a metadata/config key conventionally carries a secret."""

    normalized = str(key or "").strip().lower().replace(" ", "_")
    if normalized in _AUTH_MODE_KEYS:
        return False
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def redact_secrets(value: Any, *, key_hint: str | None = None) -> Any:
    """Recursively replace credential values with ``***``.

    This is intentionally usable for event metadata, JSON facts, and response
    payloads.  It does not mutate the caller's dictionaries/lists.
    """

    if key_hint and is_secret_key(key_hint):
        return "***"
    if isinstance(value, str):
        if _PEM_MARKER.search(value):
            return "***"
        return _CREDENTIAL_TEXT.sub(_redact_credential_match, value)
    if isinstance(value, dict):
        return {str(key): redact_secrets(item, key_hint=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


def redact_json_string(value: str | None) -> str:
    """Redact a JSON object string while preserving malformed strings safely."""

    import json

    raw = value or ""
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return "***" if _PEM_MARKER.search(raw) else raw
    return json.dumps(redact_secrets(parsed), separators=(",", ":"))


def redact_text(value: str | None, *, secrets: tuple[str, ...] = ()) -> str:
    """Redact known secret literals from free-form command/error text."""

    output = value or ""
    for secret in secrets:
        if secret:
            output = output.replace(secret, "***")
    output = _CREDENTIAL_TEXT.sub(_redact_credential_match, output)
    return "***" if _PEM_MARKER.search(output) else output
