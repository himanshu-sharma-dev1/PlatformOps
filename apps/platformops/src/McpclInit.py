import json
from pathlib import Path

try:
    from yantraAgent.src import mcpGuardrailsConfigChurn
    from yantraAgent.src import mcpGuardrailsAIConfig
except ImportError:
    mcpGuardrailsConfigChurn = None
    mcpGuardrailsAIConfig = None
from MCPClient.src import mcpInit
from cPlatformIO.src.PlatformSetting import PlatformSettings
from cPlatform.AppLogging import app_logger

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
DEFAULT_MCP_LOGGER_NAME = "cplatform_server"
_MCP_READY = False
_MCP_FAILURE_REASON = ""


def is_mcp_ready() -> bool:
    return _MCP_READY


def get_mcp_failure_reason() -> str:
    return _MCP_FAILURE_REASON


def _get(obj, *keys, default=""):
    cur = obj
    for key in keys:
        if cur is None:
            return default
        cur = cur.get(key, default) if isinstance(cur, dict) else getattr(cur, key, default)
    return cur if cur is not None else default


def _init_llm(cfg):
    model = str(_get(cfg, "llm", "llm_model"))
    host = str(_get(cfg, "llm", "llm_host", default=""))
    port = str(_get(cfg, "llm", "llm_port", default=""))
    if not model or not host or not port:
        app_logger.warning(
            f"[McpclInit] LLM not fully configured (model={model!r}, host={host!r}, "
            f"port={port!r}) — skipping LLM init. Set this from the cPlatform UI."
        )
        return True, "LLM not configured — skipped"
    lp = cfg.llm_params
    llm_params_dict = {
        "temperature": lp.temperature, "num_ctx": lp.num_ctx, "timeout": lp.timeout,
        "num_predict": lp.num_predict, "keep_alive": lp.keep_alive, "format": lp.format,
    }
    return mcpInit.mcp_llm_init(model, host, port, llm_params_dict)


def _init_log(cfg):
    from django.conf import settings as dj_settings
    ret, msg = mcpInit.mcp_log_init(str(dj_settings.BASE_DIR))
    if not ret:
        return ret, msg
    log_file_name = str(getattr(cfg.mcp_config, "log_file_name", "")).strip() or DEFAULT_MCP_LOGGER_NAME
    return mcpInit.mcp_log_name_init(log_file_name)


def _init_widget(cfg):
    wgt = cfg.widget_config
    report_url = wgt.report_url or f"{_get(cfg, 'service', 'cplatform_url')}/PlatformIO/APIv1/ScheduleWidget/"
    return mcpInit.mcp_widget_init(report_url, wgt.report_queue, wgt.template_name)


def _build_tool_payload(cfg) -> dict:
    mc = cfg.mcp_config
    if mc.use_gateway_tools or not mc.tools_config_path.strip():
        return {}
    path = Path(mc.tools_config_path)
    full_path = path if path.is_absolute() else CONFIG_DIR / path
    with open(full_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"tools config at '{full_path}' must be a JSON object")
    return payload


def _init_mcp_client(cfg):
    mc = cfg.mcp_config
    config_dict = {
        "mcp_url": str(_get(cfg, "mcp", "mcp_gateway_uri", default="")),
        "redis_server_ip": str(_get(cfg, "redis", "redis_server_ip", default="localhost")),
        "redis_server_port": str(_get(cfg, "redis", "redis_server_port", default="6379")),
        "tool_access": str(mc.tool_access or "external"),
        "use_gateway_tools": mc.use_gateway_tools,
        "tool_payload": _build_tool_payload(cfg),
    }
    return mcpInit.mcp_client_init(config_dict)


def _init_redis(cfg):
    return mcpInit.mcpcl_redis_init({
        "redis_server_ip": str(_get(cfg, "redis", "redis_server_ip", default="localhost")),
        "redis_server_port": str(_get(cfg, "redis", "redis_server_port", default="6379")),
    })


def _init_intents(cfg):
    intents = getattr(cfg, "intents", None) or []
    if not intents:
        return True, "no intents configured — skipped"
    return mcpInit.mcp_intent_init(intents)


def _init_flags(cfg):
    mc = cfg.mcp_config
    for fn, arg in (
        (mcpInit.mcp_intent_flag_init, mc.intent_flag),
        (mcpInit.mcp_platform_init, mc.platform_id),
        (mcpInit.flag_meta_data_init, mc.flag_meta_data),
        (mcpInit.mcp_follow_up_question_init, mc.follow_up_question),
    ):
        ret, msg = fn(arg)
        if not ret:
            return ret, msg
    return True, "flags OK"


def _build_guardrails_ai_config(cfg) -> dict:
    host = str(_get(cfg, "llm", "llm_host", default="localhost"))
    port = str(_get(cfg, "llm", "llm_port", default="11434"))
    model = str(_get(cfg, "llm", "llm_model", default="llama3.1"))
    lp = cfg.llm_params
    gr_config = mcpGuardrailsAIConfig.build_churn_guardrails_ai_config(
        llm_provider="ollama", llm_model=model, llm_base_url=f"http://{host}:{port}",
        llm_temperature=lp.temperature, num_ctx=lp.num_ctx, num_predict=lp.num_predict,
        keep_alive=lp.keep_alive, timeout=lp.timeout, format=lp.format,
        fail_mode="open", guardrail_ai_flag=bool(cfg.mcp_config.guardrail_ai_flag),
    )
    app_logger.debug(f"MCP INIT GUARDRAIL AI gr config -- {json.dumps(gr_config, indent=2)}")
    return gr_config


def _build_nemo_guardrails_config(cfg) -> dict:
    host = str(_get(cfg, "llm", "llm_host", default="localhost"))
    port = str(_get(cfg, "llm", "llm_port", default="11434"))
    model = str(_get(cfg, "llm", "llm_model", default="llama3.1"))
    lp = cfg.llm_params
    gr_config = mcpGuardrailsConfigChurn.build_churn_guardrails_config(
        llm_provider="ollama", llm_model=model, llm_base_url=f"http://{host}:{port}",
        llm_temperature=lp.temperature, num_ctx=lp.num_ctx, num_predict=lp.num_predict,
        keep_alive=lp.keep_alive, timeout=lp.timeout, format=lp.format,
        fail_mode="open", guardrail_flag=bool(cfg.mcp_config.guardrail_flag),
    )
    app_logger.debug(f"MCP INIT GUARDRAIL NEMO gr config -- {json.dumps(gr_config, indent=2)}")
    return gr_config


def _init_guardrails(cfg):
    mc = cfg.mcp_config
    flags = [mc.guardrail_flag, mc.guardrail_ai_flag, mc.guardrail_dspy_flag]
    if sum(bool(f) for f in flags) > 1:
        return False, "Configuration error: only one guardrail_* flag may be enabled"

    if mc.guardrail_flag:
        from MCPClient.src.mcpInit import mcp_guardrails_init
        return mcp_guardrails_init(_build_nemo_guardrails_config(cfg))

    if mc.guardrail_ai_flag:
        try:
            from MCPClient.src.mcpInit import mcp_guardrails_ai_init
        except ImportError:
            return True, "Guardrails AI skipped (missing in MCPClient)"
        return mcp_guardrails_ai_init(_build_guardrails_ai_config(cfg))

    if mc.guardrail_dspy_flag:
        try:
            from MCPClient.src.mcpInit import mcp_guardrails_dspy_init
        except ImportError:
            return True, "Guardrails DSPy skipped (missing in MCPClient)"
        return mcp_guardrails_dspy_init(cfg)

    return True, "Guardrails disabled"


def update_mcpclient_config(force: bool = False) -> tuple[bool, str]:
    """
    Single entrypoint for MCP bootstrap, safe to call from multiple
    AppConfig.ready() hooks (cPlatformIO, yantraAgent, or any future app).
    Second and subsequent calls are no-ops unless force=True.
    """
    global _MCP_READY, _MCP_FAILURE_REASON

    if _MCP_READY and not force:
        return True, "MCP already initialized — skipping duplicate init"

    cfg = PlatformSettings.get_config()
    steps = [
        ("LLM", lambda: _init_llm(cfg)),
        ("Log", lambda: _init_log(cfg)),
        ("Widget", lambda: _init_widget(cfg)),
        ("MCP client", lambda: _init_mcp_client(cfg)),
        ("Redis", lambda: _init_redis(cfg)),
        ("Intents", lambda: _init_intents(cfg)),
        ("Flags", lambda: _init_flags(cfg)),
        ("Guardrails", lambda: _init_guardrails(cfg)),
    ]
    for name, fn in steps:
        try:
            ret, msg = fn()
        except Exception as exc:
            _MCP_READY = False
            _MCP_FAILURE_REASON = f"{name} exception: {exc}"
            app_logger.error(f"[McpclInit] FAIL {name}: {_MCP_FAILURE_REASON}")
            return False, _MCP_FAILURE_REASON
        if not ret:
            _MCP_READY = False
            _MCP_FAILURE_REASON = f"{name}: {msg}"
            app_logger.error(f"[McpclInit] FAIL {name}: FATAL: {msg}")
            return False, _MCP_FAILURE_REASON
        app_logger.debug(f"[McpclInit] OK  {name}: {msg}")

    _MCP_READY = True
    _MCP_FAILURE_REASON = ""
    return True, "all MCP dependencies initialized"
