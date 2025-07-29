import io
from typing import List

from pydantic import BaseModel
from typing_extensions import TypedDict
from PIL import Image
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, END, StateGraph

from tools import get_filtered_logs, try_gitlab_api
from prompts import log_filter_prompt, log_analyzer_withcode_prompt, log_analyzer_prompt
from models import LogAttribute, LogState
from langchain.output_parsers import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field


load_dotenv(dotenv_path=".env", override=True)

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')

# --- 상태 정의 ---
# 각 단계의 결과를 저장하는 중앙 데이터 저장소입니다.
class AgentState(TypedDict):
    user_input: str
    log_state: LogState
    log_attributes: List[LogAttribute]
    selected_log: LogAttribute  # 사용자가 선택한 로그
    analysis_result: str
    code_urls: List[str]
    codes: list[Document]  # 코드 내용도 저장

# --- Pydantic 파서 ---
# LLM의 출력을 LogState 객체로 변환합니다.
output_parser = PydanticOutputParser(pydantic_object=LogState)


# --- Code Retriever를 위한 새로운 Pydantic 모델 및 프롬프트 ---
class ExtractedCodeInfo(BaseModel):
    """LLM이 로그에서 추출할 구조화된 데이터 모델"""
    project_name: str = Field(description="The name of the project, like 'eco/document' or 'carsync-service'.")
    file_path: str = Field(description="The full path to the file, like 'de/carsync/fleet/core/listener/VehicleEventListener.java'.")
    branch: str = Field(description="The name of the git branch, like 'master' or 'develop'.")

# LLM에게 정보 추출만 요청하는 단순하고 짧은 프롬프트
code_extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at extracting structured information from log entries. From the user's log, extract the project name, file path, and branch for files ending in .java or .py. The project name is usually in the 'appname' field."),
    ("human", "Log entry:\n\n{log_json}")
])

extraction_parser = PydanticOutputParser(pydantic_object=ExtractedCodeInfo)


# --- 그래프 노드(함수) 정의 ---

def extract_keywords_node(state: AgentState) -> dict:
    """사용자 입력에서 키워드를 추출합니다."""
    print("--- 1. 키워드 추출 시작 ---")
    user_input = state['user_input']

    # 프롬프트 + LLM + 출력 파서를 연결하여 체인을 만듭니다.
    chain = log_filter_prompt | llm | output_parser
    log_state_result = chain.invoke({'user_input': user_input})

    print(f"추출된 키워드: {log_state_result}")
    return {"log_state": log_state_result}

def filter_logs_node(state: AgentState) -> dict:
    """추출된 키워드로 로그를 필터링합니다."""
    print("--- 2. 로그 필터링 시작 ---")
    log_state = state['log_state']

    # tools.py의 함수를 직접 호출합니다.
    logs = get_filtered_logs(**log_state.model_dump())

    print(f"필터링된 로그 수: {len(logs)}")
    return {"log_attributes": logs}

def log_analyzer_node(state: AgentState) -> dict:
    """필터링된 로그들을 요약/분석합니다."""
    print("--- 3. 로그 분석 시작 ---")
    log_attributes = state['log_attributes']
    chain = log_analyzer_prompt | llm | StrOutputParser()
    analysis_result = chain.invoke({'log_attributes': log_attributes})
    print(f"로그 분석 결과: {analysis_result}")
    return {"analysis_result": analysis_result}

def select_log_node(state: AgentState) -> dict:
    """사용자가 하나의 로그를 선택하도록 합니다."""
    print("--- 4. 로그 선택 단계 ---")
    log_attributes = state['log_attributes']
    # 실제 환경에서는 사용자 인터랙션이 필요함. 여기서는 첫 번째 로그를 선택하는 예시.
    selected_log = log_attributes[0] if log_attributes else None
    print(f"선택된 로그: {selected_log}")
    return {"selected_log": selected_log}

def code_retriever_node(state: AgentState) -> dict:
    """
    선택된 로그(selected_log)에 대해 stack_trace(또는 exc_info)에서 각 라인의 전체 파일 경로(패키지+클래스+파일명)를 LLM으로 추출하고,
    각 경로에 대해 prefix+eco/프로젝트, prefix+원본프로젝트 순서로 모두 시도.
    모든 성공한 URL과 코드 내용을 리스트로 반환.
    """
    import ast
    selected_log = state.get('selected_log', None)
    if not selected_log:
        return {"code_urls": [], "codes": []}

    # LLM 프롬프트: stack_trace에서 전체 파일 경로만 추출
    from langchain_core.prompts import ChatPromptTemplate
    from langchain.output_parsers import CommaSeparatedListOutputParser
    file_path_parser = CommaSeparatedListOutputParser()
    file_path_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at extracting full file paths from stack traces. For each line in the stack trace, extract the full file path (including package, class, and filename) for all .java or .py files. Return only a comma-separated list of full file paths. No explanation, no extra text."),
        ("human", "Stack trace:\n{stack_trace}")
    ])

    stack_lines = []
    for attr in ['stack_trace', 'exc_info']:
        val = getattr(selected_log, attr, None)
        if val:
            if isinstance(val, str):
                try:
                    stack_lines.extend(ast.literal_eval(val))
                except Exception:
                    stack_lines.append(val)
            elif isinstance(val, list):
                stack_lines.extend(val)
    if not stack_lines:
        return {"code_urls": [], "codes": []}
    stack_text = '\n'.join(stack_lines)
    chain = file_path_prompt | llm | file_path_parser
    file_paths = chain.invoke({"stack_trace": stack_text})
    file_paths = [fp.strip() for fp in file_paths if fp.strip()]
    if not file_paths:
        return {"code_urls": [], "codes": []}
    extracted_info = code_extraction_prompt | llm | extraction_parser
    info = extracted_info.invoke({"log_json": selected_log.model_dump_json()})
    project = info.project_name
    branch = info.branch
    log_code_urls = []
    codes = []
    for file_path in file_paths:
        if file_path.endswith('.java') or file_path.endswith('.py'):
            base, ext = file_path.rsplit('.', 1)
            file_path = base.replace('.', '/') + '.' + ext
        tokens = file_path.split('/')
        prefix = f"{tokens[3]}/src/main/java/" if len(tokens) >= 4 else ''
        prefixed_file_path = prefix + file_path if prefix else file_path
        url1 = try_gitlab_api(f"eco/{project}", prefixed_file_path, branch)
        if url1 and url1['url'] not in log_code_urls:
            log_code_urls.append(url1['url'])
            codes.append(url1['code'])
            continue
        url2 = try_gitlab_api(project, prefixed_file_path, branch)
        if url2 and url2['url'] not in log_code_urls:
            log_code_urls.append(url2['url'])
            codes.append(url2['code'])
    selected_log.code_urls = log_code_urls
    return {"code_urls": log_code_urls, "codes": codes, "selected_log": selected_log}

def analyze_logs_node(state: AgentState) -> dict:
    """선택된 로그와 코드 URL, 코드 내용을 분석합니다."""
    print("--- 5. 로그 분석 시작 ---")
    selected_log = state.get('selected_log', None)
    code_urls = state.get('code_urls', [])
    codes = state.get('codes', [])
    if not selected_log:
        analysis_result = "분석할 로그가 없습니다."
    else:
        chain = log_analyzer_withcode_prompt | llm | StrOutputParser()
        analysis_result = chain.invoke({'log_attributes': [selected_log], 'code_urls': code_urls, 'codes': codes})
    print(f"분석 결과: {analysis_result}")
    return {"analysis_result": analysis_result}


# --- 그래프 구성 ---
graph_builder = StateGraph(AgentState)

# 노드를 그래프에 추가합니다.
graph_builder.add_node('extract_keywords', extract_keywords_node)
graph_builder.add_node('filter_logs', filter_logs_node)
graph_builder.add_node('log_analyzer', log_analyzer_node)
graph_builder.add_node('select_log', select_log_node)
graph_builder.add_node('code_retriever', code_retriever_node)
graph_builder.add_node('analyze_logs', analyze_logs_node)

# 노드 간의 실행 순서를 정의합니다.
graph_builder.add_edge(START, 'extract_keywords')
graph_builder.add_edge('extract_keywords', 'filter_logs')
graph_builder.add_edge('filter_logs', 'log_analyzer')
graph_builder.add_edge('log_analyzer', 'select_log')
graph_builder.add_edge('select_log', 'code_retriever')
graph_builder.add_edge('code_retriever', 'analyze_logs')
graph_builder.add_edge('analyze_logs', END)

# 그래프를 실행 가능한 앱으로 컴파일합니다.
sequence_graph = graph_builder.compile()

# --- 그래프 실행 ---
try:
    img_bytes = sequence_graph.get_graph().draw_mermaid_png()
    img = Image.open(io.BytesIO(img_bytes))
    img.show()
except ImportError:
    print("Mermaid 다이어그램을 생성하려면 'pygraphviz'와 'matplotlib'을 설치해야 합니다.")


initial_state = {'user_input': 'please get *document* project service for the last 7 days in prod env with error level'}
final_state = sequence_graph.invoke(initial_state)

print("\n--- 최종 결과 ---")
print("추출된 코드 URL:")
print(final_state.get('code_urls', []))
print("\n분석 결과:")
print(final_state.get('analysis_result', '분석 결과가 없습니다.'))
