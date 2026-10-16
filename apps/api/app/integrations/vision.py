"""Provider-neutral contract for multimodal models that return JSON under a schema."""

import base64
from dataclasses import dataclass
from typing import Any, Protocol


class VisionModelError(Exception):
    """The model call failed or returned unusable output. Message is safe to log."""


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
