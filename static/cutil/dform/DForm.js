import {
    dRow_ContainerCreate,
    dRow_Create, dRow_createAccordion,
    dRow_checkConType, dRowAdd,
    dRow_Delete_Accordion,
    dRow_MappAccRows,
    dRowMap,
    dRow_SetValues,
    _dRowAccordionAdd,
    dRowColorField
} from './DRow.js'

let count = 0

// Create Forms
function dFormCreate(form_schema, modalId, values, action = null) {
    const modalContainer = document.querySelector(modalId);
    // Empty All Child

    let child = Array.from(modalContainer.querySelector('form').childNodes)
        .slice(0, -2)
        .filter((con) => con.tagName === 'DIV');
    child.forEach((con) => {
        con.innerHTML = '';
    });
    
    console.log("form_schema==", form_schema)
    Object.keys(form_schema).forEach((con_key) => {
        console.log("con_key==", con_key)
        let { e_type, row_Schema, e_name, group_con } = form_schema[con_key];
        
        console.log("row_Schema", row_Schema)
        console.log("e_name", e_name)
        console.log("group_con", group_con)

        const groupContainer = modalContainer.querySelector(`.${group_con}`);
        let con = dRow_ContainerCreate(groupContainer, con_key, form_schema[con_key]);

        //const parentCon = document.querySelector(`#${con_key}`);
        const parentCon = con
        if (e_type === "dynamicAccordion") {
            let accVal = values?.[group_con] ? values[group_con] : null;
            _dFormAccordionCreate(action, groupContainer, parentCon, accVal, row_Schema, { e_name, e_type });
        } else if (e_type === "staticAccordion") {
            let accVal = values?.[group_con] ? values[group_con] : null;
            _dFormAccordionCreate(action, groupContainer, parentCon, accVal, row_Schema, { e_name, e_type });
        } else {
            _dFormHandleDynamicRows(action, parentCon, form_schema, con_key, values);
        }
    });
}


//Create Accordion
function _dFormAccordionCreate(action, groupContainer, parentCon, accordion_values, row_Schema, eleObj){

    if(eleObj.e_type === "dynamicAccordion"){

        if(accordion_values){
           //Create Multiple Accordion
           groupContainer.innerHTML = ''
           accordion_values.forEach((obj, index)=>{   //Create Accordion On Basis Of this Loop

                count++
                let buttonConfig = {
                    buttonText: index+1 == 1 ? '+' : '-' ,
                    buttonFun: index+1 == 1 ? '_addAccordion(event)'  : '_deleteAccordion(event)'
                }

                let conId = index+1 == 1 ? parentCon.id : `${parentCon.id}_${count}`
                let shallowCopy = parentCon.cloneNode(true)
                shallowCopy.id = conId

                groupContainer.appendChild(shallowCopy)
                let accordionBody = dRow_createAccordion(shallowCopy, `${parentCon.id}-${count}`,`${eleObj.e_name}-${count}`, buttonConfig);

                Object.keys(row_Schema).forEach((key) => {
                    dRow_ContainerCreate(accordionBody, key, row_Schema[key]);
                    const acParentCon = accordionBody.querySelector(`#${key}`);

                    _dFormHandleDynamicRows(action, acParentCon, row_Schema, key, accordion_values[index]);
                });
           })
        }
        else{
            count++
            let buttonConfig = { buttonText: '+', buttonFun: '_addAccordion(event)' }
            let accordionBody = dRow_createAccordion(parentCon, `${parentCon.id}-${count}`,`${eleObj.e_name}` , buttonConfig);
            Object.keys(row_Schema).forEach((key) => {
                dRow_ContainerCreate(accordionBody, key, row_Schema[key]);
                const acParentCon = accordionBody.querySelector(`#${key}`);
                _dFormHandleDynamicRows(action, acParentCon, row_Schema, key, null);
            });
        }
    }
    else{
        //For Static Accordion Code
        let accordionBody = dRow_createAccordion(parentCon, `${parentCon.id}-${count}`,`${eleObj.e_name}` , null);
        Object.keys(row_Schema).forEach((key) => {
            dRow_ContainerCreate(accordionBody, key, row_Schema[key]);
            const acParentCon = accordionBody.querySelector(`#${key}`);
            _dFormHandleDynamicRows(action, acParentCon, row_Schema, key, accordion_values? accordion_values : null);
        });
    }

}


// Add Row
function dFormRowAdd(event, schema) {
    dRowAdd(event, schema);
}


// Delete Row
function dFormDeleteRow(event){
    let rowContainer = event.target.parentNode
    dRow_Delete_Accordion(rowContainer)
}


function dFormCreateAccordion(event, schema, count){
    _dRowAccordionAdd(event, schema, count)
}


// Handle Dynamic and Static Rows
export function _dFormHandleDynamicRows(action, parentRowContainer, formSchema, key, rowVal){


    if (formSchema[key]['e_type'] === "dynamicRow") {
        if (rowVal) {
            let value = rowVal[formSchema[key]['e_name']]

            value.forEach((obj, index) => {

                const buttonConfig = {
                    buttonText: index+1 == '1' ? '+' : '-',
                    buttonFun: index+1 == '1' ? 'dFormAddRow(event)' : 'dFormRowDelete(event)',
                };
                dRow_Create(action, parentRowContainer, formSchema[key]['row_Schema'], buttonConfig);
            });
            _dFormSelectedValue(parentRowContainer, value)

        }
        else {
            dRow_Create(action, parentRowContainer, formSchema[key]['row_Schema'], { buttonText: '+', buttonFun: 'dFormAddRow(event)'});
        }
    } 
  
    else if (formSchema[key]['e_type'] === "tabs") {
        console.log("formSchema", formSchema)
        const tabSchema = formSchema[key];
        const tabs = tabSchema.tabs || [];


        const nav = document.createElement('ul');
        nav.className = 'nav nav-tabs';
        nav.id = `${tabSchema.e_name}-tabs`;
        nav.role = 'tablist';


        const content = document.createElement('div');
        content.className = 'tab-content mt-3';
        content.id = `${tabSchema.e_name}-content`;

        tabs.forEach((tab, index) => {
            const isActive = index === 0 ? 'active' : '';
            const showActive = index === 0 ? 'show active' : '';


            const li = document.createElement('li');
            li.className = 'nav-item';
            li.role = 'presentation';
            li.innerHTML = `
                <button class="nav-link ${isActive}" id="${tab.tab_key}-tab"
                    data-bs-toggle="tab" data-bs-target="#${tab.tab_key}"
                    type="button" role="tab" aria-controls="${tab.tab_key}">
                    ${tab.tab_name}
                </button>
            `;
            nav.appendChild(li);

      
            const pane = document.createElement('div');
            pane.className = `tab-pane fade ${showActive}`;
            pane.id = tab.tab_key;
            pane.role = 'tabpanel';

            
            const tabContainer = document.createElement('div');
            dRow_Create(action, tabContainer, tab.row_Schema, null);
            pane.appendChild(tabContainer);

            content.appendChild(pane);
        });

        parentRowContainer.appendChild(nav);
        parentRowContainer.appendChild(content);
    }
    
    else {
        dRow_Create(action, parentRowContainer, formSchema[key]['row_Schema'], null);
        if (rowVal){
            let staticObj = {};
            formSchema[key]['row_Schema'].forEach((rowObj)=>{
                staticObj[rowObj['f_name']] = rowVal[rowObj['f_name']]
            })
            _dFormSelectedValue(parentRowContainer, [staticObj])
        }
    }
}


//Map Accordion Row
function dFormMapAccordionRows(event, schema){
    dRow_MappAccRows(event, schema)
}

//Map Single Row
function dFormMapRows(event, schema){
    dRowMap(event, schema)
}

//Set Options
function dFormSetOptions(field, valueList){
    dRow_SetValues(field, valueList)
}

//Color Field
function dFormFieldColor(event, rowSchema){
    dRowColorField(event, rowSchema)
}


//default function
function dFormDefaultFunc(event){}

//Add values Trigger Event
function _dFormSelectedValue(parentRowCon, rowValues){

    let rows = parentRowCon.querySelectorAll('.row');

    rows.forEach((row, index) => {

       let value = rowValues[index]

       row.childNodes.forEach((con)=>{

          let field = con.querySelector('input, select')
          if(field){
             if(Array.isArray(value[field.name])){
                field.value = JSON.stringify(value[field.name])
                let container = con.querySelector('div')
                dAddMultipleOptions(container, field.value)
             }
             else{
                if(value[field.name]){
                    if(field.hasAttribute('onclick')){
                        let click = new Event('click')
                        field.value = value[field.name]
                        field.dispatchEvent(click)
                    }
                    else{
                      field.value = value[field.name]
                      let change = new Event('change')
                      field.dispatchEvent(change)
                    }
                }
             }
          }
       })
    });
}


// Create JSON
async function dFormCreateJson(event, schema) {
    let json_data = {};
    let fromCon = event.target.parentNode.parentNode
    let inputField = event.target.parentNode.querySelector('input')
    let data = await _dFormCreateFormJson(schema, json_data, fromCon, inputField)
    if('status' in data){
        if(!data.status) return data
    }else  return data
}

//Group Static Data
function dFormGroupStaticData(schema, values){
    let schemaKeys = Object.keys(schema)
    let groupValue = {}

    schemaKeys.forEach((key)=>{
      let rowType = schema[key]['rowType']

      if(rowType === 'Static'){
         let schemaObj = schema[key]['row_Schema']
         let groupVal = {}

         schemaObj.forEach((obj)=> groupVal[obj.f_name] = values[obj.f_name])
         groupValue[key] = groupVal
      }
    })
    return groupValue
}

//Create Form Json
async function _dFormCreateFormJson(schema, jsonObj, fromCon, jsonField){

   let validate = await dRow_checkConType(schema, jsonObj)
   if(validate){
      if(!validate.status) return validate
   }
   for(let key of Object.keys(schema)){

       let {group_con, e_type, e_name} = schema[key]
       if(e_type === 'staticAccordion'){

         let accordionParent = fromCon.querySelector(`.${group_con}`)
         jsonObj[group_con] = {}

         let rowCon = Array.from(accordionParent.childNodes)[0]
         let accordionBody = rowCon.childNodes[0].querySelector('.accordion-body')

         let validate = await dRow_checkConType(schema[key]['row_Schema'], jsonObj[group_con], accordionBody)
         if(validate){
           if(!validate.status) return validate
         }
       }

       if(e_type === 'dynamicAccordion'){

          let accordionParent = fromCon.querySelector(`.${group_con}`)
          let accordionChild = Array.from(accordionParent.childNodes)

          jsonObj[group_con] = []

          for(let con of accordionChild){
            let rowCon = con.querySelector('.row')

             let accRowObj = {}
             jsonObj[group_con].push(accRowObj)

             let accordionBody = rowCon.childNodes[0].querySelector('.accordion-body')
             let validate = await dRow_checkConType(schema[key]['row_Schema'], accRowObj, accordionBody)
             if(validate){
               if(!validate.status) return validate
             }
          }
       }
   }

   console.log(JSON.stringify(jsonObj))
   jsonField.value = JSON.stringify(jsonObj)
   return jsonObj
}

window.forms = {
    dFormCreate,
    dFormSetOptions,
    dFormRowAdd,
    dFormDeleteRow,
    dFormCreateJson,
    dFormDefaultFunc,
    dFormMapAccordionRows,
    dFormMapRows,
    dFormCreateAccordion,
    dFormFieldColor
}