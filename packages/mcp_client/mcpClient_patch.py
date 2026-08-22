# ============================================================================
# PATCH FOR MCPClient/src/mcpClient.py
# ============================================================================
#
# Three changes:
#   1. Import the guardrails check functions
#   2. Insert the INPUT rail check at the top of run_mcp_workflow (after
#      question_id is generated, before tool selection)
#   3. Wrap llm_response with the OUTPUT rail check just before
#      mcp_chat_add_response is called at the end of the workflow
#
# Detailed steps follow.
# ============================================================================


# ─── CHANGE 1: add import near the other MCPClient.src imports ───────────────
#
# Find this existing line near the top of mcpClient.py:
#
#     from MCPClient.src import mcpChat, mcpPrompt, mcpResponse
#
# Add this line right after it:

from MCPClient.src.mcpGuardrails import (
    mcp_guardrails_check_input,
    mcp_guardrails_check_output,
    mcp_guardrails_is_enabled,
)


# ─── CHANGE 2: input rail check inside run_mcp_workflow ──────────────────────
#
# In run_mcp_workflow, locate this block (around line 428):
#
#     question_id = mcpChat.mcp_generate_question_id()
#
#     if selected_tool_override:
#         ...
#
# Insert the following block IMMEDIATELY AFTER the `question_id = ...` line
# and BEFORE the `if selected_tool_override:` line:

# === BEGIN INSERT ===

    # Guardrails: input rail (domain scope check).
    # Skip entire tool selection pipeline if query is out of scope.
    if mcp_guardrails_is_enabled():
        in_scope, refusal = mcp_guardrails_check_input(user_query)
        if not in_scope:
            refusal_msg = refusal or "Sorry, that question is outside my scope."
            mcpChat.mcp_chat_add_response(
                mcp_platform, user_id, question_id, user_query, refusal_msg,
                intent="out_of_scope", tool="guardrails:input_rail"
            )
            yield {"chunk": _attach_metadata(
                {"msg": refusal_msg}, "guardrails:input_rail", ["out_of_scope"]
            )}
            return

# === END INSERT ===


# ─── CHANGE 3: output rail check before persistence ──────────────────────────
#
# The workflow yields chunks in several branches (plain-text streaming, sql,
# chart, json). For the OUTPUT rail to be effective without breaking streaming,
# apply it ONLY in the non-streaming branches where the full response is
# available before mcp_chat_add_response is called.
#
# Look for calls to mcpChat.mcp_chat_add_response that pass `llm_response`
# (not the early-return "msg" calls). For each, wrap the response like this:
#
#     # BEFORE:
#     mcpChat.mcp_chat_add_response(
#         mcp_platform, user_id, question_id, user_query, llm_response,
#         intent=top_intents, tool=selected_tool
#     )
#
#     # AFTER:
#     if mcp_guardrails_is_enabled():
#         is_safe, llm_response = mcp_guardrails_check_output(user_query, llm_response)
#         if not is_safe:
#             # Re-tag so chat history shows what happened
#             selected_tool_for_history = "guardrails:output_rail"
#             top_intents_for_history   = ["out_of_scope_response"]
#         else:
#             selected_tool_for_history = selected_tool
#             top_intents_for_history   = top_intents
#     else:
#         selected_tool_for_history = selected_tool
#         top_intents_for_history   = top_intents
#
#     mcpChat.mcp_chat_add_response(
#         mcp_platform, user_id, question_id, user_query, llm_response,
#         intent=top_intents_for_history, tool=selected_tool_for_history
#     )
#
# For the streaming plain-text branch, run the check AFTER chunks are collected
# but BEFORE the final yield, using the joined chunks string as llm_response.
#
# Skip the output rail entirely for SQL/chart output formats unless your
# domain definitely covers structured outputs — text-based topic classifiers
# typically misjudge raw SQL or JSON.
