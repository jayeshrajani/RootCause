"""Gemini text-to-speech: reads a triage summary aloud as a WAV clip.

Gemini TTS returns 24 kHz mono 16-bit audio, already wrapped as WAV by current models (raw PCM is
wrapped here if not). Nothing is stored; text and audio live only for the request.
"""

import asyncio
import base64
import io
import logging
import ssl
import time
import wave
from collections.abc import Sequence

import httpx
import truststore

logger = logging.getLogger(__name__)

PCM_RATE = 24_000
_RETRY_STATUSES = (429, 500, 503)


class SpeechSynthesisError(Exception):
    """Every model failed. The message is safe to log."""


def _as_wav(data: bytes) -> bytes:
    if data.startswith(b"RIFF"):
        return data
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(PCM_RATE)
        out.writeframes(data)
    return buffer.getvalue()


class GeminiSpeechSynthesizer:
    def __init__(
        self,
        *,
        api_keys: Sequence[str],
        models: Sequence[str] = ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"),
        voice: str = "Kore",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.models = list(models)
        self._api_keys = list(api_keys)
        self._voice = voice
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self._retry_delay = 1.0

    async def synthesize(self, text: str) -> bytes:
        """WAV audio for `text`, spoken in whatever language it is written in."""
        body = {
            # Only the words to speak: TTS models read any style instruction aloud too.
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._voice}}
                },
            },
        }
        last = "no model configured"
        # Every model on the priority key, then every model on the fallback key.
        attempts = [
            (number, key, model)
            for number, key in enumerate(self._api_keys, start=1)
            for model in self.models
        ]
        for index, (key_number, api_key, model) in enumerate(attempts):
            for attempt in range(2):
                if attempt:
                    await asyncio.sleep(self._retry_delay)
                started = time.perf_counter()
                try:
                    async with httpx.AsyncClient(
                        timeout=self._timeout,
                        transport=self._transport,
                        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                    ) as client:
                        response = await client.post(
                            f"{self._base_url}/models/{model}:generateContent",
                            headers={"x-goog-api-key": api_key},
                            json=body,
                        )
                except httpx.HTTPError as exc:
                    last = f"key {key_number} {model}: {type(exc).__name__}"
                    break
                if response.status_code == 200:
                    try:
                        part = response.json()["candidates"][0]["content"]["parts"][0]
                        audio = base64.b64decode(part["inlineData"]["data"])
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        last = (
                            f"key {key_number} {model}: unexpected payload ({type(exc).__name__})"
                        )
                        break
                    logger.info(
                        "Gemini TTS key=%d model=%s characters=%d audio_bytes=%d elapsed_ms=%d",
                        key_number,
                        model,
                        len(text),
                        len(audio),
                        (time.perf_counter() - started) * 1000,
                    )
                    return _as_wav(audio)
                last = f"key {key_number} {model}: HTTP {response.status_code}"
                if response.status_code not in _RETRY_STATUSES:
                    break
            if index < len(attempts) - 1:
                logger.warning("Gemini TTS failed, trying the next model or key: %s", last)
        raise SpeechSynthesisError(last)
