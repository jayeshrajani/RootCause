"""Google Cloud Speech-to-Text V2 client for short recordings (synchronous `recognize`).

REST rather than the gRPC SDK, so TLS uses the OS certificate store (truststore) like the other
integrations. Credentials come only from Application Default Credentials.
"""

import asyncio
import base64
import logging
import re
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
import truststore
from google.auth.exceptions import GoogleAuthError

logger = logging.getLogger(__name__)

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_LOCATION = re.compile(r"^[a-z0-9-]{2,32}$")

SpeechErrorKind = Literal["auth", "timeout", "unavailable", "rejected", "bad_response"]
AuthHeaders = Callable[[], dict[str, str]]


class SpeechError(Exception):
    """The provider call failed. `kind` and the message are safe to log."""

    def __init__(self, kind: SpeechErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class SpeechResult:
    transcript: str
    language_code: str | None


class SpeechRecognizer(Protocol):
    async def recognize(self, audio: bytes, language_code: str) -> SpeechResult: ...


def adc_auth_headers() -> AuthHeaders:
    """Authorization (and quota-project) headers from Application Default Credentials."""
    import google.auth
    import google.auth.transport.urllib3
    import urllib3

    http = urllib3.PoolManager(ssl_context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    lock = threading.Lock()
    state: dict[str, Any] = {}

    def headers() -> dict[str, str]:
        with lock:
            credentials = state.get("credentials")
            if credentials is None:
                credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
                state["credentials"] = credentials
            if not credentials.valid:
                credentials.refresh(google.auth.transport.urllib3.Request(http))  # type: ignore[no-untyped-call]
            out: dict[str, str] = {}
            credentials.apply(out)
            return out

    return headers


class GoogleSpeechClient:
    def __init__(
        self,
        *,
        project_id: str,
        location: str = "us",
        model: str = "chirp_3",
        timeout_seconds: float = 30,
        auth_headers: AuthHeaders | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not _PROJECT_ID.fullmatch(project_id) or not _LOCATION.fullmatch(location):
            raise ValueError("invalid Google Cloud project ID or location")
        self.model = model
        self._project_id = project_id
        self._location = location
        self._timeout = timeout_seconds
        self._auth_headers = auth_headers or adc_auth_headers()
        self._transport = transport

    @property
    def endpoint(self) -> str:
        return (
            f"https://{self._location}-speech.googleapis.com/v2/projects/{self._project_id}"
            f"/locations/{self._location}/recognizers/_:recognize"
        )

    async def recognize(self, audio: bytes, language_code: str) -> SpeechResult:
        try:
            headers = await asyncio.to_thread(self._auth_headers)
        except GoogleAuthError as exc:
            raise SpeechError(
                "auth", f"Google credentials unavailable ({type(exc).__name__})"
            ) from exc

        body = {
            "config": {
                "autoDecodingConfig": {},
                "languageCodes": [language_code],
                "model": self.model,
            },
            "content": base64.b64encode(audio).decode("ascii"),
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                response = await client.post(self.endpoint, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise SpeechError("timeout", "Speech-to-Text request timed out") from exc
        except httpx.HTTPError as exc:
            raise SpeechError(
                "unavailable", f"Speech-to-Text request failed: {type(exc).__name__}"
            ) from exc

        status = response.status_code
        if status in (401, 403):
            raise SpeechError("auth", f"Speech-to-Text rejected the credentials (HTTP {status})")
        if status == 400:
            raise SpeechError("rejected", "Speech-to-Text could not process the audio (HTTP 400)")
        if status != 200:
            raise SpeechError("unavailable", f"Speech-to-Text returned HTTP {status}")

        try:
            results = response.json().get("results") or []
            parts = [
                str(result["alternatives"][0].get("transcript", "")).strip()
                for result in results
                if result.get("alternatives")
            ]
            language = next(
                (str(r["languageCode"]) for r in results if r.get("languageCode")), None
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise SpeechError(
                "bad_response", "Speech-to-Text returned an unexpected payload"
            ) from exc

        logger.info(
            "Speech-to-Text model=%s language=%s audio_bytes=%d results=%d elapsed_ms=%d",
            self.model,
            language_code,
            len(audio),
            len(results),
            (time.perf_counter() - started) * 1000,
        )
        return SpeechResult(" ".join(part for part in parts if part), language)
