"""Errors raised by the crop reference retrieval engine. Messages are safe to log."""


class RetrievalError(RuntimeError):
    """Base class for retrieval failures callers can handle explicitly."""


class UnsupportedCropError(RetrievalError):
    """The crop has no reference library (only rice, tomato and potato are supported)."""


class InvalidQueryError(RetrievalError):
    """The query images are missing, too many, or unreadable."""


class EmbeddingError(RetrievalError):
    """The embedding model is unavailable or produced an unusable vector."""


class EmbeddingProviderError(EmbeddingError):
    """A hosted embedding API refused or kept failing (key, billing, quota, outage).

    Retrying image by image would not help, so batch jobs stop and keep their cached progress.
    """


class IndexUnavailableError(RetrievalError):
    """No usable index exists for the requested version or crop."""


class IndexCompatibilityError(RetrievalError):
    """Index artifacts are corrupt, stale, or built with a different embedding configuration."""


class ReferenceImageUnavailableError(RetrievalError):
    """A matched reference image cannot be read from its stored location."""
