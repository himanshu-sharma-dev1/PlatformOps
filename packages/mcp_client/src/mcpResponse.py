import json
from typing import Any, Callable
from MCPClient.logs.AppLogging import mcpcl_logger

FORMATTERS: dict[str, Callable[[Any], str]] = {}

def register_formatter(fmt: str):
    def decorator(func: Callable[[Any], str]):
        FORMATTERS[fmt] = func
        return func
    return decorator


@register_formatter("plain-text")
def format_plain_text(data: Any) -> str:
    return str(data)


@register_formatter("chart")
def format_chart_markdown(data: Any) -> str:
    return _generate_chart_markdown(data)


@register_formatter("sql")
def format_sql(data: Any) -> str:
    return data.strip() if isinstance(data, str) else str(data)


@register_formatter("json")
def format_json(data: Any) -> str:
    return json.dumps(data, indent=2)


def _generate_chart_markdown(raw_data):
    # Unwrap if raw_data is a dictionary
    if isinstance(raw_data, dict):
        for v in raw_data.values():
            if isinstance(v, list):
                raw_data = v
                break
        else:
            raise ValueError("No valid list found in input dictionary.")

    # Normalize to format: [{'param_name': ..., 'value_list': ...}]
    if all("param_name" in item and "value_list" in item for item in raw_data):
        data = raw_data  # Already in correct format
    else:
        data = []
        for item in raw_data:
            if len(item) != 1:
                raise ValueError(f"Invalid item format: {item}")
            k, v = next(iter(item.items()))
            data.append({"param_name": k, "value_list": v})

    # Identify label field (first param where all values are strings)
    label_item = next((item for item in data if all(isinstance(x, str) for x in item["value_list"])), None)
    if not label_item:
        raise ValueError("No string-based label field found.")

    labels = label_item["value_list"]
    label_len = len(labels)

    # All other numeric series with matching length
    series = []
    for item in data:
        if item["param_name"] == label_item["param_name"]:
            continue
        values = item["value_list"]
        if len(values) == label_len and all(isinstance(v, (int, float)) for v in values):
            series.append({
                "name": item["param_name"],
                "data": values
            })

    chart_block = {
        "chart_type": "line",
        "labels": labels,
        "series": series
    }

    # Format as markdown with single quotes
    md = json.dumps(chart_block, indent=2)
    return f"::: chart\n{md}\n"


def _format_llm_response(llm_response: str, fmt: str) -> str:
    try:
        ai_resp = json.loads(llm_response) if isinstance(llm_response, str) else llm_response
        final_resp = ai_resp.get("user_response") or ai_resp.get("result")
        formatter = FORMATTERS.get(fmt)
        if fmt in {"chart", "json"}:
            return True, formatter(json.loads(final_resp))
        else:
            return True,formatter(final_resp)
    except Exception as e:
        mcpcl_logger.debug(f"Failed to format LLM response: {str(e)}")
        return False, "We couldn’t find any data."


def mcp_response_generator(resp, output_format):
    try:     
        match(output_format):
            case "json":    
                return True, resp   
                               
            case "plain-text":
                llm_response = {'user_response':resp}
                return _format_llm_response(llm_response, output_format)
            
            case _:
                tool_resp = json.dumps(resp)
                llm_response = {"user_response" : tool_resp}
                return _format_llm_response(llm_response, output_format)

    except Exception as e:
        resp = f"Failed to generate response {str(e)}"
        mcpcl_logger.error(resp)
        return False, resp
    

