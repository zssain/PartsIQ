"""Acceptance tests for prompt 03 — workflow schema and database permissions.

Deterministic + offline: verbatim migrations, restricted role model, per-item/revision
candidate keys, the no-invented-identity backfill, the single-publication backstop,
transaction-local actor context, and the checkpoint setup order (autocommit library DDL
then permissions). Two actors on a reused pool and live RLS enforcement require a
disposable Postgres and run under tests/integration (skipped without a DB).

Covers F04 (demo isolation), F12 (conversation memory), F49 (audit trail).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from tools import checkpoints_setup as cps  # noqa: E402
from tools import schema_receipt as sr  # noqa: E402

MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
APP_SQL = (MIGRATIONS / "20261011000300_application.sql").read_text(encoding="utf-8")
RLS_SQL = (MIGRATIONS / "20261011000400_rls.sql").read_text(encoding="utf-8")
SPEC = REPO_ROOT / "spec" / "sql"


class MigrationsVerbatim(unittest.TestCase):
    def test_application_and_rls_match_spec(self) -> None:
        self.assertEqual(APP_SQL, (SPEC / "003_application.sql").read_text(encoding="utf-8"))
        self.assertEqual(RLS_SQL, (SPEC / "004_rls.sql").read_text(encoding="utf-8"))


class RestrictedRoleModel(unittest.TestCase):
    def test_five_nologin_group_roles(self) -> None:  # F04/F49
        for role in ("partsiq_gateway", "partsiq_search", "partsiq_orchestrator", "partsiq_worker", "partsiq_catalogue"):
            self.assertIn(f"CREATE ROLE {role} NOLOGIN", RLS_SQL)

    def test_untrusted_browser_roles_have_no_table_grants(self) -> None:
        # anon/authenticated have privileges revoked on application tables.
        self.assertIn("REVOKE ALL ON equipment_families FROM anon,authenticated", RLS_SQL)

    def test_rls_enabled_and_policies_present(self) -> None:
        self.assertGreaterEqual(RLS_SQL.count("ENABLE ROW LEVEL SECURITY"), 40)
        self.assertGreaterEqual(RLS_SQL.count("CREATE POLICY"), 100)

    def test_actor_context_is_transaction_local_current_setting(self) -> None:  # rule 11
        self.assertIn("current_setting('app.actor_id',true)", RLS_SQL)


class CandidateKeyMigration(unittest.TestCase):
    def test_per_item_per_revision_keys(self) -> None:
        self.assertIn("ADD PRIMARY KEY(item_id,revision,rank)", APP_SQL)
        self.assertIn("ADD UNIQUE(item_id,revision,part_id)", APP_SQL)

    def test_no_invented_customer_identity_backfill(self) -> None:
        # Historical rows get a legacy item from EXISTING enquiries; no fabricated owner.
        self.assertIn("Historical", APP_SQL)
        self.assertIn("FROM enquiries", APP_SQL)
        self.assertNotIn("INSERT INTO auth.users", APP_SQL)

    def test_single_recommendation_publication_backstop(self) -> None:  # F47 backstop
        self.assertIn("messages_one_publication_idx", APP_SQL)
        self.assertIn("kind='recommendation'", APP_SQL)


class CheckpointSetupOrder(unittest.IsolatedAsyncioTestCase):
    async def test_library_ddl_autocommit_then_permissions_tx(self) -> None:
        auto: list[str] = []
        tx: list[str] = []

        async def autocommit_exec(stmt: str) -> None:
            auto.append(stmt)

        async def tx_exec(script: str) -> None:
            tx.append(script)

        await cps.setup_checkpoints(
            "postgresql://u:p@127.0.0.1:54322/postgres",
            autocommit_exec=autocommit_exec,
            tx_exec=tx_exec,
        )
        # CONCURRENTLY index creation must be in the autocommit path, never in a tx.
        self.assertTrue(any("CONCURRENTLY" in s for s in auto))
        self.assertFalse(any("CONCURRENTLY" in s for s in tx))
        # permissions applied once; grants the orchestrator role DML but not DDL.
        self.assertEqual(len(tx), 1)
        self.assertIn("partsiq_orchestrator", tx[0])

    async def test_refuses_reset(self) -> None:
        with self.assertRaises(RuntimeError):
            await cps.setup_checkpoints("db reset --linked", autocommit_exec=_noop, tx_exec=_noop)


class SchemaReceiptShape(unittest.IsolatedAsyncioTestCase):
    async def test_receipt_groups_catalog_rows(self) -> None:
        canned = {
            sr._Q_VERSION: [("16.4",)],
            sr._Q_EXTENSIONS: [("vector", "0.7.0"), ("pg_trgm", "1.6")],
            sr._Q_COLUMNS: [("parts", "id"), ("parts", "part_number"), ("enquiries", "id")],
            sr._Q_INDEXES: [("parts", "parts_pkey")],
            sr._Q_POLICIES: [("enquiries", "enquiries_gateway")],
        }

        async def fetch(query: str):
            return canned[query]

        receipt = await sr.collect_schema_receipt("postgresql://x", fetch=fetch)
        self.assertEqual(receipt.postgres_version, "16.4")
        self.assertEqual(receipt.extensions["vector"], "0.7.0")
        self.assertEqual(receipt.columns["parts"], ["id", "part_number"])
        self.assertEqual(receipt.policies["enquiries"], ["enquiries_gateway"])


class TwoActorReusedPoolBlocked(unittest.TestCase):
    @unittest.skip("requires disposable Postgres; runs under tests/integration with a live DB")
    def test_two_actors_do_not_leak_context(self) -> None:  # pragma: no cover
        raise AssertionError("integration-only")


async def _noop(_: str) -> None:
    return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
