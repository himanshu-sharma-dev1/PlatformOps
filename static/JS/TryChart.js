//function createSingleChart(chartId, chartData, chartTitle){
//var chartDom = document.getElementById(chartId);
// var myChart = echarts.init(chartDom);
// console.log('chartData-------------',chartData)
//option = {
//
//  title: {
//    text: chartTitle || 'Stacked Line'
//  },
//  tooltip: {
//    trigger: 'axis'
//  },
//  legend: {
//    data:  ['2x16-QAM 3/4', '2x256-QAM 3/4', '2x64-QAM 3/4', '2x64-QAM 5/6']
//
//  },
//  grid: {
//    left: '3%',
//    right: '4%',
//    bottom: '3%',
//    containLabel: true
//  },
//  toolbox: {
//    feature: {
//      saveAsImage: {}
//    }
//  },
//  xAxis: {
//    type: 'category',
//    boundaryGap: false,
////    data:['2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30']
//
//  },
//  yAxis: {
//    type: 'value'
//  },
//  series: [
//    {
//      name: '2x16-QAM 3/4',
//      type: 'line',
//      stack: 'Total',
//      data: [8, 8, 4, 2, 3, 4, 3, 4, 4, 4, 4, 8]
//    },
//    {
//      name: '2x256-QAM 3/4',
//      type: 'line',
//      stack: 'Total',
//      data: [8, 8, 4, 2, 3, 4, 3, 4, 4, 4, 4, 8]
//    },
//    {
//      name: '2x64-QAM 3/4',
//      type: 'line',
//      stack: 'Total',
//      data: [8, 8, 4, 2, 3, 4, 3, 4, 4, 4, 4, 8]
//    },
//    {
//      name: '2x64-QAM 5/6',
//      type: 'line',
//      stack: 'Total',
//      data: [8, 8, 4, 2, 3, 4, 3, 4, 4, 4, 4, 8]
//    },
//
//  ]
//};
//
//      // Display the chart using the configuration items and data just specified.
//      myChart.setOption(option);
//}


//function createSingleChart(chartId, chartData, chartTitle){
//var myChart;
//
//myChart = echarts.init(document.getElementById(chartId));
// console.log('chartData-------------',chartData)
//
//  var seriesDataArray = Object.entries(chartData.seriesNames).map(([name, data]) => {
//        return {
//            name: name,
//            type: 'line',
//            stack: 'Total',
//            data: data
//        };
//    });
//option = {
//
//  title: {
//    text: chartTitle || 'Stacked Line'
//  },
//   tooltip: {
//    trigger: 'axis', // or 'item'
//    axisPointer: {
//        type: 'cross' // or other types based on your requirement
//    }
//},
//  legend: {
//    data: chartData.legendData
//
//  },
//  grid: {
//    left: '3%',
//    right: '4%',
//    bottom: '3%',
//    containLabel: true
//  },
//  toolbox: {
//    feature: {
//      saveAsImage: {}
//    }
//  },
//  xAxis: {
//    type: 'category',
//    boundaryGap: false,
////    data:['2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30', '2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30','2023-08-24 01:00:00+05:30']
//
//  },
//  yAxis: {
//    type: 'value'
//  },
//  series:  seriesDataArray
//};
//
//      // Display the chart using the configuration items and data just specified.
//      myChart.setOption(option);
//}


//

function createSingleChart(chartId, chartData, chartTitle) {
    var myChart;

    myChart = echarts.init(document.getElementById(chartId));
    console.log('chartData-------------', chartData);

    var seriesDataArray = Object.entries(chartData.seriesNames).map(([name, data]) => {
        return {
            name: name,
            type: 'line',
            stack: 'Total',
            data: data
        };
    });

    var option = {
        title: {
            text: chartTitle || 'Stacked Line',
            textStyle: {
                color: '#000', // Font color in hex format
                fontSize: 11
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        legend: {
            data: chartData.legendData,
            textStyle: {
                color: '#000' // Font color in hex format
            },
            top: '20px'
        },
           grid: {
            left: '2%',
            right: '2%',
            bottom: '2%',
            containLabel: true,
            show: false,
        },
        toolbox: {
            feature: {
                saveAsImage: {}
            }
        },
        /* xAxis: {
            type: 'category',
            boundaryGap: false,
            data: chartData.labels,
            axisLabel: {
                textStyle: {
                    color: '#ffffff' // Font color in hex format
                },
                formatter: function (value) {
                    // Use a formatter if you want to customize the displayed label
                    // Example: Format the label to show only the time
                    return value.split(' ')[1];
                }
            }
        },*/
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: chartData.labels,
            axisLabel: {
                textStyle: {
                color: '#000',
                fontSize: 10
                },
            }
        },

        yAxis: {
            type: 'value',
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#212529'
                }
            },
            axisLabel: {
                textStyle: {
                    color: '#000'
                }
            }
        },
        series: seriesDataArray
    };

    // Display the chart using the configuration items and data just specified.
    myChart.setOption(option);
}

