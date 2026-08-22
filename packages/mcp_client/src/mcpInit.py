import asyncio
import redis
from MCPClient.src import mcpClient
from langchain_ollama import ChatOllama
from MCPClient.mcpSetting import mcpSettings, llm_params
from MCPClient.logs.AppLogging import mcpcl_logger
from MCPClient.src.mcpGuardrails import mcp_guardrails_init as _gr_init
from MCPClient.src.mcpGuardrailsAI import mcp_guardrails_ai_init as _gr_ai_init
from MCPClient.src.mcpGuardrailDspy import mcp_guardrails_dspy_init as _gr_dspy_init


def mcp_llm_init(llm_model_name, llm_model_host, llm_model_port, llm_params_dict=None):
    if not all(isinstance(v, str) for v in [llm_model_name, llm_model_host, llm_model_port]):
        return False, "Invalid configuration: llm_model_name, llm_model_host, llm_model_port must all be strings."
    try:
        mcpSettings.llm_model_name = llm_model_name
        mcpSettings.llm_model_host = llm_model_host
        mcpSettings.llm_model_port = llm_model_port

        if llm_params_dict:
            mcpSettings.get_config().llm_setting.llm_params = llm_params(
                temperature = llm_params_dict.get("temperature"),
                num_ctx     = llm_params_dict.get("num_ctx"),
                timeout     = llm_params_dict.get("timeout"),
                num_predict = llm_params_dict.get("num_predict"),
                keep_alive  = llm_params_dict.get("keep_alive"),
                format      = llm_params_dict.get("format"),
            )

        mcpSettings.get_config().llm_setting._build_llm_instances()

        ok = mcpSettings.initialize_llm()
        if not ok:
            return False, "LLM ping failed — endpoint unreachable or timed out"

        return True, "Initialization Complete"

    except Exception as e:
        return False, f"Initialization Failed: {str(e)}"


def mcp_log_init(log_path: str):
    if not isinstance(log_path, str):
        return False, "Invalid configuration: log_path must be a string."
    mcpSettings.log_path = log_path
    return True, "Initialization Complete"



def mcp_widget_init(report_url: str, report_queue: str, template_name: str):
    if not all(isinstance(v, str) for v in [report_url, report_queue, template_name]):
        return False, "Invalid configuration: report_url, report_queue, template_name must all be strings."
    mcpSettings.report_url    = report_url
    mcpSettings.report_queue  = report_queue
    mcpSettings.template_name = template_name
    return True, "Initialization Complete"



def mcp_client_init(mcpcl_config_dict: dict):
    if not isinstance(mcpcl_config_dict.get("mcp_url"), str):
        return False, "Invalid configuration: mcp_url must be a string."
    mcpSettings.mcp_url           = mcpcl_config_dict.get("mcp_url")
    mcpSettings.redis_server_ip   = mcpcl_config_dict.get("redis_server_ip")
    mcpSettings.redis_server_port = mcpcl_config_dict.get("redis_server_port")
    mcpSettings.tool_access       = mcpcl_config_dict.get("tool_access")
    mcpSettings.use_gateway_tools = mcpcl_config_dict.get("use_gateway_tools")
    mcpSettings.tool_payload      = mcpcl_config_dict.get("tool_payload") or {}
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(mcpClient.tool_init(mcpSettings))
    except Exception as e:
        return False, f"Tool initialization failed: {str(e)}"
    return True, "Initialization Complete"



def mcpcl_redis_init(mcpcl_dict: dict):
    mcpSettings.redis_server_ip   = mcpcl_dict.get("redis_server_ip")
    mcpSettings.redis_server_port = int(mcpcl_dict.get("redis_server_port"))

    try:
        max_conn = mcpSettings.redis_max_connections
        pool = redis.ConnectionPool(
            host                 = mcpSettings.redis_server_ip,
            port                 = mcpSettings.redis_server_port,
            decode_responses     = True,
            max_connections      = max_conn,
            socket_connect_timeout = 30,
            socket_timeout       = 5,
            retry_on_timeout     = True,
            health_check_interval= 30,
        )
        redis.Redis(connection_pool=pool).ping()
        mcpSettings.redis_pool = pool
        mcpcl_logger.info(f"Redis pool initialized (max_connections={max_conn})")
        return True, "Initialization Complete"
    except Exception as e:
        mcpSettings.redis_pool = None
        mcpcl_logger.error(f"Redis init failed: {e}")
        return False, str(e)



def mcp_intent_init(intent_list: list):
    if not isinstance(intent_list, list) or not intent_list:
        return False, "Invalid intent config: must be a non-empty list."
    for item in intent_list:
        if not isinstance(item, dict):
            return False, "Invalid intent entry: must be a dict."
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            return False, f"Invalid intent name: {item.get('name')}"
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            return False, f"Invalid description for intent: {item.get('name')}"
    mcpSettings.intent_list = intent_list
    return True, "Initialization Complete"



def mcp_intent_flag_init(intent_flag: bool):
    if not isinstance(intent_flag, bool):
        return False, "Invalid configuration: intent_flag must be a boolean."
    mcpSettings.intent_classifier_flag = intent_flag
    return True, "Initialization Complete"


def mcp_postgres_db_init(db_config: dict):
    if not isinstance(db_config, dict):
        return False, "Invalid configuration: db config must be a dict."
    required = [
        "postgres_database",
        "postgres_user",
        "postgres_password",
        "postgres_host",
        "postgres_port",
    ]
    missing = [k for k in required if k not in db_config]
    if missing:
        return False, f"Invalid configuration: missing db keys: {missing}"
    mcpSettings.postgres_database = db_config.get("postgres_database")
    mcpSettings.postgres_user = db_config.get("postgres_user")
    mcpSettings.postgres_password = db_config.get("postgres_password")
    mcpSettings.postgres_host = db_config.get("postgres_host")
    mcpSettings.postgres_port = db_config.get("postgres_port")
    return True, "Initialization Complete"


def mcp_platform_init(platform_id: str):
    if not isinstance(platform_id, str):
        return False, "Invalid configuration: platform_id must be a string."
    mcpSettings.mcp_platform = platform_id
    return True, "Initialization Complete"


def flag_meta_data_init(meta_data_flag: bool):
    if not isinstance(meta_data_flag, bool):
        return False, "Invalid configuration: meta_data_flag must be a boolean."
    mcpSettings.flag_meta_data = meta_data_flag
    return True, "Initialization Complete"


def mcp_follow_up_question_init(follow_up_question: bool):
    if not isinstance(follow_up_question, bool):
        return False, "Invalid configuration: follow_up_question must be a boolean."
    mcpSettings.follow_up_question = follow_up_question
    return True, "Initialization Complete"

def mcp_log_name_init(log_file_name: str):
    if not isinstance(log_file_name, str):
        return False, "Invalid configuration: log_file_name must be a string."
    mcpSettings.log_file_name = log_file_name
    return True, "Initialization Complete"


def mcp_guardrails_ai_init(guardrails_config: dict):
    if guardrails_config is not None and not isinstance(guardrails_config, dict):
        return False, "Invalid configuration: guardrails_config must be a dict or None."
    return _gr_ai_init(guardrails_config)


def mcp_guardrails_init(guardrails_config: dict):
    if guardrails_config is not None and not isinstance(guardrails_config, dict):
        return False, "Invalid configuration: guardrails_config must be a dict or None."
    return _gr_init(guardrails_config)


def mcp_guardrails_dspy_init(guardrails_config: dict):
    if guardrails_config is not None and not isinstance(guardrails_config, dict):
        return False, "Invalid configuration: guardrails_config must be a dict or None."
    return _gr_dspy_init(guardrails_config)