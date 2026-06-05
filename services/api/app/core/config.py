import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    service_name: str
    app_env: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "commerceflow-api"),
        app_env=os.getenv("APP_ENV", "local"),
    )
