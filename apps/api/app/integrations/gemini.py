"""Gemini generateContent client for image + text analysis."""

import base64
import logging
import ssl
import time
from typing import Any

import httpx
import truststore

from app.integrations.vision import ImageInput, VisionModelError

__all__ = ["GeminiClient", "GeminiError", "ImageInput"]

logger = logging.getLogger(__name__)


class GeminiError(VisionModelError):
    """The model call failed or returned unusable output. Message is safe to log."""


class GeminiRateLimitError(GeminiError):
    """Gemini rejected the request because a rate or quota limit was reached."""


class GeminiClient:
    provider_label = "Gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 45,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    async def structured_completion(
        self,
        *,
        system: str,
        text: str,
        images: list[ImageInput],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int = 6000,
    ) -> str:
        """Return the raw JSON string produced under the given JSON schema."""
        parts: list[dict[str, Any]] = [{"text": text}]
        parts.extend(
            {
                "inlineData": {
                    "mimeType": image.media_type,
                    "data": base64.b64encode(image.data).decode("ascii"),
                }
            }
            for image in images
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "maxOutputTokens": max_tokens,
            },
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                response = await client.post(
                    f"{self._base_url}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self._api_key},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise GeminiError("Model request timed out") from exc
        except httpx.HTTPError as exc:
            raise GeminiError(f"Model request failed: {type(exc).__name__}") from exc

        if response.status_code == 429:
            raise GeminiRateLimitError("Model API rate limit exceeded (HTTP 429)")
        if response.status_code != 200:
            raise GeminiError(f"Model API returned HTTP {response.status_code}")

        try:
            payload = response.json()
            candidate = payload["candidates"][0]
            output = "".join(
                part.get("text", "")
                for part in candidate["content"]["parts"]
                if isinstance(part, dict)
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GeminiError("Model API returned an unexpected payload") from exc

        if candidate.get("finishReason") in ("MAX_TOKENS", "CONTINUATION") or not output.strip():
            raise GeminiError("Model output was empty or truncated")

        usage = payload.get("usageMetadata") or {}
        logger.info(
            "Gemini completion model=%s images=%d prompt_tokens=%s candidate_tokens=%s "
            "elapsed_ms=%d",
            self.model,
            len(images),
            usage.get("promptTokenCount"),
            usage.get("candidatesTokenCount"),
            (time.perf_counter() - started) * 1000,
        )
        return output
