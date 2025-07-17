from google.adk.agents import LlmAgent


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
    - Keep your answer brief and to the point, but provide enough detail for context (aim for 500-1000 characters).
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Only include the most important findings and recommendations.

    ## LOG TO ANALYZE
    {log_analysis_report}
    
    ## CODE TO CHECK
    {code_snippets}
    """,

    output_key="code_analysis_report"
)
