"""Evidence and provenance shared by every triage engine."""

from app.models.report import FarmerReport
from app.schemas.triage import (
    DataSource,
    DataSourceStatus,
    Evidence,
    EvidenceAvailability,
    SourceKind,
    SymptomDuration,
)

DURATION_LABELS: dict[SymptomDuration, str] = {
    SymptomDuration.LESS_THAN_3_DAYS: "less than 3 days",
    SymptomDuration.THREE_TO_7_DAYS: "3 to 7 days",
    SymptomDuration.ONE_TO_2_WEEKS: "1 to 2 weeks",
    SymptomDuration.MORE_THAN_2_WEEKS: "more than 2 weeks",
    SymptomDuration.NOT_SURE: "not sure",
}


def crop_name(report: FarmerReport) -> str | None:
    return report.crop.value.replace("_", " ") if report.crop else None


def duration_label(report: FarmerReport) -> str:
    return DURATION_LABELS[report.symptom_duration] if report.symptom_duration else "not given"


def farmer_report_evidence(report: FarmerReport) -> Evidence:
    parts = [f"Crop: {crop_name(report) or 'not specified'}", f"duration: {duration_label(report)}"]
    if report.description:
        observation = (
            f"Farmer's description: \u201c{report.description}\u201d ({', '.join(parts)})."
        )
    else:
        observation = f"No written description was given ({', '.join(parts)})."
    return Evidence(
        id="ev_farmer_report",
        source=SourceKind.FARMER_REPORT,
        availability=EvidenceAvailability.AVAILABLE,
        observation=observation,
        observed_at=report.received_at,
    )


def not_integrated_evidence() -> list[Evidence]:
    return [
        Evidence(
            id="ev_weather",
            source=SourceKind.WEATHER,
            availability=EvidenceAvailability.NOT_INTEGRATED,
            observation="No weather data was retrieved. Do not assume conditions were normal.",
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
    ]


def farmer_report_source() -> DataSource:
    return DataSource(
        id="src_farmer_report",
        name="Farmer report",
        kind=SourceKind.FARMER_REPORT,
        status=DataSourceStatus.USED,
        description="Description and any optional details the farmer added.",
    )


def not_integrated_sources() -> list[DataSource]:
    return [
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
    ]
