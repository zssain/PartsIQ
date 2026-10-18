"""F14 Nameplate OCR facade (helper ``storage.confirm_upload``).

A nameplate photo is uploaded to its short-lived signed URL (F13), then the owner CONFIRMS the
upload here. Confirmation flips the pending attachment to uploaded and ENQUEUES the nameplate
vision job for the enquiry's current revision; the response is the queued :class:`JobView` (202) —
the OCR result itself arrives later and is read through F15's stored extraction. The job is NEVER
run inline on the request path, and the vision call is NEVER made before the local pre-check (F16)
has turned back an unusable image — a model reading is never treated as confirmed truth (F15).

``expected_revision`` guards against confirming against a stale revision (409). Owner access; a
foreign attachment is NOT_FOUND. The confirmation + enqueue is one atomic, idempotent transaction
behind the injected :class:`UploadConfirmationStore` port (unit-testable with a fake). That store is
DB/queue-backed and NOT configured in this fixture/offline environment, so a clean 503 is surfaced
rather than a fabricated job id — the live PostgreSQL + job-queue adapter is wired by the owner and
BLOCKED here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView, RevisionOnly
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError


@runtime_checkable
class UploadConfirmationStore(Protocol):
    """Port over the one locked confirm-upload + enqueue-nameplate-job transaction.

    ``confirm`` re-authorises the actor against the attachment's enquiry, compares
    ``expected_revision`` (a stale confirm is a 409), marks the pending attachment uploaded and
    enqueues the nameplate vision job idempotently per ``Idempotency-Key`` — all atomically — then
    returns the queued job view.
    """

    async def confirm(
        self,
        actor: ActorContext,
        attachment_id: UUID,
        command: RevisionOnly,
        key: UUID,
    ) -> JobView: ...


def _require_confirmation_store(container: AppContainer) -> UploadConfirmationStore:
    store = getattr(container, "upload_confirmation", None)
    if store is None or not hasattr(store, "confirm"):
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="upload-confirmation store is not configured in this environment",
        )
    return store


async def confirm_upload(
    actor: ActorContext,
    attachment_id: UUID,
    command: RevisionOnly,
    key: UUID,
    *,
    container: AppContainer,
    store: UploadConfirmationStore | None = None,
) -> JobView:
    """Confirm a finished upload and enqueue the nameplate OCR job; return the job view (202)."""
    store = store or _require_confirmation_store(container)
    return await store.confirm(actor, attachment_id, command, key)
