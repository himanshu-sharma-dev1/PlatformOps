#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    from observability_utils import ObservabilityError, labels_to_selector, ns_timestamp, parse_label_args, parse_log_timestamp
except ModuleNotFoundError:
    from scripts.observability_utils import (
        ObservabilityError,
        labels_to_selector,
        ns_timestamp,
        parse_label_args,
        parse_log_timestamp,
    )

FALLBACK_WINDOWS = [
    ("7d", timedelta(days=7)),
    ("72h", timedelta(hours=72)),
    ("24h", timedelta(hours=24)),
    ("6h", timedelta(hours=6)),
    ("1h", timedelta(hours=1)),
]


class LokiRangeLimitError(ObservabilityError):
    pass


def scan_log_bounds(log_path: Path):
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
        raise LokiRangeLimitError(response.text.strip())
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
    except LokiRangeLimitError as exc:
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
        except LokiRangeLimitError as exc:
            last_error = exc

    raise ObservabilityError(
        "Loki rejected the earliest-timestamp probe because the requested range exceeds server limits"
        f": {last_error}"
    )


def push_entries(session, loki_url, labels, entries):
    payload = {
        "streams": [
            {
                "stream": labels,
                "values": entries,
            }
        ]
    }
    response = session.post(
        f"{loki_url.rstrip('/')}/loki/api/v1/push",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Backfill missing startup-gap file logs into Loki.")
    parser.add_argument("--loki-url", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--label", action="append", default=[], help="Repeat key=value labels")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--allow-full-file", action="store_true")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    if not log_path.exists():
        raise SystemExit(f"Log file not found: {log_path}")

    file_start, file_end, parsed_lines = scan_log_bounds(log_path)
    if parsed_lines == 0 or file_start is None or file_end is None:
        raise SystemExit("No parseable timestamps were found in the log file.")

    labels = parse_label_args(args.label)
    session = requests.Session()
    earliest, probe_start, probe_end, probe_window = probe_earliest_loki_timestamp(
        session,
        args.loki_url,
        labels,
        file_start,
        file_end,
    )
    if earliest is None and not args.allow_full_file:
        raise SystemExit("No existing Loki history found. Re-run with --allow-full-file to ingest the whole file.")

    pending = []
    pushed = 0
    now = datetime.now(timezone.utc)
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
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
        "log_path": str(log_path),
        "labels": labels,
        "earliest_existing": earliest.isoformat() if earliest else None,
        "probe_start": probe_start.isoformat(),
        "probe_end": probe_end.isoformat(),
        "probe_window": probe_window,
        "pushed_entries": pushed,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ObservabilityError, requests.RequestException) as exc:
        raise SystemExit(str(exc))
