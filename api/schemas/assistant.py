"""Assistant feature request/response schemas."""

from pydantic import BaseModel


class AssistantConfigResponse(BaseModel):
    """Which model, mode, and document collection currently serve the assistant."""

    enabled: bool
    model: str
    mode: str
    collection: str
