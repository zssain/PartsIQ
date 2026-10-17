"""Human corrections become labelled evaluation ground truth — gated and anonymized (F62).

A staff reviewer may promote the lesson of a real human correction into the labelled
evaluation dataset, but ONLY after an explicit staff approval and ONLY as anonymized text. This
is the sole authorized path by which real-world feedback enters the eval set, and it is bounded
by three guarantees the implementation enforces here:

  * Staff-gated: the actor must hold ``admin`` or ``reviewer``; any other (or anonymous) actor
    gets FORBIDDEN (403). The actor is the verified :class:`ActorContext`, never a request body
    ``actor_id`` (CONSTRAINTS: no domain function trusts an unverified actor).
  * Anonymized only: the curated case stores the reviewer-supplied ``anonymized_text`` and the
    labelled outcome. Raw customer PII (emails, phone numbers, long digit runs that look like
    customer IDs/serials in context) is REFUSED — the correction's original prose never lands in
    the eval fixture (CONSTRAINTS rule 17: no raw customer data leaves its boundary).
  * Linked and audited: the new case records the SOURCE correction id so the ground-truth
    provenance is traceable, and the promotion is written as an append-only audit event in the
    same persist call as the stored case — no eval case appears without its audit trail (F49).

The persistence boundary is an injected store so the decision logic is unit-testable with no
database. The store is responsible for resolving the correction id for ``case_id`` and for
committing the case + audit event atomically; this module owns the authorization, the PII
refusal and the typed :class:`CuratedView` it returns.
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import CurateRequest, CuratedView
from partsiq.core.contracts import ActorContext, AuditEvent, EvalCase
from partsiq.core.errors import PartsIQError

#: Roles permitted to promote a correction into the eval set. A catalogue_admin manages the
#: catalogue, not review ground truth, so it is deliberately NOT sufficient on its own.
CURATION_ROLES: tuple[str, ...] = ("admin", "reviewer")

# Patterns that indicate raw, un-anonymized customer PII slipped into the submitted text. These
# are conservative: an email, an international/local phone number, or a long bare digit run
# (customer account / order numbers) must be redacted by the reviewer before promotion.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{8,}\d(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{9,}(?!\d)")


class CurationStore(Protocol):
    """Injected persistence boundary for promoting a correction into the eval set."""

    async def correction_for_case(self, case_id: str) -> UUID | None:
        """Resolve the source human-correction id a curated ``case_id`` derives from.

        Returns ``None`` when no such correction exists; the caller maps that to NOT_FOUND so a
        curated case can never be fabricated without a real correction behind it.
        """
        ...

    async def persist_case(
        self, case: EvalCase, *, source_correction_id: UUID, audit: AuditEvent
    ) -> None:
        """Commit the labelled case and its audit event in ONE transaction (F49)."""
        ...


def _contains_pii(text: str) -> bool:
    """True when the submitted text still carries raw customer PII that must be redacted first."""
    return bool(_EMAIL.search(text) or _PHONE.search(text) or _LONG_DIGITS.search(text))


def _build_audit(
    actor: ActorContext, case_id: str, source_correction_id: UUID
) -> AuditEvent:
    """The append-only record of a staff promotion — ids only, no customer prose or PII."""
    return AuditEvent(
        actor_type="user",
        actor_id=str(actor.user_id),
        action="curate_eval_case",
        entity_type="eval_case",
        entity_id=case_id,
        request_id=actor.request_id,
        enquiry_id=None,
        revision=None,
        payload={"source_correction_id": str(source_correction_id)},
    )


async def curate_case(
    actor: ActorContext,
    request: CurateRequest,
    *,
    store: CurationStore,
    now: datetime | None = None,
) -> CuratedView:
    """Promote a human correction into a labelled eval case — staff-gated, anonymized, audited.

    Raises:
        PartsIQError(FORBIDDEN): the actor is not an admin or reviewer.
        PartsIQError(VALIDATION_FAILED): the submitted text still carries raw customer PII.
        PartsIQError(NOT_FOUND): no source correction backs ``request.case_id``.
    """
    if not any(role in actor.roles for role in CURATION_ROLES):
        raise PartsIQError(
            "FORBIDDEN", internal_detail="eval curation requires admin or reviewer"
        )
    if _contains_pii(request.anonymized_text):
        raise PartsIQError(
            "VALIDATION_FAILED",
            detail="Submitted text must be anonymized before curation.",
            internal_detail="raw customer PII detected in curation text",
        )

    source_correction_id = await store.correction_for_case(request.case_id)
    if source_correction_id is None:
        raise PartsIQError(
            "NOT_FOUND", internal_detail="no source correction for curated case"
        )

    case = EvalCase(
        id=request.case_id,
        scenario="curated",
        input_text=request.anonymized_text,
        expected_status=request.expected_status,
        expected_part_ids=list(request.expected_part_ids),
    )
    audit = _build_audit(actor, request.case_id, source_correction_id)
    await store.persist_case(case, source_correction_id=source_correction_id, audit=audit)

    return CuratedView(
        case_id=request.case_id,
        source_correction_id=source_correction_id,
        approved_by=actor.user_id,
        created_at=now or datetime.now(UTC),
    )


# A convenience alias for callers that only need to resolve a correction id through the store.
CorrectionResolver = Callable[[str], Awaitable[UUID | None]]
