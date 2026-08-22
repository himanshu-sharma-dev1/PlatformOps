"""
PlatformPath.py - Canonical Path Resolver for PlatformOps
Consolidates all filesystem path resolution for application logs, configuration snapshots,
migration artifacts, SSH credentials, and remote volume mapping.
"""

import os
from pathlib import Path
from django.conf import settings


def get_base_dir() -> Path:
    """Return the absolute path to the application base directory."""
    return Path(settings.BASE_DIR).resolve()


def get_local_snapshot_root() -> Path:
    """Return the directory where fetched config snapshots are stored locally."""
    root = get_base_dir() / "logs" / "config_snapshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_snapshot_labels_root() -> Path:
    """Return the directory where custom snapshot labels and metadata are stored."""
    root = get_base_dir() / "logs" / "config_snapshot_labels"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_migration_artifacts_root() -> Path:
    """Return the directory where config migration diffs and artifacts are stored."""
    root = get_base_dir() / "logs" / "config_migration_artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_temp_pem_dir() -> Path:
    """Return the directory where SSH keys are temporarily stored."""
    root = get_base_dir() / "temp_pem"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_node_volume(node_or_service=None) -> str:
    """
    Return the authoritative remote node volume path.
    Default: /home/ubuntu/PlatformOps_Backup
    """
    if node_or_service is not None:
        if hasattr(node_or_service, "node_volume") and node_or_service.node_volume:
            return str(node_or_service.node_volume).strip()
        if hasattr(node_or_service, "Node") and getattr(node_or_service.Node, "node_volume", None):
            return str(node_or_service.Node.node_volume).strip()
        if isinstance(node_or_service, dict):
            vol = node_or_service.get("node_volume") or node_or_service.get("machine_volume")
            if vol:
                return str(vol).strip()
    return "/home/ubuntu/PlatformOps_Backup"


def get_service_volume(service_instance=None) -> str:
    """
    Return the authoritative service volume path.
    Falls back to the parent node volume or /home/ubuntu/PlatformOps_Backup.
    """
    if service_instance is not None:
        if hasattr(service_instance, "service_volume") and service_instance.service_volume:
            return str(service_instance.service_volume).strip()
        if isinstance(service_instance, dict) and service_instance.get("service_volume"):
            return str(service_instance.get("service_volume")).strip()
    return get_node_volume(service_instance)


def clean_volume_for_path(volume_str: str) -> str:
    """Strip leading slashes for relative path construction."""
    return str(volume_str or "").strip().lstrip("/") or "home/ubuntu/PlatformOps_Backup"


def get_service_config_path(service_type: str, fallback: str = "") -> str:
    """
    Return the canonical in-container configuration path for a service type.
    """
    norm = str(service_type or "").strip()
    if norm == "PlatformOpsTest":
        return "/etc/test_service.conf"
    if norm in ["AIOrchestrator", "cPlatform"]:
        return "/iktara/cPlatform/cPlatform/config/cPlatform_config.yaml"
    if fallback:
        return fallback
    return f"/etc/{norm.lower()}/config.yaml"


def build_canonical_snapshot_path(node_ip: str, node_volume: str, service_name: str, version: str, timestamp: str) -> Path:
    """
    Build the canonical snapshot path:
    <snapshot_root>/<node_ip>/<clean_node_volume>/config/<service_name>/<version>/<timestamp>/config.yaml
    """
    clean_ip = str(node_ip or "127.0.0.1").strip()
    clean_vol = clean_volume_for_path(node_volume)
    clean_svc = str(service_name or "Service").strip()
    clean_ver = str(version or "1.0.0").strip()
    clean_ts = str(timestamp or "").strip()

    return get_local_snapshot_root() / clean_ip / clean_vol / "config" / clean_svc / clean_ver / clean_ts / "config.yaml"


def find_existing_snapshot_file(node_ip: str, node_volume: str, service_name: str, version: str, timestamp: str) -> Path:
    """
    Find a snapshot file across canonical and legacy layout paths.
    """
    canonical = build_canonical_snapshot_path(node_ip, node_volume, service_name, version, timestamp)
    if canonical.exists():
        return canonical

    clean_ip = str(node_ip or "127.0.0.1").strip()
    clean_svc = str(service_name or "").strip()
    clean_ver = str(version or "").strip()
    clean_ts = str(timestamp or "").strip()
    root = get_local_snapshot_root()

    # Check potential legacy volume folders under node_ip
    ip_dir = root / clean_ip
    if ip_dir.exists() and ip_dir.is_dir():
        for potential_file in ip_dir.rglob("config.yaml"):
            parts = potential_file.parts
            if clean_svc in parts and clean_ver in parts and clean_ts in parts:
                return potential_file

    return canonical
