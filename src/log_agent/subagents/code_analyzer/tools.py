import os
import urllib

import requests
from urllib.parse import quote
from dataclasses import dataclass


def get_code_snippet_from_gitlab(logs):
    """
    Fetches a code snippet from a GitLab repository for a given file and line number.
    repo_path: full namespace path (e.g., eco/document-classifier)
    file_path: path to the file in the repo
    line_number: 1-based line number
    context_lines: lines of context before/after
    branch: branch name (default: main)
    Requires GITLAB_TOKEN for private repos.
    """
    print(f"get_code_snippet_from_gitlab called with repo_path={repo_path}, file_path={file_path}, line_number={line_number}, context_lines={context_lines}, branch={branch}")
    private_token = os.environ.get("GITLAB_TOKEN")

    GITLAB_API_BASE = os.environ.get("GITLAB_API_BASE", "https://git.cardev.de/api/v4")

    encoded_project = quote(repo_path, safe='')
    encoded_file = quote(file_path, safe='')
    api_url = f"{GITLAB_API_BASE}/projects/{encoded_project}/repository/files/{encoded_file}/raw?ref={branch}"

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


def fqn_to_file_path(fqn: str, source_root: str = "core/src/main/java") -> str:
    """
    Convert a Java FQN (e.g., de.carsync.fleet.core.domain.ConnectedVehicles.predecessor)
    to a file path (e.g., core/src/main/java/de/carsync/fleet/core/domain/ConnectedVehicles.java)
    """
    # Remove method part if present
    if '(' in fqn:
        fqn = fqn.split('(')[0]
    parts = fqn.split('.')
    if len(parts) < 2:
        raise ValueError(f"Invalid FQN: {fqn}")
    class_name = parts[-2] if parts[-1][0].isupper() else parts[-2]
    # If last part is method, use previous as class
    if parts[-1][0].isupper():
        class_name = parts[-1]
        package_parts = parts[:-1]
    else:
        class_name = parts[-2]
        package_parts = parts[:-2] + [parts[-2]]
    file_path = f"{source_root}/{'/'.join(package_parts)}/{class_name}.java"
    return file_path
