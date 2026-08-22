''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : LOCALMgr.py
* Description       : Local File Manager
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 19-Dec-24 		Sandeep Mahajan		            Created.
*********************************************************************************************************************'''

import os
import shutil
from CommonUtils.logs.AppLogging import utils_logger


def _local_get_file_list(remote_path):

    try:
        file_list = os.listdir(remote_path)  # Get list of files in target folder
        return file_list
    except Exception as e:
        print(f"Error getting file list for remote path {remote_path}: {e}")
        return None


def _local_file_download(local_file_path, remote_file_path):

    shutil.copy(local_file_path, remote_file_path)

    return True


def cutil_local_download(remote_path, filename, tmp_dir):

    utils_logger.debug(
        f"cutil_local_download called with remote_path: {remote_path}, filename: {filename}, tmp_dir: {tmp_dir}")

    # Validate tmp and remote directory
    if not os.path.isdir(tmp_dir) or not os.path.isdir(remote_path):
        utils_logger.debug("Download Failure, Invalid Local or Remote Directory!")
        return False, []

    # Get List of files from given bucket name and remote path
    file_list = _local_get_file_list(remote_path)

    if not file_list:
        utils_logger.debug("Download Failure, Unable get file list from server!")
        return False, []

    if filename == '*':
        matching_files = [file for file in file_list]
    else:
        matching_files = [file for file in file_list if file.startswith(f"{filename.split('.')[0]}")]

    if not matching_files:
        utils_logger.debug("Download Failure, No matching files found !")
        return False, []

    for remote_filename in matching_files:
        if not _local_file_download(os.path.join(remote_path, remote_filename), os.path.join(tmp_dir, remote_filename)):
            utils_logger.debug(f"Download Failure, File:{remote_filename} could not be downloaded!")
            return False, []

    utils_logger.debug(f"Local Download Success, file_list:{matching_files} !")
    return True, matching_files
