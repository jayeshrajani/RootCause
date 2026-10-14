from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.triage import MockTriageService, TriageService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_triage_service() -> TriageService:
    return MockTriageService()
