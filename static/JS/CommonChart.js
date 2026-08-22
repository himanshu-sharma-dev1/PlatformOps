
function createChart(chartId, chartData, chartTitle, yAxisLabel) {
  var fontSize=12;
  var chartDom = document.getElementById(chartId);
  var myChart = echarts.init(chartDom, 'dark');

  var series = [];
  for (var i = 0; i < chartData.seriesNames.length; i++) {
    var type1 = chartData.seriesNames[i] !== 'ANOMALY' ? 'line' : 'scatter';
    series.push({
      name: chartData.seriesNames[i] || ('Series ' + (i + 1)),
      type: type1,
      smooth: true,
      data: chartData.seriesData[i] || []
    });
  }

  var option = {
    backgroundColor: 'transparent',
    animationDuration: 2000,
    title: {
      text: chartTitle || 'Stacked Line',
      textStyle: {
        fontSize: fontSize || 11
      }
    },
    tooltip: {
      order: 'valueAsc',
      triggerOn: "mousemove|click",
      position: 'right',
      show: true,
      trigger: "axis",
      renderMode: "richText",
      textStyle: {
        fontSize: fontSize || 11
      }
    },
    legend: {
      data: chartData.legendData || [],
      textStyle: {
        fontSize: fontSize || 11
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: chartData.labels || []
    },
    yAxis: {
      type: 'value',
      name: yAxisLabel || 'Fares',
      nameTextStyle: {
        fontSize: fontSize || 11
      }
    },
    series: series
  };

  option && myChart.setOption(option);
}


function createSingleChart(chartId, chartData, chartTitle, yAxisLabel, fontSize, parentBorderStyle) {
  var chartDom = document.getElementById(chartId);

  // Set border style for the chart container
  chartDom.style.border = parentBorderStyle || '1px solid #fff';

  var myChart = echarts.init(chartDom, 'dark');

  var series = [];
  for (var i = 0; i < chartData.seriesNames.length; i++) {
    series.push({
      name: chartData.seriesNames[i] || ('Series ' + (i + 1)),
      type: 'line',
      stack: 'stack',
      areaStyle: {},
      emphasis: {
        focus: 'series'
      },
      smooth: true,
      data: chartData.seriesData[i] || []
    });
  }

  var option = {
    backgroundColor: 'transparent',
    color: ['#80FFA5', '#00DDFF', '#37A2FF', '#FF0087', '#FFBF00'],
    title: {
      text: chartTitle || 'Stacked Area',
      textStyle: {
        fontSize: fontSize || 11
      }
    },

    tooltip: {
      order: 'valueAsc',
      triggerOn: "mousemove|click",
      position: 'right',
      show: true,
      trigger: "axis",
      renderMode: "richText",
      textStyle: {
        fontSize: fontSize || 11
      }
    },
    legend: {
      data: chartData.legendData || [],
      textStyle: {
        fontSize: fontSize || 11
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    toolbox: {
     show: false,
      feature: {
        saveAsImage: {},
        magicType: {
          type: ['line', 'bar', 'stack']
        }
      }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: chartData.labels || [],
      axisLabel: {
        textStyle: {
          fontSize: fontSize || 10
        }
      }
    },
    yAxis: {
      type: 'value',
      name: yAxisLabel || 'Fares',
      nameTextStyle: {
        fontSize: fontSize || 0
      },
      axisLabel: {
        textStyle: {
          fontSize: fontSize || 11
        }
      }
    },
    series: series
  };

  option && myChart.setOption(option);
}
