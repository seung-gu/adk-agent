from google.adk.agents.llm_agent import LlmAgent
from pydantic import BaseModel, Field


class ErrorDetectContent(BaseModel):
    timestamp: str = Field(description="The timestamp when the error occurred, in ISO 8601 format.")
    message: str = Field(description="The main content of the error message, providing details about the issue.")
    level: str = Field(description="The severity level of the error (e.g., 'error', 'warning', 'info').")
    topic_name: str = Field(description="The name of the topic or service where the error occurred.")
    filename: str = Field(description="The name of the file where the error occurred.")
    document_id: str = Field(description="The unique identifier of the document associated with the error.")

GEMINI_MODEL = "gemini-2.0-flash"

log_analyzer_agent = LlmAgent(
    name="LogAnalyzerAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Log Analyzer Agent.
    Your task is to analyze the filtered_logs provided by the Log Filter Agent.
    
    ## INPUT
    - You will receive filtered_logs (list of log entries).
    
    ## ACTION
    - Summarize the main error types and their frequencies.
    - Highlight any recurring issues or patterns.
    - Suggest possible causes or next steps if applicable.
    - Output a concise analysis report.
    
    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Keep your answer brief and to the point, but provide enough detail for context (aim for 500-1000 characters).
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Only include the most important findings and recommendations.
    - Ensure the summary is informative and actionable for developers.
    
    ## LOGS TO REVIEW
    {filtered_logs}
    """,
    description="Analyzes filtered logs and provides a summary of errors and patterns.",
    output_key="analysis_report",
)
