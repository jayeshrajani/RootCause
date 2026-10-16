"""Satellite vegetation evidence: windows, quality gates, trends and caching.

Pure logic over per-scene statistics from the Earth Engine adapter, so it is testable without
Earth Engine. `SatelliteService.analyze` never raises: failures become an explicit status.
"""

import asyncio
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import median
from typing import Protocol

from app.integrations.earth_engine import EarthEngineError, SamplingArea, Scene, SceneSeries
from app.schemas.satellite import (
    FieldBoundary,
    SamplingMethod,
    SatelliteAnalysis,
    SatelliteLimitation,
    SatelliteStatus,
    SatelliteWindow,
    VegetationTrend,
)

logger = logging.getLogger(__name__)

TREND_THRESHOLD = 0.05
LOW_VEGETATION_NDVI = 0.25
FULL_COVERAGE = 0.9
MIN_CLEAR_PIXELS = 5
# Median share of water pixels above which the point is treated as a water body, not a field.
MOSTLY_WATER = 0.5

_UNAVAILABLE_MESSAGES = {
    "auth": "Satellite imagery could not be accessed (Earth Engine credentials or project).",
    "quota": "The satellite service is busy right now (quota reached).",
    "timeout": "The satellite service did not respond in time.",
    "error": "The satellite service returned an error.",
}


class SceneSource(Protocol):
    def fetch_scenes(self, area: SamplingArea, start: date, end: date) -> SceneSeries: ...


@dataclass(frozen=True, slots=True)
class Windows:
    recent_start: date
    recent_end: date
    baseline_start: date
    baseline_end: date


def analysis_windows(analysis_date: date, days: int) -> Windows:
    """Recent window ends on analysis_date; the baseline is the equal-length window before it."""
    recent_start = analysis_date - timedelta(days=days - 1)
    baseline_end = recent_start - timedelta(days=1)
    return Windows(
        recent_start=recent_start,
        recent_end=analysis_date,
        baseline_start=baseline_end - timedelta(days=days - 1),
        baseline_end=baseline_end,
    )


def coordinates_look_rounded(latitude: float, longitude: float) -> bool:
    """Two or fewer decimals (~1 km) is too coarse to sample a specific field."""
    return all(abs(value * 100 - round(value * 100)) < 1e-6 for value in (latitude, longitude))


def _trend(change: float | None) -> VegetationTrend:
    if change is None:
        return VegetationTrend.UNKNOWN
    if change <= -TREND_THRESHOLD:
        return VegetationTrend.DECLINING
    if change >= TREND_THRESHOLD:
        return VegetationTrend.IMPROVING
    return VegetationTrend.STABLE


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def _median(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return median(present) if present else None


def summarize(
    series: SceneSeries,
    *,
    windows: Windows,
    sampling_method: SamplingMethod,
    buffer_m: int | None,
    min_clear_coverage: float,
    stale_days: int,
    approximate_location: bool,
    retrieved_at: datetime,
) -> SatelliteAnalysis:
    base = SatelliteAnalysis(
        status=SatelliteStatus.INSUFFICIENT_DATA,
        analysis_date=windows.recent_end,
        sampling_method=sampling_method,
        buffer_m=buffer_m,
        sampling_area_ha=round(series.area_m2 / 10_000, 2) if series.area_m2 else None,
        retrieved_at=retrieved_at,
    )
    if series.total_pixels <= 0:
        return base.model_copy(
            update={"reason": "empty_area", "message": "The sampling area contained no pixels."}
        )

    # Overlapping Sentinel-2 tiles can image the same day twice; keep the clearest.
    by_day: dict[date, Scene] = {}
    for scene in series.scenes:
        kept = by_day.get(scene.date)
        if kept is None or scene.clear_pixels > kept.clear_pixels:
            by_day[scene.date] = scene

    def coverage(scene: Scene) -> float:
        return min(1.0, scene.clear_pixels / series.total_pixels)

    clear = [
        scene
        for scene in by_day.values()
        if scene.ndvi is not None
        and scene.clear_pixels >= MIN_CLEAR_PIXELS
        and coverage(scene) >= min_clear_coverage
    ]
    recent = sorted(
        (s for s in clear if windows.recent_start <= s.date <= windows.recent_end),
        key=lambda s: s.date,
    )
    baseline = [s for s in clear if windows.baseline_start <= s.date <= windows.baseline_end]
    recent_any = [
        s for s in by_day.values() if windows.recent_start <= s.date <= windows.recent_end
    ]

    recent_ndvi = _median([s.ndvi for s in recent])
    recent_ndmi = _median([s.ndmi for s in recent])
    baseline_ndvi = _median([s.ndvi for s in baseline])
    baseline_ndmi = _median([s.ndmi for s in baseline])
    recent_window = SatelliteWindow(
        start=windows.recent_start,
        end=windows.recent_end,
        clear_observations=len(recent),
        ndvi_median=_round(recent_ndvi),
        ndmi_median=_round(recent_ndmi),
    )
    baseline_window = SatelliteWindow(
        start=windows.baseline_start,
        end=windows.baseline_end,
        clear_observations=len(baseline),
        ndvi_median=_round(baseline_ndvi),
        ndmi_median=_round(baseline_ndmi),
    )

    if not recent:
        water_share = _median([min(1.0, s.water_pixels / series.total_pixels) for s in recent_any])
        if water_share is not None and water_share >= MOSTLY_WATER:
            reason = "water"
            message = (
                "The sampled area is mostly water (a lake, river or flooded land), so crop "
                "greenness could not be measured."
            )
        elif recent_any:
            reason = "cloudy"
            message = "Every recent satellite pass was too cloudy over this area."
        else:
            reason = "no_scenes"
            message = "No satellite passes were found for this area in the recent window."
        return base.model_copy(
            update={
                "reason": reason,
                "message": message,
                "recent_window": recent_window,
                "baseline_window": baseline_window,
            }
        )

    latest = recent[-1]
    age = (windows.recent_end - latest.date).days
    ndvi_change = (
        recent_ndvi - baseline_ndvi
        if recent_ndvi is not None and baseline_ndvi is not None
        else None
    )
    ndmi_change = (
        recent_ndmi - baseline_ndmi
        if recent_ndmi is not None and baseline_ndmi is not None
        else None
    )
    trend = _trend(ndvi_change)
    low_vegetation = recent_ndvi is not None and recent_ndvi < LOW_VEGETATION_NDVI

    limitations: list[SatelliteLimitation] = []
    if sampling_method == SamplingMethod.BUFFER:
        limitations.append(SatelliteLimitation.APPROXIMATE_AREA)
    if approximate_location:
        limitations.append(SatelliteLimitation.APPROXIMATE_LOCATION)
    if not baseline:
        limitations.append(SatelliteLimitation.NO_BASELINE)
    if len(recent) == 1:
        limitations.append(SatelliteLimitation.SINGLE_OBSERVATION)
    if coverage(latest) < FULL_COVERAGE:
        limitations.append(SatelliteLimitation.PARTIAL_COVERAGE)
    if age > stale_days:
        limitations.append(SatelliteLimitation.STALE_OBSERVATION)
    if low_vegetation:
        limitations.append(SatelliteLimitation.LOW_VEGETATION)

    interpretable = (
        not approximate_location
        and not low_vegetation
        and trend != VegetationTrend.UNKNOWN
        and age <= stale_days
    )
    return base.model_copy(
        update={
            "status": SatelliteStatus.AVAILABLE,
            "ndvi": _round(latest.ndvi),
            "ndmi": _round(latest.ndmi),
            "ndvi_change": _round(ndvi_change),
            "ndmi_change": _round(ndmi_change),
            "trend": trend,
            "ndmi_trend": _trend(ndmi_change),
            "observation_date": latest.date,
            "observation_age_days": age,
            "valid_pixel_coverage": round(coverage(latest), 2),
            "recent_window": recent_window,
            "baseline_window": baseline_window,
            "interpretable": interpretable,
            "limitations": limitations,
        }
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SatelliteService:
    def __init__(
        self,
        source: SceneSource | None,
        *,
        window_days: int = 45,
        buffer_m: int = 100,
        timeout_seconds: float = 25,
        min_clear_coverage: float = 0.6,
        stale_days: int = 20,
        cache_ttl_seconds: int = 6 * 3600,
        cache_size: int = 256,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._source = source
        self._window_days = window_days
        self._buffer_m = buffer_m
        self._timeout_seconds = timeout_seconds
        self._min_clear_coverage = min_clear_coverage
        self._stale_days = stale_days
        self._cache_ttl = cache_ttl_seconds
        self._cache_size = cache_size
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, SatelliteAnalysis]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[SatelliteAnalysis]] = {}
        self._background: set[asyncio.Future[SatelliteAnalysis]] = set()

    @property
    def configured(self) -> bool:
        return self._source is not None

    def start_warmup(self) -> None:
        warm_up = getattr(self._source, "warm_up", None)
        if callable(warm_up):
            threading.Thread(target=warm_up, name="earth-engine-warmup", daemon=True).start()

    def _cache_key(
        self, latitude: float, longitude: float, day: date, boundary: FieldBoundary | None
    ) -> str:
        geometry = boundary.model_dump_json() if boundary else f"buffer:{self._buffer_m}"
        raw = f"{latitude:.5f}|{longitude:.5f}|{day}|{self._window_days}|{geometry}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cached(self, key: str) -> SatelliteAnalysis | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        stored_at, analysis = entry
        if time.monotonic() - stored_at > self._cache_ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return analysis

    def _store(self, key: str, analysis: SatelliteAnalysis) -> None:
        if self._cache_ttl <= 0:
            return
        self._cache[key] = (time.monotonic(), analysis)
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def analyze(
        self,
        latitude: float,
        longitude: float,
        *,
        analysis_date: date | None = None,
        boundary: FieldBoundary | None = None,
        approximate_location: bool | None = None,
    ) -> SatelliteAnalysis:
        now = self._clock()
        day = analysis_date or now.date()
        if self._source is None:
            return SatelliteAnalysis(
                status=SatelliteStatus.NOT_CONFIGURED,
                analysis_date=day,
                reason="not_configured",
                message="Satellite imagery is not configured for this server.",
            )
        approximate = (
            coordinates_look_rounded(latitude, longitude)
            if approximate_location is None
            else approximate_location
        )
        key = self._cache_key(latitude, longitude, day, boundary) + f"|{approximate}"
        cached = self._cached(key)
        if cached is not None:
            logger.info("Satellite analysis served from cache")
            return cached.model_copy(update={"limitations": list(cached.limitations)})
        # Concurrent callers (e.g. crop identification prefetch, then triage) share one request.
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(
                self._compute(key, latitude, longitude, day, boundary, approximate, now)
            )
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        analysis = await asyncio.shield(task)
        return analysis.model_copy(update={"limitations": list(analysis.limitations)})

    def prefetch(self, latitude: float, longitude: float) -> None:
        """Start an analysis in the background so a later `analyze` finds it cached or running."""
        if self._source is None:
            return
        task = asyncio.ensure_future(self.analyze(latitude, longitude))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _compute(
        self,
        key: str,
        latitude: float,
        longitude: float,
        day: date,
        boundary: FieldBoundary | None,
        approximate: bool,
        now: datetime,
    ) -> SatelliteAnalysis:
        assert self._source is not None
        windows = analysis_windows(day, self._window_days)
        method = SamplingMethod.FIELD_BOUNDARY if boundary else SamplingMethod.BUFFER
        area = SamplingArea(
            latitude=latitude, longitude=longitude, buffer_m=self._buffer_m, boundary=boundary
        )
        started = time.perf_counter()
        try:
            series = await asyncio.wait_for(
                asyncio.to_thread(
                    self._source.fetch_scenes, area, windows.baseline_start, windows.recent_end
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return self._unavailable(day, method, "timeout", now)
        except EarthEngineError as exc:
            return self._unavailable(day, method, exc.kind, now)
        except Exception:
            logger.exception("Unexpected satellite failure")
            return self._unavailable(day, method, "error", now)

        analysis = summarize(
            series,
            windows=windows,
            sampling_method=method,
            buffer_m=None if boundary else self._buffer_m,
            min_clear_coverage=self._min_clear_coverage,
            stale_days=self._stale_days,
            approximate_location=approximate,
            retrieved_at=now,
        )
        logger.info(
            "Satellite analysis status=%s scenes=%d elapsed_ms=%d",
            analysis.status.value,
            len(series.scenes),
            (time.perf_counter() - started) * 1000,
        )
        self._store(key, analysis)
        return analysis

    def _unavailable(
        self, day: date, method: SamplingMethod, kind: str, now: datetime
    ) -> SatelliteAnalysis:
        logger.warning("Satellite analysis unavailable: %s", kind)
        return SatelliteAnalysis(
            status=SatelliteStatus.UNAVAILABLE,
            analysis_date=day,
            sampling_method=method,
            buffer_m=self._buffer_m if method == SamplingMethod.BUFFER else None,
            reason=kind,
            message=_UNAVAILABLE_MESSAGES.get(kind, _UNAVAILABLE_MESSAGES["error"]),
            retrieved_at=now,
        )
