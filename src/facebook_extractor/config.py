from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_VAR_HINTS: dict[str, str] = {
    "FACEBOOK_PAGE_URL": "a Facebook Page URL",
    "META_ACCESS_TOKEN": "a Meta access token",
    "META_GRAPH_API_VERSION": "a Meta Graph API version (e.g. v25.0)",
}


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid (SPEC.md FR-001)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    facebook_page_url: str = Field(validation_alias="FACEBOOK_PAGE_URL")
    meta_access_token: SecretStr = Field(validation_alias="META_ACCESS_TOKEN")
    meta_graph_api_version: str = Field(validation_alias="META_GRAPH_API_VERSION")
    output_directory: Path = Field(default=Path("./downloads"), validation_alias="OUTPUT_DIRECTORY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("facebook_page_url", "meta_graph_api_version", "log_level")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("meta_access_token")
    @classmethod
    def _token_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be blank")
        return value


def load_settings() -> Settings:
    """Load and validate configuration from .env (FR-001). Never raises pydantic's
    ValidationError directly — always a ConfigurationError with an actionable message,
    and never one that echoes back a secret value (CFG-004)."""
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError(_describe(exc)) from exc


def _describe(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        env_var = str(error["loc"][0]) if error["loc"] else "configuration"
        hint = _ENV_VAR_HINTS.get(env_var, env_var)
        if error["type"] == "missing":
            lines.append(
                f"{env_var} is missing from .env.\n"
                f"Please configure {hint} before running the extractor."
            )
        else:
            lines.append(f"{env_var} is invalid: {hint} must not be blank.")
    return "\n".join(lines)
