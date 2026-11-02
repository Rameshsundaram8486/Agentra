"""Typed settings loaded from environment variables and the repository's .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    agentra_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    anthropic_api_key: SecretStr | None = None
    artifact_store: Literal["local", "azure_blob"] = "local"
    artifact_store_path: Path = Path("./var/artifacts")
    azure_key_vault_url: str | None = None
    sandbox_provider: Literal["hyperv", "azure", "fake"] = "hyperv"
    log_level: str = "INFO"
    session_ttl_hours: int = 12

    @property
    def min_password_length(self) -> int:
        """Shorter passwords are allowed only for local demo accounts in development."""
        return 8 if self.agentra_env == "development" else 12

    def secret_values(self) -> list[str]:
        """Raw secret values, so logging can mask them wherever they appear."""
        database_url = self.database_url.get_secret_value()
        values = [database_url, make_url(database_url).password]
        if self.anthropic_api_key is not None:
            values.append(self.anthropic_api_key.get_secret_value())
        return [value for value in values if value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
