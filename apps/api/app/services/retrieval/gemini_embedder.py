"""Gemini Embedding 2 image embeddings through the Gemini API (`batchEmbedContents`).

Each image is its own request inside a batch call, so every image gets its own vector. Reference
indexes and farmer queries must both use this embedder (same spec) to be comparable.
"""

import base64
import logging
import random
import ssl
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import numpy as np
import truststore

from app.integrations.vision import provider_error_detail
from app.services.retrieval.embeddings import (
    GEMINI_EMBEDDING_2,
    EmbeddingSpec,
    Vectors,
    l2_normalize,
    prepare_jpeg,
)
from app.services.retrieval.errors import EmbeddingError, EmbeddingProviderError

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Gemini Embedding 2 accepts at most 6 images per request.
MAX_IMAGES_PER_CALL = 6
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GeminiImageEmbedder:
    """Thread-safe; holds no connection state, so one instance can serve the whole process."""

    def __init__(
        self,
        api_key: str,
        *,
        spec: EmbeddingSpec = GEMINI_EMBEDDING_2,
        base_url: str = GEMINI_API_BASE,
        timeout_seconds: float = 30,
        max_attempts: int = 4,
        max_backoff_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise EmbeddingProviderError("GEMINI_API_KEY is not set")
        self._api_key = api_key
        self._spec = spec
        self._model = spec.model_id.rsplit("/", 1)[-1]
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._max_backoff = max_backoff_seconds
        self._transport = transport
        self._sleep = sleep

    @property
    def spec(self) -> EmbeddingSpec:
        return self._spec

    def embed(self, images: Sequence[bytes]) -> Vectors:
        if not images:
            return np.empty((0, self._spec.dimension), dtype=np.float32)
        prepared = [prepare_jpeg(data) for data in images]
        parts = [
            self._embed_call(prepared[start : start + MAX_IMAGES_PER_CALL])
            for start in range(0, len(prepared), MAX_IMAGES_PER_CALL)
        ]
        vectors = l2_normalize(np.concatenate(parts))
        if vectors.shape != (len(images), self._spec.dimension):
            raise EmbeddingError("unexpected embedding shape")
        return vectors

    def _embed_call(self, jpegs: Sequence[bytes]) -> Vectors:
        model = f"models/{self._model}"
        body = {
            "requests": [
                {
                    "model": model,
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": base64.b64encode(jpeg).decode("ascii"),
                                }
                            }
                        ]
                    },
                    "embedContentConfig": {"outputDimensionality": self._spec.dimension},
                }
                for jpeg in jpegs
            ]
        }
        payload = self._post(f"{self._base_url}/{model}:batchEmbedContents", body)
        try:
            rows = [item["values"] for item in payload["embeddings"]]
            matrix = np.asarray(rows, dtype=np.float32)
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Gemini returned an unexpected embedding payload") from exc
        if matrix.shape != (len(jpegs), self._spec.dimension):
            raise EmbeddingError(
                f"Gemini returned {matrix.shape} embeddings, expected "
                f"({len(jpegs)}, {self._spec.dimension})"
            )
        tokens = (payload.get("usageMetadata") or {}).get("promptTokenCount")
        logger.info("Gemini embedding images=%d prompt_tokens=%s", len(jpegs), tokens)
        return matrix

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        last_error = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(
                    timeout=self._timeout,
                    transport=self._transport,
                    verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                ) as client:
                    response = client.post(
                        url, headers={"x-goog-api-key": self._api_key}, json=body
                    )
            except httpx.HTTPError as exc:
                last_error = f"request failed ({type(exc).__name__})"
                retry_after = None
            else:
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise EmbeddingError("Gemini returned invalid JSON") from exc
                    if not isinstance(payload, dict):
                        raise EmbeddingError("Gemini returned an unexpected embedding payload")
                    return payload
                detail = provider_error_detail(response)
                last_error = f"HTTP {response.status_code}" + (f" ({detail})" if detail else "")
                if response.status_code not in _RETRYABLE_STATUS:
                    raise EmbeddingProviderError(f"Gemini embedding failed: {last_error}")
                retry_after = _retry_after_seconds(response)
            if attempt < self._max_attempts:
                delay = retry_after if retry_after is not None else self._backoff(attempt)
                logger.warning(
                    "Gemini embedding attempt %d/%d failed: %s; retrying in %.1f s",
                    attempt,
                    self._max_attempts,
                    last_error,
                    delay,
                )
                self._sleep(delay)
        raise EmbeddingProviderError(f"Gemini embedding failed: {last_error}")

    def _backoff(self, attempt: int) -> float:
        base: float = min(self._max_backoff, 2.0**attempt)
        return base * random.uniform(0.75, 1.25)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return min(60.0, max(0.0, float(value))) if value is not None else None
    except ValueError:
        return None
