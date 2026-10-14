"""Deterministic mock triage used until real analysis is integrated.

Every output is labelled as mock. It never invents weather, satellite or citation data:
those sources are reported as not integrated.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.models.report import FarmerReport
from app.schemas.triage import (
    ActionPriority,
    AnalysisMode,
    ConfidenceLevel,
    DataSource,
    DataSourceStatus,
    Evidence,
    EvidenceAvailability,
    MissingInformation,
    PossibleCause,
    RecommendedAction,
    SourceKind,
    TriageResponse,
    TriageStatus,
    UrgencyLevel,
)
from app.services.triage.common import (
    crop_name,
    duration_label,
    farmer_report_evidence,
    farmer_report_source,
    not_integrated_evidence,
    not_integrated_sources,
)

MOCK_DISCLAIMER = (
    "MOCK RESULT for development only. The photos and description were received but not "
    "analysed. Do not act on this assessment."
)

_NOT_ANALYSED = "Not assessed: mock mode does not analyse photos, weather or field history."


def _new_report_id() -> str:
    return f"mock_{uuid4().hex[:16]}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MockTriageService:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = _new_report_id,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory

    async def assess(self, report: FarmerReport) -> TriageResponse:
        crop = crop_name(report) or "crop"
        photo_count = len(report.images)
        farmer_evidence = f"Farmer report on {crop} (duration: {duration_label(report)})"

        return TriageResponse(
            report_id=self._id_factory(),
            status=TriageStatus.COMPLETED,
            analysis_mode=AnalysisMode.MOCK,
            crop=report.crop,
            summary=(
                f"[MOCK] Placeholder assessment for a {crop} report with {photo_count} "
                "photo(s). The cause has not been determined; the hypotheses below are "
                "generic examples, not a diagnosis."
            ),
            urgency=UrgencyLevel.MODERATE,
            urgency_reason=(
                "[MOCK] Fixed placeholder urgency. Real urgency will weigh symptom spread, "
                "crop stage and recent weather."
            ),
            possible_causes=[
                PossibleCause(
                    name="Fungal or bacterial leaf disease",
                    explanation=(
                        "[MOCK] Generic example hypothesis. Leaf diseases commonly cause spots, "
                        "lesions or yellowing, but the photos were not examined."
                    ),
                    supporting_evidence=[farmer_evidence],
                    contradictory_evidence=[],
                    confidence=ConfidenceLevel.LOW,
                    uncertainty_note=_NOT_ANALYSED,
                ),
                PossibleCause(
                    name="Nutrient deficiency",
                    explanation=(
                        "[MOCK] Generic example hypothesis. Deficiencies often show as uniform "
                        "discolouration patterns across leaves of similar age."
                    ),
                    supporting_evidence=[farmer_evidence],
                    contradictory_evidence=[],
                    confidence=ConfidenceLevel.LOW,
                    uncertainty_note=_NOT_ANALYSED,
                ),
                PossibleCause(
                    name="Water stress (too little or too much water)",
                    explanation=(
                        "[MOCK] Generic example hypothesis. Drought or waterlogging can cause "
                        "wilting and yellowing; no rainfall data was retrieved to check this."
                    ),
                    supporting_evidence=[farmer_evidence],
                    contradictory_evidence=[],
                    confidence=ConfidenceLevel.LOW,
                    uncertainty_note=_NOT_ANALYSED,
                ),
            ],
            evidence=[
                farmer_report_evidence(report),
                Evidence(
                    id="ev_photos",
                    source=SourceKind.PHOTO,
                    availability=EvidenceAvailability.AVAILABLE,
                    observation=(
                        f"{photo_count} photo(s) received and validated. Image content was "
                        "not analysed in mock mode."
                    ),
                    observed_at=report.received_at,
                ),
                *not_integrated_evidence(),
            ],
            missing_information=[
                MissingInformation(
                    item="Close-up photos of both sides of an affected leaf",
                    reason="Helps tell fungal spots, insect damage and deficiency patterns apart.",
                ),
                MissingInformation(
                    item="How much of the field is affected (patches or whole field)",
                    reason="Patchy spread points to different causes than uniform symptoms.",
                ),
                MissingInformation(
                    item="Recent fertiliser, pesticide or irrigation activity",
                    reason="Recent inputs can cause or mask symptoms.",
                ),
                MissingInformation(
                    item="Recent rainfall and temperature at the field",
                    reason="Weather strongly influences disease and water stress risk.",
                ),
            ],
            recommended_actions=[
                RecommendedAction(
                    action="Avoid applying chemical treatments based on this result",
                    rationale="This is a mock assessment; the cause has not been identified.",
                    priority=ActionPriority.IMMEDIATE,
                    requires_expert_verification=False,
                ),
                RecommendedAction(
                    action="Mark a few affected plants and check them again in 2 to 3 days",
                    rationale="Tracking spread helps judge how urgent the problem is.",
                    priority=ActionPriority.WITHIN_DAYS,
                    requires_expert_verification=False,
                ),
                RecommendedAction(
                    action="Show the affected plants to a local agricultural extension officer",
                    rationale="A trained expert can examine the crop in person.",
                    priority=ActionPriority.WITHIN_DAYS,
                    requires_expert_verification=True,
                ),
            ],
            requires_expert_review=True,
            generated_at=self._clock(),
            data_sources=[
                farmer_report_source(),
                DataSource(
                    id="src_photos",
                    name="Uploaded photos",
                    kind=SourceKind.PHOTO,
                    status=DataSourceStatus.RECEIVED_NOT_ANALYSED,
                    description="Validated and discarded after the request; not analysed.",
                ),
                DataSource(
                    id="src_mock_engine",
                    name="RootCause mock engine",
                    kind=SourceKind.ANALYSIS_ENGINE,
                    status=DataSourceStatus.USED,
                    description="Deterministic placeholder output for development.",
                ),
                *not_integrated_sources(),
            ],
            disclaimer=MOCK_DISCLAIMER,
        )
