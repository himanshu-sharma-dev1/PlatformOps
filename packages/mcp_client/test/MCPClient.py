import time

import pytest
import asyncio
import json
from McpClient import mcp_init, mcp_tool_request
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


'''
    -> Alter Config as per requirement  
    -> hit pytest -v --log-cli-level=INFO test_mcp_client.py in the terminal to run test
'''


@pytest.fixture
def config():
    return {
        "mcp_url": "http://192.168.10.48:9000/mcp",  # your MCP server
        "llm_model": "llama3.1",
        "llm_server_ip": "54.193.149.243",
        "llm_server_port": 11434,
        "redis_server_ip": "54.193.149.243",
        "redis_server_port": 8030
    }

user_id = "test_user09"
test_method_1 = "Get an appointment for John Dow on 15 July 2025"
test_method_2 = "Set an appointment for John Dow on 15 July 2025 between 10 to 12"

@pytest.mark.asyncio
@pytest.mark.integration
def test_mcp_initiate(config):

    ok, msg = (mcp_init(config))[:2]
    logger.info(f"[Init] ok={ok}, msg={msg}")



@pytest.mark.asyncio
async def test_tool_get_slot():
    try:
        result = await mcp_tool_request(user_id, test_method_1)
        time.sleep(7)
        logger.info(f"test_tool_get_slot Result: {result}")
        if 'error' in result:
            pytest.fail(f"test_tool_get_slot Error: {result}")

    except Exception as e:
        pytest.fail(f"test_tool_get_slot Exception: {e}")


@pytest.mark.asyncio
async def test_tool_set_slot():
    try:
        result = await mcp_tool_request(user_id, test_method_2)
        time.sleep(7)
        logger.info(f"test_tool_set_slot Result: {result}")
        if 'error' in result:
            pytest.fail(f"test_tool_set_slot Error: {result}")
    except Exception as e:
        pytest.fail(f"test_tool_set_slot Exception: {e}")
