/********************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : StoreFilter.js
* Description       : Contains functions performing Javascript Properties on Filter Feature
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 6-June-23		    Yashveer Choudhary		Created.
* 6-June-23		    Yashveer Choudhary		Added clear_search_filter and update_my_filter Function.
* 7-June-23		    Yashveer Choudhary		Added tab_switch_highlight, filter_searchBar and check_switch Function.
* 8-June-23		    Yashveer Choudhary		Added clear_my_filter, init_my_filter and update_my_filter Function.
* 8-June-23		    Yashveer Choudhary		Updated clear_my_filter, filter_searchBar Function.
**********************************************************************************************************************/

// Initialising Global Variables
var my_filter_list = [];
var id_prefix = "";

/* Desc - Clear filter tabs by providing context dictionary.
 Arguments :-
  search_option - Dictionary type (contain filter context data)
*/
function clear_search_filter_old(search_option)
{
    for (const [key, value] of Object.entries(search_option))
    {

        var DivEle= document.getElementById(value.option_name);
        console.log(DivEle)
        check_ele = DivEle.querySelectorAll(".bi-check")
        check_ele.forEach(function(button)
        {
            button.style.display = "none";
        });
        brand_ele = DivEle.querySelectorAll('input[id^="' +value.option_name+ '_"]')
        for(var i=0; i<brand_ele.length; i++)
        {
            brand_ele[i].value = "";
            brand_ele[i].removeAttribute("name");
        }
    }
}


/* Desc - Get updated list of select option in filter tabs (both list should be same length).
 Arguments :-
  search_option - Dictionary type (contain filter context data)
*/
function update_my_filter_old(search_option)
{
    var i = 0;
    var option_list = []
    for (const [key, value] of Object.entries(search_option))
    {
        option_list[i] = []

        var DivEle= document.getElementById(value.option_name);

        check_ele = DivEle.querySelectorAll(".bi-check")
        check_ele.forEach(function(button)
        {
            if (button.style.display === "block")
            {
                var brandName = button.id.replace(value.option_name + "_", "");
                option_list[i].push(brandName);
            }
        });
        my_filter_list[i]["option_value"] = option_list[i]
        i = i + 1;
    }
    console.log(my_filter_list)
    return option_list
}


/* Desc - Make filter tab highlight and UnHighlighted as per className provided.
 Arguments :-
  class_name - common class name of elements on which switching of highlighting of tab are to be done.
*/
function tab_switch_highlight(class_name)
{
    if (class_name == "")
    {
        console.log("Class Name provided for filter tab highlighting is blank")
    }
    else
    {
        var buttons = document.getElementsByClassName(class_name);
        for (var i = 0; i < buttons.length; i++)
        {
            buttons[i].onclick = function()
            {
                Array.from(buttons).forEach(function(btn)
                {
                    btn.classList.remove('selected');
                });
                this.classList.add('selected');
            }
        }
    }
}


/* Desc - Filter list by alphabets on search bar input.
 Arguments :-
  obj - Object of the element (or element itself).
*/
function filter_searchBar(obj)
{
    const input = document.getElementById(obj.id);
    const filter = input.value.toUpperCase();
    for (const [key, value] of Object.entries(my_filter_list))
    {
        ul = document.getElementById(value.option_name);
        div = ul.querySelectorAll('[id$="_' +value.option_name+ '"]')
        for (let i = 0; i < div.length; i++)
        {
            const a = div[i].querySelector("span");
            const txtValue = a.textContent || a.innerText;
            if (txtValue.toUpperCase().indexOf(filter) > -1)
            {
                div[i].style.display = "";
            }
            else
            {
                div[i].style.display = "none";
            }
        }
    }
}

/* Desc - Switch tick(check) symbol on click and update filter_data list .
 Arguments :-
  obj - Object of the element (or element itself).
*/
function update_my_filter(obj)
{
    console.log(obj)
    var ele_id = obj.name
    console.log(ele_id)
    for (const [key, value] of Object.entries(my_filter_list))
    {
        var element_id = Array.from(obj.querySelectorAll('i[id^="'+ value.option_name +'_"]')).map(i => i.id.replace(value.option_name + '_',''));
        var element_icon = Array.from(obj.querySelectorAll('i[id^="'+ value.option_name +'_"]'));
        console.log(element_icon)
        var li = value.option_value
        if (element_icon[0])
        {
            if (element_icon[0].style.display == "none")
            {
                element_icon[0].style = "display:block; color:black;";
                if(li.includes(element_id[0]))
                {
                }
                else
                {
                    li.push(element_id[0])
                }
                var hidden_ele = document.getElementById(obj.name);
                if (hidden_ele)
                {
                    hidden_ele.value = obj.name;
                    hidden_ele.name = value.option_name + "__"+obj.name;
                }
                break;
            }
            else
            {
                element_icon[0].style.display = "none";
                var hidden_ele = document.getElementById(value.option_name + "__" + obj.name);
                if (hidden_ele)
                {
                    hidden_ele.value = obj.name;
                    hidden_ele.name = value.option_name + "__"+obj.name;
                }
                for (var i = 0; i < li.length; i++)
                {
                    if (li[i] === element_id[0])
                    {
                        li.splice(i, 1);
                        console.log("Remaining elements: " + li);
                    }
                }
                break;
            }
        }
        value.option_value = li
    }
    console.log(my_filter_list)
}


/* Desc - apply filter on the window with updated filter_data list .
*/
function apply_my_filter()
{
    var index = 0;
    var selected_li  = []
    var to_clear_ele = document.querySelectorAll('[id^="'+ id_prefix +'"]');
    to_clear_ele.forEach(clear => {
      clear.style.display = 'none';
    });

    for (const [key, value] of Object.entries(my_filter_list))
    {
        selected_li[index] = my_filter_list[index]["option_value"]
        index = index + 1;
    }
    index = 0;
    console.log(selected_li)
        to_clear_ele.forEach(row => {
            var selectMatch = []
            var sub_index = 0;
            for (const [sub_key, sub_value] of Object.entries(my_filter_list))
            {
                var selectedSubIds = Array.from(row.querySelectorAll('[id^="'+ sub_value.option_reference +'_"]')).map(div => div.textContent);
                selectMatch[sub_index] = selected_li[sub_index].length === 0 || selected_li[sub_index].includes(selectedSubIds[0]);
                sub_index = sub_index + 1;
            }
            const allTrue = selectMatch.every(item => item === true);
            if (allTrue == false)
            {
                row.style.display = 'none';
            }
            else
            {
                row.style.display = 'block';
            }
        })
}


/* Desc - Initialize filter function and filter_data list .
 Arguments :-
  search_option - Dictionary type (contain filter context data)
  Id_prefix - prefix of the id of the row/div/container.. that contains elements on which filter to be applied.
*/
function init_my_filter(search_option, Id_prefix)
{
    var index = 0;
    id_prefix = Id_prefix;
    console.log(search_option)
    for (const [key, value] of Object.entries(search_option))
    {
        my_filter_list[index] = {}
        my_filter_list[index]['option_name'] = value.option_name
        my_filter_list[index]['option_value'] = []
        my_filter_list[index]['option_reference'] = value.option_reference
        index = index + 1;
    }
}


/* Desc - Clear filter checks (ticks) and filter_data list.
*/
function clear_my_filter()
{

    for (const [key, value] of Object.entries(my_filter_list))
    {
        var li = value.option_value
        if (li.length == 0)
        {
             var DivEle= document.getElementById(value.option_name);
            console.log(DivEle)
            check_ele = DivEle.querySelectorAll(".bi-check")
            check_ele.forEach(function(button)
            {
                button.style.display = "none";
            });
        }
        else
        {
            for (var i = 0; i<li.length; i++)
            {
                var elem = document.getElementById(value.option_name + "_" + li[i])
                elem.style.display = "none";
            }
            value.option_value = []
        }

    }

}