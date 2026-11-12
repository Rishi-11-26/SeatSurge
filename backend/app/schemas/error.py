from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code (e.g. NOT_FOUND, VALIDATION_ERROR)")
    message: str = Field(..., description="Human-readable error description")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured error context (conflicting seats, field names, etc.)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the error",
    )


class ErrorResponse(BaseModel):
    """
    Structured error envelope matching the RFC 7807-inspired API contract.

    All 4xx/5xx responses from SeatSurge use this schema:
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Event with ID 999 not found.",
                "details": {},
                "timestamp": "2026-11-13T12:00:00Z"
            }
        }
    """

    error: ErrorDetail
