"""Crop-filtered reference retrieval for farmer photos. Library API for the triage orchestrator.

Similarity scores rank visual resemblance to labelled reference images. They are not
diagnostic probabilities and must not be shown as such.
"""

import asyncio
import threading
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.retrieval.dataset_registry import SupportedCrop, resolve_local_uri
from app.services.retrieval.embeddings import (
    DINOV2_SMALL,
    GEMINI_EMBEDDING_2,
    Dinov2Embedder,
    EmbeddingSpec,
    ImageEmbedder,
    MemoizedEmbedder,
    default_model_dir,
)
from app.services.retrieval.errors import (
    IndexCompatibilityError,
    IndexUnavailableError,
    InvalidQueryError,
    ReferenceImageUnavailableError,
    UnsupportedCropError,
)
from app.services.retrieval.faiss_index import ReferenceIndex, load_reference_index, spec_dict

MAX_QUERY_IMAGES = 3
MAX_TOP_K = 20
SIMILARITY_NOTE = (
    "Similarity ranks visual resemblance to labelled reference images. It is not a diagnostic "
    "probability."
)


class ReferenceMatch(BaseModel):
    reference_image_id: str
    crop_id: SupportedCrop
    disease_label: str
    source_label: str
    dataset_source: str
    image_uri: str
    image_style: str
    similarity_score: float
    query_image_index: int
    license: str
    attribution: str
    source_url: str


class RetrievalResult(BaseModel):
    crop_id: SupportedCrop
    retrieval_model: str
    model_revision: str
    preprocessing_version: str
    index_version: str
    top_k: int
    matches: list[ReferenceMatch]
    similarity_note: str = SIMILARITY_NOTE


class ReferenceRetriever:
    def __init__(
        self, embedder: ImageEmbedder, index: ReferenceIndex, *, data_dir: Path | None = None
    ) -> None:
        if index.manifest.embedding != spec_dict(embedder.spec):
            raise IndexCompatibilityError("index and embedder use different embedding specs")
        self._embedder = embedder
        self._index = index
        self._data_dir = data_dir

    @property
    def index_version(self) -> str:
        return self._index.version

    async def aretrieve(
        self, crop_id: str, images: Sequence[bytes], *, top_k: int = 5
    ) -> RetrievalResult:
        """`retrieve` in a worker thread, so CPU-bound embedding never blocks the event loop."""
        return await asyncio.to_thread(self.retrieve, crop_id, images, top_k=top_k)

    def crop_similarities(self, images: Sequence[bytes]) -> dict[str, float]:
        """Best similarity of the photos to each crop's library; embeds the photos once."""
        if not 1 <= len(images) <= MAX_QUERY_IMAGES:
            raise InvalidQueryError(f"provide 1-{MAX_QUERY_IMAGES} images")
        vectors = self._embedder.embed(list(images))
        best: dict[str, float] = {}
        for crop in SupportedCrop:
            try:
                crop_index = self._index.for_crop(crop)
            except IndexUnavailableError:
                continue
            scores, _ = crop_index.search(vectors, k=1)
            best[crop.value] = round(float(scores.max()), 4)
        return best

    def reference_image(self, match: ReferenceMatch) -> bytes:
        """Bytes of a matched reference image (e.g. to show Gemini alongside the farmer photos)."""
        if self._data_dir is None or not match.image_uri.startswith("local://"):
            raise ReferenceImageUnavailableError(f"cannot read {match.reference_image_id}")
        try:
            return resolve_local_uri(self._data_dir, match.image_uri).read_bytes()
        except (OSError, ValueError) as exc:
            raise ReferenceImageUnavailableError(f"cannot read {match.reference_image_id}") from exc

    def retrieve(self, crop_id: str, images: Sequence[bytes], *, top_k: int = 5) -> RetrievalResult:
        """Most similar reference images of `crop_id` across 1-3 query images (best score wins)."""
        try:
            crop = SupportedCrop(crop_id)
        except ValueError:
            raise UnsupportedCropError(f"no reference library for crop {crop_id!r}") from None
        if not 1 <= len(images) <= MAX_QUERY_IMAGES:
            raise InvalidQueryError(f"provide 1-{MAX_QUERY_IMAGES} images")
        if not 1 <= top_k <= MAX_TOP_K:
            raise InvalidQueryError(f"top_k must be between 1 and {MAX_TOP_K}")

        crop_index = self._index.for_crop(crop)
        vectors = self._embedder.embed(list(images))
        scores, rows = crop_index.search(vectors, k=top_k * MAX_QUERY_IMAGES)
        best: dict[int, tuple[float, int]] = {}
        for query, (score_row, index_row) in enumerate(zip(scores, rows, strict=True)):
            for score, row in zip(score_row.tolist(), index_row.tolist(), strict=True):
                if row >= 0 and (row not in best or score > best[row][0]):
                    best[row] = (score, query)
        ranked = sorted(best.items(), key=lambda item: (-item[1][0], item[0]))[:top_k]

        spec = self._embedder.spec
        return RetrievalResult(
            crop_id=crop,
            retrieval_model=spec.model_id,
            model_revision=spec.model_revision,
            preprocessing_version=spec.preprocessing_version,
            index_version=self._index.version,
            top_k=top_k,
            matches=[
                ReferenceMatch(
                    reference_image_id=meta.reference_id,
                    crop_id=meta.crop,
                    disease_label=meta.condition,
                    source_label=meta.source_label,
                    dataset_source=meta.dataset_source,
                    image_uri=meta.image_uri,
                    image_style=meta.image_style,
                    similarity_score=round(score, 4),
                    query_image_index=query,
                    license=meta.license,
                    attribution=meta.attribution,
                    source_url=meta.source_url,
                )
                for row, (score, query) in ranked
                for meta in (crop_index.metadata[row],)
            ],
        )


def embedding_spec(settings: Settings) -> EmbeddingSpec:
    return GEMINI_EMBEDDING_2 if settings.retrieval_embedder == "gemini" else DINOV2_SMALL


def index_root(settings: Settings, data_dir: Path | None = None) -> Path:
    """Folder holding index versions for the configured embedder (one subfolder per model)."""
    root = settings.retrieval_index_dir
    base = data_dir or settings.data_dir
    if root is None and base is not None:
        root = base / "artifacts" / "faiss" / embedding_spec(settings).slug
    if root is None:
        raise IndexUnavailableError("set ROOTCAUSE_RETRIEVAL_INDEX_DIR or ROOTCAUSE_DATA_DIR")
    return root


def create_embedder(settings: Settings, data_dir: Path | None = None) -> ImageEmbedder:
    """The configured embedder. DINOv2 is returned unloaded; call `load()` before use."""
    if settings.retrieval_embedder == "gemini":
        from app.services.retrieval.gemini_embedder import GeminiImageEmbedder

        if settings.gemini_api_key is None:
            raise IndexUnavailableError("GEMINI_API_KEY is required for Gemini embeddings")
        return GeminiImageEmbedder(
            settings.gemini_api_key.get_secret_value(),
            timeout_seconds=settings.retrieval_embedding_timeout_seconds,
        )
    model_dir = settings.embedding_model_dir
    base = data_dir or settings.data_dir
    if model_dir is None:
        if base is None:
            raise IndexUnavailableError("set ROOTCAUSE_EMBEDDING_MODEL_DIR or ROOTCAUSE_DATA_DIR")
        model_dir = default_model_dir(base)
    return Dinov2Embedder(model_dir)


def load_reference_retriever(settings: Settings) -> ReferenceRetriever:
    """Build the process-wide retriever from settings. Loads the model and verifies the index."""
    if settings.retrieval_index_version is None:
        raise IndexUnavailableError("ROOTCAUSE_RETRIEVAL_INDEX_VERSION is not set")
    embedder = create_embedder(settings)
    index = load_reference_index(
        index_root(settings) / settings.retrieval_index_version, embedder.spec
    )
    if isinstance(embedder, Dinov2Embedder):
        embedder.load()
    else:
        # Hosted embeddings are billed per call; identification and triage reuse the vectors.
        embedder = MemoizedEmbedder(embedder)
    return ReferenceRetriever(embedder, index, data_dir=settings.data_dir)


_retriever: ReferenceRetriever | None = None
_retriever_lock = threading.Lock()


def get_reference_retriever() -> ReferenceRetriever:
    """Process-wide retriever, built on first use. Usable as a FastAPI dependency.

    Raises a `RetrievalError` subclass when retrieval is not configured or the index is unusable;
    callers can fall back to image-only analysis.
    """
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                _retriever = load_reference_retriever(get_settings())
    return _retriever
