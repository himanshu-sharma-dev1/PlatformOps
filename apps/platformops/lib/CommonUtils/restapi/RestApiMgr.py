''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : RestAPiValidation.py
* Description       : Common Utility Module supporting RestApi
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
*
*********************************************************************************************************************'''
# Import System Libraries
import json
import jsonschema
from jsonschema.validators import validate
from jsonschema.exceptions import SchemaError


def commonutils_restapi_request_decode(request):
    api_info = json.loads(request.body.decode("utf-8"))
    return api_info


def restapi_request_schema_validation(request_type,api_info):
    restapi_jsonschema = restapi_load_json_schema(request_type,file_name)
    try:
        validate(instance=api_info, schema=restapi_jsonschema)
    except SchemaError as e:
        print("There is an error with the schema")
        return False, {}
    except jsonschema.exceptions.ValidationError as err:
        print(f"Rest Api JsonSchema Error=={err}")
        return False, {}
    return True,{}