from CommonUtils.com.EmailMgr import cutil_email_init
from CommonUtils.logs.AppLogging import cutil_log_init
from CommonUtils.timer.TimerMgr import cutil_timer_init
from CommonUtils.repository.RepoMgmt import cutil_repo_init
from CommonUtils.stats.StatsMgr import cutil_stats_init
from cPlatformIO.src.PlatformSetting import PlatformSettings
from django.conf import settings

def update_commonutils_config():
    # Email Initialisation
    ret, msg = cutil_email_init(PlatformSettings.mail_username, PlatformSettings.mail_password,
                                PlatformSettings.mail_host, PlatformSettings.mail_port, PlatformSettings.mail_use_tls)
    if not ret:
        return ret , msg

    service_url = f'http://{PlatformSettings.service_ip}:{PlatformSettings.service_port}'
    # Timer Initialisation
    ret,msg = cutil_timer_init(PlatformSettings.time_zone, service_url)
    if not ret:
        return ret , msg

    # Repository Initialisation
    ret,msg = cutil_repo_init('Primary','LOCAL', str(settings.REPOSITORY_PATH), {})

    if not ret:
        return ret , msg

    # Prometheus Initialisation
    ret,msg = cutil_stats_init(str(PlatformSettings.prometheus_server_ip), str(PlatformSettings.prometheus_server_port))

    if not ret:
        return ret, msg

    # LLM Initialisation
    # ret,msg = cutil_llm_init(PlatformSettings.llm_model, PlatformSettings.llm_host, PlatformSettings.llm_port )
    # if not ret:
    #     return ret , msg

    # Log Initialisation
    ret,msg = cutil_log_init(str(settings.BASE_DIR))
    if not ret:
        return ret , msg

    return ret , msg
    # mcp_url = f"{PlatformSettings.mcp_url}/mcp"
    # cutil_config_dict = {
    #     "mcp_url": mcp_url,
    #     "llm_server_ip": PlatformSettings.llm_host,
    #     "llm_server_port": PlatformSettings.llm_port,
    #     "llm_model": PlatformSettings.llm_model,
    #     "redis_server_ip": PlatformSettings.redis_server_ip,
    #     "redis_server_port": PlatformSettings.redis_server_port
    # }
    # try:
    #     cutil_mcp_init(cutil_config_dict)
    # except:
    #     print("MCP Server not Initiated.")

    # return ret , msg
