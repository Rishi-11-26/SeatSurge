import math
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.rate_limit import check_rate_limit
from app.schemas.event import EventRead, EventListResponse
from app.schemas.seat import SeatRead, SeatMapResponse, SeatAvailabilitySummary
from app.services.event_service import EventService
from app.services.seat_service import SeatService

router = APIRouter(prefix="/events", tags=["Events & Seat Catalog"])


@router.get("", response_model=EventListResponse, dependencies=[Depends(check_rate_limit)])
async def list_events(db: AsyncSession = Depends(get_db)):
    """List all currently active events."""
    events = await EventService.get_active_events(db)
    return EventListResponse(events=events, count=len(events))


@router.get("/{event_id}", response_model=EventRead, dependencies=[Depends(check_rate_limit)])
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve detailed metadata for a specific event."""
    event = await EventService.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found.",
        )
    return event


@router.get("/{event_id}/seats", response_model=SeatMapResponse, dependencies=[Depends(check_rate_limit)])
async def get_event_seats(
    event_id: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=100, ge=1, le=1000, description="Items per page"),
    tier: Optional[str] = Query(default=None, description="Filter by tier: VIP, PREMIUM, STANDARD"),
    row: Optional[str] = Query(default=None, description="Filter by row letter"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated seat catalog with real-time status overlay."""
    event = await EventService.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found.",
        )

    seats, total_count = await SeatService.get_event_seats(
        session=db,
        event_id=event_id,
        page=page,
        page_size=page_size,
        tier=tier,
        row=row,
    )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return SeatMapResponse(
        event_id=event_id,
        total_seats=total_count,
        sequence_number=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        seats=seats,
    )


@router.get("/{event_id}/seats/{seat_id}", response_model=SeatRead, dependencies=[Depends(check_rate_limit)])
async def get_single_seat(
    event_id: int,
    seat_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve authoritative real-time status for a single seat."""
    seat = await SeatService.get_seat_by_id(db, event_id, seat_id)
    if not seat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat ID {seat_id} not found for event {event_id}.",
        )
    return seat


@router.get("/{event_id}/availability", response_model=SeatAvailabilitySummary, dependencies=[Depends(check_rate_limit)])
async def get_seat_availability(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    """High-performance aggregated seat availability summary categorized by tier."""
    event = await EventService.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found.",
        )

    return await SeatService.get_seat_availability_summary(db, event_id)
