from django.urls import path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from dFormApp.views import dform_static_form, dform_static_accordion_form, dform_map_field, dform_test, dform_tabs, api_test, dform_get_param_list, handleTestReponse, chat_ai_get_query_response

urlpatterns = [
    path('', dform_test, name='dFormApp'),
    path('dForm/Static', dform_static_form, name='dFormApp'),
    path('dForm/StaticAccordion', dform_static_accordion_form, name='dFormApp'),
    path('dForm/MapFields', dform_map_field, name='dFormApp'),
    path('dForm/ApiTest', api_test, name='dFormApp'),
    path('dForm/Tabs', dform_tabs, name='dformApp'),
    path('dForm/getParamList', dform_get_param_list, name='dFormApp'),
    path('dForm/TestResponse/', handleTestReponse, name='dFormApp'),
    path('dForm/ChatAI/GetQueryResponse/', chat_ai_get_query_response, name='dFormApp')
    
]

urlpatterns += staticfiles_urlpatterns()

