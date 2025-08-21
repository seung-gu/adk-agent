from .subagents.code_analyzer.agent import code_analyzer_agent
from .subagents.log_analyzer.agent import log_analyzer_agent
from .subagents.code_extractor.agent import code_extractor_agent
from .subagents.log_filter.agent import log_filter_agent
from google.adk.agents import SequentialAgent, ParallelAgent


def before_root_agent_callback(callback_context):
    state = callback_context._invocation_context.session.state
    state['interaction_history'] = []
    state.pop('trace', None)
    state.pop('code_urls', None)

# Run log_analyzer_agent and code_analyzer_agent in parallel after log_filter_agent
root_agent = SequentialAgent(
    name="log_agent",
    sub_agents=[
        log_filter_agent,
        ParallelAgent(
            name="log_analysis_parallel",
            sub_agents=[log_analyzer_agent, code_extractor_agent],
            description="Analyzes logs and code context in parallel.",
        ),
        code_analyzer_agent
    ],
    before_agent_callback=before_root_agent_callback,
    description="Extracts key fields from error logs and provides both log and code analysis in parallel.",
)

