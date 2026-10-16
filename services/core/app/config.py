"""Runtime settings, read once from the environment."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_HMAC_SECRET = "change-me-local-only"
LOCAL_HOSTS = ("@127.0.0.1", "@localhost", "@db:", "@postgres:")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    core_hmac_secret: str = PLACEHOLDER_HMAC_SECRET

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
    api_docs: bool = False  # /docs, /redoc, /openapi.json; API_DOCS=true for local development

    @property
    def is_deployed(self) -> bool:
        """A non-local database means this is a real deployment (live AI against a local DB is dev)."""
        return not any(h in self.database_url for h in LOCAL_HOSTS)

    @model_validator(mode="after")
    def _no_placeholder_secret(self) -> "Settings":
        # The placeholder is public (it is in this repo): a deployment signed with it would accept
        # anyone's admin calls. Refuse to start instead.
        if self.is_deployed and (
            self.core_hmac_secret == PLACEHOLDER_HMAC_SECRET or len(self.core_hmac_secret) < 32
        ):
            raise ValueError("CORE_HMAC_SECRET must be set to a random value of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
