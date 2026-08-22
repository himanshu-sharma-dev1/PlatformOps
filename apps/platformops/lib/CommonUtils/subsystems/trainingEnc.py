''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : training_if.py
* Description       : Common Utility Module supporting Interface between Orachestrator and Training SubSystem
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
*
*********************************************************************************************************************'''

import json
import os
from pathlib import Path
from jsonschema.validators import validate
import jsonschema
import requests
from jsonschema.exceptions import SchemaError
from CommonUtils.logs.AppLogging import utils_logger


def _load_training_json_schema(request_type):
    BASE_DIR = Path(__file__).resolve().parent.parent
    iot_json_file = os.path.join(BASE_DIR, 'subsystems/trainingSchema.json')
    config_dic = json.load(open(iot_json_file))
    config_dic = config_dic[request_type]
    return config_dic


def _encode_model_add_req(model_id, model_info, algo_list, training_server_info):

    model_add_req = {}
    model_add_req['model_id'] = model_id
    model_add_req['request_type'] = "Model-Add"
    model_add_req['model_info'] = model_info

    model_add_req['algo_list'] = []
    for algo_config in algo_list:
        config = {'algo_id': algo_config['algo_id'], 'algo_category': algo_config['algo_category'],
                  'algo_type': algo_config['algo_type'], 'preprocess_type': algo_config['preprocess_type'],
                  'algo_config': algo_config['algo_config']}

        model_add_req['algo_list'].append(config)
    model_add_req['training_server_info'] = {}
    model_add_req['training_server_info']['workload_mgr'] = training_server_info['workload_mgr']
    model_add_req['training_server_info']['server_info'] = []
    model_add_req['training_server_info']['dataset_info'] = training_server_info['dataset_info']
    model_add_req['training_server_info']['file_config_path'] = training_server_info['file_config_path']
    for server_info in training_server_info['server_info']:
        server_info = {
            "training_server": server_info["training_server"], "num_cpu": server_info["num_cpu"],
            "num_gpu": server_info["num_gpu"], "url": server_info["url"], "port": server_info["port"]
        }
        model_add_req['training_server_info']['server_info'].append(server_info)

    json_model_add_req = json.dumps(model_add_req)  # JSON encode the whole Model Add Request
    return json_model_add_req


def _encode_model_del_req(model_id, training_server_info):

    # Extract server info
    server_info = training_server_info.get("server_info", [])

    if not server_info or not isinstance(server_info, list):
        raise ValueError("Error: No valid server info found in training_server_info.")

    # Get the first server details
    training_server = server_info[0]
    url = training_server.get("url")
    port = training_server.get("port")

    if not url or not port:
        raise ValueError("Error: Missing URL or Port in training server info.")

    # Create the model delete request
    model_del_req = {
        'model_id': model_id,
        'request_type': "Model-Del"
    }

    json_model_del_req = json.dumps(model_del_req)  # JSON encode the request
    return json_model_del_req, url, port


def _sendto_training_server(json_req_data):

    # Ensure json_req_data is a dictionary
    if isinstance(json_req_data, str):
        try:
            json_req_data = json.loads(json_req_data)  # Convert string to dict
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")

    # Extract training server details
    server_info = json_req_data.get("training_server_info", {}).get("server_info", [])

    if not server_info or not isinstance(server_info, list) or not server_info[0].get("url") or not server_info[0].get("port"):
        raise ValueError("Error: No valid server info found in request data.")

    # Extract URL and port dynamically
    training_ip = server_info[0]["url"]
    training_port = server_info[0]["port"]
    api_url = 'TrainingServer/APIv1/Training/Add/'
    url = f'http://{training_ip}:{training_port}{api_url}'
    print(f'url--{url}')

    api_response = {}
    try:
        # Use json=json_req_data instead of data=json_req_data
        response = requests.post(url, json=json_req_data)
        response.raise_for_status()  # Raise Exception for HTTP Errors as well.

    except requests.exceptions.ConnectionError as errc:
        err_code = "Error Connecting:" + str(errc)
        return False, err_code, api_response
    except requests.exceptions.Timeout as errt:
        err_code = "Timeout Error:" + str(errt)
        return False, err_code, api_response
    except requests.exceptions.HTTPError as errh:
        err_code = "Http Error:" + str(errh)
        return False, err_code, api_response
    except requests.exceptions.RequestException as err:
        err_code = "Oops: Some Unknown Error Occurred:" + str(err)
        return False, err_code, api_response

    # JSON deserialize the response and send back to caller
    try:
        api_response = response.json()
    except json.JSONDecodeError:
        return False, "Invalid JSON response received from server.", {}

    return True, "", api_response


def _send_dlt_req_to_training_server(json_req_data, training_ip, training_port):

    # Ensure json_req_data is a dictionary
    if isinstance(json_req_data, str):
        try:
            json_req_data = json.loads(json_req_data)  # Convert string to dict
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")

    url = f'http://{training_ip}:{training_port}/'

    api_response = {}
    try:
        # Use json=json_req_data instead of data=json_req_data
        response = requests.post(url, json=json_req_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()  # Raise Exception for HTTP Errors as well.

    except requests.exceptions.ConnectionError as errc:
        err_code = "Error Connecting:" + str(errc)
        return False, err_code, api_response
    except requests.exceptions.Timeout as errt:
        err_code = "Timeout Error:" + str(errt)
        return False, err_code, api_response
    except requests.exceptions.HTTPError as errh:
        err_code = "Http Error:" + str(errh)
        return False, err_code, api_response
    except requests.exceptions.RequestException as err:
        err_code = "Oops: Some Unknown Error Occurred:" + str(err)
        return False, err_code, api_response

    # JSON deserialize the response and send back to caller
    try:
        api_response = response.json()
    except json.JSONDecodeError:
        return False, "Invalid JSON response received from server.", {}

    return True, "", api_response


def cutil_training_api_schema_validation(api_type, api_msg):
    api_schema = _load_training_json_schema(api_type)
    try:
        validate(instance=api_msg, schema=api_schema)
    except SchemaError as errS:
        return False, {f"Schema Validation Failed, ErrorCode={errS}"}
    except jsonschema.exceptions.ValidationError as errJ:
        return False, {f"Rest Api JsonSchema Error={errJ}"}

    return True, {}


def cutil_training_model_add(model_id, model_info, algo_list, training_server_info):
    utils_logger.debug(f"cutil_training_model_add, model_id, model_info, algo_list, training_server_info: "
                       f"{model_id, model_info, algo_list, training_server_info}")

    # Get JSON Encoded Message based on passed information elements
    json_model_add_req = _encode_model_add_req(model_id, model_info, algo_list, training_server_info)

    # Send JSON encoded message to Training Server
    ret_code, err_code, response = _sendto_training_server(json_model_add_req)

    return ret_code, err_code, response


def cutil_training_model_del(model_id, training_server_info):
    utils_logger.debug(f"cutil_training_model_del, model_id: {model_id}")

    # Encode Model Delete Request Message
    json_model_del_req, url, port = _encode_model_del_req(model_id, training_server_info)

    # Send Message to Training Server
    ret_code, err_code, response = _send_dlt_req_to_training_server(json_model_del_req, url, port)

    return ret_code, err_code, response
