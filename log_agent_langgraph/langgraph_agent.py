import io
from pyexpat.errors import messages
from tabnanny import check

from PIL import Image
from anyio.lowlevel import checkpoint
from dotenv import load_dotenv
import os
import json
import requests
from langchain.output_parsers import PydanticOutputParser
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt, Interrupt
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain.agents import tool

from models import LogAttribute, LogState
from tools import get_filtered_logs, try_gitlab_api
from prompts import summarize_prompt

from langchain_core.documents import Document
from typing_extensions import TypedDict, Literal

# --- 환경 설정 및 LLM 초기화 ---
load_dotenv(dotenv_path=".env", override=True)
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', temperature=0)

# --- 상태 정의 ---
class AgentState(MessagesState):
    log_state: LogState
    log_attributes: list[LogAttribute]
    selected_log: LogAttribute
    code_urls: list[str]
    codes: list[Document]


# --- GitLab API Tool 정의 ---
@tool
def fetch_code_from_gitlab(appname: str, file_path: str, branch: str) -> dict:
    """GitLab에서 특정 경로의 소스코드를 조회한다.
    Args:
        appname (str): GitLab 프로젝트 이름 (from appname in log).
        file_path (str): 파일 경로 (예: 'de/carsync/fleet/core/listener/VehicleEventListener.java').
        branch (str): 브랜치 이름 (예: 'master' 또는 'develop').
    """
    if file_path.endswith('.java') or file_path.endswith('.py'):
        base, ext = file_path.rsplit('.', 1)
    file_path = base.replace('.', '/') + '.' + ext
    tokens = file_path.split('/')
    prefix = f"{tokens[3]}/src/main/java/" if len(tokens) >= 4 else ''

    url = try_gitlab_api(f"eco/{appname}", prefix + file_path, branch)
    return url

@tool
def get_code_from_gitlab(code_url: str) -> str|None:
    """GitLab API를 호출하여 코드를 가져오는 함수입니다.
    Args:
        code_url (str): GitLab API URL.
    Returns:
        str: 가져온 코드의 내용.
    """
    private_token = os.environ.get("GITLAB_TOKEN")
    if not private_token:
        print("GITLAB_TOKEN is not set in the environment.")
        return None
    headers = {"PRIVATE-TOKEN": private_token}
    try:
        response = requests.get(code_url, headers=headers, timeout=3)
        return response.content.decode('utf-8') if response.status_code == 200 else None
    except requests.RequestException as e:
        print(f"Attempting: {code_url} -> Status: FAILED ({e})")
        return None


@tool
def keyword_extractor(message: HumanMessage) -> MessagesState:
    """
    Extract keywords from user input to create a LogState object.
    Normalize the environment value as follows:
        * 'prod', 'production', 'real', 'main', 'master', 'live' → 'prod'
        * 'stag', 'stage', 'staging' → 'staging'
        * 'dev', 'development' → 'dev'
    Args:
        message (HumanMessage): The input message from the user.
    Returns:
        LogState: A structured object containing extracted keywords.
    """
    print("[DEBUG] keyword_extractor input type:", type(message))
    print("[DEBUG] keyword_extractor input:", message)
    if hasattr(message, 'content'):
        print("[DEBUG] keyword_extractor message.content:", message.content)
    output_parser = PydanticOutputParser(pydantic_object=LogState)
    chain = llm | output_parser
    response: LogState = chain.invoke({'user_input': message.content})
    print("[DEBUG] keyword_extractor output LogState:", response)
    return {'messages': [response]}

@tool
def log_filter(response: LogState) -> list[LogAttribute]:
    """
    Retrieve logs from Datadog filtered by project_name, error_level, time_period_hours, and environment.
    Returns list of LogAttribute for downstream agents.
    Args:
        response: LogState containing the filter criteria
    Returns:
        logs: list[LogAttribute] Contains the list of filtered logs
    """
    print("[DEBUG] log_filter input type:", type(response))
    print("[DEBUG] log_filter input:", response)
    logs: list[LogAttribute] = get_filtered_logs(**response.model_dump())  # tools
    print("[DEBUG] log_filter output logs:", logs)
    return logs


def log_fetcher_node(state: AgentState) -> AgentState:
    """
    에이전트 함수는 주어진 상태에서 메시지를 가져와
    LLM과 도구를 사용하여 응답 메시지를 생성합니다.

    Args:
        state (MessagesState): 메시지 상태를 포함하는 state.

    Returns:
        MessagesState: 응답 메시지를 포함하는 새로운 state.
    """
    messages = state['messages']
    response = log_llm_with_tools.invoke(messages)

    return {'messages': [response]}


log_llm_with_tools = llm.bind_tools([keyword_extractor, log_filter])
log_tool_node = ToolNode([keyword_extractor, log_filter])

keyword_agent = create_react_agent(
    model='gpt-4o',
    tools=[keyword_extractor],
    prompt=ChatPromptTemplate.from_messages([
        ("system", """
        You are a keyword extraction agent. Given a user input, extract the following information:
        1. Project name (service)
        2. Log level (e.g., error, warning, info)
        3. Time period in hours
        4. Environment (e.g., dev, staging, prod)
        Normalize the environment value as follows:
        - 'prod', 'production', 'real', 'main', 'master', 'live' → 'prod'
        - 'stag', 'stage', 'staging' → 'staging'
        - 'dev', 'development' → 'dev'
        If any are missing, ask for only the missing values.
        Respond with a JSON object in the following Pydantic schema format:
        {{
          "project_name": str,
          "log_level": str,
          "time_period_hours": int,
          "environment": str
        }}
        Extract ALL required fields from the entire conversation history so far.
        Use previous messages as context.
        Do NOT re-ask for information already provided earlier.
        If a value is still missing after scanning all prior messages, ask for ONLY the missing value.
        """),
        ("human", "{messages}")
    ])
)

def should_continue_to_code(state: AgentState) -> Literal['log_tools', 'log_analyzer']:
    """
    주어진 메시지 상태를 기반으로 에이전트가 계속 진행할지 여부를 결정합니다.

    Args:
        state (MessagesState): `state`를 포함하는 객체.

    Returns:
        Literal['tools', END]: 도구를 사용해야 하면 `tools`를 리턴하고,
        답변할 준비가 되었다면 END를 반환해서 프로세스를 종료합니다.
    """
    # 상태에서 메시지를 추출합니다.
    messages = state['messages']

    # 마지막 AI 메시지를 가져옵니다.
    last_ai_message = messages[-1]

    # 마지막 AI 메시지가 도구 호출을 포함하고 있는지 확인합니다.
    if last_ai_message.tool_calls:
        return 'log_tools'

    return 'log_analyzer'

# --- React Agent 프롬프트 정의 ---
code_retriever_agent = create_react_agent(
    model='gpt-4o',
    tools=[fetch_code_from_gitlab],
    prompt=ChatPromptTemplate.from_messages([
        ("system", """
        You are a code retriever agent. Given a log JSON, do the following:
        1. Parse 'stack_trace' or 'exc_info' fields to extract full .py or .java file paths
        2. Extract the project name and branch name
        3. For repo path, use the 'fetch_code_from_gitlab' tool to fetch source code.
        Respond as list of URLs:
        {{ "code_urls" : [...] }} 
        DO NOT include ```json in string
    """),
        ("human", "{messages}")
    ])
)

analyze_logs_agent = create_react_agent(
    model='gpt-4o',
    tools=[get_code_from_gitlab],
    prompt=ChatPromptTemplate.from_messages([
        ("system", """
        Your task is to analyze the log.
        
        ## INPUT
        - You will receive log 'selected_log' and 'code_urls'.
        
        ## ACTION
        - Please analyze error by getting codes using 'get_code_from_gitlab' tool.
        - Highlight any recurring issues or patterns.
        - Suggest possible causes or next steps if applicable.
        - Output a concise analysis report.
        
        ## OUTPUT
        - Respond with a concise, human-readable summary (not JSON).
        - Keep your answer brief and to the point, but provide enough detail for context.
        - Respond how to modify the code to fix the issue showing before and after.
        - Please also add the file path and line number for the code change.
        - Please update the code only if you can fix the issue and if multiple code URLs are provided, check all of them.
        - Use bullet points or short paragraphs for clarity.
        - Avoid unnecessary details or lengthy explanations.
        - Only include the most important findings and recommendations.
        - Ensure the summary is informative and actionable for developers.
        
        """),
        ("human", "{messages}")
    ])
)

def extract_keywords_node(state: AgentState) -> Command[Literal['log_retriever', 'keyword_review']]:
    response = keyword_agent.invoke({"messages": state['messages']})
    messages = response['messages']
    output_parser = PydanticOutputParser(pydantic_object=LogState)
    try:
        log_state = output_parser.parse(messages[-1].content)
        return Command(goto='log_retriever', update={'messages': messages, 'log_state': log_state})
    except Exception as e:
        # If parsing fails, return to the same node to retry
        return Command(goto='keyword_review', update={'messages': messages})

def keyword_review(state: AgentState) -> Command:
    """
    keyword_review node는 LLM의 도구 호출에 대해 사람의 검토를 요청합니다.
    Args:
        state (AgentState): 메시지 기록을 포함하는 state.
    Returns:
        Command: 다음 node로 이동하기 위한 Command를 반환합니다.
    """
    user_input = input("User: ")
    # 입력을 메시지에 append 후, extract_keywords로 resume
    return Command(
        goto='extract_keywords',  # 다시 extract_keywords_node로
        update={
            'messages': state['messages'] + [HumanMessage(content=user_input)]
        }
    )
# TODO: log_retriever랑 review랑 합쳐서 agent로 만들기? prompt 만들기
def log_retriever_node(state: AgentState) -> Command[Literal[END, 'api_retriever', 'log_review']]:
    chain = summarize_prompt | llm | StrOutputParser()
    logs = get_filtered_logs(**state['log_state'].model_dump())
    response = chain.invoke({'log_attributes': logs})

    if len(logs) == 0:
        return Command(END, {"messages": [HumanMessage("No logs found for the given criteria.")]})
    elif len(logs) == 1:
        # If only one log is found, go directly to log_analyzer
        return Command(goto='api_retriever', update={"selected_log": logs[0]})
    else:
        return Command(goto='log_review', update={
            "messages": state['messages'] + [AIMessage(content=response)],
            "log_attributes": logs}
                       )

def log_review(state: AgentState) -> Command:
    user_input = input("User: ")
    try:
        selected_log = state['log_attributes'][int(user_input)-1]
        return Command(
            goto='api_retriever',  # 다시 extract_keywords_node로
            update={
                'messages': state['messages'] + [HumanMessage(content=user_input)],
                'selected_log': selected_log
            }
        )
    except (IndexError, ValueError):
        print("Invalid selection. Please try again.")
        return Command(goto='log_review', update={'messages': state['messages']})

def api_retriever_node(state: AgentState) -> AgentState:
    log = state['selected_log']
    response = code_retriever_agent.invoke({"messages": [HumanMessage(log.model_dump_json())]})
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
    response = analyze_logs_agent.invoke({"messages": [HumanMessage([{"selected_log": log, "code_urls": code_urls}])]})
    return {"messages": response['messages']}


# --- 그래프 구성 ---
graph = StateGraph(AgentState)
graph.add_node("extract_keywords", extract_keywords_node)
graph.add_node("log_retriever", log_retriever_node)
graph.add_node(keyword_review)
graph.add_node(log_review)
graph.add_node("api_retriever", api_retriever_node)
graph.add_node("analyze_logs", analyze_logs_node)

graph.add_edge(START, 'extract_keywords')
graph.add_edge("keyword_review", "extract_keywords")
graph.add_edge("log_review", "api_retriever")
graph.add_edge("api_retriever", "analyze_logs")
graph.set_finish_point("analyze_logs")

sequence_graph = graph.compile()


# --- 실행 예시 ---
if __name__ == '__main__':
    try:
        img_bytes = sequence_graph.get_graph().draw_mermaid_png()
        img = Image.open(io.BytesIO(img_bytes))
        img.show()
    except ImportError:
        print("Mermaid 다이어그램 생략")

    query = "please get *document* project log for the last days in prod env for error level"

    for chunk in sequence_graph.stream({'messages': [HumanMessage("")]}, stream_mode='values'):
        chunk['messages'][-1].pretty_print()
