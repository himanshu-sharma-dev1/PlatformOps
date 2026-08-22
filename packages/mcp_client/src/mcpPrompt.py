# Import modules
from langchain_core.prompts import ChatPromptTemplate

def get_tool_selection_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant to select a tool.
            Here are the tools:
            {tool_list}
    
            Context:
            - User Info: {user_info}
            - Chat History: {chat_history}
            - Session: {user_session}
    
            Pick one tool or 'None'. 
            Answer in strict JSON with key 'tool'."""),
            ("human", "{user_query}"
        ),
    ])


# def get_param_extraction_prompt():
#     return ChatPromptTemplate.from_messages([
#        ("system", """You are a helpful assistant to extract parameters for the tool **{tool}**.

#         The tool requires the following parameters:
#         {params}

#         Use the following context to extract values:
#         - User Info: {user_info}
#         - Chat History: {chat_history}
#         - Session: {user_session}

#         If a parameter is missing, set its value to None. 
#         Respond ONLY in JSON with keys matching the parameter names.
#         """),
#         ("human", "{user_query}"),
#     ])

# def get_param_extraction_prompt():
#     return ChatPromptTemplate.from_messages([
#        ("system", """You are a helpful assistant to extract parameters for the tool **{tool}**.

#         The tool requires the following parameters:
#         {params} and here is the parameter description {params_doc}

#         Use the following context to extract values:
#         - User Info: {user_info}
#         - Chat History: {chat_history}
#         - Session: {user_session}

#         If a parameter is missing, set its value to None. 
#         Respond ONLY in JSON with keys matching the parameter names.
#         """),
#         ("human", "{user_query}"),
#     ])



# def get_param_extraction_prompt():
#     """
#     Returns a ChatPromptTemplate for extracting parameter values based on
#     user query, chat history, and parameter documentation.
#     The output is always a valid JSON object with parameter names and their inferred values.
#     """
#     return ChatPromptTemplate.from_messages([
#         ("system",
#         """
#   You are an intelligent **Parameter Extraction Assistant**.
#   Your role is to analyze the provided context and extract structured parameter values
#   from the user query and chat history based on the parameter documentation.
#   ---
#   ### ???? INSTRUCTIONS
#   1. Carefully read the **Parameter Documentation (`params_doc`)**.
#     - It defines each parameter and describes what kind of value it represents.

#   2. **STRICT EXTRACTION PRIORITY** (Follow this order exactly):
#     a) **PRIMARY SOURCE - User Query**: 
#         - First, thoroughly analyze the current user query
#         - Extract ALL explicitly mentioned parameter values
#         - Infer implicit values from the user query context
#         - Mark parameters found in user query as CONFIRMED
    
#     b) **SECONDARY SOURCE - Chat History**: 
#         - ONLY use chat history for parameters NOT found in user query
#         - Search through the entire chat history chronologically
#         - Extract any relevant parameter values mentioned in previous messages
#         - Prefer more recent mentions over older ones if conflicts exist
    
#     c) **DEFAULT**: 
#         - If a parameter is not found in either source, assign it `null`

#   3. **THOROUGHNESS REQUIREMENTS**:
#     - Read EVERY line of the user query before moving to chat history
#     - Read EVERY message in chat history for missing parameters
#     - Look for direct mentions, synonyms, and contextual clues
#     - Consider implicit information (e.g., "tomorrow" implies a date)

#   4. Output only a **valid JSON object** containing all parameters from `params_doc`.

#   5. Do **not** include any explanations, reasoning, or extra commentary in the output.
#   ---
#   ### ???? OUTPUT FORMAT
#   Return JSON strictly in this structure:
#   {{
#     "<parameter_name_1>": "<value or null>",
#     "<parameter_name_2>": "<value or null>",
#     ...
#   }}
#   ---
#   ### ?? CRITICAL RULES
#   - **PRIORITY**: User query values ALWAYS override chat history values
#   - **COMPLETENESS**: Check every parameter against BOTH sources
#   - Keep all parameter names exactly as they appear in `params_doc`
#   - Ensure the JSON is syntactically valid (proper quotes, commas, braces)
#   - Avoid adding extra fields or metadata
#   - Never skip parameters - every parameter from `params_doc` must appear in output
#   - Use `null` (not "null", "N/A", "", or undefined) for missing values
#   ---
#   ### ???? EXTRACTION PROCESS
#   Step 1: Parse params_doc to identify all required parameters
#   Step 2: Extract values from user_query (PRIMARY)
#   Step 3: Fill remaining nulls from chat_history (SECONDARY)
#   Step 4: Return complete JSON with all parameters
#           """),
#           ("human",
#           """
#   params_doc:
#   {params_doc}

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
    Each parameter value must match the expected type defined in `params_doc`
    (e.g., string, integer, list, boolean, etc.).
    """
    return ChatPromptTemplate.from_messages([
        ("system",
        """
            You are an intelligent **Parameter Extraction Assistant**.
            Your task is to analyze the provided context and extract structured parameter values
            from the user query and chat history based on the parameter documentation.
            
            ---
            ###  INSTRUCTIONS
            
            1. Carefully read the **Parameter Documentation (`params_doc`)**.
               - It defines each parameter, its data type, and its semantic meaning.
            
            2. **STRICT EXTRACTION PRIORITY (Follow in this order):**
               a) **PRIMARY SOURCE – User Query:**
                  - Extract all explicitly mentioned parameter values.
                  - Infer implicit values from context.
                  - Mark values found here as CONFIRMED.
               b) **SECONDARY SOURCE – Chat History:**
                  - Only use chat history for parameters not found in the user query.
                  - Search chronologically and prefer the most recent mention.
               c) **DEFAULT:**
                  - If not found in either source, assign the parameter `null`.
            
            3. **TYPE ENFORCEMENT RULES:**
               - Respect each parameter’s data type as defined in `params_doc`.
                 - Example: if type is *list*, *list[str]*, or *list[int]*, output a JSON array.
                 - Example: if type is *integer*, output a number (no quotes).
                 - Example: if type is *boolean*, output `true` or `false`.
                 - Example: if type is *string*, output a quoted string.
               - Never coerce or alter data types beyond what `params_doc` specifies.
               - Parameter key names in the output JSON must EXACTLY match the names in `params_doc`. Do not rename, abbreviate, or alter them.
             
            4. **OUTPUT REQUIREMENTS:**
               - Output only a valid JSON object.
               - Must include **all parameters** defined in `params_doc`.
               - Use `null` (unquoted) for missing or unknown values.
               - No comments, reasoning, or extra text outside JSON.
            
            ---
            ###  OUTPUT FORMAT
            
            Return JSON strictly in this format:
            
            {{
              "<parameter_name_1>": <value or null>,
              "<parameter_name_2>": <value or null>,
              ...
            }}
            
            ---
            ### CRITICAL RULES
            
            - User query values override chat history.
            - Always include every parameter listed in `params_doc`.
            - Maintain correct JSON syntax (no trailing commas, proper quoting).
            - Preserve parameter names exactly as in `params_doc`.
            - Use null (not "null", "N/A", "", or undefined) for missing values.
            
            ---
            ### EXTRACTION PROCESS
            
            Step 1: Parse `params_doc` → identify parameters and expected types  
            Step 2: Extract values from `user_query` (PRIMARY)  
            Step 3: Fill remaining parameters from `chat_history` (SECONDARY)  
            Step 4: Ensure type correctness and output final JSON  
                    """),
                    ("human",
                    """
            params_doc:
            {params_doc}
            
            user_query:
            {user_query}
            
            chat_history:
            {chat_history}
                    """
        )
    ])


def get_follow_up_questions_prompt():
    return ChatPromptTemplate.from_messages([
        (
            "system",
            """
            You are an expert at generating insightful follow-up questions that naturally extend a conversation.
            
            Your Task:
            Generate follow-up questions that help the user explore the topic further.
            
            Decision Rules (IMPORTANT):
            - If a meaningful Assistant Response is provided, generate follow-up questions based on BOTH:
              - the User Question
              - the Assistant Response
            - If the Assistant Response is missing, empty, or does not contain useful explanatory text,
              generate follow-up questions based ONLY on the User Question.
            
            Question Guidelines:
            - Generate ONLY the questions that are genuinely useful
            - You may generate 1, 2, or 3 questions
            - NEVER generate more than 3 questions
            
            Question Types (use when relevant):
            1. Clarification Question: Address an unclear detail, edge case, or assumption
            2. Depth Question: Explore reasoning, implications, or underlying concepts
            3. Application Question: Focus on practical usage or next steps
            
            Constraints:
            - Maximum 15 words per question
            - One sentence per question
            - No yes/no questions
            - No repetition of stated facts
            - No generic or filler questions
            - Use direct, conversational language
            
            Heading Requirement:
            - Write ONE short, neutral heading summarizing the follow-up intent
            
            IMPORTANT OUTPUT RULES:
            - Return ONLY valid JSON
            - Do NOT include markdown, comments, or explanations
            - Do NOT wrap the output in code fences
            - Questions array length must be between 1 and 3
            
            Required JSON Format:
            {{
              "heading": "Short neutral heading",
              "questions": [
                "Follow-up question 1",
                "Follow-up question 2"
              ]
            }}
            """
                    ),
                    (
                        "human",
                        """
            User Question: {user_question}
            Assistant Response: {assistant_response}
            """
        )
    ])

def get_query_rewrite_prompt():
    return ChatPromptTemplate.from_messages([
        (
            "system",
            """
            You are an expert at rewriting user queries into clear, complete, standalone queries.
            
            Your goal:
            Resolve references and make the query fully self-contained using context.
            
            Decision Logic:
            - If the User Query depends on previous context (e.g., "its", "that", "also"):
              → Rewrite it into a complete standalone query using context
            - If the User Query is already complete:
              → Return it as-is (no unnecessary changes)
            
            Context Usage:
            - Use the provided Context to resolve references (e.g., stock name, entity, topic)
            - If context is missing or unclear, rewrite conservatively without guessing
            
            Rewriting Rules:
            - Preserve original intent exactly
            - Do NOT add new information
            - Do NOT change meaning
            - Replace vague references ("it", "its", "that") with actual entity
            - Keep query natural and concise
            - Avoid over-explaining
            
            OUTPUT RULES (STRICT):
            - Return ONLY valid JSON
            - No markdown, no explanations, no extra text
            - Always return exactly ONE rewritten query
            - The JSON must contain exactly one key: "rewritten_query"
            """
                    ),
                    (
                        "human",
                        """
            User Query: {user_query}
            Context: {context}
            """
        )
    ])
