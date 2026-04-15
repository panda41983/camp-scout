from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    environment: str = "local"
    database_url: str
    ridb_api_key: str
    scan_user_agent: str = "CampScout/0.1"
    supabase_url: str
    supabase_jwks_url: str | None = None

    model_config = {"env_file": ENV_FILE, "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def derive_jwks_url(self) -> Settings:
        if self.supabase_jwks_url is None:
            self.supabase_jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
        return self


@cache
def get_settings() -> Settings:
    return Settings()
