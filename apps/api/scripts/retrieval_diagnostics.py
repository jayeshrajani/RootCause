"""Diagnose retrieval quality for one crop and run isolated embedding experiments.

Usage (from apps/api):

    python scripts/retrieval_diagnostics.py --data-dir C:/rootcause-data --index-version v1
    python scripts/retrieval_diagnostics.py ... --crop tomato --experiments

Isolation: reads the committed manifests, the production embedding cache, the pinned model weights
and the index version; never writes to them. Experiment embeddings exist only in memory and are
searched exactly with NumPy (same scores as the production inner-product index). Output goes only to
DATA_DIR/reports/experiments/.
"""

import argparse
import io
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

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
    EmbeddingCache,
    default_model_dir,
    l2_normalize,
    preprocess,
    sha256_file,
)
from app.services.retrieval.faiss_index import load_reference_index
from app.services.retrieval.reference_retriever import index_root

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def metrics(
    labels: Sequence[str],
    styles: Sequence[str],
    top_labels: Sequence[Sequence[str]],
    top_scores: NDArray[np.float32],
    ref_labels: Sequence[str],
) -> dict[str, Any]:
    """Retrieval metrics for queries against references (top-k already applied)."""
    n, k = len(labels), len(top_labels[0])
    same = np.array([[t == q for t in row] for q, row in zip(labels, top_labels, strict=True)])
    share = Counter(ref_labels)
    votes = []
    for row, scores in zip(top_labels, top_scores, strict=True):
        weights: dict[str, float] = defaultdict(float)
        for label, score in zip(row, scores.tolist(), strict=True):
            weights[label] += score
        votes.append(max(weights, key=lambda lab: weights[lab]))
    per_condition: dict[str, list[bool]] = defaultdict(list)
    for label, hit in zip(labels, same.any(axis=1).tolist(), strict=True):
        per_condition[label].append(hit)
    precision = float(same.mean())
    chance = float(np.mean([share[q] / len(ref_labels) for q in labels]))
    result: dict[str, Any] = {
        "queries": n,
        "recall_at_k": round(float(same.any(axis=1).mean()), 3),
        "precision_at_k": round(precision, 3),
        "top1": round(float(same[:, 0].mean()), 3),
        "macro_recall_at_k": round(float(np.mean([np.mean(v) for v in per_condition.values()])), 3),
        "knn_vote_accuracy": round(
            float(np.mean([v == q for v, q in zip(votes, labels, strict=True)])), 3
        ),
        "random_precision_at_k": round(chance, 3),
        "precision_lift_over_random": round(precision / chance, 2) if chance else None,
        "k": k,
    }
    for style in ("field", "lab"):
        mask = np.array([s == style for s in styles])
        if mask.any():
            result[f"{style}_queries"] = {
                "n": int(mask.sum()),
                "recall_at_k": round(float(same[mask].any(axis=1).mean()), 3),
                "precision_at_k": round(float(same[mask].mean()), 3),
                "top1": round(float(same[mask][:, 0].mean()), 3),
            }
    return result


def exact_search(
    queries: NDArray[np.float32], refs: NDArray[np.float32], k: int
) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
    sims = queries @ refs.T
    rows = np.argsort(-sims, axis=1, kind="stable")[:, :k]
    return np.take_along_axis(sims, rows, axis=1).astype(np.float32), rows.astype(np.int64)


def diagnostics(
    crop: SupportedCrop,
    records: list[ManifestRecord],
    cache: EmbeddingCache,
    index_dir: Path,
    k: int,
) -> dict[str, Any]:
    index = load_reference_index(index_dir, DINOV2_SMALL, crops=[crop])
    crop_index = index.for_crop(crop)
    by_id = {r.reference_id: r for r in records}
    refs = [by_id[m.reference_id] for m in crop_index.metadata]
    evaluation = [r for r in records if r.split == Split.EVALUATION]
    queries = np.stack([v for r in evaluation if (v := cache.get(r.sha256)) is not None])
    if len(queries) != len(evaluation):
        raise SystemExit("evaluation embeddings missing from the cache; run build_index.py")

    scores, rows = crop_index.search(queries, k)
    top = [[refs[i] for i in row] for row in rows.tolist()]
    labels = [r.condition for r in evaluation]
    styles = [r.image_style for r in evaluation]
    ref_labels = [r.condition for r in refs]
    overall = metrics(
        labels, styles, [[t.condition for t in row] for row in top], scores, ref_labels
    )

    def table(rows_: Sequence[ManifestRecord]) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in rows_:
            out[r.condition][r.image_style] += 1
        return {c: dict(v) for c, v in sorted(out.items())}

    per_condition: dict[str, dict[str, Any]] = {}
    for condition in sorted(set(labels)):
        idx = [i for i, label in enumerate(labels) if label == condition]
        hits = [[t.condition == condition for t in top[i]] for i in idx]
        per_condition[condition] = {
            "n": len(idx),
            "styles": dict(Counter(styles[i] for i in idx)),
            "recall_at_k": round(float(np.mean([any(h) for h in hits])), 3),
            "precision_at_k": round(float(np.mean(hits)), 3),
            "top1": round(float(np.mean([h[0] for h in hits])), 3),
        }

    confusion = Counter(
        (labels[i], top[i][0].condition)
        for i in range(len(labels))
        if top[i][0].condition != labels[i]
    )
    lab_share_in_top = {
        style: round(float(np.mean([[t.image_style == "lab" for t in top[i]]
                                    for i in range(len(top)) if styles[i] == style])), 3)
        for style in sorted(set(styles))
    }  # fmt: skip

    field_refs = [i for i, r in enumerate(refs) if r.image_style == "field"]
    field_q = [i for i, s in enumerate(styles) if s == "field"]
    ref_vectors = np.stack([cache.get(r.sha256) for r in refs])  # type: ignore[misc]
    f_scores, f_rows = exact_search(queries[field_q], ref_vectors[field_refs], k)
    field_only = metrics(
        [labels[i] for i in field_q],
        ["field"] * len(field_q),
        [[refs[field_refs[j]].condition for j in row] for row in f_rows.tolist()],
        f_scores,
        [refs[i].condition for i in field_refs],
    )

    best = scores[:, 0]
    label_pairs = sorted({(r.dataset_source, r.source_label, r.condition) for r in records})
    return {
        "crop": crop.value,
        "index_version": index.version,
        "reference_counts": table(refs),
        "evaluation_counts": table(evaluation),
        "label_mapping": [
            {"source": s, "source_label": sl, "condition": c} for s, sl, c in label_pairs
        ],
        "overall": overall,
        "per_condition": per_condition,
        "top1_confusions": [
            {"true": t, "retrieved": p, "count": n} for (t, p), n in confusion.most_common(10)
        ],
        "lab_share_in_top_k_by_query_style": lab_share_in_top,
        "lab_share_in_index": round(sum(r.image_style == "lab" for r in refs) / len(refs), 3),
        "field_queries_vs_field_only_references": field_only,
        "leakage": {
            "shared_sha256": len({r.sha256 for r in refs} & {r.sha256 for r in evaluation}),
            "shared_groups": len({r.group_id for r in refs} & {r.group_id for r in evaluation}),
            "best_match_cosine_median": round(float(np.median(best)), 3),
            "best_match_cosine_at_least_0_95": int((best >= 0.95).sum()),
        },
    }


def _prep(data: bytes, short: int | None, crop: int) -> NDArray[np.float32]:
    """Production-style preprocessing at another size; `short=None` resizes without cropping."""
    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    if short is None:
        image = image.resize((crop, crop), Image.Resampling.BICUBIC)
    else:
        w, h = image.size
        scale = short / min(w, h)
        size = (max(crop, round(w * scale)), max(crop, round(h * scale)))
        image = image.resize(size, Image.Resampling.BICUBIC)
        left, top = (size[0] - crop) // 2, (size[1] - crop) // 2
        image = image.crop((left, top, left + crop, top + crop))
    pixels = (np.asarray(image, dtype=np.float32) / 255.0 - _MEAN) / _STD
    return np.ascontiguousarray(pixels.transpose(2, 0, 1), dtype=np.float32)


def experiments(
    crop: SupportedCrop,
    records: list[ManifestRecord],
    cache: EmbeddingCache,
    data_dir: Path,
    k: int,
) -> dict[str, Any]:
    import torch
    from transformers import Dinov2Model

    model_dir = default_model_dir(data_dir)
    if sha256_file(model_dir / "model.safetensors") != DINOV2_SMALL.weights_sha256:
        raise SystemExit("model weights do not match the pinned checksum")
    model = Dinov2Model.from_pretrained(str(model_dir), local_files_only=True).eval()
    refs = sorted((r for r in records if r.split == Split.REFERENCE), key=lambda r: r.reference_id)
    evaluation = [r for r in records if r.split == Split.EVALUATION]
    items = refs + evaluation
    blobs = [resolve_local_uri(data_dir, r.image_uri).read_bytes() for r in items]

    def run(prep: Callable[[bytes], NDArray[np.float32]], flip: bool = False) -> tuple[Any, Any]:
        cls_parts, patch_parts = [], []
        for start in range(0, len(blobs), 16):
            pixels = np.stack([prep(b) for b in blobs[start : start + 16]])
            if flip:
                pixels = np.ascontiguousarray(pixels[:, :, :, ::-1])
            with torch.inference_mode():
                out = model(pixel_values=torch.from_numpy(pixels))
            cls_parts.append(out.pooler_output.numpy())
            patch_parts.append(out.last_hidden_state[:, 1:].mean(dim=1).numpy())
        return l2_normalize(np.concatenate(cls_parts)), l2_normalize(np.concatenate(patch_parts))

    timings: dict[str, float] = {}

    def timed(
        name: str, prep: Callable[[bytes], NDArray[np.float32]], flip: bool = False
    ) -> tuple[Any, Any]:
        started = time.perf_counter()
        result = run(prep, flip)
        timings[name] = round((time.perf_counter() - started) * 1000 / len(blobs), 1)
        return result

    base_cls, base_patch = timed("crop224", preprocess)
    cached = np.stack([cache.get(r.sha256) for r in items])  # type: ignore[misc]
    harness_diff = float(np.abs(base_cls - cached).max())
    flip_cls, _ = timed("crop224_mirrored", preprocess, flip=True)
    full_cls, _ = timed("full224", lambda b: _prep(b, None, 224))
    big_cls, _ = timed("crop448", lambda b: _prep(b, 512, 448))

    variants: dict[str, NDArray[np.float32]] = {
        "baseline (production: CLS, crop 224)": base_cls,
        "flip TTA (mean of image + mirror)": l2_normalize(base_cls + flip_cls),
        "CLS + mean patch tokens (768-d)": l2_normalize(np.hstack([base_cls, base_patch])),
        "full image, no crop (224x224)": full_cls,
        "higher resolution (crop 448)": big_cls,
    }
    n_ref = len(refs)
    labels = [r.condition for r in evaluation]
    styles = [r.image_style for r in evaluation]
    ref_labels = [r.condition for r in refs]
    results = {}
    for name, vectors in variants.items():
        scores, rows = exact_search(vectors[n_ref:], vectors[:n_ref], k)
        results[name] = metrics(
            labels,
            styles,
            [[ref_labels[j] for j in row] for row in rows.tolist()],
            scores,
            ref_labels,
        )
    return {
        "crop": crop.value,
        "harness_max_abs_diff_vs_production_cache": harness_diff,
        "ms_per_image_by_pass": timings,
        "variants": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--index-version", required=True)
    parser.add_argument("--crop", choices=[c.value for c in SupportedCrop], default="tomato")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--experiments", action="store_true", help="Run isolated embedding variants."
    )
    args = parser.parse_args(argv)

    settings = Settings()
    data_dir: Path | None = args.data_dir or settings.data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    data_dir = data_dir.resolve()
    crop = SupportedCrop(args.crop)
    records = read_manifest(args.manifest_dir / f"{crop}.csv")
    cache = EmbeddingCache(data_dir / "embeddings", DINOV2_SMALL)
    out_dir = data_dir / "reports" / "experiments"

    report = diagnostics(
        crop, records, cache, index_root(settings, data_dir) / args.index_version, args.k
    )
    atomic_write_bytes(
        out_dir / f"{crop}_{args.index_version}_diagnostics.json",
        (json.dumps(report, indent=2) + "\n").encode("utf-8"),
    )
    print(json.dumps(report, indent=2))

    if args.experiments:
        result = experiments(crop, records, cache, data_dir, args.k)
        atomic_write_bytes(
            out_dir / f"{crop}_{args.index_version}_experiments.json",
            (json.dumps(result, indent=2) + "\n").encode("utf-8"),
        )
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
