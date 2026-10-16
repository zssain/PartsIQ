"""Acceptance tests for prompt 06 — extend legacy search (foundation gate).

Offline: the SearchService runs against an in-memory fake repository, so the prompt-06
corrections (margin before truncation, supersession terminal-fitment, NaN rejection),
the internal-token route guard, readiness separation and embed_version validation are
all exercised without a database or BGE-M3. Live asyncpg/pgvector/BGE-M3 behaviour is
integration-only and reported BLOCKED.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH = REPO_ROOT / "services" / "search"
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(SEARCH))

from fastapi import HTTPException  # noqa: E402

from app import schemas  # noqa: E402
from app.embedding_ingestion import embed_version  # noqa: E402
from app.routes import require_internal_token  # noqa: E402
from app.service import InvalidRequestError, SearchService  # noqa: E402
from partsiq_common.embeddings import EMBEDDING_DIMENSION, validate_embedding  # noqa: E402


def _load_fakes():
    spec = importlib.util.spec_from_file_location("search_fakes", SEARCH / "tests" / "_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


FAKES = _load_fakes()


class _Req:
    def __init__(self, token):
        self.app = type("A", (), {"state": type("S", (), {"settings": type("C", (), {"internal_service_token": token})()})()})()


class InternalTokenGuard(unittest.IsolatedAsyncioTestCase):
    async def test_missing_token_when_configured_is_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await require_internal_token(_Req("secret"), x_internal_token=None)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_wrong_token_is_403(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await require_internal_token(_Req("secret"), x_internal_token="nope")
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_correct_token_passes(self) -> None:
        self.assertIsNone(await require_internal_token(_Req("secret"), x_internal_token="secret"))

    async def test_unconfigured_token_is_allowed_for_local_dev(self) -> None:
        self.assertIsNone(await require_internal_token(_Req(None), x_internal_token=None))


class SearchCorrections(unittest.IsolatedAsyncioTestCase):
    def _service(self, **kw):
        return SearchService(FAKES.FakeRepository(compatibility=FAKES.full_compatibility(), **kw), None, 0.4, 5)

    async def test_margin_computed_before_limit(self) -> None:
        response = await self._service().search_parts(
            schemas.PartSearchRequest(configuration_id=FAKES.CONFIG_ID, query="fuel filter", limit=1)
        )
        self.assertEqual(len(response.candidates), 1)
        self.assertLess(response.confidence.margin, response.confidence.top_score)

    async def test_supersession_requires_terminal_fitment(self) -> None:
        response = await self._service().search_parts(
            schemas.PartSearchRequest(configuration_id=FAKES.CONFIG_ID, query="oil filter")
        )
        numbers = {c.part.part_number for c in response.candidates}
        self.assertIn("VP-NEW-6", numbers)      # successor with its own fitment is offered
        self.assertNotIn("VP-NEW-8", numbers)   # inherited-only successor is rejected

    async def test_nan_rejected(self) -> None:
        service = SearchService(
            FAKES.FakeRepository(compatibility=FAKES.full_compatibility(), semantic={2: FAKES.NAN}),
            FAKES.FakeProvider(), 0.4, 5,
        )
        with self.assertRaises(InvalidRequestError):
            await service.search_parts(schemas.PartSearchRequest(configuration_id=FAKES.CONFIG_ID, query="fuel"))

    async def test_readiness_separates_lexical_from_semantic(self) -> None:
        lexical_only = self._service().readiness()
        self.assertTrue(lexical_only["lexical"])
        self.assertFalse(lexical_only["semantic_capable"])
        with_provider = SearchService(
            FAKES.FakeRepository(compatibility=FAKES.full_compatibility()), FAKES.FakeProvider(), 0.4, 5
        ).readiness()
        self.assertTrue(with_provider["semantic_capable"])


class EmbedVersion(unittest.IsolatedAsyncioTestCase):
    async def test_validates_and_hashes(self) -> None:
        class Store:
            def __init__(self):
                self.upserts = []

            async def fetch_embedding_sources(self, version_id):
                return [(1, "oil filter"), (2, "fuel filter")]

            async def upsert_embedding(self, part_id, model_name, source_text, vector_literal, model_revision, source_hash):
                self.upserts.append(source_hash)

        store = Store()
        receipt = await embed_version(uuid4(), provider=FAKES.FakeProvider(), store=store, model_revision="rev")
        self.assertEqual(receipt.embedded_count, 2)
        self.assertTrue(all(len(h) == 64 for h in store.upserts))

    def test_validate_embedding_dimension(self) -> None:
        with self.assertRaises(ValueError):
            validate_embedding([1.0] * (EMBEDDING_DIMENSION - 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
