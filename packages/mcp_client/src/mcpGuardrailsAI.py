import os,json, re
import asyncio
import time
from typing import Optional, Tuple, Dict, Any , List

from MCPClient.mcpSetting import mcpSettings
from MCPClient.logs.AppLogging import mcpcl_logger

_state: Dict[str, Any] = {
    "enabled":         False,
    "fail_mode":       "open",
    "topic_guard":     None,
    "refusal_message": None,
    "domain":          "telecom_churn_analytics",
    "llm_provider": None,
    "llm_model": None,
    "llm_base_url": None,
}


def build_scope_classification_prompt(text: str, on_topics: List[str], off_topics: List[str]) -> str:
    return f"""You are a topic classifier for a telecom churn analytics assistant.

Given the USER TEXT, decide which TOPICS from the ON-TOPICS and OFF-TOPICS lists below are present in it.

Respond with strict JSON only, exactly in this shape:
{{"topics_present": []}}

Rules:
1. Only use topics from the ON-TOPICS or OFF-TOPICS lists below. Never output a topic not in either list.
2. Greetings, thanks, and small talk ("hi", "hello", "hey", "thanks", "ok", "bye")
   are NOT general knowledge. Output {{"topics_present": []}} for these.
3. Questions about what you can do, how to use you, or what to ask you
   ("what can you do", "help", "who are you", "what is this chatbot") must be
   classified ONLY as "assistant capabilities".
4. If the text contains no clear topic, output {{"topics_present": []}}.

Examples:
TEXT: "hello"
{{"topics_present": []}}

TEXT: "thanks"
{{"topics_present": []}}

TEXT: "what can you do"
{{"topics_present": ["assistant capabilities"]}}

TEXT: "what's the weather in delhi"
{{"topics_present": ["weather"]}}

TEXT: "show me churn rate by circle"
{{"topics_present": ["telecom subscriber churn"]}}

ON-TOPICS (in-scope for this assistant):
------
{on_topics}

OFF-TOPICS (out-of-scope, should never be answered):
------
{off_topics}

TEXT:
"{text}"

Result:
"""

_INJECTION_PATTERN = re.compile(
    r'(ignore\s+(all\s+)?previous|forget\s+(\w+\s+)*your|disregard\s+your|'
    r'system\s+prompt|bypass\s+(your\s+)?filter|developer\s+mode|'
    r'you\s+are\s+now\s+(a\s+)?different|from\s+now\s+on\s+you|'
    r'now\s+your\s+role\s+is|your\s+role\s+is\s+now|'
    r'you\s+are\s+now\s+a.*assistant|act\s+as\s+a.*assistant|'
    r'no\s+restrictions|'
    r'<\s*/?\s*(system|assistant|user)\b)',   # fake role/system tags like <system>, </system>
    re.IGNORECASE
)

def ollama_scope_classifier(
    text: str,
    valid_topics: list,
    invalid_topics: list,
    llm_cfg: dict,
) -> dict:
    from ollama import Client
    import json

    prompt = build_scope_classification_prompt(
        text=text,
        on_topics=valid_topics,
        off_topics=invalid_topics,
    )

    client = Client(
        host=(llm_cfg.get("base_url") or "").rstrip("/")
    )

    response = client.chat(
        model=llm_cfg["model"],
        format="json",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": llm_cfg.get("temperature", 0.0),
            "num_ctx": llm_cfg.get("num_ctx", 4096),
            "num_predict": llm_cfg.get("num_predict", 128),
        }
    )

    content = response["message"]["content"]

    return json.loads(content)

def build_restrict_to_topic_wrapper(
    valid_topics,
    invalid_topics,
    llm_cfg,
):
    def wrapper(text, topics):

        result = ollama_scope_classifier(
            text=text,
            valid_topics=valid_topics,
            invalid_topics=invalid_topics,
            llm_cfg=llm_cfg,
        )

        in_scope = bool(result.get("in_scope"))
        matched_topic = result.get("matched_topic", "none")

        if in_scope and matched_topic in valid_topics:
            return [matched_topic]

        if (not in_scope) and matched_topic in invalid_topics:
            return [matched_topic]

        return result.get("topics_present", [])

    return wrapper

def mcp_guardrails_ai_init(guardrails_config: Optional[Dict[str, Any]]) -> Tuple[bool, str]:

    _state["enabled"]     = False
    _state["topic_guard"] = None

    mcpSettings.guardrails_ai_enabled = False

    if not guardrails_config or not guardrails_config.get("enabled"):
        mcpcl_logger.debug("mcp_guardrails_ai_init: disabled or no config")
        return True, "Guardrails disabled"

    try:
        import transformers
        from unittest.mock import MagicMock
        transformers.pipeline = MagicMock()

        from guardrails import Guard
        from guardrails.hub import RestrictToTopic
    except ImportError as ex:
        return False, (
            f"guardrails-ai or RestrictToTopic not installed: {ex}. "
            f"Install with: pip install guardrails-ai && "
            f"guardrails hub install hub://tryolabs/restricttotopic"
        )

    try:
        topic_cfg    = guardrails_config.get("topic", {})
        messages_cfg = guardrails_config.get("messages", {})
        llm_cfg      = guardrails_config.get("llm", {})

        configured_valid_topics   = list(topic_cfg.get("valid_topics", []))
        configured_invalid_topics = list(topic_cfg.get("invalid_topics", []))

        restrict_wrapper = build_restrict_to_topic_wrapper(
            valid_topics=configured_valid_topics,
            invalid_topics=configured_invalid_topics,
            llm_cfg=llm_cfg,
        )

        restrict_validator = RestrictToTopic(
            valid_topics=configured_valid_topics,
            invalid_topics=configured_invalid_topics,
            disable_classifier=True,
            disable_llm=False,
            llm_callable=restrict_wrapper,
            on_fail="exception"
        )
        # print(f" restrict_validator -- {restrict_validator.__dict__}")

        start = time.time()
        topic_guard = Guard().use(restrict_validator)
        mcpcl_logger.debug(f"mcp_guardrails_ai_init: topic_guard build took {time.time() - start:.2f}s")

        _state["enabled"]         = True
        _state["fail_mode"]       = guardrails_config.get("fail_mode", "open")
        _state["topic_guard"]     = topic_guard
        _state["refusal_message"] = messages_cfg.get("refusal_message")
        _state["llm_provider"] = llm_cfg.get("provider")
        _state["llm_model"] = llm_cfg.get("model")
        _state["llm_base_url"] = llm_cfg.get("base_url")
        _state["llm_temperature"] = llm_cfg.get("temperature")
        _state["llm_num_ctx"] = llm_cfg.get("num_ctx")
        _state["llm_num_predict"] = llm_cfg.get("num_predict")
        _state["llm_keep_alive"] = llm_cfg.get("keep_alive")
        _state["llm_timeout"] = llm_cfg.get("timeout")
        _state["llm_format"] = llm_cfg.get("format")

        # mcpSettings.guardrails_ai_enabled = True
        mcpSettings.guardrails_ai_enabled = guardrails_config.get("enabled")

        mcpcl_logger.debug(
            f"[GUARDRAILS_AI] -- model={llm_cfg.get('model')} , provider={llm_cfg.get('provider')} "
            f"base_url={llm_cfg.get('base_url')} , fail_mode='{_state['fail_mode']}'"
            f"temperature={llm_cfg.get('temperature')} , num_ctx={llm_cfg.get('num_ctx')} "
            f"num_predict={llm_cfg.get('num_predict')} , keep_alive={llm_cfg.get('keep_alive')} "
            f"timeout={llm_cfg.get('timeout')} , format={llm_cfg.get('format')} ")

        return True, "Guardrail AI Initialization Complete"

    except Exception as ex:
        mcpcl_logger.error(f"mcp_guardrails_ai_init failed: {ex}", exc_info=True)
        return False, f"Guardrails AI init failed: {str(ex)}"


async def mcp_guardrails_ai_check_input(user_query: str) -> Tuple[bool, Optional[str], Optional[str]]:
    if not _state["enabled"] or _state["topic_guard"] is None:
        return True, None, None

    try:
        loop = asyncio.get_event_loop()

        start = time.time()
        # META_QUERIES = ["help", "what can you do",
        #     "how can you help",
        #     "who are you",
        #     "what is this chatbot",
        #     "show examples",
        #     "example queries",
        #     "supported queries",
        #     "capabilities",
        # ]
        # query_lower = user_query.lower().strip()
        #
        # if any(meta in query_lower for meta in META_QUERIES):
        #     return True, None, None

        if _INJECTION_PATTERN.search(user_query):
            mcpcl_logger.info(f"[GUARDRAILS_AI_CHECK] BLOCKED via regex (injection): query='{user_query[:80]}'")
            return False, _default_refusal(), None

        await loop.run_in_executor(None, lambda: _state["topic_guard"].validate(user_query))
        elapsed = time.time() - start

        mcpcl_logger.debug( f"[GUARDRAILS_AI_CHECK] query='{user_query[:80]}' "
            f"took={elapsed:.2f}s status=PASSED")
        return True, None, None

    except Exception as ex:
        validator_name = type(ex).__name__
        mcpcl_logger.info(
            f"[GUARDRAILS_AI_CHECK] BLOCKED validator={validator_name} "
            f"domain='{_state['domain']}' query='{user_query[:80]}' "
            f"reason='{str(ex)[:150]}'"
        )

        if _state["fail_mode"] == "closed":
            return False, _default_refusal(), None

        if "Validation" in validator_name:
            return False, _default_refusal(), None

        mcpcl_logger.warning(
            f"[GUARDRAILS_AI_CHECK] non-validation error, fail-open allowing: {ex}"
        )
        return True, None, None


def mcp_guardrails_ai_is_enabled() -> bool:
    return bool(_state["enabled"])


def _default_refusal() -> str:
    if _state.get("refusal_message"):
        return _state["refusal_message"]
    return (
        f"I can only help with questions related to {_state.get('domain', 'this assistant')}. "
        f"Could you rephrase your request in that context?"
    )