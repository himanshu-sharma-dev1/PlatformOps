import os
from MCPClient.mcpSetting import mcpSettings
from CommonUtils.logs import LogMgr

util_log_dir = mcpSettings.log_path
# Append 'log' to the base path
util_log_dir = os.path.join(util_log_dir, 'logs')

# Create the directory if it doesn't exist
os.makedirs(util_log_dir, exist_ok=True)

mcpcl_logger = LogMgr.commonutils_logger_init('MCPClientLogger', util_log_dir, 20, 2)

mcpcl_logger.propagate = False

# import loggingw
# from MCPClient.mcpSetting import mcpSettings
# log_file_name = mcpSettings.log_file_name or 'airtelChurn_server'
# mcpcl_logger = logging.getLogger(log_file_name)