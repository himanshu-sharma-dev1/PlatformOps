'''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : serviceEvent.py
* Description       : Functions related to Service Events
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-march-25                  YashKumar                        Created.
* 26-april-25                  Sumit Das                        Updated.
*
*********************************************************************************************************************'''

# Import Modules
from datetime import datetime, timedelta
from cPlatformIO.models import ServiceEvent
from cPlatform.AppLogging import app_logger


def service_get_event_info(service_id):

    app_logger.info(f" service_get_event_info, service_id={service_id}")
    index, service_event_info = 0, {}

    event_instance = ServiceEvent.objects.filter(service__service_id=service_id).order_by('-event_date', '-event_time')
    for event in event_instance:
        index = index + 1
        service_event_info[index] = {}
        service_event_info[index]['Event_Date'] = event.event_date.strftime("%Y-%m-%d")
        service_event_info[index]['Event_Time'] = event.event_time.strftime("%H:%M")
        service_event_info[index]['Event_Msg'] = f"{event.event_trigger}-{event.event_msg}"

    app_logger.info(f"service_event_info={service_event_info}")
    service_event_info = list(service_event_info.values())
    return service_event_info


def service_get_latest_event_info(service_id):
    app_logger.info(f" service_get_latest_event_info, service_id={service_id}")

    event = ServiceEvent.objects.filter(service__service_id=service_id).order_by('-event_date', '-event_time').first()
    if not event:
        return {}

    return {
        "event_date": event.event_date.strftime("%Y-%m-%d"),
        "event_time": event.event_time.strftime("%H:%M"),
        "event_at": f"{event.event_date.strftime('%Y-%m-%d')} {event.event_time.strftime('%H:%M')}",
        "event_trigger": event.event_trigger or "",
        "event_msg": f"{event.event_trigger}-{event.event_msg}" if event.event_trigger else (event.event_msg or ""),
    }


def service_get_event_info_window(service_id, hours=24, limit=50):
    app_logger.info(f"service_get_event_info_window, service_id={service_id}, hours={hours}, limit={limit}")

    start_at = datetime.now() - timedelta(hours=hours)
    event_rows = []

    event_instance = ServiceEvent.objects.filter(service__service_id=service_id).order_by('-event_date', '-event_time')
    for event in event_instance:
        event_at = datetime.combine(event.event_date, event.event_time)
        if event_at < start_at:
            continue

        event_rows.append({
            "event_date": event.event_date.strftime("%Y-%m-%d"),
            "event_time": event.event_time.strftime("%H:%M"),
            "event_at": event_at.strftime("%Y-%m-%d %H:%M"),
            "event_trigger": event.event_trigger or "",
            "event_severity": event.event_severity or "",
            "event_msg": f"{event.event_trigger}-{event.event_msg}" if event.event_trigger else (event.event_msg or ""),
        })

        if len(event_rows) >= limit:
            break

    return event_rows


def service_event_add_request(ser_ins, event_trigger, msg):
    app_logger.info(f" service_event_add_request, service_id, Trigger, msg={ser_ins.service_id, event_trigger, msg}")
    error_severity = "Medium"
    safe_trigger = str(event_trigger or "")[:100]
    safe_msg = str(msg or "")[:200]

    event_instance = ServiceEvent.objects.create(service=ser_ins, event_msg=safe_msg,
                                                 event_date=datetime.now().date(),
                                                 event_time=datetime.now().time(),
                                                 event_trigger=safe_trigger,
                                                 event_severity=error_severity
                                                 )
    event_instance.save()
    return



