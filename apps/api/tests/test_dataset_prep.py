import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from app.services.retrieval.dataset_prep import (
    Candidate,
    InvalidImageError,
    SplitPlan,
    group_candidates,
    inspect_image,
    plantvillage_leaf_id,
    select_splits,
)
from app.services.retrieval.dataset_registry import ImageStyle, Split


def image_bytes(
    seed: int,
    *,
    size: tuple[int, int] = (96, 72),
    fmt: str = "PNG",
    transpose: Image.Transpose | None = None,
) -> bytes:
    rng = np.random.default_rng(seed)
    image = Image.fromarray(rng.integers(0, 256, (6, 8, 3), dtype=np.uint8)).resize(
        size, Image.Resampling.BICUBIC
    )
    if transpose is not None:
        image = image.transpose(transpose)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def candidate_from(
    data: bytes, condition: str = "blast", style: ImageStyle = "field", leaf: str | None = None
) -> Candidate:
    info = inspect_image(data)
    return Candidate(
        condition, style, hashlib.sha256(data).hexdigest(), info.dhash, info.variants, leaf
    )


def synthetic(index: int, condition: str = "blast", style: ImageStyle = "field") -> Candidate:
    rng = np.random.default_rng(1000 + index)
    dhash = int(rng.integers(0, 2**63, dtype=np.int64))
    return Candidate(condition, style, f"{index:064x}", dhash, (dhash,) * 8)


def test_inspect_image_reports_type_size_and_hashes() -> None:
    info = inspect_image(image_bytes(1, fmt="JPEG"))

    assert info.media_type == "image/jpeg"
    assert (info.width, info.height) == (96, 72)
    assert len(info.variants) == 8 and info.variants[0] == info.dhash
    assert len(info.dhash_hex) == 16


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"definitely not an image", "unreadable"),
        (image_bytes(1, fmt="JPEG")[:200], "unreadable"),
        (image_bytes(1, fmt="GIF"), "unsupported"),
        (image_bytes(1, size=(16, 16)), "too small"),
    ],
)
def test_inspect_image_rejects_unusable_files(data: bytes, message: str) -> None:
    with pytest.raises(InvalidImageError, match=message):
        inspect_image(data)


def test_grouping_catches_exact_rotated_and_same_leaf_duplicates() -> None:
    original = image_bytes(1)
    candidates = [
        candidate_from(original),
        candidate_from(original),
        candidate_from(image_bytes(1, transpose=Image.Transpose.ROTATE_90)),
        candidate_from(image_bytes(1, transpose=Image.Transpose.FLIP_LEFT_RIGHT)),
        candidate_from(image_bytes(2)),
        candidate_from(image_bytes(3), leaf="leaf-7"),
        candidate_from(image_bytes(4), leaf="leaf-7"),
    ]

    groups = group_candidates(candidates)

    assert groups[0] == groups[1] == groups[2] == groups[3]
    assert groups[5] == groups[6]
    assert len({groups[0], groups[4], groups[5]}) == 3


def test_splits_keep_groups_whole_and_respect_quota() -> None:
    candidates = [synthetic(i) for i in range(12)]
    candidates.append(Candidate("blast", "field", candidates[0].sha256, 1, (1,) * 8))
    groups = group_candidates(candidates)

    selection = select_splits(candidates, groups, SplitPlan(reference_per_condition=5))

    splits_by_group: dict[int, set[Split]] = {}
    for index, split in selection.splits.items():
        splits_by_group.setdefault(groups[index], set()).add(split)
    assert all(len(s) == 1 for s in splits_by_group.values())
    assert len(splits_by_group) == len(selection.splits)
    assert list(selection.splits.values()).count(Split.EVALUATION) == 2
    assert list(selection.splits.values()).count(Split.REFERENCE) == 5
    assert selection.duplicates_dropped == 1


def test_groups_with_conflicting_labels_are_excluded() -> None:
    a = synthetic(1, "blast")
    b = Candidate("tungro", "field", a.sha256, a.dhash, a.variants)
    others = [synthetic(i, "tungro") for i in range(2, 6)]
    candidates = [a, b, *others]

    selection = select_splits(
        candidates, group_candidates(candidates), SplitPlan(reference_per_condition=10)
    )

    assert selection.conflicting_groups == 1
    assert 0 not in selection.splits and 1 not in selection.splits


def test_reference_prefers_field_images() -> None:
    candidates = [synthetic(i, style="field") for i in range(4)]
    candidates += [synthetic(i, style="lab") for i in range(4, 14)]

    selection = select_splits(
        candidates, group_candidates(candidates), SplitPlan(reference_per_condition=3)
    )

    reference = [i for i, s in selection.splits.items() if s == Split.REFERENCE]
    evaluation_styles = {
        candidates[i].image_style for i, s in selection.splits.items() if s == Split.EVALUATION
    }
    assert len(reference) == 3 and all(candidates[i].image_style == "field" for i in reference)
    assert evaluation_styles == {"field", "lab"}


def test_selection_is_deterministic() -> None:
    candidates = [synthetic(i, c) for i, c in enumerate(["blast", "tungro"] * 10)]
    groups = group_candidates(candidates)
    plan = SplitPlan(reference_per_condition=4)

    assert select_splits(candidates, groups, plan) == select_splits(candidates, groups, plan)


def test_near_duplicates_are_never_selected_together() -> None:
    candidates = [synthetic(i) for i in range(6)]
    near = candidates[0].dhash ^ 0b111
    candidates.append(Candidate("blast", "field", "f" * 64, near, (near,) * 8))
    groups = group_candidates(candidates)
    assert groups[0] != groups[6]

    selection = select_splits(candidates, groups, SplitPlan(reference_per_condition=10))

    assert selection.near_duplicates_skipped == 1
    assert not {0, 6} <= selection.splits.keys()


def test_plantvillage_leaf_id_follows_the_dataset_loader() -> None:
    leaf_map = {
        "rs_early.b 8178": ["Potato___Early_blight:::176.0"],
        "abc 1": ["Tomato___healthy:::1.0", "Potato___healthy:::1.0"],
    }

    assert (
        plantvillage_leaf_id("Potato___Early_blight", "u1___RS_Early.B 8178.JPG", leaf_map)
        == "Potato___Early_blight:::176.0"
    )
    assert (
        plantvillage_leaf_id("Potato___healthy", "u2___abc 1 copy.jpg", leaf_map)
        == "Potato___healthy:::1.0"
    )
    assert plantvillage_leaf_id("Tomato___Leaf_Mold", "u3___zz 9.JPG", leaf_map) is None
