''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : LogMgr.py
* Description       : Common Utility Module supporting Logging Functions
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
*
*********************************************************************************************************************'''

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from celery.utils.log import get_task_logger

log_formatter = ('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

def commonutils_logger_init(logger_name, log_path, log_size, backup_count):

    # Create new logger using logger name
    c_logger = logging.getLogger(logger_name)
    c_logger.setLevel(logging.DEBUG)

    # Create formatter for logging information
    c_formatter = logging.Formatter(log_formatter, datefmt='%d-%m-%y,%I:%M:%S%p')

    # Create file handler for debug messages
    debug_fh = RotatingFileHandler(log_path + '/' + logger_name + '_Debug.log', maxBytes=log_size * 1024 * 1024,
                                   backupCount=backup_count)
    debug_fh.setLevel(logging.DEBUG)
    debug_fh.setFormatter(c_formatter)
    c_logger.addHandler(debug_fh)

    # Create file handler for Info messages
    info_fh = RotatingFileHandler(log_path + '/' + logger_name + '_Info.log', maxBytes=log_size * 1024 * 1024,
                                  backupCount=backup_count)
    info_fh.setLevel(logging.INFO)
    info_fh.setFormatter(c_formatter)
    c_logger.addHandler(info_fh)

    # Create file handler for Error messages
    error_fh = RotatingFileHandler(log_path + '/' + logger_name + '_Error.log', maxBytes=log_size * 1024 * 1024,
                                  backupCount=backup_count)
    error_fh.setLevel(logging.ERROR)
    error_fh.setFormatter(c_formatter)
    c_logger.addHandler(error_fh)
    return c_logger


def commonutils_logger_list(logger_name):
    c_logger = logging.getLogger(logger_name)
    print(c_logger)
    for c_handler in c_logger.handlers:
        print(f"'Logger={c_logger}, handler = {c_handler}")
    return


def commonutils_celery_logger_init(logger_name, log_path, log_size, backup_count):

    # Create formatter for logging information
    c_formatter = logging.Formatter(log_formatter, datefmt='%d-%m-%y,%I:%M:%S%p')

    # create a logger for the Celery tasks
    celery_logger = get_task_logger(__name__)
    celery_logger.setLevel(logging.DEBUG)

    # create a file handler for the Celery tasks
    celery_fh = RotatingFileHandler(log_path + '/' + logger_name + '_Debug.log', maxBytes=log_size * 1024 * 1024,
                                    backupCount=backup_count)
    celery_fh.setLevel(logging.DEBUG)
    celery_fh.setFormatter(c_formatter)
    celery_logger.addHandler(celery_fh)
    return celery_logger


def commonutils_update_logger_level(logger_name,level):
    logger = logging.getLogger(logger_name)
    logger_level = logging.ERROR
    if level == 'DEBUG':
        logger_level = logging.DEBUG
    elif level == 'INFO':
        logger_level = logging.INFO
    logger.setLevel(logger_level)

    return


class Tee:

    def __init__(self, *streams):
        self.streams = streams
        self.encoding = getattr(streams[0], "encoding", "utf-8")

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return False

    def fileno(self):
        return self.streams[0].fileno()

    def __getattr__(self, name):
        return getattr(self.streams[0], name)


def commonutils_training_logger_init(algo_type, log_path):

    logger_name = f"{algo_type}_training"
    logger = logging.getLogger(logger_name)

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(log_formatter, datefmt='%d-%m-%y,%I:%M:%S%p')
    log_file = os.path.join(log_path, f"{algo_type}_training.log")

    fh = RotatingFileHandler(log_file, maxBytes=20 * 1024 * 1024, backupCount=2)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Save original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Open log file for stdout/stderr capture
    log_stream = open(log_file, "a", buffering=1)

    # Capture print() and library output
    sys.stdout = Tee(original_stdout, log_stream)
    sys.stderr = Tee(original_stderr, log_stream)

    training_context = {"logger": logger, "log_file": log_file, "stdout": original_stdout, "stderr": original_stderr,
                        "stream": log_stream}

    return training_context


def commonutils_training_logger_cleanup(training_context):

    try:

        sys.stdout = training_context["stdout"]
        sys.stderr = training_context["stderr"]
        training_context["stream"].close()

    except Exception:
        pass


'''
import sys
from pathlib import Path
import os
from logging import StreamHandler

BASE_DIR = Path(__file__).resolve().parent.parent
app_log_dir = os.path.join(BASE_DIR.parent, 'logs')

# create server logger
logger = logging.getLogger('server_logger')
logger.setLevel(logging.DEBUG)

# create file handler for server logger which logs even debug messages
fh = RotatingFileHandler(app_log_dir + '/serverDebug.log', maxBytes=5*1024*1024, backupCount=2)
fh.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = RotatingFileHandler(app_log_dir + '/serverInfo.log', maxBytes=5*1024*1024, backupCount=2)
ch.setLevel(logging.INFO)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(message)s', datefmt='%d-%m-%y,%I:%M:%S%p')
# sh.setFormatter(formatter)
ch.setFormatter(formatter)
fh.setFormatter(formatter)

# add the handlers to the server logger
logger.addHandler(ch)
logger.addHandler(fh)

# create a logger for the Celery tasks
celery_logger = get_task_logger(__name__)
celery_logger.setLevel(logging.DEBUG)

# create a file handler for the Celery tasks
celery_fh = RotatingFileHandler(app_log_dir + '/celery.log', maxBytes=5*1024*1024, backupCount=2)
celery_fh.setLevel(logging.DEBUG)

# add the file handler to the Celery logger
celery_logger.addHandler(celery_fh)
celery_fh.setFormatter(formatter)

# create a logger for Algorithms
algo_logger = logging.getLogger('app_logger')
algo_logger.setLevel(logging.DEBUG)

# create file handler for server logger which logs even debug messages
algo_fh = RotatingFileHandler(app_log_dir + '/algoDebug.log', maxBytes=5*1024*1024, backupCount=2)
algo_fh.setLevel(logging.DEBUG)

# create console handler with a higher log level
algo_ch = RotatingFileHandler(app_log_dir + '/algoInfo.log', maxBytes=5*1024*1024, backupCount=2)
algo_ch.setLevel(logging.INFO)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(message)s', datefmt='%d-%m-%y,%I:%M:%S%p')
# sh.setFormatter(formatter)
algo_ch.setFormatter(formatter)
algo_fh.setFormatter(formatter)

# add the handlers to the server logger
algo_logger.addHandler(algo_ch)
algo_logger.addHandler(algo_fh)
'''
