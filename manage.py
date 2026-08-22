#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

import os
import warnings
import logging

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

warnings.filterwarnings("ignore", module="nemoguardrails")
warnings.filterwarnings("ignore", module="paramiko")
warnings.filterwarnings("ignore", module="jsonmerge")
warnings.filterwarnings("ignore", module="pydantic")

logging.getLogger("absl").setLevel(logging.ERROR)

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cPlatform.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
