"""
DSPy MIPROv2-based guardrail classifier — third tier, alongside the
NeMo Guardrails (mcpGuardrails.py) and Guardrails-AI (mcpGuardrailsAI.py)
implementations.

This module loads a MIPROv2-compiled dspy.Predict program (instructions +
few-shot demos, saved as JSON) and uses it purely as a scope classifier:
in_scope vs out_of_scope. It exposes the same
(in_scope, refusal_message, direct_response) 3-tuple contract as the other
two tiers so it's a drop-in replacement inside run_input_guardrails() /
run_mcp_workflow() in mcpClient.py.

Unlike the NeMo path, this tier never produces a `direct_response`
(no conversational/greeting bypass) — it only answers the scope question.
"""

import time
from pathlib import Path
import asyncio
from typing import Optional, Tuple

import dspy

from MCPClient.mcpSetting import mcpSettings


# ---------- Default program location (lives inside the MCP repo, not the project) ----------

# The compiled MIPROv2 program is an asset of MCPClient itself. For now this
# is a fixed default — nothing from the calling project's config is read or
# allowed to override it.
_PACKAGE_DIR = Path(__file__).resolve().parent
_DSPY_PROGRAM_PATH = _PACKAGE_DIR / "telecom_guardrail_2.json"


# ---------- Signature (must match the compiled program's signature) ----------
#
# NOTE: this must match whatever signature `telecom_guardrail_2.json` was
# actually compiled against. If the compiled program's demos were produced
# with a 3-field (verdict/category/reason) signature, dropping `reason`
# here may make `.load()` fail or silently ignore the mismatched demos —
# verify against the compiled JSON before treating this as a pure win.
# The standalone benchmark script used this 2-field signature against the
# same JSON file successfully, which is why it's reproduced as-is here.

class ChurnScopeSignature(dspy.Signature):
    """Classify whether a query belongs to the Airtel churn analytics platform."""

    query: str = dspy.InputField(desc="User query to classify")
    verdict: str = dspy.OutputField(desc="Return exactly one of: in_scope, out_of_scope")
    category: str = dspy.OutputField(
        desc="Short label such as churn analytics, retention, politics, weather, corporate, or general"
    )


_DEFAULT_OUT_OF_SCOPE_MSG = (
"I'm a telecom churn analytics assistant. I can help with subscriber churn patterns, retention metrics, network quality drivers, and customer lifecycle insights. I can't help with that particular request — could you rephrase it in terms of churn, retention, or telecom KPIs?"
)


# ---------- Init ----------

def mcp_guardrails_dspy_init(guardrails_config: Optional[dict]) -> Tuple[bool, str]:

    if not guardrails_config:
        mcpSettings.guardrails_dspy_enabled = False
        return True, "DSPy guardrails disabled (no config supplied)"

    if not guardrails_config.get("guardrail_dspy_flag"):
        mcpSettings.guardrails_dspy_enabled = False
        return True, "DSPy guardrails disabled by flag"

    program_path = _DSPY_PROGRAM_PATH
    if not program_path.is_file():
        mcpSettings.guardrails_dspy_enabled = False
        return False, f"DSPy guardrails program file not found: '{program_path}'"

    try:

        model_str = f"openai/{guardrails_config.get('llm_model')}"
        base_url = (guardrails_config.get("llm_base_url") or "").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"

        lm = dspy.LM(
            model=model_str,
            api_base=base_url,
            api_key=guardrails_config.get("llm_api_key") or "dummy",
            temperature=guardrails_config.get("llm_temperature", 0.0),

            max_tokens=guardrails_config.get("num_predict") or 16,
        )
        classifier = dspy.Predict(ChurnScopeSignature)
        predict_end = time.perf_counter()

        classifier.load(str(program_path))

        mcpSettings.dspy_guardrail.program_path = str(program_path)
        mcpSettings.dspy_guardrail.model = classifier
        mcpSettings.dspy_guardrail.lm = lm
        mcpSettings.guardrails_dspy_enabled = True

        return True, "Initialization Complete"

    except Exception as e:
        mcpSettings.guardrails_dspy_enabled = False

        return False, f"DSPy guardrails init failed: {str(e)}"


def mcp_guardrails_dspy_is_enabled() -> bool:
    return bool(getattr(mcpSettings, "guardrails_dspy_enabled", False))


# ---------- Inference ----------

def _run_classifier(user_query: str):
    classifier = mcpSettings.dspy_guardrail.model
    lm = mcpSettings.dspy_guardrail.lm
    with dspy.context(lm=lm):
        pred = classifier(query=user_query)

    return pred


async def mcp_guardrails_dspy_check_input(user_query: str) -> Tuple[bool, Optional[str], Optional[str]]:

    if not mcp_guardrails_dspy_is_enabled() or mcpSettings.dspy_guardrail.model is None:
        return True, None, None

    try:

        pred = await asyncio.to_thread(_run_classifier, user_query)

        verdict = str(getattr(pred, "verdict", "")).strip().lower()
        category = str(getattr(pred, "category", "")).strip()


        if verdict == "out_of_scope":
            return False, _DEFAULT_OUT_OF_SCOPE_MSG, None

        return True, None, None

    except Exception as e:

        return True, None, None