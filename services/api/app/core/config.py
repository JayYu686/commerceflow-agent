from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "commerceflow-api"
    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://commerceflow:commerceflow_local_password@127.0.0.1:5432/commerceflow"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    llm_provider: str = "disabled"
    llm_model: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_compatible_base_url: str = ""
    llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    llm_max_tokens: int = Field(default=512, ge=64, le=4096)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318/v1/traces"
    otel_service_name: str = "commerceflow-api"
    trace_ui_url: str = ""
    embedding_provider: str = "deterministic"
    embedding_model: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_base_url: str = ""
    embedding_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    embedding_dimensions: int = Field(default=1536, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("llm_provider", "embedding_provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()
