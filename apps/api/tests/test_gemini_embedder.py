import hashlib
import io
import json
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image
from pydantic import SecretStr

from app.core.config import Settings
from app.services.retrieval.dataset_registry import SupportedCrop
from app.services.retrieval.embeddings import (
    GEMINI_EMBEDDING_2,
    EmbeddingCache,
    MemoizedEmbedder,
    Vectors,
    embed_with_cache,
    prepare_jpeg,
)
from app.services.retrieval.errors import (
    EmbeddingError,
    EmbeddingProviderError,
    IndexUnavailableError,
    InvalidQueryError,
)
from app.services.retrieval.gemini_embedder import GeminiImageEmbedder
from app.services.retrieval.reference_retriever import (
    create_embedder,
    index_root,
    load_reference_retriever,
)

DIM = GEMINI_EMBEDDING_2.dimension
Handler = Callable[[httpx.Request], httpx.Response]


def image_bytes(
    color: tuple[int, int, int], size: tuple[int, int] = (64, 48), fmt: str = "PNG"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def ok(count: int, *, dim: int = DIM) -> httpx.Response:
    rows = [[float(i + 1)] + [0.0] * (dim - 1) for i in range(count)]
    return httpx.Response(
        200,
        json={
            "embeddings": [{"values": row} for row in rows],
            "usageMetadata": {"promptTokenCount": 258 * count},
        },
    )


def embedder(
    handler: Handler, sleeps: list[float] | None = None, *, max_attempts: int = 4
) -> GeminiImageEmbedder:
    return GeminiImageEmbedder(
        "test-key",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append if sleeps is not None else lambda _: None,
        max_attempts=max_attempts,
    )


def test_sends_one_request_per_image_in_batches_of_six() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return ok(len(json.loads(request.content)["requests"]))

    images = [image_bytes((i * 20, 100, 50)) for i in range(8)]
    vectors = embedder(handler).embed(images)

    assert vectors.shape == (8, DIM) and vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert [len(json.loads(r.content)["requests"]) for r in sent] == [6, 2]
    first = sent[0]
    assert first.url.path == "/v1beta/models/gemini-embedding-2:batchEmbedContents"
    assert first.headers["x-goog-api-key"] == "test-key"
    request = json.loads(first.content)["requests"][0]
    assert request["model"] == "models/gemini-embedding-2"
    assert request["embedContentConfig"] == {"outputDimensionality": DIM}
    (part,) = request["content"]["parts"]
    assert part["inlineData"]["mimeType"] == "image/jpeg"
    assert "test-key" not in first.content.decode()


def test_images_are_reencoded_as_small_jpegs() -> None:
    webp = image_bytes((10, 200, 10), size=(2000, 1000), fmt="WEBP")

    jpeg = prepare_jpeg(webp)

    assert jpeg.startswith(b"\xff\xd8")
    with Image.open(io.BytesIO(jpeg)) as opened:
        assert opened.size == (768, 384)
    with pytest.raises(InvalidQueryError):
        prepare_jpeg(b"not an image")


def test_rate_limits_are_retried_with_backoff() -> None:
    responses = [httpx.Response(429, headers={"retry-after": "2"}), httpx.Response(503), ok(1)]
    sleeps: list[float] = []

    vectors = embedder(lambda _: responses.pop(0), sleeps).embed([image_bytes((1, 2, 3))])

    assert vectors.shape == (1, DIM)
    assert sleeps[0] == 2.0 and len(sleeps) == 2


def test_billing_errors_stop_immediately_with_the_reason() -> None:
    calls: list[int] = []
    body = {"error": {"status": "RESOURCE_EXHAUSTED", "message": "prepayment credits are depleted"}}

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(402, json=body)

    with pytest.raises(EmbeddingProviderError, match="HTTP 402 .*credits are depleted"):
        embedder(handler).embed([image_bytes((1, 2, 3))])
    assert len(calls) == 1


def test_persistent_outage_gives_up_after_max_attempts() -> None:
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(EmbeddingProviderError, match="HTTP 503"):
        embedder(handler, max_attempts=3).embed([image_bytes((1, 2, 3))])
    assert len(calls) == 3


def test_wrong_vector_size_is_rejected() -> None:
    with pytest.raises(EmbeddingError, match="expected"):
        embedder(lambda _: ok(1, dim=3072)).embed([image_bytes((1, 2, 3))])


def test_missing_key_is_rejected() -> None:
    with pytest.raises(EmbeddingProviderError):
        GeminiImageEmbedder("")


class CountingEmbedder:
    spec = GEMINI_EMBEDDING_2

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.calls: list[int] = []
        self._fail_after = fail_after

    def embed(self, images: Sequence[bytes]) -> Vectors:
        if self._fail_after is not None and len(self.calls) >= self._fail_after:
            raise EmbeddingProviderError("HTTP 402")
        self.calls.append(len(images))
        rows = np.zeros((len(images), DIM), dtype=np.float32)
        for i, data in enumerate(images):
            rows[i, data[0] % DIM] = 1.0
        return rows


def test_memoized_embedder_never_pays_twice_for_the_same_photo() -> None:
    inner = CountingEmbedder()
    memo = MemoizedEmbedder(inner, max_items=2)

    first = memo.embed([b"\x01a", b"\x02b", b"\x01a"])
    again = memo.embed([b"\x02b", b"\x01a"])

    assert inner.calls == [2]
    assert np.array_equal(first[0], first[2]) and np.array_equal(again[1], first[0])
    memo.embed([b"\x03c"])
    memo.embed([b"\x01a", b"\x02b"])
    assert inner.calls == [2, 1, 1]


def test_batch_job_stops_on_provider_error_and_resumes_from_cache(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path, GEMINI_EMBEDDING_2)
    data = {f"img{i}": bytes([i + 1]) * 8 for i in range(4)}
    items = [(item_id, hashlib.sha256(blob).hexdigest()) for item_id, blob in data.items()]

    with pytest.raises(EmbeddingProviderError):
        embed_with_cache(
            items, data.__getitem__, CountingEmbedder(fail_after=1), cache, batch_size=2
        )
    assert [cache.get(sha) is not None for _, sha in items] == [True, True, False, False]

    resumed = CountingEmbedder()
    report = embed_with_cache(items, data.__getitem__, resumed, cache, batch_size=2)
    assert (report.cached, report.embedded) == (2, 2)
    assert resumed.calls == [2]


def test_settings_select_the_gemini_embedder_and_its_index_folder(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, retrieval_embedder="gemini")

    assert index_root(settings) == tmp_path / "artifacts" / "faiss" / "gemini-embedding-2"
    with pytest.raises(IndexUnavailableError, match="GEMINI_API_KEY"):
        create_embedder(settings)
    keyed = settings.model_copy(update={"gemini_api_key": SecretStr("k")})
    assert isinstance(create_embedder(keyed), GeminiImageEmbedder)
    dinov2 = Settings(_env_file=None, data_dir=tmp_path)
    assert index_root(dinov2) == tmp_path / "artifacts" / "faiss" / "dinov2-small"


def test_gemini_index_serves_queries_without_torch(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    from app.services.retrieval.faiss_index import ReferenceMetadata, build_index_artifacts

    def meta(name: str, condition: str) -> ReferenceMetadata:
        return ReferenceMetadata(
            reference_id=f"tomato-plantdoc-{name}",
            crop=SupportedCrop.TOMATO,
            condition=condition,
            source_label=condition,
            dataset_source="plantdoc",
            image_uri=f"local://references/images/tomato/{name}.jpg",
            image_style="field",
            license="CC BY 4.0",
            attribution="test",
            source_url="https://example.test",
        )

    vectors = np.zeros((2, DIM), dtype=np.float32)
    vectors[0, 0] = vectors[1, 1] = 1.0
    root = tmp_path / "artifacts" / "faiss" / "gemini-embedding-2" / "v2"
    build_index_artifacts(
        root,
        index_version="v2",
        spec=GEMINI_EMBEDDING_2,
        entries={SupportedCrop.TOMATO: ([meta("a", "late_blight"), meta("b", "healthy")], vectors)},
        source_manifests={"tomato.csv": "0" * 64},
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        retrieval_index_version="v2",
        retrieval_embedder="gemini",
    ).model_copy(update={"gemini_api_key": SecretStr("k")})

    retriever = load_reference_retriever(settings)

    assert retriever.index_version == "v2"
