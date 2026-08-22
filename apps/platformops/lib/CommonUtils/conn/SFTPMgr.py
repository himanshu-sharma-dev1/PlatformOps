''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : FTPMgr.py
* Description       : SFTP Manager Module
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
* 26-Sept-24        Sumit Das               updated.
*********************************************************************************************************************'''

import os
import stat
import paramiko
from CommonUtils.logs.AppLogging import utils_logger


def _sftp_connect(server_url, username, password):
    utils_logger.debug(f"_sftp_connect, server_url, username, password: {server_url, username, password}")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_url, username=username, password=password, port=22)
        sftp = ssh.open_sftp()
        sftp._ssh_client = ssh
        utils_logger.debug(f"SFTP Connection Successful !")
        return sftp
    except Exception as e:
        utils_logger.debug(f"Failed to connect to SFTP server: Error Code:{e}")
        return None


def _sftp_get_file_list(sftp, remote_path):
    utils_logger.debug(f"_sftp_get_file_list, remote_path: {remote_path}")

    try:
        sftp.chdir(remote_path) # Change remote directory

        file_list = sftp.listdir()  # Get list of files in target folder
        actual_list = [file for file in file_list if file not in ['.', '..']]  # Filter out actual files
        utils_logger.debug(f"_sftp_get_file_list: {actual_list}")
        return actual_list
    except Exception as e:
        utils_logger.debug(f"Error getting file list for remote path {remote_path}: {e}")
        return None


def _sftp_file_download(sftp, remote_filename, local_file_path):
    utils_logger.debug(f"_sftp_file_download, remote_filename, local_file_path: {remote_filename, local_file_path}")

    try:
        sftp.get(remote_filename, local_file_path)
        utils_logger.debug(f"File :{remote_filename} downloaded to {local_file_path} !")
        return True
    except Exception as e:
        utils_logger.debug(f"Error downloading {remote_filename}: SFTP Error:{e}")
        return False


def cutil_sftp_download(server_url, username, password, remote_path, filename, tmp_dir):
    utils_logger.debug(f"cutil_sftp_download, server_url, username, password, remote_path, filename, tmp_dir: "
                       f"{server_url, username, password, remote_path, filename, tmp_dir}")
    if '.' in filename:
        filename = filename.split('.')[0]
    # Validate tmp directory
    if not os.path.isdir(tmp_dir):
        utils_logger.debug("Download Failure, Invalid Local Directory!")
        return False, []

    # Connect to SFTP Server
    sftp = _sftp_connect(server_url, username, password)
    if not sftp:
        utils_logger.debug("Download Failure, Unable to connect to SFTP server!")
        return False, []
    
    if filename != '*':
        # Get File list in remote path at SFTP Server
        file_list = _sftp_get_file_list(sftp, remote_path)
        if not file_list:
            utils_logger.debug("Download Failure, Unable get file list from server!")
            return False, []

        # Filter file list matching criteria
        matching_files = [file for file in file_list if file.startswith(filename)]
        if not matching_files:
            utils_logger.debug("Download Failure, No matching files found !")
            return False, []
    
    else:
        # Filter out actual files
        matching_files = _sftp_get_file_list(sftp, remote_path)
        if not matching_files:
            utils_logger.debug("Download Failure, Unable get file list from server!")
            return False, []

    # Download matching files
    for remote_filename in matching_files:
        if not _sftp_file_download(sftp, remote_filename, os.path.join(tmp_dir, remote_filename)):
            utils_logger.debug(f"Download Failure, File:{remote_filename} could not be downloaded!")
            return False, []

    sftp.close()
    utils_logger.debug(f"Download Successful, file_list:{matching_files} !")
    return True, matching_files


def cutil_sftp_sync(machine_config, final_remote_folder, final_local_folder):
    utils_logger.debug(f"cutil_sftp_model_download, machine_config, remote_path, filename, tmp_dir: "
                       f"{machine_config, final_remote_folder, final_local_folder}")

    # Connect to SFTP Server
    sftp = _sftp_sync_connect(machine_config)
    if not sftp:
        utils_logger.debug("Download Failure, Unable to connect to SFTP server!")
        return False, []

    if not _sftp_folder_download(sftp, final_remote_folder, final_local_folder):
        utils_logger.debug(f"Download Failure, File could not be downloaded!")
        return False, []

    sftp.close()
    utils_logger.debug(f"Download Successful!")
    return True


def _sftp_folder_download(sftp, remote_dir, local_dir):

    os.makedirs(local_dir, exist_ok=True)

    for entry in sftp.listdir_attr(remote_dir):
        remote_path = os.path.join(remote_dir, entry.filename).replace("\\", "/")
        local_path = os.path.join(local_dir, entry.filename)

        if stat.S_ISDIR(entry.st_mode):
            _sftp_folder_download(sftp, remote_path, local_path)
        else:
            sftp.get(remote_path, local_path)


def _sftp_sync_connect(machine_config):
    utils_logger.debug(f"_sftp_connect called with server_url={machine_config['host']}, username={machine_config['username']}")

    password = None if machine_config.get('password', '') == '' else machine_config['password']
    pem_file_path = None if machine_config.get('pem_file_path', '') == '' else machine_config['pem_file_path']
    port = machine_config.get('port', 22)

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if pem_file_path and os.path.exists(pem_file_path):
            ssh.connect(machine_config['host'], username=machine_config['username'], key_filename=pem_file_path, port=port)
            utils_logger.debug("SFTP Connection Successful using PEM file authentication!")
        elif password:
            ssh.connect(machine_config['host'], username=machine_config['username'], password=password, port=port)
            utils_logger.debug("SFTP Connection Successful using password authentication!")
        else:
            utils_logger.debug("No valid authentication method provided.")
            return None
        
        sftp = ssh.open_sftp()
        sftp._ssh_client = ssh
        return sftp
    except Exception as e:
        utils_logger.debug(f"Failed to connect to SFTP server: {e}", exc_info=True)
        print(f"Exception during SFTP connection: {e}")
        return None


