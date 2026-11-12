from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import Event


class EventService:
    @staticmethod
    async def get_active_events(session: AsyncSession) -> List[Event]:
        stmt = select(Event).where(Event.is_active == True).order_by(Event.id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_event_by_id(session: AsyncSession, event_id: int) -> Optional[Event]:
        stmt = select(Event).where(Event.id == event_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
