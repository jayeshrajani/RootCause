"""Satellite vegetation-evidence contract (Google Earth Engine / Sentinel-2).

Mirrored in apps/web/src/types/triage.ts and documented in docs/api-contract.md.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SATELLITE_SOURCE = "Google Earth Engine / Sentinel-2"
SATELLITE_DATASET = "COPERNICUS/S2_SR_HARMONIZED"
# Sentinel-2 L2A coverage in Earth Engine is reliable from 2017 onwards.
EARLIEST_ANALYSIS_DATE = date(2017, 6, 1)
MAX_BOUNDARY_VERTICES = 500
MAX_BOUNDARY_SPAN_DEGREES = 0.2


class SatelliteStatus(StrEnum):
    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    NOT_REQUESTED = "not_requested"


class VegetationTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


class SamplingMethod(StrEnum):
    BUFFER = "buffer"
    FIELD_BOUNDARY = "field_boundary"


class SatelliteLimitation(StrEnum):
    APPROXIMATE_AREA = "approximate_area"
    APPROXIMATE_LOCATION = "approximate_location"
    NO_BASELINE = "no_baseline"
    SINGLE_OBSERVATION = "single_observation"
    PARTIAL_COVERAGE = "partial_coverage"
    STALE_OBSERVATION = "stale_observation"
    LOW_VEGETATION = "low_vegetation"


class FieldBoundary(BaseModel):
    """GeoJSON Polygon in [longitude, latitude] order. Rings must be closed."""

    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]] = Field(min_length=1, max_length=20)

    @field_validator("coordinates")
    @classmethod
    def _valid_rings(
        cls, rings: list[list[tuple[float, float]]]
    ) -> list[list[tuple[float, float]]]:
        if sum(len(ring) for ring in rings) > MAX_BOUNDARY_VERTICES:
            raise ValueError(f"Use at most {MAX_BOUNDARY_VERTICES} boundary points.")
        for ring in rings:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Each ring needs at least 4 points and must be closed.")
            for lon, lat in ring:
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError("Boundary points must be [longitude, latitude].")
        outer = rings[0]
        lons = [lon for lon, _ in outer]
        lats = [lat for _, lat in outer]
        if max(max(lons) - min(lons), max(lats) - min(lats)) > MAX_BOUNDARY_SPAN_DEGREES:
            raise ValueError("The field boundary is too large for a single field.")
        return rings


class SatelliteAnalysisRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    analysis_date: date | None = Field(
        default=None, description="Last day of the analysis window; defaults to today (UTC)."
    )
    field_boundary: FieldBoundary | None = None

    @model_validator(mode="after")
    def _valid_date(self) -> "SatelliteAnalysisRequest":
        if self.analysis_date is not None:
            today = datetime.now().date()
            if self.analysis_date > today:
                raise ValueError("analysis_date cannot be in the future.")
            if self.analysis_date < EARLIEST_ANALYSIS_DATE:
                raise ValueError(f"analysis_date must be on or after {EARLIEST_ANALYSIS_DATE}.")
        return self


class SatelliteWindow(BaseModel):
    start: date
    end: date
    clear_observations: int = Field(ge=0)
    ndvi_median: float | None = None
    ndmi_median: float | None = None


class SatelliteAnalysis(BaseModel):
    """Measured vegetation indices. Supporting evidence only; never a diagnosis."""

    status: SatelliteStatus
    source: str = SATELLITE_SOURCE
    dataset: str = SATELLITE_DATASET
    analysis_date: date | None = None
    sampling_method: SamplingMethod | None = None
    buffer_m: int | None = Field(default=None, description="Radius when sampling_method=buffer.")
    sampling_area_ha: float | None = None
    ndvi: float | None = Field(default=None, description="Mean NDVI of the latest clear scene.")
    ndmi: float | None = Field(default=None, description="Mean NDMI of the latest clear scene.")
    ndvi_change: float | None = Field(
        default=None, description="Recent-window median minus earlier-window median NDVI."
    )
    ndmi_change: float | None = None
    trend: VegetationTrend = Field(
        default=VegetationTrend.UNKNOWN, description="NDVI trend versus the earlier window."
    )
    ndmi_trend: VegetationTrend = VegetationTrend.UNKNOWN
    observation_date: date | None = Field(
        default=None, description="Acquisition date of the latest clear scene."
    )
    observation_age_days: int | None = None
    valid_pixel_coverage: float | None = Field(
        default=None, ge=0, le=1, description="Share of the sampling area that was cloud-free."
    )
    recent_window: SatelliteWindow | None = None
    baseline_window: SatelliteWindow | None = None
    interpretable: bool = Field(
        default=False,
        description="True only when the evidence is field-level, fresh and comparable enough "
        "to interpret. Values may still be shown when false.",
    )
    limitations: list[SatelliteLimitation] = Field(default_factory=list)
    reason: str | None = Field(
        default=None, description="Machine-readable reason when status is not available."
    )
    message: str | None = None
    retrieved_at: datetime | None = None
