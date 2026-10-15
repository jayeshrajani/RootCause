"""Internal domain objects passed from route handlers to services.

Sensitive fields are excluded from repr so they cannot leak into logs by accident.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.models.references import ReferenceVotes
from app.models.weather import RecentWeather
from app.schemas.triage import Crop, ResponseLanguage, SymptomDuration


@dataclass(frozen=True, slots=True)
class ReportImage:
    media_type: str
    data: bytes = field(repr=False)

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass(frozen=True, slots=True)
class FarmerReport:
    images: tuple[ReportImage, ...]
    received_at: datetime
    crop: Crop | None = None
    description: str | None = field(default=None, repr=False)
    latitude: float | None = field(default=None, repr=False)
    longitude: float | None = field(default=None, repr=False)
    location_label: str | None = field(default=None, repr=False)
    symptom_duration: SymptomDuration | None = None
    response_language: ResponseLanguage = ResponseLanguage.ENGLISH
    weather: RecentWeather | None = None
    weather_unavailable_reason: str | None = None
    references: ReferenceVotes | None = None
    references_unavailable_reason: str | None = None
