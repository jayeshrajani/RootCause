"""Tune the reference-photo weight in evidence-fit scores on held-out field photos.

Usage (from apps/api, with retrieval configured and CEREBRAS_API_KEY set):

    python scripts/evaluate_hybrid.py --per-crop 10

Each sampled held-out photo (never in the index) gets one model call with its crop's reference
labels and one reference search. The model's causes are then re-ranked with reference weights
0/10/20/30 (0 = today's analysis-only ranking), counting how often the top cause names the photo's
dataset label. Labels are dataset annotations, not field ground truth, and samples are small.
"""

import argparse
import asyncio
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.cerebras import CerebrasClient
from app.models.references import ReferenceVotes
from app.models.report import FarmerReport, ReportImage
from app.schemas.triage import Crop
from app.services.retrieval.dataset_registry import (
    ManifestRecord,
    Split,
    SupportedCrop,
    read_manifest,
    resolve_local_uri,
)
from app.services.triage.ai import AiTriageService, _evidence_fit_score
from app.services.triage.references import (
    ReferenceUnavailableError,
    RetrievalReferenceProvider,
    match_label,
)

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"
WEIGHTS = (0, 10, 20, 30)


def sample(records: Sequence[ManifestRecord], count: int, seed: int) -> list[ManifestRecord]:
    """Round-robin across conditions so every label is represented."""
    rng = random.Random(seed)
    by_condition: dict[str, list[ManifestRecord]] = defaultdict(list)
    for record in records:
        by_condition[record.condition].append(record)
    for items in by_condition.values():
        rng.shuffle(items)
    picked: list[ManifestRecord] = []
    while len(picked) < count and any(by_condition.values()):
        for condition in sorted(by_condition):
            if by_condition[condition] and len(picked) < count:
                picked.append(by_condition[condition].pop())
    return picked


def top_label(
    causes: Sequence[tuple[int, str | None]], votes: ReferenceVotes | None, weight: int
) -> str | None:
    def fit(item: tuple[int, str | None]) -> int:
        analysis, label = item
        reference = votes.score(label) if votes and label else None
        return _evidence_fit_score(analysis, None, reference, weight)

    return max(causes, key=fit)[1]


async def evaluate(args: argparse.Namespace) -> int:
    settings = Settings()
    data_dir: Path | None = args.data_dir or settings.data_dir
    if settings.cerebras_api_key is None or data_dir is None:
        print("Set CEREBRAS_API_KEY and ROOTCAUSE_DATA_DIR (or --data-dir).", file=sys.stderr)
        return 2
    provider = RetrievalReferenceProvider(settings)
    provider.load()
    if provider.status != "ready":
        print("Reference library failed to load; see the log above.", file=sys.stderr)
        return 1
    client = CerebrasClient(
        api_key=settings.cerebras_api_key.get_secret_value(),
        model=settings.cerebras_model,
        base_url=settings.cerebras_base_url,
        timeout_seconds=settings.analysis_timeout_seconds,
        reasoning_effort=settings.cerebras_reasoning_effort,
    )
    service = AiTriageService(client, reference_provider=provider)

    tallies: dict[str, Counter[str]] = {}
    for crop in args.crops:
        tally = tallies.setdefault(crop, Counter())
        records = [
            r
            for r in read_manifest(args.manifest_dir / f"{crop}.csv")
            if r.split == Split.EVALUATION and r.image_style == "field" and r.condition != "healthy"
        ]
        for record in sample(records, args.per_crop, args.seed):
            path = resolve_local_uri(data_dir, record.image_uri)
            data = await asyncio.to_thread(path.read_bytes)
            report = FarmerReport(
                images=(ReportImage(media_type=record.media_type, data=data),),
                received_at=datetime.now(UTC),
                crop=Crop(crop),
            )
            try:
                assessment = await service._call_model(report)
            except AppError:
                tally["model_failed"] += 1
                continue
            causes = [
                (c.analysis_score, match_label(c.reference_label, crop))
                for c in assessment.possible_causes
            ]
            if not causes:
                tally["no_causes"] += 1
                continue
            try:
                votes: ReferenceVotes | None = await provider.find(crop, [data])
            except ReferenceUnavailableError:
                votes = None
            tally["photos"] += 1
            labels = {label for _, label in causes}
            tally["true_label_among_causes"] += record.condition in labels
            tally["references_top1"] += bool(votes and votes.counts[0][0] == record.condition)
            picks = {weight: top_label(causes, votes, weight) for weight in WEIGHTS}
            for weight, label in picks.items():
                tally[f"w{weight}"] += label == record.condition
            print(
                f"{crop:<7} {record.condition:<24} refs={votes.counts[0][0] if votes else '-':<22} "
                + " ".join(f"w{w}={picks[w] or '-'}" for w in WEIGHTS)
            )

    weights = "  ".join(f"w{w:<3}" for w in WEIGHTS)
    print(f"\ncrop     photos  label-in-causes  refs-top1  {weights}")
    for crop, tally in tallies.items():
        n = tally["photos"] or 1
        print(
            f"{crop:<8} {tally['photos']:>6}  {tally['true_label_among_causes'] / n:>15.2f}  "
            f"{tally['references_top1'] / n:>9.2f}  "
            + "  ".join(f"{tally[f'w{w}'] / n:.2f}" for w in WEIGHTS)
            + (f"  (model failures: {tally['model_failed']})" if tally["model_failed"] else "")
        )
    print("\nTop-1 = share of photos whose top cause names the dataset label (w0 = AI only).")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument(
        "--crops", nargs="+", choices=[c.value for c in SupportedCrop],
        default=[c.value for c in SupportedCrop],
    )  # fmt: skip
    parser.add_argument("--per-crop", type=int, default=10, help="Model calls per crop.")
    parser.add_argument("--seed", type=int, default=7)
    return asyncio.run(evaluate(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
