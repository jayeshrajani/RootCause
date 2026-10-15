from typing import Annotated

from fastapi import APIRouter, Query

from app.core.errors import AppError
from app.integrations.open_meteo import OpenMeteoClient, OpenMeteoError
from app.schemas.location import LocationOption, LocationSearchResponse

router = APIRouter(tags=["locations"])


@router.get("/locations/search", response_model=LocationSearchResponse)
async def search_locations(
    q: Annotated[str, Query(min_length=2, max_length=120)],
) -> LocationSearchResponse:
    try:
        matches = await OpenMeteoClient(timeout_seconds=4).search_locations(q)
    except OpenMeteoError as exc:
        raise AppError(
            503,
            "location_search_unavailable",
            "Location search is temporarily unavailable.",
        ) from exc
    return LocationSearchResponse(
        locations=[
            LocationOption(
                name=match.name,
                admin1=match.admin1,
                country=match.country,
                country_code=match.country_code,
                latitude=match.latitude,
                longitude=match.longitude,
            )
            for match in matches
        ]
    )
