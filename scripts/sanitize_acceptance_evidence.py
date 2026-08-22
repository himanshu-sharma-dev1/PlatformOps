#!/usr/bin/env python3
"""Scrub or scan one owned Redis acceptance evidence directory.

This helper is deliberately run-scoped. It never walks arbitrary /tmp files,
prints secret matches, or changes an artifact outside the requested run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_redis_acceptance_test as harness  # noqa: E402


def _run_dir(run_id: str, root: Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise SystemExit("run id must contain only letters, digits, underscore, or hyphen")
    path = (root / run_id).resolve()
    if path.parent != root.resolve() or path.name != run_id:
        raise SystemExit("refusing an evidence path outside the exact run directory")
    if not path.is_dir():
        raise SystemExit(f"evidence directory not found: {path}")
    return path


def _scrub_json(path: Path, *, write: bool) -> tuple[int, list[str]]:
    raw = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        findings = harness._scan_evidence_secrets(raw)
        if write:
            sanitized = harness._sanitize_text(raw)
            if harness._scan_evidence_secrets(sanitized):
                raise SystemExit(f"unable to sanitize text artifact: {path}")
            path.write_text(sanitized, encoding="utf-8")
        return 0, findings
    findings = harness._scan_evidence_secrets(raw)
    if write:
        sanitized = harness._redact(value)
        encoded = json.dumps(sanitized, indent=2, sort_keys=True, default=str) + "\n"
        remaining = harness._scan_evidence_secrets(encoded)
        if remaining:
            raise SystemExit(f"unable to sanitize JSON artifact: {path}")
        path.write_text(encoded, encoding="utf-8")
    return 1, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root", default="/tmp/platformops-redis-acceptance")
    parser.add_argument("--check", action="store_true", help="scan only; do not rewrite artifacts")
    args = parser.parse_args(argv)
    run_dir = _run_dir(args.run_id, Path(args.root).resolve())
    files = sorted(path for path in run_dir.iterdir() if path.is_file() and path.suffix in {".json", ".txt", ".log"})
    changed = 0
    findings: set[str] = set()
    for path in files:
        count, labels = _scrub_json(path, write=not args.check)
        changed += count
        findings.update(labels)
    if args.check:
        if findings:
            print(f"secret_scan=FAIL files={len(files)} patterns={','.join(sorted(findings))}")
            return 1
        print(f"secret_scan=PASS files={len(files)} patterns=0")
        return 0
    print(f"scrubbed_run={args.run_id} files={changed} secret_scan=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
