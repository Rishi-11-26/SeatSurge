from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status, Query
from app.core.rate_limit import get_client_identifier, check_rate_limit
from app.ml.bot_detector import check_bot_behavior
from app.schemas.queue import (
    QueueEnterRequest,
    QueueResponse,
    QueueLeaveRequest,
    QueueLeaveResponse,
)
from app.services.queue_service import QueueService

router = APIRouter(prefix="/queue", tags=["Virtual Waiting Room"])


@router.post(
    "/enter",
    response_model=QueueResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(check_rate_limit), Depends(check_bot_behavior)],
)
async def enter_queue_endpoint(
    request: Request,
    payload: QueueEnterRequest = QueueEnterRequest(),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Enters or polls the Virtual Waiting Room (docs/api-contract.md §5).
    Returns WAITING with position & estimated wait time, or ADMITTED with signed admission token.
    Idempotent: polling this endpoint returns the updated position or token.
    """
    session_id = x_session_id or get_client_identifier(request)
    return await QueueService.enter_or_poll_queue(
        event_id=payload.event_id,
        session_id=session_id,
    )


@router.get(
    "/status",
    response_model=QueueResponse,
    status_code=status.HTTP_200_OK,
)
async def get_queue_status_endpoint(
    request: Request,
    event_id: int = Query(1, description="Event ID to query queue status for"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Polls the queue status for the current session."""
    session_id = x_session_id or get_client_identifier(request)
    return await QueueService.enter_or_poll_queue(
        event_id=event_id,
        session_id=session_id,
    )


@router.post(
    "/leave",
    response_model=QueueLeaveResponse,
    status_code=status.HTTP_200_OK,
)
async def leave_queue_endpoint(
    request: Request,
    payload: QueueLeaveRequest = QueueLeaveRequest(),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Leaves the waiting room or relinquishes an admission token, freeing capacity."""
    session_id = x_session_id or get_client_identifier(request)
    return await QueueService.leave_queue(
        event_id=payload.event_id,
        session_id=session_id,
    )
