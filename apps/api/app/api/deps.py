from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.integrations.cerebras import CerebrasClient
from app.services.triage import AiTriageService, MockTriageService, TriageService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_triage_service(settings: SettingsDep) -> TriageService:
    if settings.use_cerebras and settings.cerebras_api_key is not None:
        client = CerebrasClient(
            api_key=settings.cerebras_api_key.get_secret_value(),
            model=settings.cerebras_model,
            base_url=settings.cerebras_base_url,
            timeout_seconds=settings.analysis_timeout_seconds,
            reasoning_effort=settings.cerebras_reasoning_effort,
        )
        return AiTriageService(client)
    return MockTriageService()
