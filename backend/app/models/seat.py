import enum
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.booking import Booking


class SeatTier(str, enum.Enum):
    VIP = "VIP"
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"


class SeatStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    PAYING = "PAYING"
    SOLD = "SOLD"
    RELEASED = "RELEASED"


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    row: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False, default="Main")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default=SeatTier.STANDARD.value)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="seats")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="seat")

    __table_args__ = (
        UniqueConstraint("event_id", "row", "number", name="uq_event_seat_row_num"),
        Index("idx_event_tier", "event_id", "tier"),
    )
