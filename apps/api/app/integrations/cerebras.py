"""Cerebras chat-completions client (OpenAI-compatible) used for image + text analysis."""

import logging
import ssl
import time
from typing import Any

import httpx
import truststore

from app.integrations.vision import ImageInput, VisionModelError

__all__ = ["CerebrasClient", "CerebrasError", "ImageInput"]

logger = logging.getLogger(__name__)


class CerebrasError(VisionModelError):
    """The model call failed or returned unusable output. Message is safe to log."""


class CerebrasClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.cerebras.ai/v1",
        timeout_seconds: float = 45,
        reasoning_effort: str = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._reasoning_effort = reasoning_effort
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
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        content += [
            {"type": "image_url", "image_url": {"url": img.as_data_url()}} for img in images
        ]
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "reasoning_effort": self._reasoning_effort,
            "max_completion_tokens": max_tokens,
            "temperature": 0.2,
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise CerebrasError("Model request timed out") from exc
        except httpx.HTTPError as exc:
            raise CerebrasError(f"Model request failed: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise CerebrasError(f"Model API returned HTTP {response.status_code}")

        try:
            payload = response.json()
            choice = payload["choices"][0]
            output = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise CerebrasError("Model API returned an unexpected payload") from exc

        if choice.get("finish_reason") == "length" or not output.strip():
            raise CerebrasError("Model output was empty or truncated")

        usage = payload.get("usage") or {}
        logger.info(
            "Cerebras completion model=%s images=%d prompt_tokens=%s completion_tokens=%s "
            "elapsed_ms=%d",
            self.model,
            len(images),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            (time.perf_counter() - started) * 1000,
        )
        return str(output)
