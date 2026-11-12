"""Runtime configuration, read from environment variables (or a local .env file)."""

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    square_environment: Literal["sandbox", "production"] = "sandbox"
    square_access_token: str = ""
    square_location_id: str = ""

    business_timezone: str = "America/Los_Angeles"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
