from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CF_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cf_agent:cf_agent_local@localhost:55432/cf_agent_v2"
    commerce_database_url: str = ""
    commerce_url: str = "http://127.0.0.1:8001"
    commerce_read_token: SecretStr = SecretStr("")
    commerce_write_token: SecretStr = SecretStr("")
    operator_password: SecretStr = SecretStr("")
    reviewer_password: SecretStr = SecretStr("")
    cookie_secure: bool = False
    model_provider: str = "qwen"
    model_url: str = "http://127.0.0.1:18080/v1"
    model_name: str = "Qwen3-8B"
    model_key: SecretStr = SecretStr("")
    deepseek_key: SecretStr = SecretStr("")
    model_timeout: int = 60
    tool_timeout: int = 15
    max_model_calls: int = 12
    max_output_tokens: int = 1024
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_revision: str = ""
    coupon_fen: int = Field(default=1000, gt=0)
    approval_threshold_fen: int = Field(default=1000, ge=0)
    budget_admission_fen: int = Field(default=2500, ge=0, le=2500)
    deepseek_input_per_million: float = 2.0
    deepseek_output_per_million: float = 8.0
    pricing_date: str = "2026-09-17"
    job_lease_seconds: int = 120


@lru_cache
def settings() -> Settings:
    return Settings()
