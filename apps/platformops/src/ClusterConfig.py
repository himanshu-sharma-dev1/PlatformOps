'''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : ClusterConfig.py
* Description       : Functions related to Cluster feature
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 31-July-23            Yashveer                            Created.
* 04-April-25           Aniket                              Updated
* 25-April-25           Sumit Das                           Updated
*
*********************************************************************************************************************'''
# Import Data Models Managed by this Module
from cPlatformIO.src import NodeConfig, AppConfig, ServiceConfig
from cPlatformIO.models import Cluster, Node, Service, REPOSITORY_TYPE, IMAGE_STORE, SERVICE_TYPE
from cPlatform.AppLogging import app_logger

CLUSTER_BASE_IDX = 1000


def _get_mapped_cluster_id(cluster_idx):
    cluster_id = 'CLST' + str(CLUSTER_BASE_IDX + cluster_idx)
    return cluster_id


def _normalize_cluster_variant(raw_variant):
    variant_map = {
        'k8s': 'Kubernetes',
        'kubernetes': 'Kubernetes',
        'standalone': 'Standalone',
        'edge': 'Edge',
    }
    normalized = str(raw_variant or '').strip().lower()
    return variant_map.get(normalized, raw_variant if raw_variant in ['Kubernetes', 'Standalone', 'Edge'] else 'Kubernetes')


def _normalize_cluster_role(raw_role):
    normalized = str(raw_role or '').strip()
    if normalized in ['Primary', 'Secondary']:
        return normalized
    return 'Primary' if not Cluster.objects.filter(cluster_type='Primary').exists() else 'Secondary'


def _normalize_image_store(raw_image_store):
    normalized = str(raw_image_store or '').strip().lower()
    if normalized == 'local':
        return 'Local'
    return 'Dockerhub'


def _bootstrap_primary_cluster(cluster_instance):
    node_ins = Node.objects.create(Cluster=cluster_instance)
    node_id = NodeConfig._get_mapped_node_id(node_ins.node_idx)
    node_ins.node_id = node_id
    node_ins.node_name = node_id
    node_ins.node_provision_config = {
        'node_name': node_id,
        'node_ip': str(node_ins.node_ip or '0.0.0.0'),
        'auth_type': node_ins.auth_type,
        'username': node_ins.username,
        'password': node_ins.password or '',
        'gpu_status': node_ins.gpu_status or 'disabled',
        'node_volume': node_ins.node_volume,
        'node_monitor_port': node_ins.node_monitor_port,
    }
    node_ins.save()
    ServiceConfig.service_add_request(node_id, 'AIOrchestrator')


def cluster_get_instance(cluster_id):
    cluster_instance = Cluster.objects.get(cluster_id=cluster_id)
    return cluster_instance


def cluster_add_request(request_info):
    app_logger.debug(f"cluster_add_request, request={request_info}")

    cluster_name = request_info['cluster_name']
    cluster_variant = _normalize_cluster_variant(request_info.get('cluster_type_varient', request_info.get('cluster_type')))
    cluster_type = _normalize_cluster_role(request_info.get('cluster_type_role', request_info.get('cluster_type')))
    repo_type = request_info['repo_type']
    image_store_type = _normalize_image_store(request_info.get('Image_store'))
    cluster_region = request_info['cluster_region']
    cluster_env = request_info['cluster_env']
    description = request_info['description']
    image_store_path = request_info.get('imagePath') if image_store_type == "Local" else None

    # Validate cluster name
    if not cluster_name:
        return False, "Cluster name cannot be empty", ""

    # Check if the cluster already exists
    if Cluster.objects.filter(cluster_name=cluster_name).exists():
        return False, "Cluster with this Name already exists", ""

    # If Image Store is 'Local', ensure a path is provided
    if image_store_type == "Local" and not image_store_path:
        return False, "Please provide a valid path for Local Image Store", ""

    # Check if Primary already exist
    if cluster_type == 'Primary' and Cluster.objects.filter(cluster_type=cluster_type).exists():
        return False, "Primary Cluster already exist", ""

    if cluster_type != 'Primary' and not Cluster.objects.filter(cluster_type='Primary').exists():
        return False, "Please create Primary cluster first", ""

    # Create a new Cluster instance
    cluster_instance = Cluster.objects.create(
        cluster_name=cluster_name, repo_type=repo_type, image_store_type=image_store_type,
        cluster_type=cluster_type, region=cluster_region, environment=cluster_env, description=description,
        cluster_type_varient=cluster_variant,
        image_store_path=image_store_path if image_store_type == "Local" else None)

    # Generate and assign cluster_id
    cluster_id = _get_mapped_cluster_id(cluster_instance.cluster_idx)
    cluster_instance.cluster_id = cluster_id
    cluster_instance.save()

    if cluster_type == 'Primary':
        _bootstrap_primary_cluster(cluster_instance)

    return True, f"Cluster {cluster_instance.cluster_name} added successfully", cluster_id


def cluster_update_request(request_info):
    app_logger.debug(f"cluster_update_request, request={request_info}")

    cluster_id = request_info.get('cluster_id')
    if not cluster_id or not Cluster.objects.filter(cluster_id=cluster_id).exists():
        return False, "Cluster does not exist", ""

    cluster_instance = Cluster.objects.get(cluster_id=cluster_id)
    cluster_variant = _normalize_cluster_variant(request_info.get('cluster_type_varient', request_info.get('cluster_type')))
    image_store_type = _normalize_image_store(request_info.get('Image_store'))
    image_store_path = request_info.get('imagePath') if image_store_type == 'Local' else None

    cluster_instance.region = request_info.get('cluster_region', cluster_instance.region)
    cluster_instance.environment = request_info.get('cluster_env', cluster_instance.environment)
    cluster_instance.description = request_info.get('description', cluster_instance.description)
    cluster_instance.repo_type = request_info.get('repo_type', cluster_instance.repo_type)
    cluster_instance.image_store_type = image_store_type
    cluster_instance.image_store_path = image_store_path
    cluster_instance.cluster_type_varient = cluster_variant
    cluster_instance.save()

    return True, f"Cluster {cluster_instance.cluster_name} updated successfully", cluster_id


def cluster_delete_request(request_info):
    app_logger.debug(f"cluster_delete_request, request={request_info}")

    cluster_id = request_info.get('cluster_id', '')
    if cluster_id != '':
        if Cluster.objects.filter(cluster_id=cluster_id).exists():
            cluster_inst = Cluster.objects.get(cluster_id=cluster_id)
            cluster_name = cluster_inst.cluster_name

            if cluster_inst.cluster_type == 'Primary' and Cluster.objects.filter(cluster_type='Secondary').exists():
                return False, "Please delete all Secondary Clusters first"

            if NodeConfig.node_get_info__cluster(cluster_inst):
                return False, "Cluster has active Nodes !"

            cluster_inst.delete()
            return True, f"Cluster {cluster_name} Deleted Successfully"
    return False, "Failed to Delete Cluster"


def cluster_get_config_options():
    cluster_options, repo_options, image_store_options = {}, [], []
    for items in REPOSITORY_TYPE:
        repo_options.append(items[1])
    cluster_options['repo_options'] = repo_options

    for items in IMAGE_STORE:
        image_store_options.append(items[1])
    cluster_options['image_store_options'] = image_store_options

    app_logger.debug(f"cluster_get_config_options, cluster_options={cluster_options}")
    return cluster_options


def cluster_get_config_info(cluster_id=None):
    app_logger.debug(f"cluster_get_config_info, cluster_id={cluster_id}")

    index, cluster_info = 0, {}
    cluster_instance = Cluster.objects.all().order_by('cluster_idx') if cluster_id is None else Cluster.objects.filter(cluster_id=cluster_id)

    for cluster in cluster_instance:
        index = index + 1
        # Get total cluster resources
        cluster_resources = NodeConfig.cluster_total_resources(cluster)

        cluster_info[index] = {}
        cluster_info[index]['cluster_id'] = cluster.cluster_id
        cluster_info[index]['cluster_name'] = cluster.cluster_name
        cluster_info[index]['node_info'] = NodeConfig.node_get_info__cluster(cluster)
        cluster_info[index]['service_counts'] = NodeConfig.node_get_service_count(cluster)

        # Added totals
        cluster_info[index]['total_vcpus'] = cluster_resources['total_vcpus']
        cluster_info[index]['total_memory'] = cluster_resources['total_memory']

        cluster_info[index]['cluster_type'] = cluster.cluster_type
        cluster_info[index]['repo_type'] = cluster.repo_type
        cluster_info[index]['image_store_type'] = cluster.image_store_type
        cluster_info[index]['region'] = cluster.region
        cluster_info[index]['description'] = cluster.description
        cluster_info[index]['environment'] = cluster.environment
        cluster_info[index]['cluster_type_varient'] = cluster.cluster_type_varient
    app_logger.debug(f"cluster_get_config_info, cluster_info={cluster_info}")

    return cluster_info

# cluster_get_config_info optimized version
def cluster_get_config_info_v2(cluster_id=None):
    """
    Optimized version of cluster_get_config_info().

    Output format is intentionally kept IDENTICAL to the existing
    cluster_get_config_info() so that no frontend/template changes
    are required.

    Optimization:
    - Fetch Cluster(s)
    - Fetch all Nodes once
    - Fetch all Services once
    - Build hierarchy completely in memory
    - Remove per-node Service queries
    """
    from collections import defaultdict
    from django.db.models import Sum, IntegerField
    from django.db.models.functions import Cast
    from django.db.models.expressions import RawSQL

    app_logger.debug(f"cluster_get_config_info_v2, cluster_id={cluster_id}")
    print(f"cluster_get_config_info_v2, cluster_id={cluster_id}")

    cluster_info = {}
    index = 0

    # ------------------------------------------------------------------
    # Get Cluster(s)
    # ------------------------------------------------------------------
    clusters = (
        Cluster.objects.filter(cluster_id=cluster_id)
        if cluster_id else Cluster.objects.all().order_by("cluster_idx")
    )

    cluster_list = list(clusters)
    if not cluster_list:
        return {}

    # ------------------------------------------------------------------
    # Get all Nodes for selected clusters (ONE QUERY)
    # ------------------------------------------------------------------
    nodes = list(Node.objects.filter(Cluster__in=cluster_list).order_by("node_idx"))

    # ------------------------------------------------------------------
    # Total Resources (ONE QUERY)
    # ------------------------------------------------------------------
    resource_rows = (
        Node.objects.filter(Cluster__in=cluster_list).annotate(
            vcpu_int=Cast(
                RawSQL("node_provision_config->>'vcpu'", []), IntegerField(),
            ),
            memory_int=Cast(
                RawSQL("node_provision_config->>'memory'", []), IntegerField(),
            ),
        )
        .values("Cluster_id")
        .annotate(
            total_vcpus=Sum("vcpu_int"),
            total_memory=Sum("memory_int"),
        )
    )

    resource_map = {
        row["Cluster_id"]: {
            "total_vcpus": row["total_vcpus"] or 0,
            "total_memory": row["total_memory"] or 0,
        }
        for row in resource_rows
    }

    # ------------------------------------------------------------------
    # Get all Services for all Nodes (ONE QUERY)
    # ------------------------------------------------------------------
    services = list(Service.objects.filter(Node__in=nodes).order_by("service_idx").values())

    # ------------------------------------------------------------------
    # Group services by node
    # ------------------------------------------------------------------
    services_by_node = defaultdict(list)

    for service in services:
        service["Application_id"] = service.get("Application_id") or ""
        services_by_node[service["Node_id"]].append(service)

    # ------------------------------------------------------------------
    # Build node info grouped by cluster
    # ------------------------------------------------------------------
    nodes_by_cluster = defaultdict(dict)
    service_count_by_cluster = defaultdict(int)
    node_counter = defaultdict(int)

    for node in nodes:
        node_counter[node.Cluster_id] += 1
        node_index = node_counter[node.Cluster_id]

        node_services = {}

        for idx, service in enumerate(
            services_by_node.get(node.node_idx, []), start=1
        ):
            node_services[idx] = service

        service_count_by_cluster[node.Cluster_id] += len(node_services)

        nodes_by_cluster[node.Cluster_id][node_index] = {
            "node_name": node.node_name or "",
            "node_id": node.node_id or "",
            "node_idx": node.node_idx or "",
            "ip_address": node.node_ip or "",
            "username": node.username or "",
            "password": node.password or "",
            "service_info": node_services,
            "node_provision_config": node.node_provision_config or {},
        }

    # ------------------------------------------------------------------
    # Build final output (SAME FORMAT AS OLD FUNCTION)
    # ------------------------------------------------------------------
    for cluster in cluster_list:
        index += 1

        resources = resource_map.get(
            cluster.cluster_idx,
            {
                "total_vcpus": 0,
                "total_memory": 0,
            },
        )

        cluster_info[index] = {}

        cluster_info[index]["cluster_id"] = cluster.cluster_id
        cluster_info[index]["cluster_name"] = cluster.cluster_name
        cluster_info[index]["node_info"] = nodes_by_cluster.get(cluster.cluster_idx, {})
        cluster_info[index]["service_counts"] = service_count_by_cluster.get(cluster.cluster_idx, 0)
        cluster_info[index]["total_vcpus"] = resources["total_vcpus"]
        cluster_info[index]["total_memory"] = resources["total_memory"]

        cluster_info[index]["cluster_type"] = cluster.cluster_type
        cluster_info[index]["repo_type"] = cluster.repo_type
        cluster_info[index]["image_store_type"] = cluster.image_store_type
        cluster_info[index]["region"] = cluster.region
        cluster_info[index]["description"] = cluster.description
        cluster_info[index]["environment"] = cluster.environment
        cluster_info[index]["cluster_type_varient"] = cluster.cluster_type_varient

    app_logger.debug(f"cluster_get_config_info_v2, cluster_info={cluster_info}")

    return cluster_info

def cluster_get_service_list(cluster_id=None, service_type=None):
    app_logger.debug(f"cluster_get_service_list, cluster_id={cluster_id}, service_type={service_type}")

    cluster_info = {}
    cluster_instance = Cluster.objects.all().order_by('cluster_idx') if cluster_id is None else Cluster.objects.filter(cluster_id=cluster_id)
    for cluster in cluster_instance:
        service_list = NodeConfig.node_get_service_list(cluster, service_type)
        cluster_info.update({cluster.cluster_name: service_list})

    app_logger.debug(f"cluster_info={cluster_info}..")
    return cluster_info


def cluster_get_service_mapping(cluster_id=None):
    app_logger.debug(f"cluster_get_service_mapping, cluster_id={cluster_id}")

    cluster_info = {}
    cluster_instance = Cluster.objects.all().order_by('cluster_idx') if cluster_id is None else Cluster.objects.filter(cluster_id=cluster_id)
    for cluster in cluster_instance:
        service_mapping = NodeConfig.node_get_service_mapping(cluster)
        cluster_info.update({cluster.cluster_name: service_mapping})
    app_logger.debug(f"cluster_map_info={cluster_info}..")
    return cluster_info


def cluster_get_name_list():
    cluster_list = list(Cluster.objects.all().order_by('cluster_idx').values_list('cluster_name', flat=True))
    app_logger.debug(f"cluster_get_name_list, cluster_list={cluster_list}")
    return cluster_list

def cluster_get_monitoring_tree():
    cluster_tree = {}
    clusters = Cluster.objects.prefetch_related("node_set__service_set").all().order_by('cluster_idx')
    
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

    for cluster in clusters:
        cluster_tree[cluster.cluster_name] = {}
        for node in cluster.node_set.all().order_by('node_idx'):
            cluster_tree[cluster.cluster_name][node.node_name] = [
                {
                    "serviceName": service.service_name,
                    "serviceType": service.service_type,
                } for service in node.service_set.all().order_by('service_idx')
                if str(service.service_type or "").strip().lower() not in EXCLUDED_SERVICE_TYPES
            ]

    return cluster_tree


def cluster_monitoring_tree():
    cluster_tree = {}
    clusters = Cluster.objects.prefetch_related("node_set__service_set").all().order_by('cluster_idx')

    for cluster in clusters:
        cluster_tree[cluster.cluster_name] = {}
        for node in cluster.node_set.all().order_by('node_idx'):
            cluster_tree[cluster.cluster_name][node.node_name] = [
                {
                    "serviceName": service.service_name,
                    "serviceType": service.service_type,
                } for service in node.service_set.all().order_by('service_idx')
            ]

    return cluster_tree

def cluster_get_all_cluster_count():
    return Cluster.objects.count()
