"""Check Gemini Embedding 2 end to end on 3 dataset images (one API call) before a full build.

Usage (from apps/api, with GEMINI_API_KEY set):

    python scripts/gemini_embedding_smoke.py --data-dir ~/rcdata

Prints the vector size and how similar two photos of the same crop are compared with a photo of
another crop. Nothing is written to disk.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.services.retrieval.dataset_registry import (
    Split,
    SupportedCrop,
    read_manifest,
    resolve_local_uri,
)
from app.services.retrieval.errors import RetrievalError
from app.services.retrieval.reference_retriever import create_embedder

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = Settings().model_copy(update={"retrieval_embedder": "gemini"})
    data_dir: Path | None = args.data_dir or settings.data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    tomato = [
        r
        for r in read_manifest(args.manifest_dir / f"{SupportedCrop.TOMATO}.csv")
        if r.split == Split.REFERENCE
    ][:2]
    rice = [
        r
        for r in read_manifest(args.manifest_dir / f"{SupportedCrop.RICE}.csv")
        if r.split == Split.REFERENCE
    ][:1]
    chosen = [*tomato, *rice]
    try:
        images = [resolve_local_uri(data_dir.resolve(), r.image_uri).read_bytes() for r in chosen]
        vectors = create_embedder(settings).embed(images)
    except (OSError, RetrievalError) as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1

    norms = np.linalg.norm(vectors, axis=1)
    print(
        f"OK: {vectors.shape[0]} vectors of {vectors.shape[1]} dimensions, norms {norms.round(3)}"
    )
    print(f"  tomato vs tomato similarity: {float(vectors[0] @ vectors[1]):.3f}")
    print(f"  tomato vs rice   similarity: {float(vectors[0] @ vectors[2]):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
