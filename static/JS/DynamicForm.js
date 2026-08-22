// Get Filter Configs
function getConfigList(config){
    let url = '/ANS/GetFilterConfig/';
    fetch(url, {
        method: 'GET'
    }).then((response) => {
        if(response.ok){
            return response.json();
        } else {
            throw new Error('Network response was not ok');
        }
    }).then((res) => {
            config['circle_list'] = res.filter_config.circle_list
            config['oem'] = res.filter_config.oem_list
    }).catch((error) => {
        console.error('There was a problem with the fetch operation:', error);
    });
}

// Create Parent Drop Down
function createDropDownField(schema, rowContainer){
    if(schema['Config_List']['required'].length == 1){
        let config_List_required = schema['Config_List']['required'][0] // Getting Field Change DropDown

        // getting Items of Dropdown
        let config_list_properties  = schema['Config_List']['properties'][config_List_required]['items']
        if (config_list_properties.hasOwnProperty('enum')){
            createDropDown(rowContainer, config_List_required, config_list_properties['enum'], 'getOptions(event)');
        }
    }
    else{
        let config_List_name = schema['Config_List']['info']
        config_List_required = schema['Config_List']['required']

        createDropDown(rowContainer, config_List_name, config_List_required, 'getAlgoOptions(event)')
    }

}

//Generate Fields According to Option
function generateFields(opVal, container, schema, activeDate = false) {

    let required_optionInfo = schema[opVal]['required'];
    let properties_optionInfo = schema[opVal]['properties'];

    let rowContainer = document.createElement('div');
    rowContainer.classList.add('row');

    let count = 0;
    required_optionInfo.forEach((fieldOp) => {
        let optionField = properties_optionInfo[fieldOp];
        if (count < 4) {
            if (optionField.type == 'string' && optionField.hasOwnProperty('items')) {

                if(fieldOp == 'Circle_List'){
                     let list = optionField['items']['enum'];
                     createMultiSelectOption([], fieldOp , rowContainer, optionField.list_function)
                }
                else if(fieldOp == 'Parameter_List'){
                     let list = optionField['items']['enum'];
                     createMultiSelectOption([], fieldOp , rowContainer, optionField.list_function)
                }
                else{
                    let list = optionField['items']['enum'];
                    createDropDown(rowContainer, fieldOp, list, optionField.list_function);
                }
            }
            else {
               if (optionField.type == 'password') {

                  createInputField(rowContainer, fieldOp, 'password');
               }

               else if (optionField.type == 'integer') {
                  createInputField(rowContainer, fieldOp, 'number', optionField.default, optionField.minimum, optionField.maximum);
               }

               else {
                  createInputField(rowContainer, fieldOp, 'text');
               }
            }
            count += 1;
        }
        else {

           container.appendChild(rowContainer);
           rowContainer = document.createElement('div');
           rowContainer.classList.add('mt-2')
           rowContainer.classList.add('row');

           count = 0;
           if (optionField.type == 'string' && optionField.hasOwnProperty('items')) {

               if(fieldOp == 'Circle_List'){
                   let list = optionField['items']['enum'];
                   createMultiSelectOption([Ap, DL], fieldOp , rowContainer, optionField.list_function)
               }
                else if(fieldOp == 'Parameter_List'){
                     let list = optionField['items']['enum'];
                     createMultiSelectOption([], fieldOp , rowContainer, optionField.list_function)
                }
                else{
                    let list = optionField['items']['enum'];
                    createDropDown(rowContainer, fieldOp, list, optionField.list_function);
                }

           }
           else {
              if (optionField.type == 'password') {
                 createInputField(rowContainer, fieldOp, 'password');
              }
              else {
                createInputField(rowContainer, fieldOp, 'text');
              }
           }
           count += 1;
        }
    });

    if (count > 0) {
        container.appendChild(rowContainer);
    }
    if(activeDate){
      addDataRange()
    }

}

// Create Drop Down
function createDropDown(rowContainer, name, list, fn){
    // Create and configure Container
    const container = document.createElement('div');
    container.className = 'col-md-3';

    // Create and configure Label
    const label = document.createElement('label');
    label.className = 'form-label ik-formLabel';
    label.setAttribute('for', name);
    label.textContent = name;

    // Create and configure DropDown
    const select = document.createElement('select');
    select.name = name;
    select.id = name;
    select.className = 'form-select ik-txt3 ik-formSelect';
    select.setAttribute('onchange', fn)

    createOptions(select, list)

    // Append elements to container and rowContainer
    container.append(label, select);
    rowContainer.appendChild(container);
}

// Create Options
function createOptions(selectField, list){
     // Add default option
    selectField.innerHTML = '<option selected disabled>------</option>';

    // Add options from the list
    selectField.append(...list.map(key => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = key;
        return option;
    }));
}


// Create Input Field
function createInputField(rowContainer, name, fType, defVal, min, max){
    // Create container with class
    const container = document.createElement('div');
    container.className = 'col-md-3';

    // Create input field with attributes and class
    const inputField = document.createElement('input');
    inputField.type = fType;
    inputField.name = name;
    inputField.id = name;
    inputField.className = 'form-select ik-txt3 ik-formSelect';

    if(defVal){
        inputField.value = defVal
    }
    if(min){
        inputField.min = min
    }
    if(defVal){
        inputField.max = max
    }

    // Create label with attributes and text content
    const label = document.createElement('label');
    label.htmlFor = name;
    label.className = 'form-label ik-formLabel';
    label.textContent = name;

    // Append label and input field to container
    container.append(label, inputField);

    // Append container to rowContainer
    rowContainer.appendChild(container);
}



// Create MultiSelect DropDown
function createMultiSelectOption(ls, name , RowContainer, fn){
    let enumContainer = document.createElement('div')
    enumContainer.classList.add(name, 'col-lg-3', 'commonList')

    RowContainer.appendChild(enumContainer)

    let label = document.createElement('label');
    label.htmlFor = name;
    label.classList.add('form-label ik-formLabel');
    label.innerText = name;

    enumContainer.appendChild(label)

    let selectList = document.createElement('div')
    selectList.id = name
    selectList.classList.add('list', 'form-select', 'ik-txt3', 'ik-formSelect')
    selectList.style.cssText = ' height: 28px; padding:1px 5px; z-index:0;'
    selectList.setAttribute('onclick', `${fn}(event)`)

    enumContainer.appendChild(selectList)

    let para = document.createElement('p')
    para.classList.add('ml-2', 'mt-1')

    selectList.appendChild(para)

    let enumItems = document.createElement('div')
    enumItems.classList.add('items', 'd-none','border','pt-1')
    enumItems.id = `${name}Items`;
    enumItems.style.cssText = `position:absolute; overflow: scroll; background: #fff; z-index:99; width: 20%; height: 60%; top: 52.5%;`

    selectList.appendChild(enumItems)
}


// Add Button For Multiselect Dropdown
function addMultiSelectButtons(ls, container, empList){

    let fragment = document.createDocumentFragment()
    ls.forEach((key)=>{
        let button =  document.createElement('button')
        let span =  document.createElement('span')
        let i = document.createElement('i')

        button.classList.add('selectable', 'col-md-12', 'btn',  'text-dark',  'ik-txt', 'text-start')
        button.value = key
        button.setAttribute('type', 'button')

        button.addEventListener('click', function() {
            activate_multiSelect(this, container, empList);
        });

        i.classList.add('ik-txt', 'text-dark')
        span.textContent = key

        span.appendChild(i)
        button.appendChild(span)
        fragment.appendChild(button)
    })
    container.appendChild(fragment)
}


// Multiple Select Function-
function activeMulti_select(button, filters, selectContainer){

    let p =  selectContainer.parentNode.querySelector('p')

    button.classList.toggle('selected');

    const buttonText = button.querySelector('span');
    const i = button.querySelector('span i');

    i.classList.toggle('bi-check');
    i.classList.toggle('text-dark');

    buttonText.classList.toggle('fw-bold');

    const parentContainer = button.parentElement.parentElement.parentElement;

    if (button.classList.contains('selected')) {
        button.style.backgroundColor = '#e8e8e8';
        filters.push(button.value)

        if(filters.length == 0){
            p.textContent = ''
        }
        else if(filters.length == 1){
            p.textContent = filters[0]
        }
        else{
            p.textContent = `${filters.length} Selected`
        }

    }
    else {
        button.style.backgroundColor = '';
        if(filters.includes(button.value)){
            filters.splice(filters.indexOf(button.value), 1)
        }
        if(filters.length == 0){
            p.textContent = ''
        }
        else if(filters.length == 1){
            p.textContent = filters[0]
        }
        else{
            p.textContent = `${filters.length} Selected`
        }

    }
}