''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : FTPMgr.py
* Description       : FTP Manager Module
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
* 26-Sept-24        Sumit Das               updated.
*********************************************************************************************************************'''
import os
import ftplib
from CommonUtils.logs.AppLogging import utils_logger


def _ftp_connect(server_url, username, password):
    utils_logger.debug(f"_ftp_connect, server_url, username, password: {server_url, username, password}")

    try:
        ftp = ftplib.FTP(server_url)
        ftp.login(user=username, passwd=password)
        # ftp.set_pasv(False)  # Disable passive mode if needed
        utils_logger.debug(f"FTP Connection Successful !")
        return ftp
    except ftplib.all_errors as e:
        utils_logger.debug(f"FTP Connection Failed, Error: {e}")
        return None


def _ftp_get_file_list(ftp, remote_path):
    utils_logger.debug(f"_ftp_get_file_list, remote_path: {remote_path}")

    try:
        ftp.cwd(remote_path) # Change remote directory
        file_list = ftp.nlst() # Get list of files in target folder
        actual_list = [file for file in file_list if file not in ['.', '..']] # Filter out actual files
        utils_logger.debug(f"_ftp_get_file_list: {actual_list}")
        return actual_list
    except Exception as e:
        utils_logger.debug(f"Error getting file list for remote path {remote_path}: {e}")
        return None


def _ftp_file_download(ftp, remote_filename, local_file_path):
    utils_logger.debug(f"_ftp_file_download, remote_filename, local_file_path: {remote_filename, local_file_path}")

    try:
        with open(local_file_path, "wb") as file:
            ftp.retrbinary(f"RETR {remote_filename}", file.write)

        utils_logger.debug(f"File:{remote_filename} downloaded to {local_file_path} !")
        return True
    except ftplib.error_perm as e:
        utils_logger.debug(f"Failed to download {remote_filename}, ftp error: {e}")
        return False


def cutil_ftp_download(server_url, username, password, remote_path, filename, tmp_dir):
    utils_logger.debug(f"cutil_ftp_download, server_url, username, password, remote_path, filename, tmp_dir ="
                       f"{server_url, username, password, remote_path, filename, tmp_dir}")
    if '.' in filename:
        filename = filename.split('.')[0]
    # Validate tmp directory
    if not os.path.isdir(tmp_dir):
        utils_logger.debug("Download Failure, Invalid Local Directory!")
        return False, []

    # Connect to FTP Server
    ftp = _ftp_connect(server_url, username, password)
    if not ftp:
        utils_logger.debug("Download Failure, Unable to connect to FTP server!")
        return False, []
    
    # check the filename
    if filename != '*':
        # Get File list in remote path at FTP Server
        file_list = _ftp_get_file_list(ftp, remote_path)
        if not file_list:
            utils_logger.debug("Download Failure, Unable get file list from server!")
            return False, []
    
        # Filter file list matching criteria
        matching_files = [file for file in file_list if file.startswith(filename) ]
        if not matching_files:
            utils_logger.debug("Download Failure, No matching files found !")
            return False, []
    
    else:
        # If filename is * download all the files 
        matching_files = _ftp_get_file_list(ftp, remote_path)
        if not matching_files:
            utils_logger.debug("Download Failure, Unable get file list from server!")
            return False, []

    # Download matching files
    for remote_filename in matching_files:
        if not _ftp_file_download(ftp, remote_filename, os.path.join(tmp_dir, remote_filename)):
            utils_logger.debug(f"Download Failure, File:{remote_filename} could not be downloaded!")
            return False, []

    ftp.close()
    utils_logger.debug(f"Download Successful, file_list:{matching_files} !")
    return True, matching_files


#
#
# def ftphandler_upload(server_url, username, password, remote_path, filename, local_dir):
#     try:
#         ftp = ftplib.FTP(server_url, username, password)
#         ftp.cwd(remote_path)
#         local_dir = local_dir + "/"
#         file_exists = os.path.exists(f'{local_dir}{filename}')
#         utils_logger.debug(f" file_exists, ={file_exists}")
#
#         if file_exists is True:
#             with open(f"{local_dir}" + filename, "rb") as file:
#                 ftp.storbinary(f"STOR {filename}", file)
#                 utils_logger.debug(f" Upload Compplete...")
#             ftp.quit()
#             return True, filename, local_dir
#         else:
#             utils_logger.debug(f"File not found.  Filename or  path may be not correct. ")
#             return False, filename, local_dir
#
#     except ftplib.all_errors as e:
#         errorcode_string = str(e).split(None, 1)[0]
#         utils_logger.debug(f"errorcode_string{errorcode_string}")
#         utils_logger.debug(f"Bad Credentials")
#         return False, filename, local_dir