"""Application configuration generated from spec/environment.json (foundation 01).

``Settings`` is a pydantic-settings ``BaseSettings`` whose field names mirror the
environment variable names (case-insensitive). Two safety rules from prompt 01 are
enforced at load time, not per-handler:

* Database URL selection is explicit by role (:meth:`Settings.runtime_dsn`). The
  schema-owner URL (``DATABASE_URL_MIGRATION``) is NEVER returned for a runtime role.
* local/test environments reject a production-looking database URL, and live AI is
  rejected when its confirmed allowance is zero or its allowance has expired.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeRole = Literal["api", "workflow", "search", "worker", "catalogue"]

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres", "supabase_db", "localstack"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "dev", "prod"] = "local"
    data_source: Literal["fixture", "snowflake"] = "fixture"
    ai_mode: Literal["fixture", "live"] = "fixture"
    real_onboarding_enabled: bool = False

    # Role-scoped least-privilege LOGIN URLs. Empty is allowed (fixture/offline mode).
    database_url_api: str = ""
    database_url_workflow: str = ""
    database_url_search: str = ""
    database_url_worker: str = ""
    database_url_catalogue: str = ""
    # Schema owner — migration command only; refused by runtime_dsn().
    database_url_migration: str = ""

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"

    redis_url: str = "redis://redis:6379/0"
    allowed_origins: str = "http://localhost:3000"

    openai_api_key: str = ""
    openai_text_model: str = ""
    openai_vision_model: str = ""
    ai_allowance_expires_at: str = ""
    ai_confirmed_allowance_usd: Decimal = Decimal("0")

    snowflake_account: str = ""
    snowflake_user_reader: str = ""
    snowflake_user_loader: str = ""
    snowflake_user_reporter: str = ""
    snowflake_private_key_file: str = ""
    snowflake_private_key_password: str = ""
    snowflake_database: Literal["PARTSIQ_DEV", "PARTSIQ_PROD"] = "PARTSIQ_DEV"
    snowflake_warehouse: str = "PARTSIQ_WH"
    snowflake_credit_allowance: Decimal = Decimal("0")
    snowflake_allowance_expires_at: str = ""

    semantic_search_enabled: bool = False
    bge_model_revision: str = ""

    stock_max_age_seconds: int = 3600
    demo_session_ttl_seconds: int = 86400
    demo_cleanup_grace_seconds: int = 3600
    job_lease_seconds: int = 120
    max_upload_bytes: int = 10485760
    max_image_pixels: int = 20000000

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""

    # --- workspace runtime (ADR 0002) -----------------------------------
    # Public recruiter demo: anonymous X-Demo-Token callers get an isolated, disposable,
    # session-scoped synthetic workspace. Turning this off leaves only invited accounts.
    demo_enabled: bool = True
    # Upper bound on concurrently held demo workspaces (oldest evicted) so a public demo on a
    # small VM cannot grow memory without limit.
    demo_max_workspaces: int = 400
    # Legacy Supabase projects sign access tokens with a shared HS256 secret instead of the
    # asymmetric JWKS. Server-side only; empty means only JWKS (RS256/ES256) tokens verify.
    supabase_jwt_secret: str = ""
    # Agent-collaboration mode and its server-enforced run limits. Defaults are deliberately
    # conservative for the owner's confirmed free allowance (docs/RUN_LIMITS.md).
    collaboration_enabled: bool = True
    run_max_agent_turns: int = 14
    run_max_tool_calls: int = 16
    run_max_output_tokens_per_turn: int = 600
    run_max_output_tokens: int = 6000
    run_max_usd: Decimal = Decimal("0.05")
    run_max_wall_seconds: int = 180
    run_max_retries: int = 1
    run_max_concurrent_per_scope: int = 3
    run_max_message_bytes: int = 4096
    run_max_instruction_chars: int = 500
    # Fixture replay pacing between workflow steps so a viewer can watch (and pause) a run.
    # The delay is real wall-clock time; nothing is reported done before it executes.
    fixture_step_delay_ms: int = 600

    next_public_api_origin: str = "http://localhost:8000"
    next_public_supabase_url: str = ""
    next_public_supabase_anon_key: str = ""
    api_domain: str = ""

    # --- derived helpers -------------------------------------------------

    @property
    def is_local_or_test(self) -> bool:
        return self.app_env in ("local", "test")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def runtime_dsn(self, role: RuntimeRole) -> str:
        """Return the configured DSN for a runtime role.

        Never returns the migration owner URL — that credential is for the schema
        migration command only (ARCHITECTURE section 4, CONSTRAINTS).
        """
        mapping = {
            "api": self.database_url_api,
            "workflow": self.database_url_workflow,
            "search": self.database_url_search,
            "worker": self.database_url_worker,
            "catalogue": self.database_url_catalogue,
        }
        dsn = mapping[role]
        if not dsn:
            raise RuntimeError(f"DATABASE_URL for role '{role}' is not configured")
        return dsn

    @staticmethod
    def _is_local_dsn(dsn: str) -> bool:
        if not dsn:
            return True
        host = (urlsplit(dsn).hostname or "").lower()
        return host in _LOCAL_HOSTS

    @staticmethod
    def _parse_utc(value: str) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    # --- load-time safety gates -----------------------------------------

    @model_validator(mode="after")
    def _reject_production_db_in_local_or_test(self) -> "Settings":
        if self.is_local_or_test:
            for role in ("api", "workflow", "search", "worker", "catalogue"):
                dsn = getattr(self, f"database_url_{role}")
                if dsn and not self._is_local_dsn(dsn):
                    raise ValueError(
                        f"app_env={self.app_env} refuses a non-local database URL for role '{role}'"
                    )
            if self.database_url_migration and not self._is_local_dsn(self.database_url_migration):
                raise ValueError(f"app_env={self.app_env} refuses a non-local migration URL")
        return self

    @model_validator(mode="after")
    def _reject_live_ai_without_allowance(self) -> "Settings":
        if self.ai_mode == "live":
            if self.ai_confirmed_allowance_usd <= 0:
                raise ValueError("live AI requires a confirmed non-zero allowance")
            expires = self._parse_utc(self.ai_allowance_expires_at)
            if expires is None:
                raise ValueError("live AI requires a confirmed allowance expiry")
            if expires <= datetime.now(timezone.utc):
                raise ValueError("live AI allowance has expired")
        return self


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache application settings (typed contract from prompt 01)."""
    return Settings()
