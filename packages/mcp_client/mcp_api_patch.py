# ============================================================================
# PATCH FOR MCPClient/mcp_api.py
# ============================================================================
#
# Two changes are needed in mcp_api.py:
#
#   1. Add `mcp_guardrails_init` to the import block from MCPClient.src.mcpInit
#   2. Add the new `mcp_api_guardrails_init` function
#   3. Add a "guardrails" step to `mcp_api_init_all`
#
# All changes shown below. Apply by:
#   - editing the import block (CHANGE 1)
#   - appending CHANGE 2 anywhere in the file (e.g. near mcp_api_intent_init)
#   - replacing the body of mcp_api_init_all per CHANGE 3
# ============================================================================


# ─── CHANGE 1: update the import from MCPClient.src.mcpInit ──────────────────
#
# Replace the existing import block:
#
#     from MCPClient.src.mcpInit import (
#         mcp_log_init,
#         mcp_llm_init,
#         mcp_client_init,
#         mcp_postgres_db_init,
#         mcp_intent_init,
#         mcp_widget_init,
#         mcpcl_redis_init
#     )
#
# With:

from MCPClient.src.mcpInit import (
    mcp_log_init,
    mcp_llm_init,
    mcp_client_init,
    mcp_postgres_db_init,
    mcp_intent_init,
    mcp_widget_init,
    mcpcl_redis_init,
    mcp_guardrails_init,          # NEW
)


# ─── CHANGE 2: new public API function ───────────────────────────────────────

def mcp_api_guardrails_init(guardrails_config: dict) -> tuple[bool, str]:
    """Initialize guardrails for this MCP client deployment.

    Pass None or {"enabled": False} to disable.
    See mcpGuardrails.mcp_guardrails_init for the expected config shape.
    """
    return mcp_guardrails_init(guardrails_config)


# ─── CHANGE 3: extend mcp_api_init_all ───────────────────────────────────────
#
# Replace the existing mcp_api_init_all with the version below.
# Only the additions are commented; the rest is unchanged.

def mcp_api_init_all(config: dict) -> tuple[bool, str]:
    steps = [
        ("log",    lambda: mcp_api_log_init(config["log_path"])),
        ("llm",    lambda: mcp_api_llm_init(
                                config["llm_model_name"],
                                config["llm_model_host"],
                                config["llm_model_port"],
                                config.get("llm_params_dict"),
                           )),
        ("client", lambda: mcp_api_client_init(
                                config["mcp_url"],
                                config["redis_server_ip"],
                                config["redis_server_port"],
                                config.get("tool_access", ""),
                                config.get("use_gateway_tools", False),
                                config.get("tool_payload", {})
                           )),
        ("intent", lambda: mcp_api_intent_init(config["intent_list"])),
    ]
    if "db" in config:
        db = config["db"]
        steps.append(("db", lambda: mcp_api_db_init(
            db["postgres_database"], db["postgres_user"], db["postgres_password"],
            db["postgres_host"], db["postgres_port"]
        )))

    # NEW — guardrails is optional; absence means "off"
    if "guardrails_config" in config:
        steps.append(("guardrails",
            lambda: mcp_api_guardrails_init(config["guardrails_config"])))

    for name, fn in steps:
        ok, msg = fn()
        if not ok:
            return False, f"[{name}] {msg}"

    return True, "All initialized"
