from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.rate_limit import check_rate_limit, get_client_identifier
from app.schemas.hold import HoldCreateRequest, HoldResponse, HoldReleaseResponse
from app.services.hold_service import HoldService

router = APIRouter(prefix="/events/{event_id}/holds", tags=["Atomic Seat Holds"])


@router.post(
    "",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit)],
)
async def create_seat_hold(
    event_id: int,
    payload: HoldCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_admission_token: Optional[str] = Header(None, alias="X-Admission-Token"),
):
    """
    Atomically claim 1 to 6 adjacent seats for up to 120 seconds.
    - Zero double-booking under extreme concurrent requests.
    - All-or-nothing: if any seat is unavailable, entire request is rejected.
    """
    session_id = x_session_id
    if not session_id:
        # Fall back to client identifier from proxy IP if header omitted
        session_id = get_client_identifier(request)

    return await HoldService.create_hold(
        db=db,
        event_id=event_id,
        seat_ids=payload.seat_ids,
        session_id=session_id,
        idempotency_key=idempotency_key,
        admission_token=x_admission_token,
    )


@router.delete(
    "/{hold_id}",
    response_model=HoldReleaseResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def release_seat_hold(
    event_id: int,
    hold_id: str,
    request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Manually release an active seat hold before the 120s expiry.
    Seats return immediately to AVAILABLE state.
    """
    session_id = x_session_id or get_client_identifier(request)
    return await HoldService.release_hold(
        event_id=event_id,
        hold_id=hold_id,
        session_id=session_id,
    )


@router.get(
    "/{hold_id}",
    response_model=HoldResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def get_hold_status(
    event_id: int,
    hold_id: str,
    session_id: str = Header(..., alias="X-Session-ID"),
):
    """Inspect active hold metadata and time remaining."""
    details = await HoldService.get_hold_details(event_id=event_id, hold_id=hold_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Hold {hold_id} not found or expired."},
        )
    if details.get("session_id") and details.get("session_id") != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You do not have permission to view this hold."},
        )
    return HoldResponse(**details)
