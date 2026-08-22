from django.db import models


# Create your models here.


class ReportModel(models.Model):
    report_name = models.CharField(max_length=100)
    report_data = models.JSONField(default=dict)  # This is the JSON field

    def __str__(self):
        return self.report_name


class ClusterModel(models.Model):
    cluster_name = models.CharField(max_length=100)
    cluster_data = models.JSONField(default=dict)  # This is the JSON field

    def __str__(self):
        return self.cluster_name
