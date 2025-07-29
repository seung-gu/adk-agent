import os
import requests
import pytz
import collections
import time
from datetime import timedelta, datetime, timezone
from urllib.parse import quote
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_query_options import LogsQueryOptions
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_sort import LogsSort
from datadog_api_client.v2.model.log import Log
from langchain_core.tools import tool

from models import LogAttribute


def fetch_all_logs(query, start_time, end_time):
    """
    Fetch all logs from Datadog based on the provided query and time range.
    This function handles pagination and returns all logs that match the query.
    :param query:
    :param start_time:
    :param end_time:
    :return:
    """
    body = LogsListRequest(
        filter=LogsQueryFilter(
            query=query,
            _from=start_time,
            to=end_time
        ),
        options=LogsQueryOptions(
            timezone="Europe/Paris"
        ),
        sort=LogsSort.TIMESTAMP_ASCENDING,
        page=LogsListRequestPage(limit=1000)
    )

    configuration = Configuration()
    all_logs = []
    next_cursor = None

    with ApiClient(configuration) as api_client:
        api_instance = LogsApi(api_client)

        # Fetch logs in a loop to handle pagination
        while True:
            if next_cursor:
                body.page = {"cursor": next_cursor}
            response = api_instance.list_logs(body=body)
            all_logs.extend(response.data)

            # Check if there is a next page (cursor)
            next_cursor = response.get('meta', {}).get('page', {}).get('after')
            if not next_cursor:
                break

    return all_logs


def get_top_unique_logs(logs: list[Log], top_n: int = 5) -> list[LogAttribute]:
    """
    Extract the top N unique logs.
    :param logs:
    :param top_n:
    :return:
    """

    log_counter = collections.Counter()
    log_key_to_log = {}

    for log in logs:
        attributes: dict = log.to_dict().get("attributes", {})
        p_log: LogAttribute = LogAttribute.from_attributes(attributes)

        # if the log has stack_trace or exc_info, we consider it for counting
        if p_log.stack_trace or p_log.exc_info:
            key = (p_log.message, p_log.filename)
            log_counter[key] += 1
            log_key_to_log[key] = p_log

    # after counting, only extract the most common top_n logs
    for key, p_log in log_key_to_log.items():
        setattr(p_log, "occurrance", log_counter[key])

    top_keys = [k for k, _ in log_counter.most_common(top_n)]
    result = [log_key_to_log[k] for k in top_keys]

    return result


def get_filtered_logs(project_name: str, log_level: str, time_period_hours: int, environment: str):
    """
    Retrieve logs from Datadog filtered by project_name, log_level, time_period_hours, and environment.
    Returns list of LogAttribute for downstream agents.
    """
    tz = pytz.timezone("Europe/Paris")
    now = datetime.now(tz)
    start_time = now - timedelta(hours=time_period_hours)

    query = f"service:{project_name} AND status:{log_level} AND env:{environment}"

    response = fetch_all_logs(query, start_time.isoformat(), now.isoformat())
    response_dict: list[LogAttribute] = get_top_unique_logs(response, top_n=15)

    return response_dict # Return as a dict for consistency


def make_datadog_url(project_name, log_level, time_period_hours, environment):
    query = f'service:{project_name} status:{log_level} env:{environment}'
    query_encoded = quote(query)

    # Datadog requires timestamps in milliseconds
    now = datetime.now(timezone.utc)
    end_ts = int(time.mktime(now.timetuple()) * 1000)
    start = now - timedelta(hours=time_period_hours)
    start_ts = int(time.mktime(start.timetuple()) * 1000)

    url = (
        f"https://app.datadoghq.eu/logs?query={query_encoded}"
        f"&from_ts={start_ts}&to_ts={end_ts}"
    )
    return url


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


def push_issue_in_gitlab(title: str, content: str, project_path: str, log_url: str):
    API_URL = f"{project_path}/issues"
    headers = {"PRIVATE-TOKEN": os.environ.get("GITLAB_TOKEN")}
    # Gitlab Docs : https://docs.gitlab.com/api/issues/#create-new-issue
    issue_data = {
        "title": title,
        "description": content + (f"\n\n----\n #### Datadog log :\n {log_url}" if log_url else ""),
        "labels": "bug,automated",
        "issue_type": "incident"
    }
    response = requests.post(API_URL, headers=headers, data=issue_data)
    return response


@tool
def fetch_code_from_gitlab(appname: str, file_path: str, branch: str) -> dict:
    """Fetch source code from GitLab for a specific path.
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


@tool
def get_code_from_gitlab(code_url: str) -> str|None:
    """Function to call GitLab API and retrieve code.
    Args:
        code_url (str): GitLab API URL.
    Returns:
        str: code content if successful, None otherwise.
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
