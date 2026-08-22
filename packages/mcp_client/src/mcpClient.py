import re
import json
import asyncio
import aiohttp
import httpx

# Import related to mcp
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# imports related to langchain
from langchain_core.output_parsers import JsonOutputParser

# imports related to fastmcp
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

# imports related to mcpclient
from MCPClient.mcpSetting import mcpSettings
from MCPClient.logs.AppLogging import mcpcl_logger
from MCPClient.src import mcpChat, mcpPrompt, mcpResponse
from MCPClient.src.mcpGuardrailsAI import mcp_guardrails_ai_check_input, mcp_guardrails_ai_is_enabled
from MCPClient.src.mcpGuardrails import mcp_guardrails_check_input, mcp_guardrails_is_enabled
from MCPClient.src.mcpGuardrailDspy import mcp_guardrails_dspy_check_input, mcp_guardrails_dspy_is_enabled
from .mcp_intent_classifier import get_top_2_intents


# ---------- LLM Down Detection ----------

_LLM_DOWN_MSG = "AI service is temporarily unavailable. Please try again in a moment."

def _is_llm_down(exc: Exception) -> bool:
    return isinstance(exc, (
        httpx.ConnectError,
        httpx.RemoteProtocolError,
        httpx.ReadTimeout,
        ConnectionRefusedError,
    )) or "connection" in str(exc).lower()


# ---------- Tool Response Formatter ----------

def _format_tool_response(tool_response):
    mcpcl_logger.debug(f"_format_tool_response, type={type(tool_response)}, value={tool_response}")
    try:
        if isinstance(tool_response, list):
            results = []
            for item in tool_response:
                if hasattr(item, "text"):
                    try:
                        results.append(json.loads(item.text))
                    except json.JSONDecodeError:
                        mcpcl_logger.error(f"Invalid JSON in item: {item.text}")
                        results.append(item.text)
                else:
                    results.append(str(item))
            return results[0] if len(results) == 1 else results

        if hasattr(tool_response, "text"):
            try:
                return json.loads(tool_response.text)
            except json.JSONDecodeError:
                return tool_response.text

        if isinstance(tool_response, str):
            try:
                return json.loads(tool_response)
            except json.JSONDecodeError:
                return tool_response

        return tool_response

    except Exception as e:
        mcpcl_logger.error(f"_format_tool_response failed: {e}", exc_info=True)
        return None


# ---------- Session Input Extractor ----------

def _extract_session_input(res, param_info, user_info):
    target_keys = [k for k in param_info.keys() if k not in res]
    target_keys += [k for k, v in res.items() if v in [None, 'null', 'None', 'Null', '']]

    for key in target_keys:
        pattern = re.compile(rf".*{re.escape(key)}.*", re.IGNORECASE)
        for info_key, info_value in user_info.items():
            if re.match(pattern, info_key):
                if param_info[key]['type'] == 'string' and isinstance(info_value, list):
                    res[key] = info_value[0]
                elif param_info[key]['type'] in ['array', 'list'] and isinstance(info_value, str):
                    res[key] = [s.strip() for s in info_value.split(',') if s.strip()]
                else:
                    res[key] = info_value
                break
    return res


# ---------- Direct Param Extractor (no LLM) ----------

def _extract_params_directly(param_info: dict, user_info: dict, user_session: dict, user_query: str = "") -> dict:
    resolved = {}
    if "user_query" in param_info and user_query:
        resolved["user_query"] = user_query


    normalized_session  = {k.strip().lower(): v for k, v in user_session.items()}
    normalized_info     = {k.strip().lower(): v for k, v in user_info.items()}
    combined_normalized = {**normalized_info, **normalized_session}

    for param_key, param_meta in param_info.items():
        if param_key in resolved:
            continue

        param_key_norm = param_key.strip().lower()
        param_type     = param_meta.get("type", "string")

        if param_key_norm in combined_normalized:
            value = combined_normalized[param_key_norm]

            if param_type in ("array", "list") and isinstance(value, str):
                value = [s.strip() for s in value.split(",") if s.strip()]
            elif param_type == "string" and isinstance(value, list):
                value = value[0]

            resolved[param_key] = value
            mcpcl_logger.debug(
                f"_extract_params_directly: '{param_key}'and '{param_key_norm}'"
            )

    mcpcl_logger.debug(
        f"_extract_params_directly: "
        f"required={list(param_info.keys())} "
        f"resolved={list(resolved.keys())} "
        f"missing={list(set(param_info.keys()) - set(resolved.keys()))}"
    )
    return resolved


# ---------- Intent-based Tool Filtering ----------

def _filter_tools_by_intent(top_intents: list[str]) -> dict:
    tools = mcpSettings.mcp_tool_dict
    if not isinstance(tools, dict):
        raise ValueError("mcp_tool_dict must be a dict")

    filtered = {
        tool_name: tool_data
        for tool_name, tool_data in tools.items()
        if any(intent in top_intents for intent in tool_data.get("intent", []))
    }

    if not filtered:
        mcpcl_logger.warning(f"No tools matched intents {top_intents}, falling back to full tool list.")
        return tools

    return filtered


# ---------- Tool Selection ----------

async def _select_tool(user_info, user_session, user_query, chat_history) -> tuple[str, list]:
    if mcpSettings.mcp.intent_classifier_flag:
        top_intents = await get_top_2_intents(user_query)
        mcpcl_logger.debug(f"_select_tool: top_intents={top_intents}")
        filtered_tools = _filter_tools_by_intent(top_intents)
    else:
        top_intents = []
        filtered_tools = mcpSettings.mcp_tool_dict
        mcpcl_logger.debug("_select_tool: intent classifier disabled, using full tool list")

    mcpcl_logger.debug(f"_select_tool: filtered_tools={list(filtered_tools.keys())}")

    prompt = mcpPrompt.get_tool_selection_prompt()
    llm    = mcpSettings.get_fresh_llm(json_format=True)
    chain  = prompt | llm | JsonOutputParser()

    try:
        mcpcl_logger.debug("STEP 1 - before chain invoke")
        res = await chain.ainvoke({
            "tool_list"   : filtered_tools,
            "user_query"  : user_query,
            "user_info"   : json.dumps(user_info, indent=2),
            "user_session": json.dumps(user_session, indent=2),
            "chat_history": json.dumps(chat_history, indent=2),
        })
        mcpcl_logger.debug("STEP 2 - after chain invoke")

        selected_tool = res.get("tool")
        if selected_tool in mcpSettings.mcp_tool_dict:
            mcpcl_logger.debug(f"_select_tool: selected tool='{selected_tool}'")
            return selected_tool, top_intents

        mcpcl_logger.error(f"_select_tool: LLM returned unknown tool: {res}")
        return "None", top_intents

    except Exception as e:
        if _is_llm_down(e):
            mcpcl_logger.error(f"_select_tool: LLM unreachable: {e}")
            return "__llm_down__", top_intents
        mcpcl_logger.error(f"_select_tool: Tool selection failed: {str(e)}")
        return "None", top_intents


# ---------- Missing Param Validator ----------

def _missing_param(param_info, llm_res):
    missing_keys = [k for k in param_info.keys() if k not in llm_res]
    none_keys    = [k for k, v in llm_res.items() if v is None]

    reasons = []
    if missing_keys:
        reasons.append(f"Missing parameters: {missing_keys}")
    if none_keys:
        reasons.append(f"Parameters with None values: {none_keys}")

    msg = "; ".join(reasons)
    mcpcl_logger.error(
        f"Validation failed. Provided: {llm_res}, Required: {list(param_info.keys())}, Reason: {msg}"
    )
    return {}, msg


# ---------- Parameter Extractor (LLM fallback) ----------

async def _extract_input(select_tool, user_info, user_session, user_query, chat_history):
    param_info = mcpSettings.mcp_tool_dict[select_tool]['parameters']['properties']
    param_doc  = mcpSettings.mcp_tool_dict[select_tool]['param_schema']

    prompt = mcpPrompt.get_param_extraction_prompt()
    llm    = mcpSettings.get_fresh_llm(json_format=True)
    chain  = prompt | llm | JsonOutputParser()

    try:
        res = await chain.ainvoke({
            "params_doc"  : json.dumps(param_doc, indent=2),
            "user_query"  : user_query,
            "chat_history": chat_history,
        })
        mcpcl_logger.debug(f"_extract_input: raw llm result={res}")
        res = _extract_session_input(res, param_info, {**user_info, **user_session})
        mcpcl_logger.debug(f"_extract_input: resolved params={res}")

        if list(res.keys()) == list(param_info.keys()) and None not in list(res.values()):
            return res, ""

        if set(param_info.keys()).issubset(set(res.keys())):
            li = {k: res[k] for k in param_info.keys()}
            if None not in li.values():
                return res, ""

        return _missing_param(param_info, res)

    except Exception as e:
        if _is_llm_down(e):
            mcpcl_logger.error(f"_extract_input: LLM unreachable: {e}")
            return {}, "__llm_down__"
        mcpcl_logger.error(f"_extract_input: Parameter extraction failed: {str(e)}")
        return {}, f"Parameter extraction failed: {str(e)}"


# ---------- Follow-up Question Helpers ----------

def _is_chart_response(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return True
    return any(
        marker in text.lower()
        for marker in ("::: chart", '"chart_type"', '"series"', '"labels"', "📊")
    )


def _followup_json_to_markdown(data: dict) -> str:
    if not isinstance(data, dict):
        return ""
    heading   = data.get("heading", "").strip()
    questions = data.get("questions", [])
    if not heading or not isinstance(questions, list):
        return ""
    lines = [heading]
    for q in questions:
        if isinstance(q, str) and q.strip():
            lines.append(f"- {q.strip()}")
    return "\n".join(lines)


async def _generate_follow_up_question(user_query, final_response) -> str:
    if not getattr(mcpSettings, "follow_up_question", False):
        return ""
    if _is_chart_response(final_response):
        final_response = ""
    try:
        prompt = mcpPrompt.get_follow_up_questions_prompt()
        llm    = mcpSettings.get_fresh_llm(json_format=True)
        chain  = prompt | llm | JsonOutputParser()
        mcpcl_logger.debug("_generate_follow_up_question: invoking follow-up chain")
        result = await chain.ainvoke({
            "user_question"     : user_query,
            "assistant_response": final_response,
        })
        mcpcl_logger.debug(f"_generate_follow_up_question: result={result}")
        return _followup_json_to_markdown(result)

    except Exception as e:
        mcpcl_logger.error(f"_generate_follow_up_question: {e}")
        return ""


def _generate_rewrite_query(user_query, final_response) -> str:
    try:
        prompt = mcpPrompt.get_query_rewrite_prompt()
        llm    = mcpSettings.get_fresh_llm(json_format=True)
        chain  = prompt | llm | JsonOutputParser()

        result = chain.invoke({
            "user_query": user_query,
            "context"   : final_response,
        })
        mcpcl_logger.debug(f"_generate_rewrite_query: context={final_response}")
        mcpcl_logger.debug(f"_generate_rewrite_query: result={result}")
        return result.get("rewritten_query", "")

    except Exception as e:
        mcpcl_logger.error(f"_generate_rewrite_query: {e}")
        return ""


# ---------- Tool Invokers ----------

async def _invoke_tool_streamable(select_tool, param_info, timeout_sec: float = 300.0):
    mcp_server_uri = mcpSettings.mcp_tool_dict[select_tool]['server_uri'] + "/mcp"
    log_queue: asyncio.Queue = asyncio.Queue()

    async def log_handler(message):
        await log_queue.put(
            message.data if hasattr(message, "data") else str(message)
        )

    transport = StreamableHttpTransport(url=mcp_server_uri)
    async with Client(transport, log_handler=log_handler) as client:

        async def run_tool():
            try:
                await client.initialize()
                result = await client.call_tool(select_tool, arguments=param_info)
                if result.is_error:
                    raise Exception(result.content)
            except Exception as e:
                mcpcl_logger.exception(
                    f"_invoke_tool_streamable: tool='{select_tool}' failed: {e}"
                )
            finally:
                await asyncio.sleep(0.1)
                await log_queue.put(None)

        def _log_task_exception(task: asyncio.Task):
            if not task.cancelled() and task.exception():
                mcpcl_logger.error(
                    f"_invoke_tool_streamable: task crashed: {task.exception()}"
                )

        tool_task = asyncio.create_task(run_tool())
        tool_task.add_done_callback(_log_task_exception)

        while True:
            try:
                chunk = await asyncio.wait_for(log_queue.get(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                mcpcl_logger.error(
                    f"_invoke_tool_streamable: timeout after {timeout_sec}s "
                    f"waiting for tool='{select_tool}'"
                )
                tool_task.cancel()
                raise Exception(f"Tool '{select_tool}' timed out after {timeout_sec} seconds.")
            if chunk is None:
                break
            yield chunk

        await tool_task


async def _invoke_tool(select_tool, param_info, timeout_sec: float = 60.0) -> tuple[bool, any]:
    mcp_server_uri = mcpSettings.mcp_tool_dict[select_tool]['server_uri']
    mcpcl_logger.debug(f"_invoke_tool: calling '{select_tool}' with args={param_info}")
    ret          = False
    tool_response = None

    try:
        async with streamablehttp_client(mcp_server_uri + "/mcp") as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                try:
                    res = await asyncio.wait_for(
                        session.call_tool(select_tool, arguments=param_info),
                        timeout=timeout_sec
                    )
                    if res.isError:
                        raise Exception(res.content)
                    tool_response = (
                        res.content if isinstance(res.content, (str, list)) else str(res.content)
                    )
                    ret = True
                except asyncio.TimeoutError:
                    mcpcl_logger.error(
                        f"_invoke_tool: timeout after {timeout_sec}s for tool='{select_tool}'"
                    )
                    tool_response = f"Tool '{select_tool}' timed out after {timeout_sec} seconds."
                except Exception as e:
                    mcpcl_logger.exception(f"_invoke_tool: '{select_tool}' failed: {e}")
                    tool_response = f"Error executing tool '{select_tool}': {str(e)}"
    except asyncio.TimeoutError:
        mcpcl_logger.error(f"_invoke_tool: connection timeout for tool='{select_tool}'")
        tool_response = f"Could not connect to tool '{select_tool}': connection timed out."

    format_resp = _format_tool_response(tool_response) if ret else tool_response
    return ret, format_resp


def _attach_metadata(payload: dict, selected_tool, top_intents):
    if getattr(mcpSettings, "flag_meta_data", False):
        payload["tool"]   = selected_tool
        payload["intent"] = top_intents if isinstance(top_intents, list) else [top_intents]
    return payload


async def run_input_guardrails(user_query):

    if mcp_guardrails_ai_is_enabled():
        return await mcp_guardrails_ai_check_input(user_query)

    if mcp_guardrails_is_enabled():
        return await mcp_guardrails_check_input(user_query)

    if mcp_guardrails_dspy_is_enabled():
        return await mcp_guardrails_dspy_check_input(user_query)

    return True, None, None

# ---------- Main Workflow ----------

async def run_mcp_workflow(user_info, user_session, user_query, selected_tool_override: str = "",
                           persist_history: bool = True, question_id_override: str = None):
    mcp_platform = getattr(mcpSettings, "mcp_platform", "mcp-default")
    user_id      = user_info['user_id']
    guardrails_ai_enabled   = mcp_guardrails_ai_is_enabled()
    guardrails_enabled      = mcp_guardrails_is_enabled()
    guardrails_dspy_enabled = mcp_guardrails_dspy_is_enabled()

    mcpcl_logger.debug(
        f"run_mcp_workflow: start user_id='{user_id}' platform='{mcp_platform}' "
        f"guardrails_ai_enabled={guardrails_ai_enabled} guardrails_enabled={guardrails_enabled} "
        f"guardrails_dspy_enabled={guardrails_dspy_enabled} persist_history={persist_history} "
        f"query='{str(user_query)[:200]}'"
    )

    def _persist(*args, **kwargs):
        if persist_history:
            mcpChat.mcp_chat_add_response(*args, **kwargs)

    chat_info, _ = mcpChat.mcp_chat_get_history(mcp_platform, user_id, 4)

    chat_history = []
    for v in chat_info.values():
        if v.get("query"):
            chat_history.append({"role": "user", "content": v["query"]})
        if v.get("response"):
            response = v["response"]
            if "Parameter extraction failed" in response:
                continue
            if "No suitable tool" in response:
                continue
            if "unable to generate" in response:
                continue
            chat_history.append({"role": "assistant", "content": response})

    # question_id = mcpChat.mcp_generate_question_id()
    question_id = (question_id_override or mcpChat.mcp_generate_question_id())
    mcpcl_logger.debug(f'Guardrails AI enabled={guardrails_ai_enabled}')
    mcpcl_logger.debug(f'Nemo Guardrails enabled={guardrails_enabled}')
    mcpcl_logger.debug(f'DSPy Guardrails enabled={guardrails_dspy_enabled}')

    if guardrails_ai_enabled:
        mcpcl_logger.debug(f" -- Guardrails AI enabled -- ")
        in_scope, refusal, direct_response = await run_input_guardrails(user_query)
        mcpcl_logger.debug(f"AI guardrail decision in_scope={in_scope} direct_response={bool(direct_response)}")
        if not in_scope:
            refusal_msg = refusal or "Sorry, that question is outside my scope."
            _persist(mcp_platform, user_id, question_id, user_query, refusal_msg,
                                          intent="out_of_scope", tool="guardrails_ai")
            yield {
                "chunk": _attach_metadata({ "complete": refusal_msg, "question_id": question_id},
                    "guardrails_ai",["out_of_scope"])}
            return
        if direct_response:
            _persist( mcp_platform, user_id, question_id, user_query, direct_response,
                                          intent="conversational", tool="guardrails_ai")
            yield {
                "chunk": _attach_metadata({"complete": direct_response, "question_id": question_id},
                    "guardrails_ai",["conversational"])}
            return

    elif guardrails_enabled:

        mcpcl_logger.debug(f" -- Nemo guardrails_enabled -- ")
        in_scope, refusal, direct_response = await run_input_guardrails(user_query)
        mcpcl_logger.debug(f"NeMo guardrail decision in_scope={in_scope} direct_response={bool(direct_response)}")
        if not in_scope:
            refusal_msg = refusal or "Sorry, that question is outside my scope."
            _persist(mcp_platform, user_id, question_id, user_query, refusal_msg,
                                          intent="out_of_scope", tool="guardrails_nemo")
            yield {
                "chunk": _attach_metadata({"complete": refusal_msg,"question_id": question_id},
                    "guardrails_nemo",["out_of_scope"])}
            return
        if direct_response:
            _persist(mcp_platform, user_id, question_id, user_query, direct_response,
                                          intent="conversational", tool="guardrails_nemo")
            yield {
                "chunk": _attach_metadata({"complete": direct_response, "question_id": question_id},
                    "guardrails_nemo", ["conversational"])}
            return

    elif guardrails_dspy_enabled:

        mcpcl_logger.debug(f" -- DSPy guardrails_dspy_enabled -- ")
        in_scope, refusal, direct_response = await run_input_guardrails(user_query)
        mcpcl_logger.debug(f"DSPy guardrail decision in_scope={in_scope} direct_response={bool(direct_response)}")
        if not in_scope:
            refusal_msg = refusal or "Sorry, that question is outside my scope."
            _persist(mcp_platform, user_id, question_id, user_query, refusal_msg,
                                          intent="out_of_scope", tool="guardrails_dspy")
            yield {
                "chunk": _attach_metadata({"complete": refusal_msg, "question_id": question_id},
                    "guardrails_dspy", ["out_of_scope"])}
            return
        if direct_response:
            _persist(mcp_platform, user_id, question_id, user_query, direct_response,
                                          intent="conversational", tool="guardrails_dspy")
            yield {
                "chunk": _attach_metadata({"complete": direct_response, "question_id": question_id},
                    "guardrails_dspy", ["conversational"])}
            return

    if selected_tool_override:
        if selected_tool_override in mcpSettings.mcp_tool_dict:
            selected_tool = selected_tool_override
            top_intents   = []
            mcpcl_logger.debug(
                f"run_mcp_workflow: using forced tool='{selected_tool_override}', skipping tool selection"
            )

            param_info = mcpSettings.mcp_tool_dict[selected_tool]['parameters']['properties']
            resolved   = _extract_params_directly(param_info, user_info, user_session, user_query)
            all_resolved = (
                set(param_info.keys()).issubset(set(resolved.keys()))
                and None not in resolved.values()
                and "" not in resolved.values()
            )
            if all_resolved:
                mcpcl_logger.debug(
                    f"run_mcp_workflow: forced tool params resolved directly — LLM skipped"
                )
                extracted_params = resolved
                msg = ""
            else:
                mcpcl_logger.debug(
                    f"run_mcp_workflow: forced tool params partially resolved={list(resolved.keys())}, "
                    f"falling back to _extract_input"
                )
                extracted_params, msg = await _extract_input(
                    selected_tool, user_info, user_session, user_query, chat_history
                )
        else:
            selected_tool    = "None"
            top_intents      = []
            extracted_params = {}
            msg              = f"Forced tool '{selected_tool_override}' not found."
            mcpcl_logger.error(
                f"run_mcp_workflow: forced tool '{selected_tool_override}' not found. "
                f"available={list(mcpSettings.mcp_tool_dict.keys())}"
            )
    else:
        if len(mcpSettings.mcp_tool_dict) == 1:
            selected_tool = next(iter(mcpSettings.mcp_tool_dict))
            top_intents   = []
            mcpcl_logger.debug(
                f"run_mcp_workflow: only one tool registered, "
                f"skipping tool selection. selected='{selected_tool}'"
            )
        else:
            selected_tool, top_intents = await _select_tool(
                user_info, user_session, user_query, chat_history,
            )

        if selected_tool == "None" or selected_tool not in mcpSettings.mcp_tool_dict:
            extracted_params, msg = {}, ""
        else:
            extracted_params, msg = await _extract_input(
                selected_tool, user_info, user_session, user_query, chat_history
            )

    if selected_tool == 'None':
        msg = "No suitable tool found."
        _persist(
            mcp_platform, user_id, question_id, user_query, msg,
            intent=top_intents, tool=selected_tool
        )
        yield {"chunk": _attach_metadata({"msg": msg}, selected_tool, top_intents)}
        return
    if msg:
        msg = f"This is the selected_tool {selected_tool}. {msg}"
        _persist(
            mcp_platform, user_id, question_id, user_query, msg,
            intent=top_intents, tool=selected_tool
        )
        yield {"chunk": _attach_metadata({"msg": msg}, selected_tool, top_intents)}
        return
    output_format = mcpSettings.mcp_tool_dict[selected_tool]['output_format']
    if output_format == 'plain-text':
        try:
            mcpcl_logger.debug(f"run_mcp_workflow: sending tool request tool='{selected_tool}'")
            chunks = []
            async for chunk in _invoke_tool_streamable(selected_tool, extracted_params):
                chunks.append(chunk)
                yield {"chunk": _attach_metadata({"msg": chunk}, selected_tool, top_intents)}
            if not chunks:
                raise RuntimeError(f"No response chunks were returned by tool '{selected_tool}'.")

            tool_response          = "".join(chunks)
            status, final_response = mcpResponse.mcp_response_generator(tool_response, output_format)

            if status:
                selected_tool_for_history = selected_tool
                top_intents_for_history = top_intents
                _persist(
                    mcp_platform, user_id, question_id, user_query, final_response,
                    intent=top_intents_for_history, tool=selected_tool_for_history
                )
                yield {"chunk": _attach_metadata({"msg": "\n\n"}, selected_tool, top_intents)}

                follow_up_task = None
                if getattr(mcpSettings, "follow_up_question", False):
                    follow_up_task = asyncio.create_task(
                        _generate_follow_up_question(user_query, tool_response)
                    )

                yield {
                    "chunk": _attach_metadata(
                        {"complete": final_response, "question_id": question_id},
                        selected_tool, top_intents
                    )
                }

                if follow_up_task is not None:
                    try:
                        follow_up_text = await follow_up_task
                    except Exception as e:
                        mcpcl_logger.error(f"follow_up_task failed (plain-text): {e}")
                        follow_up_text = ""
                    if follow_up_text:
                        yield {"chunk": _attach_metadata({"msg": follow_up_text}, selected_tool, top_intents)}
            else:
                yield {
                    "chunk": _attach_metadata(
                        {"complete": final_response, "question_id": question_id},
                        selected_tool, top_intents
                    )
                }

        except Exception as e:
            mcpcl_logger.exception(
                f"run_mcp_workflow: streaming path failed for tool='{selected_tool}'",
                exc_info=e
            )
            msg = "We are unable to generate a response at the moment. Please try again later."
            _persist(
                mcp_platform, user_id, question_id, user_query, msg,
                intent=top_intents, tool=selected_tool
            )
            yield {
                "chunk": _attach_metadata(
                    {"complete": msg, "question_id": question_id},
                    selected_tool, top_intents
                )
            }

    else:
        ret, final_response = await _invoke_tool(selected_tool, extracted_params)
        selected_tool_for_history = selected_tool
        top_intents_for_history = top_intents
        _persist(
            mcp_platform, user_id, question_id, user_query, final_response,
            intent=top_intents_for_history, tool=selected_tool_for_history
        )

        follow_up_task = None
        if ret and getattr(mcpSettings, "follow_up_question", False):
            follow_up_task = asyncio.create_task(
                _generate_follow_up_question(user_query, final_response)
            )

        yield {
            "chunk": _attach_metadata(
                {"complete": final_response, "question_id": question_id},
                selected_tool, top_intents
            )
        }

        if follow_up_task is not None:
            try:
                follow_up_text = await follow_up_task
            except Exception as e:
                mcpcl_logger.error(f"follow_up_task failed (json): {e}")
                follow_up_text = ""
            if follow_up_text:
                yield {"chunk": _attach_metadata({"msg": follow_up_text}, selected_tool, top_intents)}


# ---------- Tool Initialisation ----------

def _set_empty_tools(mcpSettings):
    mcpSettings.mcp_tools    = ""
    mcpSettings.mcp_tool_dict = {}
    return False


def _apply_tool_payload(mcpSettings, data: dict, source: str) -> bool:
    if not isinstance(data, dict):
        mcpcl_logger.error(f"tool_init[{source}]: invalid payload type={type(data)}")
        return _set_empty_tools(mcpSettings)

    tools     = []
    tool_dict = {}

    for tool in data.get("tools", []):
        name          = tool.get("name")
        desc          = tool.get("description", "")
        args_raw      = tool.get("args", {})
        output_format = tool.get("output_format", "json")
        endpoint      = tool.get("endpoint") or tool.get("server_uri")
        intent        = tool.get("intent", [])
        tool_access   = tool.get("tool_access")

        if not name or not endpoint:
            mcpcl_logger.warning(
                f"tool_init[{source}]: skipping invalid tool entry name='{name}' endpoint='{endpoint}'"
            )
            continue

        if tool_access and tool_access != mcpSettings.tool_access:
            mcpcl_logger.debug(
                f"tool_init[{source}]: skipping '{name}' "
                f"[tool.access='{tool_access}' != settings.tool_access='{mcpSettings.tool_access}']"
            )
            continue

        if not isinstance(args_raw, dict):
            args_raw = {}

        properties     = {}
        required_fields = []
        for arg_name, arg_info in args_raw.items():
            if not isinstance(arg_info, dict):
                arg_info = {}
            properties[arg_name] = {
                "title": arg_info.get("title", arg_name.replace("_", " ").title()),
                "type" : arg_info.get("type", "string"),
            }
            required_fields.append(arg_name)

        parameters = {
            "type"      : "object",
            "title"     : f"{name}Arguments",
            "properties": properties,
            "required"  : required_fields,
        }

        tools.append({
            "name"         : name,
            "description"  : desc,
            "parameters"   : parameters,
            "output_format": output_format,
            "server_uri"   : endpoint,
            "intent"       : intent,
        })

        tool_dict[name] = {
            "description"  : desc,
            "parameters"   : parameters,
            "output_format": output_format,
            "server_uri"   : endpoint,
            "intent"       : intent,
            "parameters_doc": "\n".join(
                f"  {k}: {v.get('description', '')}" for k, v in args_raw.items()
            ),
            "param_schema": {
                k: {
                    "type"       : args_raw[k].get("type", "str"),
                    "description": args_raw[k].get("description", ""),
                }
                for k in args_raw
            },
        }

    mcpSettings.mcp_tools = "\n".join(
        f"- {t['name']}: {t['description']}\n  Parameters: {json.dumps(t['parameters'])}"
        for t in tools
    )
    mcpSettings.mcp_tool_dict = tool_dict
    mcpcl_logger.debug(
        f"tool_init[{source}]: tool_access='{mcpSettings.tool_access}' -> "
        f"loaded {len(tools)} tools: {list(tool_dict.keys())}"
    )
    return True


def _load_tools_from_payload(mcpSettings) -> bool:
    data = getattr(mcpSettings, "tool_payload", {}) or {}
    if not isinstance(data, dict):
        mcpcl_logger.error(
            f"tool_init[payload]: tool_payload must be dict, got type={type(data)}"
        )
        return _set_empty_tools(mcpSettings)
    mcpcl_logger.debug("tool_init[payload]: loading tools from project-provided payload")
    return _apply_tool_payload(mcpSettings, data, source="payload")


async def _load_tools_from_gateway(mcpSettings) -> bool:
    gateway_url = f"{mcpSettings.mcp_url}/FetchTools"
    payload = {"tool_access": mcpSettings.tool_access}
    mcpcl_logger.debug(f"tool_init[gateway]: gateway_url={gateway_url} payload={payload}")
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(gateway_url, json=payload) as resp:
                if resp.status != 200:
                    mcpcl_logger.error(
                        f"tool_init[gateway]: gateway returned HTTP {resp.status} "
                        f"for url='{gateway_url}'"
                    )
                    return _set_empty_tools(mcpSettings)
                data = await resp.json()
    except aiohttp.ClientError as e:
        mcpcl_logger.exception(f"tool_init[gateway]: HTTP client error contacting gateway: {e}")
        return _set_empty_tools(mcpSettings)
    except asyncio.TimeoutError:
        mcpcl_logger.error(
            f"tool_init[gateway]: gateway timeout after 5s for url='{gateway_url}'"
        )
        return _set_empty_tools(mcpSettings)
    except Exception as e:
        mcpcl_logger.exception(f"tool_init[gateway]: unexpected error: {e}")
        return _set_empty_tools(mcpSettings)

    return _apply_tool_payload(mcpSettings, data, source="gateway")


async def tool_init(mcpSettings):
    use_gateway = getattr(mcpSettings, "use_gateway_tools", True)
    if use_gateway:
        return await _load_tools_from_gateway(mcpSettings)
    return _load_tools_from_payload(mcpSettings)