''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : WebScrapyMgr.py
* Description       : Manage Web Scraping
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 27-DEC-24 		Harsh Soni		            Created.
*********************************************************************************************************************'''


from pathlib import Path
import subprocess
from CommonUtils.logs.AppLogging import utils_logger
from CommonUtils.conn  import selenium_integration
import os
import requests
import re

import os


def get_files(tmp_dir):
    file_list = []
    for item in os.listdir(tmp_dir):
        item_path = os.path.join(tmp_dir, item)
        if os.path.isfile(item_path):
            file_list.append(item)
        elif os.path.isdir(item_path):
            for sub_item in os.listdir(item_path):
                sub_item_path = os.path.join(item_path, sub_item)
                if os.path.isfile(sub_item_path):
                    file_list.append(f"{item}/{sub_item}")
    return file_list



def _get_project_directory():
    base_directory = Path(__file__).resolve().parent
    project_dict = os.path.join(base_directory, 'web_scrap2')
    return project_dict


def cutil_webScrap_download(link,tmp_dir,depth):
    os.makedirs(tmp_dir, exist_ok=True)
    # If Link is Pdf Extension
    if ".pdf" in link.lower():
        filename = re.search(r'([^/]+\.pdf)',link).group(1)
        save_path = os.path.join(tmp_dir, filename)
        response = requests.get(link, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"PDF downloaded successfully: {save_path}")
            return True, [filename]
        else:
            print("Failed to download PDF.")

    utils_logger.debug("pdf link generated through selenium")

    project_dict = _get_project_directory()

    file_list = []
    command = [
        "scrapy",
        "crawl",
        "web_scrap",
        "-a",
        f"start_url={link}",
        "-a",
        f"download_dir={tmp_dir}",
        "-a",
        f"depth={depth}",
    ]
    try:
        subprocess.run(command, cwd=project_dict, check=True)
        file_list = get_files(tmp_dir)
        print(f"file_list ----{file_list}")
        utils_logger.debug(f'Document downloaded successfully')

    except Exception as e:
        utils_logger.debug(f"Issue with connecting to the website - Maybe Website is Restricted: {str(e)}")
        print(f"ERROR : file_list--{file_list}")
        utils_logger.error(f"False---{file_list}")
        return False, []

    return True , file_list