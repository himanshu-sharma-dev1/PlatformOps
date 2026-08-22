import argparse
import base64
import json
from pathlib import Path
from datetime import datetime, timezone
import re

LOG_TS_PATTERNS = [
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"),
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)"),
    re.compile(r"^(?P<ts>\d{2}-\d{2}-\d{2},\d{2}:\d{2}:\d{2}(?:AM|PM))"),
]


def parse_timestamp(line):
    for pattern in LOG_TS_PATTERNS:
        match = pattern.search(str(line or ""))
        if not match:
            continue
        ts_value = match.group("ts")
        try:
            if ts_value.endswith("Z"):
                return datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            if "," in ts_value:
                if ts_value.endswith("AM") or ts_value.endswith("PM"):
                    return datetime.strptime(ts_value, "%d-%m-%y,%I:%M:%S%p").replace(tzinfo=timezone.utc)
                return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=timezone.utc)
            return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def collect_files(log_paths):
    collected = []
    seen = set()
    missing_paths = []
    permission_errors = []
    for log_path in log_paths:
        path_obj = Path(log_path)
        if not path_obj.exists():
            missing_paths.append(str(path_obj))
            continue
        try:
            files = sorted(path_obj.glob("*.log*"), key=lambda path: path.stat().st_mtime, reverse=True)
        except PermissionError as exc:
            permission_errors.append({"path": str(path_obj), "error": str(exc)})
            continue
        except OSError as exc:
            permission_errors.append({"path": str(path_obj), "error": str(exc)})
            continue
        for log_file in files:
            try:
                if not log_file.is_file():
                    continue
                resolved = str(log_file.resolve())
            except PermissionError as exc:
                permission_errors.append({"path": str(log_file), "error": str(exc)})
                continue
            except OSError as exc:
                permission_errors.append({"path": str(log_file), "error": str(exc)})
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(log_file)
    return collected, missing_paths, permission_errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log_paths_b64", required=True)
    parser.add_argument("--tail_lines", type=int, default=250)
    parser.add_argument("--file_stream", default="all")
    args = parser.parse_args()

    log_paths = json.loads(base64.b64decode(args.log_paths_b64).decode())
    files, missing_paths, permission_errors = collect_files(log_paths)
    selected = args.file_stream.strip() or "all"
    if selected != "all":
        files = [log_file for log_file in files if log_file.name == selected]
        if not files:
            print(json.dumps({
                "error": f"File stream '{selected}' is not available on node",
                "log_lines": [],
                "log_source": "node_file",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "selected_file_stream": selected,
                "checked_paths": log_paths,
                "missing_paths": missing_paths,
                "permission_errors": permission_errors,
            }))
            return

    log_lines = []
    for log_file in files[:12]:
        try:
            lines = log_file.read_text(errors="ignore").splitlines()[-args.tail_lines:]
        except PermissionError as exc:
            permission_errors.append({"path": str(log_file), "error": str(exc)})
            continue
        except OSError as exc:
            permission_errors.append({"path": str(log_file), "error": str(exc)})
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            ts = parse_timestamp(line)
            log_lines.append({
                "timestamp": ts.isoformat() if ts else "",
                "message": line,
                "source": f"file:{log_file.name}",
            })

    log_lines.sort(key=lambda item: item.get("timestamp", ""))
    print(json.dumps({
        "error": "" if files or not permission_errors else "Permission denied reading configured file logs",
        "log_lines": log_lines[-args.tail_lines:],
        "log_source": "node_file",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "selected_file_stream": selected,
        "available_file_streams": [{"id": "all", "label": "All"}] + [{"id": file.name, "label": file.name} for file in files],
        "checked_paths": log_paths,
        "missing_paths": missing_paths,
        "permission_errors": permission_errors,
    }))


if __name__ == "__main__":
    main()
