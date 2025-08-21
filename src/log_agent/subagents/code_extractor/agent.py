from google.adk.agents import LlmAgent

from .tools import url_encoder, get_url, after_agent_callback, before_agent_callback, \
    after_tool_callback, before_tool_callback, fetch_url_from_gitlab
from ..log_filter.models import LogAttribute

code_extractor_agent = LlmAgent(
    name="code_extractor",
    model="gemini-2.5-flash",
    instruction="""
        You are a URL retriever agent. Given a log JSON, do the following:
        1. Parse 'stack_trace' or 'exc_info' fields to extract full .py or .java file paths
            - For Python stack traces: the innermost calls are at the **bottom** (last 3 entries).
            - For Java stack traces: the innermost calls are at the **top** (first 3 entries).
            - If there are too many file paths in the stack trace, select the 3 innermost paths according to the stack trace style.
        2. Extract the project name and branch name
        3. in appname, 
            - Put eco/ as prefix (e.g. carsync-frontend → eco/carsync-frontend)
            - If appname already has eco-, replace - with / (e.g., eco-carsync-frontend → eco/carsync-frontend)
        4. You must call 'fetch_url_from_gitlab' to fetch final code_urls as a result. Do not generate yourself.
        Respond as list of URLs:
        {{ "code_urls" : ["url1", "url2", ...] }} 
        DO NOT include ```json in string
    """,
    input_schema=LogAttribute,
    description="Extracts code urls from GitLab based on log information.",
    tools=[fetch_url_from_gitlab],
    after_agent_callback=after_agent_callback,
    before_agent_callback=before_agent_callback,
    after_tool_callback=after_tool_callback,
    before_tool_callback=before_tool_callback,
    output_key="code_urls"
)
