import pytest
from fastapi.testclient import TestClient

from app.api.routes import locations as location_routes
from app.models.weather import GeocodedLocation


def test_search_endpoint_returns_selectable_regions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeOpenMeteoClient:
        def __init__(self, *, timeout_seconds: float) -> None:
            assert timeout_seconds == 4

        async def search_locations(self, query: str) -> list[GeocodedLocation]:
            assert query == "Bhopal"
            return [
                GeocodedLocation(
                    name="Bhopal",
                    admin1="Madhya Pradesh",
                    country="India",
                    country_code="IN",
                    latitude=23.2599,
                    longitude=77.4126,
                )
            ]

    monkeypatch.setattr(location_routes, "OpenMeteoClient", FakeOpenMeteoClient)

    response = client.get("/api/v1/locations/search", params={"q": "Bhopal"})

    assert response.status_code == 200
    assert response.json()["locations"] == [
        {
            "name": "Bhopal",
            "admin1": "Madhya Pradesh",
            "country": "India",
            "country_code": "IN",
            "latitude": 23.2599,
            "longitude": 77.4126,
        }
    ]
