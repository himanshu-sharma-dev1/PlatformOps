#!/usr/bin/env python3
"""Fast, side-effect-free checks for strict Redis fixture invariants."""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_redis_acceptance_test as harness  # noqa: E402


def main() -> int:
    phase = inspect.getsource(harness.run_phase_2_cluster_node_redis)
    canonical = phase.index('"service_key": "redis-core"')
    invalid = phase.index('"service_key": "node-exporter"')
    assert canonical < invalid, "canonical redis-core must precede invalid fixture"
    assert '"service_key": "redis-core-invalid"' not in phase, "invalid fixture must use a catalog key"
    assert '"service_key": "node-exporter"' in phase, "invalid fixture must use the config-free catalog key"
    support = (ROOT / "scripts/observability_support_stack.sh").read_text()
    up_start = support.index('  up)')
    assert support.index('start_marker\n    compose up -d --wait --force-recreate', up_start) < support.index('    provision_glitchtip', up_start), "marker source must exist before Alloy/Loki startup"
    assert 'running=$(isolated_exec docker inspect --format' in support, "marker restart must be idempotent for a running container"
    assert 'sed -n \'s/^PLATFORMOPS_OBS_ADMIN_EMAIL=//p\' "$ENV_FILE"' in support, "GlitchTip provisioning must reload the run-scoped admin email"
    assert "wait_alloy_and_loki()" in support, "support stack must expose bounded Alloy/Loki readiness"
    assert "http://127.0.0.1:12345/-/ready" in support, "readiness must use Alloy's direct endpoint"
    assert 'docker run --rm --network "container:$alloy_container" redis:7-alpine' in support, "Alloy probe must use a disposable direct HTTP helper"
    assert "wait_loki_marker" in support, "readiness must prove exact Loki marker ingestion"
    acceptance_compose = (ROOT / "ops/compose/docker-compose.acceptance.yml").read_text()
    ssh_entrypoint = (ROOT / "scripts/fixtures/ssh-target/entrypoint.sh").read_text()
    ssh_dockerfile = (ROOT / "scripts/fixtures/ssh-target/Dockerfile").read_text()
    ssh_wrapper = (ROOT / "scripts/fixtures/ssh-target/docker-wrapper.sh").read_text()
    assert "ssh-target:" in acceptance_compose and "DOCKER_HOST: tcp://docker-engine:2375" in acceptance_compose, "remote fixture must target only private DinD TCP"
    assert "acceptance_remote_target_root:/tmp/platformops" in acceptance_compose and "PLATFORMOPS_ACCEPTANCE_REMOTE_VOLUME" in acceptance_compose, "remote fixture must share only the run-scoped bind root with private DinD"
    assert "/var/run/docker.sock" not in acceptance_compose and "docker.sock:" not in ssh_entrypoint, "remote fixture must not mount the host Docker socket"
    assert "PermitRootLogin prohibit-password" in ssh_entrypoint and "authorized_keys" in ssh_entrypoint, "remote fixture must require ephemeral-key SSH"
    assert "SetEnv DOCKER_HOST=tcp://docker-engine:2375" in ssh_entrypoint, "remote Python SDK must receive only the private DinD endpoint"
    assert "docker.real" in ssh_dockerfile and "COPY scripts/fixtures/ssh-target/docker-wrapper.sh" in ssh_dockerfile, "remote fixture must install the target-bound Docker wrapper"
    assert 'export DOCKER_HOST="${DOCKER_HOST:-tcp://docker-engine:2375}"' in ssh_wrapper and "docker.real" in ssh_wrapper, "remote Docker wrapper must force private DinD TCP"
    assert "PLATFORMOPS_SSH_PUBLIC_KEY_PATH" in (ROOT / "scripts/acceptance_stack.sh").read_text(), "acceptance stack must generate a run-scoped SSH key"

    # Evidence is untrusted input: invite links and credentials can be nested
    # in API payloads, metadata JSON, or arbitrary text fields.  The sanitizer
    # must retain correlation material without persisting a usable secret.
    raw_token = "InviteToken-abc123456789"
    synthetic = {
        "response": {
            "url": f"http://localhost:9020/#/invite/{raw_token}",
            "nested": {
                "Authorization": f"Bearer {raw_token}",
                "dsn": "postgresql://acceptance:plain-db-password@db.example.invalid/platformops",
                "metadata_json": json.dumps({"token": raw_token}),
            },
            "items": [{"invite_url": f"/api/auth/invite/{raw_token}?token={raw_token}"}],
        }
    }
    sanitized = harness._redact(synthetic)
    encoded = json.dumps(sanitized, sort_keys=True)
    assert raw_token not in encoded, "raw invite token survived recursive evidence sanitization"
    assert harness._scan_evidence_secrets(encoded) == [], "sanitized evidence still matches secret patterns"
    assert "sha256:" in encoded and "last4:" in encoded, "sanitizer lost safe correlation summary"

    phase7_source = inspect.getsource(harness.run_phase_7_observability)
    helper_source = inspect.getsource(harness._poll_observability_status)
    assert "_support_readiness(marker)" in phase7_source, "phase 7 must gate API status on direct support readiness"
    assert "observability_direct_readiness" in inspect.getsource(harness._support_readiness)
    assert "time.monotonic() + 90" in helper_source, "observability transition must use a bounded deadline"
    assert "observability_aggregate_poll" in helper_source, "observability transition polls require evidence"
    assert "--env-file" in phase7_source, "component recovery must reuse run-scoped support configuration"
    phase2_source = inspect.getsource(harness.run_phase_2_cluster_node_redis)
    remote_source = inspect.getsource(harness._run_positive_remote_ssh_fixture)
    seed_source = inspect.getsource(harness._seed_remote_dind_config_file)
    assert "_run_positive_remote_ssh_fixture" in phase2_source and "positive_fixture" in remote_source, "phase 2 must certify the positive remote SSH fixture"
    assert "docker_inspect_ssh" in remote_source and "no_local_fallback" in remote_source, "remote evidence must prove target-bound inspection without fallback"
    assert "remote_config_seed" in seed_source and "docker run --rm" in seed_source and "rm -rf /seed" in seed_source, "remote fixture must seed the nested DinD file bind before deployment"

    # Functional transition regression: a transient degraded response must be
    # polled until all four direct signals become available, rather than being
    # asserted immediately after Compose returns.
    class _FakeEvidence:
        def __init__(self) -> None:
            self.labels: list[str] = []

        def action(self, label: str, **details: object) -> None:
            self.labels.append(label)

    original_request = harness.request
    original_evidence = harness._evidence
    original_sleep = harness.time.sleep
    original_monotonic = harness.time.monotonic
    original_manifest = harness.IDENTITY_MANIFEST
    fake_evidence = _FakeEvidence()
    states = [
        {"overall_state": "degraded", "signals": {name: {"state": "degraded", "fresh": False} for name in ("service", "prometheus", "loki", "alloy")}},
        {"overall_state": "available", "signals": {name: {"state": "available", "fresh": True} for name in ("service", "prometheus", "loki", "alloy")}},
    ]
    clock = [0.0]
    try:
        harness.IDENTITY_MANIFEST = {"service_id": 2}
        harness.request = lambda *args, **kwargs: states.pop(0)
        harness._evidence = lambda: fake_evidence
        harness.time.sleep = lambda seconds: clock.__setitem__(0, clock[0] + float(seconds))
        harness.time.monotonic = lambda: clock[0]
        transitioned = harness._poll_observability_status("OBS-RUN-dry", available=True, label="transition")
        assert transitioned["overall_state"] == "available"
        assert fake_evidence.labels == ["observability_aggregate_poll", "observability_aggregate_poll"]
    finally:
        harness.request = original_request
        harness._evidence = original_evidence
        harness.time.sleep = original_sleep
        harness.time.monotonic = original_monotonic
        harness.IDENTITY_MANIFEST = original_manifest

    # When generated evidence is present, scan every owned run directory as a
    # regression guard.  The check reports only the path/count, never content
    # or a candidate token.
    evidence_root = Path(os.environ.get("PLATFORMOPS_ACCEPTANCE_EVIDENCE_DIR", "/tmp/platformops-redis-acceptance"))
    if evidence_root.is_dir():
        artifact_count = 0
        for artifact in evidence_root.rglob("*"):
            if artifact.is_file() and artifact.suffix in {".json", ".txt", ".log"}:
                artifact_count += 1
                payload = artifact.read_text(encoding="utf-8", errors="replace")
                assert harness._scan_evidence_secrets(payload) == [], f"secret pattern in generated artifact: {artifact}"
        assert artifact_count > 0, "evidence scan fixture found no generated artifacts"

    original_run_id = harness.RUN_ID
    harness.RUN_ID = "dry-acceptance-run"
    try:
        exact_path = "/tmp/platformops/dry-acceptance-run/redis/logs/redis.log"
        loki_payload = {
            "status": "success",
            "data": {"result": [{"stream": {"filename": exact_path}, "values": [["1", "OBS-RUN-dry-acceptance-run redis=PONG"], ["2", "OBS-RUN-dry-acceptance-run redis=PONG"], ["3", "OBS-RUN-dry-acceptance-run redis=PONG"]]}]},
        }
        assert harness._loki_marker_count(loki_payload, log_path=exact_path, marker="OBS-RUN-dry-acceptance-run") == 3
        assert harness._loki_marker_count(loki_payload, log_path="/var/log/redis/redis.log", marker="OBS-RUN-dry-acceptance-run") == 0
        assert harness._loki_marker_count(loki_payload, log_path=exact_path, marker="OBS-RUN-other-run") == 0
        valid = {
            "category": "lifecycle",
            "message": "Delete finished for dry-acceptance-run",
            "metadata_json": json.dumps({"job_id": 7, "command_ok": True, "removed": True}),
        }
        harness._validate_retained_audit_event(valid)
        applied = {
            "category": "config",
            "message": "Applied verified configuration change for dry-acceptance-run",
            "metadata_json": json.dumps({"action": "applied", "runtime_path": "/usr/local/etc/redis/redis.conf"}),
        }
        harness._validate_retained_audit_event(applied)
        drifted = {
            "category": "drift",
            "message": "Drift check for dry-acceptance-run: drifted",
            "metadata_json": json.dumps({"differences": 1}),
        }
        harness._validate_retained_audit_event(drifted)
        indexed = {
            "category": "diagnostics",
            "message": "Indexed 0 log archives for dry-acceptance-run",
            "metadata_json": json.dumps({"archives": 0}),
        }
        harness._validate_retained_audit_event(indexed)
        backfill_started = {
            "category": "diagnostics",
            "message": "Log backfill started for dry-acceptance-run",
            "metadata_json": json.dumps({"ready": True, "missing": []}),
        }
        harness._validate_retained_audit_event(backfill_started)
        archive_downloaded = {
            "category": "diagnostics",
            "message": "Bulk downloaded 1 archives for dry-acceptance-run",
            "metadata_json": json.dumps({"archive_ids": [2], "zip_filename": "dry-acceptance-run.zip"}),
        }
        harness._validate_retained_audit_event(archive_downloaded)
        chat_event = {
            "category": "diagnostics",
            "message": "AI log chat for dry-acceptance-run",
            "metadata_json": json.dumps({"window": "current", "question_len": 24}),
        }
        harness._validate_retained_audit_event(chat_event)
        unavailable_chat = {
            "success": False,
            "answer": "",
            "evidence": [],
            "error": "No container log lines available",
        }
        chat_error = str(unavailable_chat["error"]).lower()
        assert "no container log lines available" in chat_error, "typed no-log chat response lost explicit unavailable contract"
        invalid_event = {
            "category": "lifecycle",
            "message": "Unclassified dry-acceptance-run mutation",
            "metadata_json": "{}",
        }
        try:
            harness._validate_retained_audit_event(invalid_event)
        except harness.AcceptanceFailure:
            pass
        else:
            raise AssertionError("event normalization accepted empty/non-terminal metadata")
    finally:
        harness.RUN_ID = original_run_id
    print("redis acceptance harness contract checks: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
