from fastapi import APIRouter

from app.api.routes import health, triage

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(triage.router)
