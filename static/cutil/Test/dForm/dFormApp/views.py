import json

from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings
from .models import ReportModel, ClusterModel
import os

from django.views.decorators.csrf import csrf_exempt


# Create your views here.

@csrf_exempt
def cutil_get_flow_schema(file_path):
    with open(file_path, 'r') as f:
        json_data = f.read()
        schema_dict = json.loads(json_data)
    return schema_dict


@csrf_exempt
def dform_static_form(request):
    if request.method == "POST":
        report_name = request.POST.get('report_name')

        data = request.POST.get('json_data')
        action = request.POST.get('user-action')

        if action == 'add':
            ReportModel.objects.create(report_name=report_name, report_data=json.loads(data))

        if action == 'edit':
            report = ReportModel.objects.get(report_name=report_name)
            report.report_data = json.loads(data)
            report.save()

        if action == 'delete':
            report = ReportModel.objects.get(report_name=report_name)
            report.delete()

    report_list = []
    reports = ReportModel.objects.all()

    for report in reports:
        report_list.append(report.report_data)

    file_path = os.path.join(settings.BASE_DIR, 'dFormApp\DFormSchema\StaticFormSchema.json')
    schema = cutil_get_flow_schema(file_path)
    oem_list = ["Cambium","Radwin","Aviat", "Ceragon"]
    context = {'static_schema': json.dumps(schema), "report_list": report_list, 'oem_list': oem_list }
    return render(request, 'StaticForm.html', context)


@csrf_exempt
def dform_static_accordion_form(request):

    if request.method == 'POST':
        cluster_name = request.POST.get('cluster_name')
        data = request.POST.get('json_data')
        action = request.POST.get('user-action')

        if action == 'add':
            ClusterModel.objects.create(cluster_name=cluster_name, cluster_data=json.loads(data))

        if action == 'edit':
            cluster = ClusterModel.objects.get(cluster_name=cluster_name)
            cluster.cluster_data = json.loads(data)
            cluster.save()

        if action == 'delete':
            cluster = ClusterModel.objects.get(cluster_name=cluster_name)
            cluster.delete()

    cluster_list = []
    clusters = ClusterModel.objects.all()

    for cluster in clusters:
        cluster_list.append(cluster.cluster_data)

    file_path = os.path.join(settings.BASE_DIR, 'dFormApp\DFormSchema\StaticAccordionSchema.json')
    schema = cutil_get_flow_schema(file_path)
    context = {'static_acc_schema': json.dumps(schema), 'cluster_list': cluster_list}
    return render(request, 'StaticAccordionForm.html', context)


@csrf_exempt
def dform_map_field(request):
    file_path = os.path.join(settings.BASE_DIR, 'dFormApp\DFormSchema\MapFieldSchema.json')
    field_schema = cutil_get_flow_schema(file_path)
    context = {'field_schema': json.dumps(field_schema)}
    return render(request, 'MapFields.html', context)


@csrf_exempt
def dform_test(request):
    return render(request, 'Index.html', {})


@csrf_exempt
def api_test(request):
    file_path = os.path.join(settings.BASE_DIR, 'dFormApp\DFormSchema\ApiTestSchema.json')
    field_schema = cutil_get_flow_schema(file_path)
    context = {'field_schema': json.dumps(field_schema)}
    return render(request, 'ApiTest.html', context)

@csrf_exempt
def dform_tabs(request):
    file_path = os.path.join(settings.BASE_DIR, 'dFormApp\DFormSchema\TabSchema.json')
    field_schema = cutil_get_flow_schema(file_path)
    context = {'field_schema': json.dumps(field_schema)}
    return render(request, 'Tabs.html', context)


@csrf_exempt
def dform_get_param_list(request):
    if request.POST:
        oem = request.POST.get('oem')
        param = {
            'Radwin': ["HRX", "HX", "HVX"],
            'Cambium': ["HV", "CH", "TL"]
        }

        param_list = param[oem]
        return JsonResponse(param_list, safe=False)


import textwrap
import time
from django.http import HttpResponse, FileResponse, JsonResponse, StreamingHttpResponse

@csrf_exempt
def handleTestReponse(request):
#     if request.method == 'POST':
#         user_query = json.loads(request.body)
#         user_query_list = user_query['query'].split('+') if '+' in user_query['query'] else [user_query['query']]
#
#         content_type = {
# "table": textwrap.dedent("""\
#                 | ID  | Product    | Price | Quantity | In Stock |
#                 |-----|------------|-------|----------|----------|
#                 | 101 | Laptop     | $800  | 10       | Yes      |
#                 | 102 | Keyboard   | $50   | 25       | Yes      |
#                 | 103 | Mouse      | $30   | 0        | No       |
#                 | 104 | Headphone  | $100  | 15       | Yes      |
#
#             """),
#
# "list": """
# - Item 1
# - Item 2
#   - Sub-item 2.1
#   - Sub-item 2.2
# - Item 3
# """,
# "para": "Testing With Paragraph With Combination.....",
#
#             "chart": """::: chart
#             {
#               "chart_type": "line",
#               "height": "35vh",
#               "width": "60vw",
#               "labels": [
#                 "02-Jun:00:00",
#                 "02-Jun:01:00",
#                 "02-Jun:02:00",
#                 "02-Jun:03:00",
#                 "02-Jun:04:00",
#                 "02-Jun:05:00",
#                 "02-Jun:06:00",
#                 "02-Jun:07:00",
#                 "02-Jun:08:00",
#                 "02-Jun:09:00",
#                 "02-Jun:10:00",
#                 "02-Jun:11:00",
#                 "02-Jun:12:00",
#                 "02-Jun:13:00",
#                 "02-Jun:14:00",
#                 "02-Jun:15:00",
#                 "02-Jun:16:00",
#                 "02-Jun:17:00",
#                 "02-Jun:18:00",
#                 "02-Jun:19:00",
#                 "02-Jun:20:00",
#                 "02-Jun:21:00",
#                 "02-Jun:22:00",
#                 "02-Jun:23:00"
#               ],
#               "series": [
#                 {
#                   "name": "req_Count_total",
#                   "data": [
#                     484,
#                     689,
#                     749,
#                     619,
#                     379,
#                     1,
#                     23,
#                     25,
#                     24,
#                     21,
#                     26,
#                     30,
#                     48,
#                     61,
#                     56,
#                     45,
#                     60,
#                     40,
#                     40,
#                     223,
#                     717,
#                     514,
#                     448,
#                     384
#                   ]
#                 },
#                 {
#                   "name": "Overlay",
#                   "data": [
#                     6745,
#                     6556,
#                     6804,
#                     3744,
#                     2478,
#                     566,
#                     78,
#                     69,
#                     89,
#                     226,
#                     138,
#                     87,
#                     296,
#                     324,
#                     707,
#                     596,
#                     448,
#                     601,
#                     713,
#                     751,
#                     538,
#                     553,
#                     783,
#                     600
#                   ]
#                 },
#                 {
#                   "name": "zone_0",
#                   "data": [
#                     126,
#                     157,
#                     165,
#                     120,
#                     73,
#                     0,
#                     10,
#                     10,
#                     9,
#                     8,
#                     7,
#                     9,
#                     10,
#                     8,
#                     9,
#                     11,
#                     10,
#                     10,
#                     12,
#                     58,
#                     310,
#                     80,
#                     76,
#                     64
#                   ]
#                 },
#                 {
#                   "name": "zone_1",
#                   "data": [
#                     354,
#                     531,
#                     584,
#                     498,
#                     304,
#                     0,
#                     12,
#                     15,
#                     15,
#                     13,
#                     18,
#                     17,
#                     15,
#                     17,
#                     16,
#                     15,
#                     15,
#                     18,
#                     11,
#                     151,
#                     375,
#                     415,
#                     364,
#                     316
#                   ]
#                 },
#                 {
#                   "name": "zone_2",
#                   "data": [
#                     4,
#                     1,
#                     0,
#                     1,
#                     2,
#                     1,
#                     1,
#                     0,
#                     0,
#                     0,
#                     1,
#                     4,
#                     23,
#                     36,
#                     31,
#                     19,
#                     35,
#                     12,
#                     17,
#                     14,
#                     32,
#                     19,
#                     8,
#                     4
#                   ]
#                 },
#                 {
#                   "name": "zone_3",
#                   "data": [
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0,
#                     0
#                   ]
#                 }
#               ]
#             }"""
#         }
#         def content_stream():
#             for query in user_query_list:
#                 block = content_type[query]
#                 if block:
#                     for line in block.splitlines():
#                         yield line + "\n"
#                     yield "\n"  # separator between blocks
#
#         return StreamingHttpResponse(content_stream(), content_type="text/plain")

    chat_history = [
        {"query": "Example chat history as list of tuples", "link": "/link1"},
        {"query": "query2", "link": "/ANS/Analytics/NWAudit/"},
        {"query": "query3", "link": "/link3"},
        {"query": "query1", "link": "/link1"},
        {"query": "query2", "link": "/link2"},
        {"query": "query3", "link": "/link3"},
        {"query": "query1", "link": "/link1"},
        {"query": "query2", "link": "/link2"},
        {"query": "query3", "link": "/link3"},
        {"query": "query1", "link": "/link1"},
        {"query": "query2", "link": "/link2"},
        {"query": "query3", "link": "/link3"},
    ]

    query_list=["table","list","para","chart"]
    context = {"chat_history": chat_history,"user_name":"Kirti","title":"dChat","logo_path":"","service_name":"dForm","agent":"dChat_Agent","query_list":query_list,"starter_msg":"Welcome to ","starter_msg_brand":"dChat_Engine"}

    return render(request, 'dChatAI.html', context)

@csrf_exempt
def chat_ai_get_query_response(request):
    if request.method == 'POST':
        user_query = json.loads(request.body)
        user_query_list = user_query['query'].split('+') if '+' in user_query['query'] else [user_query['query']]

        content_type = {
            "table": textwrap.dedent("""\
                    | ID  | Product    | Price | Quantity | In Stock |
                    |-----|------------|-------|----------|----------|
                    | 101 | Laptop     | $800  | 10       | Yes      |
                    | 102 | Keyboard   | $50   | 25       | Yes      |
                    | 103 | Mouse      | $30   | 0        | No       |
                    | 104 | Headphone  | $100  | 15       | Yes      |

                """),

            "list": """
    - Item 1
    - Item 2
      - Sub-item 2.1
      - Sub-item 2.2
    - Item 3
    """,
            "para": "Testing With Paragraph With Combination.....",

            "chart": """::: chart
{
  "chart_type": "line",
  "labels": [
    "09-Aug:00:00",
    "09-Aug:00:15",
    "09-Aug:00:30",
    "09-Aug:00:45",
    "09-Aug:01:00",
    "09-Aug:01:15",
    "09-Aug:01:30",
    "09-Aug:01:45",
    "09-Aug:02:00",
    "09-Aug:02:15",
    "09-Aug:02:30",
    "09-Aug:02:45",
    "09-Aug:03:00",
    "09-Aug:03:15",
    "09-Aug:03:30",
    "09-Aug:03:45",
    "09-Aug:04:00",
    "09-Aug:04:15",
    "09-Aug:04:30",
    "09-Aug:04:45",
    "09-Aug:05:00",
    "09-Aug:05:15",
    "09-Aug:05:30",
    "09-Aug:05:45",
    "09-Aug:06:00",
    "09-Aug:06:15",
    "09-Aug:06:30",
    "09-Aug:06:45",
    "09-Aug:07:00",
    "09-Aug:07:15",
    "09-Aug:07:30",
    "09-Aug:07:45",
    "09-Aug:08:00",
    "09-Aug:08:15",
    "09-Aug:08:30",
    "09-Aug:08:45",
    "09-Aug:09:00",
    "09-Aug:09:15",
    "09-Aug:09:30",
    "09-Aug:09:45",
    "09-Aug:10:00",
    "09-Aug:10:15",
    "09-Aug:10:30",
    "09-Aug:10:45",
    "09-Aug:11:00",
    "09-Aug:11:15",
    "09-Aug:11:30",
    "09-Aug:11:45",
    "09-Aug:12:00",
    "09-Aug:12:15",
    "09-Aug:12:30",
    "09-Aug:12:45",
    "09-Aug:13:00",
    "09-Aug:13:15",
    "09-Aug:13:30",
    "09-Aug:13:45",
    "09-Aug:14:00",
    "09-Aug:14:15",
    "09-Aug:14:30",
    "09-Aug:14:45",
    "09-Aug:15:00",
    "09-Aug:15:15",
    "09-Aug:15:30",
    "09-Aug:15:45",
    "09-Aug:16:00",
    "09-Aug:16:15",
    "09-Aug:16:30",
    "09-Aug:16:45",
    "09-Aug:17:00",
    "09-Aug:17:15",
    "09-Aug:17:30",
    "09-Aug:17:45",
    "09-Aug:18:00",
    "09-Aug:18:15",
    "09-Aug:18:30",
    "09-Aug:18:45",
    "09-Aug:19:00",
    "09-Aug:19:15",
    "09-Aug:19:30",
    "09-Aug:19:45",
    "09-Aug:20:00",
    "09-Aug:20:15",
    "09-Aug:20:30",
    "09-Aug:20:45",
    "09-Aug:21:00",
    "09-Aug:21:15",
    "09-Aug:21:30",
    "09-Aug:21:45",
    "09-Aug:22:00",
    "09-Aug:22:15",
    "09-Aug:22:30",
    "09-Aug:22:45",
    "09-Aug:23:00",
    "09-Aug:23:15",
    "09-Aug:23:30",
    "09-Aug:23:45"
  ],
  "series": [
    {
      "name": "req_Count_total",
      "data": [
        5035,
        4685,
        4219,
        3568,
        3392,
        3161,
        2731,
        2459,
        2484,
        2455,
        2132,
        2106,
        2157,
        1929,
        1807,
        1603,
        1535,
        1463,
        1597,
        1696,
        1805,
        1673,
        1783,
        1901,
        2041,
        2259,
        2389,
        2580,
        2773,
        2924,
        3235,
        3133,
        3209,
        3640,
        3522,
        3877,
        4038,
        4155,
        4121,
        4395,
        4989,
        5094,
        5036,
        5378,
        6657,
        7207,
        7356,
        8197,
        9200,
        9638,
        10013,
        10082,
        10809,
        10889,
        10055,
        10343,
        10449,
        10601,
        10130,
        10166,
        10803,
        10433,
        10297,
        9840,
        10457,
        10658,
        10920,
        11019,
        10929,
        11980,
        11348,
        12201,
        12513,
        12465,
        11694,
        11748,
        11528,
        11800,
        10704,
        10255,
        10315,
        10179,
        10527,
        10060,
        9828,
        9377,
        9581,
        9301,
        9520,
        9992,
        9885,
        9853,
        9168,
        9252,
        8626,
        8244
      ]
    },
    {
      "name": "Overlay",
      "data": [
        1989,
        1315,
        1557,
        1156,
        992,
        653,
        764,
        660,
        651,
        486,
        268,
        254,
        299,
        255,
        242,
        236,
        315,
        261,
        272,
        264,
        303,
        429,
        532,
        466,
        405,
        320,
        444,
        768,
        874,
        911,
        941,
        987,
        1201,
        1075,
        750,
        1102,
        1158,
        1322,
        1452,
        1495,
        1953,
        1880,
        2460,
        2259,
        2733,
        2746,
        4183,
        4393,
        4416,
        4213,
        5777,
        5697,
        6073,
        5887,
        5386,
        6107,
        5371,
        5216,
        5047,
        5408,
        5483,
        5954,
        4848,
        4526,
        4755,
        4080,
        4935,
        5591,
        5307,
        4455,
        6097,
        4927,
        5544,
        5957,
        6099,
        7372,
        7709,
        6240,
        6692,
        4379,
        5641,
        4207,
        4303,
        6098,
        5714,
        4513,
        4813,
        4879,
        4611,
        4108,
        4398,
        3829,
        4059,
        3597,
        3662,
        2495
      ]
    },
    {
      "name": "zone_0",
      "data": [
        1072,
        1013,
        976,
        859,
        751,
        692,
        484,
        528,
        510,
        434,
        367,
        378,
        392,
        304,
        293,
        269,
        263,
        250,
        272,
        259,
        287,
        269,
        284,
        280,
        310,
        283,
        330,
        328,
        371,
        326,
        374,
        347,
        352,
        385,
        401,
        399,
        465,
        457,
        433,
        428,
        480,
        538,
        464,
        597,
        856,
        960,
        993,
        1328,
        1673,
        1629,
        1847,
        1847,
        1981,
        1927,
        1639,
        1722,
        1821,
        2059,
        1956,
        1899,
        2030,
        2045,
        1879,
        1806,
        1875,
        2026,
        2049,
        1916,
        1835,
        2089,
        2148,
        2227,
        2352,
        2503,
        2256,
        2174,
        1969,
        2359,
        2163,
        2249,
        2138,
        2116,
        2117,
        2121,
        2007,
        1923,
        1923,
        2023,
        2241,
        2158,
        1874,
        1891,
        1913,
        2118,
        2036,
        1811
      ]
    },
    {
      "name": "zone_1",
      "data": [
        3527,
        3303,
        2917,
        2419,
        2322,
        2192,
        1991,
        1695,
        1691,
        1765,
        1541,
        1501,
        1534,
        1413,
        1310,
        1153,
        1070,
        1025,
        1132,
        1190,
        1286,
        1158,
        1240,
        1401,
        1507,
        1727,
        1786,
        1981,
        2094,
        2296,
        2562,
        2457,
        2488,
        2888,
        2695,
        2986,
        3101,
        3211,
        3167,
        3406,
        3903,
        3984,
        3956,
        4148,
        5191,
        5597,
        5600,
        6089,
        6724,
        7123,
        7254,
        7300,
        7890,
        7961,
        7468,
        7550,
        7601,
        7661,
        7228,
        7381,
        7844,
        7472,
        7551,
        7092,
        7615,
        7688,
        7965,
        8002,
        8085,
        8765,
        8104,
        8892,
        9058,
        8904,
        8415,
        8508,
        8563,
        8397,
        7521,
        7096,
        7190,
        7061,
        7539,
        7145,
        6948,
        6552,
        6916,
        6505,
        6674,
        7178,
        7282,
        7215,
        6485,
        6438,
        5951,
        5789
      ]
    },
    {
      "name": "zone_2",
      "data": [
        436,
        369,
        326,
        290,
        319,
        277,
        256,
        236,
        283,
        256,
        224,
        227,
        231,
        212,
        204,
        181,
        202,
        188,
        193,
        247,
        232,
        246,
        259,
        220,
        224,
        249,
        273,
        271,
        308,
        302,
        299,
        329,
        369,
        367,
        426,
        492,
        472,
        487,
        521,
        561,
        606,
        572,
        616,
        633,
        610,
        650,
        763,
        780,
        803,
        886,
        912,
        935,
        938,
        1001,
        948,
        1071,
        1027,
        881,
        946,
        886,
        929,
        916,
        867,
        942,
        967,
        944,
        906,
        1101,
        1009,
        1126,
        1096,
        1082,
        1103,
        1058,
        1023,
        1066,
        996,
        1044,
        1020,
        910,
        987,
        1002,
        871,
        794,
        873,
        902,
        742,
        773,
        605,
        656,
        729,
        747,
        770,
        696,
        639,
        644
      ]
    },
    {
      "name": "zone_3",
      "data": [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0
      ]
    }
  ]
}"""
        }

        def content_stream():
            for query in user_query_list:
                block = content_type[query]
                print("block is :",block)
                if block:
                    for line in block.splitlines():
                        yield line + "\n"
                    yield "\n"  # separator between blocks

        return StreamingHttpResponse(content_stream(), content_type="text/plain")