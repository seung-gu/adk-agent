from google.adk.agents.llm_agent import LlmAgent

from .tools import analyze_code_snippets


code_extractor_agent = LlmAgent(
    name="code_extractor",
    model="gemini-2.0-flash",
    instruction="""
    You are a Code Extractor Agent.
    Your task is to extract code snippets from GitLab using the provided log information.
    
    ## INPUT
    - You MUST always call the 'analyze_code_snippets' tool with the provided logs. 
    - Do not attempt to answer or summarize directly. Wait for the tool result and only return its output.

    ## OUTPUT
    - Return the relevant code snippet for each log entry.
    - Keep your answer concise and focused on the code context.
    
    ## LOG TO ANALYZE
    {logs}
    """,

    description="Extracts code snippets from GitLab based on log information.",
    tools=[analyze_code_snippets],
)
