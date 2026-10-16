"""Process-wide Open-Meteo access with a short TTL cache and shared in-flight requests."""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from app.models.weather import GeocodedLocation, RecentWeather

T = TypeVar("T")

WEATHER_TTL_SECONDS = 3600
GEOCODE_TTL_SECONDS = 24 * 3600
_MAX_ENTRIES = 512


class WeatherSource(Protocol):
    async def geocode(self, location: str) -> GeocodedLocation | None: ...

    async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather: ...


class _TtlCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    async def get(self, key: str, load: Callable[[], Awaitable[T]]) -> T:
        entry = self._entries.get(key)
        if entry is not None and time.monotonic() - entry[0] <= self._ttl:
            self._entries.move_to_end(key)
            value: T = entry[1]
            return value
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(load())
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        value = await asyncio.shield(task)  # errors propagate and are never cached
        self._entries[key] = (time.monotonic(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > _MAX_ENTRIES:
            self._entries.popitem(last=False)
        return value


class CachedWeatherClient:
    def __init__(self, source: WeatherSource) -> None:
        self._source = source
        self._weather = _TtlCache(WEATHER_TTL_SECONDS)
        self._places = _TtlCache(GEOCODE_TTL_SECONDS)
        self._background: set[asyncio.Future[RecentWeather]] = set()

    async def geocode(self, location: str) -> GeocodedLocation | None:
        return await self._places.get(
            location.strip().casefold(), lambda: self._source.geocode(location)
        )

    async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather:
        return await self._weather.get(
            f"{latitude:.4f}|{longitude:.4f}",
            lambda: self._source.recent_weather(latitude, longitude),
        )

    def prefetch(self, latitude: float, longitude: float) -> None:
        task = asyncio.ensure_future(self.recent_weather(latitude, longitude))
        self._background.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: "asyncio.Future[RecentWeather]") -> None:
        self._background.discard(task)
        # Retrieve the exception so a failed prefetch is not reported as unhandled.
        if not task.cancelled():
            task.exception()
