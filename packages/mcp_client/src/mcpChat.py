import uuid
import json
import redis
from datetime import datetime

from CommonUtils.timer import TimerMgr
from MCPClient.mcpSetting import mcpSettings
from MCPClient.logs.AppLogging import mcpcl_logger


def get_redis_client():
    pool = getattr(mcpSettings, "redis_pool", None)

    if pool is None:
        mcpcl_logger.warning("Redis pool not initialized, using fallback")

        return redis.Redis(
            host=mcpSettings.redis_server_ip,
            port=mcpSettings.redis_server_port,
            decode_responses=True
        )

    return redis.Redis(connection_pool=pool)


def _user_chat_key(mcp_platform: str, user_id: str) -> str:
    return f"{mcp_platform}:history:{user_id}"


def mcp_generate_question_id():
    return str(uuid.uuid4())


def mcp_chat_add_response(mcp_platform, user_id, question_id, user_query,
                         llm_response, additional_info=None,
                         feedback=None, intent=None, tool=None):
    try:
        client = get_redis_client()
        current_time = TimerMgr.cutil_timer_get_app_curr_time().strftime('%d-%b-%y %H:%M:%S')

        user_msg = {
            "role": "user",
            "question_id": question_id,
            "content": user_query,
            "last_chat_time": current_time
        }

        max_chars = getattr(mcpSettings, "chat_response_max_chars", 4000)

        response_text = llm_response or ""
        truncated = False

        if len(response_text) > max_chars:
            mcpcl_logger.warning(
                f"LLM response truncated: original={len(response_text)} chars, limit={max_chars}"
            )
            response_text = response_text[:max_chars]


        assistant_msg = {
            "role": "assistant",
            "question_id": question_id,
            "content": response_text,
            "last_chat_time": current_time,
            "feedback": feedback,
            "additional_info": additional_info or {},
            "intent": intent or "",
            "tool": tool or "",
        }

        key = _user_chat_key(mcp_platform, user_id)

        pipe = client.pipeline()
        pipe.rpush(key, json.dumps(user_msg))
        pipe.rpush(key, json.dumps(assistant_msg))

        max_msgs = getattr(mcpSettings, "chat_history_max_messages", 200)
        pipe.ltrim(key, -max_msgs, -1)
        ttl = getattr(mcpSettings, "chat_history_ttl_seconds", 30 * 24 * 3600)
        pipe.expire(key, ttl)

        pipe.execute()

        mcpcl_logger.debug(f"mcp_chat_add_response: key='{key}', question_id={question_id}")

    except Exception as ex:
        mcpcl_logger.error(f"Error adding chat response: {str(ex)}")


def mcp_chat_update_feedback(mcp_platform, user_id, question_id, feedback):
    mcpcl_logger.debug(
        f"mcp_chat_update_feedback: mcp_platform={mcp_platform}, "
        f"user_id={user_id}, question_id={question_id}, feedback={feedback}"
    )

    client = get_redis_client()
    key = _user_chat_key(mcp_platform, user_id)
    chat_history = client.lrange(key, -20, -1)

    for idx, raw in enumerate(chat_history):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if msg.get("role") == "assistant" and msg.get("question_id") == question_id:
            msg["feedback"] = feedback
            client.lset(key, idx, json.dumps(msg))
            mcpcl_logger.info(f"Feedback updated — key='{key}', question_id={question_id}")
            return True

    mcpcl_logger.warning(f"No assistant message found — key='{key}', question_id={question_id}")
    return False

def mcp_chat_get_questions(mcp_platform, user_id, last_n=None):
    client = get_redis_client()
    key = _user_chat_key(mcp_platform, user_id)

    if last_n:
        raw_msgs = client.lrange(key, -(last_n * 2 + 2), -1)
    else:
        raw_msgs = client.lrange(key, 0, -1)

    questions = []

    for raw in reversed(raw_msgs):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if msg.get("role") == "user":
            questions.append({
                "query": msg.get("content", "").replace("Query: ", "", 1),
                "query_time": msg.get("last_chat_time", ""),
                "question_id": msg.get("question_id", "")
            })

        if last_n and len(questions) == last_n:
            break

    return {i: q for i, q in enumerate(reversed(questions))}

def mcp_chat_get_history(mcp_platform, user_id, last_n=None):
    client = get_redis_client()
    key = _user_chat_key(mcp_platform, user_id)
    if last_n:
        raw_msgs = client.lrange(key, -(last_n * 2 + 2), -1)
    else:
        raw_msgs = client.lrange(key, 0, -1)

    chat_history = []

    for raw in raw_msgs:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not msg.get("role") or not msg.get("content"):
            continue
        chat_history.append(msg)

    chat_info = {}
    msg_idx = 0
    for msg in chat_history:
        role = msg.get("role")

        if role == "user":
            chat_info[msg_idx] = {
                "query": msg.get("content", "").replace("Query: ", "", 1)
            }
        elif role == "assistant":
            if msg_idx in chat_info:
                chat_info[msg_idx].update({
                    "response": msg.get("content", ""),
                    "question_id": msg.get("question_id", ""),
                    "last_chat_time": msg.get("last_chat_time", ""),
                    "feedback": msg.get("feedback", "") or '',
                    "intent": msg.get("intent", ""),
                    "tool": msg.get("tool", "")
                })
                msg_idx += 1

    if last_n and len(chat_info) > last_n:
        keys = sorted(chat_info.keys())[-last_n:]
        chat_info = {i: chat_info[k] for i, k in enumerate(keys)}

    return chat_info, chat_history


def mcp_chat_get_answer(mcp_platform, user_id, question_id):
    mcpcl_logger.debug(
        f"mcp_chat_get_answer: mcp_platform={mcp_platform}, "
        f"user_id={user_id}, question_id={question_id}"
    )

    client = get_redis_client()
    key = _user_chat_key(mcp_platform, user_id)
    chat_history = client.lrange(key, 0, -1)

    question, answer = None, None

    for raw in chat_history:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if msg.get("question_id") != question_id:
            continue

        if msg.get("role") == "user":
            dt = msg.get("last_chat_time", "")
            question = {
                "question": msg.get("content", "").replace("Query: ", "", 1),
                "question_time": datetime.strptime(dt, "%d-%b-%y %H:%M:%S").strftime("%d-%m-%Y %H:%M:%S"),
                "question_id": msg.get("question_id", "")
            }

        elif msg.get("role") == "assistant":
            dt = msg.get("last_chat_time", "")
            answer = {
                "response": msg.get("content", ""),
                "response_time": datetime.strptime(dt, "%d-%b-%y %H:%M:%S").strftime("%d-%m-%Y %H:%M:%S"),
                "question_id": msg.get("question_id", ""),
                "download_link": msg.get("download_link", ""),
                "feedback": msg.get("feedback", "") or '',
                "intent": msg.get("intent", ""),
                "tool": msg.get("tool", "")
            }

    if question and answer:
        return {**question, **answer}

    return {
        "question": '',
        "question_time": '',
        "question_id": question_id,
        "response": '',
        "response_time": '',
        "download_link": '',
        "feedback": '',
        "intent": '',
        "tool": ''
    }


def mcp_chat_clear_user_history(mcp_platform, user_id):
    client = get_redis_client()
    key = _user_chat_key(mcp_platform, user_id)
    deleted = client.delete(key)
    mcpcl_logger.info(f"mcp_chat_clear_user_history: key='{key}', deleted={bool(deleted)}")
    return bool(deleted)


def mcp_chat_clear_platform_history(mcp_platform):
    client = get_redis_client()
    pattern = f"{mcp_platform}:history:*"

    cursor, deleted_count = 0, 0

    while True:
        cursor, keys = client.scan(cursor, match=pattern, count=100)
        if keys:
            client.delete(*keys)
            deleted_count += len(keys)
        if cursor == 0:
            break

    mcpcl_logger.info(
        f"mcp_chat_clear_platform_history: mcp_platform='{mcp_platform}', keys_deleted={deleted_count}"
    )
    return deleted_count


def mcp_chat_get_platform_users(mcp_platform):
    client = get_redis_client()
    pattern = f"{mcp_platform}:history:*"
    prefix = f"{mcp_platform}:history:"

    user_ids, cursor = [], 0

    while True:
        cursor, keys = client.scan(cursor, match=pattern, count=100)
        for key in keys:
            user_ids.append(key[len(prefix):])
        if cursor == 0:
            break

    mcpcl_logger.debug(
        f"mcp_chat_get_platform_users: mcp_platform='{mcp_platform}', users_found={len(user_ids)}"
    )

    return user_ids