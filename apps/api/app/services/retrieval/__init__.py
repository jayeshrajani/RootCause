"""Crop reference retrieval: DINOv2 embeddings + per-crop FAISS indexes.

Public API for the triage orchestrator; see docs/retrieval.md.
"""

from app.services.retrieval import _openmp  # noqa: F401  (must run before torch/faiss load)
from app.services.retrieval.errors import (
    EmbeddingError,
    IndexCompatibilityError,
    IndexUnavailableError,
    InvalidQueryError,
    ReferenceImageUnavailableError,
    RetrievalError,
    UnsupportedCropError,
)
from app.services.retrieval.reference_retriever import (
    SIMILARITY_NOTE,
    ReferenceMatch,
    ReferenceRetriever,
    RetrievalResult,
    get_reference_retriever,
    load_reference_retriever,
)

__all__ = [
    "SIMILARITY_NOTE",
    "EmbeddingError",
    "IndexCompatibilityError",
    "IndexUnavailableError",
    "InvalidQueryError",
    "ReferenceImageUnavailableError",
    "ReferenceMatch",
    "ReferenceRetriever",
    "RetrievalError",
    "RetrievalResult",
    "UnsupportedCropError",
    "get_reference_retriever",
    "load_reference_retriever",
]
