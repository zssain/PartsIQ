"""Apply the two immutable legacy catalogue migrations through the Supabase runner.

Contract (FLOW.md row 02):
    async def apply_catalogue_schema(dsn: str) -> None

Rules:
  * The two migration files must be byte-for-byte copies of spec/sql/001 and 002
    (they preserve numeric keys, serial-range exclusion, supersession cycle protection
    and warehouse transfer days). A tampered migration is refused.
  * This NEVER resets a database. A reset-style command is refused outright, so this
    tool cannot wipe production (CONSTRAINTS.md rule 20).
  * Applying additively is delegated to `supabase migration up`, which tracks applied
    migrations and will not re-create existing tables.
"""
from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
SPEC_SQL_DIR = REPO_ROOT / "spec" / "sql"

# (migration filename, authoritative spec source) — order matters.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("20261011000100_legacy_catalogue.sql", "001_initial_schema.sql"),
    ("20261011000200_legacy_search.sql", "002_search_and_fulfilment.sql"),
)

_FORBIDDEN_TOKENS = ("reset", "--linked", "db reset")

Runner = Callable[[list[str]], Awaitable[None]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_not_reset(args: list[str]) -> None:
    """Refuse any command that would reset/destroy a database."""
    lowered = " ".join(args).lower()
    if any(token in lowered for token in _FORBIDDEN_TOKENS):
        raise RuntimeError("refusing a reset/destructive database command")


def verify_migrations_verbatim(
    migrations_dir: Path = MIGRATIONS_DIR, spec_dir: Path = SPEC_SQL_DIR
) -> None:
    """Confirm each migration is a byte-for-byte copy of its spec source."""
    for filename, spec_name in MIGRATIONS:
        migration = migrations_dir / filename
        spec = spec_dir / spec_name
        if not migration.exists():
            raise FileNotFoundError(f"missing migration {filename}")
        if _sha256(migration) != _sha256(spec):
            raise RuntimeError(f"migration {filename} is not verbatim copy of {spec_name}")


async def _default_supabase_runner(args: list[str]) -> None:
    """Run the supabase CLI; refuse destructive commands before spawning."""
    assert_not_reset(args)
    process = await asyncio.create_subprocess_exec(*args)
    code = await process.wait()
    if code != 0:
        raise RuntimeError(f"command failed ({code}): {' '.join(args)}")


async def apply_catalogue_schema(dsn: str, *, runner: Runner | None = None) -> None:
    """Apply the immutable catalogue migrations additively to `dsn`. Never resets."""
    verify_migrations_verbatim()
    run = runner or _default_supabase_runner
    args = ["supabase", "migration", "up", "--db-url", dsn]
    assert_not_reset(args)
    await run(args)
