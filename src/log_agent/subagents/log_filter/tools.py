import pytz
from datetime import timedelta, datetime
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.logs_api import LogsApi
from datadog_api_client.v1.model.logs_list_request import LogsListRequest
from datadog_api_client.v1.model.logs_list_request_time import LogsListRequestTime
from datadog_api_client.v1.model.logs_sort import LogsSort


def get_filtered_logs(project_name: str, error_level: str, time_period_hours: int, environment: str):
    """
    Retrieve logs from Datadog filtered by project_name, error_level, time_period_hours, and environment.
    """
    print(f"get_filtered_logs called with project_name={project_name}, error_level={error_level}, time_period_hours={time_period_hours}, environment={environment}")

    tz = pytz.timezone("Europe/Paris")
    now = datetime.now(tz)
    start_time = now - timedelta(hours=time_period_hours)

    query = f"service:{project_name} status:{error_level} env:{environment}"

    body = LogsListRequest(
        index="main",
        query=query,
        sort=LogsSort.TIME_ASCENDING,
        time=LogsListRequestTime(
            _from=start_time,
            to=now,
            timezone="Europe/Paris",
        ),
    )

    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.list_logs(body=body)
        print("response:", response)
        print("response.data:", getattr(response, 'data', None))
        print("response.to_dict():", response.to_dict() if hasattr(response, 'to_dict') else None)

    response_dict = response.to_dict() if hasattr(response, 'to_dict') else response

    filtered_logs = []
    for log in response_dict.get('logs', []):
        print(log)
        content = log.get('content', {})
        # Remove 'tags' if present at this level
        if 'tags' in content:
            del content['tags']
        # If 'attributes' exists, go one level deeper
        attributes = content.get('attributes')
        target = attributes if attributes is not None else content
        # Remove 'tags' if present at attributes level
        if 'tags' in target:
            del target['tags']
        # Check for non-empty 'stack_trace' or 'exc_info'
        if target.get('stack_trace') or target.get('exc_info'):
            filtered_logs.append(log)
   # response_dict['logs'] = filtered_logs
    return response_dict
