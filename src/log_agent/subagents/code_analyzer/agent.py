from google.adk.agents.llm_agent import LlmAgent

from .tools import get_code_snippet_from_gitlab

GEMINI_MODEL = "gemini-2.0-flash"

code_analyzer_agent = LlmAgent(
    name="CodeAnalyzerAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Code Analyzer Agent.
    Your task is to analyze the code context related to the error logs provided in filtered_logs.
    
    ## INPUT
    - You will receive filtered_logs (list of log entries, each with filename, line number, message, and other metadata).
    - You have access to the get_code_snippet_from_gitlab tool to fetch code from the repository.
    
    ## ACTION
    - For each log entry in filtered_logs:
        1. If the log contains a non-empty stack_trace, extract the file path and line number from the stack_trace.
        2. Use get_code_snippet_from_gitlab to retrieve the code snippet for the extracted file path and line number.
        3. Analyze the code to explain the possible cause of the error or issue described in the log message.
        4. Suggest improvements or fixes for the problematic code if possible.
    - Output a concise analysis report for each log entry, including the code context and recommendations.
    
    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Keep your answer brief and to the point, but provide enough detail for context (aim for 500-1000 characters).
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Only include the most important findings and recommendations.
    
    ## CODE PART TO INVESTIGATE
    {filtered_logs}
    """,
    description="Analyzes project code based on error logs and provides code-level insights and suggestions.",
    output_key="code_analysis_report",
)
