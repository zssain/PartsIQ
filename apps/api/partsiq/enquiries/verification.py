"""Deterministic verification gate (prompt 12 — F46 verification gate, F28 citations).

Contract:
    def verify_facts(facts: VerifiedFacts, evidence: VerificationEvidence) -> VerificationResult
    async def verify_current(enquiry_id: UUID, revision: int) -> VerificationResult

Every rule below is a NAMED PURE function over (facts, evidence). Pass/fail is decided here
in code and never by a model (CONSTRAINTS rules 5 and 6): an LLM is never asked whether
verification passed. The aggregate allocation is recomputed across ALL items that share a
(part, warehouse) so an oversold plan split across several items is still caught. Facts are
canonicalized before SHA-256 (see ``facts.facts_sha256``), so the stored fact hash is stable
and independent of input ordering. Exactly one result row is persisted per
(enquiry, revision); each failure carries a stable code and, where item-scoped, the
offending item id.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from partsiq.core.contracts import (
    VerificationEvidence,
    VerificationFailure,
    VerificationResult,
    VerifiedFacts,
)
from partsiq.core.errors import PartsIQError

from .facts import facts_sha256, resolve_source_reference

Failures = list[VerificationFailure]


# ---------------------------------------------------------------------------
# Evidence index — the single source of what the deterministic pipeline surfaced.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class _EvidenceIndex:
    items: frozenset[UUID]
    parts_by_item: dict[UUID, frozenset[int]]
    configs_by_item_part: dict[tuple[UUID, int], frozenset[int]]
    citations_by_item_part: dict[tuple[UUID, int], frozenset[tuple[UUID, str]]]


def _index(evidence: VerificationEvidence) -> _EvidenceIndex:
    parts_by_item: dict[UUID, set[int]] = defaultdict(set)
    configs: dict[tuple[UUID, int], set[int]] = defaultdict(set)
    citations: dict[tuple[UUID, int], set[tuple[UUID, str]]] = defaultdict(set)
    for candidate in evidence.candidates:
        parts_by_item[candidate.item_id].add(candidate.part_id)
        key = (candidate.item_id, candidate.part_id)
        configs[key].add(candidate.configuration_id)
        citations[key].add((candidate.evidence_id, candidate.source_reference))
    return _EvidenceIndex(
        items=frozenset(parts_by_item),
        parts_by_item={item: frozenset(parts) for item, parts in parts_by_item.items()},
        configs_by_item_part={key: frozenset(values) for key, values in configs.items()},
        citations_by_item_part={
            key: frozenset(values) for key, values in citations.items()
        },
    )


# ---------------------------------------------------------------------------
# Named pure checks. Each returns the failures it found; none mutates its inputs.
# ---------------------------------------------------------------------------
def check_current_revision(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> Failures:
    """The plan must describe the current revision; a stale draft cannot be approved."""
    if facts.revision != evidence.current_revision:
        return [
            VerificationFailure(
                code="STALE_REVISION",
                item_id=None,
                detail=(
                    f"facts revision {facts.revision} is not the current revision "
                    f"{evidence.current_revision}"
                ),
            )
        ]
    return []


def check_catalogue_version(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> Failures:
    """The plan must be built against the active catalogue version (stale catalogue)."""
    if facts.catalogue_version_id != evidence.active_catalogue_version_id:
        return [
            VerificationFailure(
                code="STALE_CATALOGUE",
                item_id=None,
                detail="facts reference a catalogue version that is no longer active",
            )
        ]
    return []


def check_candidate_membership(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> Failures:
    """Every chosen part must be one the pipeline actually surfaced for that item.

    An item with no surfaced candidates at all is a hidden extra item; a part that is not
    among an item's surfaced candidates is an unknown part. Both are refused here.
    """
    index = _index(evidence)
    out: Failures = []
    for item in facts.items:
        if item.item_id not in index.items:
            out.append(
                VerificationFailure(
                    code="UNRESOLVED_ITEM",
                    item_id=item.item_id,
                    detail="item has no surfaced candidate evidence (hidden extra item)",
                )
            )
        elif item.part_id not in index.parts_by_item[item.item_id]:
            out.append(
                VerificationFailure(
                    code="INCOMPATIBLE",
                    item_id=item.item_id,
                    detail=(
                        f"part {item.part_id} is not among the compatible candidates "
                        "for this item"
                    ),
                )
            )
    return out


def check_configuration_membership(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> Failures:
    """The chosen part must be compatible under the item's identified configuration.

    A part that exists as a candidate but only under a different configuration is an
    incompatible part for this machine.
    """
    index = _index(evidence)
    out: Failures = []
    for item in facts.items:
        configs = index.configs_by_item_part.get((item.item_id, item.part_id))
        if configs and item.configuration_id not in configs:
            out.append(
                VerificationFailure(
                    code="INCOMPATIBLE",
                    item_id=item.item_id,
                    detail=(
                        f"part {item.part_id} is not compatible under configuration "
                        f"{item.configuration_id}"
                    ),
                )
            )
    return out


def check_source_evidence(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> Failures:
    """Every item must carry a version-specific citation that matches surfaced evidence.

    The citation must resolve to a version-specific document+page (F28) and must equal the
    (evidence_id, source_reference) the pipeline recorded for that item/part. A citation
    pointing at a different catalogue revision will not be in the current evidence set, so a
    mismatched version fails here (F28, "mismatched version fails verification").
    """
    index = _index(evidence)
    out: Failures = []
    for item in facts.items:
        if not resolve_source_reference(item.source_reference).resolved:
            out.append(
                VerificationFailure(
                    code="MISSING_EVIDENCE",
                    item_id=item.item_id,
                    detail="source reference does not resolve to a version-specific document",
                )
            )
            continue
        known = index.citations_by_item_part.get((item.item_id, item.part_id))
        if not known or (item.evidence_id, item.source_reference) not in known:
            out.append(
                VerificationFailure(
                    code="MISSING_EVIDENCE",
                    item_id=item.item_id,
                    detail="citation does not match the surfaced version-specific evidence",
                )
            )
    return out


def check_quantity(facts: VerifiedFacts, evidence: VerificationEvidence) -> Failures:
    """Requested quantity must be positive, allocations non-negative, shortage explicit.

    The shortage is recomputed from requested minus the sum of allocations; a stated
    shortage that disagrees is rejected so the plan cannot hide an unmet quantity.
    """
    out: Failures = []
    for item in facts.items:
        if item.requested_quantity <= 0:
            out.append(
                VerificationFailure(
                    code="INVALID_QUANTITY",
                    item_id=item.item_id,
                    detail="requested quantity must be positive",
                )
            )
            continue
        if any(allocation.quantity < 0 for allocation in item.allocations):
            out.append(
                VerificationFailure(
                    code="INVALID_QUANTITY",
                    item_id=item.item_id,
                    detail="allocation quantities must be non-negative",
                )
            )
            continue
        allocated = sum(
            (allocation.quantity for allocation in item.allocations), Decimal("0")
        )
        expected_shortage = item.requested_quantity - allocated
        if expected_shortage < 0:
            expected_shortage = Decimal("0")
        if item.shortage != expected_shortage:
            out.append(
                VerificationFailure(
                    code="INVALID_QUANTITY",
                    item_id=item.item_id,
                    detail=(
                        f"shortage {item.shortage} does not equal requested minus "
                        f"allocated ({expected_shortage})"
                    ),
                )
            )
    return out


def check_allocation(facts: VerifiedFacts, evidence: VerificationEvidence) -> Failures:
    """Recompute aggregate allocation per (part, warehouse) and bound it by stock.

    Summing across every item that shares a part and warehouse catches an oversold plan
    even when no single item exceeds stock on its own. A warehouse with no current stock
    evidence cannot back an allocation and is flagged stale.
    """
    allocated: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    owner: dict[tuple[int, int], UUID] = {}
    for item in facts.items:
        for allocation in item.allocations:
            key = (item.part_id, allocation.warehouse_id)
            allocated[key] += allocation.quantity
            owner.setdefault(key, item.item_id)

    available = {(row.part_id, row.warehouse_id): row.available for row in evidence.stock}

    out: Failures = []
    for key in sorted(allocated):
        part_id, warehouse_id = key
        if key not in available:
            out.append(
                VerificationFailure(
                    code="STALE_STOCK",
                    item_id=owner[key],
                    detail=(
                        f"no current stock evidence for part {part_id} at warehouse "
                        f"{warehouse_id}"
                    ),
                )
            )
            continue
        if allocated[key] > available[key]:
            out.append(
                VerificationFailure(
                    code="OVERALLOCATION",
                    item_id=owner[key],
                    detail=(
                        f"aggregate allocation {allocated[key]} exceeds available "
                        f"{available[key]} for part {part_id} at warehouse {warehouse_id}"
                    ),
                )
            )
    return out


# Ordered, named registry so the rule set is stable and inspectable (F46: stored rules).
CHECKS: tuple[
    tuple[str, "object"],
    ...,
] = (
    ("current_revision", check_current_revision),
    ("catalogue_version", check_catalogue_version),
    ("candidate_membership", check_candidate_membership),
    ("configuration_membership", check_configuration_membership),
    ("source_evidence", check_source_evidence),
    ("quantity", check_quantity),
    ("allocation", check_allocation),
)


def verify_facts(
    facts: VerifiedFacts, evidence: VerificationEvidence
) -> VerificationResult:
    """Run every named rule in order and record the canonical fact hash.

    Pure; no I/O, no LLM.
    """
    failures: Failures = []
    for _name, check in CHECKS:
        failures.extend(check(facts, evidence))  # type: ignore[operator]
    return VerificationResult(
        passed=not failures,
        failures=failures,
        facts_sha256=facts_sha256(facts),
    )


# ---------------------------------------------------------------------------
# Persistence boundary. The store is injected so the gate is testable offline; the live
# Postgres adapter (verification_results, UNIQUE(enquiry_id, revision)) is wired by the
# owner. persist() is idempotent per (enquiry, revision).
# ---------------------------------------------------------------------------
class VerificationStore(Protocol):
    async def load_current(
        self, enquiry_id: UUID, revision: int
    ) -> tuple[VerifiedFacts, VerificationEvidence] | None: ...

    async def persist(
        self, enquiry_id: UUID, revision: int, result: VerificationResult
    ) -> UUID: ...


_store: VerificationStore | None = None


def configure_store(store: VerificationStore | None) -> None:
    """Wire the live persistence adapter at service startup (owner responsibility)."""
    global _store
    _store = store


async def run_verification(
    enquiry_id: UUID, revision: int, *, store: VerificationStore
) -> tuple[VerificationResult, UUID]:
    """Load the current draft's facts+evidence, verify, persist one result, return (result, id)."""
    loaded = await store.load_current(enquiry_id, revision)
    if loaded is None:
        raise PartsIQError("NOT_FOUND", internal_detail="no current draft facts to verify")
    facts, evidence = loaded
    result = verify_facts(facts, evidence)
    verification_id = await store.persist(enquiry_id, revision, result)
    return result, verification_id


async def verify_current(
    enquiry_id: UUID, revision: int, *, store: VerificationStore | None = None
) -> VerificationResult:
    """Application entry point: verify and persist the current draft for an enquiry revision."""
    store = store or _store
    if store is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="verification store not configured",
        )
    result, _ = await run_verification(enquiry_id, revision, store=store)
    return result
