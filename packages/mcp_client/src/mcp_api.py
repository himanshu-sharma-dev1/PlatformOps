'''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : mcp_api.py
* Description       : Public API surface for MCPClient library.
*                     Use this file as the single entry point for all MCP functionality —
*                     initialization, query workflow, and chat history management.
*
* Usage Example:
*     from mcp_api import mcp_init_all, mcp_query, mcp_chat_history
*
* Revision History  :
* Date              Author              Comments
* -------------------------------------------------------------------------------------------------------------------
* 17-Mar-26         Amit                Created from mcpInit, mcpChat, mcpClient sources.
* 23-Mar-26         Anu                 Added mcp_platform parameter to mcp_api_query and all
*                                       chat history APIs so each platform maintains isolated
*                                       Redis history.  Key format: {mcp_platform}:history:{user_id}
*********************************************************************************************************************'''

import asyncio
from typing import AsyncGenerator

# ─── Internal module imports ─────────────────────────────────────────────────
from MCPClient.src.mcpInit import (
    mcp_log_init,
    mcp_llm_init,
    mcp_client_init,
    mcp_postgres_db_init,
    mcp_intent_init,
    mcp_widget_init,
    mcpcl_redis_init,
    mcp_guardrails_init,
)
from MCPClient.src.mcpChat import (
    mcp_generate_question_id,
    mcp_chat_add_response,
    mcp_chat_update_feedback,
    mcp_chat_get_questions,
    mcp_chat_get_history,
    mcp_chat_get_answer,
)
from MCPClient.src.mcpClient import run_mcp_workflow
from MCPClient.src.mcpInit import mcp_follow_up_question_init
def mcp_api_log_init(log_path: str) -> tuple[bool, str]:

    return mcp_log_init(log_path)

def mcp_api_llm_init(llm_model_name: str, llm_model_host: str, llm_model_port: str,  llm_params_dict: dict = None,) -> tuple[bool, str]:
    return mcp_llm_init(llm_model_name, llm_model_host, llm_model_port, llm_params_dict)


def mcp_api_client_init(mcp_url: str, redis_server_ip: str, redis_server_port: int,
                        tool_access: str = "external",
                        use_gateway_tools: bool = True,
                        tool_payload: dict = None) -> tuple[bool, str]:

    config = {
        "mcp_url":           mcp_url,
        "redis_server_ip":   redis_server_ip,
        "redis_server_port": redis_server_port,
        "tool_access":       tool_access,
        "use_gateway_tools": use_gateway_tools,
        "tool_payload":      tool_payload or {},
    }
    print(f"innitlaized the mcp client")
    return mcp_client_init(config)


def mcp_api_db_init(postgres_database: str, postgres_user: str, postgres_password: str,
                    postgres_host: str, postgres_port: int) -> tuple[bool, str]:

    dbconfig = {
        "postgres_database": postgres_database,
        "postgres_user":     postgres_user,
        "postgres_password": postgres_password,
        "postgres_host":     postgres_host,
        "postgres_port":     postgres_port,
    }
    return mcp_postgres_db_init(dbconfig)


def mcp_api_intent_init(intent_list: list[dict]) -> tuple[bool, str]:

    return mcp_intent_init(intent_list)


def mcp_api_guardrails_init(guardrails_config: dict) -> tuple[bool, str]:
    return mcp_guardrails_init(guardrails_config)

def mcp_api_redis_init(redis_server_ip: str, redis_server_port: int):
    config = {
        "redis_server_ip": redis_server_ip,
        "redis_server_port": redis_server_port
    }
    return mcpcl_redis_init(config)


async def mcp_api_query(user_info: dict, user_session: dict,
                        user_query: str, selected_tool_override: str = "") -> AsyncGenerator[dict, None]:

    async for chunk in run_mcp_workflow(
        user_info, user_session, user_query, selected_tool_override=selected_tool_override
    ):
        yield chunk


def mcp_api_query_sync(user_info: dict, user_session: dict,
                       user_query: str, selected_tool_override: str = "") -> list[dict]:

    async def _collect():
        results = []
        async for chunk in mcp_api_query(
            user_info, user_session, user_query, selected_tool_override=selected_tool_override
        ):
            results.append(chunk)
        return results

    return asyncio.run(_collect())


def mcp_api_generate_question_id() -> str:

    return mcp_generate_question_id()


def mcp_api_chat_save(mcp_platform: str, user_id: str, question_id: str,
                      user_query: str, llm_response: str,
                      additional_info: dict = None, feedback: str = None,
                      intent: str = None, tool: str = None) -> None:

    mcp_chat_add_response(mcp_platform, user_id, question_id, user_query,
                          llm_response, additional_info, feedback, intent, tool)


def mcp_api_chat_get_history(mcp_platform: str, user_id: str,
                             last_n: int = None) -> tuple[dict, list]:

    return mcp_chat_get_history(mcp_platform, user_id, last_n)


def mcp_api_chat_get_questions(mcp_platform: str, user_id: str,
                               last_n: int = None) -> dict:

    return mcp_chat_get_questions(mcp_platform, user_id, last_n)


def mcp_api_chat_get_answer(mcp_platform: str, user_id: str,
                            question_id: str) -> dict:

    return mcp_chat_get_answer(mcp_platform, user_id, question_id)


def mcp_api_chat_update_feedback(mcp_platform: str, user_id: str,
                                 question_id: str, feedback: str) -> bool:

    return mcp_chat_update_feedback(mcp_platform, user_id, question_id, feedback)



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
    if "guardrails_config" in config:
        steps.append((
            "guardrails",
            lambda: mcp_api_guardrails_init(config["guardrails_config"])
        ))
    for name, fn in steps:
        ok, msg = fn()
        if not ok:
            return False, f"[{name}] {msg}"

    return True, "All initialized"

def mcp_api_follow_up_question_init(follow_up_question: bool):
    return mcp_follow_up_question_init(follow_up_question)


