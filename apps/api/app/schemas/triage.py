"""Triage API contract. Changes here must be mirrored in apps/web/src/types/triage.ts
and documented in docs/api-contract.md."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Crop(StrEnum):
    RICE = "rice"
    WHEAT = "wheat"
    MAIZE = "maize"
    COTTON = "cotton"
    SUGARCANE = "sugarcane"
    SOYBEAN = "soybean"
    GROUNDNUT = "groundnut"
    CHICKPEA = "chickpea"
    TOMATO = "tomato"
    POTATO = "potato"
    ONION = "onion"
    CHILLI = "chilli"
    OTHER = "other"


class SymptomDuration(StrEnum):
    LESS_THAN_3_DAYS = "less_than_3_days"
    THREE_TO_7_DAYS = "3_to_7_days"
    ONE_TO_2_WEEKS = "1_to_2_weeks"
    MORE_THAN_2_WEEKS = "more_than_2_weeks"
    NOT_SURE = "not_sure"


class ResponseLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    PUNJABI = "pa"
    SPANISH = "es"
    FRENCH = "fr"


class AnalysisMode(StrEnum):
    MOCK = "mock"
    AI = "ai"


class TriageStatus(StrEnum):
    COMPLETED = "completed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class UrgencyLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceKind(StrEnum):
    FARMER_REPORT = "farmer_report"
    PHOTO = "photo"
    WEATHER = "weather"
    SATELLITE = "satellite"
    KNOWLEDGE_BASE = "knowledge_base"
    ANALYSIS_ENGINE = "analysis_engine"
    REFERENCE_PHOTOS = "reference_photos"


class EvidenceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_INTEGRATED = "not_integrated"


class DataSourceStatus(StrEnum):
    USED = "used"
    RECEIVED_NOT_ANALYSED = "received_not_analysed"
    UNAVAILABLE = "unavailable"
    NOT_INTEGRATED = "not_integrated"


class ActionPriority(StrEnum):
    IMMEDIATE = "immediate"
    WITHIN_DAYS = "within_days"
    MONITOR = "monitor"


class Evidence(BaseModel):
    """An observed fact (or the explicit absence of one). Never a hypothesis."""

    id: str
    source: SourceKind
    availability: EvidenceAvailability
    observation: str
    observed_at: datetime | None = Field(
        default=None, description="When the observation was made or recorded, if known."
    )


class PossibleCause(BaseModel):
    """A hypothesis. Never a confirmed diagnosis."""

    name: str
    explanation: str
    supporting_evidence: list[str]
    contradictory_evidence: list[str]
    confidence: ConfidenceLevel
    uncertainty_note: str
    analysis_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Image and farmer-report relevance score; not a probability.",
    )
    weather_score: int | None = Field(
        default=None, ge=0, le=100, description="Weather relevance score; omitted when unavailable."
    )
    reference_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Share of the most similar labelled reference photos showing this cause; "
        "not a probability. Omitted when no reference label matches the cause.",
    )
    evidence_fit_score: int | None = Field(
        default=None, ge=0, le=100, description="Weighted evidence-fit score; not a probability."
    )


class MissingInformation(BaseModel):
    item: str
    reason: str = Field(description="Why this information would improve certainty.")


class RecommendedAction(BaseModel):
    action: str
    rationale: str
    priority: ActionPriority
    requires_expert_verification: bool
    addresses: str | None = Field(
        default=None, description="The symptom or possible cause this step targets."
    )
    analysis_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Crop and symptom relevance score; not a probability.",
    )
    weather_score: int | None = Field(
        default=None, ge=0, le=100, description="Weather relevance score; omitted when unavailable."
    )
    evidence_fit_score: int | None = Field(
        default=None, ge=0, le=100, description="Weighted evidence-fit score; not a probability."
    )


class DataSource(BaseModel):
    id: str
    name: str
    kind: SourceKind
    status: DataSourceStatus
    description: str
    retrieved_at: datetime | None = None


class TriageResponse(BaseModel):
    report_id: str
    status: TriageStatus
    analysis_mode: AnalysisMode
    response_language: ResponseLanguage = ResponseLanguage.ENGLISH
    crop: Crop | None = Field(description="Crop the farmer selected, if any.")
    detected_crop: str | None = Field(
        default=None, description="Crop the photos appear to show (AI-read, unconfirmed)."
    )
    location_label: str | None = None
    approximate_location: str | None = None
    weather_summary: str | None = None
    reference_weight: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage weight of reference_score in evidence_fit_score, when compared.",
    )
    summary: str
    urgency: UrgencyLevel
    urgency_reason: str
    possible_causes: list[PossibleCause]
    evidence: list[Evidence]
    missing_information: list[MissingInformation]
    recommended_actions: list[RecommendedAction]
    requires_expert_review: bool
    generated_at: datetime
    data_sources: list[DataSource]
    disclaimer: str


class TranslateTriageRequest(BaseModel):
    result: TriageResponse
    target_language: ResponseLanguage
