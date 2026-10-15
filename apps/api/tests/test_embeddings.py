import hashlib
import io
import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.retrieval.embeddings import (
    DINOV2_SMALL,
    Dinov2Embedder,
    EmbeddingCache,
    EmbeddingSpec,
    Vectors,
    default_model_dir,
    embed_with_cache,
    l2_normalize,
    preprocess,
)
from app.services.retrieval.errors import EmbeddingError, InvalidQueryError

SPEC = EmbeddingSpec("test/model", "rev", "0" * 64, "test-v1", 4)


def png(
    seed: int, size: tuple[int, int] = (300, 200), exif_orientation: int | None = None
) -> bytes:
    rng = np.random.default_rng(seed)
    image = Image.fromarray(rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8))
    buffer = io.BytesIO()
    if exif_orientation is None:
        image.save(buffer, format="PNG")
    else:
        exif = image.getexif()
        exif[0x0112] = exif_orientation
        image.save(buffer, format="PNG", exif=exif.tobytes())
    return buffer.getvalue()


class FakeEmbedder:
    def __init__(self, fail_on: bytes | None = None) -> None:
        self.calls = 0
        self._fail_on = fail_on

    @property
    def spec(self) -> EmbeddingSpec:
        return SPEC

    def embed(self, images: Sequence[bytes]) -> Vectors:
        self.calls += 1
        if self._fail_on is not None and self._fail_on in images:
            raise InvalidQueryError("unreadable image (test)")
        rows = [
            np.frombuffer(hashlib.sha256(d).digest()[:16], dtype=np.uint8)[:4] + 1.0 for d in images
        ]
        return l2_normalize(np.array(rows))


def test_preprocess_produces_normalised_224_crop() -> None:
    pixels = preprocess(png(1))

    assert pixels.shape == (3, 224, 224) and pixels.dtype == np.float32
    assert float(pixels.min()) > -3 and float(pixels.max()) < 3


def test_preprocess_applies_exif_orientation() -> None:
    rotated = Image.open(io.BytesIO(png(2))).transpose(Image.Transpose.ROTATE_270)
    buffer = io.BytesIO()
    rotated.save(buffer, format="PNG")

    assert np.array_equal(preprocess(png(2, exif_orientation=6)), preprocess(buffer.getvalue()))


def test_preprocess_rejects_unreadable_bytes() -> None:
    with pytest.raises(InvalidQueryError):
        preprocess(b"not an image")


def test_l2_normalize_yields_unit_vectors_and_rejects_bad_input() -> None:
    vectors = l2_normalize(np.array([[3.0, 4.0], [1.0, 0.0]]))

    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert vectors.dtype == np.float32
    for bad in (np.array([[0.0, 0.0]]), np.array([[np.nan, 1.0]])):
        with pytest.raises(EmbeddingError):
            l2_normalize(bad)


def test_cache_round_trip_and_rejects_corrupt_entries(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path, SPEC)
    vector = l2_normalize(np.array([[1.0, 2.0, 3.0, 4.0]]))[0]
    sha = "ab" * 32

    cache.put(sha, vector)
    cached = cache.get(sha)

    assert cached is not None and np.array_equal(cached, vector)
    path = next(cache.directory.rglob(f"{sha}.npy"))
    path.write_bytes(b"corrupt")
    assert cache.get(sha) is None
    assert cache.get("cd" * 32) is None


def test_cache_is_scoped_by_model_and_preprocessing(tmp_path: Path) -> None:
    other = EmbeddingSpec("test/model", "rev", "0" * 64, "test-v2", 4)

    assert EmbeddingCache(tmp_path, SPEC).directory != EmbeddingCache(tmp_path, other).directory


def test_embed_with_cache_is_resumable_and_skips_bad_items(tmp_path: Path) -> None:
    images = {f"img{i}": png(i, (64, 64)) for i in range(5)}
    bad = b"definitely not an image"
    images["bad"] = bad
    items = [(k, hashlib.sha256(v).hexdigest()) for k, v in images.items()]
    items.append(("changed", "0" * 64))
    images["changed"] = png(99, (64, 64))
    cache = EmbeddingCache(tmp_path, SPEC)
    embedder = FakeEmbedder(fail_on=bad)

    first = embed_with_cache(items, images.__getitem__, embedder, cache, batch_size=3)
    calls_after_first = embedder.calls
    second = embed_with_cache(items, images.__getitem__, embedder, cache, batch_size=3)

    assert (first.embedded, first.cached) == (5, 0)
    assert set(first.failed or {}) == {"bad", "changed"}
    assert (second.embedded, second.cached) == (0, 5)
    assert set(second.failed or {}) == {"bad", "changed"}
    # Only the unreadable image is retried: once in its batch, then on its own.
    assert embedder.calls == calls_after_first + 2


def test_embedder_refuses_missing_or_unverified_weights(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingError, match="not found"):
        Dinov2Embedder(tmp_path).load()

    (tmp_path / "model.safetensors").write_bytes(b"not the pinned weights")
    with pytest.raises(EmbeddingError, match="checksum"):
        Dinov2Embedder(tmp_path).load()


def _model_dir() -> Path | None:
    configured = os.environ.get("ROOTCAUSE_EMBEDDING_MODEL_DIR")
    data_dir = os.environ.get("ROOTCAUSE_DATA_DIR")
    path = (
        Path(configured) if configured else default_model_dir(Path(data_dir)) if data_dir else None
    )
    return path if path and (path / "model.safetensors").is_file() else None


@pytest.fixture(scope="module")
def dinov2() -> Dinov2Embedder:
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    model_dir = _model_dir()
    if model_dir is None:
        pytest.skip("DINOv2 weights not available (set ROOTCAUSE_DATA_DIR)")
    embedder = Dinov2Embedder(model_dir)
    embedder.load()
    return embedder


def test_dinov2_outputs_deterministic_unit_384d_vectors(dinov2: Dinov2Embedder) -> None:
    images = [png(1), png(2)]

    first = dinov2.embed(images)
    second = dinov2.embed(images)

    assert first.shape == (2, DINOV2_SMALL.dimension) and first.dtype == np.float32
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0, atol=1e-5)
    assert np.allclose(first, second, atol=1e-6)
    assert float(first[0] @ first[1]) < 0.999
