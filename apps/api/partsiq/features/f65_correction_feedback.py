"""F65 Correction feedback facade (helper ``evaluation.curate_correction``).

Promotes the lesson of a real human correction into the labelled evaluation dataset — the sole
authorized path by which real-world feedback enters the eval set. It delegates to the domain
:func:`partsiq.evaluation.curation.curate_case`, which enforces the three guarantees:

  * Staff-gated: the actor must hold ``admin`` or ``reviewer`` (never a request-body actor id); any
    other caller gets FORBIDDEN (403). The endpoint is admin-scoped, so the gate is satisfied by an
    admin.
  * Anonymized only: raw customer PII (emails, phone numbers, long digit runs) in the submitted
    text is REFUSED (422) — the correction's original prose never lands in the eval fixture.
  * Linked and audited: the new case records its SOURCE correction id and the promotion is written
    as an append-only audit event in the SAME persist call (F49) — no case appears without its
    audit trail.

The persistence boundary is an injected :class:`CurationStore`; it resolves the correction for the
case id and commits the case + audit atomically. It is BLOCKED offline, so an admin gets a clean
503 rather than a fabricated case — and a case with no real source correction behind it is a 404.
"""
from __future__ import annotations

from partsiq.core.api_models import CurateRequest, CuratedView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.evaluation.curation import CurationStore, curate_case
from partsiq.features._ops_ports import require_store


async def curate_correction(
    actor: ActorContext,
    request: CurateRequest,
    *,
    container: AppContainer,
    store: CurationStore | None = None,
) -> CuratedView:
    """Promote a human correction into a labelled eval case — staff-gated, anonymized, audited.

    The role gate, PII refusal and append-only audit live in the domain ``curate_case``; this
    facade only resolves the injected store (a clean 503 when unwired) and delegates.
    """
    store = store or require_store(container, "curation_store")
    return await curate_case(actor, request, store=store)
