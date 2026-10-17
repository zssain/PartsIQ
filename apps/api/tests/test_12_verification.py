"""Foundation 12 acceptance: deterministic verification gate and canonical fact hashing.

Fully offline and deterministic. No LLM is used in the pass/fail path — the seven named
pure checks decide the result in ordinary Python. The live verification_results store is
BLOCKED (it is a live Postgres adapter owned by the orchestrator); an in-memory store that
mirrors the UNIQUE(enquiry_id, revision) constraint stands in for it, and the live-DB path
is SKIPPED rather than faked.

Ports the checks + coverage from services/orchestrator/app/verification.py and its tests
(tests/features/test_f46.py, test_f12.py) plus the F28 citation resolution characterized in
services/search/tests/features/test_f28.py.
"""
from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from partsiq.core.contracts import (
    Allocation,
    CandidateEvidence,
    StockEvidence,
    VerificationEvidence,
    VerificationResult,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.facts import facts_sha256, resolve_source_reference
from partsiq.enquiries.verification import (
    check_allocation,
    check_candidate_membership,
    check_catalogue_version,
    check_configuration_membership,
    check_current_revision,
    check_quantity,
    check_source_evidence,
    run_verification,
    verify_current,
    verify_facts,
)

CV = uuid4()
EV = uuid4()
WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _citation(rev: int = 1, section: str = "FILTERS") -> str:
    return f"SYNTH-CA-PB-CA-110 rev {rev}, section {section}"


def _item(
    item_id,
    *,
    part_id=10,
    config=100,
    requested="2",
    allocations=((1, "2"),),
    shortage="0",
    source=None,
    evidence_id=EV,
):
    return VerifiedItem(
        item_id=item_id,
        configuration_id=config,
        part_id=part_id,
        part_number="VP-FF-10",
        name_en="fuel filter",
        name_ar="فلتر وقود",
        requested_quantity=Decimal(requested),
        allocations=[
            Allocation(
                warehouse_id=wh, quantity=Decimal(q), transfer_days=2, stock_updated_at=WHEN
            )
            for wh, q in allocations
        ],
        shortage=Decimal(shortage),
        source_reference=source if source is not None else _citation(),
        evidence_id=evidence_id,
    )


def _facts(items, *, revision=1, catalogue=CV):
    return VerifiedFacts(
        enquiry_id=uuid4(), revision=revision, catalogue_version_id=catalogue, items=items
    )


def _candidate(item_id, *, part_id=10, config=100, source=None, evidence_id=EV):
    return CandidateEvidence(
        item_id=item_id,
        part_id=part_id,
        configuration_id=config,
        evidence_id=evidence_id,
        source_reference=source if source is not None else _citation(),
    )


def _evidence(candidates, stock, *, revision=1, catalogue=CV):
    return VerificationEvidence(
        current_revision=revision,
        active_catalogue_version_id=catalogue,
        candidates=candidates,
        stock=stock,
    )


def _stock(part_id=10, warehouse_id=1, available="5"):
    return StockEvidence(
        part_id=part_id, warehouse_id=warehouse_id, available=Decimal(available), updated_at=WHEN
    )


class CleanPlanPasses(unittest.TestCase):
    def test_success_passes_and_hashes_facts(self):
        i = uuid4()
        facts = _facts([_item(i)])
        result = verify_facts(facts, _evidence([_candidate(i)], [_stock()]))
        self.assertTrue(result.passed)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.facts_sha256, facts_sha256(facts))

    def test_multi_item_complete_and_short_plan_passes(self):
        # Two items; the second has a legitimate, explicit shortage. A correctly stated
        # short plan passes — only an inconsistent shortage is rejected (see quantity axis).
        a, b = uuid4(), uuid4()
        facts = _facts([
            _item(a, requested="2", allocations=((1, "2"),), shortage="0"),
            _item(b, part_id=20, requested="5", allocations=((1, "3"),), shortage="2"),
        ])
        evidence = _evidence(
            [_candidate(a), _candidate(b, part_id=20)],
            [_stock(part_id=10, available="5"), _stock(part_id=20, available="3")],
        )
        self.assertTrue(verify_facts(facts, evidence).passed)


class FailureCodeMappings(unittest.TestCase):
    def test_unknown_part_maps_incompatible_candidate_membership(self):
        i = uuid4()
        facts = _facts([_item(i, part_id=999)])
        evidence = _evidence([_candidate(i, part_id=10)], [_stock(part_id=999)])
        self.assertEqual(
            [f.code for f in check_candidate_membership(facts, evidence)], ["INCOMPATIBLE"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_hidden_extra_item_maps_unresolved_item(self):
        i, ghost = uuid4(), uuid4()
        facts = _facts([_item(i), _item(ghost)])
        evidence = _evidence([_candidate(i)], [_stock()])
        failures = check_candidate_membership(facts, evidence)
        self.assertEqual([f.code for f in failures], ["UNRESOLVED_ITEM"])
        self.assertEqual(failures[0].item_id, ghost)
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_incompatible_configuration_maps_incompatible(self):
        i = uuid4()
        facts = _facts([_item(i, config=200)])
        evidence = _evidence([_candidate(i, config=100)], [_stock()])
        self.assertEqual(
            [f.code for f in check_configuration_membership(facts, evidence)],
            ["INCOMPATIBLE"],
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_stale_catalogue_maps_stale_catalogue(self):
        i = uuid4()
        facts = _facts([_item(i)], catalogue=uuid4())
        evidence = _evidence([_candidate(i)], [_stock()])
        self.assertEqual(
            [f.code for f in check_catalogue_version(facts, evidence)], ["STALE_CATALOGUE"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_stale_revision_maps_stale_revision(self):
        i = uuid4()
        facts = _facts([_item(i)], revision=1)
        evidence = _evidence([_candidate(i)], [_stock()], revision=2)
        self.assertEqual(
            [f.code for f in check_current_revision(facts, evidence)], ["STALE_REVISION"]
        )
        result = verify_facts(facts, evidence)
        self.assertFalse(result.passed)
        self.assertIn("STALE_REVISION", [f.code for f in result.failures])

    def test_oversold_aggregate_across_items_maps_overallocation(self):
        # Neither item alone exceeds stock (3 <= 5), but the aggregate for the shared
        # (part, warehouse) is 6 > 5 — only recomputing across items catches it.
        a, b = uuid4(), uuid4()
        facts = _facts([
            _item(a, requested="3", allocations=((1, "3"),), shortage="0"),
            _item(b, requested="3", allocations=((1, "3"),), shortage="0"),
        ])
        evidence = _evidence([_candidate(a), _candidate(b)], [_stock(available="5")])
        self.assertEqual(
            [f.code for f in check_allocation(facts, evidence)], ["OVERALLOCATION"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_missing_stock_evidence_maps_stale_stock(self):
        i = uuid4()
        facts = _facts([_item(i)])
        # No stock row for (part 10, warehouse 1) -> cannot back the allocation.
        evidence = _evidence([_candidate(i)], [_stock(part_id=10, warehouse_id=2)])
        self.assertEqual(
            [f.code for f in check_allocation(facts, evidence)], ["STALE_STOCK"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_non_positive_quantity_maps_invalid_quantity(self):
        # requested_quantity has a gt=0 contract bound, so we exercise the check directly
        # against a model-constructed object whose validators we bypass with construct.
        i = uuid4()
        item = _item(i)
        bad = item.model_construct(**{**item.__dict__, "requested_quantity": Decimal("0")})
        facts = VerifiedFacts.model_construct(
            enquiry_id=uuid4(), revision=1, catalogue_version_id=CV, items=[bad]
        )
        evidence = _evidence([_candidate(i)], [_stock()])
        self.assertEqual([f.code for f in check_quantity(facts, evidence)], ["INVALID_QUANTITY"])

    def test_inconsistent_shortage_maps_invalid_quantity(self):
        # Allocated 2, requested 2 -> true shortage 0, but the plan claims shortage 1.
        i = uuid4()
        facts = _facts([_item(i, requested="2", allocations=((1, "2"),), shortage="1")])
        evidence = _evidence([_candidate(i)], [_stock()])
        self.assertEqual([f.code for f in check_quantity(facts, evidence)], ["INVALID_QUANTITY"])
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_absent_shortage_for_short_plan_maps_invalid_quantity(self):
        # Allocated 1 of requested 3 -> true shortage 2, but the plan hides it as 0.
        i = uuid4()
        facts = _facts([_item(i, requested="3", allocations=((1, "1"),), shortage="0")])
        evidence = _evidence([_candidate(i)], [_stock()])
        self.assertEqual([f.code for f in check_quantity(facts, evidence)], ["INVALID_QUANTITY"])
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_missing_citation_maps_missing_evidence(self):
        # A blank citation does not resolve to a version-specific document.
        i = uuid4()
        facts = _facts([_item(i, source="")])
        evidence = _evidence([_candidate(i, source="")], [_stock()])
        self.assertEqual(
            [f.code for f in check_source_evidence(facts, evidence)], ["MISSING_EVIDENCE"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_mismatched_citation_maps_missing_evidence(self):
        # The citation resolves (rev 2) but does not match the surfaced evidence (rev 1).
        i = uuid4()
        facts = _facts([_item(i, source=_citation(rev=2))])
        evidence = _evidence([_candidate(i, source=_citation(rev=1))], [_stock()])
        self.assertEqual(
            [f.code for f in check_source_evidence(facts, evidence)], ["MISSING_EVIDENCE"]
        )
        self.assertFalse(verify_facts(facts, evidence).passed)


class SourceReferenceResolution(unittest.TestCase):
    def test_version_specific_reference_resolves(self):
        citation = resolve_source_reference(_citation(rev=3, section="FILTERS"))
        self.assertTrue(citation.resolved)
        self.assertEqual(citation.revision, "3")
        self.assertEqual(citation.page, "section FILTERS")
        self.assertTrue(citation.document)

    def test_blank_reference_does_not_resolve(self):
        self.assertFalse(resolve_source_reference("   ").resolved)

    def test_reference_without_revision_does_not_resolve(self):
        self.assertFalse(resolve_source_reference("SYNTH-CA-PB-CA-110 FILTERS").resolved)


class CanonicalFactHash(unittest.TestCase):
    def test_hash_is_order_independent_across_items_and_allocations(self):
        a, b = uuid4(), uuid4()
        item_a = _item(a, part_id=10, allocations=((1, "1"), (2, "1")))
        item_b = _item(b, part_id=20, allocations=((2, "1"), (1, "1")))
        facts_one = _facts([item_a, item_b])
        # Reorder both the item list and each item's allocation list.
        reordered_b = _item(b, part_id=20, allocations=((1, "1"), (2, "1")))
        reordered_a = _item(a, part_id=10, allocations=((2, "1"), (1, "1")))
        facts_two = VerifiedFacts(
            enquiry_id=facts_one.enquiry_id,
            revision=facts_one.revision,
            catalogue_version_id=facts_one.catalogue_version_id,
            items=[reordered_b, reordered_a],
        )
        self.assertEqual(facts_sha256(facts_one), facts_sha256(facts_two))

    def test_hash_is_decimal_scale_stable(self):
        # Decimal("2") and Decimal("2.0") compare equal and must hash to the same facts.
        i = uuid4()
        enquiry_id = uuid4()
        coarse = VerifiedFacts(
            enquiry_id=enquiry_id,
            revision=1,
            catalogue_version_id=CV,
            items=[_item(i, requested="2", allocations=((1, "2"),))],
        )
        fine = VerifiedFacts(
            enquiry_id=enquiry_id,
            revision=1,
            catalogue_version_id=CV,
            items=[_item(i, requested="2.0", allocations=((1, "2.0"),))],
        )
        self.assertEqual(facts_sha256(coarse), facts_sha256(fine))

    def test_different_facts_hash_differently(self):
        i = uuid4()
        enquiry_id = uuid4()
        base = VerifiedFacts(
            enquiry_id=enquiry_id, revision=1, catalogue_version_id=CV, items=[_item(i)]
        )
        changed = VerifiedFacts(
            enquiry_id=enquiry_id,
            revision=1,
            catalogue_version_id=CV,
            items=[_item(i, part_id=11)],
        )
        self.assertNotEqual(facts_sha256(base), facts_sha256(changed))


class UniqueStore:
    """In-memory mirror of verification_results with UNIQUE(enquiry_id, revision).

    Stands in for the BLOCKED live Postgres adapter: persist() is idempotent per
    (enquiry, revision) exactly as the unique index guarantees.
    """

    def __init__(self, loaded):
        self._loaded = loaded
        self._rows: dict[tuple[UUID, int], tuple[UUID, VerificationResult]] = {}
        self.persist_calls = 0

    async def load_current(self, enquiry_id, revision):
        return self._loaded

    async def persist(self, enquiry_id, revision, result):
        self.persist_calls += 1
        key = (enquiry_id, revision)
        if key not in self._rows:
            self._rows[key] = (uuid4(), result)
        return self._rows[key][0]


class PersistenceBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_persists_exactly_one_result_per_enquiry_revision(self):
        i = uuid4()
        facts = _facts([_item(i)])
        store = UniqueStore((facts, _evidence([_candidate(i)], [_stock()])))
        result, vid = await run_verification(facts.enquiry_id, facts.revision, store=store)
        self.assertIsInstance(vid, UUID)
        self.assertTrue(result.passed)
        self.assertEqual(store.persist_calls, 1)
        # A repeat verification of the same (enquiry, revision) reuses the one row.
        _again, vid2 = await run_verification(facts.enquiry_id, facts.revision, store=store)
        self.assertEqual(vid, vid2)
        self.assertEqual(len(store._rows), 1)

    async def test_missing_draft_is_not_found(self):
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1, store=UniqueStore(None))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_store_not_configured_is_dependency_unavailable(self):
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_DB") == "1",
    "live verification_results store is BLOCKED; set PARTSIQ_LIVE_DB=1 to run",
)
class LiveVerificationStore(unittest.IsolatedAsyncioTestCase):  # pragma: no cover
    async def test_live_persist_unique_constraint(self):
        raise AssertionError("live DB path is BLOCKED and must never run in CI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
