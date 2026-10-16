"""F26 Ambiguity handling — code thresholds decide clarification; unavailable choice 409."""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.search_client import Candidate, PartSearchResult
from app.specialists.parts import run_parts, validate_selection
from app.tools import ToolSession
from partsiq_common.contracts import ItemInput, ItemState, ToolContext
from partsiq_common.errors import PartsIQError

CATALOGUE = uuid4()


def _item():
    return ItemState(
        id=uuid4(),
        request=ItemInput(description="fuel filter", source_message_id=uuid4(), source_start=0, source_end=11),
        configuration_id=1, candidate_part_ids=[], selected_part_id=None, status="unresolved",
    )


class FakeClient:
    def __init__(self, result):
        self.result = result

    async def search_parts(self, configuration_id, query, limit=None):
        return self.result

    async def identify(self, query, serial):  # pragma: no cover
        raise AssertionError


def _session(result):
    ctx = ToolContext(enquiry_id=uuid4(), revision=1, catalogue_version_id=CATALOGUE, item_id=uuid4(), max_calls=4)
    return ToolSession(FakeClient(result), ctx, CATALOGUE)


class AmbiguityHandling(unittest.IsolatedAsyncioTestCase):
    async def test_fuel_filter_vs_separator_prompts_distinction(self):
        result = PartSearchResult(1, [Candidate(10, 0.62), Candidate(11, 0.60)], top_score=0.62, margin=0.02)
        proposal = await run_parts(_item(), _ctx_passthrough(result), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")

    async def test_llm_cannot_override_low_confidence(self):
        result = PartSearchResult(1, [Candidate(10, 0.25)], top_score=0.25, margin=0.25)
        proposal = await run_parts(_item(), _ctx_passthrough(result), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")

    def test_unavailable_candidate_choice_returns_409(self):
        with self.assertRaises(PartsIQError) as ctx:
            validate_selection([10, 11], 999)
        self.assertEqual(ctx.exception.http_status, 409)


def _ctx_passthrough(_result):
    return ToolContext(enquiry_id=uuid4(), revision=1, catalogue_version_id=CATALOGUE, item_id=uuid4(), max_calls=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
