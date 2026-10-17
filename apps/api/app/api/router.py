from fastapi import APIRouter

from app.api.routes import assist, health, locations, satellite, speak, transcribe, triage

api_router = APIRouter()
api_router.include_router(assist.router)
api_router.include_router(health.router)
api_router.include_router(locations.router)
api_router.include_router(satellite.router)
api_router.include_router(speak.router)
api_router.include_router(transcribe.router)
api_router.include_router(triage.router)
