import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.services.retrieval.dataset_registry import RemoteFile
from app.services.retrieval.downloads import DownloadError, download_file

PAYLOAD = bytes(range(256)) * 40
REMOTE = RemoteFile(
    url="https://example.test/archive.7z",
    filename="archive.7z",
    size=len(PAYLOAD),
    sha256=hashlib.sha256(PAYLOAD).hexdigest(),
)


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_downloads_and_verifies(tmp_path: Path) -> None:
    dest = tmp_path / "archive.7z"

    with client_for(lambda _: httpx.Response(200, content=PAYLOAD)) as client:
        download_file(client, REMOTE, dest)

    assert dest.read_bytes() == PAYLOAD
    assert not (tmp_path / "archive.7z.part").exists()


def test_resumes_a_partial_download(tmp_path: Path) -> None:
    dest = tmp_path / "archive.7z"
    (tmp_path / "archive.7z.part").write_bytes(PAYLOAD[:1000])
    ranges: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ranges.append(request.headers.get("range"))
        return httpx.Response(206, content=PAYLOAD[1000:])

    with client_for(handler) as client:
        download_file(client, REMOTE, dest)

    assert ranges == ["bytes=1000-"]
    assert dest.read_bytes() == PAYLOAD


def test_verified_file_is_reused_without_network(tmp_path: Path) -> None:
    dest = tmp_path / "archive.7z"
    dest.write_bytes(PAYLOAD)

    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with client_for(handler) as client:
        download_file(client, REMOTE, dest)


def test_corrupt_downloads_are_retried_then_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "archive.7z"
    delays: list[float] = []
    corrupt = b"x" * len(PAYLOAD)

    with (
        client_for(lambda _: httpx.Response(200, content=corrupt)) as client,
        pytest.raises(DownloadError, match="checksum"),
    ):
        download_file(client, REMOTE, dest, attempts=3, sleep=delays.append)

    assert delays == [1.0, 2.0]
    assert not dest.exists()


def test_server_errors_are_retried(tmp_path: Path) -> None:
    dest = tmp_path / "archive.7z"
    responses = [httpx.Response(503), httpx.Response(200, content=PAYLOAD)]

    with client_for(lambda _: responses.pop(0)) as client:
        download_file(client, REMOTE, dest, sleep=lambda _: None)

    assert dest.read_bytes() == PAYLOAD
