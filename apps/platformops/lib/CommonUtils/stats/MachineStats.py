''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : MachineStats.py
* Description       : For getting the statistics of the machines from prometheus
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 06-Jan-25 		Aniket		            Created.
*********************************************************************************************************************'''
import ast

import requests
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import pytz
from CommonUtils.logs.AppLogging import utils_logger
from CommonUtils.timer.TimerMgr import cutil_timer_get_app_curr_time
from CommonUtils.CutilSetting import CutilSettings

from concurrent.futures import ThreadPoolExecutor, as_completed

def _get_time_range(period):
    step_size = '15m'
    end_date = cutil_timer_get_app_curr_time().astimezone(timezone.utc)
    end_date = end_date.replace(tzinfo=None)

    if period == '1h':
        start_date = end_date - timedelta(hours=1)
        step_size = '1m'
    elif period == '6h':
        start_date = end_date - timedelta(hours=6)
        step_size = '5m'
    elif period == '24h':
        start_date = end_date - timedelta(hours=24)
        step_size = '15m'
    elif period == '7d':
        start_date = end_date - timedelta(days=7)
        step_size = '2h'
    elif period == '1M':
        start_date = end_date - relativedelta(months=1)
        step_size = '8h'
    elif period == '3M':
        start_date = end_date - relativedelta(months=3)
        step_size = '1d'
    else:
        raise ValueError(f"Unsupported period: {period}")

    # Convert to UTC ISO strings
    start_date_iso = start_date.replace(microsecond=0).isoformat() + 'Z'
    end_date_iso = end_date.replace(microsecond=0).isoformat() + 'Z'

    return start_date_iso, end_date_iso, step_size


def _transform_raw_data(data, type):
    if type == 1:
        transformed_values = [round(val, 2) for val in data.values() if val is not None]
    else:
        values = data.values() if isinstance(data, dict) else data
        transformed_values = [round(val / (1024 ** 3), 2) if val is not None else None for val in values]
    return transformed_values


def normalize_monitoring_data(machine_stats):
    # =====================================================
    # TOP PROCESSES
    # =====================================================
    cpu_processes = {}
    memory_processes = {}

    for item in machine_stats.get("top_process_cpu", {}).get("data", []):
        metric = item.get("metric", {})
        process_name = metric.get("groupname")
        instance = metric.get("instance")

        if process_name and instance:
            cpu_processes[(process_name, instance)] = float(item["values"][-1][1])

    for item in machine_stats.get("top_process_memory", {}).get("data", []):
        metric = item.get("metric", {})
        process_name = metric.get("groupname")
        instance = metric.get("instance")

        if process_name and instance:
            memory_processes[(process_name, instance)] = float(item["values"][-1][1])

    all_processes = (set(cpu_processes.keys()) | set(memory_processes.keys()))
    machine_stats["top_processes"] = []

    for process_name, instance in all_processes:
        machine_stats["top_processes"].append({
            "process_name": process_name,
            "instance": instance,
            "cpu_usage": round(
                cpu_processes.get((process_name, instance), 0), 2
            ),
            "memory_usage": round(
                memory_processes.get((process_name, instance), 0), 2
            )
        })

    # =====================================================
    # VOLUME MOUNTS
    # =====================================================
    total_storage_map = {}
    used_storage_map = {}

    for item in machine_stats.get("total_storage_data", {}).get("data", []):
        metric = item.get("metric", {})
        device = metric.get("device")
        mountpoint = metric.get("mountpoint")
        filesystem = metric.get("fstype")

        if device and mountpoint:
            total_storage_map[(device, mountpoint)] = {
                "total_storage": float(item["values"][-1][1]),
                "filesystem": filesystem
            }

    for item in machine_stats.get("used_storage_data", {}).get("data", []):
        metric = item.get("metric", {})
        device = metric.get("device")
        mountpoint = metric.get("mountpoint")

        if device and mountpoint:
            used_storage_map[(device, mountpoint)] = float(item["values"][-1][1])

    all_volumes = (set(total_storage_map.keys()) | set(used_storage_map.keys()))
    machine_stats["volume_mounts"] = []

    for device, mountpoint in all_volumes:
        total_data = total_storage_map.get(
            (device, mountpoint),
            {"total_storage": 0, "filesystem": ""}
        )
        total_storage = total_data["total_storage"]
        filesystem = total_data["filesystem"]
        used_storage = used_storage_map.get((device, mountpoint), 0)

        usage_percent = round(
            (used_storage / total_storage * 100), 2
        ) if total_storage else 0

        machine_stats["volume_mounts"].append({
            "device": device,
            "mountpoint": mountpoint,
            "filesystem": filesystem,
            "total_storage": round(total_storage, 2),
            "used_storage": round(used_storage, 2),
            "usage_percent": usage_percent
        })

    # =====================================================
    # REMOVE RAW DATA
    # =====================================================
    machine_stats.pop("top_process_cpu", None)
    machine_stats.pop("top_process_memory", None)
    machine_stats.pop("total_storage_data", None)
    machine_stats.pop("used_storage_data", None)

    return machine_stats

def _fetch_machine_data(url, metric_name, start, end, step, metric_key, special_metrics=None):
    if start and end:
        query_url = f"{url}/api/v1/query_range?query={metric_name}&start={start}&end={end}&step={step}"
    else:
        query_url = f"{url}/api/v1/query?query={metric_name}"

    try:
        # Set timeout: (connect_timeout, read_timeout)
        response = requests.get(query_url, timeout=(1,2))
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success" and data["data"]["result"]:
            result = data["data"]["result"]
            if special_metrics and metric_key in special_metrics:
                return result
            metric_values = {
                int(value[0]): float(value[1])
                for item in result for value in item.get("values", [])
            }
            return metric_values
        else:
            return {}

    except requests.exceptions.Timeout:
        print(f"Timeout fetching data from {url}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")

    return {}


def _fill_timestamps(metrics):
    if len(metrics) == 1 and isinstance(metrics[0], list):
        metrics = metrics[0]
    flat_metrics = []
    for i, item in enumerate(metrics, start=1):
        if isinstance(item, list):
            flat_metrics.extend(item)
        else:
            flat_metrics.append(item)
    key_sets = []
    for i, m in enumerate(flat_metrics, start=1):
        if isinstance(m, dict):
            keys = set(m.keys())
            key_sets.append(keys)
        else:
            print(f"DEBUG: Flat metric {i} is not a dict: {m}")

    if key_sets:
        all_timestamps = sorted(set().union(*key_sets))
    else:
        all_timestamps = []
    aligned_metrics = []
    for i, m in enumerate(flat_metrics, start=1):
        if isinstance(m, dict):
            aligned = [m.get(ts, None) for ts in all_timestamps]
            aligned_metrics.append(aligned)
        else:
            aligned_metrics.append(None)
    return all_timestamps, aligned_metrics


def _get_machine_stats(url, port, period, gpu_status):
    prometheus_url = f'http://{url}:{port}'
    start_time, end_time, step_size = _get_time_range(period)
    app_tz = CutilSettings.app_tz
    curr_tz = pytz.timezone(app_tz)

    # Initialize machine_stats with labels (to be filled later)
    machine_stats = {"labels": []}

    # Define metrics configuration dynamically
    metrics_config = [
        {
            "key": "cpu_utilization_data",
            "metric": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance) * 100)',
            "display_name": "CPU Utilization",
            "transform_type": 1,
            "data_key": "data"
        },
        {
            "key": "free_memory_data",
            "metric": 'node_memory_MemAvailable_bytes',
            "display_name": "Memory Usage",
            "transform_type": 2,
            "data_key": "data"
        },
        {
            "key": "total_memory_data",
            "metric": 'node_memory_MemTotal_bytes',
            "display_name": "Memory Usage",
            "transform_type": 2,
            "data_key": "data"
        },
        {
            "key": "free_disk_data",
            "metric": 'node_filesystem_free_bytes',
            "display_name": "Disk Usage",
            "transform_type": 2,
            "data_key": "data"
        },
        {
            "key": "total_disk_data",
            "metric": 'node_filesystem_size_bytes',
            "display_name": "Disk Usage",
            "transform_type": 2,
            "data_key": "data"
        },
        {
            "key": "top_process_cpu",
            "metric": 'topk(10, rate(namedprocess_namegroup_cpu_seconds_total[5m]) * 100)',
            "display_name": "Top Processes CPU",
            "transform_type": 1,
            "data_key": "data"
        },
        {
            "key": "top_process_memory",
            "metric": 'topk(10, namedprocess_namegroup_memory_bytes{memtype="resident"} / 1024 / 1024)',
            "display_name": "Top Processes Memory",
            "transform_type": 1,
            "data_key": "data"
        },
        {
            "key": "total_storage_data",
            "metric": 'node_filesystem_size_bytes{device=~"/dev/.*"} / 1024 / 1024 / 1024',
            "display_name": "Storage",
            "transform_type": 2,
            "data_key": "data"
        },
        {
            "key": "used_storage_data",
            "metric": '(node_filesystem_size_bytes{device=~"/dev/.*"} - node_filesystem_avail_bytes{device=~"/dev/.*"}) / 1024 / 1024 / 1024',
            "display_name": "Storage",
            "transform_type": 2,
            "data_key": "data"
        }
    ]

    # Add GPU metrics if Not None
    if gpu_status and str(gpu_status).strip() not in ['None', 'disabled']:
        metrics_config.extend([
            {
                "key": "gpu_utilization_data",
                "metric": f'avg(avg_over_time(DCGM_FI_DEV_GPU_UTIL[{step_size}]))',
                "display_name": "GPU Utilization",
                "transform_type": 1,
                "data_key": "data"
            },
            {
                "key": "free_gpu_memory_data",
                "metric": f'avg(avg_over_time(DCGM_FI_DEV_FB_FREE[{step_size}])) / 1024',
                "display_name": "GPU Memory",
                "transform_type": 1,
                "data_key": "data"
            },
            {
                "key": "used_gpu_memory_data",
                "metric": f'avg(avg_over_time(DCGM_FI_DEV_FB_USED[{step_size}])) / 1024',
                "display_name": "GPU Memory",
                "transform_type": 1,
                "data_key": "data"
            }
        ])

    special_metrics = ["top_process_cpu", "top_process_memory", "total_storage_data", "used_storage_data"]

    # Collect all raw metrics for timestamp alignment
    raw_metrics = []
    all_raw_data = {}

    # Process each metric configuration
    with ThreadPoolExecutor(max_workers=len(metrics_config)) as executor:
        future_to_config = {
            executor.submit(
                _fetch_machine_data,
                prometheus_url, config["metric"], start_time, end_time,
                step_size, config["key"], special_metrics
            ): config
            for config in metrics_config
        }

        for future in as_completed(future_to_config):
            config = future_to_config[future]
            try:
                all_raw_data[config["key"]] = future.result()
            except Exception as e:
                print(f"Error fetching {config['key']}: {e}")
                all_raw_data[config["key"]] = {}

    for config in metrics_config:
        raw_data = all_raw_data.get(config["key"], {})

        if config["key"] in special_metrics:
            machine_stats[config["key"]] = {
                "display_name": config["display_name"],
                config["data_key"]: raw_data
            }
        else:
            transformed_data = _transform_raw_data(raw_data, type=config["transform_type"])
            machine_stats[config["key"]] = {
                "display_name": config["display_name"],
                config["data_key"]: transformed_data
            }
            raw_metrics.append(raw_data if config["data_key"] == "data" else transformed_data)

    # Align all timestamps and set labels
    timestamps, _ = _fill_timestamps(raw_metrics)
    machine_stats["labels"] = [
        datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(curr_tz).strftime('%d-%b:%H')
        for ts in timestamps
    ]

    machine_stats = normalize_monitoring_data(machine_stats)
    return machine_stats

def cutil_get_machine_stats(machine_url,machine_port,period,gpu_status):
    machine_stats = {}
    try:
        machine_stats = _get_machine_stats(machine_url, machine_port, period,gpu_status)
        utils_logger.info(f"Successfully fetched stats from machine {machine_url, machine_port}")
    except Exception as e:
        utils_logger.error(f"Error fetching stats from machine {machine_url, machine_port}: {str(e)}")

    utils_logger.debug(f"Machine statistics: {machine_stats}")

    return machine_stats
