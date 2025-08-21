from google.adk.agents import LlmAgent

from src.log_agent.subagents.code_analyzer.tools import load_code_snippets

code_analyzer_agent = LlmAgent(
    name="code_analyzer",
    model="gemini-2.0-flash",
    description="Analyzes project code based on error logs and provides code-level insights and suggestions.",
    instruction="""
    You are a Code Analyzer Agent.
    Your task is to analyze the code context related to the error logs provided in logs.

    ## INPUT
    - You will receive codes.
    - Do not attempt to answer or summarize directly. Wait for the result of log_analysis_report and code_snippets.

    ## ACTION
    - Output a concise analysis report for each log entry, including the code context and recommendations.

    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Use bullet points or short paragraphs for clarity.
    - Respond how to modify the code to fix the issue showing before and after.
    - Please also add the file path and line number for the code change.
    - Only include the most important findings and recommendations.

    ## LOG TO ANALYZE
    {log_analysis_report}
    
    ## CODE TO CHECK
    call api using load_code_snippets tool that has only 200 HTTP status code and load the codes.
    {code_urls}
    
    after return code_analyzer_report, clear all logs. It shouldn't be used in next time.
    
    ## Return language : English
    """,

    tools=[load_code_snippets],
    output_key="code_analysis_report"
)
