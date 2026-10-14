import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_triage_service
from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.cerebras import CerebrasClient, CerebrasError
from app.main import create_app
from app.models.report import FarmerReport, ReportImage
from app.services.triage import AiTriageService, MockTriageService
from app.services.triage.ai import ASSESSMENT_SCHEMA
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
        "crop_seen_in_photos": "tomato",
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


def service_with(*responses: httpx.Response) -> tuple[AiTriageService, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    client = CerebrasClient(api_key="test-key", model="qwen-test", transport=transport(handler))
    return AiTriageService(client), sent


async def test_valid_model_output_becomes_ai_triage() -> None:
    service, sent = service_with(completion(json.dumps(assessment())))

    result = await service.assess(REPORT)

    assert result.analysis_mode == "ai"
    assert result.report_id.startswith("rpt_")
    assert result.detected_crop == "tomato"
    assert result.recommended_actions[0].addresses == "Magnesium deficiency"
    photo_obs = [e.observation for e in result.evidence if e.source == "photo"]
    assert "Yellowing between veins on lower leaves" in photo_obs
    assert any("appear to show tomato" in o for o in photo_obs)
    assert sent[0]["response_format"]["json_schema"]["strict"] is True
    assert sent[0]["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


async def test_chemical_actions_always_require_expert_verification() -> None:
    service, _ = service_with(completion(json.dumps(assessment())))

    result = await service.assess(REPORT)

    assert result.recommended_actions[0].requires_expert_verification is True
    assert result.requires_expert_review is True


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
