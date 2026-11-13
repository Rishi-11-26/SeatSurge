from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.holds import router as holds_router
from app.api.v1.endpoints.ws import router as ws_router
from app.api.v1.endpoints.queue import router as queue_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(holds_router)
api_v1_router.include_router(ws_router)
api_v1_router.include_router(queue_router)
