"""
Log Filter Agent

This agent receives project name, error level, and time period, then returns filtered logs from Datadog.
"""

from google.adk.agents.llm_agent import LlmAgent
from .tools import get_filtered_logs

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
    - If any required information is missing, ask the user for it.
    
    ## ACTION
    - Use the extracted or provided values to call get_filtered_logs(project_name, error_level, time_period_hours, environment).
    - If the number of filtered logs is more than 5, return only the 5 most relevant or recent logs.
    - Return ONLY the filtered logs.
    - Do not add explanations or formatting.
    """,

    description="Retrieves filtered logs from Datadog based on project, error level, time period, and environment. Returns up to 5 logs if too many are found.",
    tools=[get_filtered_logs],
    output_key="filtered_logs",
)
