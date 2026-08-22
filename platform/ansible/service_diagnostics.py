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


def _get_logs(container_name, since_hours=None, tail_lines=250):
    command = ["docker", "logs", "--timestamps", "--tail", str(tail_lines)]
    if since_hours:
        command.extend(["--since", f"{int(since_hours)}h"])
    command.append(container_name)

    process = _run_command(command)
    output = (process.stdout or "") + (process.stderr or "")
    log_lines = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0].startswith("20"):
            timestamp, message = parts
        else:
            timestamp, message = "", line
        log_lines.append({
            "timestamp": timestamp,
            "message": message,
            "source": "docker_logs",
        })
    return log_lines[-tail_lines:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container_name", required=True)
    parser.add_argument("--since_hours", default="")
    parser.add_argument("--tail_lines", type=int, default=250)
    args = parser.parse_args()

    inspect_data = _inspect_container(args.container_name)
    if inspect_data is None:
        print(json.dumps({
            "error": "Container not found on node",
            "log_lines": [],
            "log_source": "node_docker",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }))
        return

    log_lines = _get_logs(args.container_name, args.since_hours or None, args.tail_lines)
    print(json.dumps({
        "error": "",
        "container_name": args.container_name,
        "container_state": (inspect_data.get("State", {}) or {}).get("Status", "unknown"),
        "log_lines": log_lines,
        "log_source": "node_docker",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }))


if __name__ == "__main__":
    main()
