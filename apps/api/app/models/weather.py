from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    name: str
    latitude: float
    longitude: float
    admin1: str | None = None
    country: str | None = None
    country_code: str | None = None


@dataclass(frozen=True, slots=True)
class DailyWeather:
    date: str
    temperature_min_c: float | None
    temperature_max_c: float | None
    precipitation_mm: float | None
    relative_humidity_percent: float | None


@dataclass(frozen=True, slots=True)
class RecentWeather:
    days: tuple[DailyWeather, ...]
    retrieved_at: datetime
