"""Application settings, read from environment variables and the local .env file."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Secrets and machine-specific settings. Experiment parameters live in YAML configs."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr


def load_settings() -> Settings:
    """Load settings, failing fast with a clear error if a required value is missing."""
    return Settings()
