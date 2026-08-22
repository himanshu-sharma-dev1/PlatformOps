''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : S3Mgr.py
* Description       : S3 Manager Module
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 26-Sept-24        Sumit Das               updated.
*********************************************************************************************************************'''

import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from CommonUtils.logs.AppLogging import utils_logger


def _s3_connect(aws_access_key_id, aws_secret_access_key):
    utils_logger.debug(f"_s3_connect, aws_access_key_id, aws_secret_access_key: "
                       f"{aws_access_key_id, aws_secret_access_key}")
    try:
        # Connect to S3 using credentials
        s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        return s3

    except (NoCredentialsError, PartialCredentialsError) as e:
        utils_logger.debug(f"S3 Connect Failure, Credentials error: {e}")
        return None
    except Exception as e:
        utils_logger.debug(f"S3 Connect Failure,  Unknown connection error ! {e}")
        return None


def _s3_get_file_list(s3, bucket_name, remote_path):
    utils_logger.debug(f"_s3_get_file_list, bucket_name, remote_path: {bucket_name, remote_path}")

    try:
        # List objects within the specified folder in the S3 bucket
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=remote_path)

        # Extract list of file names
        file_list = []
        if 'Contents' in response:
            file_list = [obj['Key'] for obj in response['Contents']]

        utils_logger.debug(f"_s3_get_file_list: {file_list}")
        return file_list
    except Exception as e:
        utils_logger.debug(f"Error getting file list for remote path {remote_path}, Error:{e}")
        return None


def _s3_file_download(s3, bucket_name, remote_file_path, local_file_path):

    utils_logger.debug(f"_s3_file_download, bucket_name, remote_file_path, local_file_path: "
                       f"{bucket_name, remote_file_path, local_file_path}")
    try:
        s3.download_file(bucket_name, remote_file_path, local_file_path)
        # print(f"Downloaded: {remote_file_path} to {local_file_path}")
        utils_logger.debug(f"File:{os.path.basename(remote_file_path)} downloaded successfully to:{local_file_path}")
        return True

    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            utils_logger.debug(f"s3 download failure, file:{os.path.basename(remote_file_path)} does not exist on s3 bucket.")
        else:
            utils_logger.debug(f"Failed to download file:{os.path.basename(remote_file_path)} from s3 bucket, Error {str(e)} ")
        return False


def cutil_s3_download(bucket_name, aws_access_key_id, aws_secret_access_key, remote_path, filename, tmp_dir):

    utils_logger.debug(f"cutil_s3_download, bucket, aws_access_key, aws_secret_key, path, filename, tmp_dir: "
                       f"{bucket_name, aws_access_key_id, aws_secret_access_key, remote_path, filename, tmp_dir}")

    local_file_names = []

    # Validate tmp directory
    if not os.path.isdir(tmp_dir):
        utils_logger.debug("Download Failure, Invalid Local Directory!")
        return False, []

    # Connect to AWS Server using given credentials
    s3 = _s3_connect(aws_access_key_id, aws_secret_access_key)

    if not s3:
        utils_logger.debug("Download Failure, Unable to connect to AWS Server!")
        return False, []

    # Get List of files from given bucket name and remote path
    file_list = _s3_get_file_list(s3, bucket_name, remote_path)

    if not file_list:
        utils_logger.debug("Download Failure, Unable get file list from server!")
        return False, []

    if filename == '*':
        matching_files = [file for file in file_list if file.startswith(remote_path) and not file.endswith('/')]
    else:
        matching_files = [file for file in file_list if file.startswith(f"{remote_path}/{filename.split('.')[0]}")]

    if not matching_files:
        utils_logger.debug("Download Failure, No matching files found !")
        return False, []

    for remote_filename in matching_files:

        # Construct the full remote path for the file
        remote_file_path = remote_filename  # full key should already be in matching_files

        # Extract just the file name to use in the local path
        local_file_name = os.path.basename(remote_file_path)

        # Construct the local file path
        local_file_path = os.path.join(tmp_dir, local_file_name)

        if not _s3_file_download(s3, bucket_name, remote_file_path, local_file_path):
            utils_logger.debug(f"Download Failure, File:{local_file_name} could not be downloaded!")
            return False, []

        # Append the local file name to the list
        local_file_names.append(local_file_name)

    utils_logger.debug(f"Download S3 Download Success, file_list:{matching_files} !")
    return True, local_file_names

