"""Environment safety gate for PartsIQ.

Entry contract (FLOW.md row 00):
    def verify_environment(env: Mapping[str, str]) -> list[str]:
        return missing or unsafe environment names WITHOUT values;
        reject prod database URLs when APP_ENV is local.

Why this exists: a single deterministic check, callable from tooling, CI and
service startup, that refuses to proceed when required configuration is absent or
when a non-production environment is pointed at a production database. It returns
only NAMES, never values, so it can be logged safely (CONSTRAINTS.md rule 10).

It performs NO I/O and has no provider or database side effects.
"""
from __future__ import annotations

import sys
from collections.abc import Mapping

# Minimal configuration every backend service needs to start. These have no safe
# default in spec/environment.json (operator secret/input), so their absence is a
# hard stop rather than a silent fallback.
REQUIRED: tuple[str, ...] = (
    "APP_ENV",
    "DATABASE_URL",
    "INTERNAL_SERVICE_TOKEN",
    "SUPABASE_URL",
    "SUPABASE_JWT_ISSUER",
    "SUPABASE_JWKS_URL",
)

VALID_APP_ENVS: frozenset[str] = frozenset({"local", "test", "production"})

# Database URLs owned by a restricted login or the migration credential.
DB_URL_NAMES: tuple[str, ...] = ("DATABASE_URL", "MIGRATION_DATABASE_URL")

# Browser-exposed variables that must never carry a server secret.
PUBLIC_PREFIX = "NEXT_PUBLIC_"
SECRET_NAMES: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "SUPABASE_STORAGE_KEY",
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "INTERNAL_SERVICE_TOKEN",
    "LANGFUSE_SECRET_KEY",
)

# Hosts that are always safe for a non-production database URL.
_LOCAL_DB_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1", "::1", "postgres", "db")


def _blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _looks_like_production(url: str, prod_ref: str | None) -> bool:
    """Heuristic: does this database URL point at a managed/production project?

    Conservative on purpose — a false positive blocks a local run (safe); a false
    negative could let a test suite touch production (unsafe). We therefore flag
    anything that is NOT clearly a local/compose host.
    """
    lowered = url.lower()
    if prod_ref and prod_ref.strip() and prod_ref.strip().lower() in lowered:
        return True
    # Managed Supabase hosts are production-shaped; the local Supabase CLI uses a
    # loopback host and would not match these.
    if "supabase.co" in lowered or "supabase.com" in lowered or "pooler.supabase" in lowered:
        return True
    if "prod" in lowered:
        return True
    # If a recognisable local host is present, treat it as safe.
    return not any(h in lowered for h in _LOCAL_DB_HOSTS)


def verify_environment(env: Mapping[str, str]) -> list[str]:
    """Return the names (never values) of missing or unsafe environment variables.

    An empty list means the environment passed every check.
    """
    problems: list[str] = []
    seen: set[str] = set()

    def flag(name: str) -> None:
        if name not in seen:
            seen.add(name)
            problems.append(name)

    # 1. Required variables must be present and non-blank.
    for name in REQUIRED:
        if _blank(env.get(name)):
            flag(name)

    app_env = (env.get("APP_ENV") or "").strip().lower()

    # 2. APP_ENV must be one of the known environments.
    if app_env and app_env not in VALID_APP_ENVS:
        flag("APP_ENV")

    # 3. Non-production environments must not point at a production database.
    if app_env in ("local", "test"):
        prod_ref = env.get("PRODUCTION_PROJECT_REF")
        for name in DB_URL_NAMES:
            url = env.get(name)
            if not _blank(url) and _looks_like_production(url, prod_ref):
                flag(name)

    # 4. No paid fallback is authorised; paid budget must stay zero (ADR-015).
    paid = (env.get("AI_PAID_BUDGET_USD") or "0").strip()
    try:
        if float(paid) != 0.0:
            flag("AI_PAID_BUDGET_USD")
    except ValueError:
        flag("AI_PAID_BUDGET_USD")

    # 5. When AI is enabled, a credit expiry is mandatory (ADR-015).
    if (env.get("AI_ENABLED") or "false").strip().lower() == "true":
        if _blank(env.get("AI_CREDIT_EXPIRES_AT")):
            flag("AI_CREDIT_EXPIRES_AT")

    # 6. A browser-exposed variable must never carry a server secret's value.
    secret_values = {
        env[name] for name in SECRET_NAMES if not _blank(env.get(name))
    }
    for name, value in env.items():
        if name.startswith(PUBLIC_PREFIX) and value and value in secret_values:
            flag(name)

    return problems


def main(argv: list[str] | None = None) -> int:
    """Validate os.environ (or a provided .env-style mapping) and print only names."""
    import os

    env: Mapping[str, str] = os.environ
    problems = verify_environment(env)
    if problems:
        print("Environment check FAILED. Missing or unsafe (names only):")
        for name in problems:
            print(f"  - {name}")
        return 1
    print("Environment check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
