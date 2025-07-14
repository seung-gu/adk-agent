import pytz
import json
import collections
from typing import Optional, List
from pydantic import BaseModel, field_serializer
from datetime import timedelta, datetime
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_query_options import LogsQueryOptions
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_sort import LogsSort
from datadog_api_client.v2.model.log import Log


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


def get_filtered_logs(project_name: str, error_level: str, time_period_hours: int, environment: str):
    """
    Retrieve logs from Datadog filtered by project_name, error_level, time_period_hours, and environment.
    """
    tz = pytz.timezone("Europe/Paris")
    now = datetime.now(tz)
    start_time = now - timedelta(hours=time_period_hours)

    query = f"service:{project_name} AND status:{error_level} AND env:{environment}"

    response = fetch_all_logs(query, start_time.isoformat(), now.isoformat())
    response_dict = get_top_unique_logs(response, top_n=5)

    logs = response_dict if isinstance(response_dict, list) else [response_dict]

    return {'logs': logs}


def get_top_unique_logs(logs: List[Log], top_n: int = 5) -> List[dict]:
    """
    Extract the top N unique logs.
    :param logs:
    :param top_n:
    :return:
    """

    log_counter = collections.Counter()
    log_key_to_log = {}

    for log in logs:
        attributes = log.to_dict().get("attributes", {})
        p_log = LogAttributes.from_attributes(attributes)

        # if the log has stack_trace or exc_info, we consider it for counting
        if p_log.stack_trace or p_log.exc_info:
            key = (p_log.message, p_log.filename)
            log_counter[key] += 1
            log_key_to_log[key] = p_log

    # after counting, only extract the most common top_n logs
    for key, p_log in log_key_to_log.items():
        setattr(p_log, "occurances", log_counter[key])

    top_keys = [k for k, _ in log_counter.most_common(top_n)]
    result = [log_key_to_log[k].dict() for k in top_keys]

    return result


class LogAttributes(BaseModel):
    document_id: Optional[str]
    message: Optional[str]
    service: Optional[str]
    status: Optional[str]
    timestamp: Optional[str]
    stack_trace: Optional[str]
    exc_info: Optional[str]
    filename: Optional[str]
    occurances: int = 0

    @classmethod
    def from_attributes(cls, attributes: dict):
        attributes.update(attributes.pop("attributes", {}))
        return cls(
            document_id=attributes.get("document_id", None),
            message=attributes.get("message", None),
            service=attributes.get("service", None),
            status=attributes.get("status", None),
            timestamp=attributes.get("timestamp", None),
            stack_trace=attributes.get("stack_trace", None),
            exc_info=attributes.get("exc_info", None),
            filename=attributes.get("filename", None)
        )
