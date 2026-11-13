from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.holds import router as holds_router
from app.api.v1.endpoints.ws import router as ws_router
from app.api.v1.endpoints.queue import router as queue_router

__all__ = [
    "health_router",
    "events_router",
    "metrics_router",
    "holds_router",
    "ws_router",
    "queue_router",
]
