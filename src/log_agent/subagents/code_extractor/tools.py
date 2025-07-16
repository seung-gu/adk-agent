import os
import requests
from urllib.parse import quote
from src.log_agent.subagents.log_filter.models import LogAttribute


def analyze_code_snippets(logs: list[dict]):
    """
    For each log in logs, call get_code_snippet_from_gitlab and collect results.
    """
    results = []
    for log in logs:
        results.append(get_code_snippet_from_gitlab(LogAttribute(**log)))
    return results


def get_code_from_gitlab_api():
    private_token = os.environ.get("GITLAB_TOKEN")
    headers = {"PRIVATE-TOKEN": private_token}
    return {"GITLAB_API_BASE": "https://git.cardev.de/api/v4", "private_token": private_token}


def get_code_snippet_from_gitlab(log: LogAttribute):
    """

    """

    private_token = os.environ.get("GITLAB_TOKEN")

    GITLAB_API_BASE = os.environ.get("GITLAB_API_BASE", "https://git.cardev.de/api/v4")

    encoded_project = quote(log.appname, safe='')
    encoded_file = quote(log.filename, safe='')
    api_url = f"{GITLAB_API_BASE}/projects/{encoded_project}/repository/files/{encoded_file}/raw?ref={log.branch}"

    headers = {"PRIVATE-TOKEN": private_token} if private_token else {}
    response = requests.get(api_url, headers=headers)

    print("response : ", response)
    if response.status_code == 404:
        # Try if branch is 'master' instead of 'main'
        api_url = f"{GITLAB_API_BASE}/projects/{encoded_project}/repository/files/{encoded_file}/raw?ref=master"
        response = requests.get(api_url, headers=headers)
    if response.status_code == 403:
        raise Exception("Access denied (403). Check your GITLAB_TOKEN and project permissions.")
    if response.status_code == 404:
        raise Exception(f"File or project not found: {api_url}")
    if response.status_code != 200:
        raise Exception(f"Failed to fetch file from GitLab: {response.status_code} {response.text}")
    code_lines = response.text.splitlines()
    return "\n".join(code_lines[line_number - context_lines:line_number + context_lines])
