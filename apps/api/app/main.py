from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestSizeLimitMiddleware
from app.integrations.earth_engine import EarthEngineClient
from app.integrations.open_meteo import OpenMeteoClient
from app.services.satellite import SatelliteService
from app.services.triage.references import RetrievalReferenceProvider
from app.services.usage import InvestigationLimiter
from app.services.weather import CachedWeatherClient


def build_satellite_service(settings: Settings) -> SatelliteService:
    source = (
        EarthEngineClient(
            project_id=settings.google_cloud_project_id or "",
            timeout_seconds=settings.satellite_timeout_seconds,
        )
        if settings.satellite_configured
        else None
    )
    return SatelliteService(
        source,
        window_days=settings.satellite_window_days,
        buffer_m=settings.satellite_buffer_m,
        timeout_seconds=settings.satellite_timeout_seconds,
        min_clear_coverage=settings.satellite_min_clear_coverage,
        stale_days=settings.satellite_stale_days,
        cache_ttl_seconds=settings.satellite_cache_ttl_seconds,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    references = RetrievalReferenceProvider(settings) if settings.retrieval_index_version else None
    # One instance per process so the satellite cache and EE initialisation are shared.
    satellite = build_satellite_service(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Loading takes ~30 s; triage runs without references until it is ready.
        if references is not None:
            references.start_loading()
        # Earth Engine initialisation takes several seconds; keep it off the first request.
        satellite.start_warmup()
        yield

    app = FastAPI(
        title="RootCause API",
        version=__version__,
        description="Crop distress triage and early-warning API.",
        lifespan=lifespan,
    )
    app.state.reference_provider = references
    app.state.satellite_service = satellite
    # Shared so crop identification can warm the weather cache for the following triage.
    app.state.weather_client = CachedWeatherClient(OpenMeteoClient())
    app.state.investigation_limiter = InvestigationLimiter(
        session_limit=settings.investigations_per_session,
        ip_limit_per_hour=settings.investigations_per_ip_hour,
    )
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    # Added last so it is outermost and error responses still carry CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
