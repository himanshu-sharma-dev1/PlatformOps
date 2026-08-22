''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : inference_if.py
* Description       : Common Utility Module supporting Interface between Orchestrator and Inference SubSystem
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 24-July-23 		Nikita		            Created.
* 29-Jan-25 		Sandeep Mahajan         Updated
*
*********************************************************************************************************************'''
import os
import base64
import json
import time
import requests
import jsonschema
from pathlib import Path
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validate
from CommonUtils.logs.AppLogging import utils_logger


def _load_inference_json_schema(request_type):
    BASE_DIR = Path(__file__).resolve().parent.parent
    iot_json_file = os.path.join(BASE_DIR, 'subsystems/Inference_Schema.json')
    config_dic = json.load(open(iot_json_file))
    config_dic = config_dic[request_type]
    return config_dic


def _sendto_inference_server(json_req_data, inference_server_info):
    inference_ip, inference_port = inference_server_info['url'], inference_server_info['port']
    url = f'http://{inference_ip}:{inference_port}/'

    api_response = {}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    try:
        response = requests.post(url, data=json_req_data, headers=headers)
        utils_logger.debug(f"response_from_server for Inference Req= {response.text}")
        # Raise Exception for HTTP Errors as well.
        response.raise_for_status()

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
        err_code = "OOps: Some Unknown Error Occured:" + str(err)
        return False, err_code, api_response

    # JSON de-serialise the response and send back to called
    return True, "", response.text


def cutil_inference_api_schema_validation(api_type, api_msg):
    utils_logger.debug(f"cutil_inference_api_schema_validation, api_type, api_msg = {api_type, api_msg}")

    api_schema = _load_inference_json_schema(api_type)
    try:
        validate(instance=api_msg, schema=api_schema)
    except SchemaError as errS:
        utils_logger.debug(f'Schema Validation Failed": {str(errS)}')
        return False, None
    except jsonschema.exceptions.ValidationError as errJ:
        utils_logger.debug(f'"Rest Api JsonSchema Error": {str(errJ)}')
        return False, None

    return True, json.loads(api_msg)


def _encode_inference_req(model_id, algo_list, inference_data, if_data_type):
    inference_req = {'model_id': model_id, 'algo_list': [], 'inference_data': {}}
    print(f"algo_list = {algo_list}")
    for algo in algo_list:
        algo_info = {
            'algo_id': algo['algo_id'],
            'algo_category': algo['algo_category'],
            'algo_type': algo['algo_type'],
            'preprocess_type': algo['preprocess_type'],
            'algo_enable': algo['algo_enable'],
            'algo_weightage': int(algo.get('algo_weightage', 50)),
            # Default value = 50 if 'algo_weightage' key is missing
            'algo_threshold': int(algo.get('algo_threshold', 20))
            # Default value = 20 if 'algo_threshold' key is missing
        }

        inference_req['algo_list'].append(algo_info)

    inference_req['inference_data'] = {if_data_type: inference_data}

    json_inference_req = json.dumps(inference_req)
    return json_inference_req


def cutil_encode_inference_resp(model_id, status, error_code, rating, algo_result):
    utils_logger.debug(f"cutil_encode_inference_resp, model_id, status, error_code, rating, algo_result: "
                       f"{model_id, status, error_code, rating, algo_result}")

    inference_resp = {'model_id': model_id, 'status': status, 'error_code': error_code, "rating": rating,
                      'algo_result': []}

    if 'inference_type' in algo_result and 'batch_info' not in algo_result and 'Image_Data' in algo_result['inference_type']:
        inference_result = {'Image_Data': {}}
        inference_result['Image_Data']['request_response'] = {}
        inference_result['Image_Data']['request_response']['predictions'] = algo_result['inference_result']
        algo_info = {
            'algo_id': '',
            'algo_status': algo_result['algo_status'],
            'algo_error': algo_result['algo_error'],
            "inference_result": inference_result
        }
        inference_resp['algo_result'].append(algo_info)
    elif 'inference_type' in algo_result and 'batch_info' not in algo_result and 'Batch_Data' in algo_result['inference_type']:
        inference_resp = {'model_id': algo_result['model_id'], 'status': status, 'error_code': error_code,
                          "current_progress": algo_result['current_progress']}
    elif 'model_id' in algo_result and 'batch_info' in algo_result:
        inference_resp = algo_result
    elif 'logs' in algo_result:
        inference_resp = algo_result
    else:
        for algo_key in algo_result:
            inference_result = {'Structure_Data': {}}
            inference_result['Structure_Data']['algo_score'] = algo_result[algo_key]['score']
            inference_result['Structure_Data']['max_score'] = algo_result[algo_key]['max_score']
            if 'additional_info' in algo_result[algo_key]:
                inference_result['Structure_Data']['additional_info'] = algo_result[algo_key]['additional_info']
            algo_info = {
                'algo_id': algo_result[algo_key]['algo_id'],
                'algo_status': algo_result[algo_key]['algo_status'],
                'algo_error': algo_result[algo_key]['algo_error'],
                "inference_result": inference_result
            }
            if 'model_features' in algo_result[algo_key]:
                inference_resp['model_features'] = algo_result[algo_key]['model_features']
            inference_resp['algo_result'].append(algo_info)

    json_inference_resp = json.dumps(inference_resp)
    return json_inference_resp


def cutil_inference_get(model_id, algo_list, inference_data, if_data_type, inference_server_info):

    utils_logger.debug(f"cutil_inference_get, model_id, algo_list, inference_data, if_data_type, inference_server_info: "
                       f"{model_id, algo_list, inference_data, if_data_type, inference_server_info}")

    # JSON encode the whole inference request message
    json_inference_req = _encode_inference_req(model_id, algo_list, inference_data, if_data_type)

    ret_code, err_code, response = _sendto_inference_server(json_inference_req, inference_server_info)
    utils_logger.debug(f"API Resp, ret_code, err_code, response = {ret_code, err_code, response}")
    if not ret_code:
        return False, err_code, response

    # Validate Response Schema
    ret, resp_schema_response = cutil_inference_api_schema_validation('inference_response_schema', response)
    if not ret:
        return False, {}, resp_schema_response

    response = json.loads(response)
    return True, {}, response


def cutil_encode_resnet_inference_resp(model_cat, status, error_code, prediction):
    utils_logger.debug(f"cutil_encode_resnet_inference_resp, model_cat, status, error_code, prediction = "
                       f"{model_cat, status, error_code, prediction}")
    inference_resp = {'model_category': model_cat, 'status': status, 'error_code': error_code, "prediction": prediction}
    json_inference_resp = json.dumps(inference_resp)
    return json_inference_resp

# ---------------------------------------------New Inference Functions-------------------------------------------------#
_INFERENCE_API_URLS = {
    'load':    '/InferenceServer/APIv1/LoadModel/Request/',
    'update':  '/InferenceServer/APIv1/UpdateModel/Request/',
    'delete':  '/InferenceServer/APIv1/DeleteModel/Request/',
    'infer':   '/cPlatformApp/APIv1/Inference/Request/',
}


def _send_to_inference_server(json_req, inference_list, action='load', all_files=None):
    api_url      = _INFERENCE_API_URLS[action]
    return_resp  = action == 'infer'   # only infer needs the response body back

    for server_info in inference_list:
        service_ip   = server_info.get("service_ip")
        service_port = server_info.get("service_port")
        url = f'http://{service_ip}:{service_port}{api_url}'

        try:
            if all_files:
                response = requests.post(url, data={"json_req": json.dumps(json_req)}, files=all_files)
            else:
                response = requests.post(url, data={"json_req": json.dumps(json_req)})

            response.raise_for_status()
            try:
                json_response = response.json()
                if return_resp:
                    return True, json_response   # infer: return actual response
            except json.JSONDecodeError:
                return False, f"Invalid JSON response from {service_ip}:{service_port}"

        except requests.exceptions.ConnectionError  as e:
            return False, f"Connection Error to {service_ip}:{service_port} - {e}"
        except requests.exceptions.Timeout          as e:
            return False, f"Timeout Error from {service_ip}:{service_port} - {e}"
        except requests.exceptions.HTTPError        as e:
            return False, f"HTTP Error from {service_ip}:{service_port} - {e}"
        except requests.exceptions.RequestException as e:
            return False, "No inference server available"

    return True, ""


def _send_to_ocp_server_infer_ai_signal(json_model_send_req, host, port):

    api_url = "/cPlatformApp/APIv1/ocpAI_Signal/Request/"

    # for erver_info in inference_list:
    # service_ip = server_info.get("service_ip")
    # service_port = server_info.get("service_port")
    url = f'http://{host}:{port}{api_url}'
    print("here is the url here ", url)
    try:
        response = requests.post(url, json=json_model_send_req)
        print("HERE IS THE RESPOSNE HERE ", response)
        print("Response JSON:", response.json())
        response.raise_for_status()
        try:
            json_response = response.json()
            return True, json_response

        except json.JSONDecodeError:
            return False, f"Invalid JSON response from {host}:{port}"

    except requests.exceptions.ConnectionError as errc:
        return False, f"Connection Error to {host}:{port} - {errc}"
    except requests.exceptions.Timeout as errt:
        return False, f"Timeout Error from {host}:{port} - {errt}"
    except requests.exceptions.HTTPError as errh:
        return False, f"HTTP Error from {host}:{port} - {errh}"
    except requests.exceptions.RequestException as err:
        return False, "No inference server available"

    return True, ""


def _encode_model_infer_req(model_id, algo_list):
    return {'model_id': model_id, 'algo_list': algo_list}


def _encode_model_infer_delete_req(model_id):
    return {'model_id': model_id}


def _encode_model_infer_send_req(model_id, infer_json_data):
    return {
        'model_id': model_id,
        'inference_data': {
            'Structure_Data': {
                'json_info': infer_json_data
            }
        }
    }


def cutil_inference_model_load(model_id, algo_list, inference_list, all_files):
    json_req = _encode_model_infer_req(model_id, algo_list)
    return _send_to_inference_server(json_req, inference_list, action='load', all_files=all_files)


def cutil_inference_model_update(model_id, algo_list, inference_list, all_files):
    json_req = _encode_model_infer_req(model_id, algo_list)
    return _send_to_inference_server(json_req, inference_list, action='update', all_files=all_files)


def cutil_inference_model_delete(model_id, inference_list):
    json_req = _encode_model_infer_delete_req(model_id)
    return _send_to_inference_server(json_req, inference_list, action='delete')


def cutil_inference_model_send(model_id, infer_json_data, inference_list):
    json_req = _encode_model_infer_send_req(model_id, infer_json_data)
    return _send_to_inference_server(json_req, inference_list, action='infer')


def cutil_inference_ai_signal_send(payload, host, port):
    ret_code, response = _send_to_ocp_server_infer_ai_signal(payload, host, port)
    return ret_code, response
