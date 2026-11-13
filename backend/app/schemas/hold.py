from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class HoldCreateRequest(BaseModel):
    """
    Request payload to create a single or group seat hold.
    Enforces maximum of 6 seats per transaction.
    """

    seat_ids: List[int] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Array of 1 to 6 seat IDs to claim atomically. Group holds must be adjacent.",
    )

    @field_validator("seat_ids")
    @classmethod
    def validate_unique_seats(cls, v: List[int]) -> List[int]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate seat IDs are not permitted in a single hold request.")
        return v


class HoldResponse(BaseModel):
    """Authoritative hold confirmation details matching docs/api-contract.md §6."""

    hold_id: str = Field(..., description="Unique hold identifier (e.g. hld_...)")
    event_id: int = Field(..., description="Target event ID")
    seat_ids: List[int] = Field(..., description="List of claimed seat IDs")
    held_at: str = Field(..., description="ISO 8601 UTC timestamp when hold was created")
    expires_at: str = Field(..., description="ISO 8601 UTC timestamp when hold expires (120s TTL)")
    time_remaining_seconds: int = Field(
        ..., description="Seconds remaining before hold expires and is reaped"
    )
    status: str = Field(default="HELD", description="Current hold status: HELD | PAYING")


class HoldReleaseResponse(BaseModel):
    """Confirmation payload returned on manual hold release."""

    hold_id: str
    message: str = "Hold released successfully."
    released_seats_count: int = Field(default=0)
