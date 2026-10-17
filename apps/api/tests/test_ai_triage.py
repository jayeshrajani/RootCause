import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_triage_service
from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.cerebras import CerebrasClient
from app.integrations.gemini import GeminiClient, GeminiError, GeminiRateLimitError
from app.integrations.open_meteo import OpenMeteoError
from app.integrations.vision import FallbackVisionModel, VisionModelError
from app.main import create_app
from app.models.report import FarmerReport, ReportImage
from app.models.weather import DailyWeather, GeocodedLocation, RecentWeather
from app.schemas.triage import Crop, ResponseLanguage
from app.services.triage import AiTriageService, MockTriageService
from app.services.triage.ai import ASSESSMENT_SCHEMA
from app.services.triage.common import recent_weather_summary
from tests.conftest import JPEG_BYTES, jpeg

pytestmark = pytest.mark.anyio

REPORT = FarmerReport(
    images=(ReportImage(media_type="image/jpeg", data=JPEG_BYTES),),
    received_at=datetime(2026, 10, 14, tzinfo=UTC),
    description="Yellow patches on older leaves.",
)


def assessment(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "image_quality": "good",
        "image_quality_note": "Clear close-up in daylight.",
        "crop_visible_features": ["Compound leaves with toothed leaflets", "Hairy stems"],
        "crop_seen_in_photos": "tomato",
        "crop_identification_confidence": "high",
        "photo_observations": ["Yellowing between veins on lower leaves", "No visible insects"],
        "summary": "The lower leaves may be short of a nutrient.",
        "urgency": "moderate",
        "urgency_reason": "Symptoms are limited to older leaves.",
        "possible_causes": [
            {
                "name": "Magnesium deficiency",
                "explanation": "Yellowing between veins on older leaves can mean low magnesium.",
                "supporting_evidence": ["Interveinal yellowing on older leaves"],
                "contradictory_evidence": [],
                "confidence": "high",
                "uncertainty_note": "A soil or leaf test would confirm it.",
                "analysis_score": 80,
                "weather_score": 50,
            }
        ],
        "missing_information": [{"item": "Recent fertiliser use", "reason": "Explains supply."}],
        "recommended_actions": [
            {
                "action": "Spray a fungicide on affected plants",
                "rationale": "Prevents spread.",
                "addresses": "Magnesium deficiency",
                "priority": "within_days",
                "requires_expert_verification": False,
                "analysis_score": 70,
                "weather_score": 50,
            }
        ],
        "requires_expert_review": False,
    }
    return base | overrides


def transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def completion(content: str, finish_reason: str = "STOP") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"parts": [{"text": content}]},
                    "finishReason": finish_reason,
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
        },
    )


def cerebras_completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )


def service_with(
    *responses: httpx.Response, weather_client: Any = None
) -> tuple[AiTriageService, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    client = GeminiClient(api_key="test-key", model="gemini-test", transport=transport(handler))
    return AiTriageService(client, weather_client=weather_client), sent


class StubWeatherClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.coordinates: tuple[float, float] | None = None
        self.place: str | None = None
        self.fail = fail

    async def geocode(self, place: str) -> GeocodedLocation | None:
        self.place = place
        return GeocodedLocation(name="Bhopal", latitude=23.2599, longitude=77.4126)

    async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather:
        self.coordinates = (latitude, longitude)
        if self.fail:
            raise OpenMeteoError("lookup failed")
        return RecentWeather(
            days=(
                DailyWeather(
                    date="2026-10-14",
                    temperature_min_c=18.0,
                    temperature_max_c=27.5,
                    precipitation_mm=3.2,
                    relative_humidity_percent=72.0,
                ),
            ),
            retrieved_at=datetime(2026, 10, 15, tzinfo=UTC),
        )


async def test_valid_model_output_becomes_ai_triage() -> None:
    service, sent = service_with(completion(json.dumps(assessment())))

    result = await service.assess(REPORT)

    assert result.analysis_mode == "ai"
    assert result.report_id.startswith("rpt_")
    assert result.detected_crop == "tomato"
    assert result.recommended_actions[0].addresses == "Magnesium deficiency"
    assert result.possible_causes[0].analysis_score == 80
    assert result.possible_causes[0].weather_score is None
    assert result.possible_causes[0].evidence_fit_score == 80
    assert result.recommended_actions[0].analysis_score == 70
    assert result.recommended_actions[0].weather_score is None
    assert result.recommended_actions[0].evidence_fit_score == 70
    photo_obs = [e.observation for e in result.evidence if e.source == "photo"]
    assert "Yellowing between veins on lower leaves" in photo_obs
    assert any("appear to show tomato" in o for o in photo_obs)
    assert sent[0]["systemInstruction"]["parts"][0]["text"]
    assert sent[0]["generationConfig"]["responseMimeType"] == "application/json"
    assert sent[0]["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
    assert sent[0]["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg"
    assert sent[0]["contents"][0]["parts"][1]["inlineData"]["data"]


async def test_selected_language_is_included_in_model_prompt() -> None:
    report = replace(REPORT, response_language=ResponseLanguage.HINDI)
    service, sent = service_with(completion(json.dumps(assessment())))

    await service.assess(report)

    prompt = sent[0]["contents"][0]["parts"][0]["text"]
    assert "Requested output language: Hindi" in prompt


async def test_coordinates_fetch_weather_and_include_it_in_ai_provenance() -> None:
    weather = StubWeatherClient()
    report = replace(REPORT, latitude=18.52, longitude=73.86)
    service, sent = service_with(completion(json.dumps(assessment())), weather_client=weather)

    result = await service.assess(report)

    assert weather.coordinates == (18.52, 73.86)
    assert result.approximate_location == "18.52° N, 73.86° E"
    assert result.weather_summary is not None
    assert "rain 3.2 mm" in result.weather_summary
    prompt = sent[0]["contents"][0]["parts"][0]["text"]
    assert "2026-10-14: min 18.0 C, max 27.5 C" in prompt
    evidence = next(item for item in result.evidence if item.source == "weather")
    assert evidence.availability == "available"
    assert "not measurements from the field" in evidence.observation
    source = next(item for item in result.data_sources if item.kind == "weather")
    assert source.name == "Open-Meteo recent weather"
    assert source.status == "used"
    assert result.possible_causes[0].weather_score == 50
    assert result.possible_causes[0].evidence_fit_score == 80
    assert result.possible_causes[0].evidence_ledger[0].effect == "neutral"
    assert result.recommended_actions[0].evidence_fit_score == 70
    assert result.weather_facts is not None and result.weather_facts.rain_total_mm == 3.2


async def test_weather_rules_adjust_cause_ranking_by_bounded_points() -> None:
    causes = [
        {
            "name": "Late blight",
            "explanation": "Dark lesions could be late blight.",
            "supporting_evidence": ["Dark lesions"],
            "contradictory_evidence": [],
            "confidence": "medium",
            "uncertainty_note": "Check leaf undersides.",
            "analysis_score": 67,
            "condition_key": "late_blight",
        },
        {
            "name": "Water stress",
            "explanation": "Wilting fits a lack of water.",
            "supporting_evidence": ["Wilting"],
            "contradictory_evidence": [],
            "confidence": "medium",
            "uncertainty_note": "Check soil moisture.",
            "analysis_score": 65,
            "condition_key": "water_stress",
        },
    ]
    actions = [
        {
            "action": "Inspect nearby plants for similar spots",
            "rationale": "Spread is worth checking.",
            "addresses": "Possible disease spread",
            "priority": "within_days",
            "requires_expert_verification": False,
            "analysis_score": 80,
        },
        {
            "action": "Check the newest leaf for expanding lesions",
            "rationale": "The visible pattern is the strongest clue.",
            "addresses": "Leaf lesions",
            "priority": "within_days",
            "requires_expert_verification": False,
            "analysis_score": 90,
        },
    ]
    report = replace(REPORT, latitude=18.52, longitude=73.86)
    service, sent = service_with(
        completion(json.dumps(assessment(possible_causes=causes, recommended_actions=actions))),
        weather_client=StubWeatherClient(),
    )

    result = await service.assess(report)

    # One dry day (3.2 mm): +5 for water stress, neutral for late blight.
    assert [c.condition_key for c in result.possible_causes] == ["water_stress", "late_blight"]
    assert [c.evidence_fit_score for c in result.possible_causes] == [70, 67]
    assert result.possible_causes[0].evidence_ledger[0].points == 5
    assert "Little rain" in result.possible_causes[0].evidence_ledger[0].reason
    assert "weather_score" not in json.dumps(sent[0]["generationConfig"]["responseJsonSchema"])
    assert result.recommended_actions[0].action.startswith("Check the newest leaf")
    assert [a.evidence_fit_score for a in result.recommended_actions] == [90, 80]


async def test_weak_causes_hidden_and_dominant_cause_stands_alone() -> None:
    def cause(key: str, score: int) -> dict[str, Any]:
        return {
            "name": key,
            "explanation": "x",
            "supporting_evidence": [],
            "contradictory_evidence": [],
            "confidence": "medium",
            "uncertainty_note": "x",
            "analysis_score": score,
            "condition_key": key,
        }

    async def keys(*causes: dict[str, Any]) -> list[str | None]:
        service, _ = service_with(completion(json.dumps(assessment(possible_causes=list(causes)))))
        result = await service.assess(REPORT)
        return [c.condition_key for c in result.possible_causes]

    assert await keys(cause("late_blight", 70), cause("water_stress", 49)) == ["late_blight"]
    assert await keys(cause("late_blight", 70), cause("water_stress", 50)) == [
        "late_blight",
        "water_stress",
    ]
    assert await keys(cause("late_blight", 76), cause("water_stress", 60)) == ["late_blight"]


async def test_weather_failure_does_not_block_ai_triage() -> None:
    weather = StubWeatherClient(fail=True)
    report = replace(REPORT, latitude=18.52, longitude=73.86)
    service, _ = service_with(completion(json.dumps(assessment())), weather_client=weather)

    result = await service.assess(report)

    assert result.analysis_mode == "ai"
    evidence = next(item for item in result.evidence if item.source == "weather")
    assert evidence.availability == "unavailable"
    assert "could not retrieve" in evidence.observation


async def test_weather_lookup_is_skipped_without_coordinates() -> None:
    weather = StubWeatherClient()
    service, _ = service_with(completion(json.dumps(assessment())), weather_client=weather)

    result = await service.assess(REPORT)

    assert weather.coordinates is None
    source = next(item for item in result.data_sources if item.kind == "weather")
    assert source.status == "unavailable"
    assert "Coordinates were not provided" in source.description


async def test_typed_location_is_geocoded_then_used_for_weather() -> None:
    weather = StubWeatherClient()
    report = replace(REPORT, location_label="Bhopal")
    service, _ = service_with(completion(json.dumps(assessment())), weather_client=weather)

    result = await service.assess(report)

    assert weather.place == "Bhopal"
    assert weather.coordinates == (23.2599, 77.4126)
    assert result.location_label == "Bhopal"
    assert result.approximate_location == "23.26° N, 77.41° E"
    assert result.weather_summary is not None


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (ResponseLanguage.HINDI, "पिछले 1 पूरे दिन"),
        (ResponseLanguage.PUNJABI, "ਪਿਛਲੇ 1 ਪੂਰੇ ਦਿਨ"),
        (ResponseLanguage.SPANISH, "Últimos 1 días completos"),
        (ResponseLanguage.FRENCH, "Sur les 1 derniers jours complets"),
    ],
)
def test_weather_summary_uses_requested_language(language: ResponseLanguage, expected: str) -> None:
    report = replace(
        REPORT,
        response_language=language,
        weather=RecentWeather(
            days=(
                DailyWeather(
                    date="2026-10-14",
                    temperature_min_c=18.0,
                    temperature_max_c=27.5,
                    precipitation_mm=3.2,
                    relative_humidity_percent=72.0,
                ),
            ),
            retrieved_at=datetime(2026, 10, 15, tzinfo=UTC),
        ),
    )

    summary = recent_weather_summary(report)

    assert summary is not None
    assert expected in summary


async def test_chemical_actions_always_require_expert_verification() -> None:
    service, _ = service_with(completion(json.dumps(assessment())))

    result = await service.assess(REPORT)

    assert result.recommended_actions[0].requires_expert_verification is True
    assert result.requires_expert_review is True


async def test_unsure_crop_guess_is_not_shown() -> None:
    body = assessment(crop_seen_in_photos="soybean", crop_identification_confidence="medium")
    service, _ = service_with(completion(json.dumps(body)))

    result = await service.assess(REPORT)

    assert result.detected_crop is None
    assert not any("appear to show" in e.observation for e in result.evidence)


async def test_selected_crop_mismatch_is_flagged() -> None:
    report = replace(REPORT, crop=Crop.SOYBEAN)
    body = assessment(crop_seen_in_photos="potato")
    service, sent = service_with(completion(json.dumps(body)))

    result = await service.assess(report)

    assert result.crop == "soybean"
    assert any("look more like potato than soybean" in e.observation for e in result.evidence)
    assert "Crop selected by the farmer: soybean" in sent[0]["contents"][0]["parts"][0]["text"]


async def test_confidence_is_capped_when_photos_are_limited() -> None:
    service, _ = service_with(completion(json.dumps(assessment(image_quality="limited"))))

    result = await service.assess(REPORT)

    assert result.possible_causes[0].confidence == "medium"


async def test_unusable_photos_mark_triage_as_insufficient() -> None:
    body = assessment(image_quality="unusable", possible_causes=[])
    service, _ = service_with(completion(json.dumps(body)))

    result = await service.assess(REPORT)

    assert result.status == "insufficient_information"


async def test_malformed_output_is_retried_then_fails_explicitly() -> None:
    service, sent = service_with(completion("{not json"), completion('{"summary": "only"}'))

    with pytest.raises(AppError) as exc:
        await service.assess(REPORT)

    assert exc.value.status_code == 502
    assert exc.value.code == "analysis_unavailable"
    assert len(sent) == 2


async def test_truncated_output_is_an_error() -> None:
    client = GeminiClient(
        api_key="k",
        model="m",
        transport=transport(lambda _: completion('{"a":', finish_reason="MAX_TOKENS")),
    )

    with pytest.raises(GeminiError, match="truncated"):
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )


async def test_gemini_error_keeps_the_provider_reason_for_logs() -> None:
    body = {
        "error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": "API key not valid. Please pass a valid API key.\n" + "x" * 500,
        }
    }
    client = GeminiClient(
        api_key="secret-key",
        model="m",
        transport=transport(lambda _: httpx.Response(400, json=body)),
    )

    with pytest.raises(GeminiError) as exc:
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )

    message = str(exc.value)
    assert message.startswith("Model API returned HTTP 400 (INVALID_ARGUMENT: API key not valid.")
    assert "secret-key" not in message
    assert "\n" not in message
    assert len(message) < 400


async def test_gemini_blocked_prompt_reports_the_block_reason() -> None:
    client = GeminiClient(
        api_key="k",
        model="m",
        transport=transport(
            lambda _: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        ),
    )

    with pytest.raises(GeminiError, match=r"unexpected payload \(SAFETY\)"):
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )


async def test_cerebras_error_keeps_the_provider_reason() -> None:
    body = {"message": "ignored", "error": {"type": "authentication_error", "message": "bad key"}}
    client = CerebrasClient(
        api_key="k",
        model="m",
        transport=transport(lambda _: httpx.Response(401, json=body)),
    )

    with pytest.raises(VisionModelError, match=r"HTTP 401 \(authentication_error: bad key\)"):
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )


async def test_fallback_logs_why_the_primary_failed(caplog: pytest.LogCaptureFixture) -> None:
    gemini_body = {"error": {"status": "PERMISSION_DENIED", "message": "API not enabled"}}
    model = FallbackVisionModel(
        GeminiClient(
            api_key="k",
            model="m",
            transport=transport(lambda _: httpx.Response(403, json=gemini_body)),
        ),
        CerebrasClient(
            api_key="k", model="c", transport=transport(lambda _: cerebras_completion("{}"))
        ),
    )

    await model.structured_completion(system="s", text="t", images=[], schema_name="x", schema={})

    assert "HTTP 403 (PERMISSION_DENIED: API not enabled)" in caplog.text


async def test_cerebras_is_used_when_gemini_fails() -> None:
    gemini_requests: list[httpx.Request] = []
    gemini_fallback_requests: list[httpx.Request] = []
    cerebras_requests: list[httpx.Request] = []

    def gemini_handler(request: httpx.Request) -> httpx.Response:
        gemini_requests.append(request)
        return httpx.Response(503)

    def cerebras_handler(request: httpx.Request) -> httpx.Response:
        cerebras_requests.append(request)
        return cerebras_completion('{"ok":true}')

    def gemini_fallback_handler(request: httpx.Request) -> httpx.Response:
        gemini_fallback_requests.append(request)
        return completion('{"unexpected":"fallback"}')

    model = FallbackVisionModel(
        FallbackVisionModel(
            GeminiClient(
                api_key="gemini-test-key",
                model="gemini-primary-test",
                transport=httpx.MockTransport(gemini_handler),
            ),
            GeminiClient(
                api_key="gemini-test-key",
                model="gemini-fallback-test",
                transport=httpx.MockTransport(gemini_fallback_handler),
            ),
            fallback_on=GeminiRateLimitError,
        ),
        CerebrasClient(
            api_key="cerebras-test-key",
            model="cerebras-test",
            transport=httpx.MockTransport(cerebras_handler),
        ),
    )

    output = await model.structured_completion(
        system="system", text="prompt", images=[], schema_name="result", schema={}
    )

    assert output == '{"ok":true}'
    assert len(gemini_requests) == len(cerebras_requests) == 1
    assert not gemini_fallback_requests
    assert gemini_requests[0].url.path.endswith("/models/gemini-primary-test:generateContent")
    assert gemini_requests[0].headers["x-goog-api-key"] == "gemini-test-key"
    assert cerebras_requests[0].url.path.endswith("/chat/completions")
    assert model.provider_label == "Cerebras"
    assert model.model == "cerebras-test"


async def test_gemini_rate_limit_uses_gemini_3_flash() -> None:
    requests: list[str] = []

    def rate_limited(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(429)

    def older_model(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return completion('{"ok":true}')

    model = FallbackVisionModel(
        GeminiClient(
            api_key="test-key",
            model="gemini-3.8-flash",
            transport=httpx.MockTransport(rate_limited),
        ),
        GeminiClient(
            api_key="test-key",
            model="gemini-3-flash-preview",
            transport=httpx.MockTransport(older_model),
        ),
        fallback_on=GeminiRateLimitError,
    )

    output = await model.structured_completion(
        system="system", text="prompt", images=[], schema_name="result", schema={}
    )

    assert output == '{"ok":true}'
    assert requests == [
        "/v1beta/models/gemini-3.8-flash:generateContent",
        "/v1beta/models/gemini-3-flash-preview:generateContent",
    ]
    assert model.model == "gemini-3-flash-preview"
    assert model.provider_label == "Gemini"


async def test_http_errors_do_not_leak_the_api_key() -> None:
    client = GeminiClient(
        api_key="secret-key-123",
        model="m",
        transport=transport(lambda _: httpx.Response(401, json={"error": "bad key"})),
    )

    with pytest.raises(GeminiError) as exc:
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )

    assert "401" in str(exc.value)
    assert "secret-key-123" not in str(exc.value)


def test_schema_is_strict_and_self_contained() -> None:
    text = json.dumps(ASSESSMENT_SCHEMA)
    assert "$ref" not in text
    assert ASSESSMENT_SCHEMA["additionalProperties"] is False
    assert set(ASSESSMENT_SCHEMA["required"]) == set(ASSESSMENT_SCHEMA["properties"])


@pytest.mark.parametrize(
    ("provider", "key", "expected"),
    [
        ("auto", None, MockTriageService),
        ("auto", "k", AiTriageService),
        ("mock", "k", MockTriageService),
    ],
)
def test_provider_selection(provider: str, key: str | None, expected: type) -> None:
    settings = Settings(analysis_provider=provider, gemini_api_key=key, _env_file=None)

    assert isinstance(get_triage_service(settings), expected)


def test_cerebras_remains_available_when_gemini_key_is_missing() -> None:
    settings = Settings(cerebras_api_key="cerebras-key", _env_file=None)

    service = get_triage_service(settings)

    assert isinstance(service, AiTriageService)
    assert getattr(service._client, "provider_label", None) == "Cerebras"


def test_provider_failure_returns_actionable_502(settings: Settings) -> None:
    service, _ = service_with(completion("nope"), completion("nope"))
    app = create_app(settings)
    app.dependency_overrides[get_triage_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/triage", files=[jpeg()])

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "analysis_unavailable"


def test_triage_route_forwards_requested_output_language() -> None:
    service, sent = service_with(completion(json.dumps(assessment())))
    app = create_app(Settings(analysis_provider="mock", _env_file=None))
    app.dependency_overrides[get_triage_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/triage",
            data={"response_language": "pa"},
            files=[jpeg()],
        )

    assert response.status_code == 200
    assert response.json()["response_language"] == "pa"
    assert "Requested output language: Punjabi" in sent[0]["contents"][0]["parts"][0]["text"]
