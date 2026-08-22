/********************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : DragDrop.js
* Description       : Contains functions performing Javascript Properties on Drag and Drop Feature
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 28-July-23		    Yashveer Choudhary		Created.
**********************************************************************************************************************/

var node_pod_dict = {}
var drop_id = ""
var drag_block_id = ""
var _array = []
var node_block = ""
var pod_block = ""
var pod_block_count = 0
var node_block_count = 0
var drop_block_id = ""
var node_handle = []



function init_drag_drop(block_id, node, pod, drop_block, node_list, service_count)
{
    drag_block_id = block_id;
    node_block = node;
    pod_block = pod;
    drop_block_id = drop_block
    node_handle = node_list
    node_block_count = node_list.length
    pod_block_count = service_count
}



function dragStart_add(ev)
{
    ev.dataTransfer.effectsAllowed = 'copy';
    ev.dataTransfer.setData('text', ev.target.id);
    ev.dataTransfer.setDragImage(ev.target, 0, 0);
};



function dragEnter_add(ev) {
    event.preventDefault();
    return true;
};

// dragover function for add modal (onDrag function)
function dragOver_add(ev) {
    drop_id = ev.toElement.id
    return false;
};


function check_len()
{
    if (_array.length == 1)
    {
        return true;
    }
    return false;
}

function add_ele(id)
{
    if ((_array.includes(id)) == false )
    {
        _array.push(id)
    }
}


//Service Function
function dragDrop_node(ev) {
    let eleId = ev.dataTransfer.getData('text');
    const originalDiv = document.getElementById(eleId);

    var tmp_pod_name = originalDiv.getAttribute('data-bs-whatever');
    const selectedDiv = document.getElementById(drag_block_id);

    const clonedDiv = originalDiv.cloneNode(true);
    selectedDiv.appendChild(clonedDiv);

    var src = ev.dataTransfer.getData('text');
    document.getElementById(src).removeAttribute('draggable');
    ev.stopPropagation();

    var tmp_id = ev.target.id;

    if (
        eleId.startsWith(pod_block) &&
        !tmp_id.includes("_pod_") &&
        !tmp_id.startsWith("input-edit") &&
        !tmp_id.startsWith("delete_pod_") &&
        !tmp_id.startsWith("delete_node_") &&
        tmp_id !== ""
    ) {
        pod_block_count = pod_block_count + 1;
        let node_id = drop_id.replace(/node_block_div_row_/g, '');

        let conId = ev.target.querySelector('div').querySelector('button').getAttribute('data-main-nodeId')
        add_pod(node_id,conId,tmp_pod_name);

        document.getElementById(drop_id).insertAdjacentHTML(
            'beforeend',
            `
                <div
                    class="border w-100 p-1 d-flex justify-content-between ik-add-btn ik-txt3"
                    id="node_${node_id}_pod_${pod_block_count}"
                    data-for="${tmp_pod_name}"
                    data-nodeId=""
                    data-serviceId=""
                    name="node_${node_id}_pod_${pod_block_count}"
                    onclick="CreateService(event)"
                    data-bs-toggle="modal"
                    data-bs-target="#PodModal"
                    data-bs-backdrop="static"
                    data-bs-keyboard="false"
                    data-bs-whatever="node_${node_id}_pod_${pod_block_count}"
                    style="height: 30px; font-size:12px; border-radius:5px; background:#5499c7;"
                >
                <span class"service_name">${tmp_pod_name}</span>

                <div class="ik-input-edit text-end">
                   <button
                      type="button"
                      id="delete_pod_${pod_block_count}"
                      name="${pod_block_count}"
                      class="fs-6 bi-trash ms-1 ik-actionIcon"
                      onclick="DeleteService(event)"
                      data-nodeid=""
                      data-serviceid=""
                      data-bs-toggle="modal"
                      data-bs-target="#DeleteModal"
                      data-bs-backdrop="false"
                      data-bs-keyboard="true"
                      data-bs-whatever="${pod_block_count}">
                   </button>
                </div>
            </div>
            `
        );

        document.getElementById(src).remove();
    } else {
        document.getElementById(src).remove();
    }

    return false;
}


function dragDrop_add(ev) {
    let eleId = ev.dataTransfer.getData('text');
    const originalDiv = document.getElementById(eleId);
    const selectedDiv = document.getElementById(drag_block_id);
    const clonedDiv = originalDiv.cloneNode(true);

    selectedDiv.appendChild(clonedDiv);

    var src = ev.dataTransfer.getData('text');
    document.getElementById(src).removeAttribute('draggable');
    ev.stopPropagation();

    if (eleId == node_block) {
        node_block_count = node_block_count + 1;
        document.getElementById(drop_id).insertAdjacentHTML(
            'beforeend',
            `
            <div class="border row mx-2 bg-light mt-1 ik-node-dropBox"
                 data-main-nodeId=""
                 id="node_block_div_row_${node_block_count}"
                 name="node_${node_block_count}"
                 ondragenter="return dragEnter_add(event);"
                 ondrop="return dragDrop_node(event);"
                 ondragover="return dragOver_add(event);"
                 style="width:30%; border-radius:2px; height:95%; position:relative; display: flex;">

                <div class="col-lg-9 my-1 w-100" onclick="showNodeConfig(event)" style="height: 30px; padding:0px">
                    <button class="btn ik-add-btn w-100 text-light  py-1 Node-${node_block_count}"
                            type="button"
                            data-bs-toggle="modal"
                            data-main-nodeId=""
                            data-bs-target="#NodeModal"
                            data-bs-backdrop="static"
                            data-bs-keyboard="false"
                            data-bs-whatever="${node_block_count}"
                            style="font-size:13px; background:#e40000;">
                        Node ${node_block_count}
                    </button>
                </div>

                <div class="ik-input-edit col-lg-1"  style="position: absolute; right: 25px; top:-2px">
                    <button type="button"
                            onclick="DeleteNode(event)"
                            id="delete_node_${node_block_count}"
                            data-main-nodeId=""
                            name="${node_block_count}"
                            class="fs-6 bi-trash ms-1 ik-actionIcon text-dark pt-2 Node-${node_block_count}">
                    </button>
                </div>
            </div>
            `
        );

        let buttons = document.querySelectorAll(`.Node-${node_block_count}`);
        add_node_handle(node_block_count, buttons);

        add_ele(drop_id);

        if (check_len()) {
            document.getElementById(drop_block_id).style.height = "100%";
        }

        document.getElementById(src).remove();
    } else {
        document.getElementById(src).remove();
    }

    return false;
}


function add_node_handle(node_id, buttons)
{
    node_handle[node_id-1] = 0

    var info = {
     "node": "",
     "service_id": "",
     "service_type": "",
     "user-action" : "add_node"
    }

    // send ajax to add node
    AddNode(info, buttons, node_block_count)
}

function delete_node_handle(node_id)
{
    update_nodes(node_id)
    node_handle.splice((node_id-1), 1);
    node_block_count = node_block_count - 1;
}


function get_last_node_index()
{
last_index = 0
for (let i = 0; i < node_block_count; i++) {
    for (j = last_index + 1; j < 20; j++) {
        item_id = document.getElementById('node_block_div_row_' + j);
        if (item_id) {
            last_index = j;
            break;
        } else {
            console.log('not found')
        }
    }
}
return last_index;
}


function update_nodes(node_id)
{
      last_index = get_last_node_index()
      for (var j = node_id; j < last_index; j++)
      {
            val = parseInt(j) + 1;
            document.getElementById('node_block_div_row_' + val).id = 'node_block_div_row_' + j
            document.getElementById('node_block_div_row_' + j).setAttribute("name", 'node_' + j)
            document.getElementById('delete_node_' + val).id = 'delete_node_' + j
            document.getElementById('delete_node_' + j).setAttribute("name", j)
            var tmp_html = document.getElementById('node_block_div_row_' + j).innerHTML
            var replaced_html = tmp_html.replace('Node '+val, 'Node '+j);
            document.getElementById('node_block_div_row_' + j).innerHTML = replaced_html
            update_pods(val)
      }
}

function add_pod(node_id, node_main_id, type)
{
    node_handle[node_id-1] = node_handle[node_id-1] + 1

    var info = {
     "node_id": node_main_id,
     "service_id": "",
     "service_type": type,
     "user-action" : "add_service"
    }

    AddService(info, node_id, pod_block_count)
}

function get_pods_count(node_id)
{
    return node_handle[node_id-1]
}

function update_pods(node_id)
{
    var pod_counts = get_pods_count(node_id)
    var node = parseInt(node_id) - 1
    for (var j = 1; j <= pod_counts; j++)
    {
      document.getElementById('node_'+node_id+'_pod_' + j).id = 'node_'+node+'_pod_' + j
      document.getElementById('node_'+node+'_pod_' + j).setAttribute("name", 'node_'+node+'_pod_' + j)
      document.getElementById('node_'+node+'_pod_' + j).setAttribute("data-bs-whatever", node+'_pod_'+ j)
    }
}


function get_last_pod_index(node_id, pod_id)
{
    var pod_count = get_pods_count(node_id)
    last_index = 0
    for (let i = 0; i < pod_count; i++)
    {
        for (j = last_index + 1; j < 20; j++)
        {
            item_id = document.getElementById('node_'+node_id+'_pod_' + j);
            if (item_id)
            {
                last_index = j;
                break;
            }
            else
            {
                console.log('not found')
            }
        }
    }
    return last_index;
}


function update_pods_delete(node_id, pod_id)
{
    var pod_last_index = get_last_pod_index(node_id, pod_id)
    for (var j = pod_id; j < pod_last_index; j++)
    {
        val = parseInt(j) + 1;
        document.getElementById('node_'+node_id+'_pod_' + val).id = 'node_'+node_id+'_pod_' + j
        document.getElementById('node_'+node_id+'_pod_' + j).setAttribute("name", 'node_'+node_id+'_pod_' + j)
        document.getElementById('node_'+node_id+'_pod_' + j).setAttribute("data-bs-whatever", node_id+'_pod_'+ j)
        document.getElementById('delete_pod_' + val).id = 'delete_pod_' + j
        document.getElementById('delete_pod_' + j).setAttribute("name", j)
    }
}


function delete_pods(node_id)
{
    node_handle[node_id-1] = node_handle[node_id-1] - 1
    return node_handle[node_id-1]
}







