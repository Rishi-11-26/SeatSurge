from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    name: str
    description: Optional[str] = None
    venue_name: str
    total_seats: int
    start_time: datetime
    is_active: bool


class EventRead(EventBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    events: List[EventRead]
    count: int
