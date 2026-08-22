''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : ConnectionMgr.py
* Description       : Connection Manager
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 14-Oct-24 		Vidushi Gandhi		            Created.
* 20-Oct-24 		Sumit Das		                Updated.
*********************************************************************************************************************'''
# Import System Modules
import re
import os
import shutil
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from CommonUtils.repository import RepoMgmt
from CommonUtils.conn import FTPMgr, S3Mgr, SFTPMgr, LOCALMgr,WebScrapyMgr, GDriveMgr
from CommonUtils.logs.AppLogging import utils_logger
from pathlib import Path
import yaml
# -----------------------------------------------Transform Filename function -------------------------------------------

def cutil_conn_eval_regex(filename, eval_date):
    # Define the pattern to find placeholders in the filename
    pattern = r'<(.*?)>'
    matches = re.findall(pattern, filename)

    if not matches:
        return filename

    # Dictionaries to store formats
    formats = {'Date': '%d', 'Month': '%B', 'month': '%m', 'Year': '%Y', 'year': '%y', 'monthval': '%b'}

    # Process 'Date' placeholder first
    for match in matches:
        if match.startswith('Date'):
            parts = match.split('-')
            value_to_subtract = int(parts[1]) if len(parts) > 1 else 0
            result_date = eval_date - timedelta(days=value_to_subtract)
            formatted_date = result_date.strftime(formats['Date'])
            filename = filename.replace(f'<{match}>', formatted_date)
            break  # Only one 'Date' placeholder expected

    # Process other placeholders using the result_date
    for match in matches:
        if match.startswith('Date') or match == '*':
            filename = filename.replace(f'<{match}>', '')  # Remove '*' placeholder
            continue  # Skip already processed 'Date' or remove '*'

        parts = match.split('-')
        key = parts[0]
        value_to_subtract = int(parts[1]) if len(parts) > 1 else 0

        # Use result_date for month and year calculations
        if key in ['Month', 'month', 'monthval']:
            calc_date = eval_date - relativedelta(months=value_to_subtract)
        elif key in ['Year', 'year']:
            calc_date = eval_date - relativedelta(years=value_to_subtract)
        else:
            # Unknown placeholder
            continue

        # Format the date accordingly
        formatted_date = calc_date.strftime(formats[key])
        filename = filename.replace(f'<{match}>', formatted_date)

    # Clean up filename
    if filename.endswith('.csv'):
        updated_filename = filename[:-4]  # Remove '.csv'
    elif filename.endswith('.xlsx'):
        updated_filename = filename[:-5]  # Remove '.xlsx'
    else:
        updated_filename = filename

    # Remove trailing '_AM' or '_PM' if present
    if filename.endswith('_AM') or filename.endswith('_PM'):
        filename = updated_filename[:-3]

    return filename


def _exec_date_regex(filename, eval_date):
    utils_logger.debug(f" _exec_date_regex, filename, eval_date={filename, eval_date} ")

    date_formats = {'Date': '%d', 'Day': '%d', 'Month': '%B', 'month': '%m', 'Year': '%Y', 'year': '%y', 'monthval': '%b'}

    # Define the pattern to find placeholders in the filename
    matches = re.findall(r'<(.*?)>', filename)

    # Process 'Date' placeholder first
    for match in matches:
        if not match.startswith(tuple(date_formats.keys())):
            filename = filename.replace(f'<{match}>', '')  # Remove all unaccepted keys
            continue

        parts = match.split('-')
        key = parts[0]
        value_to_subtract = int(parts[1]) if len(parts) > 1 else 0

        calc_date = eval_date
        if key in ['Day', 'Date']:
            calc_date = eval_date - relativedelta(days=value_to_subtract)
        elif key in ['Month', 'month', 'monthval']:
            calc_date = eval_date - relativedelta(months=value_to_subtract)
        elif key in ['Year', 'year']:
            calc_date = eval_date - relativedelta(years=value_to_subtract)

        filename = filename.replace(f'<{match}>', calc_date.strftime(date_formats[key]))

    utils_logger.debug(f" _exec_date_regex, new_filename:{filename} ")
    return filename


def _validate_conn_info(conn_type, conn_info):

    utils_logger.debug(f" _validate_conn_info, conn_type, conn_info={conn_type, conn_info} ")

    if conn_type not in ['FTP', 'SFTP', 'S3', 'LOCAL','WEB_SCRAP','Google_Drive']:
        utils_logger.debug(f" Invalid Connection Type ! ")
        return False

    ret = True
    if conn_type in ["FTP", "SFTP"]:
        url, login, password = conn_info.get('url', None), conn_info.get('user_name', None), conn_info.get('password', None)
        if not url or not login or not password:
            utils_logger.debug(f" Invalid FTP or SFTP Connection Info ! ")
            ret = False
    elif conn_type == "S3":
        bucket_name, aws_access_key_id, aws_secret_access_key = conn_info.get('BucketName', None), \
                        conn_info.get('AwsAccessKeyId', None), conn_info.get('AwsSecretAccessKey', None)
        if not bucket_name or not aws_access_key_id or not aws_secret_access_key:
            utils_logger.debug("Invalid S3 Connection Info!")
            ret = False
    elif conn_type=="WEB_SCRAP":
        # Will do handling according to multiple links
        # url = conn_info.get('URL', None)
        # if not url :
        #     utils_logger.debug(f" Invalid Web scrap Connection Info ! ")
        #     ret = False
        return True
    utils_logger.debug(f" Connection Information is Valid ! ")
    return ret


def _validate_file_list(file_list):

    # Check if file_list is not  empty
    if not file_list:
        return False

    # Check if 'file_name' exists and is non-empty
    for file in file_list:
        if not file.get('file_name', '').strip():
            return False
    return True


def _validate_date(eval_date):
    utils_logger.debug(f" _validate_date, eval_date={eval_date} ")
    if eval_date is not None:
        try:
            if eval_date != datetime.strptime(eval_date, "%Y-%m-%d").strftime('%Y-%m-%d'):
                utils_logger.debug(" validation failure, Incorrect Date format !")
                return None
        except ValueError:
            utils_logger.debug(" validation failure, Incorrect Date format !")
            return None

        return datetime.strptime(eval_date, '%Y-%m-%d')

    return datetime.strptime(datetime.now(), '%Y-%m-%d')

def _get_service_account_config():
    BASE_DIR_PATH = Path(__file__).resolve().parent.parent
    utils_config_path = os.path.join(BASE_DIR_PATH, "UtilsConfig.yaml")
    with open(utils_config_path, 'r') as file:
        yaml_data = yaml.safe_load(file)

    gdrive_config = yaml_data['GDrive_service']
    return gdrive_config


def cutil_conn_download(conn_type, conn_info, file_list, eval_date):
    depth_value = conn_info.get("depth")
    print("the conn_type is:",conn_type)

    # Input field format for the API
    # conn_type is of string with possible values of FTP, SFTP, S3, LOCAL
    # conn_info is of type dictionary with fields. FTP: (url, login, password), SFTP: (url, login, password), LOCAL:()
    #   S3: (bucket_name, aws_access_key_id, aws_secret_access_key)
    # file_list is of type file_list [{remote_path:"", filename:""}...]

    utils_logger.debug(f"cutil_conn_download, conn_type, conn_info, file_list, eval_date ="
                       f"{conn_type, conn_info, file_list, eval_date}")

    # Validate Connection Information
    if not _validate_conn_info(conn_type, conn_info):
        utils_logger.debug(f"API Failure, Invalid Connection Type !")
        return False, "Invalid Connection", None, []

    # # Validate file_list
    if not _validate_file_list(file_list):
        utils_logger.debug(f"API Failure, Invalid file_list!")
        return False, "Invalid file_list", None, []

    # Validate Date
    eval_date = _validate_date(eval_date)
    if eval_date is None:
        utils_logger.debug(f"API Failure, Invalid eval_date !")
        return False, "Invalid eval_date", None, []

    # create local temporary directory
    temp_folder_path = RepoMgmt.repo_get_temp_dir()
    tmp_dir = os.path.join(temp_folder_path, datetime.now().strftime('%d-%b-%H-%M-%S'))
    os.makedirs(tmp_dir, exist_ok=True)

    download_list = []

    # Making the separate condition for WEB_SCRAP Because we are not getting any list of PDF
    # subdir_path_web = os.path.join(tmp_dir,"10523",f"flow0")
    # os.makedirs(subdir_path_web, exist_ok=True)
    # if conn_type == "WEB_SCRAP":
    #     print("WEB_SCRAP_ONE")
    #     ret, msg = WebScrapyMgr.cutil_webScrap_download(conn_info['URL'], subdir_path_web)
    # fetch all download file from that Folder


    print("the conn_type is:",conn_type)
    for idx, file_info in enumerate(file_list):

        # Create Folder at cPlatform Repository if it doesn't exist
        subdir_path = os.path.join(tmp_dir, f"flow{idx}")
        os.makedirs(subdir_path, exist_ok=True)

        regex_filename = _exec_date_regex(file_info['file_name'], eval_date)  # Regex transformation
        
        # Invoke Handler based on Connection Type
        if conn_type == 'FTP':
            ret, matching_files = FTPMgr.cutil_ftp_download(conn_info['url'], conn_info['user_name'],
                                                            conn_info['password'], file_info['remote_path'],
                                                            regex_filename, subdir_path)
        elif conn_type == 'SFTP':
            ret, matching_files = SFTPMgr.cutil_sftp_download(conn_info['url'], conn_info['user_name'],
                                                              conn_info['password'], file_info['remote_path'],
                                                              regex_filename, subdir_path)
        elif conn_type == 'LOCAL':
            ret, matching_files = LOCALMgr.cutil_local_download(file_info['remote_path'], regex_filename, subdir_path)

        elif conn_type == 'S3':
            ret, matching_files = S3Mgr.cutil_s3_download(conn_info["BucketName"], conn_info["AwsAccessKeyId"],
                                                          conn_info["AwsSecretAccessKey"],file_info["remote_path"],
                                                          regex_filename, subdir_path)  

        elif conn_type == "WEB_SCRAP":
            ret, matching_files = WebScrapyMgr.cutil_webScrap_download(file_info['remote_path'], subdir_path,depth_value)

        elif conn_type == 'Google_Drive':
            acc_info = _get_service_account_config()
            ret, matching_files = GDriveMgr.cutil_gdrive_download(conn_info["DriveLink"], acc_info,file_info["remote_path"], regex_filename, subdir_path)  
        else:
            ret, matching_files = False, []

        if ret:
            download_list.append({"sub_dir":  f"flow{idx}", "file_list": matching_files, "role": file_info.get("role", [])})
        else:
            shutil.rmtree(tmp_dir) # Remove Tmp directory in case of failure
            utils_logger.debug(f"API Failure, Could not Download Matching Files !")
            return False, "Download Failure !", None, download_list

    utils_logger.debug(f"API Success, tmp_dir, download_list={tmp_dir, download_list} !")
    return True, "API Success", tmp_dir, download_list