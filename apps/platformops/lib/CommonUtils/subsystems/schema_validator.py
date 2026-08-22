import json
from jsonschema import validate, SchemaError
from importlib.resources import files
from CommonUtils.logs.AppLogging import utils_logger
import jsonschema


def dataflow_schema_validation(api_name, request):
    utils_logger.debug(f"_schema_validation. api_name={api_name}, request={request}")

    try:
        # Read the schema file using importlib_resources
        schema_path = files('CommonUtils.subsystems').joinpath('dataflowSchema.json')
        with schema_path.open('r', encoding='utf-8') as f:
            config_dic = json.load(f)
    except Exception as e:
        utils_logger.error(f"Failed to load schema file: {e}")
        return False, {}

    if api_name not in config_dic:
        return False, {}

    api_schema = config_dic[api_name]
    try:
        validate(instance=request, schema=api_schema)
    except SchemaError as e:
        utils_logger.info(f"Schema error, api_name={api_name}, Error={e}")
        return False, api_schema
    except jsonschema.exceptions.ValidationError as err:
        utils_logger.info(f"Validation failed, api_name={api_name}, Error=={err}")
        return False, api_schema

    return True, api_schema


def training_schema_validation(api_name, request):
    utils_logger.debug(f"_schema_validation. api_name={api_name}, request={request}")

    try:
        # Read the schema file using importlib_resources
        schema_path = files('CommonUtils.subsystems').joinpath('trainingSchema.json')
        with schema_path.open('r', encoding='utf-8') as f:
            config_dic = json.load(f)
    except Exception as e:
        utils_logger.error(f"Failed to load schema file: {e}")
        return False, {}

    if api_name not in config_dic:
        return False, {}

    api_schema = config_dic[api_name]
    try:
        validate(instance=request, schema=api_schema)
    except SchemaError as e:
        utils_logger.info(f"Schema error, api_name={api_name}, Error={e}")
        return False, api_schema
    except jsonschema.exceptions.ValidationError as err:
        utils_logger.info(f"Validation failed, api_name={api_name}, Error=={err}")
        return False, api_schema

    return True, api_schema


def inference_schema_validation(api_name, request):
    utils_logger.debug(f"_schema_validation. api_name={api_name}, request={request}")

    try:
        # Read the schema file using importlib_resources
        schema_path = files('CommonUtils.subsystems').joinpath('inferenceSchema.json')
        with schema_path.open('r', encoding='utf-8') as f:
            config_dic = json.load(f)

    except Exception as e:
        utils_logger.error(f"Failed to load schema file: {e}")
        return False, {}

    if api_name not in config_dic:
        return False, {}

    api_schema = config_dic[api_name]

    try:
        validate(instance=request, schema=api_schema)
    except SchemaError as e:
        utils_logger.info(f"Schema error, api_name={api_name}, Error={e}")
        return False, api_schema
    except jsonschema.exceptions.ValidationError as err:
        utils_logger.info(f"Validation failed, api_name={api_name}, Error=={err}")
        return False, api_schema

    return True, api_schema

