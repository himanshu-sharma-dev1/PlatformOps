from django.contrib import admin
from .models import (
    ApplicationInfo, Cluster, Node, Service,
    ServiceEvent, NodeEvent, UserInfo, InviteToken
)

admin.site.register(ApplicationInfo)
admin.site.register(Cluster)
admin.site.register(Node)
admin.site.register(Service)
admin.site.register(ServiceEvent)
admin.site.register(NodeEvent)
admin.site.register(UserInfo)
admin.site.register(InviteToken)

