"""Runtime configuration, read from environment variables (or a local .env file)."""

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Business
    business_name: str = "the barbershop"
    business_timezone: str = "America/Los_Angeles"

    # Square: "live" calls Square (sandbox or production); "fake" uses an in-memory stand-in
    square_mode: Literal["live", "fake"] = "live"
    square_environment: Literal["sandbox", "production"] = "sandbox"
    square_access_token: str = ""
    square_location_id: str = ""

    # Model: Claude on Bedrock (default) or the Anthropic API
    model_provider: Literal["bedrock", "anthropic"] = "bedrock"
    aws_profile: str = ""  # named AWS CLI profile; empty = default credential chain
    aws_region: str = "us-west-2"
    bedrock_model_id: str = ""  # empty = Strands' default Claude model on Bedrock
    anthropic_api_key: str = ""
    anthropic_model_id: str = "claude-sonnet-5-5"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
