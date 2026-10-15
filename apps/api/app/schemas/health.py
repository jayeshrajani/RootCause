from typing import Literal

from pydantic import BaseModel

from app.schemas.triage import AnalysisMode


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    analysis_mode: AnalysisMode
    model: str | None = None
    reference_photos: Literal["disabled", "loading", "ready", "failed"] = "disabled"
