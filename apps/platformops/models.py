import uuid
from django.db import models

REPOSITORY_TYPE = [
    ('GitHub', 'GitHub'),
    ('GitLab', 'GitLab'),
    ('Bitbucket', 'Bitbucket'),
    ('Local', 'Local'),
    ('LocalVolume', 'LocalVolume'),
    ('NFSVolume', 'NFSVolume'),
    ('DistributedFS', 'DistributedFS'),
    ('Transport_Sync', 'Transport_Sync'),
]

CLUSTER_REGION_TYPE = [
    ('ap-south-1 (Mumbai)', 'ap-south-1 (Mumbai)'),
    ('ap-south-2 (Hyderabad)', 'ap-south-2 (Hyderabad)'),
    ('north-india', 'north-india'),
    ('us-east-1 (N. Virginia)', 'us-east-1 (N. Virginia)'),
    ('eu-west-1 (Ireland)', 'eu-west-1 (Ireland)')
]

CLUSTER_ENVIRONMENT_TYPE = [
    ('Production', 'Production'),
    ('prod', 'Production'),
    ('Staging', 'Staging'),
    ('staging', 'Staging'),
    ('Development', 'Development'),
    ('dev', 'Development'),
    ('Edge', 'Edge'),
    ('UAT', 'UAT'),
    ('uat', 'UAT'),
]

CLUSTER_TYPE = [
    ('Primary', 'Primary'),
    ('Secondary', 'Secondary')
]

CLUSTER_TYPE_VARIENT = [
    ('Kubernetes', 'Kubernetes'),
    ('Standalone', 'Standalone'),
    ('Docker', 'Docker'),
    ('Docker Standalone', 'Docker Standalone'),
    ('Edge', 'Edge')
]

IMAGE_STORE = [
    ('Dockerhub', 'Dockerhub'),
    ('Local', 'Local'),
]

SERVICE_TYPE = [
    ('AIOrchestrator', 'AIOrchestrator'),
    ('TrainingServer', 'TrainingServer'),
    ('InferenceServer', 'InferenceServer'),
    ('MCPServer', 'MCPServer'),
    ('PlatformOpsTest', 'PlatformOpsTest'),
    ('redis', 'redis'),
    ('postgres', 'postgres'),
    ('rabbitmq', 'rabbitmq'),
    ('clickhouse', 'clickhouse'),
    ('kafka', 'kafka'),
    ('airflow', 'airflow'),
    ('Nifi', 'Nifi'),
    ('prometheus', 'prometheus'),
    ('process-exporter', 'process-exporter'),
]

APPLICATION_TYPE = [
    ('PlatformOps', 'PlatformOps'),
    ('Core_Infra', 'Core_Infra'),
    ('Monitoring', 'Monitoring'),
    ('Diagnostics', 'Diagnostics'),
]

SEVERITY = [
    ('CRITICAL', 'CRITICAL'),
    ('HIGH', 'HIGH'),
    ('MEDIUM', 'MEDIUM'),
    ('LOW', 'LOW'),
    ('INFO', 'INFO'),
]

DEBUG_OPTIONS = [
    ('DISABLE', 'DISABLE'),
    ('INFO', 'INFO'),
    ('DEBUG', 'DEBUG')
]

DEPLOY_OPTIONS = [
    ('NOT DEPLOYED', 'NOT DEPLOYED'),
    ('DEPLOYED', 'DEPLOYED')
]

ROLE = [
    ('Management', 'Management'),
    ('Admin', 'Admin'),
    ('System_Admin', 'System_Admin'),
    ('Operational', 'Operational'),
    ('Developer', 'Developer'),
    ('Viewer', 'Viewer'),
]


class ApplicationInfo(models.Model):
    application_idx = models.AutoField(primary_key=True)
    app_id = models.CharField(max_length=30)
    created_date = models.DateField(null=True, blank=True)
    app_name = models.CharField(max_length=30, null=True, blank=True)
    app_config = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return f"application_idx:{self.application_idx}"


class Cluster(models.Model):
    cluster_idx = models.AutoField(primary_key=True)
    cluster_id = models.CharField(max_length=30)
    cluster_name = models.CharField(max_length=100, default="None")
    repo_type = models.CharField(choices=REPOSITORY_TYPE, max_length=100)
    cluster_type = models.CharField(choices=CLUSTER_TYPE, default='Secondary', max_length=100)
    cluster_type_varient = models.CharField(choices=CLUSTER_TYPE_VARIENT, default='Standalone', max_length=100)
    image_store_type = models.CharField(choices=IMAGE_STORE, max_length=100, null=True, blank=True)
    image_store_path = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=500, default="None")
    region = models.CharField(choices=CLUSTER_REGION_TYPE, default='ap-south-1 (Mumbai)', max_length=100)
    environment = models.CharField(choices=CLUSTER_ENVIRONMENT_TYPE, default='Production', max_length=100)

    def __str__(self):
        return f"cluster_idx:{self.cluster_idx}"


class NodeAuth(models.Model):
    auth_type = models.CharField(max_length=100, default='Password')
    encryption_key_name = models.CharField(max_length=255, null=True, blank=True)
    encryption_key_text = models.TextField(null=True, blank=True)
    username = models.CharField(max_length=30, default='root')
    password = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        abstract = True


class Node(NodeAuth):
    node_idx = models.AutoField(primary_key=True)
    node_id = models.CharField(max_length=30)
    node_name = models.CharField(max_length=100, default="None")
    node_ip = models.GenericIPAddressField(null=True, default='0.0.0.0')
    node_volume = models.CharField(max_length=200, default="/tmp")
    node_monitor_port = models.IntegerField(default=9010)
    gpu_status = models.CharField(max_length=100, default='disabled', null=True)
    node_launch_status = models.BooleanField(default=False, null=True)
    node_provision_config = models.JSONField(default=dict, null=True, blank=True)
    Cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)

    def __str__(self):
        return f"node_idx:{self.node_idx}"


class NodeEvent(models.Model):
    event_id = models.AutoField(primary_key=True)
    node = models.ForeignKey(Node, on_delete=models.CASCADE)
    event_date = models.DateField()
    event_time = models.TimeField()
    event_severity = models.CharField(choices=SEVERITY, max_length=100)
    event_trigger = models.CharField(max_length=100, null=True, blank=True)
    event_msg = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"event_id:{self.event_id}"


class Service(models.Model):
    service_idx = models.AutoField(primary_key=True)
    service_id = models.CharField(max_length=30)
    service_name = models.CharField(max_length=30, default="None")
    service_type = models.CharField(max_length=100)
    service_port = models.IntegerField(default=11010)
    service_volume = models.CharField(max_length=200, default="/tmp")
    service_install = models.CharField(max_length=100, default="MANUAL")
    service_version = models.CharField(max_length=100)
    service_debug = models.CharField(max_length=100, choices=DEBUG_OPTIONS, default="DISABLE")
    deploy_status = models.CharField(max_length=100, choices=DEPLOY_OPTIONS, default="NOT DEPLOYED")
    service_config = models.JSONField(default=dict)
    Node = models.ForeignKey(Node, on_delete=models.CASCADE, null=True, blank=True)
    Application = models.ForeignKey(ApplicationInfo, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"service_idx:{self.service_idx}"


class ServiceEvent(models.Model):
    event_id = models.AutoField(primary_key=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    event_date = models.DateField()
    event_time = models.TimeField()
    event_severity = models.CharField(choices=SEVERITY, max_length=100)
    event_trigger = models.CharField(max_length=100, null=True, blank=True)
    event_msg = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"event_id:{self.event_id}"


class UserInfo(models.Model):
    user_idx = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=8)
    user_email = models.EmailField(max_length=200)
    user_name = models.CharField(max_length=100, null=True, blank=True)
    user_role = models.CharField(choices=ROLE, max_length=50)
    user_number = models.CharField(max_length=15, null=True, blank=True)
    created_date = models.DateField()
    STATUS = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('disabled', 'Disabled'),
    ]
    status = models.CharField(choices=STATUS, max_length=20, default='pending')
    login_count = models.IntegerField(default=0)
    session_info = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user_name} ({self.user_id})"


class InviteToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user_name = models.CharField(max_length=255, null=True, blank=True)
    user_email = models.EmailField(max_length=255, null=True, blank=True)
    user_role = models.CharField(max_length=50, null=True, blank=True)
    user_number = models.CharField(max_length=20, null=True, blank=True)
    permissions = models.JSONField(default=list, null=True, blank=True)
    invited_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)

    def __str__(self):
        return f"invite_{self.user_email}_{self.token}"
