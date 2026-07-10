"""Full dFormService.json import + normalizer for install-schema API."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..settings import settings

# cPlatform service type -> PlatformOps catalog service_key
DFORM_TYPE_ALIASES: dict[str, str] = {
    "AIOrchestrator": "ai-orchestrator",
    "TrainingServer": "dtrain-controller",
    "dTrain": "dtrain-controller",
    "InfraRabbitMQ": "rabbitmq-core",
    "InfraPostgreSQLCore": "postgres-core",
    "InfraRedisCore": "redis-core",
    "InfraLoki": "loki-core",
    "InfraPrometheus": "prometheus-core",
    "InfraAlloy": "alloy-core",
    "InfraNodeExporter": "node-exporter",
    "InfraProcessExporter": "process-exporter",
    "InfraClickHouse": "clickhouse-core",
}

# Reverse: catalog key -> preferred dForm type name
CATALOG_TO_DFORM: dict[str, str] = {v: k for k, v in DFORM_TYPE_ALIASES.items()}
CATALOG_TO_DFORM.update(
    {
        "ai-orchestrator": "AIOrchestrator",
        "dtrain-controller": "TrainingServer",
        "dtrain-worker": "TrainingServer",
        "dtrain-tracker": "TrainingServer",
    }
)


def _dform_paths() -> list[Path]:
    roots = [
        settings.resolve(Path("catalog/dform/dFormService.json")),
        Path(__file__).resolve().parents[4] / "catalog" / "dform" / "dFormService.json",
        Path("/home/ubuntu/PlatformOps/catalog/dform/dFormService.json"),
    ]
    return roots


@lru_cache(maxsize=1)
def load_dform_service_map() -> dict[str, Any]:
    for path in _dform_paths():
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


def list_dform_service_types() -> list[str]:
    data = load_dform_service_map()
    return sorted(k for k in data.keys() if k != "addPath" and isinstance(data.get(k), dict))


def resolve_dform_type(service_key: str) -> str | None:
    """Map catalog service_key or raw type to a dForm top-level key."""
    data = load_dform_service_map()
    if service_key in data:
        return service_key
    mapped = CATALOG_TO_DFORM.get(service_key)
    if mapped and mapped in data:
        return mapped
    # case-insensitive
    lower = {k.lower(): k for k in data.keys()}
    if service_key.lower() in lower:
        return lower[service_key.lower()]
    return None


def _map_field_type(f_type: str) -> str:
    t = (f_type or "text").lower()
    if t in {"number", "int", "integer", "float"}:
        return "number"
    if t in {"single_select", "select", "dropdown"}:
        return "select"
    if t in {"multi_select"}:
        return "multiselect"
    if t in {"password", "secret"}:
        return "password"
    if t in {"textarea", "json", "code"}:
        return "textarea"
    if t in {"checkbox", "bool", "boolean"}:
        return "checkbox"
    return "text"


def normalize_dform_fields(service_type: str) -> list[dict[str, Any]]:
    """Convert dForm properties block into install-schema field list."""
    data = load_dform_service_map()
    block = data.get(service_type) or {}
    props = block.get("properties") if isinstance(block, dict) else None
    if not isinstance(props, dict):
        return []

    fields: list[dict[str, Any]] = []
    for _prop_name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        key = str(prop.get("f_name") or _prop_name)
        label = str(prop.get("f_display_name") or key)
        field_type = _map_field_type(str(prop.get("f_type") or "text"))
        options = prop.get("v_options") or []
        if not isinstance(options, list):
            options = []
        colors = prop.get("f_color") if isinstance(prop.get("f_color"), dict) else None
        fields.append(
            {
                "key": key,
                "label": label,
                "field_type": field_type,
                "required": bool(prop.get("f_required")),
                "value": prop.get("v_default", ""),
                "default": prop.get("v_default", ""),
                "options": [str(o) for o in options],
                "min": prop.get("v_min"),
                "max": prop.get("v_max"),
                "editable": prop.get("f_editable", True),
                "display": prop.get("f_display", True),
                "disabled": bool(prop.get("f_disabled", False)),
                "width": prop.get("f_width"),
                "section": "Service parameters",
                "schema_source": "dform",
                "dform_type": service_type,
                "colors": colors,
                "help_text": str(prop.get("f_help") or prop.get("help") or ""),
            }
        )
    return fields


def dform_install_schema_for_key(service_key: str) -> dict[str, Any] | None:
    dform_type = resolve_dform_type(service_key)
    if not dform_type:
        return None
    fields = normalize_dform_fields(dform_type)
    if not fields:
        return None
    return {
        "service_key": service_key,
        "dform_type": dform_type,
        "schema_source": "dform",
        "fields": fields,
    }
