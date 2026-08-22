#!/usr/bin/env python3
"""Strict, run-scoped seven-page Redis acceptance harness.

This is an acceptance fixture, not a smoke test. A phase is green only when
the API result, a terminal side effect, and an independent runtime probe all
agree. Evidence is written below ``/tmp`` by default and is redacted before
it is persisted. The harness talks to the disposable DinD daemon through the
isolated Compose project; it never uses the host Docker socket or PlatformOps.

Authoritative fixture: ``docs/redis-seven-page-acceptance-fixture.md``.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("PLATFORMOPS_E2E_BASE", "http://localhost:9020").rstrip("/")
MAILPIT_URL = os.environ.get("PLATFORMOPS_MAILPIT_BASE", "http://localhost:9010").rstrip("/")
COMPOSE_FILE = ROOT / "ops/compose/docker-compose.isolated.yml"
COMPOSE_PROJECT = "platformops-isolated"
LIVE_PORT = 9002
ISOLATED_PORT = 9020
MAILPIT_PORT = 9010
TERMINAL_SUCCESS = {"success", "completed"}
TERMINAL_FAILURE = {"failed", "error"}

RUN_STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
try:
    GIT_SHA = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, timeout=5, check=False,
    ).stdout.strip() or "nogit"
except Exception:
    GIT_SHA = "nogit"
RUN_ID = os.environ.get("PLATFORMOPS_ACCEPTANCE_RUN_ID", "").strip() or f"parity-redis-{RUN_STAMP}-{GIT_SHA}-{uuid.uuid4().hex[:6]}"
if not re.fullmatch(r"[A-Za-z0-9_-]+", RUN_ID):
    raise SystemExit("PLATFORMOPS_ACCEPTANCE_RUN_ID must contain only letters, digits, underscore, or hyphen")
EVIDENCE_ROOT = Path(os.environ.get("PLATFORMOPS_ACCEPTANCE_EVIDENCE_DIR", "/tmp/platformops-redis-acceptance")).resolve()
EVIDENCE_DIR = EVIDENCE_ROOT / RUN_ID

IDENTITY_MANIFEST: dict[str, Any] = {
    "run_id": RUN_ID,
    "cluster_name": f"{RUN_ID}-cluster",
    "node_name": f"{RUN_ID}-node",
    "service_key": "redis-core",
    "service_name": f"Parity Redis {RUN_ID}",
    "container_name": "",
    "cluster_id": None,
    "node_id": None,
    "service_id": None,
    "external_id": "",
    "volume_root": f"/tmp/platformops/{RUN_ID}",
    "config_path": f"/tmp/platformops/{RUN_ID}/redis/config/redis.conf",
    "runtime_config_path": "/usr/local/etc/redis/redis.conf",
    "log_path": f"/tmp/platformops/{RUN_ID}/redis/logs/redis.log",
    "runtime_log_path": "/var/log/redis/redis.log",
    "metrics_job": f"redis-parity-{RUN_ID}",
    "remote_ssh": {
        "positive_fixture": False,
        "target": "platformops-ssh-target",
        "connection_mode": "ssh",
        "no_local_fallback": True,
    },
}

BASELINE_CONFIG = (
    "appendonly yes\n"
    "loglevel notice\n"
    "logfile /var/log/redis/redis.log\n"
    "maxmemory 64mb\n"
    "maxmemory-policy allkeys-lru\n"
    "save 60 1000\n"
)


class AcceptanceFailure(RuntimeError):
    """A required acceptance assertion failed."""


_SECRET_KEY_RE = re.compile(
    r"(?:token|password|passwd|secret|private.?key|authorization|bearer|session|cookie|"
    r"api[_-]?key|dsn|invite[_-]?(?:token|link|url))",
    re.I,
)
_INVITE_PATH_RE = re.compile(
    r"(?P<prefix>(?:https?://[^\s\"']+)?(?:/#/|/)(?:auth/)?invite/)"
    r"(?P<token>[A-Za-z0-9_-]{8,})",
    re.I,
)
_SECRET_KV_RE = re.compile(
    r"(?P<key>[\"']?\s*(?:token|password|passwd|secret|session|cookie|authorization|bearer|"
    r"api[_-]?key|dsn|invite[_-]?(?:token|link))[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\s,;&\"']+)(?P=quote)",
    re.I,
)
_BEARER_RE = re.compile(r"(?P<prefix>\b(?:Bearer|Basic)\s+)(?P<value>[A-Za-z0-9._~+/=-]{8,})", re.I)
_DSN_PASSWORD_RE = re.compile(
    r"(?P<prefix>\b(?:postgres(?:ql)?|redis|mysql|amqp)://[^\s/@:]+:)"
    r"(?P<password>[^\s/@]+)(?P<suffix>@)",
    re.I,
)


def _secret_summary(value: Any) -> Any:
    """Retain only a non-reversible correlation hash and optional last four."""
    if value is None or value == "" or isinstance(value, bool):
        return value
    text = str(value)
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    last4 = text[-4:] if len(text) >= 4 else text
    return f"[REDACTED sha256:{digest} last4:{last4}]"


def _sanitize_text(value: str) -> str:
    """Remove secrets embedded in arbitrary nested response/log strings."""
    text = str(value)

    def invite_replacement(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}[REDACTED invite {_secret_summary(match.group('token'))}]"

    text = _INVITE_PATH_RE.sub(invite_replacement, text)

    def dsn_replacement(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{_secret_summary(match.group('password'))}{match.group('suffix')}"

    text = _DSN_PASSWORD_RE.sub(dsn_replacement, text)

    def bearer_replacement(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{_secret_summary(match.group('value'))}"

    text = _BEARER_RE.sub(bearer_replacement, text)

    def kv_replacement(match: re.Match[str]) -> str:
        return f"{match.group('key')}{_secret_summary(match.group('value'))}"

    text = _SECRET_KV_RE.sub(kv_replacement, text)
    return text[:8000]


def _redact(value: Any, *, _key: str = "") -> Any:
    """Recursively sanitize keys and values before any evidence is persisted."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                result[key_text] = _secret_summary(item)
            else:
                result[key_text] = _redact(item, _key=key_text)
        return result
    if isinstance(value, list):
        return [_redact(item, _key=_key) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, _key=_key) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


_UNSAFE_INVITE_RE = re.compile(r"(?:/#/|/)(?:auth/)?invite/([A-Za-z0-9_-]{8,})", re.I)
_UNSAFE_BEARER_RE = re.compile(r"\b(?:Bearer|Basic)\s+(?!\[REDACTED)([A-Za-z0-9._~+/=-]{8,})", re.I)
_UNSAFE_SECRET_KV_RE = re.compile(
    r"[\"']?\s*(?:token|password|passwd|secret|session|cookie|authorization|bearer|api[_-]?key|dsn|"
    r"invite[_-]?(?:token|link))[\"']?\s*[:=]\s*(?!\[REDACTED|sha256:|last4:|true\b|false\b|null\b)([^\s,;&\"']+)",
    re.I,
)
_UNSAFE_DSN_RE = re.compile(r"\b(?:postgres(?:ql)?|redis|mysql|amqp)://[^\s/@:]+:[^\s/@]+@", re.I)


def _scan_evidence_secrets(value: Any) -> list[str]:
    """Return labels only for raw secret patterns found in evidence text."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    findings: list[str] = []
    if _UNSAFE_INVITE_RE.search(text):
        findings.append("invite-url")
    if _UNSAFE_BEARER_RE.search(text):
        findings.append("authorization")
    if _UNSAFE_SECRET_KV_RE.search(text):
        findings.append("secret-field")
    if _UNSAFE_DSN_RE.search(text):
        findings.append("dsn-password")
    return sorted(set(findings))


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(_redact(value), indent=2, sort_keys=True, default=str)
    _require(not _scan_evidence_secrets(encoded), "evidence sanitizer left a secret pattern in JSON output")
    path.write_text(encoded + "\n", encoding="utf-8")


def _text_write(path: Path, value: str) -> None:
    """Sanitize text artifacts through the same recursive evidence boundary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = _sanitize_text(value)
    _require(not _scan_evidence_secrets(sanitized), "evidence sanitizer left a secret pattern in text output")
    path.write_text(sanitized + ("\n" if not value.endswith("\n") else ""), encoding="utf-8")


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


def _port(url: str) -> int:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcceptanceFailure(f"unsafe target URL: {url!r}")
    try:
        return parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise AcceptanceFailure(f"invalid target URL port: {url!r}") from exc


class RuntimeEvidence:
    """Independent probes against the private DinD daemon."""

    def __init__(self, evidence: "Evidence") -> None:
        self.evidence = evidence

    def _compose(self, *args: str, timeout: int = 45) -> subprocess.CompletedProcess[str]:
        command = ["docker", "compose", "--project-name", COMPOSE_PROJECT, "--file", str(COMPOSE_FILE), "--profile", "isolated", "exec", "-T", "docker-engine", "docker", *args]
        _require(not os.environ.get("DOCKER_HOST", "").startswith("unix://"), "host Docker socket is forbidden")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        self.evidence.direct.append({"command": command[:9] + ["[REDACTED]"] + list(args), "returncode": result.returncode, "stdout": result.stdout[-12000:], "stderr": result.stderr[-4000:]})
        return result

    def json(self, *args: str, timeout: int = 45) -> Any:
        result = self._compose(*args, timeout=timeout)
        _require(result.returncode == 0, f"private DinD command failed: {' '.join(args)}: {result.stderr[-500:]}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceFailure(f"private DinD returned non-JSON for {' '.join(args)}") from exc

    def text(self, *args: str, timeout: int = 45) -> str:
        result = self._compose(*args, timeout=timeout)
        _require(result.returncode == 0, f"private DinD command failed: {' '.join(args)}: {result.stderr[-500:]}")
        return result.stdout

    def inspect(self, name: str) -> dict[str, Any]:
        payload = self.json("inspect", name)
        _require(isinstance(payload, list) and payload, f"private DinD target not found: {name}")
        return payload[0]

    def exec(self, container: str, *args: str, timeout: int = 45) -> str:
        return self.text("exec", container, *args, timeout=timeout)

    def postgres_sql(self, statement: str, *, timeout: int = 45) -> str:
        """Run a bounded fixture-only SQL adjustment in the disposable DB.

        This is intentionally not an API fallback: it is used only to move a
        run-scoped invite's timestamp past the product's documented 30-day
        expiry without sleeping for a month.  The acceptance overlay gives
        this Compose project a unique Postgres volume.
        """
        command = [
            "docker", "compose", "--project-name", COMPOSE_PROJECT,
            "--file", str(COMPOSE_FILE), "--profile", "isolated",
            "exec", "-T", "postgres", "psql", "-X", "-q", "-t",
            "-A", "-U", "platformops", "-d", "platformops", "-c", statement,
        ]
        _require(not os.environ.get("DOCKER_HOST", "").startswith("unix://"), "host Docker socket is forbidden")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        self.evidence.direct.append({"command": command[:-1] + ["[fixture SQL redacted]"], "returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]})
        _require(result.returncode == 0, f"disposable Postgres fixture failed: {result.stderr[-500:]}")
        return result.stdout.strip()

    def ping(self, container: str) -> bool:
        try:
            return self.exec(container, "redis-cli", "--raw", "PING").strip().upper() == "PONG"
        except AcceptanceFailure:
            return False

    def snapshot(self) -> dict[str, Any]:
        def rows(*args: str) -> list[dict[str, Any]]:
            output = self.text(*args)
            parsed: list[dict[str, Any]] = []
            for line in output.splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AcceptanceFailure(f"private DinD resource listing returned malformed JSON: {line[:200]}") from exc
                if isinstance(item, dict):
                    parsed.append(item)
            return parsed

        return {
            "containers": rows("ps", "-a", "--format", "{{json .}}"),
            "networks": rows("network", "ls", "--format", "{{json .}}"),
            "volumes": rows("volume", "ls", "--format", "{{json .}}"),
        }

    def owned_names(self) -> dict[str, list[str]]:
        snap = self.snapshot()
        return {kind: [str(item.get("Names") or item.get("Name") or item.get("name") or "") for item in rows if RUN_ID in str(item)] for kind, rows in snap.items()}


class Evidence:
    def __init__(self) -> None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=False)
        self.phase_results: dict[str, dict[str, Any]] = {}
        self.current: str | None = None
        self.actions: list[dict[str, Any]] = []
        self.direct: list[dict[str, Any]] = []
        self.manifest = dict(IDENTITY_MANIFEST)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        _require(self.current is None, f"phase overlap: {name}")
        self.current = name
        result = {"phase": name, "started_at": datetime.now(timezone.utc).isoformat(), "status": "running", "actions": []}
        self.phase_results[name] = result
        try:
            yield
        except Exception as exc:
            result.update({"status": "failed", "ended_at": datetime.now(timezone.utc).isoformat(), "error": str(exc)[:1000]})
            raise
        else:
            result.update({"status": "passed", "ended_at": datetime.now(timezone.utc).isoformat()})
        finally:
            _json_write(EVIDENCE_DIR / f"{name}.json", result)
            self.current = None

    def action(self, label: str, **details: Any) -> None:
        record = {"label": label, "at": datetime.now(timezone.utc).isoformat(), **_redact(details)}
        self.actions.append(record)
        if self.current:
            self.phase_results[self.current]["actions"].append(record)

    def save(self, success: bool, error: str | None = None) -> None:
        self.manifest["evidence_dir"] = str(EVIDENCE_DIR)
        self.manifest["phase_results"] = self.phase_results
        self.manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.manifest["status"] = "passed" if success else "failed"
        if error:
            self.manifest["error"] = error[:1000]
        _json_write(EVIDENCE_DIR / "manifest.json", self.manifest)
        _json_write(EVIDENCE_DIR / "direct-runtime.json", self.direct)
        _json_write(EVIDENCE_DIR / "final-summary.json", {"run_id": RUN_ID, "status": self.manifest["status"], "phases": self.phase_results, "actions": self.actions})


EVIDENCE: Evidence | None = None
RUNTIME: RuntimeEvidence | None = None
SESSION = requests.Session()


def _evidence() -> Evidence:
    _require(EVIDENCE is not None, "evidence bundle is not initialized")
    return EVIDENCE


def _runtime() -> RuntimeEvidence:
    _require(RUNTIME is not None, "runtime evidence adapter is not initialized")
    return RUNTIME


def request(method: str, path: str, *, expected: int | set[int] = 200, payload: Any = None, params: dict[str, Any] | None = None, session: requests.Session | None = None, timeout: int = 30, binary: bool = False) -> Any:
    client = session or SESSION
    allowed = {expected} if isinstance(expected, int) else set(expected)
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    try:
        response = client.request(method, url, json=payload, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise AcceptanceFailure(f"{method} {path} request failed: {exc}") from exc
    if binary:
        body: Any = {"bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(), "prefix": response.content[:8].hex()}
    else:
        try:
            body = response.json()
        except ValueError:
            body = response.text[:8000]
    _evidence().action("http", method=method, path=path, status=response.status_code, expected=sorted(allowed), request=payload, response=body)
    if response.status_code not in allowed:
        raise AcceptanceFailure(f"{method} {path}: expected {sorted(allowed)}, got {response.status_code}: {str(_redact(body))[:600]}")
    return body


def require_shape(payload: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    _require(isinstance(payload, dict), f"{label} must be an object")
    missing = [field for field in fields if field not in payload]
    _require(not missing, f"{label} missing fields: {', '.join(missing)}")
    return payload


def get_auth_token(email: str = "admin", password: str = "admin", *, session: requests.Session | None = None) -> str:
    # LoginOut has exactly ``token``. Fallback fields hide API regressions.
    result = request("POST", "/api/auth/login", payload={"email": email, "password": password}, session=session)
    payload = require_shape(result, ("token", "user", "expires_at"), "login response")
    token = payload["token"]
    _require(isinstance(token, str) and token.strip(), "login response token is empty")
    return token


def set_auth(token: str, *, session: requests.Session | None = None) -> None:
    (session or SESSION).headers.update({"Authorization": f"Bearer {token}"})


def poll_job(job_id: int, *, max_wait: int = 120, label: str = "job") -> dict[str, Any]:
    deadline = time.monotonic() + max_wait
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = require_shape(request("GET", f"/api/jobs/{job_id}"), ("id", "status", "action", "service_id", "node_id"), f"{label} job")
        status = str(last.get("status") or "").lower()
        if status in TERMINAL_SUCCESS:
            _evidence().action("terminal_job", job_label=label, job_id=job_id, status=status, job=last)
            return last
        if status in TERMINAL_FAILURE:
            raise AcceptanceFailure(f"{label} job {job_id} failed: {last.get('error') or last.get('output')}")
        time.sleep(1)
    raise AcceptanceFailure(f"{label} job {job_id} did not reach terminal success: {last}")


def mailpit_messages() -> list[dict[str, Any]]:
    result = request("GET", f"{MAILPIT_URL}/api/v1/messages")
    _require(isinstance(result, dict) and isinstance(result.get("messages"), list), "Mailpit messages response is malformed")
    return result["messages"]


def mailpit_token(email: str, *, known_ids: set[str]) -> tuple[str, str]:
    matches = [item for item in mailpit_messages() if str(item.get("ID") or "") not in known_ids and email.lower() in json.dumps(item, default=str).lower()]
    _require(len(matches) == 1, f"Mailpit must contain exactly one new invitation for {email}, found {len(matches)}")
    message_id = str(matches[0].get("ID") or "")
    detail = request("GET", f"{MAILPIT_URL}/api/v1/message/{message_id}")
    _require(isinstance(detail, dict), "Mailpit message detail must be an object")
    body = f"{detail.get('Text', '')}\n{detail.get('HTML', '')}"
    found = re.findall(r"/#/invite/([A-Za-z0-9_-]+)", body)
    _require(len(found) == 1, f"Mailpit invitation must contain exactly one invite URL for {email}")
    token = found[0]
    _require(f"{BASE_URL}/#/invite/{token}" in body, "Mailpit invite link host/token does not match isolated API")
    _evidence().action("mailpit_invite", email=email, message_id=message_id, token_hash=hashlib.sha256(token.encode()).hexdigest()[:16], subject=detail.get("Subject"), link_host=BASE_URL)
    return token, message_id


def browser_accept_invite(link: str, *, full_name: str, password: str) -> None:
    """Accept the invitation through the real frontend route."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # The API image/product dependencies stay untouched.  When the host
        # lacks a browser, use a disposable Playwright image on the isolated
        # Compose network and talk to the current-worktree API by service DNS.
        token_match = re.search(r"#/invite/([A-Za-z0-9_-]+)", link)
        _require(token_match is not None, "invite URL did not contain a browser-safe token")
        internal_link = f"http://platformops:8000/#/invite/{token_match.group(1)}"
        command = [
            "docker", "run", "--rm", "--network", "platformops-isolated_default",
            "-e", "PLATFORMOPS_ACCEPTANCE_INVITE_URL",
            "-e", "PLATFORMOPS_ACCEPTANCE_FULL_NAME",
            "-e", "PLATFORMOPS_ACCEPTANCE_PASSWORD",
            "-e", f"PLATFORMOPS_ACCEPTANCE_INVITE_URL={internal_link}",
            "-e", f"PLATFORMOPS_ACCEPTANCE_FULL_NAME={full_name}",
            "-e", f"PLATFORMOPS_ACCEPTANCE_PASSWORD={password}",
            "-v", f"{ROOT / 'scripts' / 'acceptance_browser_invite.py'}:/runner.py:ro",
            os.environ.get("PLATFORMOPS_ACCEPTANCE_BROWSER_IMAGE", "mcr.microsoft.com/playwright/python:v1.49.1-noble"),
            "sh", "-c", "python -m pip install --quiet 'playwright==1.49.1' && python /runner.py",
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
        _evidence().action("browser_container", image=command[command.index("-v") + 2] if "-v" in command else "playwright", returncode=result.returncode, stderr=result.stderr[-1000:])
        _require(result.returncode == 0, f"disposable Playwright browser failed: {result.stderr[-600:]}")
        try:
            result_payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise AcceptanceFailure("disposable Playwright returned no structured result") from exc
        _require(result_payload.get("session_established") is True, "disposable browser did not establish a session")
        _evidence().action("browser_invite_accept", final_path=result_payload.get("final_path", ""), session_established=True, runner="disposable-playwright")
        return
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(link, wait_until="networkidle", timeout=30_000)
            _require(page.get_by_role("heading", name="Accept invitation").count() == 1, "browser did not render invite route")
            page.get_by_placeholder("Full name").fill(full_name)
            page.get_by_placeholder("Password", exact=True).fill(password)
            page.get_by_placeholder("Confirm password", exact=True).fill(password)
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="Accept invitation & sign in").click()
            page.wait_for_timeout(1000)
            _require("/invite/" not in page.url, f"browser did not clear one-time invite URL: {page.url}")
            _require(page.evaluate("Object.keys(localStorage).some((key) => key.toLowerCase().includes('token'))"), "browser did not establish a session")
            browser.close()
    except Exception as exc:
        raise AcceptanceFailure(f"browser invitation acceptance failed: {exc}") from exc
    _evidence().action("browser_invite_accept", final_path=urlparse(link).path, session_established=True)


def run_phase_0_preflight() -> None:
    with _evidence().phase("phase-0-preflight"):
        _require(_port(BASE_URL) == ISOLATED_PORT, f"PlatformOps target must use isolated port {ISOLATED_PORT}")
        _require(_port(MAILPIT_URL) == MAILPIT_PORT, f"Mailpit target must use isolated port {MAILPIT_PORT}")
        _require(_port(BASE_URL) != LIVE_PORT, "port 9002 is the PlatformOps stack and is forbidden")
        _require(isinstance(request("GET", "/api/health"), dict), "health response must be JSON")
        _require(isinstance(request("GET", f"{MAILPIT_URL}/api/v1/info"), dict), "Mailpit readiness response must be JSON")
        verify = subprocess.run([sys.executable, str(ROOT / "scripts/verify_isolated_runtime.py")], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        _evidence().action("isolated_verify", returncode=verify.returncode, stdout=verify.stdout, stderr=verify.stderr)
        _require(verify.returncode == 0, f"isolated-verify failed: {verify.stderr[-600:]}")
        compose = subprocess.run(["docker", "compose", "--project-name", COMPOSE_PROJECT, "--file", str(COMPOSE_FILE), "--profile", "isolated", "config"], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        _require(compose.returncode == 0, f"isolated Compose config failed: {compose.stderr[-600:]}")
        # DinD itself exposes an in-container Unix socket for its own daemon;
        # only a host-socket mount is forbidden.  The static verifier already
        # rejects that mount, while this runtime check rejects PlatformOps/9002.
        _require("/var/run/docker.sock:" not in compose.stdout and not any(value in compose.stdout for value in ("9002:", "cplatform_iktara", "PlatformOps")), "isolated Compose contains forbidden host socket mount/port/network reference")
        runtime = _runtime()
        baseline = runtime.snapshot()
        baseline_text = json.dumps(baseline, default=str).lower()
        _require("cplatform_iktara" not in baseline_text and "cplatform" not in baseline_text, "private DinD baseline contains a PlatformOps resource")
        _evidence().action("preflight", git_sha=GIT_SHA, compose_sha256=hashlib.sha256(compose.stdout.encode()).hexdigest(), baseline_resources=baseline, owned_resources=runtime.owned_names())
        _json_write(EVIDENCE_DIR / "preflight.json", {"git_sha": GIT_SHA, "dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()), "compose_sha256": hashlib.sha256(compose.stdout.encode()).hexdigest(), "baseline": baseline})


def run_phase_1_users() -> None:
    with _evidence().phase("phase-1-users"):
        admin_token = get_auth_token()
        set_auth(admin_token)
        stamp = RUN_ID.lower().replace("-", "")[:18]
        operator_email = f"operator-{stamp}@example.invalid"
        invite_email = f"invite-{stamp}@example.invalid"
        invited_password = "Invitee-Redis-2026!"
        operator_password = "Operator-Redis-2026!"
        operator = require_shape(request("POST", "/api/users", expected={200, 201}, payload={"user_name": f"Operator {RUN_ID}", "user_email": operator_email, "password": operator_password, "user_role": "Operational", "user_number": "1234567890", "permissions": []}), ("user_id", "user_email", "user_role", "status"), "operator")
        _require(operator["user_role"] == "Operational" and operator["status"] == "active", "operator role/status contract mismatch")
        _evidence().manifest.update({"operator_user_id": operator["user_id"], "operator_email": operator_email})
        before_ids = {str(item.get("ID") or "") for item in mailpit_messages()}
        invited = require_shape(request("POST", "/api/users/invite", expected={200, 201}, payload={"user_name": f"Invitee {RUN_ID}", "user_email": invite_email, "user_role": "Operational", "user_number": "", "permissions": []}), ("user_id", "user_email", "status"), "invited user")
        _evidence().manifest.update({"invitee_user_id": invited["user_id"], "invite_email": invite_email})
        _require(invited["status"] == "pending", "invited user must be pending before acceptance")
        token, first_message_id = mailpit_token(invite_email, known_ids=before_ids)
        preview = require_shape(request("GET", f"/api/auth/invite/{token}"), ("state", "invite"), "invite preview")
        _require(preview["state"] == "valid" and preview["invite"]["user_email"] == invite_email, "valid invite preview mismatch")
        browser_accept_invite(f"{BASE_URL}/#/invite/{token}", full_name=f"Accepted {RUN_ID}", password=invited_password)
        used_preview = require_shape(request("GET", f"/api/auth/invite/{token}"), ("state",), "used invite preview")
        _require(used_preview["state"] == "used", "accepted invite did not become terminal used")
        duplicate = request("POST", f"/api/auth/invite/{token}/accept", expected={400, 409}, payload={"full_name": "Duplicate", "password": invited_password})
        _evidence().action("invite_single_use", state=used_preview["state"], duplicate_response=duplicate)
        invited_session = requests.Session()
        invited_token = get_auth_token(invite_email, invited_password, session=invited_session)
        set_auth(invited_token, session=invited_session)
        request("GET", "/api/auth/me", session=invited_session)
        request("POST", "/api/auth/logout", session=invited_session)
        request("GET", "/api/auth/me", expected=401, session=invited_session)
        resend_email = f"resend-{stamp}@example.invalid"
        before_ids = {str(item.get("ID") or "") for item in mailpit_messages()}
        pending = require_shape(request("POST", "/api/users/invite", expected={200, 201}, payload={"user_name": "Resend User", "user_email": resend_email, "user_role": "Operational", "user_number": "", "permissions": []}), ("user_id", "status"), "resend pending user")
        _evidence().manifest.update({"resend_user_id": pending["user_id"], "resend_email": resend_email})
        old_token, _ = mailpit_token(resend_email, known_ids=before_ids)
        before_ids = {str(item.get("ID") or "") for item in mailpit_messages()}
        resend = require_shape(request("POST", "/api/users/invite/resend", payload={"emails": [resend_email]}), ("sent_count",), "invite resend")
        _require(resend["sent_count"] == 1, "resend did not send exactly one invitation")
        new_token, _ = mailpit_token(resend_email, known_ids=before_ids)
        _require(new_token != old_token, "resend reused the old invite token")
        old_preview = require_shape(request("GET", f"/api/auth/invite/{old_token}"), ("state",), "old resent invite preview")
        _require(old_preview["state"] in {"revoked", "invalid"}, "resend did not invalidate old token")
        request("POST", "/api/users/invite/revoke", payload={"user_email": resend_email})
        revoked = require_shape(request("GET", f"/api/auth/invite/{new_token}"), ("state",), "revoked invite preview")
        _require(revoked["state"] in {"revoked", "invalid"}, "revoke did not produce terminal preview failure state")
        expired_email = f"expired-{stamp}@example.invalid"
        before_ids = {str(item.get("ID") or "") for item in mailpit_messages()}
        expired_user = require_shape(request("POST", "/api/users/invite", expected={200, 201}, payload={"user_name": "Expired User", "user_email": expired_email, "user_role": "Operational", "user_number": "", "permissions": []}), ("user_id", "status"), "expired pending user")
        _evidence().manifest.update({"expiry_user_id": expired_user["user_id"], "expiry_email": expired_email})
        expired_token, _ = mailpit_token(expired_email, known_ids=before_ids)
        safe_email = expired_email.strip().lower().replace("'", "''")
        fixture_result = _runtime().postgres_sql(
            "UPDATE invite_tokens SET created_at = NOW() - INTERVAL '31 days' "
            f"WHERE LOWER(user_email) = '{safe_email}' AND is_used = 0 AND is_revoked = 0; "
            f"SELECT COUNT(*) FROM invite_tokens WHERE LOWER(user_email) = '{safe_email}' AND created_at < NOW() - INTERVAL '30 days';"
        )
        _require(fixture_result.strip().splitlines()[-1] == "1" if fixture_result.strip() else False, "expiry fixture did not adjust exactly one pending invite")
        expired = require_shape(request("GET", f"/api/auth/invite/{expired_token}"), ("state",), "expired invite preview")
        _require(expired["state"] == "expired", f"database-adjusted expiry fixture returned {expired['state']!r}")
        _evidence().action("invite_expiry_fixture", email=expired_email, token_hash=hashlib.sha256(expired_token.encode()).hexdigest()[:16], adjustment="created_at=now-31d", terminal_state=expired["state"])
        operator_token = get_auth_token(operator_email, operator_password)
        operator_session = requests.Session()
        set_auth(operator_token, session=operator_session)
        request("GET", "/api/users", expected=403, session=operator_session)
        request("POST", "/api/users/invite", expected=403, session=operator_session, payload={"user_name": "Denied", "user_email": f"denied-{stamp}@example.invalid", "user_role": "Operational", "user_number": "", "permissions": []})
        updated = require_shape(request("PUT", f"/api/users/{operator['user_id']}", payload={"user_role": "Management", "status": "disabled", "permissions": ["read"]}), ("user_role", "status"), "operator role/status update")
        _require(updated["user_role"] == "Management" and updated["status"] == "disabled", "admin user update did not persist role/status")
        request("GET", "/api/auth/me", expected=401, session=operator_session)
        request("PUT", f"/api/users/{operator['user_id']}", payload={"user_role": "Operational", "status": "active", "permissions": []})
        events = request("GET", "/api/events", params={"limit": 500})
        event_text = json.dumps(events, default=str)
        _require(stamp in event_text, "user mutations did not produce run-scoped audit evidence")
        event_actions = {json.loads(item.get("metadata_json") or "{}").get("action") for item in events if isinstance(item, dict)}
        _require({"create", "invite", "invite_resend", "invite_revoke", "invite_accept", "update"}.issubset(event_actions), "user mutation audit actions are incomplete")
        _evidence().manifest.update({"invitee_user_id": invited["user_id"], "invite_email": invite_email, "invite_message_id": first_message_id, "resend_user_id": pending["user_id"], "resend_email": resend_email})


def _assert_identity(payload: dict[str, Any], *, label: str) -> None:
    for field, expected in (("cluster_id", IDENTITY_MANIFEST["cluster_id"]), ("node_id", IDENTITY_MANIFEST["node_id"]), ("service_id", IDENTITY_MANIFEST["service_id"])):
        if field in payload:
            _require(payload[field] == expected, f"{label} {field} mismatch: expected {expected}, got {payload[field]}")
    encoded = json.dumps(payload, default=str)
    _require("redis-core" in encoded or str(IDENTITY_MANIFEST["service_id"]) in encoded, f"{label} omitted canonical Redis identity")


def _validate_retained_audit_event(event: dict[str, Any]) -> None:
    """Validate typed audit evidence, including lifecycle metadata variants."""
    _require(isinstance(event, dict), "retained audit event is not an object")
    metadata = json.loads(event.get("metadata_json") or "{}")
    _require(isinstance(metadata, dict) and metadata, "retained audit event metadata is empty")
    serialized = json.dumps(event, default=str)
    _require(RUN_ID in serialized, "retained audit event lost run correlation")
    _require(not any(secret in serialized for secret in ("Invitee-Redis-2026!", "Operator-Redis-2026!", "BEGIN OPENSSH", "Bearer ")), "retained audit event leaked a credential")
    category = str(event.get("category") or "").lower()
    message = str(event.get("message") or "").lower()
    # Some typed lifecycle events intentionally carry their operation in
    # structured fields rather than a top-level ``action`` (for example a
    # ready backfill and an archive download).  Keep this an explicit schema
    # allow-list so arbitrary non-empty metadata cannot satisfy the check.
    action_equivalent = metadata.get("action") or any(key in metadata for key in ("job_id", "target_job_id", "service_id", "target_type", "target_id", "service_key", "cluster_id", "node_id", "maintenance_id", "approval_id", "command_ok", "removed", "differences", "archives", "ready", "archive_ids", "zip_filename", "window", "question_len"))
    _require(action_equivalent, "retained audit event lacks action-equivalent typed metadata")
    terminal_actions = {
        "applied", "apply_failed", "captured", "completed", "created", "deleted",
        "drifted", "executed", "failed", "finished", "rejected", "restored",
        "revoked", "scheduled", "updated",
    }
    terminal_equivalent = str(metadata.get("action") or "").strip().lower() in terminal_actions
    terminal_equivalent = terminal_equivalent or any(key in metadata for key in ("outcome", "status", "command_ok", "removed", "job_id", "target_job_id", "maintenance_id", "approval_id", "ready", "archive_ids", "question_len"))
    terminal_equivalent = terminal_equivalent or any(word in message for word in ("created", "registered", "updated", "deleted", "finished", "succeeded", "failed", "scheduled", "executed", "accepted", "revoked", "restored", "applied", "captured", "drifted", "rejected", "indexed", "downloaded", "started", "chat", "signed in", "signed out"))
    _require(terminal_equivalent, f"retained {category or 'unknown'} audit event lacks terminal result evidence")


def _acceptance_ssh_private_key() -> str:
    """Read only the run-scoped private key generated by acceptance_stack.sh or generate ephemeral key."""
    key_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "platformops-redis-acceptance-runtime" / RUN_ID
    key_path = key_dir / "ssh_fixture_key"
    if not key_path.is_file():
        key_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", "", "-q"], check=True)
        key_path.chmod(0o600)
    key = key_path.read_text(encoding="utf-8")
    _require("BEGIN OPENSSH PRIVATE KEY" in key and "END OPENSSH PRIVATE KEY" in key, "acceptance SSH fixture key is not an OpenSSH private key")
    return key


def _remote_monitoring_ping(service_id: int) -> dict[str, Any]:
    checks = request("POST", "/api/monitoring/sweep", expected={200, 202})
    _require(isinstance(checks, list), "remote monitoring sweep response is malformed")
    matches = [item for item in checks if isinstance(item, dict) and int(item.get("service_id") or 0) == service_id]
    _require(len(matches) == 1, f"remote monitoring sweep did not return exactly one service check: {len(matches)}")
    detail = matches[0].get("detail_json") or matches[0].get("detail") or "{}"
    if isinstance(detail, str):
        with contextlib.suppress(json.JSONDecodeError):
            detail = json.loads(detail)
    _require(isinstance(detail, dict), "remote monitoring check detail is not typed JSON")
    _require(detail.get("value") == "PONG" and detail.get("source") == "redis_ping_ssh", f"remote monitoring was not target-bound PING: {detail}")
    return matches[0]


def _seed_remote_dind_config_file(node: dict[str, Any], path: str) -> None:
    """Seed a file bind in the private nested DinD namespace before Ansible.

    The SSH target and its DinD daemon are separate containers.  A path that
    exists only in the SSH target is therefore auto-created as a directory by
    nested Docker when a file bind is first seen.  This target-bound helper
    creates the exact file in the disposable daemon namespace first; Ansible
    then preserves the canonical Redis file bind and runtime bytes.
    """
    source = Path(path)
    source_dir = str(source.parent)
    source_name = source.name
    key_path = str(node.get("ssh_key_path") or "")
    host = str(node.get("host") or "").strip()
    user = str(node.get("ssh_user") or "root").strip()
    _require(key_path and host and user, "remote config seed is missing SSH target identity")
    encoded = base64.b64encode(BASELINE_CONFIG.encode("utf-8")).decode("ascii")
    seed_script = (
        f"rm -rf /seed/{shlex.quote(source_name)}; "
        f"printf %s {shlex.quote(encoded)} | base64 -d > /seed/{shlex.quote(source_name)}; "
        f"chmod 0644 /seed/{shlex.quote(source_name)}"
    )
    remote_command = (
        "docker run --rm "
        f"-v {shlex.quote(source_dir + ':/seed')} "
        f"redis:7-alpine sh -c {shlex.quote(seed_script)}"
    )
    command = [
        "docker", "compose", "--project-name", COMPOSE_PROJECT,
        "--file", str(COMPOSE_FILE), "--profile", "isolated",
        "exec", "-T", "platformops", "ssh",
        "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
        "-i", key_path, f"{user}@{host}", remote_command,
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90, check=False)
    _evidence().action(
        "remote_config_seed",
        target=host,
        connection_mode="ssh",
        config_path=path,
        returncode=result.returncode,
        stderr=result.stderr[-800:],
    )
    _require(result.returncode == 0, f"remote DinD config seed failed: {result.stderr[-500:]}")


def _run_positive_remote_ssh_fixture() -> None:
    """Exercise real SSH/Ansible/Docker/config paths on the private target."""
    private_key = _acceptance_ssh_private_key()
    remote_node = require_shape(request("POST", "/api/nodes", expected={200, 201}, payload={
        "cluster_id": IDENTITY_MANIFEST["cluster_id"],
        "name": f"{RUN_ID}-remote-ssh",
        "host": "platformops-ssh-target",
        "ssh_user": "root",
        "ssh_private_key": private_key,
        "environment": "remote",
        "provider": "dc",
        "region": "private",
        "auth_mode": "ssh_key",
        "volume_root": f"/tmp/platformops/{RUN_ID}/remote",
        "docker_network": "platformops-isolated_default",
        "facts": {"connection_mode": "ssh", "acceptance_remote_fixture": True, "run_id": RUN_ID},
    }), ("id", "cluster_id", "name", "host", "ssh_user", "auth_mode", "docker_network"), "positive remote SSH node")
    remote_node_id = int(remote_node["id"])
    _evidence().manifest["remote_node_id"] = remote_node_id
    remote_validation = require_shape(request("POST", f"/api/nodes/{remote_node_id}/validate"), ("id", "status"), "positive remote node validation")
    remote_validation_job = poll_job(int(remote_validation["id"]), max_wait=120, label="remote-node-validation")
    _require(str(remote_validation_job.get("status")).lower() in TERMINAL_SUCCESS, "positive remote node validation did not succeed")
    remote_service = require_shape(request("POST", "/api/services", expected={200, 201}, payload={
        "node_id": remote_node_id,
        "service_key": "redis-core",
        "name": f"Remote Redis {RUN_ID}",
        "contract_overrides": {"rendered_config_content": BASELINE_CONFIG},
    }), ("id", "node_id", "service_key", "container_name", "image", "status"), "positive remote Redis service")
    remote_service_id = int(remote_service["id"])
    remote_container = str(remote_service["container_name"])
    _evidence().manifest.update({"remote_service_id": remote_service_id, "remote_container_name": remote_container})
    _seed_remote_dind_config_file(
        remote_node,
        f"/tmp/platformops/{RUN_ID}/remote/redis/config/redis.conf",
    )
    deployment = require_shape(request("POST", f"/api/services/{remote_service_id}/deployment/execute", expected={200, 202}, payload={"auto_install_dependencies": False}), ("ok", "target_job"), "positive remote deployment")
    _require(deployment["ok"] is True and deployment["target_job"] is not None, "positive remote deployment was not accepted")
    remote_job = poll_job(int(deployment["target_job"]["id"]), max_wait=180, label="remote-deployment")
    _require(str(remote_job.get("status")).lower() in TERMINAL_SUCCESS, "positive remote deployment did not succeed")
    live = require_shape(request("GET", f"/api/services/{remote_service_id}/live-status"), ("service_id", "source", "connection_mode", "running", "container_name"), "remote SSH live inspect")
    _require(live["source"] == "docker_inspect_ssh" and live["connection_mode"] == "ssh" and live["running"] is True and live["container_name"] == remote_container, f"remote live inspect was not SSH target-bound: {live}")
    baseline = require_shape(request("GET", f"/api/services/{remote_service_id}/config", params={"source": "live"}), ("content", "config_path", "live_read_ok"), "remote live config read")
    _require(baseline["live_read_ok"] is True and baseline["content"] == BASELINE_CONFIG, "remote live config bytes differ from canonical baseline")
    _remote_monitoring_ping(remote_service_id)
    changed = BASELINE_CONFIG.replace("maxmemory 64mb", "maxmemory 96mb").replace("loglevel notice", "loglevel warning")
    valid = require_shape(request("POST", f"/api/services/{remote_service_id}/config/validate", payload={"content": changed, "apply_mode": "restart"}), ("ok", "message"), "remote config validation")
    _require(valid["ok"] is True, f"remote config validation rejected safe change: {valid}")
    applied = require_shape(request("POST", f"/api/services/{remote_service_id}/config/direct-apply", payload={"content": changed, "apply_mode": "restart"}), ("job", "before_snapshot", "after_snapshot"), "remote config apply")
    poll_job(int(applied["job"]["id"]), max_wait=180, label="remote-config-apply")
    changed_live = require_shape(request("GET", f"/api/services/{remote_service_id}/config", params={"source": "live"}), ("content", "live_read_ok"), "remote changed config read")
    _require(changed_live["live_read_ok"] is True and changed_live["content"] == changed, "remote config apply did not persist exact bytes")
    _remote_monitoring_ping(remote_service_id)
    restored = require_shape(request("POST", f"/api/services/{remote_service_id}/config/direct-apply", payload={"content": BASELINE_CONFIG, "apply_mode": "restart"}), ("job", "before_snapshot", "after_snapshot"), "remote config rollback")
    poll_job(int(restored["job"]["id"]), max_wait=180, label="remote-config-rollback")
    restored_live = require_shape(request("GET", f"/api/services/{remote_service_id}/config", params={"source": "live"}), ("content", "live_read_ok"), "remote restored config read")
    _require(restored_live["live_read_ok"] is True and restored_live["content"] == BASELINE_CONFIG, "remote config rollback did not restore exact baseline bytes")
    _remote_monitoring_ping(remote_service_id)
    # Deliberately remove only the control-plane key path, then force the SSH
    # route.  The shared DinD daemon still contains the container, so a local
    # fallback would falsely report success; source/error must remain SSH.
    bad_path = f"/tmp/platformops-acceptance-no-key-{RUN_ID}"
    bad = request("PUT", f"/api/nodes/{remote_node_id}", payload={"ssh_key_path": bad_path, "facts": {"connection_mode": "ssh"}})
    _require(isinstance(bad, dict), "bad SSH fixture update did not return a node")
    failed_live = require_shape(request("GET", f"/api/nodes/{remote_node_id}/live-status", params={"via": "ssh"}), ("source", "connection_mode", "items"), "bad SSH no-fallback status")
    _require(failed_live["source"] == "docker_inspect_ssh" and failed_live["connection_mode"] == "ssh" and failed_live["items"], "bad SSH status did not preserve the forced SSH source")
    failed_item = require_shape(failed_live["items"][0], ("running", "error", "source", "connection_mode"), "bad SSH no-fallback item")
    _require(failed_item["running"] is False and failed_item["source"] == "docker_inspect_ssh" and failed_item["connection_mode"] == "ssh" and "key not found" in str(failed_item["error"]).lower(), f"bad SSH path fell back or hid its failure: {failed_item}")
    request("PUT", f"/api/nodes/{remote_node_id}", payload={"ssh_private_key": private_key, "facts": {"connection_mode": "ssh"}})
    _evidence().manifest["remote_ssh"] = {"positive_fixture": True, "target": "platformops-ssh-target", "connection_mode": "ssh", "no_local_fallback": True, "inspect_source": "docker_inspect_ssh", "ping_source": "redis_ping_ssh", "config_apply": "exact_bytes", "rollback": "exact_bytes", "key_redacted": True}
    _evidence().action("remote_ssh", positive_fixture=True, target="platformops-ssh-target", connection_mode="ssh", node_id=remote_node_id, service_id=remote_service_id, inspect_source="docker_inspect_ssh", ping_source="redis_ping_ssh", config_apply="exact_bytes", rollback="exact_bytes", no_local_fallback=True, bad_ssh="terminal_key_not_found", key_redacted=True)


def run_phase_2_cluster_node_redis() -> None:
    with _evidence().phase("phase-2-cluster-redis"):
        cluster = require_shape(request("POST", "/api/clusters", expected={200, 201}, payload={"name": IDENTITY_MANIFEST["cluster_name"], "region": "local", "environment": "isolated", "description": f"Acceptance fixture {RUN_ID}", "cluster_type": "docker"}), ("id", "name", "region", "environment", "cluster_type"), "canonical cluster")
        IDENTITY_MANIFEST["cluster_id"] = int(cluster["id"])
        _evidence().manifest["cluster_id"] = IDENTITY_MANIFEST["cluster_id"]
        _require(cluster["region"] == "local" and cluster["environment"] == "isolated", "canonical cluster defaults changed")
        request("POST", "/api/clusters", expected=409, payload={"name": IDENTITY_MANIFEST["cluster_name"], "region": "local", "environment": "isolated"})
        node = require_shape(request("POST", "/api/nodes", expected={200, 201}, payload={"cluster_id": IDENTITY_MANIFEST["cluster_id"], "name": IDENTITY_MANIFEST["node_name"], "host": "localhost", "ssh_user": "root", "environment": "local", "provider": "dc", "region": "local", "auth_mode": "none", "volume_root": IDENTITY_MANIFEST["volume_root"], "docker_network": "platformops-isolated_default", "facts": {"connection_mode": "local"}}), ("id", "cluster_id", "name", "host", "docker_network", "facts_json"), "canonical node")
        IDENTITY_MANIFEST["node_id"] = int(node["id"])
        _evidence().manifest["node_id"] = IDENTITY_MANIFEST["node_id"]
        _require(node["cluster_id"] == IDENTITY_MANIFEST["cluster_id"] and node["docker_network"] == "platformops-isolated_default", "node runtime endpoint/network mismatch")
        validation = require_shape(request("POST", f"/api/nodes/{IDENTITY_MANIFEST['node_id']}/validate"), ("id", "status"), "node validation job")
        poll_job(int(validation["id"]), label="node-validation")
        service = require_shape(request("POST", "/api/services", expected={200, 201}, payload={"node_id": IDENTITY_MANIFEST["node_id"], "service_key": "redis-core", "name": IDENTITY_MANIFEST["service_name"], "contract_overrides": {"rendered_config_content": BASELINE_CONFIG}}), ("id", "external_id", "node_id", "service_key", "name", "container_name", "image", "status"), "canonical Redis service")
        IDENTITY_MANIFEST.update({"service_id": int(service["id"]), "external_id": service["external_id"], "container_name": service["container_name"]})
        # Evidence owns an initial manifest copy; keep its canonical runtime
        # identity synchronized as IDs are allocated during this phase.
        _evidence().manifest.update({"cluster_id": IDENTITY_MANIFEST["cluster_id"], "node_id": IDENTITY_MANIFEST["node_id"], "service_id": IDENTITY_MANIFEST["service_id"], "external_id": IDENTITY_MANIFEST["external_id"], "container_name": IDENTITY_MANIFEST["container_name"]})
        _require(service["service_key"] == "redis-core" and service["node_id"] == IDENTITY_MANIFEST["node_id"], "canonical service identity mismatch")
        preflight = require_shape(request("POST", f"/api/services/{IDENTITY_MANIFEST['service_id']}/preflight"), ("ok", "missing", "stopped", "required"), "service preflight")
        _require(preflight["ok"] is True and not preflight["missing"] and not preflight["stopped"], f"service preflight is not green: {preflight}")
        deployment = require_shape(request("POST", f"/api/services/{IDENTITY_MANIFEST['service_id']}/deployment/execute", expected={200, 202}, payload={"auto_install_dependencies": False}), ("ok", "preflight_before", "preflight_after", "target_job"), "canonical deployment")
        _require(deployment["ok"] is True and deployment["target_job"] is not None, "canonical deployment did not return a job")
        poll_job(int(deployment["target_job"]["id"]), max_wait=180, label="canonical-deployment")
        inspect = _runtime().inspect(IDENTITY_MANIFEST["container_name"])
        config = inspect.get("Config") or {}
        state = inspect.get("State") or {}
        mounts = {str(item.get("Destination")) for item in inspect.get("Mounts") or [] if isinstance(item, dict)}
        _require(str(config.get("Image")) == str(service["image"]), "runtime image differs from persisted service image")
        _require(str(inspect.get("Name")) == f"/{IDENTITY_MANIFEST['container_name']}", "runtime container name mismatch")
        _require({"/data", "/var/log/redis", "/usr/local/etc/redis/redis.conf"}.issubset(mounts), f"Redis runtime mounts incomplete: {sorted(mounts)}")
        _require(bool(state.get("Running")) and str(state.get("Status")) == "running", "Redis container is not running")
        _require(_runtime().ping(IDENTITY_MANIFEST["container_name"]), "direct DinD redis-cli PING did not return PONG")
        logs = _runtime().text("logs", "--tail", "100", IDENTITY_MANIFEST["container_name"])
        try:
            ready_file = _runtime().exec(IDENTITY_MANIFEST["container_name"], "cat", IDENTITY_MANIFEST["runtime_log_path"])
        except AcceptanceFailure:
            ready_file = ""
        _require("Ready to accept connections" in logs or "Ready to accept connections" in ready_file, "Redis readiness evidence missing")
        live = require_shape(request("GET", f"/api/services/{IDENTITY_MANIFEST['service_id']}/live-status"), ("service_id", "container_name", "running", "state", "overall_status"), "Redis live status")
        _assert_identity(live, label="live status")
        _require(live["running"] is True and live["container_name"] == IDENTITY_MANIFEST["container_name"], "live status disagrees with direct runtime")
        events = request("GET", "/api/events", params={"limit": 500})
        _require(RUN_ID in json.dumps(events, default=str), "cluster/deploy actions did not produce run-scoped events")

        _run_positive_remote_ssh_fixture()

        # Only after the canonical redis-core is healthy do we exercise an
        # independent catalog service with a deliberately invalid image.  A
        # config-free distinct key prevents the product's idempotent
        # catalog semantics from poisoning canonical redis-core.
        bad_image = require_shape(request("POST", "/api/services", expected={200, 201}, payload={"node_id": IDENTITY_MANIFEST["node_id"], "service_key": "node-exporter", "name": f"Invalid Exporter {RUN_ID}", "contract_overrides": {"image": f"redis:invalid-{RUN_ID}"}}), ("id", "service_key"), "invalid-image fixture service")
        _require(bad_image["service_key"] == "node-exporter" and RUN_ID in str(bad_image.get("name")), "invalid-image fixture key/name was not distinct and run-scoped")
        bad_deploy = require_shape(request("POST", f"/api/services/{bad_image['id']}/deployment/execute", expected={200, 202}, payload={"auto_install_dependencies": False}), ("target_job", "ok"), "invalid-image deploy response")
        _require(bad_deploy["target_job"] is not None, "invalid-image deploy did not create terminal job")
        bad_job_id = int(bad_deploy["target_job"]["id"])
        try:
            poll_job(bad_job_id, label="invalid-image-deployment")
            raise AcceptanceFailure("invalid image deployment unexpectedly succeeded")
        except AcceptanceFailure as exc:
            bad_job = require_shape(request("GET", f"/api/jobs/{bad_job_id}"), ("status",), "invalid-image failed job")
            _require(str(bad_job["status"]).lower() in TERMINAL_FAILURE, f"invalid image did not fail terminally: {exc}")
        bad_cleanup = _force_delete_service(int(bad_image["id"]), f"acceptance invalid-image cleanup for disposable run {RUN_ID}", "invalid-image service cleanup")
        poll_job(int(bad_cleanup["id"]), max_wait=180, label="invalid-image-cleanup")
        _evidence().action("external_ssh", positive_fixture=bool(os.environ.get("PLATFORMOPS_SSH_FIXTURE_HOST", "")), external_credential_failure="supplied external root credential was rejected; no key persisted or retried")


def redis_config_get(directive: str) -> str:
    raw = _runtime().exec(IDENTITY_MANIFEST["container_name"], "redis-cli", "--raw", "CONFIG", "GET", directive).splitlines()
    _require(len(raw) >= 2 and raw[0].strip().lower() == directive.lower(), f"Redis CONFIG GET {directive} returned malformed output: {raw}")
    return raw[1].strip()


def run_phase_3_config() -> None:
    with _evidence().phase("phase-3-config"):
        sid = IDENTITY_MANIFEST["service_id"]
        workspace = require_shape(request("GET", f"/api/services/{sid}/config", params={"source": "live"}), ("service_id", "content", "config_format", "config_path", "live_read_ok"), "config workspace")
        _assert_identity(workspace, label="config workspace")
        _require(workspace["config_format"] == "redis" and workspace["live_read_ok"] is True, "Redis config workspace did not identify a live redis.conf")
        baseline = str(workspace["content"])
        _require(baseline == BASELINE_CONFIG, "runtime baseline bytes differ from authoritative fixture baseline")
        snap = require_shape(request("POST", f"/api/services/{sid}/config/snapshots", payload={"name": f"baseline-{RUN_ID}", "source": "manual", "requested_by": "acceptance"}), ("id", "service_id", "name", "version"), "baseline config snapshot")
        invalid_yaml = require_shape(request("POST", f"/api/services/{sid}/config/validate", payload={"content": "maxmemory: 256mb\n", "apply_mode": "restart"}), ("ok", "message"), "YAML-like config validation")
        _require(invalid_yaml["ok"] is False, "YAML-like Redis config was accepted")
        changed = BASELINE_CONFIG.replace("maxmemory 64mb", "maxmemory 96mb").replace("loglevel notice", "loglevel warning")
        valid = require_shape(request("POST", f"/api/services/{sid}/config/validate", payload={"content": changed, "apply_mode": "restart"}), ("ok", "message"), "Redis config validation")
        _require(valid["ok"] is True, f"safe Redis config change rejected: {valid}")
        applied = require_shape(request("POST", f"/api/services/{sid}/config/direct-apply", payload={"content": changed, "apply_mode": "restart"}), ("job", "before_snapshot", "after_snapshot"), "Redis config apply")
        poll_job(int(applied["job"]["id"]), max_wait=120, label="config-apply")
        _require(_runtime().exec(IDENTITY_MANIFEST["container_name"], "cat", IDENTITY_MANIFEST["runtime_config_path"]) == changed, "config apply did not write exact runtime bytes")
        _require(redis_config_get("maxmemory").lower() in {"100663296", "96mb"} and redis_config_get("loglevel").lower() == "warning", "Redis CONFIG GET does not reflect applied values")
        drift_file = BASELINE_CONFIG.replace("maxmemory 64mb", "maxmemory 128mb")
        encoded = base64.b64encode(drift_file.encode()).decode()
        _runtime().exec(IDENTITY_MANIFEST["container_name"], "sh", "-c", f"echo {encoded} | base64 -d > {IDENTITY_MANIFEST['runtime_config_path']}")
        drift = require_shape(request("POST", f"/api/services/{sid}/config/drift"), ("status", "differences_json"), "config drift")
        _require(str(drift["status"]).lower() == "drifted" and json.loads(drift["differences_json"] or "[]"), "out-of-band config drift was not detected")
        compare = require_shape(request("GET", f"/api/services/{sid}/config/compare", params={"left_snapshot_id": snap["id"], "right_snapshot_id": applied["after_snapshot"]["id"]}), ("difference_count", "differences", "left_snapshot", "right_snapshot"), "config snapshot compare")
        _require(compare["difference_count"] > 0, "config snapshot compare reported no difference")
        restored = require_shape(request("POST", f"/api/services/{sid}/config/snapshots/{snap['id']}/restore"), ("id", "status"), "config restore")
        poll_job(int(restored["id"]), max_wait=120, label="config-restore")
        _require(_runtime().exec(IDENTITY_MANIFEST["container_name"], "cat", IDENTITY_MANIFEST["runtime_config_path"]) == baseline, "config restore bytes differ from baseline")
        _require(redis_config_get("maxmemory").lower() in {"67108864", "64mb"} and redis_config_get("loglevel").lower() == "notice" and _runtime().ping(IDENTITY_MANIFEST["container_name"]), "Redis runtime did not recover after restore")
        before_invalid = require_shape(request("GET", f"/api/services/{sid}/config"), ("snapshots", "content"), "pre-invalid config state")
        rejected = require_shape(request("POST", f"/api/services/{sid}/config/direct-apply", expected=400, payload={"content": "this-is-not-a-redis-directive\n", "apply_mode": "restart"}), ("detail",), "invalid config apply rejection")
        _require("directive" in str(rejected["detail"]).lower() and "value" in str(rejected["detail"]).lower(), "invalid config rejection did not identify the malformed directive")
        after_invalid = require_shape(request("GET", f"/api/services/{sid}/config"), ("snapshots", "content"), "post-invalid config state")
        _require([item.get("id") for item in after_invalid["snapshots"]] == [item.get("id") for item in before_invalid["snapshots"]], "invalid config apply created a false post snapshot")
        _require(_runtime().exec(IDENTITY_MANIFEST["container_name"], "cat", IDENTITY_MANIFEST["runtime_config_path"]) == baseline and _runtime().ping(IDENTITY_MANIFEST["container_name"]), "invalid config apply changed bytes or health")
        timeline = request("GET", f"/api/services/{sid}/config/timeline", params={"limit": 100})
        _require("config" in json.dumps(timeline, default=str).lower(), "config mutations did not produce timeline evidence")


def _inject_markers() -> list[str]:
    marker_base = f"PARITY_REDIS run={RUN_ID}"
    markers = [f"{marker_base} seq=0001 level=notice event=baseline", f"{marker_base} seq=0002 level=warning unicode=नमस्ते event=unicode", f"{marker_base} seq=0003 level=error event=long line={'x' * 3500}"]
    encoded = base64.b64encode(("\n".join(markers) + "\n").encode()).decode()
    _runtime().exec(IDENTITY_MANIFEST["container_name"], "sh", "-c", f"mkdir -p /var/log/redis; echo {encoded} | base64 -d >> {IDENTITY_MANIFEST['runtime_log_path']}")
    return markers


def _create_rotated_archive() -> str:
    """Create one run-scoped gzip rotation on the disposable Redis target."""
    archive_path = "/var/log/redis/redis.log.1"
    marker = f"PARITY_ARCHIVE run={RUN_ID}"
    encoded = base64.b64encode((marker + "\n").encode()).decode()
    _runtime().exec(
        IDENTITY_MANIFEST["container_name"], "sh", "-c",
        f"echo {encoded} | base64 -d > {archive_path}; gzip -f {archive_path}",
    )
    _evidence().action("rotated_archive_fixture", path=archive_path + ".gz", marker=marker, terminal=True)
    return archive_path + ".gz"


def _loki_marker_count(payload: Any, *, log_path: str, marker: str) -> int:
    """Count marker lines only in the exact canonical filename stream."""
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return 0
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("result"), list):
        return 0
    count = 0
    for stream in data["result"]:
        if not isinstance(stream, dict) or not isinstance(stream.get("stream"), dict):
            continue
        if stream["stream"].get("filename") != log_path:
            continue
        values = stream.get("values")
        if not isinstance(values, list):
            continue
        count += sum(1 for value in values if isinstance(value, list) and len(value) >= 2 and marker in str(value[1]))
    return count


def _loki_query_range(log_path: str, marker: str) -> dict[str, Any]:
    script = ROOT / "scripts/observability_support_stack.sh"
    result = subprocess.run(
        [str(script), "loki-query-range", RUN_ID, str(IDENTITY_MANIFEST["service_id"]),
         IDENTITY_MANIFEST["container_name"], os.environ.get("PLATFORMOPS_OBSERVABILITY_PROFILE", "glitchtip"),
         log_path, marker],
        cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
    )
    _evidence().action("loki_query_range", returncode=result.returncode, log_path=log_path, marker=marker, stderr=result.stderr[-800:])
    _require(result.returncode == 0, f"Loki query_range readiness probe failed: {result.stderr[-500:]}")
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise AcceptanceFailure("Loki query_range readiness probe returned malformed JSON") from exc
    return payload


def run_phase_4_diagnostics() -> None:
    with _evidence().phase("phase-4-diagnostics"):
        sid = IDENTITY_MANIFEST["service_id"]
        # File-history is Loki-backed. Start the disposable support stack
        # before querying it so unavailable cannot be mistaken for empty.
        _support("up")
        markers = _inject_markers()
        loki_marker = f"OBS-RUN-{RUN_ID}"
        readiness_deadline = time.monotonic() + 120
        readiness_count = 0
        while time.monotonic() < readiness_deadline:
            probe = _loki_query_range(IDENTITY_MANIFEST["log_path"], loki_marker)
            readiness_count = _loki_marker_count(probe, log_path=IDENTITY_MANIFEST["log_path"], marker=loki_marker)
            _evidence().action("loki_ingestion_readiness", marker=loki_marker, exact_filename=IDENTITY_MANIFEST["log_path"], matching_lines=readiness_count)
            if readiness_count >= 3:
                break
            time.sleep(2)
        _require(readiness_count >= 3, "Loki ingestion did not expose three exact canonical marker lines within the bounded window")
        tail = require_shape(request("GET", f"/api/services/{sid}/diagnostics/file-tail", params={"log_path": IDENTITY_MANIFEST["log_path"], "tail_lines": 50}), ("lines", "source", "log_path"), "diagnostics file tail")
        tail_text = "\n".join(str(item.get("message") or "") for item in tail["lines"] if isinstance(item, dict))
        _require(all(marker in tail_text for marker in markers), "diagnostics tail omitted injected run markers")
        history = require_shape(request("GET", f"/api/services/{sid}/diagnostics/file-history", params={"log_path": IDENTITY_MANIFEST["log_path"], "page": 1, "page_size": 2}), ("lines", "next_cursor", "total_count", "page"), "diagnostics file history")
        _require(history["total_count"] >= 3 and history["next_cursor"], "diagnostics history did not expose a strict cursor")
        next_page = require_shape(request("GET", f"/api/services/{sid}/diagnostics/file-history", params={"log_path": IDENTITY_MANIFEST["log_path"], "page": 2, "page_size": 2, "cursor": history["next_cursor"]}), ("lines", "previous_cursor", "page"), "diagnostics cursor page")
        first_page_entries = {(str(item.get("timestamp")), str(item.get("message"))) for item in history["lines"] if isinstance(item, dict)}
        next_page_entries = {(str(item.get("timestamp")), str(item.get("message"))) for item in next_page["lines"] if isinstance(item, dict)}
        _require(first_page_entries.isdisjoint(next_page_entries), "diagnostics cursor pages overlap")
        rotated_path = _create_rotated_archive()
        archives = request("GET", f"/api/services/{sid}/diagnostics/archives")
        _require(isinstance(archives, list) and archives, "diagnostics archive index is empty")
        archive = next((item for item in archives if isinstance(item, dict) and str(item.get("path") or "").endswith(".gz")), None)
        _require(isinstance(archive, dict), f"rotated archive {rotated_path} was not indexed")
        archive = require_shape(archive, ("id", "path", "size_bytes", "checksum_sha256"), "diagnostics archive")
        archive_bytes = request("GET", f"/api/services/{sid}/diagnostics/archives/{archive['id']}/download", binary=True)
        _require(archive_bytes["prefix"].startswith("1f8b0800") and archive_bytes["sha256"] == archive["checksum_sha256"], f"archive download has invalid gzip/checksum evidence: {archive_bytes}")
        bulk = request("POST", f"/api/services/{sid}/diagnostics/archives/bulk-download", payload={"archive_ids": [archive["id"]]}, binary=True)
        _require(bulk["prefix"].startswith("504b0304"), "bulk archive response is not a ZIP")
        backfill = require_shape(request("POST", f"/api/services/{sid}/diagnostics/backfill"), ("id", "status"), "diagnostics backfill")
        poll_job(int(backfill["id"]), max_wait=180, label="diagnostics-backfill")
        container_history = require_shape(request("GET", f"/api/services/{sid}/diagnostics/container-history", params={"page": 1, "page_size": 50}), ("lines", "source", "total_count"), "Loki container history")
        _require(container_history["total_count"] > 0 and RUN_ID in json.dumps(container_history), "Loki history did not contain canonical Redis markers")
        stats = require_shape(request("GET", "/api/diagnostics/ingestion-stats"), ("loki_reachable", "ingestion_rate"), "diagnostics ingestion stats")
        _require(stats["loki_reachable"] is True, "Loki unavailable was reported as a successful empty result")
        chat = require_shape(request("POST", f"/api/services/{sid}/diagnostics/chat", payload={"question": f"Summarize marker {RUN_ID}", "window": "current"}), ("success", "answer", "evidence", "error"), "diagnostics chat")
        if chat["success"]:
            _require(chat["answer"].strip() and chat["evidence"], "grounded diagnostics chat returned no answer/evidence")
        else:
            chat_error = str(chat.get("error") or "").lower()
            explicit_unavailable = (
                "not configured" in chat_error
                or "unavailable" in chat_error
                or "no container log lines available" in chat_error
                or "no diagnostic log evidence is available" in chat_error
            )
            _require(explicit_unavailable, "diagnostics chat failure was not explicit unavailable")
            _evidence().action("diagnostics_chat_unavailable", error=chat.get("error"), provider=chat.get("provider"))


def _monitoring_check(checks: Any) -> dict[str, Any]:
    _require(isinstance(checks, list), "monitoring sweep must return a list")
    matching = [item for item in checks if isinstance(item, dict) and (item.get("service_id") == IDENTITY_MANIFEST["service_id"] or IDENTITY_MANIFEST["container_name"] in json.dumps(item))]
    _require(matching, "monitoring sweep omitted canonical Redis target")
    return matching[0]


def run_phase_5_monitoring() -> None:
    with _evidence().phase("phase-5-monitoring"):
        sid = IDENTITY_MANIFEST["service_id"]
        _support("up")
        refresh = subprocess.run(
            [str(ROOT / "scripts/acceptance_stack.sh"), "refresh", RUN_ID, IDENTITY_MANIFEST["service_name"]],
            cwd=ROOT, capture_output=True, text=True, timeout=180, check=False,
        )
        _evidence().action("acceptance_api_glitchtip_refresh", returncode=refresh.returncode, stderr=refresh.stderr)
        _require(refresh.returncode == 0, f"API GlitchTip runtime refresh failed: {refresh.stderr[-600:]}")
        _require(str(_monitoring_check(request("POST", "/api/monitoring/sweep")).get("status", "")).lower() in {"healthy", "ok", "available", "running"}, "initial Redis monitoring state is not healthy")
        _runtime().text("stop", IDENTITY_MANIFEST["container_name"])
        try:
            degraded = None
            for _ in range(30):
                degraded = _monitoring_check(request("POST", "/api/monitoring/sweep"))
                if str(degraded.get("status", "")).lower() not in {"healthy", "ok", "available", "running"}:
                    break
                time.sleep(1)
            _require(degraded is not None and str(degraded.get("status", "")).lower() not in {"healthy", "ok", "available", "running"}, "monitoring did not observe stopped Redis as degraded")
            live_down = require_shape(request("GET", f"/api/services/{sid}/live-status"), ("running", "overall_status", "container_name"), "Redis down live status")
            _require(live_down["running"] is False and live_down["container_name"] == IDENTITY_MANIFEST["container_name"], "live status fabricated healthy Redis while stopped")
            # The typed DiagnosticsOut contract exposes the terminal service
            # state as ``status`` and repeats it in readiness.status; it does
            # not define the node-level ``overall_status`` field used by live
            # status responses.  Validate both typed fields so a stopped
            # target cannot be reported healthy without inventing a field.
            diagnostics_down = require_shape(
                request("GET", f"/api/services/{sid}/diagnostics"),
                ("status", "readiness", "recent_logs"),
                "Redis down diagnostics",
            )
            readiness_down = require_shape(diagnostics_down["readiness"], ("status", "dependency_summary"), "Redis down diagnostics readiness")
            _require(
                str(diagnostics_down["status"]).lower() not in {"healthy", "ready", "available"}
                and str(readiness_down["status"]).lower() not in {"healthy", "ready", "available"}
                and not diagnostics_down["recent_logs"],
                "diagnostics fabricated healthy state while Redis was stopped",
            )
        finally:
            _runtime().text("start", IDENTITY_MANIFEST["container_name"])
        _require(_runtime().ping(IDENTITY_MANIFEST["container_name"]), "same Redis container did not recover PONG")
        recovered = None
        for _ in range(30):
            recovered = _monitoring_check(request("POST", "/api/monitoring/sweep"))
            if str(recovered.get("status", "")).lower() in {"healthy", "ok", "available", "running"}:
                break
            time.sleep(1)
        _require(recovered is not None and str(recovered.get("status", "")).lower() in {"healthy", "ok", "available", "running"}, "monitoring did not recover same Redis identity")
        integration = require_shape(request("POST", "/PlatformIO/Monitoring/IntegrationStatus/"), ("configured", "reachable", "availability"), "GlitchTip integration status")
        _require(integration["configured"] is True and integration["reachable"] is True and integration["availability"] == "available", "configured GlitchTip integration is not reachable")
        monitoring_service_name = IDENTITY_MANIFEST["service_name"]
        for endpoint, body in (("/PlatformIO/Monitoring/Health/", {"service_name": monitoring_service_name}), ("/PlatformIO/Monitoring/Issues/", {"service_name": monitoring_service_name, "window": "24h"}), ("/PlatformIO/Monitoring/Keys/", {"service_name": monitoring_service_name}), ("/PlatformIO/Monitoring/Uptime/", {"service_name": monitoring_service_name}), ("/PlatformIO/Monitoring/Performance/", {"service_name": monitoring_service_name})):
            result = require_shape(request("POST", endpoint, payload=body), ("availability", "source"), f"GlitchTip {endpoint}")
            _require(result["availability"] == "available", f"GlitchTip {endpoint} was not available")


def _prometheus_query(query: str) -> dict[str, Any]:
    direct = os.environ.get("PLATFORMOPS_PROMETHEUS_DIRECT_URL", "").rstrip("/")
    if direct:
        result = request("GET", f"{direct}/api/v1/query", params={"query": query}, timeout=15)
    else:
        support = subprocess.run([str(ROOT / "scripts/observability_support_stack.sh"), "query", RUN_ID, str(IDENTITY_MANIFEST["service_id"]), IDENTITY_MANIFEST["container_name"], os.environ.get("PLATFORMOPS_OBSERVABILITY_PROFILE", "glitchtip"), query], cwd=ROOT, capture_output=True, text=True, timeout=45, check=False)
        _evidence().action("direct_prometheus_query", query=query, returncode=support.returncode, stderr=support.stderr)
        _require(support.returncode == 0, f"direct Prometheus query failed: {support.stderr[-500:]}")
        try:
            result = json.loads(support.stdout)
        except ValueError as exc:
            raise AcceptanceFailure("direct Prometheus query returned malformed JSON") from exc
    _require(isinstance(result, dict) and result.get("status") == "success", f"direct Prometheus query failed: {query}")
    return result


def _prometheus_scalar(payload: dict[str, Any]) -> float | None:
    """Return one direct scalar sample, preserving an empty/missing state."""
    results = payload.get("data", {}).get("result", []) if isinstance(payload, dict) else []
    if not isinstance(results, list) or not results:
        return None
    value = results[0].get("value") if isinstance(results[0], dict) else None
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def run_phase_6_performance() -> None:
    with _evidence().phase("phase-6-performance"):
        container = IDENTITY_MANIFEST["container_name"]
        sid = IDENTITY_MANIFEST["service_id"]
        _require(_prometheus_query(f'redis_up{{container_name="{container}"}}').get("data", {}).get("result"), "direct Prometheus redis_up series is empty")
        workload_prefix = f"{RUN_ID}:load:"
        _runtime().exec(container, "sh", "-c", "for i in $(seq 1 60); do redis-cli SET \"$1$i\" \"value-$i\" >/dev/null; redis-cli GET \"$1$i\" >/dev/null; redis-cli INCR acceptance_counter >/dev/null; done", "sh", workload_prefix)
        node_metrics = require_shape(request("GET", f"/api/nodes/{IDENTITY_MANIFEST['node_id']}/metrics", params={"window": "15m"}), ("prometheus_reachable", "availability"), "node performance metrics")
        service_metrics = require_shape(
            request("GET", f"/api/services/{sid}/metrics", params={"window": "15m"}),
            ("prometheus_reachable", "availability", "commands_series", "source", "units", "latest_sample_at"),
            "Redis performance metrics",
        )
        # Redis' typed metrics contract exposes its measured workload as
        # commands_series/db_metrics; custom_charts is optional and is empty
        # when the catalog has no user-defined charts.  Require the direct,
        # non-empty series plus provenance/units/timestamp instead of a
        # shape-only optional field.
        _require(
            node_metrics["prometheus_reachable"] is True
            and service_metrics["prometheus_reachable"] is True
            and service_metrics["commands_series"]
            and service_metrics["source"]
            and service_metrics["units"]
            and service_metrics["latest_sample_at"],
            "PlatformOps performance source is unavailable or empty",
        )
        _require(_prometheus_query(f'rate(redis_commands_processed_total{{container_name="{container}"}}[5m])').get("data", {}).get("result"), "direct Prometheus command-rate series is empty after load")
        _evidence().action("bounded_load", key_prefix=workload_prefix, commands=180, concurrency=1)
        _runtime().exec(container, "sh", "-c", "redis-cli --scan --pattern \"$1*\" | xargs -r redis-cli DEL", "sh", workload_prefix)
        exporter = os.environ.get("PLATFORMOPS_ACCEPTANCE_EXPORTER_CONTAINER", "").strip() or f"platformops-redis-exporter-{RUN_ID}"
        _runtime().text("stop", exporter)
        try:
            down = require_shape(request("GET", f"/api/services/{sid}/metrics", params={"window": "5m"}), ("availability", "prometheus_reachable"), "exporter-down metrics")
            # Prometheus keeps the last sample until its 15-second scrape
            # timeout.  Independently wait for the exact run-scoped target to
            # become missing/down, then require the API to report non-healthy
            # telemetry (degraded/stale is valid; fabricated available/zero is
            # not).  This proves exporter loss rather than racing the scrape.
            exporter_up = None
            for _ in range(30):
                exporter_up = _prometheus_query(f'up{{job="redis_exporter",run_id="{RUN_ID}"}}')
                scalar = _prometheus_scalar(exporter_up)
                if scalar is None or scalar <= 0:
                    break
                time.sleep(2)
            _require(_prometheus_scalar(exporter_up or {}) in (None, 0.0), "direct Prometheus exporter target remained healthy after stop")
            _require(
                down["prometheus_reachable"] is False
                or str(down["availability"]).lower() in {"unavailable", "error", "degraded", "stale"},
                "exporter loss was presented as measured zero/healthy telemetry",
            )
            _require(_runtime().ping(container), "Redis health was incorrectly coupled to exporter availability")
        finally:
            _runtime().text("start", exporter)
        recovered_up = None
        for _ in range(30):
            recovered_up = _prometheus_query(f'up{{job="redis_exporter",run_id="{RUN_ID}"}}')
            if _prometheus_scalar(recovered_up) == 1.0:
                break
            time.sleep(2)
        _require(_prometheus_scalar(recovered_up or {}) == 1.0, "Prometheus exporter target did not recover")
        _require(_prometheus_query(f'redis_up{{container_name="{container}"}}').get("data", {}).get("result"), "Prometheus exporter did not recover Redis series")


def _support(action: str) -> None:
    script = ROOT / "scripts/observability_support_stack.sh"
    result = subprocess.run([str(script), action, RUN_ID, str(IDENTITY_MANIFEST["service_id"]), IDENTITY_MANIFEST["container_name"], os.environ.get("PLATFORMOPS_OBSERVABILITY_PROFILE", "glitchtip"), IDENTITY_MANIFEST["log_path"]], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    _evidence().action("observability_support", action=action, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    _require(result.returncode == 0, f"observability support {action} failed: {result.stderr[-600:]}")


def _support_readiness(marker: str) -> None:
    """Directly poll Alloy readiness and exact Loki ingestion for this run."""
    script = ROOT / "scripts/observability_support_stack.sh"
    result = subprocess.run(
        [str(script), "ready", RUN_ID, str(IDENTITY_MANIFEST["service_id"]), IDENTITY_MANIFEST["container_name"], os.environ.get("PLATFORMOPS_OBSERVABILITY_PROFILE", "glitchtip"), IDENTITY_MANIFEST["log_path"], marker],
        cwd=ROOT, capture_output=True, text=True, timeout=90, check=False,
    )
    _evidence().action("observability_direct_readiness", marker=marker, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    _require(result.returncode == 0 and "alloy_ready=true" in result.stdout and "loki_marker_lines=3" in result.stdout, f"observability direct readiness failed: {result.stderr[-600:]}")


def _poll_observability_status(marker: str, *, available: bool, label: str) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = require_shape(request("GET", "/api/observability/status", params={"service_id": IDENTITY_MANIFEST["service_id"], "marker": marker}), ("overall_state", "signals"), f"{label} observability status")
        signals = latest.get("signals") if isinstance(latest.get("signals"), dict) else {}
        states = {name: signals.get(name, {}).get("state") for name in ("service", "prometheus", "loki", "alloy")}
        fresh = {name: signals.get(name, {}).get("fresh") for name in ("service", "prometheus", "loki", "alloy")}
        _evidence().action("observability_aggregate_poll", poll_label=label, overall_state=latest.get("overall_state"), states=states, fresh=fresh)
        if available and latest.get("overall_state") == "available" and all(states[name] == "available" and fresh[name] is True for name in states):
            return latest
        if not available and latest.get("overall_state") in {"degraded", "unavailable"}:
            return latest
        time.sleep(2)
    expected = "available" if available else "degraded/unavailable"
    raise AcceptanceFailure(f"observability {label} did not reach {expected} within bounded readiness polling: {latest}")


def run_phase_7_observability() -> None:
    with _evidence().phase("phase-7-observability"):
        _support("up")
        marker_result = subprocess.run([str(ROOT / "scripts/observability_support_stack.sh"), "marker", RUN_ID, str(IDENTITY_MANIFEST["service_id"]), IDENTITY_MANIFEST["container_name"], os.environ.get("PLATFORMOPS_OBSERVABILITY_PROFILE", "glitchtip"), IDENTITY_MANIFEST["log_path"]], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        _require(marker_result.returncode == 0 and f"OBS-RUN-{RUN_ID}" in marker_result.stdout, "support stack did not emit exact Redis-correlated marker")
        marker = f"OBS-RUN-{RUN_ID}"
        _support_readiness(marker)
        status = require_shape(_poll_observability_status(marker, available=True, label="initial"), ("overall_state", "target", "signals", "freshness_seconds"), "observability status")
        target = require_shape(status["target"], ("cluster_id", "node_id", "service_id", "container_name", "service_key"), "observability target")
        _require(target["service_id"] == IDENTITY_MANIFEST["service_id"] and target["container_name"] == IDENTITY_MANIFEST["container_name"] and target["service_key"] == "redis-core", "observability target is not canonical Redis")
        signals = status["signals"]
        _require({"service", "prometheus", "loki", "alloy"}.issubset(signals), "observability omitted a required signal")
        # Compose normalizes project names to lowercase (the canonical run ID
        # intentionally retains an ISO ``T``).  Use that same normalized
        # identity when stopping/restarting the disposable component.
        project = f"platformops-observability-{RUN_ID}".lower()
        support_env = Path(os.environ.get("TMPDIR", "/tmp")) / f"platformops-observability-{RUN_ID}" / "runtime.env"
        _require(support_env.is_file(), "observability support runtime configuration is missing")
        component = os.environ.get("PLATFORMOPS_OBSERVABILITY_STOP_CONTAINER", "alloy").strip()
        compose_args = ["docker", "compose", "--project-name", project, "--env-file", str(support_env), "-f", str(ROOT / "ops/compose/docker-compose.observability.yml")]
        down = subprocess.run([*compose_args, "stop", component], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        _evidence().action("observability_component_stop", component=component, returncode=down.returncode, stderr=down.stderr)
        _require(down.returncode == 0, f"failed to stop observability component {component}")
        degraded = _poll_observability_status(marker, available=False, label="degraded")
        _require(degraded["overall_state"] in {"degraded", "unavailable"}, "stopped observability component did not produce degraded state")
        start = subprocess.run([*compose_args, "start", component], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        _require(start.returncode == 0, f"failed to recover observability component {component}")
        _support_readiness(marker)
        recovered = _poll_observability_status(marker, available=True, label="recovered")
        _require(recovered["overall_state"] == "available", "observability did not recover after component restart")


def _delete_and_poll_service() -> None:
    sid = IDENTITY_MANIFEST.get("service_id")
    if not sid:
        return
    response = _force_delete_service(int(sid), f"acceptance cleanup for disposable run {RUN_ID}", "service deletion")
    poll_job(int(response["id"]), max_wait=180, label="service-cleanup")


def _force_delete_service(service_id: int, reason: str, label: str) -> dict[str, Any]:
    """Use the product's maintenance/two-person lifecycle contract for Redis."""
    now = datetime.now(timezone.utc)
    maintenance = require_shape(request("POST", "/api/maintenance", payload={
        "service_id": service_id,
        "title": f"Acceptance disposable cleanup {RUN_ID}",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "ends_at": (now + timedelta(hours=1)).isoformat(),
        "impact": "Disposable acceptance fixture teardown",
    }), ("id", "status"), f"{label} maintenance window")
    approval = require_shape(request("POST", "/api/lifecycle/force-approvals", payload={
        "target_type": "service", "target_id": service_id,
        "reason": reason, "requested_by": "acceptance-requester", "ttl_hours": 1,
    }), ("id", "status"), f"{label} force approval")
    decided = require_shape(request("POST", f"/api/lifecycle/force-approvals/{approval['id']}/decision", payload={
        "approver": "acceptance-approver", "status": "approved", "decision_note": "Disposable acceptance teardown",
    }), ("id", "status"), f"{label} approval decision")
    _require(decided["status"] == "approved", f"{label} force approval was not approved")
    response = require_shape(request("POST", f"/api/services/{service_id}/delete", expected={200, 202}, params={
        "force": "true", "force_reason": reason, "force_approval_id": approval["id"],
    }), ("id", "status"), label)
    _evidence().action("force_service_cleanup", service_id=service_id, maintenance_id=maintenance["id"], approval_id=approval["id"], terminal_job_id=response["id"])
    return response


def _delete_node_services() -> None:
    node_ids = [IDENTITY_MANIFEST.get("node_id"), _evidence().manifest.get("remote_node_id")]
    node_ids = list(dict.fromkeys(int(value) for value in node_ids if value))
    if not node_ids:
        return
    services = request("GET", "/api/services")
    _require(isinstance(services, list), "service cleanup inventory is malformed")
    for service in services:
        if not isinstance(service, dict) or int(service.get("node_id") or 0) not in node_ids or str(service.get("status") or "").lower() == "deleted":
            continue
        sid = int(service["id"])
        response = _force_delete_service(sid, f"acceptance node cleanup for disposable run {RUN_ID}", "node service cleanup")
        poll_job(int(response["id"]), max_wait=180, label="node-service-cleanup")


def run_phase_8_cleanup() -> None:
    with _evidence().phase("phase-8-cleanup"):
        run_manifest = _evidence().manifest
        _support("down")
        _delete_and_poll_service()
        _delete_node_services()
        _require(not _runtime().ping(IDENTITY_MANIFEST["container_name"]), "deleted Redis container still answers PING")
        node_id = IDENTITY_MANIFEST.get("node_id")
        cluster_id = IDENTITY_MANIFEST.get("cluster_id")
        if node_id:
            node_delete = require_shape(request("DELETE", f"/api/nodes/{node_id}"), ("status",), "node cleanup")
            _require(node_delete["status"] == "deleted", "node cleanup did not reach terminal deleted state")
        remote_node_id = _evidence().manifest.get("remote_node_id")
        if remote_node_id:
            remote_node_delete = require_shape(request("DELETE", f"/api/nodes/{int(remote_node_id)}"), ("status",), "remote SSH node cleanup")
            _require(remote_node_delete["status"] == "deleted", "remote SSH node cleanup did not reach terminal deleted state")
            _evidence().manifest.setdefault("remote_ssh", {})["remote_resources_deleted"] = True
        if cluster_id:
            cluster_delete = require_shape(request("DELETE", f"/api/clusters/{cluster_id}"), ("status",), "cluster cleanup")
            _require(cluster_delete["status"] == "deleted", "cluster cleanup did not reach terminal deleted state")
        admin_token = get_auth_token()
        set_auth(admin_token)
        for user_id in (run_manifest.get("operator_user_id"), run_manifest.get("invitee_user_id"), run_manifest.get("resend_user_id"), run_manifest.get("expiry_user_id")):
            if user_id:
                deleted = request("DELETE", f"/api/users/{user_id}", expected={200, 204, 400})
                if isinstance(deleted, dict) and "detail" in deleted:
                    _require("does not exist" in str(deleted["detail"]).lower(), "user cleanup returned an unexpected failure")
        users = request("GET", "/api/users")
        serialized_users = json.dumps(users, default=str)
        _require(not any(value and value in serialized_users for value in (run_manifest.get("operator_email"), run_manifest.get("invite_email"), run_manifest.get("resend_email"), run_manifest.get("expiry_email"))), "run-scoped disposable users remain after cleanup")
        owned = _runtime().owned_names()
        _require(not any(owned.values()), f"owned DinD resources remain after cleanup: {owned}")
        run_events = request("GET", "/api/events", params={"limit": 100, "search": RUN_ID})
        if run_events:
            for event in run_events:
                _validate_retained_audit_event(event)
        else:
            # A focused/early failure may precede the first audited resource
            # mutation (for example a browser image pull).  Do not mask that
            # original defect with an impossible cleanup assertion.
            _require(not any(IDENTITY_MANIFEST.get(field) for field in ("cluster_id", "node_id", "service_id")), "audited resource mutations disappeared without retained events")
        live_clusters = request("GET", "/api/clusters")
        live_nodes = request("GET", "/api/nodes")
        live_services = request("GET", "/api/services")
        live_refs = json.dumps([live_clusters, live_nodes, live_services], default=str)
        _require(not any(str(value) in live_refs for value in (IDENTITY_MANIFEST.get("cluster_id"), IDENTITY_MANIFEST.get("node_id"), IDENTITY_MANIFEST.get("service_id")) if value), "live disposable cluster/node/service reference remains")
        # Mailpit is a fresh run-scoped volume.  Clear only this disposable
        # mailbox after exporting message IDs/evidence, then verify zero.
        message_ids = [str(item.get("ID") or "") for item in mailpit_messages()]
        if message_ids:
            request("DELETE", f"{MAILPIT_URL}/api/v1/messages", expected={200, 204})
        _require(not mailpit_messages(), "run-scoped Mailpit messages remain after cleanup")
        _evidence().action("cleanup_residue", owned=owned, retained_audit_events=len(run_events), audit_redaction_checked=True, live_refs_checked=True, mailpit_ids=message_ids, mailpit_checked=True)


PHASES = {
    "phase-0-preflight": run_phase_0_preflight,
    "phase-1-users": run_phase_1_users,
    "phase-2-cluster-redis": run_phase_2_cluster_node_redis,
    "phase-3-config": run_phase_3_config,
    "phase-4-diagnostics": run_phase_4_diagnostics,
    "phase-5-monitoring": run_phase_5_monitoring,
    "phase-6-performance": run_phase_6_performance,
    "phase-7-observability": run_phase_7_observability,
    "phase-8-cleanup": run_phase_8_cleanup,
}


def main(argv: list[str] | None = None) -> int:
    global EVIDENCE, RUNTIME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["all", *PHASES], default="all", help="run one phase against an existing fixture")
    args = parser.parse_args(argv)
    try:
        EVIDENCE = Evidence()
        RUNTIME = RuntimeEvidence(EVIDENCE)
        if args.phase == "all":
            for phase in PHASES.values():
                phase()
        else:
            PHASES[args.phase]()
        EVIDENCE.save(True)
        print(json.dumps({"run_id": RUN_ID, "status": "passed", "evidence_dir": str(EVIDENCE_DIR)}))
        return 0
    except Exception as exc:
        original_error = str(exc)
        # A failed phase can already have created users, services, jobs, or a
        # support stack. Reconcile those run-scoped resources before handing
        # the failure back; cleanup failures are evidence, not a reason to
        # hide the original criterion.
        if args.phase == "all" and "phase-8-cleanup" not in (_evidence().phase_results if EVIDENCE else {}):
            try:
                run_phase_8_cleanup()
            except Exception as cleanup_error:
                if EVIDENCE is not None:
                    EVIDENCE.action("failure_cleanup", original_error=original_error, cleanup_error=str(cleanup_error))
        if EVIDENCE is not None:
            EVIDENCE.save(False, original_error)
        print(f"ACCEPTANCE FAILED: {original_error}", file=sys.stderr)
        print(json.dumps({"run_id": RUN_ID, "status": "failed", "evidence_dir": str(EVIDENCE_DIR)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
