"""Embed manifest images (DINOv2 or Gemini Embedding 2) and build versioned per-crop FAISS indexes.

Usage (from apps/api):

    python scripts/build_index.py --data-dir C:/rootcause-data --index-version v1
    python scripts/build_index.py --data-dir ~/rcdata --index-version v2 --embedder gemini

DINOv2 needs the retrieval extra and local weights; Gemini needs the index extra and
GEMINI_API_KEY (billed per image). Reference and evaluation images are embedded (evaluation
vectors are cached for the evaluation script but never indexed). Every vector is saved as soon as
it is made, so re-running after an interruption only embeds what is missing. An existing index
version is never overwritten with different contents.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.services.retrieval.dataset_registry import (
    ManifestRecord,
    Split,
    SupportedCrop,
    atomic_write_bytes,
    read_manifest,
    resolve_local_uri,
    validate_manifest,
)
from app.services.retrieval.embeddings import (
    Dinov2Embedder,
    EmbeddingCache,
    ImageEmbedder,
    embed_with_cache,
)
from app.services.retrieval.errors import RetrievalError
from app.services.retrieval.faiss_index import (
    MANIFEST_NAME,
    ReferenceMetadata,
    build_index_artifacts,
    read_index_manifest,
)
from app.services.retrieval.gemini_embedder import MAX_IMAGES_PER_CALL
from app.services.retrieval.reference_retriever import create_embedder, embedding_spec, index_root

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"


def metadata_for(record: ManifestRecord) -> ReferenceMetadata:
    return ReferenceMetadata(
        reference_id=record.reference_id,
        crop=record.crop,
        condition=record.condition,
        source_label=record.source_label,
        dataset_source=record.dataset_source,
        image_uri=record.image_uri,
        image_style=record.image_style,
        license=record.license,
        attribution=record.attribution,
        source_url=record.source_url,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--index-version", required=True, help="e.g. v1 (immutable once built)")
    parser.add_argument(
        "--embedder",
        choices=("dinov2", "gemini"),
        help="Defaults to ROOTCAUSE_RETRIEVAL_EMBEDDER (dinov2).",
    )
    parser.add_argument("--model-dir", type=Path, help="DINOv2 weights folder.")
    parser.add_argument("--force", action="store_true", help="Replace an existing version.")
    args = parser.parse_args(argv)

    settings = Settings()
    if args.embedder:
        settings = settings.model_copy(update={"retrieval_embedder": args.embedder})
    data_dir: Path | None = args.data_dir or settings.data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    data_dir = data_dir.resolve()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", args.index_version):
        print(
            "--index-version may contain only letters, digits, '.', '_' and '-'.", file=sys.stderr
        )
        return 2
    spec = embedding_spec(settings)

    records: dict[SupportedCrop, list[ManifestRecord]] = {}
    source_manifests: dict[str, str] = {}
    for crop in SupportedCrop:
        path = args.manifest_dir / f"{crop}.csv"
        records[crop] = read_manifest(path)
        source_manifests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        problems = validate_manifest(crop, records[crop])
        if problems:
            print(f"{crop} manifest is invalid: {'; '.join(problems)}", file=sys.stderr)
            return 1

    cache = EmbeddingCache(data_dir / "embeddings", spec)
    every = [r for crop_records in records.values() for r in crop_records]
    items = list(dict.fromkeys((r.image_uri, r.sha256) for r in every))
    gemini = settings.retrieval_embedder == "gemini"

    def progress(done: int, total: int) -> None:
        if done == total or done % (MAX_IMAGES_PER_CALL * 10) == 0:
            print(f"  embedded {done}/{total}", flush=True)

    try:
        embedder: ImageEmbedder = (
            Dinov2Embedder(args.model_dir, spec=spec)
            if args.model_dir and not gemini
            else create_embedder(settings, data_dir)
        )
        if isinstance(embedder, Dinov2Embedder):
            embedder.load()
        print(f"Embedding with {spec.model_id} ({spec.dimension} dimensions)")
        report = embed_with_cache(
            items,
            lambda uri: resolve_local_uri(data_dir, uri).read_bytes(),
            embedder,
            cache,
            # One API call per batch, so an interruption loses at most one call.
            batch_size=MAX_IMAGES_PER_CALL if gemini else 32,
            progress=progress if gemini else None,
        )
    except RetrievalError as exc:
        print(f"Embedding failed: {exc}", file=sys.stderr)
        print("Vectors made so far are saved; re-run the same command to resume.", file=sys.stderr)
        return 1
    failed = report.failed or {}
    print(f"Embeddings: {report.cached} cached, {report.embedded} new, {len(failed)} failed")
    atomic_write_bytes(
        cache.directory / "last_run.json",
        json.dumps(
            {"cached": report.cached, "embedded": report.embedded, "failed": failed}, indent=2
        ).encode("utf-8"),
    )
    reference_failures = [
        r.reference_id for r in every if r.split == Split.REFERENCE and r.image_uri in failed
    ]
    if reference_failures:
        print(f"Reference images failed to embed: {reference_failures[:5]}", file=sys.stderr)
        return 1

    entries = {}
    for crop, crop_records in records.items():
        refs = sorted(
            (r for r in crop_records if r.split == Split.REFERENCE), key=lambda r: r.reference_id
        )
        vectors = [cache.get(r.sha256) for r in refs]
        if any(v is None for v in vectors):
            print(f"{crop}: missing cached embeddings", file=sys.stderr)
            return 1
        entries[crop] = ([metadata_for(r) for r in refs], np.stack(vectors))  # type: ignore[arg-type]

    root = index_root(settings, data_dir)
    target = root / args.index_version
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=root, prefix=f".{args.index_version}."))
    try:
        manifest = build_index_artifacts(
            staging,
            index_version=args.index_version,
            spec=spec,
            entries=entries,
            source_manifests=source_manifests,
        )
        if (target / MANIFEST_NAME).exists():
            if read_index_manifest(target) == manifest:
                print(f"Index {args.index_version} already built with identical contents.")
                return 0
            if not args.force:
                print(
                    f"Index {args.index_version} exists with different contents. Use a new "
                    "--index-version (or --force).",
                    file=sys.stderr,
                )
                return 1
            shutil.rmtree(target)
        staging.replace(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    for crop, artifacts in manifest.crops.items():
        print(f"  {crop:<7} {artifacts.count:>4} reference vectors")
    print(f"Index {args.index_version} written to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
