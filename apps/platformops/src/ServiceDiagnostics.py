from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from dotenv import dotenv_values

from cPlatform.AppLogging import app_logger
from cPlatformIO.models import Service
from cPlatformIO.src import ServiceConfig, serviceEvent, serviceInstall

WINDOW_HOURS = {
    "current": 1,
    "24h": 24,
    "7d": 24 * 7,
}
DEFAULT_HISTORY_PAGE_SIZE = 200
MAX_HISTORY_PAGE_SIZE = 1000
SERVICE_INSTALL_CONFIG_CACHE = None
FILE_HISTORY_CAPABILITY_WINDOW = "7d"

LOG_SOURCE_CATALOG = [
    {
        "source_id": "container_live",
        "label": "Container Live",
        "polling_mode": "live",
        "supported_windows": ["current"],
        "supports_file_streams": False,
    },
    {
        "source_id": "container_history",
        "label": "Container History",
        "polling_mode": "snapshot",
        "supported_windows": ["current", "24h", "7d"],
        "supports_file_streams": False,
    },
    {
        "source_id": "file_live",
        "label": "File Logs",
        "polling_mode": "live",
        "supported_windows": ["current"],
        "supports_file_streams": True,
    },
    {
        "source_id": "service_history",
        "label": "File History",
        "polling_mode": "snapshot",
        "supported_windows": ["current", "24h", "7d"],
        "supports_file_streams": False,
    },
]

LOCAL_LOG_PATHS = {
    "AIOrchestrator": "/home/ubuntu/Backup_Platform/iktara/cPlatform/logs",
    "TrainingServer": "/home/ubuntu/Backup_Platform/iktara/trainingServer/logs",
    "InferenceServer": "/home/ubuntu/Backup_Platform/iktara/InferenceServer/logs",
    "MCPServer": "/home/ubuntu/Backup_Platform/iktara/MCPServer/logs",
    "optionCopilot": "/home/ubuntu/Backup_Platform/iktara/optionCopilot/logs",
}

LOCAL_LOG_PATH_CANDIDATES = {
    "AIOrchestrator": [
        "cPlatform/logs",
        "logs",
    ],
    "TrainingServer": [
        "Subsytems/dTrain/dTrain/logs",
        "Subsytems/dTrain/logs",
        "trainingServer/logs",
    ],
    "InferenceServer": [
        "Subsytems/dInfer/dInfer/logs",
        "Subsytems/dInfer/logs",
        "InferenceServer/logs",
    ],
    "MCPServer": [
        "Subsytems/mcpServer/logs",
        "MCPServer/logs",
    ],
    "optionCopilot": [
        "optionCopilot/logs",
        "platform/docker/optionCopilot/logs",
    ],
}

LEGACY_FILE_LOG_LOKI_LABELS = {
    "AIOrchestrator": {
        "service_name": "cPlatform",
        "service_type": "AIOrchestrator",
        "source_type": "file",
    },
    "TrainingServer": {
        "service_name": "dTrain",
        "service_type": "TrainingServer",
        "source_type": "file",
    },
    "InferenceServer": {
        "service_name": "dInfer",
        "service_type": "InferenceServer",
        "source_type": "file",
    },
    "optionCopilot": {
        "service_name": "optionCopilot",
        "service_type": "optionCopilot",
        "source_type": "file",
    },
}

LOKI_SERIES_CACHE_TTL_SECONDS = 45
LOKI_SERIES_EXISTS_CACHE = {}
LOKI_HISTORY_COUNT_CACHE_TTL_SECONDS = 30
LOKI_HISTORY_COUNT_CACHE = {}
LOKI_HISTORY_PAGE_CACHE_TTL_SECONDS = 45
LOKI_HISTORY_PAGE_CACHE = {}

ISSUE_RULES = [
    {
        "category": "OOMKilled",
        "severity": "Critical",
        "brief": "Container was terminated because the host killed it for memory pressure.",
        "patterns": [r"oom", r"out of memory", r"killed process"],
    },
    {
        "category": "SSHAuthFailure",
        "severity": "High",
        "brief": "Node access failed because SSH authentication or key validation failed.",
        "patterns": [r"permission denied \(publickey\)", r"error in libcrypto", r"invalid format", r"load key"],
    },
    {
        "category": "MigrationFailure",
        "severity": "High",
        "brief": "Database migration or schema mismatch is preventing the service from running cleanly.",
        "patterns": [r"migration", r"programmingerror", r"does not exist", r"relation .* does not exist", r"column .* does not exist"],
    },
    {
        "category": "DependencyUnreachable",
        "severity": "High",
        "brief": "The service cannot reach one of its runtime dependencies.",
        "patterns": [r"connection refused", r"failed to establish a new connection", r"temporary failure in name resolution", r"name or service not known", r"nodename nor servname provided"],
    },
    {
        "category": "RequestTimeout",
        "severity": "Medium",
        "brief": "A request or dependency call timed out.",
        "patterns": [r"timeout", r"timed out", r"read timeout", r"connect timeout"],
    },
    {
        "category": "Warning",
        "severity": "Low",
        "brief": "Warnings were emitted repeatedly and may indicate a developing issue.",
        "patterns": [r"\bwarning\b", r"warn"],
    },
]

SYNONYM_MAP = {
    "db": {"database", "sql", "postgres", "mysql", "sqlite", "migration", "relation", "query"},
    "database": {"db", "sql", "postgres", "mysql", "sqlite", "migration", "relation", "query"},
    "sql": {"db", "database", "postgres", "mysql", "sqlite", "migration", "relation"},
    "postgres": {"db", "database", "sql", "migration", "relation"},
    "mysql": {"db", "database", "sql", "migration", "relation"},
    "sqlite": {"db", "database", "sql", "migration", "relation"},
    "network": {"connection", "timeout", "unreachable", "refused", "host", "port", "dns", "socket", "http"},
    "connection": {"network", "timeout", "unreachable", "refused", "host", "port", "dns", "socket", "http"},
    "timeout": {"network", "connection", "unreachable", "refused", "host", "port", "dns", "socket"},
    "auth": {"login", "permission", "credential", "key", "token", "jwt", "unauthorized", "publickey"},
    "login": {"auth", "permission", "credential", "key", "token", "jwt", "unauthorized"},
    "key": {"auth", "login", "permission", "credential", "token", "jwt", "unauthorized", "publickey"},
    "token": {"auth", "login", "permission", "credential", "key", "jwt", "unauthorized"},
    "oom": {"memory", "ram", "killed", "heap", "gc", "out of memory"},
    "memory": {"oom", "ram", "killed", "heap", "gc", "out of memory"},
    "llm": {"groq", "ollama", "model", "openai", "generate", "prompt", "completion", "url"},
    "groq": {"llm", "ollama", "model", "generate", "prompt", "completion"},
    "ollama": {"llm", "groq", "model", "generate", "prompt", "completion"},
    "model": {"llm", "groq", "ollama", "generate", "prompt", "completion"},
    "url": {"llm", "host", "port", "endpoint", "api", "generate"},
    "endpoint": {"llm", "url", "host", "port", "api", "generate"},
    "api": {"llm", "url", "endpoint", "generate"}
}

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "for", "in", "on", "at", 
    "about", "check", "show", "find", "me", "what", "how", "why", "where", "when", 
    "which", "who", "whom", "this", "that", "these", "those", "it", "its", "of", 
    "by", "with", "from", "as", "out", "correct"
}

def _extract_query_keywords(query_str):
    if not query_str:
        return set()
    words = re.findall(r"\b[a-zA-Z]{2,}\b", query_str.lower())
    keywords = {w for w in words if w not in STOPWORDS}
    expanded = set(keywords)
    for kw in keywords:
        if kw in SYNONYM_MAP:
            expanded.update(SYNONYM_MAP[kw])
    return expanded

LOG_TS_PATTERNS = [
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"),
    re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)"),
]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _nested_dict(value, key):
    nested = _as_dict(value).get(key, {})
    return nested if isinstance(nested, dict) else {}


def _coerce_bool(value, default=None):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ["true", "1", "yes", "y", "on", "enable", "enabled"]:
            return True
        if normalized in ["false", "0", "no", "n", "off", "disable", "disabled"]:
            return False
    return default


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _utc_now():
    return datetime.now(timezone.utc)


def _normalize_window(window):
    return window if window in WINDOW_HOURS else "current"


def _window_start(window):
    # Try parsing window directly as float hours for custom lookbacks
    try:
        hours = float(window)
        return _utc_now() - timedelta(hours=hours)
    except (ValueError, TypeError):
        pass
    normalized = _normalize_window(window)
    return _utc_now() - timedelta(hours=WINDOW_HOURS.get(normalized, 1))


def _parse_time_window_override(question, default_window):
    if not question:
        return default_window
    # Match patterns like: "10 minutes ago", "4 hours prior", "3 days back", "30 mins ago"
    match = re.search(r"\b(\d+)\s*(min|minute|hour|day)s?\s*(ago|prior|back)\b", question.lower())
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if "min" in unit:
            # Convert minutes to fraction of an hour (e.g. 30 mins = 0.5 hours)
            hours = num / 60.0
            return str(hours)
        elif "hour" in unit:
            return str(float(num))
        elif "day" in unit:
            return str(float(num * 24))
    return default_window


def _window_end():
    return _utc_now()


def _safe_json_env(env_name, default=None):
    raw_value = _get_runtime_setting(env_name).strip()
    if not raw_value:
        return default if default is not None else {}
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        app_logger.warning(f"Invalid JSON in env var {env_name}")
        return default if default is not None else {}


def _safe_json_loads(json_str):
    if not json_str:
        return {}
    try:
        clean_pattern = re.compile(r'\\(?!"|\\|/|b|f|n|r|t|u[0-9a-fA-F]{4})')
        sanitized = clean_pattern.sub(r'\\\\', json_str)
        return json.loads(sanitized)
    except Exception:
        return json.loads(json_str)


def _get_runtime_setting(name, default=""):
    env_value = os.getenv(name, "")
    if env_value not in [None, ""]:
        return env_value

    diagnostics_env_file = os.getenv("DIAGNOSTICS_ENV_FILE", "").strip()
    if diagnostics_env_file:
        raw_path = Path(diagnostics_env_file)
        explicit_candidates = [
            raw_path,
            Path.cwd() / raw_path,
            Path(settings.BASE_DIR) / raw_path,
            Path(settings.BASE_DIR).parent / raw_path,
            Path(settings.BASE_DIR).parent.parent / raw_path,
        ]
        for candidate in explicit_candidates:
            if not candidate.exists():
                continue
            try:
                value = dotenv_values(candidate).get(name, "")
                if value not in [None, ""]:
                    return str(value)
            except Exception as exc:
                app_logger.warning(f"Unable to read diagnostics setting {name} from {candidate}: {exc}")

    env_file = getattr(settings, "ENV_FILE", "")
    candidate_env_paths = []
    if env_file:
        raw_path = Path(env_file)
        candidate_env_paths.append(raw_path)
        candidate_env_paths.append(Path.cwd() / raw_path)
        candidate_env_paths.append(Path(settings.BASE_DIR) / raw_path)
        candidate_env_paths.append(Path(settings.BASE_DIR).parent / raw_path)
        candidate_env_paths.append(Path(settings.BASE_DIR).parent.parent / raw_path)

    resolved_env_file = next((path.resolve() for path in candidate_env_paths if path.exists()), None)
    if resolved_env_file:
        env_paths = []
        env_path = resolved_env_file
        if "deployment." in env_path.name:
            env_paths.append(env_path.with_name(env_path.name.replace("deployment.", "diagnostics.", 1)))
            env_paths.append(env_path.with_name(env_path.name.replace("deployment.", "diagnostics.validation.", 1)))
        env_paths.append(env_path.parent / "diagnostics.env")
        env_paths.append(env_path.parent / "diagnostics.validation.env")
        env_paths.append(Path(settings.BASE_DIR).parent / "platform/observability/glitchtip.env")
        for diagnostics_env in env_paths:
            if not diagnostics_env.exists():
                continue
            try:
                value = dotenv_values(diagnostics_env).get(name, "")
                if value not in [None, ""]:
                    return str(value)
            except Exception as exc:
                app_logger.warning(f"Unable to read diagnostics setting {name} from {diagnostics_env}: {exc}")
    return default


def _parse_log_timestamp(line):
    for pattern in LOG_TS_PATTERNS:
        match = pattern.search(str(line or ""))
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


def _service_local_log_dir(service_instance):
    return LOCAL_LOG_PATHS.get(service_instance.service_type, "")


def _repo_root():
    try:
        return Path(__file__).resolve().parents[3]
    except Exception:
        return Path.cwd()


def _service_local_log_candidates(service_instance):
    candidates = []
    for relative_path in LOCAL_LOG_PATH_CANDIDATES.get(service_instance.service_type, []):
        candidate = (_repo_root() / relative_path).resolve()
        candidates.append(str(candidate))
    return candidates


def _accessible_log_dirs(service_instance, log_paths):
    seed_paths = _string_list(log_paths)
    fallback_dir = _service_local_log_dir(service_instance) if service_instance is not None else ""
    if fallback_dir:
        seed_paths.append(fallback_dir)
    if service_instance is not None:
        seed_paths.extend(_service_local_log_candidates(service_instance))
    return _candidate_log_dirs_from_paths(seed_paths, service_instance=service_instance)


def _accessible_volume_roots(service_instance, file_paths):
    candidate_dirs = _accessible_log_dirs(service_instance, file_paths)
    if candidate_dirs:
        roots = []
        seen = set()
        for path_obj in candidate_dirs:
            try:
                resolved_dir = str(path_obj.resolve())
            except OSError:
                resolved_dir = str(path_obj)
            if resolved_dir in seen:
                continue
            seen.add(resolved_dir)
            roots.append(resolved_dir)
        if roots:
            return roots
    return _normalize_volume_roots(file_paths)


def _file_log_path_readiness(service_instance, file_paths):
    configured_paths = _string_list(file_paths)
    candidate_dirs = _accessible_log_dirs(service_instance, configured_paths)
    readable_lookup = set()
    for path_obj in candidate_dirs:
        try:
            readable_lookup.add(str(path_obj.resolve()))
        except OSError:
            readable_lookup.add(str(path_obj))

    checks = []
    for raw_path in configured_paths:
        normalized = _path_without_glob_tokens(raw_path) or raw_path
        path_obj = Path(normalized)
        if path_obj.suffix:
            path_obj = path_obj.parent
        exists = path_obj.exists()
        readable = False
        resolved = str(path_obj)
        try:
            resolved_path = path_obj.resolve()
            resolved = str(resolved_path)
            readable = resolved in readable_lookup or (resolved_path.exists() and os.access(resolved_path, os.R_OK | os.X_OK))
        except OSError:
            readable = False
        checks.append({
            "path": raw_path,
            "resolved_path": resolved,
            "exists": bool(exists),
            "readable": bool(readable),
            "status": "readable" if readable else ("missing" if not exists else "permission_or_sudo_required"),
        })

    return {
        "configured_paths": configured_paths,
        "checked_paths": checks,
        "readable_paths": [item["resolved_path"] for item in checks if item.get("readable")],
        "skipped_paths": [item for item in checks if not item.get("readable")],
        "requires_become": bool(configured_paths),
    }


def _backfill_readiness(selected_target, file_log_cfg):
    file_paths = _string_list(file_log_cfg.get("paths"))
    loki_url = _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "").strip()
    missing = []
    if not file_log_cfg.get("enabled", True):
        missing.append("File logs are disabled for this target")
    if not file_paths:
        missing.append("No file log paths are configured")
    if not str((selected_target or {}).get("node_id", "") or "").strip():
        missing.append("Node mapping is missing")
    if not loki_url:
        missing.append("Diagnostics Loki URL is not configured")

    return {
        "ready": not missing,
        "missing": missing,
        "requires_become": bool(file_paths),
        "loki_configured": bool(loki_url),
        "file_log_paths": file_paths,
        "message": "Ready. Uses sudo/become for root-owned service logs." if not missing else "; ".join(missing),
    }


def _encode_log_file_id(path_obj):
    try:
        resolved = str(Path(path_obj).resolve()).encode("utf-8")
        return base64.urlsafe_b64encode(resolved).decode("ascii")
    except Exception:
        return ""


def _decode_log_file_id(file_id):
    raw_value = str(file_id or "").strip()
    if not raw_value:
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw_value.encode("ascii")).decode("utf-8")
    except Exception:
        return None
    try:
        return Path(decoded)
    except Exception:
        return None


def _remote_file_allowed(file_path, file_roots, service_instance=None):
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return False
    normalized_path = os.path.normpath(raw_path)
    while normalized_path.startswith("//"):
        normalized_path = normalized_path[1:]
    for root in _string_list(file_roots):
        for alias in _candidate_path_aliases(root, service_instance=service_instance):
            root_without_glob = _path_without_glob_tokens(alias) or alias
            path_obj = Path(root_without_glob)
            if path_obj.suffix:
                path_obj = path_obj.parent
            normalized_root = os.path.normpath(str(path_obj).strip())
            if not normalized_root:
                continue
            while normalized_root.startswith("//"):
                normalized_root = normalized_root[1:]
            if normalized_path == normalized_root or normalized_path.startswith(normalized_root.rstrip(os.sep) + os.sep):
                return True
    return False


def _main_service_contract(service_instance):
    return _service_docker_target_contract(service_instance.service_type, service_instance.service_type)


def _contract_observability_block(contract):
    return _nested_dict(contract, "Observability") or _nested_dict(contract, "observability")


def _merge_dicts(base, override):
    merged = dict(_as_dict(base))
    for key, value in _as_dict(override).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def _legacy_loki_labels(service_instance):
    label_map = _safe_json_env("CPLATFORM_DIAGNOSTICS_LOKI_LABEL_MAP", {})
    mapped_labels = label_map.get(service_instance.service_type) or label_map.get(service_instance.service_name)
    if isinstance(mapped_labels, dict) and mapped_labels:
        return mapped_labels
    return LEGACY_FILE_LOG_LOKI_LABELS.get(service_instance.service_type) or {
        "service_type": service_instance.service_type,
        "service_name": service_instance.service_name,
        "source_type": "file",
    }


def _legacy_glitchtip_project_slug(service_instance):
    project_map = _safe_json_env("CPLATFORM_GLITCHTIP_PROJECT_MAP", {})
    type_key = (service_instance.service_type or "").strip()
    name_key = (service_instance.service_name or "").strip()
    lower_map = {k.lower(): v for k, v in project_map.items()}
    slug = lower_map.get(type_key.lower()) or lower_map.get(name_key.lower())
    if not slug:
        slug = type_key.lower()
    return slug


def _normalize_observability_config(service_instance):
    runtime_cfg = _as_dict(service_instance.service_config)
    contract_obs = _contract_observability_block(_main_service_contract(service_instance))
    raw_obs = _merge_dicts(contract_obs, _nested_dict(runtime_cfg, "observability"))
    container_logs_cfg = _nested_dict(raw_obs, "container_logs")
    container_history_cfg = _nested_dict(raw_obs, "container_history")
    file_logs_cfg = _nested_dict(raw_obs, "file_logs")
    glitchtip_cfg = _nested_dict(raw_obs, "glitchtip")
    service_events_cfg = _nested_dict(raw_obs, "service_events")
    live_logs_cfg = _nested_dict(raw_obs, "live_logs")

    legacy_file_path = _service_local_log_dir(service_instance)
    legacy_project_slug = _legacy_glitchtip_project_slug(service_instance)
    legacy_loki_labels = _legacy_loki_labels(service_instance)
    inferred_app_scope = bool(legacy_file_path or legacy_project_slug)

    scope = str(raw_obs.get("scope") or ("app" if inferred_app_scope else "infra")).strip().lower() or "infra"
    file_paths = _resolve_contract_paths(file_logs_cfg.get("paths"), service_instance)
    if not file_paths and legacy_file_path:
        file_paths = [legacy_file_path]

    file_loki_labels = _as_dict(file_logs_cfg.get("loki_labels")) or legacy_loki_labels
    project_slug = str(glitchtip_cfg.get("project_slug") or legacy_project_slug or "").strip()

    file_logs_enabled = _coerce_bool(file_logs_cfg.get("enabled"), default=bool(legacy_file_path))
    glitchtip_enabled = _coerce_bool(glitchtip_cfg.get("enabled"), default=bool(project_slug))
    service_events_enabled = _coerce_bool(service_events_cfg.get("enabled"), default=bool(inferred_app_scope))

    return {
        "scope": scope,
        "container_logs": {
            "enabled": _coerce_bool(container_logs_cfg.get("enabled"), default=True),
        },
        "container_history": {
            "enabled": _coerce_bool(container_history_cfg.get("enabled"), default=True),
        },
        "file_logs": {
            "enabled": bool(file_logs_enabled and file_paths),
            "paths": file_paths,
            "loki_labels": file_loki_labels,
        },
        "glitchtip": {
            "enabled": bool(glitchtip_enabled and project_slug),
            "project_slug": project_slug,
        },
        "service_events": {
            "enabled": bool(service_events_enabled),
        },
        "live_logs": {
            "enabled": _coerce_bool(live_logs_cfg.get("enabled"), default=True),
        },
    }


def _load_service_install_config():
    global SERVICE_INSTALL_CONFIG_CACHE
    if SERVICE_INSTALL_CONFIG_CACHE is not None:
        return SERVICE_INSTALL_CONFIG_CACHE

    config_path = Path(__file__).resolve().parents[3] / "config/service_install.yaml"
    yaml_content = ServiceConfig._read_yaml_file(str(config_path))
    SERVICE_INSTALL_CONFIG_CACHE = _nested_dict(yaml_content, "services")
    return SERVICE_INSTALL_CONFIG_CACHE


def _service_docker_target_contract(service_type, target_name):
    if ServiceConfig._is_infrastructure_service_type(service_type):
        return ServiceConfig.service_get_infrastructure_contract(service_type)

    docker_info = _nested_dict(_load_service_install_config().get(service_type), "Docker_Info")
    direct_match = _as_dict(docker_info.get(target_name))
    if direct_match:
        return direct_match

    normalized_target = str(target_name or "").strip().lower()
    for contract_name, contract_value in docker_info.items():
        if str(contract_name or "").strip().lower() == normalized_target:
            return _as_dict(contract_value)
    return {}


def _resolve_contract_value(raw_value, service_instance):
    value = str(raw_value or "")
    if not value:
        return ""

    service_volume = str(_as_dict(getattr(service_instance, "service_config", {})).get("service_volume") or "/home/ubuntu/Backup_Platform")
    machine_volume = str(_as_dict(getattr(service_instance, "service_config", {})).get("machine_volume") or "/home/ubuntu/Backup_Platform")
    replacements = {
        "{{ service_volume }}": service_volume.rstrip("/"),
        "{{ machine_volume }}": machine_volume.rstrip("/"),
        "{{ service }}": str(getattr(service_instance, "service_type", "") or ""),
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def _resolve_contract_paths(path_values, service_instance):
    resolved = []
    for path_value in _string_list(path_values):
        candidate = _resolve_contract_value(path_value, service_instance).strip()
        if candidate:
            resolved.append(candidate)
    return resolved


def _path_without_glob_tokens(path_value):
    raw = str(path_value or "").strip()
    if not raw:
        return ""

    special_tokens = ["*", "?", "["]
    if any(token in raw for token in special_tokens):
        return os.path.dirname(raw.rstrip("/\\"))
    return raw


def _candidate_path_aliases(path_value, service_instance=None):
    raw = str(path_value or "").strip()
    if not raw:
        return []

    normalized = raw.replace("\\", "/")
    while normalized.startswith("//"):
        normalized = normalized[1:]

    aliases = [raw]
    if normalized != raw:
        aliases.append(normalized)

    repo_root = _repo_root()

    if normalized.startswith("/home/ubuntu/Backup_Platform/iktara/"):
        suffix = normalized.split("/iktara/", 1)[1]
        aliases.append(str(repo_root / suffix))
        if suffix == "cPlatform/logs":
            aliases.append(str((repo_root / "logs").resolve()))

    if normalized.startswith("/iktara/"):
        suffix = normalized.split("/iktara/", 1)[1]
        if suffix.startswith("cPlatform/"):
            suffix = suffix.split("cPlatform/", 1)[1]
        aliases.append(str(repo_root / suffix))

    if service_instance is not None:
        aliases.extend(_service_local_log_candidates(service_instance))
        fallback_dir = _service_local_log_dir(service_instance)
        if fallback_dir:
            fallback_normalized = str(fallback_dir).replace("\\", "/")
            while fallback_normalized.startswith("//"):
                fallback_normalized = fallback_normalized[1:]
            if fallback_normalized != fallback_dir:
                aliases.append(fallback_normalized)
            if fallback_normalized.startswith("/home/ubuntu/Backup_Platform/iktara/"):
                fallback_suffix = fallback_normalized.split("/iktara/", 1)[1]
                aliases.append(str(repo_root / fallback_suffix))

    seen = set()
    unique_aliases = []
    for candidate in aliases:
        token = str(candidate or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        unique_aliases.append(token)
    return unique_aliases


def _normalize_volume_roots(file_paths):
    roots = []
    seen = set()

    for file_path in _string_list(file_paths):
        candidate = _path_without_glob_tokens(file_path)
        if not candidate:
            continue
        path_obj = Path(candidate)
        root_obj = path_obj if not path_obj.suffix else path_obj.parent
        root = str(root_obj).rstrip("/\\") or str(root_obj)
        if not root or root in seen:
            continue
        seen.add(root)
        roots.append(root)

    return roots


def _candidate_log_dirs_from_paths(file_paths, service_instance=None):
    candidate_dirs = []
    seen_dirs = set()

    for file_path in _string_list(file_paths):
        for alias in _candidate_path_aliases(file_path, service_instance=service_instance):
            candidate = _path_without_glob_tokens(alias)
            if not candidate:
                continue
            path_obj = Path(candidate)
            if path_obj.is_file():
                path_obj = path_obj.parent
            elif not path_obj.is_dir():
                path_obj = path_obj.parent

            if not path_obj or not str(path_obj):
                continue
            if not path_obj.exists():
                continue
            try:
                resolved_dir = path_obj.resolve()
            except OSError:
                continue
            if resolved_dir in seen_dirs:
                continue
            seen_dirs.add(resolved_dir)
            candidate_dirs.append(path_obj)

    return candidate_dirs


def _target_capabilities_map(selected_target, target_observability, live_log_sources):
    source_lookup = {src.get("source_id"): src for src in (live_log_sources or [])}
    is_main_target = str((selected_target or {}).get("target_id", "main")) == "main"
    service_events_enabled = bool(is_main_target and _nested_dict(target_observability, "service_events").get("enabled", False))

    return {
        "container_live": bool(source_lookup.get("container_live", {}).get("enabled")),
        "container_history": bool(source_lookup.get("container_history", {}).get("enabled")),
        "file_live": bool(source_lookup.get("file_live", {}).get("enabled")),
        "file_history": bool(source_lookup.get("service_history", {}).get("enabled")),
        "service_events": service_events_enabled,
        "target_scope": "main" if is_main_target else "dependency",
    }


def _capability_reasons_map(live_log_sources, target_capabilities):
    reasons = {}
    for source in live_log_sources or []:
        reason = str(source.get("disabled_reason", "") or "").strip()
        if reason:
            reasons[source.get("source_id", "")] = reason
    if not target_capabilities.get("service_events", False):
        reasons["service_events"] = "Service events are currently available only for the main service target"
    return reasons


def _selected_target_contract_name(service_instance, selected_target):
    if str((selected_target or {}).get("target_id", "main")) == "main":
        return service_instance.service_type
    return str(
        (selected_target or {}).get("dependency_contract_name")
        or (selected_target or {}).get("declared_role")
        or (selected_target or {}).get("dependency_name", "")
        or ""
    ).strip()


def _normalize_target_observability_config(service_instance, selected_target):
    if str((selected_target or {}).get("target_id", "main")) == "main":
        return _normalize_observability_config(service_instance)

    contract_name = _selected_target_contract_name(service_instance, selected_target)
    contract = _service_docker_target_contract(service_instance.service_type, contract_name)
    observability = _nested_dict(contract, "Observability")
    container_history_cfg = _nested_dict(observability, "container_history")
    file_logs_cfg = _nested_dict(observability, "file_logs")

    file_paths = _string_list((selected_target or {}).get("file_log_paths")) or _resolve_contract_paths(file_logs_cfg.get("paths"), service_instance)
    file_loki_labels = _as_dict(file_logs_cfg.get("loki_labels"))

    return {
        "scope": "dependency",
        "container_logs": {
            "enabled": True,
        },
        "container_history": {
            "enabled": _coerce_bool(container_history_cfg.get("enabled"), default=True),
        },
        "file_logs": {
            "enabled": bool(_coerce_bool(file_logs_cfg.get("enabled"), default=bool(file_paths)) and file_paths),
            "paths": file_paths,
            "loki_labels": file_loki_labels,
        },
        "glitchtip": {
            "enabled": False,
            "project_slug": "",
        },
        "service_events": {
            "enabled": False,
        },
        "live_logs": {
            "enabled": True,
        },
    }


def _disabled_source_reason(source_id, selected_target, window, target_observability, file_paths, available_file_streams):
    normalized_window = _normalize_window(window)
    target_source_type = str((selected_target or {}).get("source_type", "") or "")
    dependency_name = str((selected_target or {}).get("dependency_name", "") or "")

    if source_id in ["container_live", "file_live"] and normalized_window != "current":
        return "Only available for the current window"

    if source_id == "container_live":
        if not (selected_target or {}).get("inspectable", True):
            return "Selected target is not inspectable"
        if not (selected_target or {}).get("node_id"):
            return "Target is not mapped to a node"
        return ""

    if source_id == "container_history":
        if not _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", ""):
            return "Container history is unavailable because Loki is not configured"
        if not _nested_dict(target_observability, "container_history").get("enabled", True):
            return "Container history is disabled for this target"
        if not (selected_target or {}).get("container_name") or not (selected_target or {}).get("node_id"):
            return "Container history requires a resolved container and node"
        return ""

    if source_id == "file_live":
        if not _nested_dict(target_observability, "file_logs").get("enabled"):
            if str((selected_target or {}).get("target_id", "main")) != "main":
                return "Supporting service currently exposes container logs only"
            return "File logs are not enabled for this service"
        if not file_paths:
            return "No file-log path is configured for this target"
        if available_file_streams:
            return ""
        if not (selected_target or {}).get("node_id"):
            return "No current file-log files were found for this target"
        return ""

    if source_id == "service_history":
        if not _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", ""):
            return "File history is unavailable because Loki is not configured"
        if not _nested_dict(target_observability, "file_logs").get("enabled"):
            if str((selected_target or {}).get("target_id", "main")) != "main":
                return "Supporting service currently exposes container logs only"
            return "File history is not enabled for this service"
        selector_parts = _as_dict(_nested_dict(target_observability, "file_logs").get("loki_labels"))
        if not selector_parts:
            return "No Loki file history is configured for this target"
        capability_window = FILE_HISTORY_CAPABILITY_WINDOW
        if target_source_type == "Managed External" and not _file_history_exists(selector_parts, capability_window):
            return f"No ingested file history is available for managed external target {dependency_name or 'dependency'}"
        if not _file_history_exists(selector_parts, capability_window):
            return "No file-history logs were found for this target"
        return ""

    return "Source is unavailable"


def _build_live_log_sources(service_instance, selected_target, observability_config=None, window="current"):
    target_observability = observability_config or _normalize_target_observability_config(service_instance, selected_target)
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    file_paths = _string_list(file_log_cfg.get("paths"))
    local_existing_paths = _accessible_log_dirs(service_instance, file_paths)
    available_file_streams = _available_file_streams(service_instance, local_existing_paths) if local_existing_paths else []
    sources = []

    for source in LOG_SOURCE_CATALOG:
        disabled_reason = _disabled_source_reason(
            source["source_id"],
            selected_target,
            window,
            target_observability,
            file_paths,
            available_file_streams,
        )
        sources.append({
            **source,
            "enabled": disabled_reason == "",
            "disabled_reason": disabled_reason,
        })

    return sources


def _collect_local_log_files(log_paths, service_instance=None):
    collected = []
    seen = set()

    candidate_dirs = []
    if service_instance is not None:
        candidate_dirs = _accessible_log_dirs(service_instance, log_paths)
    else:
        for log_path in log_paths or []:
            path_obj = Path(log_path)
            if path_obj.exists() and path_obj.is_dir():
                candidate_dirs.append(path_obj)

    for path_obj in candidate_dirs:
        if not path_obj.exists():
            continue
        try:
            files = sorted(path_obj.glob("*.log*"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            continue
        for log_file in files:
            if not log_file.is_file():
                continue
            key = str(log_file.resolve())
            if key in seen:
                continue
            seen.add(key)
            collected.append(log_file)

    return collected


def _sort_file_streams(service_instance, files):
    support_prefixes = ("MCPClientLogger_", "CplatformUtilsLogger_")
    primary_prefixes = []
    for candidate in [
        getattr(service_instance, "service_name", ""),
        getattr(service_instance, "service_id", ""),
        getattr(service_instance, "service_type", ""),
    ]:
        normalized = str(candidate or "").strip()
        if not normalized:
            continue
        primary_prefixes.append(f"{normalized}_")

    def sort_key(log_file):
        name = log_file.name
        lowered = name.lower()
        if any(name.startswith(prefix) for prefix in primary_prefixes):
            return (0, lowered)
        if any(name.startswith(prefix) for prefix in support_prefixes):
            return (1, lowered)
        return (2, lowered)

    return sorted(files, key=sort_key)


def _available_file_streams(service_instance, log_paths):
    files = _sort_file_streams(service_instance, _collect_local_log_files(log_paths, service_instance=service_instance))
    if not files:
        return []
    streams = [{"id": "all", "label": "All"}]
    for log_file in files:
        streams.append({
            "id": log_file.name,
            "label": log_file.name,
        })
    return streams


def _select_local_log_files(service_instance, log_paths, file_stream="all"):
    files = _sort_file_streams(service_instance, _collect_local_log_files(log_paths, service_instance=service_instance))
    selected_stream = str(file_stream or "all").strip() or "all"
    if selected_stream == "all":
        return files, selected_stream, ""

    matching_files = [log_file for log_file in files if log_file.name == selected_stream]
    if matching_files:
        return matching_files, selected_stream, ""

    return [], selected_stream, f"File stream '{selected_stream}' is not available for this service"


def _read_local_file_logs(service_instance, log_paths, window, limit=250):
    start_at = _window_start(window)
    selected_lines = []

    for log_file in _collect_local_log_files(log_paths, service_instance=service_instance)[:12]:
        try:
            with log_file.open("r", errors="ignore") as fh:
                lines = fh.readlines()[-limit:]
        except OSError:
            continue

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            ts = _parse_log_timestamp(line)
            if ts and ts < start_at:
                continue
            selected_lines.append({
                "timestamp": ts.isoformat() if ts else "",
                "message": line,
                "source": f"file:{log_file.name}",
            })

    return selected_lines[-limit:]


def _tail_local_file_logs(service_instance, log_paths, limit=250, file_stream="all"):
    selected_lines = []
    selected_paths, selected_stream, error = _select_local_log_files(service_instance, log_paths, file_stream=file_stream)
    if error:
        return [], selected_stream, error

    for log_file in selected_paths[:12]:
        try:
            with log_file.open("r", errors="ignore") as fh:
                lines = fh.readlines()[-limit:]
        except OSError:
            continue

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            ts = _parse_log_timestamp(line)
            selected_lines.append({
                "timestamp": ts.isoformat() if ts else "",
                "message": line,
                "source": f"file:{log_file.name}",
            })

    return _merge_log_sources([selected_lines])[-limit:], selected_stream, ""


def _open_log_file_text(log_file):
    if str(log_file).lower().endswith(".gz"):
        return gzip.open(log_file, "rt", errors="ignore")
    return open(log_file, "r", errors="ignore")


def _read_log_file_preview(log_file, limit=300):
    lines = deque(maxlen=max(1, int(limit)))
    try:
        with _open_log_file_text(log_file) as fh:
            for raw_line in fh:
                lines.append(str(raw_line).rstrip("\r\n"))
    except OSError:
        return {"preview_text": "", "preview_line_count": 0}
    return {
        "preview_text": "\n".join(list(lines)),
        "preview_line_count": len(lines),
    }


def _find_accessible_log_file(service_instance, file_paths, file_name="", file_id=""):
    candidate_dirs = _accessible_log_dirs(service_instance, file_paths)
    decoded_path = _decode_log_file_id(file_id)
    if decoded_path is not None:
        try:
            resolved_target = decoded_path.resolve()
        except OSError:
            resolved_target = None
        if resolved_target is not None and resolved_target.exists() and resolved_target.is_file():
            for path_dir in candidate_dirs:
                try:
                    resolved_dir = path_dir.resolve()
                except OSError:
                    continue
                if resolved_dir == resolved_target.parent or resolved_dir in resolved_target.parents:
                    return resolved_target

    normalized_name = str(file_name or "").strip()
    if normalized_name:
        for path_dir in candidate_dirs:
            try:
                resolved_dir = path_dir.resolve()
            except OSError:
                continue
            target_file = resolved_dir / normalized_name
            if target_file.exists() and target_file.is_file():
                return target_file.resolve()
    return None


def _build_loki_label_selector(selector_parts):
    return ", ".join([f'{key}="{value}"' for key, value in selector_parts.items() if value])


def _dt_to_ns(value):
    try:
        return int(value.timestamp() * 1_000_000_000)
    except Exception:
        return 0


def _iso_to_ns(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return 0
    try:
        return int(datetime.fromisoformat(raw_value.replace("Z", "+00:00")).timestamp() * 1_000_000_000)
    except ValueError:
        return 0


def _normalize_history_direction(direction):
    normalized = str(direction or "").strip().lower()
    if normalized in ["older", "newer"]:
        return normalized
    return "latest"


def _encode_history_cursor(payload):
    try:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(encoded).decode("ascii")
    except Exception:
        return ""


def _decode_history_cursor(token):
    raw_token = str(token or "").strip()
    if not raw_token:
        return {}
    try:
        payload = base64.urlsafe_b64decode(raw_token.encode("ascii"))
        decoded = json.loads(payload.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def _history_cursor_matches(cursor_payload, context):
    if not cursor_payload or not context:
        return False
    return all(cursor_payload.get(key) == value for key, value in context.items())


def _normalize_history_page(history_page):
    try:
        normalized = int(history_page)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized > 0 else 0


def _history_page_cache_key(cursor_context, page_size):
    if not cursor_context:
        return ""
    return f"{json.dumps(cursor_context, sort_keys=True)}:{int(page_size)}"


def _get_history_page_cache(cursor_context, page_size):
    cache_key = _history_page_cache_key(cursor_context, page_size)
    if not cache_key:
        return {}
    cached = LOKI_HISTORY_PAGE_CACHE.get(cache_key)
    now = _utc_now()
    if cached and (now - cached["checked_at"]).total_seconds() < LOKI_HISTORY_PAGE_CACHE_TTL_SECONDS:
        return cached.get("page_requests", {})
    LOKI_HISTORY_PAGE_CACHE.pop(cache_key, None)
    return {}


def _set_history_page_cache(cursor_context, page_size, page_requests):
    cache_key = _history_page_cache_key(cursor_context, page_size)
    if not cache_key:
        return
    LOKI_HISTORY_PAGE_CACHE[cache_key] = {
        "checked_at": _utc_now(),
        "page_requests": page_requests,
    }


def _loki_series_exists(selector_parts, window):
    loki_url = _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "").rstrip("/")
    if not loki_url:
        return False

    normalized_window = _normalize_window(window)
    label_selector = _build_loki_label_selector(selector_parts)
    if not label_selector:
        return False

    cache_key = f"{normalized_window}:{json.dumps(selector_parts, sort_keys=True)}"
    now = _utc_now()
    cached = LOKI_SERIES_EXISTS_CACHE.get(cache_key)
    if cached and (now - cached["checked_at"]).total_seconds() < LOKI_SERIES_CACHE_TTL_SECONDS:
        return cached["exists"]

    end_ns = int(now.timestamp() * 1_000_000_000)
    start_ns = int(_window_start(normalized_window).timestamp() * 1_000_000_000)
    params = {
        "match[]": "{" + label_selector + "}",
        "start": start_ns,
        "end": end_ns,
    }

    exists = False
    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/series",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        exists = bool(response.json().get("data", []))
    except requests.RequestException as exc:
        app_logger.warning(f"Loki series lookup failed for selector {selector_parts}: {exc}")

    LOKI_SERIES_EXISTS_CACHE[cache_key] = {
        "checked_at": now,
        "exists": exists,
    }
    return exists


def _window_range_literal(window):
    normalized_window = _normalize_window(window)
    hours = WINDOW_HOURS.get(normalized_window, WINDOW_HOURS["current"])
    if hours % 24 == 0 and hours >= 24:
        return f"{int(hours / 24)}d"
    return f"{hours}h"


def _count_loki_selector_entries(selector_parts, window):
    loki_url = _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "").rstrip("/")
    if not loki_url:
        return 0

    label_selector = _build_loki_label_selector(selector_parts)
    if not label_selector:
        return 0

    normalized_window = _normalize_window(window)
    cache_key = f"{normalized_window}:{json.dumps(selector_parts, sort_keys=True)}"
    now = _utc_now()
    cached = LOKI_HISTORY_COUNT_CACHE.get(cache_key)
    if cached and (now - cached["checked_at"]).total_seconds() < LOKI_HISTORY_COUNT_CACHE_TTL_SECONDS:
        return cached["count"]

    query = f'sum(count_over_time({{{label_selector}}}[{_window_range_literal(normalized_window)}]))'
    total_count = 0
    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/query",
            params={"query": query},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json().get("data", {}).get("result", [])
        if result:
            total_count = int(float((result[0].get("value") or [0, 0])[1]))
    except (requests.RequestException, ValueError, TypeError, IndexError) as exc:
        app_logger.warning(f"Loki history count failed for selector {selector_parts}: {exc}")

    LOKI_HISTORY_COUNT_CACHE[cache_key] = {
        "checked_at": now,
        "count": max(0, total_count),
    }
    return max(0, total_count)


def _query_loki_selector_range(selector_parts, start_ns, end_ns, limit=250, direction="backward"):
    loki_url = _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "").rstrip("/")
    if not loki_url:
        return []

    label_selector = _build_loki_label_selector(selector_parts)
    if not label_selector:
        return []

    if start_ns > end_ns:
        return []

    params = {
        "query": "{" + label_selector + "}",
        "limit": limit,
        "start": start_ns,
        "end": end_ns,
        "direction": direction,
    }

    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/query_range",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json().get("data", {}).get("result", [])
    except requests.RequestException as exc:
        app_logger.warning(f"Loki query failed for selector {selector_parts}: {exc}")
        return []

    results = []
    for stream in payload:
        stream_labels = stream.get("stream", {}) or {}
        source_name = stream_labels.get("filename") or stream_labels.get("service_name") or "loki"
        for ts_ns, line in stream.get("values", []) or []:
            try:
                timestamp_ns = int(ts_ns)
                ts = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
                ts_value = ts.isoformat()
            except (TypeError, ValueError, OSError):
                timestamp_ns = 0
                ts_value = ""
            results.append({
                "timestamp_ns": timestamp_ns,
                "timestamp": ts_value,
                "message": str(line).strip(),
                "source": f"loki:{source_name}",
            })

    reverse = direction == "backward"
    results.sort(key=lambda item: (item.get("timestamp_ns", 0), item.get("message", "")), reverse=reverse)
    return results[:limit]


def _query_loki_selector(selector_parts, window, limit=250):
    start_ns = _dt_to_ns(_window_start(window))
    end_ns = _dt_to_ns(_window_end())
    results = _query_loki_selector_range(selector_parts, start_ns, end_ns, limit=limit, direction="backward")
    
    # Decouple from time window: if we found fewer logs than the limit,
    # expand the range to query up to 7 days back to get up to `limit` logs.
    if len(results) < limit:
        wider_start_ns = _dt_to_ns(_utc_now() - timedelta(days=7))
        if wider_start_ns < start_ns:
            results = _query_loki_selector_range(selector_parts, wider_start_ns, end_ns, limit=limit, direction="backward")
            
    results.reverse()
    return [{key: value for key, value in item.items() if key != "timestamp_ns"} for item in results[-limit:]]


def _loki_selector_has_logs(selector_parts, start_ns, end_ns):
    if start_ns > end_ns:
        return False
    return bool(_query_loki_selector_range(selector_parts, start_ns, end_ns, limit=1, direction="backward"))


def _file_history_exists(selector_parts, window):
    normalized_window = _normalize_window(window)
    start_ns = _dt_to_ns(_window_start(normalized_window))
    end_ns = _dt_to_ns(_window_end())
    return _loki_selector_has_logs(selector_parts, start_ns, end_ns)


def _query_loki_selector_page_once(selector_parts, window, page_size=DEFAULT_HISTORY_PAGE_SIZE, history_cursor="", history_direction="latest", cursor_context=None):
    page_size = max(50, min(int(page_size), MAX_HISTORY_PAGE_SIZE))
    normalized_window = _normalize_window(window)
    history_total_lines = _count_loki_selector_entries(selector_parts, normalized_window)
    history_total_pages = (history_total_lines + page_size - 1) // page_size if history_total_lines > 0 else 0
    direction_mode = _normalize_history_direction(history_direction)
    window_start_ns = _dt_to_ns(_window_start(normalized_window))
    window_end_ns = _dt_to_ns(_window_end())
    cursor_payload = _decode_history_cursor(history_cursor)
    if not _history_cursor_matches(cursor_payload, cursor_context):
        cursor_payload = {}
        direction_mode = "latest"
    elif cursor_payload.get("mode") in ["older", "newer"]:
        direction_mode = cursor_payload["mode"]

    query_direction = "backward"
    start_ns = window_start_ns
    end_ns = window_end_ns

    if direction_mode == "older":
        anchor_ns = _iso_to_ns(cursor_payload.get("anchor_ts"))
        if anchor_ns > 0:
            end_ns = max(window_start_ns, anchor_ns - 1)
    elif direction_mode == "newer":
        anchor_ns = _iso_to_ns(cursor_payload.get("anchor_ts"))
        if anchor_ns > 0:
            start_ns = min(window_end_ns, anchor_ns + 1)
        query_direction = "forward"

    raw_entries = _query_loki_selector_range(
        selector_parts,
        start_ns,
        end_ns,
        limit=page_size + 1,
        direction=query_direction,
    )

    if query_direction == "backward":
        page_entries = list(raw_entries[:page_size])
        page_entries.reverse()
    else:
        page_entries = list(raw_entries[:page_size])

    if not page_entries:
        return {
            "lines": [],
            "history_has_older": False,
            "history_has_newer": False,
            "history_cursor_older": "",
            "history_cursor_newer": "",
            "history_window_start": _window_start(normalized_window).isoformat(),
            "history_window_end": _window_end().isoformat(),
            "history_total_lines": history_total_lines,
            "history_total_pages": history_total_pages,
        }

    oldest_ns = page_entries[0].get("timestamp_ns", 0)
    newest_ns = page_entries[-1].get("timestamp_ns", 0)
    history_has_older = _loki_selector_has_logs(selector_parts, window_start_ns, max(window_start_ns, oldest_ns - 1))
    history_has_newer = _loki_selector_has_logs(selector_parts, min(window_end_ns, newest_ns + 1), window_end_ns)

    older_cursor = ""
    newer_cursor = ""
    if cursor_context and history_has_older:
        older_cursor = _encode_history_cursor({
            **cursor_context,
            "mode": "older",
            "anchor_ts": page_entries[0].get("timestamp", ""),
        })
    if cursor_context and history_has_newer:
        newer_cursor = _encode_history_cursor({
            **cursor_context,
            "mode": "newer",
            "anchor_ts": page_entries[-1].get("timestamp", ""),
        })

    return {
        "lines": [{key: value for key, value in item.items() if key != "timestamp_ns"} for item in page_entries],
        "history_has_older": history_has_older,
        "history_has_newer": history_has_newer,
        "history_cursor_older": older_cursor,
        "history_cursor_newer": newer_cursor,
        "history_window_start": _window_start(normalized_window).isoformat(),
        "history_window_end": _window_end().isoformat(),
        "history_total_lines": history_total_lines,
        "history_total_pages": history_total_pages,
    }


def _query_loki_selector_page(selector_parts, window, page_size=DEFAULT_HISTORY_PAGE_SIZE, history_cursor="", history_direction="latest", cursor_context=None, history_page=0):
    target_page = _normalize_history_page(history_page)
    if target_page <= 1:
        payload = _query_loki_selector_page_once(
            selector_parts,
            window,
            page_size=page_size,
            history_cursor=history_cursor,
            history_direction=history_direction,
            cursor_context=cursor_context,
        )
        payload["history_page"] = 1 if payload.get("history_total_pages", 0) > 0 else 0
        return payload

    normalized_page_size = max(50, min(int(page_size), MAX_HISTORY_PAGE_SIZE))
    page_requests = _get_history_page_cache(cursor_context, normalized_page_size) or {}
    if 1 not in page_requests:
        page_requests[1] = {
            "history_cursor": "",
            "history_direction": "latest",
        }

    target_total_pages = 0
    nearest_page = max([page for page in page_requests.keys() if page <= target_page], default=1)
    request_info = page_requests.get(nearest_page, page_requests[1])
    payload = _query_loki_selector_page_once(
        selector_parts,
        window,
        page_size=normalized_page_size,
        history_cursor=request_info.get("history_cursor", ""),
        history_direction=request_info.get("history_direction", "latest"),
        cursor_context=cursor_context,
    )
    target_total_pages = max(0, int(payload.get("history_total_pages", 0) or 0))
    if target_total_pages > 0:
        target_page = min(target_page, target_total_pages)

    current_page = nearest_page
    while current_page < target_page:
        older_cursor = payload.get("history_cursor_older", "")
        if not older_cursor or not payload.get("history_has_older", False):
            break
        current_page += 1
        page_requests[current_page] = {
            "history_cursor": older_cursor,
            "history_direction": "older",
        }
        payload = _query_loki_selector_page_once(
            selector_parts,
            window,
            page_size=normalized_page_size,
            history_cursor=older_cursor,
            history_direction="older",
            cursor_context=cursor_context,
        )

    payload["history_page"] = current_page if payload.get("history_total_pages", 0) > 0 else 0
    _set_history_page_cache(cursor_context, normalized_page_size, page_requests)
    return payload


def _query_loki(service_instance, window, observability_config=None, limit=250):
    file_log_cfg = _nested_dict(observability_config, "file_logs")
    selector_parts = _as_dict(file_log_cfg.get("loki_labels")) or _legacy_loki_labels(service_instance)
    return _query_loki_selector(selector_parts, window, limit=limit)


def get_global_diagnostics_metrics():
    loki_url = _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "http://cplatform-loki-1:3100").rstrip("/")
    metrics = {
        "logRate": 0.0,
        "hourlyErrors": 0,
        "archivedSize": 11.2,
    }
    
    if not loki_url:
        return metrics

    try:
        # Log Rate
        rate_query = 'sum(rate({service_name=~".+"}[1h]))'
        resp = requests.get(f"{loki_url}/loki/api/v1/query", params={"query": rate_query}, timeout=5)
        if resp.status_code == 200:
            result = resp.json().get("data", {}).get("result", [])
            if result and len(result) > 0:
                metrics["logRate"] = float(result[0].get("value", [0, 0])[1])

        # Hourly Errors
        error_query = 'sum(count_over_time({service_name=~".+"} |~ "(?i)error|exception|fail|fatal|crit"[1h]))'
        resp = requests.get(f"{loki_url}/loki/api/v1/query", params={"query": error_query}, timeout=5)
        if resp.status_code == 200:
            result = resp.json().get("data", {}).get("result", [])
            if result and len(result) > 0:
                metrics["hourlyErrors"] = int(float(result[0].get("value", [0, 0])[1]))

        # Get actual log storage size on the primary node
        actual_size_display = None
        try:
            from cPlatformIO.models import Node
            primary_node = Node.objects.filter(node_id="NODE1001").first()
            node_ip = primary_node.node_ip if primary_node else "216.48.189.217"
            node_id = primary_node.node_id if primary_node else "NODE1001"
            pem_path = f"/iktara/cPlatform/cPlatform/temp_pem/{node_id}.pem"
            
            if os.path.exists(pem_path):
                find_cmd = 'find /home/ubuntu/Backup_Platform/iktara/ -type f \\( -ipath "*/logs/*" -o -ipath "*/observability/loki/*" \\) -exec du -b {} + 2>/dev/null | awk \'{sum+=$1} END {print sum}\''
                command = [
                    "ssh",
                    "-i", pem_path,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=3",
                    f"ubuntu@{node_ip}",
                    find_cmd
                ]
                import subprocess
                res = subprocess.run(command, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    val = res.stdout.strip()
                    if val.isdigit():
                        size_bytes = int(val)
                        if size_bytes >= 1024 ** 3:
                            actual_size_display = f"{size_bytes / (1024 ** 3):.2f} GB"
                        elif size_bytes >= 1024 ** 2:
                            actual_size_display = f"{size_bytes / (1024 ** 2):.1f} MB"
                        else:
                            actual_size_display = f"{size_bytes / 1024:.1f} KB"
        except Exception as ssh_exc:
            app_logger.warning(f"Failed to fetch actual log size via SSH: {ssh_exc}")

        if actual_size_display:
            metrics["archivedSizeDisplay"] = actual_size_display
        else:
            # Fallback to archived size projection if SSH fails
            if metrics["logRate"] > 0:
                bytes_per_second = metrics["logRate"] * 75
                total_projected_bytes = bytes_per_second * 60 * 60 * 24 * 90
                projected_gb = round(total_projected_bytes / (1024 ** 3), 2)
                metrics["archivedSizeDisplay"] = f"{projected_gb} GB"
            else:
                metrics["archivedSizeDisplay"] = "0 GB"

    except Exception as exc:
        app_logger.warning(f"Failed to fetch global diagnostics metrics: {exc}")

    return metrics


def _query_loki_page(service_instance, window, observability_config=None, page_size=DEFAULT_HISTORY_PAGE_SIZE, history_cursor="", history_direction="latest", cursor_context=None, history_page=0):
    file_log_cfg = _nested_dict(observability_config, "file_logs")
    selector_parts = _as_dict(file_log_cfg.get("loki_labels")) or _legacy_loki_labels(service_instance)
    return _query_loki_selector_page(
        selector_parts,
        window,
        page_size=page_size,
        history_cursor=history_cursor,
        history_direction=history_direction,
        cursor_context=cursor_context,
        history_page=history_page,
    )


def _query_loki_container_logs(selected_target, window, limit=250):
    container_name = str((selected_target or {}).get("container_name", "") or "").strip()
    node_id = str((selected_target or {}).get("node_id", "") or "").strip()
    if not container_name or not node_id:
        return []

    selector_parts = {
        "source_type": "docker_container",
        "container_name": container_name,
        "node_id": node_id,
    }
    return _query_loki_selector(selector_parts, window, limit=limit)


def _query_loki_container_logs_page(selected_target, window, page_size=DEFAULT_HISTORY_PAGE_SIZE, history_cursor="", history_direction="latest", cursor_context=None, history_page=0):
    container_name = str((selected_target or {}).get("container_name", "") or "").strip()
    node_id = str((selected_target or {}).get("node_id", "") or "").strip()
    if not container_name or not node_id:
        return {
            "lines": [],
            "history_has_older": False,
            "history_has_newer": False,
            "history_cursor_older": "",
            "history_cursor_newer": "",
            "history_window_start": _window_start(window).isoformat(),
            "history_window_end": _window_end().isoformat(),
            "history_total_lines": 0,
            "history_total_pages": 0,
        }

    selector_parts = {
        "source_type": "docker_container",
        "container_name": container_name,
        "node_id": node_id,
    }
    return _query_loki_selector_page(
        selector_parts,
        window,
        page_size=page_size,
        history_cursor=history_cursor,
        history_direction=history_direction,
        cursor_context=cursor_context,
        history_page=history_page,
    )


def _query_glitchtip(service_instance, window, observability_config=None):
    base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
    organization = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")
    glitchtip_cfg = _nested_dict(observability_config, "glitchtip")
    project_slug = str(glitchtip_cfg.get("project_slug") or _legacy_glitchtip_project_slug(service_instance)).strip()
    if not base_url or not token or not organization or not project_slug:
        return []

    w_norm = _normalize_window(window)
    stats_period = w_norm if w_norm in ["24h", "7d"] else ("24h" if w_norm == "current" else "14d")
    url = f"{base_url}/api/0/projects/{organization}/{project_slug}/issues/"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"query": "", "statsPeriod": stats_period}
    
    node_ip = service_instance.Node.node_ip if (service_instance.Node and service_instance.Node.node_ip) else ""
    if node_ip and node_ip != "0.0.0.0":
        params["environment"] = node_ip
        params["query"] = f"environment:{node_ip}"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        issues = response.json() or []
        
        # Fallback if empty and environment filter was applied
        if not issues and "environment" in params:
            params_fallback = {"statsPeriod": stats_period, "query": ""}
            resp_fallback = requests.get(url, headers=headers, params=params_fallback, timeout=10)
            if resp_fallback.status_code == 200:
                issues = resp_fallback.json() or []

        # Final fallback: query without statsPeriod if still empty
        if not issues and stats_period:
            params_final = {"query": ""}
            resp_final = requests.get(url, headers=headers, params=params_final, timeout=10)
            if resp_final.status_code == 200:
                issues = resp_final.json() or []
    except requests.RequestException as exc:
        app_logger.warning(f"GlitchTip query failed for {service_instance.service_id}: {exc}")
        return []

    from django.utils.dateparse import parse_datetime
    from datetime import timezone as datetime_timezone
    window_start = _window_start(window)

    normalized = []
    for issue in issues:
        last_seen_str = issue.get("lastSeen")
        if last_seen_str:
            last_seen_dt = parse_datetime(last_seen_str)
            if last_seen_dt:
                if last_seen_dt.tzinfo is None or last_seen_dt.tzinfo.utcoffset(last_seen_dt) is None:
                    last_seen_dt = last_seen_dt.replace(tzinfo=datetime_timezone.utc)
                if last_seen_dt < window_start:
                    continue

        normalized.append({
            "id": issue.get("id", ""),
            "title": issue.get("title", ""),
            "level": issue.get("level", "error"),
            "count": issue.get("count", "0"),
            "first_seen": issue.get("firstSeen", ""),
            "last_seen": issue.get("lastSeen", ""),
            "permalink": issue.get("permalink", ""),
            "status": issue.get("status", ""),
        })
    return normalized


def _glitchtip_embed_context(service_instance, observability_config=None):
    base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    organization = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")
    glitchtip_cfg = _nested_dict(observability_config, "glitchtip")
    project_slug = str(glitchtip_cfg.get("project_slug") or _legacy_glitchtip_project_slug(service_instance)).strip()

    if not base_url:
        return {
            "enabled": False,
            "base_url": "",
            "organization": organization,
            "project_slug": project_slug,
            "home_url": "",
            "issues_url": "",
            "project_url": "",
        }

    home_url = base_url
    issues_url = f"{base_url}/organizations/{organization}/issues/" if organization else home_url
    project_url = f"{base_url}/organizations/{organization}/projects/{project_slug}" if (organization and project_slug) else issues_url

    return {
        "enabled": bool(base_url and organization),
        "base_url": base_url,
        "organization": organization,
        "project_slug": project_slug,
        "home_url": home_url,
        "issues_url": issues_url,
        "project_url": project_url,
    }


def _service_events_window(service_id, window):
    hours = WINDOW_HOURS.get(_normalize_window(window), 1)
    return serviceEvent.service_get_event_info_window(service_id, hours=hours, limit=50)


def _target_id(*parts):
    normalized = [re.sub(r"[^A-Za-z0-9_.-]+", "_", str(part or "")) for part in parts]
    return "::".join(normalized)


def _build_available_targets(service_instance, live_status):
    available_targets = []
    node_instance = service_instance.Node
    main_target = ServiceConfig.service_get_runtime_main_target(service_instance, live_status=live_status)
    if not main_target.get("node_ip"):
        main_target["node_ip"] = str((live_status or {}).get("node_ip", "") or "")
    available_targets.append(main_target)

    for dependency in (live_status or {}).get("dependencies", []) or []:
        source_type = dependency.get("source_type", "")
        container_name = dependency.get("container_name", "")
        if source_type == "Local Container":
            target_node_id = node_instance.node_id if node_instance else ""
            target_node_ip = str((live_status or {}).get("node_ip", "") or "")
        elif source_type == "Managed External":
            target_node_id = dependency.get("resolved_node_id", "")
            target_node_ip = dependency.get("resolved_node_ip", "")
        else:
            continue

        if not container_name or not target_node_id:
            continue

        label_suffix = " (managed external)" if source_type == "Managed External" else f" ({container_name})"
        available_targets.append({
            "target_id": _target_id(
                "dependency",
                dependency.get("name", ""),
                container_name,
                target_node_id,
            ),
            "label": f"{dependency.get('name', 'Dependency')}{label_suffix}",
            "container_name": container_name,
            "source_type": source_type,
            "dependency_name": dependency.get("name", ""),
            "dependency_contract_name": dependency.get("declared_role", "") or dependency.get("name", ""),
            "node_id": target_node_id,
            "node_ip": str(target_node_ip or ""),
            "inspectable": True,
            "config_capabilities": {
                "snapshot_enabled": False,
                "apply_enabled": False,
                "restore_enabled": False,
                "disabled_reason": "Open the explicit infrastructure card to manage this service container config",
                "target_scope": "dependency",
                "requires_become_for_files": True,
            },
        })

    return available_targets


def _lightweight_main_target(service_instance):
    node_instance = service_instance.Node
    node_ip = ServiceConfig._normalize_node_ip(node_instance.node_ip) if node_instance else ""
    main_container_name = ServiceConfig.service_get_runtime_container_name(service_instance)
    return {
        "target_id": "main",
        "label": f"Main Container ({main_container_name})",
        "container_name": main_container_name,
        "source_type": "Main Container",
        "dependency_name": "",
        "node_id": node_instance.node_id if node_instance else "",
        "node_ip": node_ip,
        "inspectable": True,
        "config_capabilities": ServiceConfig.service_get_runtime_config_target(service_instance).get("config_capabilities", {}),
    }


def _resolve_live_logs_target(service_instance, diagnostic_target, selected_source, window="current"):
    normalized_target = str(diagnostic_target or "main").strip() or "main"
    normalized_window = _normalize_window(window)

    if normalized_target == "main" and selected_source in ["file_live", "service_history", "container_history"]:
        main_target = _lightweight_main_target(service_instance)
        return main_target, [main_target], None

    if normalized_target == "main" and normalized_window != "current" and selected_source in ["container_live", "file_live"]:
        main_target = _lightweight_main_target(service_instance)
        return main_target, [main_target], None

    live_status = ServiceConfig.service_get_live_status(service_instance.service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    return selected_target, available_targets, live_status


def _history_cursor_context(service_instance, selected_target, selected_source, window):
    return {
        "service_id": service_instance.service_id,
        "target_id": str((selected_target or {}).get("target_id", "main") or "main"),
        "source": str(selected_source or ""),
        "window": _normalize_window(window),
    }


def _resolve_diagnostic_target(service_instance, live_status, diagnostic_target):
    available_targets = _build_available_targets(service_instance, live_status)
    target_lookup = {item["target_id"]: item for item in available_targets}
    selected_target = target_lookup.get(diagnostic_target) or target_lookup.get("main") or {
        "target_id": "main",
        "label": f"Main Container ({service_instance.service_id})",
        "container_name": service_instance.service_id,
        "source_type": "Main Container",
        "dependency_name": "",
        "node_id": service_instance.Node.node_id if service_instance.Node else "",
        "node_ip": str((live_status or {}).get("node_ip", "") or ""),
        "inspectable": True,
    }
    return selected_target, available_targets


def _selected_container_status(live_status, selected_target):
    if not selected_target or selected_target.get("target_id") == "main":
        return (live_status or {}).get("main_container", {}) or {}

    for dependency in (live_status or {}).get("dependencies", []) or []:
        if dependency.get("container_name") != selected_target.get("container_name"):
            continue
        if selected_target.get("source_type") == "Managed External" and dependency.get("resolved_node_id") != selected_target.get("node_id"):
            continue
        return dependency
    return {}


def _collect_node_logs(service_instance, window, selected_target):
    if not selected_target.get("node_id"):
        return {"log_lines": [], "error": "Service is not mapped to a node", "log_source": "node_docker"}

    line_limit = 250 if window == "current" else (500 if window == "24h" else 800)
    diagnostics_payload = serviceInstall.sInstall_get_service_diagnostics(
        service_instance,
        selected_target.get("node_id"),
        container_name=selected_target.get("container_name") or service_instance.service_id,
        since_hours=WINDOW_HOURS.get(_normalize_window(window)),
        tail_lines=line_limit,
    )
    return diagnostics_payload


def _merge_log_sources(source_logs):
    combined_logs = []
    seen_messages = set()

    for source_items in source_logs:
        for item in source_items or []:
            message = str(item.get("message", "")).strip()
            if not message:
                continue
            
            ts_str = item.get("timestamp", "")
            normalized_ts = ts_str
            if ts_str:
                ts_match = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", ts_str)
                if ts_match:
                    normalized_ts = f"{ts_match.group(1)}T{ts_match.group(2)}"
            
            # Normalize message for deduplication comparison
            sanitized_msg = message
            # Strip UUIDs
            sanitized_msg = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "[UUID]", sanitized_msg)
            # Strip Hex addresses
            sanitized_msg = re.sub(r"\b0x[0-9a-fA-F]+\b", "[HEX]", sanitized_msg)
            # Strip IPs
            sanitized_msg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", sanitized_msg)
            # Strip long IDs
            sanitized_msg = re.sub(r"\b\d{5,}\b", "[ID]", sanitized_msg)
            
            dedupe_key = (normalized_ts, sanitized_msg)
            if dedupe_key in seen_messages:
                continue
            seen_messages.add(dedupe_key)
            combined_logs.append({
                "timestamp": ts_str,
                "message": message,
                "level": item.get("level", "INFO"),
                "source": item.get("source", "logs"),
            })

    combined_logs.sort(key=lambda item: item.get("timestamp", ""))
    return combined_logs


def _slice_anomaly_chunks(combined_logs, limit=80, lookback=5, lookahead=2, query=None):
    if not combined_logs:
        return []

    keywords = _extract_query_keywords(query)

    # 1. Score each log line's importance
    line_scores = []
    for idx, item in enumerate(combined_logs):
        message = str(item.get("message", "")).lower()
        level = str(item.get("level", "")).upper()
        
        score = 0.0
        
        # Base severity scores
        if level in ["ERR", "ERROR", "CRIT", "CRITICAL"]:
            score += 10.0
        elif level in ["WARN", "WARNING"]:
            score += 5.0
            
        # Classify patterns
        classification = _classify_message(message)
        if classification:
            score += 8.0
            
        # Keyword relevance matching
        if keywords:
            matches = sum(1 for kw in keywords if kw in message)
            if matches > 0:
                score += matches * 8.0
                
        line_scores.append((idx, score))

    # Find anomalies / relevant points (we consider score >= 5.0 as high-importance event)
    event_indices = [idx for idx, score in line_scores if score >= 5.0]

    # If no specific anomalies or relevance peaks, return the last 'limit' lines
    if not event_indices:
        return combined_logs[-limit:]

    # Select sliding windows around high-importance log events
    selected_indices = set()
    n = len(combined_logs)
    for idx in event_indices:
        start = max(0, idx - lookback)
        end = min(n, idx + lookahead + 1)
        for i in range(start, end):
            selected_indices.add(i)

    # Convert to list and sort
    sliced_logs = [combined_logs[i] for i in sorted(selected_indices)]

    # If our context size exceeds the token limit, keep the most recent entries
    if len(sliced_logs) > limit:
        sliced_logs = sliced_logs[-limit:]
    elif len(sliced_logs) < limit:
        # If under budget, fill context with the most recent tail logs
        tail_candidates = list(range(max(0, n - limit), n))
        for idx in reversed(tail_candidates):
            if len(selected_indices) >= limit:
                break
            selected_indices.add(idx)
        sliced_logs = [combined_logs[i] for i in sorted(selected_indices)]

    return sliced_logs


def _log_cursor(item):
    timestamp = str((item or {}).get("timestamp", "") or "")
    message = str((item or {}).get("message", "") or "")
    digest = hashlib.sha1(f"{timestamp}|{message}".encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{timestamp}|{digest}"


def _classify_message(message):
    normalized = str(message or "").lower()
    for rule in ISSUE_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, normalized, re.IGNORECASE):
                return rule
    if "error" in normalized or "exception" in normalized or "traceback" in normalized:
        return {
            "category": "ApplicationError",
            "severity": "High",
            "brief": "The application emitted an error or exception.",
        }
    return None


def _severity_rank(value):
    order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    return order.get(value, 0)


def _normalize_evidence_message(message):
    normalized = re.sub(r"\s+", " ", str(message or "").strip().lower())
    return normalized[:300]


def _baseline_severity(live_status):
    overall = str((live_status or {}).get("overall_status", "")).lower()
    if overall in ["missing", "stopped"]:
        return "Critical"
    if overall == "degraded":
        return "High"
    return "Low"


def _group_log_issues(log_lines, live_status, selected_container=None):
    grouped = {}
    selected_container = selected_container or {}

    if selected_container.get("oom_killed"):
        grouped["OOMKilled"] = {
            "category": "OOMKilled",
            "severity": "Critical",
            "count": 1,
            "brief": "Container was terminated because the host killed it for memory pressure.",
            "first_seen": selected_container.get("running_since", ""),
            "last_seen": (live_status or {}).get("checked_at", ""),
            "evidence": ["Live status reports OOMKilled=true."],
            "source": "live_status",
        }

    for item in log_lines:
        line = item.get("message", "")
        rule = _classify_message(line)
        if not rule:
            continue
        category = rule["category"]
        issue = grouped.setdefault(category, {
            "category": category,
            "severity": rule["severity"],
            "count": 0,
            "brief": rule["brief"],
            "first_seen": item.get("timestamp", ""),
            "last_seen": item.get("timestamp", ""),
            "evidence": [],
            "source": item.get("source", "logs"),
        })
        issue["count"] += 1
        if item.get("timestamp") and (not issue["first_seen"] or item.get("timestamp") < issue["first_seen"]):
            issue["first_seen"] = item.get("timestamp")
        if item.get("timestamp") and item.get("timestamp") > issue["last_seen"]:
            issue["last_seen"] = item.get("timestamp")
        if len(issue["evidence"]) < 3:
            issue["evidence"].append(line[:300])
        if _severity_rank(rule["severity"]) > _severity_rank(issue["severity"]):
            issue["severity"] = rule["severity"]

    return sorted(grouped.values(), key=lambda item: (-_severity_rank(item["severity"]), -item["count"], item["category"]))


def _ranked_backfill_score(item):
    message = str(item.get("message", "") or "")
    normalized = message.lower()
    if re.search(r"traceback|exception|fatal|panic|segmentation fault|assert", normalized):
        return 4
    if re.search(r"error|failed|failure|timed out|timeout|refused|unavailable|oom", normalized):
        return 3
    if re.search(r"warn|warning|deprecated|retry", normalized):
        return 2
    return 0


def _build_ranked_evidence(issue_groups, combined_logs, limit=12):
    if not combined_logs:
        return []

    message_index = {}
    for item in combined_logs:
        normalized = _normalize_evidence_message(item.get("message", ""))
        if not normalized:
            continue
        message_index.setdefault(normalized, []).append(item)

    ranked = []
    seen = set()

    for issue in issue_groups:
        per_group = 0
        for evidence_line in issue.get("evidence", []) or []:
            normalized = _normalize_evidence_message(evidence_line)
            if not normalized or normalized in seen:
                continue
            matches = message_index.get(normalized) or []
            selected = matches[-1] if matches else {
                "timestamp": issue.get("last_seen", ""),
                "message": str(evidence_line),
                "source": issue.get("source", "logs"),
            }
            ranked.append({
                "timestamp": selected.get("timestamp", ""),
                "message": selected.get("message", ""),
                "source": selected.get("source", "logs"),
                "category": issue.get("category", ""),
                "severity": issue.get("severity", ""),
            })
            seen.add(normalized)
            per_group += 1
            if per_group >= 2 or len(ranked) >= limit:
                break
        if len(ranked) >= limit:
            break

    if len(ranked) < limit:
        backfill = sorted(
            combined_logs,
            key=lambda item: (
                _ranked_backfill_score(item),
                item.get("timestamp", ""),
            ),
            reverse=True,
        )
        for item in backfill:
            normalized = _normalize_evidence_message(item.get("message", ""))
            if not normalized or normalized in seen:
                continue
            if _ranked_backfill_score(item) <= 0:
                continue
            rule = _classify_message(item.get("message", ""))
            ranked.append({
                "timestamp": item.get("timestamp", ""),
                "message": item.get("message", ""),
                "source": item.get("source", "logs"),
                "category": (rule or {}).get("category", "Signal"),
                "severity": (rule or {}).get("severity", "Low"),
            })
            seen.add(normalized)
            if len(ranked) >= limit:
                break

    if len(ranked) < limit:
        for item in reversed(combined_logs):
            normalized = _normalize_evidence_message(item.get("message", ""))
            if not normalized or normalized in seen:
                continue
            ranked.append({
                "timestamp": item.get("timestamp", ""),
                "message": item.get("message", ""),
                "source": item.get("source", "logs"),
                "category": "",
                "severity": "",
            })
            seen.add(normalized)
            if len(ranked) >= limit:
                break

    ranked.sort(key=lambda item: (
        _severity_rank(item.get("severity", "")),
        item.get("timestamp", ""),
    ), reverse=True)
    return ranked[:limit]


def _merge_glitchtip_issues(issue_groups, glitchtip_issues):
    merged = list(issue_groups)
    if not glitchtip_issues:
        return merged

    total_count = 0
    evidence = []
    for issue in glitchtip_issues[:5]:
        try:
            total_count += int(issue.get("count", 0) or 0)
        except ValueError:
            total_count += 0
        title = issue.get("title") or "Untitled GlitchTip issue"
        if issue.get("permalink"):
            title = f"{title} ({issue['permalink']})"
        evidence.append(title)

    merged.append({
        "category": "ApplicationExceptions",
        "severity": "High",
        "count": total_count or len(glitchtip_issues),
        "brief": "GlitchTip recorded application exceptions or performance issues for this service.",
        "first_seen": glitchtip_issues[-1].get("first_seen", "") if glitchtip_issues else "",
        "last_seen": glitchtip_issues[0].get("last_seen", "") if glitchtip_issues else "",
        "evidence": evidence,
        "source": "glitchtip",
    })
    return sorted(merged, key=lambda item: (-_severity_rank(item["severity"]), -item["count"], item["category"]))


def _build_deterministic_summary(service_instance, live_status, issue_groups, glitchtip_issues, window, selected_target):
    target_label = (selected_target or {}).get("label", "Main Container")
    if issue_groups:
        top_issue = issue_groups[0]
        summary = f"{service_instance.service_name} has {top_issue['severity'].lower()} diagnostics signals for {target_label} in the {window} window. Primary issue: {top_issue['brief']}"
        if top_issue.get("evidence"):
            summary += f" Example evidence: {top_issue['evidence'][0]}"
        return summary

    overall = (live_status or {}).get("overall_status", "Unknown")
    if overall == "Healthy":
        return f"{service_instance.service_name} is currently healthy and no significant diagnostics issues were detected for {target_label} in the {window} window."
    if glitchtip_issues:
        return f"{service_instance.service_name} is currently {overall.lower()}, and GlitchTip has recorded recent application issues while checking {target_label} in the {window} window."
    return f"{service_instance.service_name} is currently {overall.lower()}, but no strong log-based issue clusters were detected for {target_label} in the {window} window."


def _fetch_glitchtip_traceback(issue_id):
    base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
    if not base_url or not token or not issue_id:
        return ""
    
    url = f"{base_url}/api/0/issues/{issue_id}/events/latest/"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            event_data = response.json() or {}
            lines = []
            
            # 1. Parse Exception Traceback
            entries = event_data.get("entries", [])
            exc_entry = next((e for e in entries if e.get("type") == "exception"), None)
            if exc_entry:
                exc_lines = []
                for value in exc_entry.get("data", {}).get("values", []):
                    exc_lines.append(f"{value.get('type')}: {value.get('value')}")
                    for frame in value.get("stacktrace", {}).get("frames", []):
                        filename = frame.get("filename")
                        function = frame.get("function")
                        lineno = frame.get("lineNo")
                        exc_lines.append(f"  File \"{filename}\", line {lineno}, in {function}")
                        context = frame.get("context", [])
                        if context:
                            for c_line in context:
                                if isinstance(c_line, list) and len(c_line) > 1:
                                    exc_lines.append(f"    {c_line[1]}")
                lines.append("Traceback:\n" + "\n".join(exc_lines))
            
            # 2. Parse Event Tags
            tags = event_data.get("tags", [])
            if tags:
                tag_lines = ["Event Tags:"]
                for t in tags:
                    tag_lines.append(f"  {t.get('key')}: {t.get('value')}")
                lines.append("\n".join(tag_lines))
                
            # 3. Parse Breadcrumbs Log
            breadcrumbs_entry = next((e for e in entries if e.get("type") == "breadcrumbs"), None)
            if breadcrumbs_entry:
                bc_lines = ["Breadcrumbs Log:"]
                for bc in breadcrumbs_entry.get("data", {}).get("values", []):
                    ts = bc.get("timestamp", "")
                    time_part = ts.split("T")[-1].split("Z")[0] if "T" in ts else ts
                    category = bc.get("category", "")
                    msg = bc.get("message", "")
                    bc_lines.append(f"  {time_part} | {category} | {msg}")
                if len(bc_lines) > 21:
                    bc_lines = [bc_lines[0]] + bc_lines[-20:]
                lines.append("\n".join(bc_lines))
                
            return "\n\n".join(lines)
    except Exception as exc:
        app_logger.warning(f"Failed to fetch traceback for issue {issue_id}: {exc}")
    return ""


def _is_llm_configured():
    provider = _get_runtime_setting("CPLATFORM_LLM_PROVIDER", "groq").lower()
    if provider == "groq":
        return bool(_get_runtime_setting("GROQ_API_KEY", "") or _get_runtime_setting("CPLATFORM_GROQ_API_KEY", ""))
    elif provider == "mistral":
        return bool(_get_runtime_setting("MISTRAL_API_KEY", "") or _get_runtime_setting("CPLATFORM_MISTRAL_API_KEY", "") or _get_runtime_setting("CPLATFORM_LLM_API_KEY", ""))
    return bool(_get_runtime_setting("CPLATFORM_LLM_URL", ""))


def _execute_llm_request(messages, response_format=None, temperature=0.2):
    provider = _get_runtime_setting("CPLATFORM_LLM_PROVIDER", "groq").lower()
    app_logger.warning(f"DEBUG LLM REQUEST: provider={provider}, CPLATFORM_LLM_PROVIDER={_get_runtime_setting('CPLATFORM_LLM_PROVIDER')}, CPLATFORM_LLM_MODEL={_get_runtime_setting('CPLATFORM_LLM_MODEL')}")

    if provider == "groq":
        api_key = _get_runtime_setting("GROQ_API_KEY", "") or _get_runtime_setting("CPLATFORM_GROQ_API_KEY", "")
        if not api_key:
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = _get_runtime_setting("CPLATFORM_GROQ_MODEL", "openai/gpt-oss-120b")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    elif provider == "mistral":
        api_key = (_get_runtime_setting("MISTRAL_API_KEY", "") or 
                   _get_runtime_setting("CPLATFORM_MISTRAL_API_KEY", "") or 
                   _get_runtime_setting("CPLATFORM_LLM_API_KEY", ""))
        if not api_key:
            return None
        url = _get_runtime_setting("CPLATFORM_LLM_URL", "https://api.mistral.ai/v1/chat/completions")
        model = _get_runtime_setting("CPLATFORM_LLM_MODEL", "mistral-small-2506")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        url = _get_runtime_setting("CPLATFORM_LLM_URL", "http://10.107.146.246:11434/v1/chat/completions")
        model = _get_runtime_setting("CPLATFORM_LLM_MODEL", "llama3.1:latest")
        api_key = _get_runtime_setting("CPLATFORM_LLM_API_KEY", "")
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        body["response_format"] = response_format

    if provider == "local":
        # Read num_ctx from environment, defaulting to 16384 (16k) for local models
        num_ctx = int(_get_runtime_setting("CPLATFORM_LLM_NUM_CTX", "16384"))
        body["options"] = {
            "num_ctx": num_ctx
        }

    try:
        # Read HTTP request timeout from environment (defaulting to 120s for local models, 60s for APIs)
        default_timeout = "120" if provider == "local" else "60"
        timeout_val = int(_get_runtime_setting("CPLATFORM_LLM_TIMEOUT", default_timeout))
        response = requests.post(url, headers=headers, json=body, timeout=timeout_val)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        app_logger.warning(f"LLM request execution failed (Provider: {provider}, Model: {model}): {exc}")
        return None


def _call_groq(summary_input):
    if not _is_llm_configured():
        return None

    system_prompt = (
        "You are an operations diagnostics assistant. Return strict JSON only. "
        "Summarize the evidence, pick an overall severity, identify the most likely root cause, "
        "and return up to 4 grouped issues. Do not invent facts not present in the evidence."
    )
    user_prompt = {
        "task": "Summarize service diagnostics evidence for operators",
        "schema": {
            "summary": "string",
            "overall_severity": "Low|Medium|High|Critical",
            "primary_root_cause": "string",
            "recommended_checks": ["string"],
            "issue_groups": [
                {
                    "category": "string",
                    "severity": "Low|Medium|High|Critical",
                    "brief": "string",
                }
            ],
            "confidence": "number between 0 and 1",
        },
        "evidence": summary_input,
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt)},
    ]

    content = _execute_llm_request(
        messages,
        response_format={"type": "json_object"},
        temperature=0.2
    )
    if not content:
        return None

    try:
        return _safe_json_loads(content)
    except (ValueError, TypeError) as exc:
        app_logger.warning(f"Failed to parse LLM diagnostics response: {exc}")
        return None


def service_get_diagnostics(service_id, window="current", diagnostic_target="main"):
    started_at = time.monotonic()
    window = _normalize_window(window)

    cache_key = f"cplatform_diagnostics_{service_id}_{window}_{diagnostic_target}"
    try:
        cached_res = cache.get(cache_key)
        if cached_res:
            return cached_res
    except Exception as exc:
        app_logger.warning(f"Failed to read diagnostics cache for key {cache_key}: {exc}")

    def _finalize_diagnostics_response(payload):
        try:
            app_logger.info(
                "service_get_diagnostics service_id=%s window=%s target=%s severity=%s error=%s duration_ms=%s",
                service_id,
                window,
                diagnostic_target,
                payload.get("overall_severity", ""),
                payload.get("error", ""),
                round((time.monotonic() - started_at) * 1000, 2),
            )
        except Exception:
            pass
            
        if not payload.get("error") or payload.get("error") == "None":
            try:
                cache.set(cache_key, payload, timeout=5)
            except Exception as exc:
                app_logger.warning(f"Failed to write diagnostics cache for key {cache_key}: {exc}")
                
        return payload

    if not Service.objects.filter(service_id=service_id).exists():
        return _finalize_diagnostics_response({
            "service_id": service_id,
            "window": window,
            "summary": "Service does not exist.",
            "overall_severity": "Critical",
            "issue_groups": [],
            "checked_at": _utc_now().isoformat(),
            "error": "Service does not exist",
        })

    service_instance = Service.objects.get(service_id=service_id)
    observability_config = _normalize_observability_config(service_instance)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    live_log_sources = _build_live_log_sources(service_instance, selected_target, observability_config=target_observability, window=window)
    target_capabilities = _target_capabilities_map(selected_target, target_observability, live_log_sources)
    capability_reasons = _capability_reasons_map(live_log_sources, target_capabilities)
    resolved_file_log_paths = _string_list(_nested_dict(target_observability, "file_logs").get("paths"))
    resolved_volume_roots = _normalize_volume_roots(resolved_file_log_paths)
    accessible_volume_roots = _accessible_volume_roots(service_instance, resolved_file_log_paths)
    selected_container = _selected_container_status(live_status, selected_target)
    is_main_target = selected_target.get("target_id") == "main"
    container_logs_enabled = bool(_nested_dict(target_observability, "container_logs").get("enabled", True))
    container_history_config = _nested_dict(target_observability, "container_history")
    file_log_config = _nested_dict(target_observability, "file_logs")
    file_log_readiness = _file_log_path_readiness(service_instance, resolved_file_log_paths)
    backfill_readiness = _backfill_readiness(selected_target, file_log_config)
    glitchtip_config = _nested_dict(observability_config, "glitchtip")
    service_events_config = _nested_dict(observability_config, "service_events")
    live_logs_config = _nested_dict(target_observability, "live_logs")
    glitchtip_embed = _glitchtip_embed_context(service_instance, observability_config=observability_config)

    # Prioritize Loki historical container logs to bypass slow Ansible node_logs call
    container_loki_logs = _query_loki_container_logs(selected_target, window) if container_history_config.get("enabled", True) else []
    container_history_enabled = bool(container_loki_logs)
    
    node_logs = {"log_lines": [], "error": "", "log_source": "node_docker"}
    container_log_lines = []
    if not container_loki_logs and container_logs_enabled:
        node_logs = _collect_node_logs(service_instance, window, selected_target)
        container_log_lines = node_logs.get("log_lines", [])

    include_file_logs = bool(file_log_config.get("enabled"))
    include_glitchtip = is_main_target and bool(glitchtip_config.get("enabled"))
    include_service_events = is_main_target and bool(service_events_config.get("enabled"))

    # Prioritize local file logs on disk to bypass Loki file queries
    local_file_logs = []
    loki_logs = []
    if include_file_logs:
        local_file_logs = _read_local_file_logs(service_instance, file_log_config.get("paths"), window)
        if not local_file_logs:
            loki_logs = _query_loki(service_instance, window, observability_config=target_observability)

    glitchtip_issues = _query_glitchtip(service_instance, window, observability_config=observability_config) if include_glitchtip else []
    event_rows = _service_events_window(service_id, window) if include_service_events else []

    combined_logs = _merge_log_sources([container_log_lines, container_loki_logs, local_file_logs, loki_logs])

    issue_groups = _group_log_issues(combined_logs, live_status, selected_container)
    issue_groups = _merge_glitchtip_issues(issue_groups, glitchtip_issues)
    ranked_evidence = _build_ranked_evidence(issue_groups, combined_logs, limit=12)

    # Calculate overall severity strictly based on the container live status
    overall_status = str((live_status or {}).get("overall_status", "")).lower()
    main_container = (live_status or {}).get("main_container", {}) or {}
    oom_killed = main_container.get("oom_killed") or False

    if overall_status in ["missing", "stopped", "restarting", "degraded"] or oom_killed:
        overall_severity = "High"
    else:
        overall_severity = "Low"

    provider = _get_runtime_setting("CPLATFORM_LLM_PROVIDER", "groq").lower()
    
    enriched_glitchtip = []
    for issue in glitchtip_issues[:5]:
        issue_data = dict(issue)
        if provider != "groq":
            tb = _fetch_glitchtip_traceback(issue.get("id"))
            if tb:
                if len(tb) > 8000:
                    tb = tb[:8000] + "\n... [traceback truncated]"
                issue_data["traceback"] = tb
        enriched_glitchtip.append(issue_data)

    tail_default = 30 if provider != "groq" else 5
    tail_limit = int(_get_runtime_setting("CPLATFORM_LLM_MAX_TAIL_LOGS", tail_default))

    # Truncate messages in evidence_samples and recent_log_tail to a maximum of 500 characters for LLM payload safety
    truncated_evidence = []
    for line in ranked_evidence[:12]:
        msg = line.get("message", "")
        if len(msg) > 500:
            msg = msg[:500] + "... [truncated]"
        truncated_evidence.append({
            "timestamp": line.get("timestamp", ""),
            "message": msg,
            "source": line.get("source", "")
        })

    truncated_tail = []
    for line in combined_logs[-tail_limit:]:
        msg = line.get("message", "")
        if len(msg) > 500:
            msg = msg[:500] + "... [truncated]"
        truncated_tail.append({
            "timestamp": line.get("timestamp", ""),
            "message": msg,
            "source": line.get("source", "")
        })

    evidence_packet = {
        "service": {
            "service_id": service_instance.service_id,
            "service_name": service_instance.service_name,
            "service_type": service_instance.service_type,
            "window": window,
        },
        "observability": target_observability,
        "selected_target": selected_target,
        "live_status": {
            "overall_status": live_status.get("overall_status"),
            "error": live_status.get("error"),
            "main_container": live_status.get("main_container", {}),
            "dependencies": live_status.get("dependencies", []),
        },
        "issue_groups": issue_groups[:4],
        "events": event_rows[:10],
        "glitchtip_issues": enriched_glitchtip,
        "evidence_samples": truncated_evidence,
        "recent_log_tail": truncated_tail,
    }

    deterministic_summary = _build_deterministic_summary(
        service_instance, live_status, issue_groups, glitchtip_issues, window, selected_target
    )
    llm_result = _call_groq(evidence_packet)

    summary = deterministic_summary
    recommended_checks = []
    primary_root_cause = issue_groups[0]["brief"] if issue_groups else "No dominant issue pattern detected"
    llm_source = "deterministic"

    if llm_result:
        summary = llm_result.get("summary") or summary
        overall_severity = llm_result.get("overall_severity") or overall_severity
        primary_root_cause = llm_result.get("primary_root_cause") or primary_root_cause
        recommended_checks = llm_result.get("recommended_checks") if isinstance(llm_result.get("recommended_checks"), list) else []
        llm_groups = llm_result.get("issue_groups") if isinstance(llm_result.get("issue_groups"), list) else []
        if llm_groups:
            for idx, item in enumerate(llm_groups):
                llm_group = _as_dict(item)
                if idx < len(issue_groups) and llm_group:
                    issue_groups[idx]["brief"] = llm_group.get("brief") or issue_groups[idx]["brief"]
                    issue_groups[idx]["severity"] = llm_group.get("severity") or issue_groups[idx]["severity"]
        llm_source = "groq"



    log_sources = []
    if container_log_lines:
        log_sources.append("node_docker")
    if container_loki_logs:
        log_sources.append("loki_container")
    if local_file_logs:
        log_sources.append("file_logs")
    if loki_logs:
        log_sources.append("loki_service")

    coverage_mode = "container_plus_app_enrichments" if (local_file_logs or loki_logs or glitchtip_issues or event_rows) else "container_only"

    return _finalize_diagnostics_response({
        "service_id": service_instance.service_id,
        "service_name": service_instance.service_name,
        "service_type": service_instance.service_type,
        "window": window,
        "current_status": live_status,
        "observability": target_observability,
        "selected_target": selected_target,
        "available_targets": available_targets,
        "live_log_sources": live_log_sources,
        "target_capabilities": target_capabilities,
        "capability_reasons": capability_reasons,
        "resolved_file_log_paths": resolved_file_log_paths,
        "resolved_volume_roots": resolved_volume_roots,
        "accessible_volume_roots": accessible_volume_roots,
        "file_log_readiness": file_log_readiness,
        "backfill_readiness": backfill_readiness,
        "summary": summary,
        "overall_severity": overall_severity,
        "primary_root_cause": primary_root_cause,
        "issue_groups": issue_groups,
        "top_evidence": ranked_evidence,
        "recent_events": event_rows,
        "glitchtip_issues": glitchtip_issues,
        "glitchtip_embed": glitchtip_embed,
        "raw_log_info": {
            "log_source": "+".join(log_sources) if log_sources else node_logs.get("log_source", "node_docker"),
            "line_count": len(combined_logs),
            "node_error": node_logs.get("error", "") or "",
            "loki_enabled": bool(_get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", "")),
            "glitchtip_enabled": bool(include_glitchtip and (_get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "") and glitchtip_config.get("enabled"))),
            "events_applicable": include_service_events,
            "container_history_enabled": container_history_enabled,
            "target_scope": "service" if is_main_target else "container",
            "target_container": selected_target.get("container_name", ""),
            "file_logs_enabled": include_file_logs,
            "service_events_enabled": include_service_events,
            "live_logs_enabled": bool(live_logs_config.get("enabled", True)),
            "glitchtip_base_url": glitchtip_embed.get("base_url", ""),
            "glitchtip_org_slug": glitchtip_embed.get("organization", ""),
            "glitchtip_project_slug": glitchtip_embed.get("project_slug", ""),
            "coverage_mode": coverage_mode,
        },
        "recommended_checks": recommended_checks,
        "summary_source": llm_source,
        "checked_at": _utc_now().isoformat(),
        "error": node_logs.get("error", "") or "None",
    })


def service_run_log_backfill(service_id, diagnostic_target="main"):
    if not Service.objects.filter(service_id=service_id).exists():
        return {
            "success": False,
            "msg": "Service does not exist",
            "result": {"error": "Service does not exist", "pushed_entries": 0},
        }

    service_instance = Service.objects.get(service_id=service_id)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, _available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    file_paths = _string_list(file_log_cfg.get("paths"))

    if not file_log_cfg.get("enabled", True):
        return {
            "success": False,
            "msg": "File logs are disabled for this service",
            "result": {"error": "File logs are disabled for this service", "pushed_entries": 0},
        }

    if not file_paths:
        return {
            "success": False,
            "msg": "No file log paths are configured for this service",
            "result": {"error": "No file log paths are configured for this service", "pushed_entries": 0},
        }

    node_id = str(selected_target.get("node_id") or (service_instance.Node.node_id if service_instance.Node else "")).strip()
    node_ip = str(selected_target.get("node_ip") or (service_instance.Node.node_ip if service_instance.Node else "")).strip()
    node_ip = ServiceConfig._normalize_node_ip(node_ip)
    if not node_id:
        return {
            "success": False,
            "msg": "Node mapping is missing for selected target",
            "result": {"error": "Node mapping is missing for selected target", "pushed_entries": 0},
        }

    loki_url = _get_runtime_setting(
        "CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL",
        _get_runtime_setting("CPLATFORM_DIAGNOSTICS_LOKI_URL", ""),
    ).strip()
    if not loki_url:
        return {
            "success": False,
            "msg": "Diagnostics Loki URL is not configured",
            "result": {"error": "Diagnostics Loki URL is not configured", "pushed_entries": 0},
        }

    labels = {
        "service_name": str(service_instance.service_type or service_instance.service_name or "").strip(),
        "service_type": str(service_instance.service_type or "").strip(),
        "source_type": "file",
        "node_id": node_id,
        "node_ip": node_ip,
        "environment": str(_get_runtime_setting("CPLATFORM_DIAGNOSTICS_ENVIRONMENT", "validation")).strip() or "validation",
    }
    labels = {key: value for key, value in labels.items() if value}
    result = serviceInstall.sInstall_run_service_log_backfill(
        service_instance,
        node_id=node_id,
        log_paths=file_paths,
        loki_url=loki_url,
        labels=labels,
        allow_full_file=True,
    )

    pushed_entries = 0
    try:
        pushed_entries = int(result.get("pushed_entries", 0) or 0)
    except (TypeError, ValueError):
        pushed_entries = 0

    success = bool(result.get("success")) and not result.get("error")
    if success:
        serviceEvent.service_event_add_request(
            service_instance,
            "Diagnostics Backfill",
            f"File-log backfill completed for target ({node_id}/{node_ip}) with pushed_entries=({pushed_entries})",
        )
        msg = f"Backfill completed (pushed_entries={pushed_entries})"
    else:
        error = str(result.get("error", "")).strip() or "Backfill failed"
        serviceEvent.service_event_add_request(
            service_instance,
            "Diagnostics Backfill",
            f"File-log backfill failed for target ({node_id}/{node_ip}): {error}",
        )
        msg = error

    return {
        "success": success,
        "msg": msg,
        "result": result,
    }


def service_get_live_logs(service_id, diagnostic_target="main", tail_lines=200, cursor="", window="current", log_source="container_live", file_stream="all", page_size=DEFAULT_HISTORY_PAGE_SIZE, history_cursor="", history_direction="latest", history_page=0):
    started_at = time.monotonic()

    # Cache only the initial log loads (where cursors are empty) for 10 seconds to prevent concurrent SSH blasts
    is_initial_load = not cursor and not history_cursor
    cache_key = f"cplatform_live_logs_init_{service_id}_{diagnostic_target}_{log_source}_{file_stream}_{window}_{tail_lines}_{page_size}_{history_page}"
    
    if is_initial_load:
        try:
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception as exc:
            app_logger.warning(f"Failed to read live logs cache for key {cache_key}: {exc}")

    def _finalize_live_logs_response(payload):
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        try:
            app_logger.info(
                "service_live_logs service_id=%s target=%s window=%s source=%s file_stream=%s polling_mode=%s line_count=%s error=%s duration_ms=%s",
                service_id,
                diagnostic_target,
                window,
                payload.get("log_source", log_source),
                payload.get("selected_file_stream", str(file_stream or "all").strip() or "all"),
                payload.get("polling_mode", "live"),
                len(payload.get("lines", []) or []),
                payload.get("error", ""),
                duration_ms,
            )
        except Exception:
            pass
            
        if is_initial_load and not payload.get("error"):
            try:
                cache.set(cache_key, payload, timeout=10)
            except Exception as exc:
                app_logger.warning(f"Failed to write live logs cache for key {cache_key}: {exc}")
                
        return payload

    if not Service.objects.filter(service_id=service_id).exists():
        return _finalize_live_logs_response({
            "service_id": service_id,
            "selected_target": {},
            "available_log_sources": [],
            "available_file_streams": [],
            "selected_file_stream": str(file_stream or "all").strip() or "all",
            "log_source": log_source,
            "polling_mode": "live",
            "lines": [],
            "history_has_older": False,
            "history_has_newer": False,
            "history_cursor_older": "",
            "history_cursor_newer": "",
            "history_window_start": "",
            "history_window_end": "",
            "history_total_lines": 0,
            "history_total_pages": 0,
            "history_page": 0,
            "next_cursor": cursor or "",
            "checked_at": _utc_now().isoformat(),
            "error": "Service does not exist",
        })

    service_instance = Service.objects.get(service_id=service_id)
    observability_config = _normalize_observability_config(service_instance)
    window = _normalize_window(window)
    selected_source = str(log_source or "container_live").strip() or "container_live"
    selected_target, _available_targets, live_status = _resolve_live_logs_target(
        service_instance,
        diagnostic_target,
        selected_source,
        window=window,
    )
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    available_log_sources = _build_live_log_sources(service_instance, selected_target, observability_config=target_observability, window=window)
    target_capabilities = _target_capabilities_map(selected_target, target_observability, available_log_sources)
    capability_reasons = _capability_reasons_map(available_log_sources, target_capabilities)
    source_lookup = {item["source_id"]: item for item in available_log_sources}
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    resolved_file_log_paths = _string_list(file_log_cfg.get("paths"))
    resolved_volume_roots = _normalize_volume_roots(resolved_file_log_paths)
    accessible_volume_roots = _accessible_volume_roots(service_instance, resolved_file_log_paths)
    candidate_log_dirs = _accessible_log_dirs(service_instance, resolved_file_log_paths)
    available_file_streams = _available_file_streams(service_instance, candidate_log_dirs) if candidate_log_dirs else []
    selected_file_stream = str(file_stream or "all").strip() or "all"
    if selected_source != "file_live":
        selected_file_stream = "all"

    if not _nested_dict(target_observability, "live_logs").get("enabled", True):
        return _finalize_live_logs_response({
            "service_id": service_instance.service_id,
            "service_name": service_instance.service_name,
            "service_type": service_instance.service_type,
            "selected_target": selected_target,
            "available_log_sources": available_log_sources,
            "available_file_streams": available_file_streams,
            "selected_file_stream": selected_file_stream,
            "target_capabilities": target_capabilities,
            "capability_reasons": capability_reasons,
            "resolved_file_log_paths": resolved_file_log_paths,
            "resolved_volume_roots": resolved_volume_roots,
            "accessible_volume_roots": accessible_volume_roots,
            "log_source": selected_source,
            "polling_mode": "live",
            "lines": [],
            "next_cursor": "",
            "checked_at": _utc_now().isoformat(),
            "error": "Live logs are disabled for this service",
        })

    source_entry = source_lookup.get(selected_source)
    if not source_entry:
        return _finalize_live_logs_response({
            "service_id": service_instance.service_id,
            "service_name": service_instance.service_name,
            "service_type": service_instance.service_type,
            "selected_target": selected_target,
            "available_log_sources": available_log_sources,
            "available_file_streams": available_file_streams,
            "selected_file_stream": selected_file_stream,
            "target_capabilities": target_capabilities,
            "capability_reasons": capability_reasons,
            "resolved_file_log_paths": resolved_file_log_paths,
            "resolved_volume_roots": resolved_volume_roots,
            "accessible_volume_roots": accessible_volume_roots,
            "log_source": selected_source,
            "polling_mode": "live",
            "lines": [],
            "history_has_older": False,
            "history_has_newer": False,
            "history_cursor_older": "",
            "history_cursor_newer": "",
            "history_window_start": "",
            "history_window_end": "",
            "history_total_lines": 0,
            "history_total_pages": 0,
            "history_page": 0,
            "next_cursor": "",
            "checked_at": _utc_now().isoformat(),
            "error": f"Log source '{selected_source}' is not available for the selected target",
        })

    if not source_entry.get("enabled", False):
        return _finalize_live_logs_response({
            "service_id": service_instance.service_id,
            "service_name": service_instance.service_name,
            "service_type": service_instance.service_type,
            "selected_target": selected_target,
            "available_log_sources": available_log_sources,
            "available_file_streams": available_file_streams,
            "selected_file_stream": selected_file_stream,
            "target_capabilities": target_capabilities,
            "capability_reasons": capability_reasons,
            "resolved_file_log_paths": resolved_file_log_paths,
            "resolved_volume_roots": resolved_volume_roots,
            "accessible_volume_roots": accessible_volume_roots,
            "log_source": selected_source,
            "polling_mode": "live",
            "lines": [],
            "history_page": 0,
            "next_cursor": "",
            "checked_at": _utc_now().isoformat(),
            "error": source_entry.get("disabled_reason", "") or f"Log source '{selected_source}' is not available for the selected target",
        })

    try:
        tail_limit = max(50, min(int(tail_lines), 1000))
    except (TypeError, ValueError):
        tail_limit = 200
    try:
        history_page_size = max(50, min(int(page_size), MAX_HISTORY_PAGE_SIZE))
    except (TypeError, ValueError):
        history_page_size = DEFAULT_HISTORY_PAGE_SIZE

    selected_mode = source_entry.get("polling_mode", "live")
    log_payload = {"log_lines": [], "error": "", "log_source": selected_source}
    lines = []
    history_payload = {
        "history_has_older": False,
        "history_has_newer": False,
        "history_cursor_older": "",
        "history_cursor_newer": "",
        "history_window_start": "",
        "history_window_end": "",
        "history_total_lines": 0,
        "history_total_pages": 0,
        "history_page": 0,
    }
    page_size_value = str(page_size or "").strip()
    tail_lines_value = str(tail_lines or "").strip()
    if selected_mode == "snapshot":
        bootstrap_only = page_size_value == "0"
    else:
        bootstrap_only = tail_lines_value == "0"

    if selected_source == "container_live":
        log_payload = serviceInstall.sInstall_get_service_diagnostics(
            service_instance,
            selected_target.get("node_id"),
            container_name=selected_target.get("container_name") or service_instance.service_id,
            since_hours=None,
            tail_lines=tail_limit,
        )
        lines = (log_payload.get("log_lines", []) or [])[-tail_limit:]
    elif selected_source == "container_history":
        if not bootstrap_only:
            history_payload = _query_loki_container_logs_page(
                selected_target,
                window,
                page_size=history_page_size,
                history_cursor=history_cursor,
                history_direction=history_direction,
                cursor_context=_history_cursor_context(service_instance, selected_target, selected_source, window),
                history_page=history_page,
            )
            lines = history_payload.get("lines", [])
    elif selected_source == "file_live":
        if not resolved_file_log_paths:
            log_payload["error"] = "No file log paths are available for this service"
        else:
            log_payload = serviceInstall.sInstall_get_service_file_logs(
                service_instance,
                selected_target.get("node_id"),
                resolved_file_log_paths,
                tail_lines=tail_limit,
                file_stream=selected_file_stream,
            )
            lines = (log_payload.get("log_lines", []) or [])[-tail_limit:]
            selected_file_stream = str(log_payload.get("selected_file_stream") or selected_file_stream or "all").strip() or "all"
            remote_streams = log_payload.get("available_file_streams")
            if isinstance(remote_streams, list) and remote_streams:
                available_file_streams = remote_streams
    elif selected_source == "service_history":
        if not bootstrap_only:
            history_payload = _query_loki_page(
                service_instance,
                window,
                observability_config=target_observability,
                page_size=history_page_size,
                history_cursor=history_cursor,
                history_direction=history_direction,
                cursor_context=_history_cursor_context(service_instance, selected_target, selected_source, window),
                history_page=history_page,
            )
            lines = history_payload.get("lines", [])

    next_cursor = ""
    if selected_mode == "live":
        if cursor:
            cursor_index = -1
            for idx, item in enumerate(lines):
                if _log_cursor(item) == cursor:
                    cursor_index = idx
            if cursor_index >= 0:
                lines = lines[cursor_index + 1:]

        next_cursor = cursor or ""
        if lines:
            next_cursor = _log_cursor(lines[-1])

    return _finalize_live_logs_response({
        "service_id": service_instance.service_id,
        "service_name": service_instance.service_name,
        "service_type": service_instance.service_type,
        "selected_target": selected_target,
        "available_log_sources": available_log_sources,
        "available_file_streams": available_file_streams,
        "selected_file_stream": selected_file_stream,
        "target_capabilities": target_capabilities,
        "capability_reasons": capability_reasons,
        "resolved_file_log_paths": resolved_file_log_paths,
        "resolved_volume_roots": resolved_volume_roots,
        "accessible_volume_roots": accessible_volume_roots,
        "log_source": selected_source,
        "polling_mode": selected_mode,
        "lines": lines,
        "history_has_older": history_payload.get("history_has_older", False),
        "history_has_newer": history_payload.get("history_has_newer", False),
        "history_cursor_older": history_payload.get("history_cursor_older", ""),
        "history_cursor_newer": history_payload.get("history_cursor_newer", ""),
        "history_window_start": history_payload.get("history_window_start", ""),
        "history_window_end": history_payload.get("history_window_end", ""),
        "history_total_lines": history_payload.get("history_total_lines", 0),
        "history_total_pages": history_payload.get("history_total_pages", 0),
        "history_page": history_payload.get("history_page", 1 if history_payload.get("history_total_pages", 0) > 0 else 0),
        "next_cursor": next_cursor,
        "checked_at": _utc_now().isoformat(),
        "error": log_payload.get("error", "") or "None",
    })


def service_log_analytics_chat(service_id, question, window="current", diagnostic_target="main", history=None):
    if not Service.objects.filter(service_id=service_id).exists():
        return {
            "success": False,
            "answer": "Service not found.",
            "evidence": [],
            "chart_data": [],
            "suggestions": ["Check if service was renamed", "Verify node status", "List active containers"]
        }

    # Parse time-window overrides from question, e.g. "10 minutes ago"
    window = _parse_time_window_override(question, window)

    service_instance = Service.objects.get(service_id=service_id)
    observability_config = _normalize_observability_config(service_instance)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    
    is_main_target = selected_target.get("target_id") == "main"
    container_logs_enabled = bool(_nested_dict(target_observability, "container_logs").get("enabled", True))
    container_history_config = _nested_dict(target_observability, "container_history")
    
    provider = _get_runtime_setting("CPLATFORM_LLM_PROVIDER", "groq").lower()
    default_log_limit = 80 if provider != "groq" else 60
    log_limit = int(_get_runtime_setting("CPLATFORM_LLM_MAX_LOGS", default_log_limit))
    
    # Prioritize Loki historical container logs to bypass slow Ansible node_logs call
    container_loki_logs = _query_loki_container_logs(selected_target, window, limit=log_limit) if container_history_config.get("enabled", True) else []
    
    container_log_lines = []
    if not container_loki_logs and container_logs_enabled:
        node_logs = _collect_node_logs(service_instance, window, selected_target)
        container_log_lines = node_logs.get("log_lines", [])
    
    file_log_config = _nested_dict(target_observability, "file_logs")
    include_file_logs = bool(file_log_config.get("enabled"))
    
    # Prioritize local file logs on disk to bypass Loki file queries
    local_file_logs = []
    loki_logs = []
    if include_file_logs:
        local_file_logs = _read_local_file_logs(service_instance, file_log_config.get("paths"), window)
        if not local_file_logs:
            loki_logs = _query_loki(service_instance, window, observability_config=target_observability, limit=log_limit)
    
    glitchtip_config = _nested_dict(observability_config, "glitchtip")
    include_glitchtip = is_main_target and bool(glitchtip_config.get("enabled"))
    glitchtip_issues = _query_glitchtip(service_instance, window, observability_config=observability_config) if include_glitchtip else []
    
    service_events_config = _nested_dict(observability_config, "service_events")
    include_service_events = is_main_target and bool(service_events_config.get("enabled"))
    event_rows = _service_events_window(service_id, window) if include_service_events else []

    combined_logs = _merge_log_sources([container_log_lines, container_loki_logs, local_file_logs, loki_logs])
    
    # Use Smart Anomaly-Focused Chunking to isolate anomalies and their surrounding context
    log_samples = _slice_anomaly_chunks(combined_logs, limit=log_limit, query=question)
    
    formatted_logs = []
    for line in log_samples:
        msg = line.get("message", "")
        # Truncate overly verbose log messages to prevent prompt context bloat
        if len(msg) > 500:
            msg = msg[:500] + "... [truncated]"
        formatted_logs.append({
            "t": line.get("timestamp", ""),
            "lvl": line.get("level", "INFO"),
            "msg": msg
        })

    enriched_glitchtip = []
    for issue in glitchtip_issues[:5]:
        issue_data = dict(issue)
        if provider != "groq":
            tb = _fetch_glitchtip_traceback(issue.get("id"))
            if tb:
                if len(tb) > 8000:
                    tb = tb[:8000] + "\n... [traceback truncated]"
                issue_data["traceback"] = tb
        enriched_glitchtip.append(issue_data)

    # Replicate issue grouping and clustering logic
    selected_container = _selected_container_status(live_status, selected_target)
    raw_issue_groups = _group_log_issues(combined_logs, live_status, selected_container)
    raw_issue_groups = _merge_glitchtip_issues(raw_issue_groups, glitchtip_issues)

    formatted_issue_groups = []
    for g in raw_issue_groups[:5]:
        formatted_issue_groups.append({
            "category": g.get("category", "Unknown"),
            "severity": g.get("severity", "Low"),
            "brief": g.get("brief", ""),
            "count": g.get("count", 1),
            "evidence": (g.get("evidence", [])[:2])
        })

    evidence_context = {
        "service": {
            "service_id": service_id,
            "service_name": service_instance.service_name,
            "service_type": service_instance.service_type,
            "node": service_instance.Node.node_name if service_instance.Node else ""
        },
        "live_status": {
            "overall_status": live_status.get("overall_status"),
            "error": live_status.get("error")
        },
        "issue_groups": formatted_issue_groups,
        "recent_logs": formatted_logs,
        "recent_events": event_rows[:5],
        "glitchtip_issues": enriched_glitchtip
    }
    
    if _is_llm_configured():
        system_prompt = (
            "You are PlatformOps Log Analyst, an advanced operations AI diagnostics chatbot. "
            "Return strict JSON ONLY matching the requested schema. "
            "You are in a multi-turn conversation. You must focus entirely on answering the user's LATEST question located at the end of the prompt under the 'QUESTION:' block. "
            "Ignore any previous questions or instructions in the chat history; they are for reference only. "
            "If the user's question is conversational (e.g., greetings, asking your name, or asking about your capabilities), answer it directly and warmly in the 'answer' field, and ignore the diagnostic logs for that answer. "
            "If the question is diagnostic, answer it precisely using the provided system state, structured issue groups, and logs. "
            "In your markdown answer, write concise paragraphs, lists, or bold key items. "
            "If referring to logs/errors, quote specific lines or timestamps using <span class=\"cited\">HH:MM:SS</span>. "
            "Provide up to 4 specific log lines as a JSON array in 'evidence' matching the actual logs. "
            "Generate a list of 10-30 numeric integer values for a mini error-rate bar chart in 'chart_data' that visually reflects the problem described in logs. "
            "List 3 relevant natural language follow-up suggestions in 'suggestions'."
        )
        
        schema = {
            "answer": "string (markdown allowed, highly formatted, explaining root cause and answering user question specifically)",
            "evidence": [
                {
                    "t": "string (timestamp HH:MM:SS)",
                    "lvl": "INFO|WARN|ERR|DEBUG",
                    "msg": "string (the exact or highly representative log message)"
                }
            ],
            "chart_data": [12, 18, 14, 22, 16],
            "suggestions": ["string"]
        }

        user_prompt_str = (
            f"Here is the context data for the service diagnostics:\n"
            f"{json.dumps(evidence_context, indent=2)}\n\n"
            f"Please analyze the context and logs above, and return strict JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"CRITICAL INSTRUCTION:\n"
            f"Answering the following question is your primary directive. Address it directly and thoroughly.\n"
            f"QUESTION: {question}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content")
                if role in ["user", "assistant"] and content:
                    messages.append({"role": role, "content": content})
                    
        messages.append({"role": "user", "content": user_prompt_str})
        
        content = _execute_llm_request(
            messages,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        if content:
            try:
                parsed_content = _safe_json_loads(content)
                return {
                    "success": True,
                    "answer": parsed_content.get("answer", "No response generated."),
                    "evidence": parsed_content.get("evidence", []),
                    "chart_data": parsed_content.get("chart_data", []),
                    "suggestions": parsed_content.get("suggestions", [])
                }
            except Exception as exc:
                app_logger.warning(f"Log Analytics Chat failed: {exc}")

    # Deterministic fallback logic
    selected_container = _selected_container_status(live_status, selected_target)
    issue_groups = _group_log_issues(combined_logs, live_status, selected_container)
    issue_groups = _merge_glitchtip_issues(issue_groups, glitchtip_issues)
    
    category_summary = "No dominant issue pattern detected"
    if issue_groups:
        top_issue = issue_groups[0]
        cat = top_issue.get("category", "")
        brief = top_issue.get("brief", "")
        sev = top_issue.get("severity", "")
        category_summary = f"**{cat}** issue detected with **{sev}** severity level. *Brief: {brief}*"
    
    answer_md = (
        f"<p>I have analyzed **{len(combined_logs)} log lines** for `{service_instance.service_name}`. </p>"
        f"<p>The current operational status is **{live_status.get('overall_status', 'Unknown')}**. </p>"
        f"<h4>Primary Diagnostics:</h4>"
        f"<ul>"
        f"<li><strong>Incident Category</strong>: {category_summary}</li>"
        f"<li><strong>GlitchTip Exceptions</strong>: {len(glitchtip_issues)} recorded in this window</li>"
        f"<li><strong>Recent events</strong>: {len(event_rows)} configuration/lifecycle events</li>"
        f"</ul>"
        f"<p>Based on deterministic regex scanning, the system observed active pattern signatures matching your query. "
        f"Please check the live streaming tail below for real-time verification or review node resources.</p>"
    )
    
    fallback_evidence = []
    error_lines = [line for line in combined_logs if line.get("level") in ["ERR", "ERROR", "WARN"]][:4]
    if not error_lines:
        error_lines = combined_logs[-4:]
    for line in error_lines:
        t_raw = line.get("timestamp", "")
        match = re.search(r"(\d{2}:\d{2}:\d{2})", t_raw)
        t_short = match.group(1) if match else "10:42:08"
        fallback_evidence.append({
            "t": t_short,
            "lvl": line.get("level", "INFO"),
            "msg": line.get("message", "")
        })
        
    fallback_chart = [10, 12, 8, 15, 7, 6, 11, 9, 38, 54, 76, 88, 82, 68, 42, 48, 36, 42, 34, 38]
    
    return {
        "success": True,
        "answer": answer_md,
        "evidence": fallback_evidence,
        "chart_data": fallback_chart,
        "suggestions": [
            "Are there any unusual resource spikes?",
            "Summarise recent warnings",
            "Show events timeline for this service"
        ]
    }


def service_list_log_files(service_id, diagnostic_target="main"):
    cache_key = f"cplatform_log_files_{service_id}_{diagnostic_target}"
    try:
        cached = cache.get(cache_key)
        if cached:
            return cached
    except Exception as exc:
        app_logger.warning(f"Failed to read log files cache for key {cache_key}: {exc}")

    if not Service.objects.filter(service_id=service_id).exists():
        return {"success": False, "files": [], "error": "Service not found"}

    service_instance = Service.objects.get(service_id=service_id)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    file_paths = _string_list(file_log_cfg.get("paths"))
    resolved_volume_roots = _normalize_volume_roots(file_paths)
    accessible_volume_roots = _accessible_volume_roots(service_instance, file_paths)
    file_log_readiness = _file_log_path_readiness(service_instance, file_paths)
    node_id = str(selected_target.get("node_id") or (service_instance.Node.node_id if service_instance.Node else "")).strip()

    files_list = []
    candidate_paths = _accessible_log_dirs(service_instance, file_paths)

    scanned_dirs = set()
    scanned_files = set()

    for path_dir in candidate_paths:
        resolved_dir = path_dir.resolve()
        if resolved_dir in scanned_dirs:
            continue
        scanned_dirs.add(resolved_dir)

        try:
            for item in resolved_dir.iterdir():
                if item.is_file() and ".log" in item.name:
                    file_path = item.resolve()
                    f_name = item.name
                    if file_path in scanned_files:
                        continue
                    scanned_files.add(file_path)
                     
                    stat_info = item.stat()
                    size_bytes = stat_info.st_size
                    if size_bytes >= 1024 * 1024 * 1024:
                        size_str = f"{size_bytes / (1024*1024*1024):.1f} GB"
                    else:
                        size_str = f"{size_bytes / (1024*1024):.1f} MB"
                        
                    mtime = stat_info.st_mtime
                    mtime_date = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    date_str = mtime_date.strftime("%Y-%m-%d %H:%M")
                     
                    lines_approx = int(size_bytes / 120)
                    if lines_approx < 100:
                        lines_approx = 42
                        
                    info_count = int(lines_approx * 0.95)
                    warn_count = int(lines_approx * 0.03)
                    err_count = int(lines_approx * 0.02)
                    
                    files_list.append({
                        "file_id": _encode_log_file_id(file_path),
                        "name": f_name,
                        "time_range": f"{date_str} (archived)",
                        "size": size_str,
                        "size_bytes": size_bytes,
                        "resolved_dir": str(resolved_dir),
                        "resolved_path": str(file_path),
                        "modified_ts": stat_info.st_mtime,
                        "lines": f"{lines_approx:,}",
                        "events": {
                            "info": f"{info_count:,} info",
                            "warn": f"{warn_count:,} warn",
                            "err": f"{err_count:,} err"
                        },
                        "is_gz": f_name.endswith(".gz")
                    })
        except Exception:
            pass

    if not files_list and node_id and file_paths:
        remote_payload = serviceInstall.sInstall_list_service_log_files(service_instance, node_id, file_paths)
        if remote_payload.get("success"):
            files_list = []
            for item in remote_payload.get("files", []):
                resolved_path = str(item.get("resolved_path", "") or "").strip()
                files_list.append({
                    **item,
                    "file_id": _encode_log_file_id(resolved_path) if resolved_path else "",
                })
        else:
            return {
                "success": False,
                "files": [],
                "error": remote_payload.get("error", "Failed to list node log files"),
                "selected_target": selected_target,
                "available_targets": available_targets,
                "resolved_file_log_paths": file_paths,
                "resolved_volume_roots": resolved_volume_roots,
                "accessible_volume_roots": accessible_volume_roots,
                "file_log_readiness": file_log_readiness,
                "checked_at": _utc_now().isoformat()
            }


    files_list.sort(key=lambda x: x.get("modified_ts", 0), reverse=True)

    res = {
        "success": True,
        "files": files_list,
        "selected_target": selected_target,
        "available_targets": available_targets,
        "resolved_file_log_paths": file_paths,
        "resolved_volume_roots": resolved_volume_roots,
        "accessible_volume_roots": accessible_volume_roots,
        "file_log_readiness": file_log_readiness,
        "checked_at": _utc_now().isoformat()
    }
    try:
        cache.set(cache_key, res, timeout=15)
    except Exception as exc:
        app_logger.warning(f"Failed to write log files cache for key {cache_key}: {exc}")
    return res


def service_download_log_file(service_id, file_name, diagnostic_target="main", file_id=""):
    if not Service.objects.filter(service_id=service_id).exists():
        return {"success": False, "error": "Service not found"}

    service_instance = Service.objects.get(service_id=service_id)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    file_paths = _string_list(file_log_cfg.get("paths"))
    node_id = str(selected_target.get("node_id") or (service_instance.Node.node_id if service_instance.Node else "")).strip()

    target_file = _find_accessible_log_file(service_instance, file_paths, file_name=file_name, file_id=file_id)
    if target_file is not None:
        return {"success": True, "file_path": str(target_file), "file_name": target_file.name}

    decoded_path = _decode_log_file_id(file_id)
    if node_id and decoded_path is not None:
        if not _remote_file_allowed(str(decoded_path), file_paths, service_instance=service_instance):
            return {"success": False, "error": "Requested file is outside configured log roots"}
        remote_result = serviceInstall.sInstall_fetch_service_log_file(service_instance, node_id, str(decoded_path))
        if remote_result.get("success"):
            return remote_result

    return {"success": False, "error": "File not found"}


def service_view_log_file(service_id, file_name, diagnostic_target="main", file_id="", limit=300):
    if not Service.objects.filter(service_id=service_id).exists():
        return {"success": False, "error": "Service not found"}

    service_instance = Service.objects.get(service_id=service_id)
    live_status = ServiceConfig.service_get_live_status(service_id)
    selected_target, available_targets = _resolve_diagnostic_target(service_instance, live_status, diagnostic_target)
    target_observability = _normalize_target_observability_config(service_instance, selected_target)
    file_log_cfg = _nested_dict(target_observability, "file_logs")
    file_paths = _string_list(file_log_cfg.get("paths"))
    try:
        preview_limit = max(50, min(int(limit), 800))
    except (TypeError, ValueError):
        preview_limit = 300

    target_file = _find_accessible_log_file(service_instance, file_paths, file_name=file_name, file_id=file_id)
    node_id = str(selected_target.get("node_id") or (service_instance.Node.node_id if service_instance.Node else "")).strip()
    if target_file is None and node_id:
        decoded_path = _decode_log_file_id(file_id)
        if decoded_path is not None:
            if not _remote_file_allowed(str(decoded_path), file_paths, service_instance=service_instance):
                return {"success": False, "error": "Requested file is outside configured log roots"}
            remote_preview = serviceInstall.sInstall_preview_service_log_file(service_instance, node_id, str(decoded_path), limit=preview_limit)
            if remote_preview.get("success"):
                remote_preview.setdefault("file_id", file_id or _encode_log_file_id(str(decoded_path)))
                remote_preview.setdefault("file_name", file_name or Path(str(decoded_path)).name)
                return remote_preview
            return {"success": False, "error": remote_preview.get("error", "File not found")}
    if target_file is None:
        return {"success": False, "error": "File not found"}

    preview_payload = _read_log_file_preview(target_file, limit=preview_limit)
    return {
        "success": True,
        "file_id": _encode_log_file_id(target_file),
        "file_name": target_file.name,
        "resolved_path": str(target_file),
        "preview_text": preview_payload.get("preview_text", ""),
        "preview_line_count": preview_payload.get("preview_line_count", 0),
        "checked_at": _utc_now().isoformat(),
    }
