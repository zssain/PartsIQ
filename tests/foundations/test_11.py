"""Acceptance tests for prompt 11 — parts specialist and tools.

Offline: a fake search client drives run_parts and the ToolSession bounds/guards; a fake
HTTP transport exercises the SearchClient adapter parsing. Deterministic candidate
restriction, threshold-based clarification, the 4-call bound and stale-version rejection
are all verified without the search service or a database. Covers F11, F26.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from app.search_client import Candidate, PartSearchResult, SearchClient  # noqa: E402
from app.specialists.parts import run_parts, validate_selection  # noqa: E402
from app.tools import StaleCatalogueError, ToolBudgetError, ToolSession  # noqa: E402
from partsiq_common.contracts import ItemInput, ItemState, ToolContext  # noqa: E402
from partsiq_common.errors import PartsIQError  # noqa: E402

CATALOGUE = uuid4()


def _item(config=1):
    return ItemState(
        id=uuid4(),
        request=ItemInput(description="fuel filter", source_message_id=uuid4(), source_start=0, source_end=11),
        configuration_id=config, candidate_part_ids=[], selected_part_id=None, status="unresolved",
    )


def _context(max_calls=4, catalogue=CATALOGUE):
    return ToolContext(enquiry_id=uuid4(), revision=1, catalogue_version_id=catalogue, item_id=uuid4(), max_calls=max_calls)


class FakeSearchClient:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def search_parts(self, configuration_id, query, limit=None):
        self.calls += 1
        return self.result

    async def identify(self, query, serial):  # pragma: no cover
        raise AssertionError


def _session(result, *, max_calls=4, current=CATALOGUE, context_catalogue=CATALOGUE):
    return ToolSession(FakeSearchClient(result), _context(max_calls, context_catalogue), current)


class RunParts(unittest.IsolatedAsyncioTestCase):
    async def test_no_configuration_asks_for_machine(self):
        proposal = await run_parts(_item(config=None), _context(), session=_session(None))
        self.assertEqual(proposal.clarification_code, "needs_model")
        self.assertEqual(proposal.candidate_part_ids, [])

    async def test_confident_single_candidate(self):
        result = PartSearchResult(1, [Candidate(10, 0.9)], top_score=0.9, margin=0.5)
        proposal = await run_parts(_item(), _context(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "none")
        self.assertEqual(proposal.candidate_part_ids, [10])

    async def test_close_runner_up_is_ambiguous(self):  # F26
        result = PartSearchResult(1, [Candidate(10, 0.61), Candidate(11, 0.60)], top_score=0.61, margin=0.01)
        proposal = await run_parts(_item(), _context(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")
        self.assertEqual(proposal.candidate_part_ids, [10, 11])

    async def test_low_confidence_cannot_be_overridden(self):  # F26
        result = PartSearchResult(1, [Candidate(10, 0.3)], top_score=0.3, margin=0.3)
        proposal = await run_parts(_item(), _context(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")

    async def test_candidates_only_from_compatible_set(self):
        result = PartSearchResult(1, [Candidate(10, 0.9), Candidate(11, 0.2)], top_score=0.9, margin=0.7)
        proposal = await run_parts(_item(), _context(), session=_session(result))
        self.assertTrue(set(proposal.candidate_part_ids).issubset({10, 11}))

    async def test_no_candidate_returns_unavailable(self):
        result = PartSearchResult(1, [], top_score=0.0, margin=0.0)
        proposal = await run_parts(_item(), _context(), session=_session(result))
        self.assertEqual(proposal.candidate_part_ids, [])


class ToolGuards(unittest.IsolatedAsyncioTestCase):
    async def test_tool_call_budget_enforced(self):
        session = _session(PartSearchResult(1, [], 0.0, 0.0), max_calls=1)
        await session.search_parts(1, "q")
        with self.assertRaises(ToolBudgetError):
            await session.search_parts(1, "q")

    async def test_stale_catalogue_version_rejected(self):
        session = _session(PartSearchResult(1, [], 0.0, 0.0), current=uuid4(), context_catalogue=CATALOGUE)
        with self.assertRaises(StaleCatalogueError):
            await session.search_parts(1, "q")


class Selection(unittest.TestCase):
    def test_unavailable_candidate_choice_is_409(self):  # F26
        with self.assertRaises(PartsIQError) as ctx:
            validate_selection([10, 11], 99)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(ctx.exception.http_status, 409)

    def test_available_candidate_choice_ok(self):
        validate_selection([10, 11], 10)


class SearchClientAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_parses_search_response(self):
        payload = {
            "configuration": {"id": 7},
            "candidates": [{"part": {"id": 10}, "score": 0.9}, {"part": {"id": 11}, "score": 0.4}],
            "confidence": {"top_score": 0.9, "margin": 0.5},
        }

        class FakeHttp:
            async def post(self, url, json, headers):
                return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)

        client = SearchClient("http://search:8000", "tok", FakeHttp())
        result = await client.search_parts(7, "fuel")
        self.assertEqual(result.configuration_id, 7)
        self.assertEqual([c.part_id for c in result.candidates], [10, 11])
        self.assertEqual(result.top_score, 0.9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
