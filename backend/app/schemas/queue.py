from typing import Optional
from pydantic import BaseModel, Field


class QueueEnterRequest(BaseModel):
    event_id: int = Field(1, description="Event ID to join queue for")


class QueueResponse(BaseModel):
    status: str = Field(..., description="Current status: WAITING or ADMITTED")
    queue_position: int = Field(..., description="1-based position if WAITING, 0 if ADMITTED")
    estimated_wait_seconds: int = Field(0, description="Estimated wait time in seconds")
    admission_token: Optional[str] = Field(None, description="Signed admission token when ADMITTED")
    token_expires_at: Optional[str] = Field(None, description="ISO timestamp when admission token expires")
    session_id: str = Field(..., description="Client session identifier")
    event_id: int = Field(..., description="Event identifier")


class QueueLeaveRequest(BaseModel):
    event_id: int = Field(1, description="Event ID to leave queue for")


class QueueLeaveResponse(BaseModel):
    status: str = Field(..., description="Outcome: LEFT or CANCELLED")
    message: str = Field(..., description="Status message")
    session_id: str = Field(..., description="Client session identifier")
    event_id: int = Field(..., description="Event identifier")
