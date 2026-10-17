"""Publish ONE recommendation + the approved snapshot, atomically (prompt 14 — F47, F49).

Ported from the publication half of ``services/orchestrator/app/approval.py``'s committed
transaction. Only the human approval path reaches here (F47: "only approval service inserts
recommendation messages"). Given the locked, verified :class:`ReviewSnapshot` and the
rendered reply text, :func:`publish_recommendation` performs the irreversible business
mutation as one unit of work behind an injected :class:`PublicationStore` port:

  1. insert the ``review_decision`` (the approved decision);
  2. build the immutable :class:`ApprovedSnapshot` (what the PDF/export reads — never the
     live plan — CONSTRAINTS: "PDF uses ApprovedSnapshot only");
  3. insert EXACTLY ONE recommendation ``message`` for this ``(enquiry_id, revision)``,
     coupled to the approved decision (the DB CHECK rejects an orphan recommendation and the
     UNIQUE index rejects a second one — F47);
  4. append the :class:`AuditEvent` IN THE SAME TRANSACTION, so if the audit write fails the
     whole approval rolls back and nothing is published (F49).

The port mirrors those DB invariants so the coupling is testable offline; the live Postgres
adapter (the real unique index, CHECK and append-only trigger) is wired by the owner. The
audit payload is deliberately MINIMAL — ids, revision, the fact hash — and carries no reply
prose, no citation text and no secret (F49, CONSTRAINTS rule 17).

This module does NOT reserve inventory or send any external message (prompt 14 step 10).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from partsiq.core.contracts import (
    ActorContext,
    ApprovalResult,
    ApprovedSnapshot,
    AuditEvent,
    VerifiedFacts,
)

from .approval import ReviewSnapshot
from .facts import facts_sha256


class PublicationStore(Protocol):
    """Port over the atomic publish unit of work.

    The live adapter wraps all four writes in one transaction. The offline fake mirrors the
    same guarantees: ``insert_decision``/``insert_recommendation`` enforce the one-per-revision
    UNIQUE index and the decision-coupling CHECK, and ``append_audit`` is called within the
    same transaction so its failure aborts everything.
    """

    async def insert_decision(
        self, actor: ActorContext, snapshot: ReviewSnapshot, decision_id: UUID
    ) -> None: ...

    async def insert_recommendation(
        self,
        snapshot: ReviewSnapshot,
        decision_id: UUID,
        rendered_text: str,
        snapshot_record: ApprovedSnapshot,
    ) -> UUID: ...

    async def append_audit(self, event: AuditEvent) -> None: ...


def build_approved_snapshot(
    facts: VerifiedFacts,
    *,
    decision_id: UUID,
    locale: str,
    reply: str,
    approved_at: datetime,
    synthetic: bool,
) -> ApprovedSnapshot:
    """Freeze the approved facts + reply the export layer will read (never the live plan)."""
    return ApprovedSnapshot(
        decision_id=decision_id,
        approved_at=approved_at,
        locale=locale,  # type: ignore[arg-type]  # Locale is 'en'|'ar', validated by the model
        facts=facts,
        reply=reply,
        synthetic=synthetic,
    )


def build_audit_event(
    actor: ActorContext,
    snapshot: ReviewSnapshot,
    decision_id: UUID,
    *,
    action: str,
) -> AuditEvent:
    """Build the MINIMAL, redacted audit row for an irreversible review mutation (F49).

    Carries who/what/which-revision and the fact hash only — never the reply prose, citation
    text or any secret. The fact hash lets an auditor confirm the approval was bound to a
    specific plan without storing the plan's contents.
    """
    return AuditEvent(
        actor_type="user",
        actor_id=str(actor.user_id),
        action=action,
        entity_type="review_decision",
        entity_id=str(decision_id),
        request_id=actor.request_id,
        enquiry_id=snapshot.enquiry_id,
        revision=snapshot.revision,
        payload={
            "catalogue_version_id": str(snapshot.catalogue_version_id),
            "facts_sha256": facts_sha256(snapshot.facts),
            "draft_id": str(snapshot.draft_id) if snapshot.draft_id else None,
        },
    )


async def publish_recommendation(
    actor: ActorContext,
    snapshot: ReviewSnapshot,
    rendered_text: str,
    *,
    store: PublicationStore,
    synthetic: bool = False,
    now: datetime | None = None,
) -> ApprovalResult:
    """Insert the decision, the one recommendation and the audit row as one transaction.

    One recommendation per ``(enquiry_id, revision)`` and the decision coupling are enforced
    by the store (mirroring the DB UNIQUE index and CHECK). The audit append is the LAST write
    and lives in the same transaction, so an audit failure rolls the approval back (F49).
    Returns the :class:`ApprovalResult` the API surfaces; ``already_applied`` is false on a
    first publish and set true only on an idempotent replay upstream in ``approve``.
    """
    approved_at = now or datetime.now(UTC)
    decision_id = uuid4()

    await store.insert_decision(actor, snapshot, decision_id)

    approved_snapshot = build_approved_snapshot(
        snapshot.facts,
        decision_id=decision_id,
        locale=snapshot.locale,
        reply=rendered_text,
        approved_at=approved_at,
        synthetic=synthetic,
    )
    message_id = await store.insert_recommendation(
        snapshot, decision_id, rendered_text, approved_snapshot
    )

    # Same-transaction audit append: if this raises, the whole approval is rolled back (F49).
    await store.append_audit(build_audit_event(actor, snapshot, decision_id, action="approve"))

    return ApprovalResult(
        decision_id=decision_id,
        message_id=message_id,
        revision=snapshot.revision,
        already_applied=False,
    )
