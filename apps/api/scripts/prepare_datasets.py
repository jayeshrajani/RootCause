"""Download and prepare the crop reference datasets into validated manifests.

Usage (from apps/api, with the venv active):

    python scripts/prepare_datasets.py --data-dir C:/rootcause-data

Downloads are verified and cached under DATA_DIR/raw; git sources fetch only the needed image
files. Re-running reuses everything already present. No embeddings are generated here.
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import httpx
import py7zr
import truststore

from app.core.config import Settings
from app.services.retrieval.dataset_prep import (
    Candidate,
    InvalidImageError,
    SplitPlan,
    group_candidates,
    inspect_image,
    plantvillage_leaf_id,
    select_splits,
)
from app.services.retrieval.dataset_registry import (
    CONDITIONS,
    MENDELEY_RICE,
    MENDELEY_RICE_ARCHIVE,
    PLANTDOC,
    PLANTVILLAGE,
    DatasetSource,
    ManifestRecord,
    MediaType,
    Split,
    SupportedCrop,
    atomic_write_bytes,
    read_manifest,
    resolve_local_uri,
    validate_manifest,
    write_manifest,
)
from app.services.retrieval.downloads import DownloadError, download_file, is_verified

logger = logging.getLogger("prepare_datasets")

PILOT_REFERENCE_IMAGES = 300
PLANTVILLAGE_PER_CLASS = 40
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
EXTENSIONS: dict[MediaType, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "manifests"
_GIT_ENV = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}

Loader = Callable[[Sequence[str]], Iterator[tuple[str, bytes]]]


class PrepError(RuntimeError):
    """Preparation cannot continue; the message is safe to print."""


def _lines(values: Iterable[str]) -> bytes:
    return "".join(f"{value}\n" for value in values).encode()


def _git(
    *args: str, cwd: Path | None = None, data: bytes | None = None, network: bool = False
) -> bytes:
    command = ["git"]
    if network and os.name == "nt":
        # Use the Windows certificate store (corporate TLS inspection).
        command += ["-c", "http.sslBackend=schannel"]
    if cwd is not None:
        command += ["-C", str(cwd)]
    command += args
    result = subprocess.run(command, input=data, capture_output=True, env=_GIT_ENV, check=False)
    if result.returncode != 0:
        verb = next((a for a in args if not a.startswith("-") and "=" not in a), "?")
        lines = result.stderr.decode(errors="replace").strip().splitlines()
        raise PrepError(f"git {verb} failed: {lines[-1] if lines else result.returncode}")
    return result.stdout


class GitSource:
    """A blobless clone pinned to one commit; image files are fetched individually by object id."""

    def __init__(self, path: Path, source: DatasetSource) -> None:
        self.path = path
        self.url = source.url
        self.commit = source.version.removeprefix("git:")

    def ensure(self, *, offline: bool) -> None:
        if not (self.path / ".git").exists():
            if offline:
                raise PrepError(f"{self.path} is missing and --offline was given")
            logger.info("Cloning %s (file list only, no images)", self.url)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _git(
                "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--depth", "1",
                self.url, str(self.path), network=True,
            )  # fmt: skip
        has_commit = subprocess.run(
            ["git", "-C", str(self.path), "cat-file", "-e", f"{self.commit}^{{commit}}"],
            capture_output=True,
            env=_GIT_ENV,
            check=False,
        )
        if has_commit.returncode != 0:
            if offline:
                raise PrepError(f"commit {self.commit[:12]} missing and --offline was given")
            self._git("fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin",
                      self.commit, network=True)  # fmt: skip

    def _git(self, *args: str, data: bytes | None = None, network: bool = False) -> bytes:
        return _git(*args, cwd=self.path, data=data, network=network)

    def list_files(self, *paths: str) -> list[tuple[str, str]]:
        """(path, object id) for every file under `paths` at the pinned commit."""
        out = self._git("ls-tree", "-r", "-z", self.commit, "--", *paths)
        entries: list[tuple[str, str]] = []
        for item in out.split(b"\0"):
            if not item:
                continue
            meta, _, path = item.partition(b"\t")
            _mode, kind, oid = meta.decode().split()
            if kind == "blob":
                entries.append((path.decode("utf-8"), oid))
        return entries

    def ensure_blobs(self, oids: Iterable[str], *, offline: bool) -> None:
        unique = sorted(set(oids))
        check = self._git("cat-file", "--batch-check", data=_lines(unique)).decode()
        missing = [line.split()[0] for line in check.splitlines() if line.endswith(" missing")]
        if not missing:
            return
        if offline:
            raise PrepError(f"{len(missing)} files not downloaded yet and --offline was given")
        logger.info("Downloading %d files from %s", len(missing), self.url)
        for start in range(0, len(missing), 400):
            batch = _lines(missing[start : start + 400])
            for attempt in range(1, 4):
                try:
                    self._git(
                        "-c", "fetch.negotiationAlgorithm=noop", "fetch", "--quiet", "--no-tags",
                        "--no-write-fetch-head", "--recurse-submodules=no", "--filter=blob:none",
                        "--stdin", "origin", data=batch, network=True,
                    )  # fmt: skip
                    break
                except PrepError:
                    if attempt == 3:
                        raise
                    logger.warning("Fetch attempt %d/3 failed; retrying", attempt)
                    time.sleep(2.0**attempt)

    def read_blobs(self, oids: Sequence[str]) -> Iterator[tuple[str, bytes]]:
        for start in range(0, len(oids), 100):
            batch = oids[start : start + 100]
            out = self._git("cat-file", "--batch", data=_lines(batch))
            pos = 0
            for oid in batch:
                newline = out.index(b"\n", pos)
                header = out[pos:newline].decode().split()
                if len(header) != 3:
                    raise PrepError(f"object {oid[:12]} is missing")
                size = int(header[2])
                yield oid, out[newline + 1 : newline + 1 + size]
                pos = newline + 1 + size + 1


@dataclass(frozen=True, slots=True)
class RawItem:
    source_label: str
    source_image_id: str
    key: str
    data: bytes
    leaf_group: str | None = None


@dataclass(frozen=True, slots=True)
class SourceImage:
    source: DatasetSource
    crop: SupportedCrop
    source_label: str
    source_image_id: str
    key: str
    media_type: MediaType
    width: int
    height: int
    dhash_hex: str
    candidate: Candidate


@dataclass
class CropStats:
    candidates: Counter[str] = field(default_factory=Counter)
    rejected: Counter[str] = field(default_factory=Counter)


@dataclass
class Report:
    crops: dict[SupportedCrop, CropStats] = field(default_factory=lambda: defaultdict(CropStats))
    unknown_labels: Counter[str] = field(default_factory=Counter)


def collect(
    source: DatasetSource,
    items: Iterable[RawItem],
    crops: set[SupportedCrop],
    out: dict[SupportedCrop, list[SourceImage]],
    report: Report,
) -> None:
    for item in items:
        mapped = source.normalize(item.source_label)
        if mapped is None:
            report.unknown_labels[f"{source.id}: {item.source_label}"] += 1
            continue
        crop, condition = mapped
        if crop not in crops:
            continue
        stats = report.crops[crop]
        try:
            info = inspect_image(item.data)
        except InvalidImageError as exc:
            stats.rejected[f"{source.id}: {exc}"] += 1
            continue
        stats.candidates[source.id] += 1
        sha256 = hashlib.sha256(item.data).hexdigest()
        out[crop].append(
            SourceImage(
                source=source,
                crop=crop,
                source_label=item.source_label,
                source_image_id=item.source_image_id,
                key=item.key,
                media_type=info.media_type,
                width=info.width,
                height=info.height,
                dhash_hex=info.dhash_hex,
                candidate=Candidate(
                    condition=condition,
                    image_style=source.image_style,
                    sha256=sha256,
                    dhash=info.dhash,
                    variants=info.variants,
                    leaf_group=item.leaf_group,
                ),
            )
        )


def _http_client() -> httpx.Client:
    return httpx.Client(
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        timeout=httpx.Timeout(60, connect=20),
        headers={"User-Agent": "RootCause-dataset-prep/0.1"},
    )


def prepare_rice(data_dir: Path, client: httpx.Client, *, offline: bool) -> Path:
    raw = data_dir / "raw" / "rice"
    archive = raw / MENDELEY_RICE_ARCHIVE.filename
    if offline:
        if not is_verified(archive, MENDELEY_RICE_ARCHIVE):
            raise PrepError("rice archive missing or incomplete and --offline was given")
    else:
        logger.info("Rice: downloading/verifying %s", MENDELEY_RICE_ARCHIVE.filename)
        download_file(client, MENDELEY_RICE_ARCHIVE, archive)

    target = raw / "extracted"
    marker = target / ".complete"
    if marker.exists() and marker.read_text(encoding="utf-8") == MENDELEY_RICE_ARCHIVE.sha256:
        return target
    logger.info("Rice: extracting archive")
    with py7zr.SevenZipFile(archive, mode="r") as seven_zip:
        for name in seven_zip.getnames():
            parts = PurePosixPath(name.replace("\\", "/"))
            if parts.is_absolute() or ".." in parts.parts or ":" in name:
                raise PrepError("rice archive contains an unsafe path; refusing to extract")
        if target.exists():
            shutil.rmtree(target)
        seven_zip.extractall(path=target)
    marker.write_text(MENDELEY_RICE_ARCHIVE.sha256, encoding="utf-8")
    return target


def rice_items(folder: Path) -> Iterator[RawItem]:
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            yield RawItem(
                source_label=path.parent.name,
                source_image_id=path.relative_to(folder).as_posix(),
                key=str(path),
                data=path.read_bytes(),
            )


def read_files(keys: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    for key in keys:
        yield key, Path(key).read_bytes()


def plantdoc_items(
    repo: GitSource, crops: set[SupportedCrop], *, offline: bool
) -> Iterator[RawItem]:
    entries: list[tuple[str, str, str]] = []
    for path, oid in repo.list_files("train", "test"):
        parts = path.split("/")
        mapped = PLANTDOC.normalize(parts[1]) if len(parts) == 3 else None
        if mapped and mapped[0] in crops and PurePosixPath(parts[2]).suffix.lower():
            entries.append((path, oid, parts[1]))
    repo.ensure_blobs((oid for _, oid, _ in entries), offline=offline)
    by_oid: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, oid, label in entries:
        by_oid[oid].append((path, label))
    for oid, data in repo.read_blobs(sorted(by_oid)):
        for path, label in by_oid[oid]:
            yield RawItem(source_label=label, source_image_id=path, key=oid, data=data)


def plantvillage_items(
    repo: GitSource, crops: set[SupportedCrop], *, per_class: int, seed: int, offline: bool
) -> Iterator[RawItem]:
    (leaf_map_oid,) = [oid for path, oid in repo.list_files("leaf-map.json")]
    repo.ensure_blobs([leaf_map_oid], offline=offline)
    leaf_map = json.loads(next(repo.read_blobs([leaf_map_oid]))[1])

    by_class: dict[str, list[tuple[str, str, str | None]]] = defaultdict(list)
    for path, oid in repo.list_files("raw/color"):
        parts = path.split("/")
        mapped = PLANTVILLAGE.normalize(parts[2]) if len(parts) == 4 else None
        if mapped and mapped[0] in crops:
            by_class[parts[2]].append(
                (path, oid, plantvillage_leaf_id(parts[2], parts[3], leaf_map))
            )

    chosen: list[tuple[str, str, str, str | None]] = []
    for class_name, files in sorted(by_class.items()):
        files.sort(key=lambda f: hashlib.sha256(f"{seed}:{f[0]}".encode()).hexdigest())
        seen: set[str] = set()
        picked = 0
        for path, oid, leaf in files:
            leaf_key = leaf or f"file:{path}"
            if leaf_key in seen:
                continue
            seen.add(leaf_key)
            chosen.append((path, oid, class_name, leaf))
            picked += 1
            if picked == per_class:
                break

    repo.ensure_blobs((oid for _, oid, _, _ in chosen), offline=offline)
    by_oid: dict[str, list[tuple[str, str, str | None]]] = defaultdict(list)
    for path, oid, class_name, leaf in chosen:
        by_oid[oid].append((path, class_name, leaf))
    for oid, data in repo.read_blobs(sorted(by_oid)):
        for path, class_name, leaf in by_oid[oid]:
            yield RawItem(class_name, path, oid, data, leaf_group=leaf)


def build_crop(
    crop: SupportedCrop,
    images: Sequence[SourceImage],
    loaders: dict[str, Loader],
    data_dir: Path,
    manifest_dir: Path,
    *,
    reference_images: int,
    seed: int,
) -> tuple[list[ManifestRecord], dict[str, int]]:
    candidates = [image.candidate for image in images]
    groups = group_candidates(candidates)
    plan = SplitPlan(reference_per_condition=reference_images // len(CONDITIONS[crop]), seed=seed)
    selection = select_splits(candidates, groups, plan)

    records: list[ManifestRecord] = []
    for index, split in sorted(selection.splits.items()):
        image = images[index]
        reference_id = f"{crop}-{image.source.id}-{image.candidate.sha256[:12]}"
        folder = "references" if split == Split.REFERENCE else "evaluation"
        relative = f"{folder}/images/{crop}/{reference_id}{EXTENSIONS[image.media_type]}"
        records.append(
            ManifestRecord(
                reference_id=reference_id,
                crop=crop,
                condition=image.candidate.condition,
                source_label=image.source_label,
                dataset_source=image.source.id,
                dataset_version=image.source.version,
                source_image_id=image.source_image_id,
                image_uri=f"local://{relative}",
                sha256=image.candidate.sha256,
                dhash=image.dhash_hex,
                media_type=image.media_type,
                width=image.width,
                height=image.height,
                group_id=selection.group_ids[groups[index]],
                split=split,
                image_style=image.candidate.image_style,
                license=image.source.license,
                attribution=image.source.attribution,
                source_url=image.source.url,
            )
        )

    _write_images(records, images, selection.splits, loaders, data_dir)
    manifest_path = manifest_dir / f"{crop}.csv"
    write_manifest(manifest_path, records)
    reloaded = read_manifest(manifest_path)
    problems = validate_manifest(crop, reloaded)
    if problems:
        raise PrepError(f"{crop} manifest failed validation: {'; '.join(problems)}")
    return reloaded, {
        "duplicate_copies_dropped": selection.duplicates_dropped,
        "near_duplicates_skipped": selection.near_duplicates_skipped,
        "conflicting_label_groups": selection.conflicting_groups,
    }


def _write_images(
    records: Sequence[ManifestRecord],
    images: Sequence[SourceImage],
    splits: dict[int, Split],
    loaders: dict[str, Loader],
    data_dir: Path,
) -> None:
    targets: dict[str, dict[str, list[tuple[Path, str]]]] = defaultdict(lambda: defaultdict(list))
    for record, index in zip(records, sorted(splits), strict=True):
        image = images[index]
        path = resolve_local_uri(data_dir, record.image_uri)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256:
            continue
        targets[image.source.id][image.key].append((path, record.sha256))
    for source_id, by_key in targets.items():
        for key, data in loaders[source_id](sorted(by_key)):
            for path, sha256 in by_key[key]:
                if hashlib.sha256(data).hexdigest() != sha256:
                    raise PrepError(f"content changed for {path.name}")
                atomic_write_bytes(path, data)

    wanted = {resolve_local_uri(data_dir, r.image_uri) for r in records}
    crop = records[0].crop if records else None
    for folder in ("references", "evaluation"):
        managed = data_dir / folder / "images" / str(crop)
        if crop is None or not managed.is_dir():
            continue
        for stale in (p for p in managed.iterdir() if p.is_file() and p not in wanted):
            stale.unlink()


def summarize(records: Sequence[ManifestRecord]) -> dict[str, dict[str, dict[str, int]]]:
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for record in records:
        by_split = counts.setdefault(record.condition, {})
        styles = by_split.setdefault(record.split.value, {})
        styles[record.image_style] = styles.get(record.image_style, 0) + 1
    return dict(sorted(counts.items()))


def print_table(crop: SupportedCrop, counts: dict[str, dict[str, dict[str, int]]]) -> None:
    def cell(styles: dict[str, int]) -> str:
        return f"{sum(styles.values()):>4} ({styles.get('field', 0)}/{styles.get('lab', 0)})"

    print(f"\n{crop}: condition | reference (field/lab) | evaluation (field/lab)")
    totals: dict[str, Counter[str]] = {"reference": Counter(), "evaluation": Counter()}
    for condition in CONDITIONS[crop]:
        by_split = counts.get(condition, {})
        for split, styles in by_split.items():
            totals[split].update(styles)
        ref, ev = by_split.get("reference", {}), by_split.get("evaluation", {})
        print(f"  {condition:<24} {cell(ref):>16} {cell(ev):>16}")
    ref_total, ev_total = cell(dict(totals["reference"])), cell(dict(totals["evaluation"]))
    print(f"  {'TOTAL':<24} {ref_total:>16} {ev_total:>16}")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument(
        "--crops", nargs="+", choices=[c.value for c in SupportedCrop],
        default=[c.value for c in SupportedCrop],
    )  # fmt: skip
    parser.add_argument(
        "--reference-images",
        type=int,
        default=PILOT_REFERENCE_IMAGES,
        help="Approximate reference images per crop, split evenly across conditions.",
    )
    parser.add_argument("--plantvillage-per-class", type=int, default=PLANTVILLAGE_PER_CLASS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--offline", action="store_true", help="Fail instead of downloading.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data_dir: Path | None = args.data_dir or Settings().data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    data_dir = data_dir.resolve()
    crops = {SupportedCrop(c) for c in args.crops}
    images: dict[SupportedCrop, list[SourceImage]] = defaultdict(list)
    loaders: dict[str, Loader] = {}
    report = Report()

    try:
        with _http_client() as client:
            if SupportedCrop.RICE in crops:
                folder = prepare_rice(data_dir, client, offline=args.offline)
                loaders[MENDELEY_RICE.id] = read_files
                collect(MENDELEY_RICE, rice_items(folder), crops, images, report)
        if crops & {SupportedCrop.TOMATO, SupportedCrop.POTATO}:
            plantdoc = GitSource(data_dir / "raw" / "plantdoc", PLANTDOC)
            plantdoc.ensure(offline=args.offline)
            loaders[PLANTDOC.id] = plantdoc.read_blobs
            collect(PLANTDOC, plantdoc_items(plantdoc, crops, offline=args.offline),
                    crops, images, report)  # fmt: skip

            plantvillage = GitSource(data_dir / "raw" / "plantvillage", PLANTVILLAGE)
            plantvillage.ensure(offline=args.offline)
            loaders[PLANTVILLAGE.id] = plantvillage.read_blobs
            items = plantvillage_items(
                plantvillage, crops, per_class=args.plantvillage_per_class, seed=args.seed,
                offline=args.offline,
            )  # fmt: skip
            collect(PLANTVILLAGE, items, crops, images, report)

        summary: dict[str, object] = {}
        for crop in sorted(crops):
            records, dedupe = build_crop(
                crop, images[crop], loaders, data_dir, args.manifest_dir,
                reference_images=args.reference_images, seed=args.seed,
            )  # fmt: skip
            counts = summarize(records)
            print_table(crop, counts)
            stats = report.crops[crop]
            summary[crop.value] = {
                "valid_candidates_by_source": dict(sorted(stats.candidates.items())),
                "rejected": dict(sorted(stats.rejected.items())),
                **dedupe,
                "conditions_without_reference": [
                    c for c in CONDITIONS[crop] if "reference" not in counts.get(c, {})
                ],
                "conditions_without_field_reference": [
                    c for c in CONDITIONS[crop]
                    if not counts.get(c, {}).get("reference", {}).get("field")
                ],
                "counts": counts,
            }  # fmt: skip
        summary["unknown_source_labels"] = dict(sorted(report.unknown_labels.items()))
    except (PrepError, DownloadError, OSError, httpx.HTTPError) as exc:
        logger.error("%s", exc)
        return 1

    summary_path = args.manifest_dir / "summary.json"
    atomic_write_bytes(summary_path, (json.dumps(summary, indent=2) + "\n").encode("utf-8"))
    print(f"\nManifests and summary written to {args.manifest_dir}")
    if report.unknown_labels:
        print(f"Skipped unknown source labels: {dict(report.unknown_labels)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
