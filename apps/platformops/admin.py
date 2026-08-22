from django.contrib import admin

from .models import (DataflowRealtimeConfig, DataFlowLogs, ModelInfo, ApplicationInfo, ModelInfer,AlgoInfer, \
                     AlgoInfo, ModelCompare, ModelCompareRow, Cluster,ReportInfo, Node, Service, ResourceRow,
                     InferenceResource,UserInfo,ReportLog,DataflowBatchConfig, ServiceEvent,NodeEvent,DataflowStreamConfig, InviteToken,
                     DBPullInferenceJob, DBPullInferenceLog)

# Register your models here.
admin.site.register(DataflowBatchConfig)
admin.site.register(DataflowRealtimeConfig)
admin.site.register(DataFlowLogs)
admin.site.register(ModelInfo)
admin.site.register(ApplicationInfo)
admin.site.register(ModelInfer)
admin.site.register(AlgoInfer)
admin.site.register(AlgoInfo)
admin.site.register(ModelCompare)
admin.site.register(ModelCompareRow)
admin.site.register(Cluster)
admin.site.register(Node)
admin.site.register(Service)
admin.site.register(ResourceRow)
admin.site.register(InferenceResource)
admin.site.register(UserInfo)
admin.site.register(ReportInfo)
admin.site.register(ReportLog)
admin.site.register(ServiceEvent)
admin.site.register(NodeEvent)
admin.site.register(DataflowStreamConfig)
admin.site.register(InviteToken)
admin.site.register(DBPullInferenceJob)
admin.site.register(DBPullInferenceLog)

