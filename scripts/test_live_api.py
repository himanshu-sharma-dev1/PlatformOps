import requests
import json
import sys

BASE_URL = "http://localhost:9002"

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

print("=" * 60)
print("STARTING PLATFORMOPS LIVE API VERIFICATION")
print("=" * 60)

failed = 0
passed = 0

for method, path, payload in endpoints:
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json=payload, timeout=10)
        
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
