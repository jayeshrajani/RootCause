import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import get_speak_limiter, get_speech_synthesizer
from app.core.errors import AppError
from app.integrations.gemini_tts import GeminiSpeechSynthesizer, SpeechSynthesisError
from app.schemas.errors import ErrorResponse
from app.schemas.speech import SpeakRequest
from app.services.usage import InvestigationLimiter, InvestigationLimitError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["speech"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorResponse, "description": "Too many read-aloud requests from this network"},
    502: {"model": ErrorResponse, "description": "Speech provider failed"},
    503: {"model": ErrorResponse, "description": "Read-aloud is not configured"},
}


@router.post(
    "/speak",
    responses={200: {"content": {"audio/wav": {}}}, **_ERROR_RESPONSES},
    response_class=Response,
)
async def speak(
    body: SpeakRequest,
    request: Request,
    synthesizer: Annotated[GeminiSpeechSynthesizer | None, Depends(get_speech_synthesizer)],
    limiter: Annotated[InvestigationLimiter, Depends(get_speak_limiter)],
) -> Response:
    """Read a triage summary aloud (WAV). The text is neither stored nor logged."""
    if synthesizer is None:
        raise AppError(503, "speech_unavailable", "Read-aloud isn't available right now.")
    try:
        with limiter.reserve(session_id=None, ip=request.client.host if request.client else None):
            audio = await synthesizer.synthesize(body.text.strip())
    except InvestigationLimitError as exc:
        error = AppError(429, "speak_limit", "Read-aloud is resting for a bit. Try again soon.")
        error.headers = exc.headers
        raise error from exc
    except SpeechSynthesisError as exc:
        logger.warning("Read-aloud failed: %s", exc)
        raise AppError(
            502, "speech_failed", "We couldn't read this aloud. Please try again."
        ) from exc
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
