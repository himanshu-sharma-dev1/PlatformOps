from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
import uuid
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

REPOSITORY_TYPE = [
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
    ('Staging', 'Staging'),
    ('Development', 'Development'),
    ('Edge', 'Edge')
]

CLUSTER_TYPE = [
    ('Primary', 'Primary'),
    ('Secondary', 'Secondary')
]

CLUSTER_TYPE_VARIENT = [
    ('Kubernetes', 'Kubernetes'),
    ('Standalone', 'Standalone'),
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
    ('ConvForm', 'ConvForm'),
    ('RAG', 'RAG'),
    ('Text2SQL', 'Text2SQL'),
    ('Text2CLK', 'Text2CLK'),
    ('ASR', 'ASR'),
    ('ANS', 'ANS'),
    ('DataJam', 'DataJam'),
    ('MCPServer', 'MCPServer'),
    ('optionCopilot', 'optionCopilot'),
    ('AirtelChurn', 'AirtelChurn'),
]

FILE_DOWNLOAD_PROTOCOL = [
    ('FTP', 'FTP'),
    ('SFTP', 'SFTP'),
]

SOURCE = [
    ('FTP', 'FTP'),
    ('S3', 'S3'),
    ('LOCAL', 'LOCAL'),
    ('SFTP', 'SFTP'),
    ('WEB_SCRAP', 'WEB_SCRAP'),
    ('Google_Drive', 'Google_Drive'),
    ('Fin_Data', 'Fin_Data'),
    ('churnData','churnData'),
]

MODEL_STATUS = [
    ('Scheduled', 'Scheduled'),
    ('Present', 'Present'),
    ('TrainingFailed', 'TrainingFailed'),
    ('TrainingInProcess', 'TrainingInProcess'),
    ('TrainingComplete', 'TrainingComplete'),
]

ADMIN_STATUS = [
    ('Enable', 'Enable'),
    ('Disable', 'Disable'),
]

REPORT_METHOD = [
    ('LOCAL', 'LOCAL'),
    ('EMAIL', 'EMAIL'),
]

DATAFLOW_STATUS = [
    ('Started', 'Started'),
    ('Success', 'Success'),
    ('Failure', 'Failure'),
]

ROLE = [
    ('System_Admin', 'System_Admin'),
    ('Operational', 'Operational'),
    ('Management', 'Management'),
]

REAMTIME_PROTOCOL = [
    ('HTTP', 'HTTP'),
    ('MQTT', 'MQTT'),
    ('CDC', 'CDC'),
]

DATAFLOW_DIRECTION = [
    ('Ingress', 'Ingress'),
    ('Egress', 'Egress'),
]

INGESTION = [
    ('FrontEnd', 'FrontEnd'),
    ('BackEnd', 'BackEnd'),
]

DATAFLOW_TYPE_INGRESS = [
    ('Transaction Data', 'Transaction Data'),
    ('Dealer Data', 'Dealer Data'),
    ('Customer Data', 'Customer Data'),
]

DATAFLOW_TYPE_EGRESS = [
    ('Event_Data', 'Event_Data'),
    ('Suspected_Tx', 'Suspected_Tx'),
]

DATAFLOW_TYPE_REALTIME = [
    ('CLICKSTREAM', 'CLICKSTREAM'),
    ('TRANSACTION', 'TRANSACTION'),
]

DATAFLOW_LOG_CAT = [
    ('Scheduled', 'Scheduled'),
    ('Adhoc', 'Adhoc'),
]

SCHEDULE_PERIODICITY = [
    ('5m', '5m'),
    ('15m', '15m'),
    ('HOURLY', 'HOURLY'),
    ('DAILY', 'DAILY'),
    ('WEEKLY', 'WEEKLY'),
    ('MONTHLY', 'MONTHLY'),
    ('ONCE', 'ONCE'),
]

TIMEZONES = [
    ('US/Eastern', 'US/Eastern'),
    ('US/Central', 'US/Central'),
    ('US/Pacific', 'US/Pacific'),
    ('Europe/London', 'Europe/London'),
    ('UTC', 'UTC'),
    ('Europe/Belgrade', 'Europe/Belgrade'),
    ('Asia/Kolkata', 'Asia/Kolkata')
]

SEVERITY = [
    ('Low', 'Low'),
    ('Medium', 'Medium'),
    ('High', 'High')
]

MODEL_PREPROCESS = [
    ('2-Stage-Preprocess', '2-Stage-Preprocess'),
    ('Woe-Encode', 'Woe-Encode'),
    ('Text-Tokenization', 'Text-Tokenization'),
    ('Donut_Processor', 'Donut_Processor')
]

MODEL_ALGO_CATEGORY = [
    ('Supervised', 'Supervised'),
    ('AutoEncoder', 'AutoEncoder'),
    ('Supervised-Unbalanced', 'Supervised-Unbalanced'),
    ('Anomaly', 'Anomaly'),
    ('TelecomChurn', 'TelecomChurn'),
    ('FraudAnalytics', 'FraudAnalytics'),
    ('TimeSeries_Forecast', 'TimeSeries_Forecast'),
    ('Telecom_KPI_Prediction', 'Telecom_KPI_Prediction'),
    ('ReinforceLearning', 'ReinforceLearning'),
    ('CausalML', 'CausalML'),
    ('GenAI_DocModels', 'GenAI_DocModels'),
    ('NLP', 'NLP'),
    ('ComputerVision', 'ComputerVision'),
    ('Rule_Mining', 'Rule_Mining'),
]

MODEL_ALGO_TYPE = [
    ('LR', 'LR'),  # Supervised
    ('LGM', 'LGM'),  # Supervised
    ('XGBOOST', 'XGBOOST'),  # Supervised
    ('NN', 'NN'),  # Supervised

    ('LGM_UB', 'LGM_UB'),  # Supervised Unbalanced
    ('XGBOOST_UB', 'XGBOOST_UB'),  # Supervised Unbalanced
    ('NN_UB', 'NN_UB'),  # Supervised Unbalanced

    ('Anomaly_OCS', 'Anomaly_OCS'),  # Anomaly
    ('Anomaly_LOF', 'Anomaly_LOF'),  # Anomaly
    ('Anomaly_IF', 'Anomaly_IF'),  # Anomaly
    ('Anomaly_PM', 'Anomaly_PM'),  # Anomaly

    ('IPAnalytics', 'IPAnalytics'),  # FraudAnalytics
    ('EmailAnalytics', 'EmailAnalytics'),  # FraudAnalytics
    ('DigitalFootprints', 'DigitalFootprints'),  # FraudAnalytics

    ('DeepAR', 'DeepAR'),  # TimeSeries_Forecast
    ('Prophet', 'Prophet'),  # TimeSeries_Forecast
    ('PM-ARIMA', 'PM-ARIMA'),  # TimeSeries_Forecast
    ('LSTM', 'LSTM'),  # TimeSeries_Forecast

    ('DeepAR', 'DeepAR'),  # ReinforceLearning

    ('LinearDML', 'LinearDML'),  # CausalML
    ('NonParamDML', 'NonParamDML'),  # CausalML
    ('CausalForestDML', 'CausalForestDML'),  # CausalML
    ('MetaLearner', 'MetaLearner'),  # CausalML

    ('LayoutLM', 'LayoutLM'),  # DocumentAI
    ('LayoutLM3', 'LayoutLM3'),  # DocumentAI
    ('Clova-ix Donut-base', 'Clova-ix Donut-base'),  # DocumentAI

    ('Google_T5', 'Google_T5'),  # NLP
    ('Google_Bert', 'Google_Bert'),  # NLP
    ('Meta_Bard', 'Meta_Bard'),  # NLP

    ('Meta_Segment', 'Meta_Segment'),  # ComputerVision

    ('LSTM_Multivariate', 'LSTM_Multivariate'),  # Telecom_KPI_Prediction

    ('FP-Growth', 'FP-Growth'),
    ('Apriori ', 'Apriori '),

    ('XGBOOST_Churn_UB', 'XGBOOST_Churn_UB'),
    ('XGBOOST_Churn_PREDICTION', 'XGBOOST_Churn_PREDICTION'),
    ('AUTO_GLUON_CHURN_UB', 'AUTO_GLUON_CHURN_UB'),

    ('ACCESSIBILITY', 'ACCESSIBILITY'),
    ('RELIABILITY', 'RELIABILITY'),
    ('RETAINABILITY', 'RETAINABILITY'),
    ('MOBILITY', 'MOBILITY'),
    ('VOICE_INTEGRITY', 'VOICE_INTEGRITY'),
    ('DATA_INTEGRITY', 'DATA_INTEGRITY'),
    ('RECHARGE', 'RECHARGE'),
    ('USAGE_DATA', 'USAGE_DATA'),
    ('USAGE_VOICE', 'USAGE_VOICE'),
    ('NETWORK', 'NETWORK')
]

MODEL_CONFIG_ROLE = [
    ('ModelEvaluate', 'ModelEvaluate'),
    ('ModelActive', 'ModelActive'),
]

MODEL_ALGO_STATUS = [
    ('Created', 'Created'),
    ('Training_Scheduled', 'Training_Scheduled'),
    ('Training_Ongoing', 'Training_Ongoing'),
    ('Training_Success', 'Training_Success'),
    ('Training_Failed', 'Training_Failed'),
]

DATAFLOW_TYPE = DATAFLOW_TYPE_INGRESS + DATAFLOW_TYPE_EGRESS

APPLICATION_TYPE = [
    ('P2P_Credit', 'P2P_Credit'),
    ('SME_Credit', 'SME_Credit'),
    ('Vehicle_Credit', 'Vehicle_Credit'),
    ('Register_Fraud', 'Register_Fraud'),
    ('Transact_Fraud', 'Transact_Fraud'),
    ('Propensity_Onboard', 'Propensity_Onboard'),
    ('Uplift_Onboard', 'Uplift_Onboard'),
    ('Churn_Service', 'Churn_Service'),
    ('P2P_Collection', 'P2P_Collection'),
    ('SME_Collection', 'SME_Collection'),
    ('Vehicle_Collection', 'Vehicle_Collection'),
    ('Brand', 'Brand'),
    ('Recommend', 'Recommend'),
    ('DocumentAI', 'DocumentAI'),
    ('NLP_Summarization', 'NLP_Summarization'),
    ('NLP_QnA', 'NLP_QnA'),
    ('Custom_CV', 'Custom_CV'),
    ('Predictive_Maintenance', 'Predictive_Maintenance'),
    ('Lightstorm_ts', 'Lightstorm_ts'),
    ('Anomaly_PM', 'Anomaly_PM'),
]

DATASET_TYPE = [
    ('CORD-v2', 'CORD-v2'),
    ('DocVQA', 'DocVQA'),
    ('RVL_CDIP', 'RVL_CDIP'),
    ('FUNSD', 'FUNSD'),
    ('CNN-DailyMail', 'CNN-DailyMail'),
    ('ClickHouse', 'ClickHouse'),
    ('External_DataSet', 'External_DataSet'),
    ('Internal_DataSet', 'Internal_DataSet'),
    ('DB_Pull_Dataset', 'DB_Pull_Dataset')
]

REP_TYPE = [
    ('DAILY', 'DAILY'),
    ('HOURLY', 'HOURLY'),
    ('WEEKLY', 'WEEKLY'),
    ('MONTHLY', 'MONTHLY'),
]

REP_Category = [
    ('Inventory', 'Inventory'),
    ('Performance', 'Performance'),

]

REP_COVERAGE = [
    ('Today', 'Today'),
    ('Yesterday', 'Yesterday'),
    ('LastWeek', 'LastWeek'),
    ('Last2Weeks', 'Last2Weeks')
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

NODE_TYPE = [
    ('EXISTING', 'EXISTING'),
    ('CREATE', 'CREATE'),
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
    cluster_type = models.CharField(choices=CLUSTER_TYPE,  default='Secondary', max_length=100)
    cluster_type_varient = models.CharField(choices=CLUSTER_TYPE_VARIENT,  default='Standalone', max_length=100)
    image_store_type = models.CharField(choices=IMAGE_STORE, max_length=100, null=True, blank=True)
    image_store_path = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=500, default="None")
    region = models.CharField(choices=CLUSTER_REGION_TYPE, default='ap-south-1 (Mumbai)', max_length=100)
    environment = models.CharField(choices=CLUSTER_ENVIRONMENT_TYPE,  default='Production', max_length=100)

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


class ModelSchedule(models.Model):
    start_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    time_zone = models.CharField(choices=TIMEZONES, max_length=100, null=True, blank=True)
    periodicity = models.CharField(choices=SCHEDULE_PERIODICITY, max_length=30)

    class Meta:
        abstract = True


class ModelTrainingInfo(models.Model):
    workloadmgr = models.BooleanField(default=False, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        abstract = True


class ModelDatasetInfo(models.Model):
    dataset_type = models.CharField(choices=DATASET_TYPE, max_length=50)
    dataset_config = models.JSONField(default=dict)

    class Meta:
        abstract = True


class ModelInfo(ModelSchedule, ModelDatasetInfo, ModelTrainingInfo):
    model_idx = models.AutoField(primary_key=True)
    model_id = models.CharField(max_length=30, null=True, blank=True)
    model_name = models.CharField(max_length=50, null=True, blank=True, default="")
    created_date = models.DateField(null=True, blank=True)
    status = models.CharField(choices=MODEL_STATUS, default='Scheduled', max_length=20, null=True, blank=True)

    def __str__(self):
        return f"model_idx:{self.model_idx}"


class AlgoMetrics(models.Model):
    performance_config = models.JSONField(default=dict)

    class Meta:
        abstract = True


class AlgoInfo(AlgoMetrics):
    algo_idx = models.AutoField(primary_key=True)
    algo_id = models.CharField(max_length=15, null=True, blank=True)
    algo_category = models.CharField(choices=MODEL_ALGO_CATEGORY, max_length=100, null=True, blank=True)
    algo_type = models.CharField(choices=MODEL_ALGO_TYPE, max_length=50, null=True, blank=True)
    preprocess_type = models.CharField(choices=MODEL_PREPROCESS, max_length=50, null=True, blank=True)
    algo_config = models.JSONField(default=dict, null=True, blank=True)
    algo_status = models.CharField(choices=MODEL_ALGO_STATUS, max_length=50, null=True, blank=True, default="Created")
    algo_time = models.IntegerField(null=True, blank=True, default=0)
    algo_error = models.CharField(max_length=100, null=True, blank=True, default="")
    Model = models.ForeignKey(ModelInfo, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"algo_idx:{self.algo_idx}"


class ModelInfer(models.Model):
    model_infer_idx = models.AutoField(primary_key=True)
    model_infer_id = models.CharField(max_length=30, null=True, blank=True)
    model_infer_name = models.CharField(max_length=50, null=True, blank=True)
    infer_config = models.JSONField(default=dict, null=True, blank=True)
    Model = models.ForeignKey(ModelInfo, on_delete=models.CASCADE, null=True, blank=True)
    created_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"model_infer_idx:{self.model_infer_idx}"


class AlgoInfer(models.Model):
    algo_infer_idx = models.AutoField(primary_key=True)
    algo_infer_id = models.CharField(max_length=15, null=True, blank=True)
    Algo = models.ForeignKey(AlgoInfo, on_delete=models.CASCADE, null=True, blank=True)
    algo_weight = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, validators=[
        MinValueValidator(Decimal('0.00')),MaxValueValidator(Decimal('1.00'))])
    ModelInfer = models.ForeignKey(ModelInfer, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"algo_infer_idx:{self.algo_infer_idx}"


class ModelCompare(models.Model):
    model_compare_idx = models.AutoField(primary_key=True)
    model_compare_id = models.CharField(max_length=30, null=True, blank=True)
    model_compare_name = models.CharField(max_length=30, null=True, blank=True)
    created_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"model_compare_idx:{self.model_compare_idx}"


class ModelCompareRow(models.Model):
    model_compare_r_idx = models.AutoField(primary_key=True)
    Algo = models.ForeignKey(AlgoInfo, on_delete=models.CASCADE, null=True, blank=True)
    ModelCompare = models.ForeignKey(ModelCompare, on_delete=models.CASCADE, null=True, blank=True)
    base_flag = models.BooleanField(null=True, blank=True)

    def __str__(self):
        return f"model_compare_r_idx:{self.model_compare_r_idx}"


class InferenceResource(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    inference_r_idx = models.AutoField(primary_key=True)
    inference_r_id = models.CharField(max_length=15, null=True, blank=True)
    num_cpu = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(64)])
    num_gpu = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(64)])
    Application = models.ForeignKey(ApplicationInfo, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"inference_r_idx:{self.inference_r_idx}"


class ResourceRow(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    resource_r_idx = models.AutoField(primary_key=True)
    resource_r_id = models.CharField(max_length=15, null=True, blank=True)
    num_cpu = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(64)])
    num_gpu = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(64)])
    Model = models.ForeignKey(ModelInfo, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"resource_r_idx:{self.resource_r_idx}"


class DataflowRealtimeConfig(models.Model):
    dataflow_id = models.AutoField(primary_key=True)
    dataflow_name = models.CharField(max_length=100)
    service_name = models.CharField(max_length=50)
    dataflow_type = models.CharField(max_length=50)
    service_port = models.IntegerField()

    def __str__(self):
        return f"dataflow name :{self.dataflow_name}"


class DataflowBatchConfig(models.Model):
    dataflow_idx = models.AutoField(primary_key=True)
    dataflow_id = models.CharField(max_length=100)
    dataflow_name = models.CharField(max_length=100)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    dataflow_type = models.CharField(max_length=50)
    ingestion = models.CharField(choices=INGESTION, default='BackEnd', max_length=30)
    conn_type = models.CharField(choices=SOURCE, max_length=20, default='FTP')
    conn_info = models.JSONField(default=dict)
    dataflows = models.JSONField(default=dict)
    start_date = models.DateField()
    start_time = models.TimeField()
    time_zone = models.CharField(choices=TIMEZONES, max_length=100, default='Asia/Kolkata')
    periodicity = models.CharField(choices=SCHEDULE_PERIODICITY, max_length=30, default='DAILY')
    dataflow_status = models.CharField(choices=ADMIN_STATUS, default='Enable', max_length=20)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"dataflow_id:{self.dataflow_id}"


class DataflowStreamConfig(models.Model):
    dataflow_idx = models.AutoField(primary_key=True)
    dataflow_id = models.CharField(max_length=100)
    dataflow_name = models.CharField(max_length=100)
    # The NOC control-plane stream is owned by the shared NiFi/Kafka runtime
    # rather than an optional cPlatform service deployment.  Keep the legacy
    # service-backed streams intact while allowing this explicit demo contract
    # to be registered without inventing a fake service row.
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    dataflow_type = models.CharField(max_length=50)
    ingestion = models.CharField(choices=INGESTION, default='BackEnd', max_length=30)
    conn_type = models.CharField(choices=SOURCE, max_length=20, default='Fin_Data')
    conn_info = models.JSONField(default=dict)
    dataflow_status = models.CharField(choices=ADMIN_STATUS, default='Enable', max_length=20)
    create_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    time_zone = models.CharField(choices=TIMEZONES, max_length=100, default='Asia/Kolkata')
    periodicity = models.CharField(choices=SCHEDULE_PERIODICITY, max_length=30, default='DAILY')
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"dataflow_id:{self.dataflow_id}"


class DataFlowLogs(models.Model):
    log_id = models.AutoField(primary_key=True)
    dataflow_id = models.CharField(max_length=100)
    status = models.CharField(choices=DATAFLOW_STATUS, max_length=20)
    dataflow_date = models.DateField()
    dataflow_time = models.TimeField()
    log_info = models.JSONField(default=dict)
    msg = models.CharField(max_length=100, null=True, blank=True)
    report_path = models.TextField(null=True, blank=True)
    def __str__(self):
        return f"log_id:{self.log_id}"


class UserInfo(models.Model):
    user_idx = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=8)
    user_email = models.EmailField(max_length=200)
    user_name = models.CharField(max_length=100, null=True, blank=True)
    user_role = models.CharField(choices=ROLE, max_length=50)
    user_number = models.CharField(max_length=15,null=True, blank=True)
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


class ReportInfo(models.Model):
    report_name = models.CharField(primary_key=True, max_length=100)
    create_date = models.DateField(blank=True)
    start_date = models.DateField(blank=True)
    start_time = models.TimeField(blank=True)
    time_zone = models.CharField(choices=TIMEZONES, max_length=100)
    periodicity = models.CharField(choices=REP_TYPE, max_length=20)
    report_method = models.CharField(choices=REPORT_METHOD, max_length=20, null=True)
    email_list = models.CharField(max_length=500)
    reports = models.JSONField(default=dict)
    status = models.CharField(choices=ADMIN_STATUS, default='Enable', max_length=20, null=True, blank=True)
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE, null=True, blank=True)
    service_name = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"report_name:{self.report_name}"


class ReportLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    log_date = models.DateField(null=True, blank=True)
    log_time = models.TimeField(null=True, blank=True)
    log_time_zone = models.CharField(choices=TIMEZONES, max_length=100)
    msg = models.CharField(max_length=100, null=True, blank=True)
    file_name = models.CharField(max_length=500, null=True, blank=True)
    email_list = models.CharField(max_length=500, null=True, blank=True)
    report = models.ForeignKey(ReportInfo, on_delete=models.CASCADE)

    def __str__(self):
        return f"reportLog_idx:{self.log_id}"


DB_PULL_JOB_STATUS = [
    ('PENDING',   'PENDING'),
    ('RUNNING',   'RUNNING'),
    ('COMPLETED', 'COMPLETED'),
    ('FAILED',    'FAILED'),
]

DB_PULL_LOG_TYPE = [
    ('INFO',    'INFO'),
    ('WARNING', 'WARNING'),
    ('ERROR',   'ERROR'),
    ('SUMMARY', 'SUMMARY'),
]

DB_PULL_JOB_BASE_IDX = 5000


class DBPullInferenceJob(models.Model):
    """Tracks one DB-pull inference run end-to-end."""
    job_idx          = models.AutoField(primary_key=True)
    job_id           = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    Model            = models.ForeignKey(ModelInfo, on_delete=models.SET_NULL, null=True, blank=True)
    model_infer_name = models.CharField(max_length=50, null=True, blank=True)   # which ModelInfer config to use
    profile_column   = models.JSONField(default=dict)
    profile_key      = models.CharField(max_length=100, null=True, blank=True)  # e.g. "W24-2026"
    source_type      = models.CharField(max_length=20, default='db_pull')
    local_file_path  = models.CharField(max_length=500, null=True, blank=True)
    eval_file_path   = models.CharField(max_length=500, null=True, blank=True)
    threshold        = models.FloatField(null=True, blank=True)
    source_config    = models.JSONField(default=dict)   # ClickHouse source: host, port, db, table, user, pw
    dest_config      = models.JSONField(default=dict)   # ClickHouse dest:   host, port, db, table, user, pw
    chunk_size       = models.IntegerField(default=10000)
    status           = models.CharField(choices=DB_PULL_JOB_STATUS, max_length=20, default='PENDING')
    triggered_by     = models.CharField(max_length=100, null=True, blank=True)
    triggered_at     = models.DateTimeField(auto_now_add=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    total_records    = models.BigIntegerField(default=0)
    processed_records = models.BigIntegerField(default=0)
    error_msg        = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"job:{self.job_id}"


class DBPullInferenceLog(models.Model):
    """Per-event log lines for a DBPullInferenceJob."""
    log_idx           = models.AutoField(primary_key=True)
    Job               = models.ForeignKey(DBPullInferenceJob, on_delete=models.CASCADE,
                                          null=True, blank=True, related_name='logs')
    log_type          = models.CharField(choices=DB_PULL_LOG_TYPE, max_length=20, default='INFO')
    message           = models.TextField(null=True, blank=True)
    records_processed = models.BigIntegerField(default=0)
    inference_summary = models.JSONField(default=dict, null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"log:{self.log_idx}"


class InviteToken(models.Model):
    token       = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user_name   = models.CharField(max_length=255, null=True, blank=True)
    user_email  = models.EmailField(max_length=255, null=True, blank=True)
    user_role   = models.CharField(max_length=50, null=True, blank=True)
    user_number = models.CharField(max_length=20, null=True, blank=True)
    permissions = models.JSONField(default=list, null=True, blank=True)
    invited_by  = models.CharField(max_length=255, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_used     = models.BooleanField(default=False)
    is_revoked  = models.BooleanField(default=False)

    def __str__(self):
        return f"invite_{self.user_email}_{self.token}"

