"""Resumable, checksum-verified HTTP downloads for offline dataset preparation."""

import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from app.services.retrieval.dataset_registry import RemoteFile

logger = logging.getLogger(__name__)

_CHUNK_BYTES = 1024 * 1024


class DownloadError(RuntimeError):
    """The file could not be downloaded or failed verification."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def is_verified(path: Path, remote: RemoteFile) -> bool:
    return (
        path.exists() and path.stat().st_size == remote.size and sha256_file(path) == remote.sha256
    )


def download_file(
    client: httpx.Client,
    remote: RemoteFile,
    dest: Path,
    *,
    attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Download `remote` to `dest`, resuming partial downloads and verifying size and SHA-256.

    A verified file already at `dest` is reused without any network request.
    """
    if is_verified(dest, remote):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            _fetch_into(client, remote, part)
            if not is_verified(part, remote):
                part.unlink(missing_ok=True)
                raise DownloadError("checksum mismatch")
            part.replace(dest)
            return dest
        except (httpx.HTTPError, DownloadError) as exc:
            if attempt == attempts:
                raise DownloadError(f"{remote.filename}: {exc}") from exc
            delay = float(2 ** (attempt - 1))
            logger.warning(
                "Download of %s failed (attempt %d/%d, %s); retrying in %.0fs",
                remote.filename,
                attempt,
                attempts,
                type(exc).__name__,
                delay,
            )
            sleep(delay)
    raise DownloadError(f"{remote.filename}: no download attempts were made")


def _fetch_into(client: httpx.Client, remote: RemoteFile, part: Path) -> None:
    offset = part.stat().st_size if part.exists() else 0
    if offset > remote.size:
        part.unlink()
        offset = 0
    if offset == remote.size:
        return
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with client.stream("GET", remote.url, headers=headers, follow_redirects=True) as response:
        if response.status_code == 206 and offset:
            mode = "ab"
        elif response.status_code == 200:
            mode = "wb"
        else:
            raise DownloadError(f"HTTP {response.status_code}")
        with part.open(mode) as handle:
            for chunk in response.iter_bytes(_CHUNK_BYTES):
                handle.write(chunk)
    if part.stat().st_size < remote.size:
        raise DownloadError("incomplete download")
