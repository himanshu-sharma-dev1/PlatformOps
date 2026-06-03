from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .settings import settings


def _read_yaml(path: Path) -> dict[str, Any]:
    resolved = settings.resolve(path)
    if not resolved.exists():
        return {}
    with resolved.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=8)
def service_catalog() -> dict[str, dict[str, Any]]:
    return _read_yaml(settings.service_catalog_path).get("services", {})


@lru_cache(maxsize=8)
def dependency_catalog() -> dict[str, list[str]]:
    return _read_yaml(settings.dependency_catalog_path).get("dependencies", {})


@lru_cache(maxsize=8)
def observability_catalog() -> dict[str, Any]:
    return _read_yaml(settings.observability_catalog_path)


def get_service_contract(service_key: str) -> dict[str, Any]:
    return service_catalog().get(service_key, {})


def required_dependencies(service_key: str) -> list[str]:
    return dependency_catalog().get(service_key, [])


def format_contract_value(value: Any, *, node_id: int, volume_root: str) -> Any:
    if isinstance(value, str):
        return value.format(
            node_id=node_id,
            volume_root=volume_root.rstrip("/"),
            project_root=str(settings.project_root),
        )
    if isinstance(value, list):
        return [format_contract_value(item, node_id=node_id, volume_root=volume_root) for item in value]
    if isinstance(value, dict):
        return {
            key: format_contract_value(item, node_id=node_id, volume_root=volume_root) for key, item in value.items()
        }
    return value


def rendered_contract(service_key: str, *, node_id: int, volume_root: str) -> dict[str, Any]:
    contract = dict(get_service_contract(service_key))
    return format_contract_value(contract, node_id=node_id, volume_root=volume_root)
