import base64
import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError

from app.api.deps import get_transcription_service
from app.core.config import Settings, get_settings
from app.integrations.gemini_speech import GeminiSpeechClient
from app.integrations.google_speech import GoogleSpeechClient, SpeechError
from app.main import create_app
from app.services.transcription import (
    FallbackRecognizer,
    TranscriptionService,
    detect_audio_type,
)

WEBM = b"\x1aE\xdf\xa3" + b"\x42" * 2048
OGG = b"OggS" + b"\x00" * 2048
WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 2048
FLAC = b"fLaC" + b"\x00" * 2048
MP4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 2048
HINDI = "मेरे टमाटर के पत्ते पीले हो रहे हैं"

Handler = Callable[[httpx.Request], httpx.Response]


def speech_response(*transcripts: str, language: str = "hi-in") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "results": [
                {"alternatives": [{"transcript": t}], "languageCode": language} for t in transcripts
            ]
        },
    )


def fake_headers() -> dict[str, str]:
    return {"authorization": "Bearer test-token"}


def service_for(
    handler: Handler, auth: Callable[[], dict[str, str]] = fake_headers
) -> TranscriptionService:
    client = GoogleSpeechClient(
        project_id="rootcause-test",
        auth_headers=auth,
        transport=httpx.MockTransport(handler),
    )
    return TranscriptionService(client)


@pytest.fixture
def speech_settings() -> Settings:
    return Settings(
        environment="test",
        analysis_provider="mock",
        google_cloud_project_id="rootcause-test",
        max_audio_bytes=8192,
        _env_file=None,
    )


@pytest.fixture
def make_client(
    speech_settings: Settings,
) -> Iterator[Callable[[TranscriptionService], TestClient]]:
    clients: list[TestClient] = []

    def factory(service: TranscriptionService) -> TestClient:
        app = create_app(speech_settings)
        app.dependency_overrides[get_settings] = lambda: speech_settings
        app.dependency_overrides[get_transcription_service] = lambda: service
        test_client = TestClient(app)
        clients.append(test_client)
        return test_client

    yield factory
    for test_client in clients:
        test_client.close()


def post(client: TestClient, audio: bytes | None, language: str | None = "en-IN") -> Any:
    files = {"audio": ("note.webm", audio, "audio/webm")} if audio is not None else None
    data = {"language": language} if language is not None else {}
    return client.post("/api/v1/transcribe", files=files, data=data)


def test_transcribes_english_with_chirp3(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return speech_response("Yellow spots on the lower leaves.", language="en-in")

    response = post(make_client(service_for(handler)), WEBM, "en-IN")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "transcript": "Yellow spots on the lower leaves.",
        "language": "en-IN",
    }
    request = sent[0]
    assert request.url.host == "us-speech.googleapis.com"
    assert request.url.path == "/v2/projects/rootcause-test/locations/us/recognizers/_:recognize"
    assert request.headers["authorization"] == "Bearer test-token"
    body = json.loads(request.content)
    assert body["config"]["model"] == "chirp_3"
    assert body["config"]["languageCodes"] == ["en-IN"]
    assert body["config"]["autoDecodingConfig"] == {}
    assert "features" not in body["config"]
    assert base64.b64decode(body["content"]) == WEBM


def test_transcribes_hindi_without_translating(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return speech_response(HINDI, "तीन दिन से।")

    response = post(make_client(service_for(handler)), OGG, "hi-IN")

    assert response.status_code == 200, response.text
    assert response.json() == {"transcript": f"{HINDI} तीन दिन से।", "language": "hi-IN"}
    assert sent[0]["config"]["languageCodes"] == ["hi-IN"]


@pytest.mark.parametrize("audio", [WAV, FLAC], ids=["wav", "flac"])
def test_accepts_wav_and_flac(
    make_client: Callable[[TranscriptionService], TestClient], audio: bytes
) -> None:
    response = post(make_client(service_for(lambda _: speech_response("ok"))), audio)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "audio", [b"definitely not audio" * 64, MP4], ids=["random-bytes", "mp4-aac"]
)
def test_rejects_unsupported_audio(
    make_client: Callable[[TranscriptionService], TestClient], audio: bytes
) -> None:
    response = post(make_client(service_for(lambda _: speech_response("unused"))), audio)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_audio_type"


@pytest.mark.parametrize("language", ["ta-IN", "fr-FR", "", None])
def test_rejects_unsupported_or_missing_language(
    make_client: Callable[[TranscriptionService], TestClient], language: str | None
) -> None:
    response = post(make_client(service_for(lambda _: speech_response("unused"))), WEBM, language)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_language"
    assert response.json()["error"]["details"][0]["field"] == "language"


@pytest.mark.parametrize(
    ("audio", "code"),
    [
        (None, "audio_required"),
        (b"", "empty_audio"),
        (b"\x1aE\xdf\xa3" + b"\x00" * 64, "empty_audio"),
    ],
    ids=["missing", "zero-bytes", "headers-only"],
)
def test_rejects_missing_or_empty_recordings(
    make_client: Callable[[TranscriptionService], TestClient], audio: bytes | None, code: str
) -> None:
    response = post(make_client(service_for(lambda _: speech_response("unused"))), audio)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_rejects_oversized_recordings(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    response = post(make_client(service_for(lambda _: speech_response("unused"))), WEBM * 5)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "audio_too_large"


@pytest.mark.parametrize(
    "payload", [{}, {"results": []}, {"results": [{"alternatives": [{"transcript": " "}]}]}]
)
def test_silence_is_reported_as_no_speech(
    make_client: Callable[[TranscriptionService], TestClient], payload: dict[str, Any]
) -> None:
    response = post(make_client(service_for(lambda _: httpx.Response(200, json=payload))), WEBM)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_speech_detected"


def test_provider_timeout(make_client: Callable[[TranscriptionService], TestClient]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    response = post(make_client(service_for(handler)), WEBM)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "transcription_timeout"


@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_provider_failures(
    make_client: Callable[[TranscriptionService], TestClient], status: int
) -> None:
    response = post(make_client(service_for(lambda _: httpx.Response(status))), WEBM)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "transcription_failed"


def test_malformed_provider_payload(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    response = post(make_client(service_for(lambda _: httpx.Response(200, text="<html>"))), WEBM)

    assert response.status_code == 502


def test_missing_credentials(make_client: Callable[[TranscriptionService], TestClient]) -> None:
    def no_credentials() -> dict[str, str]:
        raise DefaultCredentialsError("Could not automatically determine credentials.")  # type: ignore[no-untyped-call]

    response = post(
        make_client(service_for(lambda _: speech_response("unused"), no_credentials)), WEBM
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "transcription_unavailable"


def test_rejected_credentials(make_client: Callable[[TranscriptionService], TestClient]) -> None:
    response = post(make_client(service_for(lambda _: httpx.Response(403))), WEBM)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "transcription_unavailable"


def test_unconfigured_project_is_unavailable(client: TestClient) -> None:
    response = client.post(
        "/api/v1/transcribe",
        files={"audio": ("note.webm", WEBM, "audio/webm")},
        data={"language": "en-IN"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "transcription_unavailable"


def test_audio_and_transcript_are_not_logged(
    make_client: Callable[[TranscriptionService], TestClient], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = post(make_client(service_for(lambda _: speech_response(HINDI))), WEBM, "hi-IN")

    assert response.status_code == 200
    assert "Transcription completed" in caplog.text
    assert HINDI not in caplog.text
    assert base64.b64encode(WEBM).decode()[:40] not in caplog.text


def test_speech_project_override_and_client_reuse() -> None:
    settings = Settings(
        speech_project_id="speech-project", google_cloud_project_id="ee-project", _env_file=None
    )

    first = get_transcription_service(settings)
    second = get_transcription_service(settings)

    assert settings.speech_project == "speech-project"
    assert first.configured and second._recognizer is first._recognizer
    assert not get_transcription_service(Settings(_env_file=None)).configured
    assert not get_transcription_service(
        Settings(google_cloud_project_id="ee-project", speech_enabled=False, _env_file=None)
    ).configured


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (WEBM, "audio/webm"),
        (OGG, "audio/ogg"),
        (WAV, "audio/wav"),
        (FLAC, "audio/flac"),
        (MP4, None),
        (b"ID3\x04" + b"\x00" * 64, None),
        (b"", None),
    ],
)
def test_detect_audio_type(data: bytes, expected: str | None) -> None:
    assert detect_audio_type(data) == expected


def gemini_response(transcript: str, language: str) -> httpx.Response:
    text = json.dumps({"transcript": transcript, "language": language})
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def gemini_client(handler: Handler) -> GeminiSpeechClient:
    client = GeminiSpeechClient(api_key="test-key", transport=httpx.MockTransport(handler))
    client._retry_delay = 0
    return client


def test_auto_language_uses_gemini_detection(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return gemini_response(HINDI, "hi-IN")

    response = post(make_client(TranscriptionService(gemini_client(handler))), WEBM, "auto")

    assert response.status_code == 200, response.text
    assert response.json() == {"transcript": HINDI, "language": "hi-IN"}
    request = sent[0]
    assert request.url.path == "/v1beta/models/gemini-flash-lite-latest:generateContent"
    assert request.headers["x-goog-api-key"] == "test-key"
    body = json.loads(request.content)
    audio = body["contents"][0]["parts"][1]["inlineData"]
    assert audio["mimeType"] == "audio/webm"
    assert base64.b64decode(audio["data"]) == WEBM
    assert "Devanagari" in body["systemInstruction"]["parts"][0]["text"]


def test_auto_language_with_unknown_detection_reports_auto(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    service = TranscriptionService(gemini_client(lambda _: gemini_response("Bonjour", "other")))

    response = post(make_client(service), WEBM, "auto")

    assert response.json() == {"transcript": "Bonjour", "language": "auto"}


def test_auto_language_maps_speech_to_text_codes(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return speech_response(HINDI, language="hi-in")

    response = post(make_client(service_for(handler)), WEBM, "auto")

    assert response.json() == {"transcript": HINDI, "language": "hi-IN"}
    assert sent[0]["config"]["languageCodes"] == ["auto"]


def test_gemini_retries_once_when_overloaded(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    statuses = iter([503, 200])

    def handler(_: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return gemini_response("Brown spots", "en-IN") if status == 200 else httpx.Response(503)

    response = post(make_client(TranscriptionService(gemini_client(handler))), WEBM, "auto")

    assert response.status_code == 200
    assert response.json()["transcript"] == "Brown spots"


def test_falls_back_to_speech_to_text_when_gemini_is_unavailable(
    make_client: Callable[[TranscriptionService], TestClient],
) -> None:
    gemini = gemini_client(lambda _: httpx.Response(503))
    google = GoogleSpeechClient(
        project_id="rootcause-test",
        auth_headers=fake_headers,
        transport=httpx.MockTransport(lambda _: speech_response("Brown spots", language="en-in")),
    )
    service = TranscriptionService(FallbackRecognizer([gemini, google]))

    response = post(make_client(service), WEBM, "auto")

    assert response.json() == {"transcript": "Brown spots", "language": "en-IN"}


@pytest.mark.anyio
async def test_fallback_stops_on_rejected_audio() -> None:
    called: list[str] = []

    class Rejecting:
        async def recognize(self, audio: bytes, language_code: str) -> Any:
            raise SpeechError("rejected", "bad audio")

    class Never:
        async def recognize(self, audio: bytes, language_code: str) -> Any:
            called.append("never")

    with pytest.raises(SpeechError):
        await FallbackRecognizer([Rejecting(), Never()]).recognize(WEBM, "auto")
    assert called == []


def test_gemini_is_preferred_when_key_is_set() -> None:
    both = Settings(gemini_api_key="k", google_cloud_project_id="ee-project", _env_file=None)
    only_google = Settings(
        gemini_api_key="k",
        google_cloud_project_id="ee-project",
        speech_provider="google",
        _env_file=None,
    )

    assert isinstance(get_transcription_service(both)._recognizer, FallbackRecognizer)
    assert isinstance(get_transcription_service(only_google)._recognizer, GoogleSpeechClient)
    assert isinstance(
        get_transcription_service(Settings(gemini_api_key="k", _env_file=None))._recognizer,
        GeminiSpeechClient,
    )
