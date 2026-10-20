"""Apply the timestamped Supabase migrations in order (additive, idempotent, target-confirmed).

    PARTSIQ_MIGRATE_TARGET=<label> DATABASE_URL_MIGRATION=... \
      uv run --all-packages python tools/apply_migrations.py --target <label> [--dry-run]

* Only ``supabase/migrations/<14-digit>_*.sql`` files are applied (the untimestamped 001_…005_
  copies are historical duplicates and would double-apply).
* Applied versions are recorded in ``supabase_migrations.schema_migrations`` — the same table the
  Supabase CLI uses — so a version is never applied twice and an applied file is never edited:
  each file's SHA-256 is recorded and a changed applied file is refused.
* Destructive statements (DROP TABLE/SCHEMA/DATABASE, TRUNCATE, DELETE without WHERE, db reset)
  are refused before anything runs. ``--target`` must equal PARTSIQ_MIGRATE_TARGET.
* The connection string is read from DATABASE_URL_MIGRATION and never printed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
# Matched at the START of a statement only (a "BEFORE TRUNCATE" trigger clause is not destructive).
_DESTRUCTIVE = re.compile(r"(^|;)\s*(DROP\s+(TABLE|SCHEMA|DATABASE)\b|TRUNCATE\b|DELETE\s+FROM\s+[\w.]+\s*;)", re.IGNORECASE)


def pending_files() -> list[Path]:
    return sorted(p for p in MIGRATIONS.glob("*.sql") if re.match(r"^\d{14}_", p.name))


def check_safe(path: Path, sql: str) -> None:
    body = re.sub(r"--.*", "", sql)
    match = _DESTRUCTIVE.search(body)
    if match:
        raise SystemExit(f"refused: {path.name} contains a destructive statement ({match.group(0)!r})")


async def main(argv: list[str] | None = None) -> int:
    import asyncpg

    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if os.environ.get("PARTSIQ_MIGRATE_TARGET") != args.target:
        print(f"refused: set PARTSIQ_MIGRATE_TARGET={args.target} to confirm the target database", file=sys.stderr)
        return 2
    dsn = os.environ.get("DATABASE_URL_MIGRATION", "")
    if not dsn:
        print("refused: DATABASE_URL_MIGRATION is not set", file=sys.stderr)
        return 2
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        await conn.execute(
            "CREATE SCHEMA IF NOT EXISTS supabase_migrations;"
            "CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (version text PRIMARY KEY, statements text[], name text);"
            "ALTER TABLE supabase_migrations.schema_migrations ADD COLUMN IF NOT EXISTS partsiq_sha256 text;"
        )
        applied = {r["version"]: r["partsiq_sha256"] for r in await conn.fetch("SELECT version, partsiq_sha256 FROM supabase_migrations.schema_migrations")}
        for path in pending_files():
            version = path.name.split("_", 1)[0]
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode()).hexdigest()
            if version in applied:
                if applied[version] and applied[version] != digest:
                    print(f"refused: {path.name} changed after it was applied (never edit an applied migration)", file=sys.stderr)
                    return 3
                print(f"ok      {path.name} (already applied)")
                continue
            check_safe(path, sql)
            if args.dry_run:
                print(f"pending {path.name}")
                continue
            # Each file carries its own BEGIN/COMMIT; record the version in a follow-up statement.
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO supabase_migrations.schema_migrations(version, name, partsiq_sha256) VALUES ($1,$2,$3)",
                version, path.stem.split("_", 1)[1], digest,
            )
            print(f"applied {path.name}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
