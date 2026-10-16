"""F22 Compatibility gate — only fitment members rank; provenance always carried."""
from __future__ import annotations

import unittest

from app import schemas
from app.service import SearchService
from tests._fakes import CONFIG_ID, FakeRepository, full_compatibility


def _service(compatibility):
    return SearchService(FakeRepository(compatibility=compatibility), None, 0.4, 5)


class CompatibilityGate(unittest.IsolatedAsyncioTestCase):
    async def test_perfect_lexical_match_outside_fitment_is_absent(self) -> None:
        service = _service(full_compatibility())
        # "hydraulic filter" is the exact name of part VP-HF-4, which is NOT compatible.
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="hydraulic filter")
        )
        numbers = {c.part.part_number for c in response.candidates}
        self.assertNotIn("VP-HF-4", numbers)

    async def test_empty_fitment_returns_no_candidates(self) -> None:
        service = _service([])
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
        )
        self.assertEqual(response.candidates, [])
        self.assertEqual(response.confidence.top_score, 0.0)

    async def test_every_candidate_carries_source_reference(self) -> None:
        service = _service(full_compatibility())
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
        )
        self.assertTrue(response.candidates)
        self.assertTrue(all(c.source_reference for c in response.candidates))


if __name__ == "__main__":
    unittest.main(verbosity=2)
