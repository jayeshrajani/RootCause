"""Check that DINOv2 retrieval behaves sensibly: sanity statistics plus a visual HTML gallery.

Usage (from apps/api):

    # Sanity checks + gallery of held-out photos and their top matches
    python scripts/inspect_retrieval.py --data-dir C:/rootcause-data --index-version v1

    # Your own photo(s) of one crop
    python scripts/inspect_retrieval.py --data-dir C:/rootcause-data --index-version v1 \
        --crop tomato --image leaf1.jpg --image leaf2.jpg

Reports are written to DATA_DIR/reports/ and only reference local files; nothing is uploaded.
"""

import argparse
import hashlib
import html
import io
import json
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageEnhance, ImageOps

from app.core.config import Settings
from app.services.retrieval.dataset_registry import (
    ManifestRecord,
    Split,
    SupportedCrop,
    atomic_write_bytes,
    read_manifest,
    resolve_local_uri,
)
from app.services.retrieval.embeddings import (
    DINOV2_SMALL,
    Dinov2Embedder,
    EmbeddingCache,
    default_model_dir,
)
from app.services.retrieval.faiss_index import load_reference_index
from app.services.retrieval.reference_retriever import (
    ReferenceRetriever,
    RetrievalResult,
    index_root,
)

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"


def _encode(image: Image.Image, quality: int = 95) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def photo_variants(data: bytes) -> dict[str, bytes]:
    """Edits that keep the same photo: an embedding should barely move under them."""
    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    dx, dy = width // 20, height // 20
    return {
        "mirrored": _encode(ImageOps.mirror(image)),
        "jpeg_quality_50": _encode(image, quality=50),
        "half_resolution": _encode(image.resize((max(1, width // 2), max(1, height // 2)))),
        "crop_90_percent": _encode(image.crop((dx, dy, width - dx, height - dy))),
        "brighter_20_percent": _encode(ImageEnhance.Brightness(image).enhance(1.2)),
    }


def _mean_offdiag(a: NDArray[np.float32], b: NDArray[np.float32], same: bool) -> float:
    sims = a @ b.T
    if same:
        mask = ~np.eye(len(a), dtype=bool)
        return float(sims[mask].mean())
    return float(sims.mean())


def sanity_checks(
    embedder: Dinov2Embedder,
    cache: EmbeddingCache,
    records: dict[SupportedCrop, list[ManifestRecord]],
    data_dir: Path,
    samples: int,
    seed: int,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    evaluation = [r for crop in SupportedCrop for r in records[crop] if r.split == Split.EVALUATION]
    chosen = [evaluation[i] for i in rng.choice(len(evaluation), samples, replace=False)]

    first = resolve_local_uri(data_dir, chosen[0].image_uri).read_bytes()
    repeat = embedder.embed([first, first])
    determinism = float(np.abs(repeat[0] - repeat[1]).max())

    variant_sims: dict[str, list[float]] = defaultdict(list)
    for record in chosen:
        data = resolve_local_uri(data_dir, record.image_uri).read_bytes()
        names, blobs = zip(*photo_variants(data).items(), strict=True)
        vectors = embedder.embed([data, *blobs])
        for name, vector in zip(names, vectors[1:], strict=True):
            variant_sims[name].append(float(vectors[0] @ vector))

    same_label: list[float] = []
    different_label: list[float] = []
    for crop in SupportedCrop:
        rows = [r for r in records[crop] if r.split == Split.EVALUATION]
        vectors = np.stack([v for r in rows if (v := cache.get(r.sha256)) is not None])
        labels = [r.condition for r in rows]
        sims = vectors @ vectors.T
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                (same_label if labels[i] == labels[j] else different_label).append(
                    float(sims[i, j])
                )

    references = {
        crop: np.stack([v for r in records[crop] if r.split == Split.REFERENCE
                        if (v := cache.get(r.sha256)) is not None])
        for crop in SupportedCrop
    }  # fmt: skip
    crop_matrix = {
        a.value: {b.value: round(_mean_offdiag(references[a], references[b], a == b), 3)
                  for b in SupportedCrop}
        for a in SupportedCrop
    }  # fmt: skip

    return {
        "determinism_max_abs_diff": determinism,
        "same_photo_edits": {
            name: {"mean": round(float(np.mean(v)), 3), "min": round(float(np.min(v)), 3)}
            for name, v in variant_sims.items()
        },
        "same_crop_same_label_mean": round(float(np.mean(same_label)), 3),
        "same_crop_different_label_mean": round(float(np.mean(different_label)), 3),
        "crop_similarity_matrix": crop_matrix,
        "samples": samples,
    }


def print_sanity(report: dict[str, object]) -> None:
    edits = report["same_photo_edits"]
    assert isinstance(edits, dict)
    print("\n1) Determinism: same image embedded twice, max difference "
          f"{report['determinism_max_abs_diff']:.2e} (0 = identical)")  # fmt: skip
    print(f"\n2) Same photo after edits (cosine to original, {report['samples']} photos):")
    for name, stats in edits.items():
        print(f"     {name:<22} mean {stats['mean']:.3f}   min {stats['min']:.3f}")
    print("\n3) Different photos of the same crop (cosine, held-out images):")
    print(f"     same disease label        mean {report['same_crop_same_label_mean']:.3f}")
    print(f"     different disease label   mean {report['same_crop_different_label_mean']:.3f}")
    print("\n4) Mean cosine between reference images, by crop:")
    matrix = report["crop_similarity_matrix"]
    assert isinstance(matrix, dict)
    print("              " + "".join(f"{c:>9}" for c in matrix))
    for crop, row in matrix.items():
        print(f"     {crop:<8}" + "".join(f"{row[c]:>9.3f}" for c in matrix))
    print("\nHealthy embeddings: (2) close to 1, well above (3); in (3) same label above different "
          "label; in (4) the diagonal is the largest value in each row.")  # fmt: skip


def _src(path: Path, report_dir: Path) -> str:
    try:
        relative = os.path.relpath(path, report_dir)
    except ValueError:
        return html.escape(path.resolve().as_uri())
    return quote(Path(relative).as_posix())


def _card(src: str, title: str, lines: Sequence[str], css: str) -> str:
    text = "".join(f"<div>{html.escape(line)}</div>" for line in lines)
    return (
        f'<figure class="{css}"><img src="{src}" alt="{html.escape(title)}" loading="lazy">'
        f"<figcaption><b>{html.escape(title)}</b>{text}</figcaption></figure>"
    )


def render_html(
    title: str,
    rows: Sequence[tuple[str, Path, str | None, RetrievalResult]],
    data_dir: Path,
    report_dir: Path,
) -> str:
    body = []
    for heading, query_path, query_label, result in rows:
        cards = [_card(_src(query_path, report_dir), "Query", [heading], "query")]
        for rank, match in enumerate(result.matches, start=1):
            css = "neutral" if query_label is None else (
                "hit" if match.disease_label == query_label else "miss"
            )  # fmt: skip
            cards.append(
                _card(
                    _src(resolve_local_uri(data_dir, match.image_uri), report_dir),
                    f"#{rank} {match.disease_label}",
                    [f"similarity {match.similarity_score:.3f}",
                     f"{match.dataset_source} · {match.image_style}"],
                    css,
                )
            )  # fmt: skip
        body.append(f'<section class="row">{"".join(cards)}</section>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f5; color: #16261c; }}
.row {{ display: flex; gap: 10px; margin: 14px 0; padding: 10px; background: #fff;
        border-radius: 12px; overflow-x: auto; }}
figure {{ margin: 0; width: 170px; flex: none; border: 4px solid #ccc; border-radius: 10px;
          overflow: hidden; background: #fff; }}
figure img {{ width: 100%; height: 150px; object-fit: cover; display: block; }}
figcaption {{ font-size: 12px; padding: 6px; line-height: 1.35; }}
.query {{ border-color: #16261c; }} .hit {{ border-color: #2f9e44; }}
.miss {{ border-color: #e03131; }} .neutral {{ border-color: #868e96; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p>Green: same dataset label as the query. Red: different label. Similarity measures visual
resemblance to labelled reference photos; it is <b>not</b> a diagnosis or a probability.</p>
{"".join(body)}
</body></html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--index-version", required=True)
    parser.add_argument("--crop", choices=[c.value for c in SupportedCrop])
    parser.add_argument("--image", type=Path, action="append", help="Your photo (repeat up to 3).")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--per-condition", type=int, default=2, help="Gallery queries per label.")
    parser.add_argument("--sanity-samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    settings = Settings()
    data_dir: Path | None = args.data_dir or settings.data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    data_dir = data_dir.resolve()
    if bool(args.image) != bool(args.crop):
        print("Use --crop and --image together.", file=sys.stderr)
        return 2

    spec = DINOV2_SMALL
    embedder = Dinov2Embedder(default_model_dir(data_dir, spec), spec=spec)
    index = load_reference_index(index_root(settings, data_dir) / args.index_version, spec)
    retriever = ReferenceRetriever(embedder, index)
    report_dir = data_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.image:
        images = [path.read_bytes() for path in args.image]
        result = retriever.retrieve(args.crop, images, top_k=args.top_k)
        print(f"Top {args.top_k} {args.crop} references (index {result.index_version}):")
        for rank, m in enumerate(result.matches, start=1):
            print(f"  #{rank} {m.disease_label:<24} similarity {m.similarity_score:.3f} "
                  f"(query photo {m.query_image_index + 1}, {m.dataset_source})")  # fmt: skip
        rows = [(f"Your photo · {args.crop}", args.image[0], None, result)]
        out = report_dir / "retrieval_query.html"
        page = render_html(f"Your {args.crop} photo vs references", rows, data_dir, report_dir)
        atomic_write_bytes(out, page.encode("utf-8"))
        print(f"\nOpen in a browser: {out}")
        return 0

    records = {c: read_manifest(args.manifest_dir / f"{c}.csv") for c in SupportedCrop}
    cache = EmbeddingCache(data_dir / "embeddings", spec)
    sanity = sanity_checks(embedder, cache, records, data_dir, args.sanity_samples, args.seed)
    print_sanity(sanity)

    gallery: list[tuple[str, Path, str | None, RetrievalResult]] = []
    top1_hits = 0
    for crop in SupportedCrop:
        by_condition: dict[str, list[ManifestRecord]] = defaultdict(list)
        for record in records[crop]:
            if record.split == Split.EVALUATION:
                by_condition[record.condition].append(record)
        for condition in sorted(by_condition):
            ranked = sorted(
                by_condition[condition],
                key=lambda r: hashlib.sha256(f"{args.seed}:{r.reference_id}".encode()).hexdigest(),
            )
            for record in ranked[: args.per_condition]:
                path = resolve_local_uri(data_dir, record.image_uri)
                result = retriever.retrieve(crop, [path.read_bytes()], top_k=args.top_k)
                top1_hits += bool(result.matches) and result.matches[0].disease_label == condition
                heading = f"{crop} · true label: {condition} ({record.image_style})"
                gallery.append((heading, path, condition, result))

    out = report_dir / f"retrieval_gallery_{index.version}.html"
    page = render_html(f"Retrieval gallery · index {index.version}", gallery, data_dir, report_dir)
    atomic_write_bytes(out, page.encode("utf-8"))
    atomic_write_bytes(
        report_dir / f"retrieval_sanity_{index.version}.json",
        (json.dumps(sanity, indent=2) + "\n").encode("utf-8"),
    )
    print(
        f"\nGallery: {len(gallery)} held-out photos, top-1 label match {top1_hits}/{len(gallery)}"
    )
    print(f"Open in a browser: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
