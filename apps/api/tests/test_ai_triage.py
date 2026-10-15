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
from app.integrations.cerebras import CerebrasClient, CerebrasError
from app.integrations.open_meteo import OpenMeteoError
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


def completion(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
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

    client = CerebrasClient(api_key="test-key", model="qwen-test", transport=transport(handler))
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
    assert sent[0]["response_format"]["json_schema"]["strict"] is True
    assert sent[0]["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


async def test_selected_language_is_included_in_model_prompt() -> None:
    report = replace(REPORT, response_language=ResponseLanguage.HINDI)
    service, sent = service_with(completion(json.dumps(assessment())))

    await service.assess(report)

    prompt = sent[0]["messages"][1]["content"][0]["text"]
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
    prompt = sent[0]["messages"][1]["content"][0]["text"]
    assert "2026-10-14: min 18.0 C, max 27.5 C" in prompt
    evidence = next(item for item in result.evidence if item.source == "weather")
    assert evidence.availability == "available"
    assert "not measurements from the field" in evidence.observation
    source = next(item for item in result.data_sources if item.kind == "weather")
    assert source.name == "Open-Meteo recent weather"
    assert source.status == "used"
    assert result.possible_causes[0].weather_score == 50
    assert result.possible_causes[0].evidence_fit_score == 77
    assert result.recommended_actions[0].evidence_fit_score == 68


async def test_weather_can_adjust_cause_ranking_by_only_its_ten_percent_weight() -> None:
    causes = [
        {
            "name": "Cause supported by analysis",
            "explanation": "Visible signs fit this cause.",
            "supporting_evidence": ["Visible signs"],
            "contradictory_evidence": [],
            "confidence": "high",
            "uncertainty_note": "Check the field.",
            "analysis_score": 90,
            "weather_score": 0,
        },
        {
            "name": "Cause supported by weather",
            "explanation": "Visible signs and recent weather are consistent.",
            "supporting_evidence": ["Visible signs", "Recent rainfall estimate"],
            "contradictory_evidence": [],
            "confidence": "medium",
            "uncertainty_note": "Check the field.",
            "analysis_score": 80,
            "weather_score": 100,
        },
    ]
    actions = [
        {
            "action": "Check the newest leaf for expanding lesions",
            "rationale": "The visible pattern is the strongest clue.",
            "addresses": "Leaf lesions",
            "priority": "within_days",
            "requires_expert_verification": False,
            "analysis_score": 90,
            "weather_score": 0,
        },
        {
            "action": "Inspect nearby plants for similar spots after recent rain",
            "rationale": (
                "Recent rain may make spread worth checking, but does not confirm disease."
            ),
            "addresses": "Possible disease spread",
            "priority": "within_days",
            "requires_expert_verification": False,
            "analysis_score": 80,
            "weather_score": 100,
        },
    ]
    weather = StubWeatherClient()
    report = replace(REPORT, latitude=18.52, longitude=73.86)
    service, _ = service_with(
        completion(json.dumps(assessment(possible_causes=causes, recommended_actions=actions))),
        weather_client=weather,
    )

    result = await service.assess(report)

    assert result.possible_causes[0].name == "Cause supported by weather"
    assert [cause.evidence_fit_score for cause in result.possible_causes] == [82, 81]
    assert result.recommended_actions[0].action.startswith("Inspect nearby plants")
    assert [action.evidence_fit_score for action in result.recommended_actions] == [82, 81]


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
    assert "Crop selected by the farmer: soybean" in sent[0]["messages"][1]["content"][0]["text"]


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
    client = CerebrasClient(
        api_key="k",
        model="m",
        transport=transport(lambda _: completion('{"a":', finish_reason="length")),
    )

    with pytest.raises(CerebrasError, match="truncated"):
        await client.structured_completion(
            system="s", text="t", images=[], schema_name="x", schema={}
        )


async def test_http_errors_do_not_leak_the_api_key() -> None:
    client = CerebrasClient(
        api_key="secret-key-123",
        model="m",
        transport=transport(lambda _: httpx.Response(401, json={"error": "bad key"})),
    )

    with pytest.raises(CerebrasError) as exc:
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
    settings = Settings(analysis_provider=provider, cerebras_api_key=key, _env_file=None)

    assert isinstance(get_triage_service(settings), expected)


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
    assert "Requested output language: Punjabi" in sent[0]["messages"][1]["content"][0]["text"]
