/********************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : DatajamFilter.js
* Description       : Contains functions performing Javascript Properties on DataJam Feature
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-Jan-24		    Sandeep Mahajan		Created.
**********************************************************************************************************************/


// Multi Select Filter is toggled
function reporting_filter_toggle_multi_select(app_filters, button, filter_name) {
    button.classList.toggle('selected');

    const buttonText = button.querySelector('span');
    const i = button.querySelector('span i');

    i.classList.toggle('bi-check');
    i.classList.toggle('text-dark');

    buttonText.classList.toggle('fw-bold');

    const parentDiv = button.parentElement.parentElement;

    if (button.classList.contains('selected')) {
        parentDiv.style.backgroundColor = '#e8e8e8';
        filter_list_add(app_filters, filter_name, 'Selected', button.value);
    } else {
        parentDiv.style.backgroundColor = '';
        filter_list_delete(app_filters, filter_name, 'Selected', button.value);
    }
}


// single select
function reporting_filter_activate_single_select(app_filters, clickedButton, container, filter_name){
    const buttons = container.querySelectorAll('button');
    buttons.forEach(btn => {
        const spanI = btn.querySelector('span i');
        const buttonText = btn.querySelector('span');
        if (btn === clickedButton){
            spanI.classList.add('bi-check');
            spanI.classList.add('text-dark');
            buttonText.classList.add('fw-bold');
            for (let [key, value] of Object.entries(app_filters)) {
                value.selected_list = [];
            }
            let pr_value = clickedButton.value;
            for (const [key, filter] of Object.entries(app_filters)) {
                if (filter.name == filter_name) {
                    filter.selected_list.push(pr_value);
                }
            }
        }
        else{
            spanI.classList.remove('bi-check');
            spanI.classList.remove('text-dark');
            buttonText.classList.remove('fw-bold');
        }
    });
}




