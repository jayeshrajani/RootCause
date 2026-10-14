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
    SymptomDuration,
    TriageResponse,
    TriageStatus,
    UrgencyLevel,
)

MOCK_DISCLAIMER = (
    "MOCK RESULT for development only. The photos and description were received but not "
    "analysed. Do not act on this assessment."
)

_DURATION_LABELS: dict[SymptomDuration, str] = {
    SymptomDuration.LESS_THAN_3_DAYS: "less than 3 days",
    SymptomDuration.THREE_TO_7_DAYS: "3 to 7 days",
    SymptomDuration.ONE_TO_2_WEEKS: "1 to 2 weeks",
    SymptomDuration.MORE_THAN_2_WEEKS: "more than 2 weeks",
    SymptomDuration.NOT_SURE: "not sure",
}

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
        crop_name = report.crop.value.replace("_", " ")
        photo_count = len(report.images)
        duration = (
            _DURATION_LABELS[report.symptom_duration] if report.symptom_duration else "not given"
        )
        farmer_evidence = f"Farmer-reported symptoms on {crop_name} (duration: {duration})"

        return TriageResponse(
            report_id=self._id_factory(),
            status=TriageStatus.COMPLETED,
            analysis_mode=AnalysisMode.MOCK,
            crop=report.crop,
            summary=(
                f"[MOCK] Placeholder assessment for a {crop_name} report with {photo_count} "
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
                Evidence(
                    id="ev_farmer_report",
                    source=SourceKind.FARMER_REPORT,
                    availability=EvidenceAvailability.AVAILABLE,
                    observation=(
                        f"Farmer described symptoms on {crop_name}; reported duration: {duration}."
                    ),
                    observed_at=report.received_at,
                ),
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
                Evidence(
                    id="ev_weather",
                    source=SourceKind.WEATHER,
                    availability=EvidenceAvailability.NOT_INTEGRATED,
                    observation=(
                        "No weather data was retrieved. Do not assume conditions were normal."
                    ),
                ),
                Evidence(
                    id="ev_satellite",
                    source=SourceKind.SATELLITE,
                    availability=EvidenceAvailability.NOT_INTEGRATED,
                    observation="No satellite vegetation data was retrieved.",
                ),
                Evidence(
                    id="ev_knowledge",
                    source=SourceKind.KNOWLEDGE_BASE,
                    availability=EvidenceAvailability.NOT_INTEGRATED,
                    observation="No agricultural guidance was retrieved; no sources are cited.",
                ),
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
                DataSource(
                    id="src_farmer_report",
                    name="Farmer report",
                    kind=SourceKind.FARMER_REPORT,
                    status=DataSourceStatus.USED,
                    description="Crop, description, duration and approximate location.",
                ),
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
                DataSource(
                    id="src_weather",
                    name="Weather (Open-Meteo)",
                    kind=SourceKind.WEATHER,
                    status=DataSourceStatus.NOT_INTEGRATED,
                    description="Planned for Milestone 2.",
                ),
                DataSource(
                    id="src_satellite",
                    name="Satellite vegetation indices",
                    kind=SourceKind.SATELLITE,
                    status=DataSourceStatus.NOT_INTEGRATED,
                    description="Planned for Milestone 3.",
                ),
                DataSource(
                    id="src_knowledge",
                    name="Agricultural knowledge base",
                    kind=SourceKind.KNOWLEDGE_BASE,
                    status=DataSourceStatus.NOT_INTEGRATED,
                    description="Planned for Milestone 4.",
                ),
            ],
            disclaimer=MOCK_DISCLAIMER,
        )
