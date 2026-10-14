from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response


class RequestSizeLimitMiddleware:
    """Reject requests whose Content-Length exceeds the limit before the body is read."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                    response = error_response(
                        413,
                        "request_too_large",
                        f"The upload is larger than {self.max_bytes // (1024 * 1024)} MB in total.",
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
