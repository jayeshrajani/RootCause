import pytest

from app.services.image_validation import detect_image_type


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"GIF89a", None),
        (b"%PDF-1.7", None),
        (b"", None),
    ],
)
def test_detect_image_type_uses_magic_bytes(data: bytes, expected: str | None) -> None:
    assert detect_image_type(data) == expected
