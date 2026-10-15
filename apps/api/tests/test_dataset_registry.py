from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.retrieval.dataset_registry import (
    CONDITIONS,
    MANIFEST_FIELDS,
    MENDELEY_RICE,
    PLANTDOC,
    PLANTVILLAGE,
    SOURCES,
    ManifestRecord,
    SupportedCrop,
    read_manifest,
    resolve_local_uri,
    validate_manifest,
    write_manifest,
)


def record(**overrides: Any) -> ManifestRecord:
    base: dict[str, Any] = {
        "reference_id": "tomato-plantdoc-0123456789ab",
        "crop": "tomato",
        "condition": "late_blight",
        "source_label": "Tomato leaf late blight",
        "dataset_source": "plantdoc",
        "dataset_version": PLANTDOC.version,
        "source_image_id": "train/Tomato leaf late blight/a.jpg?itok=x.jpg",
        "image_uri": "local://references/images/tomato/tomato-plantdoc-0123456789ab.jpg",
        "sha256": "a" * 64,
        "dhash": "0000000000000000",
        "media_type": "image/jpeg",
        "width": 256,
        "height": 256,
        "group_id": "g1",
        "split": "reference",
        "image_style": "field",
        "license": PLANTDOC.license,
        "attribution": PLANTDOC.attribution,
        "source_url": PLANTDOC.url,
    }
    return ManifestRecord.model_validate(base | overrides)


def evaluation_record(**overrides: Any) -> ManifestRecord:
    defaults: dict[str, Any] = {
        "reference_id": "tomato-plantdoc-bbbbbbbbbbbb",
        "image_uri": "local://evaluation/images/tomato/tomato-plantdoc-bbbbbbbbbbbb.jpg",
        "sha256": "b" * 64,
        "dhash": "ffffffffffffffff",
        "group_id": "g2",
        "split": "evaluation",
    }
    return record(**(defaults | overrides))


def test_every_source_label_maps_to_a_known_condition() -> None:
    for source in SOURCES.values():
        assert source.labels, source.id
        for crop, condition in source.labels.values():
            assert condition in CONDITIONS[crop], (source.id, condition)


@pytest.mark.parametrize(
    ("source_id", "label", "expected"),
    [
        ("plantdoc", "Tomato leaf", ("tomato", "healthy")),
        ("plantdoc", "tomato  LEAF late-blight", ("tomato", "late_blight")),
        ("plantdoc", "Potato leaf early blight", ("potato", "early_blight")),
        ("plantvillage", "Potato___healthy", ("potato", "healthy")),
        (
            "plantvillage",
            "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
            ("tomato", "yellow_leaf_curl_virus"),
        ),
        ("mendeley_rice", "Brownspot", ("rice", "brown_spot")),
        ("mendeley_rice", "BACTERIAL_BLIGHT", ("rice", "bacterial_blight")),
    ],
)
def test_labels_normalise_regardless_of_case_and_punctuation(
    source_id: str, label: str, expected: tuple[str, str]
) -> None:
    assert SOURCES[source_id].normalize(label) == expected


@pytest.mark.parametrize(
    ("source_id", "label"),
    [
        ("plantdoc", "Bell_pepper leaf"),
        ("plantvillage", "Apple___healthy"),
        ("mendeley_rice", "Healthy"),
        ("mendeley_rice", "Leaf smut"),
    ],
)
def test_unsupported_labels_are_not_mapped(source_id: str, label: str) -> None:
    assert SOURCES[source_id].normalize(label) is None


def test_rice_has_only_the_four_supported_diseases() -> None:
    assert CONDITIONS[SupportedCrop.RICE] == ("bacterial_blight", "blast", "brown_spot", "tungro")
    assert {c for _, c in MENDELEY_RICE.labels.values()} == set(CONDITIONS[SupportedCrop.RICE])


def test_sources_record_licence_and_pinned_version() -> None:
    assert MENDELEY_RICE.license == "CC BY 4.0"
    assert "10.17632/fwcj7stb8r.2" in MENDELEY_RICE.version
    assert PLANTDOC.license == "CC BY 4.0"
    assert PLANTVILLAGE.license == "CC BY-SA 3.0"
    for source in (PLANTDOC, PLANTVILLAGE):
        assert source.version.startswith("git:") and len(source.version) == 44


def test_manifest_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "tomato.csv"
    records = [record(), evaluation_record()]

    write_manifest(path, records)

    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(MANIFEST_FIELDS)
    assert sorted(read_manifest(path), key=lambda r: r.reference_id) == records


def test_read_manifest_rejects_unexpected_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("reference_id,crop\nx,tomato\n", encoding="utf-8")

    with pytest.raises(ValueError, match="columns"):
        read_manifest(path)


@pytest.mark.parametrize(
    "overrides",
    [
        {"condition": "blast"},
        {"dataset_source": "unknown"},
        {"image_uri": "file:///etc/passwd"},
        {"sha256": "xyz"},
        {"split": "train"},
        {"reference_id": "tomato plantdoc 1"},
    ],
)
def test_record_rejects_invalid_values(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        record(**overrides)


def test_clean_manifest_has_no_problems() -> None:
    assert validate_manifest(SupportedCrop.TOMATO, [record(), evaluation_record()]) == []


def test_validation_detects_group_in_both_splits() -> None:
    problems = validate_manifest(SupportedCrop.TOMATO, [record(), evaluation_record(group_id="g1")])

    assert any("both splits" in p for p in problems)


def test_validation_detects_near_duplicate_across_splits() -> None:
    near = evaluation_record(dhash="0000000000000003")

    problems = validate_manifest(SupportedCrop.TOMATO, [record(), near])

    assert any("near-duplicate" in p for p in problems)


def test_validation_detects_duplicates_wrong_crop_and_missing_split() -> None:
    other_crop = record(
        reference_id="potato-plantdoc-cccccccccccc",
        crop="potato",
        condition="late_blight",
        image_uri="local://references/images/potato/x.jpg",
        sha256="c" * 64,
        group_id="g3",
    )
    duplicate = record(
        reference_id="tomato-plantdoc-dddddddddddd",
        image_uri="local://references/images/tomato/d.jpg",
        group_id="g4",
    )

    problems = validate_manifest(SupportedCrop.TOMATO, [record(), duplicate, other_crop])

    assert any("duplicate sha256" in p for p in problems)
    assert any("another crop" in p for p in problems)
    assert "no evaluation images" in problems


def test_resolve_local_uri_stays_inside_data_dir(tmp_path: Path) -> None:
    assert resolve_local_uri(tmp_path, "local://references/images/rice/a.jpg") == (
        tmp_path / "references" / "images" / "rice" / "a.jpg"
    )
    for uri in ("local://../secret.txt", "local:///etc/passwd", "gs://bucket/a.jpg", "local://"):
        with pytest.raises(ValueError):
            resolve_local_uri(tmp_path, uri)
