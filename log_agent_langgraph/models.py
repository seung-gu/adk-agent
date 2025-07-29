from pydantic import BaseModel, Field


class LogState(BaseModel):
    project_name: str
    log_level: str
    time_period_hours: int
    environment: str

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
    occurrance: int = Field(default=0, description="Number of occurrences of this log entry")

    @classmethod
    def extract_stack_trace(cls, stack_trace: str|None, exc_info: str|None) -> str|None:
        """
        Extracts the stack trace from the log message if available.
        :return: The stack trace as a string or None if not available
        """
        # default as None if not provided
        try:
            if not stack_trace:
                return exc_info if exc_info else None

            error_lines = [line.strip() for line_no, line in enumerate(stack_trace.splitlines())
                           if ("de.carsync." in line and ".java:" in line) or line_no==0][:5]
            return str(error_lines) if len(error_lines) > 1 else None
        except Exception as e:
            print(f"Error extracting stack trace: {e}")
            return None


    @classmethod
    def extract_branch(cls, tags: list[str]):
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
            stack_trace=cls.extract_stack_trace(attributes.get("stack_trace", None), attributes.get("exc_info", None)),
            exc_info=attributes.get("exc_info", None),
            filename=attributes.get("filename", None) or attributes.get("logger_name", None),
            branch=cls.extract_branch(attributes.get("tags", None)),
            appname=attributes.get("application-name", None),
        )
