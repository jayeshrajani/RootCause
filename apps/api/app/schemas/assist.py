"""Follow-on help after a triage: safe treatment guidance and nearby agri-input shops."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.triage import ResponseLanguage


class TreatmentRequest(BaseModel):
    crop: str = Field(min_length=1, max_length=60, description="Crop name, e.g. potato.")
    cause: str = Field(min_length=1, max_length=120, description="Likely cause, e.g. Late blight.")
    evidence_fit_score: int | None = Field(default=None, ge=0, le=100)
    response_language: ResponseLanguage = ResponseLanguage.ENGLISH


class IngredientKind(StrEnum):
    FUNGICIDE = "fungicide"
    INSECTICIDE = "insecticide"
    BACTERICIDE = "bactericide"
    BIOLOGICAL = "biological"
    NUTRIENT = "nutrient"
    OTHER = "other"


class ActiveIngredient(BaseModel):
    name: str = Field(description="Generic active ingredient, never a brand, e.g. mancozeb.")
    kind: IngredientKind
    note: str = Field(description="When it is typically used and the label caution to follow.")


class TreatmentPlan(BaseModel):
    crop: str
    cause: str
    confirm_first: bool = Field(
        description="True when the diagnosis is not confident enough to act on chemicals yet."
    )
    non_chemical_steps: list[str]
    active_ingredients: list[ActiveIngredient]
    safety: list[str]
    expert_note: str
    response_language: ResponseLanguage


class ShopSearchRequest(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    place: str | None = Field(default=None, max_length=120, description="Village or district.")


class Shop(BaseModel):
    name: str
    address: str | None = None
    offers: str | None = None
    maps_uri: str | None = None
    place_id: str | None = None


class ShopSearchResponse(BaseModel):
    shops: list[Shop]
    source: str = Field(description="Where the listings came from.")
