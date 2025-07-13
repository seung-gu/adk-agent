import pytz
from datetime import timedelta, datetime
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_query_options import LogsQueryOptions
from datadog_api_client.v2.model.logs_sort import LogsSort
import json
import datetime as dt


def fetch_all_logs(query, start_time, end_time):
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
        page={"limit": 1000}
    )

    configuration = Configuration()
    all_logs = []
    next_cursor = None

    with ApiClient(configuration) as api_client:
        api_instance = LogsApi(api_client)

        while True:
            if next_cursor:
                body.page = {"cursor": next_cursor}
            response = api_instance.list_logs(body=body)
            all_logs.extend(response.data)

            if not response.meta or not hasattr(response.meta, 'after') or not response.meta.after:
                break
            next_cursor = response.meta.after

    return all_logs


def get_filtered_logs(project_name: str, error_level: str, time_period_hours: int, environment: str):
    """
    Retrieve logs from Datadog filtered by project_name, error_level, time_period_hours, and environment.
    """
    print(f"get_filtered_logs called with project_name={project_name}, error_level={error_level}, time_period_hours={time_period_hours}, environment={environment}")

    tz = pytz.timezone("Europe/Paris")
    now = datetime.now(tz)
    start_time = now - timedelta(hours=time_period_hours)

    query = f"service:{project_name} AND status:{error_level} AND env:{environment}"

    response = fetch_all_logs(query, start_time.isoformat(), now.isoformat())

    print("response:", response)
    print("response.data:", getattr(response, 'data', None))
    print("response.to_dict():", response.to_dict() if hasattr(response, 'to_dict') else None)

    response_dict = response.to_dict() if hasattr(response, 'to_dict') else response
    response_dict = get_top_unique_logs_by_message_and_filename(response_dict, top_n=5)

    logs = response_dict if isinstance(response_dict, list) else response_dict.get('logs', [])

    return {'logs': logs}

def get_top_unique_logs_by_message_and_filename(response_dict, top_n=5):
    """
    Deduplicate logs by (message, filename) and return the top N most frequent unique combinations.
    For Datadog v2: extract from log['attributes'], and only keep 'attributes', 'message', 'service', 'timestamp' at the top level of the log dict.
    Accepts response_dict as a list of logs (not a dict with 'logs').
    Output is a list of filtered log dicts (no 'content' key).
    """
    import collections
    logs = response_dict if isinstance(response_dict, list) else []
    log_counter = collections.Counter()
    log_key_to_log = {}
    for log in logs:
        # For Datadog v2, all info is in log['attributes']
        attributes = log.get('attributes', {})
        nested_attributes = attributes.get('attributes')
        msg = attributes.get('message')
        service = attributes.get('service')
        timestamp = attributes.get('timestamp')
        # Convert datetime to ISO string if needed
        if isinstance(timestamp, dt.datetime):
            timestamp = timestamp.isoformat()
        fname = nested_attributes['filename'] if isinstance(nested_attributes, dict) and 'filename' in nested_attributes else None
        # Deduplicate by (message, filename)
        if msg is not None and fname is not None:
            key = (msg, fname)
            log_counter[key] += 1
            filtered_log = {}
            if isinstance(nested_attributes, dict):
                filtered_log['attributes'] = nested_attributes
            if msg is not None:
                filtered_log['message'] = msg
            if service is not None:
                filtered_log['service'] = service
            if timestamp is not None:
                filtered_log['timestamp'] = timestamp
            # Add count of occurrences for this (message, filename) pair
            filtered_log['count'] = 1  # Will update after loop
            log_key_to_log[key] = filtered_log
    # After counting, update each filtered_log with the correct count
    for key, filtered_log in log_key_to_log.items():
        filtered_log['count'] = log_counter[key]
    if not log_counter:
        return []
    top_keys = [k for k, _ in log_counter.most_common(top_n)]
    result = [log_key_to_log[k] for k in top_keys]
    # Serialize and deserialize to ensure all datetime are converted to string
    def default_converter(o):
        if isinstance(o, dt.datetime):
            return o.isoformat()
        raise TypeError
    result = json.loads(json.dumps(result, default=default_converter))
    return result
