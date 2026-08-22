''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : ServiceMonitoring.py
* Description       : Functions related to monitoring the service
*
* Revision History  :
* Date				    Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-Jun-2024		Aniket Kaushik	            Created.
*
*********************************************************************************************************************'''


# Import System Libraries
import time
from datetime import datetime, date, timedelta
import pytz
import pandas as pd
from dateutil.relativedelta import relativedelta

# Import Logger
from .AppLogging import app_logger

from .AppStats import (
    appstats_get_counter_data,
    DATAFLOW_SUCCESS_STATS,
    DATAFLOW_FAILURE_STATS

)

'''----------------------------------------Service Monitoring Functions----------------------------------------------'''

def ctaw_map_period_to_dates(period):
    step_size = '1d'
    # Calculate the end date as the start of the current day
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'Last24h':
        # Set the end date to include the current day and adjust the step size to 1 hour
        end_date = end_date + timedelta(days=1)
        start_date = end_date + timedelta(hours=-24)
        step_size = '1h'
    elif period == '1Week':
        start_date = end_date + timedelta(weeks=-1)
    elif period == '1Month':
        start_date = end_date + relativedelta(months=-1)
    elif period == '2Month':
        start_date = end_date + relativedelta(months=-2)
    elif period == '3Month':
        start_date = end_date + relativedelta(months=-3)
    else:
        # Default to last 24 hours if period doesn't match any case
        end_date = end_date + timedelta(days=1)
        start_date = end_date + timedelta(hours=-24)
        step_size = '1h'

    # Format the start and end dates as ISO 8601 strings
    start_date_iso = start_date.replace(microsecond=0).isoformat() + 'Z'
    end_date_iso = end_date.replace(microsecond=0).isoformat() + 'Z'

    app_logger.debug(
        f"ctaw_map_period_to_dates, period={period}, start_date={start_date_iso}, end_date={end_date_iso}, step_size={step_size}"
    )
    return start_date_iso, end_date_iso, step_size


def _convert_dt_to_ist(dt):
    utc_zone = pytz.utc
    ist_zone = pytz.timezone('Asia/Kolkata')
    if dt.tzinfo is None:
        dt = utc_zone.localize(dt)
    return dt.astimezone(ist_zone)


def _transform_dataframe(df, start_date, end_date, date_format='%d-%b'):
    date_range = pd.date_range(start=start_date, end=end_date, freq='D').strftime(date_format)
    all_dates_df = pd.DataFrame({'date': date_range})

    if 'date' not in df.columns:
        df['date'] = pd.NaT
        df = df[df['date'].notna()]

    if 'stats' not in df.columns:
        df['stats'] = 0

    df_transformed = pd.merge(all_dates_df, df, on='date', how='left').fillna({'stats': 0})

    if 'period' in df_transformed.columns:
        df_transformed['period'] = pd.to_datetime(df_transformed['period'], errors='coerce')
    else:
        df_transformed['period'] = pd.NaT

    df_transformed['period'] = df_transformed['period'].fillna(
        pd.to_datetime(df_transformed['date'] + ' 00:00:00', format=f"{date_format} %H:%M:%S"))

    # Convert stats to integer
    df_transformed['stats'] = df_transformed['stats'].astype(int)

    df_transformed['period_ist'] = df_transformed['period'].apply(_convert_dt_to_ist)

    df_transformed['hour'] = df_transformed['period_ist'].dt.strftime('%d-%b:%H')

    return df_transformed

def _get_dataflow_stats(start_date, end_date, step_size):
    dataflow_success_df = appstats_get_counter_data(DATAFLOW_SUCCESS_STATS, start_date, end_date, step_size)
    dataflow_failure_df = appstats_get_counter_data(DATAFLOW_FAILURE_STATS, start_date, end_date, step_size)

    # Fill missing dates for each DataFrame
    dataflow_success_stats = _transform_dataframe(dataflow_success_df, start_date, end_date)
    dataflow_failure_stats = _transform_dataframe(dataflow_failure_df, start_date, end_date)

    labels = dataflow_success_stats['hour'].tolist() if step_size == '1h' else dataflow_success_stats['date'].tolist()

    dataflow_stats = {
        'labels': labels,
        'dataflow_success_stats': dataflow_success_stats['stats'].tolist() if len(dataflow_success_stats) != 0 else [],
        'dataflow_failure_stats': dataflow_failure_stats['stats'].tolist() if len(dataflow_failure_stats) != 0 else []
    }
    app_logger.debug(f'_get_dataflow_stats: dataflow_stats={dataflow_stats}')
    return dataflow_stats


def ctaw_service_stats(period):

    start_date, end_date, step_size = ctaw_map_period_to_dates(period)
    dataflow_stats = _get_dataflow_stats(start_date, end_date, step_size)

    # Gather Register Statistics
    stats_info = {
        "labels": dataflow_stats.get("labels", []),
        "Dataflow Success Stats": {
            "display_name": "Dataflow Stats",
            "data": dataflow_stats.get('dataflow_success_stats', []),
        },
        "Dataflow Failure Stats": {
            "display_name": "Dataflow Stats",
            "data": dataflow_stats.get('dataflow_failure_stats', []),
        }
    }
    return stats_info
