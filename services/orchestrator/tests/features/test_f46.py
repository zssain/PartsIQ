"""F46 Verification gate — named deterministic rules decide pass/fail; never an LLM.

Checks item/configuration/candidate membership, provenance, catalogue version, selected
quantities and allocation bounds; computes the canonical fact hash; stores named rule
results. The five failure scenarios — unknown part, incompatible part, stale catalogue,
oversold plan, hidden extra item — each fail a specific named rule asserted here.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.verification import (
    canonical_facts_sha256,
    check_allocation,
    check_candidate_membership,
    check_catalogue_version,
    check_configuration_membership,
    run_verification,
    verify_current,
    verify_facts,
)
from partsiq_common.contracts import (
    Allocation,
    CandidateEvidence,
    StockEvidence,
    VerificationEvidence,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError

CV = uuid4()
EV = uuid4()
WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _citation(rev: int = 1, section: str = "FILTERS") -> str:
    return f"SYNTH-CA-PB-CA-110 rev {rev}, section {section}"


def _item(item_id, *, part_id=10, config=100, requested="2", allocations=((1, "2"),), shortage="0", source=None):
    return VerifiedItem(
        item_id=item_id, configuration_id=config, part_id=part_id, part_number="VP-FF-10",
        name_en="fuel filter", name_ar="فلتر وقود", requested_quantity=Decimal(requested),
        allocations=[
            Allocation(warehouse_id=wh, quantity=Decimal(q), transfer_days=2, stock_updated_at=WHEN)
            for wh, q in allocations
        ],
        shortage=Decimal(shortage), source_reference=source or _citation(), evidence_id=EV,
    )


def _facts(items, *, revision=1, catalogue=CV):
    return VerifiedFacts(enquiry_id=uuid4(), revision=revision, catalogue_version_id=catalogue, items=items)


def _candidate(item_id, *, part_id=10, config=100, source=None):
    return CandidateEvidence(
        item_id=item_id, part_id=part_id, configuration_id=config, evidence_id=EV,
        source_reference=source or _citation(),
    )


def _evidence(candidates, stock, *, revision=1, catalogue=CV):
    return VerificationEvidence(
        current_revision=revision, active_catalogue_version_id=catalogue, candidates=candidates, stock=stock,
    )


def _stock(part_id=10, warehouse_id=1, available="5"):
    return StockEvidence(part_id=part_id, warehouse_id=warehouse_id, available=Decimal(available), updated_at=WHEN)


class VerificationGate(unittest.TestCase):
    def test_success_passes_and_hashes_facts(self):
        i = uuid4()
        facts = _facts([_item(i)])
        result = verify_facts(facts, _evidence([_candidate(i)], [_stock()]))
        self.assertTrue(result.passed)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.facts_sha256, canonical_facts_sha256(facts))

    def test_unknown_part_fails_candidate_membership(self):
        i = uuid4()
        facts = _facts([_item(i, part_id=999)])
        evidence = _evidence([_candidate(i, part_id=10)], [_stock(part_id=999)])
        self.assertEqual([f.code for f in check_candidate_membership(facts, evidence)], ["INCOMPATIBLE"])
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_incompatible_part_fails_configuration_membership(self):
        i = uuid4()
        facts = _facts([_item(i, config=200)])
        evidence = _evidence([_candidate(i, config=100)], [_stock()])
        self.assertEqual([f.code for f in check_configuration_membership(facts, evidence)], ["INCOMPATIBLE"])

    def test_stale_catalogue_fails_version_rule(self):
        i = uuid4()
        facts = _facts([_item(i)], catalogue=uuid4())
        evidence = _evidence([_candidate(i)], [_stock()])
        self.assertEqual([f.code for f in check_catalogue_version(facts, evidence)], ["STALE_CATALOGUE"])

    def test_oversold_plan_fails_allocation(self):
        a, b = uuid4(), uuid4()
        facts = _facts([
            _item(a, requested="3", allocations=((1, "3"),)),
            _item(b, requested="3", allocations=((1, "3"),)),
        ])
        evidence = _evidence([_candidate(a), _candidate(b)], [_stock(available="5")])
        self.assertEqual([f.code for f in check_allocation(facts, evidence)], ["OVERALLOCATION"])

    def test_hidden_extra_item_fails_candidate_membership(self):
        i, ghost = uuid4(), uuid4()
        facts = _facts([_item(i), _item(ghost)])
        evidence = _evidence([_candidate(i)], [_stock()])
        failures = check_candidate_membership(facts, evidence)
        self.assertEqual([f.code for f in failures], ["UNRESOLVED_ITEM"])
        self.assertEqual(failures[0].item_id, ghost)

    def test_stale_revision_whole_gate_fails(self):  # stale-revision axis
        i = uuid4()
        facts = _facts([_item(i)], revision=1)
        evidence = _evidence([_candidate(i)], [_stock()], revision=2)
        result = verify_facts(facts, evidence)
        self.assertFalse(result.passed)
        self.assertIn("STALE_REVISION", [f.code for f in result.failures])


class FakeStore:
    def __init__(self, loaded):
        self._loaded = loaded
        self._rows = {}
        self.persist_calls = 0

    async def load_current(self, enquiry_id, revision):
        return self._loaded

    async def persist(self, enquiry_id, revision, result):
        self.persist_calls += 1
        key = (enquiry_id, revision)
        self._rows.setdefault(key, uuid4())
        return self._rows[key]


class VerifyCurrentPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_persists_one_result_for_current_draft(self):
        i = uuid4()
        facts = _facts([_item(i)])
        store = FakeStore((facts, _evidence([_candidate(i)], [_stock()])))
        _result, vid = await run_verification(facts.enquiry_id, facts.revision, store=store)
        self.assertIsInstance(vid, UUID)
        self.assertEqual(store.persist_calls, 1)

    async def test_missing_draft_is_not_found(self):  # invalid-input axis
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1, store=FakeStore(None))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_store_not_configured_is_dependency_unavailable(self):  # dependency-failure axis
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
