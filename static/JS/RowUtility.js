/********************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : RowUtility.js
* Description       : Contains functions performing Javascript Properties on various Row operations Feature
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 16-Aug-23		    Yashveer Choudhary		Created.
**********************************************************************************************************************/

var block_count = 1

var base_exist = false

function RowUtility_add_block(base_id, base_flag)
{
    // cloning target element
    var clone = $("#"+base_id).clone()
    var block = document.getElementById(base_id)
    var parentElement = document.getElementById(base_id).parentElement
    base_exist = base_flag
    // retrieving row count from element
    var row_count = block.getAttribute('data-row-count')
    block_count = parseInt(row_count) + 1

    // updating row count back to the element
    block.setAttribute("data-row-count", block_count)

    var clone_ele = clone[0]
    clone_ele.removeAttribute('id')
    clone_ele.removeAttribute('data-row-count')

    // getting fields list from cloned element
    var button_list = clone_ele.getElementsByTagName('button')
    var input_list = clone_ele.getElementsByTagName('input')
    var select_list = clone_ele.getElementsByTagName('select')

    // converting add button to delete(trash) button for cloned element
    if (button_list.length == 1)
    {

         button_list[0].className = "fs-6 bi-trash py-0 ik-actionIcon mt-1"
         button_list[0].innerHTML = ""
         button_list[0].setAttribute("data-parent-div-class", block.className)
         button_list[0].removeAttribute('onclick')
         button_list[0].onclick = function(){RowUtility_remove_block(this)};
    }

    // updating ids of all input fields in cloned row
    for (var i=0; i<input_list.length; i++)
    {
        input_list[i].id = input_list[i].id + block_count
        input_list[i].name = input_list[i].name + block_count
    }

    // updating ids of all Select fields in cloned row
    for (var i=0; i<select_list.length; i++)
    {
        select_list[i].id = select_list[i].id + block_count
        select_list[i].name = select_list[i].name + block_count
    }

    //inserting cloned element to the DOM
    parentElement.append(clone_ele);
}

//remove the requested row
function RowUtility_remove_block(input)
{
    const parentDiv = input.closest('.row');
    var parentElement = parentDiv.parentElement
    var rows_list = parentElement.children;

    //remove element except the default and mandatory element
    if (base_exist == true)
    {
        if (rows_list.length > 3)
        {
            parentDiv.remove();
        }
    }
    else
    {
        parentDiv.remove();
    }
}


function RowUtility_save_info(base_id, hidden_param, data_flag)
{
    var info = {}
    var index = 1
    var parentElement = document.getElementById(base_id).parentElement
    var rows_list = parentElement.children;

    // get all inputs in all rows to create a info list of all input and their values
    for (var row=0; row<rows_list.length; row++)
    {
        var dict = {};
        var input_list = rows_list[row].getElementsByTagName('input')
        var select_list = rows_list[row].getElementsByTagName('select')

        if (data_flag == "true")
        {
            if (rows_list[row].id != base_id)
            {
                for (var i=0; i<input_list.length; i++)
                {
                     if (input_list[i].value != "" && input_list[i].id != hidden_param)
                     {
                        var input_name = input_list[i].id

                        //remove numeric character from the name srtring
                        var replaced = input_name.replace(/[0-9]/g, '');
                        dict[replaced] = input_list[i].value;
                     }
                }
                for (var i=0; i<select_list.length; i++)
                {
                     if (select_list[i].value != "" && select_list[i].id != hidden_param)
                     {
                        var select_name = select_list[i].id

                        //remove numeric character from the name srtring
                        var replaced = select_name.replace(/[0-9]/g, '');
                        dict[replaced] = select_list[i].value;
                     }
                }
                if (Object.keys(dict).length != 0)
                {
                    info[index] = dict
                    index = parseInt(index) + 1
                }
            }
        }
        else
        {
            if (rows_list[row].tagName.toLowerCase() != 'input')
            {
                for (var i=0; i<input_list.length; i++)
                {
                     if (input_list[i].value != "" && input_list[i].id != hidden_param)
                     {
                        var input_name = input_list[i].id

                        //remove numeric character from the name srtring
                        var replaced = input_name.replace(/[0-9]/g, '');
                        dict[replaced] = input_list[i].value;
                     }
                }
                for (var i=0; i<select_list.length; i++)
                {
                     if (select_list[i].value != "" && select_list[i].id != hidden_param)
                     {
                        var select_name = select_list[i].id

                        //remove numeric character from the name srtring
                        var replaced = select_name.replace(/[0-9]/g, '');
                        dict[replaced] = select_list[i].value;
                     }
                }
                if (Object.keys(dict).length != 0)
                {
                    info[index] = dict
                    index = parseInt(index) + 1
                }
            }
        }
    }

    // Convert the array to a JSON string
    const rulesJson = JSON.stringify(info);
    // Set the JSON string as the value of the hidden textarea
    let paramValue = document.getElementById(hidden_param).value = rulesJson;

}