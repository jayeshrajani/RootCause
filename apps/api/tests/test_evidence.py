import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_crop_identifier
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.report import ReportImage
from app.models.weather import DailyWeather, GeocodedLocation, RecentWeather
from app.schemas.satellite import SatelliteAnalysis, SatelliteStatus, VegetationTrend
from app.schemas.triage import (
    AnalysisMode,
    ConfidenceLevel,
    Crop,
    ReferenceAgreement,
    WeatherFacts,
)
from app.services.triage.evidence import (
    CONDITIONS,
    condition_keys_for,
    satellite_adjustment,
    weather_adjustment,
    weather_facts,
)
from app.services.triage.identify import CropIdentifier, CropModelOutput, fuse
from app.services.weather import CachedWeatherClient
from tests.conftest import JPEG_BYTES, jpeg

pytestmark = pytest.mark.anyio


def week(*, tmin: float, tmax: float, rain: float, rh: float, days: int = 7) -> RecentWeather:
    return RecentWeather(
        days=tuple(
            DailyWeather(
                date=f"2026-10-{8 + i:02d}",
                temperature_min_c=tmin,
                temperature_max_c=tmax,
                precipitation_mm=rain,
                relative_humidity_percent=rh,
            )
            for i in range(days)
        ),
        retrieved_at=datetime(2026, 10, 15, tzinfo=UTC),
    )


COOL_HUMID = weather_facts(week(tmin=14, tmax=24, rain=4, rh=90))
HOT_DRY = weather_facts(week(tmin=24, tmax=38, rain=0, rh=35))
assert COOL_HUMID is not None and HOT_DRY is not None


def facts(f: WeatherFacts | None) -> WeatherFacts:
    assert f is not None
    return f


# --- weather facts and rules ------------------------------------------------------------------


def test_weather_facts_summarise_the_week() -> None:
    f = facts(COOL_HUMID)
    assert (f.days, f.temp_mean_c, f.rain_total_mm, f.wet_days, f.humid_days) == (7, 19, 28, 7, 7)
    assert f.pattern == "wet"
    assert facts(HOT_DRY).pattern == "hot_dry"
    assert weather_facts(None) is None


@pytest.mark.parametrize(
    ("key", "weather", "sign"),
    [
        ("late_blight", COOL_HUMID, 1),
        ("late_blight", HOT_DRY, -1),
        ("spider_mites", HOT_DRY, 1),
        ("spider_mites", COOL_HUMID, -1),
        ("water_stress", HOT_DRY, 1),
        ("water_stress", COOL_HUMID, -1),
        ("heat_stress", HOT_DRY, 1),
        ("bacterial_blight", HOT_DRY, -1),
        ("nutrient_deficiency", HOT_DRY, 0),
    ],
)
def test_weather_rules_follow_agronomic_tendencies(
    key: str, weather: WeatherFacts | None, sign: int
) -> None:
    result = weather_adjustment(key, facts(weather))
    assert (result.points > 0) - (result.points < 0) == sign
    assert -10 <= result.points <= 10
    assert result.reason


def test_unknown_condition_is_neutral() -> None:
    assert weather_adjustment("made_up", facts(HOT_DRY)).points == 0


def test_every_condition_has_a_rule_and_crops_get_specific_keys() -> None:
    assert all(weather_adjustment(k, facts(HOT_DRY)).reason for k in CONDITIONS)
    assert condition_keys_for("rice")[:4] == ("blast", "brown_spot", "bacterial_blight", "tungro")
    assert "blast" not in condition_keys_for("wheat")
    assert "blast" in condition_keys_for(None) and "late_blight" in condition_keys_for(None)


def sat(
    trend: VegetationTrend, ndmi: VegetationTrend = VegetationTrend.STABLE
) -> SatelliteAnalysis:
    return SatelliteAnalysis(
        status=SatelliteStatus.AVAILABLE,
        analysis_date=date(2026, 10, 15),
        ndvi=0.6,
        ndvi_change=-0.1 if trend == VegetationTrend.DECLINING else 0.0,
        trend=trend,
        ndmi_trend=ndmi,
        interpretable=True,
    )


def test_satellite_rules_are_bounded_and_explained() -> None:
    drying = sat(VegetationTrend.DECLINING, VegetationTrend.DECLINING)
    assert satellite_adjustment("water_stress", drying, None).points == 6
    assert satellite_adjustment("water_stress", sat(VegetationTrend.IMPROVING), None).points == -4
    # Decline in a wet week points to a spreading problem, not drought.
    assert satellite_adjustment("late_blight", drying, facts(COOL_HUMID)).points == 4
    # Decline in a dry week could be drought, so it does not support disease.
    assert satellite_adjustment("late_blight", drying, facts(HOT_DRY)).points == 0
    steady = satellite_adjustment("late_blight", sat(VegetationTrend.STABLE), None)
    assert steady.points == 0 and "some plants" in steady.reason
    greener = satellite_adjustment("late_blight", sat(VegetationTrend.IMPROVING), None)
    assert "getting greener" in greener.reason


# --- crop identification --------------------------------------------------------------------


def model_says(
    crop: str, confidence: str = "high", alternative: str = "none", quality: str = "good"
) -> CropModelOutput:
    return CropModelOutput(
        crop_visible_features=["leaflets"],
        crop_seen_in_photos=crop,
        crop_identification_confidence=ConfidenceLevel(confidence),
        alternative_crop=alternative,
        image_quality=quality,
    )


def test_confident_model_with_agreeing_references_continues() -> None:
    result = fuse(model_says("tomato"), {"tomato": 0.62, "potato": 0.55}, AnalysisMode.AI)
    assert result.crop == Crop.TOMATO
    assert result.reference_agreement == ReferenceAgreement.AGREES
    assert not result.needs_confirmation


def test_references_that_clearly_disagree_ask_the_farmer() -> None:
    result = fuse(model_says("tomato"), {"tomato": 0.40, "potato": 0.62}, AnalysisMode.AI)
    assert result.reference_agreement == ReferenceAgreement.DISAGREES
    assert result.needs_confirmation
    assert result.candidates == [Crop.TOMATO, Crop.POTATO]


def test_unsure_model_asks_with_candidates() -> None:
    result = fuse(model_says("potato", "medium", "tomato"), {}, AnalysisMode.AI)
    assert result.needs_confirmation
    assert result.candidates == [Crop.POTATO, Crop.TOMATO]
    assert result.reference_agreement == ReferenceAgreement.UNAVAILABLE


def test_crops_outside_the_library_rely_on_the_model() -> None:
    result = fuse(model_says("wheat"), {"rice": 0.6, "tomato": 0.3}, AnalysisMode.AI)
    assert result.reference_agreement == ReferenceAgreement.NOT_COVERED
    assert result.crop == Crop.WHEAT and not result.needs_confirmation


def test_without_a_model_the_farmer_confirms() -> None:
    result = fuse(None, {"rice": 0.7}, AnalysisMode.MOCK)
    assert result.needs_confirmation and result.crop == Crop.RICE


class FailingModel:
    model = "broken"

    async def structured_completion(self, **_: Any) -> str:
        from app.integrations.vision import VisionModelError

        raise VisionModelError("Model request timed out")


async def test_model_failure_never_blocks_identification() -> None:
    identifier = CropIdentifier(FailingModel())
    result = await identifier.identify([ReportImage(media_type="image/jpeg", data=JPEG_BYTES)])
    assert result.needs_confirmation and result.crop is None


def test_identify_endpoint_prefetches_weather(settings: Settings) -> None:
    calls: list[tuple[float, float]] = []

    class Source:
        async def geocode(self, location: str) -> GeocodedLocation | None:
            return None

        async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather:
            calls.append((latitude, longitude))
            return week(tmin=10, tmax=20, rain=0, rh=50)

    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_crop_identifier] = lambda: CropIdentifier(None)
    app.state.weather_client = CachedWeatherClient(Source())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/triage/identify",
            data={"latitude": "30.7712", "longitude": "75.4693"},
            files=[jpeg()],
        )

    assert response.status_code == 200
    assert response.json()["needs_confirmation"] is True
    assert response.json()["analysis_mode"] == "mock"
    assert calls == [(30.7712, 75.4693)]


def test_identify_requires_a_photo(client: TestClient) -> None:
    response = client.post("/api/v1/triage/identify", data={})
    assert response.status_code == 422


# --- weather cache ----------------------------------------------------------------------------


async def test_weather_cache_shares_inflight_requests_and_never_caches_errors() -> None:
    calls = 0
    fail = True

    class Source:
        async def geocode(self, location: str) -> GeocodedLocation | None:
            return None

        async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            if fail:
                raise RuntimeError("down")
            return week(tmin=10, tmax=20, rain=0, rh=50)

    cache = CachedWeatherClient(Source())
    with pytest.raises(RuntimeError):
        await cache.recent_weather(1, 2)
    fail = False
    first, second = await asyncio.gather(cache.recent_weather(1, 2), cache.recent_weather(1, 2))
    await cache.recent_weather(1, 2)

    assert first is second
    assert calls == 2
