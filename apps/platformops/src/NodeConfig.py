'''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : NodeConfig.py
* Description       : Functions related to Node feature
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 08-April-25                   Aniket                           Created
* 21-April-25                   Sumit Das                        Updated
*********************************************************************************************************************'''
import json
import os
import ipaddress
import textwrap

from django.conf import settings
from django.forms.models import model_to_dict
from django.db.models import IntegerField, Sum
from django.db.models.functions import Cast
from django.db.models.expressions import RawSQL

# Import Data Models Managed by this Module
from cPlatformIO.src import ClusterConfig, ServiceConfig, Cutilinit
from cPlatformIO.models import Node, Service, REPOSITORY_TYPE, IMAGE_STORE, SERVICE_TYPE, ApplicationInfo

from cPlatformIO.src import serviceInstall, NodeEvent
try:
    from cPlatformIO.src import TerraformMgmt
except ImportError:
    TerraformMgmt = None
from cPlatform.AppLogging import app_logger

from CommonUtils.timer.TimerMgr import cutil_timer_crontab_start, cutil_timer_get_app_curr_time
from pathlib import Path

NODE_BASE_IDX = 1000


def _get_mapped_node_id(node_idx):
    node_id = 'NODE' + str(NODE_BASE_IDX + node_idx)
    return node_id


def _validate_ip_address(ip_address):
    try:
        ipaddress.ip_address(ip_address)
    except ValueError:
        app_logger.debug(f"_validate_ip_address, Invalid ip_address=={ip_address}, Error={ValueError}")
        return False
    return True


def node_get_instance(node_id):
    node_ins = Node.objects.get(node_id=node_id)
    return node_ins


def node_get_service_count(cluster_instance):
    service_count = ServiceConfig.service_get_count__cluster(cluster_instance)
    return service_count


def node_get_info__cluster(cluster_instance):
    node_info = {}
    nodes = Node.objects.filter(Cluster=cluster_instance).order_by('node_idx')

    for idx, node in enumerate(nodes, start=1):
        node_info[idx] = {
            'node_name': node.node_name or "",
            'node_id': node.node_id or "",
            'node_idx': node.node_idx or "",
            'ip_address': node.node_ip or "",
            'username': node.username or "",
            'password': node.password or "",
            'service_info': ServiceConfig.service_get_info__node(node) or {},
            'node_provision_config': node.node_provision_config or {}
        }

    return node_info


def cluster_total_resources(cluster_instance):
    """
    Returns total vCPU and memory allocated
    across all nodes in a cluster using DB aggregation.
    """

    totals = (
        Node.objects
        .filter(Cluster=cluster_instance)
        .annotate(
            vcpu_int=Cast(
                RawSQL(
                    "node_provision_config->>'vcpu'",
                    []
                ),
                IntegerField()
            ),
            memory_int=Cast(
                RawSQL(
                    "node_provision_config->>'memory'",
                    []
                ),
                IntegerField()
            )
        )
        .aggregate(
            total_vcpus=Sum('vcpu_int'),
            total_memory=Sum('memory_int')
        )
    )

    return {
        "total_vcpus": totals.get("total_vcpus") or 0,
        "total_memory": totals.get("total_memory") or 0
    }


def node_list_get_info_cluster(cluster_name):
    node_list_info = []
    nodes = Node.objects.filter(Cluster__cluster_name=cluster_name).select_related('Cluster')
    for node in nodes:
        cluster_info = {
            'node_idx': node.node_idx,
            'node_id': node.node_id,
            'ip_address': node.node_ip,
            'node_port': node.node_monitor_port,
            'node_volume': node.node_volume,
            'node_name': node.node_name,
            'gpu_status': node.gpu_status
        }
        node_list_info.append(cluster_info)

    return node_list_info

def node_get_info_cluster(cluster_name, node_name):
    node = Node.objects.filter(
            Cluster__cluster_name=cluster_name, node_name=node_name
        ).select_related('Cluster').first()

    if not node:
        return None

    prometheus_service = Service.objects.filter(
            Node=node, service_type="InfraPrometheus"
        ).first()

    return {
        'node_idx': node.node_idx,
        'node_id': node.node_id,
        'ip_address': node.node_ip,
        'node_port': node.node_monitor_port,
        'node_volume': node.node_volume,
        'node_name': node.node_name,
        'gpu_status': node.gpu_status,
        'service_config': (
            prometheus_service.service_config if prometheus_service else None
        )
    }

def node_get_service_list(cluster_instance, service_type=None):
    service_list = ServiceConfig.service_get_list__cluster(cluster_instance, service_type)
    return service_list


def node_get_service_mapping(cluster_ins):
    service_mapping = ServiceConfig.service_get_mapping__cluster(cluster_ins)
    return service_mapping


def _update_pem_key(node_ins, encryption_key_str, encryption_key_path):
    if not encryption_key_str:
        return False, "Empty PEM key"

    pem_cleaned = encryption_key_str.strip().replace('\r', '').replace('\n', '')
    corrected_pem = ""

    if "BEGIN OPENSSH PRIVATE KEY" in pem_cleaned:
        pem_body = pem_cleaned.replace("-----BEGIN OPENSSH PRIVATE KEY-----", "") \
            .replace("-----END OPENSSH PRIVATE KEY-----", "") \
            .replace(" ", "")
        wrapped_key = "\n".join(textwrap.wrap(pem_body, 70))
        corrected_pem = (
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                + wrapped_key + "\n"
                + "-----END OPENSSH PRIVATE KEY-----\n"
        )

        with open(encryption_key_path, 'w', encoding='utf-8') as pem_file:
            pem_file.write(corrected_pem)
        os.chmod(encryption_key_path, 0o600)
        node_ins.encryption_key_text = corrected_pem
        return True, "PEM Key updated"

    elif "BEGIN RSA PRIVATE KEY" in pem_cleaned:
        pem_body = pem_cleaned.replace("-----BEGIN RSA PRIVATE KEY-----", "") \
            .replace("-----END RSA PRIVATE KEY-----", "") \
            .replace(" ", "")
        wrapped_key = "\n".join(textwrap.wrap(pem_body, 64))
        corrected_pem = (
                "-----BEGIN RSA PRIVATE KEY-----\n"
                + wrapped_key + "\n"
                + "-----END RSA PRIVATE KEY-----\n"
        )

        with open(encryption_key_path, 'w', encoding='utf-8') as pem_file:
            pem_file.write(corrected_pem)
        os.chmod(encryption_key_path, 0o600)
        node_ins.encryption_key_text = corrected_pem
        return True, "PEM Key updated"

    return False, "Invalid PEM Key Format"


# ---------------------------------------Node API functions-------------------------------------------------------------


def node_add_request(request_info):
    cluster_id = request_info.get('cluster_id')
    app_logger.debug(f"node_add_request, cluster_id=={cluster_id}")

    cluster_instance = ClusterConfig.cluster_get_instance(cluster_id)
    node_ins = Node.objects.create(Cluster=cluster_instance)
    node_id = _get_mapped_node_id(node_ins.node_idx)
    node_ins.node_id = node_id
    node_ins.node_name = node_id
    node_ins.save()
    config_str = request_info.get("node_provision_config")
    config = json.loads(config_str)
    node_name = config.get('node_name')
    gpu_status = config.get('gpu_status')
    ip_address = config.get('node_ip')
    auth_type = config.get('auth_type')
    username = config.get('username')
    pwd = config.get('password')
    encryption_key_str = config.get('encryption_key')

    if pwd and not encryption_key_str:
        encryption_key_str = ""
    elif encryption_key_str and not pwd:
        pwd = ""

    # Check for duplicate node name
    if Node.objects.filter(node_name=node_name).exclude(node_id=node_id).exists():
        return False, "Node with same name exists", ""

    # Validate IP address
    if not _validate_ip_address(ip_address):
        return False, "Invalid Node IP Address", ""

    # Validate authentication parameters
    if username == '' or (auth_type == "Password" and pwd == '') or (
        auth_type == "EncryptionKey" and not encryption_key_str):
        return False, "Invalid Authentication Parameters", ""

    node_ins = Node.objects.filter(node_id=node_id).first()
    if not node_ins:
        return False, "Node not found", ""
    # Update node fields
    node_ins.node_name = node_name
    node_ins.node_ip = ip_address
    node_ins.auth_type = auth_type
    node_ins.username = username
    node_ins.password = pwd
    node_ins.node_volume = config.get('node_volume')
    node_ins.node_monitor_port = config.get('node_monitor_port')
    node_ins.gpu_status = gpu_status
    node_ins.node_provision_config = config

    encryption_key_path = ""

    if auth_type == "EncryptionKey" and encryption_key_str:
        key_filename = f"{node_id}.pem"
        node_ins.encryption_key_name = key_filename

        pem_dir = os.path.join(settings.BASE_DIR, 'temp_pem')
        os.makedirs(pem_dir, exist_ok=True)
        encryption_key_path = os.path.join(pem_dir, key_filename)

        # Update pem file
        ret, msg = _update_pem_key(node_ins, encryption_key_str, encryption_key_path)
        if not ret:
            return False, msg, ""

    serviceInstall.sInstall_add_inv_file(node_ins.node_id, auth_type, ip_address, username, pwd, encryption_key_path)
    node_ins.save()
    if node_ins.node_ip and node_ins.node_volume:
        deployed, deploy_msg = serviceInstall.sInstall_deploy_node_observability(node_ins)
        if not deployed:
            app_logger.warning(f"Node observability deploy failed for {node_ins.node_id}: {deploy_msg}")
    return True, f"Node {node_ins.node_name} added successfully", node_ins.node_id


def node_delete_request(node_id):
    app_logger.debug(f"node_delete_request, node_id=={node_id}")

    if not Node.objects.filter(node_id=node_id).exists():
        return False, "Unable to delete node, Node ID does not exists !"

    node_ins = Node.objects.get(node_id=node_id)
    node_name = node_ins.node_name
    if ServiceConfig.service_get_count__node(node_ins) != 0:
        return False, "Unable to delete node, Please delete services first!"

    if ServiceConfig.service_get_count__node(node_ins, service_type=None) != 0:
        return False, "Unable to delete node, Services mapped to Node!"

    serviceInstall.sInstall_del_inv_file(node_id)
    timer_arg = {"node_id": node_id, "node_provision_config": node_ins.node_provision_config}
    timer_name = f"NODE_DELETE_TIMER -{str(node_id)}"
    sys_time = cutil_timer_get_app_curr_time()
    current_date = sys_time.strftime("%Y-%m-%d")
    current_time = sys_time.strftime("%H:%M:%S")
    config_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    tf_dir = Path(f"{config_path}/terraform/{node_id}")
    if tf_dir.exists():
        cutil_timer_crontab_start(timer_name, timer_arg, 'cPlatformIO.src.TerraformMgmt.destroy_instance',
                                  current_date, current_time, "Asia/Kolkata",
                                  "ONCE", "cPlatform_dataflow")
    else:
        delete_node_instance(node_id)
    return True, f"Node {node_name} deleted successfully"


def node_edit_request(request_info):
    app_logger.debug(f"node_edit_request, request=={request_info}")
    config_str = request_info.get("node_provision_config")
    if isinstance(config_str, str):
        config = json.loads(config_str)
    elif isinstance(config_str, dict):
        config = config_str
    else:
        config = {}
    node_name = config.get('node_name')
    node_id = config.get('node_id')
    gpu_status = config.get('gpu_status')
    ip_address = config.get('node_ip')
    auth_type = config.get('auth_type')
    username = config.get('username')
    pwd = config.get('password')
    encryption_key_str = config.get('encryption_key')

    if pwd and not encryption_key_str:
        encryption_key_str = ""
    elif encryption_key_str and not pwd:
        pwd = ""

    # Check for duplicate node name
    if Node.objects.filter(node_name=node_name).exclude(node_id=node_id).exists():
        return False, "Node with same name exists", ""

    # Validate IP address
    if not _validate_ip_address(ip_address):
        return False, "Invalid Node IP Address", ""

    # Validate authentication parameters
    if username == '' or (auth_type == "Password" and pwd == '') or (
            auth_type == "EncryptionKey" and not encryption_key_str):
        return False, "Invalid Authentication Parameters", ""

    node_ins = Node.objects.filter(node_id=node_id).first()
    if not node_ins:
        return False, "Node not found", ""
    # Update node fields
    node_ins.node_name = node_name
    node_ins.node_ip = ip_address
    node_ins.auth_type = auth_type
    node_ins.username = username
    node_ins.password = pwd
    node_ins.node_volume = config.get('node_volume')
    node_ins.node_monitor_port = config.get('node_monitor_port')
    node_ins.gpu_status = gpu_status

    encryption_key_path = ""

    if auth_type == "EncryptionKey" and encryption_key_str:
        key_filename = f"{node_id}.pem"
        node_ins.encryption_key_name = key_filename

        pem_dir = os.path.join(settings.BASE_DIR, 'temp_pem')
        os.makedirs(pem_dir, exist_ok=True)
        encryption_key_path = os.path.join(pem_dir, key_filename)

        # Update pem file
        ret, msg = _update_pem_key(node_ins, encryption_key_str, encryption_key_path)
        if not ret:
            return False, msg, ""

    serviceInstall.sInstall_add_inv_file(node_ins.node_id, auth_type, ip_address, username, pwd, encryption_key_path)
    node_ins.save()
    if node_ins.node_ip and node_ins.node_volume:
        deployed, deploy_msg = serviceInstall.sInstall_deploy_node_observability(node_ins)
        if not deployed:
            app_logger.warning(f"Node observability deploy failed for {node_ins.node_id}: {deploy_msg}")
    return True, f"Node {node_ins.node_name} updated successfully", node_ins.node_name


def node_get_config_info(node_id):
    node_info = {}
    node_instance = Node.objects.filter(node_id=node_id).first()

    if node_instance:
        service_info = ServiceConfig.service_get_info__node(node_instance)
        node_info = model_to_dict(node_instance)
        config = node_info.get("node_provision_config", {})
        merged_config = {
            **config,
            **{k: v for k, v in node_info.items() if k != "node_provision_config"}
        }
        merged_config = {
            k: ("" if v is None else v)
            for k, v in merged_config.items()
        }
        merged_config["service_info"] = (
            service_info
        )

        return merged_config
    return {}


def node_launch_request(request_info):
    app_logger.debug(f"node_launch_request, request_info=={request_info}")
    config_str = request_info.get("node_provision_config")
    if isinstance(config_str, str):
        config = json.loads(config_str)
    elif isinstance(config_str, dict):
        config = config_str
    else:
        config = {}
    node_id = config.get('node_id')
    if not node_id:
        return False, "Node ID missing for launch request", ""
    node_ins = Node.objects.filter(node_id=node_id).first()
    if not node_ins:
        return False, "Node not found", ""
    timer_arg = {"node_provision_config": config,
                 "node_id": node_id}
    timer_name = f"NODE_CREATE_TIMER -{str(node_id)}"
    sys_time = cutil_timer_get_app_curr_time()
    current_date = sys_time.strftime("%Y-%m-%d")
    current_time = sys_time.strftime("%H:%M:%S")
    NodeEvent.node_event_add_request(
        node_ins,
        "Launch Instance",
        "Terraform provisioning initiated for launching instance."
    )
    cutil_timer_crontab_start(timer_name, timer_arg, 'cPlatformIO.src.TerraformMgmt.initiate_provision_instance',
                              current_date, current_time, "Asia/Kolkata",
                              "ONCE", "cPlatform_dataflow")
    node_ins.node_provision_config = config

    # Update node fields
    node_ins.save()
    return True, f"Node {node_ins.node_name} launched successfully", node_ins.node_name


def delete_node_instance(node_id):
    if not Node.objects.filter(node_id=node_id).exists():
        return False, "Unable to delete node, Node ID does not exists !"

    node_ins = Node.objects.get(node_id=node_id)
    node_ins.delete()
    return True, f"Node {node_id} deleted successfully"


def node_get_monitoring_stats():
    stats_info = {"cluster_count": ClusterConfig.cluster_get_all_cluster_count(), "node_count": Node.objects.count(),
                  "gpu_node_count": Node.objects.exclude(gpu_status__in=["None", "disabled"]).count(),
                  "live_node_count": Node.objects.filter(service__service_type="InfraPrometheus").distinct().count(),
                  "infra_service_count": ServiceConfig.service_get_infra_service_count,
                  "config_snapshot_count": sum(
                      1 for _ in Path("/iktara/cPlatform/cPlatform/logs/config_snapshots").rglob("config.yaml")
                  ),                  }
    return stats_info
