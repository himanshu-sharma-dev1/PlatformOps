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

# def get_param_extraction_prompt():
#     """
#     Returns a ChatPromptTemplate for extracting parameter values based on
#     user query, chat history, and parameter documentation.
#     The output is always a valid JSON object with parameter names and their inferred values.
#     """
#     return ChatPromptTemplate.from_messages([
#         ("system",
#         """
# You are an intelligent **Parameter Extraction Assistant**.

# Your role is to analyze the provided context and extract structured parameter values
# from the user query and chat history based on the parameter documentation.

# ---

# ### 🧠 INSTRUCTIONS

# 1. Carefully read the **Parameter Documentation (`params_doc`)**.
#    - It defines each parameter and describes what kind of value it represents.

# 2. Use information from both the **User Query** and **Chat History** to determine values.
#    - Extract explicit mentions directly.
#    - Infer implicit details logically when possible.
#    - If a parameter cannot be determined, assign it `null`.

# 3. Output only a **valid JSON object** containing all parameters from `params_doc`.

# 4. Do **not** include any explanations, reasoning, or extra commentary in the output.

# ---

# ### ✅ OUTPUT FORMAT
# Return JSON strictly in this structure:
# {{
#   "<parameter_name_1>": "<value or null>",
#   "<parameter_name_2>": "<value or null>",
#   ...
# }}

# ---

# ### ⚖️ RULES
# - Keep all parameter names exactly as they appear in `params_doc`.
# - Ensure the JSON is syntactically valid.
# - Avoid adding extra fields or metadata.
#         """),
#         ("human",
#         """
# params_doc:
# {params_doc}

# user_query:
# {user_query}

# chat_history:
# {chat_history}
#         """)
#     ])
      

def get_param_extraction_prompt():
    """
    Returns a ChatPromptTemplate for extracting parameter values based on
    user query, chat history, and parameter documentation.
    The output is always a valid JSON object with parameter names and their inferred values.
    """
    return ChatPromptTemplate.from_messages([
        ("system",
        """
You are an intelligent **Parameter Extraction Assistant**.
Your role is to analyze the provided context and extract structured parameter values
from the user query and chat history based on the parameter documentation.
---
### ???? INSTRUCTIONS
1. Carefully read the **Parameter Documentation (`params_doc`)**.
   - It defines each parameter and describes what kind of value it represents.

2. **STRICT EXTRACTION PRIORITY** (Follow this order exactly):
   a) **PRIMARY SOURCE - User Query**: 
      - First, thoroughly analyze the current user query
      - Extract ALL explicitly mentioned parameter values
      - Infer implicit values from the user query context
      - Mark parameters found in user query as CONFIRMED
   
   b) **SECONDARY SOURCE - Chat History**: 
      - ONLY use chat history for parameters NOT found in user query
      - Search through the entire chat history chronologically
      - Extract any relevant parameter values mentioned in previous messages
      - Prefer more recent mentions over older ones if conflicts exist
   
   c) **DEFAULT**: 
      - If a parameter is not found in either source, assign it `null`

3. **THOROUGHNESS REQUIREMENTS**:
   - Read EVERY line of the user query before moving to chat history
   - Read EVERY message in chat history for missing parameters
   - Look for direct mentions, synonyms, and contextual clues
   - Consider implicit information (e.g., "tomorrow" implies a date)

4. Output only a **valid JSON object** containing all parameters from `params_doc`.

5. Do **not** include any explanations, reasoning, or extra commentary in the output.
---
### ???? OUTPUT FORMAT
Return JSON strictly in this structure:
{{
  "<parameter_name_1>": "<value or null>",
  "<parameter_name_2>": "<value or null>",
  ...
}}
---
### ?? CRITICAL RULES
- **PRIORITY**: User query values ALWAYS override chat history values
- **COMPLETENESS**: Check every parameter against BOTH sources
- Keep all parameter names exactly as they appear in `params_doc`
- Ensure the JSON is syntactically valid (proper quotes, commas, braces)
- Avoid adding extra fields or metadata
- Never skip parameters - every parameter from `params_doc` must appear in output
- Use `null` (not "null", "N/A", "", or undefined) for missing values
---
### ???? EXTRACTION PROCESS
Step 1: Parse params_doc to identify all required parameters
Step 2: Extract values from user_query (PRIMARY)
Step 3: Fill remaining nulls from chat_history (SECONDARY)
Step 4: Return complete JSON with all parameters
        """),
        ("human",
        """
params_doc:
{params_doc}

user_query:
{user_query}

chat_history:
{chat_history}
        """)
    ])

# ============================================================
#                   LLM Configuration
# ============================================================

llm = ChatOllama(
    base_url='http://172.236.115.95:11434',
    model='llama3.1',
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
project_name: Name of the project for which impressions data is requested.
start_date: Start date of the impression window.
end_date: End date of the impression window.
"""


CHAT_HISTORY = []
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
            "start_date": "22 August 2025",
            "end_date": "26 August 2025",
            
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
            
        }
    },
    {
        "test_id": "TC_003",
        "description": "Custom project and date range",
        "user_query": "show me impression data for ACMS project between 01 July 2025 and 05 July 2025",
        "expected": {
            "project_name": "ACMS",
            "start_date": "01 July 2025",
            "end_date": "05 July 2025",
            
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
            
        }
    },
    {
        "test_id": "TC_005",
        "description": "When all the parameters are missing",
        "user_query": "show me dwell time data ",
        "expected": {
            "project_name": "Pulse_Project",
            "start_date": "22 August 2025",
            "end_date": "26 August 2025",
            
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
            "chat_history": CHAT_HISTORY
        }     
        response = chain.invoke(value)
        CHAT_HISTORY.insert(0,case["user_query"])
        print(f'Query: {case["user_query"]}')
        print(f'response-{response},CHAT_HISTORY-{CHAT_HISTORY}')
           

# ============================================================
#                           MAIN
# ============================================================

if __name__ == "__main__":
    run_param_extraction_tests()
