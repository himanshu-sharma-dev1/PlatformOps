''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : SchemaDwld.py
* Description       : Functions related to Mgmt of Schema
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 13-Jan-25 		Sumit Das		            Created.
*********************************************************************************************************************'''
import json
from CommonUtils.logs.AppLogging import utils_logger


def cutil_get_flow_schema(file_path):

    with open(file_path, 'r') as f:
        json_data = f.read()
        schema_dict = json.loads(json_data)

    utils_logger.debug(f"cutil_get_flow_schema, raw JSON: {json_data}")
    return schema_dict


def convert_row_schema(old_schema, new_schema):

    path = old_schema.get("addPath", "").split()
    add_list = get_add_list(path, new_schema)
    if add_list is None:
        add_list = []

    for key, value in old_schema.items():
        if not isinstance(value, dict):
            continue

        properties = value.get("properties", {})
        if isinstance(properties, dict):
            for p_key, prop in properties.items():
                if isinstance(prop, dict):
                    existing = next(
                        (item for item in add_list if item.get("f_display_name") == prop.get("f_display_name")), None
                    )
                    if existing:
                        existing.setdefault("b_name", []).append(key)
                    else:
                        prop.setdefault("b_name", []).append(key)
                        add_list.append(prop)

    json_schema = json.dumps(new_schema)
    return json_schema


def get_add_list(path, schema):
    for key in path:
        schema = schema.get(key, {})
        if not isinstance(schema, dict):
            return schema if isinstance(schema, list) else []
    return []
