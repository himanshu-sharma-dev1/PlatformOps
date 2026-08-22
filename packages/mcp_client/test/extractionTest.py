from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama

def get_param_extraction_prompt():
    return ChatPromptTemplate.from_messages([
        ("system",
         """
You are a specialized parameter extraction assistant. Your task is to extract ALL required parameters for a tool by systematically analyzing the provided context.

## PARAMETERS TO EXTRACT
{params_doc}

## AVAILABLE CONTEXT
1. **User Query**: {user_query}
2. **Chat History**: {chat_history}
3. **User Info**: {user_info}

## EXTRACTION PROCEDURE

Follow this systematic approach to extract each parameter:

Procedure : 
Your work is to find out the parameters from all the data provided to you
Step 1: Try to first extract the parameter from User Query if found
Step 2: If parameters are still missing use **Chat History**
Step 3: If there are still missing then extract the parameters from **User Info**
Step 4: If not find anywhere in the context provided assign the missing values None.


Strict Conditions
Always try to find all the parameters which is provided as per description from the context,spend some time in each step thinking and analyzing the parameters
go through all the points and the input field provided to generate the data

## OUTPUT FORMAT
Return a valid JSON object with this exact structure. Also provide a `reason` field explaining:
- How the instructions were followed
- Why some parameters were extracted from a particular source
- Why any parameter failed (set to null)

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
    "param_name_1": "Explain which step it was extracted from and why",
    "param_name_2": "Explain why it could not be found or source used"
  }}
}} """),
        ("human", "{user_query}"),
    ])




if __name__ == "__main__":
    # Initialize model
    llm_config = ChatOllama(
        base_url='http://172.236.115.95:11434',
        model='qwen3:8b',
        temperature=0.1,
        format="json",
        timeout=60,
        num_predict=-2,
        num_ctx=16000,
        keep_alive=-1
    )

    # Create chain
    prompt = get_param_extraction_prompt()
    chain = prompt | llm_config | JsonOutputParser()



    # Common metadata for all test cases
    tool = "get_impressions"
    params = [
        "project_name", "start_date", "end_date", "username","user_query"
    ]
    params_doc = """
      project_name: The Project Name for the Impressions
      start_date: The start date of the impressions.
      end_date: The end date of the impressions.
      username: The username of the authorized user.
      user_query: User query
    """


    chat_history = ["show me Pulse_Project impression data for this date 22 August,2025 and 26 August 2025"]

    user_info =  """{
    "user_id": {"description": "Unique user id", "value": "UR10002"},
    "user_name": {"description": "username", "value": "admin"},
    "project_name": {"description": "Project name", "value": "Pulse_Project"},
    "start_date": {"description": "Start date", "value": "21-Aug-2025 "},
    "end_date": {"description": "end date", "value": "25-Aug-2025"},
    "device_list": {"description": "Devices", "value": [""]},
    "location_list": {"description": "Locations", "value": [""]}
}"""


    # ✅ Define multiple test cases
    testcases= {"test_1" : [
        {"query": "show me Pulse_Project impression data for this date 22 August,2025 and 26 August 2025"},
        {"query": "Tell me impression data of ACMS project 27 August to 31 September 2024"},
    ],

    "test_2" : [
        {"query": "show me impression data "},
        {"query": "show me Pulse_Project impression data"},
        {"query": "show me impression data of any project"},
        {"query": "show me impression data for this date 23-May-2025 only"},
    ]}

    # ✅ Run test cases
    print("----- Running Parameter Extraction Test Cases -----\n")
    for idx, test in testcases.items():
        for i,q in enumerate(test):
          print(f"Test Case {idx} User Query: {q['query']}")
          value = {
                  "tool": tool,
                  "params_doc": params_doc,
                  "user_query": q['query'],
                  "user_info": user_info,
                  "chat_history": chat_history
              }
          try:
              print("Response:", chain.invoke(value), "\n")
          except Exception as e:
              print("❌ Error:", e, "\n")


