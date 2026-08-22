import os
from CommonUtils.logs import LogMgr
from CommonUtils.CutilSetting import CutilSettings 

util_log_dir = CutilSettings.log_path
# Append 'log' to the base path
util_log_dir = os.path.join(util_log_dir, 'logs')

# Create the directory if it doesn't exist
os.makedirs(util_log_dir, exist_ok=True)

utils_logger = LogMgr.commonutils_logger_init('CplatformUtilsLogger', util_log_dir, 20, 2)


def cutil_log_init(log_path):
    """
    Setting up log initialization.
    Args:
        log_path (str): Log Directory 
                
     Returns:
        tuple: (bool, MIMEMultipart or str) – success status and message or error string.
    """

    if not all(isinstance(val, str) for val in [log_path]):
        return False,"Invalid configuration: log_base_path must be string."
    CutilSettings.log_path = log_path
    
    return True ,"Initialization Complete"
    

