"""Evaluate crop-filtered retrieval on the held-out evaluation images.

Usage (from apps/api):

    python scripts/evaluate_retrieval.py --data-dir C:/rootcause-data --index-version v1

Per crop: Recall@K (share of queries with at least one same-label reference in the top K),
Precision@K (share of top-K references with the query's label), top-1 label agreement, a
random-retrieval baseline for Precision@K, and embedding/search latency. Labels are dataset
annotations, not field ground truth.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from app.core.config import Settings
from app.services.retrieval.dataset_registry import (
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
from app.services.retrieval.reference_retriever import index_root

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--index-version", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--latency-samples", type=int, default=20)
    args = parser.parse_args(argv)

    settings = Settings()
    data_dir: Path | None = args.data_dir or settings.data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    data_dir = data_dir.resolve()
    spec = DINOV2_SMALL
    index = load_reference_index(index_root(settings, data_dir) / args.index_version, spec)
    cache = EmbeddingCache(data_dir / "embeddings", spec)
    embedder = Dinov2Embedder(default_model_dir(data_dir, spec), spec=spec)
    embedder.load()

    report: dict[str, object] = {"index_version": index.version, "k": args.k, "crops": {}}
    print(f"Index {index.version} · {spec.model_id} · K={args.k}")
    print("crop     queries  recall@K  precision@K  random P@K  top-1   search ms (p50)")
    all_eval_paths: list[Path] = []
    for crop in SupportedCrop:
        crop_index = index.for_crop(crop)
        indexed_ids = {m.reference_id for m in crop_index.metadata}
        evaluation = [r for r in read_manifest(args.manifest_dir / f"{crop}.csv")
                      if r.split == Split.EVALUATION]  # fmt: skip
        if any(r.reference_id in indexed_ids for r in evaluation):
            print(f"{crop}: evaluation image found in the index (leakage)", file=sys.stderr)
            return 1
        all_eval_paths += [resolve_local_uri(data_dir, r.image_uri) for r in evaluation]
        label_share = Counter(m.condition for m in crop_index.metadata)
        hits = precision = top1 = chance = 0.0
        search_ms: list[float] = []
        per_condition: dict[str, list[int]] = {}
        by_style: dict[str, list[tuple[int, int]]] = {}
        for record in evaluation:
            vector = cache.get(record.sha256)
            if vector is None:
                data = resolve_local_uri(data_dir, record.image_uri).read_bytes()
                vector = embedder.embed([data])[0]
            started = time.perf_counter()
            _, rows = crop_index.search(vector[None, :], args.k)
            search_ms.append((time.perf_counter() - started) * 1000)
            labels = [crop_index.metadata[i].condition for i in rows[0].tolist() if i >= 0]
            same = sum(label == record.condition for label in labels)
            hits += same > 0
            precision += same / len(labels)
            top1 += bool(labels) and labels[0] == record.condition
            chance += label_share[record.condition] / len(crop_index.metadata)
            per_condition.setdefault(record.condition, []).append(int(same > 0))
            first = bool(labels) and labels[0] == record.condition
            by_style.setdefault(record.image_style, []).append((int(same > 0), int(first)))
        n = len(evaluation)
        result = {
            "queries": n,
            "reference_vectors": len(crop_index.metadata),
            "recall_at_k": round(hits / n, 3),
            "precision_at_k": round(precision / n, 3),
            "random_precision_at_k": round(chance / n, 3),
            "top1_label_agreement": round(top1 / n, 3),
            "macro_recall_at_k": round(
                statistics.mean(sum(v) / len(v) for v in per_condition.values()), 3
            ),
            "by_query_style": {
                style: {
                    "queries": len(v),
                    "recall_at_k": round(sum(h for h, _ in v) / len(v), 3),
                    "top1_label_agreement": round(sum(t for _, t in v) / len(v), 3),
                }
                for style, v in sorted(by_style.items())
            },
            "search_ms_p50": round(statistics.median(search_ms), 3),
            "recall_at_k_by_condition": {
                c: round(sum(v) / len(v), 3) for c, v in sorted(per_condition.items())
            },
        }
        report["crops"][crop.value] = result  # type: ignore[index]
        print(
            f"{crop:<8} {n:>7} {result['recall_at_k']:>9} {result['precision_at_k']:>12} "
            f"{result['random_precision_at_k']:>11} {result['top1_label_agreement']:>6} "
            f"{result['search_ms_p50']:>17}"
        )
        styles = result["by_query_style"]
        assert isinstance(styles, dict)
        for style, values in styles.items():
            print(
                f"  {style} queries: {values['queries']:>4}  recall@K {values['recall_at_k']}"
                f"  top-1 {values['top1_label_agreement']}"
            )

    sample = all_eval_paths[: args.latency_samples]
    timings = []
    for path in sample:
        data = path.read_bytes()
        started = time.perf_counter()
        embedder.embed([data])
        timings.append((time.perf_counter() - started) * 1000)
    report["embedding_ms_per_image"] = {
        "samples": len(timings),
        "p50": round(statistics.median(timings), 1),
        "max": round(max(timings), 1),
        "device": "cpu",
    }
    print(f"Embedding latency (CPU, 1 image): p50 {report['embedding_ms_per_image']['p50']} ms "  # type: ignore[index]
          f"over {len(timings)} images")  # fmt: skip
    out = data_dir / "reports" / f"retrieval_eval_{index.version}.json"
    atomic_write_bytes(out, (json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(f"Report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
