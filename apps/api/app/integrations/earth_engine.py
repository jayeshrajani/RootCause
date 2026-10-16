"""Google Earth Engine adapter. The only module that imports `ee`.

Returns raw per-scene statistics; interpretation lives in app.services.satellite.
"""

import contextlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import ee
import google.auth
import truststore
from google.auth.exceptions import GoogleAuthError

from app.schemas.satellite import SATELLITE_DATASET, FieldBoundary

logger = logging.getLogger(__name__)

EE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine.readonly",
    "https://www.googleapis.com/auth/cloud-platform",
)
# Sentinel-2 Scene Classification: 4 vegetation, 5 bare soil, 7 unclassified. Everything else
# (no data, saturated, dark/shadow, cloud shadow, water, clouds, cirrus, snow) is masked out.
CLEAR_SCL_CLASSES = (4, 5, 7)
WATER_SCL_CLASS = 6
SCALE_M = 10
_MAX_SCENES = 200
_INIT_RETRY_SECONDS = 60


class EarthEngineError(Exception):
    """Earth Engine failed. `kind` is one of auth, quota, timeout, error."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class SamplingArea:
    latitude: float
    longitude: float
    buffer_m: int
    boundary: FieldBoundary | None = None


@dataclass(frozen=True, slots=True)
class Scene:
    date: date
    ndvi: float | None
    ndmi: float | None
    clear_pixels: int
    water_pixels: int = 0


@dataclass(frozen=True, slots=True)
class SceneSeries:
    total_pixels: int
    area_m2: float
    scenes: tuple[Scene, ...]


def _classify(exc: BaseException) -> EarthEngineError:
    text = str(exc).lower()
    if isinstance(exc, GoogleAuthError) or any(
        word in text
        for word in ("permission", "credential", "authoriz", "not registered", "unauthenticated")
    ):
        return EarthEngineError("auth", "Earth Engine rejected the credentials or project.")
    if "quota" in text or "too many" in text or "rate limit" in text:
        return EarthEngineError("quota", "Earth Engine quota was exceeded.")
    if "deadline" in text or "timed out" in text or "timeout" in text:
        return EarthEngineError("timeout", "Earth Engine did not respond in time.")
    return EarthEngineError("error", f"Earth Engine request failed: {type(exc).__name__}")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class EarthEngineClient:
    def __init__(self, *, project_id: str, timeout_seconds: float) -> None:
        self._project_id = project_id
        self._timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._ready = False
        self._last_failure = 0.0

    def _ensure_initialized(self) -> None:
        with self._lock:
            if self._ready:
                return
            if time.monotonic() - self._last_failure < _INIT_RETRY_SECONDS:
                raise EarthEngineError("auth", "Earth Engine initialisation recently failed.")
            # The SDK's httplib2 transport ignores the OS trust store; corporate TLS proxies
            # need it, and it is a no-op elsewhere.
            truststore.inject_into_ssl()
            try:
                credentials: Any
                if os.path.exists(ee.oauth.get_credentials_path()):
                    # Saved by `earthengine authenticate`; skips google.auth.default()'s
                    # metadata-server probe, which costs ~12 s off Google Cloud.
                    credentials = "persistent"
                else:
                    credentials = google.auth.default(scopes=list(EE_SCOPES))[0]
                ee.Initialize(credentials=credentials, project=self._project_id)
                ee.data.setDeadline(int(self._timeout_seconds * 1000))
            except Exception as exc:
                self._last_failure = time.monotonic()
                error = _classify(exc)
                logger.warning("Earth Engine initialisation failed: %s", error.kind)
                raise error from exc
            self._ready = True
            logger.info("Earth Engine initialised for project %s", self._project_id)

    def warm_up(self) -> None:
        """Initialise ahead of the first request; failures are retried on demand."""
        with contextlib.suppress(EarthEngineError):
            self._ensure_initialized()

    def fetch_scenes(self, area: SamplingArea, start: date, end: date) -> SceneSeries:
        """Per-scene mean NDVI/NDMI over clear pixels for [start, end], in one round trip."""
        self._ensure_initialized()
        try:
            payload = self._build_query(area, start, end).getInfo()
        except Exception as exc:
            raise _classify(exc) from exc
        return self._parse(payload)

    @staticmethod
    def _geometry(area: SamplingArea) -> Any:
        if area.boundary is not None:
            rings = [[list(point) for point in ring] for ring in area.boundary.coordinates]
            return ee.Geometry.Polygon(rings, None, False)
        return ee.Geometry.Point([area.longitude, area.latitude]).buffer(area.buffer_m)

    def _build_query(self, area: SamplingArea, start: date, end: date) -> Any:
        geometry = self._geometry(area)

        def scene_stats(image: Any) -> Any:
            scl = image.select("SCL")
            clear = scl.remap(list(CLEAR_SCL_CLASSES), [1] * len(CLEAR_SCL_CLASSES), 0).rename(
                "clear"
            )
            indices = (
                image.normalizedDifference(["B8", "B4"])
                .rename("ndvi")
                .addBands(image.normalizedDifference(["B8", "B11"]).rename("ndmi"))
                .updateMask(clear)
            )
            means = indices.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geometry, scale=SCALE_M, maxPixels=10_000_000
            )
            clear_pixels = clear.selfMask().reduceRegion(
                reducer=ee.Reducer.count(), geometry=geometry, scale=SCALE_M, maxPixels=10_000_000
            )
            water_pixels = (
                scl.eq(WATER_SCL_CLASS)
                .selfMask()
                .rename("water")
                .reduceRegion(
                    reducer=ee.Reducer.count(),
                    geometry=geometry,
                    scale=SCALE_M,
                    maxPixels=10_000_000,
                )
            )
            return ee.Feature(
                None,
                {
                    "date": image.date().format("YYYY-MM-dd"),
                    "ndvi": means.get("ndvi"),
                    "ndmi": means.get("ndmi"),
                    "clear_pixels": clear_pixels.get("clear"),
                    "water_pixels": water_pixels.get("water"),
                },
            )

        scenes = (
            ee.ImageCollection(SATELLITE_DATASET)
            .filterBounds(geometry)
            .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
            .map(scene_stats)
        )
        total_pixels = (
            ee.Image.constant(1)
            .reduceRegion(
                reducer=ee.Reducer.count(), geometry=geometry, scale=SCALE_M, maxPixels=10_000_000
            )
            .get("constant")
        )
        return ee.Dictionary(
            {
                "total_pixels": total_pixels,
                "area_m2": geometry.area(1),
                "scenes": scenes.toList(_MAX_SCENES).map(
                    lambda feature: ee.Feature(feature).toDictionary()
                ),
            }
        )

    @staticmethod
    def _parse(payload: Any) -> SceneSeries:
        if not isinstance(payload, dict):
            raise EarthEngineError("error", "Earth Engine returned an unexpected payload.")
        scenes: list[Scene] = []
        for raw in payload.get("scenes") or []:
            if not isinstance(raw, dict) or not isinstance(raw.get("date"), str):
                continue
            clear = _number(raw.get("clear_pixels"))
            water = _number(raw.get("water_pixels"))
            scenes.append(
                Scene(
                    date=date.fromisoformat(raw["date"]),
                    ndvi=_number(raw.get("ndvi")),
                    ndmi=_number(raw.get("ndmi")),
                    clear_pixels=int(clear) if clear is not None else 0,
                    water_pixels=int(water) if water is not None else 0,
                )
            )
        total = _number(payload.get("total_pixels"))
        area = _number(payload.get("area_m2"))
        return SceneSeries(
            total_pixels=int(total) if total is not None else 0,
            area_m2=area if area is not None else 0.0,
            scenes=tuple(scenes),
        )
