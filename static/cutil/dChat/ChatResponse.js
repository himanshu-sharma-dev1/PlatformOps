let chat_container;
//Send Request
async function sendRequest(url, query, userId=''){
    let response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ "query": query, 'user_id': userId })
    });

    return response
}

//Handle Stream Response
async function HandleStreamResponse(response, container) {
    let chatCon = document.querySelector('.chat-container')

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let complete = false;
    let buffer = '';

    while (!complete) {
        const { value, done } = await reader.read();
        complete = done;

        if (value) {
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;

            const liveHtml = marked.parse(buffer);
            container.innerHTML = liveHtml;
            chatCon.scrollTop = chatCon.scrollHeight;
        }
    }
    return complete;
}


//Get Query And Show Response
async function _setResponse(event, streamUrl, resFormatUrl, userId=''){
    let textField = event.target.closest('.input-container').querySelector('input'); // Adjust selector accordingly
    if(textField.value === '') return

    let user_query = textField.value;
    event.target.parentNode.style.display = 'none';

    let chat_container = document.querySelector('.chat-container'); // Get Parent Chat Container
    let chatBox = createContainer(['chat-box', 'row']); // Add Query And Response
    chat_container.appendChild(chatBox);

    // Add Query On UI
    let qCon = createContainer(['d-flex', 'gap-3', 'align-items-start']);
    qCon.style.cssText = 'width: 100%;'
    qCon.innerHTML = `<i class="bi bi-person-fill-check user-icon"></i>`

    let queryCon = createContainer(['row', 'query-con']);
    queryCon.textContent = user_query;
    queryCon.style.backgroundColor = '#FFEACF'
    queryCon.style.width = '100%'

    qCon.appendChild(queryCon);
    chatBox.appendChild(qCon);

    textField.value = ''

    // Add Loader
    let loader = document.createElement('p');
    loader.classList.add('loading');
    loader.textContent = 'Processing ';
    let span = document.createElement('span');
    span.classList.add('loader');
    loader.appendChild(span);
    chatBox.appendChild(loader);

    let strRes = await sendRequest(streamUrl, user_query, userId)

    if(strRes.ok){
        chatBox.removeChild(loader); // Remove loader

        let rCon = createContainer(['d-flex', 'gap-3', 'align-items-start']);
        rCon.style.cssText = 'margin-left : 45px;'
        rCon.innerHTML = `<i class="bi bi-robot bot-icon"></i>`

        let chatRes = document.createElement('div');
        chatRes.classList.add('response', 'row');

        rCon.appendChild(chatRes);
        chatBox.appendChild(rCon);

        let streamCon = createContainer(['chat-message', 'col-md-12', 'mt-2']);
        chatRes.appendChild(streamCon);
        let isComplete = await HandleStreamResponse(strRes, streamCon)

        if(isComplete){

            if (resFormatUrl !== ""){

              let loading = document.createElement('p');
              loading.style.marginLeft = '50%'
              loading.style.marginTop = '15px'
              let LoadingSpan = document.createElement('span');
              LoadingSpan.classList.add('loader');
              loading.appendChild(LoadingSpan);
              streamCon.appendChild(loading)

              let response = await sendRequest(resFormatUrl, user_query, userId)

              let contentType = response.headers.get("content-type");

              streamCon.removeChild(loading)
              if (contentType && contentType.includes("application/json")) {
                  let res = await response.json();
                  console.log(res)
                  let responseText = res["data"][0]["response"];
                  responseText.forEach((obj) => {
                      checkResFormat(obj, chatRes);
                  });
              }
              else{
                  let resCon = createContainer(['chat-message', 'col-md-12', 'mt-2']);
                  chatRes.appendChild(resCon);
                  let complete = HandleStreamResponse(response, resCon)
              }
            }
        }
    }
    event.target.parentNode.style.display = 'block';
}


//Check Response Format
function checkResFormat(response, contentCol) {
    let chat_container = document.querySelector('.chat-container')
    if (response.format === "graph") {
        response.res.forEach((chartRes) => {
            let con = createContainer(['chartRes', `col-md-${chartRes.width}`]);
            con.style.width = "600px";
            con.style.height = "250px";
            contentCol.appendChild(con);
            createChart(con, chartRes);
            chat_container.scrollTop = chat_container.scrollHeight;
        });
    }

    if (response.format === "table") {
        response.res.forEach((tableRes)=>{
            let con = createContainer(['tableRes', `col-md-${tableRes.width}`]);
            contentCol.appendChild(con);
            let table = createTable(tableRes)
            con.appendChild(table)
            chat_container.scrollTop = chat_container.scrollHeight;
        })
    }

    if (response.format === "list") {
        response.res.forEach((listRes)=>{
            let con = createContainer(['listRes', `col-md-${listRes.width}`]);
            contentCol.appendChild(con);
            let list = createList(listRes.list_items, listRes.list_title)
            con.appendChild(list)
            chat_container.scrollTop = chat_container.scrollHeight;
        })
    }
    if (response.format === "link") {
    response.res.forEach((linkRes) => {
        let con = createContainer(['linkRes', `col-md-${linkRes.width}`, 'mb-1', 'mt-2', 'text-center', 'w-100']);
        let link = createLink(linkRes);

        if(link){
            let hrTop = document.createElement('hr');
            hrTop.style.cssText = 'margin-top : 5px; margin-bottom : 0px'

            let hrBottom = document.createElement('hr');
            hrBottom.style.cssText = 'margin-top:0px'

            con.appendChild(hrTop);
            con.appendChild(link);
            con.appendChild(hrBottom);

            contentCol.appendChild(con);
            chat_container.scrollTop = chat_container.scrollHeight;
        }
    });
}
    if (response.format === "text") {
            response.res.forEach((textRes) => {
                let con = createContainer(['textRes', `col-md-${textRes.width}`, 'mb-2']);
                contentCol.appendChild(con);

                const textElement = document.createElement('div');
                textElement.style.whiteSpace = 'pre-wrap';
                textElement.innerHTML = textRes.text_res;

                if (textRes.title) {
                    const title = document.createElement('strong');
                    title.textContent = textRes.title + '\n';
                    textElement.prepend(title);
                }

                con.appendChild(textElement);
                chat_container.scrollTop = chat_container.scrollHeight;
            });
        }
}


//create Container
function createContainer(classList) {
    let container = document.createElement('div')
    classList.forEach(cls => {
        container.classList.add(cls)
    });
    return container
}

//Create Link
function createLink(linkRes) {
    let link = document.createElement('a');

    if(linkRes.link_str != 'None'){
        link.href = linkRes.link_str;
        link.innerHTML = `<i class="bi bi-box-arrow-up-right"></i> ${linkRes.link_name}`
        link.target = '_blank';
        link.rel = 'noopener noreferrer';

        // Add CSS styles
        link.style.display = 'inline-block';
        link.style.textDecoration = 'none';
        link.style.color = '#0078ff';
        link.style.fontWeight = 'bold';
        link.style.padding = '2px 5px';
        link.style.borderRadius = '5px';
    }else{
       return false;
    }
    return link;
}

//Create Graph
function createChart(container, config) {
    if (!container) {
        console.error("Chart container is missing.");
        return;
    }

    let chart = echarts.init(container);

    let option = {
        title: { text: config.chart_name },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: config.chart_labels },
        yAxis: { type: 'value' },
        series: [{
            name: 'Value',
            type: config.chart_type || 'line',
            data: config.chart_data,
            smooth: config.chart_type === 'line'
        }]
    };

    chart.setOption(option);
}


//Create Table
function createTable(tableConfig) {
    let container = document.createElement('div');
    container.classList.add('mb-5');

    // Add table title if provided
    if (tableConfig.table_title) {
        let title = document.createElement('h6');
        title.textContent = tableConfig.table_title;
        title.classList.add('table-title');
        container.appendChild(title);
    }

    // Create a wrapper for table to enable scrolling
    let tableWrapper = document.createElement('div');
    tableWrapper.classList.add('table-container');

    let table = document.createElement('table');
    table.classList.add('responsive-table');

    // Create table header
    let thead = document.createElement('thead');
    let headerRow = document.createElement('tr');
    tableConfig.table_headings.forEach(headerText => {
        let th = document.createElement('th');
        th.textContent = headerText;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Create table body
    let tbody = document.createElement('tbody');
    JSON.parse(tableConfig.table_data).forEach(rowData => {
        let row = document.createElement('tr');
        rowData.forEach(cellData => {
            let td = document.createElement('td');
            td.textContent = cellData;
            row.appendChild(td);
        });
        tbody.appendChild(row);
    });
    table.appendChild(tbody);

    tableWrapper.appendChild(table);
    container.appendChild(tableWrapper);
    return container;
}


//Create List
function createList(items, list_title, isOrdered = false) {
    let container = document.createElement('div');

    // Add list title if provided
    if (list_title) {
        let title = document.createElement('h6');
        title.textContent = list_title;
        title.style.textAlign = 'start';
        title.style.marginBottom = '5px';
        title.style.fontWeight = 'bold';
        title.style.borderBottom = '2px solid black';
        container.appendChild(title);
    }

    let list = document.createElement(isOrdered ? 'ol' : 'ul');
    list.style.padding = '10px';
    list.style.marginTop = '10px';

    items.forEach(itemText => {
        let listItem = document.createElement('li');
        listItem.textContent = itemText;
        listItem.style.padding = '5px';
        list.appendChild(listItem);
    });

    container.appendChild(list);
    return container;
}



//Get Schema
async function getSchema() {
    try {
        let response = await fetch("responseSchema.json");
        let data = await response.json();

        if (!data || !data.chat_response_schema) {
            console.error("Error: Schema data is missing or malformed", data);
            throw new Error("Invalid schema data");
        }
        return data;
    } catch (error) {
        console.error("Error fetching schema:", error);
        throw error;
    }
}


//Validate Response
async function validateRes(res_data) {
    if (!res_data || !Array.isArray(res_data)) {
        console.error("Invalid input: res_data is not an array", res_data);
        return false;
    }

    try {
        let { chat_response_schema } = await getSchema();

        if (!chat_response_schema || !Array.isArray(chat_response_schema)) {
            console.error("Error: chat_response_schema is missing or not an array", chat_response_schema);
            return false;
        }

        for (const res of res_data) {
            if (!res || !res.format) {
                console.error("Error: Missing 'format' in res object", res);
                return false;
            }

            let schemaObj = chat_response_schema.find(schema => schema.format === res.format);
            if (!schemaObj) {
                console.error("Error: Invalid format", res.format);
                return false;
            }

            let requiredOption = schemaObj.required;
            for (const res_obj of res["res"]) {
                for (const option of requiredOption) {
                    if (!res_obj.hasOwnProperty(option)) {
                        console.error(`Error: Missing required option '${option}' in`, res_obj);
                        return false;
                    }

                    let expectedType = schemaObj["properties"][option]["type"];
                    let actualValue = res_obj[option];

                    let isValidType = (
                        (expectedType === "array" && Array.isArray(actualValue)) ||
                        (expectedType === "object" && typeof actualValue === "object" && !Array.isArray(actualValue)) ||
                        (expectedType === "number" && typeof actualValue === "number") ||
                        (expectedType === "string" && typeof actualValue === "string") ||
                        (expectedType === "boolean" && typeof actualValue === "boolean")
                    );

                    if (!isValidType) {
                        console.error(`Error: Invalid data type for "${option}". Expected: ${expectedType}, Got: ${typeof actualValue}`, actualValue);
                        return false;
                    }
                }
            }
        }
        return true;
    } catch (error) {
        console.error("Error in validateRes:", error);
        return false;
    }
}



(function (global, factory) {
    if (typeof module !== "undefined" && typeof module.exports !== "undefined") {
        module.exports = factory();
    } else {
        global.MyLibrary = factory();
    }
})(typeof window !== "undefined" ? window : global, function () {
    return {
        getSchema,
        validateRes
    };
});
