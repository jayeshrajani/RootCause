"""Offline dataset preparation: image checks, perceptual hashes, duplicate grouping and
leakage-free reference/evaluation splits."""

import hashlib
import io
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.services.retrieval.dataset_registry import (
    NEAR_DUPLICATE_THRESHOLD,
    ImageStyle,
    MediaType,
    Split,
)

MIN_IMAGE_SIDE = 32
# Copies (re-encodes, rotations, flips) differ by at most this many dHash bits. Larger values
# chain unrelated low-detail photos together through union-find.
COPY_THRESHOLD = 1
_MEDIA_TYPES: Mapping[str, MediaType] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class InvalidImageError(ValueError):
    """Bytes that are not a readable JPEG, PNG or WebP image of usable size."""


@dataclass(frozen=True, slots=True)
class ImageInfo:
    media_type: MediaType
    width: int
    height: int
    dhash: int
    # dHash of the image under all 8 rotations/flips (identity first), to catch augmented copies.
    variants: tuple[int, ...]

    @property
    def dhash_hex(self) -> str:
        return f"{self.dhash:016x}"


def _dhash(gray: Image.Image) -> int:
    pixels = np.asarray(gray.resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
    bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


def inspect_image(data: bytes) -> ImageInfo:
    """Fully decode the image and return its type, size and perceptual hashes."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = probe.format
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            thumb = image.convert("L").resize((64, 64), Image.Resampling.BILINEAR)
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError(f"unreadable ({type(exc).__name__})") from exc

    media_type = _MEDIA_TYPES.get(image_format or "")
    if media_type is None:
        raise InvalidImageError(f"unsupported format ({image_format or 'unknown'})")
    if min(width, height) < MIN_IMAGE_SIDE:
        raise InvalidImageError("too small")
    base = _dhash(thumb)
    variants = (base, *(_dhash(thumb.transpose(t)) for t in Image.Transpose))
    return ImageInfo(media_type, width, height, base, variants)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A valid source image considered for the manifest."""

    condition: str
    image_style: ImageStyle
    sha256: str
    dhash: int
    variants: tuple[int, ...]
    # Source-provided grouping, e.g. several photos of the same physical leaf.
    leaf_group: str | None = None


def group_candidates(
    candidates: Sequence[Candidate],
    *,
    threshold: int = COPY_THRESHOLD,
    chunk: int = 64,
) -> list[int]:
    """Group index per candidate: same bytes, same leaf, or a copy (incl. rotated/flipped)."""
    parent = list(range(len(candidates)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[max(root_i, root_j)] = min(root_i, root_j)

    first_seen: dict[str, int] = {}
    for index, candidate in enumerate(candidates):
        keys = [f"sha:{candidate.sha256}"]
        if candidate.leaf_group:
            keys.append(f"leaf:{candidate.leaf_group}")
        for key in keys:
            if key in first_seen:
                union(index, first_seen[key])
            else:
                first_seen[key] = index

    if candidates:
        bases = np.array([c.dhash for c in candidates], dtype=np.uint64)
        variants = np.array([c.variants for c in candidates], dtype=np.uint64)
        for start in range(0, len(candidates), chunk):
            block = variants[start : start + chunk]
            distances = np.bitwise_count(block[:, :, None] ^ bases[None, None, :]).min(axis=1)
            rows, cols = np.nonzero(distances <= threshold)
            for row, col in zip(rows.tolist(), cols.tolist(), strict=True):
                if start + row != col:
                    union(start + row, col)
    return [find(i) for i in range(len(candidates))]


@dataclass(frozen=True, slots=True)
class SplitPlan:
    reference_per_condition: int
    evaluation_fraction: float = 0.2
    max_evaluation_per_condition: int = 25
    near_duplicate_threshold: int = NEAR_DUPLICATE_THRESHOLD
    seed: int = 42


@dataclass(frozen=True, slots=True)
class Selection:
    splits: dict[int, Split]
    """Candidate index -> split. One representative per group; other members are unused."""
    group_ids: dict[int, str]
    """Group index -> stable group id."""
    conflicting_groups: int
    duplicates_dropped: int
    near_duplicates_skipped: int


def _order(seed: int, sha256: str) -> str:
    return hashlib.sha256(f"{seed}:{sha256}".encode()).hexdigest()


def _is_near(candidate: Candidate, chosen: Sequence[int], threshold: int) -> bool:
    return any((v ^ base).bit_count() <= threshold for base in chosen for v in candidate.variants)


def select_splits(
    candidates: Sequence[Candidate], groups: Sequence[int], plan: SplitPlan
) -> Selection:
    """Pick one image per group and assign whole groups to evaluation or reference.

    Evaluation takes a share of each condition's groups from every image style; reference is
    then filled with field images first, up to the per-condition quota. An image near any
    evaluation image, or near one already chosen for its split, is skipped (checked pairwise,
    including rotations). Groups whose members carry different labels are excluded.
    """
    members: dict[int, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        members[group].append(index)

    group_ids: dict[int, str] = {}
    representatives: dict[str, list[int]] = defaultdict(list)
    conflicting = duplicates = 0
    for group, indices in members.items():
        group_ids[group] = "g" + min(candidates[i].sha256 for i in indices)[:16]
        if len({candidates[i].condition for i in indices}) > 1:
            conflicting += 1
            continue
        duplicates += len(indices) - 1
        rep = min(
            indices, key=lambda i: (candidates[i].image_style != "field", candidates[i].sha256)
        )
        representatives[candidates[rep].condition].append(rep)

    splits: dict[int, Split] = {}
    pools: dict[str, tuple[list[int], list[int]]] = {}
    evaluation_hashes: list[int] = []
    skipped = 0
    for condition in sorted(representatives):
        reps = sorted(
            representatives[condition], key=lambda i: _order(plan.seed, candidates[i].sha256)
        )
        field = [i for i in reps if candidates[i].image_style == "field"]
        lab = [i for i in reps if candidates[i].image_style != "field"]
        pools[condition] = (field, lab)
        n_eval = min(plan.max_evaluation_per_condition, round(plan.evaluation_fraction * len(reps)))
        if len(reps) >= 2:
            n_eval = max(n_eval, 1)
        n_eval_field = min(len(field), round(n_eval * len(field) / len(reps)))
        n_eval_lab = min(len(lab), n_eval - n_eval_field)
        for pool, quota in ((field, n_eval_field), (lab, n_eval_lab)):
            taken = 0
            for i in pool:
                if taken == quota:
                    break
                if _is_near(candidates[i], evaluation_hashes, plan.near_duplicate_threshold):
                    skipped += 1
                    continue
                splits[i] = Split.EVALUATION
                evaluation_hashes.append(candidates[i].dhash)
                taken += 1

    reference_hashes: list[int] = []
    for field, lab in pools.values():
        taken = 0
        for i in field + lab:
            if taken == plan.reference_per_condition:
                break
            if i in splits:
                continue
            if _is_near(
                candidates[i], evaluation_hashes + reference_hashes, plan.near_duplicate_threshold
            ):
                skipped += 1
                continue
            splits[i] = Split.REFERENCE
            reference_hashes.append(candidates[i].dhash)
            taken += 1
    return Selection(splits, group_ids, conflicting, duplicates, skipped)


def plantvillage_leaf_id(
    class_name: str, file_name: str, leaf_map: Mapping[str, Sequence[str]]
) -> str | None:
    """Physical-leaf id from PlantVillage's leaf map, mirroring the dataset's own loader."""
    ident = file_name.replace("_final_masked", "")
    if "___" in ident:
        ident = ident.split("___")[-1]
    ident = ident.split("copy")[0]
    for ext in (".jpg", ".JPG", ".png", ".PNG"):
        ident = ident.replace(ext, "")
    suggestions = leaf_map.get(ident.lower().strip(), ())
    if len(suggestions) == 1:
        return suggestions[0]
    return next((s for s in suggestions if class_name in s), None)
