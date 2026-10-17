import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_shop_finder, get_treatment_advisor
from app.core.config import Settings, get_settings
from app.integrations.gemini_maps import GeminiMapsShopFinder, shops_from_response
from app.main import create_app
from app.services.treatment import TreatmentAdvisor

pytestmark = pytest.mark.anyio

ANSWER = """Here are some options:
1. **Sheti Udyog Bhandar** | 501, Shivaji Rd, Pune | Seeds, pesticides
2. **Naik Krishi Udyog & Co** | 976B, Swargate, Pune | Fertilisers
3. **Made Up Agro** | Nowhere | Everything"""


def maps_payload(text: str = ANSWER, extra_places: tuple[str, ...] = ()) -> dict[str, Any]:
    chunks = [
        {
            "maps": {
                "title": "Sheti Udyog Bhandar - Google Maps",
                "uri": "https://maps/1",
                "placeId": "P1",
            }
        },
        {
            "maps": {
                "title": "Review of Sheti Udyog Bhandar - Google Maps",
                "uri": "https://maps/1r",
            }
        },
        {
            "maps": {
                "title": "Naik Krishi Udyog & Co - Google Maps",
                "uri": "https://maps/2",
                "placeId": "P2",
            }
        },
        *(
            {"maps": {"title": title, "uri": "https://maps/x", "placeId": title}}
            for title in extra_places
        ),
    ]
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}]},
                "groundingMetadata": {"groundingChunks": chunks},
            }
        ]
    }


def test_only_shops_backed_by_maps_places_are_listed() -> None:
    shops = shops_from_response(maps_payload())

    assert [(s.name, s.place_id, s.maps_uri) for s in shops] == [
        ("Sheti Udyog Bhandar", "P1", "https://maps/1"),
        ("Naik Krishi Udyog & Co", "P2", "https://maps/2"),
    ]
    assert shops[0].address == "501, Shivaji Rd, Pune"
    assert shops[0].offers == "Seeds, pesticides"


def test_unparsed_answer_still_lists_maps_places() -> None:
    shops = shops_from_response(
        maps_payload(text="Sorry, here you go.", extra_places=("Krishi Kendra",))
    )

    assert [s.name for s in shops] == [
        "Sheti Udyog Bhandar",
        "Naik Krishi Udyog & Co",
        "Krishi Kendra",
    ]
    assert shops[0].address is None


async def test_finder_sends_location_and_falls_back_to_the_second_key() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.headers["x-goog-api-key"] == "first":
            return httpx.Response(403)
        return httpx.Response(200, json=maps_payload())

    finder = GeminiMapsShopFinder(
        api_keys=["first", "second"], models=["m"], transport=httpx.MockTransport(handler)
    )
    shops = await finder.find(latitude=18.52, longitude=73.86, place=None)

    assert len(shops) == 2
    body = json.loads(sent[-1].content)
    assert body["tools"] == [{"googleMaps": {}}]
    assert body["toolConfig"]["retrievalConfig"]["latLng"] == {
        "latitude": 18.52,
        "longitude": 73.86,
    }
    assert "JSON" not in body["contents"][0]["parts"][0]["text"]


class StubClient:
    provider_label = "Stub"
    model = "stub"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def structured_completion(self, **kwargs: Any) -> str:
        self.prompts.append(kwargs["text"])
        return json.dumps(
            {
                "non_chemical_steps": ["Remove infected leaves"],
                "active_ingredients": [
                    {"name": "mancozeb", "kind": "fungicide", "note": "Follow the label."}
                ],
                "safety": ["Wear gloves"],
                "expert_note": "Check with your KVK first.",
            }
        )


def client_with(
    advisor: TreatmentAdvisor | None, finder: GeminiMapsShopFinder | None = None
) -> TestClient:
    settings = Settings(environment="test", analysis_provider="mock", _env_file=None)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_treatment_advisor] = lambda: advisor
    app.dependency_overrides[get_shop_finder] = lambda: finder
    return TestClient(app)


@pytest.mark.parametrize(("fit", "confirm_first"), [(82, False), (75, True), (None, True)])
def test_treatment_plan_asks_to_confirm_unless_confident(
    fit: int | None, confirm_first: bool
) -> None:
    stub = StubClient()
    response = client_with(TreatmentAdvisor(stub)).post(
        "/api/v1/triage/treatment",
        json={
            "crop": "potato",
            "cause": "Late blight",
            "evidence_fit_score": fit,
            "response_language": "hi",
        },
    )

    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["confirm_first"] is confirm_first
    assert plan["active_ingredients"][0]["name"] == "mancozeb"
    assert "Hindi" in stub.prompts[0]


def test_unconfigured_and_missing_location() -> None:
    client = client_with(None)

    assert (
        client.post("/api/v1/triage/treatment", json={"crop": "potato", "cause": "x"}).status_code
        == 503
    )
    missing = client.post("/api/v1/places/agri-shops", json={})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "location_required"
    assert client.post("/api/v1/places/agri-shops", json={"latitude": 18.5}).status_code == 422
    assert client.post("/api/v1/places/agri-shops", json={"place": "Nashik"}).status_code == 503
