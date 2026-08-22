''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : DriveMgr.py
* Description       : Google Drive Manager Module
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 26-Apr-25        Aadarsh Ranjan               updated.
*********************************************************************************************************************'''

from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
from googleapiclient.http import MediaIoBaseDownload
import re
import os 

from CommonUtils.logs.AppLogging import utils_logger


def _drive_connect(service_account_info):
    """
    Establishes a connection to the Google Drive API using a service account.
    """
    utils_logger.debug(f"service_account_info: {service_account_info}")

    try:
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )

        service = build('drive', 'v3', credentials=credentials)
        return service

    except ValueError as e:
        utils_logger.error(f"Google Drive Connect Failure: Invalid credentials - {e}")
    except Exception as e:
        utils_logger.error(f"Google Drive Connect Failure: Unexpected error - {e}")

    return None

def _extract_folder_id(url):
    patterns = [
        r'/folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            print(match.group(1))
            return match.group(1)

    raise ValueError("No valid folder ID found in the link.")

def _drive_get_file_list(service, drive_link, remote_path):
    utils_logger.debug(f"_drive_get_file_list, service, drive_link, remote_path: {service, drive_link, remote_path}")

    try:
        folder_id = _extract_folder_id(drive_link)
        print("the folder id is :",folder_id)

        # --- List Files in Folder ---
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name, mimeType)"
        ).execute()
        print("result is :",results)
        items = results.get('files', [])
        # file_names = [item['name'] for item in items]
        # print("items is :",file_names)
        return items
    except Exception as e:
        utils_logger.debug(f"Error getting file list for remote path {drive_link}, Error:{e}")
        return None


def _drive_file_download(service, drive_link, remote_file_id, local_file_path):
    """
    Downloads a file from Google Drive using its file ID and saves it locally.

    Parameters:
        service: Authenticated Google Drive API service instance.
        drive_link: URL to the file on Drive (used for logging).
        remote_file_id: ID of the file on Google Drive.
        local_file_path: Path to save the downloaded file locally.

    Returns:
        True if download succeeds, False otherwise.
    """
    print("drive file download function",local_file_path)
    utils_logger.debug(f"_service_file_download - drive_link: {drive_link}, "
                       f"remote_file_id: {remote_file_id}, local_file_path: {local_file_path}")

    try:
        if os.path.isdir(local_file_path):
            local_file_path = os.path.join(local_file_path, remote_file_id['name'])

        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        request = service.files().get_media(fileId=remote_file_id['id'])
        print("download request is reached ")
        fh = io.FileIO(local_file_path, 'wb')
        print("download fh is reached ")
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download {int(status.progress() * 100)}%.")

        utils_logger.debug(f"File {remote_file_id} downloaded successfully to {local_file_path}")
        return True

    except Exception as e:
        print(f"Failed to download file {remote_file_id} from Drive: {str(e)}")
        utils_logger.debug(f"Failed to download file {remote_file_id} from Drive: {str(e)}")
        return False


def cutil_drive_download(drive_link, service_account_info, filename, tmp_dir):
    print("service_account_info",service_account_info)
    remote_path = ''
    utils_logger.debug(f"cutil_drive_download, drive_link, service_account_info, remote_path, filename, tmp_dir: "
                       f"{drive_link, service_account_info, remote_path, filename, tmp_dir}")

    local_file_names = []
    print("filename is :",filename)
    # Validate tmp directory
    if not os.path.isdir(tmp_dir):
        utils_logger.debug("Download Failure, Invalid Local Directory!")
        return False, []
    print("temp_dir is correct")
    # Connect to drive Server using given credentials
    service = _drive_connect(service_account_info)
    print("service is correct")
    if not service:
        utils_logger.debug("Download Failure, Unable to connect to Drive Server!")
        return False, []
    print("service is passed")
    # Get List of files from given bucket name and remote path
    file_list = _drive_get_file_list(service, drive_link, remote_path)

    if not file_list:
        utils_logger.debug("Download Failure, Unable get file list from server!")
        return False, []

    if filename == '*':
        matching_files = file_list
    else:
        matching_files = [item for item in file_list if item['name'].startswith(filename)]

    print("matching files",matching_files)
    if not matching_files:
        utils_logger.debug("Download Failure, No matching files found !")
        return False, []
    print("matching files passed")
    for remote_filename in matching_files:
        print("inside the loop")
        # Construct the full remote path for the file
        remote_file_path = remote_filename  # full key should already be in matching_files
        print("inside the loop 2")
        # Extract just the file name to use in the local path
        # local_file_name = os.path.basename(remote_file_path)

        # Construct the local file path
        # local_file_path = os.path.join(tmp_dir, local_file_name)

        if not _drive_file_download(service, drive_link, remote_file_path,tmp_dir):
            print("matching files not downloded")
            utils_logger.debug(f"Download Failure, File:{local_file_name} could not be downloaded!")
            return False, []
        print("matching files downloded")
        # Append the local file name to the list
        # local_file_names.append(local_file_name)

    utils_logger.debug(f"Download service Download Success, file_list:{matching_files} !")
    return True, []

