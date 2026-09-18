"""Application configuration, loaded once from the environment.

Settings are read from environment variables (and a local ``.env`` file in
development). Import the shared :data:`settings` instance everywhere rather than
reading ``os.environ`` directly, so configuration has a single source of truth.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI / LLM
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2048, alias="OPENAI_MAX_TOKENS")

    # Laravel backend (em_backend)
    backend_base_url: str = Field(
        default="http://127.0.0.1:8000/api", alias="BACKEND_BASE_URL"
    )
    backend_timeout_seconds: float = Field(
        default=15.0, alias="BACKEND_TIMEOUT_SECONDS"
    )

    # Service
    app_name: str = Field(default="rosewood-ai", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ai_internal_key: str = Field(default="", alias="AI_INTERNAL_KEY")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,http://localhost:8080,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()


settings = get_settings()
