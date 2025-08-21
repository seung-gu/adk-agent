from langchain.prompts import PromptTemplate, ChatPromptTemplate


keyword_prompt = PromptTemplate(
    input_variables=["messages"],
    template="""
    You are a keyword extraction agent. Given a user input, extract the following information:
    1. Project name (service)
    2. Log level (e.g., error, warning, info)
    3. Time period in hours
    4. Environment (e.g., dev, staging, prod)
    Normalize the environment value as follows:
    - 'prod', 'production', 'real', 'main', 'master', 'live' → 'prod'
    - 'stag', 'stage', 'staging' → 'staging'
    - 'dev', 'development' → 'dev'
    If any are missing, ask for only the missing values.
    Respond with a JSON object in the following Pydantic schema format:
    {{
      "project_name": str,
      "log_level": str,
      "time_period_hours": int,
      "environment": str
    }}
    Extract ALL required fields from the entire conversation history so far.
    Use previous {messages} as context.
    Do NOT re-ask for information already provided earlier.
    If a value is still missing after scanning all prior messages, ask for ONLY the missing value.
    """,
)


summarize_prompt = PromptTemplate(
    input_variables=["log_attributes"],
    template="""
    Your task is to summarize the logs provided.
    
    ## INPUT
    - You will receive logs {log_attributes}.
    
    ## ACTION
    - Show the error messages and their frequencies.
    - Highlight any recurring issues or patterns.
    
    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Output the number of errors and their types so that the user can choose which ones to analyze further.
    - Ask to the user to specify the number of the error entry from the list.
    """,
)

code_retriever_prompt = ChatPromptTemplate.from_messages([
    ("system", """
        You are a URL retriever agent. Given a log JSON, do the following:
        1. Parse 'stack_trace' or 'exc_info' fields to extract full .py or .java file paths
            - For Python stack traces: the innermost calls are at the **bottom** (last 3 entries).
            - For Java stack traces: the innermost calls are at the **top** (first 3 entries).
            - If there are too many file paths in the stack trace, select the 3 innermost paths according to the stack trace style.
        2. Extract the project name and branch name
        3. in appname, 
            - Put eco/ as prefix (e.g. carsync-frontend → eco/carsync-frontend)
            - If appname already has eco-, replace - with / (e.g., eco-carsync-frontend → eco/carsync-frontend)
        4. For repo path, use the 'fetch_code_from_gitlab' tool to fetch urls.
        Respond as list of URLs:
        {{ "code_urls" : [...] }} 
        DO NOT include ```json in string
    """),
    ("human", "{messages}")
])

log_analyze_prompt = ChatPromptTemplate.from_messages([
    ("system", """
        Your task is to analyze the log.
        
        ## INPUT
        - You will receive log 'selected_log' and 'code_urls'.
        
        ## ACTION
        - Please analyze error by getting codes using 'get_code_from_gitlab' tool.
        - Highlight any recurring issues or patterns.
        - Suggest possible causes or next steps if applicable.
        - Output a concise analysis report.
        
        ## OUTPUT
        - Respond with a concise, human-readable summary (not JSON).
        - Keep your answer brief and to the point, but provide enough detail for context.
        - Respond how to modify the code to fix the issue showing before and after by calling 'get_code_from_gitlab'.
        - Do not fucking create before code on your fucking self.
        - Please also add the file path and line number for the code change.
        - Use title (Title: ) and bullet points or short paragraphs for clarity.
        - Avoid unnecessary details or lengthy explanations.
        - Ensure the summary is informative and actionable for developers.
    """),
    ("human", "{messages}")
])