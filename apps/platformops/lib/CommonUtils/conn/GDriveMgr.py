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


def _gdrive_connect(service_account_info):
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
            return match.group(1)

    raise ValueError("No valid folder ID found in the link.")

def _gdrive_get_folder_id_by_path(service, root_folder_id, path):
    if path.strip() in ['', '/']:
        return root_folder_id  # root path

    path_parts = [part for part in path.strip('/').split('/') if part]
    current_folder_id = root_folder_id

    for part in path_parts:
        results = service.files().list(
            q=f"'{current_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='{part}' and trashed=false",
            fields="files(id, name)",
            pageSize=10
        ).execute()
        folders = results.get('files', [])
        if not folders:
            raise FileNotFoundError(f"Folder '{part}' not found in path '{path}'")
        current_folder_id = folders[0]['id']  # Move to next subfolder

    return current_folder_id

def _gdrive_get_file_list(service, drive_link, remote_path):
    utils_logger.debug(f"_gdrive_get_file_list, service, drive_link, remote_path: {service, drive_link, remote_path}")

    try:
        root_folder_id = _extract_folder_id(drive_link)
        target_folder_id = _gdrive_get_folder_id_by_path(service, root_folder_id, remote_path)

        # --- List Files in Folder ---
        results = service.files().list(
            q=f"'{target_folder_id}' in parents and trashed = false",
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        return items
    except Exception as e:
        utils_logger.debug(f"Error getting file list for remote path {drive_link}, Error:{e}")
        return None


def _gdrive_file_download(service, drive_link, remote_file_id, local_file_path):
    utils_logger.debug(f"_service_file_download - drive_link: {drive_link}, "
                       f"remote_file_id: {remote_file_id}, local_file_path: {local_file_path}")

    try:
        if os.path.isdir(local_file_path):
            local_file_path = os.path.join(local_file_path, remote_file_id['name'])

        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        if remote_file_id['mimeType'] == 'application/vnd.google-apps.document':
            # It's a Google Doc, export it
            request = service.files().export_media(
                fileId=remote_file_id['id'],
                mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        else:
            request = service.files().get_media(fileId=remote_file_id['id'])
        fh = io.FileIO(local_file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                utils_logger.debug(f"Download {int(status.progress() * 100)}%.")

        utils_logger.debug(f"File {remote_file_id} downloaded successfully to {local_file_path}")
        return True

    except Exception as e:
        utils_logger.debug(f"Failed to download file {remote_file_id} from Drive: {str(e)}")
        return False

def cutil_gdrive_download(drive_link, service_account_info,remote_path, filename, tmp_dir):
    filename = os.path.splitext(filename)[0]
    utils_logger.debug(f"cutil_gdrive_download, drive_link, service_account_info, remote_path, filename, tmp_dir: "
                       f"{drive_link, service_account_info, remote_path, filename, tmp_dir}")

    local_file_names = []
    # Validate tmp directory
    if not os.path.isdir(tmp_dir):
        utils_logger.debug("Download Failure, Invalid Local Directory!")
        return False, []
    # Connect to drive Server using given credentials
    service = _gdrive_connect(service_account_info)
    if not service:
        utils_logger.debug("Download Failure, Unable to connect to Drive Server!")
        return False, []
    # Get List of files from given bucket name and remote path
    file_details = _gdrive_get_file_list(service, drive_link, remote_path)

    if not file_details:
        utils_logger.debug("Download Failure, Unable get file list from server!")
        return False, []

    if filename != '*':
        # Get File list in remote path at SFTP Server
        file_list = [item['name'] for item in file_details]
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
        matching_files = [item['name'] for item in file_details]
        if not matching_files:
            utils_logger.debug("Download Failure, Unable get file list from server!")
            return False, []

    if not matching_files:
        utils_logger.debug("Download Failure, No matching files found !")
        return False, []
    matching_file_details = [file for file in file_details if file["name"] in matching_files]
    for remote_detail in matching_file_details:
        if not _gdrive_file_download(service, drive_link, remote_detail,tmp_dir):
            utils_logger.debug(f"Download Failure, File: could not be downloaded!")
            return False, []
        # Append the local file name to the list
        local_file_names.append(remote_detail['name'])

    utils_logger.debug(f"Download service Download Success, file_list:{matching_files} !")
    return True, local_file_names

