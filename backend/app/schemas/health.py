from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system health status: ok, degraded, or down")
    instance_id: str = Field(..., description="FastAPI replica identifier (e.g. backend-1, backend-2)")
    version: str = Field(..., description="SeatSurge API version")
    timestamp: str = Field(..., description="Current server UTC timestamp")
    services: Dict[str, ServiceStatus] = Field(..., description="Status breakdown of dependencies")


class ReadinessResponse(BaseModel):
    ready: bool = Field(..., description="True only when DB, Redis, AND recovery are all healthy")
    instance_id: str
    database: bool
    redis: bool
    recovery_complete: bool = Field(
        ...,
        description=(
            "True when Redis state reconstruction from PostgreSQL has completed "
            "successfully for this process lifetime. False means this instance is "
            "not yet safe to serve booking traffic."
        ),
    )
