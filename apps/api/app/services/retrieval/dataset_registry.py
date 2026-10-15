"""Supported crops, reference dataset sources, label normalisation and the manifest schema.

Dataset labels describe what each source annotated. They are not ground truth for urgency,
treatment or field diagnosis.
"""

import csv
import io
import os
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SupportedCrop(StrEnum):
    RICE = "rice"
    TOMATO = "tomato"
    POTATO = "potato"


class Split(StrEnum):
    REFERENCE = "reference"
    EVALUATION = "evaluation"


ImageStyle = Literal["field", "lab"]
MediaType = Literal["image/jpeg", "image/png", "image/webp"]

# Images within this many bits of 64-bit dHash are treated as near-duplicates.
NEAR_DUPLICATE_THRESHOLD = 6

CONDITIONS: Mapping[SupportedCrop, tuple[str, ...]] = {
    SupportedCrop.RICE: ("bacterial_blight", "blast", "brown_spot", "tungro"),
    SupportedCrop.TOMATO: (
        "bacterial_spot",
        "early_blight",
        "healthy",
        "late_blight",
        "leaf_mold",
        "mosaic_virus",
        "septoria_leaf_spot",
        "spider_mites",
        "target_spot",
        "yellow_leaf_curl_virus",
    ),
    SupportedCrop.POTATO: ("early_blight", "healthy", "late_blight"),
}


def label_key(label: str) -> str:
    """Match labels regardless of case, spacing and punctuation."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _labels(
    crop: SupportedCrop, mapping: Mapping[str, str]
) -> dict[str, tuple[SupportedCrop, str]]:
    return {label_key(label): (crop, condition) for label, condition in mapping.items()}


@dataclass(frozen=True, slots=True)
class DatasetSource:
    id: str
    name: str
    version: str
    url: str
    license: str
    license_url: str
    citation: str
    attribution: str
    image_style: ImageStyle
    labels: Mapping[str, tuple[SupportedCrop, str]]

    def normalize(self, source_label: str) -> tuple[SupportedCrop, str] | None:
        """Map an original dataset label to (crop, canonical condition), or None if unsupported."""
        return self.labels.get(label_key(source_label))


@dataclass(frozen=True, slots=True)
class RemoteFile:
    url: str
    filename: str
    size: int
    sha256: str


# Replaces Paddy Doctor, whose IEEE DataPort files require a paid subscription.
MENDELEY_RICE = DatasetSource(
    id="mendeley_rice",
    name="Rice Leaf Disease Image Samples",
    version="v2 (doi:10.17632/fwcj7stb8r.2)",
    url="https://data.mendeley.com/datasets/fwcj7stb8r/2",
    license="CC BY 4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    citation=(
        "Sethy, P. K. (2024). Rice Leaf Disease Image Samples. Mendeley Data, V2, "
        "doi:10.17632/fwcj7stb8r.2. Sethy et al. (2020), Computers and Electronics in "
        "Agriculture 175:105527, doi:10.1016/j.compag.2020.105527"
    ),
    attribution="Sethy (2024), Rice Leaf Disease Image Samples, doi:10.17632/fwcj7stb8r.2",
    image_style="field",
    labels=_labels(
        SupportedCrop.RICE,
        {
            "Bacterial blight": "bacterial_blight",
            "Blast": "blast",
            "Brown spot": "brown_spot",
            "Tungro": "tungro",
        },
    ),
)

MENDELEY_RICE_ARCHIVE = RemoteFile(
    url=(
        "https://data.mendeley.com/public-files/datasets/fwcj7stb8r/files/"
        "fd8717c4-0d65-4c80-a76c-3b61cb68e80d/file_downloaded"
    ),
    filename="Rice Leaf Disease Images.7z",
    size=179_355_409,
    sha256="b2d5fbef5a8ef6adefa04a83be7ee5150091f412d40162ecdf9fd2b1b5e24aaf",
)

PLANTDOC = DatasetSource(
    id="plantdoc",
    name="PlantDoc (cropped classification set)",
    version="git:5467f6012d78d1c446145d5f582da6096f852ae8",
    url="https://github.com/pratikkayal/PlantDoc-Dataset",
    license="CC BY 4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    citation=(
        "Singh, Jain, Jain, Kayal, Kumawat and Batra (2020). PlantDoc: A Dataset for Visual "
        "Plant Disease Detection. CoDS-COMAD 2020, doi:10.1145/3371158.3371196"
    ),
    attribution="Singh et al. (2020), PlantDoc, doi:10.1145/3371158.3371196",
    image_style="field",
    labels={
        **_labels(
            SupportedCrop.TOMATO,
            {
                "Tomato leaf": "healthy",
                "Tomato leaf bacterial spot": "bacterial_spot",
                "Tomato Early blight leaf": "early_blight",
                "Tomato leaf late blight": "late_blight",
                "Tomato mold leaf": "leaf_mold",
                "Tomato leaf mosaic virus": "mosaic_virus",
                "Tomato Septoria leaf spot": "septoria_leaf_spot",
                "Tomato two spotted spider mites leaf": "spider_mites",
                "Tomato leaf yellow virus": "yellow_leaf_curl_virus",
            },
        ),
        **_labels(
            SupportedCrop.POTATO,
            {
                "Potato leaf early blight": "early_blight",
                "Potato leaf late blight": "late_blight",
            },
        ),
    },
)

PLANTVILLAGE = DatasetSource(
    id="plantvillage",
    name="PlantVillage (colour images)",
    version="git:7f7ecc7e1eaca78107e3affe7cb5abd9427e139a",
    url="https://github.com/spMohanty/PlantVillage-Dataset",
    license="CC BY-SA 3.0",
    license_url="https://creativecommons.org/licenses/by-sa/3.0/",
    citation=(
        "Mohanty, Hughes and Salathé (2016). Using deep learning for image-based plant disease "
        "detection. Frontiers in Plant Science 7:1419, doi:10.3389/fpls.2016.01419"
    ),
    attribution="Mohanty, Hughes and Salathé (2016), PlantVillage, doi:10.3389/fpls.2016.01419",
    image_style="lab",
    labels={
        **_labels(
            SupportedCrop.TOMATO,
            {
                "Tomato___healthy": "healthy",
                "Tomato___Bacterial_spot": "bacterial_spot",
                "Tomato___Early_blight": "early_blight",
                "Tomato___Late_blight": "late_blight",
                "Tomato___Leaf_Mold": "leaf_mold",
                "Tomato___Tomato_mosaic_virus": "mosaic_virus",
                "Tomato___Septoria_leaf_spot": "septoria_leaf_spot",
                "Tomato___Spider_mites Two-spotted_spider_mite": "spider_mites",
                "Tomato___Target_Spot": "target_spot",
                "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "yellow_leaf_curl_virus",
            },
        ),
        **_labels(
            SupportedCrop.POTATO,
            {
                "Potato___healthy": "healthy",
                "Potato___Early_blight": "early_blight",
                "Potato___Late_blight": "late_blight",
            },
        ),
    },
)

SOURCES: Mapping[str, DatasetSource] = {
    source.id: source for source in (MENDELEY_RICE, PLANTDOC, PLANTVILLAGE)
}


class ManifestRecord(BaseModel):
    """One image in a crop manifest, with enough provenance to trace it to its source."""

    model_config = ConfigDict(frozen=True)

    reference_id: str = Field(pattern=r"^(rice|tomato|potato)-[a-z0-9_]+-[0-9a-f]{12}$")
    crop: SupportedCrop
    condition: str
    source_label: str = Field(min_length=1)
    dataset_source: str
    dataset_version: str = Field(min_length=1)
    source_image_id: str = Field(min_length=1)
    image_uri: str = Field(pattern=r"^(local|gs)://\S+$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dhash: str = Field(pattern=r"^[0-9a-f]{16}$")
    media_type: MediaType
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    group_id: str = Field(min_length=1)
    split: Split
    image_style: ImageStyle
    license: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    source_url: str = Field(min_length=1)

    @model_validator(mode="after")
    def _known_values(self) -> Self:
        if self.condition not in CONDITIONS[self.crop]:
            raise ValueError(f"unknown condition {self.condition!r} for crop {self.crop}")
        if self.dataset_source not in SOURCES:
            raise ValueError(f"unknown dataset source {self.dataset_source!r}")
        return self


MANIFEST_FIELDS: tuple[str, ...] = tuple(ManifestRecord.model_fields)


def resolve_local_uri(data_dir: Path, uri: str) -> Path:
    """Map a `local://` image URI to a path inside `data_dir`, refusing anything that escapes it."""
    if not uri.startswith("local://"):
        raise ValueError("not a local:// URI")
    relative = PurePosixPath(uri.removeprefix("local://"))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe local URI")
    return data_dir.joinpath(*relative.parts)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a temporary file and rename, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_manifest(path: Path, records: Iterable[ManifestRecord]) -> None:
    rows = sorted(records, key=lambda r: (r.split, r.condition, r.reference_id))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row.model_dump(mode="json") for row in rows)
    atomic_write_bytes(path, buffer.getvalue().encode("utf-8"))


def read_manifest(path: Path) -> list[ManifestRecord]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ValueError(f"{path.name}: unexpected manifest columns")
        return [ManifestRecord.model_validate(row) for row in reader]


def hamming(a_hex: str, b_hex: str) -> int:
    return (int(a_hex, 16) ^ int(b_hex, 16)).bit_count()


def validate_manifest(
    crop: SupportedCrop,
    records: Sequence[ManifestRecord],
    *,
    near_duplicate_threshold: int = NEAR_DUPLICATE_THRESHOLD,
) -> list[str]:
    """Return problems that would make the manifest unsafe to index or evaluate."""
    problems: list[str] = []
    for field in ("reference_id", "sha256", "image_uri"):
        repeated = [v for v, n in Counter(getattr(r, field) for r in records).items() if n > 1]
        if repeated:
            problems.append(f"duplicate {field} ({len(repeated)}), e.g. {repeated[0]}")

    other_crop = [r.reference_id for r in records if r.crop != crop]
    if other_crop:
        problems.append(f"{len(other_crop)} record(s) for another crop, e.g. {other_crop[0]}")

    splits_by_group: dict[str, set[Split]] = defaultdict(set)
    for record in records:
        splits_by_group[record.group_id].add(record.split)
    leaked = sorted(group for group, splits in splits_by_group.items() if len(splits) > 1)
    if leaked:
        problems.append(f"{len(leaked)} group(s) in both splits, e.g. {leaked[0]}")

    reference = [r for r in records if r.split == Split.REFERENCE]
    evaluation = [r for r in records if r.split == Split.EVALUATION]
    if not reference:
        problems.append("no reference images")
    if not evaluation:
        problems.append("no evaluation images")
    close = [
        (ref.reference_id, ev.reference_id)
        for ref in reference
        for ev in evaluation
        if hamming(ref.dhash, ev.dhash) <= near_duplicate_threshold
    ]
    if close:
        problems.append(
            f"{len(close)} near-duplicate reference/evaluation pair(s), e.g. {close[0]}"
        )
    return problems
