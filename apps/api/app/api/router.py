from fastapi import APIRouter

from app.api.routes import health, locations, triage

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(locations.router)
api_router.include_router(triage.router)
