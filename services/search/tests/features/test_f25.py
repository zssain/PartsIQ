"""F25 Ranked candidates — margin computed before the response limit; NaN rejected."""
from __future__ import annotations

import unittest

from app import schemas
from app.service import InvalidRequestError, SearchService
from tests._fakes import CONFIG_ID, NAN, FakeProvider, FakeRepository, full_compatibility


class RankedCandidates(unittest.IsolatedAsyncioTestCase):
    async def test_limit_one_still_reports_runner_up_margin(self) -> None:
        service = SearchService(FakeRepository(compatibility=full_compatibility()), None, 0.4, 5)
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="fuel filter", limit=1)
        )
        # Only one candidate returned, but the margin reflects the close runner-up,
        # computed over the full ranked set before truncation.
        self.assertEqual(len(response.candidates), 1)
        self.assertGreater(response.confidence.top_score, 0.0)
        self.assertLess(response.confidence.margin, response.confidence.top_score)

    async def test_nan_score_is_rejected(self) -> None:
        repo = FakeRepository(compatibility=full_compatibility(), semantic={2: NAN})
        service = SearchService(repo, FakeProvider(), 0.4, 5)
        with self.assertRaises(InvalidRequestError):
            await service.search_parts(
                schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="fuel filter")
            )

    async def test_empty_result_has_zero_confidence(self) -> None:
        service = SearchService(FakeRepository(compatibility=full_compatibility()), None, 0.4, 5)
        response = await service.search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="zzzzz")
        )
        self.assertEqual(response.candidates, [])
        self.assertEqual(response.confidence.top_score, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
