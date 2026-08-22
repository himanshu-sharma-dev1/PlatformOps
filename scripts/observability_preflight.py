#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from observability_utils import (
    ObservabilityError,
    dump_json,
    labels_to_selector,
    load_env_file,
    load_service_install,
    main_service_contract_records,
    path_is_covered_by_volume,
    resolve_contract_value,
    resolve_host_volume_sources,
)

REQUIRED_DIAGNOSTICS_VARS = [
    "CPLATFORM_DIAGNOSTICS_LOKI_URL",
]


def check_url(session, url):
    response = session.get(url, timeout=5)
    response.raise_for_status()
    return response


def loki_series_exists(session, loki_url, labels):
    response = session.get(
        f"{loki_url.rstrip('/')}/loki/api/v1/series",
        params={"match[]": labels_to_selector(labels)},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    return bool((payload or {}).get("data"))


def main():
    parser = argparse.ArgumentParser(description="Validate diagnostics and observability reproducibility inputs.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--diagnostics-env", required=True)
    parser.add_argument("--service-install", default=None)
    parser.add_argument("--service-volume", default="/home/ubuntu/Backup_Platform")
    parser.add_argument("--machine-volume", default=None)
    parser.add_argument("--check-loki-series", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    service_install_path = Path(args.service_install or repo_root / "cPlatform/config/service_install.yaml").resolve()
    diagnostics_env_path = Path(args.diagnostics_env).resolve()
    machine_volume = args.machine_volume or args.service_volume

    report = {"errors": [], "warnings": [], "checks": {}}

    try:
        diagnostics_env = load_env_file(diagnostics_env_path)
    except ObservabilityError as exc:
        report["errors"].append(str(exc))
        print(dump_json(report))
        return 1

    missing = [name for name in REQUIRED_DIAGNOSTICS_VARS if not diagnostics_env.get(name)]
    if missing:
        report["errors"].append(f"Missing diagnostics env vars: {', '.join(missing)}")

    session = requests.Session()
    loki_url = diagnostics_env.get("CPLATFORM_DIAGNOSTICS_LOKI_URL", "")
    glitchtip_url = diagnostics_env.get("CPLATFORM_GLITCHTIP_BASE_URL", "")

    if loki_url:
        try:
            check_url(session, f"{loki_url.rstrip('/')}/ready")
            report["checks"]["loki_ready"] = True
        except Exception as exc:
            report["warnings"].append(f"Loki health check failed: {exc}")
    if glitchtip_url:
        try:
            response = session.get(glitchtip_url.rstrip("/") + "/", timeout=5, allow_redirects=False)
            if response.status_code not in [200, 302]:
                raise ObservabilityError(f"unexpected status {response.status_code}")
            report["checks"]["glitchtip_reachable"] = True
        except Exception as exc:
            report["warnings"].append(f"GlitchTip health check failed: {exc}")

    service_install = load_service_install(service_install_path)
    contract_checks = []
    for service_name, main_contract, obs in main_service_contract_records(service_install):
        service_errors = []
        service_warnings = []
        target_name = service_name
        file_logs = (obs or {}).get("file_logs") or {}
        labels = dict(file_logs.get("loki_labels") or {})
        paths = [
            resolve_contract_value(path, args.service_volume, machine_volume, service_name)
            for path in (file_logs.get("paths") or [])
        ]
        path_exists = any(Path(path).exists() for path in paths)
        volume_sources = resolve_host_volume_sources(
            (main_contract or {}).get("Volumes") or [],
            args.service_volume,
            machine_volume,
            service_name,
        )
        contract_report = {
            "service": service_name,
            "target": target_name,
            "has_main_contract": bool(main_contract),
            "paths": paths,
            "path_exists": path_exists,
            "labels": labels,
            "volume_sources": volume_sources,
            "errors": service_errors,
            "warnings": service_warnings,
        }

        if not main_contract:
            service_errors.append("missing main Docker_Info.<ServiceName> contract")
            report["errors"].append(f"{service_name}/{target_name}: missing main Docker_Info.<ServiceName> contract")
            contract_checks.append(contract_report)
            continue

        for key in ["container_history", "live_logs", "service_events", "file_logs"]:
            section = (obs or {}).get(key)
            if not isinstance(section, dict) or "enabled" not in section:
                service_errors.append(f"missing Observability.{key}.enabled")
                report["errors"].append(f"{service_name}/{target_name}: missing Observability.{key}.enabled")

        file_logs_enabled = bool((file_logs or {}).get("enabled"))
        if file_logs_enabled:
            if not paths:
                service_errors.append("file logs enabled but no paths configured")
                report["errors"].append(f"{service_name}/{target_name}: file logs enabled but no paths configured")
            if not labels:
                service_errors.append("file logs enabled but no Loki labels configured")
                report["errors"].append(f"{service_name}/{target_name}: file logs enabled but no Loki labels configured")
            uncovered_paths = [path for path in paths if not path_is_covered_by_volume(path, volume_sources)]
            if uncovered_paths:
                service_errors.append(f"file log paths are not backed by a host volume: {', '.join(uncovered_paths)}")
                report["errors"].append(
                    f"{service_name}/{target_name}: file log paths are not backed by a host volume: {', '.join(uncovered_paths)}"
                )
            if not path_exists:
                service_warnings.append("none of the configured file log paths exist locally")
                report["warnings"].append(f"{service_name}/{target_name}: none of the configured file log paths exist locally")

        if args.check_loki_series and loki_url and labels:
            try:
                contract_report["loki_series_exists"] = loki_series_exists(session, loki_url, labels)
                if not contract_report["loki_series_exists"]:
                    service_warnings.append(f"no Loki series found for selector {labels}")
                    report["warnings"].append(f"{service_name}/{target_name}: no Loki series found for selector {labels}")
            except Exception as exc:
                report["errors"].append(f"{service_name}/{target_name}: Loki series check failed: {exc}")
        contract_checks.append(contract_report)

    report["checks"]["main_service_observability_contracts"] = contract_checks
    print(dump_json(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
