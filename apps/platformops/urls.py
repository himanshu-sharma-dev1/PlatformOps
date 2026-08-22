from django.urls import path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from cPlatformIO.views import (
    custom_login_redirect,
    cPlatformIO_user_view,
    cPlatformIO_auth_user,
    cPlatformIO_create_user,
    cPlatformIO_update_user,
    accept_invite_view,
    cPlatformIO_cluster_view,
    cPlatformIO_cluster_config,
    cPlatformIO_get_services_by_conn_type,
    cPlatformIO_get_conn_type_config,
    ctaw_get_service_stats,
    cPlatformIO_config_manager_view,
    cPlatformIO_system_monitoring,
    cPlatformIO_get_monitoring_tree,
    cPlatformIO_get_node_performance,
    cPlatformIO_get_service_performance,
    cPlatformIO_monitoring_view,
    cPlatformIO_monitoring_issues,
    cPlatformIO_monitoring_issue_event_details,
    cPlatformIO_monitoring_transaction_groups,
    cPlatformIO_monitoring_health,
    cPlatformIO_monitoring_integration_status,
    cPlatformIO_monitoring_uptime_list,
    cPlatformIO_monitoring_uptime_add,
    cPlatformIO_monitoring_uptime_delete,
    cPlatformIO_monitoring_issue_action,
    cPlatformIO_monitoring_project_keys,
    cPlatformIO_glitchtip_health,
    cPlatformIO_diagnostics_view,
)


urlpatterns = [
    # Login & Auth
    path('LoginRedirect/', custom_login_redirect, name='LoginRedirect'),

    # 1. Users & RBAC
    path('PlatformIO/Users/', cPlatformIO_user_view, name='PlatformIOUsers'),
    path('PlatformIO/AP1v1/AuthUser/', cPlatformIO_auth_user, name='AuthUser'),
    path('PlatformIO/AP1v1/CreateUser/', cPlatformIO_create_user, name='CreateUser'),
    path('PlatformIO/AP1v1/UpdateUser/', cPlatformIO_update_user, name='UpdateUser'),
    path('invite/accept/<uuid:token>/', accept_invite_view, name='accept_invite'),

    # 2. Clusters, Nodes & Services
    path('PlatformIO/ClusterView/', cPlatformIO_cluster_view, name='ClusterView'),
    path('PlatformIO/ClusterConfig/', cPlatformIO_cluster_config, name='ClusterConfig'),
    path('PlatformIO/APIv1/GetServicesByConnType/', cPlatformIO_get_services_by_conn_type, name='GetServicesByConnType'),
    path('PlatformIO/APIv1/GetConnTypeConfig/', cPlatformIO_get_conn_type_config, name='GetConnTypeConfig'),
    path('cPlatformApp/APIv1/GetServiceStats/', ctaw_get_service_stats, name='ServiceStatistics'),

    # 3. Config Manager
    path('PlatformIO/ConfigManager/', cPlatformIO_config_manager_view, name='PlatformIOConfigManager'),

    # 4. Performance & System Monitoring
    path('PlatformIO/SystemMonitoring/', cPlatformIO_system_monitoring, name='SystemMonitoring'),
    path('PlatformIO/GetMonitoringTree/', cPlatformIO_get_monitoring_tree, name='GetMonitoringTree'),
    path('PlatformIO/GetNodePerformance/', cPlatformIO_get_node_performance, name='GetNodePerformance'),
    path('PlatformIO/GetServicePerformance/', cPlatformIO_get_service_performance, name='GetServicePerformance'),

    # 5. Monitoring & GlitchTip
    path('PlatformIO/Monitoring/', cPlatformIO_monitoring_view, name='PlatformIOMonitoring'),
    path('PlatformIO/Monitoring/Issues/', cPlatformIO_monitoring_issues, name='MonitoringIssues'),
    path('PlatformIO/Monitoring/Issues/EventDetails/', cPlatformIO_monitoring_issue_event_details, name='MonitoringIssueEventDetails'),
    path('PlatformIO/Monitoring/Performance/', cPlatformIO_monitoring_transaction_groups, name='MonitoringPerformance'),
    path('PlatformIO/Monitoring/Health/', cPlatformIO_monitoring_health, name='MonitoringHealth'),
    path('PlatformIO/Monitoring/IntegrationStatus/', cPlatformIO_monitoring_integration_status, name='MonitoringIntegrationStatus'),
    path('PlatformIO/Monitoring/Uptime/', cPlatformIO_monitoring_uptime_list, name='MonitoringUptimeList'),
    path('PlatformIO/Monitoring/Uptime/Add/', cPlatformIO_monitoring_uptime_add, name='MonitoringUptimeAdd'),
    path('PlatformIO/Monitoring/Uptime/Delete/', cPlatformIO_monitoring_uptime_delete, name='MonitoringUptimeDelete'),
    path('PlatformIO/Monitoring/IssueAction/', cPlatformIO_monitoring_issue_action, name='MonitoringIssueAction'),
    path('PlatformIO/Monitoring/Keys/', cPlatformIO_monitoring_project_keys, name='MonitoringProjectKeys'),
    path('PlatformIO/APIv1/GlitchTipHealth/', cPlatformIO_glitchtip_health, name='GlitchTipHealth'),

    # 6. Diagnostics & Logs
    path('PlatformIO/Diagnostics/', cPlatformIO_diagnostics_view, name='PlatformIODiagnostics'),
]

urlpatterns += staticfiles_urlpatterns()
