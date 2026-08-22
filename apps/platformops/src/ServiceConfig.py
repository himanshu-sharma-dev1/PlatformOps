'''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : ServiceConfig.py
* Description       : Functions related to Service feature
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 08-Apr-25                     Aniket                            Created.
* 18-Apr-25                     Sumit Das                         Updated.
*********************************************************************************************************************'''

import json
import os
import time
import hashlib
import uuid
import re
import yaml
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import requests
from omegaconf import OmegaConf
from celery import shared_task
# Module Models & Constants
from cPlatformIO.models import Service, ApplicationInfo, Node
from cPlatform.AppLogging import app_logger
from cPlatformIO.src import serviceInstall, NodeConfig, Cutilinit, PlatformConfig, McpclInit
from cPlatformIO.src.serviceEvent import service_event_add_request
from cPlatformIO.src.PlatformSetting import PlatformSettings
from CommonUtils.logs import LogMgr
from CommonUtils.timer.TimerMgr import cutil_timer_interval_start, cutil_timer_stop
from django.db.models import Q
from django_celery_beat.models import PeriodicTask

SERVICE_BASE_IDX = 1000
SERVICE_DEPLOY_MAX_RETRY = 6
SERVICE_LIVE_STATUS_CACHE_TTL_SECONDS = 5
SERVICE_LIVE_STATUS_CACHE = {}

INFRA_SERVICE_VERSIONS = {
    "InfraRabbitMQ": "3.13.7",
    "InfraPostgreSQLCore": "17.5",
    "InfraRedisCore": "7.2.12",
    "InfraAirflowPostgreSQL": "3.0.3",
    "InfraAirflowRedis": "3.0.3",
    "InfraAirflowScheduler": "3.0.3",
    "InfraAirflowWorker": "3.0.3",
    "InfraAirflowDagProcessor": "3.0.3",
    "InfraAirflowTriggerer": "3.0.3",
    "InfraClickHouse": "25.8.2.29",
    "InfraKafkaCore": "3.8.1",
    "InfraNiFi": "1.0.0",
    "InfraMilvus": "1.0.0",
    "InfraEtcd": "1.0.0",
    "InfraMinio": "1.0.0",
    "InfraNodeExporter": "1.9.1",
    "InfraProcessExporter": "0.8.7",
    "InfraKafkaExporter": "v1.8.0",
    "InfraDcgmExporter": "4.2.3",
    "InfraPrometheus": "1.0.0",
    "InfraPrometheusANS": "1.0.0",
    "InfraPrometheusRAG": "1.0.0",
}

INFRASTRUCTURE_SERVICE_CATALOG = {
    "InfraRabbitMQ": {
        "display_name": "RabbitMQ Core",
        "source_service": "ANS",
        "source_role": "RabbitMQ",
        "container_slug": "rabbitmq",
        "category": "stream",
    },
    "InfraPostgreSQLCore": {
        "display_name": "PostgreSQL Core",
        "source_service": "ANS",
        "source_role": "PostgreSQL",
        "container_slug": "postgresql-core",
        "category": "db",
    },
    "InfraRedisCore": {
        "display_name": "Redis Core",
        "source_service": "RAG",
        "source_role": "redis",
        "container_slug": "redis-core",
        "category": "cache",
    },
    "InfraAirflowPostgreSQL": {
        "display_name": "Airflow PostgreSQL",
        "source_service": "Airflow",
        "source_role": "PostgreSQL",
        "container_slug": "airflow-postgresql",
        "category": "db",
    },
    "InfraAirflowRedis": {
        "display_name": "Airflow Redis",
        "source_service": "Airflow",
        "source_role": "redis",
        "container_slug": "airflow-redis",
        "category": "cache",
    },
    "InfraAirflowScheduler": {
        "display_name": "Airflow Scheduler",
        "source_service": "Airflow",
        "source_role": "Airflow-Scheduler",
        "container_slug": "airflow-scheduler",
        "category": "service",
    },
    "InfraAirflowWorker": {
        "display_name": "Airflow Worker",
        "source_service": "Airflow",
        "source_role": "Airflow-Worker",
        "container_slug": "airflow-worker",
        "category": "service",
    },
    "InfraAirflowDagProcessor": {
        "display_name": "Airflow Dag Processor",
        "source_service": "Airflow",
        "source_role": "Airflow-DagProcessor",
        "container_slug": "airflow-dagprocessor",
        "category": "service",
    },
    "InfraAirflowTriggerer": {
        "display_name": "Airflow Triggerer",
        "source_service": "Airflow",
        "source_role": "Airflow-Triggerer",
        "container_slug": "airflow-triggerer",
        "category": "service",
    },
    "InfraClickHouse": {
        "display_name": "ClickHouse Core",
        "source_service": "ANS",
        "source_role": "ClickHouse",
        "container_slug": "clickhouse",
        "category": "db",
    },
    "InfraKafkaCore": {
        "display_name": "Kafka Core (single-node KRaft)",
        "source_service": "ANS",
        "source_role": "Kafka",
        "container_slug": "kafka",
        "category": "stream",
    },
    "InfraNiFi": {
        "display_name": "NiFi Core",
        "source_service": "ANS",
        "source_role": "NiFi",
        "container_slug": "nifi",
        "category": "stream",
    },
    "InfraMilvus": {
        "display_name": "Milvus Vector Store",
        "source_service": "RAG",
        "source_role": "Milvus",
        "container_slug": "milvus",
        "category": "db",
    },
    "InfraEtcd": {
        "display_name": "etcd Core",
        "source_service": "RAG",
        "source_role": "etcd",
        "container_slug": "etcd",
        "category": "db",
    },
    "InfraMinio": {
        "display_name": "MinIO Object Store",
        "source_service": "RAG",
        "source_role": "minio",
        "container_slug": "minio",
        "category": "storage",
    },
    "InfraNodeExporter": {
        "display_name": "Node Exporter",
        "source_service": "ANS",
        "source_role": "node-exporter",
        "container_slug": "node-exporter",
        "category": "monitor",
    },
    "InfraProcessExporter": {
        "display_name": "Process Exporter",
        "source_service": "ANS",
        "source_role": "process-exporter",
        "container_slug": "process-exporter",
        "category": "monitor",
    },
    "InfraKafkaExporter": {
        "display_name": "Kafka Exporter",
        "source_service": "ANS",
        "source_role": "kafka-exporter",
        "container_slug": "kafka-exporter",
        "category": "monitor",
    },
    "InfraDcgmExporter": {
        "display_name": "DCGM Exporter",
        "source_service": "ANS",
        "source_role": "dcgmExporter",
        "container_slug": "dcgm-exporter",
        "category": "monitor",
    },
    "InfraPrometheus": {
        "display_name": "Prometheus",
        "source_service": "ANS",
        "source_role": "Prometheus",
        "container_slug": "prometheus",
        "category": "monitor",
    },
    "InfraPrometheusANS": {
        "display_name": "Prometheus ANS",
        "source_service": "ANS",
        "source_role": "Prometheus",
        "container_slug": "prometheus-ans",
        "category": "monitor",
        "catalog_visible": False,
    },
    "InfraPrometheusRAG": {
        "display_name": "Prometheus RAG",
        "source_service": "RAG",
        "source_role": "Prometheus",
        "container_slug": "prometheus-rag",
        "category": "monitor",
        "catalog_visible": False,
    },
}

INFRASTRUCTURE_CONFIG_PATHS = {
    "Text2CLK": "/iktara/text2clk/text2clk/config/text2clkConfig.yaml",
    "MCPServer": "/iktara/mcpServer/mcpServer/config/toolRegistry.yaml",
    "Postgres": "/var/lib/postgresql/data/postgresql.conf",
    "Airflow": "/opt/airflow/airflow.cfg",
    "InfraRabbitMQ": "/etc/rabbitmq/rabbitmq.conf",
    "InfraPostgreSQLCore": "/var/lib/postgresql/data/postgresql.conf",
    "InfraRedisCore": "/usr/local/etc/redis/redis.conf",
    "InfraAirflowPostgreSQL": "/var/lib/postgresql/data/postgresql.conf",
    "InfraAirflowRedis": "/usr/local/etc/redis/redis.conf",
    "InfraAirflowScheduler": "/opt/airflow/airflow.cfg",
    "InfraAirflowWorker": "/opt/airflow/airflow.cfg",
    "InfraAirflowDagProcessor": "/opt/airflow/airflow.cfg",
    "InfraAirflowTriggerer": "/opt/airflow/airflow.cfg",
    "InfraClickHouse": "/etc/clickhouse-server/config.xml",
    "InfraKafkaCore": "/opt/bitnami/kafka/config/server.properties",
    "InfraProcessExporter": "/etc/process-exporter/process-exporter.yml",
    "InfraPrometheus": "/etc/prometheus/prometheus.yml",
    "InfraPrometheusANS": "/etc/prometheus/prometheus.yml",
    "InfraPrometheusRAG": "/etc/prometheus/prometheus.yml",
    "InfraNodeExporter": "/etc/node-exporter/config.yml",
    "InfraNiFi": "/opt/nifi/nifi-current/conf/nifi.properties",
    "InfraMinio": "/root/.minio/config.json",
    "InfraEtcd": "/etc/etcd/etcd.yml",
    "InfraDcgmExporter": "/etc/dcgm-exporter/default-counters.csv",
}

INFRASTRUCTURE_DISCOVERY_HINTS = {
    "InfraRabbitMQ": ["rabbitmq"],
    "InfraPostgreSQLCore": ["postgres", "postgresql"],
    "InfraRedisCore": ["redis"],
    "InfraAirflowPostgreSQL": ["airflow", "postgres"],
    "InfraAirflowRedis": ["airflow", "redis"],
    "InfraAirflowScheduler": ["airflow", "scheduler"],
    "InfraAirflowWorker": ["airflow", "worker"],
    "InfraAirflowDagProcessor": ["airflow", "dagprocessor"],
    "InfraAirflowTriggerer": ["airflow", "triggerer"],
    "InfraClickHouse": ["clickhouse"],
    "InfraKafkaCore": ["kafka"],
    "InfraNiFi": ["nifi"],
    "InfraMilvus": ["milvus"],
    "InfraEtcd": ["etcd"],
    "InfraMinio": ["minio"],
    "InfraNodeExporter": ["node-exporter", "node_exporter"],
    "InfraProcessExporter": ["process-exporter", "process_exporter"],
    "InfraKafkaExporter": ["kafka-exporter", "kafka_exporter"],
    "InfraDcgmExporter": ["dcgm"],
    "InfraPrometheus": ["prometheus"],
    "InfraPrometheusANS": ["prometheus"],
    "InfraPrometheusRAG": ["prometheus"],
}

INFRASTRUCTURE_DISCOVERY_EXCLUDES = {
    "InfraPostgreSQLCore": ["airflow", "glitchtip"],
    "InfraRedisCore": ["airflow", "glitchtip", "valkey"],
    "InfraPrometheusANS": ["rag"],
    "InfraPrometheusRAG": ["ans"],
}

INFRASTRUCTURE_SERVICE_EQUIVALENTS = {
    "InfraPrometheus": ["InfraPrometheus", "InfraPrometheusANS", "InfraPrometheusRAG"],
    "InfraPrometheusANS": ["InfraPrometheus", "InfraPrometheusANS", "InfraPrometheusRAG"],
    "InfraPrometheusRAG": ["InfraPrometheus", "InfraPrometheusANS", "InfraPrometheusRAG"],
}

INFRASTRUCTURE_DISCOVERY_BLOCKED_MARKERS = [
    "glitchtip",
    "signoz",
    "config-migration",
    "alloy",
    "otel",
    "loki",
    "grafana",
]

SERVICE_INFRASTRUCTURE_DEPENDENCIES = {
    "TrainingServer": ["InfraRabbitMQ"],
    "ANS": [
        "InfraNodeExporter",
        "InfraDcgmExporter",
        "InfraPrometheus",
        "InfraClickHouse",
        "InfraKafkaCore",
        "InfraNiFi",
        "InfraPostgreSQLCore",
        "InfraRabbitMQ",
    ],
    "RAG": [
        "InfraMilvus",
        "InfraEtcd",
        "InfraMinio",
        "InfraNodeExporter",
        "InfraDcgmExporter",
        "InfraPrometheus",
        "InfraPostgreSQLCore",
        "InfraRedisCore",
        "InfraRabbitMQ",
    ],
    "Text2SQL": ["InfraPostgreSQLCore", "InfraRedisCore"],
    "Text2CLK": ["InfraPostgreSQLCore"],
    "AirtelChurn": ["InfraRedisCore"],
    "ASR": ["InfraPostgreSQLCore"],
    "TTS": ["InfraPostgreSQLCore"],
    "ConvCall": ["InfraPostgreSQLCore"],
    "ConvForm": ["InfraPostgreSQLCore", "InfraRedisCore", "InfraRabbitMQ"],
    "InferenceServer": ["InfraRabbitMQ"],
    "McpProxy": ["InfraRabbitMQ", "InfraRedisCore"],
    "optionCopilot": ["InfraPostgreSQLCore", "InfraRabbitMQ", "InfraRedisCore", "InfraClickHouse"],
    "Airflow": ["InfraAirflowPostgreSQL", "InfraAirflowRedis"],
    "AgenticNOC": [
        "InfraKafkaCore",
        "InfraNiFi",
        "InfraPostgreSQLCore",
        "InfraClickHouse",
        "InfraPrometheus",
    ],
}


# -----------------------------------------Utility Function-------------------------------------------------------------

def _get_mapped_service_id(service_idx):
    service_id = 'SERV' + str(SERVICE_BASE_IDX + service_idx)
    return service_id


def _normalize_discovery_token(value):
    return re.sub(r'[^a-z0-9]+', '', str(value or '').strip().lower())


def _split_image_ref(image_ref):
    image_ref = str(image_ref or "").strip()
    if not image_ref:
        return "", ""
    image_ref = image_ref.split("@", 1)[0]
    last_segment = image_ref.rsplit("/", 1)[-1]
    if ":" in last_segment:
        repo, tag = image_ref.rsplit(":", 1)
        return repo.strip(), tag.strip()
    return image_ref, ""


def _image_identity_tokens(image_ref):
    repo, tag = _split_image_ref(image_ref)
    raw_parts = [
        repo.rsplit("/", 1)[-1],
        tag,
    ]
    generic_tokens = {"iktaraai", "services", "service", "cplatform", "image", "server"}
    tokens = set()
    for raw_part in raw_parts:
        normalized = _normalize_discovery_token(raw_part)
        if normalized and normalized not in generic_tokens:
            tokens.add(normalized)
        for piece in re.split(r'[^a-z0-9]+', str(raw_part or "").strip().lower()):
            normalized_piece = _normalize_discovery_token(piece)
            if normalized_piece and normalized_piece not in generic_tokens:
                tokens.add(normalized_piece)
    return tokens


def _is_infrastructure_service_type(service_type):
    return str(service_type or "").strip() in INFRASTRUCTURE_SERVICE_CATALOG


def _equivalent_infrastructure_service_types(service_type):
    raw_type = str(service_type or "").strip()
    if not raw_type:
        return []
    return list(INFRASTRUCTURE_SERVICE_EQUIVALENTS.get(raw_type, [raw_type]))


def _load_service_install_services():
    config_path = Path(__file__).resolve().parent.parents[1] / 'config/service_install.yaml'
    with open(config_path, 'r') as fh:
        service_config_dict = yaml.load(fh, Loader=yaml.FullLoader) or {}
    return service_config_dict.get("services", {}) or {}


def _canonical_service_type(service_type):
    raw_type = str(service_type or "").strip()
    if not raw_type:
        return ""

    service_install_types = set(_load_service_install_services().keys())
    known_types = service_install_types.union(set(INFRASTRUCTURE_SERVICE_CATALOG.keys())).union({"AIOrchestrator", "cPlatform"})
    if raw_type in INFRASTRUCTURE_SERVICE_EQUIVALENTS:
        return INFRASTRUCTURE_SERVICE_EQUIVALENTS[raw_type][0]
    if raw_type in known_types:
        return raw_type

    lookup = {}
    for candidate in known_types:
        lookup.setdefault(str(candidate).lower(), candidate)
    for alias, equivalent_types in INFRASTRUCTURE_SERVICE_EQUIVALENTS.items():
        lookup.setdefault(alias.lower(), equivalent_types[0])
    return lookup.get(raw_type.lower(), raw_type)


def _normalize_service_instance_type(service_instance, requested_service_type=""):
    canonical_type = _canonical_service_type(requested_service_type or service_instance.service_type)
    if not canonical_type:
        return service_instance.service_type

    if str(service_instance.service_type or "").strip() == canonical_type:
        return canonical_type

    service_config = service_instance.service_config if isinstance(service_instance.service_config, dict) else {}
    service_config["service_type"] = canonical_type
    service_instance.service_type = canonical_type
    service_instance.service_config = service_config
    service_instance.save(update_fields=["service_type", "service_config"])
    return canonical_type


def _infra_catalog_entry(service_type):
    return INFRASTRUCTURE_SERVICE_CATALOG.get(str(service_type or "").strip(), {})


def _find_infrastructure_service_instance(node_instance, infra_service_type):
    if not node_instance:
        return None
    equivalent_types = _equivalent_infrastructure_service_types(infra_service_type)
    if not equivalent_types:
        return None
    for candidate_type in equivalent_types:
        instance = Service.objects.filter(Node=node_instance, service_type=candidate_type).first()
        if instance:
            return instance
    return None


def _infra_container_name(service_type, node_id):
    entry = _infra_catalog_entry(service_type)
    if not entry:
        return ""
    node_fragment = str(node_id or "node").strip().lower()
    return f"node-{node_fragment}-{entry['container_slug']}"


def _runtime_config(service_instance):
    service_cfg = _service_config_dict(service_instance)
    runtime = service_cfg.get("runtime", {})
    return runtime if isinstance(runtime, dict) else {}


def _runtime_container_name(service_instance):
    runtime_name = str(_runtime_config(service_instance).get("container_name") or "").strip()
    if runtime_name:
        return runtime_name
    return str(_service_config_dict(service_instance).get("container_name") or "").strip()


def _infra_runtime_binding(service_type, node_id, contract, container=None, mode="managed"):
    entry = _infra_catalog_entry(service_type)
    container = container or {}
    container_name = (
        str(container.get("name") or "").strip()
        or _infra_container_name(service_type, node_id)
    )
    return {
        "infra_mode": mode,
        "managed_by_cplatform": mode == "managed",
        "container_name": container_name,
        "container_ip": str(container.get("container_ip") or contract.get("Int_IP_Addr") or "").strip(),
        "internal_port": contract.get("Int_Port", ""),
        "network_name": str(contract.get("Network_Name") or "").strip(),
        "network_subnet": str(contract.get("Network_Subnet") or "").strip(),
        "role": entry.get("source_role", ""),
        "image": str(container.get("image") or contract.get("Image_Name") or "").strip(),
        "state": str(container.get("state") or "").strip(),
        "running": bool(container.get("running", False)),
        "discovered_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _runtime_binding_with_status(runtime, adoption_status="", validation_error="", match_confidence=0, match_basis=""):
    runtime = dict(runtime or {})
    runtime.update({
        "adoption_status": adoption_status or runtime.get("adoption_status") or "",
        "validation_error": validation_error or "",
        "match_confidence": match_confidence,
        "match_basis": match_basis or runtime.get("match_basis") or "",
        "last_validated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    return runtime


def _infra_default_service_name(service_type, node_id, service_id=""):
    entry = _infra_catalog_entry(service_type)
    if not entry:
        return f"{service_type}_{service_id}" if service_id else str(service_type or "")
    node_fragment = str(node_id or "node").strip()
    return f"{entry['container_slug'].replace('-', '_')}_{node_fragment}"


def _get_infrastructure_contract(service_type):
    entry = _infra_catalog_entry(service_type)
    if not entry:
        return {}

    services = _load_service_install_services()
    source_service = entry.get("source_service")
    source_role = entry.get("source_role")
    docker_info = services.get(source_service, {}).get("Docker_Info", {})
    # AgenticNOC used to expose four infrastructure roles. Keep old catalog
    # records usable after the roles were collapsed into one ordinary
    # contract, and never let their compatibility metadata launch a second
    # role container.
    legacy_alias = entry.get("legacy_alias_of")
    source_contract = (
        docker_info.get(legacy_alias, {})
        if legacy_alias
        else docker_info.get(source_role, {})
    )
    if not isinstance(source_contract, dict) or not source_contract:
        source_contract = docker_info.get(source_role, {})
    if not isinstance(source_contract, dict):
        return {}

    contract = deepcopy(source_contract)
    contract["Role"] = source_role
    contract["Deployment_Mode"] = "INFRA_ONLY"
    contract["Config_Push_Required"] = False
    contract["Publish_Port"] = False
    # These values are deployment defaults, not immutable runtime settings.
    # The service card/API may override the network name and container IP for
    # an existing node network, while an empty container_ip requests Docker's
    # next address from the network pool.
    contract.setdefault("Network_Name", "cplatform_iktara_cPlatform")
    contract.setdefault("Network_Subnet", "180.75.0.0/24")
    return contract


def service_get_infrastructure_contract(service_type):
    return deepcopy(_get_infrastructure_contract(service_type))


def service_get_infrastructure_container_name(service_type, node_id):
    return _infra_container_name(service_type, node_id)


def service_get_infrastructure_catalog():
    catalog = []
    for service_type, entry in INFRASTRUCTURE_SERVICE_CATALOG.items():
        if entry.get("catalog_visible", True) is False:
            continue
        contract = _get_infrastructure_contract(service_type)
        if not contract:
            continue
        catalog.append({
            "service_type": service_type,
            "display_name": entry["display_name"],
            "source_role": entry["source_role"],
            "category": entry.get("category", "service"),
            "container_slug": entry.get("container_slug", ""),
            "image": contract.get("Image_Name", ""),
            "version": contract.get("Image_Ver", "1.0.0"),
            "display_version": INFRA_SERVICE_VERSIONS.get(service_type, contract.get("Image_Ver", "1.0.0")),
            "internal_port": contract.get("Int_Port", ""),
            "default_expose_service": _coerce_bool(contract.get("Default_Expose_Service", False)),
            "default_host_port": str(contract.get("Default_Host_Port", "") or ""),
            "container_ip": str(contract.get("Int_IP_Addr", "") or ""),
            "network_name": str(contract.get("Network_Name", "") or ""),
            "network_subnet": str(contract.get("Network_Subnet", "") or ""),
        })
    return catalog

# optimized function
def _get_infrastructure_contract_v2(service_type, services):
    entry = _infra_catalog_entry(service_type)
    if not entry:
        return {}

    source_service = entry.get("source_service")
    source_role = entry.get("source_role")
    docker_info = services.get(source_service, {}).get("Docker_Info", {})
    legacy_alias = entry.get("legacy_alias_of")
    source_contract = (
        docker_info.get(legacy_alias, {})
        if legacy_alias
        else docker_info.get(source_role, {})
    )
    if not isinstance(source_contract, dict) or not source_contract:
        source_contract = docker_info.get(source_role, {})

    if not isinstance(source_contract, dict):
        return {}

    contract = deepcopy(source_contract)
    contract["Role"] = source_role
    contract["Deployment_Mode"] = "INFRA_ONLY"
    contract["Config_Push_Required"] = False
    contract["Publish_Port"] = False
    contract.setdefault("Network_Name", "cplatform_iktara_cPlatform")
    contract.setdefault("Network_Subnet", "180.75.0.0/24")

    return contract


def service_get_infrastructure_catalog_v2():
    """
    Optimized version.
    Loads service_install.yaml only once and reuses it
    for all infrastructure services.
    """
    services = _load_service_install_services()
    catalog = []
    for service_type, entry in INFRASTRUCTURE_SERVICE_CATALOG.items():
        if entry.get("catalog_visible", True) is False:
            continue

        contract = _get_infrastructure_contract_v2(service_type, services,)
        if not contract:
            continue

        catalog.append({
            "service_type": service_type,
            "display_name": entry["display_name"],
            "source_role": entry["source_role"],
            "category": entry.get("category", "service"),
            "container_slug": entry.get("container_slug", ""),
            "image": contract.get("Image_Name", ""),
            "version": contract.get("Image_Ver", "1.0.0"),
            "display_version": INFRA_SERVICE_VERSIONS.get(
                service_type, contract.get("Image_Ver", "1.0.0"),
            ),
            "internal_port": contract.get("Int_Port", ""),
            "default_expose_service": _coerce_bool(contract.get("Default_Expose_Service", False)),
            "default_host_port": str(contract.get("Default_Host_Port", "") or ""),
            "container_ip": str(contract.get("Int_IP_Addr", "") or ""),
            "network_name": str(contract.get("Network_Name", "") or ""),
            "network_subnet": str(contract.get("Network_Subnet", "") or ""),
        })
    return catalog


def _service_config_dict(service_instance):
    return service_instance.service_config if isinstance(getattr(service_instance, "service_config", {}), dict) else {}


def _runtime_service_name(service_instance):
    return str(service_instance.service_type or service_instance.service_name or service_instance.service_id or "").strip()


def _runtime_service_version(service_instance):
    return str(service_instance.service_version or _service_config_dict(service_instance).get("service_version") or "latest").strip() or "latest"


def _resolve_contract_value(raw_value, service_instance):
    value = str(raw_value or "")
    if not value:
        return ""

    service_cfg = _service_config_dict(service_instance)
    node_instance = getattr(service_instance, "Node", None)
    node_volume = getattr(node_instance, "node_volume", "") if node_instance else ""
    service_volume = str(service_cfg.get("service_volume") or node_volume or "/home/ubuntu/Backup_Platform")
    if _is_infrastructure_service_type(getattr(service_instance, "service_type", "")) and service_volume.rstrip("/") in ["", "/tmp"]:
        service_volume = str(node_volume or "/home/ubuntu/Backup_Platform")
    machine_volume = str(service_cfg.get("machine_volume") or node_volume or service_volume)
    replacements = {
        "{{ service_volume }}": service_volume.rstrip("/"),
        "{{ machine_volume }}": machine_volume.rstrip("/"),
        "{{ service }}": str(getattr(service_instance, "service_type", "") or ""),
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _resolve_contract_paths(path_values, service_instance):
    resolved = []
    for path_value in _string_list(path_values):
        candidate = _resolve_contract_value(path_value, service_instance).strip()
        if candidate:
            resolved.append(candidate)
    return resolved


def _contract_observability_file_paths(contract, service_instance):
    observability = contract.get("Observability", {}) if isinstance(contract, dict) else {}
    file_logs = observability.get("file_logs", {}) if isinstance(observability, dict) else {}
    return _resolve_contract_paths(file_logs.get("paths"), service_instance)


def _contract_volume_roots(contract, service_instance):
    roots = []
    seen = set()
    for volume in _string_list((contract or {}).get("Volumes")):
        host_path = _resolve_contract_value(volume.split(":", 1)[0], service_instance).strip()
        if not host_path or not host_path.startswith("/"):
            continue
        if host_path.endswith(".conf") or host_path.endswith(".yaml") or host_path.endswith(".yml") or host_path.endswith(".json"):
            host_path = str(Path(host_path).parent)
        if host_path not in seen:
            seen.add(host_path)
            roots.append(host_path)
    return roots


def _contract_has_config_files(contract):
    config_files = (contract or {}).get("Config_Files")
    if isinstance(config_files, dict):
        return bool(config_files)
    if isinstance(config_files, list):
        return bool(config_files)
    return False


def _contract_config_path(service_type, contract):
    service_type = str(service_type or "").strip()
    if service_type in INFRASTRUCTURE_CONFIG_PATHS:
        return INFRASTRUCTURE_CONFIG_PATHS[service_type]
    if _contract_has_config_files(contract):
        config_files = contract.get("Config_Files")
        if isinstance(config_files, dict):
            first_value = next(iter(config_files.values()), {})
            if isinstance(first_value, dict):
                return str(first_value.get("dest") or first_value.get("Container_Relative_Path") or "").strip()
        if isinstance(config_files, list) and config_files:
            first_value = config_files[0]
            if isinstance(first_value, dict):
                return str(first_value.get("dest") or first_value.get("Container_Relative_Path") or "").strip()
    return ""


def _config_capabilities(service_instance, contract, target_scope="main"):
    service_type = str(service_instance.service_type or "").strip()
    is_infra = _is_infrastructure_service_type(service_type)
    config_path = _contract_config_path(service_type, contract)
    has_explicit_config = bool(config_path or _contract_has_config_files(contract))
    infra_without_config = is_infra and not has_explicit_config
    config_path_l = str(config_path or "").lower()
    config_is_yaml = config_path_l.endswith(".yaml") or config_path_l.endswith(".yml")

    snapshot_enabled = bool(service_instance.Node and (not is_infra or has_explicit_config))
    apply_enabled = bool(service_instance.Node and (not is_infra or has_explicit_config))
    disabled_reason = ""
    if not service_instance.Node:
        disabled_reason = "Service is not mapped to a node"
    elif is_infra and infra_without_config:
        disabled_reason = "This infrastructure service has no explicit editable runtime config path"

    return {
        "snapshot_enabled": snapshot_enabled,
        "apply_enabled": apply_enabled,
        "restore_enabled": apply_enabled,
        "restart_required": bool(is_infra),
        "config_path": config_path,
        "config_is_yaml": config_is_yaml,
        "disabled_reason": disabled_reason,
        "target_scope": target_scope,
        "requires_become_for_files": True,
    }


def service_get_runtime_container_name(service_instance):
    node_instance = service_instance.Node
    service_type = str(service_instance.service_type or "").strip()
    if service_type in ["AIOrchestrator", "cPlatform"]:
        return "iktara_cPlatform"
    runtime_container = _runtime_container_name(service_instance)
    if runtime_container:
        return runtime_container
    if _is_infrastructure_service_type(service_type):
        return _infra_container_name(service_type, node_instance.node_id if node_instance else "")
    return service_instance.service_id


def service_get_runtime_main_target(service_instance, live_status=None):
    node_instance = service_instance.Node
    service_type = str(service_instance.service_type or "").strip()
    contract, _dependencies = _get_service_docker_contract(service_type)
    container_name = service_get_runtime_container_name(service_instance)
    live_main = (live_status or {}).get("main_container", {}) if isinstance(live_status, dict) else {}
    if live_main.get("name") and not _is_infrastructure_service_type(service_type):
        container_name = live_main.get("name")

    runtime = _runtime_config(service_instance)
    infra_mode = str(runtime.get("infra_mode") or _service_config_dict(service_instance).get("infra_mode") or "").strip()
    display_name = _infra_catalog_entry(service_type).get("display_name") if _is_infrastructure_service_type(service_type) else ""
    label = f"{display_name or 'Main Container'} ({container_name})"
    file_paths = _contract_observability_file_paths(contract, service_instance)
    return {
        "target_id": "main",
        "label": label,
        "container_name": container_name,
        "source_type": (
            f"Infrastructure Card ({infra_mode})"
            if _is_infrastructure_service_type(service_type) and infra_mode
            else ("Infrastructure Card" if _is_infrastructure_service_type(service_type) else "Main Container")
        ),
        "dependency_name": "",
        "dependency_contract_name": "",
        "contract_role": contract.get("Role", service_type),
        "node_id": node_instance.node_id if node_instance else "",
        "node_ip": _normalize_node_ip(getattr(node_instance, "node_ip", "")) if node_instance else "",
        "inspectable": True,
        "file_log_paths": file_paths,
        "volume_roots": _contract_volume_roots(contract, service_instance),
        "config_capabilities": _config_capabilities(service_instance, contract, target_scope="main"),
        "config_service_name": _runtime_service_name(service_instance),
        "config_version": _runtime_service_version(service_instance),
    }


def service_get_runtime_config_target(service_instance):
    return service_get_runtime_main_target(service_instance)


def service_get_runtime_config_capabilities(service_id):
    if not Service.objects.filter(service_id=service_id).exists():
        return {"snapshot_enabled": False, "apply_enabled": False, "restore_enabled": False, "disabled_reason": "Service does not exist"}
    service_instance = Service.objects.get(service_id=service_id)
    return service_get_runtime_config_target(service_instance).get("config_capabilities", {})


def _deploy_timer_name(service_id):
    return f"Service_Deploy-{service_id}"


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _update_service_deploy_timer_arg(service_id, timer_arg):
    timer_name = _deploy_timer_name(service_id)
    PeriodicTask.objects.filter(name=timer_name).update(args=json.dumps([timer_arg]))


def _stop_service_deploy_timer(service_id, reason, ser_ins=None):
    timer_name = _deploy_timer_name(service_id)
    cutil_timer_stop(timer_name)

    if reason == "deployment_succeeded":
        stop_msg = "Timer stopped: success"
    elif reason.startswith("terminal_failure:"):
        stop_msg = f"Timer stopped: terminal failure - {reason.split(':', 1)[1]}"
    elif reason.startswith("max_retries_exceeded"):
        stop_msg = "Timer stopped: max retries exceeded"
    else:
        stop_msg = f"Timer stopped: {reason}"

    if ser_ins:
        service_event_add_request(ser_ins, "Deploy Timer", stop_msg)
    app_logger.info(f"{timer_name} -> {stop_msg}")


def _is_terminal_deploy_failure(msg: str) -> bool:
    msg_l = (msg or "").lower()
    terminal_markers = [
        "does not exist",
        "service requirements not satisfied",
        "not configured for ansible",
        "not compatible for service",
        "requirements not met",
        "invalid",
        "missing config",
        "deployment blocked",
    ]
    return any(marker in msg_l for marker in terminal_markers)


def _is_transient_deploy_failure(msg: str) -> bool:
    msg_l = (msg or "").lower()
    transient_markers = [
        "system info retrieval failed",
        "service config push failed",
        "timeout",
        "network",
        "connection",
        "temporar",
        "failed to deploy service",
        "request",
    ]
    return any(marker in msg_l for marker in transient_markers)


def _handle_deploy_failure(ser_ins, timer_arg, msg):
    service_id = timer_arg.get('service_id')

    if _is_terminal_deploy_failure(msg):
        _stop_service_deploy_timer(service_id, f"terminal_failure:{msg}", ser_ins)
        return False, msg

    if _is_transient_deploy_failure(msg):
        retry_count = _safe_int(timer_arg.get('retry_count'), 0) + 1
        max_retry = max(1, _safe_int(timer_arg.get('max_retry'), SERVICE_DEPLOY_MAX_RETRY))

        timer_arg['retry_count'] = retry_count
        timer_arg['max_retry'] = max_retry
        _update_service_deploy_timer_arg(service_id, timer_arg)

        if retry_count >= max_retry:
            _stop_service_deploy_timer(service_id, "max_retries_exceeded", ser_ins)
        elif ser_ins:
            service_event_add_request(
                ser_ins,
                "Deploy Timer",
                f"Retrying deployment ({retry_count}/{max_retry}) due to: {msg}",
            )
        return False, msg

    _stop_service_deploy_timer(service_id, f"terminal_failure:{msg}", ser_ins)
    return False, msg


def _get_service_default(service_type):
    file_path = os.path.join(Path(__file__).resolve().parent.parent, 'forms')
    f = open(file_path + '/dFormService.json')
    ser_schema = json.load(f)
    service_config = {}
    if service_type in ser_schema:
        row_schema = ser_schema[service_type].get("properties", [])
        for key, value in row_schema.items():
            field_name = value.get("f_name")
            default_value = value.get("v_default", "")
            if field_name:
                service_config[field_name] = default_value

    if not service_config and _is_infrastructure_service_type(service_type):
        contract = _get_infrastructure_contract(service_type)
        entry = _infra_catalog_entry(service_type)
        service_config = {
            "service_name": "",
            "service_type": service_type,
            "service_port": contract.get("Int_Port", 0) or 0,
            "host_port": str(contract.get("Default_Host_Port", "") or ""),
            "expose_service": _coerce_bool(contract.get("Default_Expose_Service", False)),
            "container_ip": str(contract.get("Int_IP_Addr", "") or ""),
            "network_name": str(contract.get("Network_Name", "") or ""),
            "network_subnet": str(contract.get("Network_Subnet", "") or ""),
            "service_volume": "/tmp",
            "service_install": "ANSIBLE",
            "deploy_status": "NOT DEPLOYED",
            "service_debug": "DISABLE",
            "service_version": contract.get("Image_Ver", "1.0.0"),
            "service_category": "Infrastructure",
            "infrastructure_role": entry.get("source_role", ""),
            "external_port_required": False,
        }

    return service_config


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ["1", "true", "yes", "on"]


def _normalize_infra_exposure_config(service_type, service_config):
    config = dict(service_config or {})
    if not _is_infrastructure_service_type(service_type):
        return True, "", config

    expose_service = _coerce_bool(config.get("expose_service", False))
    config["expose_service"] = expose_service

    host_port = str(config.get("host_port", "") or "").strip()
    if not expose_service:
        config["host_port"] = ""
        return True, "", config

    if not host_port:
        return False, "Host port is required when exposing an infrastructure service.", config

    if not host_port.isdigit():
        return False, "Host port must be a numeric value.", config

    host_port_int = int(host_port)
    if host_port_int < 1 or host_port_int > 65535:
        return False, "Host port must be between 1 and 65535.", config

    config["host_port"] = str(host_port_int)
    return True, "", config

def _read_yaml_file(file_path):
    yaml_content = {}
    try:
        with open(file_path, 'r') as file:
            yaml_content = yaml.safe_load(file)
    except FileNotFoundError:
        app_logger.debug(f"The file '{file_path}' does not exist.")
    except Exception as e:
        app_logger.debug(f"An error occurred: {e}")
    return yaml_content


def _normalize_node_ip(node_ip):
    return str(node_ip).split('/')[0] if node_ip else ""


def _get_service_docker_contract(service_type):
    infra_contract = _get_infrastructure_contract(service_type)
    if infra_contract:
        return infra_contract, []

    service_config_dict = {"services": _load_service_install_services()}
    docker_info = service_config_dict.get("services", {}).get(service_type, {}).get("Docker_Info", {})
    main_info = docker_info.get(service_type, {}) or {}
    dependencies = []

    for role, cfg in docker_info.items():
        if role == service_type or not isinstance(cfg, dict) or cfg.get("Legacy_Alias_Of"):
            continue
        dependencies.append({
            "role": role,
            "ip": cfg.get("Int_IP_Addr", ""),
            "port": cfg.get("Int_Port"),
        })

    return main_info, dependencies


def _get_dependency_contract_by_name(service_type, dependency_name):
    _, dependencies = _get_service_docker_contract(service_type)
    dependency_name_l = str(dependency_name or "").lower()

    for dependency in dependencies:
        if str(dependency.get("role", "")).lower() == dependency_name_l:
            return dependency
    return {}


def _find_node_by_host(target_host):
    if not target_host:
        return None

    normalized_host = _normalize_node_ip(target_host)
    for node in Node.objects.all():
        if _normalize_node_ip(node.node_ip) == normalized_host:
            return node
    return None


def _resolve_managed_dependency_status(service_instance, dependency):
    target_host = dependency.get("target_host")
    node_instance = _find_node_by_host(target_host)
    if not node_instance:
        dependency["resolved_node_id"] = ""
        dependency["resolved_node_ip"] = ""
        dependency["error"] = dependency.get("error", "") or ""
        return dependency

    dependency_contract = _get_dependency_contract_by_name(service_instance.service_type, dependency.get("name"))
    dependency["resolved_node_id"] = node_instance.node_id
    dependency["resolved_node_ip"] = _normalize_node_ip(node_instance.node_ip)

    status_payload = serviceInstall.sInstall_get_service_live_status(
        service_instance,
        node_instance.node_id,
        dependency_contract.get("port"),
        [],
        "",
        dependency.get("name"),
        dependency.get("target_port"),
    )

    if status_payload.get("error"):
        dependency["source_type"] = "Managed External"
        dependency["state"] = "Unknown"
        dependency["container_name"] = ""
        dependency["image"] = ""
        dependency["container_ip"] = ""
        dependency["created_at"] = ""
        dependency["running_since"] = ""
        dependency["restart_count"] = 0
        dependency["exit_code"] = None
        dependency["oom_killed"] = False
        dependency["error"] = status_payload.get("error")
        return dependency

    managed_container = status_payload.get("main_container", {}) or {}
    dependency["source_type"] = "Managed External"
    dependency["container_name"] = managed_container.get("name", "")
    dependency["state"] = managed_container.get("state", "Unknown")
    dependency["image"] = managed_container.get("image", "")
    dependency["container_ip"] = managed_container.get("container_ip", "")
    dependency["created_at"] = managed_container.get("created_at", "").split("T")[0] + " " + \
                               managed_container.get("created_at", "").split("T")[1][:8] if managed_container.get(
        "created_at") else ""
    dependency["running_since"] = managed_container.get("running_since", "").split("T")[0] + " " + \
                                  managed_container.get("running_since", "").split("T")[1][:8] if managed_container.get(
        "running_since") else ""
    dependency["restart_count"] = managed_container.get("restart_count", 0)
    dependency["exit_code"] = managed_container.get("exit_code")
    dependency["oom_killed"] = managed_container.get("oom_killed", False)
    dependency["error"] = status_payload.get("error", "") or ""
    return dependency


def _derive_overall_status(main_container, dependencies):
    if not main_container.get("name"):
        return "Missing"

    main_state = main_container.get("state", "missing")
    if main_state in ["missing", "unknown"]:
        return "Missing"
    if main_state in ["exited", "dead", "restarting"]:
        return "Stopped"

    degraded = False
    if main_state != "running":
        degraded = True
    if not main_container.get("expected_port_listening", False):
        degraded = True
    if main_container.get("oom_killed", False):
        degraded = True
    if int(main_container.get("restart_count", 0) or 0) > 0:
        degraded = True

    for dependency in dependencies:
        source_type = dependency.get("source_type")
        dep_state = str(dependency.get("state", "") or "").lower()
        if dependency.get("name") == "AirflowInit" and dependency.get("satisfied"):
            continue
        if source_type == "Local Container" and dep_state != "running":
            degraded = True
            break
        if source_type == "Managed External" and dep_state and dep_state not in ["running", "unknown", "external"]:
            degraded = True
            break

    return "Degraded" if degraded else "Healthy"


def service_network_state(service_name):
    service_instance = Service.objects.filter(service_name=service_name).first()

    if not service_instance:
        return "LOCAL"  # Default to LOCAL if service not found

    node = service_instance.Node

    ai_orchestrator_exists = Service.objects.filter(
        Node=node,
        service_type__in=["AIOrchestrator", "cPlatform"]
    ).exclude(service_name=service_name).exists()

    return "LOCAL" if ai_orchestrator_exists else "REMOTE"

# Determine the IP and port of a service based on deployment type and network state.
def service_get_route(service_instance):
    from cPlatformIO.src.PlatformSetting import PlatformSettings
    if PlatformSettings.deployment_type.upper() == 'LOCAL':
        return True, '127.0.0.1', service_instance.service_port

    config_root = Path(__file__).resolve().parents[2] / 'config'

    config_data = _read_yaml_file(str(config_root / 'cPlatform_config.yaml'))
    deployment_type = config_data.get('CPLATFORM_CONFIG', {}).get('deployment_type', '').upper()

    service_name = service_instance.service_name
    service_type = service_instance.service_type

    if deployment_type == 'DOCKER' and service_network_state(service_name) == 'LOCAL':
        docker_config = _read_yaml_file(str(config_root / 'service_install.yaml'))
        docker_info = docker_config["services"].get(service_type, {}).get("Docker_Info", {}).get(service_type)

        if docker_info:
            return True, docker_info.get("Int_IP_Addr"), docker_info.get("Int_Port")
        else:
            app_logger.error(f"[service_get_route] Missing Docker info for service type: {service_type}")
            return False, None, None

    # This is the fallback (non-DOCKER or REMOTE) case.
    return True, service_instance.Node.node_ip, service_instance.service_port


def _update_orchestrator_config(request_info):

    ser_ins = Service.objects.get(service_id=request_info.get('service_id'))
    PlatformConfig.platform_update_config(ser_ins, request_info)

    # Update CommonUtils log_level
    LogMgr.commonutils_update_logger_level('cplatform_server', request_info['service_debug'])
    LogMgr.commonutils_update_logger_level('cplatform_celery', request_info['service_debug'])

    # Update CommonUtils Config
    ret, msg = Cutilinit.update_commonutils_config()

    # Update MCPClient Config
    ret, msg = McpclInit.update_mcpclient_config()

    return ret, msg


def _send_service_config_api(service_name, service_port):
    app_logger.debug(f"_send_service_config_api: service_name={service_name}, service_port={service_port}")

    service_instance = Service.objects.filter(service_name=service_name).first()
    if not service_instance:
        app_logger.warning(f"Service not found: {service_name}")
        return

    service_type = service_instance.service_type
    req_data = dict(service_instance.service_config or {})
    repo_sync = service_network_state(service_name)
    msg, host, port = service_get_route(service_instance)

    req_data.update({
        'service_ip': host,
        'service_port': port,
        'service_ip_ext': service_instance.Node.node_ip,
        'service_port_ext': service_port,
        'service_debug': service_instance.service_debug,
        'cplatform_url': PlatformSettings.cplatform_url,
        'master_host': PlatformSettings.master_host,
        'master_username': PlatformSettings.master_username,
        'master_password': PlatformSettings.master_password,
        'master_auth_type': PlatformSettings.master_auth_type,
        'master_pem_file_name': PlatformSettings.master_pem_file_name,
        'master_pem_file_text': PlatformSettings.master_pem_file_text,
        'master_path': PlatformSettings.master_path,
        'orchestrator_url': PlatformSettings.master_host or PlatformSettings.cplatform_url,
        'orchestrator_host': PlatformSettings.master_host or PlatformSettings.cplatform_url,
        'orchestrator_username': PlatformSettings.master_username,
        'orchestrator_password': PlatformSettings.master_password,
        'orchestrator_auth_type': PlatformSettings.master_auth_type,
        'orchestrator_pem_file_name': PlatformSettings.master_pem_file_name,
        'orchestrator_pem_file': PlatformSettings.master_pem_file_text,
        'orchestrator_path': PlatformSettings.master_path,
        'mcp_url': PlatformSettings.mcp_url,
        'text2sql_url':PlatformSettings.text2sql_url,
        'repo_role': 'Secondary',
        'repo_sync': repo_sync,
        'prometheus_server_ip': PlatformSettings.prometheus_server_ip,
        'prometheus_server_port': PlatformSettings.prometheus_server_port
    })

    # Backward compatibility for older TTS UpdateService payload contracts.
    if service_type == "TTS":
        req_data.setdefault("model_key", req_data.get("load_model"))
        req_data.setdefault("no_of_cpu", req_data.get("num_cpu", 1))
        req_data.setdefault("no_of_gpu", req_data.get("num_gpu", 0))

    # Map cPlatform fields to optionCopilot expectation
    if service_type == "optionCopilot":
        inf_server_name = req_data.get("inference_server")
        inf_serv_info = {}
        if inf_server_name:
            inf_serv_inst = Service.objects.filter(service_name=inf_server_name).first()
            if inf_serv_inst:
                inf_serv_info = {
                    "inf_service_name": str(inf_serv_inst.service_name),
                    "inf_service_port": str(inf_serv_inst.service_port),
                    "inf_service_ip": str(inf_serv_inst.Node.node_ip)
                }
        req_data["inference_serv_info"] = json.dumps(inf_serv_info)

        model_name = req_data.get("model_name")
        model_info = {}
        if model_name:
            from cPlatformIO.models import ModelInfo
            model_inst = ModelInfo.objects.filter(model_name=model_name).first()
            if model_inst:
                model_end_date = None
                if hasattr(model_inst, 'dataset_config') and model_inst.dataset_config:
                    date_range = model_inst.dataset_config.get("date_range")
                    if isinstance(date_range, str) and " - " in date_range:
                        model_end_date = date_range.split(" - ")[-1].strip()
                model_info = {
                    "model_name": str(model_inst.model_name),
                    "model_id": str(model_inst.model_id),
                    "model_end_date": str(model_end_date)
                }
        req_data["model_info"] = json.dumps(model_info)
        req_data["inference_flag"] = req_data.get("inference_flag", "No")

    main_contract, _ = _get_service_docker_contract(service_type)
    config_push_path = str(
        main_contract.get("Config_Push_Path")
        or f"/{service_type}/APIv1/UpdateService/"
    ).strip()
    if not config_push_path.startswith("/"):
        config_push_path = f"/{config_push_path}"
    service_url = f"http://{host}:{port}{config_push_path}"
    try:
        response = requests.post(url=service_url, json=req_data, timeout=30, verify=False)
        app_logger.debug(f"Service Config API Response for {service_name}: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        app_logger.error(f"Failed to send config to {service_name} at {service_url}: {e}")
        response = None

    return response


def _parse_bool(value, default=False):
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in ["1", "true", "yes", "on"]:
        return True
    if normalized in ["0", "false", "no", "off"]:
        return False
    return default


def _is_infra_only_service(ser_ins):
    main_contract, _ = _get_service_docker_contract(ser_ins.service_type)
    deployment_mode = str(main_contract.get("Deployment_Mode", "")).strip().upper()
    if deployment_mode == "INFRA_ONLY":
        return True
    return ser_ins.service_type == "Airflow"


def _service_requires_config_push(ser_ins):
    main_contract, _ = _get_service_docker_contract(ser_ins.service_type)
    config_push_required = main_contract.get("Config_Push_Required")
    if config_push_required is None:
        return not _is_infra_only_service(ser_ins)
    return _parse_bool(config_push_required, default=True)


def _service_wait_for_health(ser_ins):
    main_contract, _ = _get_service_docker_contract(ser_ins.service_type)
    health_cfg = main_contract.get("Health_Check", {}) if isinstance(main_contract.get("Health_Check", {}), dict) else {}
    if not _parse_bool(health_cfg.get("Enabled"), default=False):
        return True, "Health check disabled"

    path = str(health_cfg.get("Path", "/")).strip() or "/"
    if not path.startswith("/"):
        path = f"/{path}"

    timeout_sec = max(10, _safe_int(health_cfg.get("Timeout_Sec"), 180))
    interval_sec = max(1, _safe_int(health_cfg.get("Interval_Sec"), 5))
    expected_codes = health_cfg.get("Status_Code", [200])
    if not isinstance(expected_codes, list):
        expected_codes = [expected_codes]
    expected_codes = {int(code) for code in expected_codes if str(code).isdigit()}
    if not expected_codes:
        expected_codes = {200}

    msg, host, port = service_get_route(ser_ins)
    if not msg or not host or not port:
        return False, "Health check route unavailable"

    url = f"http://{host}:{port}{path}"
    start_time = time.monotonic()
    while (time.monotonic() - start_time) < timeout_sec:
        try:
            response = requests.get(url=url, timeout=min(interval_sec, 10), verify=False)
            if response.status_code in expected_codes:
                return True, f"Health check passed ({response.status_code})"
        except requests.RequestException:
            pass
        time.sleep(interval_sec)

    return False, f"Health check timed out for {url}"


def _required_infrastructure_service_types(service_type):
    if _is_infrastructure_service_type(service_type):
        return []
    return SERVICE_INFRASTRUCTURE_DEPENDENCIES.get(service_type, [])


def _discovered_container_names(node_id, discovered_containers=None):
    if discovered_containers is not None:
        return {
            str(container.get("name") or "").strip()
            for container in discovered_containers
            if str(container.get("name") or "").strip()
        }

    try:
        discovery = serviceInstall.sInstall_discover_infrastructure_containers(node_id)
        if not discovery.get("success"):
            return set()
        return {
            str(container.get("name") or "").strip()
            for container in discovery.get("containers", [])
            if str(container.get("name") or "").strip()
        }
    except Exception as e:
        app_logger.error(f"Error in _discovered_container_names calling discovery: {e}")
        return set()


def _reserved_runtime_names(node_id, discovered_containers=None):
    reserved = set()
    for service in Service.objects.filter(Node__node_id=node_id):
        runtime_name = _runtime_container_name(service)
        if runtime_name:
            reserved.add(runtime_name)
    reserved.update(_discovered_container_names(node_id, discovered_containers=discovered_containers))
    return reserved


def _allocate_service_id(node_id, service_idx, discovered_containers=None):
    existing_ids = {
        str(service_id).strip()
        for service_id in Service.objects.exclude(service_id__isnull=True).values_list("service_id", flat=True)
        if str(service_id).strip()
    }
    reserved_runtime_names = _reserved_runtime_names(node_id, discovered_containers=discovered_containers)

    candidate_num = SERVICE_BASE_IDX + int(service_idx)
    while True:
        candidate = f"SERV{candidate_num}"
        if candidate not in existing_ids and candidate not in reserved_runtime_names:
            return candidate
        candidate_num += 1


def _container_matches_service(container, service_type, contract, is_infra=True):
    name = str(container.get("name") or "").lower()
    image = str(container.get("image") or "").lower()
    haystack = f"{name} {image}"

    for blocked_marker in INFRASTRUCTURE_DISCOVERY_BLOCKED_MARKERS:
        if blocked_marker and blocked_marker in haystack:
            return 0, "blocked_marker"

    excludes = INFRASTRUCTURE_DISCOVERY_EXCLUDES.get(service_type, []) if is_infra else []
    for excluded in excludes:
        if excluded and excluded.lower() in haystack:
            return 0, "excluded_marker"

    hints = INFRASTRUCTURE_DISCOVERY_HINTS.get(service_type, []) if is_infra else [service_type.lower()]
    expected_tokens = set(hints)
    expected_tokens.update(_image_identity_tokens(contract.get("Image_Name", "")))
    expected_tokens = {
        _normalize_discovery_token(token)
        for token in expected_tokens
        if _normalize_discovery_token(token)
    }

    candidate_tokens = set()
    candidate_tokens.update(_image_identity_tokens(container.get("image", "")))
    candidate_tokens.update(
        _normalize_discovery_token(piece)
        for piece in re.split(r'[^a-z0-9]+', name)
        if _normalize_discovery_token(piece)
    )
    if expected_tokens and not (expected_tokens & candidate_tokens):
        return 0, "image_identity_mismatch"

    score = 0
    match_basis = []
    expected_ip = str(contract.get("Int_IP_Addr") or "").strip()
    actual_ip = str(container.get("container_ip") or "").strip()
    if expected_ip:
        if actual_ip != expected_ip:
            return 0, "expected_ip_mismatch"
        score += 100
        match_basis.append("expected_ip")

    expected_port = str(contract.get("Int_Port") or "").strip()
    exposed_ports = {str(port) for port in container.get("exposed_ports", [])}
    host_ports = {str(port) for port in container.get("host_ports", [])}
    if expected_port and (expected_port in exposed_ports or expected_port in host_ports):
        score += 15
        match_basis.append("expected_port")

    for hint in hints:
        normalized_hint = str(hint or "").lower()
        if normalized_hint and normalized_hint in name:
            score += 10
            match_basis.append(f"name:{normalized_hint}")
        elif normalized_hint and normalized_hint in image:
            score += 8
            match_basis.append(f"image:{normalized_hint}")

    expected_image_tokens = _image_identity_tokens(contract.get("Image_Name", ""))
    if expected_image_tokens and expected_image_tokens & candidate_tokens:
        score += 25
        match_basis.append("image_family")

    # Image version match
    version_tags = []
    if "Image_Ver_List" in contract:
        version_tags = [str(v) for v in contract.get("Image_Ver_List", [])]
    elif "Image_Ver" in contract:
        version_tags = [str(contract.get("Image_Ver"))]

    matched_version = False
    for v_tag in version_tags:
        expected_version = _normalize_discovery_token(v_tag)
        if expected_version and expected_version in _normalize_discovery_token(image):
            matched_version = True
            break
    if matched_version:
        score += 5
        match_basis.append("image_version")

    expected_name = _infra_container_name(service_type, "")
    container_name = str(container.get("name") or "").strip().lower()
    if expected_name and container_name.endswith(expected_name.lower()):
        score += 20
        match_basis.append("canonical_name")

    if container.get("running"):
        score += 5
        match_basis.append("running")

    return (score if score >= 30 else 0), ",".join(match_basis)


def _select_service_container(discovered_containers, service_type, contract, is_infra=True):
    scored = []
    for container in discovered_containers:
        score, basis = _container_matches_service(container, service_type, contract, is_infra=is_infra)
        if score:
            scored.append((score, container, basis))
    if not scored:
        return None, {"reason": "no_valid_candidate", "match_confidence": 0, "match_basis": ""}
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, {"reason": "ambiguous_match", "match_confidence": scored[0][0], "match_basis": scored[0][2]}
    return scored[0][1], {"reason": "", "match_confidence": scored[0][0], "match_basis": scored[0][2]}


def _apply_adopted_service(node_instance, service_type, container, is_infra=True, adoption_status="adopted", validation_error="", discovered_containers=None, existing_instance=None, match_confidence=0, match_basis=""):
    if is_infra:
        contract = _get_infrastructure_contract(service_type)
        entry = _infra_catalog_entry(service_type)
    else:
        contract, _ = _get_service_docker_contract(service_type)
        entry = {"display_name": service_type, "source_role": contract.get("Role", "Primary"), "category": "Main"}

    if not contract:
        return None, "skipped"

    service_instance = existing_instance or Service.objects.filter(Node=node_instance, service_type=service_type).first()
    created = False
    if not service_instance:
        service_instance = Service.objects.create(Node=node_instance, service_type=service_type)
        service_instance.service_id = _allocate_service_id(
            node_instance.node_id,
            service_instance.service_idx,
            discovered_containers=discovered_containers,
        )
        created = True

    is_already_managed = False
    if existing_instance:
        existing_cfg = existing_instance.service_config if isinstance(existing_instance.service_config, dict) else {}
        if existing_cfg.get("infra_mode") == "managed" or existing_cfg.get("managed_by_cplatform") is True:
            is_already_managed = True

    infra_mode_val = "managed" if is_already_managed else "adopted"
    managed_by_cplatform_val = True if is_already_managed else False

    if created and not is_infra:
        service_cfg = _get_service_default(service_type)
    else:
        service_cfg = service_instance.service_config if isinstance(service_instance.service_config, dict) else {}

    runtime = _infra_runtime_binding(
        service_type,
        node_instance.node_id,
        contract,
        container=container,
        mode=infra_mode_val,
    )
    runtime = _runtime_binding_with_status(
        runtime,
        adoption_status=adoption_status,
        validation_error=validation_error,
        match_confidence=match_confidence,
        match_basis=match_basis,
    )
    service_cfg.update({
        "service_id": service_instance.service_id,
        "service_name": service_cfg.get("service_name") or _infra_default_service_name(
            service_type,
            node_instance.node_id,
            service_instance.service_id,
        ),
        "service_type": service_type,
        "service_port": contract.get("Int_Port", ""),
        "service_install": "ANSIBLE",
        "service_version": contract.get("Image_Ver", "1.0.0") if is_infra else contract.get("Image_Ver_List", ["1.0.0"])[0],
        "service_category": "Infrastructure" if is_infra else "Main",
        "service_display_name": entry.get("display_name", service_type),
        "infrastructure_role": entry.get("source_role", "") if is_infra else "",
        "external_port_required": False,
        "host_port": str(
            service_cfg.get("host_port")
            or (container.get("host_ports") or [""])[0]
            or contract.get("Default_Host_Port", "")
        ).strip(),
        "expose_service": _coerce_bool(
            service_cfg.get("expose_service")
            if "expose_service" in service_cfg
            else bool(container.get("host_ports")) or contract.get("Default_Expose_Service", False)
        ),
        "container_ip": str(
            service_cfg.get("container_ip")
            if "container_ip" in service_cfg
            else contract.get("Int_IP_Addr", "")
        ).strip(),
        "network_name": str(
            service_cfg.get("network_name")
            or contract.get("Network_Name", "")
        ).strip(),
        "network_subnet": str(
            service_cfg.get("network_subnet")
            or contract.get("Network_Subnet", "")
        ).strip(),
        "infra_mode": infra_mode_val,
        "managed_by_cplatform": managed_by_cplatform_val,
        "container_name": runtime["container_name"],
        "runtime": runtime,
    })

    service_instance.service_name = service_cfg["service_name"]
    service_instance.service_port = service_cfg["service_port"]
    service_instance.service_install = service_cfg["service_install"]
    service_instance.service_version = service_cfg["service_version"]
    service_instance.service_debug = service_cfg.get("service_debug", "DISABLE")
    service_instance.deploy_status = (
        "DEPLOYED"
        if adoption_status != "quarantined" and container.get("running")
        else "NOT DEPLOYED"
    )
    service_instance.service_config = service_cfg
    service_instance.save()
    service_event_add_request(
        service_instance,
        "Infrastructure Discovery" if is_infra else "Service Discovery",
        f"{adoption_status.title()} runtime container {runtime['container_name']}",
    )
    return service_instance, "created" if created else "updated"


def _quarantine_adopted_service(node_instance, service_type, reason, is_infra=True, existing_instance=None):
    service_instance = existing_instance or Service.objects.filter(Node=node_instance, service_type=service_type).first()
    if not service_instance:
        return None, "skipped"

    service_cfg = service_instance.service_config if isinstance(service_instance.service_config, dict) else {}

    is_already_managed = False
    if existing_instance:
        existing_cfg = existing_instance.service_config if isinstance(existing_instance.service_config, dict) else {}
        if existing_cfg.get("infra_mode") == "managed" or existing_cfg.get("managed_by_cplatform") is True:
            is_already_managed = True

    infra_mode_val = "managed" if is_already_managed else "adopted"
    managed_by_cplatform_val = True if is_already_managed else False

    runtime = _runtime_binding_with_status(
        _runtime_config(service_instance),
        adoption_status="quarantined",
        validation_error=reason,
        match_confidence=0,
        match_basis="",
    )
    runtime["infra_mode"] = infra_mode_val
    runtime["managed_by_cplatform"] = managed_by_cplatform_val
    service_cfg["infra_mode"] = infra_mode_val
    service_cfg["managed_by_cplatform"] = managed_by_cplatform_val
    service_cfg["container_name"] = runtime.get("container_name") or service_cfg.get("container_name") or ""
    service_cfg["runtime"] = runtime

    service_instance.deploy_status = "NOT DEPLOYED"
    service_instance.service_config = service_cfg
    service_instance.save(update_fields=["deploy_status", "service_config"])
    service_event_add_request(
        service_instance,
        "Infrastructure Discovery" if is_infra else "Service Discovery",
        f"Quarantined service binding: {reason}" if not is_infra else f"Quarantined infrastructure binding: {reason}",
    )
    return service_instance, "quarantined"


def service_discover_infrastructure_request(node_id):
    node_instance = Node.objects.filter(node_id=node_id).first()
    if not node_instance:
        return False, "Node does not exist", {"node_id": node_id, "adopted": []}

    discovery = serviceInstall.sInstall_discover_infrastructure_containers(node_id)
    if not discovery.get("success"):
        return False, discovery.get("error") or "Infrastructure discovery failed", {
            "node_id": node_id,
            "adopted": [],
        }

    containers = discovery.get("containers", [])
    details = []
    summary = {
        "kept": 0,
        "adopted": 0,
        "repaired": 0,
        "quarantined": 0,
        "skipped": 0,
    }
    used_container_names = set()

    # Build list of all discoverable services: tuples of (service_type, is_infra, contract, catalog_entry)
    discoverable_services = []

    # 1. Infrastructure services
    for infra_service_type, catalog_entry in INFRASTRUCTURE_SERVICE_CATALOG.items():
        if catalog_entry.get("catalog_visible", True) is False:
            continue
        contract = _get_infrastructure_contract(infra_service_type)
        if contract:
            discoverable_services.append((infra_service_type, True, contract, catalog_entry))

    # 2. Main services from dFormService.json keys
    try:
        file_path = os.path.join(Path(__file__).resolve().parent.parent, 'forms')
        with open(file_path + '/dFormService.json', 'r') as f:
            ser_schema = json.load(f)
        for main_type in ser_schema.keys():
            if main_type.startswith("Infra") or main_type in ("addPath", "AIOrchestrator", "cPlatform"):
                continue
            if main_type in INFRASTRUCTURE_SERVICE_CATALOG:
                continue
            contract, _ = _get_service_docker_contract(main_type)
            if contract and contract.get("Image_Name"):
                discoverable_services.append((main_type, False, contract, {
                    "display_name": main_type,
                    "source_role": contract.get("Role", "Primary"),
                    "category": "Main"
                }))
    except Exception as e:
        app_logger.error(f"Error loading dFormService.json keys for auto-discovery: {e}")

    for service_type, is_infra, contract, entry in discoverable_services:
        existing_instance = Service.objects.filter(Node=node_instance, service_type=service_type).first()
        current_name = _runtime_container_name(existing_instance) if existing_instance else ""
        current_container = next(
            (
                container for container in containers
                if str(container.get("name") or "").strip() == current_name
            ),
            None,
        )

        if current_container and str(current_name or "").strip() not in used_container_names:
            current_score, current_basis = _container_matches_service(current_container, service_type, contract, is_infra=is_infra)
            if current_score:
                service_instance, action = _apply_adopted_service(
                    node_instance,
                    service_type,
                    current_container,
                    is_infra=is_infra,
                    adoption_status="adopted",
                    discovered_containers=containers,
                    existing_instance=existing_instance,
                    match_confidence=current_score,
                    match_basis=current_basis,
                )
                if service_instance:
                    used_container_names.add(str(current_container.get("name") or ""))
                    summary["kept"] += 1
                    details.append({
                        "service_id": service_instance.service_id,
                        "service_type": service_type,
                        "display_name": entry.get("display_name", service_type),
                        "container_name": current_container.get("name", ""),
                        "state": current_container.get("state", ""),
                        "action": "kept",
                        "reason": "",
                    })
                    continue

        candidates = [
            container for container in containers
            if str(container.get("name") or "").strip() not in used_container_names
        ]
        container, selection = _select_service_container(candidates, service_type, contract, is_infra=is_infra)
        if container:
            action_label = "adopted"
            if existing_instance and current_name and str(container.get("name") or "").strip() != current_name:
                action_label = "repaired"
            service_instance, action = _apply_adopted_service(
                node_instance,
                service_type,
                container,
                is_infra=is_infra,
                adoption_status="repaired" if action_label == "repaired" else "adopted",
                discovered_containers=containers,
                existing_instance=existing_instance,
                match_confidence=selection.get("match_confidence", 0),
                match_basis=selection.get("match_basis", ""),
            )
            if service_instance:
                used_container_names.add(str(container.get("name") or ""))
                summary[action_label] += 1
                details.append({
                    "service_id": service_instance.service_id,
                    "service_type": service_type,
                    "display_name": entry.get("display_name", service_type),
                    "container_name": container.get("name", ""),
                    "state": container.get("state", ""),
                    "action": action_label,
                    "reason": "",
                })
            continue

        if existing_instance:
            existing_cfg = existing_instance.service_config if isinstance(existing_instance.service_config, dict) else {}
            is_managed = existing_cfg.get("infra_mode") == "managed" or existing_cfg.get("managed_by_cplatform") is True
            if not is_infra and is_managed and existing_instance.deploy_status == "NOT DEPLOYED":
                summary["skipped"] += 1
                continue

            reason = selection.get("reason") or "no_valid_candidate"
            if current_name and not current_container:
                reason = f"bound container {current_name} is missing on node"
            service_instance, _action = _quarantine_adopted_service(
                node_instance,
                service_type,
                reason,
                is_infra=is_infra,
                existing_instance=existing_instance,
            )
            if service_instance:
                summary["quarantined"] += 1
                details.append({
                    "service_id": service_instance.service_id,
                    "service_type": service_type,
                    "display_name": entry.get("display_name", service_type),
                    "container_name": current_name or "",
                    "state": "unknown",
                    "action": "quarantined",
                    "reason": reason,
                })
            continue

        summary["skipped"] += 1

    handled_count = sum(summary.values()) - summary["skipped"]
    return True, f"Discovered {handled_count} service runtime(s)", {
        "node_id": node_id,
        "summary": summary,
        "results": details,
        "adopted": [item for item in details if item.get("action") in ["adopted", "repaired", "kept"]],
        "container_count": len(containers),
    }


def _infrastructure_dependency_status(node_instance, infra_service_type):
    entry = _infra_catalog_entry(infra_service_type)
    contract = _get_infrastructure_contract(infra_service_type)
    container_name = _infra_container_name(infra_service_type, getattr(node_instance, "node_id", ""))
    dependency = {
        "service_type": infra_service_type,
        "display_name": entry.get("display_name", infra_service_type),
        "role": entry.get("source_role", ""),
        "container_name": container_name,
        "internal_port": contract.get("Int_Port", ""),
        "state": "missing",
        "deploy_status": "NOT DEPLOYED",
        "reason": "",
    }

    infra_instance = _find_infrastructure_service_instance(node_instance, infra_service_type)
    if not infra_instance:
        dependency["reason"] = "Infrastructure card is not installed on this node"
        return dependency

    dependency["service_id"] = infra_instance.service_id
    dependency["service_name"] = infra_instance.service_name
    dependency["deploy_status"] = infra_instance.deploy_status
    runtime = _runtime_config(infra_instance)
    runtime_container = _runtime_container_name(infra_instance)
    if runtime_container:
        container_name = runtime_container
        dependency["container_name"] = runtime_container
    dependency["infra_mode"] = runtime.get("infra_mode") or _service_config_dict(infra_instance).get("infra_mode") or "managed"
    if infra_instance.deploy_status != "DEPLOYED":
        dependency["state"] = "not_deployed"
        dependency["reason"] = str(runtime.get("validation_error") or "").strip() or "Infrastructure card exists but is not deployed"
        return dependency

    status_payload = serviceInstall.sInstall_get_service_live_status(
        infra_instance,
        node_instance.node_id,
        contract.get("Int_Port"),
        [],
        container_name,
        entry.get("source_role", ""),
        contract.get("Int_Port"),
    )
    if status_payload.get("error"):
        dependency["state"] = "unknown"
        dependency["reason"] = status_payload.get("error")
        return dependency

    main_container = status_payload.get("main_container", {}) or {}
    dependency["state"] = main_container.get("state", "missing")
    dependency["container_ip"] = main_container.get("container_ip", "")
    dependency["image"] = main_container.get("image", "")
    if dependency["state"] != "running":
        dependency["reason"] = f"Container is {dependency['state']}"
    return dependency


def service_check_dependency_preflight(ser_ins):
    node_instance = ser_ins.Node
    required_service_types = _required_infrastructure_service_types(ser_ins.service_type)
    dependencies = [
        _infrastructure_dependency_status(node_instance, infra_service_type)
        for infra_service_type in required_service_types
    ]
    missing_dependencies = [
        dependency for dependency in dependencies
        if str(dependency.get("state", "")).lower() != "running"
    ]
    return {
        "success": len(missing_dependencies) == 0,
        "code": "" if not missing_dependencies else "MISSING_DEPENDENCIES",
        "service_id": ser_ins.service_id,
        "service_name": ser_ins.service_name,
        "service_type": ser_ins.service_type,
        "node_id": node_instance.node_id if node_instance else "",
        "dependencies": dependencies,
        "missing_dependencies": missing_dependencies,
    }

def _check_service_requirement(ser_ins, machine_info):
    # Load requirement dictionary
    config_path = Path(__file__).resolve().parent.parents[1] / 'config/service_install.yaml'
    with open(config_path, 'r') as fh:
        requirement_dict = yaml.load(fh, Loader=yaml.FullLoader)

    # Extract service requirements
    service_requirements = requirement_dict.get(ser_ins.service_type, {})

    # Extract system information
    system_info = machine_info.get('System Info', {})

    # Compare CPU, RAM, and Storage
    required_cpu = service_requirements.get('CPU Info', {}).get('vCPUs', 0)
    required_ram = service_requirements.get('CPU Info', {}).get('RAM (GBs)', 0)
    required_storage = service_requirements.get('CPU Info', {}).get('Storage (GBs)', 0)
    machine_cpu = system_info.get('CPU Info', {}).get('vCPUs', 0)
    machine_ram = system_info.get('CPU Info', {}).get('RAM (GBs)', 0)
    machine_storage = system_info.get('CPU Info', {}).get('Storage (GBs)', 0)

    if machine_cpu < required_cpu or machine_ram < required_ram or machine_storage < required_storage:
        service_event_add_request(ser_ins, "ERROR", f"Hardware Requirements not met..!! ")
        return False

    # Compare software requirements
    required_sw_info = service_requirements.get('SW Info', {})
    machine_sw_info = system_info.get('SW Info', {})
    sw_requirements_skip_keys = set()
    if str(getattr(ser_ins, "service_type", "")).strip().upper() == "RAG":
        # Hotfix: allow RAG deployment on nodes without NVIDIA toolkit.
        sw_requirements_skip_keys.add("NVIDIA Container Toolkit Installed")

    for key, required_value in required_sw_info.items():
        if key in sw_requirements_skip_keys:
            continue
        machine_value = machine_sw_info.get(key, None)
        if machine_value is None or machine_value != required_value:
            service_event_add_request(ser_ins, "ERROR", f"Software Requirements not met..!! ")
            return False

    service_event_add_request(ser_ins, "Validating Node", f"Node found Compatible for Service.")
    return True


# -----------------------------------------Service Config Function------------------------------------------------------


def service_get_info__node(node_instance):
    service_info = {}
    service_index = 0
    if Service.objects.filter(Node=node_instance).exists():
        service_instance = Service.objects.filter(Node=node_instance).order_by('service_idx').values()
        filter_dict = (dict(enumerate(list(service_instance))))
        for key in filter_dict:
            service_index += 1
            service = filter_dict[key]
            service['Application_id'] = service.get('Application_id') or ''
            service_info[service_index] = service
        return service_info
    return service_info


def service_get_list__node(node_instance):
    service_list_info = []
    if Service.objects.filter(Node=node_instance).exists():
        service_instance = Service.objects.filter(Node=node_instance).order_by('service_idx')
        for service in service_instance:
            service_info = {
                'service_id': service.service_id,
                'service_name': service.service_name,
                'service_port': service.service_port,
            }
            service_list_info.append(service_info)
    return service_list_info


def service_get__node(node_name, service_name):
    service_ins = Service.objects.filter(
        Node__node_name=node_name, service_name=service_name
    ).first()

    if not service_ins:
        return None

    return {
        "serviceId": service_ins.service_id,
        "serviceName": service_ins.service_name,
        "serviceType": service_ins.service_type,
        "servicePort": service_ins.service_port,
        "hostPort": service_ins.service_config.get("host_port"),
    }

def service_get_prometheus__node(node_name):
    prometheus_service = Service.objects.filter(
        Node__node_name=node_name, service_type="InfraPrometheus"
    ).first()

    if not prometheus_service:
        return None

    return {
        "serviceName": prometheus_service.service_name,
        "servicePort": prometheus_service.service_port,
        "hostPort": prometheus_service.service_config.get("host_port"),
    }


def service_get_info(service_id):
    service_config = {}
    if Service.objects.filter(service_id=service_id).exists():
        service_instance = Service.objects.get(service_id=service_id)
        service_config = service_instance.service_config
    return service_config


def service_get_runtime_patch_status(service_id):
    if not Service.objects.filter(service_id=service_id).exists():
        return {
            "success": False,
            "error": "Service does not exist",
            "status": {},
        }

    service_instance = Service.objects.get(service_id=service_id)
    service_cfg = service_instance.service_config if isinstance(service_instance.service_config, dict) else {}
    observability_cfg = service_cfg.get("observability", {}) if isinstance(service_cfg.get("observability", {}), dict) else {}
    runtime_patch_cfg = observability_cfg.get("runtime_patch", {}) if isinstance(observability_cfg.get("runtime_patch", {}), dict) else {}

    return {
        "success": True,
        "error": "",
        "status": {
            "last_status": str(runtime_patch_cfg.get("last_status", "never")).strip() or "never",
            "last_message": str(runtime_patch_cfg.get("last_message", "")).strip(),
            "last_checked_at": str(runtime_patch_cfg.get("last_checked_at", "")).strip(),
            "last_container": str(runtime_patch_cfg.get("last_container", "")).strip(),
            "last_project_slug": str(runtime_patch_cfg.get("last_project_slug", "")).strip(),
            "last_release": str(runtime_patch_cfg.get("last_release", "")).strip(),
            "last_environment": str(runtime_patch_cfg.get("last_environment", "")).strip(),
        },
    }


def service_get_live_status(service_id):
    started_at = time.monotonic()

    def _finalize_status_response(payload, cache_hit=False):
        try:
            app_logger.info(
                "service_get_live_status service_id=%s cache_hit=%s overall_status=%s error=%s duration_ms=%s",
                service_id,
                cache_hit,
                payload.get("overall_status", ""),
                payload.get("error", ""),
                round((time.monotonic() - started_at) * 1000, 2),
            )
        except Exception:
            pass
        return payload

    cached = SERVICE_LIVE_STATUS_CACHE.get(service_id)
    if cached and (time.monotonic() - cached["created_at"]) < SERVICE_LIVE_STATUS_CACHE_TTL_SECONDS:
        return _finalize_status_response(dict(cached["payload"]), cache_hit=True)

    if not Service.objects.filter(service_id=service_id).exists():
        return _finalize_status_response({
            "service_id": service_id,
            "error": "Service does not exist",
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    service_instance = Service.objects.get(service_id=service_id)
    node_instance = service_instance.Node
    node_ip = _normalize_node_ip(node_instance.node_ip) if node_instance else ""
    main_contract, dependency_contracts = _get_service_docker_contract(service_instance.service_type)

    status_payload = {}
    if node_instance:
        container_name = service_get_runtime_container_name(service_instance)
        status_payload = serviceInstall.sInstall_get_service_live_status(
            service_instance,
            node_instance.node_id,
            main_contract.get("Int_Port"),
            dependency_contracts,
            container_name,
        )

    main_container = status_payload.get("main_container", {}) or {}
    dependencies = status_payload.get("dependencies", []) or []
    resolved_dependencies = [
        _resolve_managed_dependency_status(service_instance, dependency.copy())
        for dependency in dependencies
    ]

    service_status = {
        "service_id": service_instance.service_id,
        "service_name": service_instance.service_name,
        "service_type": service_instance.service_type,
        "node_id": node_instance.node_id if node_instance else "",
        "node_ip": node_ip,
        "overall_status": _derive_overall_status(main_container, resolved_dependencies),
        "main_container": {
            "name": main_container.get("name", service_instance.service_id),
            "state": main_container.get("state", "missing"),
            "service_port": main_contract.get("Int_Port"),
            "created_at": main_container.get("created_at", "").split("T")[0] + " " + main_container.get("created_at", "").split("T")[1][:8] if main_container.get("created_at") else "",
            "running_since": main_container.get("running_since", "").split("T")[0] + " " + main_container.get("running_since", "").split("T")[1][:8] if main_container.get("running_since") else "",
            "restart_count": main_container.get("restart_count", 0),
            "oom_killed": main_container.get("oom_killed", False),
            "expected_port_listening": main_container.get("expected_port_listening", False),
            "container_ip": main_container.get("container_ip", ""),
            "image": main_container.get("image", ""),
        },
        "dependencies": resolved_dependencies,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": status_payload.get("error", "") or "None",
    }
    if service_status.get("error", "") in ["", "None"]:
        SERVICE_LIVE_STATUS_CACHE[service_id] = {
            "created_at": time.monotonic(),
            "payload": dict(service_status),
        }
    else:
        SERVICE_LIVE_STATUS_CACHE.pop(service_id, None)
    return _finalize_status_response(service_status)


def service_get_config_schema():
    file_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    f = open(file_path + '/service_config_schema.json')
    config_schema = json.load(f)
    # app_logger.debug(f"service_get_config_schema, config_schema:{config_schema}")
    return config_schema


def service_get_instance(service_name):
    if Service.objects.filter(service_name=service_name).exists():
        service_inst = Service.objects.get(service_name=service_name)
        return service_inst
    return None


def service_get_ins_type(service_type, app_name):
    service_ins_list = Service.objects.filter(service_type=service_type, Application__app_name=app_name)
    serv_name_list = list(service_ins_list.values_list('service_name', flat=True))
    return serv_name_list


def service_get_infer_serv_list():
    serv_name_list = Service.objects.filter(service_type='InferenceServer')
    serv_infer_list = []
    for serv in serv_name_list:
        service_name = serv.service_name
        service_port = serv.service_port
        service_ip = serv.Node.node_ip
        serv_infer_list.append({"inf_service_name": str(service_name), "inf_service_port": str(service_port),
                                "inf_service_ip":str(service_ip)})

    return serv_infer_list


def service_update_app_mapping(service_name, app_ins):
    service_ins = Service.objects.get(service_name=service_name)
    service_ins.Application = app_ins
    service_ins.save()
    return


def service_check_app_mapping(service_name):
    if not Service.objects.filter(service_name=service_name).exists():
        return False

    ser_ins = Service.objects.get(service_name=service_name)
    if not ser_ins.Application:
        return False
    return True


def service_get_count__cluster(cluster_instance):

    ser_ins = Service.objects.filter(Node__Cluster=cluster_instance)
    return ser_ins.count()


def service_get_list__cluster(cluster_instance, service_type=None):
    ser_ins = Service.objects.filter(Node__Cluster=cluster_instance)
    if service_type is not None:
        ser_ins = ser_ins.filter(service_type=service_type)

    service_list = list(ser_ins.values_list('service_name', flat=True))
    return service_list


def service_get_mapping__cluster(cluster_ins):
    ser_ins = Service.objects.filter(Node__Cluster=cluster_ins)

    service_mappings = []

    for service in ser_ins:
        if service.service_type in ["AIOrchestrator", "cPlatform"]:
            continue
        mapping = {service.service_name: service.service_type}
        service_mappings.append(mapping)

    return service_mappings


def service_get_count__node(node_instance, service_type=None):
    ser_ins = Service.objects.filter(Node=node_instance)
    if service_type is not None:
        ser_ins = ser_ins.filter(service_type=service_type)

    return ser_ins.count()


def service_get_instance_by_node(node_instance):
    services = Service.objects.filter(Node=node_instance)
    return services


def service_check_mapped_usage(service_name):
    ser_ins = Service.objects.filter(service_name=service_name).first()
    if not ser_ins:
        return True
    return True


def service_get_service_count(cluster_instance, service_type):
    service_count = Service.objects.filter(Q(Node__Cluster=cluster_instance) & Q(service_type=service_type)).count()
    return service_count


def service_get_application_info():
    app_info = {}

    for app in ApplicationInfo.objects.all():
        services = Service.objects.filter(Application=app)
        service_list = []

        for service in services:
            service_list.append({service.service_name: service.service_type})

        app_info[app.app_name] = service_list

    return app_info


# ---------------------------------------Service API functions---------------------------------------------------------

def service_add_request(node_id, service_type, request_info=None):
    service_type = _canonical_service_type(service_type)
    node_instance = NodeConfig.node_get_instance(node_id)

    service_type_candidates = _equivalent_infrastructure_service_types(service_type) if _is_infrastructure_service_type(service_type) else [service_type]
    if not Service.objects.filter(Node=node_instance, service_type__in=service_type_candidates).exists():
        service_instance = Service.objects.create(Node=node_instance, service_type=service_type)
        service_id = _allocate_service_id(node_id, service_instance.service_idx)
        service_instance.service_id = service_id
        service_config = _get_service_default(service_type)
        if isinstance(request_info, dict):
            for key, value in request_info.items():
                if key in ('user-action', 'node_id'):
                    continue
                if value is None or value == '':
                    continue
                service_config[key] = value
        if _is_infrastructure_service_type(service_type):
            contract = _get_infrastructure_contract(service_type)
            entry = _infra_catalog_entry(service_type)
            runtime = _infra_runtime_binding(service_type, node_id, contract, mode="managed")
            requested_expose = (
                request_info.get("expose_service")
                if isinstance(request_info, dict) and "expose_service" in request_info
                else contract.get("Default_Expose_Service", False)
            )
            requested_host_port = (
                request_info.get("host_port")
                if isinstance(request_info, dict) and "host_port" in request_info
                else contract.get("Default_Host_Port", "")
            )
            requested_container_ip = (
                request_info.get("container_ip")
                if isinstance(request_info, dict) and "container_ip" in request_info
                else contract.get("Int_IP_Addr", "")
            )
            requested_network_name = (
                request_info.get("network_name")
                if isinstance(request_info, dict) and "network_name" in request_info
                else contract.get("Network_Name", "")
            )
            requested_network_subnet = (
                request_info.get("network_subnet")
                if isinstance(request_info, dict) and "network_subnet" in request_info
                else contract.get("Network_Subnet", "")
            )
            service_config.update({
                "service_name": (
                    service_config.get("service_name")
                    or _infra_default_service_name(service_type, node_id, service_id)
                ),
                "service_type": service_type,
                "service_port": contract.get("Int_Port", 0) or 0,
                "service_install": "ANSIBLE",
                "service_version": contract.get("Image_Ver", "1.0.0"),
                "service_category": "Infrastructure",
                "service_display_name": entry.get("display_name", service_type),
                "infrastructure_role": entry.get("source_role", ""),
                "external_port_required": False,
                "host_port": str(requested_host_port or "").strip(),
                "expose_service": _coerce_bool(requested_expose),
                "container_ip": str(requested_container_ip or "").strip(),
                "network_name": str(requested_network_name or "").strip(),
                "network_subnet": str(requested_network_subnet or "").strip(),
                "infra_mode": "managed",
                "managed_by_cplatform": True,
                "container_name": runtime["container_name"],
                "runtime": runtime,
            })
        ret, msg, service_config = _normalize_infra_exposure_config(service_type, service_config)
        if not ret:
            service_instance.delete()
            return False, msg, " ", " "
        service_config['service_name'] = service_config.get('service_name') or (service_type + "_" + service_id)
        service_config['service_type'] = service_type
        service_instance.service_name = service_config['service_name']
        service_instance.service_port = service_config['service_port']
        service_instance.service_install = service_config['service_install']
        service_instance.service_version = service_config['service_version']
        service_instance.service_volume = service_config.get("service_volume") or getattr(node_instance, "node_volume", "/tmp")
        service_instance.service_debug = service_config.get("service_debug", "DISABLE")
        service_instance.service_config = service_config
        service_instance.save()
        service_event_add_request(service_instance, "Service Added", f"Service '{service_id}' Added Successfully")
        return (True, f"Service {service_instance.service_name} added successfully", service_id,
                service_instance.service_name)

    return False, "Service already exist in this Node", " ", " "


def service_delete_request(service_id, node_id):
    # Check Valid Service ID
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Unable to service, ID does not exists !"

    ser_ins = Service.objects.get(service_id=service_id)
    service_name = ser_ins.service_name

    if ser_ins.service_type in ['AIOrchestrator', 'cPlatform'] and Service.objects.exclude(service_id=service_id).exists():
        return False, "Cannot delete AIOrchestrator. Please delete all other services first!"

    # Check No Application linked to this service
    if ser_ins.Application:
        return False, f"Service {service_name} is in use by Application, cannot delete !"

    if _is_infrastructure_service_type(ser_ins.service_type):
        dependents = []
        current_equivalents = set(_equivalent_infrastructure_service_types(ser_ins.service_type))
        for service in Service.objects.filter(Node=ser_ins.Node, deploy_status="DEPLOYED"):
            required_types = set()
            for infra_service_type in _required_infrastructure_service_types(service.service_type):
                required_types.update(_equivalent_infrastructure_service_types(infra_service_type))
            if current_equivalents.intersection(required_types):
                dependents.append(service.service_name)
        if dependents:
            return False, (
                f"Cannot delete {service_name}. It is required by deployed services: "
                f"{', '.join(dependents)}"
            )

    service_cfg = _service_config_dict(ser_ins)
    runtime = _runtime_config(ser_ins)
    adopted_infra = (
        _is_infrastructure_service_type(ser_ins.service_type)
        and (
            str(runtime.get("infra_mode") or service_cfg.get("infra_mode") or "").lower() == "adopted"
            or runtime.get("managed_by_cplatform") is False
            or service_cfg.get("managed_by_cplatform") is False
        )
    )

    if ser_ins.deploy_status == "DEPLOYED" and not adopted_infra:
        serviceInstall.sInstall_remove_service(ser_ins, node_id, ser_ins.Node.username)

    ser_ins.delete()
    if adopted_infra:
        return True, f"Service {service_name} unregistered; adopted runtime container was left untouched"
    return True, f"Service {service_name} deleted successfully"


def service_edit_request(request_info):
    if Service.objects.filter(service_id=request_info.get('service_id')).exists():
        ser_ins = Service.objects.get(service_id=request_info.get('service_id'))
        request_info = dict(request_info or {})
        canonical_type = _normalize_service_instance_type(ser_ins, request_info.get('service_type'))
        request_info['service_type'] = canonical_type
        ret, msg, request_info = _normalize_infra_exposure_config(canonical_type, request_info)
        if not ret:
            return False, msg, ser_ins.service_name
        if not Service.objects.filter(service_name=request_info.get('service_name')).exclude(
                service_id=ser_ins.service_id).exists():
            ser_ins.service_install = request_info.get('service_install')
            ser_ins.service_type = canonical_type
            ser_ins.service_version = request_info.get('service_version')
            ser_ins.service_volume = request_info.get('service_volume')
            
            new_name = request_info.get('service_name')
            if new_name == ser_ins.service_id and ser_ins.service_name and ser_ins.service_name != ser_ins.service_id:
                # Retain existing name if frontend falls back to service_id incorrectly
                pass
            else:
                ser_ins.service_name = new_name
            raw_port = request_info.get('service_port')
            if raw_port and str(raw_port).strip():
                try:
                    ser_ins.service_port = int(str(raw_port).strip())
                except ValueError:
                    pass
            ser_ins.service_debug = request_info.get('service_debug')
            ser_ins.service_config = request_info
            ser_ins.save()

            # Forwarding service config to a non-orchestrator service
            if ser_ins.service_type not in ['AIOrchestrator', 'cPlatform']:
                if _service_requires_config_push(ser_ins):
                    _send_service_config_api(request_info.get('service_name'), request_info.get('service_port'))
                return True, f"Service {ser_ins.service_name} updated successfully", ser_ins.service_name
            else:
                # Updating orchestrator config
                ret, msg = _update_orchestrator_config(request_info)
                if ret:
                    return True, f"Service {ser_ins.service_name} updated successfully", ser_ins.service_name
                else:
                    return ret, msg, ser_ins.service_name
        return False, f"Service {request_info.get('service_name')} already exist!", ser_ins.service_name

    return False, "Failed to update Service", ''


def service_deploy_request(request):
    service_id = request.get('service_id')
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service requirements not satisfied..", {}

    ser_ins = Service.objects.get(service_id=service_id)
    _normalize_service_instance_type(ser_ins)
    ser_ins = Service.objects.get(service_id=service_id)
    preflight = service_check_dependency_preflight(ser_ins)
    if not preflight.get("success"):
        service_event_add_request(
            ser_ins,
            "Dependency Check",
            f"Deployment blocked; missing dependencies: "
            f"{', '.join(item.get('display_name', item.get('service_type', '')) for item in preflight.get('missing_dependencies', []))}",
        )
        return False, "Deployment blocked: missing dependencies", preflight

    timer_name = _deploy_timer_name(service_id)
    cutil_timer_stop(timer_name)
    timer_arg = {
        "service_id": service_id,
        "retry_count": 0,
        "max_retry": max(1, _safe_int(request.get('max_retry'), SERVICE_DEPLOY_MAX_RETRY)),
    }
    cutil_timer_interval_start(timer_name, timer_arg, "cPlatformIO.src.ServiceConfig.start_service_deployment",
                               5, "cPlatform_dataflow")

    return True, f"Service {ser_ins.service_name} deployment initiated.", preflight


def service_runtime_patch_request(service_id):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service does not exist", {}

    ser_ins = Service.objects.get(service_id=service_id)
    
    service_type_lower = str(ser_ins.service_type or "").strip().lower()
    EXCLUDED_SERVICE_TYPES = {
        "infrarabbitmq",
        "infrapostgresqlcore",
        "infrarediscore",
        "infraairflowpostgresql",
        "infraairflowredis",
        "infraclickhouse",
        "infranifi",
        "inframilvus",
        "infraetcd",
        "inframinio",
        "infranodeexporter",
        "infraprocessexporter",
        "infrakafkaexporter",
        "infradcgmexporter",
        "infraprometheus",
        "infraprometheusans",
        "infraprometheusrag",
        "airflowinit",
    }
    if service_type_lower in EXCLUDED_SERVICE_TYPES:
        return False, f"Service type '{ser_ins.service_type}' does not support GlitchTip runtime patching as it is not a Python-based service.", {}

    node_ins = ser_ins.Node
    runtime_payload = serviceInstall.sInstall_run_service_runtime_patch(
        ser_ins,
        node_ins.node_id,
        container_name=service_get_runtime_container_name(ser_ins),
        restart_service=True,
    )

    runtime_success = bool(runtime_payload.get("success"))
    runtime_error = str(runtime_payload.get("error", "")).strip()
    if runtime_success:
        if runtime_payload.get("restarted"):
            runtime_msg = "Runtime patch applied and service restarted"
        elif runtime_payload.get("restart_requested") and not runtime_payload.get("restart_required"):
            runtime_msg = "Runtime patch already up to date; restart skipped"
        else:
            runtime_msg = "Runtime patch applied"
    else:
        runtime_msg = runtime_error or "Runtime patch failed"

    service_cfg = ser_ins.service_config if isinstance(ser_ins.service_config, dict) else {}
    observability_cfg = service_cfg.get("observability", {}) if isinstance(service_cfg.get("observability", {}), dict) else {}
    runtime_patch_cfg = observability_cfg.get("runtime_patch", {}) if isinstance(observability_cfg.get("runtime_patch", {}), dict) else {}
    runtime_patch_cfg.update({
        "last_status": "success" if runtime_success else "failed",
        "last_message": runtime_msg,
        "last_checked_at": str(runtime_payload.get("checked_at", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))),
        "last_container": str(runtime_payload.get("container_name", ser_ins.service_id)),
        "last_project_slug": str(runtime_payload.get("project_slug", "")),
        "last_release": str(runtime_payload.get("release", "")),
        "last_environment": str(runtime_payload.get("environment", "")),
    })
    observability_cfg["runtime_patch"] = runtime_patch_cfg
    service_cfg["observability"] = observability_cfg
    ser_ins.service_config = service_cfg
    ser_ins.save(update_fields=["service_config"])

    if runtime_success:
        service_event_add_request(ser_ins, "Diagnostics Wiring", f"Runtime Sentry patch applied for {ser_ins.service_id}")
    else:
        service_event_add_request(ser_ins, "ERROR", f"Runtime Sentry patch failed for {ser_ins.service_id}: {runtime_msg}")

    return runtime_success, runtime_msg, runtime_payload


@shared_task
def start_service_deployment(request):
    timer_arg = dict(request)
    service_id = timer_arg.get('service_id')
    retry_count = max(0, _safe_int(timer_arg.get('retry_count'), 0))
    max_retry = max(1, _safe_int(timer_arg.get('max_retry'), SERVICE_DEPLOY_MAX_RETRY))
    timer_arg['retry_count'] = retry_count
    timer_arg['max_retry'] = max_retry

    # Validate Service Exists
    if not Service.objects.filter(service_id=service_id).exists():
        _stop_service_deploy_timer(service_id, "terminal_failure:Service requirements not satisfied..")
        return False, "Service requirements not satisfied.."

    # Validate Node Connection
    ser_ins = Service.objects.get(service_id=service_id)
    if ser_ins.deploy_status == "DEPLOYED":
        if _service_requires_config_push(ser_ins):
            response = _send_service_config_api(ser_ins.service_name, ser_ins.service_port)
            if response is None or not 200 <= response.status_code < 300:
                msg = "Service config push failed after deployment."
                return _handle_deploy_failure(ser_ins, timer_arg, msg)

        health_ok, health_msg = _service_wait_for_health(ser_ins)
        if health_ok:
            _stop_service_deploy_timer(service_id, "deployment_succeeded", ser_ins)
            return True, f"Service {ser_ins.service_name} already deployed."

        return _handle_deploy_failure(ser_ins, timer_arg, health_msg)

    if ser_ins.service_install != 'ANSIBLE':
        log_msg = f"Service not configured for Ansible Install !"
        service_event_add_request(ser_ins, "Validating Node", log_msg)
        return _handle_deploy_failure(ser_ins, timer_arg, log_msg)

    preflight = service_check_dependency_preflight(ser_ins)
    if not preflight.get("success"):
        missing = ", ".join(
            item.get("display_name", item.get("service_type", ""))
            for item in preflight.get("missing_dependencies", [])
        )
        log_msg = f"Deployment blocked; missing dependencies: {missing}"
        service_event_add_request(ser_ins, "Dependency Check", log_msg)
        return _handle_deploy_failure(ser_ins, timer_arg, log_msg)

    node_ins = ser_ins.Node

    # Get Node Info and validate node authentication parameters
    node_info = serviceInstall.sInstall_get_node_info(ser_ins, node_ins.node_id)
    if not node_info:
        log_msg = f"System info retrieval failed for Node ({ser_ins.Node.node_ip}"
        service_event_add_request(ser_ins, "ERROR", log_msg)
        return _handle_deploy_failure(ser_ins, timer_arg, log_msg)

    # Validate node compatible for service
    service_event_add_request(ser_ins, "Validating Node", f"Retrieved Node Info for Node_ID=({node_ins.node_id})")
    if not _check_service_requirement(ser_ins, node_info):
        log_msg = "Deployment Failure, Node not compatible for Service !"
        return _handle_deploy_failure(ser_ins, timer_arg, log_msg)

    # Install and Run service on Node
    service_event_add_request(ser_ins, "Install Service", f"Service '{ser_ins.service_id}' Start Deploying..!!")
    if not serviceInstall.sInstall_deploy_service(ser_ins, node_ins.node_id, node_ins.username,
                                                  ser_ins.service_version):
        service_event_add_request(ser_ins, "ERROR", f"Service '{ser_ins.service_id}' Deployment not Successfully Done")
        log_msg = f"Failed to deploy Service {ser_ins.service_name}"
        return _handle_deploy_failure(ser_ins, timer_arg, log_msg)

    service_event_add_request(ser_ins, "Install Service", f"Deployment Successfully on Node_ID=({node_ins.node_id})")
    if _service_requires_config_push(ser_ins):
        response = _send_service_config_api(ser_ins.service_name, ser_ins.service_port)
        if response is None or response.status_code >= 400:
            return _handle_deploy_failure(ser_ins, timer_arg, "Service config push failed after deployment.")

    health_ok, health_msg = _service_wait_for_health(ser_ins)
    if not health_ok:
        return _handle_deploy_failure(ser_ins, timer_arg, health_msg)

    # Update deploy status only after post-deploy integration checks pass
    deploy_status = "DEPLOYED"
    ser_ins.deploy_status = deploy_status
    service_config = ser_ins.service_config
    service_config['deploy_status'] = deploy_status
    ser_ins.save()

    observability_ok, observability_msg = serviceInstall.sInstall_deploy_node_observability(
        node_ins,
        include_service_instance=ser_ins,
    )
    if observability_ok:
        service_event_add_request(ser_ins, "Diagnostics Wiring", f"Node observability updated on Node_ID=({node_ins.node_id})")
    else:
        service_event_add_request(ser_ins, "Diagnostics Warning", f"Node observability update failed: {observability_msg}")

    _stop_service_deploy_timer(service_id, "deployment_succeeded", ser_ins)
    return True, f"Service {ser_ins.service_name} deployed successfully."


def get_service_instance_from_app_name(app_name, service_type):
    if ApplicationInfo.objects.filter(app_name=app_name).exists():
        return Service.objects.filter(Application__app_name=app_name, service_type=service_type).first()
    return None


def _resolve_config_store_snapshots(service_instance, max_items=200):
    node_instance = service_instance.Node
    if not node_instance:
        return []

    node_ip = _normalize_node_ip(getattr(node_instance, "node_ip", getattr(node_instance, "ip_address", "")))
    node_volume = getattr(node_instance, "node_volume", "")
    if not node_ip or not node_volume:
        return []

    node_volume_clean = node_volume.lstrip("/")
    base_dir = Path("/iktara/cPlatform/cPlatform/logs/config_snapshots") / node_ip / node_volume_clean / "config"
    service_name = service_instance.service_type or service_instance.service_name or service_instance.service_id

    if not base_dir.exists() or not base_dir.is_dir():
        return []

    label_map = _load_config_snapshot_labels(service_instance.service_id)
    snapshot_items = []
    service_dir = base_dir / str(service_name)
    if not service_dir.exists():
        return []

    for version_dir in service_dir.iterdir():
        if not version_dir.is_dir():
            continue
        for ts_dir in version_dir.iterdir():
            if not ts_dir.is_dir():
                continue
            config_file = ts_dir / "config.yaml"
            if not config_file.exists():
                continue

            remote_path = f"{node_volume.rstrip('/')}/config/{service_name}/{version_dir.name}/{ts_dir.name}/config.yaml"

            try:
                dt = datetime.strptime(ts_dir.name, "%Y%m%dT%H%M%SZ")
                display_date = dt.strftime("%d-%b-%Y %H:%M")
            except Exception:
                display_date = ts_dir.name

            snapshot_key = _config_snapshot_key(version_dir.name, ts_dir.name)
            snapshot_items.append({
                "service": service_name,
                "version": version_dir.name,
                "timestamp": ts_dir.name,
                "snapshot_key": snapshot_key,
                "display_date": display_date,
                "path": remote_path,
                "mtime": config_file.stat().st_mtime,
                "custom_name": str(label_map.get(snapshot_key, "") or "").strip(),
            })

    _apply_config_snapshot_display_names(snapshot_items)
    snapshot_items.sort(key=lambda item: item.get("mtime", 0), reverse=True)
    return snapshot_items[:max_items]


def _config_snapshot_labels_root():
    return Path("/iktara/cPlatform/cPlatform/logs/config_snapshot_labels")


def _config_snapshot_labels_path(service_id):
    return _config_snapshot_labels_root() / f"{str(service_id or '').strip()}.json"


def _config_snapshot_key(version, timestamp):
    return f"{str(version or '').strip()}::{str(timestamp or '').strip()}"


def _load_config_snapshot_labels(service_id):
    labels_path = _config_snapshot_labels_path(service_id)
    if not labels_path.exists():
        return {}
    try:
        payload = json.loads(labels_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    labels = payload.get("labels", {}) if isinstance(payload, dict) else {}
    return labels if isinstance(labels, dict) else {}


def _save_config_snapshot_labels(service_id, labels):
    labels_path = _config_snapshot_labels_path(service_id)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.write_text(
        json.dumps({
            "service_id": service_id,
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "labels": labels,
        }, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _normalize_snapshot_label(label):
    cleaned = re.sub(r"\s+", " ", str(label or "").strip())
    if len(cleaned) > 80:
        cleaned = cleaned[:80].strip()
    return cleaned


def _apply_config_snapshot_display_names(snapshot_items):
    by_version = {}
    for item in snapshot_items:
        by_version.setdefault(str(item.get("version", "")), []).append(item)

    for version, items in by_version.items():
        ordered = sorted(items, key=lambda item: (item.get("mtime", 0), item.get("timestamp", "")))
        for idx, item in enumerate(ordered, start=1):
            default_name = f"{version}-v{idx}"
            custom_name = str(item.get("custom_name", "") or "").strip()
            item["default_name"] = default_name
            item["display_name"] = custom_name or default_name
            item["snapshot_name"] = item["display_name"]
            item["is_custom_name"] = bool(custom_name)


def service_rename_config_snapshot(service_id, version, timestamp, new_name):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service does not exist", {}

    label = _normalize_snapshot_label(new_name)
    if not label:
        return False, "Snapshot name cannot be empty", {}

    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,79}$", label):
        return False, "Snapshot name may only contain letters, numbers, spaces, dots, underscores, and hyphens", {}

    service_instance = Service.objects.get(service_id=service_id)
    snapshots = _resolve_config_store_snapshots(service_instance, max_items=500)
    target_key = _config_snapshot_key(version, timestamp)
    target_snapshot = next((item for item in snapshots if item.get("snapshot_key") == target_key), None)
    if target_snapshot is None:
        return False, "Snapshot not found", {}

    label_l = label.lower()
    for snapshot in snapshots:
        if snapshot.get("snapshot_key") == target_key:
            continue
        existing_name = str(snapshot.get("display_name") or snapshot.get("default_name") or "").strip()
        if existing_name.lower() == label_l:
            return False, f"Snapshot name '{label}' already exists for this service", {}

    labels = _load_config_snapshot_labels(service_id)
    default_name = str(target_snapshot.get("default_name", "") or "").strip()
    if label == default_name:
        labels.pop(target_key, None)
    else:
        labels[target_key] = label
    _save_config_snapshot_labels(service_id, labels)

    refreshed = _resolve_config_store_snapshots(service_instance)
    renamed_snapshot = next((item for item in refreshed if item.get("snapshot_key") == target_key), {})
    return True, "Snapshot renamed successfully", {
        "snapshot": renamed_snapshot,
        "snapshots": refreshed,
    }


def service_get_config_store(service_id):
    if not Service.objects.filter(service_id=service_id).exists():
        return {
            "success": False,
            "error": "Service does not exist",
            "snapshots": [],
        }

    service_instance = Service.objects.get(service_id=service_id)
    snapshots = _resolve_config_store_snapshots(service_instance)
    return {
        "success": True,
        "snapshots": snapshots,
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "config_capabilities": service_get_runtime_config_target(service_instance).get("config_capabilities", {}),
    }


def service_get_snapshot_content(service_id, version, timestamp):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service not found", ""

    service_instance = Service.objects.get(service_id=service_id)
    node_instance = service_instance.Node
    if not node_instance:
        return False, "Node not found", ""

    node_ip = _normalize_node_ip(getattr(node_instance, "node_ip", getattr(node_instance, "ip_address", "")))
    node_volume = getattr(node_instance, "node_volume", "").lstrip("/")
    service_name = service_instance.service_type or service_instance.service_name or service_instance.service_id

    local_path = Path("/iktara/cPlatform/cPlatform/logs/config_snapshots") / node_ip / node_volume / "config" / service_name / version / timestamp / "config.yaml"

    if not local_path.exists():
        return False, f"Snapshot file not found at {local_path}", ""

    try:
        with open(local_path, 'r') as f:
            content = f.read()
        return True, "Success", content
    except Exception as e:
        return False, str(e), ""


def service_run_config_checkpoint(service_id):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service does not exist", ""

    service_instance = Service.objects.get(service_id=service_id)
    node_instance = service_instance.Node
    if not node_instance:
        return False, "Service node not found", ""

    runtime_target = service_get_runtime_config_target(service_instance)
    capabilities = runtime_target.get("config_capabilities", {})
    if not capabilities.get("snapshot_enabled", True):
        return False, capabilities.get("disabled_reason") or "Config snapshot is disabled for this service", ""

    snapshot_result = serviceInstall.sInstall_get_service_config_snapshot(
        service_instance,
        node_instance.node_id,
        container_name=runtime_target.get("container_name") or service_instance.service_id,
        service_name=runtime_target.get("config_service_name") or service_instance.service_type,
        version=runtime_target.get("config_version") or service_instance.service_version,
        config_path=capabilities.get("config_path") or None,
        node_volume=node_instance.node_volume,
    )

    if not snapshot_result.get("success"):
        error_msg = snapshot_result.get("error") or "Service config snapshot failed"
        return False, error_msg, snapshot_result.get("snapshot_path", "")

    snapshot_path = snapshot_result.get("snapshot_path", "")
    msg = "Checkpoint completed" if snapshot_path else "Checkpoint completed (path unavailable)"
    return True, msg, snapshot_path


# =========================================================
# SIMPLE CONFIG MIGRATION (OmegaConf based)
# =========================================================

def generate_diff_ops(old, new, path=""):
    ops = []

    if type(old) != type(new):
        ops.append({
            "op": "type_change",
            "path": path,
            "old_type": type(old).__name__,
            "new_type": type(new).__name__,
            "value": deepcopy(new)
        })
        return ops

    if isinstance(old, dict):
        old_keys = set(old.keys())
        new_keys = set(new.keys())

        removed_keys = old_keys - new_keys
        added_keys = new_keys - old_keys

        matched_removed = set()
        matched_added = set()

        for old_key in removed_keys:
            old_val = old[old_key]
            for new_key in added_keys:
                new_val = new[new_key]
                if type(old_val) == type(new_val) and old_val == new_val:
                    old_path = f"{path}.{old_key}" if path else old_key
                    new_path = f"{path}.{new_key}" if path else new_key
                    ops.append({
                        "op": "move",
                        "from": old_path,
                        "path": new_path,
                        "value": deepcopy(old_val)
                    })
                    matched_removed.add(old_key)
                    matched_added.add(new_key)
                    break

        for key in removed_keys - matched_removed:
            key_path = f"{path}.{key}" if path else key
            ops.append({
                "op": "remove",
                "path": key_path,
                "old": deepcopy(old[key])
            })

        for key in added_keys - matched_added:
            key_path = f"{path}.{key}" if path else key
            ops.append({
                "op": "add",
                "path": key_path,
                "value": deepcopy(new[key])
            })

        for key in old_keys & new_keys:
            key_path = f"{path}.{key}" if path else key
            ops.extend(generate_diff_ops(old[key], new[key], key_path))

        return ops

    if isinstance(old, list):
        if old != new:
            ops.append({
                "op": "replace",
                "path": path,
                "old": deepcopy(old),
                "value": deepcopy(new)
            })
        return ops

    if old != new:
        ops.append({
            "op": "replace",
            "path": path,
            "old": deepcopy(old),
            "value": deepcopy(new)
        })

    return ops


def delete_path(cfg, path):
    parts = path.split(".")
    node = cfg

    for p in parts[:-1]:
        if p not in node:
            return
        node = node[p]

    if parts[-1] in node:
        del node[parts[-1]]


def apply_diff_ops(base_cfg, ops):
    cfg = OmegaConf.create(
        OmegaConf.to_container(base_cfg, resolve=False)
    )

    for op in ops:
        op_type = op["op"]

        if op_type == "add":
            OmegaConf.update(
                cfg,
                op["path"],
                op["value"],
                merge=False
            )
        elif op_type == "replace":
            OmegaConf.update(
                cfg,
                op["path"],
                op["value"],
                merge=False
            )
        elif op_type == "type_change":
            OmegaConf.update(
                cfg,
                op["path"],
                op["value"],
                merge=False
            )
        elif op_type == "remove":
            delete_path(cfg, op["path"])
        elif op_type == "move":
            value = OmegaConf.select(cfg, op["from"])
            if value is not None:
                OmegaConf.update(
                    cfg,
                    op["path"],
                    value,
                    merge=False
                )
                delete_path(cfg, op["from"])

    return cfg


def _snapshot_rank_key(snapshot_info):
    timestamp = str(snapshot_info.get("timestamp", ""))
    version = str(snapshot_info.get("version", ""))
    try:
        ts_dt = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
    except Exception:
        ts_dt = datetime.min
    return ts_dt, version


def _snapshot_content_to_dict(service_id, snapshot_info, label):
    version = snapshot_info.get("version")
    timestamp = snapshot_info.get("timestamp")
    ret, msg, content = service_get_snapshot_content(service_id, version, timestamp)
    if not ret:
        return False, f"Failed to load {label}: {msg}", {}

    try:
        parsed_content = yaml.safe_load(content) if content else {}
    except Exception as e:
        return False, f"Failed to parse {label}: {str(e)}", {}

    if parsed_content is None:
        parsed_content = {}
    if not isinstance(parsed_content, dict):
        parsed_content = {"value": parsed_content}
    return True, "Success", parsed_content


def _migration_artifacts_root():
    return Path("/iktara/cPlatform/cPlatform/logs/config_migration_artifacts")


def _migration_artifact_paths(service_id, artifact_id):
    artifact_dir = _migration_artifacts_root() / str(service_id)
    yaml_path = artifact_dir / f"{artifact_id}.yaml"
    meta_path = artifact_dir / f"{artifact_id}.json"
    return artifact_dir, yaml_path, meta_path


def _persist_migration_artifact(service_id, final_yaml, payload):
    artifact_id = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    artifact_dir, yaml_path, meta_path = _migration_artifact_paths(service_id, artifact_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    checksum = hashlib.sha256((final_yaml or "").encode("utf-8")).hexdigest()
    metadata = {
        "artifact_id": artifact_id,
        "service_id": service_id,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "checksum_sha256": checksum,
        "selected_configs": payload.get("selected_configs", {}),
        "ranked_configs": payload.get("ranked_configs", {}),
    }

    yaml_path.write_text(final_yaml or "", encoding="utf-8")
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "id": artifact_id,
        "yaml_path": str(yaml_path),
        "meta_path": str(meta_path),
        "checksum_sha256": checksum,
        "created_at": metadata["created_at"],
    }


def _load_migration_artifact(service_id, artifact_id):
    artifact_id = str(artifact_id or "").strip()
    if not artifact_id:
        return False, "Migration artifact id is required", {}

    _, yaml_path, meta_path = _migration_artifact_paths(service_id, artifact_id)
    if not yaml_path.exists():
        return False, f"Migration artifact YAML not found: {yaml_path}", {}
    if not meta_path.exists():
        return False, f"Migration artifact metadata not found: {meta_path}", {}

    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Failed to read migration artifact: {str(e)}", {}

    try:
        yaml_dict = yaml.safe_load(yaml_text) if yaml_text else {}
    except Exception as e:
        return False, f"Invalid migration artifact YAML: {str(e)}", {}

    if yaml_dict is None:
        yaml_dict = {}

    return True, "Success", {
        "artifact_id": artifact_id,
        "yaml_text": yaml_text,
        "yaml_dict": yaml_dict,
        "metadata": metadata,
        "yaml_path": str(yaml_path),
        "meta_path": str(meta_path),
    }


def service_prepare_snapshot_migrate_payload(service_id, snap1, snap2):
    ret1, msg1, config1 = _snapshot_content_to_dict(service_id, snap1, "snapshot 1")
    if not ret1:
        return False, msg1, {}

    ret2, msg2, config2 = _snapshot_content_to_dict(service_id, snap2, "snapshot 2")
    if not ret2:
        return False, msg2, {}

    selected_configs = {
        "selected_1": {
            "snapshot": dict(snap1),
            "config_dict": config1,
        },
        "selected_2": {
            "snapshot": dict(snap2),
            "config_dict": config2,
        },
    }

    # Respect the user-selected direction (snap1 -> snap2)
    source_config = deepcopy(config1)
    target_config = deepcopy(config2)

    ops = generate_diff_ops(source_config, target_config)

    source_cfg = OmegaConf.create(deepcopy(source_config))
    target_cfg = OmegaConf.create(deepcopy(target_config))
    migrated_cfg = apply_diff_ops(source_cfg, ops)

    try:
        final_cfg = OmegaConf.merge(target_cfg, source_cfg)
    except Exception as e:
        app_logger.warning("OmegaConf merge failed, falling back to target config: %s", str(e))
        final_cfg = target_cfg

    migrated_config_dict = OmegaConf.to_container(migrated_cfg, resolve=False)
    final_merged_config = OmegaConf.to_container(final_cfg, resolve=False)
    final_merged_config_yaml = OmegaConf.to_yaml(final_cfg)

    print("\n==============================")
    print("FINAL CONFIG (MIGRATION OUTPUT)")
    print("==============================")
    print(final_merged_config_yaml)

    payload = {
        "selected_configs": selected_configs,
        "ranked_configs": {
            "rank_1": selected_configs["selected_2"],
            "rank_2": selected_configs["selected_1"],
        },
        "config_rank_1": target_config,
        "config_rank_2": source_config,
        "migration_ops": ops,
        "migrated_config": migrated_config_dict,
        "final_merged_config": final_merged_config,
        "final_merged_config_yaml": final_merged_config_yaml,
    }

    artifact_info = _persist_migration_artifact(service_id, final_merged_config_yaml, payload)
    payload["migration_artifact"] = artifact_info

    return True, "Migration completed", payload


def service_apply_snapshot_migration(service_id, migration_artifact_id, apply_mode="reload", edited_migration_yaml=""):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service does not exist", {}

    apply_mode = str(apply_mode or "reload").strip().lower()
    if apply_mode not in ["reload", "restart"]:
        return False, f"Invalid apply mode: {apply_mode}", {}

    service_instance = Service.objects.get(service_id=service_id)
    node_instance = service_instance.Node
    if not node_instance:
        return False, "Service node not found", {}

    ret, msg, artifact_data = _load_migration_artifact(service_id, migration_artifact_id)
    if not ret:
        return False, msg, {}

    merged_config_yaml = artifact_data.get("yaml_text", "")
    edited_text = str(edited_migration_yaml or "").strip()
    if edited_text:
        try:
            edited_payload = yaml.safe_load(edited_migration_yaml)
        except Exception as e:
            return False, f"Edited migration YAML is invalid: {str(e)}", {}

        if edited_payload is None:
            edited_payload = {}
        if not isinstance(edited_payload, (dict, list)):
            return False, "Edited migration YAML must be a mapping or list", {}

        merged_config_yaml = yaml.safe_dump(
            edited_payload,
            sort_keys=False,
            default_flow_style=False
        )

    # 1. Rollback protection: capture current config checkpoint before overwriting
    service_run_config_checkpoint(service_id)

    runtime_target = service_get_runtime_config_target(service_instance)
    capabilities = runtime_target.get("config_capabilities", {})
    if not capabilities.get("apply_enabled", True):
        return False, capabilities.get("disabled_reason") or "Config apply is disabled for this service", {
            "artifact_id": artifact_data.get("artifact_id"),
            "apply_result": {},
        }
    if capabilities.get("restart_required") and apply_mode == "reload":
        apply_mode = "restart"

    # 2. Apply config to node
    apply_result = serviceInstall.sInstall_apply_service_config_migration(
        service_instance,
        node_instance.node_id,
        merged_config_yaml=merged_config_yaml,
        apply_mode=apply_mode,
        container_name=runtime_target.get("container_name") or service_instance.service_id,
        service_name=runtime_target.get("config_service_name") or service_instance.service_type,
        version=runtime_target.get("config_version") or service_instance.service_version,
        config_path=capabilities.get("config_path") or None,
        node_volume=node_instance.node_volume,
        artifact_id=artifact_data.get("artifact_id", ""),
    )

    if not apply_result.get("success"):
        error_msg = apply_result.get("error") or "Failed to apply migrated config"
        return False, error_msg, {
            "artifact_id": artifact_data.get("artifact_id"),
            "apply_result": apply_result,
        }

    # 3. Synchronize database
    try:
        config_dict = yaml.safe_load(merged_config_yaml)
        if config_dict is not None:
            service_instance.service_config = config_dict
            service_instance.save()
    except Exception as e:
        app_logger.error("Failed to sync DB with applied migration: %s", str(e))

    # 4. Capture a new checkpoint of the applied config so it's logged in history
    service_run_config_checkpoint(service_id)

    print("\n==============================")
    print("MIGRATION APPLY RESULT")
    print("==============================")
    print(json.dumps(apply_result, indent=2))

    return True, "Migration applied successfully", {
        "artifact_id": artifact_data.get("artifact_id"),
        "apply_result": apply_result,
    }


def service_restore_snapshot_migration(service_id, backup_path, resolved_config_path, apply_mode="reload"):
    if not Service.objects.filter(service_id=service_id).exists():
        return False, "Service does not exist", {}

    apply_mode = str(apply_mode or "reload").strip().lower()
    if apply_mode not in ["reload", "restart"]:
        return False, f"Invalid apply mode: {apply_mode}", {}

    service_instance = Service.objects.get(service_id=service_id)
    node_instance = service_instance.Node
    if not node_instance:
        return False, "Service node not found", {}

    node_volume = node_instance.node_volume if node_instance else None
    runtime_target = service_get_runtime_config_target(service_instance)
    capabilities = runtime_target.get("config_capabilities", {})
    if not capabilities.get("restore_enabled", True):
        return False, capabilities.get("disabled_reason") or "Config restore is disabled for this service", {
            "restore_result": {},
        }
    if capabilities.get("restart_required") and apply_mode == "reload":
        apply_mode = "restart"

    # Apply restore playbook
    restore_result = serviceInstall.sInstall_restore_service_config_migration(
        service_instance,
        node_instance.node_id,
        backup_path=backup_path,
        resolved_config_path=resolved_config_path,
        apply_mode=apply_mode,
        container_name=runtime_target.get("container_name") or service_instance.service_id,
        service_name=runtime_target.get("config_service_name") or service_instance.service_type,
        version=runtime_target.get("config_version") or service_instance.service_version,
        node_volume=node_volume,
    )

    if not restore_result.get("success"):
        error_msg = restore_result.get("error") or "Failed to restore migrated config"
        return False, error_msg, {
            "restore_result": restore_result,
        }

    # Synchronize database on restore: run a new checkpoint, read output, and update DB
    ret_cp, cp_msg, local_snapshot_path = service_run_config_checkpoint(service_id)
    if ret_cp and local_snapshot_path and os.path.exists(local_snapshot_path):
        try:
            with open(local_snapshot_path, "r", encoding="utf-8") as f:
                restored_yaml = f.read()
            config_dict = yaml.safe_load(restored_yaml)
            if config_dict is not None:
                service_instance.service_config = config_dict
                service_instance.save()
        except Exception as e:
            app_logger.error("Failed to sync restored config to DB: %s", str(e))

    print("\n==============================")
    print("MIGRATION RESTORE RESULT")
    print("==============================")
    print(json.dumps(restore_result, indent=2))

    return True, "Migration restored successfully", {
        "restore_result": restore_result,
    }


def service_validate_yaml_text(yaml_text):
    text = str(yaml_text or "")
    if not text.strip():
        return False, "YAML text is empty", {}
    try:
        parsed = yaml.safe_load(text)
    except Exception as e:
        return False, f"Invalid YAML syntax: {str(e)}", {}

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, (dict, list)):
        return False, "YAML must be a mapping or list", {}
    return True, "Valid YAML", {"parsed_type": type(parsed).__name__}


def _render_split_diff_html(diff_text: str, source_name: str, target_name: str) -> str:
    if not diff_text:
        return "<div class='text-muted'>No changes detected.</div>"

    lines = diff_text.splitlines()
    rows = []

    def _escape(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _row(left: str, right: str, left_cls: str = "", right_cls: str = "") -> str:
        return f"<tr><td class='diff-line {left_cls}'>{_escape(left)}</td><td class='diff-line {right_cls}'>{_escape(right)}</td></tr>"

    rows.append(f"<tr class='diff-header'><th>{_escape(source_name)}</th><th>{_escape(target_name)}</th></tr>")

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("---") or line.startswith("+++"):
            idx += 1
            continue
        if line.startswith("@@"):
            rows.append(f"<tr class='diff-info'><td colspan='2'>{_escape(line)}</td></tr>")
            idx += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            left = line
            right = ""
            if idx + 1 < len(lines) and lines[idx + 1].startswith("+") and not lines[idx + 1].startswith("+++"):
                right = lines[idx + 1]
                idx += 1
            rows.append(_row(left, right, "diff-del", "diff-add" if right else ""))
            idx += 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            rows.append(_row("", line, "", "diff-add"))
            idx += 1
            continue
        rows.append(_row(line, line))
        idx += 1

    return f"<table class='diff-table'>{''.join(rows)}</table>"


def service_get_snapshots_diff(service_id, snap1, snap2):
    try:
        ret1, msg1, content1 = service_get_snapshot_content(service_id, snap1['version'], snap1['timestamp'])
        if not ret1:
            return False, f"Failed to load snapshot 1: {msg1}", ""

        ret2, msg2, content2 = service_get_snapshot_content(service_id, snap2['version'], snap2['timestamp'])
        if not ret2:
            return False, f"Failed to load snapshot 2: {msg2}", ""

        from cPlatformIO.src.structured_io import _unified_diff, _load_structured_file
        from tempfile import NamedTemporaryFile

        def _parse_content(content):
            with NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                data, _ = _load_structured_file(Path(tmp_path))
                return data
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        dict1 = _parse_content(content1)
        dict2 = _parse_content(content2)

        label1 = f"{snap1['version']} ({snap1['timestamp']})"
        label2 = f"{snap2['version']} ({snap2['timestamp']})"
        diff_text = _unified_diff(dict1, dict2, label1, label2)
        html_diff = _render_split_diff_html(diff_text, label1, label2)

        return True, "Success", html_diff
    except Exception as e:
        app_logger.exception(f"Error in service_get_snapshots_diff: {str(e)}")
        return False, str(e), ""



def service_get_infra_service_count():
    return Service.objects.filter(service_type__startswith="Infra").count()
