let resCon;
let ques_id;

// Create MarkDown Object
const md = window.markdownit();
md.use(chartPlugin);

window.md=md;

// Extend MarkDown For Charts
function chartPlugin(md) {
  md.use(window.markdownitContainer, 'chart', {
    render(tokens, idx) {
      const token = tokens[idx];
      if (token.nesting === 1) { // opening ::: chart
        // Find the content between ::: chart and :::
        let content = '';
        let i = idx + 1;
        while (i < tokens.length && tokens[i].type !== 'container_chart_close') {
          if (tokens[i].type === 'inline') {
            content += tokens[i].content;
          } tokens[i].content = '';
          if (tokens[i].children) {
            tokens[i].children.forEach(child => { child.content = ''; });
          }
          if (tokens[i].type === 'paragraph_open' || tokens[i].type === 'paragraph_close') {
            tokens[i].hidden = true;
          }
          i++;
        }

        content = content.trim();

        if (content) {
          try {
            const chartData = JSON.parse(content);
            const randomId = "chart-" + Math.random().toString(36).slice(2, 9);

            // Schedule chart rendering after DOM update
            setTimeout(() => dChatRenderChart(chartData, randomId), 10);

            // Apply width and height from JSON data as inline styles
            const width = chartData.width || '100%';
            const height = chartData.height || '50vh';
            return `<div id="${randomId}" style="width:${width}; height:${height}; min-height: 300px;"></div>`;
          } catch (e) {
//            console.error("Invalid chart JSON in ::: chart block:", e);
            // return `<div class="text-red-400 p-4 border border-red-600 rounded">Error: Invalid chart JSON - ${e.message}</div>`;
          }
        }
      }
      return ''; // closing tag or fallback
    }
  });
}

// Send Request
async function dChatSendRequest(query, url, resContainer) {
  resCon = resContainer;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query })
  });

  const question_id = response.headers.get("X-Question-ID");
  if (question_id) {
    ques_id = question_id;
  }

  if (response.ok) {
    dChatHandleStreamResponse(response);
  }
}

 // --- Helper function to wrap ONLY tables ---
  function wrapOnlyTables(htmlString) {
    if (htmlString && htmlString.includes("<table")) {
      
      let wrappedHtml = htmlString.replace(/<table/g, '<div class="table-container"><table');
      wrappedHtml = wrappedHtml.replace(/<\/table>/g, '</table></div>');
      return wrappedHtml;
    }
    return htmlString; 
  }

  

async function dChatHandleStreamResponse(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let isComplete = false;
  let displayBuffer = "";
  let renderIndex = 0;
  let isChartContent = false;

  resCon.classList.add("response-block");
  const wrapper = resCon.closest('.bot-response-wrapper');
  if (wrapper) {
    wrapper.classList.remove("d-none");
  }
  const container = resCon.parentNode.parentNode;
  const loader = container.querySelector('.loader');
  if (loader) {
    loader.remove();
  }

  if (ques_id) {
    resCon.setAttribute("data-question-id", ques_id);
  }

  while (!isComplete) {
    const { done, value } = await reader.read();
    isComplete = done;
    buffer += decoder.decode(value, { stream: true });

    const isTableContent = buffer.includes("|----------") ||
                           buffer.includes("|---") ||
                           (buffer.includes('|') && buffer.includes('\n|'));

    if (buffer.includes("::: chart")) {
       isChartContent = true;
     }
    if (isChartContent) {
       resCon.innerHTML = md.render(buffer);
    } else if (isTableContent && !isComplete) {

      renderIndex = buffer.length;
      displayBuffer = buffer;
      let renderedHtml = md.render(buffer);

      resCon.innerHTML = wrapOnlyTables(renderedHtml);
      resCon.scrollTop = resCon.scrollHeight;
      resCon.dispatchEvent(new CustomEvent('dChatTextUpdate', {
        detail: { text: buffer, isComplete: false }
      }));
    } else {
      while (renderIndex < buffer.length) {
        displayBuffer += buffer[renderIndex];
        renderIndex++;
        resCon.innerHTML = md.render(displayBuffer);
        resCon.scrollTop = resCon.scrollHeight;

        // Dispatch event for live updates (e.g. for live speech)
        resCon.dispatchEvent(new CustomEvent('dChatTextUpdate', {
          detail: { text: displayBuffer, isComplete: false }
        }));

        await new Promise(resolve => setTimeout(resolve, 1));
      }
    }
  }
  let finalRenderedHtml = md.render(buffer);
  resCon.innerHTML = wrapOnlyTables(finalRenderedHtml);

  // Dispatch final event
  resCon.dispatchEvent(new CustomEvent('dChatTextUpdate', {
    detail: { text: buffer, isComplete: true }
  }));

  if(isComplete){
    let input = document.createElement('input');
    resCon.appendChild(input);
    input.style.cssText = 'opacity: 0; position: absolute; bottom: 0; left: 10%;';
    input.setAttribute("value", buffer);
    if(buffer.includes("::: chart")){
      let chartFormat = buffer.split("\n").map((line) => line.trim()).filter((line) => line !== "").join("\n");
       md.render(chartFormat);
    }
  }
}



function dChatRenderChart(chartData, containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    
    return;
  }


  const chart = echarts.init(container);
  const { chart_type, labels, series, height, width } = chartData;

 
  if (width) container.style.width = width;
  if (height) container.style.height = height;

  let option = {}; 


  const commonOptions = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      data: series.map(s => s.name),
      top: 0,
      textStyle: { color: '#333' }
    },
  };

  switch(chart_type) {
    case 'line':
    case 'bar':
    case 'stacked':
    default:
      const isStacked = chart_type === "stacked";
      const type = isStacked ? 'line' : chart_type;

      option = {
        ...commonOptions,
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
        toolbox:{
          feature: {
            magicType: { type: ['line', 'bar','stack', 'tiled'] },
            saveAsImage: {}
          }
        },
        xAxis: {
           type: 'category',
            data: labels,
            axisLabel: {
                rich: {
                    a: { fontSize: 12, color: '#999', fontWeight: 'bold' }
                }
            }
        },
        yAxis: {
          type: "value",
          nameLocation: "middle",
          nameGap: 50,
          boundaryGap: [0, '100%'],
          max: value => Math.ceil(value.max * 1.1),
          splitLine: { show: false },
          axisLabel: { color: '#666' },
          splitLine: { lineStyle: { color: '#eee' } }
        },
        dataZoom: [{ type: 'inside', start: 0, end: 100 }],
        series: series.map(s => ({
          name: s.name,
          type: type === 'stacked' ? 'line' : type,
          stack: isStacked ? "total" : undefined,
          data: s.data,
          smooth: true,
          showSymbol: false
        }))
      };
      break;
  }

  chart.setOption(option);

  // Add resize listener
  const resizeHandler = () => chart.resize();
  window.addEventListener('resize', resizeHandler);

  // Store resize handler for cleanup if needed
  container._resizeHandler = resizeHandler;
}

// Export the main function
window.dChat = { dChatSendRequest };