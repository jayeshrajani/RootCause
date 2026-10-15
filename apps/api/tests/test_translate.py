import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_triage_translator
from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.cerebras import CerebrasClient
from app.main import create_app
from app.schemas.triage import (
    ActionPriority,
    AnalysisMode,
    ConfidenceLevel,
    Crop,
    Evidence,
    EvidenceAvailability,
    MissingInformation,
    PossibleCause,
    RecommendedAction,
    ResponseLanguage,
    SourceKind,
    TriageResponse,
    TriageStatus,
    UrgencyLevel,
)
from app.services.triage.translate import TriageTranslator

pytestmark = pytest.mark.anyio

FARMER_WORDS = "Farmer's description: “पत्तियाँ पीली हो रही हैं”."


def hindi_result(**overrides: Any) -> TriageResponse:
    result = TriageResponse(
        report_id="rpt_translate",
        status=TriageStatus.COMPLETED,
        analysis_mode=AnalysisMode.AI,
        response_language=ResponseLanguage.HINDI,
        crop=Crop.TOMATO,
        detected_crop="टमाटर",
        location_label="Bhopal",
        weather_summary="पिछले 7 पूरे दिन: बारिश 3.2 mm",
        summary="निचली पत्तियों पर भूरे धब्बे हैं।",
        urgency=UrgencyLevel.MODERATE,
        urgency_reason="धब्बे ऊपर की ओर फैल रहे हैं।",
        possible_causes=[
            PossibleCause(
                name="अगेती झुलसा",
                explanation="गोल धब्बे इस रोग से मेल खाते हैं।",
                supporting_evidence=["छल्लेदार धब्बे"],
                contradictory_evidence=[],
                confidence=ConfidenceLevel.MEDIUM,
                uncertainty_note="पत्ती के नीचे की फोटो से पुष्टि होगी।",
                analysis_score=72,
                weather_score=60,
                evidence_fit_score=71,
            )
        ],
        evidence=[
            Evidence(
                id="ev_farmer_report",
                source=SourceKind.FARMER_REPORT,
                availability=EvidenceAvailability.AVAILABLE,
                observation=FARMER_WORDS,
            ),
            Evidence(
                id="ev_photo_1",
                source=SourceKind.PHOTO,
                availability=EvidenceAvailability.AVAILABLE,
                observation="निचली पत्तियों पर भूरे धब्बे",
            ),
        ],
        missing_information=[
            MissingInformation(item="पत्ती का निचला हिस्सा", reason="फफूंद की जाँच के लिए।")
        ],
        recommended_actions=[
            RecommendedAction(
                action="धब्बेदार निचली पत्तियाँ हटाएँ",
                rationale="इससे फैलाव धीमा हो सकता है।",
                priority=ActionPriority.WITHIN_DAYS,
                requires_expert_verification=False,
                addresses="अगेती झुलसा",
                analysis_score=80,
                evidence_fit_score=80,
            )
        ],
        requires_expert_review=False,
        generated_at=datetime(2026, 10, 15, 9, 30, tzinfo=UTC),
        data_sources=[],
        disclaimer="AI सलाह पक्का निदान नहीं है।",
    )
    return result.model_copy(update=overrides)


def english_text(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "There are brown spots on the lower leaves.",
        "urgency_reason": "The spots are spreading upwards.",
        "detected_crop": "tomato",
        "weather_summary": "Previous 7 completed days: rain 3.2 mm",
        "disclaimer": "AI guidance is not a confirmed diagnosis.",
        "photo_observations": ["Brown spots on lower leaves"],
        "possible_causes": [
            {
                "name": "Early blight",
                "explanation": "Round spots match this disease.",
                "supporting_evidence": ["Ringed spots"],
                "contradictory_evidence": [],
                "uncertainty_note": "A photo of the leaf underside would confirm it.",
            }
        ],
        "missing_information": [{"item": "Underside of the leaf", "reason": "To check for mould."}],
        "recommended_actions": [
            {
                "action": "Remove spotted lower leaves",
                "rationale": "This may slow the spread.",
                "addresses": "Early blight",
            }
        ],
    }
    return base | overrides


def completion(content: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )


def translator_with(*responses: httpx.Response) -> tuple[TriageTranslator, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    client = CerebrasClient(
        api_key="test-key", model="qwen-test", transport=httpx.MockTransport(handler)
    )
    return TriageTranslator(client), sent


async def test_translation_replaces_text_and_keeps_scores_and_farmer_words() -> None:
    translator, sent = translator_with(completion(english_text()))

    translated = await translator.translate(hindi_result(), ResponseLanguage.ENGLISH)

    assert translated.response_language == ResponseLanguage.ENGLISH
    assert translated.summary == "There are brown spots on the lower leaves."
    assert translated.detected_crop == "tomato"
    cause = translated.possible_causes[0]
    assert cause.name == "Early blight"
    assert (cause.analysis_score, cause.weather_score, cause.evidence_fit_score) == (72, 60, 71)
    assert cause.confidence == ConfidenceLevel.MEDIUM
    action = translated.recommended_actions[0]
    assert action.action == "Remove spotted lower leaves"
    assert action.priority == ActionPriority.WITHIN_DAYS
    assert action.evidence_fit_score == 80
    assert translated.evidence[0].observation == FARMER_WORDS
    assert translated.evidence[1].observation == "Brown spots on lower leaves"
    assert translated.report_id == "rpt_translate"
    assert translated.location_label == "Bhopal"

    prompt = sent[0]["messages"][1]["content"][0]["text"]
    assert prompt.startswith("Target language: English")
    assert "निचली पत्तियों" in prompt
    assert "पीली हो रही" not in prompt
    assert sent[0]["response_format"]["json_schema"]["name"] == "triage_translation"


async def test_translation_that_changes_structure_is_retried_then_rejected() -> None:
    reshaped = english_text(photo_observations=[])
    translator, sent = translator_with(completion(reshaped), completion(reshaped))

    with pytest.raises(AppError) as exc_info:
        await translator.translate(hindi_result(), ResponseLanguage.ENGLISH)

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "translation_unavailable"
    assert len(sent) == 2


async def test_same_language_returns_result_without_model_call() -> None:
    translator, sent = translator_with()
    result = hindi_result()

    assert await translator.translate(result, ResponseLanguage.HINDI) is result
    assert sent == []


async def test_oversized_result_is_rejected_before_model_call() -> None:
    translator, sent = translator_with()

    with pytest.raises(AppError) as exc_info:
        await translator.translate(hindi_result(summary="x" * 20_001), ResponseLanguage.ENGLISH)

    assert exc_info.value.status_code == 413
    assert sent == []


@pytest.fixture
def ai_client() -> Iterator[tuple[TestClient, list[dict[str, Any]]]]:
    settings = Settings(environment="test", analysis_provider="mock", _env_file=None)
    translator, sent = translator_with(completion(english_text()))
    app = create_app(settings)
    app.dependency_overrides[get_triage_translator] = lambda: translator
    with TestClient(app) as test_client:
        yield test_client, sent


def test_translate_endpoint_returns_translated_result(
    ai_client: tuple[TestClient, list[dict[str, Any]]],
) -> None:
    test_client, sent = ai_client
    body = {"result": hindi_result().model_dump(mode="json"), "target_language": "en"}

    response = test_client.post("/api/v1/triage/translate", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_language"] == "en"
    assert payload["possible_causes"][0]["name"] == "Early blight"
    assert payload["possible_causes"][0]["evidence_fit_score"] == 71
    assert len(sent) == 1


def test_translate_endpoint_is_unavailable_without_ai(client: TestClient) -> None:
    body = {"result": hindi_result().model_dump(mode="json"), "target_language": "en"}

    response = client.post("/api/v1/triage/translate", json=body)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "translation_unavailable"


def test_translate_endpoint_rejects_unknown_language(client: TestClient) -> None:
    body = {"result": hindi_result().model_dump(mode="json"), "target_language": "de"}

    response = client.post("/api/v1/triage/translate", json=body)

    assert response.status_code == 422
