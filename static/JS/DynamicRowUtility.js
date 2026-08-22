// Get Schema
function GetSchema(url, oem, schema_type, csrf_token, obj, key=null){
    let formData = new FormData()
    formData.append('oem', oem)
    formData.append('schema_type', schema_type)
    formData.append('csrfmiddlewaretoken', csrf_token)

    // Make Request
    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, false)
    xhr.onload = function(){
        if(xhr.status == 200){
            let data = JSON.parse(xhr.responseText);
            obj[key? key: oem] = data.json_schema.properties
        }
        else{
            console.error("Error : ", xhr.statusText)
        }
    }
    xhr.send(formData)
}


// ------------------------------------Create Fields Functions----------------------------------------------------------


// Input Field
function createInputField(type, classes, ids, name, input_display){

    let input = document.createElement('input')
    input.setAttribute('type', type)
    input.classList.add(...classes.split(' '))
    input.id = ids
    input.setAttribute('name', ids)
    input.value =''

    if(input_display){
        input.setAttribute('required', '')
    }

    if(type == 'number'){
        input.setAttribute('min', '')
        input.setAttribute('max', '')
    }
    return input
}

// Create Labels
function createLabel(names, ids , classes){
    let label = document.createElement('label')
    label.setAttribute('for', ids)
    label.classList.add(...classes.split(' '))
    label.innerText = names
    return label
}


// Create Container
function createContainer(classes, ids) {
    let container = document.createElement('div');
    container.classList.add(...classes.split(' '));
    if(ids){
        container.id = ids
    }
    return container;
}


// Create DropDown
function createDropDown(ids, classes, function_name, value_list){
    let select = document.createElement('select')
    let optional = document.createElement('option')
    optional.innerText = '--------'
    optional.value = ""
    optional.disabled = true;
    optional.selected = true;
    select.appendChild(optional)

    select.classList.add(...classes.split(' '))
    select.id = ids
    select.name = ids
    if(function_name != ''){
          select.setAttribute('onchange', `${function_name}(event)`);
    }
    let fragment = document.createDocumentFragment();
    value_list.forEach((op)=>{
        let option = document.createElement('option')
        option.value = op
        option.innerText = op
        fragment.appendChild(option)
    })
    select.appendChild(fragment)
    return select
}

// Create Delete Button
function createDeleteButton(rowcount, ParentContainer){
    let ChildContainer = createContainer('col-md-1 mt-4', `btn_${rowcount}`)
    let button =  document.createElement('button')
    button.type = 'button'
    button.classList.add('fs-6', 'bi-trash', 'py-0', 'ik-actionIcon', 'mt-1', 'text-dark', 'fw-bold')
    button.setAttribute('onclick', 'dynamic_util_del_row(event)')
    button.id = `btn-${rowcount}`
    ChildContainer.appendChild(button)
    ParentContainer.appendChild(ChildContainer)
}

//Create Button
function createButton(attribute_list, classList, btnText, bgColor){

    let button = document.createElement('button')
    let attributeKeys = Object.keys(attribute_list)

    attributeKeys.forEach((key)=>{
        button.setAttribute(key, attribute_list[key])
    })

    button.style.backgroundColor = bgColor
    button.classList.add(...classList.split(' '))

    if(btnText != ''){
        button.innerText = btnText
    }

    return button
}


// Create Input Fragment
function createInputFragment(ParentContainer, input_name, input_type, input_id, input_display){

    let input = createInputField(input_type,'form-control ik-formControl p-1',  input_id, input_display)
    let label = createLabel(input_name, input_id, 'form-label text-dark ik-formLabel')
    let ChildContainer = createContainer('col-md-2')

    if(!input_display){
        ChildContainer.classList.add('d-none')
    }

    ChildContainer.appendChild(label)
    ChildContainer.appendChild(input)
    ParentContainer.appendChild(ChildContainer)

    return ParentContainer
}


// Create Option Fragment
function createOptionFragment(ParentContainer, option_name, option_id, option_values,option_fn, input_display){
        let ChildContainer = createContainer('col-md-2')
        if(!input_display) ChildContainer.classList.add('d-none')

        let dropDown = createDropDown(option_id, 'form-select p-1 ik-formSelect', option_fn, option_values)
        dropDown.required = input_display 

        let dropDownLabel = createLabel(option_name, option_id, 'form-label text-dark ik-formLabel')
        ChildContainer.appendChild(dropDownLabel)
        ChildContainer.appendChild(dropDown)
        ParentContainer.appendChild(ChildContainer)
        return ParentContainer
}



// Create Button Fragment
function CreateButtonFragment(parent,childClass,attribute_list, classList, btnText, bgColor){
         let ChildContainer = createContainer(childClass)
         let button = createButton(attribute_list, classList, btnText, bgColor)
         ChildContainer.appendChild(button)
         parent.appendChild(ChildContainer)
}


// Create MultiSelect DropDown
function createMultiSelectOption(rowCount, RowContainer, input_display){
    let enumContainer = document.createElement('div')
    enumContainer.classList.add('circleContainer', 'col-lg-3')
    enumContainer.setAttribute('data-count', `${rowCount}`)

    RowContainer.appendChild(enumContainer)

     if(!input_display){
         enumContainer.classList.add('d-none')
     }

    let label = document.createElement('label');
    label.htmlFor = 'enumList';
    label.classList.add('form-label', 'ik-formLabel');
    label.innerText = 'enumValue';

    enumContainer.appendChild(label)

    let enumList = document.createElement('div')
    enumList.id = 'enumList'
    enumList.classList.add('list', 'form-select', 'ik-formSelect', 'ik-txt3')
    enumList.style.cssText = ' height: 28px; padding:1px 5px; z-index:0;'
    enumList.setAttribute('onclick', 'showCircles(event)')

    enumContainer.appendChild(enumList)

    let para = document.createElement('p')
    para.classList.add('ml-2', 'mt-1')

    enumList.appendChild(para)

    let enumItems = document.createElement('div')
    enumItems.classList.add('items', 'd-none','border','pt-1')
    enumItems.id = 'circleItems';
    enumItems.style.cssText = `position:absolute; overflow: scroll; background: #fff; z-index:99; min-height:10vh;`
    enumList.appendChild(enumItems)
}


// ------------------------------------Create Rows Functions----------------------------------------------------------


function dynamic_util_add_row(parentContainer, rowCount, oem, jsonSchemas){
    let ParentContainer = parentContainer
    let RowContainer = createContainer('row mb-1 mt-1', `row_${rowCount}`);
    ParentContainer.appendChild(RowContainer)

    // Parameter Name Container
    parameter_list = schema_mgr_get_param_list(jsonSchemas[oem], ['integer', 'unit_value', 'ratio_value', 'enum'])
    createOptionFragment(RowContainer, 'Parameter', `sp_con_param_name_${rowCount}`, parameter_list, 'selectParam', true)

    // Rules Conditions
    operations_list = ['Range', '==', '<', '>', '!=', '<=', '>=', 'Include', 'Exclude', '=EnumPlan']
    createOptionFragment(RowContainer, 'Operations', ` sp_con_rules_${rowCount}`, operations_list, 'selectOperation', true)

    // Min Container
    createInputFragment(RowContainer, 'MinRange', 'number', `sp_con_min_value-${rowCount}`, false)

    // MaxRange
    createInputFragment(RowContainer, 'MaxRange', 'number', `sp_con_max_value_${rowCount}`, false)

    // Single Value
    createInputFragment(RowContainer, 'Value', 'number', `sp_con_single_value-${rowCount}`, false)

    // Create Enum Multi Select Field
    createMultiSelectOption(rowCount, RowContainer, false)

    // Planning drop-down, based on Planning Schema
    createOptionFragment(RowContainer, 'PlanValue', `sp_con_plan_name_${rowCount}`, [], '', false)

    //No Of Days
    createInputFragment(RowContainer, 'NumberDays', 'number', `sp_con_days_value-${rowCount}`, false)

     //Change Operator
    change_operator = ['==', '<', '>', '!=', '<=', '>=']
    createOptionFragment(RowContainer, 'ChangeOperator', ` operator_${rowCount}`, change_operator, '', false)

    //Change Value
    createInputFragment(RowContainer, 'ChangeValue', 'number', `sp_con_change_value-${rowCount}`, false)

    //Peer Values
    createOptionFragment(RowContainer, 'PeerValues', `sp_con_peer_value_${rowCount}`, parameter_list, '', false)

    //Plan Operations
    let plan_operations_list = ["CMP",'==', '<', '>', '!=', '<=', '>=']
    createOptionFragment(RowContainer, 'PlanOperations', ` plan_operation_${rowCount}`, plan_operations_list, 'selectPlan', false)

    //CMP Field
    createInputFragment(RowContainer, 'CMP', 'number', `cmp_${rowCount}`, false)

    //Operator
    createOptionFragment(RowContainer, 'Operator', ` sp_con_operator_${rowCount}`, ['OR', 'AND'], '', true)

    // Delete Button
    let deleteButton = createDeleteButton(rowCount, RowContainer)

}


// Add PM Row
function dynamic_util_add_PM_row(parentContainer, rowCount, oem, jsonSchemas){

    let RowContainer = createContainer('row mt-2', `rowContainer_${rowCount}`);
    parentContainer.appendChild(RowContainer)

    // Parameter Name Container
    parameter_list = schema_mgr_get_param_list(jsonSchemas[oem], ['integer', 'unit_value', 'ratio_value', 'enum'])
    createOptionFragment(RowContainer, 'Parameter', `parameter_name_${rowCount}`, parameter_list, 'selectParam', true)

    // Aggr level Container
    createOptionFragment(RowContainer, 'Aggr Level', `sp_con_aggr_level_${rowCount}`, ['Daily', 'Hourly','Weekly','Monthly'], '', true)

    // Aggr Function Container
    createOptionFragment(RowContainer, 'Aggr Func', `sp_con_aggr_func_${rowCount}`, ['Sum', 'Avg', 'Min', 'Max', 'Bucketise'], 'Aggr', true)

    // Rules Conditions
    operations_list = ['Range', '==', '<', '>', '!=', '<=', '>=', 'Include', 'Exclude']
    createOptionFragment(RowContainer, 'Operations', ` operation_${rowCount}`, operations_list, 'selectOperation', true)

    // Min Container
    createInputFragment(RowContainer, 'MinRange', 'number', `MinRange_${rowCount}`, false)

    // MaxRange
    createInputFragment(RowContainer, 'MaxRange', 'number', `MaxRange_${rowCount}`, false)

    // Single Value
    createInputFragment(RowContainer, 'Value', 'number', `unit_${rowCount}`, false)

    // Create Null Value List, to be updated when parameter is selected
    createOptionFragment(RowContainer, 'enumValue', `enum_${rowCount}`, [''], '', false)

    //Top Field
    createInputFragment(RowContainer, 'TopPeriod', 'number', `Top_${rowCount}`, false)

    // Create Planning Drop Down
    let paramTypes = ['integer', 'unit_value', 'ratio_value', 'enum', 'Float'];
    let plan_list =  oem === 'Aviat' ? schema_mgr_get_param_list(jsonSchemas['AviatPlanning'], paramTypes)
                                     :schema_mgr_get_param_list(jsonSchemas['CambiumPlanning'], paramTypes)
    plan_list.splice(0, 0, '');
    createOptionFragment(RowContainer, 'Planning', `planning_${rowCount}`, plan_list, '', false)

    //CMP Field
    createInputFragment(RowContainer, 'CMP', 'number', `cmp_${rowCount}`, false)
}


// Delete Row
function dynamic_util_del_row(event){
    let container = event.target.parentNode.parentNode.querySelector('.accordion')
    if(container){
       let containerId = container.id.split('_')[1]

       if(containerId){
         if(report_filters){
            let val = report_filters[containerId]
            if(val){
                delete report_filters[containerId]
            }
         }
       }
    }
    event.target.parentNode.parentNode.parentNode.removeChild(event.target.parentNode.parentNode);
}


// ------------------------------------Accordian Function---------------------------------------------------------------


// Create Accordian
function dynamic_util_add_accordion(super_container, cloneId, ruleCount, accordianId, ruleNameId, Condition, oem, jsonSchemas, r_name = '') {

    // Create Container
    let parentContainer = createContainer('row mt-1', '');
    let childContainer = createContainer('col-lg-11', '');
    let accordion_Items = createContainer('accordion-item mt-3', '');

    // Clone Container
    let fetchParentContainer = document.querySelector(`#${cloneId}`);
    let fetchCloneContainer = fetchParentContainer.cloneNode(true);
    fetchCloneContainer.innerHTML = '';
    fetchCloneContainer.id = `accordion_${ruleCount}`;

    // Create Buttons
    let button = document.createElement('button');
    button.classList.add('accordion-button', 'collapsed', 'ik-h2', 'py-1', 'shadow-none', 'text-dark','ik-accordionBtn');
    button.type = 'button';
    button.setAttribute('data-bs-toggle', 'collapse');
    button.setAttribute('data-bs-target', `#ac_${ruleCount}`);
    button.setAttribute('aria-expanded', 'true');
    button.setAttribute('aria-controls', 'collapse');
    button.innerText = `Rules_${ruleCount} : ${r_name}`;

    // Append icon to button
    let icon = document.createElement('i');
    icon.classList.add('bi', 'bi-plus-lg');
    button.appendChild(icon);

     button.addEventListener('click', function () {
        if (button.classList.contains('collapsed')) {
            icon.classList.remove('bi-dash-lg');
            icon.classList.add('bi-plus-lg');
        } else {
            icon.classList.remove('bi-plus-lg');
            icon.classList.add('bi-dash-lg');
        }
    });

    accordion_Items.appendChild(button);

    // Create container
    let collapseContainer = createContainer('accordion-collapse collapse mt-3', `ac_${ruleCount}`);
    collapseContainer.setAttribute('aria-labelledby', 'ik-h2');
    collapseContainer.setAttribute('data-bs-parent', `#accordion_${ruleCount}`);

    accordion_Items.appendChild(collapseContainer);

    // Rule Names
    let accordian_body = createContainer('accordion-body pt-0', accordianId);
    collapseContainer.appendChild(accordian_body);

    let rulesContainer = createContainer('row', `sp_con_rule_name_${ruleCount}`);

    // Create RuleName
    let rule_name = createInputFragment(rulesContainer, 'Rule Name', 'text', ruleNameId, true);
    let plan_action = createInputFragment(rulesContainer, 'Corrective Action', 'text', `edit_sp_con_plan_action-${ruleCount}`, true);
    accordian_body.appendChild(rule_name);
    accordian_body.appendChild(plan_action);

    if (Condition) {
        dynamic_util_add_PM_row(accordian_body, ruleCount, oem, jsonSchemas);
    } else {
        // Create Add Row Button
        let addRowContainer = createContainer('col-md-3 mt-4', `addRow_${ruleCount}`);
        let addButton = document.createElement('button');
        addButton.classList.add('btn', 'text-light', 'pr-0', 'pl-0', 'pt-0', 'pb-0','ik-btn','mt-1');
        addButton.type = 'button';
        addButton.style.backgroundColor = '#E72929';
        addButton.innerText = '+ Condition';
        addButton.setAttribute('onclick', 'addRow(event)');
        addRowContainer.appendChild(addButton);
        rulesContainer.appendChild(addRowContainer);
    }

    // Delete Button Container
    let deleteContainer = createContainer('col-lg-1', '');
    let deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.setAttribute('onclick', 'dynamic_util_del_row(event)');
    deleteBtn.classList.add('fs-6', 'bi-trash', 'py-0', 'ik-actionIcon', 'mt-3', 'text-dark');
    deleteContainer.appendChild(deleteBtn);

    // Append All Container
    fetchCloneContainer.appendChild(accordion_Items);
    childContainer.appendChild(fetchCloneContainer);
    parentContainer.appendChild(childContainer);
    parentContainer.appendChild(deleteContainer);

    super_container.appendChild(parentContainer);
}


//------------------------------------Parameter Functions---------------------------------------------------------------


// Select ParamName
function dynamic_util_select_param(parameter_name, oem, jsonSchemas, paramContainer, operationContainer,eumList, IntList, condition){
   // Fetch Sibling Elements
   let minContainer = operationContainer.nextElementSibling;
   let maxContainer = minContainer.nextElementSibling;
   let singleContainer = maxContainer.nextElementSibling;
   let enumContainer = singleContainer.nextElementSibling


   param_info = schema_mgr_get_param_info(jsonSchemas[oem], parameter_name)
   let operationField = operationContainer.querySelector('select')

   if(param_info.dataType === "integer" || param_info.dataType === "unit_value" || param_info.dataType === "ratio_value"){

       // Integer Options
       operationField.innerHTML = ''
       addOptions(operationField, IntList)

       if (param_info.min !== '' && param_info.max !== '') {
          minContainer.querySelector('input').setAttribute('min', param_info.min);
          minContainer.querySelector('input').setAttribute('max', param_info.max);
          maxContainer.querySelector('input').setAttribute('min', param_info.min);
          maxContainer.querySelector('input').setAttribute('max', param_info.max);
          singleContainer.querySelector('input').setAttribute('min', param_info.min);
          singleContainer.querySelector('input').setAttribute('max', param_info.max);
       }
   }

   if(param_info.dataType === "enum"){
        operationField.innerHTML = ''
        addOptions(operationField, eumList)

         if(param_info.val_list){
             if(condition){
                 let enumItems = enumContainer.querySelector('div').querySelector('div')
                 enumItems.innerHTML = ''
                 addButtons(enumItems, param_info.val_list)
             }
             else{
               let enumField = enumContainer.querySelector('select')
               enumField.innerHTML = ''
               addOptions(enumField, param_info.val_list)
             }
         }

   }
}


//AddButtons
function addButtons(itemContainer, list){

    list.forEach((val)=>{

        let button = document.createElement('button')
        button.classList.add("selectable", 'col-md-12', 'btn', 'text-dark',  'text-start','py-0')
        button.value = `${val}`
        button.type = 'button'
        button.setAttribute('onclick', 'activate_multiSelect(this)')

        let span = document.createElement('span')
        span.innerText = `${val}`

        let i = document.createElement('i')
        i.classList.add('text-dark')

        span.appendChild(i)
        button.appendChild(span)
        itemContainer.appendChild(button)
    })

}

//Add Options
function addOptions(field, list){
    let optional = document.createElement('option')
    optional.innerText = '--------'
    optional.value = ""
    optional.disabled = true;
    optional.selected = true;

    field.appendChild(optional)
    let fragment = document.createDocumentFragment()
    list.forEach((val)=>{
        let option = document.createElement('option')
        option.value = val
        option.innerText = val
        fragment.appendChild(option)
    })
    field.appendChild(fragment)
}


// Add Aggr fields Option
function addAggrFieldsOptions(aggrFnContainer, aggrLevelContainer, param_name, oemVal){

    let aggrFnField = aggrFnContainer.querySelector('select')
    let aggrLevelField = aggrLevelContainer.querySelector('select')

    let param_info = schema_mgr_get_param_info(jsonSchemas[oemVal], param_name)

    aggrFnField.innerHTML = ''
    aggrLevelField.innerHTML = ''

    // Create Aggr Level Options
    addOptions(aggrLevelField, ["Daily", "Hourly",'Weekly','Monthly'])

    // Add Aggr function Options
    if(param_info.dataType == 'integer'){
        addOptions(aggrFnField, ["Sum", "Avg", "Min", "Max","Bucketise"])
    }
    else{
        addOptions(aggrFnField, ["Self_Bucket"])
    }
}


// ------------------------------------Parameter Functions--------------------------------------------------------------


// Select Operation
function dynamic_util_select_operation_new(parentContainer, operation_name) {
    if (operation_name === 'Range') {
        dynamic_util_set_display(parentContainer, ['MinRange', "MaxRange"]);
    } else if (operation_name === 'Include' || operation_name === 'Exclude') {
        dynamic_util_set_display(parentContainer, ['enumValue']);
    } else if (operation_name === '=EnumPlan') {
        dynamic_util_set_display(parentContainer, ['PlanValue']);
    }else if (operation_name === '=Int_Plan') {
        dynamic_util_set_display(parentContainer, ['PlanValue']);
    } else if (operation_name === '=TopK') {
        dynamic_util_set_display(parentContainer, ['TopPeriod']);
    } else if (operation_name === 'Highest') {
        dynamic_util_set_display(parentContainer, []);
    } else if (operation_name === 'Lowest') {
        dynamic_util_set_display(parentContainer, []);
    } else if (operation_name === '=PlanCMP') {
        dynamic_util_set_display(parentContainer, ['CMP', 'Planning']);
    } else if (operation_name === '=Config_Changes') {
        dynamic_util_set_display(parentContainer, ['ChangeOperator', 'NumberDays', 'ChangeValue']);
    } else if (operation_name === '=Peer' || operation_name === '!=Peer') {
        dynamic_util_set_display(parentContainer, ['PeerValues']);
    } else {
        dynamic_util_set_display(parentContainer, ['Value']);
    }
}



function dynamic_util_set_display(parentContainer, enable_elements){
    let row_elements = parentContainer.querySelectorAll('label');
    const all_elements = ['MinRange', "MaxRange", "Value","CMP", "PlanValue", "enumValue","TopPeriod", "CMP", "Planning",
                                                      'ChangeOperator', 'NumberDays', 'ChangeValue', "PeerValues"];

    for (var i = 0; i < row_elements.length; i++) {
        // disable display for all input elements (and mark them not required)
        if (all_elements.includes(row_elements[i].innerText)) {
            row_elements[i].parentNode.classList.add('d-none');
            row_elements[i].nextElementSibling.removeAttribute('required');
        }

        // enable display for requested elements
        if (enable_elements.includes(row_elements[i].innerText)) {
            row_elements[i].parentNode.classList.remove('d-none');
            row_elements[i].nextElementSibling.setAttribute('required', '');
        }
    }
}


// Add Top K value
function addTopKValue(operatorContainer, aggrValue){

    let operatorField  = operatorContainer.querySelector('select')
    let optionList = []

    if(aggrValue === 'Bucketise' || aggrValue === 'Self_Bucket'){
       operatorField.innerHTML = ""
       addOptions(operatorField, ['=TopK', 'Highest', 'Lowest'])
    }
    else{
       operatorField.innerHTML = ""
       addOptions(operatorField, ['Range', '==', '<', '>', '!=', '<=', '>=', '=PlanCMP','Percentile'])
    }
}


// -----------------------------------------Json Functions--------------------------------------------------------------


// Create PM Json
function dynamic_util_create_pm_json(event, ruleSetName, Oem, Default, inputId){


      let formContainer = event.target.parentNode.parentNode;
      let parentContainer = formContainer.querySelector('div');
      let childContainer = parentContainer.querySelectorAll('div');

      let accordionContainer = [];
      Array.from(childContainer).forEach((container) => {
        if (container.classList.contains('accordion-body')) {
            accordionContainer.push(container);
        }
      });


      let rulesetData = {
        "ruleset_name": ruleSetName,
        "oem": Oem,
        "default": Default.toLowerCase()
      };

      rulesetData.rules = {};
      accordionContainer.forEach((acContainer, i) => {
           let childNode = acContainer.childNodes

           let nodes = Array.from(childNode).filter((node)=>{
              if(node.tagName === 'DIV'){
                return node
              }
           })

           // Fetch All Container
            let paramNameContainer = nodes[1].querySelector('div');
            let aggr_levelContainer = paramNameContainer.nextElementSibling
            let aggr_funcContainer =  aggr_levelContainer.nextElementSibling
            let operationContainer =  aggr_funcContainer.nextElementSibling
            let minContainer =  operationContainer.nextElementSibling
            let maxContainer =  minContainer.nextElementSibling
            let singleContainer =  maxContainer.nextElementSibling
            let enumContainer =  singleContainer.nextElementSibling
            let topContainer =  enumContainer.nextElementSibling
            let planningContainer =  topContainer.nextElementSibling
            let cmpContainer =  planningContainer.nextElementSibling

            //Fetch all Fields
            let param_name = paramNameContainer.querySelector('select').value
            let aggr_level = aggr_levelContainer.querySelector('select').value
            let aggr_func = aggr_funcContainer.querySelector('select').value
            let operation = operationContainer.querySelector('select').value
            let min_val = minContainer.querySelector('input').value
            let max_val = maxContainer.querySelector('input').value
            let single_val = singleContainer.querySelector('input').value
            let enum_val = enumContainer.querySelector('select').value
            let top_val = topContainer.querySelector('input').value
            let planning_val = planningContainer.querySelector('select').value
            let cmp_val = cmpContainer.querySelector('input').value

            let param_info = schema_mgr_get_param_info(jsonSchemas[Oem], param_name);
            let plan_info = Oem == "Aviat" ? schema_mgr_get_param_info(jsonSchemas['AviatPlanning'], planning_val):
                                             schema_mgr_get_param_info(jsonSchemas['CambiumPlanning'], planning_val)

            let divCon = Array.from(nodes[0].childNodes).filter((node)=>{
              if(node.tagName === 'DIV'){
                return node
              }
            })

            let rule_json = {
                'rule_name' : divCon[0].querySelector('input').value,
                'action_plan' : divCon[1].querySelector('input').value,
                'param_name': param_info.int_key,
                'aggr_level': aggr_level,
                'aggr_func': aggr_func,
                'param_rule': operation,
                'min_val': min_val,
                'max_val': max_val,
                'val': single_val,
                'value_list': [enum_val],
                'top_k_period': top_val,
                'planning_val' : plan_info['int_key'] ? plan_info['int_key'] : '' ,
                'cmp_val' : cmp_val,
            };
            rulesetData.rules[i] = rule_json

      })
      let jsonString = JSON.stringify(rulesetData);
      console.log(jsonString)
      document.querySelector(`#${inputId}`).value = jsonString;
}



//Create CM Json
function dynamic_util_create_json(event, ruleSetName, Oem, Default, inputId){
     let formContainer = event.target.parentNode.parentNode;
     let parentContainer = formContainer.querySelector('div');
     let childContainer = parentContainer.querySelectorAll('div');

     let accordionContainer = [];
     Array.from(childContainer).forEach((container) => {
        if (container.classList.contains('accordion-body')) {
            accordionContainer.push(container);
        }
     });


    let rulesetData = {
       "ruleset_name": ruleSetName,
       "oem": Oem,
       "default": Default.toLowerCase()
    };

    rulesetData.rules = {};
    accordionContainer.forEach((acContainer, i) => {
       let RuleName = acContainer.querySelector('div').querySelector('div')
       let actionPlan = RuleName.nextElementSibling
       let childNodes = acContainer.childNodes;

       let rules = {
          'rule_name': RuleName.querySelector('input').value,
          'action_plan': actionPlan.querySelector('input').value,
          'rule_json': {}
       };


        let subRules = [];
        Array.from(childNodes).forEach((node) => {
          if (node.tagName === 'DIV' && node.id.startsWith('row')) {
            subRules.push(node);
          }
        });

        for (let j = 0; j < subRules.length; j++) {

            let parentContainer = subRules[j].parentNode.parentNode.querySelector('.accordion-body')

            let parentId = parentContainer.id.split('_')[0] === 'edit' ? parentContainer.id.split('_')[3] : parentContainer.id.split('_')[2]
            let con_id =  subRules[j].id.split('_')[1]

            // Fetch All Container
            let paramNameContainer = subRules[j].querySelector('div');
            let operationContainer =  paramNameContainer.nextElementSibling
            let minContainer =  operationContainer.nextElementSibling
            let maxContainer =  minContainer.nextElementSibling
            let singleContainer =  maxContainer.nextElementSibling
            let enumContainer =  singleContainer.nextElementSibling
            let planContainer =  enumContainer.nextElementSibling
            let numDays = planContainer.nextElementSibling
            let changeOperation = numDays.nextElementSibling
            let changeValue = changeOperation.nextElementSibling
            let peerContainer = changeValue.nextElementSibling
            let planOpCon = peerContainer.nextElementSibling
            let cmpContainer = planOpCon.nextElementSibling
            let operatorContainer =  cmpContainer.nextElementSibling

            //Fetch all Fields
            let param_name = paramNameContainer.querySelector('select').value
            let operation = operationContainer.querySelector('select').value
            let min_val = minContainer.querySelector('input').value
            let max_val = maxContainer.querySelector('input').value
            let single_val = singleContainer.querySelector('input').value
            let plan_val = planContainer.querySelector('select').value
            let cmp = cmpContainer.querySelector('input').value
            let noDays = numDays.querySelector('input').value
            let chgOperation = changeOperation.querySelector('select').value
            let chgValue = changeValue.querySelector('input').value
            let peerValue = peerContainer.querySelector('select').value
            let plan_op = planOpCon.querySelector('select').value
            let operator = operatorContainer.querySelector('select').value


            let param_info = schema_mgr_get_param_info(jsonSchemas[Oem], param_name);
            let peer_info = schema_mgr_get_param_info(jsonSchemas[Oem], peerValue);

            let rule_json = {
               'param_name': param_info.int_key,
               'param_rule': operation,
               'min_val': min_val,
               'max_val': max_val,
               'val': single_val,
               'value_list' : report_filters[parentId] && report_filters[parentId][con_id] ? report_filters[parentId][con_id] : [""],
               'plan_value': plan_val,
               'cmp': cmp,
               'rule_operator': operator,
               'change_days' : noDays,
               'change_operation' : chgOperation,
               'change_val' : chgValue,
               'plan_operator' : plan_op,
               'peer_value' : peer_info.int_key? peer_info.int_key : '',
            };
          let planning_info = Oem == "Aviat" ? schema_mgr_get_param_info(jsonSchemas['AviatPlanning'], rule_json['plan_value']):
                                               schema_mgr_get_param_info(jsonSchemas['CambiumPlanning'], rule_json['plan_value'])
          rule_json['plan_value'] = planning_info.int_key? planning_info.int_key : '';
          rules.rule_json[j] = rule_json;

        }
        rulesetData.rules[i] = rules;
    });
    let jsonString = JSON.stringify(rulesetData);
    console.log(jsonString)
    document.querySelector(`#${inputId}`).value = jsonString;

}


// -----------------------------------------EditFunctions--------------------------------------------------------------

// Add Selected Value in dropDown
function SetOptionValues(field, value){
    let options = field.options

    Array.from(options).forEach((option)=>{
        if(value === option.value){
            option.selected = true
        }
    })
}


//Add MultiSelect Values
function setMultiSelectValue(enumContainer, accordianId, container, sl_list){
    const buttons = container.querySelectorAll('button');
    buttons.forEach(btn => {
        const spanI = btn.querySelector('span i');
        if (sl_list.includes(btn.value)){
            spanI.classList.add('bi-check');
            spanI.classList.add('text-dark');
            btn.classList.add('selected');
            filter_list_add(enumContainer, accordianId, btn.value);
            btn.style.backgroundColor = '#e8e8e8';
        }
    });
}


// CM  Edit Accordian
function dynamic_util_save_edit(ruleSet_list){
    let rule = ruleSet_list

    let editContainer = document.getElementById('edit_super_container');
    editContainer.innerHTML = ''

    let parentContainer = createContainer('row', '')
    editContainer.appendChild(parentContainer)

    // Create Static Fields
    createStaticFields(parentContainer, ["Radwin", "Cambium","Aviat"])

    // Set Ruleset Name
    document.querySelector('#edit_ruleset_name').value = rule.ruleset_name

    // Set OEM
    SetOptionValues(document.querySelector('#edit_oem'), rule.oem)

    // Set default Value
    SetOptionValues(document.querySelector('#edit_Default'), rule.default)


    let accRuleKeys = Object.keys(rule.rules)

    // Create Rules
    for (let i = 1; i <= accRuleKeys.length; i++){
        ruleCount = i

        dynamic_util_add_accordion(editContainer, 'accordion_1', i, `edit_sp_con_${i}`, `edit_sp_con_rule_name-${i}`,
                                                            false,rule.oem, jsonSchemas, rule.rules[i]['rule_name']);
        let accRule = rule.rules

        let subRules = accRule[i].rule_json
        // SetValues
        document.querySelector(`#edit_sp_con_rule_name-${i}`).value = accRule[i].rule_name
        document.querySelector(`#edit_sp_con_rule_name-${i}`).required = true
        document.querySelector(`#edit_sp_con_rule_name-${i}`).parentNode.nextElementSibling.querySelector('input').value = accRule[i].plan_action
        let SubRuleKeys = Object.keys(subRules)

        for(let j = 1; j<=SubRuleKeys.length; j++){
            rowCount = rowCount + 1
            let parentContainer = document.querySelector(`#edit_sp_con_${i}`)
            dynamic_util_add_row(parentContainer, rowCount, rule.oem, jsonSchemas)

            let subRule = subRules[j-1]
            let rowContainer = document.querySelector(`#row_${rowCount}`)
            dynamic_util_set_row(rowContainer, rowCount, rule.oem, jsonSchemas, subRule['param_name'],
                                 subRule['param_rule'], subRule['min_val'], subRule['max_val'], subRule['val'],
                                 subRule['value_list'], subRule['plan_value'],subRule['cmp'], subRule['rule_operator'],
                                 subRule['change_days'], subRule['change_operation'], subRule['change_val'],
                                 subRule['peer_value'], subRule['plan_operator'])

        }
    }

}

// Create static Fields For Accordian
function createStaticFields(parentContainer, oemList){

    // Create Template Name
    createInputFragment(parentContainer, 'RuleSetName', 'text', 'edit_ruleset_name', true)
    createOptionFragment(parentContainer, 'OEM', 'edit_oem', oemList,'', true)

    document.querySelector('#edit_oem').setAttribute('disabled', 'disabled')
    createOptionFragment(parentContainer, 'Default RuleSet', 'edit_Default', ['True', 'False'],'', true)

    //Create Accordian  button
    let cloneContainer = createContainer('col-md-3', '')
    let button =  document.createElement('button')
    button.classList.add('btn', 'mt-4', 'rule', 'text-light', 'pr-2', 'pl-2', 'pt-0', 'pb-0','ik-bg-color')
    button.type = 'button'
    button.setAttribute('onclick', 'createAccordion(event)')
    button.innerText = '+ Rule'
    cloneContainer.appendChild(button);
    parentContainer.appendChild(cloneContainer);
}


// Set CM Input Field Options
function dynamic_util_set_row(parentContainer, rowCount, oem, jsonSchemas, param_name, operation_name, min_val,
                             max_val, val, enum_val, plan_val,cmp, op, change_days,change_operation,change_val,
                             peer_val, plan_operator) {

    let paramContainer = parentContainer.querySelector('div')
    let operationContainer = paramContainer.nextElementSibling

    param_info = schema_mgr_get_param_info(jsonSchemas[oem], param_name)

    let eumList= ['Include', 'Exclude', '=Config_Changes', "=Peer", '=EnumPlan','!=Peer']
    let IntList= ['Range', '==', '<', '>', '!=', '<=', '>=', '=Int_Plan', '=Config_Changes', "=Peer",'!=Peer']
    dynamic_util_select_param(param_info.param_name, oem, jsonSchemas,paramContainer, operationContainer,eumList,
                                                                                                       IntList, true)
    dynamic_util_select_operation_new(parentContainer, operation_name)

    // Set Values
    let paramName = parentContainer.querySelector('div')
    let operationName = paramName.nextElementSibling
    let min = operationName.nextElementSibling
    let max = min.nextElementSibling
    let singleVal = max.nextElementSibling
    let enumVal = singleVal.nextElementSibling
    let planingVal = enumVal.nextElementSibling
    let numDays = planingVal.nextElementSibling
    let changeOperation = numDays.nextElementSibling
    let changeValue = changeOperation.nextElementSibling
    let peerValue = changeValue.nextElementSibling
    let planOp = peerValue.nextElementSibling
    let cmpVal = planOp.nextElementSibling
    let operatorVal = cmpVal.nextElementSibling

    dynamic_util_set_values(paramName, operationName, min, max, singleVal, enumVal, param_info.param_name,
                                                    operation_name, min_val, max_val, val, enum_val, true)

    let plan_info = oem == 'Aviat' ? schema_mgr_get_param_info(jsonSchemas['AviatPlanning'], plan_val):
                                     schema_mgr_get_param_info(jsonSchemas['CambiumPlanning'], plan_val)
    let planning_value = plan_info.param_name

    SetOptionValues(operatorVal.querySelector('select'), op)
    SetOptionValues(changeOperation.querySelector('select'), change_operation)

    let paramTypes = operation_name === '=Int_Plan' ? ['integer','ratio_value'] : ['enum']
    let plan_list =  oem === 'Aviat' ? schema_mgr_get_param_list(jsonSchemas['AviatPlanning'], paramTypes)
                                     :schema_mgr_get_param_list(jsonSchemas['CambiumPlanning'], paramTypes)
    plan_list.splice(0, 0, '');
    addOptionsEdit(planingVal.querySelector('select') , plan_list)
    SetOptionValues(planingVal.querySelector('select'), planning_value)

    let peer_info = schema_mgr_get_param_info(jsonSchemas[oem], peer_val)
    SetOptionValues(peerValue.querySelector('select'), peer_info.param_name)

    changeValue.querySelector('input').value = change_val
    numDays.querySelector('input').value = change_days
    cmpVal.querySelector('input').value = cmp

    if(operation_name === '=Int_Plan'){
        planOp.classList.remove('d-none')
        planOp.querySelector('select').value = plan_operator
    }
    if(plan_operator === 'CMP'){
        cmpVal.classList.remove('d-none')
    }
}



function addOptionsEdit(field , optionList){
    field.innerHTML = ''
    let fragment =  document.createDocumentFragment()

    let optional = document.createElement('option')
    optional.disabled = true
    optional.selected = true
    optional.textContent = '---------'
    fragment.appendChild(optional)

    optionList.forEach((op)=>{
        if(op != ''){
            let option = document.createElement('option')
            option.value = op
            option.innerText = op
            fragment.appendChild(option)
        }
    })
    field.appendChild(fragment)
}


//SET Common Field Values
function dynamic_util_set_values(paramName, operationName, min, max, singleVal, enumVal, param_name, operation_name,
                                                                        min_val ,max_val, val, enum_val, condition){

   // Set Param value
   SetOptionValues(paramName.querySelector('select'), param_name)

   // Set Operation Value
   SetOptionValues(operationName.querySelector('select'), operation_name)

   // Set Min and Max Range
   if(operation_name === 'Range'){
      let minField = min.querySelector('input').value = min_val
      let maxField = max.querySelector('input').value = max_val
   }
   else{
      let valField = singleVal.querySelector('input').value = val
   }

   if(condition){
       //Set Enum Val
       if(!enumVal.classList.contains('d-none')){
          let itemsContainer = enumVal.querySelector('div').querySelector('div')
          if(itemsContainer.childNodes.length != 0  && enum_val[0] != ''){
                let accordianId = enumVal.parentNode.parentNode.id.split('_')[3]
                setMultiSelectValue(enumVal, accordianId, itemsContainer, enum_val)
          }
       }
   }
   else{
      SetOptionValues(enumVal.querySelector('select'), enum_val[0])
   }
}



// PM Edit Accordian
function dynamic_util_save_pm_edit(rule){
    let editContainer = document.getElementById('edit_super_container');
    editContainer.innerHTML = ''

    let parentContainer = createContainer('row', '')
    editContainer.appendChild(parentContainer)

    // Create Static Fields
    createStaticFields(parentContainer, ["Radwin", "Cambium", "Aviat"])

    // Set Ruleset Name
    document.querySelector('#edit_ruleset_name').value = rule.ruleset_name

    // Set OEM
    SetOptionValues(document.querySelector(`#edit_oem`), rule.oem)

    // Set default Value
    SetOptionValues(document.querySelector(`#edit_Default`), rule.default)

     let pm_rules = rule.rules
     let keys = Object.keys(pm_rules)

     // create accordian
     keys.forEach((key, i)=>{
        ruleCount = i+1
        dynamic_util_add_accordion(editContainer, 'accordion_1', i+1, `edit_sp_con_${i+1}`, `edit_sp_con_rule_name-${i+1}`,
                                                           true,rule.oem, jsonSchemas, pm_rules[ruleCount]['rule_name'])

        let parentContainer = document.querySelector(`#edit_sp_con_${i+1}`)
        let rules = pm_rules[key]
        dynamic_util_set_pm_row(parentContainer, rules, rule.oem)
     })

}

// Set PM Input Field Options
function dynamic_util_set_pm_row(container, rule, oem){

    param_info = schema_mgr_get_param_info(jsonSchemas[oem], rule.param_name)

    let ruleContainer = container.querySelector('div')
    let rowContainer = ruleContainer.nextElementSibling

    let paramContainer = rowContainer.querySelector('div')
    let aggrLevelContainer = paramContainer.nextElementSibling
    let aggrFnContainer =    aggrLevelContainer.nextElementSibling
    let operationContainer = aggrFnContainer.nextElementSibling

    let eumList= []
    let IntList= ['Range', '==', '<', '>', '!=', '<=', '>=', '=PlanCMP']

    dynamic_util_select_param(param_info.param_name, oem, jsonSchemas,paramContainer, operationContainer,eumList, IntList, false)
    dynamic_util_select_operation_new(rowContainer, rule.param_rule)
    addTopKValue(operationContainer, rule.aggr_func)

    addAggrFieldsOptions(aggrFnContainer, aggrLevelContainer, param_info.param_name, oem)

    set_Pm_Values(param_info.param_name, rule , oem, ruleContainer, rowContainer)

}

//Set PM Values
function set_Pm_Values(param_name, rule , oem, ruleContainer, rowContainer){

     let divCon = Array.from(ruleContainer.childNodes).filter((node)=>{
       if(node.tagName === 'DIV'){
         return node
       }
     })

    divCon[0].querySelector('input').value = rule.rule_name
    divCon[1].querySelector('input').value = rule.plan_action

    let paramContainer = rowContainer.querySelector('div')
    let aggr_levelContainer = paramContainer.nextElementSibling
    let aggr_funcContainer =  aggr_levelContainer.nextElementSibling
    let operationContainer =  aggr_funcContainer.nextElementSibling
    let minContainer =  operationContainer.nextElementSibling
    let maxContainer =  minContainer.nextElementSibling
    let singleContainer =  maxContainer.nextElementSibling
    let enumContainer =  singleContainer.nextElementSibling
    let topContainer =  enumContainer.nextElementSibling
    let planContainer =  topContainer.nextElementSibling
    let cmpContainer =  planContainer.nextElementSibling

    let plan_info = oem == 'Aviat' ? schema_mgr_get_param_info(jsonSchemas['AviatPlanning'], rule.planning_val):
                                     schema_mgr_get_param_info(jsonSchemas['CambiumPlanning'], rule.planning_val)

    SetOptionValues(aggr_levelContainer.querySelector('select'), rule.aggr_level)
    SetOptionValues(aggr_funcContainer.querySelector('select'), rule.aggr_func)
    SetOptionValues(planContainer.querySelector('select'), plan_info['param_name'])


    topContainer.querySelector('input').value = rule.top_k_period
    cmpContainer.querySelector('input').value = rule.cmp_val

    dynamic_util_set_values(paramContainer, operationContainer, minContainer, maxContainer, singleContainer, enumContainer
    ,param_name, rule.param_rule, rule.min_val, rule.max_val, rule.val, rule.value_list, false)
}
