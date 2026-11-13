from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class SeatRead(BaseModel):
    """
    Authoritative single-seat representation.

    Field `seat_id` matches the API contract (docs/api-contract.md §4).
    Field `id` is retained as an alias for frontend component compatibility.
    Status reflects the real-time overlay: AVAILABLE, HELD, PAYING, or SOLD.
    """

    seat_id: int = Field(..., description="Unique seat identifier")
    id: Optional[int] = Field(None, description="Alias for seat_id for frontend compatibility")
    event_id: int
    row: str
    number: int
    section: str
    tier: str
    price_cents: int
    is_accessible: bool
    status: str = Field(
        default="AVAILABLE",
        description="Authoritative real-time seat status (AVAILABLE | HELD | PAYING | SOLD)",
    )

    model_config = ConfigDict(from_attributes=True)


class SeatMapResponse(BaseModel):
    """Paginated seat catalogue snapshot with real-time status overlay."""

    event_id: int
    total_seats: int
    sequence_number: int = Field(
        default=0,
        description=(
            "Monotonically increasing sequence number for real-time synchronisation. "
            "Phase 1 stub — always 0 until Phase 3 WebSocket fan-out is implemented."
        ),
    )
    timestamp: str
    page: int
    page_size: int
    total_pages: int
    seats: List[SeatRead]


class TierAvailability(BaseModel):
    tier: str
    total: int
    available: int
    held: int = Field(
        default=0,
        description="Active holds — populated from Redis counter in Phase 2",
    )
    sold: int
    price_cents: int


class SeatAvailabilitySummary(BaseModel):
    event_id: int
    total_seats: int
    available_seats: int
    held_seats: int = Field(
        default=0,
        description=(
            "Active hold count sourced from Redis counter (holds:active:count). "
            "Phase 1 stub — 0 until Phase 2 Lua scripts maintain the counter."
        ),
    )
    sold_seats: int
    tiers: Dict[str, TierAvailability]
    timestamp: str
