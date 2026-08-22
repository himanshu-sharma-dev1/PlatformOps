# ============================================================================
# APPEND THIS BLOCK TO THE END OF MCPClient/src/mcpInit.py
# ============================================================================

from MCPClient.src.mcpGuardrails import mcp_guardrails_init as _gr_init


def mcp_guardrails_init(guardrails_config: dict):
    """Init wrapper matching the signature of other mcp_*_init functions.

    Accepts the full guardrails_config dict (or None to disable).
    Returns (success: bool, message: str).
    """
    if guardrails_config is not None and not isinstance(guardrails_config, dict):
        return False, "Invalid configuration: guardrails_config must be a dict or None."
    return _gr_init(guardrails_config)
