#!/usr/bin/env python3
import argparse
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

import requests

LOG_TS_PATTERNS = [
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"),
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)"),
    re.compile(r"^(?P<ts>\d{2}-\d{2}-\d{2},\d{2}:\d{2}:\d{2}(?:AM|PM))"),
]

FALLBACK_WINDOWS = [
    ("7d", timedelta(days=7)),
    ("72h", timedelta(hours=72)),
    ("24h", timedelta(hours=24)),
    ("6h", timedelta(hours=6)),
    ("1h", timedelta(hours=1)),
]


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ["true", "1", "yes", "y", "on"]:
            return True
        if normalized in ["false", "0", "no", "n", "off"]:
            return False
    return default


def _parse_iso_z(ts_value):
    matched = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$", ts_value)
    if not matched:
        return None
    base = matched.group(1)
    fraction = (matched.group(2) or "")
    if fraction:
        fraction = (fraction[:6]).ljust(6, "0")
        normalized = f"{base}.{fraction}+00:00"
    else:
        normalized = f"{base}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_log_timestamp(line):
    line = str(line or "")
    for pattern in LOG_TS_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        ts_value = match.group("ts")
        try:
            if ts_value.endswith("Z"):
                parsed = _parse_iso_z(ts_value)
                if parsed is not None:
                    return parsed
                continue
            if "," in ts_value:
                if ts_value.endswith("AM") or ts_value.endswith("PM"):
                    return datetime.strptime(ts_value, "%d-%m-%y,%I:%M:%S%p").replace(tzinfo=timezone.utc)
                return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=timezone.utc)
            return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ns_timestamp(ts):
    return str(int(ts.timestamp() * 1_000_000_000))


def _escape_label_value(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def labels_to_selector(labels):
    pairs = [f'{key}="{_escape_label_value(value)}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(pairs) + "}"


def collect_files(log_paths):
    collected = []
    seen = set()
    missing_paths = []
    permission_errors = []
    for raw_path in log_paths:
        path_obj = Path(str(raw_path))
        if not path_obj.exists():
            missing_paths.append(str(path_obj))
            continue
        if path_obj.is_file():
            files = [path_obj]
        else:
            try:
                files = sorted(path_obj.glob("*.log*"), key=lambda path: path.stat().st_mtime, reverse=True)
            except PermissionError as exc:
                permission_errors.append({"path": str(path_obj), "error": str(exc)})
                continue
            except OSError as exc:
                permission_errors.append({"path": str(path_obj), "error": str(exc)})
                continue
        for file_path in files:
            try:
                if not file_path.is_file():
                    continue
                resolved = str(file_path.resolve())
            except PermissionError as exc:
                permission_errors.append({"path": str(file_path), "error": str(exc)})
                continue
            except OSError as exc:
                permission_errors.append({"path": str(file_path), "error": str(exc)})
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(file_path)
    safe_files = []
    for file_path in collected:
        try:
            file_path.stat()
            safe_files.append(file_path)
        except PermissionError as exc:
            permission_errors.append({"path": str(file_path), "error": str(exc)})
        except OSError as exc:
            permission_errors.append({"path": str(file_path), "error": str(exc)})
    return sorted(safe_files, key=lambda path: path.stat().st_mtime, reverse=True), missing_paths, permission_errors


def scan_log_bounds(log_path):
    earliest = None
    latest = None
    parsed_lines = 0
    now = datetime.now(timezone.utc)

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            ts = parse_log_timestamp(line)
            if ts is None or ts > now:
                continue
            parsed_lines += 1
            if earliest is None or ts < earliest:
                earliest = ts
            if latest is None or ts > latest:
                latest = ts
    return earliest, latest, parsed_lines


def earliest_loki_timestamp(session, loki_url, labels, start_at, end_at):
    selector = labels_to_selector(labels)
    response = session.get(
        f"{loki_url.rstrip('/')}/loki/api/v1/query_range",
        params={
            "query": selector,
            "direction": "forward",
            "limit": 1,
            "start": ns_timestamp(start_at),
            "end": ns_timestamp(end_at),
        },
        timeout=20,
    )
    if response.status_code == 400 and "exceeds the limit" in (response.text or "").lower():
        raise RuntimeError(response.text.strip())
    response.raise_for_status()
    streams = ((response.json() or {}).get("data") or {}).get("result") or []
    if not streams:
        return None
    values = streams[0].get("values") or []
    if not values:
        return None
    return datetime.fromtimestamp(int(values[0][0]) / 1_000_000_000, tz=timezone.utc)


def probe_earliest_loki_timestamp(session, loki_url, labels, start_at, end_at):
    try:
        earliest = earliest_loki_timestamp(session, loki_url, labels, start_at, end_at)
        return earliest, start_at, end_at, "file_range"
    except RuntimeError as exc:
        last_error = exc

    now = datetime.now(timezone.utc)
    bounded_end = min(end_at, now)
    for window_name, window_size in FALLBACK_WINDOWS:
        bounded_start = max(start_at, now - window_size)
        if bounded_start >= bounded_end:
            continue
        try:
            earliest = earliest_loki_timestamp(session, loki_url, labels, bounded_start, bounded_end)
            return earliest, bounded_start, bounded_end, window_name
        except RuntimeError as exc:
            last_error = exc

    raise RuntimeError(
        "Loki rejected earliest-timestamp probe because requested range exceeds server limits"
        f": {last_error}"
    )


def push_entries(session, loki_url, labels, entries):
    payload = {"streams": [{"stream": labels, "values": entries}]}
    response = session.post(
        f"{loki_url.rstrip('/')}/loki/api/v1/push",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Backfill startup-gap file logs to Loki for a service.")
    parser.add_argument("--loki_url", required=True)
    parser.add_argument("--log_paths_b64", required=True)
    parser.add_argument("--labels_b64", required=True)
    parser.add_argument("--allow_full_file", default="true")
    parser.add_argument("--chunk_size", type=int, default=1000)
    args = parser.parse_args()

    allow_full_file = _coerce_bool(args.allow_full_file, default=True)
    log_paths = json.loads(base64.b64decode(args.log_paths_b64).decode())
    labels = json.loads(base64.b64decode(args.labels_b64).decode())
    files, missing_paths, permission_errors = collect_files(log_paths)
    if not files:
        print(json.dumps({
            "success": False,
            "error": "Permission denied reading configured file logs" if permission_errors else "No file logs found on node for configured paths",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "candidate_files": [],
            "checked_paths": log_paths,
            "missing_paths": missing_paths,
            "permission_errors": permission_errors,
        }))
        return

    selected_log = files[0]
    file_start, file_end, parsed_lines = scan_log_bounds(selected_log)
    if parsed_lines == 0 or file_start is None or file_end is None:
        print(json.dumps({
            "success": False,
            "error": "No parseable timestamps found in selected log file",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "selected_log_path": str(selected_log),
            "candidate_files": [str(path) for path in files[:20]],
            "checked_paths": log_paths,
            "missing_paths": missing_paths,
            "permission_errors": permission_errors,
        }))
        return

    session = requests.Session()
    earliest, probe_start, probe_end, probe_window = probe_earliest_loki_timestamp(
        session, args.loki_url, labels, file_start, file_end
    )
    if earliest is None and not allow_full_file:
        print(json.dumps({
            "success": False,
            "error": "No existing Loki history for labels; enable allow_full_file to ingest complete file",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "selected_log_path": str(selected_log),
            "candidate_files": [str(path) for path in files[:20]],
            "parsed_lines": parsed_lines,
            "checked_paths": log_paths,
            "missing_paths": missing_paths,
            "permission_errors": permission_errors,
        }))
        return

    pending = []
    pushed = 0
    now = datetime.now(timezone.utc)
    with selected_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            ts = parse_log_timestamp(line)
            if ts is None or ts > now:
                continue
            if earliest is not None and ts >= earliest:
                break
            pending.append([ns_timestamp(ts), line.rstrip("\n")])
            if len(pending) >= args.chunk_size:
                push_entries(session, args.loki_url, labels, pending)
                pushed += len(pending)
                pending = []

    if pending:
        push_entries(session, args.loki_url, labels, pending)
        pushed += len(pending)

    print(json.dumps({
        "success": True,
        "error": "",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "selected_log_path": str(selected_log),
        "candidate_files": [str(path) for path in files[:20]],
        "checked_paths": log_paths,
        "missing_paths": missing_paths,
        "permission_errors": permission_errors,
        "labels": labels,
        "parsed_lines": parsed_lines,
        "earliest_existing": earliest.isoformat() if earliest else None,
        "probe_start": probe_start.isoformat(),
        "probe_end": probe_end.isoformat(),
        "probe_window": probe_window,
        "pushed_entries": pushed,
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({
            "success": False,
            "error": str(exc),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }))
