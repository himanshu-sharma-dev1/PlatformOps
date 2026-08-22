'''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : NodeEvent.py
* Description       : Functions related to Node Events
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 25-June-25                  Yashveer                        Created.
*
*********************************************************************************************************************'''

# Import Modules
from datetime import datetime
from cPlatformIO.models import NodeEvent
from cPlatform.AppLogging import app_logger


def node_get_event_info(node_id):

    app_logger.info(f" node_get_event_info, node_id={node_id}")
    index, node_event_info = 0, {}

    event_instance = NodeEvent.objects.filter(node__node_id=node_id).order_by('-event_date', '-event_time')
    for event in event_instance:
        index = index + 1
        node_event_info[index] = {}
        node_event_info[index]['Event_Date'] = event.event_date.strftime("%Y-%m-%d")
        node_event_info[index]['Event_Time'] = event.event_time.strftime("%H:%M")
        node_event_info[index]['Event_Msg'] = f"{event.event_trigger}-{event.event_msg}"

    app_logger.info(f"node_event_info={node_event_info}")
    node_event_info = list(node_event_info.values())
    return node_event_info


def node_event_add_request(node_ins, event_trigger, msg):
    app_logger.info(f" node_event_add_request, node_id, Trigger, msg={node_ins.node_id, event_trigger, msg}")
    error_severity = "Medium"

    event_instance = NodeEvent.objects.create(node=node_ins, event_msg=msg,
                                                 event_date=datetime.now().date(),
                                                 event_time=datetime.now().time(),
                                                 event_trigger=event_trigger,
                                                 event_severity=error_severity
                                                 )
    event_instance.save()
    return



