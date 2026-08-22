import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
app_log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(app_log_dir, exist_ok=True)

from CommonUtils.logs import LogMgr
app_logger = LogMgr.commonutils_logger_init('cplatform_server', app_log_dir, 20, 2)
celery_logger = LogMgr.commonutils_celery_logger_init('cplatform_celery', app_log_dir, 20, 2)

