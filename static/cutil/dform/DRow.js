import {dCreateMultiSelect} from './DMultiSelect.js'
import {_dFormHandleDynamicRows} from './DForm.js'


//create Parent Row Container
export function dRow_ContainerCreate(parentContainer , con_id, schema){
    let div = document.createElement('div')
    div.id = con_id
    div.classList.add('mt-2', schema['e_name'])

    if (schema['e_display']) {
       div.style.display = 'block';
    } else {
        div.style.display = 'none';
    }
    parentContainer.appendChild(div)
    return div
}

// Create Row
export function dRow_Create(action, parentContainer, row_schema, buttonObj){
    let f_row_container =  document.createElement('div')
    f_row_container.classList.add('row', 'mt-2')

    parentContainer.appendChild(f_row_container)
    let inputListType = ["text", "email", "number", "password", "date", "time", "date_range", "tel", "file"]

    row_schema.forEach((field_schema)=>{

        if(inputListType.includes(field_schema.f_type)){
           _createInputFields(action, field_schema, f_row_container)
        }
        else if(field_schema.f_type === "single_select"){
            _createSingleSelectFields(action, field_schema, f_row_container)
        }
        else if(field_schema.f_type === "data_list"){
            _createDataList(field_schema, f_row_container)
        }
        else if(field_schema.f_type === "multi_select"){
            dCreateMultiSelect(field_schema, f_row_container)
        }
    })

    if(buttonObj){
        parentContainer.style.border = "0.5px dotted black";
        parentContainer.style.padding = "10px";
        parentContainer.style.borderRadius = "5px";

        let buttonCon =  document.createElement('div')
        buttonCon.textContent = buttonObj['buttonText']
        buttonCon.classList.add('addButton', 'col-lg-2', 'mt-4')
        buttonCon.style.cssText = 'cursor : pointer'
        buttonCon.setAttribute('onclick', buttonObj['buttonFun'])

        buttonCon.style.setProperty('display', 'block', 'important');
        // Append Delete Button
        f_row_container.appendChild(buttonCon)
    }
}


//Add Row
export function dRowAdd(event, schema){

    let parentContainer = event.target.parentNode.parentNode;
    let rowSchema, buttonCon

    if (parentContainer.parentNode.classList[0] === "accordion-body") {
        let topAccordianConId = event.target.parentNode.closest('.accordion').parentNode.parentNode.id;
        let accId = topAccordianConId.includes('_') ? topAccordianConId.split('_')[0] : topAccordianConId

        rowSchema = schema[accId]['row_Schema'][parentContainer.id]['row_Schema'];

        buttonCon = {
            buttonText: '-',
            buttonFun: 'dFormRowDelete(event)'
        };
    } else {
        rowSchema = schema[parentContainer.id]['row_Schema'];
        buttonCon = {
            buttonText: '-',
            buttonFun: 'dFormRowDelete(event)'
        };
    }

    let parentConId = parentContainer.id;
    let status = _ValidateSchema(rowSchema);
    dRow_Create(null, parentContainer, rowSchema, buttonCon);
}


// Delete
export function dRow_Delete_Accordion(rowContainer){
    let parentContainer = rowContainer.parentNode
    parentContainer.removeChild(rowContainer)
}


//Add Accordion
export function _dRowAccordionAdd(event, schema, count){
    //Get Form Container
    let accordionParentId = event.target.parentNode.parentNode.id

    let {e_type, e_display, e_name, row_Schema, group_con} = schema[accordionParentId]

    const groupContainer = event.target.parentNode.parentNode.parentNode

    // Create Dynamic Id
    let dynamicId = `${accordionParentId.split('_')[0]}_${count}`

    //Create Accordion Parent Container
    let getCon = dRow_ContainerCreate(groupContainer, dynamicId, schema[accordionParentId])

    //Create Accordion
    let buttonObj = { buttonText: '-', buttonFun: 'dFormRowDelete(event)' }
    let accordionBody = dRow_createAccordion(getCon, `ac-${count}`, `${e_name}-${count}`, buttonObj)

    //Create Accordion Rows
    Object.keys(row_Schema).forEach((key)=>{
       let rowParent = dRow_ContainerCreate(accordionBody, key, row_Schema[key])
       _dFormHandleDynamicRows(null, rowParent, row_Schema, key, null)
    })
}

//Check Row Type
export async function dRow_checkConType(schema, parentObject, accordionBody = null){

    for(let key of Object.keys(schema)){
       let {e_type, e_name} = schema[key]

       if(e_type === "dynamicRow"){
          let parentRowCon = accordionBody ? accordionBody.querySelector(`#${key}`) : document.querySelector(`#${key}`)
          let validate = _createDynamicRowJson(parentObject, parentRowCon, e_name)
          if (validate) if (!validate.status) return validate;
       }

       if(e_type === "staticRow"){
          let parentRowCon = accordionBody ? accordionBody.querySelector(`#${key}`) : document.querySelector(`#${key}`)
          let validate = await _createStaticValueObj(parentRowCon, parentObject)
           if (validate) if (!validate.status) return validate;
       }
    }
}


// Create Accordion
export function dRow_createAccordion(parentContainer, targetConId, displayName, buttonObj) {
    let topParentContainer = document.createElement('div');
    topParentContainer.classList.add('row')
    parentContainer.appendChild(topParentContainer);

   // Accordion Container
   let accordionCon = document.createElement('div');
   accordionCon.classList.add('accordion', 'col-lg-12');
   topParentContainer.appendChild(accordionCon);


   // Accordion Item Container
   let accordionItemCon = document.createElement('div');
   accordionItemCon.classList.add('accordion-item');
   accordionCon.appendChild(accordionItemCon);

   // Create Accordion Button
   let accordionButton = document.createElement('button');
   accordionButton.classList.add(
      'accordion-button',
      'collapsed',
      'ik-h2',
      'py-1',
      'shadow-none',
      'text-dark',
      'ik-formLabel'
   );
   accordionButton.type = 'button';
   accordionButton.id = `${targetConId}-header`;
   accordionButton.setAttribute('data-bs-toggle', 'collapse');
   accordionButton.setAttribute('data-bs-target', `#${targetConId}`);
   accordionButton.setAttribute('aria-expanded', 'false');
   accordionButton.setAttribute('aria-controls', targetConId);
   accordionButton.innerHTML = `${displayName}`;
   accordionItemCon.appendChild(accordionButton);

   // Create Target Element Container
   let targetCon = document.createElement('div');
   targetCon.id = targetConId;
   targetCon.classList.add('accordion-collapse', 'collapse', 'mt-3');
   targetCon.setAttribute('aria-labelledby', accordionButton.id);
   targetCon.setAttribute('data-bs-parent', `#${parentContainer.id}`);
   accordionItemCon.appendChild(targetCon);

   // Create Accordion Body
   let accordionBody = document.createElement('div');
   accordionBody.classList.add('accordion-body', 'pt-0');
   targetCon.appendChild(accordionBody);

    // Create Button
    if(buttonObj){
        accordionCon.classList.remove('col-lg-12')
        accordionCon.classList.add('col-lg-11')

        let buttonCon =  document.createElement('div')
        buttonCon.textContent = buttonObj['buttonText']
        buttonCon.classList.add('addButton', 'col-lg-1')
        buttonCon.style.cssText = 'cursor : pointer'
        buttonCon.setAttribute('onclick', buttonObj['buttonFun'])

        topParentContainer.appendChild(buttonCon);
    }
   return accordionBody;
}

// Set Options
export function dRow_SetValues(field, valueList){
   field.innerHTML = ''
   let optional = document.createElement('option')
   let fragment = document.createDocumentFragment()

   optional.textContent = '-------'
   optional.value = ''
   optional.selected = true
   optional.disabled = true
   fragment.appendChild(optional)

   if(valueList && valueList.length !=0){
      valueList.forEach((val)=>{
          let option = document.createElement('option')
          option.textContent = val
          option.value = val
          fragment.appendChild(option)
      })
      field.appendChild(fragment)
   }
}


function _dRowReadFileContent(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) =>  resolve(e.target.result)
    reader.onerror = reject;

    reader.readAsText(file);
  });
}

async function _createStaticValueObj(parentRowCon, parentObj) {
  const rowCon = parentRowCon.querySelector('.row');
  const allFieldCon = rowCon.querySelectorAll('div');
  let validate = {}

  for (const con of allFieldCon) {
    const check = con.classList.contains('d-none');
    if (!check) {
      const field = con.querySelector('input, select');
      if (field) {
        if (field.value.startsWith("[")) {
          parentObj[field.name] = JSON.parse(field.value);
        }
        else if (field.type === "file") {
          if (field.files[0]) {
            try {
              const content = await _dRowReadFileContent(field.files[0]);
              parentObj[field.name] = content;
            } catch (e) {
              console.error("Error reading file:", e);
            }
          }
        }
        else {
            validate = _dRowValidateValue(field)
            if(validate.status) parentObj[field.name] = field.value
            else {
              break
            }
        }
      }
    }
  }
  if(!validate.status) return validate
}



// Add Dynamic Value
async function _createDynamicRowJson(parentObject, parentRowCon, keyName){
    let rowCons = parentRowCon.querySelectorAll('.row')
    let valArray = []
    let validate = {}

    for(let rowCon of rowCons){
         let rowVal = {}
         let allFieldCon = rowCon.querySelectorAll('div')

         for(let con of allFieldCon){
            let check = con.classList.contains('d-none');
            if (!check) {
              let field = con.querySelector('input, select')
              if(field){
                if (field.value.startsWith('[')){
                     rowVal[field.name] = JSON.parse(field.value)
                }
                else if (field.type === "file") {
                  if (field.files[0]) {
                    try {
                      const content = await _dRowReadFileContent(field.files[0]);
                      parentObj[field.name] = content;
                    } catch (e) {
                      console.error("Error reading file:", e);
                    }
                  }
                }
                else {
                    validate = _dRowValidateValue(field)
                    if(validate.status) rowVal[field.name] = field.value
                    else {
                      break
                    }
                }
              }
            }
         }

         if(validate.status) valArray.push(rowVal)
         else break
    }
    if(validate.status) parentObject[keyName] = valArray
    else return validate
}

// Validate Json Value
function _dRowValidateValue(field){
    let validate  = {status: true, mess: ''}

    if(field.type === "tel"){
         if(field.value.length !== 0 && field.value.length !== 10){
            validate.status = false
            validate.mess = "Enter the Valid Number...."
         }

    }
    if(field.type === "number"){
        if(field.hasAttribute('min') && field.hasAttribute('max')){
            let maxVal = parseInt(field.getAttribute('max'))
            let minVal = parseInt(field.getAttribute('min'))
            if(parseInt(field.value) > maxVal || parseInt(field.value) < minVal){
                 validate.status = false
                 validate.mess = `${field.getAttribute('name')} should be in range than ${minVal} - ${maxVal}`
            }
        }
    }

    return validate
}


// Validate JSON Schema
function _ValidateSchema(row_schema){
    let fieldTypeList = ["text", "email", "number", "password", "date", "time", "date_range", "phone", "multi_select", "single_select", "file"]

    // Validate Name
    let field_list = new Set()
    let validate = true

    row_schema.forEach((field_schema)=>{

        if(field_list.has(field_schema.f_display_name)){
           console.error("Display Name Should be Unique")
           validate =  false
        }
        else {
            field_list.add(field_schema.f_display_name);
        }

        if (!fieldTypeList.includes(field_schema.f_type)) {
            console.error("Type field Invalid ! ");
            validate = false;
        }

        if (!field_schema.f_display_name || !field_schema.f_type || !field_schema.f_name) {
            console.error(`Missing required property in field: ${JSON.stringify(field_schema)}`);
            validate = false;
        }

        if (typeof field_schema.f_required !== "boolean") {
            console.error(`Invalid value for 'f_required'. It should be a boolean: ${field_schema.f_display_name}`);
            validate = false;
        }

        if ((field_schema.f_type === "multi_select" || field_schema.f_type === "single_select")
                && (!Array.isArray(field_schema.v_options))) {
            console.error(`Options are missing or invalid for field: ${field_schema.f_display_name}`);
            validate = false;
        }

    })
    return validate
}

// Create Input Field
function _createInputFields(action, field_schema, row_container){

    let container = document.createElement('div')
    container.classList.add(field_schema.f_display_name, `col-lg-${field_schema.f_width}`)

    if(!field_schema.f_display)container.classList.add('d-none')
    if(field_schema.f_display === "always") container.style.setProperty('display', 'block', 'important');

    let label = document.createElement('label')
    label.classList.add('form-label', 'ik-formLabel' )
    label.textContent = field_schema.f_display_name

    let inputTag = document.createElement('input')
    inputTag.classList.add('form-control', 'ik-formControl', 'py-1')
    inputTag.name = field_schema.f_name
    inputTag.type = field_schema.f_type
    inputTag.value = field_schema.v_default
    inputTag.setAttribute('onclick', field_schema.a_onChange)

    container.appendChild(label)
    container.appendChild(inputTag)

     // Apply attributes
    if (field_schema.f_placeholder) inputTag.placeholder = field_schema.f_placeholder;
    if (field_schema.v_min !== undefined) inputTag.min = field_schema.v_min;
    if (field_schema.v_max !== undefined) inputTag.max = field_schema.v_max;
    if (field_schema.v_min_len !== undefined && inputTag.type !== 'number') inputTag.minLength = field_schema.v_min_len;
    if (field_schema.v_max_len !== undefined && inputTag.type !== 'number') inputTag.maxLength = field_schema.v_max_len;
    if (field_schema.f_required) inputTag.required = true;
    if(field_schema.f_type === "file") inputTag.setAttribute('accept', field_schema.f_accept)

    if("f_add_visible" in field_schema) {
        if(!field_schema.f_add_visible && action === "edit")container.classList.remove('d-none')
    }
    if(!field_schema.f_editable && action === "edit") inputTag.readOnly = true
    row_container.appendChild(container)
}

// Create Single Select DropDown
function _createSingleSelectFields(action, field_schema, row_container){

    let container = document.createElement('div')
    if(!field_schema.f_display)container.classList.add('d-none')
    if(field_schema.f_display === "always") container.style.setProperty('display', 'block', 'important');

    let label = document.createElement('label')
    label.classList.add('form-label', 'ik-formLabel')
    label.textContent = field_schema.f_display_name

    let selectTag = document.createElement('select')
    selectTag.name = field_schema.f_name
    selectTag.classList.add('form-select', 'ik-formSelect', 'py-1')

    if (field_schema.a_onChange) selectTag.setAttribute('onchange', field_schema.a_onChange);
    selectTag.required = field_schema.f_required

    container.classList.add(field_schema.f_display_name, `col-lg-${field_schema.f_width}`)
    container.appendChild(label)
    container.appendChild(selectTag)

    if("f_add_visible" in field_schema) {
        if(!field_schema.f_add_visible && action === "edit") container.classList.remove('d-none')
    }
    if(!field_schema.f_editable && action === "edit") selectTag.disabled = true
    row_container.appendChild(container)

    //Set Options
    dRow_SetValues(selectTag, field_schema.v_options)
    selectTag.value = field_schema.v_default
}

//Create DataList
function _createDataList(field_schema, row_container){
    let container = document.createElement('div')
    container.classList.add(field_schema.f_display_name, `col-lg-${field_schema.f_width}`)

    if(!field_schema.f_display)container.classList.add('d-none')
    if(field_schema.f_display === "always") container.style.setProperty('display', 'block', 'important');
    row_container.appendChild(container)

    //Create Lable
    let label = document.createElement('label')
    label.classList.add('form-label', 'ik-formLabel')
    label.textContent = field_schema.f_display_name
    container.appendChild(label)

    // Create an input element
    const input = document.createElement("input");
    input.setAttribute("list", "items");
    input.setAttribute("id", "myInput");
    input.setAttribute('name', field_schema.f_name)
    input.classList.add('form-select', 'ik-formSelect', 'py-1')
    container.appendChild(input);

    // Create a DataList element
    const dataList = document.createElement("datalist");
    dataList.setAttribute("id", "items");
    container.appendChild(dataList);

    // Add options dynamically
    dRow_SetValues(dataList, field_schema.v_options)
}

//Mapping Accordion Rows
export function dRow_MappAccRows(event, schema){
    let dependencyRowCon, rowChild;
    let targetTopParent = event.target.parentNode.parentNode.parentNode
    let topParent = targetTopParent.closest('.row').parentNode
    let labelText = event.target.parentNode.querySelector('label').textContent

    let targetRowSchema  = schema[topParent.id]['row_Schema'][targetTopParent.id]['row_Schema']

    let filterObj = targetRowSchema.find(obj => obj.f_display_name === labelText)

    filterObj['b_rows'].forEach((key)=>{
        let dependencyRowSchema = schema[topParent.id]['row_Schema'][key]['row_Schema']
        if(targetTopParent.id === key){
            dependencyRowCon = targetTopParent
            rowChild = event.target.parentNode.parentNode.childNodes
        }
        else{
            dependencyRowCon = document.querySelector(`#${key}`)
            rowChild = dependencyRowCon.querySelector('.row').childNodes
        }

        dependencyRowCon.style.display = 'block'
        let keyList = dependencyRowSchema.filter(obj => obj.b_name.includes(event.target.value))
        .map(obj => obj.f_display_name);

        // Loop through each child node in rowChild
        Array.from(rowChild).forEach((child) => {
          const hasMatchingClass = keyList.some((className) => child.classList.contains(className));

          if (hasMatchingClass) child.classList.remove('d-none');
          else child.classList.add('d-none');
        });
    })

}

// Map Single Rows
export function dRowMap(event, schema){
    let topParentId = event.target.parentNode.closest('.row').parentNode.id
    let fieldParent = event.target.parentNode

    let value = event.target.value

    let rowSchema = schema[topParentId]['row_Schema']
    let fieldObject = rowSchema.find(obj => obj.f_display_name === fieldParent.classList[0])
 
    fieldObject['b_rows'].forEach(con => {
       let dependent_con = document.querySelector(`#${con}`)
       dependent_con.style.display = 'block'

       let dependentRowSchema =  schema[con]['row_Schema']

       let filterFields = dependentRowSchema.filter(dep_obj => {
            return dep_obj.b_name.some(rule => {
                if (rule.includes(":")) {
                    const [field, val] = rule.split(":");
                    let selected = document.querySelector(`[name="${field}"]`)?.value;
                    return selected === val;
                }
                return rule === value;  
            });
        });


       let dependent_row = fieldParent.parentNode
       let row_container = dependent_row.querySelectorAll('div')

       row_container.forEach(con => con.classList.add('d-none'))

       filterFields.forEach(field_obj => {
            row_container.forEach(row_con =>{
                if(row_con.classList.contains(field_obj['f_display_name'])){
                    row_con.classList.remove('d-none')

                     if(row_con.querySelector('div')){
                        row_con.querySelector('div').classList.remove('d-none')
                     }
                }
            })
       })
    })
}



export function dRowColorField(event, row_schema){
    let labelText = event.target.parentNode.querySelector('label').textContent
    let filedObj = row_schema.find(obj => obj.f_display_name === labelText)
    event.target.style.backgroundColor = filedObj['f_color'][event.target.value]
}


//Disabled Field
function _dRowDisabledField(row_schema) {
  row_schema.forEach((obj) => {
    if (!obj.f_editable) {
      const container = document.querySelector(`.${obj.f_display_name}`);
      if (!container) return;

      const field = container.querySelector('input, select');
      if (!field) return;

      const tag = field.tagName.toLowerCase();
      if (tag === 'input') field.readOnly = true;
      if (tag === 'select') field.disabled = true;
    }
  });
}


// Function Export For Both
(function (global, factory) {
    if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
        module.exports = factory();
    } else {
        global.MyLibrary = factory();
    }
})(typeof window !== "undefined" ? window : global, function () {
    return {
        _ValidateSchema,
        dRow_ContainerCreate,
        _createInputFields,
        _createSingleSelectFields,
        dRow_SetValues,
        dRow_createAccordion,
        dRow_Create
    };
});
