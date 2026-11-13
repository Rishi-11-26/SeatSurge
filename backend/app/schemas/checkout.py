from typing import List, Optional
from pydantic import BaseModel, Field


class CheckoutPayRequest(BaseModel):
    hold_id: str = Field(..., description="Active hold identifier")
    payment_method: Optional[str] = Field("simulated_card", description="Payment method identifier")
    simulate_failure: Optional[bool] = Field(False, description="Simulate card declined failure")
    simulate_pending: Optional[bool] = Field(False, description="Simulate payment in-flight processing")


class CheckoutPayResponse(BaseModel):
    payment_id: Optional[str] = Field(None, description="Payment transaction reference")
    booking_id: Optional[str] = Field(None, description="Confirmed booking reference")
    status: str = Field(..., description="Payment state: SUCCEEDED | DECLINED | PROCESSING | VOIDED")
    seat_ids: Optional[List[int]] = Field(None, description="List of confirmed seat IDs")
    total_cents: Optional[int] = Field(None, description="Total amount in cents")
    confirmed_at: Optional[str] = Field(None, description="ISO-8601 confirmed timestamp")
    error_code: Optional[str] = Field(None, description="Error code if payment failed")
    message: Optional[str] = Field(None, description="Human-readable outcome message")


class CheckoutReconcileRequest(BaseModel):
    payment_id: str = Field(..., description="Payment transaction ID to reconcile")
    target_outcome: Optional[str] = Field("SUCCEEDED", description="Target terminal outcome: SUCCEEDED | DECLINED | VOIDED")


class CheckoutPaymentStatusResponse(BaseModel):
    payment_id: str = Field(..., description="Payment transaction ID")
    hold_id: str = Field(..., description="Hold identifier")
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Payment state: SUCCEEDED | DECLINED | PROCESSING | VOIDED")
    amount_cents: int = Field(..., description="Total amount in cents")
    booking_id: Optional[str] = Field(None, description="Authoritative booking ID if confirmed")
    seat_ids: Optional[List[int]] = Field(None, description="Seat IDs confirmed")
    confirmed_at: Optional[str] = Field(None, description="ISO-8601 confirmation timestamp")

