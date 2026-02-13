from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Required: encryption for stored Plex tokens
    secret_key: str = Field(..., alias="REMOVARR_SECRET_KEY")

    # Webhook protection
    webhook_token: str = Field("change-me-webhook", alias="REMOVARR_WEBHOOK_TOKEN")

    # Database
    db_url: str = Field("sqlite:///./data/removarr.db", alias="REMOVARR_DB_URL")

    # Optional Plex server verification
    verify_in_plex: bool = Field(False, alias="REMOVARR_VERIFY_IN_PLEX")
    plex_base_url: str | None = Field(None, alias="PLEX_BASE_URL")
    plex_server_token: str | None = Field(None, alias="PLEX_SERVER_TOKEN")

settings = Settings()
