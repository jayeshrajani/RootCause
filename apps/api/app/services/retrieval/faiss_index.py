"""Versioned per-crop FAISS indexes of reference embeddings (exact inner-product search).

Each index version is a folder of artifacts written together and verified together:
`{crop}.faiss`, `{crop}.metadata.json` and `index_manifest.json` (written last, with checksums
and the embedding spec). Loading refuses stale, corrupt or differently embedded indexes.
"""

import dataclasses
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, ValidationError

from app.services.retrieval.dataset_registry import SupportedCrop, atomic_write_bytes
from app.services.retrieval.embeddings import EmbeddingSpec, Vectors
from app.services.retrieval.errors import IndexCompatibilityError, IndexUnavailableError

INDEX_FORMAT = 1
MANIFEST_NAME = "index_manifest.json"


class ReferenceMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_id: str
    crop: SupportedCrop
    condition: str
    source_label: str
    dataset_source: str
    image_uri: str
    image_style: str
    license: str
    attribution: str
    source_url: str


class CropArtifacts(BaseModel):
    count: int
    index_file: str
    index_sha256: str
    metadata_file: str
    metadata_sha256: str


class IndexManifest(BaseModel):
    format: int
    index_version: str
    metric: Literal["inner_product"]
    embedding: dict[str, Any]
    crops: dict[SupportedCrop, CropArtifacts]
    source_manifests: dict[str, str]


def spec_dict(spec: EmbeddingSpec) -> dict[str, Any]:
    return dataclasses.asdict(spec)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_index_artifacts(
    directory: Path,
    *,
    index_version: str,
    spec: EmbeddingSpec,
    entries: Mapping[SupportedCrop, tuple[Sequence[ReferenceMetadata], Vectors]],
    source_manifests: Mapping[str, str],
) -> IndexManifest:
    """Write one exact inner-product index per crop; the manifest is written last."""
    import faiss

    crops: dict[SupportedCrop, CropArtifacts] = {}
    for crop, (metadata, vectors) in sorted(entries.items()):
        matrix = np.ascontiguousarray(vectors, dtype=np.float32)
        if matrix.shape != (len(metadata), spec.dimension) or not len(metadata):
            raise IndexCompatibilityError(f"{crop}: vectors do not match metadata or dimension")
        if not np.all(np.isfinite(matrix)) or not np.allclose(
            np.linalg.norm(matrix, axis=1), 1.0, atol=1e-3
        ):
            raise IndexCompatibilityError(f"{crop}: vectors must be finite and L2-normalised")
        if any(m.crop != crop for m in metadata):
            raise IndexCompatibilityError(f"{crop}: metadata contains another crop")
        index = faiss.IndexFlatIP(spec.dimension)
        index.add(matrix)
        index_bytes = faiss.serialize_index(index).tobytes()
        metadata_bytes = (
            json.dumps([m.model_dump(mode="json") for m in metadata], indent=1) + "\n"
        ).encode("utf-8")
        index_file, metadata_file = f"{crop}.faiss", f"{crop}.metadata.json"
        atomic_write_bytes(directory / index_file, index_bytes)
        atomic_write_bytes(directory / metadata_file, metadata_bytes)
        crops[crop] = CropArtifacts(
            count=len(metadata),
            index_file=index_file,
            index_sha256=_sha256(index_bytes),
            metadata_file=metadata_file,
            metadata_sha256=_sha256(metadata_bytes),
        )
    manifest = IndexManifest(
        format=INDEX_FORMAT,
        index_version=index_version,
        metric="inner_product",
        embedding=spec_dict(spec),
        crops=crops,
        source_manifests=dict(sorted(source_manifests.items())),
    )
    atomic_write_bytes(directory / MANIFEST_NAME, manifest_bytes(manifest))
    return manifest


def manifest_bytes(manifest: IndexManifest) -> bytes:
    return (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")


def read_index_manifest(directory: Path) -> IndexManifest:
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise IndexUnavailableError(f"no index manifest for version {directory.name!r}")
    try:
        return IndexManifest.model_validate_json(path.read_bytes())
    except ValidationError as exc:
        raise IndexCompatibilityError("index manifest is malformed") from exc


@dataclass(frozen=True, slots=True)
class CropIndex:
    crop: SupportedCrop
    index: Any
    metadata: tuple[ReferenceMetadata, ...]

    def search(self, queries: Vectors, k: int) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
        """Top-k rows by inner product (cosine similarity for normalised vectors)."""
        k = min(k, len(self.metadata))
        scores, rows = self.index.search(np.ascontiguousarray(queries, dtype=np.float32), k)
        return np.asarray(scores, dtype=np.float32), np.asarray(rows, dtype=np.int64)


@dataclass(frozen=True, slots=True)
class ReferenceIndex:
    manifest: IndexManifest
    crops: Mapping[SupportedCrop, CropIndex]

    @property
    def version(self) -> str:
        return self.manifest.index_version

    def for_crop(self, crop: SupportedCrop) -> CropIndex:
        try:
            return self.crops[crop]
        except KeyError:
            raise IndexUnavailableError(f"no reference index loaded for {crop}") from None


def load_reference_index(
    directory: Path, spec: EmbeddingSpec, crops: Iterable[SupportedCrop] | None = None
) -> ReferenceIndex:
    """Load and verify an index version built with exactly `spec`."""
    import faiss

    manifest = read_index_manifest(directory)
    if manifest.format != INDEX_FORMAT:
        raise IndexCompatibilityError(f"unsupported index format {manifest.format}")
    if manifest.index_version != directory.name:
        raise IndexCompatibilityError("index folder does not match its manifest version")
    if manifest.embedding != spec_dict(spec):
        raise IndexCompatibilityError(
            "index was built with a different embedding model or preprocessing"
        )

    loaded: dict[SupportedCrop, CropIndex] = {}
    for crop in sorted(crops or manifest.crops):
        artifacts = manifest.crops.get(crop)
        if artifacts is None:
            continue
        try:
            index_bytes = (directory / artifacts.index_file).read_bytes()
            metadata_bytes = (directory / artifacts.metadata_file).read_bytes()
        except OSError as exc:
            raise IndexCompatibilityError(f"{crop}: index artifacts are missing") from exc
        if (
            _sha256(index_bytes) != artifacts.index_sha256
            or _sha256(metadata_bytes) != artifacts.metadata_sha256
        ):
            raise IndexCompatibilityError(f"{crop}: index artifacts fail checksum verification")
        index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
        try:
            metadata = tuple(
                ReferenceMetadata.model_validate(item) for item in json.loads(metadata_bytes)
            )
        except (ValueError, ValidationError) as exc:
            raise IndexCompatibilityError(f"{crop}: metadata is malformed") from exc
        if (
            index.d != spec.dimension
            or index.ntotal != artifacts.count
            or len(metadata) != artifacts.count
            or index.metric_type != faiss.METRIC_INNER_PRODUCT
            or any(m.crop != crop for m in metadata)
        ):
            raise IndexCompatibilityError(f"{crop}: index does not match its metadata")
        loaded[crop] = CropIndex(crop, index, metadata)
    return ReferenceIndex(manifest, loaded)
