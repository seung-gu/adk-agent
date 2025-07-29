import io
import json
from PIL import Image
from dotenv import load_dotenv
from typing_extensions import Literal
from langchain.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langgraph.types import Command
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.prebuilt import create_react_agent

from models import LogAttribute, LogState
from tools import (get_filtered_logs, fetch_code_from_gitlab, get_code_from_gitlab, make_datadog_url,
                   push_issue_in_gitlab)
from prompts import summarize_prompt, keyword_prompt, log_analyze_prompt, code_retriever_prompt


# --- Environment setup and LLM initialization ---
load_dotenv(dotenv_path=".env", override=True)


# --- State definition ---
class AgentState(MessagesState):
    log_state: LogState
    log_attributes: list[LogAttribute]
    selected_log: LogAttribute
    code_urls: list[str]
    codes: list[Document]


def extract_keywords_node(state: AgentState) -> Command[Literal['log_retriever', 'keyword_review']]:
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', temperature=0)
    chain = keyword_prompt | llm
    message: AIMessage = chain.invoke({"messages": state['messages']})
    output_parser = PydanticOutputParser(pydantic_object=LogState)
    try:
        log_state = output_parser.parse(message.content)
        return Command(goto='log_retriever', update={'messages': [message], 'log_state': log_state})
    except Exception as e:
        # If parsing fails, return to the same node to retry
        return Command(goto='keyword_review', update={'messages': [message]})

def keyword_review(state: AgentState) -> Command:
    """
    keyword_review node requests human review.
    """
    user_input = input("User: ")
    # Append input to messages and resume to extract_keywords
    return Command(
        goto='extract_keywords',
        update={'messages': state['messages'] + [HumanMessage(content=user_input)]}
    )

def log_retriever_node(state: AgentState) -> Command[Literal[END, 'api_retriever', 'log_review']]:
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', temperature=0)
    chain = summarize_prompt | llm | StrOutputParser()
    logs = get_filtered_logs(**state['log_state'].model_dump())
    response = chain.invoke({'log_attributes': logs})
    if len(logs) == 0:
        return Command(goto=END, update={"messages": [HumanMessage("No logs found for the given criteria.")]})
    elif len(logs) == 1:
        # If only one log is found, go directly to log_analyzer
        return Command(goto='api_retriever', update={"selected_log": logs[0]})
    else:
        return Command(
            goto='log_review',
            update={"messages": state['messages'] + [AIMessage(content=response)], "log_attributes": logs}
        )

def log_review(state: AgentState) -> Command:
    user_input = input("User: ")
    try:
        selected_log = state['log_attributes'][int(user_input)-1]
        return Command(
            goto='api_retriever',
            update={'messages': state['messages'] + [HumanMessage(content=user_input)], 'selected_log': selected_log}
        )
    except (IndexError, ValueError):
        print("Invalid selection. Please try again.")
        return Command(goto='log_review', update={'messages': state['messages']})

def api_retriever_node(state: AgentState) -> AgentState:
    log = state['selected_log']
    response = create_react_agent(
        model='openai:gpt-4.1', tools=[fetch_code_from_gitlab], prompt=code_retriever_prompt
    ).invoke({"messages": [HumanMessage(log.model_dump_json())]})
    messages = response['messages']
    ai_message: AIMessage = messages[-1]  # from react agent, list of messages returned
    try:
        code_urls = json.loads(ai_message.content)
    except json.JSONDecodeError:
        print(f"Error decoding JSON: {ai_message.content}")
        code_urls = []
    return {"messages": messages, "code_urls": code_urls.get('code_urls', [])}

def analyze_logs_node(state: AgentState) -> AgentState:
    log = state.get('selected_log')
    code_urls = state.get('code_urls', [])
    response = create_react_agent(
        model='google_genai:gemini-2.0-flash', tools=[get_code_from_gitlab], prompt=log_analyze_prompt
    ).invoke({"messages": [HumanMessage([{"selected_log": log, "code_urls": code_urls}])]})
    return {"messages": response['messages']}

def create_issue_node(state: AgentState) -> AgentState:
    """
    This node is a placeholder for creating an issue in gitlab issues.
    It can be implemented later based on the specific requirements.
    """
    content = state['messages'][-1].content
    try:
        title = content.split('Title:')[1].split('\n')[0]
        title = "[🤖 Auto-generated Issue] " + title.strip()
    except IndexError:
        title = "[🤖 Auto-generated Issue] "

    print(f"Do you want to create an issue in GitLab based on the analyzed logs? (Title: {title}) (y)")

    user_input = input("User: ")
    if user_input.lower() == 'y':
        datadog_log_url = make_datadog_url(**state['log_state'].model_dump())
        gitlab_code_api = state.get('code_urls', [])
        if gitlab_code_api:
            project_api = gitlab_code_api[0].split('/repository')[0]
            response = push_issue_in_gitlab(title, content, project_api, datadog_log_url)
            if response.status_code == 201:
                print("Issue created successfully in GitLab.")
            else:
                print("Failed to create issue in GitLab.")
    return state


# --- Graph construction ---
graph = StateGraph(AgentState)
graph.add_node("extract_keywords", extract_keywords_node)
graph.add_node("log_retriever", log_retriever_node)
graph.add_node(keyword_review)
graph.add_node(log_review)
graph.add_node("api_retriever", api_retriever_node)
graph.add_node("analyze_logs", analyze_logs_node)
graph.add_node("create_issue", create_issue_node)

graph.add_edge(START, 'extract_keywords')
graph.add_edge("keyword_review", "extract_keywords")
graph.add_edge("log_review", "api_retriever")
graph.add_edge("api_retriever", "analyze_logs")
graph.add_edge("analyze_logs", "create_issue")
graph.set_finish_point("create_issue")

sequence_graph = graph.compile()


# --- Execution example ---
if __name__ == '__main__':
    img_bytes = sequence_graph.get_graph().draw_mermaid_png()
    img = Image.open(io.BytesIO(img_bytes))
    img.show()

    query = "please get *document* project log for the last days in prod env for error level"

    for chunk in sequence_graph.stream({'messages': [HumanMessage("")]}, stream_mode='values'):
        chunk['messages'][-1].pretty_print()
