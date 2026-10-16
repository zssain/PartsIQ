"""F11 Clarifying questions — reason codes are code-decided, never LLM-authored.

run_parts chooses the clarification code from tested score/margin thresholds and the
identification state; a low-confidence or ambiguous result cannot be overridden into a
confident answer, and an unidentified machine asks for the model rather than guessing.
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.search_client import Candidate, PartSearchResult
from app.specialists.parts import run_parts
from app.tools import ToolSession
from partsiq_common.contracts import ItemInput, ItemState, ToolContext

CATALOGUE = uuid4()


def _item(config=1):
    return ItemState(
        id=uuid4(),
        request=ItemInput(description="fuel filter", source_message_id=uuid4(), source_start=0, source_end=11),
        configuration_id=config, candidate_part_ids=[], selected_part_id=None, status="unresolved",
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


class ClarifyingQuestions(unittest.IsolatedAsyncioTestCase):
    async def test_unidentified_machine_asks_for_model(self):
        proposal = await run_parts(_item(config=None), _ctx(), session=_session(PartSearchResult(1, [], 0.0, 0.0)))
        self.assertEqual(proposal.clarification_code, "needs_model")

    async def test_ambiguous_close_runner_up(self):
        result = PartSearchResult(1, [Candidate(10, 0.62), Candidate(11, 0.60)], top_score=0.62, margin=0.02)
        proposal = await run_parts(_item(), _ctx(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")

    async def test_low_confidence_cannot_be_overridden(self):
        result = PartSearchResult(1, [Candidate(10, 0.2)], top_score=0.2, margin=0.2)
        proposal = await run_parts(_item(), _ctx(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "ambiguous_part")

    async def test_confident_single_candidate_needs_no_question(self):
        result = PartSearchResult(1, [Candidate(10, 0.95)], top_score=0.95, margin=0.9)
        proposal = await run_parts(_item(), _ctx(), session=_session(result))
        self.assertEqual(proposal.clarification_code, "none")


def _ctx():
    return ToolContext(enquiry_id=uuid4(), revision=1, catalogue_version_id=CATALOGUE, item_id=uuid4(), max_calls=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
