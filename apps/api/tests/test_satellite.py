import asyncio
import json
import threading
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_triage_service
from app.core.config import Settings, get_settings
from app.integrations.cerebras import CerebrasClient
from app.integrations.earth_engine import (
    EarthEngineClient,
    EarthEngineError,
    SamplingArea,
    Scene,
    SceneSeries,
    _classify,
)
from app.main import create_app
from app.models.report import FarmerReport, ReportImage
from app.schemas.satellite import (
    SamplingMethod,
    SatelliteAnalysis,
    SatelliteLimitation,
    SatelliteStatus,
    VegetationTrend,
)
from app.services.satellite import (
    SatelliteService,
    analysis_windows,
    coordinates_look_rounded,
    summarize,
)
from app.services.triage import AiTriageService
from tests.conftest import JPEG_BYTES, jpeg
from tests.test_ai_triage import StubWeatherClient, assessment, completion

pytestmark = pytest.mark.anyio

DAY = date(2026, 10, 1)
WINDOWS = analysis_windows(DAY, 45)
NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
TOTAL = 314  # ~100 m buffer at 10 m pixels
PRECISE = (23.25991, 77.41264)


def scene(days_ago: int, ndvi: float | None, ndmi: float | None = 0.2, clear: int = TOTAL) -> Scene:
    return Scene(date=DAY - timedelta(days=days_ago), ndvi=ndvi, ndmi=ndmi, clear_pixels=clear)


def series(*scenes: Scene, total: int = TOTAL) -> SceneSeries:
    return SceneSeries(total_pixels=total, area_m2=31_400.0, scenes=scenes)


def run(
    source: SceneSeries,
    *,
    approximate: bool = False,
    method: SamplingMethod = SamplingMethod.BUFFER,
) -> SatelliteAnalysis:
    return summarize(
        source,
        windows=WINDOWS,
        sampling_method=method,
        buffer_m=100 if method == SamplingMethod.BUFFER else None,
        min_clear_coverage=0.6,
        stale_days=20,
        approximate_location=approximate,
        retrieved_at=NOW,
    )


# --- pure analysis -------------------------------------------------------------------------


def test_valid_imagery_reports_latest_scene_and_declining_trend() -> None:
    result = run(
        series(
            scene(5, 0.58, 0.10),
            scene(15, 0.62, 0.14),
            scene(60, 0.70, 0.22),
            scene(75, 0.68, 0.20),
        )
    )

    assert result.status == SatelliteStatus.AVAILABLE
    assert result.ndvi == 0.58
    assert result.observation_date == DAY - timedelta(days=5)
    assert result.valid_pixel_coverage == 1.0
    assert result.ndvi_change == pytest.approx(0.60 - 0.69, abs=1e-3)
    assert result.trend == VegetationTrend.DECLINING
    assert result.ndmi_trend == VegetationTrend.DECLINING
    assert result.recent_window and result.recent_window.clear_observations == 2
    assert result.baseline_window and result.baseline_window.clear_observations == 2
    assert result.interpretable is True
    assert result.limitations == [SatelliteLimitation.APPROXIMATE_AREA]


def test_cloudy_imagery_is_insufficient_and_never_zero() -> None:
    result = run(series(scene(5, 0.6, clear=40), scene(20, None, None, clear=0)))

    assert result.status == SatelliteStatus.INSUFFICIENT_DATA
    assert result.reason == "cloudy"
    assert result.ndvi is None and result.ndmi is None
    assert result.trend == VegetationTrend.UNKNOWN
    assert result.interpretable is False


def test_a_lake_is_reported_as_water_not_cloud() -> None:
    lake = Scene(
        date=DAY - timedelta(days=5), ndvi=0.1, ndmi=0.0, clear_pixels=60, water_pixels=240
    )
    result = run(series(lake, lake))

    assert result.status == SatelliteStatus.INSUFFICIENT_DATA
    assert result.reason == "water"
    assert result.ndvi is None
    result = run(series())

    assert result.status == SatelliteStatus.INSUFFICIENT_DATA
    assert result.reason == "no_scenes"
    assert result.ndvi is None


def test_empty_sampling_area_is_insufficient() -> None:
    assert run(series(scene(5, 0.6), total=0)).reason == "empty_area"


def test_duplicate_tiles_keep_the_clearest_and_flag_partial_coverage() -> None:
    result = run(series(scene(5, 0.3, clear=200), scene(5, 0.66, clear=250), scene(60, 0.6)))

    assert result.ndvi == 0.66
    assert result.valid_pixel_coverage == pytest.approx(250 / TOTAL, abs=0.01)
    assert SatelliteLimitation.PARTIAL_COVERAGE in result.limitations


def test_low_vegetation_is_not_interpreted_as_distress() -> None:
    result = run(series(scene(5, 0.15), scene(60, 0.55)))

    assert result.status == SatelliteStatus.AVAILABLE
    assert result.trend == VegetationTrend.DECLINING
    assert SatelliteLimitation.LOW_VEGETATION in result.limitations
    assert result.interpretable is False


def test_approximate_location_is_area_level_only() -> None:
    result = run(series(scene(5, 0.6), scene(60, 0.7)), approximate=True)

    assert SatelliteLimitation.APPROXIMATE_LOCATION in result.limitations
    assert result.interpretable is False


def test_without_a_baseline_the_trend_is_unknown() -> None:
    result = run(series(scene(5, 0.6)))

    assert result.trend == VegetationTrend.UNKNOWN
    assert result.ndvi_change is None
    assert {SatelliteLimitation.NO_BASELINE, SatelliteLimitation.SINGLE_OBSERVATION} <= set(
        result.limitations
    )
    assert result.interpretable is False


def test_stale_scene_is_not_interpretable() -> None:
    result = run(series(scene(30, 0.6), scene(60, 0.7)))

    assert SatelliteLimitation.STALE_OBSERVATION in result.limitations
    assert result.interpretable is False


def test_field_boundary_is_not_labelled_approximate_area() -> None:
    result = run(series(scene(5, 0.6), scene(60, 0.6)), method=SamplingMethod.FIELD_BOUNDARY)

    assert result.sampling_method == SamplingMethod.FIELD_BOUNDARY
    assert SatelliteLimitation.APPROXIMATE_AREA not in result.limitations
    assert result.trend == VegetationTrend.STABLE


def test_windows_are_adjacent_and_equal_length() -> None:
    assert WINDOWS.recent_end == DAY
    assert (WINDOWS.recent_end - WINDOWS.recent_start).days == 44
    assert WINDOWS.baseline_end == WINDOWS.recent_start - timedelta(days=1)
    assert (WINDOWS.baseline_end - WINDOWS.baseline_start).days == 44


@pytest.mark.parametrize(
    ("lat", "lon", "rounded"),
    [(18.52, 73.86, True), (18.5, 73.0, True), (18.5204, 73.8567, False)],
)
def test_rounded_coordinates_are_detected(lat: float, lon: float, rounded: bool) -> None:
    assert coordinates_look_rounded(lat, lon) is rounded


# --- adapter parsing ------------------------------------------------------------------------


def test_adapter_parses_payload_and_ignores_null_indices() -> None:
    parsed = EarthEngineClient._parse(
        {
            "total_pixels": 314,
            "area_m2": 31_400,
            "scenes": [
                {"date": "2026-09-20", "ndvi": 0.61, "ndmi": 0.2, "clear_pixels": 300},
                {"date": "2026-09-25", "ndvi": None, "ndmi": None, "clear_pixels": None},
                "garbage",
            ],
        }
    )

    assert parsed.total_pixels == 314
    assert parsed.scenes[0] == Scene(date(2026, 9, 20), 0.61, 0.2, 300)
    assert parsed.scenes[1].ndvi is None and parsed.scenes[1].clear_pixels == 0
    assert len(parsed.scenes) == 2


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("Permission denied on project", "auth"),
        ("Project is not registered to use Earth Engine", "auth"),
        ("Quota exceeded for quota metric", "quota"),
        ("Deadline exceeded", "timeout"),
        ("Image.reduceRegion: Something odd", "error"),
    ],
)
def test_adapter_classifies_errors(message: str, kind: str) -> None:
    assert _classify(Exception(message)).kind == kind


# --- service: failures, caching, configuration ---------------------------------------------


class FakeSource:
    def __init__(self, result: SceneSeries | Exception, delay: float = 0) -> None:
        self.result = result
        self.delay = delay
        self.calls = 0

    def fetch_scenes(self, area: SamplingArea, start: date, end: date) -> SceneSeries:
        self.calls += 1
        if self.delay:
            import time

            time.sleep(self.delay)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def service(source: FakeSource | None, **kwargs: Any) -> SatelliteService:
    return SatelliteService(source, clock=lambda: NOW, **kwargs)


async def test_unconfigured_service_reports_not_configured() -> None:
    result = await service(None).analyze(*PRECISE)

    assert result.status == SatelliteStatus.NOT_CONFIGURED


async def test_authentication_failure_is_unavailable_not_an_exception() -> None:
    result = await service(FakeSource(EarthEngineError("auth", "denied"))).analyze(*PRECISE)

    assert result.status == SatelliteStatus.UNAVAILABLE
    assert result.reason == "auth"
    assert result.ndvi is None


async def test_slow_earth_engine_times_out() -> None:
    result = await service(FakeSource(series(), delay=0.3), timeout_seconds=0.05).analyze(*PRECISE)

    assert result.status == SatelliteStatus.UNAVAILABLE
    assert result.reason == "timeout"


async def test_unexpected_errors_are_contained() -> None:
    result = await service(FakeSource(RuntimeError("boom"))).analyze(*PRECISE)

    assert result.status == SatelliteStatus.UNAVAILABLE
    assert result.reason == "error"


async def test_results_are_cached_by_location_and_window() -> None:
    source = FakeSource(series(scene(5, 0.6), scene(60, 0.6)))
    svc = service(source)

    first = await svc.analyze(*PRECISE, analysis_date=DAY)
    second = await svc.analyze(*PRECISE, analysis_date=DAY)
    await svc.analyze(PRECISE[0] + 0.01, PRECISE[1], analysis_date=DAY)

    assert first == second
    assert source.calls == 2


async def test_failures_are_not_cached() -> None:
    source = FakeSource(EarthEngineError("quota", "busy"))
    svc = service(source)

    await svc.analyze(*PRECISE)
    await svc.analyze(*PRECISE)

    assert source.calls == 2


def test_warmup_initialises_the_source_in_the_background() -> None:
    warmed = threading.Event()

    class WarmSource(FakeSource):
        def warm_up(self) -> None:
            warmed.set()

    service(WarmSource(SceneSeries(0, 0, ()))).start_warmup()

    assert warmed.wait(timeout=2)


# --- endpoint -------------------------------------------------------------------------------


def _client_with(svc: SatelliteService | None, settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    if svc is not None:
        app.state.satellite_service = svc
    return TestClient(app)


def test_endpoint_returns_satellite_analysis(settings: Settings) -> None:
    svc = service(FakeSource(series(scene(5, 0.58), scene(60, 0.7))))
    with _client_with(svc, settings) as client:
        response = client.post(
            "/api/v1/satellite/analysis",
            json={"latitude": PRECISE[0], "longitude": PRECISE[1], "analysis_date": str(DAY)},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "available"
    assert body["source"] == "Google Earth Engine / Sentinel-2"
    assert body["sampling_method"] == "buffer"
    assert body["trend"] == "declining"
    assert body["observation_date"] == str(DAY - timedelta(days=5))


def test_endpoint_without_project_is_not_configured(settings: Settings) -> None:
    with _client_with(None, settings) as client:
        response = client.post("/api/v1/satellite/analysis", json={"latitude": 1, "longitude": 2})

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 91, "longitude": 0},
        {"latitude": 1, "longitude": 2, "analysis_date": "2999-01-01"},
        {"latitude": 1, "longitude": 2, "analysis_date": "2010-01-01"},
        {
            "latitude": 1,
            "longitude": 2,
            "field_boundary": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1]]]},
        },
        {
            "latitude": 1,
            "longitude": 2,
            "field_boundary": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
            },
        },
    ],
)
def test_endpoint_validates_inputs(settings: Settings, payload: dict[str, Any]) -> None:
    with _client_with(None, settings) as client:
        response = client.post("/api/v1/satellite/analysis", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_endpoint_accepts_a_field_boundary(settings: Settings) -> None:
    source = FakeSource(series(scene(5, 0.6), scene(60, 0.6)))
    boundary = {
        "type": "Polygon",
        "coordinates": [[[77.41, 23.25], [77.411, 23.25], [77.411, 23.251], [77.41, 23.25]]],
    }
    with _client_with(service(source), settings) as client:
        response = client.post(
            "/api/v1/satellite/analysis",
            json={"latitude": 23.2505, "longitude": 77.4105, "field_boundary": boundary},
        )

    assert response.json()["sampling_method"] == "field_boundary"
    assert response.json()["buffer_m"] is None


# --- integration with AI triage -----------------------------------------------------------


class StubSatellite:
    def __init__(self, result: SatelliteAnalysis | Exception) -> None:
        self.result = result
        self.calls: list[tuple[float, float]] = []

    async def analyze(
        self, latitude: float, longitude: float, *, approximate_location: bool | None = None
    ) -> SatelliteAnalysis:
        self.calls.append((latitude, longitude))
        await asyncio.sleep(0)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


INTERPRETABLE = run(series(scene(5, 0.58, 0.1), scene(60, 0.7, 0.25)))
NOT_INTERPRETABLE = run(series(scene(5, 0.12), scene(60, 0.5)))

REPORT = FarmerReport(
    images=(ReportImage(media_type="image/jpeg", data=JPEG_BYTES),),
    received_at=datetime(2026, 10, 1, tzinfo=UTC),
    description="Leaves wilting across the field.",
    latitude=PRECISE[0],
    longitude=PRECISE[1],
)


def ai_service(
    satellite: StubSatellite, *body: dict[str, Any], weather: Any = None
) -> tuple[AiTriageService, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    responses = [completion(json.dumps(b)) for b in body]

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return responses.pop(0)

    client = CerebrasClient(api_key="k", model="qwen-test", transport=httpx.MockTransport(handler))
    return (
        AiTriageService(client, weather_client=weather, satellite_service=satellite),
        sent,
    )


def with_condition(key: str) -> dict[str, Any]:
    body = assessment()
    body["possible_causes"][0]["condition_key"] = key
    return body


async def test_interpretable_satellite_evidence_feeds_prompt_and_score() -> None:
    satellite = StubSatellite(INTERPRETABLE)
    svc, sent = ai_service(satellite, with_condition("water_stress"))

    result = await svc.assess(REPORT)

    prompt = sent[0]["messages"][1]["content"][0]["text"]
    assert "Satellite vegetation evidence (Google Earth Engine" in prompt
    assert "Satellite interpretation allowed: yes" in prompt
    cause = result.possible_causes[0]
    # Greenness and canopy moisture both falling: +6 for water stress.
    assert cause.satellite_score == 100
    assert cause.evidence_fit_score == 86
    assert cause.evidence_ledger[0].signal == "satellite"
    assert result.satellite is not None and result.satellite.trend == "declining"
    evidence = next(e for e in result.evidence if e.source == "satellite")
    assert evidence.availability == "available"
    assert next(s for s in result.data_sources if s.kind == "satellite").status == "used"


async def test_uninterpretable_satellite_is_shown_but_not_scored() -> None:
    svc, sent = ai_service(StubSatellite(NOT_INTERPRETABLE), with_condition("water_stress"))

    result = await svc.assess(REPORT)

    assert "Satellite interpretation allowed: no" in sent[0]["messages"][1]["content"][0]["text"]
    assert result.possible_causes[0].satellite_score is None
    assert result.possible_causes[0].evidence_fit_score == 80
    assert result.satellite is not None and result.satellite.interpretable is False


async def test_satellite_failure_does_not_block_triage() -> None:
    svc, _ = ai_service(StubSatellite(RuntimeError("ee down")), assessment())

    result = await svc.assess(REPORT)

    assert result.status == "completed"
    assert result.satellite is not None and result.satellite.status == "unavailable"
    assert next(e for e in result.evidence if e.source == "satellite").availability == (
        "unavailable"
    )


async def test_place_name_only_skips_satellite() -> None:
    satellite = StubSatellite(INTERPRETABLE)
    report = FarmerReport(
        images=REPORT.images,
        received_at=REPORT.received_at,
        location_label="Bhopal",
    )
    svc, _ = ai_service(satellite, assessment(), weather=StubWeatherClient())

    result = await svc.assess(report)

    assert satellite.calls == []
    assert result.satellite is not None and result.satellite.status == "not_requested"


async def test_place_search_coordinates_skip_satellite() -> None:
    satellite = StubSatellite(INTERPRETABLE)
    report = replace(REPORT, latitude=23.25, longitude=77.4)
    svc, _ = ai_service(satellite, assessment(), weather=StubWeatherClient())

    result = await svc.assess(report)

    assert satellite.calls == []
    assert result.satellite is not None
    assert (result.satellite.status, result.satellite.reason) == (
        "not_requested",
        "approximate_location",
    )


async def test_satellite_runs_alongside_weather() -> None:
    satellite = StubSatellite(INTERPRETABLE)
    weather = StubWeatherClient()
    svc, _ = ai_service(satellite, assessment(), weather=weather)

    await svc.assess(REPORT)

    assert satellite.calls == [PRECISE]
    assert weather.coordinates == PRECISE


def test_triage_endpoint_returns_satellite_evidence(settings: Settings) -> None:
    satellite = StubSatellite(INTERPRETABLE)
    svc, _ = ai_service(satellite, assessment())
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_triage_service] = lambda: svc
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/triage",
            data={"latitude": str(PRECISE[0]), "longitude": str(PRECISE[1])},
            files=[jpeg()],
        )

    assert response.status_code == 200
    assert response.json()["satellite"]["status"] == "available"
    assert response.json()["satellite"]["trend"] == "declining"
