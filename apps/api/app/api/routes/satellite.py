from fastapi import APIRouter

from app.api.deps import SatelliteServiceDep
from app.schemas.errors import ErrorResponse
from app.schemas.satellite import SatelliteAnalysis, SatelliteAnalysisRequest

router = APIRouter(tags=["satellite"])


@router.post(
    "/satellite/analysis",
    responses={422: {"model": ErrorResponse, "description": "Invalid location or boundary"}},
)
async def analyze_satellite(
    request: SatelliteAnalysisRequest, service: SatelliteServiceDep
) -> SatelliteAnalysis:
    """Sentinel-2 NDVI/NDMI for a location. Always 200; check `status` for availability."""
    return await service.analyze(
        request.latitude,
        request.longitude,
        analysis_date=request.analysis_date,
        boundary=request.field_boundary,
    )
