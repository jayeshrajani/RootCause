from pydantic import BaseModel, Field


class LocationOption(BaseModel):
    name: str
    admin1: str | None
    country: str | None
    country_code: str | None
    latitude: float
    longitude: float


class LocationSearchResponse(BaseModel):
    locations: list[LocationOption] = Field(default_factory=list)
