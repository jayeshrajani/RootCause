from fastapi import UploadFile, status

from app.core.errors import AppError
from app.models.report import ReportImage
from app.schemas.errors import ErrorDetail

ALLOWED_MEDIA_TYPES = ("image/jpeg", "image/png", "image/webp")


def detect_image_type(data: bytes) -> str | None:
    """Identify the image format from its magic bytes. The client-sent content type is ignored."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_error(status_code: int, code: str, message: str) -> AppError:
    return AppError(status_code, code, message, [ErrorDetail(field="images", message=message)])


async def read_validated_images(
    files: list[UploadFile], *, max_images: int, max_image_bytes: int
) -> tuple[ReportImage, ...]:
    if not files:
        raise _image_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "images_required",
            "Add at least one photo of the affected crop.",
        )
    if len(files) > max_images:
        raise _image_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "too_many_images",
            f"Add no more than {max_images} photos.",
        )

    max_mb = max_image_bytes / (1024 * 1024)
    images: list[ReportImage] = []
    for index, upload in enumerate(files, start=1):
        data = await upload.read(max_image_bytes + 1)
        if not data:
            raise _image_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "empty_image",
                f"Photo {index} is empty.",
            )
        if len(data) > max_image_bytes:
            raise _image_error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "image_too_large",
                f"Photo {index} is larger than {max_mb:g} MB.",
            )
        media_type = detect_image_type(data)
        if media_type is None:
            raise _image_error(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "unsupported_image_type",
                f"Photo {index} must be a JPEG, PNG or WebP image.",
            )
        images.append(ReportImage(media_type=media_type, data=data))
    return tuple(images)
