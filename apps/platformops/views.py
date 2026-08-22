import os
import json
import requests
import jsonschema
# from django.contrib.auth import login
from django.views import View
from django.conf import settings
from jsonmerge import SchemaError
from django.contrib import messages
from jsonschema.validators import validate
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.http import JsonResponse, HttpResponse, FileResponse
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate
from .models import InviteToken, Cluster, Node, Service, UserInfo
from CommonUtils.auth.AuthMgr import admin_only
from CommonUtils.dformSchema import getSchema
from CommonUtils.restapi.RestApiMgr import commonutils_restapi_request_decode
from CommonUtils.stats import MachineStats, ServiceStats

from cPlatformIO.src import (
    AppConfig, ClusterConfig, UserMgmnt, ServiceConfig, NodeConfig,
    serviceEvent, NodeEvent, Cutilinit, ServiceDiagnostics,
    systemMonitoring
)

from cPlatform import ServiceMonitoring
from cPlatform.AppLogging import app_logger
from cPlatformIO.src.PlatformSetting import PlatformSettings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import yaml
# Base directory
BASE_DIR = settings.NEW_BASE_DIR


class LicenseFailView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'Reporting/LicenseFail.html')


class UserLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        # Check if device is mobile
        print(f"request.POST=={self.request.POST}")
        is_mobile = self.request.POST.get('is_mobile')
        user_mail = form.cleaned_data.get('username')
        UserMgmnt.user_check_self_create(user_mail)  # Check and Self Create User in absent

        user_ins = UserMgmnt.user_get_instance__mail(user_mail)
        if user_ins.user_role == 'System_Admin' and is_mobile == 'true':
            from django.contrib import messages
            messages.error(self.request, "Admin login from mobile is not allowed.")
            return redirect('license_fail')

        response = super().form_valid(form)

        # res = UserMgmnt.user_license_validated(user_mail)
        # if not res:
        #     print("License validation failed after login. Redirecting to license_fail.")
        #     return redirect('license_fail')

        user_result = UserMgmnt.user_login_count_increment(user_mail)
        app_logger.debug(f"User login count increment result: {user_result}")

        return response


def _cplatform_schema_validation(api_name, api_info):
    app_logger.debug(f"_cplatform_schema_validation, api_name={api_name}, api_info={api_info}")

    json_file = os.path.join(settings.BASE_DIR, 'config/cPlatform_interface_schema.json')
    config_dic = json.load(open(json_file))
    api_schema = config_dic[api_name]

    try:
        validate(instance=api_info, schema=api_schema)
    except SchemaError as e:
        app_logger.info(f"There is an error with the schema, api_name={api_name}, Error={e}")
        return False, {}
    except jsonschema.exceptions.ValidationError as err:
        app_logger.info(f"Rest Api JsonSchema, api_name={api_name}, Error=={err}")
        return False, {}
    return True, {}


def _cplatform_common_api_validation(request, api_name):
    request_info = commonutils_restapi_request_decode(request)
    app_logger.debug(f"_cplatform_common_api_validation: request={request_info}")

    # Validate Received Message Schema

    ret, context = _cplatform_schema_validation(api_name, request_info)
    if not ret:
        return 400, "Invalid Json Schema", request_info

    return 200, "", request_info


# @csrf_exempt
# def cPlatformIO_dataflow_log(request):
#     if request.method == "POST":
#         app_logger.info(f" request.POST = {request.POST}")
#         dataflow_id = request.POST.get('dataflow_id')
#         dataflow_log = MultiDataflowMgmt.cPlatformIO_get_multi_task_log(dataflow_id)
#         return JsonResponse(status=200, data=dataflow_log)


@csrf_exempt
def cPlatformIO_batch_ingress_view(request):
    def _is_json_request(req):
        return 'application/json' in (req.content_type or '').lower()

    def _load_request_info(req):
        if _is_json_request(req):
            try:
                return json.loads(req.body.decode('utf-8') or '{}')
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}

        json_data = req.POST.get('json_data')
        if json_data:
            try:
                return json.loads(json_data)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return {}

    def _success_payload(ret_msg):
        text = str(ret_msg or '').lower()
        failed_tokens = ['failure', 'invalid', 'unable', 'already exists', 'does not exist', 'failed']
        return not any(token in text for token in failed_tokens)

    if request.method == "POST":
        app_logger.info(f"Received POST request with data: {request.POST}")
        full_payload = _load_request_info(request)
        dataflow_action = full_payload.get('user-action', request.POST.get('user-action'))

        request_info = full_payload.get('request_info', full_payload.get('json_data', full_payload))
        if isinstance(request_info, str):
            try:
                request_info = json.loads(request_info)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        is_json_req = _is_json_request(request)

        if dataflow_action == 'add':
            ret_msg = DataflowMgmt.dataflow_add_request(request_info)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow add request processed successfully with message: {ret_msg}")

            new_id = None
            if _success_payload(ret_msg):
                try:
                    from cPlatformIO.models import DataflowBatchConfig
                    df = DataflowBatchConfig.objects.get(dataflow_name=request_info.get('dataflow_name'))
                    new_id = df.dataflow_id
                except Exception:
                    pass

            if is_json_req:
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg, 'dataflow_id': new_id})

        elif dataflow_action == 'edit':
            ret_msg = DataflowMgmt.dataflow_edit_request(request_info)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow edit request processed successfully with message: {ret_msg}")
            if is_json_req:
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg})

        elif dataflow_action == 'scheduled_rerun':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            eval_dates = full_payload.get('eval_dates', [])          # list of date strings
            scheduled_date = full_payload.get('scheduled_date')      # e.g. "2026-06-07"
            scheduled_time = full_payload.get('scheduled_time')      # e.g. "10:00"
            try:
                ret_msg = DataflowMgmt.dataflow_scheduled_rerun_request(dataflow_id, eval_dates, scheduled_date, scheduled_time)
                messages.success(request, ret_msg)
                app_logger.info(f"Dataflow scheduled_rerun request processed successfully with message: {ret_msg}")
                if is_json_req:
                    return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg})
            except Exception as e:
                app_logger.error(f"scheduled_rerun exception: {e}", exc_info=True)
                if is_json_req:
                    return JsonResponse({'success': False, 'message': f'Rerun failed: {str(e)}'}, status=500)
                raise

        elif dataflow_action == 'delete':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            ret_msg = DataflowMgmt.dataflow_delete_request(dataflow_id)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow delete request processed successfully with message: {ret_msg}")
            if is_json_req:
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg})

        elif dataflow_action == 'dataflow_log':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            dataflow_type = full_payload.get('dataflow_type', request.POST.get('dataflow_type'))
            dataflow_logs = DataflowMgmt.dataflow_get_log_info(dataflow_id, dataflow_type)
            app_logger.info("Dataflow log retrieved successfully")
            return JsonResponse(dataflow_logs, safe=False)

        elif dataflow_action == 'bulletin_board':
            logs_instances = DataflowMgmt.dataflow_get_bulletin_info()
            app_logger.info("Last 24 hrs logs retrieved successfully")
            return JsonResponse(logs_instances, safe=False)

        elif dataflow_action == 'dataflow_summary':
            dataflow_summary = DataflowMgmt.dataflow_get_summary_report()
            app_logger.info("Dataflow summary report retrieved successfully")
            return JsonResponse(dataflow_summary, safe=False)

        elif dataflow_action == 'get_data_status':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            circle = full_payload.get('circle', request.POST.get('circle', ''))
            dataflow_type = full_payload.get('dataflow_type', request.POST.get('dataflow_type', ''))
            start_date = full_payload.get('start_date', request.POST.get('start_date', ''))
            end_date = full_payload.get('end_date', request.POST.get('end_date', ''))
            app_logger.info(
                f"get_data_status: dataflow_id={dataflow_id}, circle={circle}, dataflow_type={dataflow_type}, "
                f"start_date={start_date}, end_date={end_date}"
            )
            result = DataflowMgmt.dataflow_get_data_status(circle, dataflow_type, start_date, end_date, dataflow_id=dataflow_id)
            return JsonResponse(result, safe=False)

    # Log INFO to record data retrieval process for the view
    app_logger.info("Retrieving dataflow configuration and options")

    # Get information for dataflow configuration and listing
    dataflow_info = DataflowMgmt.dataflow_get_info()
    app_logger.debug(f"Retrieved dataflow_info: {dataflow_info}")

    dataflow_type_config = DataflowMgmt.dataflow_get_type_config()

    training_info = ClusterConfig.cluster_get_service_list(None, "TrainingServer")

    ans_info = ClusterConfig.cluster_get_service_list(None, "ANS")

    opcop_info = ClusterConfig.cluster_get_service_list(None, "optionCopilot")

    application_info = ServiceConfig.service_get_application_info()

    # Calculate summary metrics
    ingress_count = 0
    egress_count = 0
    scheduled_count = 0
    ondemand_count = 0

    for df in dataflow_info:
        df_type = df.get('dataflow_type', '').upper()
        if 'INGRESS' in df_type:
            ingress_count += 1
        elif 'EGRESS' in df_type:
            egress_count += 1

        period = df.get('periodicity', '').upper()
        if 'DEMAND' in period or 'ON_DEMAND' in period:
            ondemand_count += 1
        else:
            scheduled_count += 1

    # Fetch last 24h stats for bulletin
    bulletin_info = DataflowMgmt.dataflow_get_bulletin_info()
    records_moved_24h_val = 0
    failed_runs_24h_val = 0
    running_now_val = 0

    for log_item in bulletin_info.values():
        rec_str = log_item.get('Total_Records', '')
        if rec_str:
            try:
                rec_str_clean = str(rec_str).strip().upper()
                multiplier = 1
                if rec_str_clean.endswith('K'):
                    multiplier = 1000
                    rec_str_clean = rec_str_clean[:-1]
                elif rec_str_clean.endswith('M'):
                    multiplier = 1000000
                    rec_str_clean = rec_str_clean[:-1]
                elif rec_str_clean.endswith('B'):
                    multiplier = 1000000000
                    rec_str_clean = rec_str_clean[:-1]
                records_moved_24h_val += int(float(rec_str_clean) * multiplier)
            except ValueError:
                pass

        status = log_item.get('Status', '')
        # Only count ❌ as failure — "Started" logs must not be counted as failures
        if '❌' in status:
            failed_runs_24h_val += 1

    # Calculate running_now by finding dataflows whose MOST RECENT log is "Started".
    # This is accurate: once Success/Failure arrives, that becomes the latest log
    # and the job is no longer counted as running.
    try:
        from django.db.models import Max as _Max
        from cPlatformIO.models import DataFlowLogs as _DFL
        from datetime import datetime as _dt, timedelta as _td
        _24h_ago = _dt.now() - _td(hours=24)
        _latest = (
            _DFL.objects
            .filter(dataflow_date__gte=_24h_ago.date())
            .values('dataflow_id')
            .annotate(latest_id=_Max('log_id'))
        )
        for _entry in _latest:
            _log = _DFL.objects.filter(log_id=_entry['latest_id']).first()
            if _log and _log.status == 'Started':
                running_now_val += 1
    except Exception:
        pass

    def format_records(num):
        if num >= 1000000000:
            return f"{num / 1000000000:.1f}B"
        elif num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return str(num)

    records_moved_24h = format_records(records_moved_24h_val) if records_moved_24h_val > 0 else "0"

    # Calculate 7d success rate
    success_rate_7d = "100%"
    try:
        from datetime import datetime, timedelta
        from cPlatformIO.models import DataFlowLogs
        seven_days_ago = datetime.now() - timedelta(days=7)
        total_runs_7d = DataFlowLogs.objects.filter(dataflow_date__gte=seven_days_ago.date()).count()
        if total_runs_7d > 0:
            success_runs_7d = DataFlowLogs.objects.filter(dataflow_date__gte=seven_days_ago.date(), status='Success').count()
            success_rate_7d = f"{int((success_runs_7d / total_runs_7d) * 100)}%"
    except Exception:
        pass

    file_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormDataflow.json')
    dataflow_schema = getSchema.cutil_get_flow_schema(file_path)
    cluster_info = ClusterConfig.cluster_get_config_info_v2()

    stats_14d = DataflowMgmt.dataflow_get_14d_stats()

    active_dataflows_count = sum(1 for df in dataflow_info if df.get('dataflow_status') == 'Enable')

    context = {'dataflow_info': dataflow_info,
               "dataflow_type_config": dataflow_type_config, "dataflow_schema": json.dumps(dataflow_schema),
               'training_info': training_info, 'ans_info': ans_info, 'opcop_info': opcop_info,
               'application_info': application_info,
               'running_now_count': running_now_val,
               'records_moved_24h': records_moved_24h,
               'success_rate_7d': success_rate_7d,
               'failed_runs_24h_count': failed_runs_24h_val,
               'active_dataflows_count': active_dataflows_count,
               'ingress_count': ingress_count,
               'egress_count': egress_count,
               'scheduled_count': scheduled_count,
               'ondemand_count': ondemand_count,
               'cluster_info': cluster_info,
               'cluster_info_json': json.dumps(cluster_info),
               'stats_14d_json': json.dumps(stats_14d),
               'current_page': 'Data / Batch I/O'
               }
    return render(request, 'PlatformIO/BatchIngress.html', context)


@csrf_exempt
def cPlatformIO_stream_ingress_view(request):
    def _is_json_request(req):
        return 'application/json' in (req.content_type or '').lower()

    def _load_request_info(req):
        if _is_json_request(req):
            try:
                return json.loads(req.body.decode('utf-8') or '{}')
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}

        json_data = req.POST.get('json_data')
        if json_data:
            try:
                return json.loads(json_data)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return {}

    def _success_payload(ret_msg):
        text = str(ret_msg or '').lower()
        failed_tokens = ['failure', 'invalid', 'unable', 'already exists', 'does not exist', 'failed']
        return not any(token in text for token in failed_tokens)

    if request.method == "POST":
        app_logger.info(f"Received POST request with data: {request.POST}")
        full_payload = _load_request_info(request)
        dataflow_action = full_payload.get('user-action', request.POST.get('user-action'))

        request_info = full_payload.get('request_info', full_payload.get('json_data', full_payload))
        if isinstance(request_info, str):
            try:
                request_info = json.loads(request_info)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        is_json_req = _is_json_request(request)

        if dataflow_action == 'add':
            # The demo control plane accepts only FTP or a local path and
            # stores the normalized contract alongside the legacy dataflow
            # row.  Legacy service-backed streams continue down the existing
            # StrmflowMgmt path unchanged.
            if str(request_info.get('conn_type') or '').upper() in {'FTP', 'LOCAL', 'ENDPOINT', 'HTTP_ENDPOINT', 'SSE'}:
                try:
                    request_info['control_plane_contract'] = build_stream_contract(request_info)
                    request_info['conn_info'] = dict(request_info.get('conn_info') or {})
                    request_info['conn_info']['control_plane_contract'] = request_info['control_plane_contract']
                    request_info['conn_info']['events_per_second'] = request_info['control_plane_contract']['replay']['events_per_second']
                    request_info['conn_info']['continuous_replay'] = request_info['control_plane_contract']['replay']['continuous']
                    request_info['conn_info']['replay_mode'] = request_info['control_plane_contract']['replay']['mode']
                    request_info['dataflow_type'] = request_info.get('dataflow_type') or 'nocAlarmStream'
                    request_info['ingestion'] = request_info.get('ingestion') or 'BackEnd'
                    # Legacy DataflowStreamConfig creation explicitly passes
                    # these scheduling fields, so a JSON caller that only
                    # supplies the NOC contract must still receive valid
                    # database values.  The control-plane lifecycle is
                    # started by its own runtime endpoint, not by a legacy
                    # periodic scheduler.
                    request_info['time_zone'] = request_info.get('time_zone') or 'UTC'
                    request_info['periodicity'] = request_info.get('periodicity') or 'ONCE'
                except ContractValidationError as exc:
                    error = {'success': False, 'message': str(exc)}
                    if exc.field:
                        error['field'] = exc.field
                    return JsonResponse(error, status=400)
            ret_msg = StrmflowMgmt.dataflow_add_request(request_info)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow add request processed successfully with message: {ret_msg}")

            new_id = None
            if _success_payload(ret_msg):
                try:
                    df = DataflowStreamConfig.objects.get(dataflow_name=request_info.get('dataflow_name'))
                    new_id = df.dataflow_id
                    if isinstance((df.conn_info or {}).get('control_plane_contract'), dict):
                        runtime = noc_runtime_for(df)
                        runtime['state'] = 'registered'
                        runtime['last_error'] = None
                        noc_save_runtime(df, runtime, status='Disable')
                except Exception:
                    pass

            if is_json_req:
                updated_info = StrmflowMgmt.dataflow_get_info()
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg, 'dataflow_id': new_id, 'dataflow_info': updated_info})

        elif dataflow_action == 'edit':
            edit_id = full_payload.get('dataflow_id') or request_info.get('dataflow_id')
            existing_demo = None
            if edit_id:
                existing_demo = DataflowStreamConfig.objects.filter(dataflow_id=edit_id).first()
            if existing_demo is None and request_info.get('dataflow_name'):
                existing_demo = DataflowStreamConfig.objects.filter(dataflow_name=request_info.get('dataflow_name')).first()
            # Editing a live flow is deliberately a stop -> edit -> new cycle
            # operation.  We stop the owned NiFi processors before persisting
            # the new contract and mark the group for a clean rebuild on the
            # next Start action.
            if existing_demo and isinstance((existing_demo.conn_info or {}).get('control_plane_contract'), dict):
                existing_runtime = noc_runtime_for(existing_demo)
                if existing_runtime.get('state') in {'running', 'starting', 'paused'}:
                    try:
                        noc_apply_action(existing_demo, 'stop')
                    except NocRuntimeError as exc:
                        return JsonResponse({'success': False, 'message': f'Unable to stop stream before edit: {exc}'}, status=409)
            if str(request_info.get('conn_type') or '').upper() in {'FTP', 'LOCAL', 'ENDPOINT', 'HTTP_ENDPOINT', 'SSE'}:
                try:
                    request_info['control_plane_contract'] = build_stream_contract(request_info)
                    request_info['conn_info'] = dict(request_info.get('conn_info') or {})
                    request_info['conn_info']['control_plane_contract'] = request_info['control_plane_contract']
                    request_info['conn_info']['events_per_second'] = request_info['control_plane_contract']['replay']['events_per_second']
                    request_info['conn_info']['continuous_replay'] = request_info['control_plane_contract']['replay']['continuous']
                    request_info['conn_info']['replay_mode'] = request_info['control_plane_contract']['replay']['mode']
                    request_info['dataflow_type'] = request_info.get('dataflow_type') or 'nocAlarmStream'
                    request_info['ingestion'] = request_info.get('ingestion') or 'BackEnd'
                    request_info['time_zone'] = request_info.get('time_zone') or 'UTC'
                    request_info['periodicity'] = request_info.get('periodicity') or 'ONCE'
                except ContractValidationError as exc:
                    error = {'success': False, 'message': str(exc)}
                    if exc.field:
                        error['field'] = exc.field
                    return JsonResponse(error, status=400)
            ret_msg = StrmflowMgmt.dataflow_edit_request(request_info)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow edit request processed successfully with message: {ret_msg}")
            if is_json_req:
                try:
                    edited = DataflowStreamConfig.objects.filter(
                        dataflow_id=edit_id
                    ).first() if edit_id else DataflowStreamConfig.objects.filter(
                        dataflow_name=request_info.get('dataflow_name')
                    ).first()
                    if edited and isinstance((edited.conn_info or {}).get('control_plane_contract'), dict):
                        runtime = noc_runtime_for(edited)
                        runtime['state'] = 'stopped'
                        runtime['rebuild_required'] = True
                        runtime['last_error'] = None
                        noc_save_runtime(edited, runtime, status='Disable')
                except Exception as exc:
                    app_logger.warning(f'Could not update NOC runtime after edit: {exc}')
                updated_info = StrmflowMgmt.dataflow_get_info()
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg, 'dataflow_info': updated_info})

        elif dataflow_action == 'delete':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            ret_msg = StrmflowMgmt.dataflow_delete_request(dataflow_id)
            messages.success(request, ret_msg)
            app_logger.info(f"Dataflow delete request processed successfully with message: {ret_msg}")
            if is_json_req:
                updated_info = StrmflowMgmt.dataflow_get_info()
                return JsonResponse({'success': _success_payload(ret_msg), 'message': ret_msg, 'dataflow_info': updated_info})

        elif dataflow_action == 'dataflow_log':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            dataflow_type = full_payload.get('dataflow_type', request.POST.get('dataflow_type'))

            # A demo stream does not require an optionCopilot deployment just
            # to render its metrics drawer.  Return the same shape consumed by
            # the existing frontend, with a generalized link to monitoring.
            demo_stream = DataflowStreamConfig.objects.filter(dataflow_id=dataflow_id).first()
            demo_contract = (demo_stream.conn_info or {}).get('control_plane_contract') if demo_stream else None
            if isinstance(demo_contract, dict):
                replay = demo_contract.get('replay', {})
                source = demo_contract.get('source', {})
                nifi = demo_contract.get('nifi', {})
                topic = demo_contract.get('kafka', {}).get('topic', 'noc.alarm.normalized.v1')
                metrics = {
                    'status': 'Running' if demo_stream.dataflow_status == 'Enable' else 'Stopped',
                    'entity': [source.get('type', 'source'), nifi.get('flow_name', 'NiFi'), topic],
                    'fyer': {'desc': 'Replay source', 'ticks_per_sec': replay.get('events_per_second', 100)},
                    'nifi': {'desc': 'Raw row JSON transform', 'processed_flow_files_min': 0},
                    'clickhouse': {'desc': f'Kafka topic {topic}', 'trades_rows_inserted_5m': 0},
                    'metrics_link': demo_contract.get('metrics', {}).get('link', '/PlatformIO/Monitoring/Performance/'),
                }
                return JsonResponse({'success': True, 'metrics': metrics})

            from cPlatformIO.models import Service
            ocp_service = Service.objects.filter(service_type="optionCopilot").first()
            if not ocp_service:
                app_logger.error("No optionCopilot service registered")
                return JsonResponse({'success': False, 'message': 'optionCopilot service not configured'}, status=503)

            ret, service_ip, service_port = ServiceConfig.service_get_route(ocp_service)
            if not ret or not service_ip:
                app_logger.error(f"Could not resolve route for optionCopilot service {ocp_service.service_id}")
                return JsonResponse({'success': False, 'message': 'Unable to reach optionCopilot service'}, status=502)

            try:
                resp = requests.get(
                    f"http://{service_ip}:{service_port}/cPlatformApp/APIv1/Dataflow/Metrics/",
                    params={'dataflow_id': dataflow_id, 'dataflow_type': dataflow_type},
                    timeout=60,
                )
                resp.raise_for_status()
                dataflow_metrics = resp.json()
            except requests.RequestException as exc:
                app_logger.error(f"Failed to fetch dataflow metrics from OCP: {exc}")
                return JsonResponse({'success': False, 'message': 'Unable to retrieve metrics'}, status=502)

            app_logger.info("Dataflow metrics retrieved successfully from OCP")
            return JsonResponse(dataflow_metrics, safe=False)

        elif dataflow_action == 'stream_history':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            dataflow_type = full_payload.get('dataflow_type', request.POST.get('dataflow_type'))
            time_range = full_payload.get('time_range', request.POST.get('time_range', '24h'))

            from cPlatformIO.models import Service
            ocp_service = Service.objects.filter(service_type="optionCopilot").first()
            if not ocp_service:
                app_logger.error("No optionCopilot service registered")
                return JsonResponse({'success': False, 'message': 'optionCopilot service not configured'}, status=503)

            ret, service_ip, service_port = ServiceConfig.service_get_route(ocp_service)
            if not ret or not service_ip:
                app_logger.error(f"Could not resolve route for optionCopilot service {ocp_service.service_id}")
                return JsonResponse({'success': False, 'message': 'Unable to reach optionCopilot service'}, status=502)

            try:
                resp = requests.get(
                    f"http://{service_ip}:{service_port}/cPlatformApp/APIv1/Dataflow/MetricsHistory/",
                    params={'dataflow_id': dataflow_id, 'dataflow_type': dataflow_type, 'time_range': time_range},
                    timeout=60,
                )
                resp.raise_for_status()
                dataflow_history = resp.json()
            except requests.RequestException as exc:
                app_logger.error(f"Failed to fetch dataflow metrics history from OCP: {exc}")
                # Mocking data for UI until service is fully integrated
                avg_value = 120 if time_range == '24h' else (85 if time_range == '7d' else 45)
                return JsonResponse({'success': True, 'avg_value': avg_value, 'data': []})

            app_logger.info("Dataflow history retrieved successfully from OCP")
            return JsonResponse(dataflow_history, safe=False)

        elif dataflow_action == 'stream_exceptions':
            dataflow_id = full_payload.get('dataflow_id', request.POST.get('dataflow_id'))
            dataflow_type = full_payload.get('dataflow_type', request.POST.get('dataflow_type', 'TickerData'))

            # Demo / control plane streams return clean state or DB failure logs
            demo_stream = DataflowStreamConfig.objects.filter(dataflow_id=dataflow_id).first()
            demo_contract = (demo_stream.conn_info or {}).get('control_plane_contract') if demo_stream else None
            if isinstance(demo_contract, dict):
                unified_exceptions = StrmflowMgmt.dataflow_get_unified_exceptions(dataflow_id, dataflow_type, ocp_exceptions=[])
                return JsonResponse(unified_exceptions, safe=False)

            from cPlatformIO.models import Service
            ocp_service = Service.objects.filter(service_type="optionCopilot").first()
            ocp_exceptions = []
            if ocp_service:
                ret, service_ip, service_port = ServiceConfig.service_get_route(ocp_service)
                if ret and service_ip:
                    try:
                        resp = requests.get(
                            f"http://{service_ip}:{service_port}/cPlatformApp/APIv1/Dataflow/Exceptions/",
                            params={'dataflow_id': dataflow_id, 'dataflow_type': dataflow_type},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            ocp_data = resp.json()
                            ocp_exceptions = ocp_data.get('exceptions', [])
                    except Exception as exc:
                        app_logger.warning(f"Failed to fetch NiFi exceptions from OCP: {exc}")

            # Merge with Django DataFlowLogs and deduplicate
            unified_res = StrmflowMgmt.dataflow_get_unified_exceptions(dataflow_id, dataflow_type, ocp_exceptions=ocp_exceptions)
            return JsonResponse(unified_res, safe=False)

        elif dataflow_action == 'bulletin_board':
            logs_instances = StrmflowMgmt.dataflow_get_bulletin_info()
            app_logger.info("Last 24 hrs logs retrieved successfully")
            return JsonResponse(logs_instances, safe=False)

        elif dataflow_action == 'dataflow_summary':
            dataflow_summary = StrmflowMgmt.dataflow_get_summary_report()
            app_logger.info("Dataflow summary report retrieved successfully")
            return JsonResponse(dataflow_summary, safe=False)

    # Log INFO to record data retrieval process for the view
    app_logger.info("Retrieving dataflow configuration and options")

    # Get information for dataflow configuration and listing
    dataflow_info = StrmflowMgmt.dataflow_get_info()
    app_logger.debug(f"Retrieved dataflow_info: {dataflow_info}")

    dataflow_type_config = StrmflowMgmt.dataflow_get_type_config()

    training_info = ClusterConfig.cluster_get_service_list(None, "TrainingServer")
    ans_info = ClusterConfig.cluster_get_service_list(None, "ANS")
    opcop_info = ClusterConfig.cluster_get_service_list(None, "optionCopilot")

    application_info = ServiceConfig.service_get_application_info()

    file_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormStreamflow.json')
    dataflow_schema = getSchema.cutil_get_flow_schema(file_path)
    cluster_info = ClusterConfig.cluster_get_config_info_v2()

    context = {'dataflow_info': dataflow_info,
               'dataflow_info_json': json.dumps(dataflow_info),
               "dataflow_type_config": json.dumps(dataflow_type_config), "dataflow_schema": json.dumps(dataflow_schema),
               'training_info': training_info, 'ans_info': ans_info, 'opcop_info': opcop_info,
               'application_info': application_info,
               'cluster_info': cluster_info,
               'cluster_info_json': json.dumps(cluster_info),
               'current_page': 'Data / Stream I/O'
               }
    return render(request, 'PlatformIO/StreamIngress.html', context)


@csrf_exempt
def cPlatformIO_control_plane_catalog(request):
    """Expose the small Kafka/NiFi catalog used by the NOC alarm demo.

    This endpoint is intentionally independent of the large service catalog:
    clients can render the demo contract even when no optional service has been
    provisioned on a cluster yet.
    """

    if request.method not in {"GET", "HEAD"}:
        return JsonResponse({"success": False, "message": "Only GET is allowed"}, status=405)
    from cPlatformIO.src.demo_control_plane import NORMALIZED_ALARM_TOPIC

    bootstrap_servers = request.GET.get("bootstrap_servers") or os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return JsonResponse({
        "success": True,
        "catalog": kafka_catalog(bootstrap_servers=bootstrap_servers),
        "topic": NORMALIZED_ALARM_TOPIC,
    })


@csrf_exempt
def cPlatformIO_stream_contract(request):
    """Validate/normalize a demo stream request for FTP or a local path.

    The response is a deployment contract, not a promise that a broker or
    NiFi instance is reachable.  Runtime health remains observable through the
    generalized metrics link in the returned contract.
    """

    if request.method == "GET":
        return JsonResponse({
            "success": True,
            "defaults": {
                "source_type": "LOCAL",
                "eps": 100,
                "continuous": True,
                "replay_mode": "continuous",
                "topic": "noc.alarm.normalized.v1",
            },
        })
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Only GET or POST is allowed"}, status=405)

    try:
        if "application/json" in (request.content_type or "").lower():
            raw_body = request.body.decode("utf-8") if request.body else "{}"
            body = json.loads(raw_body)
        else:
            body = request.POST.get("json_data", "{}")
            body = json.loads(body) if isinstance(body, str) else body
        if isinstance(body, dict) and isinstance(body.get("request_info"), dict):
            body = body["request_info"]
        contract = build_stream_contract(body, base_url=request.build_absolute_uri("/").rstrip("/"))
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Request body must be valid JSON"}, status=400)
    except ContractValidationError as exc:
        error = {"success": False, "message": str(exc)}
        if exc.field:
            error["field"] = exc.field
        return JsonResponse(error, status=400)

    # Do not echo a password from the legacy FTP form back to the browser.
    source = contract.get("source")
    if isinstance(source, dict) and source.get("password"):
        source["password"] = "********"
    return JsonResponse({"success": True, "contract": contract})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cPlatformIO_stream_runtime(request):
    """Control and observe a registered NOC demo stream.

    ``GET`` is a read-only, normalized snapshot.  ``POST`` accepts one of
    ``start``, ``pause``, ``resume``, ``stop`` or ``delete`` and delegates all
    NiFi mutations to :mod:`cPlatformIO.src.noc_runtime`.  The endpoint is
    intentionally small so the existing Stream I/O page can drive it without
    knowing NiFi's revision and processor APIs.
    """

    dataflow_id = request.GET.get('dataflow_id') if request.method == 'GET' else None
    body: dict[str, Any] = {}
    if request.method == 'POST':
        try:
            if 'application/json' in (request.content_type or '').lower():
                body = json.loads(request.body.decode('utf-8') if request.body else '{}')
            else:
                raw = request.POST.get('json_data') or '{}'
                body = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'message': 'Request body must be valid JSON'}, status=400)
        dataflow_id = body.get('dataflow_id')

    if not dataflow_id:
        return JsonResponse({'success': False, 'message': 'dataflow_id is required'}, status=400)

    dataflow = DataflowStreamConfig.objects.filter(dataflow_id=str(dataflow_id)).first()
    if not dataflow:
        return JsonResponse({'success': False, 'message': 'dataflow was not found'}, status=404)
    if not isinstance((dataflow.conn_info or {}).get('control_plane_contract'), dict):
        return JsonResponse({'success': False, 'message': 'dataflow is not a NOC control-plane stream'}, status=409)

    if request.method == 'GET':
        try:
            return JsonResponse(noc_snapshot_for(dataflow))
        except Exception as exc:
            app_logger.error(f'Unable to read NOC stream runtime: {exc}', exc_info=True)
            return JsonResponse({'success': False, 'message': 'Unable to read stream runtime'}, status=502)

    action = body.get('action') or body.get('user-action')
    try:
        result = noc_apply_action(dataflow, str(action or ''))
    except NocRuntimeError as exc:
        app_logger.error(f'NOC stream action failed ({action}): {exc}', exc_info=True)
        try:
            snapshot = noc_snapshot_for(dataflow, include_remote=False)
        except Exception:
            snapshot = {'dataflow_id': dataflow.dataflow_id}
        snapshot.update({'success': False, 'message': str(exc), 'action': action})
        return JsonResponse(snapshot, status=502)
    except Exception as exc:
        app_logger.error(f'Unexpected NOC stream action error ({action}): {exc}', exc_info=True)
        return JsonResponse({'success': False, 'message': 'Unexpected stream control error'}, status=500)
    return JsonResponse(result)


@require_http_methods(["GET"])
def cPlatformIO_stream_runtime_history(request):
    """Proxy persisted NOC history without changing stock History behavior."""

    dataflow_id = request.GET.get("dataflow_id")
    cycle_id = request.GET.get("cycle_id")
    window = request.GET.get("window") or request.GET.get("time_range") or "24h"
    if not dataflow_id or not cycle_id:
        return JsonResponse(
            {"success": False, "message": "dataflow_id and cycle_id are required"},
            status=400,
        )
    dataflow = DataflowStreamConfig.objects.filter(dataflow_id=str(dataflow_id)).first()
    if not dataflow or not isinstance((dataflow.conn_info or {}).get("control_plane_contract"), dict):
        return JsonResponse(
            {"success": False, "message": "dataflow is not a NOC control-plane stream"},
            status=409,
        )
    base = (
        os.environ.get("AGENTICNOC_RUNTIME_HISTORY_URL")
        or os.environ.get("AGENTICNOC_BASE_URL", "http://180.75.0.7:8000").rstrip("/")
        + "/api/stream/runtime/history/"
    )
    try:
        response = requests.get(
            base,
            params={"dataflow_id": dataflow_id, "cycle_id": cycle_id, "window": window},
            timeout=float(os.environ.get("NOC_RUNTIME_TIMEOUT", "8")),
        )
        response.raise_for_status()
        payload = response.json()
        return JsonResponse(payload, safe=False)
    except (requests.RequestException, ValueError) as exc:
        app_logger.error("Unable to read persisted NOC runtime history: %s", exc, exc_info=True)
        return JsonResponse(
            {"success": False, "message": "Unable to retrieve NOC runtime history"},
            status=502,
        )

def cPlatformIO_stream_bulletin(request):
    context = {'current_page': 'Data / Stream dataflow'}
    return render(request, 'PlatformIO/streamBulletin.html', context)

def cPlatformIO_stream_crud(request):
    return render(request, 'PlatformIO/streamCrud.html')

@login_required
def custom_login_redirect(request):
    user = request.user
    if user.groups.filter(name='Admin').exists():
        return redirect('/PlatformIO')  # Redirect to admin page for admin users
    else:
        return redirect('/login')  # Redirect to login page for other users

@csrf_exempt
def cPlatformIO_auth_user(request):
    app_logger.debug(f"cPlatformIO_auth_user - { request}")
    json_status, json_msg, req_info = _cplatform_common_api_validation(request, 'user_authentication_schema')
    if json_status != 200:
        app_logger.debug(f"json_status, json_msg, req_info - {json_status}, {json_msg}, {req_info}")
        return JsonResponse({"authenticate": "False", "error": "Schema validation failed", "msg": json_msg},
            status=json_status )

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_mail = data.get("email")
            password = data.get("password")
            auth_user = authenticate(username=user_mail, password=password)
            if auth_user:
                user_ins = UserMgmnt.user_get_instance__mail(user_mail)
                if not user_ins:
                    app_logger.debug(f"User info not found")
                    return JsonResponse({"authenticate": "False", "msg": "User info not found"})
                payload = {"user_id" : user_ins.user_id,"user_mail" : user_mail,"user_name" : user_ins.user_name ,
                           "user_role" : user_ins.user_role,"user_number" : user_ins.user_number,"first_name": getattr(user_ins, "first_name", ""),
                           "last_name": getattr(user_ins, "last_name", ""),"session_info" : user_ins.session_info,"created_date" : user_ins.created_date, "password": password
                }
                UserMgmnt.user_login_count_increment(user_mail)
                return JsonResponse({"authenticate": "True", "data": payload})
            else:
                app_logger.debug(f"Invalid Schema or Authentication Failed")
                return JsonResponse({"authenticate": "False", "data": {"msg":"Invalid Schema or Authentication Failed"}})
        except Exception as e:
            app_logger.error(f"Exception occurred in AuthUser: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Only POST allowed"}, status=405)


@login_required
@admin_only
def cPlatformIO_batch_egress_view(request, *args, **kwargs):
    if request.method == "POST":
        app_logger.info(f" request.POST = {request.POST}")
    # setup_adopt_periodic_tasks()
    return render(request, 'PlatformIO/DataflowBatchEgress.html')


@login_required
@admin_only
def cPlatformIO_realtime_view(request, *args, **kwargs):
    # These comments refer to predefined functions. So I have commented them out for future use.
    if request.method == "POST":
        app_logger.info(f" request.POST = {request.POST}")
        realtimedatapipeline_action = request.POST.get('realtimedatapipeline-action')
        if realtimedatapipeline_action == 'add':
            status = 'CREATE'
            # res, ret_msg = DataflowConfig.real_time_dataflow_main_function(status,
            #                                                                request.POST.get('dataflow_name'),
            #                                                                request.POST.get('dataflow_type'),
            #                                                                request.POST.get('dataflow_ip'),
            #                                                                request.POST.get('dataflow_port'),
            #                                                                request.POST.get('dataflow_protocol'),
            #                                                                request.POST.get('dataflow_id')
            #                                                                )
            # if res == False:
            #     messages.warning(request, ret_msg)

            ret, ret_msg = RTMgmt.dataflow_realtime_add(
                request.POST.get('dataflow_name'),
                request.POST.get('dataflow_type'),
                request.POST.get('service_port'),
                request.POST.get('cluster_service'))

            if ret:
                messages.success(request, 'New Data Flow Added...')
            else:
                messages.warning(request, ret_msg)
        elif realtimedatapipeline_action == 'edit':
            # ***********Dataflow Real Time Function**************
            # res, ret_msg = DataflowConfig.real_time_dataflow_main_function(request.POST.get('dataflow_status'),
            #                                                                request.POST.get('dataflow_name'),
            #                                                                request.POST.get('dataflow_type'),
            #                                                                request.POST.get('dataflow_ip'),
            #                                                                request.POST.get('dataflow_port'),
            #                                                                request.POST.get('dataflow_protocol'),
            #                                                                request.POST.get('dataflow_id'))
            # if res == False:
            #     messages.warning(request, ret_msg)
            # else:
            ret, ret_msg = RTMgmt.dataflow_realtime_edit(request.POST.get('dataflow_id'),
                                                         request.POST.get('dataflow_name'),
                                                         request.POST.get('dataflow_type2'),
                                                         request.POST.get('service_port'),
                                                         request.POST.get('cluster_service2'))
            if ret:
                messages.success(request, 'Data Flow Modified Successfully...')
            else:
                messages.warning(request, ret_msg)
        elif realtimedatapipeline_action == 'delete':
            dataflow_id = request.POST.get('dataflow_id')
            RTMgmt.dataflow_realtime_delete(dataflow_id)
            messages.success(request, 'Data Flow Deleted Successfully...')

    realtimeingress_info = RTMgmt.dataflow_realtime_get_all()
    dataflow_config = RTMgmt.realtime_dataflow_get_service_config()

    context = {"dataflow_config": dataflow_config,
               "realtimeingress_info": list(realtimeingress_info),
               }
    return render(request, 'PlatformIO/DataflowRealtime.html', context)

# @login_required
# @admin_only
@csrf_exempt
def cPlatformIO_model_train_view(request):
    model_name = request.GET.get('model_name')
    if model_name:
        app_logger.info(f"model_name :: {model_name}")
        model_data = ModelMgmt.model_get_info(model_name)
        algo_info = AlgoInfoConfig.algo_get_info(model_name)
        performance_info = ModelMgmt.performance_get_info(model_name)
        log_info = ModelMgmt.logs_get_info(model_name)

        context = {
            "model_name": model_name,
            "model_info": model_data,
            "algo_info": algo_info,
            "performance_info": performance_info,
            "log_info": log_info,
            'current_page': 'Models / ModelDetails'
        }
        return render(request, 'PlatformIO/06-model-detail.html', context)

    if request.body:
        body = json.loads(request.body.decode("utf-8"))
        request_info = body.get('json_data')
        user_action = body.get("user-action", None)

        if user_action:
            # Handle user actions
            if user_action == "add":
                app_logger.info(f"cPlatformIO_model_view request: {request_info}")
                try:
                    ret_msg = ModelMgmt.model_add_request(request_info)
                    success = "Failure" not in str(ret_msg) and "Error" not in str(ret_msg)
                    return JsonResponse({"success": success, "msg": ret_msg})
                except:
                    app_logger.debug("\n\ncouldn't process add request!!!")
            elif user_action == 'edit':
                try:
                    msg = ModelMgmt.model_edit_request(request_info)
                    failure_keywords = ["Failure", "Error", "Cannot", "Does Not", "Failed", "Duplicate", "Missing",
                                        "Invalid"]
                    success = not any(kw in str(msg) for kw in failure_keywords)
                    return JsonResponse({"success": success, "msg": msg})
                except Exception as e:
                    app_logger.debug(traceback.format_exc())
                    return JsonResponse({"success": False, "msg": str(e)}, status=500)
            elif user_action == 'delete':
                msg = ModelMgmt.model_delete_request(request_info)
                return JsonResponse({"success": True, "msg": msg})

    # prepare the context
    file1_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormModel.json')
    file2_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormAlgo.json')
    model_schema = getSchema.cutil_get_flow_schema(file1_path)
    algo_schema = getSchema.cutil_get_flow_schema(file2_path)
    updated_schema = getSchema.convert_row_schema(algo_schema, model_schema)

    retriever_options = ModelMgmt.model_get_retriever_options()
    algo_options = ModelMgmt.model_get_algo_options()
    model_data = ModelMgmt.model_get_info()
    trn_In_Progress = len([model for model in model_data if model.get("training_status") == "TrainingInProgress"])
    trn_completed = len([model for model in model_data if model.get("training_status") == "TrainingComplete"])
    trn_failed = len([model for model in model_data if model.get("training_status") == "TrainingFailed"])
    trn_schedule = len([model for model in model_data if model.get("training_status") == "Scheduled"])

    # training_info, service_list = ClusterConfig.model_get_training_info()
    training_info = ClusterConfig.cluster_get_service_list(None, "TrainingServer")
    ans_info = ClusterConfig.cluster_get_service_list(None, "optionCopilot")
    application_info = ServiceConfig.service_get_application_info()
    dataflow_info_list = DataflowMgmt.model_get_dataflow_info_list()
    context = {
        "retriever_options": retriever_options, "training_info": training_info, "service_list": ans_info,
        "model_schema": json.dumps(updated_schema), "algo_options": algo_options, "model_data": model_data,
        "application_info": application_info, "dataflow_info_list": dataflow_info_list,
        "trn_in_progress": trn_In_Progress, "trn_complete": trn_completed, "trn_failed": trn_failed,
        "trn_schedule": trn_schedule,
        'current_page': 'Models / ModelTrain',
    }

    return render(request, "PlatformIO/05-models.html", context)


# @login_required
# @admin_only
@require_http_methods(["GET", "POST"])
def cPlatformIO_AppConfig_view(request):
    if request.method == "POST":
        user_action = request.POST.get('user-action')
        app_logger.info(f"cPlatformIO_AppConfig_view:user_action={user_action}, request={request.POST}")
        if user_action == 'add':
            ret, ret_msg = AppConfig.app_add_request(request)
            messages.success(request, ret_msg)
        elif user_action == 'edit':
            ret, ret_msg = AppConfig.app_edit_request(request)
            messages.success(request, ret_msg)
        elif user_action == 'delete':
            ret_msg = AppConfig.app_delete_request(request)
            messages.success(request, ret_msg)

    app_options = AppConfig.app_get_config_options()

    file_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormApp.json')
    app_schema = getSchema.cutil_get_flow_schema(file_path)
    context = {'appSchema': json.dumps(app_schema),
               'cluster_info_dict': ClusterConfig.cluster_get_service_mapping(None),
               'serv_keys': app_options['serv_keys'],
               'app_data': AppConfig.app_get_config_info(),
               'current_page': 'Models / Compare'}
    app_logger.info(f"cPlatformIO_AppConfig_view:context={context}")
    return render(request, 'PlatformIO/ApplicationConfig.html', context)

@csrf_exempt
# @login_required
# @admin_only
def cPlatformIO_model_infer_view(request):
    if request.body:
        request_info = json.loads(request.body)
        user_action = request_info.get('user_action')

        if user_action == 'add':
            ret, ret_msg = ModelInferMgmt.model_infer_add_request(request_info)
            if ret:
                messages.success(request, ret_msg)
                return JsonResponse({'status': 'ok', 'msg': ret_msg}, status=200)
            messages.error(request, ret_msg)
            return JsonResponse({'status': 'err', 'msg': ret_msg}, status=400)

        elif user_action == 'edit':
            ret, ret_msg = ModelInferMgmt.model_infer_edit_request(request_info)
            if ret:
                messages.success(request, ret_msg)
                return JsonResponse({'status': 'ok', 'msg': ret_msg}, status=200)
            messages.error(request, ret_msg)
            return JsonResponse({'status': 'err', 'msg': ret_msg}, status=400)

        elif user_action == 'delete':
            ret, ret_msg = ModelInferMgmt.model_infer_delete_request(request_info)
            if ret:
                messages.success(request, ret_msg)
                return JsonResponse({'status': 'ok', 'msg': ret_msg}, status=200)
            messages.error(request, ret_msg)
            return JsonResponse({'status': 'err', 'msg': ret_msg}, status=400)

        elif user_action == 'batch_request':
            ret, json_res = ModelInferMgmt.model_infer_batch_request(request)
            return JsonResponse(json_res, status=200, safe=False)

        elif user_action == 'sequential_request':
            ret, json_res = ModelInferMgmt.model_infer_sequential_request(request)
            return JsonResponse(json_res, status=200, safe=False)

        elif user_action == 'AI_Signal':
            ret, json_res = ModelInferMgmt.model_infer_ai_signal_request(request)
            return JsonResponse(json_res, status=200, safe=False)

    model_ids = ModelInferMgmt.model_infer_get_model_list()
    model_service_info = DBPullInferenceMgmt.get_model_service_info(model_ids)
    algo_ids = ModelInferMgmt.model_infer_get_algo_list()
    model_infer_data = ModelInferMgmt.model_infer_get_info()
    model_id_list = ModelInferMgmt.get_inferred_model_ids(model_ids)
    cluster_config = ClusterConfig.cluster_get_config_info_v2()
    service_list = ClusterConfig.cluster_get_service_list(None, "InferenceServer")
    file_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormModelConfig.json')
    model_config_schema = getSchema.cutil_get_flow_schema(file_path)
    json_schema = json.dumps(model_config_schema)
    artifacts = []
    for model_name in model_ids:
        artifacts.append(ModelInferMgmt.get_artifacts(model_name))
    edit_id = request.GET.get("edit_id")
    prefill = None
    if edit_id:
        prefill = next((r for r in model_infer_data if str(r.get('model_infer_id')) == str(edit_id)),None)

    context = {
        "model_infer_data": model_infer_data,
        "model_ids": model_ids,
        "model_id_list" :model_id_list,
        "model_service_info": model_service_info,
        "algo_ids": algo_ids,
        "model_infer_schema": json_schema,
        "inference_info": {"cluster_info_json": json.dumps(cluster_config), "service_list": json.dumps(service_list),},
        "prefill_infer": json.dumps(prefill, cls=DjangoJSONEncoder) if prefill else 'null',
        'current_page': 'Models / Infer',
        'artifacts': artifacts
    }
    if request.GET.get("mode") == "infer":
        return render(request, 'PlatformIO/ModelInfer.html', context)
    return render(request, 'PlatformIO/ModelList.html', context)

@csrf_exempt
def cPlatformIO_download_inference_artifact(request, model_id, job_id, filename):
    print(f"model_id, job_id, filename --- {model_id, job_id, filename}")
    data =  ModelInferMgmt.download_inference_artifact(model_id, job_id, filename)
    if data is None:
        return HttpResponse("File not found", status=404)
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    content_type_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "csv": "text/csv", "json": "application/json", "log": "text/plain"}
    content_type = content_type_map.get(ext, "application/octet-stream")
    response = HttpResponse(data, content_type=content_type)
    disposition = "inline" if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


@csrf_exempt
def cPlatformIO_get_inference_logs1(request):
    body = json.loads(request.body)
    model_name = body.get("model_name")
    if not model_name:
        return JsonResponse({"status": "error", "msg": "model_name required"}, status=400)
    limit = min(int(body.get("limit", 50)), 200)
    entries = ModelInferMgmt.get_model_infer_log(model_name, limit)
    app_logger.debug(f"entries -- {entries}")
    return JsonResponse({"status": "success", "model_name": model_name, "count": len(entries), "logs": entries})


@csrf_exempt
def cPlatformIO_get_inference_logs(request):
    app_logger.info(f" -- cPlatformIO_get_inference_logs -- ")
    body = json.loads(request.body)
    app_logger.debug(f"body -- {body}")
    model_name = body.get("model_name")
    job_id = body.get("job_id")
    if not model_name:
        return JsonResponse({"status": "error", "msg": "model_name required"}, status=400)

    logs_dict = ModelInferMgmt.get_dbpull_inference_logs(model_name)
    app_logger.debug(f"logs dict -- {logs_dict}")
    if job_id:
        logs_dict = {k: v for k, v in logs_dict.items() if v["job_name"] == job_id}

    return JsonResponse({
        "status": "success",
        "model_name": model_name,
        "count": len(logs_dict),
        "logs": list(logs_dict.values()),
    })

@login_required
@admin_only
def cPlatformIO_model_evaluate(request):
    model_config_list = ModelEvaluate.modelEvaluate_get_model_config_and_modelAlgo_ids_dict()
    gain_table_data, model_id, model_algo = {}, '', ''
    if request.method == "POST":
        model_config_id = request.POST.get("model_config_id")
        model_algo = request.POST.get("model_algo")
        gain_table_data, model_id = ModelEvaluate.modelEvaluate_get_gain_table_info(model_config_id, model_algo)
    context = {
        "model_config_list": model_config_list, "model_id": model_id,
        "gain_table_data": gain_table_data, "algo_type": model_algo
    }
    return render(request, 'PlatformIO/ModelEvaluate.html', context)


@csrf_exempt
@login_required
@admin_only
def cPlatformIO_model_compare_view(request):

    if request.method == "POST":
        user_action = request.POST.get('user-action')
        if user_action == 'add':
            result = ModelCompare.model_compare_add_request(request)
            if isinstance(result, dict) and 'error' in result:
                return JsonResponse({'status': 'err', 'message': result['error']}, status=400)
            return JsonResponse({'status': 'ok', 'compare': result})  # ← make sure this line exists and has return

        elif user_action == 'edit':
            ret_msg = ModelCompare.model_compare_edit_request(request)
            messages.success(request, ret_msg)

        elif user_action == 'delete':
            ret_msg = ModelCompare.model_compare_delete_request(request)
            messages.success(request, ret_msg)

        elif user_action == 'get_algo_info':

            model_name = request.POST.get('model_name')
            algo_id = request.POST.get('algo_id')
            model_compare_id = request.POST.get('model_compare_id')
            context = ModelCompare.model_compare_get_algo_info(model_name, algo_id, model_compare_id)
            app_logger.info(f"cPlatformIO_model_compare :: {context}")
            return JsonResponse(status=200, data=context)

        elif user_action == 'remove_row':
            algo_id = request.POST.get('algo_id')
            model_compare_id = request.POST.get('model_compare_id')
            ret, ret_msg = ModelCompare.model_compare_row_remove(algo_id, model_compare_id)
            if not ret:
                return JsonResponse({'status': 'err', 'message': ret_msg}, status=400)
            messages.success(request, ret_msg)
            return JsonResponse({'status': 'ok', 'message': ret_msg})

        elif user_action == 'compare_info':
            model_compare_id = request.POST.get('compare_id')
            context = ModelCompare._get_model_compare_detail_context(model_compare_id)
            return render(request, 'PlatformIO/ModelCompare.html', context)

    # For GET requests
    compare_id = request.GET.get('compare_id')
    if compare_id:
        try:
            context = ModelCompare._get_model_compare_detail_context(compare_id)
            return render(request, 'PlatformIO/ModelCompare.html', context)
        except Exception as e:
            app_logger.error(f"Error loading model compare detail view: {e}")
            messages.error(request, "Failed to load model comparison details.")

    model_list = ModelInferMgmt.model_infer_get_model_list()
    trained_model_data = ModelMgmt.model_get_info()
    total_algo_available = sum(
        len(model.get("algo_info_Json", {}).get("algo_field_info", []))
        for model in trained_model_data
        if model.get("training_status") == "TrainingComplete"
    )
    algo_list = ModelInferMgmt.model_infer_get_algo_list()
    algo_category = ModelCompare.model_compare_get_algo_category()
    model_info = ModelCompare.model_compare_get_info()
    context = {"model_ids": model_list, "category_dict": algo_category, "model_info": model_info,
               "algo_list": algo_list, 'total_algo_available': total_algo_available, 'current_page': 'Models / ModelCompare'}
    return render(request, 'PlatformIO/ModelCompareList.html', context)


def model_info(request):
    if request.method == 'POST':
        target_model = request.POST.get('target_model')
        model_info = AlgoInfoConfig.get_algo_info(target_model)
        return JsonResponse(model_info)


@csrf_exempt
def cPlatformIO_restapi_Repo_training_response(request):
    if request.method == 'POST':
        app_logger.debug(f"cPlatformIO_restapi_Repo_training_response {request}")
        status_code, msg = ModelMgmt.cPlatform_model_repo_handle_training_update(request)
        return JsonResponse(status=status_code, data={'message': msg})


@csrf_exempt
def cPlatformIO_restapi_Repo_ensemble_response(request):
    if request.method == 'POST':
        status_code, msg = ModelInferMgmt.moder_infer_ensemble_update(request)
        return JsonResponse(status=status_code, data={'message': msg})


@csrf_exempt
def cPlatformIO_model_inference(inf_request):
    if inf_request.method == "GET":
        # Try to get model mapped to this application
        ret, model_id, model_info = AppConfig.cPlatform_app_get_model("Credit", "ModelActive")

        if not ret:
            return JsonResponse(status=500, data={'message': 'No configured Model'})

        model_id = inf_request['model_id']
        algo_list = inf_request['algo_list']
        ret_code, context, inf_resp = cutil_inference_get(model_id=model_id, algo_list=algo_list,
                                                          inference_data=inf_request['inference_data'],
                                                          if_data_type='Structure_Data')

        return JsonResponse(status=200, data={'response': inf_resp})
    return JsonResponse(status=500, data={'message': 'Invalid request method'})


def _populate_service_schema_options(schema_dict, service_names, model_names):
    try:
        row_schema = schema_dict.get('ServiceConfig', {}).get('row_Schema', [])
        for field in row_schema:
            if field.get('f_name') == 'inference_server':
                field['v_options'] = service_names
            elif field.get('f_name') == 'model_name':
                field['v_options'] = model_names
    except Exception as e:
        app_logger.error(f"Error populating service schema options: {e}")
    return schema_dict


@csrf_exempt
def cPlatformIO_cluster_config(request):

    if request.method == 'POST':
        print(f"request.body=={request.body}")
        request_info = json.loads(request.body)

        user_action = request_info.get('user-action')

        cluster_id = request_info.get('cluster_id')

        if user_action == "open-cluster-config":
            return JsonResponse({
                "success": True,
                "redirect_url":
                    f"/PlatformIO/ClusterConfig/?cluster_id={cluster_id}"
            })

        if user_action == 'add_node':
            ret, msg, node_id = NodeConfig.node_add_request(request_info)
            infra_discovery = {}
            if ret and node_id:
                try:
                    dret, dmsg, details = ServiceConfig.service_discover_infrastructure_request(node_id)
                    infra_discovery = details or {}
                    infra_discovery.update({"success": dret, "msg": dmsg})
                except Exception as exc:
                    infra_discovery = {"success": False, "msg": str(exc), "adopted": []}
            context = {"msg": msg, "success": f"{ret}", "node_id": node_id, "infra_discovery": infra_discovery}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'get_cluster_info':
            cluster_info = ClusterConfig.cluster_get_config_info_v2(cluster_id)
            context = {"msg": f"Cluster {cluster_id} info updated", "success": True, "cluster_info": cluster_info}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'delete_node':
            node_id = request_info.get('node_id') or request.POST.get('node_id')
            ret, msg = NodeConfig.node_delete_request(node_id)
            details = {}
            if not ret:
                node = Node.objects.filter(node_id=node_id).first()
                if node:
                    services = Service.objects.filter(Node=node)
                    if services.exists():
                        details = {
                            "code": "NODE_HAS_SERVICES",
                            "node_id": node.node_id,
                            "node_name": node.node_name,
                            "services": [
                                {
                                    "service_id": service.service_id,
                                    "service_name": service.service_name,
                                    "service_type": service.service_type,
                                    "deploy_status": service.deploy_status,
                                }
                                for service in services
                            ],
                        }
            context = {"msg": msg, "success": f"{ret}", "details": details}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'update_node':
            ret, msg, node_name = NodeConfig.node_edit_request(request_info)
            context = {"msg": msg, "success": f"{ret}", "node_name": node_name}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'launch_node':
            ret, msg, node_name = NodeConfig.node_launch_request(request_info)
            context = {"msg": msg, "success": f"{ret}", "node_name": node_name}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'get_node_info':
            node_info = NodeConfig.node_get_config_info(request_info.get('node_id'))
            context = {"success": True}
            context.update(node_info or {})
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'discover_infrastructure':
            node_id = request_info.get('node_id') or request.POST.get('node_id')
            ret, msg, details = ServiceConfig.service_discover_infrastructure_request(node_id)
            context = {"msg": msg, "success": f"{ret}", "details": details}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'add_service':
            node_id = request_info.get('node_id')
            service_type = request_info.get('service_type')
            ret, msg, service_id, service_name = ServiceConfig.service_add_request(node_id, service_type, request_info)
            context = {
                "msg": msg,
                "success": f"{ret}",
                "service_id": service_id,
                "node_id": node_id,
                "service_name": service_name
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'delete_service':
            service_id = request_info.get('service_id') or request.POST.get('service_id')
            node_id = request_info.get('node_id') or request.POST.get('node_id')
            ret, msg = ServiceConfig.service_delete_request(service_id, node_id)
            context = {"msg": msg, "success": f"{ret}"}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'update_service':
            ret, msg, service_name = ServiceConfig.service_edit_request(request_info)
            context = {"msg": msg, "success": f"{ret}", "service_name": service_name}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'deploy_service':
            deploy_result = ServiceConfig.service_deploy_request(request_info)
            ret, msg = deploy_result[0], deploy_result[1]
            details = deploy_result[2] if len(deploy_result) > 2 else {}
            context = {"msg": msg, "success": f"{ret}", "details": details}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'get_service_info':
            service_id = request_info.get('service_id') or request.POST.get('service_id')
            service_info = ServiceConfig.service_get_info(service_id)
            context = {"success": True, "service_info": service_info}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_live_status':
            service_id = request_info.get("service_id") or request.POST.get("service_id")
            service_live_status = ServiceConfig.service_get_live_status(service_id)
            context = {"service_live_status": service_live_status}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_diagnostics':
            service_id = request_info.get("service_id") or request.POST.get("service_id")
            window = request_info.get("window") or request.POST.get("window", "current")
            diagnostic_target = request_info.get("diagnostic_target") or request.POST.get("diagnostic_target", "main")
            service_diagnostics = ServiceDiagnostics.service_get_diagnostics(service_id, window, diagnostic_target)
            context = {"service_diagnostics": service_diagnostics}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_live_logs':
            service_id = request.POST.get("service_id")
            diagnostic_target = request.POST.get("diagnostic_target", "main")
            tail_lines = request.POST.get("tail_lines", "200")
            cursor = request.POST.get("cursor", "")
            window = request.POST.get("window", "current")
            log_source = request.POST.get("log_source", "container_live")
            file_stream = request.POST.get("file_stream", "all")
            page_size = request.POST.get("page_size", "200")
            history_cursor = request.POST.get("history_cursor", "")
            history_direction = request.POST.get("history_direction", "latest")
            service_live_logs = ServiceDiagnostics.service_get_live_logs(
                service_id,
                diagnostic_target=diagnostic_target,
                tail_lines=tail_lines,
                cursor=cursor,
                window=window,
                log_source=log_source,
                file_stream=file_stream,
                page_size=page_size,
                history_cursor=history_cursor,
                history_direction=history_direction,
            )
            context = {"service_live_logs": service_live_logs}
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_log_backfill':
            service_id = request.POST.get("service_id")
            diagnostic_target = request.POST.get("diagnostic_target", "main")
            backfill_result = ServiceDiagnostics.service_run_log_backfill(service_id, diagnostic_target=diagnostic_target)
            context = {
                "success": backfill_result.get("success", False),
                "msg": backfill_result.get("msg", ""),
                "service_log_backfill": backfill_result.get("result", {}),
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_event':
            service_id = request_info.get("service_id") or request.POST.get("service_id")
            service_event_info = serviceEvent.service_get_event_info(service_id)
            context = {"service_event_info": service_event_info }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_store':
            service_id = request.POST.get("service_id")
            store_info = ServiceConfig.service_get_config_store(service_id)
            context = {
                "snapshots": store_info.get("snapshots", []),
                "updated_at": store_info.get("updated_at", ""),
                "config_capabilities": store_info.get("config_capabilities", {}),
                "msg": "Config store loaded",
            }
            if not store_info.get("success", True):
                context["msg"] = store_info.get("error", "Failed to load config store")
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_checkpoint':
            service_id = request.POST.get("service_id")
            ret, msg, snapshot_path = ServiceConfig.service_run_config_checkpoint(service_id)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "snapshot_path": snapshot_path,
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_view':
            service_id = request.POST.get("service_id")
            version = request.POST.get("version")
            timestamp = request.POST.get("timestamp")
            ret, msg, content = ServiceConfig.service_get_snapshot_content(service_id, version, timestamp)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "content": content,
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_diff':
            service_id = request.POST.get("service_id")
            snap1 = {
                "version": request.POST.get("snap1_version"),
                "timestamp": request.POST.get("snap1_timestamp")
            }
            snap2 = {
                "version": request.POST.get("snap2_version"),
                "timestamp": request.POST.get("snap2_timestamp")
            }
            ret, msg, diff_html = ServiceConfig.service_get_snapshots_diff(service_id, snap1, snap2)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "diff_html": diff_html,
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_migrate':
            service_id = request.POST.get("service_id")
            snap1 = {
                "version": request.POST.get("source_version") or request.POST.get("snap1_version"),
                "timestamp": request.POST.get("source_timestamp") or request.POST.get("snap1_timestamp")
            }
            snap2 = {
                "version": request.POST.get("target_version") or request.POST.get("snap2_version"),
                "timestamp": request.POST.get("target_timestamp") or request.POST.get("snap2_timestamp")
            }
            ret, msg, payload = ServiceConfig.service_prepare_snapshot_migrate_payload(service_id, snap1, snap2)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "selected_configs": payload.get("selected_configs", {}),
                "ranked_configs": payload.get("ranked_configs", {}),
                "config_rank_1": payload.get("config_rank_1", {}),
                "config_rank_2": payload.get("config_rank_2", {}),
                "migration_ops": payload.get("migration_ops", []),
                "migrated_config": payload.get("migrated_config", {}),
                "final_merged_config": payload.get("final_merged_config", {}),
                "final_merged_config_yaml": payload.get("final_merged_config_yaml", ""),
                "migration_artifact": payload.get("migration_artifact", {}),
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_apply':
            service_id = request.POST.get("service_id")
            migration_artifact_id = request.POST.get("migration_artifact_id")
            apply_mode = request.POST.get("apply_mode", "reload")
            edited_migration_yaml = request.POST.get("edited_migration_yaml", "")
            ret, msg, payload = ServiceConfig.service_apply_snapshot_migration(
                service_id,
                migration_artifact_id,
                apply_mode=apply_mode,
                edited_migration_yaml=edited_migration_yaml,
            )
            context = {
                "success": f"{ret}",
                "msg": msg,
                "artifact_id": payload.get("artifact_id", ""),
                "apply_result": payload.get("apply_result", {}),
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_restore':
            service_id = request.POST.get("service_id")
            backup_path = request.POST.get("backup_path")
            resolved_config_path = request.POST.get("resolved_config_path")
            apply_mode = request.POST.get("apply_mode", "reload")
            ret, msg, payload = ServiceConfig.service_restore_snapshot_migration(
                service_id,
                backup_path,
                resolved_config_path,
                apply_mode=apply_mode,
            )
            context = {
                "success": f"{ret}",
                "msg": msg,
                "restore_result": payload.get("restore_result", {}),
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_config_snapshot_validate_yaml':
            yaml_text = request.POST.get("yaml_text", "")
            ret, msg, payload = ServiceConfig.service_validate_yaml_text(yaml_text)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "details": payload,
            }

            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_runtime_patch':
            service_id = request_info.get("service_id") or request.POST.get("service_id")
            ret, msg, details = ServiceConfig.service_runtime_patch_request(service_id)
            context = {
                "success": f"{ret}",
                "msg": msg,
                "details": details,
            }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'service_runtime_patch_status':
            service_id = request_info.get("service_id") or request.POST.get("service_id")
            context = ServiceConfig.service_get_runtime_patch_status(service_id)
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'node_event':
            node_id = request_info.get("node_id") or request.POST.get("node_id")
            node_event_info = NodeEvent.node_get_event_info(node_id)
            context = {"node_event_info": node_event_info }
            return HttpResponse(json.dumps(context), content_type="application/json")

        elif user_action == 'track_visit':
            cluster_id = request_info.get('cluster_id', '')
            node_id = request_info.get('node_id', '')
            service_name = request_info.get('service_name', '')
            cluster_name = ''
            node_name = ''
            if cluster_id:
                try:
                    cluster_instance = Cluster.objects.get(cluster_id=cluster_id)
                    cluster_name = cluster_instance.cluster_name
                except Cluster.DoesNotExist:
                    pass
            if node_id:
                try:
                    node_ins = Node.objects.get(node_id=node_id)
                    node_name = node_ins.node_name
                except Node.DoesNotExist:
                    pass
            snapshot = {
                'cluster_name': cluster_name,
                'node_name': node_name,
                'service_name': service_name,
            }
            UserMgmnt.user_update_last_visited(str(request.user), snapshot)
            print(f"DEBUG track_visit done, snapshot={snapshot}")  # ADD
            return JsonResponse({'success': True})
        else:
            cluster_id = request_info.get('cluster_id')
            cluster_info = ClusterConfig.cluster_get_config_info_v2(cluster_id)
            old_service_schema = ServiceConfig.service_get_config_schema()

            file1_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormServiceConfig.json')
            file2_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormService.json')
            base_schema = getSchema.cutil_get_flow_schema(file1_path)
            service_schema = getSchema.cutil_get_flow_schema(file2_path)
            new_schema = getSchema.convert_row_schema(service_schema, base_schema)
            node_schema_path = os.path.join(BASE_DIR, "cPlatform/cPlatformIO/forms/dForm_Node_Schema.json")
            node_schema = getSchema.cutil_get_flow_schema(node_schema_path)

            serv_infer_list = ServiceConfig.service_get_infer_serv_list()
            model_info_list = []

            launch_node_schema_path = os.path.join(BASE_DIR,
                                                   "cPlatform/cPlatformIO/forms/dForm_Node_Launch_Schema.json")
            launch_node_schema = getSchema.cutil_get_flow_schema(launch_node_schema_path)
            cluster_detail = next(iter(cluster_info.values()), {}) if isinstance(cluster_info, dict) else {}
            cluster_name = cluster_detail.get("cluster_name") or cluster_id or "Cluster"

            service_names = [item["inf_service_name"] for item in serv_infer_list if "inf_service_name" in item]
            model_names = [item["model_name"] for item in model_info_list if "model_name" in item]
            parsed_schema = json.loads(new_schema)
            parsed_schema = _populate_service_schema_options(parsed_schema, service_names, model_names)

            context = {"cluster_info": cluster_info, "service_schema": parsed_schema,
                       "service_options": old_service_schema, "cluster_config_id": cluster_id,
                       "serv_infer_list": serv_infer_list, "model_info_list": model_info_list,
                       "node_schema": json.dumps(node_schema), "launch_node_schema": json.dumps(launch_node_schema),
                       "infra_service_catalog": ServiceConfig.service_get_infrastructure_catalog(),
                       'current_page': 'Infrastructure / ClusterConfig',
                       'breadcrumb_items': [
                           {'label': 'Infrastructure', 'href': '/PlatformIO/ClusterView/'},
                           {'label': 'Clusters', 'href': '/PlatformIO/ClusterView/'},
                           {'label': cluster_name, 'href': ''},
                       ]}

            return render(request, 'PlatformIO/04-cluster-detail.html', context)
        # Actual page render
    elif request.method == 'GET':

        cluster_id = request.GET.get('cluster_id')

        cluster_info = ClusterConfig.cluster_get_config_info_v2(cluster_id)
        cluster_detail = next(iter(cluster_info.values()), {}) if isinstance(cluster_info, dict) else {}
        cluster_name = cluster_detail.get("cluster_name") or cluster_id or "Cluster"

        old_service_schema = ServiceConfig.service_get_config_schema()

        file1_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormServiceConfig.json')
        file2_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormService.json')

        base_schema = getSchema.cutil_get_flow_schema(file1_path)

        service_schema = getSchema.cutil_get_flow_schema(file2_path)

        new_schema = getSchema.convert_row_schema(service_schema, base_schema)

        node_schema_path = os.path.join(
            BASE_DIR,
            "cPlatform/cPlatformIO/forms/dForm_Node_Schema.json"
        )

        node_schema = getSchema.cutil_get_flow_schema(node_schema_path)

        serv_infer_list = ServiceConfig.service_get_infer_serv_list()

        model_info_list = []

        launch_node_schema_path = os.path.join(
            BASE_DIR,
            "cPlatform/cPlatformIO/forms/dForm_Node_Launch_Schema.json"
        )

        launch_node_schema = getSchema.cutil_get_flow_schema(
            launch_node_schema_path
        )

        service_names = [item["inf_service_name"] for item in serv_infer_list if "inf_service_name" in item]
        model_names = [item["model_name"] for item in model_info_list if "model_name" in item]
        parsed_schema = json.loads(new_schema)
        parsed_schema = _populate_service_schema_options(parsed_schema, service_names, model_names)

        context = {
            "cluster_info": cluster_info,
            "service_schema": parsed_schema,
            "service_options": old_service_schema,
            "cluster_config_id": cluster_id,
            "serv_infer_list": serv_infer_list,
            "model_info_list": model_info_list,
            "node_schema": json.dumps(node_schema),
            "launch_node_schema": json.dumps(launch_node_schema),
            "infra_service_catalog": ServiceConfig.service_get_infrastructure_catalog_v2(),
            "infra_service_version": [
                {
                    "service_name": k,
                    "version": v,
                }
                for k, v in ServiceConfig.INFRA_SERVICE_VERSIONS.items()
            ],
            'current_page': 'Infrastructure / ClusterConfig',
            'breadcrumb_items': [
                {'label': 'Infrastructure', 'href': '/PlatformIO/ClusterView/'},
                {'label': 'Clusters', 'href': '/PlatformIO/ClusterView/'},
                {'label': cluster_name, 'href': ''},
            ],
        }

        return render(
            request,
            'PlatformIO/04-cluster-detail.html',
            context
        )
    else:
        return redirect('/PlatformIO/ClusterView/')


@csrf_exempt
def cPlatformIO_cluster_view(request):

    if request.method == 'POST':
        request_info = json.loads(request.body.decode('utf-8'))
        user_action = request_info.get('user-action')

        if user_action == 'add_cluster':
            ret, msg, cluster_id = ClusterConfig.cluster_add_request(request_info)
            messages.success(request, msg)
            return JsonResponse({
                "success": ret,
                "message": msg,
                "cluster_id": cluster_id
            })

        elif user_action == 'update_cluster':
            ret, msg, cluster_id = ClusterConfig.cluster_update_request(request_info)
            messages.success(request, msg)
            return JsonResponse({
                "success": ret,
                "message": msg,
                "cluster_id": cluster_id
            })

        elif user_action == 'delete_cluster':
            cluster_id = request_info.get('cluster_id', '')
            ret, msg = ClusterConfig.cluster_delete_request(request_info)
            details = {}
            cluster = Cluster.objects.filter(cluster_id=cluster_id).first()
            if not ret and cluster:
                nodes = Node.objects.filter(Cluster=cluster)
                if nodes.exists():
                    details = {
                        "code": "CLUSTER_HAS_NODES",
                        "cluster_id": cluster.cluster_id,
                        "cluster_name": cluster.cluster_name,
                        "nodes": [
                            {
                                "node_id": node.node_id,
                                "node_name": node.node_name,
                            }
                            for node in nodes
                        ],
                    }
                elif cluster.cluster_type == 'Primary' and Cluster.objects.filter(cluster_type='Secondary').exists():
                    details = {
                        "code": "PRIMARY_CLUSTER_HAS_SECONDARIES",
                        "cluster_id": cluster.cluster_id,
                        "cluster_name": cluster.cluster_name,
                    }
            messages.success(request, msg)
            return JsonResponse({
                "success": ret,
                "message": msg,
                "details": details,
            })

    cluster_options = ClusterConfig.cluster_get_config_options()
    cluster_info = ClusterConfig.cluster_get_config_info_v2()
    cluster_schema_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dForm_ClusterView_Schema.json')
    cluster_schema = getSchema.cutil_get_flow_schema(cluster_schema_path)
    context = {"cluster_schema": json.dumps(cluster_schema), "cluster_info": cluster_info,
               "service_options": ServiceConfig.service_get_config_schema(),
               "cluster_option": cluster_options['repo_options'],
               "Image_store_options": cluster_options['image_store_options'],
               'current_page': 'Infrastructure / Clusters',
               'breadcrumb_items': [
                    {'label': 'Infrastructure', 'href': '/PlatformIO/ClusterView/'},
                    {'label': 'Clusters', 'href': ''},
               ],
               "total_nodes": sum(
                    len(cluster.get("node_info", {}))
                    for cluster in cluster_info.values()),
               "total_services":  sum(
                    len(node.get("service_info", {}))
                    for cluster in cluster_info.values()
                    for node in cluster.get("node_info", {}).values())
               }
    return render(request, 'PlatformIO/02-clusters.html', context)

@csrf_exempt
@login_required
def cPlatformIO_user_view(request):
    if request.method == "POST":
        app_logger.info(f'cPlatformIO_user_view, request={request.POST}')
        user_action = request.POST.get('user-action')
        if user_action == 'add':
            msg = UserMgmnt.user_add_request(request.POST.get('user_name'), request.POST.get('user_email'),
                                             request.POST.get('password'), request.POST.get('user_role'),
                                             request.POST.get('user_number')
                                             )
            messages.success(request, msg)
        elif user_action == 'edit':
            msg = UserMgmnt.user_edit_request(request.POST.get('user_name'), request.POST.get('user_email'),
                                              request.POST.get('password'), request.POST.get('user_number'),
                                              request.POST.get('user_role'),
                                              )
            messages.success(request, msg)
        elif user_action == 'delete':
            # UserMgmnt.service_user_delete(request.POST.get('user_email'))
            # msg = UserMgmnt.user_delete_request(request.POST.get('user_id'))
            UserMgmnt.user_delete_request(request.POST.get('user_email'),initiated_by=str(request.user))
            # messages.success(request, msg)
            messages.success(request, 'User deleted successfully')
        elif user_action == 'revoke_invite':
            email = request.POST.get('user_email')
            UserMgmnt.service_revoke_and_delete_pending(email, invited_by=str(request.user))
            messages.success(request, 'Invitation revoked')
        elif user_action == 'invite_user':
            UserMgmnt.service_user_invite(request.POST.get('user_name'),request.POST.get('user_email'),
                                              request.POST.get('user_number'),request.POST.get('user_role'),
                                              request.POST.getlist('permissions'),invited_by=str(request.user),)
            messages.success(request, 'Invitation sent successfully')
        elif user_action == 'resend_invite':
            user_email_value = request.POST.getlist('user_email')
            emails = [e.strip() for e in user_email_value if e and e.strip()]
            sent_count, skipped_count = UserMgmnt.service_user_resend_invite_bulk(
                emails, invited_by=str(request.user))
            if skipped_count > 0:
                messages.success(request,f'Invitation resent to {sent_count} pending user(s); {skipped_count} user(s) were not pending and skipped.')
            else:
                messages.success(request, f'Invitation resent successfully to {sent_count} pending user(s).')
        return redirect('PlatformIOUsers')

    if request.user.is_staff:
        user_data = UserMgmnt.user_get_info(None)
    else:
        user_data = UserMgmnt.user_get_info(str(request.user))

    file_path = os.path.join(BASE_DIR, "cPlatform/cPlatformIO/forms/dFormUser.json")
    user_schema = getSchema.cutil_get_flow_schema(file_path)

    total_users = len(user_data)
    active_users = sum(1 for u in user_data if u['status'] == 'active')
    pending_users = sum(1 for u in user_data if u['status'] == 'pending')
    disabled_users = sum(1 for u in user_data if u['status'] == 'disabled')
    admin_users = sum(1 for u in user_data if u['user_role'] == 'System_Admin')
    highest_login_count = max([u['login_count'] for u in user_data],default=1)
    for user in user_data:
        user['activity_percent'] = round((user['login_count'] / highest_login_count) * 100,1) if highest_login_count else 0
    cplatform_url = PlatformSettings.cplatform_url
    try:
        current_user_info = UserInfo.objects.get(user_email=str(request.user))
        current_user_role = current_user_info.user_role
    except UserInfo.DoesNotExist:
        current_user_role = ''
    context = {
        'user_data': user_data,
        'user_schema': json.dumps(user_schema),
        'total_users': total_users,
        'active_users': active_users,
        'pending_users': pending_users,
        'disabled_users': disabled_users,
        'admin_users': admin_users,
        'cplatform_url': cplatform_url,
        'current_user_role': current_user_role,
        'current_page': 'Identity / Users'
    }
    return render(request, 'PlatformIO/01-users.html', context)

@csrf_exempt
@login_required
def cPlatformIO_dataflow_status(request):
    """
    Returns the count of currently running dataflows (status = 'Started')
    and per-dataflow last log info for the frontend to auto-patch card pills.
    """
    from cPlatformIO.models import DataFlowLogs, DataflowBatchConfig
    from cPlatformIO.src.DataflowMgmt import _get_dataflow_recent_runs
    from django.http import JsonResponse
    try:
        running_count = 0

        # Build per-dataflow latest log snapshot so the frontend can auto-update
        # cards that are currently showing a "Running" pill.
        dataflow_logs = {}
        for df in DataflowBatchConfig.objects.all():
            last_log = (
                DataFlowLogs.objects
                .filter(dataflow_id=df.dataflow_id)
                .order_by('-dataflow_date', '-dataflow_time')
                .first()
            )
            if last_log:
                if last_log.status == 'Started':
                    running_count += 1
                log_info = last_log.log_info or {}
                if isinstance(log_info, str):
                    try:
                        import json as _json
                        log_info = _json.loads(log_info)
                    except Exception:
                        log_info = {}
                records = (
                    log_info.get('Total Records')
                    or log_info.get('total_records')
                    or '-'
                )
                dataflow_logs[df.dataflow_id] = {
                    'status': last_log.status,          # 'Success', 'Failure', 'Started'
                    'date': str(last_log.dataflow_date),
                    'time': str(last_log.dataflow_time),
                    'records': str(records),
                    'recent_runs': _get_dataflow_recent_runs(df.dataflow_id),
                }

        return JsonResponse({"running_count": running_count, "dataflow_logs": dataflow_logs})
    except Exception as e:
        app_logger.error(f"Error in cPlatformIO_dataflow_status: {e}")
        return JsonResponse({"running_count": 0, "dataflow_logs": {}, "error": str(e)}, status=500)



@csrf_exempt
def cPlatformIO_dataflow_logs_add(request):
    request_info = request.POST.dict()
    app_logger.debug(f"cPlatformIO_dataflow_logs_add, request_info={request_info}")

    uploaded_file = request.FILES.get('file')

    if uploaded_file:
        base_path = settings.REPOSITORY_PATH
        report_base_path = os.path.join(base_path, 'DataflowReports', str(request_info['dataflow_id']))
        os.makedirs(report_base_path, exist_ok=True)
        with open(f"{report_base_path}/{uploaded_file.name}", 'wb+') as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)
        request_info['filename'] = uploaded_file.name
    DataflowMgmt.dataflow_log_add_request(request_info)
    return JsonResponse(status=200, data={'context': 'Dataflow logs successfully!'})


@login_required()
@require_http_methods(["GET", "POST"])
@csrf_exempt
def cPlatformIO_system_monitoring(request):
    context = {
        'current_page': 'Observability / Monitoring',
        'error': None
    }

    try:
        session_info = UserMgmnt.get_session_info(request.user)
        context["session_info"] = json.dumps(session_info.get("last_visited", {}))
    except Exception as e:
        context["error"] = str(e)
    context["stats"] = NodeConfig.node_get_monitoring_stats()

    return render(request, "PlatformIO/SystemMonitoring.html", context)

@login_required()
@require_http_methods(["GET"])
@csrf_exempt
def cPlatformIO_get_monitoring_tree(request):
    try:
        cluster_tree = ClusterConfig.cluster_monitoring_tree()
        return JsonResponse({
            "success": True,
            "cluster_tree": cluster_tree
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_get_node_performance(request):
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:
        json_data = request.POST.get("json_data")
        if not json_data:
            raise ValueError("No JSON data provided")

        data = json.loads(json_data)

        period = data.get("period", "24h")
        cluster = data.get("cluster", "")
        node_name = data.get("node", "")
        force_refresh = data.get("refresh", False)

        # ---------------------------------------------
        # selected node info
        # ---------------------------------------------
        node_info = NodeConfig.node_get_info_cluster(cluster, node_name)

        if not node_info:
            raise ValueError(
                f"Node not found: {node_name}"
            )

        service_config = node_info.get("service_config")

        if not service_config:
            raise ValueError(
                f"Data not found: {node_name}"
            )

        ip_address = node_info.get("ip_address")
        node_port = node_info.get("node_port")
        gpu_status = node_info.get("gpu_status")
        node_idx = node_info.get("node_idx")
        host_port = service_config.get("host_port")

        machine_stats = {
            "nodeInfo": {
                "node_name": node_name,
                "ip_address": ip_address,
                "node_port": node_port,
                "gpu_status": gpu_status,
                "node_idx": node_idx,
            }
        }

        # ---------------------------------------------
        # machine stats
        # ---------------------------------------------
        try:
            sys_stats = MachineStats.cutil_get_machine_stats(
                ip_address, host_port, period, gpu_status
            )
            machine_stats.update(sys_stats)
        except Exception as e:
            machine_stats["error"] = f"Failed to fetch system stats: {str(e)}"

        if not force_refresh:
            UserMgmnt.update_session_info(
                request.user,
                {
                    "cluster_name": cluster,
                    "node_name": node_name,
                    "service_name": None,
                }
            )

        return JsonResponse({
            "success": True,
            "machine_stats": machine_stats
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_get_service_performance(request):
    # try:
    json_data = request.POST.get("json_data")

    if not json_data:
        raise ValueError("No JSON data provided")

    data = json.loads(json_data)
    print(f"data = {data}")

    period = data.get("period", "24h")
    node_name = data.get("node", "")
    service_name = data.get("service", "")
    ip_address = data.get("ipAddress", "")
    force_refresh = data.get("refresh", False)

    service_info = ServiceConfig.service_get__node(node_name, service_name) or {}
    prometheus_info = ServiceConfig.service_get_prometheus__node(node_name) or {}

    service_type = service_info.get("serviceType")
    service_port = service_info.get("servicePort")
    prometheus_port = prometheus_info.get("hostPort")

    service_stats = {}
    prometheus_stats = {}
    # try:
    if service_port and "Infra" not in service_type:
        service_stats = cPlatformIO_service_stats(
            ip_address, service_port, period
        )
    # except Exception as e:
    #     service_stats = {
    #         "error": f"Failed to fetch stats: {str(e)}"
    #     }

    if prometheus_port and service_type:
        if service_type == "ANS":
            service_type = "ans"

        INFRA_SERVICE_MAPPING = systemMonitoring.get_infra_service_group_mapping()

        prometheus_stats = ServiceStats.cutil_get_service_stats(
            ip_address, prometheus_port, period, service_type, INFRA_SERVICE_MAPPING
        )

    if not force_refresh:
        UserMgmnt.update_session_info(
            request.user,
            {
                "node_name": node_name,
                "service_name": service_name,
            }
        )

    return JsonResponse({
        "success": True,
        "serviceInfo": service_info,
        "serviceStats": {
            "counterData": service_stats,
            "stats": prometheus_stats
        }
    })

    # except Exception as e:
    #     return JsonResponse({
    #         "success": False,
    #         "error": str(e)
    #     })


@login_required()
@require_http_methods(["GET"])
@csrf_exempt
def cPlatformIO_monitoring_view(request):
    from cPlatformIO.src.ServiceDiagnostics import _get_runtime_setting
    gt_base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    gt_org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")
    gt_token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
    gt_configured = bool(gt_base_url and gt_org and gt_token)

    gt_external_url = ""
    try:
        from pathlib import Path
        env_path = Path(__file__).resolve().parent.parent.parent / "platform/observability/glitchtip.env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GLITCHTIP_DOMAIN="):
                    gt_external_url = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
    if not gt_external_url:
        gt_external_url = gt_base_url

    session_info = {}
    try:
        session_info = UserMgmnt.get_session_info(request.user).get("last_visited", {})
    except Exception:
        pass

    context = {
        "session_info": json.dumps(session_info),
        "gt_configured": gt_configured,
        "gt_base_url": gt_base_url,
        "gt_external_url": gt_external_url,
        "gt_org": gt_org,
        "current_page": "Observability / Monitoring",
        "error": None,
        "stats": NodeConfig.node_get_monitoring_stats()
    }
    return render(request, "PlatformIO/Monitoring.html", context)


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_issues(request):
    """Fetch GlitchTip issues for a specific service."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _query_glitchtip,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        window = body.get("window", "24h")

        if not service_name:
            return JsonResponse({"success": False, "error": "service_name required"})

        cache_key = f"gt_issues_{service_name}_{window}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        obs_config = _normalize_observability_config(service_instance)
        issues = _query_glitchtip(service_instance, window, observability_config=obs_config)
        res = {"success": True, "issues": issues, "service_name": service_name, "window": window}
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_health(request):
    """Return live health status for a service (container up/down + issue count)."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _query_glitchtip,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        window = body.get("window", "24h")

        if not service_name:
            return JsonResponse({"success": False, "error": "service_name required"})

        cache_key = f"gt_health_{service_name}_{window}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        live_status = ServiceConfig.service_get_live_status(service_instance.service_id)
        obs_config = _normalize_observability_config(service_instance)
        issues = _query_glitchtip(service_instance, window, observability_config=obs_config)

        # Derive a health colour from live status
        container_state = (live_status or {}).get("main_container", {}).get("state", "unknown")
        running = str(container_state).lower() in ("running", "healthy", "up")
        error_count = sum(1 for i in issues if i.get("level") in ("error", "fatal"))
        warning_count = sum(1 for i in issues if i.get("level") == "warning")

        if not running:
            health = "error"
        elif error_count:
            health = "error"
        elif warning_count:
            health = "warn"
        else:
            health = "ok"

        project_slug = obs_config.get("glitchtip", {}).get("project_slug", "")

        res = {
            "success": True,
            "health": health,
            "running": running,
            "container_state": container_state,
            "issue_count": len(issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "service_name": service_name,
            "project_slug": project_slug,
        }
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["GET"])
@csrf_exempt
def cPlatformIO_monitoring_integration_status(request):
    """Return GlitchTip connectivity / configuration status."""
    from cPlatformIO.src.ServiceDiagnostics import _get_runtime_setting
    base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")
    token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
    configured = bool(base_url and org and token)

    reachable = False
    error_msg = ""
    if configured:
        try:
            resp = __import__("requests").get(
                f"{base_url}/api/0/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            reachable = resp.status_code < 500
        except Exception as exc:
            error_msg = str(exc)

    return JsonResponse({
        "success": True,
        "configured": configured,
        "reachable": reachable,
        "base_url": base_url,
        "org": org,
        "error": error_msg,
    })


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_uptime_list(request):
    """List uptime monitors for a specific service's project slug."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        if not service_name:
            return JsonResponse({"success": False, "error": "service_name required"})

        cache_key = f"gt_uptime_{service_name}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        obs_config = _normalize_observability_config(service_instance)
        project_slug = obs_config.get("glitchtip", {}).get("project_slug", "")
        if not project_slug:
            return JsonResponse({"success": True, "monitors": [], "project_slug": ""})

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
        org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")

        if not base_url or not token or not org:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{base_url}/api/0/organizations/{org}/monitors/", headers=headers, timeout=30)
        resp.raise_for_status()
        monitors = resp.json() or []

        # Filter monitors by project name/slug and fetch details to get response time
        project_slug = project_slug or ""
        filtered = []
        for m in monitors:
            if (m.get("projectName") or "").lower() == project_slug.lower():
                mon_id = m.get("id")
                if mon_id:
                    try:
                        # 1. Fetch details to get response_time and latest checks
                        detail_resp = requests.get(
                            f"{base_url}/api/0/organizations/{org}/monitors/{mon_id}/",
                            headers=headers,
                            timeout=5,
                        )
                        if detail_resp.status_code == 200:
                            m = detail_resp.json()

                        # 2. Fetch downtime transitions (incidents)
                        incidents_resp = requests.get(
                            f"{base_url}/api/0/organizations/{org}/monitors/{mon_id}/checks/",
                            params={"is_change": "true"},
                            headers=headers,
                            timeout=5,
                        )
                        if incidents_resp.status_code == 200:
                            m["incidents"] = incidents_resp.json() or []
                    except Exception:
                        pass
                filtered.append(m)

        res = {"success": True, "monitors": filtered, "project_slug": project_slug}
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_uptime_add(request):
    """Add a new uptime monitor for a specific service's project."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        name = body.get("name", "")
        monitor_type = body.get("monitor_type", "Ping")
        url = body.get("url", "")
        interval = int(body.get("interval", 60))
        expected_status = body.get("expected_status")
        timeout = body.get("timeout")
        expected_body = body.get("expected_body", "")

        if not service_name or not name or not url:
            return JsonResponse({"success": False, "error": "service_name, name, and url are required"})

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        obs_config = _normalize_observability_config(service_instance)
        project_slug = obs_config.get("glitchtip", {}).get("project_slug", "")
        if not project_slug:
            return JsonResponse({"success": False, "error": "No project mapped to this service"})

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
        org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")

        if not base_url or not token or not org:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # First, resolve project slug to project ID string via GlitchTip API
        proj_resp = requests.get(f"{base_url}/api/0/projects/{org}/{project_slug}/", headers=headers, timeout=5)
        proj_resp.raise_for_status()
        project_id = proj_resp.json().get("id")
        if not project_id:
            return JsonResponse({"success": False, "error": "Could not retrieve GlitchTip project ID"})

        payload = {
            "name": name,
            "monitorType": monitor_type,
            "url": url,
            "interval": interval,
            "project": str(project_id),
            "expectedBody": expected_body,
            "expectedStatus": int(expected_status) if expected_status is not None else 200,
            "timeout": int(timeout) if timeout is not None else 10
        }

        add_resp = requests.post(f"{base_url}/api/0/organizations/{org}/monitors/", json=payload, headers=headers, timeout=30)
        if add_resp.status_code >= 400:
            return JsonResponse({"success": False, "error": add_resp.text})

        return JsonResponse({"success": True, "monitor": add_resp.json()})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_uptime_delete(request):
    """Delete an uptime monitor from GlitchTip."""
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
    )
    try:
        body = json.loads(request.body)
        monitor_id = body.get("monitor_id")
        if not monitor_id:
            return JsonResponse({"success": False, "error": "monitor_id required"})

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
        org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")

        if not base_url or not token or not org:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}"}
        del_resp = requests.delete(f"{base_url}/api/0/organizations/{org}/monitors/{monitor_id}/", headers=headers, timeout=30)
        if del_resp.status_code >= 400:
            return JsonResponse({"success": False, "error": f"Failed to delete monitor: {del_resp.text}"})

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_issue_action(request):
    """Resolve or Ignore a GlitchTip issue."""
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
    )
    try:
        body = json.loads(request.body)
        issue_id = body.get("issue_id")
        action = body.get("action", "resolved") # e.g. "resolved" or "ignored" or "unresolved"

        if not issue_id:
            return JsonResponse({"success": False, "error": "issue_id required"})

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")

        if not base_url or not token:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"status": action}

        resp = requests.put(f"{base_url}/api/0/issues/{issue_id}/", json=payload, headers=headers, timeout=30)
        if resp.status_code >= 400:
            return JsonResponse({"success": False, "error": resp.text})

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_project_keys(request):
    """Retrieve DSN project keys for a service."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        if not service_name:
            return JsonResponse({"success": False, "error": "service_name required"})

        cache_key = f"gt_keys_{service_name}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        obs_config = _normalize_observability_config(service_instance)
        project_slug = obs_config.get("glitchtip", {}).get("project_slug", "")
        if not project_slug:
            return JsonResponse({"success": False, "error": "No project mapped to this service"})

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
        org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")

        if not base_url or not token or not org:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}"}
        keys_resp = requests.get(f"{base_url}/api/0/projects/{org}/{project_slug}/keys/", headers=headers, timeout=30)
        keys_resp.raise_for_status()
        keys = keys_resp.json() or []

        res = {"success": True, "keys": keys, "project_slug": project_slug}
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_issue_event_details(request):
    """Fetch latest event details (traceback, tags, breadcrumbs) for a specific issue from GlitchTip."""
    from cPlatformIO.src.ServiceDiagnostics import _get_runtime_setting
    try:
        body = json.loads(request.body)
        issue_id = body.get("issue_id")
        if not issue_id:
            return JsonResponse({"success": False, "error": "issue_id required"})

        cache_key = f"gt_event_details_{issue_id}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")

        if not base_url or not token:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}"}

        # Get latest event for this issue
        resp = requests.get(f"{base_url}/api/0/issues/{issue_id}/events/latest/", headers=headers, timeout=30)
        if resp.status_code == 404:
            res_404 = {"success": True, "event": None, "message": "No events found for this issue"}
            cache.set(cache_key, res_404, timeout=15)
            return JsonResponse(res_404)
        resp.raise_for_status()
        event_data = resp.json()

        res = {"success": True, "event": event_data}
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def cPlatformIO_monitoring_transaction_groups(request):
    """Fetch transaction groups for a specific service's project."""
    from cPlatformIO.models import Service
    from cPlatformIO.src.ServiceDiagnostics import (
        _get_runtime_setting,
        _normalize_observability_config,
    )
    try:
        body = json.loads(request.body)
        service_name = body.get("service_name", "")
        if not service_name:
            return JsonResponse({"success": False, "error": "service_name required"})

        cache_key = f"gt_transactions_{service_name}"
        cached_res = cache.get(cache_key)
        if cached_res:
            return JsonResponse(cached_res)

        service_instance = Service.objects.filter(service_name=service_name).first()
        if not service_instance:
            return JsonResponse({"success": False, "error": f"Service not found: {service_name}"})

        obs_config = _normalize_observability_config(service_instance)
        project_slug = obs_config.get("glitchtip", {}).get("project_slug", "")

        base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
        token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
        org = _get_runtime_setting("CPLATFORM_GLITCHTIP_ORG_SLUG", "")

        if not base_url or not token or not org:
            return JsonResponse({"success": False, "error": "GlitchTip not configured"})

        headers = {"Authorization": f"Bearer {token}"}

        project_id = None
        if project_slug:
            proj_resp = requests.get(f"{base_url}/api/0/projects/{org}/{project_slug}/", headers=headers, timeout=5)
            if proj_resp.status_code == 200:
                project_id = proj_resp.json().get("id")

        params = {}
        if project_id:
            params["project"] = str(project_id)

        node_ip = service_instance.Node.node_ip if (service_instance.Node and service_instance.Node.node_ip) else ""
        if node_ip and node_ip != "0.0.0.0":
            params["environment"] = node_ip

        # Call GlitchTip transaction-groups API
        tg_url = f"{base_url}/api/0/organizations/{org}/transaction-groups/"
        resp = requests.get(tg_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        transactions = resp.json() or []

        # Fallback if empty and environment filter was applied
        if not transactions and "environment" in params:
            params_fallback = params.copy()
            del params_fallback["environment"]
            try:
                resp_fallback = requests.get(tg_url, headers=headers, params=params_fallback, timeout=30)
                if resp_fallback.status_code == 200:
                    transactions = resp_fallback.json() or []
            except Exception:
                pass

        res = {"success": True, "transactions": transactions, "project_slug": project_slug, "node_ip": node_ip}
        cache.set(cache_key, res, timeout=15)
        return JsonResponse(res)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
def cPlatformIO_service_stats(service_ip, service_port, period):
    # try:
    print(f"service_ip, service_port, period == {service_ip, service_port, period}")

    # url = f"http://{service_ip}:{service_port}/cPlatformApp/APIv1/GetServiceStats/"
    url = f"http://{service_ip}:{service_port}/cPlatformApp/APIv1/GetServiceStats/"
    response = requests.post(
        url,
        json={
            "period": period,
        },
        timeout=15)
    response.raise_for_status()

    data = response.json()
    print(f"data=={data}")
    if isinstance(data, dict):
        if data.get("status") == "success":
            return data.get("data", {})
        return data
    else:
        return {"error": "Unexpected response type", "raw": data}

    # except requests.exceptions.RequestException as e:
    #     return {"error": f"Failed to fetch service stats: {str(e)}"}


@csrf_exempt
def cPlatformIO_report_demo(request):
    file_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormReportConfig.json')
    user_schema = getSchema.cutil_get_flow_schema(file_path)

    context = {
        'user_schema': json.dumps(user_schema),
    }

    return render(request, 'PlatformIO/ReportDemo.html', context)


@csrf_exempt
def cPlatformIO_report_timeout(request):
    json_status, json_msg, req_info = _cplatform_common_api_validation(request, 'report_timeout_handler_api')
    if json_status != 200:
        return JsonResponse(status=json_status, data={"msg": json_msg})
    ReportMgmt.cplatform_report_handler(req_info)
    return JsonResponse(status=200, data={})


@csrf_exempt
def cPlatformIO_widget_timeout(request):
    json_status, json_msg, req_info = _cplatform_common_api_validation(request, 'widget_timer_handler_api')
    if json_status != 200:
        return JsonResponse(status=json_status, data={"msg": json_msg})
    mcpWidget.mcp_widget_mail_handler(req_info)
    return JsonResponse(status=200, data={})


@csrf_exempt
def cPlatformIO_dataflow_timeout(request):
    json_status, json_msg, req_info = _cplatform_common_api_validation(request, 'dataflow_timeout_handler_api')
    if json_status != 200:
        return JsonResponse(status=json_status, data={"msg": json_msg})
    DataflowMgmt.dataflow_connection_handler(req_info)
    return JsonResponse(status=200, data={})


@csrf_exempt
def cPlatformIO_model_timeout(request):
    json_status, json_msg, req_info = _cplatform_common_api_validation(request, 'model_timeout_handler_api')
    if json_status != 200:
        return JsonResponse(status=json_status, data={"msg": json_msg})
    ModelMgmt.model_training_handler(req_info)
    return JsonResponse(status=200, data={})


@csrf_exempt
@login_required
def cPlatformIO_model_live_status(request):
    model_id = request.GET.get('model_id', '').strip()
    if not model_id:
        return JsonResponse({'error': 'model_id is required'}, status=400)

    try:
        model_instance = ModelInfo.objects.get(model_id=model_id)
    except ModelInfo.DoesNotExist:
        return JsonResponse({'error': f'Model {model_id} not found'}, status=404)

    # Read from file as fallback/cache first
    artifacts_dir = os.path.join(settings.REPOSITORY_PATH, "Models", str(model_id), "artifacts")
    file_path = os.path.join(artifacts_dir, "live_status.json")

    status_data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                status_data = json.load(f)
        except Exception as e:
            app_logger.error(f"Error reading live_status.json for model {model_id}: {e}")

    # Try fetching from dtrain directly to get the absolute latest status if the model is still training
    service_ins = model_instance.service
    if service_ins:
        ret, service_ip, service_port = ServiceConfig.service_get_route(service_ins)
        if ret and service_ip and service_port:
            url = f"http://{service_ip}:{service_port}/TrainingServer/APIv1/LiveStatus/?model_id={model_id}"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    status_data = response.json()
                    # Write to file
                    os.makedirs(artifacts_dir, exist_ok=True)
                    with open(file_path, 'w') as f:
                        json.dump(status_data, f, indent=4)
            except Exception as e:
                # If dtrain is unreachable, fall back to cached file data
                app_logger.debug(f"dtrain server unreachable for model {model_id}: {e}")

    if status_data:
        return JsonResponse(status_data)
    else:
        # Default status
        return JsonResponse({
            'model_id': model_id,
            'stage': 'Initializing',
            'logs': [],
            'epoch': None,
            'total_epochs': None,
            'updated_at': ''
        })


@require_http_methods(["GET", "POST"])
@login_required
def cPlatformIO_batch_ingress_download(request):
    app_logger.debug(f"cPlatformIO_batch_ingress_download, request={request.body}")
    req_info = json.loads(request.body.decode('utf-8'))
    log_id = req_info.get('log_id')
    file_name = DataflowMgmt.dataflow_get_log_report(log_id)
    if file_name:
        path = settings.REPOSITORY_PATH
        modify_path = path / "DataflowReports" / file_name.split('_')[0] / file_name
        response = FileResponse(open(modify_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    else:
        app_logger.exception("No matching file")
        return JsonResponse({'error': "No matching file"}, status=500)


@require_http_methods(["GET", "POST"])
@login_required
def cPlatformIO_stream_ingress_download(request):
    app_logger.debug(f"cPlatformIO_stream_ingress_download, request={request.body}")
    req_info = json.loads(request.body.decode('utf-8'))
    log_id = req_info.get('log_id')
    file_name = DataflowMgmt.dataflow_get_log_report(log_id)
    if file_name:
        path = settings.REPOSITORY_PATH
        modify_path = path / "DataflowReports" / file_name.split('_')[0] / file_name
        response = FileResponse(open(modify_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    else:
        app_logger.exception("No matching file")
        return JsonResponse({'error': "No matching file"}, status=500)


@csrf_exempt
def cPlatformIO_get_app_list(request):
    app_list = AppConfig.get_app_lists()
    return JsonResponse({'app_list': app_list})

@csrf_exempt
def ctaw_get_service_stats(request):
    request_info = json.loads(request.body.decode('utf-8'))

    print(f"ctaw_get_service_stats, request_info == {request_info}")

    stats_info = ServiceMonitoring.ctaw_service_stats(
        request_info.get('service_ip'),
        request_info.get('service_port'),
        request_info.get('service_type'),
        request_info.get('period')
    )
    app_logger.debug(f"service_monitoring: {stats_info}")
    return JsonResponse(status=200, data=stats_info)

@csrf_exempt
def cPlatformIO_create_user(request):
    data = json.loads(request.body)
    msg = UserMgmnt.user_add_request(data.get("fname"), data.get("email"),data.get("password"),data.get("user_role"),data.get("user_number"))

    user_ins = UserMgmnt.user_get_instance__mail(data.get("email"))
    payload = {"user_id": user_ins.user_id,
               "user_mail": data.get("email"),
               "user_name": user_ins.user_name,
               "user_role": user_ins.user_role,
               "user_number": user_ins.user_number,
               "first_name": getattr(user_ins, "first_name", ""),
               "last_name": getattr(user_ins, "last_name", ""),
               "session_info": user_ins.session_info,
               "created_date": user_ins.created_date,
               "password": data.get("password")
               }
    return JsonResponse({'msg': msg,'data':payload}, status=200)

@csrf_exempt
def cPlatformIO_update_user(request):
    data = json.loads(request.body)
    user_ins = UserMgmnt._update_user(data.get("fname"), data.get("email"), data.get("password"), data.get("user_number"))

    return JsonResponse({'msg': {
        "user_id": user_ins.user_id,
        "user_name": user_ins.user_name,
        "user_email": user_ins.user_email,
        "user_number": user_ins.user_number,
    }}, status=200)


@csrf_exempt
def cPlatformIO_ingestion_agent(request):
    if request.method == "POST":
        data = json.loads(request.body)
        llm = dspy.LM(api_base=f"http://{PlatformSettings.llm_host}:{PlatformSettings.llm_port}",
                      model="ollama_chat/distil-qwen3-4b-text2sql", temperature=0.0)
        interval = int(data.get("interval_days"))
        results = DataflowAIIngMgmt.run_ingestion_agent(llm,interval)
        response = [{"dataflow_id": r.dataflow_id, "result": r.result, "issues": r.issues, "summary": r.summary}
                    for r in results]
        return JsonResponse({'msg': response}, status=200)

    return JsonResponse({"error": "POST required"}, status=400)

def accept_invite_view(request, token):
    print(f"\nfxn: accept_invite_view....request, token : {request, token} ")
    try:
        invite = InviteToken.objects.get(token=token)
    except InviteToken.DoesNotExist:
        return render(request, 'PlatformIO/01a-invite-accept.html', {'state': 'revoked', 'invite': None})

    # Determine state
    if invite.is_used:
        state = 'used'
    elif invite.is_revoked:
        state = 'revoked'
    elif timezone.now() > invite.created_at + timedelta(days=30):
        state = 'expired'
    else:
        state = 'valid'

    # Handle form submission
    if request.method == 'POST' and state == 'valid':
        full_name  = request.POST.get('full_name', '').strip()
        password   = request.POST.get('password', '')

        if not full_name or not password:
            return JsonResponse({'status': 'err', 'msg': 'Name and password are required'})

        # Create the Django user
        user = User.objects.create_user(
            username   = invite.user_email,
            email      = invite.user_email,
            password   = password,
            first_name = full_name.split()[0],
            last_name  = ' '.join(full_name.split()[1:]),
        )

        # Mark invite as used
        # Mark invite as used
        invite.is_used = True
        invite.save()

        # Activate the UserInfo record
        UserInfo.objects.filter(user_email=invite.user_email).update(status='active')
        #
        # # Log them in
        # login(request, user)

        return JsonResponse({'status': 'ok'})
    cplatform_url = PlatformSettings.cplatform_url
    return render(request, 'PlatformIO/01a-invite-accept.html', {
        'state':  state,
        'invite': invite,
        'cplatform_url' : cplatform_url
    })


@csrf_exempt
def cPlatformIO_config_manager_view(request):
    app_logger.debug(f"fxn: cPlatformIO_config_manager_view , request = {request.body}")
    if request.method == 'POST':
        try:
            request_info = json.loads(request.body)
        except Exception:
            request_info = request.POST

        user_action = request_info.get('user-action')

        if user_action == 'track_visit':
            snapshot = {
                'cluster_name': request_info.get('cluster_name', ''),
                'node_name': request_info.get('node_name', ''),
                'service_name': request_info.get('service_name', ''),
            }
            UserMgmnt.user_update_last_visited(str(request.user), snapshot)
            return JsonResponse({'success': True})

        service_id = request_info.get('service_id')
        if not Service.objects.filter(service_id=service_id).exists():
            return JsonResponse({"success": False, "error": "Service not found"})

        service_instance = Service.objects.get(service_id=service_id)

        if user_action == 'get_service_workspace':
            runtime_target = ServiceConfig.service_get_runtime_config_target(service_instance)
            config_capabilities = runtime_target.get("config_capabilities", {})
            # Fetch config store snapshots
            store_info = ServiceConfig.service_get_config_store(service_id)
            snapshots = store_info.get("snapshots", [])

            # Load active/current config cleanly (READ-ONLY)
            current_config = ""
            has_loaded = False
            config_source = "empty"
            config_source_label = "No config found"

            # 1. Try to read from latest snapshot if it exists
            if snapshots:
                latest_snap = snapshots[0]
                ok, msg, content = ServiceConfig.service_get_snapshot_content(
                    service_id, latest_snap["version"], latest_snap["timestamp"]
                )
                if ok:
                    current_config = content
                    has_loaded = True
                    config_source = "latest_checkpoint"
                    config_source_label = f"Latest checkpoint v{latest_snap.get('version', '-')}"

            # 2. Fallback: load current DB config dict representation
            if not has_loaded:
                db_config = getattr(service_instance, "service_config", {})
                if db_config:
                    current_config = yaml.dump(db_config, default_flow_style=False)
                    config_source = "database_fallback"
                    config_source_label = "Database fallback"
                else:
                    current_config = "# No configuration found. Save a checkpoint or edit to start.\n"

            # Calculate dynamic metrics/context
            snapshot_count = len(snapshots)
            active_checkpoint = snapshots[0] if snapshots else None
            last_sync = active_checkpoint.get("display_date", "Never") if active_checkpoint else "Never"
            last_modified = active_checkpoint.get("timestamp", "Never") if active_checkpoint else "Never"

            node_volume = getattr(service_instance.Node, "node_volume", "vol1").lstrip("/")
            service_name = runtime_target.get("config_service_name") or service_instance.service_type or service_instance.service_name or service_instance.service_id
            config_path = config_capabilities.get("config_path") or f"/iktara/data/volume/{node_volume}/config/{service_name}/config.yaml"
            file_label = f"{runtime_target.get('container_name') or service_name}/config.yaml"

            # This comparison is workspace/editor content against the active checkpoint.
            # A separate live-container read is required before calling this true runtime drift.
            drift_state = "Editor matches active checkpoint"
            if active_checkpoint:
                ok, msg, snap_content = ServiceConfig.service_get_snapshot_content(
                    service_id, active_checkpoint["version"], active_checkpoint["timestamp"]
                )
                if ok and snap_content.strip() != current_config.strip():
                    drift_state = "Editor differs from active checkpoint"
            elif snapshot_count > 0:
                drift_state = "Editor differs from checkpoint history"
            else:
                drift_state = "No checkpoint captured yet"

            # Get peer nodes of the same type in this cluster
            cluster = service_instance.Node.Cluster
            peers = Service.objects.filter(Node__Cluster=cluster, service_type=service_instance.service_type).exclude(service_id=service_id)
            peer_list = []
            for peer in peers:
                peer_list.append({
                    "service_id": peer.service_id,
                    "service_name": peer.service_name,
                    "node_name": peer.Node.node_name,
                    "node_ip": peer.Node.node_ip,
                })

            db_config = getattr(service_instance, "service_config", {})
            if db_config:
                database_fallback_config = yaml.dump(db_config, default_flow_style=False)
            else:
                database_fallback_config = "# No database configuration fallback found.\n"

            return JsonResponse({
                "success": True,
                "snapshots": snapshots,
                "current_config": current_config,
                "database_fallback_config": database_fallback_config,
                "peers": peer_list,
                "drift_state": drift_state,
                "last_sync": last_sync,
                "last_modified": last_modified,
                "snapshot_count": snapshot_count,
                "config_source": config_source,
                "config_source_label": config_source_label,
                "config_path": config_path,
                "file_label": file_label,
                "runtime_target": runtime_target,
                "config_capabilities": config_capabilities,
                "active_checkpoint": active_checkpoint,
                "service_info": {
                    "service_id": service_instance.service_id,
                    "service_name": service_instance.service_name,
                    "service_type": service_instance.service_type,
                    "service_version": service_instance.service_version,
                    "node_name": service_instance.Node.node_name,
                    "cluster_name": cluster.cluster_name,
                }
            })

        elif user_action == 'create_checkpoint':
            ret, msg, snapshot_path = ServiceConfig.service_run_config_checkpoint(service_id)
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            store_info = ServiceConfig.service_get_config_store(service_id)
            snapshots = store_info.get("snapshots", [])
            return JsonResponse({
                "success": True,
                "msg": "Checkpoint successfully captured!",
                "snapshots": snapshots,
                "active_checkpoint": snapshots[0] if snapshots else None
            })

        elif user_action == 'rename_checkpoint':
            version = request_info.get('version')
            timestamp = request_info.get('timestamp')
            new_name = request_info.get('new_name')
            ret, msg, payload = ServiceConfig.service_rename_config_snapshot(
                service_id,
                version,
                timestamp,
                new_name,
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            return JsonResponse({
                "success": True,
                "msg": msg,
                "snapshot": payload.get("snapshot", {}),
                "snapshots": payload.get("snapshots", []),
                "active_checkpoint": payload.get("snapshots", [None])[0] if payload.get("snapshots") else None,
            })

        elif user_action == 'view_snapshot':
            version = request_info.get('version')
            timestamp = request_info.get('timestamp')
            ret, msg, content = ServiceConfig.service_get_snapshot_content(
                service_id,
                version,
                timestamp
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            return JsonResponse({
                "success": True,
                "msg": "Snapshot content loaded successfully!",
                "content": content,
                "version": version,
                "timestamp": timestamp,
            })

        elif user_action == 'prepare_migration':
            source_snapshot = {
                "version": request_info.get('source_version'),
                "timestamp": request_info.get('source_timestamp'),
            }
            target_snapshot = {
                "version": request_info.get('target_version'),
                "timestamp": request_info.get('target_timestamp'),
            }
            ret, msg, payload = ServiceConfig.service_prepare_snapshot_migrate_payload(
                service_id,
                source_snapshot,
                target_snapshot
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            return JsonResponse({
                "success": True,
                "msg": msg,
                "selected_configs": payload.get("selected_configs", {}),
                "ranked_configs": payload.get("ranked_configs", {}),
                "config_rank_1": payload.get("config_rank_1", {}),
                "config_rank_2": payload.get("config_rank_2", {}),
                "migration_ops": payload.get("migration_ops", []),
                "migrated_config": payload.get("migrated_config", {}),
                "final_merged_config": payload.get("final_merged_config", {}),
                "final_merged_config_yaml": payload.get("final_merged_config_yaml", ""),
                "migration_artifact": payload.get("migration_artifact", {}),
            })

        elif user_action == 'direct_apply_config':
            yaml_text = request_info.get('yaml_text', '')
            apply_mode = request_info.get('apply_mode', 'reload')

            node_instance = service_instance.Node
            runtime_target = ServiceConfig.service_get_runtime_config_target(service_instance)
            config_capabilities = runtime_target.get("config_capabilities", {})
            if not config_capabilities.get("apply_enabled", True):
                return JsonResponse({
                    "success": False,
                    "error": config_capabilities.get("disabled_reason") or "Config apply is disabled for this service"
                })
            if config_capabilities.get("restart_required") and apply_mode == "reload":
                apply_mode = "restart"

            config_is_yaml = config_capabilities.get("config_is_yaml", True)

            # Validate YAML only if it is a yaml file
            if config_is_yaml:
                val_ret, val_msg, val_payload = ServiceConfig.service_validate_yaml_text(yaml_text)
                if not val_ret:
                    return JsonResponse({"success": False, "error": f"Invalid YAML: {val_msg}"})

            # Parse YAML into dict to update database
            if config_is_yaml:
                try:
                    config_dict = yaml.safe_load(yaml_text)
                except Exception as e:
                    return JsonResponse({"success": False, "error": f"YAML parse error: {str(e)}"})
            else:
                try:
                    config_dict = yaml.safe_load(yaml_text)
                    if not isinstance(config_dict, dict):
                        config_dict = {"raw_content": yaml_text}
                except Exception:
                    config_dict = {"raw_content": yaml_text}

            # 1. Capture current config checkpoint before overwriting (Rollback protection)
            ServiceConfig.service_run_config_checkpoint(service_id)

            # 2. Apply to node
            from cPlatformIO.src import serviceInstall
            apply_res = serviceInstall.sInstall_apply_service_config_migration(
                service_instance,
                node_instance.node_id,
                yaml_text,
                apply_mode=apply_mode,
                container_name=runtime_target.get("container_name") or service_instance.service_id,
                service_name=runtime_target.get("config_service_name") or service_instance.service_type or service_instance.service_name,
                version=runtime_target.get("config_version") or service_instance.service_version,
                config_path=config_capabilities.get("config_path") or None,
                node_volume=node_instance.node_volume,
            )

            if not apply_res.get("success", False):
                return JsonResponse({"success": False, "error": apply_res.get("error", "Failed to apply config")})

            # 3. Synchronize database
            service_instance.service_config = config_dict
            service_instance.save()

            # 4. Capture a new checkpoint of the applied config so it's logged in history
            ServiceConfig.service_run_config_checkpoint(service_id)

            store_info = ServiceConfig.service_get_config_store(service_id)
            return JsonResponse({
                "success": True,
                "msg": "Config applied successfully!",
                "snapshots": store_info.get("snapshots", []),
                "details": apply_res
            })

        elif user_action == 'apply_migration':
            migration_artifact_id = request_info.get('migration_artifact_id')
            apply_mode = request_info.get('apply_mode', 'reload')
            edited_migration_yaml = request_info.get('edited_migration_yaml', '')
            ret, msg, payload = ServiceConfig.service_apply_snapshot_migration(
                service_id,
                migration_artifact_id,
                apply_mode=apply_mode,
                edited_migration_yaml=edited_migration_yaml,
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            store_info = ServiceConfig.service_get_config_store(service_id)
            return JsonResponse({
                "success": True,
                "msg": msg,
                "artifact_id": payload.get("artifact_id", ""),
                "apply_result": payload.get("apply_result", {}),
                "snapshots": store_info.get("snapshots", []),
            })

        elif user_action == 'restore_migration':
            backup_path = request_info.get('backup_path')
            resolved_config_path = request_info.get('resolved_config_path')
            apply_mode = request_info.get('apply_mode', 'reload')
            ret, msg, payload = ServiceConfig.service_restore_snapshot_migration(
                service_id,
                backup_path,
                resolved_config_path,
                apply_mode=apply_mode,
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            store_info = ServiceConfig.service_get_config_store(service_id)
            return JsonResponse({
                "success": True,
                "msg": msg,
                "restore_result": payload.get("restore_result", {}),
                "snapshots": store_info.get("snapshots", []),
            })

        elif user_action == 'validate_yaml':
            yaml_text = request_info.get('yaml_text', '')
            runtime_target = ServiceConfig.service_get_runtime_config_target(service_instance)
            config_capabilities = runtime_target.get("config_capabilities", {})
            config_is_yaml = config_capabilities.get("config_is_yaml", True)

            if config_is_yaml:
                val_ret, val_msg, val_payload = ServiceConfig.service_validate_yaml_text(yaml_text)
            else:
                val_ret, val_msg, val_payload = True, "Config format is not YAML (validation bypassed)", {}

            return JsonResponse({
                "success": val_ret,
                "msg": val_msg,
                "details": val_payload
            })

        elif user_action == 'get_snapshots_diff':
            snap1 = request_info.get('snap1', {})
            snap2 = request_info.get('snap2', {})
            ok, msg, diff_html = ServiceConfig.service_get_snapshots_diff(service_id, snap1, snap2)
            return JsonResponse({
                "success": ok,
                "msg": msg,
                "diff_html": diff_html
            })

        return JsonResponse({"success": False, "error": "Invalid action"})

    # GET request: render Config Manager view
    cluster_info = ClusterConfig.cluster_get_config_info_v2(None)

    # Selected parameters for deep-linking
    selected_cluster_id = request.GET.get('cluster_id', '')
    selected_node_id = request.GET.get('node_id', '')
    selected_service_id = request.GET.get('service_id', '')

    session_last_visited = {}
    try:
        user_info = UserInfo.objects.get(user_email=request.user)
        session_last_visited = user_info.session_info.get('last_visited', {})
    except Exception as e:
        app_logger.error(f"ERROR: {e}")
        print(f"ERROR: {e}")

    return render(request, 'PlatformIO/08-config-manager.html', {
        'cluster_info': cluster_info,
        'selected_cluster_id': selected_cluster_id,
        'selected_node_id': selected_node_id,
        'selected_service_id': selected_service_id,
        'session_last_visited': session_last_visited,
        'current_page': 'Infrastructure / Config Manager',
        'breadcrumb_items': [
            {'label': 'Infrastructure', 'href': '/PlatformIO/ClusterView/'},
            {'label': 'Config Manager', 'href': ''},
        ],
        "config_stats": NodeConfig.node_get_monitoring_stats()
    })


@csrf_exempt
def cPlatformIO_model_create_view(request):
    # Detect edit / view mode from query string
    page_mode   = request.GET.get('mode', 'create')   # 'create' | 'edit' | 'view'
    edit_model_name = request.GET.get('model_name', '')

    # prepare the context
    file1_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormModel.json')
    file2_path = os.path.join(BASE_DIR, 'cPlatform/cPlatformIO/forms/dFormAlgo.json')
    model_schema = getSchema.cutil_get_flow_schema(file1_path)
    algo_schema = getSchema.cutil_get_flow_schema(file2_path)
    updated_schema = getSchema.convert_row_schema(algo_schema, model_schema)
    retriever_options = ModelMgmt.model_get_retriever_options()
    algo_options = ModelMgmt.model_get_algo_options()
    model_data = ModelMgmt.model_get_info()
    trn_In_Progress = len([model for model in model_data if model.get("training_status") == "TrainingInProgress"])
    trn_completed = len([model for model in model_data if model.get("training_status") == "TrainingComplete"])
    trn_failed = len([model for model in model_data if model.get("training_status") == "TrainingFailed"])
    trn_schedule = len([model for model in model_data if model.get("training_status") == "Scheduled"])

    training_info = ClusterConfig.cluster_get_service_list(None, "TrainingServer")
    ans_info = ClusterConfig.cluster_get_service_list(None, "optionCopilot")
    application_info = ServiceConfig.service_get_application_info()
    dataflow_info_list = DataflowMgmt.model_get_dataflow_info_list()
    cluster_info = ClusterConfig.cluster_get_config_info_v2()

    # For edit/view: fetch the existing model's data so the template can pre-populate
    edit_model_data = {}
    if page_mode in ('edit', 'view') and edit_model_name:
        model_info_list = ModelMgmt.model_get_info(edit_model_name)
        if model_info_list:
            edit_model_data = model_info_list[0]
            # Ensure training_status is correct (view mode for non-Scheduled)
            if edit_model_data.get('training_status') != 'Scheduled':
                page_mode = 'view'

    context = {
        "retriever_options": retriever_options, "training_info": training_info, "service_list": ans_info,
        "model_schema": json.loads(updated_schema), "algo_options": algo_options, "model_data": model_data,
        "application_info": application_info, "dataflow_info_list": dataflow_info_list,
        "trn_in_progress": trn_In_Progress, "trn_complete": trn_completed, "trn_failed": trn_failed,
        "trn_schedule": trn_schedule, "cluster_info": cluster_info, 'cluster_info_json': json.dumps(cluster_info),
        "algo_schema": algo_schema,
        # edit/view mode extras
        "page_mode": page_mode,
        "edit_model_name": edit_model_name,
        "edit_model_data_json": json.dumps(edit_model_data),
    }
    return render(request, 'PlatformIO/modelCreate.html', context)


@csrf_exempt
@login_required
def cPlatformIO_db_pull_infer_view(request):
    """
    Page + API for DB Pull Inference.
    GET  → render DBPullInfer.html with model list + job history
    POST user_action=trigger  → create job, forward to dInfer, return {job_id}
    POST user_action=job_list → return current job list as JSON
    POST user_action=job_detail → return one job + its logs
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'status': 'error', 'msg': 'Invalid JSON'}, status=400)

        user_action = body.get('user_action')

        if user_action == 'trigger':
            ret, result = DBPullInferenceMgmt.job_create(body, str(request.user))
            if not ret:
                return JsonResponse({'status': 'error', 'msg': result}, status=400)
            job_id = result
            cplatform_url = request.build_absolute_uri('/').rstrip('/')
            ret2, msg2 = DBPullInferenceMgmt.job_trigger_inference(job_id, cplatform_url)
            if not ret2:
                return JsonResponse({'status': 'error', 'job_id': job_id, 'msg': msg2}, status=200)
            return JsonResponse({'status': 'ack', 'job_id': job_id,
                                 'msg': 'Job accepted — inference running asynchronously'}, status=202)

        if user_action == 'job_list':
            return JsonResponse({'status': 'success', 'data': DBPullInferenceMgmt.job_get_list()}, status=200)

        if user_action == 'job_detail':
            job_id = body.get('job_id')
            return JsonResponse({'status': 'success', 'data': DBPullInferenceMgmt.job_get_detail(job_id)}, status=200)

        if user_action == 'job_config':
            job_id = body.get('job_id')
            config = DBPullInferenceMgmt.get_job_config(job_id)
            app_logger.debug(f"config -- {config}")
            if config is None:
                return JsonResponse({'status': 'error', 'msg': 'Job not found'}, status=404)
            return JsonResponse({'status': 'success', 'data': config}, status=200)

        if user_action == 'job_artifacts':
            model_name = body.get('model_name')
            return JsonResponse({
                'status': 'success',
                'data': ModelInferMgmt.get_artifacts(model_name)
            }, status=200)

        return JsonResponse({'status': 'error', 'msg': 'Unknown user_action'}, status=400)

    # GET — render page
    model_data = ModelMgmt.model_get_info()
    model_infer_data = ModelInferMgmt.model_infer_get_info()
    job_list = DBPullInferenceMgmt.job_get_list()
    context = {
        'model_data': model_data,
        'model_infer_data': model_infer_data,
        'job_list': job_list,
        'current_page': 'Models / DB Pull Inference',
    }
    return render(request, 'PlatformIO/DBPullInfer.html', context)


@csrf_exempt
def cPlatformIO_db_pull_infer_callback(request):
    """
    Receives the completion callback POSTed by the dInfer server
    when a DB pull inference job finishes (or fails).
    No authentication — called server-to-server.
    """
    app_logger.info(f" -- cPlatformIO_db_pull_infer_callback --")
    # print(f"DBPull callback content_type={request.content_type}")
    # print(f"DBPull callback POST keys={list(request.POST.keys())}")
    # print(f"DBPull callback FILE keys={list(request.FILES.keys())}")

    try:
        if request.POST.get("payload"):
            callback_data = json.loads(request.POST["payload"])
        elif request.body:
            callback_data = json.loads(request.body)
        else:
            callback_data = {}
    except json.JSONDecodeError as exc:
        print(f"DBPull callback invalid payload body={request.body[:500]!r}")
        return JsonResponse({'status': 'error', 'msg': f'Invalid callback JSON: {exc}'}, status=400)

    # print(f"DBPull callback payload keys={list(callback_data.keys())}")
    # print(f"DBPull callback payload={callback_data}")

    files_dict = request.FILES

    try:
        DBPullInferenceMgmt.handle_completion_callback(callback_data, files_dict)
    except Exception as exc:
        app_logger.error(f"cPlatformIO_db_pull_infer_callback error: {exc}")
        return JsonResponse({'status': 'error', 'msg': str(exc)}, status=500)

    return JsonResponse({'status': 'success'}, status=200)


@csrf_exempt
def cPlatformIO_get_inference_metrics(request):
    """
    Relay inference metrics from the dInfer server to the browser.

    POST body:
        {
            "model_id":       "MODEL1062",          # required
            "window_seconds": 3600,                 # optional, default 1 h
            "service_name":   "InferenceServer-1"   # optional, auto-detect if omitted
        }
    """
    try:
        request_info = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({"status": "error", "msg": "Invalid JSON body"}, status=400)

    model_id = request_info.get("model_id")
    if not model_id:
        return JsonResponse({"status": "error", "msg": "model_id is required"}, status=400)

    window_seconds = int(request_info.get("window_seconds", 3600))
    service_name = request_info.get("service_name")

    service_ip, service_port = InferenceMetricsMgmt.resolve_inference_server(service_name)
    if not service_ip:
        return JsonResponse(
            {"status": "error", "msg": "No InferenceServer configured in platform"},
            status=404,
        )

    ret, data = InferenceMetricsMgmt.get_inference_metrics(
        model_id, service_ip, service_port, window_seconds
    )
    if ret:
        return JsonResponse({"status": "success", "data": data}, status=200)
    return JsonResponse({"status": "error", "data": data}, status=200)


@csrf_exempt
def cPlatformIO_diagnostics_view(request):
    from cPlatformIO.models import Service
    from cPlatformIO.src import ServiceDiagnostics, ClusterConfig

    if request.method == 'POST':
        try:
            request_info = json.loads(request.body)
        except Exception:
            request_info = request.POST

        user_action = request_info.get('user-action')

        if user_action == 'track_visit':
            snapshot = {
                'cluster_name': request_info.get('cluster_name', ''),
                'node_name': request_info.get('node_name', ''),
                'service_name': request_info.get('service_name', ''),
            }
            UserMgmnt.user_update_last_visited(str(request.user), snapshot)
            return JsonResponse({'success': True})

        elif user_action == 'global_diagnostics_metrics':
            metrics = ServiceDiagnostics.get_global_diagnostics_metrics()
            return JsonResponse({'success': True, 'metrics': metrics})

        service_id = request_info.get('service_id')

        if user_action == 'service_log_analytics_chat':
            question = request_info.get('question', '')
            window = request_info.get('window', 'current')
            diagnostic_target = request_info.get('diagnostic_target', 'main')
            history = request_info.get('history', [])

            chat_result = ServiceDiagnostics.service_log_analytics_chat(
                service_id,
                question=question,
                window=window,
                diagnostic_target=diagnostic_target,
                history=history
            )
            return JsonResponse(chat_result)

        elif user_action == 'service_list_log_files':
            diagnostic_target = request_info.get('diagnostic_target', 'main')
            files_result = ServiceDiagnostics.service_list_log_files(
                service_id,
                diagnostic_target=diagnostic_target
            )
            return JsonResponse(files_result)

        elif user_action == 'service_live_logs':
            diagnostic_target = request_info.get("diagnostic_target", "main")
            tail_lines = request_info.get("tail_lines", "200")
            cursor = request_info.get("cursor", "")
            window = request_info.get("window", "current")
            log_source = request_info.get("log_source", "container_live")
            file_stream = request_info.get("file_stream", "all")
            page_size = request_info.get("page_size", "200")
            history_cursor = request_info.get("history_cursor", "")
            history_direction = request_info.get("history_direction", "latest")
            history_page = request_info.get("history_page", "0")
            service_live_logs = ServiceDiagnostics.service_get_live_logs(
                service_id,
                diagnostic_target=diagnostic_target,
                tail_lines=tail_lines,
                cursor=cursor,
                window=window,
                log_source=log_source,
                file_stream=file_stream,
                page_size=page_size,
                history_cursor=history_cursor,
                history_direction=history_direction,
                history_page=history_page,
            )
            return JsonResponse({"success": True, "service_live_logs": service_live_logs})

        elif user_action == 'service_diagnostics':
            window = request_info.get("window", "current")
            diagnostic_target = request_info.get("diagnostic_target", "main")
            service_diagnostics = ServiceDiagnostics.service_get_diagnostics(service_id, window, diagnostic_target)
            return JsonResponse({"success": True, "service_diagnostics": service_diagnostics})

        elif user_action == 'service_log_backfill':
            diagnostic_target = request_info.get("diagnostic_target", "main")
            backfill_result = ServiceDiagnostics.service_run_log_backfill(service_id, diagnostic_target=diagnostic_target)
            return JsonResponse({
                "success": backfill_result.get("success", False),
                "msg": backfill_result.get("msg", ""),
                "service_log_backfill": backfill_result.get("result", {}),
            })

        elif user_action == 'service_download_log_file':
            file_name = request_info.get('file_name', '')
            file_id = request_info.get('file_id', '')
            diagnostic_target = request_info.get('diagnostic_target', 'main')
            download_result = ServiceDiagnostics.service_download_log_file(
                service_id,
                file_name,
                diagnostic_target=diagnostic_target,
                file_id=file_id,
            )
            if download_result.get("success"):
                file_path = download_result["file_path"]
                response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=download_result.get("file_name", file_name))
                return response
            else:
                return JsonResponse({"success": False, "error": download_result.get("error", "File not found")})

        elif user_action == 'service_view_log_file':
            file_name = request_info.get('file_name', '')
            file_id = request_info.get('file_id', '')
            diagnostic_target = request_info.get('diagnostic_target', 'main')
            preview_result = ServiceDiagnostics.service_view_log_file(
                service_id,
                file_name,
                diagnostic_target=diagnostic_target,
                file_id=file_id,
                limit=request_info.get('limit', 300),
            )
            return JsonResponse(preview_result)

        elif user_action == 'service_download_bulk_logs':
            file_names = request_info.get('file_names', [])
            file_ids = request_info.get('file_ids', [])
            diagnostic_target = request_info.get('diagnostic_target', 'main')

            import zipfile
            import tempfile

            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            try:
                with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
                    request_items = []
                    if isinstance(file_ids, list) and file_ids:
                        for idx, file_id in enumerate(file_ids):
                            fallback_name = file_names[idx] if idx < len(file_names) else ''
                            request_items.append({"file_id": file_id, "file_name": fallback_name})
                    else:
                        for fname in file_names:
                            request_items.append({"file_id": "", "file_name": fname})

                    for item in request_items:
                        download_result = ServiceDiagnostics.service_download_log_file(
                            service_id,
                            item.get("file_name", ""),
                            diagnostic_target=diagnostic_target,
                            file_id=item.get("file_id", ""),
                        )
                        if download_result.get("success"):
                            zip_file.write(download_result["file_path"], arcname=download_result.get("file_name", item.get("file_name", "")))

                response = FileResponse(open(temp_zip.name, 'rb'), as_attachment=True, filename=f"{service_id}_bulk_logs.zip")
                return response
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Invalid action"})

    # GET request: render diagnostics view
    cluster_info = ClusterConfig.cluster_get_config_info_v2(None)

    selected_cluster_id = request.GET.get('cluster_id', '')
    selected_node_id = request.GET.get('node_id', '')
    selected_service_id = request.GET.get('service_id', '')

    session_last_visited = {}
    try:
        user_info = UserInfo.objects.get(user_email=str(request.user))
        print("DEBUG session_info:", user_info.session_info)
        session_last_visited = user_info.session_info.get('last_visited', {})
    except Exception:
        pass

    return render(request, 'PlatformIO/09-diagnostics.html', {
        'cluster_info': cluster_info,
        'selected_cluster_id': selected_cluster_id,
        'selected_node_id': selected_node_id,
        'selected_service_id': selected_service_id,
        'session_last_visited': session_last_visited,
        'current_page': 'Infrastructure / Diagnostics',
        'breadcrumb_items': [
            {'label': 'Infrastructure', 'href': '/PlatformIO/ClusterView/'},
            {'label': 'Diagnostics', 'href': ''},
        ],
    })


@login_required()
@require_http_methods(["GET"])
def cPlatformIO_glitchtip_health(request):
    from cPlatformIO.src.ServiceDiagnostics import _get_runtime_setting
    base_url = _get_runtime_setting("CPLATFORM_GLITCHTIP_BASE_URL", "").rstrip("/")
    token = _get_runtime_setting("CPLATFORM_GLITCHTIP_TOKEN", "")
    if not base_url or not token:
        return JsonResponse({"status": "unconfigured"})
    url = f"{base_url}/api/0/organizations/"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return JsonResponse({"status": "ok"})
        return JsonResponse({"status": "error", "code": response.status_code})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@login_required()
@require_http_methods(["POST"])
def cPlatformIO_get_services_by_conn_type(request):
    """
    Returns a Cluster → Node → Service tree for a given connection type.
    POST body: {"conn_type": "churnData"}  or  {"conn_type": "Fin_Data"}
    Maps:
        churnData  → service_type AirtelChurn
        Fin_Data   → service_type optionCopilot
    """
    CONN_TYPE_MAP = {
        "churnData": "AirtelChurn",
        "Fin_Data": "optionCopilot",
    }
    try:
        body = json.loads(request.body)
        conn_type = body.get("conn_type", "")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    service_type = CONN_TYPE_MAP.get(conn_type)
    if not service_type:
        return JsonResponse({"success": False, "message": f"Unknown conn_type: {conn_type}"}, status=400)

    try:
        # Directly query Service model with joins for full node/cluster info
        services = Service.objects.select_related('Node', 'Node__Cluster').filter(
            service_type=service_type
        ).order_by('Node__Cluster__cluster_idx', 'Node__node_idx', 'service_idx')

        # Build the Cluster → Node → Service tree
        cluster_map = {}
        for svc in services:
            node = svc.Node
            cluster = node.Cluster if node else None
            cluster_name = cluster.cluster_name if cluster else 'Unknown'
            node_name = node.node_name if node else 'Unknown'
            node_ip = str(node.node_ip) if (node and node.node_ip) else ''

            if cluster_name not in cluster_map:
                cluster_map[cluster_name] = {}
            if node_name not in cluster_map[cluster_name]:
                cluster_map[cluster_name][node_name] = {'node_ip': node_ip, 'services': []}

            cluster_map[cluster_name][node_name]['services'].append({
                'service_name': svc.service_name or '',
                'service_id': svc.service_id or '',
                'service_type': svc.service_type or '',
                'service_port': str(svc.service_port) if svc.service_port else '',
                'node_ip': node_ip,
            })

        result = [
            {
                'cluster_name': cname,
                'nodes': [
                    {
                        'node_name': nname,
                        'node_ip': ndata['node_ip'],
                        'services': ndata['services'],
                    }
                    for nname, ndata in nodes_dict.items()
                ]
            }
            for cname, nodes_dict in cluster_map.items()
        ]
        return JsonResponse({'success': True, 'clusters': result})
    except Exception as e:
        app_logger.error(f'[get_services_by_conn_type] Error: {e}')
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required()
@require_http_methods(["POST"])
def cPlatformIO_get_conn_type_config(request):
    """
    Fetches filter config (circles_list / symbols_list) from the explicitly selected service node.
    POST body: {"conn_type": "churnData", "service_name": "AirtelChurn_SERV1033"}
               {"conn_type": "Fin_Data",  "service_name": "optionCopilot_SERV1040"}
    Uses service_name_override to bypass all fallback logic and route directly to the chosen node.
    """
    try:
        body = json.loads(request.body)
        conn_type = body.get("conn_type", "")
        service_name = body.get("service_name", "")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    if not service_name:
        return JsonResponse({"success": False, "message": "service_name is required"}, status=400)

    try:
        if conn_type == "churnData":
            from ProxyChurn.views import _resolve_churn_target, _send_churn_backend_request
            # Resolve the explicit service node — returns (ok, host, port)
            ok, host, port = _resolve_churn_target(service_name_override=service_name)
            if not ok or not host:
                return JsonResponse({"success": False, "message": "AirtelChurn service not found or unreachable"}, status=404)
            # Call backend using service_name_override so it routes to the exact node
            result = _send_churn_backend_request(request, service_name_override=service_name)
            filter_config = result.get("filter_config") or result
            return JsonResponse({"success": True, "filter_config": filter_config})

        elif conn_type == "Fin_Data":
            from ProxyoptionCopilot.views import _resolve_opcop_target, _send_opcop_requests
            ok, host, port = _resolve_opcop_target(service_name_override=service_name)
            app_logger.debug(f"==========\ok = {ok}, nhost= {host}, port = {port}")
            if not ok or not host:
                return JsonResponse({"success": False, "message": "optionCopilot service not found or unreachable"}, status=404)
            result = _send_opcop_requests(
                request, "POST", "/Common/GetSymbolsConfig/", {},
                service_name_override=service_name
            )
            filter_config = result.get("filter_config") or result
            return JsonResponse({"success": True, "filter_config": filter_config})

        else:
            return JsonResponse({"success": False, "message": f"Unsupported conn_type: {conn_type}"}, status=400)

    except Exception as e:
        app_logger.error(f"[get_conn_type_config] Error: {e}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)
