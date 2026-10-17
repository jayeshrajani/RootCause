import base64
import json
from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_speech_synthesizer
from app.core.config import Settings, get_settings
from app.integrations.gemini_tts import GeminiSpeechSynthesizer, SpeechSynthesisError
from app.main import create_app

PCM = b"\x01\x00" * 2400
WAV = b"RIFF" + b"\x00" * 40 + PCM

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx.Request], httpx.Response]


def audio_response(data: bytes) -> httpx.Response:
    part = {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(data).decode()}}
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [part]}}]})


def synthesizer(handler: Handler) -> GeminiSpeechSynthesizer:
    client = GeminiSpeechSynthesizer(api_key="k", transport=httpx.MockTransport(handler))
    client._retry_delay = 0
    return client


def client_for(service: GeminiSpeechSynthesizer | None, ip_cap: int = 120) -> TestClient:
    config = Settings(
        environment="test",
        analysis_provider="mock",
        tts_requests_per_ip_hour=ip_cap,
        _env_file=None,
    )
    app = create_app(config)
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_speech_synthesizer] = lambda: service
    return TestClient(app)


def test_reads_text_aloud_as_wav() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return audio_response(WAV)

    response = client_for(synthesizer(handler)).post(
        "/api/v1/speak", json={"text": "आलू पर अगेती झुलसा की संभावना है।"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == WAV
    body = json.loads(sent[0].content)
    assert sent[0].url.path.endswith("/gemini-3.8-flash-lite-tts:generateContent")
    assert body["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert "अगेती झुलसा" in body["contents"][0]["parts"][0]["text"]


async def test_raw_pcm_is_wrapped_as_wav() -> None:
    audio = await synthesizer(lambda _: audio_response(PCM)).synthesize("Hello")

    assert audio.startswith(b"RIFF") and audio[8:12] == b"WAVE"
    assert audio.endswith(PCM)


async def test_falls_back_to_the_next_model_when_overloaded() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return audio_response(WAV) if "flash-tts" in request.url.path else httpx.Response(429)

    assert await synthesizer(handler).synthesize("Hello") == WAV
    assert len(paths) == 3  # lite twice (one retry), then the full model


async def test_raises_when_every_model_fails() -> None:
    with pytest.raises(SpeechSynthesisError):
        await synthesizer(lambda _: httpx.Response(503)).synthesize("Hello")


def test_validation_unconfigured_and_failure_responses() -> None:
    working = client_for(synthesizer(lambda _: audio_response(WAV)))
    assert working.post("/api/v1/speak", json={"text": ""}).status_code == 422
    assert working.post("/api/v1/speak", json={"text": "x" * 1201}).status_code == 422

    unconfigured = client_for(None).post("/api/v1/speak", json={"text": "Hi"})
    assert unconfigured.status_code == 503
    assert unconfigured.json()["error"]["code"] == "speech_unavailable"

    failing = client_for(synthesizer(lambda _: httpx.Response(500))).post(
        "/api/v1/speak", json={"text": "Hi"}
    )
    assert failing.status_code == 502


def test_per_ip_cap() -> None:
    client = client_for(synthesizer(lambda _: audio_response(WAV)), ip_cap=2)
    codes = [client.post("/api/v1/speak", json={"text": "Hi"}).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
