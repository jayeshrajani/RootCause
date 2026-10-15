import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import SettingsDep, get_triage_service, get_triage_translator
from app.core.errors import AppError
from app.models.report import FarmerReport
from app.schemas.errors import ErrorDetail, ErrorResponse
from app.schemas.triage import (
    Crop,
    ResponseLanguage,
    SymptomDuration,
    TranslateTriageRequest,
    TriageResponse,
)
from app.services.image_validation import read_validated_images
from app.services.triage import TriageService
from app.services.triage.translate import TriageTranslator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["triage"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Upload too large"},
    415: {"model": ErrorResponse, "description": "Unsupported image type"},
    422: {"model": ErrorResponse, "description": "Invalid or missing fields"},
    502: {"model": ErrorResponse, "description": "Analysis provider unavailable"},
}

_TRANSLATE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Result too long to translate"},
    422: {"model": ErrorResponse, "description": "Invalid result or language"},
    502: {"model": ErrorResponse, "description": "Translation provider unavailable"},
    503: {"model": ErrorResponse, "description": "Translation is not configured"},
}


@router.post("/triage", responses=_ERROR_RESPONSES)
async def create_triage(
    settings: SettingsDep,
    service: Annotated[TriageService, Depends(get_triage_service)],
    images: Annotated[list[UploadFile] | None, File(description="1-3 JPEG/PNG/WebP photos")] = None,
    description: Annotated[str | None, Form(max_length=2000)] = None,
    crop: Annotated[Crop | None, Form()] = None,
    symptom_duration: Annotated[SymptomDuration | None, Form()] = None,
    latitude: Annotated[float | None, Form(ge=-90, le=90, allow_inf_nan=False)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180, allow_inf_nan=False)] = None,
    location_label: Annotated[str | None, Form(max_length=120)] = None,
    response_language: Annotated[ResponseLanguage, Form()] = ResponseLanguage.ENGLISH,
) -> TriageResponse:
    if (latitude is None) != (longitude is None):
        missing = "longitude" if longitude is None else "latitude"
        message = "Add both latitude and longitude, or leave both empty."
        raise AppError(
            422,
            "validation_error",
            "Some fields are missing or invalid.",
            [ErrorDetail(field=missing, message=message)],
        )
    validated_images = await read_validated_images(
        images or [],
        max_images=settings.max_images,
        max_image_bytes=settings.max_image_bytes,
    )
    report = FarmerReport(
        images=validated_images,
        received_at=datetime.now(UTC),
        crop=crop,
        description=(description or "").strip() or None,
        latitude=latitude,
        longitude=longitude,
        location_label=(location_label or "").strip() or None,
        symptom_duration=symptom_duration,
        response_language=response_language,
    )
    result = await service.assess(report)
    logger.info(
        "Triage completed report_id=%s crop=%s images=%d mode=%s status=%s",
        result.report_id,
        report.crop.value if report.crop else "unspecified",
        len(validated_images),
        result.analysis_mode.value,
        result.status.value,
    )
    return result


@router.post("/triage/translate", responses=_TRANSLATE_ERROR_RESPONSES)
async def translate_triage(
    request: TranslateTriageRequest,
    translator: Annotated[TriageTranslator | None, Depends(get_triage_translator)],
) -> TriageResponse:
    if translator is None:
        raise AppError(
            503,
            "translation_unavailable",
            "Translation needs the AI analysis service, which isn't available right now.",
        )
    return await translator.translate(request.result, request.target_language)
