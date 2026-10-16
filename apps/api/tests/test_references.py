import json
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.cerebras import CerebrasClient
from app.main import create_app
from app.models.references import ReferenceVotes
from app.schemas.triage import Crop
from app.services.retrieval import ReferenceMatch, RetrievalResult
from app.services.retrieval.dataset_registry import SupportedCrop
from app.services.triage import AiTriageService
from app.services.triage.ai import _evidence_fit_score
from app.services.triage.references import (
    ReferenceStatus,
    ReferenceUnavailableError,
    RetrievalReferenceProvider,
    match_label,
    votes_from,
)
from tests.conftest import JPEG_BYTES
from tests.test_ai_triage import REPORT, assessment, completion

pytestmark = pytest.mark.anyio


class FakeReferences:
    def __init__(
        self,
        votes: ReferenceVotes | None = None,
        *,
        status: ReferenceStatus = "ready",
        error: str | None = None,
    ) -> None:
        self.votes = votes
        self.status = status
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def find(self, crop: str, images: Sequence[bytes]) -> ReferenceVotes:
        self.calls.append((crop, len(images)))
        if self.error:
            raise ReferenceUnavailableError(self.error)
        assert self.votes is not None
        return self.votes


def votes(crop: str, **counts: int) -> ReferenceVotes:
    ordered = tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return ReferenceVotes(
        crop=crop,
        index_version="v1",
        total=sum(counts.values()),
        counts=ordered,
        best_similarity=0.7,
    )


def cause(name: str, analysis: int, label: str) -> dict[str, Any]:
    return {
        "name": name,
        "explanation": "Visible signs fit this cause.",
        "supporting_evidence": ["Spots on leaves"],
        "contradictory_evidence": [],
        "confidence": "medium",
        "uncertainty_note": "Check more leaves.",
        "analysis_score": analysis,
        "condition_key": label,
    }


def service_with(
    provider: FakeReferences | None, *responses: httpx.Response
) -> tuple[AiTriageService, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    client = CerebrasClient(
        api_key="test-key", model="qwen-test", transport=httpx.MockTransport(handler)
    )
    return AiTriageService(client, reference_provider=provider), sent


def prompt_of(sent: list[dict[str, Any]]) -> str:
    text: str = sent[0]["messages"][1]["content"][0]["text"]
    return text


def rice_match(label: str, score: float) -> ReferenceMatch:
    return ReferenceMatch(
        reference_image_id=f"rice-test-{label}-{score}",
        crop_id=SupportedCrop.RICE,
        disease_label=label,
        source_label=label,
        dataset_source="mendeley_rice",
        image_uri=f"local://references/images/rice/{label}.jpg",
        image_style="field",
        similarity_score=score,
        query_image_index=0,
        license="CC BY 4.0",
        attribution="Test",
        source_url="https://example.org",
    )


def rice_result(*matches: ReferenceMatch) -> RetrievalResult:
    return RetrievalResult(
        crop_id=SupportedCrop.RICE,
        retrieval_model="facebook/dinov2-small",
        model_revision="test",
        preprocessing_version="test",
        index_version="v1",
        top_k=len(matches),
        matches=list(matches),
    )


@pytest.mark.parametrize(
    ("reference", "weight", "adjustment", "expected"),
    [
        (None, 0, 0, 80),  # analysis only
        (30, 20, 0, 70),  # 80/20
        (30, 10, 0, 75),  # tomato: 90/10
        (None, 0, 8, 88),  # weather/satellite points are added after blending
        (100, 30, 30, 100),  # clamped
    ],
)
def test_evidence_fit_weights(
    reference: int | None, weight: int, adjustment: int, expected: int
) -> None:
    assert _evidence_fit_score(80, reference, weight, adjustment) == expected


def test_votes_count_labels_among_closest_references() -> None:
    result = votes_from(
        rice_result(
            rice_match("blast", 0.8), rice_match("brown_spot", 0.7), rice_match("blast", 0.6)
        )
    )

    assert result.counts == (("blast", 2), ("brown_spot", 1))
    assert (result.score("blast"), result.score("brown_spot"), result.score("tungro")) == (
        67,
        33,
        0,
    )


def test_weak_resemblance_is_not_used() -> None:
    with pytest.raises(ReferenceUnavailableError, match="did not closely resemble"):
        votes_from(rice_result(rice_match("blast", 0.2)))


@pytest.mark.parametrize(
    ("raw", "crop", "expected"),
    [
        ("early_blight", "tomato", "early_blight"),
        ("Early blight", "tomato", "early_blight"),
        ("none", "tomato", None),
        ("rust", "tomato", None),
        ("blast", "wheat", None),
    ],
)
def test_model_labels_are_validated(raw: str, crop: str, expected: str | None) -> None:
    assert match_label(raw, crop) == expected


async def test_reference_votes_can_reorder_causes_for_a_selected_crop() -> None:
    provider = FakeReferences(votes("rice", blast=8, brown_spot=2))
    output = assessment(
        crop_seen_in_photos="rice",
        possible_causes=[cause("Brown spot", 80, "brown_spot"), cause("Blast", 72, "blast")],
    )
    service, sent = service_with(provider, completion(json.dumps(output)))

    result = await service.assess(replace(REPORT, crop=Crop.RICE))

    assert provider.calls == [("rice", 1)]
    assert [c.name for c in result.possible_causes] == ["Blast", "Brown spot"]
    assert [c.reference_score for c in result.possible_causes] == [80, 20]
    assert [c.evidence_fit_score for c in result.possible_causes] == [74, 62]
    assert result.reference_weight == 30
    assert "blast, brown_spot, bacterial_blight, tungro, fungal_disease" in prompt_of(sent)
    evidence = next(e for e in result.evidence if e.source == "reference_photos")
    assert evidence.availability == "available"
    assert "blast 8, brown spot 2" in evidence.observation
    source = next(s for s in result.data_sources if s.kind == "reference_photos")
    assert source.status == "used"


async def test_causes_without_a_matching_label_keep_their_score() -> None:
    provider = FakeReferences(votes("tomato", early_blight=6, healthy=4))
    output = assessment(possible_causes=[cause("Magnesium deficiency", 80, "nutrient_deficiency")])
    service, _ = service_with(provider, completion(json.dumps(output)))

    result = await service.assess(replace(REPORT, crop=Crop.TOMATO))

    assert result.possible_causes[0].reference_score is None
    assert result.possible_causes[0].evidence_fit_score == 80
    assert result.reference_weight is None


async def test_detected_crop_is_searched_when_none_was_selected() -> None:
    provider = FakeReferences(votes("tomato", early_blight=10))
    output = assessment(
        crop_seen_in_photos="Tomato plant",
        possible_causes=[cause("Early blight", 70, "early_blight")],
    )
    service, sent = service_with(provider, completion(json.dumps(output)))

    result = await service.assess(REPORT)

    assert provider.calls == [("tomato", 1)]
    prompt = prompt_of(sent)
    assert "blast" in prompt and "late_blight" in prompt and "water_stress" in prompt
    assert result.possible_causes[0].reference_score == 100
    assert result.possible_causes[0].evidence_fit_score == 73


async def test_unsupported_crop_keeps_todays_scoring() -> None:
    provider = FakeReferences(votes("rice", blast=10))
    service, sent = service_with(provider, completion(json.dumps(assessment())))

    result = await service.assess(replace(REPORT, crop=Crop.WHEAT))

    assert provider.calls == []
    assert result.possible_causes[0].evidence_fit_score == 80
    assert "Condition keys for condition_key: fungal_disease," in prompt_of(sent)
    evidence = next(e for e in result.evidence if e.source == "reference_photos")
    assert evidence.availability == "unavailable"
    assert "rice, tomato and potato only" in evidence.observation


async def test_reference_failure_never_blocks_triage() -> None:
    provider = FakeReferences(error="The reference photo library is still loading.")
    service, _ = service_with(provider, completion(json.dumps(assessment())))

    result = await service.assess(replace(REPORT, crop=Crop.TOMATO))

    assert result.status == "completed"
    assert result.possible_causes[0].reference_score is None
    source = next(s for s in result.data_sources if s.kind == "reference_photos")
    assert source.status == "unavailable"
    assert source.description == "The reference photo library is still loading."


async def test_references_for_a_different_crop_are_discarded() -> None:
    provider = FakeReferences(votes("tomato", early_blight=10))
    output = assessment(
        crop_seen_in_photos="potato",
        possible_causes=[cause("Early blight", 70, "early_blight")],
    )
    service, _ = service_with(provider, completion(json.dumps(output)))

    result = await service.assess(replace(REPORT, crop=Crop.TOMATO))

    assert result.possible_causes[0].reference_score is None
    evidence = next(e for e in result.evidence if e.source == "reference_photos")
    assert "different crop" in evidence.observation


async def test_condition_keys_do_not_depend_on_the_library() -> None:
    provider = FakeReferences(
        status="loading", error="The reference photo library is still loading."
    )
    service, sent = service_with(provider, completion(json.dumps(assessment())))

    await service.assess(replace(REPORT, crop=Crop.TOMATO))

    assert "Condition keys for condition_key: early_blight, late_blight" in prompt_of(sent)


async def test_without_a_provider_reference_photos_are_not_integrated() -> None:
    service, _ = service_with(None, completion(json.dumps(assessment())))

    result = await service.assess(REPORT)

    evidence = next(e for e in result.evidence if e.source == "reference_photos")
    assert evidence.availability == "not_integrated"
    source = next(s for s in result.data_sources if s.kind == "reference_photos")
    assert source.status == "not_integrated"


async def test_unconfigured_library_fails_softly() -> None:
    provider = RetrievalReferenceProvider(Settings(retrieval_index_version="v1", _env_file=None))
    with pytest.raises(ReferenceUnavailableError, match="still loading"):
        await provider.find("rice", [JPEG_BYTES])

    provider.load()

    assert provider.status == "failed"
    with pytest.raises(ReferenceUnavailableError, match="unavailable"):
        await provider.find("rice", [JPEG_BYTES])


def test_health_reports_reference_library_status(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["reference_photos"] == "disabled"
        app.state.reference_provider = FakeReferences(status="ready")
        assert client.get("/api/v1/health").json()["reference_photos"] == "ready"
