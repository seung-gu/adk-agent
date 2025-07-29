from langchain.prompts import PromptTemplate

log_filter_prompt = PromptTemplate(
    input_variables=["user_input"],
    template= """
    You are a Log Filter Agent.
    Your job is to extract and return the following information in structured JSON format.

    ## INPUT REQUIREMENTS
    - If the user provides as {user_input} in a sentence or description, extract relevant keywords as output for:
      1. Project name (service)
      2. Log level (e.g., error, warning, info)
      3. Time period in hours
      4. Environment (e.g., dev, staging, prod)

    - If any are missing, ask for only the missing values.

    ## ENVIRONMENT NORMALIZATION
    - The 'environment' field can have various user expressions.
    - Normalize the environment value as follows:
        * 'prod', 'production', 'real', 'main', 'master', 'live' → 'prod'
        * 'stag', 'stage', 'staging' → 'staging'
        * 'dev', 'development' → 'dev'
    - If the user's input is similar to these (e.g., 'prod1', 'prod-env'), treat as 'prod'.

    ## Output Format (strict)
    Return only a JSON object in the following Pydantic schema format with no explanation or extra text:

    Please return the result as raw JSON, without markdown fences.
    Example output :
    {{
      "project_name": str,
      "log_level": str,
      "time_period_hours": int,
      "environment": str
    }}
    If any are missing, output ONLY a short clarification question to the user (no JSON, no explanation, no extra text).
    """
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

log_analyzer_withcode_prompt = PromptTemplate(
    input_variables=["selected_log", "code_urls"],
    template="""
    You are a Log Analyzer Agent.
    Your task is to analyze the log.
    
    ## INPUT
    - You will receive log {selected_log} and {code_urls}.
    
    ## ACTION
    - Summarize the main error types and their frequencies.
    - Please analyze error types with {codes}. CHECK ONLY CODES THAT ARE PROVIDED.
    - Highlight any recurring issues or patterns.
    - Suggest possible causes or next steps if applicable.
    - Output a concise analysis report.
    
    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Keep your answer brief and to the point, but provide enough detail for context.
    - Respond how to modify the code to fix the issue.
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Only include the most important findings and recommendations.
    - Ensure the summary is informative and actionable for developers.
    
    """,
)