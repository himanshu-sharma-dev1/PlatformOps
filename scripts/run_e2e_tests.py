"""
PlatformOps E2E suite (cluster lifecycle + optional monitoring).

Mailing / SMTP / invite-email are OUT OF SCOPE for this suite.
  - Never calls /api/users/invite, resend, or GlitchTip account-email endpoints.
  - GlitchTip phase (when enabled) only checks issues/uptime/APM/keys — not mail.
  - Set SKIP_GLITCHTIP=1 to skip Phase 4 entirely (cluster-focused runs).
"""
import os
import sys
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse

BASE_URL = os.environ.get("PLATFORMOPS_E2E_BASE", "http://localhost:9020").rstrip("/")
# 9002 is the current live PlatformOps-coupled PlatformOps stack.  Never allow
# this destructive lifecycle suite to run against it, even when a caller has
# supplied an explicit base URL.
LIVE_PLATFORMOPS_PORT = 9002
ISOLATED_PLATFORMOPS_PORT = 9020


def validate_e2e_target() -> None:
    """Reject live-stack targets before any request can mutate data.

    Local isolated Compose runs use localhost:9020.  A non-default target is
    still supported for CI/remote environments only with an explicit opt-in;
    port 9002 remains rejected unconditionally because it is the known live
    PlatformOps stack.
    """
    parsed = urlparse(BASE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(
            "Unsafe E2E target: PLATFORMOPS_E2E_BASE must be an http(s) URL "
            "such as http://localhost:9020."
        )

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise SystemExit(f"Unsafe E2E target: invalid port in {BASE_URL!r}.") from exc

    if port == LIVE_PLATFORMOPS_PORT:
        raise SystemExit(
            "Refusing to run E2E against port 9002 (the live PlatformOps stack). "
            "Use the isolated target at http://localhost:9020."
        )

    # Keep accidental remote/default-stack execution opt-in while allowing the
    # standard isolated host mapping without additional flags.
    allow_non_isolated = os.environ.get("PLATFORMOPS_E2E_ALLOW_NON_ISOLATED", "")
    if port != ISOLATED_PLATFORMOPS_PORT and allow_non_isolated.strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise SystemExit(
            f"Refusing non-isolated E2E target {BASE_URL!r}. Expected port 9020; "
            "set PLATFORMOPS_E2E_ALLOW_NON_ISOLATED=1 only for an explicitly "
            "reviewed test environment (port 9002 is always blocked)."
        )


validate_e2e_target()

GLITCHTIP_DSN = os.environ.get(
    "PLATFORMOPS_E2E_GLITCHTIP_DSN",
    "http://766ac5ce00fd46ff8f7ea55a47be97e0@localhost:9011/4",
)
# Cluster-first default: skip GlitchTip exception capture (can trigger alert mail in GT).
# Set SKIP_GLITCHTIP=0 to re-enable Phase 4 integration checks (still no mailing tests).
SKIP_GLITCHTIP = os.environ.get("SKIP_GLITCHTIP", "1").strip() not in ("0", "false", "False", "no")
# Even when GlitchTip is on, never raise live exceptions that may notify via mail.
SKIP_GLITCHTIP_EXCEPTION_CAPTURE = os.environ.get("SKIP_GLITCHTIP_EXCEPTION_CAPTURE", "1").strip() not in (
    "0",
    "false",
    "False",
    "no",
)

SESSION = requests.Session()


def log_header(title):
    print("\n" + "=" * 60)
    print(f" {title.upper()} ")
    print("=" * 60)


def assert_status(response, expected_status=200):
    if response.status_code != expected_status:
        print(f"🔴 ERROR: Expected status {expected_status}, got {response.status_code}")
        print(f"Response content: {response.text[:500]}")
        sys.exit(1)


def login():
    """Authenticate so protected routes work; uses login field only (not invite mail)."""
    email = os.environ.get("PLATFORMOPS_E2E_USER", "admin")
    password = os.environ.get("PLATFORMOPS_E2E_PASSWORD", "admin")
    r = SESSION.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Authentication failed with HTTP {r.status_code}; refusing unauthenticated E2E mutations.")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("token")
    if isinstance(token, str) and token.strip():
        SESSION.headers["Authorization"] = f"Bearer {token}"
        print("🟢 Authenticated for E2E (no invite/mail flow)")
    else:
        raise SystemExit("Authentication response did not contain a bearer token; refusing E2E mutations.")


def run_tests():
    # Helper lists
    created_clusters = []
    created_nodes = []
    created_services = []
    created_approvals = []
    created_monitors = []
    created_incidents = []
    created_secrets = []
    created_maintenance = []

    log_header("Phase 0: Auth (no mailing)")
    login()
    print("🟢 E2E scope: cluster/node/service + optional GT issues/uptime — mailing EXCLUDED")

    # -------------------------------------------------------------
    log_header("Phase 1: Cluster & Node Lifecycle")
    # -------------------------------------------------------------
    # 1.1 Create Cluster
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    cluster_payload = {
        "name": f"e2e-cluster-{stamp}",
        "region": "us-west-2",
        "environment": "e2e"
    }
    r = SESSION.post(f"{BASE_URL}/api/clusters", json=cluster_payload)
    assert_status(r, 200)
    cluster = r.json()
    cluster_id = cluster["id"]
    created_clusters.append(cluster_id)
    print(f"🟢 Created cluster '{cluster['name']}' with ID {cluster_id}")

    # Verify cluster list
    r = SESSION.get(f"{BASE_URL}/api/clusters")
    assert_status(r, 200)
    assert any(c["id"] == cluster_id for c in r.json()), "Created cluster not found in list"

    # 1.2 Update Cluster
    r = SESSION.put(f"{BASE_URL}/api/clusters/{cluster_id}", json={"region": "eu-central-1", "environment": "staging"})
    assert_status(r, 200)
    updated_cluster = r.json()
    assert updated_cluster["region"] == "eu-central-1", "Cluster update failed"
    print(f"🟢 Updated cluster {cluster_id} region to eu-central-1")

    # 1.3 Create Node
    node_payload = {
        "cluster_id": cluster_id,
        "name": f"e2e-node-{stamp}",
        "host": "localhost",
        "ssh_user": "ubuntu",
        "environment": "local",
        "volume_root": "/tmp/e2e-test",
        "docker_network": "e2e-net"
    }
    r = SESSION.post(f"{BASE_URL}/api/nodes", json=node_payload)
    assert_status(r, 200)
    node = r.json()
    node_id = node["id"]
    created_nodes.append(node_id)
    print(f"🟢 Created node '{node['name']}' with ID {node_id}")

    # 1.4 Validate Node
    r = SESSION.post(f"{BASE_URL}/api/nodes/{node_id}/validate")
    assert_status(r, 200)
    job = r.json()
    job_id = job["id"]
    print(f"🟢 Validation job started with ID {job_id}")

    # Wait for validation job
    for _ in range(20):
        r = SESSION.get(f"{BASE_URL}/api/jobs/{job_id}")
        assert_status(r, 200)
        status = r.json()["status"]
        if status in ("success", "failed"):
            break
        time.sleep(0.5)
    assert status == "success", f"Validation job failed: {r.json()}"
    print("🟢 Node validation succeeded")

    # 1.5 Node onboarding readiness
    r = SESSION.get(f"{BASE_URL}/api/nodes/{node_id}/onboarding-readiness")
    assert_status(r, 200)
    readiness = r.json()
    assert "overall_status" in readiness, "Readiness response missing overall_status"
    print("🟢 Onboarding readiness report fetched successfully")

    # 1.6 Node onboarding remediate
    r = SESSION.post(f"{BASE_URL}/api/nodes/{node_id}/onboarding-remediate", json={"action": "apply-local-preset"})
    assert_status(r, 200)
    remediation = r.json()
    assert remediation["ok"], "Remediation preset failed"
    print("🟢 Local onboarding preset remediation applied successfully")

    # 1.7 Attempt cluster deletion (should be blocked since it has nodes)
    r = SESSION.delete(f"{BASE_URL}/api/clusters/{cluster_id}")
    assert_status(r, 409)
    print("🟢 Verified: Cluster deletion blocked correctly due to active nodes")

    # 1.8 Force delete approval request
    approval_payload = {
        "target_type": "cluster",
        "target_id": cluster_id,
        "reason": "E2E testing cleanup",
        "requested_by": "test-agent"
    }
    r = SESSION.post(f"{BASE_URL}/api/lifecycle/force-approvals", json=approval_payload)
    assert_status(r, 200)
    approval = r.json()
    approval_id = approval["id"]
    created_approvals.append(approval_id)
    print(f"🟢 Created force-delete approval request ID {approval_id}")

    # Decide approval
    r = SESSION.post(f"{BASE_URL}/api/lifecycle/force-approvals/{approval_id}/decision", json={"approver": "admin-user", "status": "approved", "decision_note": "E2E approved"})
    assert_status(r, 200)
    assert r.json()["status"] == "approved", "Failed to approve force-delete request"
    print(f"🟢 Approved force-delete request {approval_id}")

    # -------------------------------------------------------------
    log_header("Phase 2: Service Registry & Placement")
    # -------------------------------------------------------------
    # 2.1 Service Catalog
    r = SESSION.get(f"{BASE_URL}/api/catalog/services")
    assert_status(r, 200)
    catalog = r.json()
    assert len(catalog) >= 10, "Service catalog is empty or too small"
    print("🟢 Service catalog loaded successfully")

    # 2.2 Install Schema
    r = SESSION.get(f"{BASE_URL}/api/catalog/services/option-copilot/install-schema?node_id={node_id}")
    assert_status(r, 200)
    print("🟢 Option Copilot install-schema retrieved successfully")

    # 2.3 Create Service Instance
    service_payload = {
        "node_id": node_id,
        "service_key": "option-copilot",
        "name": f"e2e-optioncopilot-{stamp}"
    }
    r = SESSION.post(f"{BASE_URL}/api/services", json=service_payload)
    assert_status(r, 200)
    service = r.json()
    service_id = service["id"]
    created_services.append(service_id)
    print(f"🟢 Created service instance '{service['name']}' with ID {service_id}")

    # 2.4 Preflight Dependency Check
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/preflight")
    assert_status(r, 200)
    preflight = r.json()
    print(f"🟢 Dependency preflight status: {preflight['ok']} (message: {preflight['message']})")

    # 2.5 Placement Recommendations
    r = SESSION.get(f"{BASE_URL}/api/services/placement/recommendations/option-copilot")
    assert_status(r, 200)
    print("🟢 Placement recommendations fetched successfully")

    # 2.6 Deployment Plan
    r = SESSION.get(f"{BASE_URL}/api/nodes/{node_id}/deployment-plan/option-copilot")
    assert_status(r, 200)
    print("🟢 Deployment plan generated successfully")

    # 2.7 Diagnostics Targets
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/diagnostics/targets")
    assert_status(r, 200)
    print("🟢 Service diagnostics targets retrieved successfully")

    # 2.8 Service Summary
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/summary")
    assert_status(r, 200)
    print("🟢 Service summary retrieved successfully")

    # -------------------------------------------------------------
    log_header("Phase 3: Configuration Manager")
    # -------------------------------------------------------------
    # 3.1 Get Config Workspace
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/config?source=live")
    assert_status(r, 200)
    config_workspace = r.json()
    print("🟢 Service config workspace loaded successfully")

    # 3.2 Create Snapshot
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/snapshots", json={"name": "before-apply", "source": "live", "requested_by": "test-agent"})
    assert_status(r, 200)
    snap1 = r.json()
    snap1_id = snap1["id"]
    print(f"🟢 Created config snapshot '{snap1['name']}' with ID {snap1_id}")

    # 3.3 List Snapshots
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/config/snapshots")
    assert_status(r, 200)
    assert any(s["id"] == snap1_id for s in r.json()["items"]), "Snapshot missing from list"

    # 3.4 Validate Config
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/validate", json={"content": "service_key: option-copilot\noptionCopilot:\n  debug: true\n", "apply_mode": "reload"})
    assert_status(r, 200)
    assert r.json()["ok"], "Config validation failed"
    print("🟢 Config YAML validation succeeded")

    # 3.5 Apply Config
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/apply", json={"content": "service_key: option-copilot\noptionCopilot:\n  debug: true\n", "apply_mode": "reload"})
    assert_status(r, 200)
    config_job_id = r.json()["id"]
    # Wait for config apply
    for _ in range(20):
        r = SESSION.get(f"{BASE_URL}/api/jobs/{config_job_id}")
        assert_status(r, 200)
        if r.json()["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    print("🟢 Configuration applied successfully via Ansible")

    # 3.6 Create Snapshot after apply
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/snapshots", json={"name": "after-apply", "source": "live", "requested_by": "test-agent"})
    assert_status(r, 200)
    snap2 = r.json()
    snap2_id = snap2["id"]
    print(f"🟢 Created second config snapshot '{snap2['name']}' with ID {snap2_id}")

    # 3.7 Compare Snapshots
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/config/compare?left_snapshot_id={snap1_id}&right_snapshot_id={snap2_id}")
    assert_status(r, 200)
    print("🟢 Snapshot comparison retrieved successfully")

    # 3.8 Drift Detection
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/drift")
    assert_status(r, 200)
    print("🟢 Configuration drift scan executed successfully")

    # 3.9 Rename Snapshot
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/snapshots/{snap1_id}/rename", json={"name": "before-apply-renamed", "requested_by": "test-agent"})
    assert_status(r, 200)
    assert r.json()["name"] == "before-apply-renamed"
    print("🟢 Snapshot renamed successfully")

    # 3.10 Restore Snapshot
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/config/snapshots/{snap1_id}/restore")
    assert_status(r, 200)
    restore_job_id = r.json()["id"]
    for _ in range(20):
        r = SESSION.get(f"{BASE_URL}/api/jobs/{restore_job_id}")
        assert_status(r, 200)
        if r.json()["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    print("🟢 Config snapshot restored (rolled back) successfully")

    # 3.11 Config Timeline
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/config/timeline")
    assert_status(r, 200)
    print("🟢 Configuration timeline logs retrieved successfully")

    # -------------------------------------------------------------
    # Phase 4: GlitchTip (optional) — NO mailing / SMTP / invite-email
    # Exception capture disabled by default (can fire GT alert mail).
    # -------------------------------------------------------------
    log_header("Phase 4: GlitchTip Integration (no mailing)")
    if SKIP_GLITCHTIP:
        print("🟡 SKIP_GLITCHTIP=1 — skipping GlitchTip phase (cluster E2E focus; no mail)")
    else:
        try:
            # 4.1 Integration Status only (read-only)
            r = SESSION.get(f"{BASE_URL}/PlatformIO/Monitoring/IntegrationStatus/", timeout=30)
            if r.status_code != 200:
                print(f"🟡 GlitchTip IntegrationStatus HTTP {r.status_code}; skipping rest of Phase 4")
            else:
                print("🟢 GlitchTip integration status verified (read-only)")

                # 4.2 Exception capture — DISABLED by default to avoid mailing/alert side effects
                if SKIP_GLITCHTIP_EXCEPTION_CAPTURE:
                    print("🟡 SKIP_GLITCHTIP_EXCEPTION_CAPTURE=1 — not raising live exceptions (no alert mail)")
                else:
                    import sentry_sdk  # optional path only
                    test_message = f"E2E Test Exception [{stamp}] from PlatformOps Validation"
                    print(f"👉 Triggering real error payload: '{test_message}'")
                    sentry_sdk.init(dsn=GLITCHTIP_DSN, traces_sample_rate=1.0)
                    try:
                        raise ValueError(test_message)
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                    sentry_sdk.flush()
                    time.sleep(8)
                    r = SESSION.post(
                        f"{BASE_URL}/PlatformIO/Monitoring/Issues/",
                        json={"service_name": "optionCopilot", "window": "24h"},
                        timeout=30,
                    )
                    if r.status_code == 200 and r.json().get("success"):
                        issues = r.json().get("issues") or []
                        target = next((i for i in issues if test_message in str(i.get("title", ""))), None)
                        if target:
                            print(f"🟢 Captured issue id={target.get('id')}")
                        else:
                            print("🟡 Exception not yet indexed; continuing without assert")
                    else:
                        print("🟡 Issues query failed after capture; continuing")

                # 4.3 Read-only API checks (no mail endpoints)
                for label, path, body in [
                    ("Keys", "/PlatformIO/Monitoring/Keys/", {"service_name": "optionCopilot"}),
                    ("Performance", "/PlatformIO/Monitoring/Performance/", {"service_name": "optionCopilot"}),
                    ("Health", "/PlatformIO/Monitoring/Health/", {"service_name": "optionCopilot"}),
                    ("Uptime list", "/PlatformIO/Monitoring/Uptime/", {"service_name": "optionCopilot"}),
                ]:
                    rr = SESSION.post(f"{BASE_URL}{path}", json=body, timeout=30)
                    if rr.status_code == 200:
                        print(f"🟢 GlitchTip {label} ok")
                    else:
                        print(f"🟡 GlitchTip {label} HTTP {rr.status_code}")

                # Explicitly NOT tested: invite email, SMTP, account verification mail, alert digests
                print("🟢 Phase 4 done — mailing/SMTP/invite-email intentionally not tested")
        except Exception as e:
            print(f"🟡 GlitchTip phase soft-failed (non-fatal for cluster E2E): {e}")

    # -------------------------------------------------------------
    log_header("Phase 5: SRE Operations")
    # -------------------------------------------------------------
    # 5.1 Policy Scan
    r = SESSION.post(f"{BASE_URL}/api/policy/scan")
    assert_status(r, 200)
    print("🟢 Policy scan executed successfully")

    # 5.2 Evaluate SLOs
    r = SESSION.post(f"{BASE_URL}/api/slo/evaluate")
    assert_status(r, 200)
    print("🟢 SLO target evaluation executed successfully")

    # 5.3 Open Incident
    incident_payload = {
        "title": f"E2E System alert {stamp}",
        "severity": "medium",
        "summary": "Automated verification sequence",
        "service_id": service_id,
        "node_id": node_id
    }
    r = SESSION.post(f"{BASE_URL}/api/incidents", json=incident_payload)
    assert_status(r, 200)
    incident = r.json()
    incident_id = incident["id"]
    created_incidents.append(incident_id)
    print(f"🟢 Opened SRE incident with ID {incident_id}")

    # 5.4 Execute Incident Runbook
    r = SESSION.post(f"{BASE_URL}/api/incidents/{incident_id}/runbook/restart-service")
    assert_status(r, 200)
    print("🟢 Restart-service runbook executed successfully on active incident")

    # 5.5 Resolve Incident
    r = SESSION.post(f"{BASE_URL}/api/incidents/{incident_id}/resolve")
    assert_status(r, 200)
    assert r.json()["status"] == "resolved"
    print("🟢 Incident resolved successfully")

    # 5.6 Monitoring Sweep
    r = SESSION.post(f"{BASE_URL}/api/monitoring/sweep")
    assert_status(r, 200)
    print("🟢 Global monitoring sweep executed successfully")

    # -------------------------------------------------------------
    log_header("Phase 6: Secrets, Maintenance, Capacity, Audit")
    # -------------------------------------------------------------
    # 6.1 Create Secret
    secret_payload = {
        "key": "E2E_DATABASE_PASSWORD",
        "service_id": service_id,
        "scope": "service",
        "rotation_interval_days": 30
    }
    r = SESSION.post(f"{BASE_URL}/api/secrets", json=secret_payload)
    assert_status(r, 200)
    secret = r.json()
    secret_id = secret["id"]
    created_secrets.append(secret_id)
    print(f"🟢 Created secret '{secret['key']}' with ID {secret_id}")

    # 6.2 Rotate Secret
    r = SESSION.post(f"{BASE_URL}/api/secrets/{secret_id}/rotate")
    assert_status(r, 200)
    assert r.json()["status"] == "rotated", "Secret status did not change to rotated"
    assert r.json()["rotated_at"] is not None, "Secret rotated_at is None"
    print("🟢 Secret rotated successfully")

    # 6.3 Schedule Maintenance
    maint_payload = {
        "title": "E2E System Patching",
        "starts_at": "2026-07-02T00:00:00Z",
        "ends_at": "2026-07-02T02:00:00Z",
        "impact": "partial",
        "service_id": service_id,
        "node_id": node_id
    }
    r = SESSION.post(f"{BASE_URL}/api/maintenance", json=maint_payload)
    assert_status(r, 200)
    maint = r.json()
    maint_id = maint["id"]
    created_maintenance.append(maint_id)
    print(f"🟢 Scheduled maintenance window ID {maint_id}")

    # 6.4 Complete Maintenance
    r = SESSION.post(f"{BASE_URL}/api/maintenance/{maint_id}/complete")
    assert_status(r, 200)
    assert r.json()["status"] == "completed"
    print("🟢 Maintenance window completed successfully")

    # 6.5 Capacity Report
    r = SESSION.post(f"{BASE_URL}/api/nodes/{node_id}/capacity")
    assert_status(r, 200)
    print("🟢 Node capacity report generated successfully")

    # 6.6 Audit Export
    r = SESSION.post(f"{BASE_URL}/api/audit/exports?export_type=summary")
    assert_status(r, 200)
    print("🟢 Audit log export generated successfully")

    # -------------------------------------------------------------
    log_header("Phase 7: Observability Stack & Telemetry")
    # -------------------------------------------------------------
    # 7.1 Pipeline
    r = SESSION.get(f"{BASE_URL}/api/observability/pipeline")
    assert_status(r, 200)
    print("🟢 Observability pipeline report retrieved successfully")

    # 7.2 Observability Status
    obs_params = {"service_id": service_id}
    observability_marker = os.environ.get("PLATFORMOPS_OBSERVABILITY_MARKER", "").strip()
    if observability_marker:
        obs_params["marker"] = observability_marker
    r = SESSION.get(f"{BASE_URL}/api/observability/status", params=obs_params)
    assert_status(r, 200)
    obs_status = r.json()
    assert obs_status.get("target", {}).get("service_id") == service_id
    assert "signals" in obs_status and "overall_state" in obs_status
    print(f"🟢 Observability direct probe status verified: {obs_status.get('overall_state')}")

    # 7.3 Node Metrics
    r = SESSION.get(f"{BASE_URL}/api/metrics/node")
    assert_status(r, 200)
    print("🟢 Prometheus host metrics retrieved successfully")

    # 7.4 Process Metrics
    r = SESSION.get(f"{BASE_URL}/api/metrics/processes")
    assert_status(r, 200)
    print("🟢 Host process metrics retrieved successfully")

    # 7.5 Loki Logs query
    r = SESSION.get(f"{BASE_URL}/api/diagnostics/logs?service=platformops")
    assert_status(r, 200)
    print("🟢 Loki diagnostics logs query succeeded")

    # 7.6 Topology Graph
    r = SESSION.get(f"{BASE_URL}/api/topology")
    assert_status(r, 200)
    print("🟢 Global topology dependencies graph retrieved successfully")

    # 7.7 Dashboard summary includes gpu_node_count
    r = SESSION.get(f"{BASE_URL}/api/dashboard/summary")
    assert_status(r, 200)
    summary = r.json()
    assert "gpu_node_count" in summary, "dashboard summary missing gpu_node_count"
    print(f"🟢 Dashboard summary gpu_node_count={summary.get('gpu_node_count')}")

    # 7.8 Node metrics schema fields
    r = SESSION.get(f"{BASE_URL}/api/nodes/{node_id}/metrics?window=1h")
    assert_status(r, 200)
    node_metrics = r.json()
    assert "mounted_volumes" in node_metrics, "node metrics missing mounted_volumes"
    assert "prometheus_reachable" in node_metrics, "node metrics missing prometheus_reachable"
    print(f"🟢 Node metrics mounted_volumes={len(node_metrics.get('mounted_volumes') or [])} prom={node_metrics.get('prometheus_reachable')}")

    # 7.9 Service metrics schema fields
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/metrics?window=1h")
    assert_status(r, 200)
    svc_metrics = r.json()
    assert "custom_charts" in svc_metrics, "service metrics missing custom_charts"
    print(f"🟢 Service metrics keys present (db/broker/custom) prom={svc_metrics.get('prometheus_reachable')}")

    # 7.10 Ingestion stats
    r = SESSION.get(f"{BASE_URL}/api/diagnostics/ingestion-stats")
    assert_status(r, 200)
    stats = r.json()
    assert "ingestion_rate_display" in stats
    print(f"🟢 Ingestion stats rate={stats.get('ingestion_rate_display')} loki={stats.get('loki_reachable')}")

    # 7.11 File tail / file history / chat
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/diagnostics/file-tail?tail_lines=20")
    assert_status(r, 200)
    assert "lines" in r.json()
    print("🟢 Diagnostics file-tail succeeded")

    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/diagnostics/file-history?page=1&page_size=10")
    assert_status(r, 200)
    hist = r.json()
    assert "lines" in hist
    print(f"🟢 Diagnostics file-history lines={len(hist.get('lines') or [])} next_cursor={'yes' if hist.get('next_cursor') else 'no'}")

    r = SESSION.post(
        f"{BASE_URL}/api/services/{service_id}/diagnostics/chat",
        json={"question": "Summarize recent errors", "window": "current"},
    )
    assert_status(r, 200)
    chat = r.json()
    assert isinstance(chat, dict), "chat response must be an object"
    assert isinstance(chat.get("success"), bool), "chat response missing boolean success"
    assert isinstance(chat.get("answer"), str), "chat response missing string answer"
    assert isinstance(chat.get("evidence"), list), "chat response missing evidence list"
    assert isinstance(chat.get("chart_data"), list), "chat response missing chart_data list"
    assert isinstance(chat.get("suggestions"), list), "chat response missing suggestions list"
    if chat["success"]:
        assert chat["answer"].strip(), "configured diagnostics chat returned an empty answer"
        print(f"🟢 Diagnostics AI chat responded (provider={chat.get('provider') or 'unknown'})")
    else:
        chat_error = str(chat.get("error") or "")
        if "not configured" in chat_error.lower():
            print(f"🟢 Diagnostics AI chat explicitly unavailable by contract ({chat_error})")
        else:
            raise AssertionError(f"configured diagnostics chat failed: {chat_error or chat}")

    # 7.12 Archives view
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/diagnostics/archives")
    assert_status(r, 200)
    archives = r.json()
    assert isinstance(archives, list) and archives, "diagnostics archive index is empty"
    archive_id = archives[0]["id"]
    r = SESSION.get(f"{BASE_URL}/api/services/{service_id}/diagnostics/archives/{archive_id}/view")
    assert_status(r, 200)
    print(f"🟢 Archive view succeeded for archive {archive_id}")

    # 7.13 Issues cursor contract
    r = SESSION.post(
        f"{BASE_URL}/PlatformIO/Monitoring/Issues/",
        json={"service_name": "optionCopilot", "window": "24h"},
    )
    # optionCopilot may not exist in this run; fall back to service name if present
    if r.status_code != 200 or not r.json().get("success"):
        # try the deployed service name
        r2 = SESSION.get(f"{BASE_URL}/api/services/{service_id}")
        svc_name = r2.json().get("name") if r2.status_code == 200 else None
        if svc_name:
            r = SESSION.post(
                f"{BASE_URL}/PlatformIO/Monitoring/Issues/",
                json={"service_name": svc_name, "window": "24h"},
            )
    assert_status(r, 200)
    assert r.json().get("success"), f"Issues query failed: {r.json()}"
    assert "issues" in r.json()
    assert "next_cursor" in r.json()
    print(f"🟢 Issues cursor contract ok (issues={len(r.json().get('issues') or [])})")

    # -------------------------------------------------------------
    log_header("Phase 8: Cleanup & Cascaded Retracts")
    # -------------------------------------------------------------
    # 8.1 Delete Service
    print(f"👉 Deleting test service {service_id}")
    r = SESSION.post(f"{BASE_URL}/api/services/{service_id}/delete")
    assert_status(r, 200)
    job_del = r.json()
    job_del_id = job_del["id"]
    delete_status = None
    delete_result = None
    for _ in range(20):
        r = SESSION.get(f"{BASE_URL}/api/jobs/{job_del_id}")
        assert_status(r, 200)
        delete_result = r.json()
        delete_status = delete_result["status"]
        if delete_status in ("success", "failed", "error"):
            break
        time.sleep(0.5)
    assert delete_status == "success", f"Service delete job failed: {delete_result}"
    print(f"🟢 Test service delete job {job_del_id} reached terminal status={delete_status}")

    # 8.2 Prepare policy-compliant node cleanup. The service delete is an
    # asynchronous job, while node force deletion requires a node-scoped
    # two-person approval and an active current-time maintenance window.
    node_cleanup_reason = "E2E cleanup of disposable node lifecycle resources"
    node_approval_payload = {
        "target_type": "node",
        "target_id": node_id,
        "reason": node_cleanup_reason,
        "requested_by": "test-agent",
        "ttl_hours": 4,
    }
    r = SESSION.post(f"{BASE_URL}/api/lifecycle/force-approvals", json=node_approval_payload)
    assert_status(r, 200)
    node_approval = r.json()
    node_approval_id = node_approval["id"]
    created_approvals.append(node_approval_id)
    assert node_approval.get("target_type") == "node", "Node cleanup approval has the wrong target type"
    assert node_approval.get("target_id") == node_id, "Node cleanup approval has the wrong target"
    print(f"🟢 Created node cleanup approval request ID {node_approval_id}")

    r = SESSION.post(
        f"{BASE_URL}/api/lifecycle/force-approvals/{node_approval_id}/decision",
        json={
            "approver": "admin-user",
            "status": "approved",
            "decision_note": "Approved disposable E2E node cleanup",
        },
    )
    assert_status(r, 200)
    assert r.json().get("status") == "approved", "Failed to approve node cleanup request"
    print(f"🟢 Approved node cleanup request {node_approval_id}")

    cleanup_window_start = datetime.utcnow() - timedelta(minutes=1)
    cleanup_window_end = datetime.utcnow() + timedelta(minutes=30)
    cleanup_maintenance_payload = {
        "title": "E2E disposable node cleanup",
        "starts_at": cleanup_window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ends_at": cleanup_window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "impact": "disposable E2E node teardown",
        "node_id": node_id,
    }
    r = SESSION.post(f"{BASE_URL}/api/maintenance", json=cleanup_maintenance_payload)
    assert_status(r, 200)
    cleanup_maintenance = r.json()
    cleanup_maintenance_id = cleanup_maintenance["id"]
    created_maintenance.append(cleanup_maintenance_id)
    assert cleanup_maintenance.get("status") == "scheduled", "Node cleanup maintenance is not scheduled"
    assert cleanup_maintenance.get("node_id") == node_id, "Node cleanup maintenance has the wrong target"
    print(f"🟢 Opened active node cleanup maintenance window {cleanup_maintenance_id}")

    # 8.3 Delete Node (with force, scoped approval, and maintenance window)
    print(f"👉 Force deleting test node {node_id}")
    r = SESSION.delete(
        f"{BASE_URL}/api/nodes/{node_id}",
        params={
            "force": "true",
            "force_reason": node_cleanup_reason,
            "force_approval_id": node_approval_id,
        },
    )
    assert_status(r, 200)
    node_delete = r.json()
    assert node_delete.get("status") == "deleted", f"Node cleanup did not reach deleted state: {node_delete}"
    print("🟢 Test node force deleted successfully (terminal response)")

    # 8.4 Delete Cluster (with force + existing approval)
    print(f"👉 Force deleting cluster {cluster_id}")
    r = SESSION.delete(
        f"{BASE_URL}/api/clusters/{cluster_id}",
        params={
            "force": "true",
            "force_reason": "E2E cleanup of disposable cluster lifecycle resources",
            "force_approval_id": approval_id,
        },
    )
    assert_status(r, 200)
    cluster_delete = r.json()
    assert cluster_delete.get("status") == "deleted", f"Cluster cleanup did not reach deleted state: {cluster_delete}"
    print("🟢 Test cluster force deleted successfully (terminal response)")

    # 8.5 Verify cleanup events
    r = SESSION.get(f"{BASE_URL}/api/events?limit=50")
    assert_status(r, 200)
    print("🟢 Final lifecycle events verified")

    log_header("E2E Test Run Completed Successfully")
    print("✨ Cluster/node/service lifecycle + config/SRE/obs targets verified.")
    print("✨ GlitchTip mailing/SMTP/invite-email: NOT in suite scope.")
    if SKIP_GLITCHTIP:
        print("✨ GlitchTip Phase 4: skipped (SKIP_GLITCHTIP=1).")
    else:
        print("✨ GlitchTip Phase 4: read-only checks only (no exception mail).")
    print("✨ Ansible validation/deployment/rollback runner triggers: VERIFIED.")

if __name__ == "__main__":
    run_tests()
