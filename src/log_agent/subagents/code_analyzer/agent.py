from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools.agent_tool import AgentTool

from src.log_agent.subagents.code_extractor.agent import code_extractor_agent


code_analyzer_agent = LoopAgent(
    name="code_analyzer",
    max_iterations=5,

    description="Analyzes project code based on error logs and provides code-level insights and suggestions.",
    sub_agents=[code_extractor_agent],
   # output_key="code_analysis_report"
)
"""
    model="gemini-2.0-flash",
    instruction=
    You are a Code Analyzer Agent.
    Your task is to analyze the code context related to the error logs provided in logs.

    ## INPUT
    - You will receive logs (list of log entries and other metadata).
    - You MUST always call the 'code_extractor_agent' with the provided logs.
    - You will receive codes to check from the 'code_extractor_agent'.
    - Do not attempt to answer or summarize directly. Wait for the tool result and only return its output.

    ## ACTION
    - Use the extracted or provided values to call code_extractor_agent.
    - Output a concise analysis report for each log entry, including the code context and recommendations.

    ## OUTPUT
    - Respond with a concise, human-readable summary (not JSON).
    - Keep your answer brief and to the point, but provide enough detail for context (aim for 500-1000 characters).
    - Use bullet points or short paragraphs for clarity.
    - Avoid unnecessary details or lengthy explanations.
    - Only include the most important findings and recommendations.

    ## LOG TO ANALYZE
    {code_snippets}
    ,
    """