from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

LOG_TS_PATTERNS = [
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"),
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)"),
]
ENV_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


class ObservabilityError(Exception):
    pass


def parse_log_timestamp(line: str):
    raw = str(line or "")
    for pattern in LOG_TS_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        ts_value = match.group("ts")
        try:
            if ts_value.endswith("Z"):
                return datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            if "," in ts_value:
                return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=timezone.utc)
            return datetime.strptime(ts_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ns_timestamp(value: datetime) -> str:
    return str(int(value.timestamp() * 1_000_000_000))


def parse_label_args(label_items: Iterable[str]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for item in label_items:
        if "=" not in item:
            raise ObservabilityError(f"Invalid label '{item}'. Expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ObservabilityError(f"Invalid label '{item}'. Expected non-empty key and value")
        labels[key] = value
    return labels


def labels_to_selector(labels: Dict[str, str]) -> str:
    parts = [f'{key}="{value}"' for key, value in sorted(labels.items())]
    return "{" + ", ".join(parts) + "}"


def load_env_file(path: Path, *, strict: bool = False) -> Dict[str, str]:
    if not path.exists():
        raise ObservabilityError(f"Env file not found: {path}")
    values: Dict[str, str] = {}
    with path.open() as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if strict and not ENV_LINE_RE.match(line):
                raise ObservabilityError(f"Invalid env line {line_no} in {path}: {line}")
            if "=" not in line:
                if strict:
                    raise ObservabilityError(f"Invalid env line {line_no} in {path}: {line}")
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                if strict:
                    raise ObservabilityError(f"Invalid env line {line_no} in {path}: {line}")
                continue
            values[key] = value
    return values


def derive_diagnostics_env_path(django_env_path: Path) -> Path:
    name = django_env_path.name
    if name == "deployment.env":
        return django_env_path.with_name("diagnostics.env")
    if name.startswith("deployment.") and name.endswith(".env"):
        return django_env_path.with_name("diagnostics" + name[len("deployment"):])
    return django_env_path.with_name("diagnostics.env")


def resolve_contract_value(raw_value: str, service_volume: str, machine_volume: str, service_name: str) -> str:
    value = str(raw_value or "")
    replacements = {
        "{{ service_volume }}": service_volume.rstrip("/"),
        "{{ machine_volume }}": machine_volume.rstrip("/"),
        "{{ service }}": service_name,
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    if value.startswith("//"):
        value = "/" + value.lstrip("/")
    return value


def load_service_install(path: Path):
    with path.open() as fh:
        return yaml.safe_load(fh)


def main_service_contract_records(config: dict) -> List[Tuple[str, dict, dict]]:
    records = []
    services = (config or {}).get("services", {})
    for service_name, service_cfg in services.items():
        docker_info = (service_cfg or {}).get("Docker_Info", {})
        main_contract = docker_info.get(service_name)
        if not isinstance(main_contract, dict):
            records.append((service_name, {}, {}))
            continue
        obs = main_contract.get("Observability") or main_contract.get("observability") or {}
        records.append((service_name, main_contract, obs if isinstance(obs, dict) else {}))
    return records


def main_service_observability_contracts(config: dict) -> List[Tuple[str, dict]]:
    results = []
    for service_name, _main_contract, obs in main_service_contract_records(config):
        if obs:
            results.append((service_name, obs))
    return results


def all_observability_contracts(config: dict) -> List[Tuple[str, str, dict]]:
    results = []
    services = (config or {}).get("services", {})
    for service_name, service_cfg in services.items():
        docker_info = (service_cfg or {}).get("Docker_Info", {})
        for target_name, target_cfg in docker_info.items():
            if not isinstance(target_cfg, dict):
                continue
            obs = target_cfg.get("Observability") or target_cfg.get("observability") or {}
            if obs:
                results.append((service_name, target_name, obs))
    return results


def resolve_host_volume_sources(volume_values, service_volume: str, machine_volume: str, service_name: str) -> List[str]:
    sources: List[str] = []
    for value in volume_values or []:
        if not isinstance(value, str) or ":" not in value:
            continue
        host_path = resolve_contract_value(value.split(":", 1)[0], service_volume, machine_volume, service_name).strip()
        if host_path:
            sources.append(host_path)
    return sources


def path_is_covered_by_volume(candidate_path: str, volume_sources: Iterable[str]) -> bool:
    normalized_candidate = str(candidate_path or "").rstrip("/")
    if not normalized_candidate:
        return False
    for volume_path in volume_sources:
        normalized_volume = str(volume_path or "").rstrip("/")
        if not normalized_volume:
            continue
        if normalized_candidate == normalized_volume:
            return True
        if normalized_candidate.startswith(normalized_volume + "/"):
            return True
    return False


def dump_json(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
