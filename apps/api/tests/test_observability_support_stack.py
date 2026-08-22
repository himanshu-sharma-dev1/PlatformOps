"""Focused contracts for the disposable observability support seam."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[3]


def test_support_script_gates_three_markers_and_waits_for_exact_loki_evidence():
    script_path = ROOT / "scripts" / "observability_support_stack.sh"
    subprocess.run(["sh", "-n", str(script_path)], check=True)
    script = script_path.read_text(encoding="utf-8")

    assert script.index("start_marker\n    compose up") < script.index("release_marker\n    wait_loki_marker")
    assert "for seq in 0001 0002 0003" in script
    assert "(?<![A-Za-z0-9_-])" in script and "(?![A-Za-z0-9_-])" in script
    assert 'PLATFORMOPS_OBS_LOG_PATH=$LOG_PATH' in script


def test_alloy_writes_only_to_support_private_loki_alias():
    compose = (ROOT / "ops" / "compose" / "docker-compose.observability.yml").read_text(encoding="utf-8")
    alloy = (ROOT / "ops" / "compose" / "observability" / "config.alloy").read_text(encoding="utf-8")

    assert "observability-support-loki" in compose
    assert 'url = "http://observability-support-loki:3100/loki/api/v1/push"' in alloy
    assert 'action = "keep"' in alloy
    for forbidden in ("/var/run/docker.sock", "cplatform_iktara_cPlatform", "9002:", "9008:", "ipv4_address"):
        assert forbidden not in compose
