"""Reference-photo evidence for triage: labelled public photos that look most like the farmer's.

The similarity search (DINOv2 + FAISS, app/services/retrieval) ranks visual resemblance only.
Here it becomes a vote over condition labels, used as one bounded input to evidence-fit scores.
"""

import logging
import threading
from collections import Counter
from collections.abc import Sequence
from typing import Literal, Protocol

from app.core.config import Settings
from app.models.references import ReferenceVotes
from app.services.retrieval import (
    ReferenceRetriever,
    RetrievalError,
    RetrievalResult,
    load_reference_retriever,
)
from app.services.retrieval.dataset_registry import CONDITIONS, SupportedCrop, label_key

logger = logging.getLogger(__name__)

ReferenceStatus = Literal["disabled", "loading", "ready", "failed"]
SUPPORTED_CROPS = tuple(crop.value for crop in SupportedCrop)
TOP_K = 10
# Held-out field photos score >= 0.45 against their best reference; blank or noise images <= 0.21.
MIN_SIMILARITY = 0.35


class ReferenceUnavailableError(Exception):
    """References cannot be used for this report. The message is safe to show and log."""


class ReferenceProvider(Protocol):
    @property
    def status(self) -> ReferenceStatus: ...

    async def find(self, crop: str, images: Sequence[bytes]) -> ReferenceVotes: ...


def reference_labels(crop: str) -> tuple[str, ...]:
    """Condition labels in the reference library for `crop`; empty when the crop is not covered."""
    try:
        return CONDITIONS[SupportedCrop(crop)]
    except ValueError:
        return ()


def match_label(raw: str, crop: str) -> str | None:
    """The library label the model picked for a cause, or None for "none" or anything unknown."""
    key = label_key(raw)
    return next((label for label in reference_labels(crop) if label_key(label) == key), None)


def votes_from(
    result: RetrievalResult, *, min_similarity: float = MIN_SIMILARITY
) -> ReferenceVotes:
    if not result.matches:
        raise ReferenceUnavailableError("No reference photos were returned for this crop.")
    best = result.matches[0].similarity_score
    if best < min_similarity:
        raise ReferenceUnavailableError(
            "The photos did not closely resemble any labelled reference photo."
        )
    counts = Counter(match.disease_label for match in result.matches)
    return ReferenceVotes(
        crop=result.crop_id.value,
        index_version=result.index_version,
        total=len(result.matches),
        counts=tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        best_similarity=best,
    )


class RetrievalReferenceProvider:
    """Loads the reference library once in a background thread; never blocks or fails a triage."""

    def __init__(
        self,
        settings: Settings,
        *,
        top_k: int = TOP_K,
        min_similarity: float = MIN_SIMILARITY,
    ) -> None:
        self._settings = settings
        self._top_k = top_k
        self._min_similarity = min_similarity
        self._retriever: ReferenceRetriever | None = None
        self._failed = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def status(self) -> ReferenceStatus:
        if self._retriever is not None:
            return "ready"
        return "failed" if self._failed else "loading"

    def start_loading(self) -> None:
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self.load, name="reference-library", daemon=True
                )
                self._thread.start()

    def load(self) -> None:
        """Load the model and index (blocking). Failures are logged and reported by `status`."""
        try:
            retriever = load_reference_retriever(self._settings)
        # torch/faiss import and runtime errors are not RetrievalErrors; none may crash startup.
        except Exception as exc:
            self._failed = True
            logger.warning("Reference library unavailable: %s: %s", type(exc).__name__, exc)
            return
        self._retriever = retriever
        logger.info("Reference library ready (index %s)", retriever.index_version)

    async def find(self, crop: str, images: Sequence[bytes]) -> ReferenceVotes:
        retriever = self._retriever
        if retriever is None:
            raise ReferenceUnavailableError(
                "The reference photo library is unavailable."
                if self._failed
                else "The reference photo library is still loading."
            )
        try:
            result = await retriever.aretrieve(crop, images, top_k=self._top_k)
        except RetrievalError as exc:
            logger.warning("Reference retrieval failed: %s", exc)
            raise ReferenceUnavailableError(
                "Reference photos could not be compared for this report."
            ) from exc
        return votes_from(result, min_similarity=self._min_similarity)
