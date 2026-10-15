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
from app.services.triage.references import RetrievalReferenceProvider


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    references = RetrievalReferenceProvider(settings) if settings.retrieval_index_version else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Loading takes ~30 s; triage runs without references until it is ready.
        if references is not None:
            references.start_loading()
        yield

    app = FastAPI(
        title="RootCause API",
        version=__version__,
        description="Crop distress triage and early-warning API.",
        lifespan=lifespan,
    )
    app.state.reference_provider = references
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
