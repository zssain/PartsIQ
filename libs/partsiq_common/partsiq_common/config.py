"""Environment-driven configuration shared by all services."""

from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Settings common to every service. Service-specific settings subclass this model."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = Field(default="partsiq-service", min_length=1)
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: PostgresDsn | None = None
    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=10, ge=1)
    db_command_timeout_seconds: float = Field(default=30.0, gt=0)

    redis_url: RedisDsn | None = None

    health_check_timeout_seconds: float = Field(default=2.0, gt=0)

    @model_validator(mode="after")
    def _validate_pool_bounds(self) -> "BaseServiceSettings":
        if self.db_pool_max_size < self.db_pool_min_size:
            raise ValueError("db_pool_max_size must be greater than or equal to db_pool_min_size")
        return self
