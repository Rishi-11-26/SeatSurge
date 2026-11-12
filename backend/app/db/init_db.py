import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Set, Tuple
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.models.event import Event
from app.models.seat import Seat, SeatTier

DEFAULT_EVENT_ID = 1
DEFAULT_EVENT_NAME = "YUKTIK 2026 Grand Concert"
ADVISORY_LOCK_ID = 987654321

# Expected tier counts for YUKTIK 2026
EXPECTED_TIER_COUNTS = {
    SeatTier.VIP.value: 240,
    SeatTier.PREMIUM.value: 1200,
    SeatTier.STANDARD.value: 3600,
}
EXPECTED_TOTAL_SEATS = 5040


def generate_seat_layout(event_id: int) -> List[Dict[str, Any]]:
    """
    Generates exact 5,040 seat layout:
    - VIP: Rows A-D (4 rows * 60 seats = 240 seats, $150.00)
    - PREMIUM: Rows E-P (12 rows * 100 seats = 1,200 seats, $100.00)
    - STANDARD: Rows Q-Z (10 rows) + AA-AH (8 rows) = 18 rows * 200 seats = 3,600 seats ($50.00)
    Total = 240 + 1,200 + 3,600 = 5,040 seats.
    """
    seats = []
    seat_id = 1

    # 1. VIP Section: Rows A to D (4 rows, 60 seats/row)
    vip_rows = ["A", "B", "C", "D"]
    for row in vip_rows:
        for num in range(1, 61):
            seats.append({
                "id": seat_id,
                "event_id": event_id,
                "row": row,
                "number": num,
                "section": "Floor VIP",
                "tier": SeatTier.VIP.value,
                "price_cents": 15000,
                "is_accessible": (num in [1, 2]),
                "created_at": datetime.now(timezone.utc),
            })
            seat_id += 1

    # 2. PREMIUM Section: Rows E to P (12 rows, 100 seats/row)
    premium_rows = ["E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P"]
    for row in premium_rows:
        for num in range(1, 101):
            seats.append({
                "id": seat_id,
                "event_id": event_id,
                "row": row,
                "number": num,
                "section": "Lower Bowl",
                "tier": SeatTier.PREMIUM.value,
                "price_cents": 10000,
                "is_accessible": (num in [1, 2]),
                "created_at": datetime.now(timezone.utc),
            })
            seat_id += 1

    # 3. STANDARD Section: Rows Q to Z (10 rows) + AA to AH (8 rows) = 18 rows, 200 seats/row
    standard_rows = [
        "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH",
    ]
    for row in standard_rows:
        for num in range(1, 201):
            seats.append({
                "id": seat_id,
                "event_id": event_id,
                "row": row,
                "number": num,
                "section": "Upper Bowl",
                "tier": SeatTier.STANDARD.value,
                "price_cents": 5000,
                "is_accessible": (num in [1, 2]),
                "created_at": datetime.now(timezone.utc),
            })
            seat_id += 1

    return seats


async def verify_seat_distribution(session: AsyncSession, event_id: int) -> bool:
    """Verifies that the database has the expected total seats and tier distribution."""
    stmt = (
        select(Seat.tier, func.count(Seat.id))
        .where(Seat.event_id == event_id)
        .group_by(Seat.tier)
    )
    result = await session.execute(stmt)
    actual_counts = {tier: count for tier, count in result.all()}

    total_actual = sum(actual_counts.values())
    if total_actual != EXPECTED_TOTAL_SEATS:
        logger.warning(f"Seat total mismatch: expected {EXPECTED_TOTAL_SEATS}, found {total_actual}")
        return False

    for tier, expected_count in EXPECTED_TIER_COUNTS.items():
        actual = actual_counts.get(tier, 0)
        if actual != expected_count:
            logger.warning(f"Tier {tier} mismatch: expected {expected_count}, found {actual}")
            return False

    return True


async def init_db(engine: AsyncEngine) -> None:
    """
    Concurrency-safe, crash-recoverable database schema initialization and seat seeding.
    Features:
    1. PostgreSQL session-level advisory lock (pg_try_advisory_lock) to prevent concurrent seeds.
    2. Idempotent: safe to run multiple times without duplicating or corrupting data.
    3. Recoverable: partial seed runs are safely detected and completed by filling missing seats.
    4. Full layout & tier distribution validation.
    """
    is_postgres = "postgres" in str(engine.url)

    async with engine.connect() as conn:
        acquired_lock = False
        if is_postgres:
            try:
                # Try to acquire PostgreSQL advisory lock to ensure only one instance seeds
                res = await conn.execute(text(f"SELECT pg_try_advisory_lock({ADVISORY_LOCK_ID})"))
                acquired_lock = res.scalar() is True
            except Exception as e:
                logger.warning(f"Could not check advisory lock: {e}")
                acquired_lock = True
        else:
            acquired_lock = True

        if not acquired_lock:
            logger.info("Another backend instance is initializing the database. Waiting...")
            for _ in range(30):
                await asyncio.sleep(0.5)
                try:
                    async with conn.begin():
                        check = await conn.execute(text("SELECT count(*) FROM seats WHERE event_id = 1"))
                        if check.scalar() >= EXPECTED_TOTAL_SEATS:
                            logger.info("Database initialized by peer instance.")
                            return
                except Exception:
                    pass
            logger.warning("Peer initialization timed out. Proceeding with safety checks...")

        try:
            logger.info("Initializing database tables and seed data...")
            async with conn.begin():
                await conn.run_sync(Base.metadata.create_all)

            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                # 1. Ensure default event exists
                event_stmt = select(Event).where(Event.id == DEFAULT_EVENT_ID)
                result = await session.execute(event_stmt)
                event = result.scalar_one_or_none()

                if not event:
                    new_event = Event(
                        id=DEFAULT_EVENT_ID,
                        name=DEFAULT_EVENT_NAME,
                        description="YUKTIK 2026 flagship tech & music festival live concert.",
                        venue_name="YUKTIK Grand Auditorium",
                        total_seats=EXPECTED_TOTAL_SEATS,
                        start_time=datetime.now(timezone.utc) + timedelta(days=7),
                        is_active=True,
                    )
                    session.add(new_event)
                    await session.commit()
                    logger.info("Created default event with ID 1")

                # 2. Inspect existing seats to support partial-seed recovery
                existing_stmt = select(Seat.id, Seat.row, Seat.number).where(Seat.event_id == DEFAULT_EVENT_ID)
                existing_res = await session.execute(existing_stmt)
                existing_rows = existing_res.all()
                existing_ids: Set[int] = {r[0] for r in existing_rows}
                existing_coords: Set[Tuple[str, int]] = {(r[1], r[2]) for r in existing_rows}

                current_seats = len(existing_ids)

                if current_seats < EXPECTED_TOTAL_SEATS:
                    logger.info(
                        f"Seeding seats (current count: {current_seats}/{EXPECTED_TOTAL_SEATS}). "
                        "Generating full layout and inserting missing seats..."
                    )
                    all_seat_dicts = generate_seat_layout(DEFAULT_EVENT_ID)

                    # Filter out seats already present in database (safe recovery)
                    missing_seats = [
                        s for s in all_seat_dicts
                        if (s["id"] not in existing_ids and (s["row"], s["number"]) not in existing_coords)
                    ]

                    logger.info(f"Identified {len(missing_seats)} missing seats to seed.")
                    batch_size = 1000
                    for i in range(0, len(missing_seats), batch_size):
                        batch = missing_seats[i:i + batch_size]
                        seat_objs = [Seat(**item) for item in batch]
                        session.add_all(seat_objs)
                        await session.commit()

                    logger.info("Successfully completed seat seeding!")

                # 3. Final verification of distribution
                is_valid = await verify_seat_distribution(session, DEFAULT_EVENT_ID)
                if is_valid:
                    logger.info(f"Seat distribution verified: exactly {EXPECTED_TOTAL_SEATS} seats with correct tier ratios.")
                else:
                    logger.error("Seat distribution check failed after initialization!")

        finally:
            if is_postgres and acquired_lock:
                try:
                    await conn.execute(text(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})"))
                except Exception as e:
                    logger.warning(f"Error releasing advisory lock: {e}")
