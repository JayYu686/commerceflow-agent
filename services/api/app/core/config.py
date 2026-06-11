import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    service_name: str
    app_env: str
    database_url: str
    cors_origins: list[str]
    llm_provider: str
    llm_model: str
    openai_api_key: str
    openai_compatible_base_url: str
    llm_timeout_seconds: float
    llm_max_tokens: int
    llm_temperature: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "commerceflow-api"),
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://commerceflow:commerceflow_local_password@127.0.0.1:5432/commerceflow",
        ),
        cors_origins=parse_csv_env("CORS_ORIGINS", default="http://localhost:3000"),
        llm_provider=os.getenv("LLM_PROVIDER", "disabled").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_compatible_base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").strip(),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
    )


def parse_csv_env(name: str, *, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]
