"""After a triage: safe treatment guidance and nearby agri-input shops."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_assist_limiter, get_shop_finder, get_treatment_advisor
from app.core.errors import AppError
from app.integrations.gemini_maps import GeminiMapsShopFinder, ShopSearchError
from app.schemas.assist import (
    ShopSearchRequest,
    ShopSearchResponse,
    TreatmentPlan,
    TreatmentRequest,
)
from app.schemas.errors import ErrorResponse
from app.services.treatment import TreatmentAdvisor
from app.services.usage import InvestigationLimiter, InvestigationLimitError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assist"])

Limiter = Annotated[InvestigationLimiter, Depends(get_assist_limiter)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Invalid request"},
    429: {"model": ErrorResponse, "description": "Too many requests from this network"},
    502: {"model": ErrorResponse, "description": "Provider failed"},
    503: {"model": ErrorResponse, "description": "Not configured"},
}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _limited(exc: InvestigationLimitError) -> AppError:
    error = AppError(429, "assist_limit", "That's a lot of lookups. Please try again soon.")
    error.headers = exc.headers
    return error


@router.post("/triage/treatment", responses=_ERRORS)
async def treatment(
    body: TreatmentRequest,
    request: Request,
    advisor: Annotated[TreatmentAdvisor | None, Depends(get_treatment_advisor)],
    limiter: Limiter,
) -> TreatmentPlan:
    """Generic, label-first treatment guidance for a likely cause. Never brands or doses."""
    if advisor is None:
        raise AppError(
            503, "treatment_unavailable", "Treatment guidance isn't available right now."
        )
    try:
        with limiter.reserve(session_id=None, ip=_ip(request)):
            return await advisor.plan(body)
    except InvestigationLimitError as exc:
        raise _limited(exc) from exc


@router.post("/places/agri-shops", responses=_ERRORS)
async def agri_shops(
    body: ShopSearchRequest,
    request: Request,
    finder: Annotated[GeminiMapsShopFinder | None, Depends(get_shop_finder)],
    limiter: Limiter,
) -> ShopSearchResponse:
    """Agri-input shops and Krishi Vigyan Kendras near the field, from Google Maps via Gemini."""
    has_coords = body.latitude is not None and body.longitude is not None
    if (body.latitude is None) != (body.longitude is None) or not (
        has_coords or (body.place or "").strip()
    ):
        raise AppError(422, "location_required", "Share the field's location or a place name.")
    if finder is None:
        raise AppError(503, "shops_unavailable", "Shop search isn't available right now.")
    try:
        with limiter.reserve(session_id=None, ip=_ip(request)):
            shops = await finder.find(
                latitude=body.latitude, longitude=body.longitude, place=(body.place or "").strip()
            )
    except InvestigationLimitError as exc:
        raise _limited(exc) from exc
    except ShopSearchError as exc:
        logger.warning("Shop search failed: %s", exc)
        raise AppError(502, "shops_failed", "We couldn't search nearby shops. Try again.") from exc
    return ShopSearchResponse(shops=shops, source="Google Maps via Gemini")
