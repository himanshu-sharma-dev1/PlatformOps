// Create Multi Select DropDown
export function dCreateMultiSelect(obj,row_container){
   let container = document.createElement('div')
   if(!obj["f_display"]) container.classList.add('d-none')

   let hidden_input = document.createElement('input')
   hidden_input.classList.add('d-none')
   hidden_input.name = obj.f_name
   hidden_input.value = JSON.stringify([]);

   container.classList.add(obj.f_display_name, `col-lg-${obj.f_width}`)

   let label = document.createElement('label')
   label.classList.add('form-label',  'ik-formLabel')
   label.textContent = obj.f_display_name

   let optionList = document.createElement('div')
   optionList.classList.add('list', 'form-select', 'ik-formSelect')
   optionList.style.cssText = 'position: relative; height: 28px; padding: 0px'
   optionList.setAttribute('onclick', obj.a_onChange);

   let para = document.createElement('p')
   para.classList.add('ml-2', 'mt-1')
   para.textContent = '-------'

   let optionItems =  document.createElement('div')
   optionItems.classList.add('d-none', 'items')
   optionItems.style.cssText = `position: absolute; top: 28px; overflow: scroll; background-color: white; z-index: 999;
                            border:1px solid rgba(0, 0, 0, 0.3); width:100%; box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);`

   optionList.appendChild(para)
   optionList.appendChild(hidden_input)
   optionList.appendChild(optionItems)

   container.appendChild(label)
   container.appendChild(optionList)

   row_container.appendChild(container)

   if(obj.v_options.length != 0){
      optionItems.style.maxHeight = obj.v_options.length <= 3 ? '15vh' : '20vh';
      dCreateMultiSelectOption(optionItems, obj.v_options)
   }
}


// Create MultiSelect Options
function dCreateMultiSelectOption(container, list){
    container.innerHTML = ''
    container.style.maxHeight = list.length <= 3 ? '15vh' : '20vh';
    let fragment = document.createDocumentFragment()

    let buttonDiv = document.createElement('div')
    buttonDiv.classList.add('d-flex')
    buttonDiv.style.cssText = "border-bottom : 1px solid rgba(0, 0, 0, 0.3); background-color: #d5d0d0; justify-content: flex-end;"
    fragment.appendChild(buttonDiv)

    let selectAllButton = document.createElement('button')
    selectAllButton.type = 'button'
    selectAllButton.title = "Select All"
    selectAllButton.classList.add('btn')
    selectAllButton.style.cssText = 'font-weight: bold; font-size: 12px; padding: 2px !important; margin-left: 10px;'
    selectAllButton.setAttribute('onclick', 'selectAllOptions(event)')
    selectAllButton.innerHTML = `<i class="fa-solid fa-check-double fa-xl"></i>`

    let clearAllButton = document.createElement('button')
    clearAllButton.type = 'button'
    clearAllButton.title = "Clear All"
    clearAllButton.classList.add('btn')
    clearAllButton.style.cssText = "font-weight: bold; font-size: 12px;  padding: 2px !important; padding-right: 15px !important;"
    clearAllButton.setAttribute('onclick', 'clearAllOptions(event)')
    clearAllButton.innerHTML = `<i class="bi bi-eraser-fill fa-xl"></i>`

    buttonDiv.appendChild(selectAllButton)
    buttonDiv.appendChild(clearAllButton)

    list.forEach((val)=>{
        let button = document.createElement('button')
        button.classList.add("selectable", 'col-md-12', 'btn', 'text-dark',  'text-start','py-0')
        button.value = `${val}`
        button.type = 'button'
        button.setAttribute('onclick', 'selectMultipleOption(this)')

        button.addEventListener('mouseover', ()=>{ button.style.cssText =`background-color : #0d6efd;  border-radius: 0px;`})
        button.addEventListener('mouseout', ()=>{ button.style.cssText = `background-color : white;  border-radius: 0px;`})

        let span = document.createElement('span')
        span.innerText = `${val}`
        span.style.fontSize = '12px'

        let i = document.createElement('i')
        i.classList.add('text-dark')

        span.appendChild(i)
        button.appendChild(span)
        fragment.appendChild(button)
    })
    container.appendChild(fragment)
}



//Clear All
function dClearAll(optionList, optionContainer){

    let buttonContainer = optionContainer.querySelector('div')

    optionList.forEach(op => dRemoveMultiSelectOption(op, optionContainer))
    const buttons = buttonContainer.querySelectorAll('button');

    buttons.forEach((button)=>{
        if(button.classList.contains('selected')){
             button.classList.remove('selected')
             button.style.backgroundColor = ''
             const buttonText = button.querySelector('span');
             const i = button.querySelector('span i');
             i.classList.toggle('bi-check');
             i.classList.toggle('text-dark');
        }
    })
}


// Toggle Multiple Option
function dToggleMultiOption(button, optionContainer){
    button.classList.toggle('selected');

    const buttonText = button.querySelector('span');
    const i = button.querySelector('span i');

    i.classList.toggle('bi-check');
    i.classList.toggle('text-dark');

    if (button.classList.contains('selected')) {
        dAddMultiSelectOption(button.value, optionContainer);
    }
    else {
        button.style.backgroundColor = '';
        dRemoveMultiSelectOption(button.value, optionContainer);
    }
}


// Add MultiSelect Option
function dAddMultiSelectOption(value, optionContainer) {

    let para = optionContainer.querySelector('p');
    let input = optionContainer.querySelector('input');

    let jsonInput = JSON.parse(input.value || "[]")

    if(!jsonInput.includes(value)){
        jsonInput.push(value)
    }

    const newValue = JSON.stringify(jsonInput);
    input.value = newValue;
    input.setAttribute('value', newValue);
    para.textContent = jsonInput.length <= 2 ? jsonInput.join(", ") : `${jsonInput.length} Selected`;
}


// Remove MultiSelect Option
function dRemoveMultiSelectOption(value, optionContainer){

    let para = optionContainer.querySelector('p')

    let input = optionContainer.querySelector('input');
    let jsonInput = JSON.parse(input.value)

    let index = jsonInput.indexOf(value)
    jsonInput.splice(index, 1)

    const newValue = JSON.stringify(jsonInput);

    input.value = newValue;
    input.setAttribute('value', newValue);

    para.textContent = jsonInput.length <= 2 ? jsonInput.join(", ") : `${jsonInput.length} Selected`;
    if(jsonInput.length <= 0) para.textContent = '--------'
}


// Add All Select Options
function dAddMultipleOptions(optionContainer, list){

    let buttonContainer = optionContainer.querySelector('div')
    const buttons = Array.from(buttonContainer.querySelectorAll('button'));

    buttons.forEach(btn => {
        const spanI = btn.querySelector('span i');
        if(spanI){
            if (list.includes(btn.value)){
                spanI.classList.add('bi-check');
                spanI.classList.add('text-dark');
                btn.classList.add('selected');
                //Add Value
                dAddMultiSelectOption(btn.value, optionContainer);
            }
        }
    });

}

// Hide MultiSelect Options
function dHideOptions(containers){
    containers.forEach(container =>{
        const circleItems = container.querySelector('.items');
        const toggleElement = container.querySelector('.list');

        if (circleItems && toggleElement && !circleItems.contains(event.target) && !toggleElement.contains(event.target)) {
            circleItems.classList.add('d-none');
        }
    });
}


//Create And Set Dynamic Options
function createDynamicOptions(event, optionList){
    let container = event.currentTarget.querySelector('div');
    let list = container.parentNode.querySelector('input')
    container.classList.toggle('d-none');

    dCreateMultiSelectOption(container, optionList)
    let inputVal = container.parentNode.querySelector('input').value

    const buttons = container.querySelectorAll('button');
    buttons.forEach(btn => {
        const spanI = btn.querySelector('span i');
        if (JSON.parse(inputVal).includes(btn.value)){
            spanI.classList.add('bi-check');
            spanI.classList.add('text-dark');
            btn.classList.add('selected');
        }
    });
}


//Close DropDown Click Outside
function CloseOnClickOut(e){
    const itemContainer = Array.from(document.querySelectorAll('.items'));

  if(itemContainer.length != 0){
     itemContainer.forEach((con) => {
        if(e.target.tagName !== 'P' && !con.classList.contains('d-none')){
          con.classList.add('d-none');
        }
     });
  }
}


// Show Options
function showOptions(event){
    let container = event.currentTarget.querySelector('div');
    container.classList.toggle('d-none');
}


// Multi Select
function selectMultipleOption(clickedButton){
    event.stopPropagation();
    let circleContainer = clickedButton.parentNode.parentNode
    dToggleMultiOption(clickedButton, circleContainer)
}


// Select All
function selectAllOptions(event){
    event.stopPropagation();

    let optionContainer =  event.target.parentNode.parentNode.parentNode.parentNode
    let buttons = Array.from(optionContainer.querySelector('.items').querySelectorAll('button'))
    buttons.splice(0,2)

    let optionList = []
    buttons.forEach(btn => optionList.push(btn.value))

    dAddMultipleOptions(optionContainer, optionList)
}


//Clear All
function clearAllOptions(event){
    event.stopPropagation();
    let optionContainer =  event.target.parentNode.parentNode.parentNode.parentNode

    let buttons = Array.from(optionContainer.querySelector('.items').querySelectorAll('button'))
    buttons.splice(0,2)

    let optionList = []
    buttons.forEach(btn => optionList.push(btn.value))

    dClearAll(optionList, optionContainer)
}


window.selectAllOptions = selectAllOptions
window.dCreateMultiSelectOption = dCreateMultiSelectOption
window.clearAllOptions = clearAllOptions
window.dAddMultipleOptions = dAddMultipleOptions
window.selectMultipleOption = selectMultipleOption
window.CloseOnClickOut = CloseOnClickOut
window.createDynamicOptions = createDynamicOptions
window.showOptions = showOptions