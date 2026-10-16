"""Stage 1: identify the crop before diagnosis, combining the vision model and reference photos.

The model reads visible plant structure; the reference library (rice, tomato, potato) adds an
independent visual check. When they disagree, or the model is unsure, the farmer confirms the
crop before the crop-specific diagnosis runs.
"""

import asyncio
import logging
from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, ValidationError

from app.integrations.vision import ImageInput, VisionModel, VisionModelError
from app.models.report import ReportImage
from app.schemas.triage import (
    AnalysisMode,
    ConfidenceLevel,
    Crop,
    CropIdentification,
    ReferenceAgreement,
)
from app.services.triage.ai import CROP_ID_RULES, strict_json_schema
from app.services.triage.references import MIN_SIMILARITY

logger = logging.getLogger(__name__)

# Reference similarities closer than this are treated as a tie, not a disagreement.
DISAGREEMENT_MARGIN = 0.05
_CROP_VALUES = [crop.value for crop in Crop]

IDENTIFY_SYSTEM_PROMPT = (
    "You identify which crop farmer photos show. Do not diagnose problems.\n\nRules:\n"
    + CROP_ID_RULES
    + """- For this task always give your best guess in crop_seen_in_photos, even when \
crop_identification_confidence is "medium" or "low"; use "unclear" only when no plant is \
recognisable. Use "other" for a recognisable crop that is not in the list.
- alternative_crop: the next most likely crop, or "none".
- image_quality: "unusable" when the photos are blurry, too far away or show no plant."""
)


class CropModelOutput(BaseModel):
    crop_visible_features: list[str]
    crop_seen_in_photos: str = Field(json_schema_extra={"enum": [*_CROP_VALUES, "unclear"]})
    crop_identification_confidence: ConfidenceLevel
    alternative_crop: str = Field(json_schema_extra={"enum": [*_CROP_VALUES, "none"]})
    image_quality: Literal["good", "limited", "unusable"]


CROP_SCHEMA = strict_json_schema(CropModelOutput)


@runtime_checkable
class CropSimilaritySource(Protocol):
    async def crop_similarities(self, images: Sequence[bytes]) -> dict[str, float]: ...


def _crop(value: str) -> Crop | None:
    try:
        return Crop(value)
    except ValueError:
        return None


def fuse(
    output: CropModelOutput | None, similarities: dict[str, float], mode: AnalysisMode
) -> CropIdentification:
    model_crop = _crop(output.crop_seen_in_photos) if output else None
    alternative = _crop(output.alternative_crop) if output else None
    confidence = output.crop_identification_confidence if output else ConfidenceLevel.LOW
    quality = output.image_quality if output else "limited"

    ref_crop: Crop | None = None
    if similarities:
        best = max(similarities, key=lambda crop: similarities[crop])
        if similarities[best] >= MIN_SIMILARITY:
            ref_crop = Crop(best)

    if not similarities:
        agreement = ReferenceAgreement.UNAVAILABLE
    elif model_crop is None or model_crop.value not in similarities:
        agreement = ReferenceAgreement.NOT_COVERED
    elif (
        ref_crop is None
        or ref_crop == model_crop
        or similarities[ref_crop.value] - similarities[model_crop.value] < DISAGREEMENT_MARGIN
    ):
        agreement = ReferenceAgreement.AGREES
    else:
        agreement = ReferenceAgreement.DISAGREES

    candidates = list(dict.fromkeys(c for c in (model_crop, alternative, ref_crop) if c))[:3]
    confident = (
        model_crop is not None
        and model_crop != Crop.OTHER
        and confidence == ConfidenceLevel.HIGH
        and quality != "unusable"
        and agreement != ReferenceAgreement.DISAGREES
    )
    return CropIdentification(
        crop=model_crop or ref_crop,
        confidence=confidence,
        needs_confirmation=not confident,
        candidates=candidates,
        image_quality=quality,
        reference_agreement=agreement,
        analysis_mode=mode,
    )


class CropIdentifier:
    def __init__(
        self,
        client: VisionModel | None,
        references: CropSimilaritySource | None = None,
        *,
        attempts: int = 2,
    ) -> None:
        self._client = client
        self._references = references
        self._attempts = attempts

    async def identify(self, images: Sequence[ReportImage]) -> CropIdentification:
        output, similarities = await asyncio.gather(
            self._ask_model(images), self._similarities(images)
        )
        mode = AnalysisMode.AI if self._client is not None else AnalysisMode.MOCK
        result = fuse(output, similarities, mode)
        logger.info(
            "Crop identified crop=%s confidence=%s agreement=%s confirm=%s",
            result.crop.value if result.crop else "none",
            result.confidence.value,
            result.reference_agreement.value,
            result.needs_confirmation,
        )
        return result

    async def _similarities(self, images: Sequence[ReportImage]) -> dict[str, float]:
        if self._references is None:
            return {}
        try:
            return await self._references.crop_similarities([image.data for image in images])
        except Exception:
            logger.exception("Reference crop check failed; continuing without it")
            return {}

    async def _ask_model(self, images: Sequence[ReportImage]) -> CropModelOutput | None:
        if self._client is None:
            return None
        inputs = [ImageInput(media_type=i.media_type, data=i.data) for i in images]
        for attempt in range(1, self._attempts + 1):
            try:
                raw = await self._client.structured_completion(
                    system=IDENTIFY_SYSTEM_PROMPT,
                    text=f"Photos attached: {len(inputs)}. Which crop is this?",
                    images=inputs,
                    schema_name="crop_identification",
                    schema=CROP_SCHEMA,
                    max_tokens=1500,
                )
                return CropModelOutput.model_validate_json(raw)
            except (ValidationError, VisionModelError) as exc:
                logger.warning("Crop identification attempt %d failed: %s", attempt, exc)
                if "timed out" in str(exc):
                    break
        # The farmer can still pick the crop, so identification failure never blocks triage.
        return None
