"""Nearby agri-input shops via Gemini grounded on Google Maps (works with a Gemini API key).

The model's answer is matched to the grounding chunks, which carry the real Google Maps place id
and link, so every listing points at an actual Maps place rather than model-written text.
"""

import asyncio
import logging
import re
import ssl
import time
from collections.abc import Sequence
from typing import Any

import httpx
import truststore

from app.schemas.assist import Shop

logger = logging.getLogger(__name__)

MAX_SHOPS = 5
_RETRY_STATUSES = (429, 500, 503)

# Plain lines, not JSON: asking for JSON makes the model skip Maps grounding entirely.
_PROMPT = (
    "Find up to {n} shops near {where} that sell agricultural inputs (pesticides, fungicides, "
    "fertilisers or seeds), or a nearby Krishi Vigyan Kendra. For each, write one line: "
    "name | address | what they sell."
)


class ShopSearchError(Exception):
    """Every key and model failed. The message is safe to log."""


def _listed(text: str) -> list[dict[str, str]]:
    """Rows of "name | address | offers" from the model's answer (markdown and numbering ok)."""
    rows = []
    for line in text.splitlines():
        cells = [
            re.sub(r"^[\s*#>-]*(\d+[.)]\s*)?|\*\*", "", cell).strip() for cell in line.split("|")
        ]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 2 and not set(cells[0]) <= set("-: "):
            rows.append(
                {
                    "name": cells[0],
                    "address": cells[1],
                    "offers": cells[2] if len(cells) > 2 else "",
                }
            )
    return rows


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def shops_from_response(payload: dict[str, Any]) -> list[Shop]:
    """Model-listed shops, linked to their Maps places; Maps places alone if parsing fails."""
    candidate = payload["candidates"][0]
    text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
    places: dict[str, dict[str, Any]] = {}
    for chunk in candidate.get("groundingMetadata", {}).get("groundingChunks", []):
        place = chunk.get("maps") or {}
        title = str(place.get("title", "")).removesuffix(" - Google Maps").strip()
        if not title or title.lower().startswith(("review of", "photo of")):
            continue
        places.setdefault(_norm(title), {**place, "title": title})

    shops: list[Shop] = []
    for item in _listed(text):
        name = str(item["name"]).strip()
        place = places.pop(_norm(name), None)
        if place is None:
            # Only list shops Maps actually returned; never model-only names.
            match = next((key for key in places if key in _norm(name) or _norm(name) in key), None)
            place = places.pop(match) if match else None
        if place is None:
            continue
        shops.append(
            Shop(
                name=place["title"],
                address=str(item.get("address") or "").strip() or None,
                offers=str(item.get("offers") or "").strip() or None,
                maps_uri=place.get("uri"),
                place_id=place.get("placeId"),
            )
        )
    for place in places.values():
        if len(shops) >= MAX_SHOPS:
            break
        shops.append(
            Shop(name=place["title"], maps_uri=place.get("uri"), place_id=place.get("placeId"))
        )
    return shops[:MAX_SHOPS]


class GeminiMapsShopFinder:
    def __init__(
        self,
        *,
        api_keys: Sequence[str],
        models: Sequence[str] = ("gemini-flash-lite-latest", "gemini-flash-latest"),
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._attempts = [(n, key, model) for n, key in enumerate(api_keys, 1) for model in models]
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self._retry_delay = 1.0

    async def find(
        self, *, latitude: float | None, longitude: float | None, place: str | None
    ) -> list[Shop]:
        where = "this location" if latitude is not None else (place or "this place")
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": _PROMPT.format(n=MAX_SHOPS, where=where)}]}],
            "tools": [{"googleMaps": {}}],
        }
        if latitude is not None and longitude is not None:
            body["toolConfig"] = {
                "retrievalConfig": {"latLng": {"latitude": latitude, "longitude": longitude}}
            }

        last = "no key configured"
        for key_number, api_key, model in self._attempts:
            for attempt in range(2):
                if attempt:
                    await asyncio.sleep(self._retry_delay)
                started = time.perf_counter()
                try:
                    async with httpx.AsyncClient(
                        timeout=self._timeout,
                        transport=self._transport,
                        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                    ) as client:
                        response = await client.post(
                            f"{self._base_url}/models/{model}:generateContent",
                            headers={"x-goog-api-key": api_key},
                            json=body,
                        )
                except httpx.HTTPError as exc:
                    last = f"key {key_number} {model}: {type(exc).__name__}"
                    break
                if response.status_code == 200:
                    try:
                        shops = shops_from_response(response.json())
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        last = (
                            f"key {key_number} {model}: unexpected payload ({type(exc).__name__})"
                        )
                        break
                    logger.info(
                        "Maps shop search key=%d model=%s shops=%d elapsed_ms=%d",
                        key_number,
                        model,
                        len(shops),
                        (time.perf_counter() - started) * 1000,
                    )
                    return shops
                last = f"key {key_number} {model}: HTTP {response.status_code}"
                if response.status_code not in _RETRY_STATUSES:
                    break
        raise ShopSearchError(last)
