import os
import json
import requests
import jsonschema
from pathlib import Path
from datetime import date, datetime
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





# @login_required
# @admin_only


# @login_required
# @admin_only



















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
    is_admin = request.user.is_superuser or request.user.is_staff or UserInfo.objects.filter(user_email=str(request.user), user_role='System_Admin').exists()

    if request.method == "POST":
        app_logger.info(f'cPlatformIO_user_view, request={request.POST}')
        if not is_admin:
            messages.error(request, 'Permission denied: only System_Admin can manage users and invitations.')
            return redirect('PlatformIOUsers')

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
            UserMgmnt.user_delete_request(request.POST.get('user_email'), initiated_by=str(request.user))
            messages.success(request, 'User deleted successfully')
        elif user_action == 'revoke_invite':
            email = request.POST.get('user_email')
            UserMgmnt.service_revoke_and_delete_pending(email, invited_by=str(request.user))
            messages.success(request, 'Invitation revoked')
        elif user_action == 'invite_user':
            UserMgmnt.service_user_invite(request.POST.get('user_name'), request.POST.get('user_email'),
                                          request.POST.get('user_number'), request.POST.get('user_role'),
                                          request.POST.getlist('permissions'), invited_by=str(request.user))
            messages.success(request, 'Invitation sent successfully')
        elif user_action == 'resend_invite':
            user_email_value = request.POST.getlist('user_email')
            emails = [e.strip() for e in user_email_value if e and e.strip()]
            sent_count, skipped_count = UserMgmnt.service_user_resend_invite_bulk(
                emails, invited_by=str(request.user))
            if skipped_count > 0:
                messages.success(request, f'Invitation resent to {sent_count} pending user(s); {skipped_count} user(s) were not pending and skipped.')
            else:
                messages.success(request, f'Invitation resent successfully to {sent_count} pending user(s).')
        return redirect('PlatformIOUsers')

    if is_admin:
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
    highest_login_count = max([u['login_count'] for u in user_data], default=1)
    for user in user_data:
        user['activity_percent'] = round((user['login_count'] / highest_login_count) * 100, 1) if highest_login_count else 0

    from cPlatformIO.src import PlatformPath
    platformops_url = PlatformPath.get_public_url(request)
    try:
        current_user_info = UserInfo.objects.get(user_email=str(request.user))
        current_user_role = current_user_info.user_role
    except UserInfo.DoesNotExist:
        current_user_role = 'System_Admin' if request.user.is_superuser else 'Operational'

    context = {
        'user_data': user_data,
        'user_schema': json.dumps(user_schema),
        'total_users': total_users,
        'active_users': active_users,
        'pending_users': pending_users,
        'disabled_users': disabled_users,
        'admin_users': admin_users,
        'platformops_url': platformops_url,
        'cplatform_url': platformops_url,
        'current_user_role': current_user_role,
        'is_admin': is_admin,
        'current_page': 'Identity / Users'
    }
    return render(request, 'PlatformIO/01-users.html', context)






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



    # except requests.exceptions.RequestException as e:
    #     return {"error": f"Failed to fetch service stats: {str(e)}"}



















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

        # Create or update the Django auth user
        user = User.objects.filter(username=invite.user_email).first()
        first_name = full_name.split()[0] if full_name else ''
        last_name = ' '.join(full_name.split()[1:]) if full_name and len(full_name.split()) > 1 else ''

        if not user:
            user = User.objects.create_user(
                username=invite.user_email,
                email=invite.user_email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        else:
            user.set_password(password)
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save()

        # Assign user to group based on role
        if invite.user_role == 'System_Admin':
            user.is_staff = True
            user.is_superuser = True
            user.save()
            admin_group, _ = Group.objects.get_or_create(name='Admin')
            admin_group.user_set.add(user)
        else:
            primary_group, _ = Group.objects.get_or_create(name='PrimaryUsers')
            primary_group.user_set.add(user)

        # Mark invite as used
        invite.is_used = True
        invite.save()

        # Activate and synchronize UserInfo record
        user_info = UserInfo.objects.filter(user_email=invite.user_email).first()
        if user_info:
            user_info.user_name = full_name or user_info.user_name
            user_info.user_role = invite.user_role or user_info.user_role
            user_info.status = 'active'
            user_info.save()
        else:
            UserMgmnt._create_userinfo_instance(
                full_name or invite.user_name or invite.user_email,
                invite.user_email,
                invite.user_role or 'Operational',
                invite.user_number or '',
                status='active'
            )

        return JsonResponse({'status': 'ok'})

    from cPlatformIO.src import PlatformPath
    platformops_url = PlatformPath.get_public_url(request)
    return render(request, 'PlatformIO/01a-invite-accept.html', {
        'state':  state,
        'invite': invite,
        'platformops_url': platformops_url,
        'cplatform_url': platformops_url,
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
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            contract = ConfigEngine.get_service_config_contract(service_instance)
            caps = ConfigEngine.get_service_capabilities(service_instance)
            target = ConfigEngine.get_service_runtime_target(service_instance)
            snapshots = ConfigEngine.get_snapshots_list(service_instance)

            live_res = ConfigEngine.read_live(service_instance)
            current_config = live_res.get("content", "")
            config_source = live_res.get("source", "empty")
            config_source_label = live_res.get("source_label", "Live Runtime")
            content_hash = live_res.get("content_hash", "")
            config_format = target.get("format", "raw")
            config_path = target.get("config_path", "")

            snapshot_count = len(snapshots)
            active_checkpoint = snapshots[0] if snapshots else None
            last_sync = active_checkpoint.get("timestamp", "Never") if active_checkpoint else "Never"
            file_label = f"{target['container_name']}/{os.path.basename(config_path)}" if config_path else target["container_name"]

            drift_state = "Editor matches active checkpoint"
            if active_checkpoint:
                ok_s, _, snap_content = ConfigEngine.get_snapshot_content(service_instance, snapshot_id=active_checkpoint.get("snapshot_id"))
                if ok_s and snap_content.strip() != current_config.strip():
                    drift_state = "Editor differs from active checkpoint"
            elif snapshot_count > 0:
                drift_state = "Editor differs from checkpoint history"
            else:
                drift_state = "No checkpoint captured yet"

            cluster = service_instance.Node.Cluster if getattr(service_instance, "Node", None) else None
            peers = Service.objects.filter(Node__Cluster=cluster, service_type=service_instance.service_type).exclude(service_id=service_id) if cluster else []
            peer_list = [{"service_id": p.service_id, "service_name": p.service_name, "node_name": p.Node.node_name, "node_ip": p.Node.node_ip} for p in peers]

            return JsonResponse({
                "success": True,
                "snapshots": snapshots,
                "current_config": current_config,
                "content_hash": content_hash,
                "peers": peer_list,
                "drift_state": drift_state,
                "last_sync": last_sync,
                "last_modified": last_sync,
                "snapshot_count": snapshot_count,
                "config_source": config_source,
                "config_source_label": config_source_label,
                "config_path": config_path,
                "file_label": file_label,
                "format": config_format,
                "runtime_target": target,
                "config_capabilities": caps,
                "config_contract": contract,
                "active_checkpoint": active_checkpoint,
                "service_info": {
                    "service_id": service_instance.service_id,
                    "service_name": service_instance.service_name,
                    "service_type": service_instance.service_type,
                    "service_version": service_instance.service_version,
                    "node_name": service_instance.Node.node_name if service_instance.Node else "N/A",
                    "cluster_name": cluster.cluster_name if cluster else "N/A",
                }
            })

        elif user_action == 'create_checkpoint':
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            label = request_info.get('label', '')
            res = ConfigEngine.checkpoint(service_instance, label=label, actor=str(request.user))
            if not res.get("success"):
                return JsonResponse({"success": False, "error": res.get("error", "Failed to capture checkpoint")})

            snapshots = ConfigEngine.get_snapshots_list(service_instance)
            return JsonResponse({
                "success": True,
                "msg": "Checkpoint successfully captured!",
                "snapshot_id": res.get("snapshot_id"),
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

            from cPlatformIO.src.ConfigEngine import ConfigEngine
            snapshots = ConfigEngine.get_snapshots_list(service_instance)
            return JsonResponse({
                "success": True,
                "msg": msg,
                "snapshot": payload.get("snapshot", {}),
                "snapshots": snapshots,
                "active_checkpoint": snapshots[0] if snapshots else None,
            })

        elif user_action == 'view_snapshot':
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            snapshot_id = request_info.get('snapshot_id')
            version = request_info.get('version')
            timestamp = request_info.get('timestamp')
            ok, msg, content = ConfigEngine.get_snapshot_content(service_instance, snapshot_id=snapshot_id, version=version, timestamp=timestamp)
            if not ok:
                return JsonResponse({"success": False, "error": msg})

            return JsonResponse({
                "success": True,
                "msg": "Snapshot content loaded successfully!",
                "content": content,
                "snapshot_id": snapshot_id,
                "version": version,
                "timestamp": timestamp,
            })

        elif user_action == 'get_snapshots_diff':
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            snap1 = request_info.get('snap1', {})
            snap2 = request_info.get('snap2', {})
            diff_res = ConfigEngine.compare(service_instance, snap1, snap2)
            return JsonResponse(diff_res)

        elif user_action in ['validate_yaml', 'validate_config']:
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            text = request_info.get('yaml_text') or request_info.get('config_text') or ''
            target = ConfigEngine.get_service_runtime_target(service_instance)
            val_res = ConfigEngine.validate(text, target["format"])
            return JsonResponse({
                "success": val_res["valid"],
                "msg": val_res["message"],
                "details": val_res["details"],
                "format": target["format"],
            })

        elif user_action == 'direct_apply_config':
            from cPlatformIO.src.ConfigEngine import ConfigEngine
            text = request_info.get('yaml_text') or request_info.get('config_text') or ''
            apply_mode = request_info.get('apply_mode', 'reload')
            app_res = ConfigEngine.apply(service_instance, text, apply_mode=apply_mode, actor=str(request.user))
            if not app_res.get("success"):
                return JsonResponse({"success": False, "error": app_res.get("error", "Apply failed"), "stage": app_res.get("stage")})

            snapshots = ConfigEngine.get_snapshots_list(service_instance)
            return JsonResponse({
                "success": True,
                "msg": app_res.get("msg", "Configuration applied successfully!"),
                "operation_id": app_res.get("operation_id"),
                "content_hash": app_res.get("content_hash"),
                "snapshots": snapshots,
                "details": app_res
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

            from cPlatformIO.src.ConfigEngine import ConfigEngine
            snapshots = ConfigEngine.get_snapshots_list(service_instance)
            return JsonResponse({
                "success": True,
                "msg": msg,
                "artifact_id": payload.get("artifact_id", ""),
                "apply_result": payload.get("apply_result", {}),
                "snapshots": snapshots,
            })

        elif user_action == 'restore_migration':
            backup_path = request_info.get('backup_path')
            snapshot_id = request_info.get('snapshot_id')
            resolved_config_path = request_info.get('resolved_config_path')
            apply_mode = request_info.get('apply_mode', 'reload')

            from cPlatformIO.src.ConfigEngine import ConfigEngine
            if snapshot_id:
                ok_c, msg_c, snap_content = ConfigEngine.get_snapshot_content(service_instance, snapshot_id=snapshot_id)
                if ok_c and snap_content:
                    app_res = ConfigEngine.apply(service_instance, snap_content, apply_mode=apply_mode, actor=str(request.user))
                    if app_res.get("success"):
                        snapshots = ConfigEngine.get_snapshots_list(service_instance)
                        return JsonResponse({
                            "success": True,
                            "msg": "Snapshot restored successfully!",
                            "snapshots": snapshots,
                        })
                    return JsonResponse({"success": False, "error": app_res.get("error", "Restore failed")})

            ret, msg, payload = ServiceConfig.service_restore_snapshot_migration(
                service_id,
                backup_path,
                resolved_config_path,
                apply_mode=apply_mode,
            )
            if not ret:
                return JsonResponse({"success": False, "error": msg})

            snapshots = ConfigEngine.get_snapshots_list(service_instance)
            return JsonResponse({
                "success": True,
                "msg": msg,
                "restore_result": payload.get("restore_result", {}),
                "snapshots": snapshots,
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
