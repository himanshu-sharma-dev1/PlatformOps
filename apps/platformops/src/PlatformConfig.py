''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : CommonConfig.py
* Description       : Functions related to platform config
*
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 06-Aug-25 		Sumit Das		            Created.
*********************************************************************************************************************'''

import os
import yaml
from pathlib import Path
from cPlatformIO.src.PlatformSetting import PlatformSettings
from cPlatform.AppLogging import app_logger


def _safe_int(val, default=0):
    try:
        return int(str(val or "").strip())
    except (ValueError, TypeError):
        return default


def _read_cplatform_config():
    config_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    with open(config_path + '/cPlatform_config.yaml') as fh:
        cplatform_config = yaml.load(fh, Loader=yaml.FullLoader)
    return cplatform_config


def _save_cplatform_config(cplatform_config):
    app_logger.debug(f'_update_cplatform_config:{cplatform_config}')
    config_path = os.path.join(Path(__file__).resolve().parent.parent.parent, 'config')
    with open(config_path + '/cPlatform_config.yaml', 'w') as fh:
        yaml.dump(cplatform_config, fh, default_flow_style=False)
    return


def _update_llm_config(req_info):
    llm_config = {
        "llm_host": req_info.get('llm_host'),
        "llm_port": req_info.get('llm_port'),
        "llm_model": req_info.get('llm_model', '')
    }
    return llm_config


def _update_prometheus_config(ser_ins):
    prometheus_config = {
        "prometheus_server_ip": str(ser_ins.Node.node_ip),
        "prometheus_server_port": str(ser_ins.Node.node_monitor_port)
    }
    return prometheus_config


def _update_mail_config(req_info):
    mail_config = {
        "mail_host": req_info.get('email_host', ''),
        "mail_username": req_info.get('email_username', ''),
        "mail_password": req_info.get('email_password', ''),
        "mail_port": _safe_int(req_info.get('email_port'), 0),
        "mail_use_tls": True,
        "mail_agent": req_info.get('email_agent', ''),
    }
    return mail_config


def _update_repo_config(ser_ins):
    repo_config = {
        "master_host": str(ser_ins.Node.node_ip),
        "master_path": os.path.join(str(ser_ins.Node.node_volume), 'iktara/Repository'),
        "master_username": ser_ins.Node.username,
        "master_password": ser_ins.Node.password,
        "master_pem_file_text": ser_ins.Node.encryption_key_text,
        "master_pem_file_name": ser_ins.Node.encryption_key_name,
        "master_auth_type": ser_ins.Node.auth_type,
        "repo_role": 'Primary',
        "repo_sync": 'LOCAL'
    }
    return repo_config


def _update_service_config(ser_ins, req_info):
    service_config = {
        'deploy_status': req_info.get('deploy_status'),
        'time_zone': req_info.get('time_zone', ''),
        'cplatform_url': req_info.get('orchestrator_url', '').strip().rstrip('/'),
        'service_ip': str(ser_ins.Node.node_ip),
        'service_port': _safe_int(req_info.get('service_port'), ser_ins.service_port or 80),
        'service_install': str(req_info.get('service_install')),
        'service_version': str(req_info.get('service_version')),
        'mcp_url': req_info.get('mcp_url'),
        'text2sql_url': req_info.get('text2sql_url'),
        'gpu_flag': 'Disable'
    }
    return service_config


def platform_update_config(ser_ins, req_info):
    
    cplatform_config = _read_cplatform_config()

    # Update llm Info
    cplatform_config['CPLATFORM_CONFIG']['llm'] = _update_llm_config(req_info)

    # Update mail Info
    cplatform_config['CPLATFORM_CONFIG']['mail'] = _update_mail_config(req_info)

    # update dataflow ingestion agent flag
    cplatform_config['CPLATFORM_CONFIG']['dataflow_agent_flag'] = req_info.get('dataflow_agent_flag')
    # Update repo Info
    cplatform_config['CPLATFORM_CONFIG']['repo'] = _update_repo_config(ser_ins)

    # Update service Info
    cplatform_config['CPLATFORM_CONFIG']['service'] = _update_service_config(ser_ins, req_info)

    # Update prometheus Info
    cplatform_config['CPLATFORM_CONFIG']['prometheus'] = _update_prometheus_config(ser_ins)

    _save_cplatform_config(cplatform_config)

    # Update PlatformSettings data class
    PlatformSettings.update_config()
    return
