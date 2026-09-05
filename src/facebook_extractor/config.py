from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Raised when configuration is invalid (SPEC.md FR-001)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    output_directory: Path = Field(default=Path("./downloads"), validation_alias="OUTPUT_DIRECTORY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("log_level")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


def load_settings() -> Settings:
    """Load configuration from .env (SPEC.md FR-001). Never raises pydantic's
    ValidationError directly — always a ConfigurationError with an actionable message."""
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc
