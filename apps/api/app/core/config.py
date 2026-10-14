from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _API_DIR.parents[1]

MEBIBYTE = 1024 * 1024


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables prefixed with ROOTCAUSE_."""

    model_config = SettingsConfigDict(
        env_prefix="ROOTCAUSE_",
        # Later files take precedence: apps/api/.env overrides the repo-root .env.
        env_file=(_REPO_ROOT / ".env", _API_DIR / ".env"),
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    max_images: int = Field(default=3, ge=1, le=10)
    max_image_bytes: int = Field(default=5 * MEBIBYTE, ge=1)

    # "auto" uses Cerebras when CEREBRAS_API_KEY is set, otherwise the labelled mock.
    analysis_provider: Literal["auto", "mock", "cerebras"] = "auto"
    analysis_timeout_seconds: float = Field(default=45, gt=0)

    cerebras_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CEREBRAS_API_KEY", "ROOTCAUSE_CEREBRAS_API_KEY"),
    )
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "qwen-3.8-27b"
    cerebras_reasoning_effort: Literal["low", "medium", "high"] = "low"

    @property
    def use_cerebras(self) -> bool:
        if self.analysis_provider == "cerebras":
            return True
        return self.analysis_provider == "auto" and self.cerebras_api_key is not None

    @property
    def max_request_bytes(self) -> int:
        # Allow headroom for text fields and multipart boundaries.
        return self.max_images * self.max_image_bytes + MEBIBYTE


@lru_cache
def get_settings() -> Settings:
    return Settings()
