''''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : Appconfig.py
* Description       : Functions related to Application Configuration
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
*            				                Created.
* 15-July-23        Yogita                  Edit Model Configurations.
* 07-April-25       Aniket                  Updated
*********************************************************************************************************************'''
# Import System Libraries
import os
import json
import yaml
from datetime import datetime
from pathlib import Path

# Import Logger
from cPlatform.AppLogging import app_logger

# Import DataModel Definitions
from cPlatformIO.models import ApplicationInfo, APPLICATION_TYPE, AlgoInfo, Cluster, Node
from cPlatformIO.src import ServiceConfig


# Initialize Global Variables
APP_BASE_IDX = 1000

# ----------------------------------------Utility Functions--------------------------------------------------------

def get_first_app_ins():
    app_ins = ApplicationInfo.objects.first()
    if app_ins:
        app_logger.debug(f"get_first_app_ins, app_ins={app_ins.app_name}")
        return app_ins
    else:
        app_logger.debug("No application instances found.")
        return None


def _get_mapped_app_id(application_idx):
    app_logger.debug(f"get_mapped_app_id, app_idx=={application_idx}")
    app_id = 'APP' + str(APP_BASE_IDX + application_idx)
    return app_id


def _check_app_exists(app_name):
    if ApplicationInfo.objects.filter(app_name=app_name).exists():
        app_logger.debug(f"application exists")
        return True
    app_logger.debug(f"application does not exists !")
    return False


def _check_services_valid_add(app_config):
    app_logger.debug(f"_check_services_valid_add, app_config=={app_config}")

    service_list = []
    for config in app_config:
        service_name = config.get("services")
        # Check for Duplicate Service Name
        if service_name in service_list:
            app_logger.debug(f"Check Failed, Duplicate Service={service_name} !")
            return False

        # Check Service is not mapped to any application. One Service can be mapped to one Application only..
        if ServiceConfig.service_check_app_mapping(service_name):
            app_logger.debug(f"Check Failed, Service ={service_name} already mapped to Application !")
            return False

        service_list.append(service_name)

    app_logger.debug(f"Service List in Application are Valid!")
    return True


def _check_services_valid_edit(app_name, app_config):
    app_logger.debug(f"_check_services_valid_edit, app_name, app_config={app_name, app_config}")

    app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
    curr_ser_list, new_ser_list = set(), set()

    for config in app_ins.app_config: # Create set for curr_ser_list
        curr_ser_list.add(config.get("services"))

    for config in app_config:
        service_name = config.get("services")

        # Check for Duplicate Service Name
        if service_name in new_ser_list:
            app_logger.debug(f"Check Failed, Duplicate Service={service_name} !")
            return False

        new_ser_list.add(service_name)

        # Check Service is not mapped to any application. One Service can be mapped to one Application only..
        if service_name not in curr_ser_list and ServiceConfig.service_check_app_mapping(service_name):
            app_logger.debug(f"Check Failed, Service ={service_name} already mapped to Application !")
            return False
    for service_name in curr_ser_list - new_ser_list:
        if not ServiceConfig.service_check_mapped_usage(service_name):
            app_logger.debug(f"Check Failed, Service ={service_name} in Use by Model or Dataflow !")
            return False

    return True


def _check_services_valid_delete(app_name):
    if not ApplicationInfo.objects.filter(app_name=app_name).exists():
        return False

    app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
    for config in app_ins.app_config:
        service_name = config.get("services")

        if not ServiceConfig.service_check_mapped_usage(service_name):
            app_logger.debug(f"Check Failed, Service ={service_name} in Use by Model or Dataflow !")
            return False
    return True


def get_app_lists():
    app_names = list(ApplicationInfo.objects.values_list('app_name', flat=True))
    app_logger.debug(f"Fetched application list: {app_names}")
    return app_names


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


def app_add_request(request):
    app_logger.debug(f"app_add_request, request: {request}")

    # Extract 'json_data' and parse JSON
    json_data = request.POST.get('json_data')
    if not json_data:
        return False, "Missing JSON data in request"

    # Extract necessary fields
    app_json = json.loads(json_data)  # Convert JSON string to dictionary
    app_name = app_json.get('app_name')

    app_config = app_json['app_config']

    # Check if application type and application name does not exist !
    if _check_app_exists(app_name):
        return False, f"Failed to add application: {app_name} already exists"

    # Check services are valid (not mapped to any application currently)!
    if not _check_services_valid_add(app_config):
        return False, f"Failed to add application: Service already Mapped or Duplicate Services in Configuration"

    # Create new application instance
    app_ins = ApplicationInfo.objects.create(app_name=app_name, app_config=app_config,
                                                  created_date=datetime.now())

    # Generate application ID and update instance
    app_id = _get_mapped_app_id(app_ins.application_idx)
    app_ins.app_id = app_id

    # Update Application mapping in services
    for config in app_config:
        ServiceConfig.service_update_app_mapping(config.get("services"), app_ins)

    app_ins.save()

    return True, f"Application '{app_name}' added successfully"


def app_edit_request(request):
    app_logger.debug(f"app_edit_request, request: {request}")

    # Extract 'json_data' and parse JSON
    json_data = request.POST.get('json_data')
    if not json_data:
        return False, "Missing JSON data in request"

    # Parse JSON data from request
    app_json = json.loads(json_data)
    app_name, app_config = app_json.get('app_name'), app_json['app_config']

    # Fetch the application instance
    app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
    if not app_ins:
        return False, f"Application {app_json.get('app_name')} not exists"

    if not _check_services_valid_edit(app_name, app_config):
        return False, f"New Service List not valid !"

    curr_ser_list = set(config.get("services") for config in app_ins.app_config)
    new_ser_list = set(config.get("services") for config in app_config)

    # Unmap services that are removed in new config
    for service_name in curr_ser_list - new_ser_list:
        ServiceConfig.service_update_app_mapping(service_name, None)

    # Map newly added services to this application
    for service_name in new_ser_list - curr_ser_list:
        ServiceConfig.service_update_app_mapping(service_name, app_ins)

    app_ins.app_config = app_config
    app_ins.save()

    return True, f"Application {app_json.get('app_name')} edited successfully"


def app_delete_request(request):
    app_logger.debug(f"app_delete_request, request: {request}")
    # Extract required fields
    app_name = request.POST.get('app_name')
    if not _check_services_valid_delete(app_name):
        return f'Application "{app_name}" can not be Deleted, services in use currently !'

    # Remove all Application mapping in the service
    app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
    for config in app_ins.app_config:
        ServiceConfig.service_update_app_mapping(config.get("services"), None)

    ApplicationInfo.objects.filter(app_name=app_name).delete()
    app_logger.debug(f"app_delete_request: application {app_name} Deleted Successfully..")
    return f'Application "{app_name}" Deleted Successfully...'


def app_get_config_options():
    app_logger.debug(f"app_get_config_options..")

    file_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    yaml_data = _read_yaml_file(f"{file_path}/cPlatform_config.yaml")

    serv_options = {'serv_keys': yaml_data.get('SERVICE_KEYS', {})}
    app_logger.debug(f"serv_options = {serv_options}")
    return serv_options


def app_get_config_info():
    app_info = []
    for app in ApplicationInfo.objects.all():
        mapped_services = []
        if isinstance(app.app_config, list):
            for config in app.app_config:
                service_name = config.get("services")
                keys = json.loads(config.get("keys", "[]")) if isinstance(config.get("keys"), str) else config.get(
                    "keys", [])
                mapped_services.append({service_name: ", ".join(keys)})

        formatted_date = app.created_date.strftime('%d-%b-%Y') if app.created_date else None
        app_info.append({"app_name": app.app_name, "created_date": formatted_date,
                         "mapped_services": mapped_services, "app_config": app.app_config})
    app_logger.debug(f"app_get_config_info, app_info={app_info}")
    return app_info


# def app_route_service(app_name, user_key, serv_type):
#     app_logger.debug(f"app_route_service, app_name={app_name}, user_key={user_key}, serv_type={serv_type}")
#     print('app_name&&&', app_name)
#     print("user_key&&&", user_key)
#     app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
#     if not app_ins:
#         app_logger.debug(f"App Name {app_name} not found in ApplicationInfo")
#         return False, None, None
#     print("serv_type:", serv_type)
#     serv_name_list = ServiceConfig.service_get_ins_type(serv_type, app_name)
    # config_root = Path(__file__).resolve().parent.parent.parent / 'config'
    # config_data = _read_yaml_file(str(config_root / 'cPlatform_config.yaml'))
    # dep_type = config_data.get('CPLATFORM_CONFIG', {}).get('deployment_type', '')

    # If running inside Docker and service uses LOCAL networking
    # if dep_type == 'DOCKER' and ServiceConfig.get_network_method(serv_type) == 'LOCAL':
    #     try:
    #         docker_info = _read_yaml_file(str(config_root / 'service_install.yaml'))["services"][serv_type]["Docker_Info"][serv_type]
    #         return True, docker_info["Int_IP_Addr"], docker_info["Int_Port"]
    #     except KeyError as e:
    #         app_logger.error(f"Missing key in YAML config for '{serv_type}': {e}")
    #         return False, None, None

    # Match based on user_key or "Default", without serv_name filtering

    # matched_config = None
    # app_configs = app_ins.app_config if isinstance(app_ins.app_config, list) else []
    #
    # for config in app_configs:
    #     keys = config.get("keys", [])
    #     config_keys = json.loads(keys) if isinstance(keys, str) else keys
    #     services = config.get("services", [])
    #
    #     # Ensure `services` is a list of service names or dicts with names
    #     if isinstance(services, dict):
    #         services = list(services.keys())
    #     elif isinstance(services, str):
    #         services = [services]
    #
    #     is_service_matched = serv_name in services
    #
    #     if is_service_matched:
    #         if user_key and user_key in config_keys:
    #             matched_config = config
    #             break
    #         elif not user_key and "Default" in config_keys:
    #             matched_config = config
    #         elif "Default" in config_keys and matched_config is None:
    #             matched_config = config
    #
    # print(f"[DEBUG] Matched Config: {matched_config}")
    # if matched_config:
    #     ser_ins = ServiceConfig.service_get_instance(matched_config.get("services"))
    #     if ser_ins and ser_ins.Node:
    #         return True, ser_ins.Node.node_ip, ser_ins.service_port
    #
    # return False, None, None


def app_route_service(app_name, user_key, serv_type):
    app_logger.debug(f"app_route_service, app_name={app_name}, user_key={user_key}, serv_type={serv_type}")

    app_ins = ApplicationInfo.objects.filter(app_name=app_name).first()
    if not app_ins:
        app_logger.debug(f"App Name '{app_name}' not found in ApplicationInfo")
        return False, None, None
    if not user_key.strip():
        user_key = "Default"
    serv_name_list = ServiceConfig.service_get_ins_type(serv_type, app_name)
    print("serv_name_list:", serv_name_list)
    config_root = Path(__file__).resolve().parent.parent.parent / 'config'
    config_data = _read_yaml_file(str(config_root / 'cPlatform_config.yaml'))
    dep_type = config_data.get('CPLATFORM_CONFIG', {}).get('deployment_type', '')

    #If running inside Docker and service uses LOCAL networking
    if dep_type == 'DOCKER' and ServiceConfig.service_network_state(serv_name_list[0]) == 'LOCAL':
        try:
            docker_info = _read_yaml_file(str(config_root / 'service_install.yaml'))["services"][serv_type]["Docker_Info"][serv_type]
            return True, docker_info["Int_IP_Addr"], docker_info["Int_Port"]
        except KeyError as e:
            app_logger.error(f"Missing key in YAML config for '{serv_type}': {e}")
            return False, None, None

    if not serv_name_list:
        app_logger.debug(f"No service names found for type '{serv_type}' and app '{app_name}'")
        return False, None, None

    app_configs = app_ins.app_config if isinstance(app_ins.app_config, list) else []

    for serv_name in serv_name_list:
        for config in app_configs:
            keys = config.get("keys", [])
            config_keys = json.loads(keys) if isinstance(keys, str) else keys

            services = config.get("services", [])
            if isinstance(services, str):
                services = [services]
            elif isinstance(services, dict):
                services = list(services.keys())

            if serv_name in services and user_key in config_keys:
                matched_config = config
                break
        else:
            continue
        break

    else:
        app_logger.debug("No matching service config found with user_key or 'Default'")
        return False, None, None

    # Get service instance from ServiceConfig helper
    ser_ins = ServiceConfig.service_get_instance(matched_config.get("services"))
    if ser_ins and ser_ins.Node:
        return True, ser_ins.Node.node_ip, ser_ins.service_port

    app_logger.debug("Service instance not found or missing Node info")
    return False, None, None






