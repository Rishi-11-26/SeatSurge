from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.rate_limit import check_rate_limit, get_client_identifier
from app.schemas.checkout import (
    CheckoutPayRequest,
    CheckoutPayResponse,
    CheckoutReconcileRequest,
    CheckoutPaymentStatusResponse,
)
from app.services.checkout_service import CheckoutService

router = APIRouter(prefix="/checkout", tags=["Checkout & Payment Simulator"])


@router.post(
    "/pay",
    response_model=CheckoutPayResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(check_rate_limit)],
)
async def checkout_pay(
    payload: CheckoutPayRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Initiate checkout payment simulation (docs/api-contract.md §7).
    - Transitions hold to PAYING (protected from expiry reaper).
    - On success: marks seats SOLD in Redis + DB, creates confirmed Booking, and releases queue admission slot.
    - On declined: reverts hold to HELD for user retry without releasing seats.
    - Idempotent: repeated calls with same Idempotency-Key return cached response.
    """
    session_id = x_session_id or get_client_identifier(request)

    return await CheckoutService.process_payment(
        db=db,
        hold_id=payload.hold_id,
        session_id=session_id,
        idempotency_key=idempotency_key,
        payment_method=payload.payment_method or "simulated_card",
        simulate_failure=bool(payload.simulate_failure),
        simulate_pending=bool(payload.simulate_pending),
    )


@router.get(
    "/payments/{payment_id}",
    response_model=CheckoutPaymentStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(check_rate_limit)],
)
async def get_payment_status(
    payment_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Authoritative query for payment transaction status and confirmed booking ID.
    Enforces strict ownership check against X-Session-ID to prevent enumeration.
    """
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Session-ID header is required."},
        )
    return await CheckoutService.get_payment_status(db=db, payment_id=payment_id, session_id=x_session_id)


@router.post(
    "/reconcile",
    response_model=CheckoutPayResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(check_rate_limit)],
)
async def reconcile_payment(
    payload: CheckoutReconcileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
):
    """
    Reconciles a pending or uncertain payment transaction into a definitive terminal state:
    SUCCEEDED, DECLINED, or VOIDED.
    Restricted to trusted internal services or authorized simulator operations via X-Internal-Token.
    """
    from app.core.config import settings

    if not x_internal_token or x_internal_token != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED_RECONCILIATION",
                "message": "Reconciliation is restricted to trusted internal services or authorized simulator operations.",
            },
        )

    return await CheckoutService.reconcile_payment(
        db=db,
        payment_id=payload.payment_id,
        target_outcome=payload.target_outcome or "SUCCEEDED",
        session_id=x_session_id,
    )
