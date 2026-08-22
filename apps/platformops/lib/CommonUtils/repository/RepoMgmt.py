''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : RepoMgmt.py
* Description       : Functions related to Repository Mgmt
*
*
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 14-July-22 		Yashveer 		 Created.
* 14-March-24 		Sumit Das 		 Updated.
*********************************************************************************************************************'''
import os
import stat
import paramiko
import os.path
import shutil
from pathlib import Path
import yaml
from CommonUtils.repository import RepoPorting
from CommonUtils.CutilSetting import CutilSettings
from CommonUtils.conn.SFTPMgr import cutil_sftp_sync
from CommonUtils.logs.AppLogging import utils_logger


# ---------------------------------------------------- Helper functions ---------------------------------------------#

def RepoMgmt_init_repo():
    base_path = CutilSettings.base_path
    ret = RepoPorting.RepoPorting_mkdir(base_path)
    return ret


def _check_parameter_types(repo_role, repo_sync_method, base_path, primary_machine_info):
    if not isinstance(repo_role, str):
        return False, "repo_role must be a string"
    if not isinstance(repo_sync_method, str):
        return False, "repo_sync_method must be a string."
    if not isinstance(base_path, str):
        return False, "base_path must be a string."
    if not isinstance(primary_machine_info, dict):
        return False, "primary_machine_info must be an dict."
    return True, ""


def _validate_repo_request(repo_role, repo_sync_method, base_path):
    # validate_repo_role
    if repo_role not in {"Primary", "Secondary"}:
        utils_logger.error(f"repo_role must be 'Primary' or 'Secondary', got '{repo_role}'")
        return False, f"repo_role must be 'Primary' or 'Secondary'!"

    # Validate repo_sync_method
    if repo_sync_method not in {"LOCAL", "REMOTE"}:
        utils_logger.error(f"repo_sync_method must be 'LOCAL' or 'REMOTE', got '{repo_sync_method}'")
        return False, f"repo_sync_method must be 'LOCAL' or 'REMOTE'!"

    # Validate Path
    if not os.path.exists(base_path):
        utils_logger.error(f"Invalid Path:{base_path}")
        return False, f"Invalid Path !"

    return True, f"Repo Request Validated Successfully"


def repo_get_temp_dir():
    base_path = CutilSettings.base_path
    temp_path = os.path.join(base_path, 'Temp_folder')
    os.makedirs(temp_path, exist_ok=True)
    return temp_path

# ----------------------------------------------------------new report related functions--------------------------------


def repo_report_create(report_name):
    utils_logger.debug(f"repo_report_create, report_name ={report_name}")

    base_path = CutilSettings.base_path
    report_path = os.path.join(base_path, 'Reports')
    folder_path = os.path.join(report_path, str(report_name))
    os.makedirs(folder_path, exist_ok=True)
    return os.path.isdir(folder_path)


def repo_report_save(report_name, file_path):
    utils_logger.debug(f"repo_report_save, report_name, file_path ={report_name, file_path}")

    base_path = CutilSettings.base_path
    report_path = os.path.join(base_path, 'Reports')
    folder_path = os.path.join(report_path, str(report_name))

    # If the folder path exists return True
    if os.path.exists(folder_path):
        # Copy the file from file_path to the folder_path
        destination_path = os.path.join(folder_path, os.path.basename(file_path))

        shutil.copy(file_path, destination_path)  # Copy the file
        return True
    else:
        return False


def repo_report_get(report_name, file_name):
    utils_logger.debug(f"repo_report_get, report_name, file_name ={report_name, file_name}")

    # Retrieve storage configuration
    base_path = CutilSettings.base_path
    temp_folder_path = repo_get_temp_dir()

    # Construct paths
    report_folder = os.path.join(base_path, str(report_name))
    file_path = os.path.join(report_folder, file_name)
    tmp_file_path = os.path.join(temp_folder_path, file_name)

    # Ensure the temp folder exists
    os.makedirs(temp_folder_path, exist_ok=True)

    # Check if the file exists and copy it to the temp folder
    if os.path.isfile(file_path):
        shutil.copy(file_path, tmp_file_path)
        return tmp_file_path  # Return the temporary file path if copied successfully
    else:
        return None  # Return None if the file does not exist


def repo_report_delete(report_name):
    utils_logger.debug(f"repo_report_delete, report_name ={report_name}")

    base_path = CutilSettings.base_path
    report_path = os.path.join(base_path, 'Reports')
    folder_path = os.path.join(report_path, str(report_name))

    # Check and delete the folder if it exists
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        return True
    else:
        return False


def repo_report_clear(report_name):
    utils_logger.debug(f"repo_report_clear, report_name ={report_name}")

    base_path = CutilSettings.base_path
    report_path = os.path.join(base_path, 'Reports')
    folder_path = os.path.join(report_path, str(report_name))

    if os.path.isdir(folder_path):
        [os.remove(os.path.join(folder_path, file)) for file in os.listdir(folder_path)]
        return True
    else:
        return False


# ------------------------------------new dataflow related functions----------------------------------------------------

def repo_dataflow_create(dataflow_id):
    utils_logger.debug(f"repo_dataflow_create, dataflow_id ={dataflow_id}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))
    os.makedirs(folder_path, exist_ok=True)

    return os.path.exists(folder_path)


def repo_dataflow_save(dataflow_id, tmp_dir):
    utils_logger.debug(f"repo_dataflow_save, dataflow_id, tmp_dir ={dataflow_id, tmp_dir}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))

    # os.makedirs(folder_path, exist_ok=True)  # Ensure the folder exists
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)  # Remove the existing folder
        # Move the tmp_folder to the dataflow_folder
        shutil.move(tmp_dir, folder_path)
        return True

    return False


def repo_dataflow_save_fldr(dataflow_id, fldr_dir):
    utils_logger.debug(f"repo_dataflow_save_fldr, dataflow_id, fldr_dir = {dataflow_id, fldr_dir}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))

    if not os.path.exists(folder_path):
        return False

    if not os.path.exists(fldr_dir):
        return False

    # Iterate over subfolders
    for entry in os.listdir(folder_path):
        subdir_path = os.path.join(folder_path, entry)
        if os.path.isdir(subdir_path) and entry.startswith("flow"):
            for filename in os.listdir(subdir_path):
                file_path = os.path.join(subdir_path, filename)
                if os.path.isfile(file_path):
                    shutil.copy(file_path, fldr_dir)

    return True


def repo_read_file(dataflow_id, file_name, subdir):
    utils_logger.debug(f"repo_read_file, dataflow_id, file_name, subdir ={dataflow_id, file_name, subdir}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))
    file_path = folder_path + f"/{subdir}" + f"/{file_name}"

    # Check if the directory exists
    if not os.path.exists(file_path):
        return False, ""

    return True, file_path


def repo_save_file(dataflow_id, file_name, dataflow_df, subdir):
    utils_logger.debug(f"repo_save_file, dataflow_id, file_name, subdir ={dataflow_id, file_name, subdir}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))

    file_path = folder_path + f'/{subdir}' + f'/{file_name}'

    if file_name.endswith(".csv"):
        dataflow_df.to_csv(file_path)
    else:
        dataflow_df.to_excel(file_path)

    return


def repo_dataflow_delete(dataflow_id):
    utils_logger.debug(f"repo_dataflow_delete, dataflow_id ={dataflow_id}")

    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))

    # Check and delete the folder if it exists
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        return True
    else:
        return False


def repo_dataflow_filepath(dataflow_id, download_list):
    base_path = CutilSettings.base_path
    dataflow_path = os.path.join(base_path, 'Dataflow')
    folder_path = os.path.join(dataflow_path, str(dataflow_id))
    folder_path = os.path.join(dataflow_path, str(dataflow_id))
    file_list = []
    for key, value in enumerate(download_list):
        for file in value['file_list']:
            file_path = folder_path + f"/{value['sub_dir']}" + f"/{file}"
            file_list.append(file_path)
    return file_list


# ----------------------------------new model related functions---------------------------------------------------------


def _update_meta_data_yaml(model_id, yaml_dict):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    with open(f'{model_dir}/meta_data.yaml', 'w') as yaml_file:
        yaml.dump([yaml_dict], yaml_file, default_flow_style=False)


def _get_meta_data_yaml(model_id):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    # opening a file
    with open(f'{model_dir}/meta_data.yaml') as stream:
        # Converts yaml document to pyt
        # hon object
        yaml_dict = yaml.safe_load(stream)
    return yaml_dict[0]


def cutil_repo_model_create(model_id):
    if model_id == "" or model_id is None:
        return False
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    # Create model directory
    os.makedirs(model_dir, exist_ok=True)

    model_source_dir = os.path.join(model_dir, 'SourceData')
    os.makedirs(model_source_dir, exist_ok=True)

    model_common_dir = os.path.join(model_dir, 'CommonData')
    os.makedirs(model_common_dir, exist_ok=True)

    meta_data = {}
    meta_data['model'] = {}
    _update_meta_data_yaml(model_id, meta_data)

    return True


def cutil_repo_model_save(model_id, fldr_name, file_path):
    base_path = CutilSettings.base_path

    if not base_path or not isinstance(base_path, str):
        return False

    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    model_fldr_dir = os.path.join(model_dir, fldr_name)

    if not os.path.exists(model_fldr_dir):
        return False

    if not os.path.exists(file_path):
        return False
    try:
        destination_path = os.path.join(model_fldr_dir, os.path.basename(file_path))
        shutil.move(file_path, destination_path)
        return True
    except:
        return False


def cutil_repo_model_save_new(model_id, fldr_name, tmp_dir):
    base_path = CutilSettings.base_path

    if not base_path or not isinstance(base_path, str):
        return False

    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    model_fldr_dir = os.path.join(model_dir, fldr_name)

    if os.path.exists(model_fldr_dir):
        shutil.rmtree(model_fldr_dir)

    if not os.path.exists(tmp_dir):
        return False
    try:
        shutil.move(tmp_dir, model_fldr_dir)
        return True
    except:
        return False


def cutil_repo_model_get(model_id, fldr_name, file_name):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    model_fldr_dir = os.path.join(model_dir, fldr_name)
    # Check if the directory exists
    if not os.path.exists(model_fldr_dir):
        raise FileNotFoundError(f"The directory {model_fldr_dir} does not exist.")

    for file in os.listdir(model_fldr_dir):
        if file == file_name:
            file_path = os.path.join(model_fldr_dir, file)
            return True, file_path
    return False, f"File '{file_name}' not found in '{model_fldr_dir}'."


def cutil_repo_model_get_new(model_id, fldr_name, file_name, subdir):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    model_fldr_dir = os.path.join(model_dir, fldr_name)
    model_subdir_path = model_fldr_dir + f"/{subdir}"
    # Check if the directory exists
    if not os.path.exists(model_subdir_path):
        raise FileNotFoundError(f"The directory {model_subdir_path} does not exist.")

    for file in os.listdir(model_subdir_path):
        if file == file_name:
            file_path = os.path.join(model_subdir_path, file)
            return True, file_path
    return False, f"File '{file_name}' not found in '{model_fldr_dir}'."


def cutil_repo_model_delete(model_id):
    base_path = CutilSettings.base_path

    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    # Check and delete the folder if it exists
    if os.path.isdir(model_dir):
        shutil.rmtree(model_dir)
        return True
    else:
        return False


# -----------------------------------------new algo related functions---------------------------------------------------


def cutil_repo_algo_create(model_id, algo_id):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    # Create Algo dir
    algo_dir = os.path.join(model_dir, str(algo_id))
    os.makedirs(algo_dir, exist_ok=True)

    # Create Algo Reports dir
    algo_report_dir = os.path.join(algo_dir, 'artifacts')
    os.makedirs(algo_report_dir, exist_ok=True)

    # Create Algo Model dir
    algo_model_dir = os.path.join(algo_dir, 'artifacts')
    os.makedirs(algo_model_dir, exist_ok=True)

    # Create Algo run dir
    algo_run_dir = os.path.join(algo_dir, 'artifacts')
    os.makedirs(algo_run_dir, exist_ok=True)

    # update meta data yaml
    meta_data = _get_meta_data_yaml(model_id)
    meta_data['model'][algo_id] = {}
    meta_data['model'][algo_id]['artifacts'] = {}
    meta_data['model'][algo_id]['artifacts'] = {}
    meta_data['model'][algo_id]['artifacts'] = {}
    _update_meta_data_yaml(model_id, meta_data)

    return True


def cutil_repo_algo_save(model_id, algo_id, fldr_name, file_path):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    algo_dir = os.path.join(model_dir, str(algo_id))
    algo_fldr_dir = os.path.join(algo_dir, str(fldr_name))
    os.makedirs(algo_fldr_dir, exist_ok=True)

    if not os.path.exists(algo_fldr_dir):
        return False

    if not os.path.exists(file_path):
        return False

    try:
        file_name = os.path.basename(file_path)
        destination_path = os.path.join(algo_fldr_dir, file_name)
        shutil.move(file_path, destination_path)
        return True
    except:
        return False


def cutil_repo_algo_get(model_id, algo_id, fldr_name, file_name):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    algo_dir = os.path.join(model_dir, str(algo_id))
    algo_fldr_dir = os.path.join(algo_dir, str(fldr_name))
    for file in os.listdir(algo_fldr_dir):
        if file == file_name:
            file_path = os.path.join(algo_fldr_dir, file)
            return True, file_path
        else:
            return False, f"File '{file_name}' not found in folder '{algo_fldr_dir}'."


# def cutil_repo_get_fldr_path(model_id, algo_id, fldr_name):
#     base_path = CutilSettings.base_path
#     model_path = os.path.join(base_path, 'Models')
#     model_dir = os.path.join(model_path, str(model_id))
#
#     algo_dir = os.path.join(model_dir, str(algo_id))
#     algo_fldr_dir = os.path.join(algo_dir, str(fldr_name))
#     for file in os.listdir(algo_fldr_dir):
#         file_path = os.path.join(algo_fldr_dir, file)
#         if os.path.exists(file_path):
#             return True, file_path
#         else:
#             return False, f"File '{file}' not found in folder '{algo_fldr_dir}'."


def cutil_repo_get_fldr_path(model_id, algo_id, fldr_name):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    algo_dir = os.path.join(model_dir, str(algo_id))
    algo_fldr_dir = os.path.join(algo_dir, str(fldr_name))

    if not os.path.exists(algo_fldr_dir):
        return False, f"Folder '{algo_fldr_dir}' does not exist."

    file_paths = []
    for file in os.listdir(algo_fldr_dir):
        file_path = os.path.join(algo_fldr_dir, file)
        if os.path.isfile(file_path):
            file_paths.append(file_path)

    if file_paths:
        return True, file_paths
    else:
        return False, f"No files found in folder '{algo_fldr_dir}'."


def cutil_repo_algo_delete(model_id, algo_id):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    algo_dir = os.path.join(model_dir, str(algo_id))
    if os.path.isdir(algo_dir):
        shutil.rmtree(algo_dir)
        return True
    else:
        return False


# -----------------------------------------new data sync related functions----------------------------------------------

def cutil_repo_dataflow_sync_data(dataflow_id):
    deployment_type = CutilSettings.repo_sync_method

    if deployment_type == 'REMOTE':
        local_base_path = CutilSettings.base_path
        local_dataflow_folder = os.path.join(local_base_path, 'Dataflow')
        # Create local folder if it doesn't exist
        os.makedirs(local_dataflow_folder, exist_ok=True)
        local_pem_folder = os.path.join(local_base_path, 'PemFolder')
        os.makedirs(local_pem_folder, exist_ok=True)
        final_local_folder = os.path.join(local_dataflow_folder, str(dataflow_id))

        # Define remote path
        machine_config = CutilSettings.primary_machine_info
        remote_base_path = machine_config['base_path']
        if machine_config['auth_type'] == 'EncryptionKey':
            pem_file_text = machine_config['pem_file_text']
            key_clean = pem_file_text.encode('utf-8').decode('unicode_escape')

            pem_file_path = os.path.join(local_pem_folder, f"{machine_config['pem_file_name']}")

            with open(pem_file_path, 'w', encoding='utf-8') as pem_file:
                pem_file.write(key_clean)

            machine_config['pem_file_path'] = pem_file_path

        model_folder = os.path.join(remote_base_path, 'Dataflow')
        final_remote_folder = os.path.join(model_folder, str(dataflow_id))

        cutil_sftp_sync(machine_config, final_remote_folder, final_local_folder)
        return True

    else:
        return True


def cutil_repo_model_sync_data(model_id):

    deployment_type = CutilSettings.repo_sync_method

    if deployment_type == 'REMOTE':
        local_base_path = CutilSettings.base_path
        local_dataflow_folder = os.path.join(local_base_path, 'Models')
        # Create local folder if it doesn't exist
        os.makedirs(local_dataflow_folder, exist_ok=True)
        local_pem_folder = os.path.join(local_base_path, 'PemFolder')
        os.makedirs(local_pem_folder, exist_ok=True)

        final_local_folder = os.path.join(local_dataflow_folder, str(model_id))

        # Define remote path
        machine_config = CutilSettings.primary_machine_info
        remote_base_path = machine_config['base_path']
        model_folder = os.path.join(remote_base_path, 'Models')
        final_remote_folder = os.path.join(model_folder, str(model_id))

        if machine_config['auth_type'] == 'EncryptionKey':
            pem_file_text = machine_config['pem_file_text']
            key_clean = pem_file_text.encode('utf-8').decode('unicode_escape')

            pem_file_path = os.path.join(local_pem_folder, f"{machine_config['pem_file_name']}")

            with open(pem_file_path, 'w', encoding='utf-8') as pem_file:
                pem_file.write(key_clean)

            machine_config['pem_file_path'] = pem_file_path

        cutil_sftp_sync(machine_config, final_remote_folder, final_local_folder)
        return True

    else:
        return True

# -----------------------------------------Repo init function----------------------------------------------


def cutil_repo_init(repo_role, repo_sync_method, base_path, primary_machine_info):
    utils_logger.debug(f"cutil_repo_init request : repo_role, repo_sync_method, base_path, Primary_machine_info "
                       f"{repo_role, repo_sync_method, base_path, primary_machine_info}")

    # Data type validation
    ret, msg = _check_parameter_types(repo_role, repo_sync_method, base_path, primary_machine_info)
    if not ret:
        return ret, msg

    # Validate request
    ret, msg = _validate_repo_request(repo_role, repo_sync_method, base_path)
    if not ret:
        utils_logger.info(msg)
        return ret, msg

    CutilSettings.repo_role = repo_role
    CutilSettings.repo_sync_method = repo_sync_method
    CutilSettings.base_path = base_path
    CutilSettings.primary_machine_info = primary_machine_info

    return True, "Initialization Complete"


# -----------------------------------------Model Infer Related function-------------------------------------------------

def cutil_repo_ensemble_save(model_id, fldr_name, file_path):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))

    ensemble_fldr_dir = os.path.join(model_dir, str(fldr_name))
    os.makedirs(ensemble_fldr_dir, exist_ok=True)

    if not os.path.exists(ensemble_fldr_dir):
        return False

    if not os.path.exists(file_path):
        return False

    try:
        file_name = os.path.basename(file_path)
        destination_path = os.path.join(ensemble_fldr_dir, file_name)
        shutil.move(file_path, destination_path)
        return True
    except:
        return False


def cutil_repo_ensemble_get(model_id, fldr_name, file_name):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    ensmbl_fldr_dir = os.path.join(model_dir, str(fldr_name))
    for file in os.listdir(ensmbl_fldr_dir):
        if file == file_name:
            file_path = os.path.join(ensmbl_fldr_dir, file)
            return True, file_path
        else:
            return False, f"File '{file_name}' not found in folder '{ensmbl_fldr_dir}'."


def cutil_repo_model_infer_get_new(model_id, fldr_name, subdir):
    base_path = CutilSettings.base_path
    model_path = os.path.join(base_path, 'Models')
    model_dir = os.path.join(model_path, str(model_id))
    model_fldr_dir = os.path.join(model_dir, fldr_name)
    model_subdir_path = model_fldr_dir + f"/{subdir}"
    # Check if the directory exists
    if not os.path.exists(model_subdir_path):
        raise FileNotFoundError(f"The directory {model_subdir_path} does not exist.")

    for file in os.listdir(model_subdir_path):
        if file:
            file_path = os.path.join(model_subdir_path, file)
            return True, file_path

        return False, f"Feature config File not found in '{model_fldr_dir}'."
