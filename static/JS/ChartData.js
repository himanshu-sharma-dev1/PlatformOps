
//---------------------------------------------------- Echarts ---------------------------------------------------------

// Pie Charts
function createPieChart(obj) {
    const option = {
        tooltip: {
            trigger: 'item',
            position: ['70%', '50%'],
            formatter: function (params) {
                return `<strong>${params.name}</strong>: ${params.value} (${params.percent}%)`;
            },
            show: true
        },

         legend: {
            orient: 'vertical',
            left: 'left',
            top: 'top',
            width: 'auto',
            height: 'auto',
            itemWidth: 15,
            itemHeight: 12,
            textStyle: {
                fontSize: 9
            },
            data: obj.label_data,
        },

        series: [
            {
                name: 'Lot Category',
                type: 'pie',
                radius: '75%',
                center: ['65%', '50%'],
                label: {
                    position: 'outside',
                    formatter: '{d}%',
                    color: '#000',
                    fontSize: 10,
                    show: true
                },
                labelLine: {
                    show: true,
                    length: 5,
                    length2: 8
                },
                percentPrecision: 0,
                itemStyle: {
                    borderColor: '#fff',
                    borderWidth: 1
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: 12,
                        fontWeight: 'normal',
                        formatter: ' {c} '
                    },
                    itemStyle: {
                        shadowBlur: 0,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                },
                data: obj.data.map((item, index) => ({
                    value: item.value,
                    name: item.name,
                    itemStyle: {
                        color: obj['data'][index]['color']
                    }
                }))
            }
        ]
    };

    const chartElement = document.getElementById(obj.chartId);
    if (!chartElement) {
        console.error('Element with id', obj.chartId, 'not found.');
        return;
    } else {
        const chart = echarts.init(chartElement);
        chart.setOption(option);
        return chart;
    }
}




// Meter Chart
function createMeter(chartId, user_data) {
    let chart = document.getElementById(chartId).getContext('2d');

    let barChartData1 = {
        datasets: [
            {
                backgroundColor: ['#ed8585', '#efdf71', '#53cda9'],
                borderWidth: 0,
                cutout: '40%',
                data: [20, 30, 50],
            },
            {
                backgroundColor: ['#6495ED', 'grey'],
                borderWidth: 0,
                data: user_data,
            }
        ],
    };

    let myBarChart1 = new Chart(chart, {
        type: 'doughnut',
        data: barChartData1,
        options: {
            maintainAspectRatio: false,
            animation: {
                duration: 3000,
                easing: "easeInOutBounce"
            },
            tooltips: { enabled: false },
            responsive: true,
            rotation: 86 * Math.PI,
            circumference: 57 * Math.PI,
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#000' }
                },
                datalabels: {
                    display: false
                }
            }
        }
    });
}


// Create Series
function createSeries(data, name, color) {
    return {
        data: data,
        type: 'line',
        name: name,
        smooth: false,
        symbol: 'none',
        lineStyle: {
            color: color,
            width: 2
        },
        itemStyle: {
            color: color
        },
        emphasis: {
            focus: 'series'
        }
    };
}

// Create Chart
function generateHourlyLineChart(containerId, data, ParamName, title) {
    if (!data || typeof data !== 'object') {
        console.error('Invalid data provided.');
        return;
    }
    let avgValue = data['AVG'];
    let maxValue = data['MAX'];
    let minValue = data['MIN'];
    let labels = data['chart_date'];

    let maxDataValue = Math.max(...minValue, ...maxValue, ...avgValue);
    let yAxisMax = maxDataValue < 0 ? 0 : Math.ceil(maxDataValue / 10) * 10;

    let gridTop = '10%', gridBottom = '10%';
    if (labels.length > 48 || labels.length > 24) {
        gridTop = '08%', gridBottom = '10%';
    }

    const option = {
       title: {
          text: title? title : '',
          left: '350',
          top: '0px',
          textStyle: {
            fontSize: 10,
            color: '#817f7f',
          },
       },
        tooltip: {
            trigger: 'axis',
            textStyle: {
                fontSize: 12,
                fontFamily: 'Arial',
            },
            formatter: function (params) {
                if (params.length === 0) return '';

                let tooltipContent = `<div style="font-size: 14px; margin-bottom: 5px;">${params[0].name}</div>`;
                params.forEach(param => {
                    tooltipContent += `
                        <div style="color: ${param.color};">
                            ${param.seriesName}: ${param.value}
                        </div>`;
                });
                return tooltipContent;
            }
        },
        legend: {
            data: ['AVG', 'MIN', 'MAX'],
            align: 'left',
            left: '10%',
            textStyle: {
                fontSize: 10,
            },
            selectedMode: true
        },

        xAxis: {
            type: 'category',
            data: labels,
            nameLocation: 'middle',
            nameGap: 30,
            boundaryGap: false,
            splitLine: {
                show: false
            },
            axisLabel: {
                rotate: 0,
                formatter: function (value) {
                    let dataArr = value.split('_')
                    let newFormat = dataArr.join("-")
 
                    const parsed = dayjs(`${newFormat}:00`, 'DD-MM HH');
                    const timeStr = parsed.format('HH:mm');
                    const dateStr = parsed.format('DD-MMM');
                    return `{a|${timeStr}}\n{b|${dateStr}}`;
                },
                rich: {
                    a: {
                        fontSize: 12,
                        color: '#333',
                        fontWeight: 'bold'
                    },
                    b: {
                        fontSize: 11,
                        color: '#999'
                    }
                }
            }
        },


        yAxis: {
            type: 'value',
            nameLocation: 'middle',
            nameGap: 50,
            axisLabel: {
                formatter: function (value) {
                    if (value >= 1000000) {
                        return (value / 1000000) + 'M';
                    } else if (value >= 1000) {
                        return (value / 1000) + 'K';
                    } else {
                        return value;
                    }
                }
            },
            max: yAxisMax,
            boundaryGap: [0, '100%'],
            splitLine: {
                show: false
            }
        },
        grid: {
            left: '2%',
            right: '3%',
            bottom: gridBottom,
            top: gridTop,
            containLabel: true
        },
        toolbox: {
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {},
                saveAsImage: {
                    name: ParamName
                }
            }
        },
        dataZoom: [
            {
                type: 'inside',
                start: 0,
                end: 100
            }
        ],
        series: [
            createSeries(avgValue, 'AVG', '#B57BA6'),
            createSeries(minValue, 'MIN', '#96C3CE'),
            createSeries(maxValue, 'MAX', '#4BC6B9')
        ]
    };

    let chart = echarts.init(document.getElementById(containerId));
    chart.setOption(option);
}



//Create Line Chart
function createLineChart(data, labels, chartDom,chart_param){
    let option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'line',
                label: {
                    backgroundColor: '#6a7985'
                }
            }
        },
        legend: {
            data: [],
            align: 'left',
            selectedMode: true,
            textStyle: {
                fontSize: 10,
            }
        },
        toolbox: {
            feature: {
                saveAsImage: {
                    name : chart_param
                }
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: [
            {
                type: 'category',
                boundaryGap: false,
                data: labels,
                splitLine: {
                    show: false
                }
            }
        ],
        yAxis: {
            type: 'value',
            nameLocation: 'middle',
            nameGap: 50,
            axisLabel: {
                formatter: function (value) {
                    if (value >= 1000000) {
                        return (value / 1000000) + 'M';
                    } else if (value >= 1000) {
                        return (value / 1000) + 'K';
                    } else {
                        return value;
                    }
                }
            },

            boundaryGap: [0, '100%'],
            splitLine: {
                show: false
            }
        },
        series: {
            name: chart_param,
            type: 'line',
            emphasis: {
                focus: 'series'
            },
            data: data,
            symbol: 'circle',
            symbolSize: 4
          }
    };

    let myChart = echarts.init(chartDom);
    myChart.setOption(option);
}