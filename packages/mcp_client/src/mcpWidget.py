''''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : mcpWidget.py
* Description       : Functions related to MCP Widget Management
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 10-Sept-25 		Anu		            Created.

*********************************************************************************************************************'''
import json
import uuid
import redis
import pytz
import requests
import markdown
from datetime import datetime
from asgiref.sync import async_to_sync
from celery import shared_task
from MCPClient.src import mcpClient
from django.template.loader import render_to_string
from CommonUtils.timer import TimerMgr
from CommonUtils.com.EmailMgr import cutil_send_email
from MCPClient.mcpSetting import mcpSettings
from MCPClient.logs.AppLogging import mcpcl_logger
from CommonUtils.timer.TimerMgr import cutil_timer_crontab_start, cutil_timer_stop



@shared_task
def mcp_widget_timeout_handler(req_info):
    mcpcl_logger.debug(f"mcp_widget_timeout_handler, req_info={req_info}")
    try:
        requests.post(url=mcpSettings.report_url, json=req_info, timeout=60, verify=False)
        mcpcl_logger.debug(f"Internal Message Dispatched for url ={mcpSettings.report_url} msg={req_info}")
    except Exception as e:
        pass
    mcpcl_logger.debug(f"schedule_report_request")
    return


# ---------- Redis Client ----------

def _get_redis_client():
    return redis.Redis(host=mcpSettings.redis_server_ip, port=mcpSettings.redis_server_port, decode_responses=True)


def _add_widget_info(user_id, widget_info):
    expected_keys = ['widget_name', 'start_date', 'time', 'time_zone', 'periodicity', 'emails', 'question','session_info','user_info']
    widget_info = {k: widget_info[k] for k in expected_keys if k in widget_info}
    current_time = TimerMgr.cutil_timer_get_app_curr_time().strftime('%d-%b-%y %H:%M:%S')
    widget_info.update({'current_time': current_time})

    client = _get_redis_client()
    pipe = client.pipeline()
    pipe.rpush(f"{user_id}-{widget_info['widget_name']}", json.dumps(widget_info))
    pipe.execute()
    return


def _delete_widget_info(user_id, widget_name):
    client = _get_redis_client()
    client.delete(f"{user_id}-{widget_name}", 0, -1)
    return


def _chk_widget_exists(user_id, widget_name):
    client = _get_redis_client()
    if client.exists(f"{user_id}-{widget_name}"):
        return True
    return False


def _start_widget_timer(widget_info):
    timer_name = "WIDGET_TIMER-" + str(widget_info['widget_name'])
    cutil_timer_crontab_start(timer_name, widget_info,
                              'MCPClient.src.mcpWidget.mcp_widget_timeout_handler', widget_info['start_date'],
                              widget_info['time']+':00', widget_info['time_zone'], widget_info['periodicity'],
                              mcpSettings.report_queue)
    return


def _stop_widget_timer(user_id,widget_name):
    mcpcl_logger.debug(f"debug, user_id ={user_id} widget_name = {widget_name}")
    timer_name ="WIDGET_TIMER" + "-" + str(user_id + "-" + str(widget_name))
    cutil_timer_stop(timer_name)
    return


def _validate_date_parameter(start_date, time, timezone):
    if time is not None and start_date is not None and timezone is not None:
        # Get the request datetime
        request_datetime = datetime.strptime(start_date + " " + time, "%Y-%m-%d %H:%M")
        request_datetime = pytz.timezone(timezone).localize(request_datetime)

        # Get the current datetime
        current_datetime = TimerMgr.cutil_timer_get_app_curr_time()

        # Compare the two datetime
        if request_datetime < current_datetime:
            return False
    return True

def _generate_context(widget_info):
    res_time = TimerMgr.cutil_timer_get_app_curr_time()
    user_history={"question": widget_info['question'], "response": '',
                  "question_id": str(uuid.uuid4()),"response_time": res_time.strftime("%d-%m-%Y %H:%M:%S")}
    user_session = widget_info['session_info']
    user_info = widget_info["user_info"]

    ret,resp = async_to_sync(mcpClient.run_mcp_workflow)(user_info, user_session, str("Query: " + widget_info['question']))

    if ret:
        user_history.update({"response": resp})
    return ret, user_history


def _prepare_email(user_history,req_info):
    ## Remove all hardcoding from this function
    response_html = markdown.markdown(user_history["response"], extensions=["tables", "fenced_code"])

    user_history["response_html"] = response_html
    mail_subject = f"{req_info['widget_name']} {req_info['periodicity']} Report - {user_history['question']}"
    mail_body = render_to_string(mcpSettings.template_name, {"user_history": user_history})
    return mail_subject, mail_body

# ---------- Main Function Logic ----------

def mcp_widget_add(user_id, widget_info):
    mcpcl_logger.debug(f'add_user_widget-widget_info:{widget_info}')
    expected_keys = ['widget_name', 'start_date', 'time', 'time_zone', 'periodicity', 'emails', 'question','session_info','user_info']
    if not set(expected_keys).issubset(set(widget_info.keys())):
        return False, f"Widget Add Failure! Expected keys are missing!"

    # Validate for duplicate widget name
    if _chk_widget_exists(user_id, widget_info.get('widget_name')):
        return False, f"Widget Add Failure! Duplicate Name!"

    # Validate Schedule is valid
    if not _validate_date_parameter(widget_info.get('start_date'), widget_info.get('time'),
                                    widget_info.get('time_zone')):
        mcpcl_logger.error(f"Widget Add Failure! Invalid Date Time !request:{widget_info}")
        return False, f"Widget add Failure! Invalid Date Time !"

    # Email Check
    if not widget_info.get('emails'):
        mcpcl_logger.error(f"Widget Add Failure! Not Valid Email:{widget_info}")
        return False, f"Widget add Failure! Not Valid Email!"

    _add_widget_info(user_id, widget_info)
    widget_info["user_id"] = user_id
    _start_widget_timer(widget_info)
    mcpcl_logger.debug(f"Widget added successfully and timer started!")
    return True, f"Widget added successfully!"


def mcp_fetch_user_widgets(user_id):
    mcpcl_logger.debug(f"get_widget_info : {user_id}")
    client = _get_redis_client()
    widget_info = []
    # Get all stored raw messages
    for key in client.scan_iter(match=f"{user_id}-*"):
        # key = key.decode()
        widget = client.lrange(key, 0, -1)[0]
        try:
            widget = json.loads(widget)
            widget['email_list'] = json.loads(widget['emails'])
            widget['type'] = widget['periodicity']
            widget['name'] = f"{widget['widget_name']} - {widget['periodicity']} Report"
            widget_info.append(widget)
        except json.JSONDecodeError:
            continue

    return widget_info


def mcp_get_widget_info(user_id, widget_name):
    if not _chk_widget_exists(user_id, widget_name):
        return False,{}
    client = _get_redis_client()
    widget = client.lrange(f"{user_id}-{widget_name}", 0, -1)[0]

    if isinstance(widget, bytes):
        widget = widget.decode("utf-8")
    widget = json.loads(widget)

    widget['email_list'] = json.loads(widget['emails'])
    widget['type'] = widget['periodicity']
    widget['widget_name'] = f"{widget['widget_name']} - {widget['periodicity']} Report"
    return True,widget

    
def mcp_widget_edit(user_id, widget_info):
    mcpcl_logger.debug(f'edit_user_widget user_id:{user_id} widget_info:{widget_info}')
    expected_keys = ['widget_name', 'start_date', 'time', 'time_zone', 'periodicity', 'emails', 'question','session_info','user_info']

    if not set(expected_keys).issubset(set(widget_info.keys())):
        mcpcl_logger.error(f"Widget edit Failure! Expected keys are missing !request:{widget_info}")
        return False, f"Widget edit Failure! Expected keys are missing !"

    ret, msg = mcp_widget_delete(user_id, widget_info['widget_name'])

    if ret:
        ret, msg = mcp_widget_add(user_id, widget_info)
        widget_info["user_id"] = user_id
        _start_widget_timer(widget_info)
        msg = msg.replace('add', 'edit')

    return ret, msg


def mcp_widget_delete(user_id, widget_name):
    mcpcl_logger.debug(f'mcp_widget_delete req:{user_id, widget_name}')
    if not _chk_widget_exists(user_id, widget_name):
        return False,'Widget delete Failure! Widget not exist!!'
    
    _delete_widget_info(user_id, widget_name)
    _stop_widget_timer(user_id,widget_name)

    return True, f"Widget deleted successfully!"


def mcp_widget_mail_handler(req_info):
    mcpcl_logger.debug(f"mcp_widget_mail_handler: {req_info}")

    # Generate the report file
    ret,user_history = _generate_context(req_info)
    if not ret:
        mcpcl_logger.error("Widget mail failed: Response could not be generated")
        return
    # Prepare email details
    email_list = json.loads(req_info.get("emails", ""))

    mail_subject, mail_body = _prepare_email(user_history, req_info)

    # Send email with report attached
    ret, msg = cutil_send_email(mail_subject, mail_body, email_list)
    mcpcl_logger.debug(f"ret -{ret},msg-  {msg}")
    if not ret:
        mcpcl_logger.error(f"Email sending failed: {msg}")
    return


