import os
import requests
import json
import sys
from urllib.parse import urlparse

BASE_URL = os.environ.get("PLATFORMOPS_BASE", "http://localhost:9020").rstrip("/")
LIVE_PLATFORMOPS_PORT = 9002
ISOLATED_PLATFORMOPS_PORT = 9020
ALLOW_NON_ISOLATED = "PLATFORMOPS_LIVE_API_ALLOW_NON_ISOLATED"

endpoints = [
    ("GET", "/api/health", None),
    ("GET", "/api/catalog/services", None),
    ("GET", "/api/catalog/services/option-copilot/install-schema?node_id=1", None),
    ("GET", "/api/topology", None),
    ("GET", "/api/observability/pipeline", None),
    ("GET", "/api/observability/status", None),
    ("GET", "/api/dashboard/summary", None),
    ("GET", "/api/events", None),
    ("GET", "/api/capabilities/coverage", None),
    ("GET", "/api/lifecycle/audit", None),
    ("GET", "/api/policy/findings", None),
    ("GET", "/api/slo/reports", None),
    ("GET", "/api/incidents", None),
    ("GET", "/api/runbooks/executions", None),
    ("GET", "/api/capacity/reports", None),
    ("GET", "/api/secrets", None),
    ("GET", "/api/maintenance", None),
    ("GET", "/api/audit/exports", None),
    ("GET", "/api/clusters", None),
    ("GET", "/api/nodes", None),
    ("GET", "/api/services", None),
    ("POST", "/PlatformIO/Monitoring/IntegrationStatus/", {}),
    ("POST", "/PlatformIO/Monitoring/Issues/", {"service_name": "optionCopilot"}),
    ("POST", "/PlatformIO/Monitoring/Uptime/", {"service_name": "optionCopilot"}),
]

def validate_target() -> None:
    """Reject the live cPlatform-coupled endpoint before any HTTP request."""

    parsed = urlparse(BASE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(
            "Unsafe live API target: PLATFORMOPS_BASE must be an http(s) URL "
            "such as http://localhost:9020."
        )
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise SystemExit(f"Unsafe live API target: invalid port in {BASE_URL!r}.") from exc
    if port == LIVE_PLATFORMOPS_PORT:
        raise SystemExit(
            "Refusing live API verification against port 9002 (the live cPlatform stack). "
            "Use the isolated target at http://localhost:9020."
        )
    if port != ISOLATED_PLATFORMOPS_PORT and os.environ.get(ALLOW_NON_ISOLATED, "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise SystemExit(
            f"Refusing non-isolated API target {BASE_URL!r}. Expected port 9020; "
            f"set {ALLOW_NON_ISOLATED}=1 only for an explicitly reviewed environment."
        )


def login(session: requests.Session) -> None:
    """Authenticate before any protected endpoint is requested."""

    email = os.environ.get("PLATFORMOPS_USER", "admin")
    password = os.environ.get("PLATFORMOPS_PASSWORD", "admin")
    try:
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"Authentication request failed; refusing API checks: {exc}") from exc
    if response.status_code != 200:
        raise SystemExit(
            f"Authentication failed with HTTP {response.status_code}; refusing unauthenticated API checks."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SystemExit("Authentication returned non-JSON data; refusing API checks.") from exc
    token = payload.get("token") or payload.get("access_token") or payload.get("session_token")
    if not isinstance(token, str) or not token.strip():
        raise SystemExit("Authentication returned no bearer token; refusing API checks.")
    session.headers.update({"Authorization": f"Bearer {token}"})


validate_target()
session = requests.Session()
login(session)

print("=" * 60)
print("STARTING PLATFORMOPS ISOLATED API VERIFICATION")
print("=" * 60)
print(f"BASE={BASE_URL}")

failed = 0
passed = 0

for method, path, payload in endpoints:
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            r = session.get(url, timeout=10)
        else:
            r = session.post(url, json=payload, timeout=10)
        
        status = r.status_code
        is_json = False
        try:
            r.json()
            is_json = True
        except ValueError:
            pass
            
        if status == 200:
            print(f"🟢 PASSED: {method} {path} -> Status {status} (JSON: {is_json})")
            passed += 1
        else:
            print(f"🔴 FAILED: {method} {path} -> Status {status} (JSON: {is_json})")
            print(f"   Response: {r.text[:200]}")
            failed += 1
    except Exception as e:
        print(f"🔴 ERROR: {method} {path} -> Exception: {e}")
        failed += 1

print("=" * 60)
print(f"TEST SUMMARY: {passed} PASSED, {failed} FAILED")
print("=" * 60)

if failed > 0:
    sys.exit(1)
sys.exit(0)
