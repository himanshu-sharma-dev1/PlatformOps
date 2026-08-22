/********************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : Filter.js
* Description       : Contains functions performing Javascript Properties on Filter Feature
*
* Revision History  :
* Date              Author                  Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-Jan-24         Sandeep Mahajan     Created.
**********************************************************************************************************************/

// Initialising Global Variables
function init_filter(app_filters){
    var index = 0;
    for (const [key, filter] of Object.entries(app_filters)) {
        if (filter.type == "radio" || filter.type == "checkbox") {
            filter.selected_list = [];
        }
    }
}


// Add Select Element
function filter_list_add(app_filters, filter_name, list, value){
    for (const [key, filter] of Object.entries(app_filters)) {
        if (filter.name == filter_name) {
            if (list == 'Selected') {
                filter.selected_list.push(value);
            }
        }
    }
}


// Delete Unselect Element
function filter_list_delete(app_filters, filter_name, list_name, value){
    for (const [key, filter] of Object.entries(app_filters)) {
        if (filter.name == filter_name) {
            if (list_name == 'Selected'){
                var index = filter.selected_list.indexOf(value)
                if (index != -1) {
                    filter.selected_list.splice(index, 1)

                }
            }
        }
    }
}


function filter_list_update(app_filters, filter_name, list_name, val_list){

    for (const [key, filter] of Object.entries(app_filters)) {
        if (filter.name == filter_name){
            if (list_name == 'Selected'){
                filter.selected_list = val_list;

            }
        }
    }
}


function filter_list_get(app_filters, filter_name, list_name){
    val_list = []
    for (const [key, filter] of Object.entries(app_filters)) {
        if (filter.name == filter_name) {
            if (list_name == 'Selected'){
                val_list = filter.selected_list;
            }
        }
    }
    return val_list
}

// Add Button list
function create_filter_fragment(filterContainer, filter_name, list, select_function){
    let fragment = document.createDocumentFragment();
    filterContainer.innerHTML = ''
    for (let ls of list){
        let inner_container = document.createElement('div');
        inner_container.className = 'row mx-2 filter_color slProject border-bottom';

        inner_container.innerHTML = `
            <div id="${ls}" class="row filter_color ">
                <button class="selectable col-md-12 btn text-dark ik-txt text-start" value="${ls}"
                                             onclick="${select_function}(this, '${filter_name}')">
                    <span>${ls}<i class="ik-txt text-dark"></i></span>
                </button>
            </div>
        `;
        fragment.appendChild(inner_container);
    }
    filterContainer.appendChild(fragment);
}


// Input Search
function InputSearch(obj){
   let id = obj.id;
   const inputElement = document.getElementById(id);
   const filter = inputElement.value.toUpperCase();
   const container = document.querySelector(`.${id}`);
   buttons = container.querySelectorAll('button');
   const li = container.getElementsByClassName("row");

   for (let i = 0; i < li.length; i++) {
        const a = li[i].querySelector("span");
        const txtValue = a.textContent || a.innerText;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
             li[i].style.display = "";
        }
        else {
            li[i].style.display = "none";
        }
   }
}

// Change Accordian Color
function ChangeFilterColor(buttons){
    buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            buttons.forEach(function (resetBtn) {
                resetBtn.style.backgroundColor = '';
                resetBtn.style.color = '';
            });

            btn.style.backgroundColor = '#fff';
            btn.style.color = '#000';
        });
    });

}

// Add Selected Values
function setValue(impression_filters, container, sl_list, filter_name) {
    const buttons = container.querySelectorAll('button');
    buttons.forEach(btn => {
        const spanI = btn.querySelector('span i');
        if (sl_list.includes(btn.value)) {
            const buttonText = btn.querySelector('span');
            spanI.classList.add('bi-check');
            spanI.classList.add('text-dark');
            btn.classList.add('selected');
            buttonText.classList.add('fw-bold');
            filter_list_add(impression_filters, filter_name, 'Selected', btn.value);
        }
    });
}


// Fetch Schema
function activate_oem(url, oem, schema_type, csrf_token) {
    let formData = new FormData();
    formData.append('oem', oem)
    formData.append('schema_type', schema_type)
    formData.append('csrfmiddlewaretoken', csrf_token)

    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(Resdata => {
        let parameter_list = GetParameter(Resdata.json_schema.properties)
        create_filter_fragment(document.querySelector('#ParameterList'), 'parameter_list', parameter_list,'activate_multi_select')
    })
    .catch(error => {
        console.error('There was a problem with the fetch operation:', error);
    });
}


//Fetch Devices
function activate_circle(url, circle, oem, csrf_token, fnName){
    let formData = new FormData();
    formData.append('oem', oem)
    formData.append('circle_list', circle)
    formData.append('csrfmiddlewaretoken', csrf_token)

    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(Resdata => {
        let device_list = Resdata.device_list
        create_filter_fragment(document.querySelector('#deviceList'), 'device_list', device_list, fnName)
    })
    .catch(error => {
        console.error('There was a problem with the fetch operation:', error);
    });
}

//--------------------------------------------- Table Functions---------------------------------------------------------

// Add Table Headings
function addTable(dev_keys, tableheadId = "audit_head", table_footId = "audit_foot" ){
    let table_head = document.querySelector(`#${tableheadId}`)
    let table_foot = document.querySelector(`#${table_footId}`)

    let headRow = document.createElement('tr')
    let footRow = document.createElement('tr');

    let headFragment =  document.createDocumentFragment()
    let footFragment = document.createDocumentFragment();

    dev_keys.forEach((key)=>{
        let th = document.createElement('th')
        th.style.cssText = 'background-color : #fff; color : #e40000;'
        let footTh = document.createElement('th');

        th.textContent = key
        headFragment.appendChild(th)
        footFragment.appendChild(footTh);
    })
    headRow.appendChild(headFragment)
    table_head.appendChild(headRow)

    footRow.appendChild(footFragment)
    table_foot.appendChild(footRow)
}

// Add Table Data
function addTableData(dataArray, target, oem, ruleset_name, date, cond = false, tableId ="example") {
    

    // Check if dataArray is empty
    if (dataArray.length === 0) {
        hideLoader();
        return;
    }
    else{
        showLoader()
    }

    var table = $(`#${tableId}`).DataTable({
        data: dataArray,
        columnDefs: [
            {
                targets: target,
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        if (cond){
                            if (target == 1) {
                                let url = '/ANS/Diagnostics/DeviceDashboard/';
                                let obj = {
                                    'oem': oem,
                                    'ruleset_name': ruleset_name ? ruleset_name : '',
                                    'data': data,
                                    'date': date,
                                    'circle': row[3],
                                    'rule_name': '',
                                    'd_device_name':row[0],
                                    'd_oem':oem,
                                    'd_circle': row[3],
                                    'serial_number':row[1]
                                };
                                data = `<p style="cursor: pointer" onclick='sendData(${JSON.stringify(obj)}, "${url}")'>${row[1]}</p>`;
                            }

                        }
                        else{
                            if (target == 0) {
                                let url = '/ANS/GetDeviceRawPerfData/';
                                let obj = {
                                    'oem': oem,
                                    'ruleset_name': ruleset_name ? ruleset_name : '',
                                    'data': data,
                                    'date': date,
                                    'circle': row[3],
                                };
                                data = `<p style="cursor: pointer" onclick='sendData(${JSON.stringify(obj)}, "${url}")'>${row[0]}</p>`;
                            }
                            else if (target == 1) {
                                let url = '/ANS/GetDeviceAuditRes/';
                                let obj = {
                                    'oem': oem,
                                    'ruleset_name': ruleset_name ? ruleset_name : '',
                                    'circle': row[3],
                                    'data': data,
                                    'd_date': row[6]
                                };
                                data = `<p style="cursor: pointer" onclick='sendData(${JSON.stringify(obj)}, "${url}")'>${row[1]}</p>`;
                            }
    
                        }
                        
                    }
                    return data;
                }
            },

            {
                targets: '_all',
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        if (data === 'True') {
                            return '<i class="fa-solid fa-circle-check" aria-hidden="true" style="color: green;"></i>';
                        } else if (data === 'False') {
                            return '<i class="fa-solid fa-circle-xmark" aria-hidden="true" style="color: red;"></i>';
                        }
                        else if (data === 'NoPlan') {
                            return '<i class="fa-solid fa-question" aria-hidden="true" style="color: red;"></i>';
                        }
                    }
                    return data;
                }
            }
        ],
        initComplete: function () {
          var api = this.api();

          api.columns().every(function () {
            var column = this;
            var footerCell = $(column.footer()).empty();

            var select = $('<select class=""><option value=""></option></select>').appendTo(footerCell);

            // Initialize Select2 on the select element
            $(select).select2({
              width: '100%',
              placeholder: "Search...",
              allowClear: true,
            });

            // Add event listener for changes in Select2 dropdown
            select.on('change', function () {
              var val = $(this).val();
              column.search(val ? '^' + val + '$' : '', true, false).draw();
            });

            column.data().unique().sort().each(function (d) {
              select.append('<option value="' + d + '">' + d + '</option>');
            });
          });

          hideLoader();
        }
    });
}


// Send Data && Redirect
function sendData(data, pageUrl){
  const url = pageUrl;
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  form.target = '_blank';

  const jsonInput = document.createElement('input');
  jsonInput.type = 'hidden';
  jsonInput.name = 'json_data';
  jsonInput.value = JSON.stringify(data);

  form.appendChild(jsonInput);
  document.body.appendChild(form);
  form.submit();
}

// Export your function here
window.init_filter = init_filter
window.filter_list_update = filter_list_update;
window.create_filter_fragment = create_filter_fragment
window.filter_list_add = filter_list_add
window.filter_list_delete = filter_list_delete
window.filter_list_get = filter_list_get
window.setValue = setValue
