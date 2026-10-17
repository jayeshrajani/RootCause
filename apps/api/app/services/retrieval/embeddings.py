"""Image embeddings shared by reference indexing and farmer queries (DINOv2 or Gemini).

Reference and query images must be embedded with the same model revision and preprocessing.
Vectors from different specs (e.g. DINOv2 vs Gemini Embedding 2) live in different spaces and
must never be compared; every index records its spec and refuses a mismatched embedder.
"""

import hashlib
import io
import os
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from app.services.retrieval.errors import (
    EmbeddingError,
    EmbeddingProviderError,
    InvalidQueryError,
    RetrievalError,
)

Vectors = NDArray[np.float32]

_RESIZE_SHORT_EDGE = 256
_CROP = 224
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True, slots=True)
class EmbeddingSpec:
    """Everything that must match for two vectors to be comparable."""

    model_id: str
    model_revision: str
    weights_sha256: str
    preprocessing_version: str
    dimension: int

    @property
    def slug(self) -> str:
        return self.model_id.rsplit("/", 1)[-1]


DINOV2_SMALL = EmbeddingSpec(
    model_id="facebook/dinov2-small",
    model_revision="ed25f3a31f01632728cabb09d1542f84ab7b0056",
    weights_sha256="ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1",
    preprocessing_version="exif-rgb-short256-bicubic-center224-imagenet-v1",
    dimension=384,
)

# Hosted model: no local weights, so there is no checksum to pin.
GEMINI_EMBEDDING_2 = EmbeddingSpec(
    model_id="google/gemini-embedding-2",
    model_revision="gemini-embedding-2",
    weights_sha256="",
    preprocessing_version="exif-rgb-max768-jpeg90-v1",
    dimension=768,
)

_GEMINI_MAX_EDGE = 768
_GEMINI_JPEG_QUALITY = 90


def default_model_dir(data_dir: Path, spec: EmbeddingSpec = DINOV2_SMALL) -> Path:
    return data_dir / "models" / spec.slug / spec.model_revision


class ImageEmbedder(Protocol):
    @property
    def spec(self) -> EmbeddingSpec: ...

    def embed(self, images: Sequence[bytes]) -> Vectors:
        """One L2-normalised float32 row per image, in input order."""
        ...


def preprocess(data: bytes) -> NDArray[np.float32]:
    """EXIF-orient, RGB, resize short edge to 256 (bicubic), centre-crop 224, ImageNet-normalise."""
    image = _open_rgb(data)
    width, height = image.size
    scale = _RESIZE_SHORT_EDGE / min(width, height)
    size = (max(_CROP, round(width * scale)), max(_CROP, round(height * scale)))
    image = image.resize(size, Image.Resampling.BICUBIC)
    left, top = (size[0] - _CROP) // 2, (size[1] - _CROP) // 2
    image = image.crop((left, top, left + _CROP, top + _CROP))
    pixels = (np.asarray(image, dtype=np.float32) / 255.0 - _MEAN) / _STD
    return np.ascontiguousarray(pixels.transpose(2, 0, 1), dtype=np.float32)


def prepare_jpeg(data: bytes) -> bytes:
    """EXIF-orient, RGB, shrink the long edge to at most 768 px, JPEG q90 (Gemini preprocessing).

    Gemini Embedding 2 accepts only PNG/JPEG; one consistent re-encode also keeps reference and
    query images comparable and request sizes small.
    """
    image = _open_rgb(data)
    image.thumbnail((_GEMINI_MAX_EDGE, _GEMINI_MAX_EDGE), Image.Resampling.BICUBIC)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_GEMINI_JPEG_QUALITY)
    return buffer.getvalue()


def _open_rgb(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            return ImageOps.exif_transpose(opened).convert("RGB")
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidQueryError(f"unreadable image ({type(exc).__name__})") from exc


def l2_normalize(vectors: NDArray[Any]) -> Vectors:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise EmbeddingError("embedding contains non-finite values")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise EmbeddingError("embedding has zero length")
    return np.asarray(matrix / norms, dtype=np.float32)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Dinov2Embedder:
    """CPU DINOv2 embedder. Load once per process and share; `embed` is thread-safe."""

    def __init__(
        self,
        model_dir: Path,
        *,
        spec: EmbeddingSpec = DINOV2_SMALL,
        batch_size: int = 16,
        verify_weights: bool = True,
    ) -> None:
        self._model_dir = model_dir
        self._spec = spec
        self._batch_size = batch_size
        self._verify_weights = verify_weights
        self._lock = threading.Lock()
        self._forward: Callable[[Any], Any] | None = None

    @property
    def spec(self) -> EmbeddingSpec:
        return self._spec

    @property
    def loaded(self) -> bool:
        return self._forward is not None

    def load(self) -> None:
        """Load weights from the local model directory. Never downloads."""
        with self._lock:
            if self._forward is not None:
                return
            weights = self._model_dir / "model.safetensors"
            if not weights.is_file():
                raise EmbeddingError(f"model weights not found in {self._model_dir}")
            if self._verify_weights and sha256_file(weights) != self._spec.weights_sha256:
                raise EmbeddingError("model weights do not match the pinned checksum")
            try:
                import torch
                from transformers import Dinov2Model

                model = Dinov2Model.from_pretrained(str(self._model_dir), local_files_only=True)
            except (ImportError, OSError, ValueError) as exc:
                raise EmbeddingError(f"could not load model ({type(exc).__name__})") from exc
            if int(model.config.hidden_size) != self._spec.dimension:
                raise EmbeddingError("model dimension does not match the embedding spec")
            model.eval()

            def forward(pixels: Any) -> Any:
                with torch.inference_mode():
                    return model(pixel_values=torch.from_numpy(pixels)).pooler_output.numpy()

            self._forward = forward

    def embed(self, images: Sequence[bytes]) -> Vectors:
        if not images:
            return np.empty((0, self._spec.dimension), dtype=np.float32)
        self.load()
        assert self._forward is not None
        pixels = np.stack([preprocess(data) for data in images])
        parts = [
            np.asarray(self._forward(pixels[start : start + self._batch_size]), dtype=np.float32)
            for start in range(0, len(pixels), self._batch_size)
        ]
        vectors = l2_normalize(np.concatenate(parts))
        if vectors.shape != (len(images), self._spec.dimension):
            raise EmbeddingError("unexpected embedding shape")
        return vectors


class MemoizedEmbedder:
    """Remembers recent vectors by image checksum, so a photo is embedded (and billed) once.

    Crop identification and triage both embed the same farmer photos; this halves those calls.
    """

    def __init__(self, inner: ImageEmbedder, *, max_items: int = 256) -> None:
        self._inner = inner
        self._max_items = max_items
        self._vectors: OrderedDict[str, NDArray[np.float32]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def spec(self) -> EmbeddingSpec:
        return self._inner.spec

    def embed(self, images: Sequence[bytes]) -> Vectors:
        keys = [hashlib.sha256(data).hexdigest() for data in images]
        with self._lock:
            known = {key: self._vectors[key] for key in keys if key in self._vectors}
            for key in known:
                self._vectors.move_to_end(key)
        missing = list(dict.fromkeys(key for key in keys if key not in known))
        if missing:
            by_key = dict(zip(keys, images, strict=True))
            fresh = self._inner.embed([by_key[key] for key in missing])
            with self._lock:
                for key, vector in zip(missing, fresh, strict=True):
                    known[key] = vector
                    self._vectors[key] = vector
                while len(self._vectors) > self._max_items:
                    self._vectors.popitem(last=False)
        if not keys:
            return np.empty((0, self.spec.dimension), dtype=np.float32)
        return np.stack([known[key] for key in keys]).astype(np.float32, copy=False)


class EmbeddingCache:
    """One .npy per image checksum, scoped by model revision and preprocessing version."""

    def __init__(self, root: Path, spec: EmbeddingSpec) -> None:
        self._spec = spec
        self.directory = root / spec.slug / spec.model_revision[:12] / spec.preprocessing_version

    def _path(self, sha256: str) -> Path:
        return self.directory / sha256[:2] / f"{sha256}.npy"

    def get(self, sha256: str) -> NDArray[np.float32] | None:
        path = self._path(sha256)
        if not path.is_file():
            return None
        try:
            vector = np.load(path, allow_pickle=False)
        except (OSError, ValueError):
            return None
        if (
            vector.shape != (self._spec.dimension,)
            or vector.dtype != np.float32
            or not np.all(np.isfinite(vector))
            or abs(float(np.linalg.norm(vector)) - 1.0) > 1e-3
        ):
            return None
        return np.asarray(vector, dtype=np.float32)

    def put(self, sha256: str, vector: NDArray[np.float32]) -> None:
        path = self._path(sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        np.save(buffer, np.asarray(vector, dtype=np.float32), allow_pickle=False)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(buffer.getvalue())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


@dataclass
class EmbedReport:
    cached: int = 0
    embedded: int = 0
    failed: dict[str, str] | None = None


def embed_with_cache(
    items: Sequence[tuple[str, str]],
    read: Callable[[str], bytes],
    embedder: ImageEmbedder,
    cache: EmbeddingCache,
    *,
    batch_size: int = 32,
    progress: Callable[[int, int], None] | None = None,
) -> EmbedReport:
    """Embed (item_id, sha256) pairs not yet cached. Each vector is checkpointed as it is made.

    `read(item_id)` returns image bytes; bytes whose SHA-256 differs from the expected value are
    recorded as failures, never embedded under the wrong key. An `EmbeddingProviderError` stops
    the run (re-running resumes from the cache); `progress(done, total)` follows new embeddings.
    """
    report = EmbedReport(failed={})
    assert report.failed is not None
    pending = []
    for item_id, sha256 in items:
        if cache.get(sha256) is not None:
            report.cached += 1
        else:
            pending.append((item_id, sha256))

    for start in range(0, len(pending), batch_size):
        batch: list[tuple[str, str, bytes]] = []
        for item_id, sha256 in pending[start : start + batch_size]:
            try:
                data = read(item_id)
            except OSError as exc:
                report.failed[item_id] = f"unreadable file ({type(exc).__name__})"
                continue
            if hashlib.sha256(data).hexdigest() != sha256:
                report.failed[item_id] = "file content changed since the manifest was built"
                continue
            batch.append((item_id, sha256, data))
        try:
            vectors = embedder.embed([data for _, _, data in batch])
            results = list(zip(batch, vectors, strict=True))
        except EmbeddingProviderError:
            raise
        except RetrievalError:
            results = []
            for item in batch:
                try:
                    results.append((item, embedder.embed([item[2]])[0]))
                except EmbeddingProviderError:
                    raise
                except RetrievalError as exc:
                    report.failed[item[0]] = str(exc)
        for (_, sha256, _), vector in results:
            cache.put(sha256, vector)
            report.embedded += 1
        if progress is not None:
            progress(report.embedded + len(report.failed), len(pending))
    return report
