"""F30 Old part numbers — supersession resolves to a current part that has explicit
fitment; inherited-only compatibility is rejected (ADR-018)."""
from __future__ import annotations

import unittest

from app import schemas
from app.service import SearchService
from tests._fakes import CONFIG_ID, FakeRepository, full_compatibility


class OldPartNumbers(unittest.IsolatedAsyncioTestCase):
    async def test_successor_with_own_fitment_is_offered_with_old_number(self) -> None:
        service = SearchService(FakeRepository(compatibility=full_compatibility()), None, 0.4, 5)
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
        )
        new6 = next((c for c in response.candidates if c.part.part_number == "VP-NEW-6"), None)
        self.assertIsNotNone(new6)
        self.assertIn("VP-OLD-5", new6.superseded_from)

    async def test_successor_without_own_fitment_is_rejected(self) -> None:
        # Part 7 (compatible, superseded) -> part 8, but 8 has NO fitment row of its own.
        service = SearchService(FakeRepository(compatibility=full_compatibility()), None, 0.4, 5)
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="belt filter oil fuel")
        )
        numbers = {c.part.part_number for c in response.candidates}
        self.assertNotIn("VP-NEW-8", numbers)
        self.assertNotIn("VP-OLD-7", numbers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
