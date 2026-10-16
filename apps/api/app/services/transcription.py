"""Speech-to-text for the farmer's optional symptom description.

Recordings are held in memory for the request only; neither audio nor transcripts are stored or
logged. The transcript is returned in the spoken language and is never translated here.
"""

import logging
from collections.abc import Sequence

from fastapi import UploadFile, status

from app.core.errors import AppError
from app.integrations.google_speech import SpeechError, SpeechRecognizer
from app.schemas.errors import ErrorDetail

logger = logging.getLogger(__name__)

# Below this size a container holds headers only, not speech.
MIN_AUDIO_BYTES = 512


def detect_audio_type(data: bytes) -> str | None:
    """Identify the recording format from its magic bytes; the client content type is ignored.

    Only containers Speech-to-Text V2 auto-decodes are accepted (MP4/AAC and MP3 are not).
    """
    if data.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"fLaC"):
        return "audio/flac"
    return None


def _error(status_code: int, code: str, message: str, field: str | None = None) -> AppError:
    details = [ErrorDetail(field=field, message=message)] if field else []
    return AppError(status_code, code, message, details)


def validate_language(language: str | None, enabled: Sequence[str]) -> str:
    if language is None or language not in enabled:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_language",
            f"Voice input supports: {', '.join(enabled)}.",
            "language",
        )
    return language


async def read_validated_audio(upload: UploadFile | None, *, max_bytes: int) -> bytes:
    if upload is None:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "audio_required", "Add a recording.", "audio"
        )
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "audio_too_large",
            f"The recording is over {max_bytes / (1024 * 1024):g} MB. Keep it under a minute.",
            "audio",
        )
    if len(data) < MIN_AUDIO_BYTES:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "empty_audio",
            "The recording is empty. Tap the microphone and speak, then try again.",
            "audio",
        )
    if detect_audio_type(data) is None:
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_audio_type",
            "This recording format isn't supported. Use WebM or Ogg (Opus), WAV or FLAC.",
            "audio",
        )
    return data


class TranscriptionService:
    """Transcribes validated audio with the configured recognizer (None = not configured)."""

    def __init__(self, recognizer: SpeechRecognizer | None) -> None:
        self._recognizer = recognizer

    @property
    def configured(self) -> bool:
        return self._recognizer is not None

    async def transcribe(self, audio: bytes, language: str) -> str:
        if self._recognizer is None:
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "transcription_unavailable",
                "Voice input isn't available right now. Please type your description instead.",
            )
        try:
            result = await self._recognizer.recognize(audio, language)
        except SpeechError as exc:
            logger.warning("Transcription failed kind=%s language=%s: %s", exc.kind, language, exc)
            if exc.kind == "auth":
                raise _error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "transcription_unavailable",
                    "Voice input isn't available right now. Please type your description instead.",
                ) from exc
            if exc.kind == "timeout":
                raise _error(
                    status.HTTP_504_GATEWAY_TIMEOUT,
                    "transcription_timeout",
                    "Transcription took too long. Please try again.",
                ) from exc
            raise _error(
                status.HTTP_502_BAD_GATEWAY,
                "transcription_failed",
                "We couldn't transcribe the recording. Please try again or type instead.",
            ) from exc

        transcript = result.transcript.strip()
        if not transcript:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "no_speech_detected",
                "We couldn't hear any speech. Speak closer to the phone and try again.",
                "audio",
            )
        logger.info(
            "Transcription completed language=%s audio_bytes=%d characters=%d",
            language,
            len(audio),
            len(transcript),
        )
        return transcript
