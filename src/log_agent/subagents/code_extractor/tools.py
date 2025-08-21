import os
import requests
from urllib.parse import quote

from src.log_agent.subagents.code_extractor.models import CodeUrl, CodeSnippets
from src.log_agent.subagents.log_filter.models import LogAttribute


def try_gitlab_api(project: str, file_path: str, branch: str):
    """
    Construct and validate a GitLab API URL for the given project, file path, and branch.
    Returns a dict with 'url' and 'code' if successful, otherwise None.
    """
    # Construct the GitLab API URL for raw file content
    base_url = "https://git.cardev.de/api/v4/projects"
    # Encode project path for API (replace / with %2F)
    project_encoded = quote(project, safe='')
    file_path_encoded = quote(file_path, safe='')
    url = f"{base_url}/{project_encoded}/repository/files/{file_path_encoded}/raw?ref={branch}"
    private_token = os.environ.get("GITLAB_TOKEN")
    headers = {"PRIVATE-TOKEN": private_token} if private_token else {}
    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            return url
        else:
            print(f"Failed to fetch {url}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def fetch_url_from_gitlab(appname: str, file_path: str, branch: str) -> dict:
    """Fetch source code urls from GitLab for a specific path.
    Args:
        appname (str): GitLab project name (from appname in log).
        file_path (str): File path (e.g., 'de/carsync/fleet/core/listener/VehicleEventListener.java').
        branch (str): Branch name (e.g., 'master' or 'develop').
    """
    if file_path.endswith('.java') or file_path.endswith('.py'):
        base, ext = file_path.split('.', 1)
        file_path = base.replace('.', '/') + '.' + ext
    if file_path.endswith('.java'):
        tokens = file_path.split('/')
        file_path = f"{tokens[3]}/src/main/java/" + file_path if len(tokens) >= 4 else ''

    url = try_gitlab_api(appname, file_path, branch)
    return url


def get_url(api_url: str) -> requests.status_codes:
    """
    Make an API call to the given URL with optional headers.
    Returns the response object.
    """
    private_token = os.environ.get("GITLAB_TOKEN")
    headers = {"PRIVATE-TOKEN": private_token}
    response = requests.get(api_url, headers=headers)
    print(f"API URL: {api_url} (HTTP Status Code: {response.status_code})")
    if response.status_code == 200:
        return api_url
    else:
        return None


def url_encoder(value: str) -> str:
    """
    Encode the value for URL usage, replacing '.' with '/'.
    """
    if value.endswith('.java' or '.py'):
        base, ext = value.rsplit('.', 1)
        value = base.replace('.', '/') + '.' + ext
    return quote(value, safe='')


def before_agent_callback(callback_context):
    ctx = callback_context
    state = ctx.state
    if "trace" not in state:
        state["trace"] = []
    # 단일 프롬프트만 보관, 여러 part면 첫 part
    input_text = ctx.user_content.parts[0].text if ctx.user_content.parts else "(no text)"
    state["trace"].append({
        "agent": ctx.agent_name,
        "invocation_id": ctx.invocation_id,
        "input": input_text,
        "output": None,
    })
    # 보통 before에선 Content를 반환하지 않아도 됨
    return None


def after_agent_callback(callback_context):
    ctx = callback_context
    state = ctx.state
    # print_trace 함수에서 알아서 state['trace'] 순회
    print_tree_style_trace(state['trace'])
    return None

def before_tool_callback(tool, args, tool_context):
    # args: dict
    # tool: BaseTool
    state = tool_context.state
    if "trace" not in state:
        state["trace"] = []
    state["trace"].append({
        "type": "tool",
        "name": getattr(tool, "name", str(tool)),
        "input": str(args),
        "output": None,
    })

def after_tool_callback(tool, args, tool_context, tool_response):
    state = tool_context.state
    # tool_output은 dict로 나옴
    for entry in reversed(state["trace"]):
        if entry["type"] == "tool" and entry["name"] == getattr(tool, "name", str(tool)) and entry["output"] is None:
            entry["output"] = str(tool_response)
            break


import re

def print_tree_style_trace(trace):
    # 1. 유저 쿼리 출력
    first = trace[0]
    print(f'User Query ("{first["input"]}")')
    print("│")

    # 2. 파일별로 묶기 위한 준비
    file_groups = []
    current_file = None
    current_items = []

    # 파일명을 추출하는 정규식 (java 경로만 추출)
    filename_regex = re.compile(r"src/main/java/(.*?\.java)")

    # 파일별로 그룹핑
    for entry in trace[1:]:
        if entry.get('type') == 'tool' and entry['name'] == 'url_encoder':
            match = filename_regex.search(entry['input'])
            if match:
                # 이전 파일 그룹 저장
                if current_file and current_items:
                    file_groups.append((current_file, current_items))
                    current_items = []
                # 새 파일 그룹 시작
                current_file = match.group(1)
        if current_file:
            current_items.append(entry)
    # 마지막 파일 그룹 저장
    if current_file and current_items:
        file_groups.append((current_file, current_items))

    # 3. 각 파일별 트리 출력
    for i, (filename, items) in enumerate(file_groups):
        is_last = (i == len(file_groups) - 1)
        prefix = "└──" if is_last else "├──"
        print(f"{prefix} <{filename}>")

        for entry in items:
            if entry.get('type') == 'tool' and entry['name'] == 'url_encoder':
                val = eval(entry['input']).get('value')
                print(f"│    ├─ url_encoder({repr(val)}) → {entry['output']}")
            if entry.get('type') == 'tool' and entry['name'] == 'get_url':
                url = eval(entry['input']).get('api_url')
                output = entry['output']
                # 성공/실패 판단
                success = False
                if isinstance(output, str):
                    success = output.startswith("http")
                elif isinstance(output, dict):
                    success = output.get("result", "").startswith("http")
                if success:
                    print(f"│    ├─ get_url(프로젝트=..., 파일={output}) → 성공")
                else:
                    print(f"│    ├─ get_url(프로젝트=..., 파일={output}) → 실패")
        print("│")

