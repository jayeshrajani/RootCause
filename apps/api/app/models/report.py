"""Internal domain objects passed from route handlers to services.

Sensitive fields are excluded from repr so they cannot leak into logs by accident.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.schemas.triage import Crop, SymptomDuration


@dataclass(frozen=True, slots=True)
class ReportImage:
    media_type: str
    data: bytes = field(repr=False)

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass(frozen=True, slots=True)
class FarmerReport:
    crop: Crop
    description: str = field(repr=False)
    latitude: float = field(repr=False)
    longitude: float = field(repr=False)
    location_label: str | None = field(repr=False)
    symptom_duration: SymptomDuration | None
    images: tuple[ReportImage, ...]
    received_at: datetime
