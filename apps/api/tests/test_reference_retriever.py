import dataclasses
import json
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np
import pytest

from app.services.retrieval.dataset_registry import ManifestRecord, SupportedCrop
from app.services.retrieval.embeddings import EmbeddingSpec, Vectors, l2_normalize
from app.services.retrieval.errors import (
    IndexCompatibilityError,
    IndexUnavailableError,
    InvalidQueryError,
    ReferenceImageUnavailableError,
    UnsupportedCropError,
)
from app.services.retrieval.faiss_index import (
    MANIFEST_NAME,
    ReferenceIndex,
    ReferenceMetadata,
    build_index_artifacts,
    load_reference_index,
)
from app.services.retrieval.reference_retriever import ReferenceRetriever

pytest.importorskip("faiss")

SPEC = EmbeddingSpec("test/model", "rev", "0" * 64, "test-v1", 4)
UNIT = {
    "a": [1.0, 0.0, 0.0, 0.0],
    "b": [0.0, 1.0, 0.0, 0.0],
    "c": [0.0, 0.0, 1.0, 0.0],
    "ab": [1.0, 0.9, 0.0, 0.0],
}


def meta(crop: SupportedCrop, name: str, condition: str) -> ReferenceMetadata:
    return ReferenceMetadata(
        reference_id=f"{crop}-plantdoc-{name}",
        crop=crop,
        condition=condition,
        source_label=condition,
        dataset_source="plantdoc",
        image_uri=f"local://references/images/{crop}/{name}.jpg",
        image_style="field",
        license="CC BY 4.0",
        attribution="test",
        source_url="https://example.test",
    )


def build(directory: Path, spec: EmbeddingSpec = SPEC) -> None:
    tomato = [
        meta(SupportedCrop.TOMATO, n, c)
        for n, c in (("a", "late_blight"), ("b", "healthy"), ("ab", "late_blight"))
    ]
    potato = [meta(SupportedCrop.POTATO, "c", "early_blight")]
    build_index_artifacts(
        directory,
        index_version=directory.name,
        spec=spec,
        entries={
            SupportedCrop.TOMATO: (
                tomato,
                l2_normalize(np.array([UNIT["a"], UNIT["b"], UNIT["ab"]])),
            ),
            SupportedCrop.POTATO: (potato, l2_normalize(np.array([UNIT["c"]]))),
        },
        source_manifests={"tomato.csv": "0" * 64},
    )


class FixedEmbedder:
    """Query bytes are keys into UNIT, so tests control exactly what is similar."""

    def __init__(self, spec: EmbeddingSpec = SPEC) -> None:
        self._spec = spec

    @property
    def spec(self) -> EmbeddingSpec:
        return self._spec

    def embed(self, images: Sequence[bytes]) -> Vectors:
        return l2_normalize(np.array([UNIT[image.decode()] for image in images]))


@pytest.fixture
def index(tmp_path: Path) -> ReferenceIndex:
    build(tmp_path / "v1")
    return load_reference_index(tmp_path / "v1", SPEC)


def test_index_round_trip_and_exact_search(index: ReferenceIndex) -> None:
    tomato = index.for_crop(SupportedCrop.TOMATO)

    scores, rows = tomato.search(l2_normalize(np.array([UNIT["a"]])), k=3)

    assert [tomato.metadata[i].reference_id for i in rows[0]] == [
        "tomato-plantdoc-a",
        "tomato-plantdoc-ab",
        "tomato-plantdoc-b",
    ]
    assert scores[0][0] == pytest.approx(1.0) and scores[0][2] == pytest.approx(0.0, abs=1e-6)


def test_retriever_returns_only_selected_crop(index: ReferenceIndex) -> None:
    result = ReferenceRetriever(FixedEmbedder(), index).retrieve("tomato", [b"c"], top_k=5)

    assert result.crop_id == "tomato" and len(result.matches) == 3
    assert all(m.crop_id == "tomato" for m in result.matches)
    assert "not a diagnostic probability" in result.similarity_note


def test_retriever_merges_query_images_keeping_best_score(index: ReferenceIndex) -> None:
    result = ReferenceRetriever(FixedEmbedder(), index).retrieve("tomato", [b"a", b"b"], top_k=2)

    assert [(m.reference_image_id, m.query_image_index) for m in result.matches] == [
        ("tomato-plantdoc-a", 0),
        ("tomato-plantdoc-b", 1),
    ]
    assert result.matches[0].similarity_score == pytest.approx(1.0)
    assert result.retrieval_model == "test/model" and result.index_version == "v1"


@pytest.mark.parametrize(
    ("crop", "images", "top_k", "error"),
    [
        ("wheat", [b"a"], 5, UnsupportedCropError),
        ("tomato", [], 5, InvalidQueryError),
        ("tomato", [b"a"] * 4, 5, InvalidQueryError),
        ("tomato", [b"a"], 0, InvalidQueryError),
        ("rice", [b"a"], 5, IndexUnavailableError),
    ],
)
def test_retriever_rejects_invalid_requests(
    index: ReferenceIndex, crop: str, images: list[bytes], top_k: int, error: type[Exception]
) -> None:
    with pytest.raises(error):
        ReferenceRetriever(FixedEmbedder(), index).retrieve(crop, images, top_k=top_k)


def test_retriever_refuses_mismatched_embedding_spec(index: ReferenceIndex) -> None:
    other = dataclasses.replace(SPEC, preprocessing_version="test-v2")

    with pytest.raises(IndexCompatibilityError):
        ReferenceRetriever(FixedEmbedder(other), index)


def test_reference_image_reads_local_files_only(index: ReferenceIndex, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    image = data_dir / "references" / "images" / "tomato" / "a.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg bytes")
    retriever = ReferenceRetriever(FixedEmbedder(), index, data_dir=data_dir)
    match = retriever.retrieve("tomato", [b"a"], top_k=1).matches[0]

    assert retriever.reference_image(match) == b"jpeg bytes"
    for unreadable in (
        match.model_copy(update={"image_uri": "gs://bucket/a.jpg"}),
        match.model_copy(update={"image_uri": "local://references/images/tomato/b.jpg"}),
        match.model_copy(update={"image_uri": "local://../outside.jpg"}),
    ):
        with pytest.raises(ReferenceImageUnavailableError):
            retriever.reference_image(unreadable)
    with pytest.raises(ReferenceImageUnavailableError):
        ReferenceRetriever(FixedEmbedder(), index).reference_image(match)


@pytest.mark.anyio
async def test_aretrieve_matches_retrieve(index: ReferenceIndex) -> None:
    retriever = ReferenceRetriever(FixedEmbedder(), index)

    assert await retriever.aretrieve("tomato", [b"a"], top_k=2) == retriever.retrieve(
        "tomato", [b"a"], top_k=2
    )


def test_process_wide_retriever_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.retrieval.reference_retriever as module
    from app.core.config import Settings
    from app.services.retrieval import get_reference_retriever

    monkeypatch.setattr(module, "_retriever", None)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(IndexUnavailableError, match="INDEX_VERSION"):
        get_reference_retriever()


def test_loading_rejects_stale_tampered_or_missing_indexes(tmp_path: Path) -> None:
    build(tmp_path / "v1")

    with pytest.raises(IndexCompatibilityError, match="different embedding"):
        load_reference_index(tmp_path / "v1", dataclasses.replace(SPEC, model_revision="other"))

    (tmp_path / "v1" / "tomato.metadata.json").write_text("[]", encoding="utf-8")
    with pytest.raises(IndexCompatibilityError, match="checksum"):
        load_reference_index(tmp_path / "v1", SPEC)

    with pytest.raises(IndexUnavailableError):
        load_reference_index(tmp_path / "v2", SPEC)


def test_loading_rejects_renamed_version_folder(tmp_path: Path) -> None:
    build(tmp_path / "v1")
    (tmp_path / "v1").rename(tmp_path / "v9")

    with pytest.raises(IndexCompatibilityError, match="version"):
        load_reference_index(tmp_path / "v9", SPEC)


def test_build_rejects_unnormalised_or_mismatched_vectors(tmp_path: Path) -> None:
    item = [meta(SupportedCrop.TOMATO, "a", "healthy")]
    invalid: list[Vectors] = [
        np.array([[2.0, 0, 0, 0]], dtype=np.float32),
        np.full((2, 4), 0.5, dtype=np.float32),
    ]
    for vectors in invalid:
        with pytest.raises(IndexCompatibilityError):
            build_index_artifacts(
                tmp_path / "v1",
                index_version="v1",
                spec=SPEC,
                entries={SupportedCrop.TOMATO: (item, vectors)},
                source_manifests={},
            )
    assert not (tmp_path / "v1" / MANIFEST_NAME).exists()


@pytest.fixture(scope="module")
def public_retriever() -> Iterator[ReferenceRetriever]:
    """The exact handoff path: `get_reference_retriever()` with real DINOv2 and index files."""
    pytest.importorskip("torch")
    data_dir = os.environ.get("ROOTCAUSE_DATA_DIR")
    version = os.environ.get("ROOTCAUSE_RETRIEVAL_INDEX_VERSION", "v1")
    if not data_dir:
        pytest.skip("set ROOTCAUSE_DATA_DIR to run the end-to-end smoke tests")
    if not (
        Path(data_dir) / "artifacts" / "faiss" / "dinov2-small" / version / MANIFEST_NAME
    ).exists():
        pytest.skip(f"index {version} not built")
    import app.services.retrieval.reference_retriever as module
    from app.core.config import Settings
    from app.services.retrieval import get_reference_retriever

    settings = Settings(_env_file=None, data_dir=Path(data_dir), retrieval_index_version=version)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, "_retriever", None)
        patch.setattr(module, "get_settings", lambda: settings)
        retriever = get_reference_retriever()
        assert get_reference_retriever() is retriever
        yield retriever


def _manifest_path(crop: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "manifests" / f"{crop}.csv"


def _manifest_records(crop: str) -> dict[str, "ManifestRecord"]:
    from app.services.retrieval.dataset_registry import read_manifest

    return {r.reference_id: r for r in read_manifest(_manifest_path(crop))}


def _evaluation_images(crop: str, count: int) -> list[tuple[str, bytes]]:
    from app.services.retrieval.dataset_registry import Split, resolve_local_uri

    data_dir = Path(os.environ["ROOTCAUSE_DATA_DIR"])
    records = [r for r in _manifest_records(crop).values() if r.split == Split.EVALUATION]
    return [
        (r.reference_id, resolve_local_uri(data_dir, r.image_uri).read_bytes())
        for r in records[:count]
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(("crop", "photos"), [("rice", 1), ("tomato", 3), ("potato", 2)])
async def test_public_api_end_to_end(
    public_retriever: ReferenceRetriever, crop: str, photos: int
) -> None:
    import hashlib

    queries = _evaluation_images(crop, photos)

    result = await public_retriever.aretrieve(crop, [data for _, data in queries])

    assert result.crop_id == crop and result.retrieval_model == "facebook/dinov2-small"
    assert len(result.matches) == 5 and all(m.crop_id == crop for m in result.matches)
    scores = [m.similarity_score for m in result.matches]
    assert scores == sorted(scores, reverse=True) and all(-1 <= s <= 1 for s in scores)
    assert {m.query_image_index for m in result.matches} <= set(range(photos))
    assert not {qid for qid, _ in queries} & {m.reference_image_id for m in result.matches}
    expected = _manifest_records(crop)
    for match in result.matches:
        record = expected[match.reference_image_id]
        assert match.disease_label == record.condition and match.license and match.attribution
        assert hashlib.sha256(public_retriever.reference_image(match)).hexdigest() == record.sha256
    json.dumps(result.model_dump(mode="json"))


@pytest.mark.anyio
async def test_public_api_rejects_bad_input(public_retriever: ReferenceRetriever) -> None:
    ((_, photo),) = _evaluation_images("tomato", 1)

    with pytest.raises(UnsupportedCropError):
        await public_retriever.aretrieve("wheat", [photo])
    with pytest.raises(InvalidQueryError):
        await public_retriever.aretrieve("tomato", [photo, b"not an image"])
    with pytest.raises(InvalidQueryError):
        await public_retriever.aretrieve("tomato", [photo] * 4)
