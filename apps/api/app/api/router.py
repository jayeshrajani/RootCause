from fastapi import APIRouter

from app.api.routes import health, locations, satellite, transcribe, triage

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(locations.router)
api_router.include_router(satellite.router)
api_router.include_router(transcribe.router)
api_router.include_router(triage.router)
