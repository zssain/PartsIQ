"""F24 Semantic retrieval — 1024-d unit vectors enforced; lexical fallback; ingestion."""
from __future__ import annotations

import unittest
from uuid import uuid4

from partsiq_common.embeddings import EMBEDDING_DIMENSION, validate_embedding

from app import schemas
from app.embedding_ingestion import embed_version
from app.service import SearchService
from tests._fakes import CONFIG_ID, FakeProvider, FakeRepository, full_compatibility


class VectorValidation(unittest.TestCase):
    def test_unit_vector_of_correct_dimension_passes(self) -> None:
        vector = [0.0] * EMBEDDING_DIMENSION
        vector[0] = 1.0
        validate_embedding(vector)

    def test_wrong_dimension_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_embedding([1.0, 0.0])

    def test_nan_rejected(self) -> None:
        bad = [0.0] * EMBEDDING_DIMENSION
        bad[0] = float("nan")
        with self.assertRaises(ValueError):
            validate_embedding(bad)

    def test_non_unit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_embedding([0.5] * EMBEDDING_DIMENSION)


class SemanticFallback(unittest.IsolatedAsyncioTestCase):
    async def test_no_provider_means_semantic_disabled(self) -> None:
        service = SearchService(FakeRepository(compatibility=full_compatibility()), None, 0.4, 5)
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
        )
        self.assertFalse(response.semantic_search_enabled)
        self.assertTrue(response.candidates)  # lexical still returns candidates


class Ingestion(unittest.IsolatedAsyncioTestCase):
    async def test_embed_version_upserts_with_source_hash(self) -> None:
        class FakeStore:
            def __init__(self):
                self.upserts = []

            async def fetch_embedding_sources(self, version_id):
                return [(1, "oil filter | فلتر"), (2, "fuel filter | وقود")]

            async def upsert_embedding(self, part_id, model_name, source_text, vector_literal, model_revision, source_hash):
                self.upserts.append((part_id, source_hash, model_revision))

        store = FakeStore()
        receipt = await embed_version(uuid4(), provider=FakeProvider(), store=store, model_revision="rev-abc")
        self.assertEqual(receipt.embedded_count, 2)
        self.assertEqual(len(store.upserts), 2)
        self.assertTrue(all(len(h) == 64 for _, h, _ in store.upserts))
        self.assertTrue(all(rev == "rev-abc" for _, _, rev in store.upserts))

    async def test_embed_version_rejects_wrong_dimension(self) -> None:
        class FakeStore:
            async def fetch_embedding_sources(self, version_id):
                return [(1, "text")]

            async def upsert_embedding(self, *a, **k):
                raise AssertionError("must not upsert an invalid vector")

        with self.assertRaises(ValueError):
            await embed_version(uuid4(), provider=FakeProvider(dimension=512), store=FakeStore(), model_revision="r")


if __name__ == "__main__":
    unittest.main(verbosity=2)
