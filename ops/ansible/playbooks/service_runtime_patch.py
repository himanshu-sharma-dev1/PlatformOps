import argparse
import json
import subprocess
from datetime import datetime, timezone


def _run_command(command):
    return subprocess.run(command, capture_output=True, text=True)


def _inspect_container(container_name):
    process = _run_command(["docker", "inspect", container_name])
    if process.returncode != 0:
        return None
    try:
        return json.loads(process.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        return None


def _resolve_python_cmd(container_name):
    for candidate in ("python3", "python"):
        process = _run_command(["docker", "exec", container_name, candidate, "-V"])
        if process.returncode == 0:
            return candidate
    return ""


def _install_sentry_sdk(container_name, python_cmd):
    check_cmd = (
        "import importlib.metadata as m; "
        "import sentry_sdk; "
        "print(m.version('sentry-sdk'))"
    )
    check = _run_command([
        "docker", "exec", container_name, python_cmd, "-c", check_cmd
    ])
    if check.returncode == 0:
        return True, False, (check.stdout or "").strip()

    install = _run_command([
        "docker", "exec", container_name, "sh", "-lc",
        f"{python_cmd} -m pip install --no-cache-dir sentry-sdk==2.39.0",
    ])
    if install.returncode != 0:
        return False, False, (install.stderr or install.stdout or "").strip()

    check_after = _run_command([
        "docker", "exec", container_name, python_cmd, "-c", check_cmd
    ])
    if check_after.returncode != 0:
        return False, False, "sentry-sdk install command ran but package import failed"
    return True, True, (check_after.stdout or "").strip()


BOOTSTRAP_INSTALLER = r'''
import os
import site
import sys
import sysconfig
from pathlib import Path

MARK_BEGIN = "# IKTARA_GLITCHTIP_PATCH_BEGIN"
MARK_END = "# IKTARA_GLITCHTIP_PATCH_END"

dsn = os.getenv("SENTRY_DSN", "").strip()
glitchtip_enabled_default = os.getenv("GLITCHTIP_ENABLED", "true").strip() or "true"
service_name = os.getenv("GLITCHTIP_SERVICE_NAME", "").strip() or "service"
service_type = os.getenv("GLITCHTIP_SERVICE_TYPE", "").strip() or service_name
service_id = os.getenv("GLITCHTIP_SERVICE_ID", "").strip() or service_name
node_id = os.getenv("GLITCHTIP_NODE_ID", "").strip()
node_ip = os.getenv("GLITCHTIP_NODE_IP", "").strip()
container_name = os.getenv("GLITCHTIP_CONTAINER_NAME", "").strip() or service_id
container_id = os.getenv("GLITCHTIP_CONTAINER_ID", "").strip()
environment = os.getenv("GLITCHTIP_ENVIRONMENT", "").strip() or "validation"
release = os.getenv("GLITCHTIP_RELEASE", "").strip() or service_name
traces_sample_rate = os.getenv("GLITCHTIP_TRACES_SAMPLE_RATE", "0.0").strip() or "0.0"

if not dsn:
    raise SystemExit("missing SENTRY_DSN")

candidate_paths = []
purelib = sysconfig.get_paths().get("purelib", "")
if purelib:
    candidate_paths.append(purelib)
for path_value in site.getsitepackages():
    if path_value not in candidate_paths:
        candidate_paths.append(path_value)
for path_value in list(sys.path):
    if ("site-packages" in path_value or "dist-packages" in path_value) and path_value not in candidate_paths:
        candidate_paths.append(path_value)

target_dir = None
for candidate in candidate_paths:
    if not candidate:
        continue
    p = Path(candidate)
    if p.exists() and p.is_dir():
        target_dir = p
        break

if target_dir is None:
    raise SystemExit("Unable to find site-packages directory")

target_file = target_dir / "sitecustomize.py"

patch_block = f"""{MARK_BEGIN}
import os
import logging
try:
    _enabled_raw = os.getenv("GLITCHTIP_ENABLED", {glitchtip_enabled_default!r}).strip().lower()
    _enabled = _enabled_raw in ("1", "true", "yes", "on")
    if _enabled:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        _integrations = [LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR)]
        try:
            from sentry_sdk.integrations.django import DjangoIntegration
            _integrations.append(DjangoIntegration())
        except Exception:
            pass
        sentry_sdk.init(
            dsn={dsn!r},
            integrations=_integrations,
            environment={environment!r},
            release={release!r},
            traces_sample_rate=float({traces_sample_rate!r}),
            send_default_pii=False,
        )
        sentry_sdk.set_tag("service_type", {service_type!r})
        sentry_sdk.set_tag("service_name", {service_name!r})
        sentry_sdk.set_tag("service_id", {service_id!r})
        sentry_sdk.set_tag("node_id", {node_id!r})
        sentry_sdk.set_tag("node_ip", {node_ip!r})
        sentry_sdk.set_tag("container_name", {container_name!r})
        sentry_sdk.set_tag("container_id", {container_id!r})
except Exception:
    pass
{MARK_END}
"""

existing = ""
if target_file.exists():
    existing = target_file.read_text(encoding="utf-8")

patch_changed = False
if MARK_BEGIN in existing and MARK_END in existing:
    start_idx = existing.index(MARK_BEGIN)
    end_idx = existing.index(MARK_END) + len(MARK_END)
    existing_block = existing[start_idx:end_idx]
    if existing_block.strip() == patch_block.strip():
        updated = existing
    else:
        updated = existing[:start_idx] + patch_block + existing[end_idx:]
        patch_changed = True
else:
    suffix = "" if existing.endswith("\n") or not existing else "\n"
    updated = existing + suffix + patch_block + "\n"
    patch_changed = True

if patch_changed:
    target_file.write_text(updated, encoding="utf-8")
print(f"PATCH_CHANGED={'true' if patch_changed else 'false'}")
print(str(target_file))
'''


def _install_runtime_bootstrap(
    container_name,
    container_id,
    python_cmd,
    sentry_dsn,
    glitchtip_enabled,
    service_type,
    service_name,
    service_id,
    node_id,
    node_ip,
    environment,
    release,
    traces_sample_rate,
):
    command = [
        "docker", "exec",
        "-e", f"SENTRY_DSN={sentry_dsn}",
        "-e", f"GLITCHTIP_ENABLED={glitchtip_enabled}",
        "-e", f"GLITCHTIP_SERVICE_TYPE={service_type}",
        "-e", f"GLITCHTIP_SERVICE_NAME={service_name}",
        "-e", f"GLITCHTIP_SERVICE_ID={service_id}",
        "-e", f"GLITCHTIP_NODE_ID={node_id}",
        "-e", f"GLITCHTIP_NODE_IP={node_ip}",
        "-e", f"GLITCHTIP_CONTAINER_NAME={container_name}",
        "-e", f"GLITCHTIP_CONTAINER_ID={container_id}",
        "-e", f"GLITCHTIP_ENVIRONMENT={environment}",
        "-e", f"GLITCHTIP_RELEASE={release}",
        "-e", f"GLITCHTIP_TRACES_SAMPLE_RATE={traces_sample_rate}",
        container_name,
        python_cmd,
        "-c",
        BOOTSTRAP_INSTALLER,
    ]
    process = _run_command(command)
    if process.returncode != 0:
        return False, "", (process.stderr or process.stdout or "").strip(), False
    stdout_value = (process.stdout or "").strip()
    lines = stdout_value.splitlines()
    bootstrap_path = lines[-1] if lines else ""
    patch_changed = False
    for line in lines:
        if line.startswith("PATCH_CHANGED="):
            patch_changed = str(line.split("=", 1)[1]).strip().lower() == "true"
            break
    return True, bootstrap_path, "", patch_changed


def _restart_container(container_name):
    restart = _run_command(["docker", "restart", container_name])
    if restart.returncode != 0:
        return False, (restart.stderr or restart.stdout or "").strip()

    inspect_data = _inspect_container(container_name)
    if not inspect_data:
        return False, "Container missing after restart"
    state = (inspect_data.get("State", {}) or {}).get("Status", "")
    if state != "running":
        return False, f"Container state after restart: {state or 'unknown'}"
    return True, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container_name", required=True)
    parser.add_argument("--service_type", required=True)
    parser.add_argument("--service_name", required=True)
    parser.add_argument("--service_id", required=True)
    parser.add_argument("--sentry_dsn", required=True)
    parser.add_argument("--glitchtip_enabled", default="true")
    parser.add_argument("--node_id", default="")
    parser.add_argument("--node_ip", default="")
    parser.add_argument("--environment", default="validation")
    parser.add_argument("--release", default="")
    parser.add_argument("--traces_sample_rate", default="0.0")
    parser.add_argument("--restart", default="true")
    args = parser.parse_args()

    checked_at = datetime.now(timezone.utc).isoformat()
    inspect_data = _inspect_container(args.container_name)
    if inspect_data is None:
        print(json.dumps({
            "success": False,
            "error": "Container not found on node",
            "checked_at": checked_at,
        }))
        return

    container_id = str(inspect_data.get("Id", "")).strip()
    python_cmd = _resolve_python_cmd(args.container_name)
    if not python_cmd:
        print(json.dumps({
            "success": False,
            "error": "Python runtime not found in target container",
            "checked_at": checked_at,
        }))
        return

    install_ok, installed_now, install_info = _install_sentry_sdk(args.container_name, python_cmd)
    if not install_ok:
        print(json.dumps({
            "success": False,
            "error": f"Failed to install sentry-sdk: {install_info}",
            "checked_at": checked_at,
        }))
        return

    release_value = args.release.strip() or args.service_name or args.service_type
    bootstrap_ok, bootstrap_path, bootstrap_error, patch_changed = _install_runtime_bootstrap(
        args.container_name,
        container_id,
        python_cmd,
        args.sentry_dsn.strip(),
        args.glitchtip_enabled.strip() or "true",
        args.service_type.strip() or args.service_name.strip(),
        args.service_name.strip() or args.service_type.strip(),
        args.service_id.strip() or args.container_name.strip(),
        args.node_id.strip(),
        args.node_ip.strip(),
        args.environment.strip() or "validation",
        release_value,
        args.traces_sample_rate.strip() or "0.0",
    )
    if not bootstrap_ok:
        print(json.dumps({
            "success": False,
            "error": f"Failed to install runtime bootstrap: {bootstrap_error}",
            "checked_at": checked_at,
        }))
        return

    restart_requested = str(args.restart).strip().lower() in ["true", "1", "yes", "on"]
    restart_required = bool(installed_now or patch_changed)
    restarted = False
    restart_skipped_reason = ""
    if restart_requested and restart_required:
        restarted = True
        restart_ok, restart_error = _restart_container(args.container_name)
        if not restart_ok:
            print(json.dumps({
                "success": False,
                "error": restart_error,
                "checked_at": checked_at,
                "python_cmd": python_cmd,
                "bootstrap_path": bootstrap_path,
                "patch_changed": bool(patch_changed),
            }))
            return
    elif restart_requested and not restart_required:
        restart_skipped_reason = "No runtime patch changes detected"

    print(json.dumps({
        "success": True,
        "error": "",
        "container_name": args.container_name,
        "container_id": container_id,
        "service_id": args.service_id,
        "service_type": args.service_type,
        "python_cmd": python_cmd,
        "sentry_sdk_installed_now": bool(installed_now),
        "sentry_sdk_version": install_info,
        "bootstrap_path": bootstrap_path,
        "patch_changed": bool(patch_changed),
        "restart_requested": restart_requested,
        "restart_required": restart_required,
        "restarted": restarted,
        "restart_skipped_reason": restart_skipped_reason,
        "checked_at": checked_at,
    }))


if __name__ == "__main__":
    main()
