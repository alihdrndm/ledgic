"""Runtime settings, read once from the environment."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    core_hmac_secret: str = "change-me-local-only"

    llm_mode: Literal["fixture", "live"] = "fixture"
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    embed_model: str = "text-embedding-3-small"
    embed_dims: int = 512
    llm_daily_cap_usd: Decimal = Decimal("0.50")

    worker_enabled: bool = True
    replay_enabled: bool = False
    orchestrator_version: str = "v1"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
