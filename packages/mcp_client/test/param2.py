"""
*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : param_extraction_test.py
* Description       : Automated parameter extraction test cases with validation using LangChain + Ollama
*
* Revision History  :
* Date              Author                Comments
* -----------------------------------------------------------------------------------------------------------------
* 07-Oct-25         Vidushi Gandhi        Added validation framework for parameter extraction responses
*******************************************************************************************************************
"""

# ============================================================
#                   Import System Modules
# ============================================================

import os
import json
import csv
from datetime import datetime
from pathlib import Path

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama

# ============================================================
#               Define Prompt Template for Extraction
# ============================================================

from langchain.prompts import ChatPromptTemplate


def get_param_extraction_prompt():
    return ChatPromptTemplate.from_messages([
        ("system",
         """You are a specialized parameter extraction assistant. Your task is to extract ALL required parameters for a tool by systematically 
		 analyzing the provided context. Extract ONLY the specified parameters—do not add extras. Be precise, thorough, and exhaustive in searching every part of the context. Treat the entire context as a unified source: cross-reference across User Query, Chat History, and User Info to resolve values. If a parameter is implied or referenced indirectly, extract it if it logically matches the description. This is critical: failure to extract from any source, especially User Info, is not acceptable unless absolutely no evidence exists after exhaustive search.

## PARAMETERS TO EXTRACT
{params_doc}

## AVAILABLE CONTEXT
1. **User Query**: {user_query} — Primary source. Scan for direct, indirect, or implied values (e.g., dates in sentences, names in requests).
2. **Chat History**: {chat_history} — Full conversation log. Review ALL messages: prior mentions, updates, or contextual clues . Chronological order matters—use most recent if conflicts.
3. **User Info**: {user_info} — Profile or metadata. This is a mandatory source to parse exhaustively. Treat it as potentially structured data (e.g., JSON, key-value pairs) or unstructured text. Parse EVERY field strictly: look for exact key matches to parameter names , partial matches , or descriptive implications . If JSON-like, mentally parse it as a dictionary and extract accordingly. Infer associations only if evidence is clear and direct—cite the exact text.

## EXTRACTION PROCEDURE
For EACH parameter, follow this EXACT step-by-step process MANDATORILY. Think step-by-step internally: analyze, quote relevant text, and justify before assigning. You MUST exhaust each step before moving to the next. Double-check User Info multiple times if needed. Output ONLY the JSON.

**Step 1: Scan User Query Thoroughly (Mandatory First Step)**
- Read multiple times: Extract direct values, synonyms, or implications (e.g., "start on May 23" ? start_date='23-May-2025').
- Quote the exact matching text in reason.
- If found: High confidence. LOCK IN THIS VALUE—do not check or override with later sources (Chat History or User Info).
- If not found: Explicitly state in reason and move to Step 2.

**Step 2: Exhaust Chat History Completely (If Not Found in Step 1)**
- Review EVERY message in full: Look for assignments, references, or buildup 
- Combine with Query: If Query refers to "the project", link to History's mention.
- Specify the exact message/text where found in reason.
- If found: Medium-high confidence. LOCK IN THIS VALUE—do not check or override with User Info.
- If not found: Explicitly state in reason and move to Step 3.

**Step 3: Parse User Info Exhaustively (If Still Missing—This Step is Critical and Mandatory)**
- Examine ALL content repeatedly: If structured , parse as JSON/dict and extract matching keys (exact or similar, e.g., 'username' or 'user').
- For unstructured: Scan for phrases implying the parameter .
- Cross-reference with prior sources for consistency (but do not override if already found earlier).
- Standardize formats: Convert dates to 'DD-MMM-YYYY' (e.g., '22 August,2025' ? '22-Aug-2025').
- If found: Medium confidence if inferred, high if direct. Quote the exact key/text.
- If not found: Only after triple-checking, state in reason and move to Step 4.

**Step 4: Assign None ONLY After Exhausting All (Last Resort—Avoid If Possible)**
- Re-scan ALL sources one final time. Set to None only if ZERO evidence anywhere. Low confidence. Explain why no match in any source.

**Strict Rules**
- Completeness: EVERY parameter MUST be addressed—no skips. Prioritize extraction over None.
- Prioritization: STRICT WATERFALL ORDER—User Query > Chat History > User Info > None. If found in an earlier source, DO NOT OVERRIDE or change from later sources, even if later ones have values. Use later sources ONLY for confirmation (not replacement).
- Formats: Strictly match {params_doc} (e.g., dates as 'DD-MMM-YYYY'—reformat if needed, like '22 August,2025' to '22-Aug-2025').
- Ambiguities: Choose most relevant/recent within the source; explain in reason. Use medium/low confidence if weak match.
- Evidence-Based: MANDATORILY quote/cite specific text from sources in reasons for every step followed (e.g., "Step 1: Found in query: 'text'—locked, no further checks.").
- No Fabrication: Only use provided context—do not assume external knowledge. Emphasize User Info parsing: treat as key source, parse as structured if possible.

## OUTPUT FORMAT
Return ONLY a valid JSON object with this EXACT structure. No additional text.

```json
{{
  "parameters": {{
    "param_name_1": "extracted_value_or_null",
    "param_name_2": "extracted_value_or_null"
  }},
  "extraction_source": {{
    "param_name_1": "user_query|chat_history|user_info|not_found",
    "param_name_2": "user_query|chat_history|user_info|not_found"
  }},
  "confidence": {{
    "param_name_1": "high|medium|low",
    "param_name_2": "high|medium|low"
  }},
  "reason": {{
    "param_name_1": "Step-by-step explanation with quotes from source",
    "param_name_2": "Step-by-step explanation with quotes from source"
  }}
}}
```"""),
        ("human", "{user_query}"),
    ])
# ============================================================
#                   LLM Configuration
# ============================================================

llm = ChatOllama(
    base_url='http://172.236.115.95:11434',
    model='qwen3:8b',
    # model='llama3.1',
    temperature=0.1,
    format="json",
    num_ctx=16000,
    timeout=90,
)

# ============================================================
#                Metadata & Configurations
# ============================================================

TOOL_NAME = "get_impressions"

PARAMS_DOC = """
user_id : The user id.
user_query: Query asked by the user.
"""

CHAT_HISTORY = [
    "show me Pulse_Project impression data for this date 22 August,2025 and 26 August 2025"
]

USER_INFO =  """{
    "user_id": {"description": "Unique user id", "value": "UR10002"},
    "user_name": {"description": "username", "value": "admin"},
    "project_name": {"description": "Project name", "value": "Pulse_Project"},
    "start_date": {"description": "Start date", "value": "21-Aug-2025 "},
    "end_date": {"description": "end date", "value": "25-Aug-2025"},
    "device_list": {"description": "Devices", "value": [""]},
    "location_list": {"description": "Locations", "value": [""]}
}"""

# ============================================================
#                   Test Case Definitions
# ============================================================

TEST_CASES = [
    {
        "test_id": "TC_001",
        "description": "Full context extraction",
        "user_query": "show me Pulse_Project impression data for this date 22 August 2025 and 26 August 2025",
        "expected": {
            "project_name": "Pulse_Project",
            "start_date": "22-Aug-2025",
            "end_date": "26-Aug-2025",
            "username": "admin"
        }
    },
    {
        "test_id": "TC_002",
        "description": "Missing project name - should infer from user_info",
        "user_query": "show me impression data for this date 23-May-2025 only",
        "expected": {
            "project_name": "Pulse_Project",
            "start_date": "23-May-2025",
            "end_date": "23-May-2025",
            "username": "admin"
        }
    },
    {
        "test_id": "TC_003",
        "description": "Custom project and date range",
        "user_query": "show me impression data for ACMS project between 01 July 2025 and 05 July 2025",
        "expected": {
            "project_name": "ACMS",
            "start_date": "01-Jul-2025",
            "end_date": "05-Jul-2025",
            "username": "admin"
        }
    },
    {
        "test_id": "TC_004",
        "description": "When all the parameters are missing",
        "user_query": "show me impression data ",
        "expected": {
            "project_name": "Pulse_Project",
            "start_date": "22 August 2025",
            "end_date": "26 August 2025",
            "username": "admin"
        }
    },
]

# ============================================================
#                   Validation Function
# ============================================================

def validate_response(extracted: dict, expected: dict):
    """
    Compare extracted vs expected parameter values.
    Returns (is_passed, mismatch_details)
    """
    mismatches = {}
    for key, exp_val in expected.items():
        ext_val = extracted.get(key)
        # Normalize None/null
        if isinstance(ext_val, str) and ext_val.lower() == "null":
            ext_val = None
        if ext_val != exp_val:
            mismatches[key] = {"expected": exp_val, "found": ext_val}
    return (len(mismatches) == 0, mismatches)

# ============================================================
#                   Main Test Execution
# ============================================================

def run_param_extraction_tests():
    """
    Run all defined test cases with validation.
    Prints results and logs into CSV.
    """
    prompt = get_param_extraction_prompt()
    chain = prompt | llm | JsonOutputParser()

    report_file = Path("param_extraction_results.csv")
    csv_headers = ["Test ID", "Description", "Status", "Mismatches", "Extracted JSON"]
    results = []

    print("\n===================================================================")
    print("🧩 PARAMETER EXTRACTION TESTS - VALIDATION MODE")
    print("===================================================================\n")

    for case in TEST_CASES:
        print(f"🔹 Running {case['test_id']} - {case['description']}")
        value = {
            "tool": TOOL_NAME,
            "params_doc": PARAMS_DOC,
            "user_query": case["user_query"],
            "user_info": USER_INFO,
            "chat_history": CHAT_HISTORY
        }

        try:
            response = chain.invoke(value)
            print(f'response-{response}')
            extracted = response.get("parameters", {})
            passed, mismatches = validate_response(extracted, case["expected"])

            if passed:
                status = "✅ PASS"
                print(f"   ✅ PASS - Extracted Correctly")
            else:
                status = "❌ FAIL"
                print(f"   ❌ FAIL - Mismatches: {mismatches}")

            # Save to result list
            results.append([
                case["test_id"],
                case["description"],
                status,
                json.dumps(mismatches),
                json.dumps(extracted)
            ])

        except Exception as e:
            print(f"   ⚠️ ERROR: {e}")
            results.append([
                case["test_id"], case["description"], "❌ ERROR", str(e), "{}"
            ])

    # =====================================================
    # Save results to CSV
    # =====================================================
    with open(report_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        writer.writerows(results)

    print("\n===================================================================")
    print(f"📄 TEST SUMMARY SAVED TO: {report_file.resolve()}")
    print("===================================================================\n")


# ============================================================
#                           MAIN
# ============================================================

if __name__ == "__main__":
    run_param_extraction_tests()
