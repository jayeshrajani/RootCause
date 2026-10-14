from fastapi import APIRouter

from app import __version__
from app.schemas.health import HealthResponse
from app.schemas.triage import AnalysisMode

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="rootcause-api",
        version=__version__,
        analysis_mode=AnalysisMode.MOCK,
    )
