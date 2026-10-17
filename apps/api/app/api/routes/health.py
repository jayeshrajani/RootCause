from fastapi import APIRouter

from app import __version__
from app.api.deps import ReferenceProviderDep, SettingsDep
from app.schemas.health import HealthResponse
from app.schemas.triage import AnalysisMode

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: SettingsDep, references: ReferenceProviderDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="rootcause-api",
        version=__version__,
        analysis_mode=AnalysisMode.AI
        if settings.use_gemini or settings.use_cerebras
        else AnalysisMode.MOCK,
        model=(
            settings.gemini_model
            if settings.use_gemini
            else settings.cerebras_model
            if settings.use_cerebras
            else None
        ),
        reference_photos=references.status if references else "disabled",
        satellite_imagery="configured" if settings.satellite_configured else "disabled",
    )
