from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.integrations.open_meteo import OpenMeteoClient, OpenMeteoError

pytestmark = pytest.mark.anyio


def weather_payload() -> dict[str, object]:
    today = datetime.now(UTC).date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(7, -2, -1)]
    hourly_times = [f"{day}T{hour:02}:00" for day in dates for hour in range(24)]
    return {
        "timezone": str(ZoneInfo("UTC")),
        "daily": {
            "time": dates,
            "temperature_2m_min": [10.0] * len(dates),
            "temperature_2m_max": [25.0] * len(dates),
            "precipitation_sum": [2.5] * len(dates),
        },
        "hourly": {
            "time": hourly_times,
            "relative_humidity_2m": [60.0] * len(hourly_times),
        },
    }


async def test_recent_weather_queries_and_summarizes_completed_days() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=weather_payload())

    result = await OpenMeteoClient(transport=httpx.MockTransport(handler)).recent_weather(
        18.52, 73.86
    )

    assert len(requests) == 1
    assert requests[0].url.host == "api.open-meteo.com"
    assert requests[0].url.path == "/v1/forecast"
    assert requests[0].url.params["latitude"] == "18.52"
    assert requests[0].url.params["longitude"] == "73.86"
    assert requests[0].url.params["past_days"] == "7"
    assert "relative_humidity_2m" in requests[0].url.params["hourly"]
    assert len(result.days) == 7
    assert result.days[0].temperature_min_c == 10.0
    assert result.days[0].temperature_max_c == 25.0
    assert result.days[0].precipitation_mm == 2.5
    assert result.days[0].relative_humidity_percent == 60.0


async def test_provider_http_failure_is_reported_as_weather_error() -> None:
    client = OpenMeteoClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )

    with pytest.raises(OpenMeteoError):
        await client.recent_weather(18.52, 73.86)


async def test_geocode_falls_back_for_nearby_place_labels() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params["name"] != "Baramati":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(
            200,
            json={"results": [{"name": "Baramati", "latitude": 18.15174, "longitude": 74.57767}]},
        )

    result = await OpenMeteoClient(transport=httpx.MockTransport(handler)).geocode(
        "Near Baramati, Pune"
    )

    assert result is not None
    assert result.name == "Baramati"
    assert result.latitude == 18.15174
    assert result.longitude == 74.57767
    assert requests[0].url.host == "geocoding-api.open-meteo.com"
    assert requests[0].url.params["name"] == "Near Baramati, Pune"
    assert requests[-1].url.params["name"] == "Baramati"


async def test_geocode_returns_none_when_no_place_matches() -> None:
    client = OpenMeteoClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": []})),
    )

    assert await client.geocode("No such place") is None


async def test_search_locations_preserves_city_region_and_country() -> None:
    payload = {
        "results": [
            {
                "name": "Bhopal",
                "admin1": "Madhya Pradesh",
                "country": "India",
                "country_code": "IN",
                "latitude": 23.2599,
                "longitude": 77.4126,
            },
            {
                "name": "Bhopal",
                "admin1": "Uttar Pradesh",
                "country": "India",
                "country_code": "IN",
                "latitude": 26.0,
                "longitude": 80.0,
            },
        ]
    }
    client = OpenMeteoClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )

    results = await client.search_locations("Bhopal")

    assert len(results) == 2
    assert (results[0].name, results[0].admin1, results[0].country) == (
        "Bhopal",
        "Madhya Pradesh",
        "India",
    )
