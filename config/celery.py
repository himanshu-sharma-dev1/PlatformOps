from __future__ import absolute_import
import os
import sys
import yaml
from celery import Celery
from pathlib import Path
from dotenv import load_dotenv
from cPlatformIO.src.PlatformSetting import PlatformSettings
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
temp_path = os.path.join(BASE_DIR,'config')
NEW_BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(NEW_BASE_DIR))

ENV_FILE = os.environ.get('DJANGO_ENV_FILE', f'{NEW_BASE_DIR}/platform/docker/cPlatform/local.env')
load_dotenv(ENV_FILE)

config_file = (temp_path + '/cPlatform_config.yaml')
with open(config_file) as fh:
    setting_config=(yaml.load(fh, Loader=yaml.FullLoader))

# from kombu import Consumer, Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cPlatform.settings')
app = Celery(PlatformSettings.celery_app, broker=PlatformSettings.celery_broker, backend='rpc://', broker_heartbeat=0)
# app = Celery('cPlatform', broker='amqp://admin:admin@180.75.0.2:5672//', backend='rpc://', broker_heartbeat=0)

# Optional configuration, see the application user guide.
app.conf.update(result_expires=3600, )
CELERY_ACKS_LATE = True
CELERYD_PREFETCH_MULTIPLIER = 1
task_acks_late = True
app.autodiscover_tasks()

if __name__ == '__main__':
    app.start()
