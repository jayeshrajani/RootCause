from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.integrations.cerebras import CerebrasClient
from app.integrations.open_meteo import OpenMeteoClient
from app.services.triage import AiTriageService, MockTriageService, TriageService
from app.services.triage.translate import TriageTranslator

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _cerebras_client(settings: Settings) -> CerebrasClient | None:
    if not settings.use_cerebras or settings.cerebras_api_key is None:
        return None
    return CerebrasClient(
        api_key=settings.cerebras_api_key.get_secret_value(),
        model=settings.cerebras_model,
        base_url=settings.cerebras_base_url,
        timeout_seconds=settings.analysis_timeout_seconds,
        reasoning_effort=settings.cerebras_reasoning_effort,
    )


def get_triage_service(settings: SettingsDep) -> TriageService:
    client = _cerebras_client(settings)
    if client is not None:
        return AiTriageService(client, weather_client=OpenMeteoClient())
    return MockTriageService()


def get_triage_translator(settings: SettingsDep) -> TriageTranslator | None:
    client = _cerebras_client(settings)
    return TriageTranslator(client) if client is not None else None
