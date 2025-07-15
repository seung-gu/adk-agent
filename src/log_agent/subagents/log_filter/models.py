from typing import List
from pydantic import BaseModel, Field, field_validator


class LogAttribute(BaseModel):
    document_id: str|None = None
    message: str|None = Field(default=None, description="Log message content")
    service: str|None = Field(default=None, description="Service name associated with the log")
    status: str|None = Field(default=None, description="Log status (e.g., error, warning, info)")
    timestamp: str|None = Field(default=None, description="Timestamp of the log entry")
    stack_trace: str|None = Field(default=None, description="Stack trace associated with the log entry")
    exc_info: str|None = Field(default=None, description="Exception information associated with the log entry")
    filename: str|None = Field(default=None, description="Filename where the log was generated")
    branch: str|None = Field(default=None, description="Branch name extracted from image tag")
    appname: str|None = Field(default=None, description="Application name associated with the log entry")
    occurance: int = Field(default=0, description="Number of occurrences of this log entry")

    @field_validator("stack_trace", mode="before")
    @classmethod
    def extract_stack_trace(cls, v):
        """
        Extracts the stack trace from the log message if available.
        :return: The stack trace as a string or None if not available
        """
        # default as None if not provided
        return ' '.join([line.strip() for line in v.splitlines() if "de.carsync." in line]) or None

    @field_validator("branch", mode="before")
    @classmethod
    def extract_branch(cls, tags: List[str]):
        """
        Extracts the branch name from the tags in the log attributes.
        :param tags: List of tags from the log attributes
        :return: The branch name extracted from the tags, or None if not found
        """
        for tag in tags:
            if tag.startswith("image_tag:"):
                full = tag.split(":", 1)[1]
                # master-df7809... → '-' is used to separate the tag from the commit hash
                return full.split("-", 1)[0] if "-" in full else full
        return None

    @classmethod
    def from_attributes(cls, attributes: dict):
        if not attributes:
            return cls()
        attributes.update(attributes.pop("attributes", {}))
        return cls(
            document_id=attributes.get("document_id", None),
            message=attributes.get("message", None),
            service=attributes.get("service", None),
            status=attributes.get("status", None),
            timestamp=attributes.get("timestamp", None),
            stack_trace=attributes.get("stack_trace", None),
            exc_info=attributes.get("exc_info", None),
            filename=attributes.get("filename", None),
            branch=attributes.get("tags", None),
            appname=attributes.get("application-name", None),
        )


class LogFilterInputSchema(BaseModel):
    project_name: str = Field(..., description="Project name (service)")
    error_level: str = Field(..., description="Error level (e.g., error, warning, info)")
    time_period_hours: int = Field(..., description="Time period in hours")
    environment: str = Field(..., description="Environment (e.g., dev, staging, prod)")


class LogFilterOutputSchema(BaseModel):
    logs: List[LogAttribute] = Field(default=[], description="List of LogAttribute to process")
