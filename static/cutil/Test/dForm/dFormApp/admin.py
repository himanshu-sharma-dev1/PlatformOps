from django.contrib import admin

# Register your models here.
from .models import ReportModel, ClusterModel

admin.site.register(ReportModel)
admin.site.register(ClusterModel)
