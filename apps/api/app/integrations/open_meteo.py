"""Best-effort recent weather lookup using Open-Meteo's forecast API."""

import ssl
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import truststore

from app.models.weather import DailyWeather, GeocodedLocation, RecentWeather

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_TIMEOUT_SECONDS = 8.0


class OpenMeteoError(Exception):
    """Open-Meteo failed or returned an unusable response."""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class OpenMeteoClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = _TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def search_locations(self, location: str, *, count: int = 6) -> list[GeocodedLocation]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                for query in _geocoding_queries(location):
                    response = await client.get(
                        _GEOCODING_URL,
                        params={
                            "name": query,
                            "count": count,
                            "language": "en",
                            "format": "json",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    results = payload.get("results", []) if isinstance(payload, dict) else []
                    if results:
                        return [
                            self._location(result) for result in results if isinstance(result, dict)
                        ]
            return []
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OpenMeteoError("Open-Meteo geocoding failed") from exc

    async def geocode(self, location: str) -> GeocodedLocation | None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                for query in _geocoding_queries(location):
                    response = await client.get(
                        _GEOCODING_URL,
                        params={
                            "name": query,
                            "count": 1,
                            "language": "en",
                            "format": "json",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    results = payload.get("results", []) if isinstance(payload, dict) else []
                    if results:
                        break
                else:
                    return None
            result = results[0]
            if not isinstance(result, dict):
                raise OpenMeteoError("Open-Meteo returned an invalid geocoding result")
            return self._location(result)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OpenMeteoError("Open-Meteo geocoding failed") from exc

    @staticmethod
    def _location(result: dict[str, Any]) -> GeocodedLocation:
        name = result.get("name")
        latitude = _number(result.get("latitude"))
        longitude = _number(result.get("longitude"))
        if not isinstance(name, str) or latitude is None or longitude is None:
            raise OpenMeteoError("Open-Meteo returned an incomplete geocoding result")
        admin1 = result.get("admin1")
        country = result.get("country")
        country_code = result.get("country_code")
        return GeocodedLocation(
            name=name,
            latitude=latitude,
            longitude=longitude,
            admin1=admin1 if isinstance(admin1, str) else None,
            country=country if isinstance(country, str) else None,
            country_code=country_code if isinstance(country_code, str) else None,
        )

    async def recent_weather(self, latitude: float, longitude: float) -> RecentWeather:
        params: dict[str, str | float | int] = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
            "hourly": "relative_humidity_2m",
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            ) as client:
                response = await client.get(_FORECAST_URL, params=params)
            response.raise_for_status()
            return self._parse(response.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            raise OpenMeteoError("Open-Meteo weather lookup failed") from exc

    @staticmethod
    def _parse(payload: Any) -> RecentWeather:
        if not isinstance(payload, dict):
            raise OpenMeteoError("Open-Meteo returned an invalid response")
        daily = payload["daily"]
        hourly = payload["hourly"]
        timezone = ZoneInfo(payload["timezone"])
        times = daily["time"]
        humidity_times = hourly["time"]
        humidity_values = hourly["relative_humidity_2m"]
        if not all(isinstance(values, list) for values in (times, humidity_times, humidity_values)):
            raise OpenMeteoError("Open-Meteo returned an invalid response")
        if len(humidity_times) != len(humidity_values):
            raise OpenMeteoError("Open-Meteo returned mismatched hourly data")

        humidity_by_day: dict[str, list[float]] = {}
        for timestamp, value in zip(humidity_times, humidity_values, strict=True):
            number = _number(value)
            if isinstance(timestamp, str) and number is not None:
                humidity_by_day.setdefault(timestamp[:10], []).append(number)

        today = datetime.now(timezone).date().isoformat()
        completed_days = [day for day in times if isinstance(day, str) and day < today][-7:]
        if not completed_days:
            raise OpenMeteoError("Open-Meteo returned no completed daily weather")

        days: list[DailyWeather] = []
        for day in completed_days:
            index = times.index(day)
            humidity = humidity_by_day.get(day, [])
            days.append(
                DailyWeather(
                    date=day,
                    temperature_min_c=_number(daily["temperature_2m_min"][index]),
                    temperature_max_c=_number(daily["temperature_2m_max"][index]),
                    precipitation_mm=_number(daily["precipitation_sum"][index]),
                    relative_humidity_percent=(sum(humidity) / len(humidity) if humidity else None),
                )
            )
        return RecentWeather(days=tuple(days), retrieved_at=datetime.now(UTC))


def _geocoding_queries(location: str) -> tuple[str, ...]:
    original = location.strip()
    simplified = original
    for prefix in ("nearby ", "near ", "around ", "at "):
        if original.casefold().startswith(prefix):
            simplified = original[len(prefix) :].strip()
            break
    place_name = simplified.split(",", maxsplit=1)[0].strip()
    return tuple(dict.fromkeys(query for query in (original, simplified, place_name) if query))
