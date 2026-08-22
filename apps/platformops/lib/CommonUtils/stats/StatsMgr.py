''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : ServiceStats.py
* Description       : Common Utility Module supporting Project Statistics
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
* 10-April-24       Aniket                  Updated.
* 03-June-25        Aniket                  Updated.
*********************************************************************************************************************'''
import json

import yaml
import os
import requests
import pandas as pd
from pathlib import Path
from prometheus_client import Counter, Gauge, REGISTRY
import json
from CommonUtils.CutilSetting import CutilSettings


def cutil_init_counters(app_counter_config):
    counters = []
    for key, value in app_counter_config.items():
        if value['Owner'] is True:
            counter_val = Counter(value['CounterName'], value['CounterDesc'])
            counters.append(counter_val)
    return counters


def cutil_init_gauges(gauge_config):
    gauges = []
    for key, value in gauge_config.items():
        gauge_name = value.get('GaugeName')
        owner = value.get('Owner', False)

        if gauge_name and owner:
            if gauge_name not in REGISTRY._names_to_collectors:
                gauge = Gauge(gauge_name, value.get('GaugeDesc', ''))
                restored_value = _read_persisted_value(gauge_name)
                if restored_value is not None:
                    gauge.set(restored_value)
            else:
                gauge = REGISTRY._names_to_collectors[gauge_name]

            gauges.append(gauge)
    return gauges


def cutil_persist_gauge_value(gauge, value):
    file_path = 'gauge_values.json'
    gauge_values = {}

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                gauge_values = json.load(f)
        except json.JSONDecodeError:
            gauge_values = {}

    gauge_values[gauge._name] = value

    with open(file_path, 'w') as f:
        json.dump(gauge_values, f)


def _read_persisted_value(gauge_name):
    file_path = 'gauge_values.json'
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get(gauge_name, None)
        except json.JSONDecodeError:
            return None
    return None


def cutil_get_stats(counter_name, start_date, end_date, step_size):
    resp = requests.get(
        "http://" + CutilSettings.prometheus_server_ip + ":" + CutilSettings.prometheus_server_port + "/api/v1/query_range?"
                                                                          'query=increase(' + counter_name + '[' + step_size + '])&start=' + start_date + "&end=" + end_date + "&step=" + step_size)
    resp_json = resp.json()
    # Convert to DataFrame and format date/time
    df_stats = pd.DataFrame(columns=['period', 'stats'])
    if len(resp_json['data']['result']) != 0:
        df_stats = pd.DataFrame(columns=['period', 'stats'], data=resp_json['data']['result'][0]['values'])
        df_stats['period'] = pd.to_datetime(df_stats['period'], unit='s')
        df_stats['date'] = df_stats['period'].dt.strftime('%d' + '-%b')
        df_stats['hour'] = df_stats['period'].dt.strftime('%d' + '-%b' + ':' + '%H')
        df_stats['stats'] = pd.to_numeric(df_stats['stats'], errors='coerce').fillna(0).astype(int)
    return df_stats


def cutil_get_gauge_stats(gauge_name, start_date, end_date, step_size):
    url = f"http://{CutilSettings.prometheous_server_ip }:{CutilSettings.prometheus_server_port}/api/v1/query_range?query={gauge_name}&start={start_date}&end={end_date}&step={step_size}"
    # Make the request
    resp = requests.get(url)
    # Convert response to JSON
    resp_json = resp.json()
    df_stats = pd.DataFrame(columns=['period', 'stats'])
    if len(resp_json['data']['result']) != 0:
        df_stats = pd.DataFrame(columns=['period', 'stats'], data=resp_json['data']['result'][0]['values'])
        df_stats['period'] = pd.to_datetime(df_stats['period'], unit='s')
        df_stats['date'] = df_stats['period'].dt.strftime('%d' + '-%b')
        df_stats['hour'] = df_stats['period'].dt.strftime('%d' + '-%b' + ':' + '%H')
        df_stats['stats'] = pd.to_numeric(df_stats['stats'], errors='coerce').fillna(0).astype(int)
    return df_stats


def cutil_stats_init(prom_ip, prom_port):
    if not all(isinstance(val, str) for val in [prom_ip, prom_port]):
        return False, "Invalid configuration:prom_ip, prom_port must all be strings."
    CutilSettings.prometheus_server_ip = prom_ip
    CutilSettings.prometheus_server_port = prom_port

    return True, "Initialization Complete"
