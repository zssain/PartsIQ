"""Acceptance tests for prompt 02 — catalogue migration.

Deterministic + offline: the two migrations are byte-for-byte copies of spec/sql, the
critical legacy constraints are present in the SQL, and apply_catalogue_schema applies
additively and REFUSES a reset. Actually running the schema needs a disposable local
Supabase/Postgres and is reported BLOCKED here (no database in this environment).

Covers the structural guarantees behind F20, F22, F28, F30, F33/F34.
"""
from __future__ import annotations

import asyncio
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools import apply_catalogue_schema as acs  # noqa: E402

MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
CATALOGUE_SQL = (MIGRATIONS / "20261011000100_legacy_catalogue.sql").read_text(encoding="utf-8")
SEARCH_SQL = (MIGRATIONS / "20261011000200_legacy_search.sql").read_text(encoding="utf-8")


class MigrationsAreVerbatim(unittest.TestCase):
    def test_copies_match_spec_byte_for_byte(self) -> None:
        acs.verify_migrations_verbatim()  # raises on any mismatch

    def test_config_toml_is_valid_and_local(self) -> None:
        config = tomllib.loads((REPO_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["db"]["major_version"], 16)
        self.assertTrue(config["auth"]["enable_anonymous_sign_ins"])


class CriticalConstraintsPreserved(unittest.TestCase):
    def test_serial_range_exclusion_for_unambiguous_lookup(self) -> None:  # F20
        self.assertIn("EXCLUDE USING gist", CATALOGUE_SQL)
        self.assertIn("int8range(serial_start, serial_end, '[]') WITH &&", CATALOGUE_SQL)

    def test_compatibility_relation_exists(self) -> None:  # F22
        self.assertIn("CREATE TABLE part_compatibility", CATALOGUE_SQL)

    def test_supersession_cycle_protection(self) -> None:  # F30
        self.assertIn("CREATE TABLE part_supersessions", CATALOGUE_SQL)
        self.assertIn("WITH RECURSIVE", CATALOGUE_SQL)

    def test_numeric_keys_preserved(self) -> None:
        self.assertIn("SERIAL PRIMARY KEY", CATALOGUE_SQL)

    def test_part_number_normalization_and_transfer_days(self) -> None:  # F23/F30, F34
        self.assertIn("part_number_key", SEARCH_SQL)
        self.assertIn("warehouse_transfer_routes", SEARCH_SQL)
        self.assertIn("transfer_days", SEARCH_SQL)


class ApplyRefusesReset(unittest.TestCase):
    def test_assert_not_reset_blocks_destructive_commands(self) -> None:
        with self.assertRaises(RuntimeError):
            acs.assert_not_reset(["supabase", "db", "reset"])

    def test_apply_uses_migration_up_and_never_resets(self) -> None:
        captured: list[list[str]] = []

        async def fake_runner(args: list[str]) -> None:
            acs.assert_not_reset(args)
            captured.append(args)

        asyncio.run(acs.apply_catalogue_schema("postgresql://u:p@127.0.0.1:54322/postgres", runner=fake_runner))
        self.assertEqual(len(captured), 1)
        self.assertIn("up", captured[0])
        self.assertNotIn("reset", " ".join(captured[0]))
        self.assertIn("postgresql://u:p@127.0.0.1:54322/postgres", captured[0])


class LiveApplicationBlocked(unittest.TestCase):
    @unittest.skip("requires a disposable local Supabase/Postgres; not available in this environment")
    def test_schema_applies_to_disposable_db(self) -> None:  # pragma: no cover
        raise AssertionError("integration-only; run against local Supabase")


if __name__ == "__main__":
    unittest.main(verbosity=2)
