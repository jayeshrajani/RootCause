from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.integrations.cerebras import CerebrasClient
from app.integrations.google_speech import GoogleSpeechClient
from app.integrations.open_meteo import OpenMeteoClient
from app.integrations.vision import VisionModel
from app.services.satellite import SatelliteService
from app.services.transcription import TranscriptionService
from app.services.triage import AiTriageService, MockTriageService, TriageService
from app.services.triage.identify import CropIdentifier, CropSimilaritySource
from app.services.triage.references import ReferenceProvider
from app.services.triage.translate import TriageTranslator
from app.services.weather import CachedWeatherClient

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_weather_client(request: Request) -> CachedWeatherClient:
    client: CachedWeatherClient | None = getattr(request.app.state, "weather_client", None)
    return client if client is not None else CachedWeatherClient(OpenMeteoClient())


WeatherClientDep = Annotated[CachedWeatherClient, Depends(get_weather_client)]


def get_satellite_service(request: Request) -> SatelliteService:
    service: SatelliteService | None = getattr(request.app.state, "satellite_service", None)
    return service if service is not None else SatelliteService(None)


SatelliteServiceDep = Annotated[SatelliteService, Depends(get_satellite_service)]


def get_reference_provider(request: Request) -> ReferenceProvider | None:
    provider: ReferenceProvider | None = getattr(request.app.state, "reference_provider", None)
    return provider


ReferenceProviderDep = Annotated[ReferenceProvider | None, Depends(get_reference_provider)]


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


def vision_model(settings: Settings) -> VisionModel | None:
    """The configured multimodal model, or None for the labelled mock."""
    return _cerebras_client(settings)


def get_triage_service(
    settings: SettingsDep,
    reference_provider: ReferenceProviderDep = None,
    satellite: Annotated[SatelliteService | None, Depends(get_satellite_service)] = None,
    weather: Annotated[CachedWeatherClient | None, Depends(get_weather_client)] = None,
) -> TriageService:
    client = vision_model(settings)
    if client is not None:
        return AiTriageService(
            client,
            weather_client=weather or OpenMeteoClient(),
            reference_provider=reference_provider,
            satellite_service=satellite if satellite is not None and satellite.configured else None,
        )
    return MockTriageService()


def get_crop_identifier(
    settings: SettingsDep, reference_provider: ReferenceProviderDep = None
) -> CropIdentifier:
    references = (
        reference_provider if isinstance(reference_provider, CropSimilaritySource) else None
    )
    return CropIdentifier(vision_model(settings), references)


def get_triage_translator(settings: SettingsDep) -> TriageTranslator | None:
    client = vision_model(settings)
    return TriageTranslator(client) if client is not None else None


_speech_clients: dict[tuple[str, str, str, float], GoogleSpeechClient] = {}


def get_transcription_service(settings: SettingsDep) -> TranscriptionService:
    project = settings.speech_project
    if not settings.speech_configured or project is None:
        return TranscriptionService(None)
    key = (
        project,
        settings.speech_location,
        settings.speech_model,
        settings.speech_timeout_seconds,
    )
    if key not in _speech_clients:
        # One client per configuration, so ADC credentials and tokens are reused across requests.
        _speech_clients[key] = GoogleSpeechClient(
            project_id=project,
            location=settings.speech_location,
            model=settings.speech_model,
            timeout_seconds=settings.speech_timeout_seconds,
        )
    return TranscriptionService(_speech_clients[key])
