"""Gemini transcription for short voice notes, with the spoken language detected automatically.

Gemini accepts the WebM/Opus that Chrome records, and is told to keep Hindi in Devanagari so
Hindi speech is never written in Urdu or Latin script. Nothing is translated here.
"""

import asyncio
import base64
import json
import logging
import ssl
import time
from typing import Any

import httpx
import truststore

from app.integrations.google_speech import SpeechError, SpeechResult
from app.services.transcription import AUTO_LANGUAGE, detect_audio_type

logger = logging.getLogger(__name__)

# Codes the model may report; anything else is returned as None.
DETECTABLE_LANGUAGES = ("en-IN", "hi-IN")

_SYSTEM = (
    "You transcribe a farmer's short voice note about a crop problem. The speech is English, "
    "Hindi, or a mix of both. Write exactly what was said: Hindi words in Devanagari script, "
    "English words in Latin script. Do not translate, summarise, correct or add anything. "
    "If there is no intelligible speech, return an empty transcript."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "language": {
            "type": "string",
            "enum": [*DETECTABLE_LANGUAGES, "other"],
            "description": "Main spoken language.",
        },
    },
    "required": ["transcript", "language"],
}

# Gemini sheds load with 503s under high demand; one quick retry clears most of them.
_RETRY_STATUSES = (429, 500, 503)
_RETRY_DELAY_SECONDS = 1.0


class GeminiSpeechClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-flash-lite-latest",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self._retry_delay = _RETRY_DELAY_SECONDS

    async def recognize(self, audio: bytes, language_code: str) -> SpeechResult:
        mime_type = detect_audio_type(audio)
        if mime_type is None:
            raise SpeechError("rejected", "Unsupported recording format")
        instruction = (
            "Transcribe this voice note."
            if language_code == AUTO_LANGUAGE
            else f"Transcribe this voice note. The farmer chose {language_code}."
        )
        body = {
            "systemInstruction": {"parts": [{"text": _SYSTEM}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": instruction},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(audio).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _SCHEMA,
                "temperature": 0,
            },
        }

        started = time.perf_counter()
        response = await self._post(body)
        try:
            candidate = response.json()["candidates"][0]
            output = "".join(part.get("text", "") for part in candidate["content"]["parts"])
            parsed = json.loads(output)
            transcript = str(parsed.get("transcript", "")).strip()
            detected = parsed.get("language")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise SpeechError("bad_response", "Gemini returned an unexpected payload") from exc

        language = detected if detected in DETECTABLE_LANGUAGES else None
        logger.info(
            "Gemini transcription model=%s requested=%s detected=%s audio_bytes=%d elapsed_ms=%d",
            self.model,
            language_code,
            language,
            len(audio),
            (time.perf_counter() - started) * 1000,
        )
        return SpeechResult(transcript, language)

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        url = f"{self._base_url}/models/{self.model}:generateContent"
        status = 0
        for attempt in range(2):
            if attempt:
                await asyncio.sleep(self._retry_delay)
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                    verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                ) as client:
                    response = await client.post(
                        url, headers={"x-goog-api-key": self._api_key}, json=body
                    )
            except httpx.TimeoutException as exc:
                raise SpeechError("timeout", "Gemini transcription timed out") from exc
            except httpx.HTTPError as exc:
                raise SpeechError(
                    "unavailable", f"Gemini transcription failed: {type(exc).__name__}"
                ) from exc
            status = response.status_code
            if status == 200:
                return response
            if status not in _RETRY_STATUSES:
                break
        if status in (401, 403):
            raise SpeechError("auth", f"Gemini rejected the API key (HTTP {status})")
        if status == 400:
            raise SpeechError("rejected", "Gemini could not process the audio (HTTP 400)")
        raise SpeechError("unavailable", f"Gemini returned HTTP {status}")
