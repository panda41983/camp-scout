from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    environment: str = "local"
    database_url: str
    ridb_api_key: str
    scan_user_agent: str = "CampScout/0.1"

    model_config = {"env_file": ENV_FILE, "env_file_encoding": "utf-8"}


@cache
def get_settings() -> Settings:
    return Settings()
