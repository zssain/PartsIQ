"""Gateway configuration."""

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator

from partsiq_common.config import BaseServiceSettings

from app.security import parse_api_keys


class GatewaySettings(BaseServiceSettings):
    """Settings for the gateway. API keys are validated at startup so misconfiguration fails fast."""

    api_keys: SecretStr = Field(validation_alias="GATEWAY_API_KEYS")
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000, validation_alias="GATEWAY_RATE_LIMIT_PER_MINUTE")
    orchestrator_url: AnyHttpUrl = Field(validation_alias="ORCHESTRATOR_URL")
    search_url: AnyHttpUrl = Field(validation_alias="SEARCH_URL")
    upstream_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    upstream_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    max_request_body_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    # Supabase identity (prompt 07/08). Optional at import so tooling/tests can import
    # the app without a full environment; required for a running public API.
    supabase_jwt_issuer: str | None = Field(default=None, validation_alias="SUPABASE_JWT_ISSUER")
    supabase_jwks_url: str | None = Field(default=None, validation_alias="SUPABASE_JWKS_URL")
    supabase_audience: str = Field(default="authenticated")
    internal_service_token: SecretStr | None = Field(default=None, validation_alias="INTERNAL_SERVICE_TOKEN")

    @model_validator(mode="after")
    def _validate_api_keys(self) -> "GatewaySettings":
        parse_api_keys(self.api_keys.get_secret_value())
        return self
