import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.seat import Seat


class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class Booking(Base):
    """
    Permanent record of every booking action — confirmed, cancelled, and refunded.

    Lifecycle design:
        AVAILABLE → (Redis Lua hold) → HELD → PAYING → CONFIRMED (row inserted here)
        CONFIRMED → CANCELLED  (row updated; seat becomes AVAILABLE again)
        CONFIRMED → REFUNDED   (row updated; seat may optionally be released)

    Database integrity guarantees:
        1. Only one CONFIRMED booking per (event_id, seat_id) is allowed.
           Partial unique index (WHERE status = 'CONFIRMED') enforces this for
           both PostgreSQL and SQLite without blocking re-sales after cancellation.

        2. Cancelled and refunded records are retained for full audit history.
           Do NOT delete rows to release a seat.

        3. idempotency_key links this booking to a specific checkout request.
           Repeated checkout calls with the same key MUST look up and return
           the existing booking rather than attempting a duplicate INSERT.
           The unique constraint on idempotency_key enforces this at DB level.
    """

    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Booking lifecycle ───────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BookingStatus.CONFIRMED.value,
        index=True,
        comment="CONFIRMED | CANCELLED | REFUNDED",
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Refund reference — populated when status transitions to REFUNDED
    refund_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Idempotency ─────────────────────────────────────────────────────────
    # Stores the client-supplied Idempotency-Key header from the checkout call.
    # Phase 6 checkout service must:
    #   1. Look up Booking by idempotency_key before inserting.
    #   2. If found → return existing booking (idempotent response).
    #   3. If not found → insert with this key.
    # Auto-generated default ensures test code that doesn't set a key still works.
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default=lambda: f"auto_{uuid.uuid4().hex}",
        comment="Client-supplied Idempotency-Key from checkout request",
    )

    # ── Relationships ────────────────────────────────────────────────────────
    event: Mapped["Event"] = relationship("Event", back_populates="bookings")
    seat: Mapped["Seat"] = relationship("Seat", back_populates="bookings")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        # CRITICAL: Only one CONFIRMED booking per (event, seat).
        # CANCELLED/REFUNDED rows do NOT block future confirmed bookings.
        # Partial unique index — supported natively by both PostgreSQL and SQLite.
        Index(
            "ix_booking_one_confirmed_per_seat",
            "event_id",
            "seat_id",
            unique=True,
            postgresql_where=text("status = 'CONFIRMED'"),
            sqlite_where=text("status = 'CONFIRMED'"),
        ),
        # Idempotency: one booking record per checkout request.
        # PhaseIV 6 service must query by this key before inserting.
        UniqueConstraint("idempotency_key", name="uq_booking_idempotency_key"),
        Index("idx_booking_session", "session_id"),
        Index("idx_booking_payment", "payment_id"),
        Index("idx_booking_status", "status"),
        Index("idx_booking_refund", "refund_id"),
    )
