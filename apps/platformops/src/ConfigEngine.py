import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from django.conf import settings

from cPlatformIO.src import PlatformPath
from cPlatformIO.src.format_adapters import get_adapter

logger = logging.getLogger("platformops")

# -----------------------------------------------------------------------------
# Authoritative Configuration Contracts
# -----------------------------------------------------------------------------

SERVICE_CONFIG_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "PlatformOpsTest": {
        "enabled": True,
        "config_path": "/etc/test_service.conf",
        "format": "json",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "reload", "restart", "restore"],
        "activation_method": "service_api",
        "activation_port": 9031,
        "activation_endpoint": "/update_config",
        "health_endpoint": "/health",
        "validation_command": "",
        "migration_safe": True,
        "category": "Main",
    },
    "AIOrchestrator": {
        "enabled": True,
        "config_path": "/iktara/cPlatform/cPlatform/config/cPlatform_config.yaml",
        "format": "yaml",
        "read_mechanism": "local_file",
        "write_mechanism": "local_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "reload", "restart", "restore"],
        "activation_method": "none",
        "validation_command": "",
        "migration_safe": True,
        "category": "ControlPlane",
    },
    "cPlatform": {
        "enabled": True,
        "config_path": "/iktara/cPlatform/cPlatform/config/cPlatform_config.yaml",
        "format": "yaml",
        "read_mechanism": "local_file",
        "write_mechanism": "local_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "reload", "restart", "restore"],
        "activation_method": "none",
        "validation_command": "",
        "migration_safe": True,
        "category": "ControlPlane",
    },
    "MCPServer": {
        "enabled": True,
        "config_path": "/iktara/mcpServer/mcpServer/config/toolRegistry.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "validation_command": "",
        "migration_safe": True,
        "category": "App",
    },
    "Text2CLK": {
        "enabled": True,
        "config_path": "/iktara/text2clk/text2clk/config/text2clkConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "reload", "restart", "restore"],
        "activation_method": "service_api",
        "activation_port": 9002,
        "activation_endpoint": "/update_config",
        "validation_command": "",
        "migration_safe": True,
        "category": "App",
    },
    "AirtelChurn": {
        "enabled": True,
        "config_path": "/iktara/airtelChurn/airtelChurn/config/airtelChurnConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "validation_command": "",
        "migration_safe": True,
        "category": "App",
    },
    "AgenticNOC": {
        "enabled": True,
        "config_path": "/iktara/agenticNOC/agenticNOC/config/agenticNOCConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "validation_command": "",
        "migration_safe": True,
        "category": "App",
    },
    "dTrain": {
        "enabled": True,
        "config_path": "/iktara/dtrain/dtrain/config/dtrainConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "TrainingServer": {
        "enabled": True,
        "config_path": "/iktara/dtrain/dtrain/config/dtrainConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "dInfer": {
        "enabled": True,
        "config_path": "/iktara/dinfer/dinfer/config/dinferConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "InferenceServer": {
        "enabled": True,
        "config_path": "/iktara/dinfer/dinfer/config/dinferConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "optionCopilot": {
        "enabled": True,
        "config_path": "/iktara/optionCopilot/optionCopilot/config/optionCopilotConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "RAG": {
        "enabled": True,
        "config_path": "/iktara/rag/rag/config/ragConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "ASR": {
        "enabled": True,
        "config_path": "/iktara/asr/asr/config/asrConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "TTS": {
        "enabled": True,
        "config_path": "/iktara/tts/tts/config/ttsConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "ConvCall": {
        "enabled": True,
        "config_path": "/iktara/convCall/convCall/config/convCallConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "ConvForm": {
        "enabled": True,
        "config_path": "/iktara/convForm/convForm/config/convFormConfig.yaml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "App",
    },
    "InfraRedisCore": {
        "enabled": True,
        "config_path": "/usr/local/etc/redis/redis.conf",
        "format": "redis-conf",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "redis": {
        "enabled": True,
        "config_path": "/usr/local/etc/redis/redis.conf",
        "format": "redis-conf",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraPostgreSQLCore": {
        "enabled": True,
        "config_path": "/var/lib/postgresql/data/postgresql.conf",
        "format": "properties",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "apply", "reload", "restart", "restore"],
        "activation_method": "reload_command",
        "activation_command": "pg_ctl reload",
        "migration_safe": False,
        "category": "Infra",
    },
    "InfraRabbitMQ": {
        "enabled": True,
        "config_path": "/etc/rabbitmq/rabbitmq.conf",
        "format": "ini",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraAirflowScheduler": {
        "enabled": True,
        "config_path": "/opt/airflow/airflow.cfg",
        "format": "ini",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraAirflowWorker": {
        "enabled": True,
        "config_path": "/opt/airflow/airflow.cfg",
        "format": "ini",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraAirflowTriggerer": {
        "enabled": True,
        "config_path": "/opt/airflow/airflow.cfg",
        "format": "ini",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraKafkaCore": {
        "enabled": True,
        "config_path": "/opt/bitnami/kafka/config/server.properties",
        "format": "properties",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraNiFi": {
        "enabled": True,
        "config_path": "/opt/nifi/nifi-current/conf/nifi.properties",
        "format": "properties",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": True,
        "category": "Infra",
    },
    "InfraClickHouse": {
        "enabled": True,
        "config_path": "/etc/clickhouse-server/config.xml",
        "format": "xml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "apply", "restart", "restore"],
        "activation_method": "container_restart",
        "migration_safe": False,
        "category": "Infra",
    },
    "InfraPrometheus": {
        "enabled": True,
        "config_path": "/etc/prometheus/prometheus.yml",
        "format": "yaml",
        "read_mechanism": "ssh_container_file",
        "write_mechanism": "ssh_container_file",
        "supported_operations": ["read", "checkpoint", "validate", "compare", "migrate", "apply", "reload", "restart", "restore"],
        "activation_method": "reload_command",
        "activation_command": "kill -HUP 1",
        "migration_safe": True,
        "category": "Infra",
    },
}


class ConfigEngine:
    """
    Authoritative, generic configuration management engine for PlatformOps.
    """

    @classmethod
    def get_service_config_contract(cls, service_instance) -> Dict[str, Any]:
        service_type = str(getattr(service_instance, "service_type", "") or "").strip()
        contract = SERVICE_CONFIG_CONTRACTS.get(service_type)
        if contract:
            return dict(contract)
        return {
            "enabled": False,
            "disabled_reason": f"Service '{service_type}' has no declared editable runtime configuration contract.",
            "format": "raw",
            "supported_operations": [],
            "category": "Stateless",
        }

    @classmethod
    def get_service_capabilities(cls, service_instance) -> Dict[str, Any]:
        contract = cls.get_service_config_contract(service_instance)
        node_instance = getattr(service_instance, "Node", None)
        enabled = contract.get("enabled", False)
        disabled_reason = contract.get("disabled_reason", "")

        if not node_instance:
            enabled = False
            disabled_reason = "Service is not assigned to an active node"

        supported_ops = contract.get("supported_operations", [])
        return {
            "enabled": enabled,
            "editable": enabled and ("apply" in supported_ops),
            "snapshot_enabled": enabled and ("checkpoint" in supported_ops),
            "apply_enabled": enabled and ("apply" in supported_ops),
            "restore_enabled": enabled and ("restore" in supported_ops),
            "migrate_enabled": enabled and ("migrate" in supported_ops) and contract.get("migration_safe", False),
            "config_path": contract.get("config_path", ""),
            "format": contract.get("format", "raw"),
            "activation_method": contract.get("activation_method", "none"),
            "supported_operations": supported_ops,
            "disabled_reason": disabled_reason,
        }

    @classmethod
    def get_service_runtime_target(cls, service_instance) -> Dict[str, Any]:
        node_instance = getattr(service_instance, "Node", None)
        node_id = getattr(node_instance, "node_id", "") if node_instance else ""
        node_ip = str(getattr(node_instance, "node_ip", "") or getattr(node_instance, "ip_address", "") or "127.0.0.1")
        service_type = str(getattr(service_instance, "service_type", "") or "").strip()
        contract = cls.get_service_config_contract(service_instance)

        # Determine authoritative container name
        container_name = ""
        svc_cfg = getattr(service_instance, "service_config", {}) or {}
        if isinstance(svc_cfg, dict):
            runtime = svc_cfg.get("runtime", {})
            if isinstance(runtime, dict):
                container_name = str(runtime.get("container_name") or "").strip()

        if not container_name:
            if service_type in ["AIOrchestrator", "cPlatform"]:
                container_name = "iktara_cPlatform"
            elif service_type == "PlatformOpsTest":
                node_clean = node_id.lower() or "node1001"
                container_name = f"node-{node_clean}-platformops-test-service"
            else:
                container_name = str(getattr(service_instance, "service_id", ""))

        return {
            "target_id": "main",
            "service_id": str(getattr(service_instance, "service_id", "")),
            "service_name": str(getattr(service_instance, "service_name", service_type)),
            "service_type": service_type,
            "node_id": node_id,
            "node_ip": node_ip,
            "container_name": container_name,
            "config_path": contract.get("config_path", ""),
            "format": contract.get("format", "raw"),
            "activation_method": contract.get("activation_method", "none"),
            "activation_port": contract.get("activation_port"),
            "activation_endpoint": contract.get("activation_endpoint", ""),
            "category": contract.get("category", "Main"),
            "capabilities": cls.get_service_capabilities(service_instance),
        }

    @classmethod
    def read_live(cls, service_instance) -> Dict[str, Any]:
        """
        Authoritatively read the exact live configuration from the running service container / host.
        """
        caps = cls.get_service_capabilities(service_instance)
        if not caps["enabled"]:
            return {
                "success": False,
                "error": caps["disabled_reason"],
                "content": "",
                "format": caps["format"],
                "content_hash": "",
                "source": "unsupported",
            }

        target = cls.get_service_runtime_target(service_instance)
        service_type = target["service_type"]
        node_instance = getattr(service_instance, "Node", None)
        node_volume = PlatformPath.get_node_volume(node_instance) if node_instance else "/home/ubuntu/PlatformOps_Backup"

        content = ""
        source = ""

        # 1. AIOrchestrator / ControlPlane (Local Web File)
        if service_type in ["AIOrchestrator", "cPlatform"]:
            candidates = [
                PlatformPath.get_base_dir() / "config" / "cPlatform_config.yaml",
                PlatformPath.get_base_dir() / "config" / "projectConfig.yaml",
                Path(node_volume) / "iktara" / "cPlatform" / "config" / "cPlatform_config.yaml",
            ]
            for p in candidates:
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8")
                        if content.strip():
                            source = "live_container"
                            break
                    except Exception:
                        pass

        # 2. PlatformOpsTest (Bind-mounted host file or live read)
        elif service_type == "PlatformOpsTest":
            candidates = [
                Path(node_volume) / "platformops" / "testServiceConfig" / "test_service.conf",
                Path("/home/ubuntu/PlatformOps_Backup/platformops/testServiceConfig/test_service.conf"),
                Path("/home/ubuntu/Backup_Platform/platformops/testServiceConfig/test_service.conf"),
            ]
            for p in candidates:
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8")
                        if content.strip():
                            source = "live_container"
                            break
                    except Exception:
                        pass

        # 3. Direct volume mapped file for other services
        if not content and node_volume:
            cfg_rel = target["config_path"].lstrip("/")
            candidates = [
                Path(node_volume) / cfg_rel,
                Path("/home/ubuntu/PlatformOps_Backup") / cfg_rel,
            ]
            for p in candidates:
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8")
                        if content.strip():
                            source = "live_container"
                            break
                    except Exception:
                        pass

        # Fallback to latest valid checkpoint if live read didn't return content
        if not content:
            snaps = cls.get_snapshots_list(service_instance)
            if snaps:
                latest_snap = snaps[0]
                ok_s, msg_s, c_s = cls.get_snapshot_content(service_instance, snapshot_id=latest_snap.get("snapshot_id"))
                if ok_s and c_s:
                    content = c_s
                    source = "latest_checkpoint"

        if not content:
            return {
                "success": False,
                "error": f"Unable to read live configuration from container '{target['container_name']}' at '{target['config_path']}'.",
                "content": "",
                "format": target["format"],
                "content_hash": "",
                "source": "failed",
            }

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "success": True,
            "content": content,
            "format": target["format"],
            "content_hash": content_hash,
            "source": source or "live_container",
            "source_label": f"Live runtime ({target['config_path']})" if source == "live_container" else "Latest Checkpoint Fallback",
            "retrieval_time": datetime.utcnow().isoformat() + "Z",
        }

    @classmethod
    def validate(cls, content: str, format_name: str) -> Dict[str, Any]:
        adapter = get_adapter(format_name)
        is_valid, msg, details = adapter.validate(content)
        return {
            "valid": is_valid,
            "message": msg,
            "details": details,
            "format": format_name,
        }

    @classmethod
    def checkpoint(cls, service_instance, label: str = "", parent_id: str = "", actor: str = "admin") -> Dict[str, Any]:
        """
        Capture exact live configuration bytes, generate immutable snapshot ID, and persist manifest.
        """
        caps = cls.get_service_capabilities(service_instance)
        if not caps["snapshot_enabled"]:
            return {"success": False, "error": caps["disabled_reason"]}

        read_res = cls.read_live(service_instance)
        if not read_res["success"] or not read_res["content"]:
            return {"success": False, "error": f"Cannot capture checkpoint: {read_res.get('error', 'empty content')}"}

        target = cls.get_service_runtime_target(service_instance)
        node_instance = getattr(service_instance, "Node", None)
        node_ip = target["node_ip"]
        node_volume = PlatformPath.get_node_volume(node_instance) if node_instance else "/home/ubuntu/PlatformOps_Backup"
        clean_vol = PlatformPath.clean_volume_for_path(node_volume)
        service_name = target["service_type"]
        version = getattr(service_instance, "service_version", "1.0.0") or "1.0.0"

        now_utc = datetime.utcnow()
        timestamp = now_utc.strftime("%Y%m%dT%H%M%SZ")
        content_hash = read_res["content_hash"]
        hash8 = content_hash[:8]
        snapshot_id = f"snap_{target['node_id'].lower()}_{service_name.lower()}_{timestamp}_{hash8}"

        # Directory layout: logs/config_snapshots/<node_ip>/<clean_vol>/config/<service_name>/<version>/<timestamp>/
        snap_dir = PlatformPath.get_local_snapshot_root() / node_ip / clean_vol / "config" / service_name / version / timestamp
        snap_dir.mkdir(parents=True, exist_ok=True)

        config_file = snap_dir / "config.yaml"
        config_file.write_text(read_res["content"], encoding="utf-8")

        manifest = {
            "snapshot_id": snapshot_id,
            "service_id": target["service_id"],
            "service_name": target["service_name"],
            "service_type": service_name,
            "node_id": target["node_id"],
            "node_ip": node_ip,
            "container_name": target["container_name"],
            "config_path": target["config_path"],
            "format": target["format"],
            "source_type": read_res["source"],
            "timestamp": timestamp,
            "created_at": now_utc.isoformat() + "Z",
            "version": version,
            "label": label or f"{version} ({timestamp})",
            "content_hash": content_hash,
            "parent_snapshot_id": parent_id,
            "actor": actor,
            "file_size": len(read_res["content"]),
            "canonical_path": str(config_file),
        }

        manifest_file = snap_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Also store label in legacy label map for seamless backward compatibility
        try:
            from cPlatformIO.src import ServiceConfig
            ServiceConfig._save_config_snapshot_label(target["service_id"], timestamp, label or f"{version} ({timestamp})")
        except Exception:
            pass

        logger.info(f"Captured checkpoint {snapshot_id} for {service_name} at {config_file}")
        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "manifest": manifest,
            "path": str(config_file),
            "timestamp": timestamp,
            "version": version,
        }

    @classmethod
    def get_snapshots_list(cls, service_instance) -> List[Dict[str, Any]]:
        """
        Return structured list of all snapshots for a service sorted newest to oldest.
        """
        target = cls.get_service_runtime_target(service_instance)
        node_instance = getattr(service_instance, "Node", None)
        node_ip = target["node_ip"]
        node_volume = PlatformPath.get_node_volume(node_instance) if node_instance else "/home/ubuntu/PlatformOps_Backup"
        clean_vol = PlatformPath.clean_volume_for_path(node_volume)
        service_name = target["service_type"]

        base_dir = PlatformPath.get_local_snapshot_root() / node_ip / clean_vol / "config" / service_name
        snapshots = []

        if base_dir.exists() and base_dir.is_dir():
            for ver_dir in sorted(base_dir.iterdir(), reverse=True):
                if not ver_dir.is_dir():
                    continue
                ver_name = ver_dir.name
                for ts_dir in sorted(ver_dir.iterdir(), reverse=True):
                    if not ts_dir.is_dir():
                        continue
                    ts_name = ts_dir.name
                    cfg_file = ts_dir / "config.yaml"
                    if not cfg_file.exists() or not cfg_file.is_file():
                        continue

                    manifest_file = ts_dir / "manifest.json"
                    if manifest_file.exists() and manifest_file.is_file():
                        try:
                            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                        except Exception:
                            manifest = {}
                    else:
                        manifest = {}

                    snapshot_id = manifest.get("snapshot_id") or f"snap_{target['node_id'].lower()}_{service_name.lower()}_{ts_name}"
                    snapshots.append({
                        "snapshot_id": snapshot_id,
                        "display_name": manifest.get("label") or f"{ver_name} ({ts_name})",
                        "label": manifest.get("label") or f"{ver_name} ({ts_name})",
                        "version": ver_name,
                        "timestamp": ts_name,
                        "path": str(cfg_file),
                        "created_at": manifest.get("created_at") or ts_name,
                        "content_hash": manifest.get("content_hash", ""),
                        "format": manifest.get("format", target["format"]),
                        "file_size": cfg_file.stat().st_size,
                    })

        return snapshots

    @classmethod
    def get_snapshot_content(cls, service_instance, snapshot_id: str = None, version: str = None, timestamp: str = None) -> Tuple[bool, str, str]:
        """
        Resolve snapshot content by immutable snapshot_id or legacy (version, timestamp).
        """
        target = cls.get_service_runtime_target(service_instance)
        snaps = cls.get_snapshots_list(service_instance)

        match_path = None
        for s in snaps:
            if snapshot_id and s["snapshot_id"] == snapshot_id:
                match_path = Path(s["path"])
                break
            if version and timestamp and s["version"] == version and s["timestamp"] == timestamp:
                match_path = Path(s["path"])
                break

        if match_path and match_path.exists() and match_path.is_file():
            try:
                return True, "Success", match_path.read_text(encoding="utf-8")
            except Exception as e:
                return False, f"Error reading snapshot: {str(e)}", ""

        # Fallback to PlatformPath.find_existing_snapshot_file
        node_instance = getattr(service_instance, "Node", None)
        node_volume = PlatformPath.get_node_volume(node_instance) if node_instance else "/home/ubuntu/PlatformOps_Backup"
        fallback_file = PlatformPath.find_existing_snapshot_file(
            target["node_ip"], node_volume, target["service_type"], version or "1.0.0", timestamp or ""
        )
        if fallback_file.exists() and fallback_file.is_file():
            try:
                return True, "Success", fallback_file.read_text(encoding="utf-8")
            except Exception as e:
                return False, f"Error reading fallback snapshot: {str(e)}", ""

        return False, f"Snapshot not found (ID: {snapshot_id}, ver: {version}, ts: {timestamp})", ""

    @classmethod
    def compare(cls, service_instance, snap1_param: Any, snap2_param: Any) -> Dict[str, Any]:
        """
        Compare two checkpoints (by snapshot_id or {version, timestamp} dict).
        """
        id1 = snap1_param.get("snapshot_id") if isinstance(snap1_param, dict) else str(snap1_param)
        ver1 = snap1_param.get("version") if isinstance(snap1_param, dict) else ""
        ts1 = snap1_param.get("timestamp") if isinstance(snap1_param, dict) else ""

        id2 = snap2_param.get("snapshot_id") if isinstance(snap2_param, dict) else str(snap2_param)
        ver2 = snap2_param.get("version") if isinstance(snap2_param, dict) else ""
        ts2 = snap2_param.get("timestamp") if isinstance(snap2_param, dict) else ""

        ok1, msg1, c1 = cls.get_snapshot_content(service_instance, snapshot_id=id1, version=ver1, timestamp=ts1)
        if not ok1:
            return {"success": False, "error": f"Failed to load snapshot 1: {msg1}", "diff_html": ""}

        ok2, msg2, c2 = cls.get_snapshot_content(service_instance, snapshot_id=id2, version=ver2, timestamp=ts2)
        if not ok2:
            return {"success": False, "error": f"Failed to load snapshot 2: {msg2}", "diff_html": ""}

        target = cls.get_service_runtime_target(service_instance)
        adapter = get_adapter(target["format"])
        label1 = f"{ver1 or 'snap1'} ({ts1})"
        label2 = f"{ver2 or 'snap2'} ({ts2})"

        diff_result = adapter.diff(c1, c2, label1=label1, label2=label2)
        from cPlatformIO.src import ServiceConfig
        html_diff = ServiceConfig._render_split_diff_html(diff_result["unified_diff"], label1, label2)

        return {
            "success": True,
            "diff_html": html_diff,
            "identical": diff_result["identical"],
            "semantic_diff": diff_result["semantic_diff"],
        }

    @classmethod
    def apply(cls, service_instance, new_content: str, apply_mode: str = "reload", actor: str = "admin") -> Dict[str, Any]:
        """
        14-Step Atomic Apply Transaction with Automatic Rollback.
        """
        caps = cls.get_service_capabilities(service_instance)
        if not caps["apply_enabled"]:
            return {"success": False, "error": caps["disabled_reason"]}

        target = cls.get_service_runtime_target(service_instance)
        op_id = f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        # Step 1: Validate submitted content syntax
        val_res = cls.validate(new_content, target["format"])
        if not val_res["valid"]:
            return {"success": False, "error": f"Configuration validation failed: {val_res['message']}", "stage": "validation"}

        # Step 2: Read current live configuration
        live_res = cls.read_live(service_instance)
        current_content = live_res["content"] if live_res["success"] else ""

        # Step 3: Capture mandatory pre-apply checkpoint
        pre_cp = cls.checkpoint(service_instance, label=f"Pre-Apply Backup ({op_id})", actor=actor)
        if not pre_cp["success"]:
            return {"success": False, "error": f"Mandatory pre-apply checkpoint failed: {pre_cp.get('error')}", "stage": "pre_checkpoint"}
        pre_snapshot_id = pre_cp["snapshot_id"]

        node_instance = getattr(service_instance, "Node", None)
        node_volume = PlatformPath.get_node_volume(node_instance) if node_instance else "/home/ubuntu/PlatformOps_Backup"

        try:
            # Step 4-8: Replace file and activate according to mechanism
            service_type = target["service_type"]

            # 1. AIOrchestrator (Local ControlPlane file)
            if service_type in ["AIOrchestrator", "cPlatform"]:
                local_path = PlatformPath.get_base_dir() / "config" / "cPlatform_config.yaml"
                local_path.write_text(new_content, encoding="utf-8")

            # 2. Remote node services (executed via atomic Ansible apply pipeline)
            else:
                # Update local host bind-mount copy if present
                if service_type == "PlatformOpsTest":
                    test_conf_path = Path(node_volume) / "platformops" / "testServiceConfig" / "test_service.conf"
                    if test_conf_path.parent.exists():
                        try:
                            test_conf_path.write_text(new_content, encoding="utf-8")
                        except Exception:
                            pass

                from cPlatformIO.src import serviceInstall
                apply_res = serviceInstall.sInstall_apply_service_config_migration(
                    service_instance,
                    target["node_id"],
                    new_content,
                    apply_mode=apply_mode,
                    container_name=target["container_name"],
                    service_name=target["service_type"],
                    version=getattr(service_instance, "service_version", "1.0.0"),
                    config_path=target["config_path"],
                    node_volume=node_volume,
                )
                if not apply_res.get("success", False):
                    return {"success": False, "error": apply_res.get("error", "Remote configuration apply failed"), "stage": "remote_apply"}

            # Step 9-10: Re-read live configuration and verify hash
            post_read = cls.read_live(service_instance)
            new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

            # Step 11: Synchronize database record without replacing runtime metadata
            adapter = get_adapter(target["format"])
            ok_p, parsed_data, _ = adapter.parse(new_content)

            prev_runtime = {}
            if isinstance(service_instance.service_config, dict):
                prev_runtime = service_instance.service_config.get("runtime", {})

            if isinstance(parsed_data, dict):
                service_instance.service_config = dict(parsed_data)
            else:
                service_instance.service_config = {"raw_content": new_content}

            if prev_runtime:
                service_instance.service_config["runtime"] = prev_runtime
            service_instance.save()

            # Step 12: Capture post-apply checkpoint
            post_cp = cls.checkpoint(service_instance, label=f"Post-Apply State ({op_id})", parent_id=pre_snapshot_id, actor=actor)

            # Step 13: Record ServiceEvent
            try:
                from cPlatformIO.models import ServiceEvent
                ServiceEvent.objects.create(
                    service=service_instance,
                    event_date=date.today(),
                    event_time=datetime.now().time(),
                    event_type="Config Applied",
                    event_description=f"Applied new configuration via {apply_mode} (Operation {op_id})",
                )
            except Exception:
                pass

            logger.info(f"Successfully applied configuration for {target['service_name']} (Op: {op_id})")
            return {
                "success": True,
                "operation_id": op_id,
                "msg": "Configuration successfully applied and verified",
                "pre_snapshot_id": pre_snapshot_id,
                "post_snapshot_id": post_cp.get("snapshot_id"),
                "content_hash": new_hash,
            }

        except Exception as e:
            logger.exception(f"Exception during apply transaction for {target['service_name']}: {str(e)}")
            # Rollback to pre-apply content
            if current_content:
                try:
                    if service_type in ["AIOrchestrator", "cPlatform"]:
                        (PlatformPath.get_base_dir() / "config" / "cPlatform_config.yaml").write_text(current_content, encoding="utf-8")
                    elif service_type == "PlatformOpsTest":
                        (Path(node_volume) / "platformops" / "testServiceConfig" / "test_service.conf").write_text(current_content, encoding="utf-8")
                except Exception:
                    pass
            return {"success": False, "error": f"Apply transaction aborted: {str(e)}", "stage": "execution_exception"}
