
// Parameter List
function fetchParams(keys, schema){
    let intParamList = [];
    let enumParamList = [];
    let wholeList = []
    keys.forEach((key) => {
        let values = schema[key];
        if (values.handling == 'process') {
            if (values.datatype == 'integer' || values.datatype == "unit_value") {
                let auditParam = {
                    'dataType': values.datatype,
                    'param_name': values.display_name,
                    'int_key' : values.int_key,
                    'min': values.min,
                    'max': values.max
                };
                intParamList.push(auditParam);
                wholeList.push(auditParam);
            }
            if (values.datatype == 'enum') {
                let auditParam = {
                    'dataType': values.datatype,
                    'param_name': values.display_name,
                    'int_key' : values.int_key,
                    'list': values.value_list,
                };
                enumParamList.push(auditParam);
                wholeList.push(auditParam);
            }
        }
    });
    return [intParamList, enumParamList, wholeList];
}


// get Display name
function fetch_displayName(paramName, wholeList){
    let param_name = wholeList.filter((val)=>{
        return val.int_key == paramName
    })

    return param_name[0].param_name
}


// Get Parameter
function GetParameter(schema){
   let parameter = []
   let keys = Object.keys(schema)
   keys.forEach((key)=>{
        let data = schema[key]
        if(data.handling == 'process'){
            parameter.push(data.display_name)
        }
   })
   return parameter
}
// Get Integer Parameter
function GetIntegerParameter(schema){
   let parameter = []
   let keys = Object.keys(schema)
   keys.forEach((key)=>{
        let data = schema[key]
        if(data.handling == 'process' && data.datatype == "integer"){
            parameter.push(data.display_name)
        }
   })
   return parameter
}



// New Schema Functions
function schema_mgr_get_param_list(m_schema, data_type_list) {
   let param_list = [];
   let m_keys = m_schema ? Object.keys(m_schema) : []

   m_keys.forEach((key) => {
       let attr = m_schema[key];
       if (attr.handling === 'process' && data_type_list.includes(attr.datatype)) {
           param_list.push(attr.display_name);
       }
   });
   return param_list;
}


function schema_mgr_get_param_info(m_schema, param_name){
   param_info = {}
   let m_keys = m_schema ?  Object.keys(m_schema) : []
   if( m_keys.length > 0)m_keys.forEach((key)=>{
       let attr = m_schema[key]
       if(attr.display_name == param_name || attr.int_key == param_name){
            param_info = {
                'dataType': attr.datatype,
                'param_name': attr.display_name,
                'int_key' : attr.int_key,
                'min': attr.min,
                'max': attr.max,
                'val_list': attr.value_list
            }
       }

   })
   return param_info
}


function operationList(schema , param){
    let opList = []
    let schemaKeys = Object.keys(schema)
    schemaKeys.forEach((key)=>{
        let schemaObj = schema[key]
        if(schemaObj.display_name == param){
            opList = schemaObj.ops_list
        }
    })
    return opList
}

//Validate Schema
function validateSchema(schema) {
    let oemKeys = Object.keys(schema);

    for (let oem_key of oemKeys) {
        let oem_schema = schema[oem_key];
        let keys = Object.keys(oem_schema);

        // First, filter the objects where handling is "process"
        let filterObject = keys
            .filter((key) => oem_schema[key]['handling'] === 'process')
            .map((key) => oem_schema[key]);

        let intKeySet = new Set();
        let displayKeySet = new Set();

        for (let obj of filterObject) {
            if (intKeySet.has(obj.int_key)) {
                let message = `Invalid schema for ${oem_key}: Duplicate int_key ${obj.int_key}`;
                return { "isUnique": false, "message": message };
            }
            if (displayKeySet.has(obj.display_name)) {
                let message = `Invalid schema for ${oem_key}: Duplicate display_name ${obj.display_name}`;
                return { "isUnique": false, "message": message };
            }

            intKeySet.add(obj.int_key);
            displayKeySet.add(obj.display_name);
        }
    }

    return { "isUnique": true, "message": "" };
}



// Make Global
window.GetParameter = GetParameter
window.fetch_displayName = fetch_displayName
window.schema_mgr_get_param_info = schema_mgr_get_param_info
window.schema_mgr_get_param_list = schema_mgr_get_param_list


