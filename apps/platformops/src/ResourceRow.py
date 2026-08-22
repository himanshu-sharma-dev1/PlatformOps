''''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : ResourceRow.py
* Description       : Functions related to Model Resource Allocation
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 2-Aug-23 		Yashveer		            Created.

*2-Sept-24 		Sumit Das		            Updated.
*********************************************************************************************************************'''
import json
import os
from pathlib import Path

# Import System Libraries
from datetime import datetime

# Import Common Local Project functions
from cPlatform.AppLogging import app_logger

# Import Data Models Managed by this Module
from cPlatformIO.models import ModelInfo, ResourceRow
from cPlatformIO.src import ClusterConfig, ServiceConfig
from django.db.models import F

RESOURCE_ROW_BASE_IDX = 1000


def cPlatform_get_mapped_resource_r_id(resource_r_idx):
    resource_r_id = 'RESR' + str(RESOURCE_ROW_BASE_IDX + resource_r_idx)
    return resource_r_id


def cPlatform_get_mapped_resource_r_idx(resource_r_id):
    resource_r_idx = int(resource_r_id.split('RESR')[1]) - RESOURCE_ROW_BASE_IDX
    return resource_r_idx


def cPlatform_add_resource_row(cluster_name, training_server, num_cpu, num_gpu, model_instance):
    # Fetch the service instance based on cluster_name and training_server
    service_ins = ServiceConfig.service_get_instance(training_server)

    # Create a new ResourceRow instance with the service and model instance
    resource_r_instance = ResourceRow.objects.create(service=service_ins,
                                                     num_cpu=int(num_cpu), num_gpu=int(num_gpu),
                                                     Model=model_instance)

    # Map and assign the resource_r_id
    resource_r_instance.resource_r_id = cPlatform_get_mapped_resource_r_id(resource_r_instance.resource_r_idx)
    resource_r_instance.save()

    return service_ins


def cPlatform_delete_all_rows(model_instance):
    rows = ResourceRow.objects.filter(Model=model_instance)

    # Check if there are any rows to delete
    if rows.exists():
        rows.delete()  # Bulk delete all rows
    return


def cPlatform_get_model_resource_data(model_id=None):

    cluster_dict = {}

    if model_id is None:
        resource_r_instance = ResourceRow.objects.all().values()
    else:
        resource_r_instance = ResourceRow.objects.filter(Model__model_id=model_id).annotate(
            training_server=F('service__service_name'),
            service_config=F('service__service_config'),
            cluster_name=F('service__Node__Cluster__cluster_name'),
            cluster_id=F('service__Node__Cluster__cluster_id')).values("cluster_name",
                                                                       "cluster_id",
                                                                       "resource_r_idx",
                                                                       "resource_r_id",
                                                                       "training_server",
                                                                       "service_config",
                                                                       "num_cpu",
                                                                       "num_gpu",
                                                                       "Model")

    resource_info = (dict(enumerate(list(resource_r_instance))))
    cluster_dict['resource_info'] = resource_info
    cluster_dict['training_field_info'] = list(resource_r_instance)
    return cluster_dict


def cPlatform_check_training_server_duplicate(training_server, model_name):
    if ResourceRow.objects.filter(training_server=training_server, Model__model_name=model_name).exists():
        return True, "Training Server Duplicate"
    return False, ""


def cPlatform_get_training_servers_list(model_id):
    training_server = []
    resources = ResourceRow.objects.filter(Model__model_id=model_id)
    for server in resources:
        training_server.append(server.service.service_name)
    return training_server


def cplatform_get_model_resource_info(model_id):
    resource_info_arr = []

    model_instance = ModelInfo.objects.get(model_id=model_id)

    service_ins = model_instance.service

    ret,service_ip,service_port = ServiceConfig.service_get_route(service_ins)

    resource_info = cPlatform_get_model_resource_data(model_id)

    for index, info in resource_info['resource_info'].items():
        info = {
            'training_server': info['training_server'],
            'num_cpu': info['num_cpu'],
            'num_gpu': info['num_gpu'],
            'url': service_ip,
            'port': service_port
        }
        resource_info_arr.append(info)

    return resource_info_arr
