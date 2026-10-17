"""Provider-neutral contract for multimodal models that return JSON under a schema."""

import base64
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class VisionModelError(Exception):
    """The model call failed or returned unusable output. Message is safe to log."""


def provider_error_detail(response: httpx.Response, limit: int = 300) -> str:
    """The provider's own error reason (status and message), shortened for logs."""
    try:
        error = response.json().get("error")
    except ValueError:
        return ""
    if isinstance(error, dict):
        parts = [str(error.get(key)) for key in ("status", "type", "message") if error.get(key)]
        detail = ": ".join(parts)
    else:
        detail = str(error or "")
    detail = " ".join(detail.split())
    return detail if len(detail) <= limit else detail[: limit - 1] + "…"


@dataclass(frozen=True, slots=True)
class ImageInput:
    media_type: str
    data: bytes

    def as_data_url(self) -> str:
        return f"data:{self.media_type};base64,{base64.b64encode(self.data).decode()}"


class VisionModel(Protocol):
    @property
    def model(self) -> str: ...

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
        """Raw JSON text conforming to `schema`; raises VisionModelError on any failure."""
        ...


class FallbackVisionModel:
    def __init__(
        self,
        primary: VisionModel,
        fallback: VisionModel,
        *,
        fallback_on: type[VisionModelError] | tuple[type[VisionModelError], ...] | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallback_on = fallback_on
        self._active = primary

    @property
    def provider_label(self) -> str:
        return getattr(self._active, "provider_label", "AI")

    @property
    def model(self) -> str:
        return self._active.model

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
        try:
            result = await self._primary.structured_completion(
                system=system,
                text=text,
                images=images,
                schema_name=schema_name,
                schema=schema,
                max_tokens=max_tokens,
            )
        except VisionModelError as primary_error:
            if self._fallback_on is not None and not isinstance(primary_error, self._fallback_on):
                raise
            logging.getLogger(__name__).warning(
                "Primary vision provider %s failed (%s); trying %s",
                getattr(self._primary, "provider_label", "AI"),
                primary_error,
                getattr(self._fallback, "provider_label", "AI"),
            )
            try:
                result = await self._fallback.structured_completion(
                    system=system,
                    text=text,
                    images=images,
                    schema_name=schema_name,
                    schema=schema,
                    max_tokens=max_tokens,
                )
            except VisionModelError as fallback_error:
                self._active = self._fallback
                raise fallback_error from primary_error
            self._active = self._fallback
            return result

        self._active = self._primary
        return result
