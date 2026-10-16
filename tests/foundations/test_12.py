"""Acceptance tests for prompt 12 — deterministic verification (foundation gate).

Offline: verify_facts is a pure function over typed facts+evidence; every named rule is
exercised directly, the aggregate allocation is recomputed across items sharing a
(part, warehouse), the canonical fact hash is shown stable and order-independent, and
verify_current persists exactly one result through an injected store (the live Postgres
adapter is integration-only and reported BLOCKED). No LLM participates in pass/fail.

Covers F46 (verification gate) and F28 (version-specific citation resolution). The five
F46 failure scenarios — unknown part, incompatible part, stale catalogue, oversold plan,
hidden extra item — each fail a specific named rule asserted below.
"""
from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.controller import next_step  # noqa: E402
from app.graph import build_graph  # noqa: E402
from app.handlers import WorkflowHandlers, make_verify_handler  # noqa: E402
from app.verification import (  # noqa: E402
    canonical_facts_sha256,
    check_allocation,
    check_candidate_membership,
    check_catalogue_version,
    check_configuration_membership,
    check_current_revision,
    check_quantity,
    check_source_evidence,
    resolve_source_reference,
    run_verification,
    verify_current,
    verify_facts,
)
from partsiq_common.contracts import (  # noqa: E402
    Allocation,
    CandidateEvidence,
    EnquiryState,
    ItemInput,
    ItemState,
    StockEvidence,
    VerificationEvidence,
    VerificationResult,
    VerifiedFacts,
    VerifiedItem,
    WorkflowStep,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

CV = uuid4()
EV = uuid4()
WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _citation(rev: int = 1, section: str = "FILTERS", model: str = "CA-110") -> str:
    return f"SYNTH-CA-PB-{model} rev {rev}, section {section}"


def _item(
    item_id: UUID,
    *,
    part_id: int = 10,
    config: int = 100,
    requested: str = "2",
    allocations=((1, "2"),),
    shortage: str = "0",
    evidence_id: UUID = EV,
    source: str | None = None,
) -> VerifiedItem:
    return VerifiedItem(
        item_id=item_id,
        configuration_id=config,
        part_id=part_id,
        part_number="VP-FF-10",
        name_en="fuel filter",
        name_ar="فلتر وقود",
        requested_quantity=Decimal(requested),
        allocations=[
            Allocation(warehouse_id=wh, quantity=Decimal(q), transfer_days=2, stock_updated_at=WHEN)
            for wh, q in allocations
        ],
        shortage=Decimal(shortage),
        source_reference=source if source is not None else _citation(),
        evidence_id=evidence_id,
    )


def _facts(items, *, revision: int = 1, catalogue: UUID = CV) -> VerifiedFacts:
    return VerifiedFacts(enquiry_id=uuid4(), revision=revision, catalogue_version_id=catalogue, items=items)


def _candidate(item_id: UUID, *, part_id: int = 10, config: int = 100, source: str | None = None) -> CandidateEvidence:
    return CandidateEvidence(
        item_id=item_id,
        part_id=part_id,
        configuration_id=config,
        evidence_id=EV,
        source_reference=source if source is not None else _citation(),
    )


def _evidence(candidates, stock, *, revision: int = 1, catalogue: UUID = CV) -> VerificationEvidence:
    return VerificationEvidence(
        current_revision=revision,
        active_catalogue_version_id=catalogue,
        candidates=candidates,
        stock=stock,
    )


def _good_pair():
    """A plan that passes every rule: one item, one allocation that meets the request."""
    i = uuid4()
    facts = _facts([_item(i)])
    evidence = _evidence(
        [_candidate(i)],
        [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
    )
    return facts, evidence, i


class HappyPath(unittest.TestCase):
    def test_valid_plan_passes_with_no_failures(self):
        facts, evidence, _ = _good_pair()
        result = verify_facts(facts, evidence)
        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.failures, [])

    def test_result_carries_canonical_fact_hash(self):
        facts, evidence, _ = _good_pair()
        result = verify_facts(facts, evidence)
        self.assertRegex(result.facts_sha256, r"^[a-f0-9]{64}$")
        self.assertEqual(result.facts_sha256, canonical_facts_sha256(facts))


class NamedRuleFailures(unittest.TestCase):
    """Each F46 failure scenario fails a SPECIFIC named rule — asserted on that rule."""

    def test_stale_revision(self):
        facts, _, i = _good_pair()
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
            revision=2,
        )
        failures = check_current_revision(facts, evidence)
        self.assertEqual([f.code for f in failures], ["STALE_REVISION"])
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_stale_catalogue(self):
        i = uuid4()
        facts = _facts([_item(i)], catalogue=uuid4())  # not the active version
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_catalogue_version(facts, evidence)
        self.assertEqual([f.code for f in failures], ["STALE_CATALOGUE"])

    def test_unknown_part_fails_candidate_membership(self):
        i = uuid4()
        facts = _facts([_item(i, part_id=999)])  # 999 was never surfaced
        evidence = _evidence(
            [_candidate(i, part_id=10)],
            [StockEvidence(part_id=999, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_candidate_membership(facts, evidence)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].code, "INCOMPATIBLE")
        self.assertEqual(failures[0].item_id, i)

    def test_hidden_extra_item_fails_candidate_membership(self):
        i, ghost = uuid4(), uuid4()
        facts = _facts([_item(i), _item(ghost)])  # ghost has no candidate evidence
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_candidate_membership(facts, evidence)
        self.assertEqual([f.code for f in failures], ["UNRESOLVED_ITEM"])
        self.assertEqual(failures[0].item_id, ghost)

    def test_incompatible_part_fails_configuration_membership(self):
        i = uuid4()
        facts = _facts([_item(i, config=200)])  # item claims config 200
        evidence = _evidence(
            [_candidate(i, config=100)],  # but the part is only compatible under 100
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_configuration_membership(facts, evidence)
        self.assertEqual([f.code for f in failures], ["INCOMPATIBLE"])
        self.assertEqual(failures[0].item_id, i)

    def test_oversold_plan_fails_allocation_in_aggregate(self):
        # Two items each allocate 3 of part 10 at warehouse 1; neither alone exceeds 5,
        # but the aggregate (6) does. The recompute across items catches it.
        a, b = uuid4(), uuid4()
        facts = _facts(
            [
                _item(a, requested="3", allocations=((1, "3"),), shortage="0"),
                _item(b, requested="3", allocations=((1, "3"),), shortage="0"),
            ]
        )
        evidence = _evidence(
            [_candidate(a), _candidate(b)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_allocation(facts, evidence)
        self.assertEqual([f.code for f in failures], ["OVERALLOCATION"])
        self.assertFalse(verify_facts(facts, evidence).passed)

    def test_missing_stock_evidence_fails_allocation_stale(self):
        i = uuid4()
        facts = _facts([_item(i, allocations=((2, "2"),))])  # warehouse 2 has no stock row
        evidence = _evidence([_candidate(i)], [])
        failures = check_allocation(facts, evidence)
        self.assertEqual([f.code for f in failures], ["STALE_STOCK"])

    def test_inconsistent_shortage_fails_quantity(self):
        i = uuid4()
        # requested 2, allocated 2 -> shortage must be 0, but the plan claims 5.
        facts = _facts([_item(i, requested="2", allocations=((1, "2"),), shortage="5")])
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_quantity(facts, evidence)
        self.assertEqual([f.code for f in failures], ["INVALID_QUANTITY"])

    def test_explicit_shortage_is_accepted(self):
        i = uuid4()
        # requested 5, allocated 2 -> shortage 3 is explicit and consistent: valid.
        facts = _facts([_item(i, requested="5", allocations=((1, "2"),), shortage="3")])
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        self.assertEqual(check_quantity(facts, evidence), [])


class SourceEvidence(unittest.TestCase):
    """F28 — resolve source_reference to a version-specific document and page."""

    def test_resolves_to_version_specific_document_and_page(self):
        citation = resolve_source_reference(_citation(rev=3, section="FILTERS"))
        self.assertTrue(citation.resolved)
        self.assertEqual(citation.revision, "3")
        self.assertIn("rev 3", citation.document)
        self.assertEqual(citation.page, "section FILTERS")

    def test_blank_reference_does_not_resolve(self):
        self.assertFalse(resolve_source_reference("").resolved)
        self.assertFalse(resolve_source_reference("   ").resolved)

    def test_missing_citation_fails_source_evidence(self):
        i = uuid4()
        facts = _facts([_item(i, source="")])
        evidence = _evidence(
            [_candidate(i)],
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_source_evidence(facts, evidence)
        self.assertEqual([f.code for f in failures], ["MISSING_EVIDENCE"])

    def test_mismatched_version_fails_source_evidence(self):
        i = uuid4()
        facts = _facts([_item(i, source=_citation(rev=2))])  # plan cites rev 2
        evidence = _evidence(
            [_candidate(i, source=_citation(rev=1))],  # current evidence is rev 1
            [StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],
        )
        failures = check_source_evidence(facts, evidence)
        self.assertEqual([f.code for f in failures], ["MISSING_EVIDENCE"])


class CanonicalHash(unittest.TestCase):
    def test_hash_is_order_independent(self):
        a, b = UUID(int=1), UUID(int=2)
        facts_ab = _facts([_item(a), _item(b)])
        facts_ba = _facts([_item(b), _item(a)]).model_copy(update={"enquiry_id": facts_ab.enquiry_id})
        self.assertEqual(canonical_facts_sha256(facts_ab), canonical_facts_sha256(facts_ba))

    def test_hash_changes_with_decimal_quantity(self):
        i = UUID(int=3)
        base = _facts([_item(i, requested="2", allocations=((1, "2"),))]).model_copy(
            update={"enquiry_id": UUID(int=99)}
        )
        changed = _facts([_item(i, requested="3", allocations=((1, "3"),))]).model_copy(
            update={"enquiry_id": UUID(int=99)}
        )
        self.assertNotEqual(canonical_facts_sha256(base), canonical_facts_sha256(changed))

    def test_canonical_payload_renders_decimals_as_strings(self):
        # The hash input must contain decimal strings, not floats (stable across platforms).
        i = UUID(int=7)
        facts = _facts([_item(i, requested="2.500", allocations=((1, "2.500"),), shortage="0")])
        # Re-derive the canonical string to assert the decimal rendering contract.
        import json

        from app.verification import _canonical_payload

        canonical = json.dumps(_canonical_payload(facts), sort_keys=True, separators=(",", ":"))
        self.assertIn('"2.500"', canonical)
        self.assertNotRegex(canonical, r":2\.5[,}]")  # never a bare float


class FakeStore:
    """In-memory verification_results: one row per (enquiry, revision), idempotent persist."""

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
        else:
            # UNIQUE(enquiry_id, revision): replace the row contents, keep the id (idempotent).
            self._rows[key] = (self._rows[key][0], result)
        return self._rows[key][0]


class VerifyCurrent(unittest.IsolatedAsyncioTestCase):
    async def test_persists_one_result_and_returns_it(self):
        facts, evidence, _ = _good_pair()
        store = FakeStore((facts, evidence))
        result = await verify_current(facts.enquiry_id, facts.revision, store=store)
        self.assertTrue(result.passed)
        self.assertEqual(store.persist_calls, 1)

    async def test_persist_is_idempotent_per_revision(self):
        facts, evidence, _ = _good_pair()
        store = FakeStore((facts, evidence))
        _r1, id1 = await run_verification(facts.enquiry_id, facts.revision, store=store)
        _r2, id2 = await run_verification(facts.enquiry_id, facts.revision, store=store)
        self.assertEqual(id1, id2)  # same (enquiry, revision) -> same row

    async def test_missing_draft_is_not_found(self):  # invalid-input axis
        store = FakeStore(None)
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1, store=store)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_unconfigured_store_is_dependency_unavailable(self):  # dependency-failure axis
        with self.assertRaises(PartsIQError) as ctx:
            await verify_current(uuid4(), 1)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class GraphWiring(unittest.IsolatedAsyncioTestCase):
    """Regression for the graph/handlers connection (prompt 12 FILES TO MODIFY)."""

    async def test_verify_handler_sets_verification_and_routes_to_review(self):
        facts, evidence, item_id = _good_pair()
        store = FakeStore((facts, evidence))
        verify = make_verify_handler(store)

        state = EnquiryState(
            enquiry_id=facts.enquiry_id,
            revision=1,
            session_generation=None,
            catalogue_version_id=CV,
            items=[
                ItemState(
                    id=item_id,
                    request=ItemInput(
                        description="fuel filter", source_message_id=uuid4(), source_start=0, source_end=11
                    ),
                    configuration_id=100,
                    candidate_part_ids=[10],
                    selected_part_id=10,
                    status="ready",
                )
            ],
            step_count=0,
            pending_question=None,
            draft_id=uuid4(),
            verification_id=None,
            phase="planned",
        )
        self.assertEqual(next_step(state), WorkflowStep.VERIFY)  # before: verification pending

        updated = await verify(state)
        self.assertIsNotNone(updated.verification_id)
        self.assertEqual(updated.phase, "verified")
        self.assertEqual(next_step(updated), WorkflowStep.REVIEW)  # after: human review gate
        self.assertEqual(store.persist_calls, 1)

    async def test_build_graph_accepts_verify_handler(self):
        facts, evidence, _ = _good_pair()
        store = FakeStore((facts, evidence))

        async def passthrough(s):
            return s

        handlers = WorkflowHandlers(
            intake=passthrough, identify=passthrough, search=passthrough, choose=passthrough,
            plan=passthrough, draft=passthrough, verify=make_verify_handler(store),
        )
        graph = build_graph(handlers, InMemorySaver())
        self.assertIsNotNone(graph)  # compiles with the real verify handler wired


if __name__ == "__main__":
    unittest.main(verbosity=2)
