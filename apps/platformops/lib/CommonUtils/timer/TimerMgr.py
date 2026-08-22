''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : TimeMgr.py
* Description       : Common Utility Module supporting periodic timers
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
*
*********************************************************************************************************************'''

import json
import pytz
import datetime

import requests
from celery import shared_task
from CommonUtils.CutilSetting import CutilSettings
from datetime import datetime, time, date,timedelta
from CommonUtils.logs.AppLogging import utils_logger
from django_celery_beat.models import CrontabSchedule, PeriodicTask, ClockedSchedule
# --------------------------------------- New Timer Functions -------------------------------------------------

def _convert_to_app_tz(start_date, start_time, timezone):

    sys_timezone = CutilSettings.app_tz

    # Create timezone objects
    input_tz = pytz.timezone(timezone)
    system_tz = pytz.timezone(sys_timezone)

    # Ensure date_str is a string and convert to datetime.date if necessary
    if isinstance(start_date, str):
        date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, date):
        date_obj = start_date
    else:
        raise ValueError("date_str must be a string or a datetime.date object")

    # Ensure time_str is a string and convert to datetime.time if necessary
    if isinstance(start_time, str):
        time_obj = datetime.strptime(start_time, '%H:%M:%S').time()
    elif isinstance(start_time, time):
        time_obj = start_time
    else:
        raise ValueError("time_str must be a string or a datetime.time object")

    # Combine date and time to create a datetime object
    dt = datetime.combine(date_obj, time_obj)

    # Localize the datetime object with the input timezone
    localized_dt = input_tz.localize(dt)

    # Convert the localized datetime to the system's timezone
    system_dt = localized_dt.astimezone(system_tz)

    # Format the system timezone datetime as a string
    app_dt = system_dt.strftime('%Y-%m-%d %H:%M:%S')

    return app_dt


def cutil_timer_init(app_tz, service_url=''):
    """
    Setting up timer initialization.
    Args:
        app_tz (str): App Timezone

     Returns:
        tuple: (bool, MIMEMultipart or str) – success status and message or error string.
    """
    utils_logger.debug(f"cutil_timer_init request : app_tz {app_tz}")
    timezone_list = ['US/Eastern', 'US/Central', 'US/Pacific', 'Europe/London',
                     'UTC', 'Europe/Belgrade', 'Asia/Kolkata','America/New_York']
    CutilSettings.service_url = service_url
    if app_tz in timezone_list:
        CutilSettings.app_tz = app_tz
        return True, "Initialization Complete"
    return False, f"Invalid Timezone, valid timezone list: {timezone_list}"


def cutil_timer_stop(timer_name):
    utils_logger.debug(f"cutil_timer_stop: timer_name={timer_name}")

    if PeriodicTask.objects.filter(name=timer_name).exists():
        PeriodicTask.objects.get(name=timer_name).delete()
    return


def cutil_timer_crontab_start(timer_name, timer_arg, timeout_task, start_date, start_time, time_zone, periodicity, queue):
    # timer_name should be unique timer name , timer_arg can be single field or dictionary.
    # periodicity can be ONCE, HOURLY, DAILY, WEEKLY, MONTHLY

    utils_logger.debug(f"cutil_timer_crontab_start: "
                       f"timer_name, timer_arg, timeout_task, start_date, start_time, periodicity, time_zone, queue"
                       f"{timer_name, timer_arg, timeout_task, start_date, start_time, periodicity, time_zone, queue}")

    if isinstance(start_date, str):
        r_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, date):
        r_date = start_date
    else:
        raise ValueError("start_date must be a string or a datetime.date object")

    if isinstance(start_time, str):
        r_time = datetime.strptime(start_time, '%H:%M:%S').time()
    elif isinstance(start_time,time):
        r_time = start_time
    else:
        raise ValueError("start_time must be a string or a datetime.time object")

    if periodicity not in ['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY','ONCE', '5m', '15m']:
        raise ValueError("Invalid periodicity for the timer")

    # Stop Timer if exists for this timer_type, timer_arg
    cutil_timer_stop(timer_name)
    r_min, r_hour, r_weekday, r_day = r_time.strftime('%M'), r_time.strftime('%H'), r_date.strftime('%w'), r_date.day
    if periodicity == 'HOURLY':
        r_hour, r_weekday, r_day = '*', '*', '*'
    elif periodicity == 'DAILY':
        r_weekday, r_day = '*', '*'
    elif periodicity == 'WEEKLY':
        r_day = '*'
    elif periodicity == 'MONTHLY':
        r_weekday = '*'
    elif periodicity == '5m':
        # Every 5 minutes
        r_min = "*/5"
        r_hour = "*"
        r_weekday = "*"
        r_day = "*"

    elif periodicity == '15m':
        # Every 15 minutes
        r_min = "*/15"
        r_hour = "*"
        r_weekday = "*"
        r_day = "*"
    if periodicity == "ONCE":
        run_at = datetime.combine(r_date, r_time)

        clocked, _ = ClockedSchedule.objects.get_or_create(
            clocked_time=run_at
        )

        PeriodicTask.objects.create(
            name=timer_name,
            task=timeout_task,
            clocked=clocked,
            start_time=run_at,
            one_off=True,
            enabled=True,
            args=json.dumps([timer_arg]),
            queue=queue,
        )
        return
    # Create Crontab Schedule to be used for starting Periodic Task
    cron_schedule, _ = CrontabSchedule.objects.get_or_create(minute=r_min, hour=r_hour, day_of_week=r_weekday,
                                                             day_of_month=r_day, month_of_year='*', timezone=time_zone)

    # Change the localized time into UTC time
    app_start_time = _convert_to_app_tz(start_date, start_time, time_zone)

    # Start Periodic Task using cronTab schedule
    one_off = True if periodicity == "ONCE" else False
    PeriodicTask.objects.create(crontab=cron_schedule, name=timer_name, task=timeout_task, args=json.dumps([timer_arg]),
                                start_time=app_start_time, one_off=one_off, queue=queue)

    return

def cutil_timer_interval_start(timer_name, timer_arg, timeout_task, minutes, queue):

    # Interval timer is one off timer. Application need to start new timer at timeout if needed
    utils_logger.debug(f"cutil_timer_interval_start, timer_name, timer_arg, timeout_task, minutes, queue:"
                       f" {timer_name, timer_arg, timeout_task, minutes, queue}")

    cutil_timer_stop(timer_name)     # Stop timer if running
    # Create Crontab Schedule for Interval Timer
    app_tz = CutilSettings.app_tz
    int_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=f"*/{minutes}",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=pytz.timezone(app_tz),
    )
       # Start New Interval Timer
    app_start_time = cutil_timer_get_app_curr_time()
    PeriodicTask.objects.create(crontab=int_schedule, name=timer_name, task=timeout_task, args=json.dumps([timer_arg]),
                                start_time=app_start_time, one_off=False, queue=queue)
    return


def cutil_timer_get_app_curr_time():
    system_tz = pytz.timezone(CutilSettings.app_tz)
    app_curr_time = datetime.now(system_tz)    # Get current
    # utils_logger.debug(f"cutil_timer_get_app_curr_time: {app_curr_time}")
    return app_curr_time

def commonutils_crontab_timer_disable(timer_type, timer_arg):
    timer_name = str(timer_type) + '-' + str(timer_arg)
    if PeriodicTask.objects.filter(name=timer_name).exists():
        task_instance = PeriodicTask.objects.get(name=timer_name)
        task_instance.enabled = False
        task_instance.save()
    return


def commonutils_crontab_timer_enable(timer_type, timer_arg):
    timer_name = str(timer_type) + '-' + str(timer_arg)
    if PeriodicTask.objects.filter(name=timer_name).exists():
        task_instance = PeriodicTask.objects.get(name=timer_name)
        task_instance.enabled = True
        task_instance.save()
    return


@shared_task
def common_crontab_handler(timer_arg):
    """
    Common handler for crontab tasks.
    Expected timer_arg structure: {'endpoint': 'endpoint/path', 'argument': ...}
    Triggers an HTTP POST request to {CutilSettings.service_url}/{endpoint}/ with argument as payload.
    """
    utils_logger.debug(f"common_crontab_handler triggering with: {timer_arg}")
    try:
        # Handle if timer_arg is passed as JSON string
        if isinstance(timer_arg, str):
            timer_data = json.loads(timer_arg)
        else:
            timer_data = timer_arg

        endpoint = timer_data.get('endpoint')
        argument = timer_data.get('argument')

        if not endpoint:
            utils_logger.error("Endpoint not found in timer arguments for common handler")
            return

        if not isinstance(argument, dict):
            utils_logger.error("Argument is not a dictionary in timer arguments for common handler")
            return
        service_url = CutilSettings.service_url
        if not service_url:
            utils_logger.error("service_url not configured in CutilSettings")
            return

        # Construct URL
        # Ensure no double slashes if service_url ends with / or endpoint starts with /
        base = service_url.rstrip('/')
        path = endpoint.lstrip('/')
        url = f"{base}/{path}/"

        utils_logger.debug(f"Making POST request to {url} with payload: {argument}")

        try:
            requests.post(url=url, json=argument, timeout=60, verify=False)
        except Exception as e:
            utils_logger.error(f"Error requesting {url}: {e}")

    except Exception as e:
        utils_logger.error(f"Error executing common_crontab_handler: {e}")


def cutil_timer_common_crontab_start(timer_name, timer_arg, start_date, start_time, time_zone, periodicity, queue):
    """
    Starts a crontab timer that uses the common_crontab_handler.
    timer_arg MUST be a dictionary containing 'endpoint' and 'argument'.
    """
    utils_logger.debug(f"cutil_timer_common_crontab_start: "
                       f"timer_name, timer_arg, start_date, start_time, periodicity, time_zone, queue"
                       f"{timer_name, timer_arg, start_date, start_time, periodicity, time_zone, queue}")

    # Validate timer_arg structure
    if not isinstance(timer_arg, dict) or 'endpoint' not in timer_arg or 'argument' not in timer_arg:
        raise ValueError("timer_arg must be a dict with 'endpoint' and 'argument' keys")

    if not isinstance(timer_arg['argument'], dict):
        raise ValueError("timer_arg['argument'] must be a dictionary")

    if isinstance(start_date, str):
        r_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, date):
        r_date = start_date
    else:
        raise ValueError("start_date must be a string or a datetime.date object")

    if isinstance(start_time, str):
        r_time = datetime.strptime(start_time, '%H:%M:%S').time()
    elif isinstance(start_time, time):
        r_time = start_time
    else:
        raise ValueError("start_time must be a string or a datetime.time object")

    if periodicity not in ['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', 'ONCE', '5m', '15m']:
        raise ValueError("Invalid periodicity for the timer")

    # Stop Timer if exists
    cutil_timer_stop(timer_name)

    r_min, r_hour, r_weekday, r_day = r_time.strftime('%M'), r_time.strftime('%H'), r_date.strftime('%w'), r_date.day
    if periodicity == 'HOURLY':
        r_hour, r_weekday, r_day = '*', '*', '*'
    elif periodicity == 'DAILY':
        r_weekday, r_day = '*', '*'
    elif periodicity == 'WEEKLY':
        r_day = '*'
    elif periodicity == 'MONTHLY':
        r_weekday = '*'
    elif periodicity == '5m':
        r_min = "*/5"
        r_hour = "*"
        r_weekday = "*"
        r_day = "*"

    elif periodicity == '15m':
        r_min = "*/15"
        r_hour = "*"
        r_weekday = "*"
        r_day = "*"

    # Create Crontab Schedule
    cron_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=r_min, hour=r_hour, day_of_week=r_weekday,
        day_of_month=r_day, month_of_year='*', timezone=time_zone
    )

    # Change the localized time into UTC time
    app_start_time = _convert_to_app_tz(start_date, start_time, time_zone)

    # Hardcoded task name for the common handler
    # Assuming this file's module path is CommonUtils.timer.TimerMgr
    timeout_task = 'CommonUtils.timer.TimerMgr.common_crontab_handler'

    # Start Periodic Task
    one_off = True if periodicity == "ONCE" else False
    PeriodicTask.objects.create(
        crontab=cron_schedule,
        name=timer_name,
        task=timeout_task,
        args=json.dumps([timer_arg]),
        start_time=app_start_time,
        one_off=one_off,
        queue=queue
    )

    return


def cutil_timer_common_interval_start(timer_name, timer_arg, minutes, queue, one_off=False):
    """
    Starts an interval timer that uses the common_crontab_handler.
    timer_arg MUST be a dictionary containing 'endpoint' and 'argument'.
    """
    utils_logger.debug(f"cutil_timer_common_interval_start, timer_name, timer_arg, minutes, queue:"
                       f" {timer_name, timer_arg, minutes, queue}")

    # Validate timer_arg structure
    if not isinstance(timer_arg, dict) or 'endpoint' not in timer_arg or 'argument' not in timer_arg:
        raise ValueError("timer_arg must be a dict with 'endpoint' and 'argument' keys")

    if not isinstance(timer_arg['argument'], dict):
        raise ValueError("timer_arg['argument'] must be a dictionary")

    cutil_timer_stop(timer_name)  # Stop timer if running

    # Create Crontab Schedule for Interval Timer
    app_tz = CutilSettings.app_tz
    int_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=f"*/{minutes}",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=pytz.timezone(app_tz),
    )

    # Use the common handler
    timeout_task = 'CommonUtils.timer.TimerMgr.common_crontab_handler'

    # Start New Interval Timer
    app_start_time = cutil_timer_get_app_curr_time()

    PeriodicTask.objects.create(
        crontab=int_schedule,
        name=timer_name,
        task=timeout_task,
        args=json.dumps([timer_arg]),
        start_time=app_start_time,
        one_off=False,
        queue=queue
    )
    return

