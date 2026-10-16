import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import SettingsDep, get_transcription_service
from app.schemas.errors import ErrorResponse
from app.schemas.transcription import TranscriptionResponse
from app.services.transcription import (
    TranscriptionService,
    read_validated_audio,
    validate_language,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["transcription"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Recording too large"},
    415: {"model": ErrorResponse, "description": "Unsupported recording format"},
    422: {
        "model": ErrorResponse,
        "description": "Missing/empty recording, unsupported language or no speech",
    },
    502: {"model": ErrorResponse, "description": "Transcription provider failed"},
    503: {
        "model": ErrorResponse,
        "description": "Transcription not configured or credentials unavailable",
    },
    504: {"model": ErrorResponse, "description": "Transcription provider timed out"},
}


@router.post("/transcribe", responses=_ERROR_RESPONSES)
async def transcribe(
    settings: SettingsDep,
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
    audio: Annotated[
        UploadFile | None,
        File(
            description=(
                "Recording under 1 minute (the app stops at 55 s): WebM/Ogg (Opus), WAV or FLAC"
            )
        ),
    ] = None,
    language: Annotated[str | None, Form(max_length=20)] = None,
) -> TranscriptionResponse:
    code = validate_language(language, settings.speech_languages)
    data = await read_validated_audio(audio, max_bytes=settings.max_audio_bytes)
    transcript = await service.transcribe(data, code)
    return TranscriptionResponse(transcript=transcript, language=code)
