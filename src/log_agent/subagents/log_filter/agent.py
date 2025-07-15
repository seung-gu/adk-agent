"""
Log Filter Agent

This agent receives project name, error level, and time period, then returns filtered logs from Datadog.
"""
from google.adk.agents.llm_agent import LlmAgent
from .tools import get_filtered_logs
from .models import LogFilterInputSchema


GEMINI_MODEL = "gemini-2.0-flash"


log_filter_agent = LlmAgent(
    name="LogFilterAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Log Filter Agent.
    Your task is to help the user retrieve logs from Datadog.
    
    ## INPUT REQUIREMENTS
    - If the user provides a sentence or description, extract relevant keywords for:
      1. Project name (service)
      2. Error level (e.g., error, warning, info)
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
    
    ## ACTION
    - Use the extracted or provided values to call get_filtered_logs(project_name, error_level, time_period_hours, environment).
    - If there are more than 5 logs, return the logs with the top 5 most frequent unique messages (no duplicate messages).
    - Do not add explanations or formatting.
    """,
    input_schema=LogFilterInputSchema,
    description="Retrieves logs from Datadog based on project, error level, time period, and environment. Returns up to 5 logs if too many are found.",
    tools=[get_filtered_logs],
    output_key="logs",  # The key where the filtered logs will be stored in the output
)
