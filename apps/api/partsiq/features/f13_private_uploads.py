"""F13 Private uploads facade (helpers ``storage.create_upload`` / ``storage.list_attachments``).

``create`` runs the real :func:`partsiq.storage.service.create_upload` domain function, which
chooses a server-side, enquiry/revision-scoped PENDING object key (never a caller path) and asks
the backend for a short-lived signed upload URL. In fixture mode the backend is synthetic: it
returns a clearly-labelled ``synthetic://`` URL and signs no live object — no real storage is
touched. The attachment is then registered as ``pending`` on the caller's own enquiry so a later
``list`` reflects it. Access is ``owner``; a foreign enquiry is NOT_FOUND.
"""
from __future__ import annotations

from partsiq.core.api_models import AttachmentList
from partsiq.core.contracts import ActorContext, UploadRequest, UploadTicket
from partsiq.core.dependencies import AppContainer
from partsiq.storage.service import create_upload


class _SyntheticStorageBackend:
    """Fixture storage backend: signs nothing live, returns a labelled synthetic URL.

    Used only in fixture mode so the private-upload flow serves a real UploadTicket shape
    without a live Supabase Storage service-role credential (BLOCKED offline).
    """

    async def create_signed_upload_url(
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str:
        return f"synthetic://{bucket}/{object_key}?ttl={ttl_seconds}"

    async def create_signed_download_url(  # pragma: no cover - not used by F13
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str:
        return f"synthetic://{bucket}/{object_key}?ttl={ttl_seconds}"

    async def download(self, bucket: str, object_key: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    async def remove(self, bucket: str, object_key: str) -> None:  # pragma: no cover
        return None


async def create(
    actor: ActorContext, command: UploadRequest, *, container: AppContainer
) -> UploadTicket:
    """Mint a pending attachment id + short-lived synthetic upload URL for the caller's enquiry."""
    journey = container.require_journey()
    # Ownership is enforced here (NOT_FOUND for a foreign enquiry) before issuing a ticket.
    await journey.get_enquiry(actor, command.enquiry_id)
    ticket = await create_upload(actor, command, backend=_SyntheticStorageBackend())
    await journey.register_upload(actor, command.enquiry_id, ticket)
    return ticket


async def list_attachments(
    actor: ActorContext, enquiry_id, *, container: AppContainer
) -> AttachmentList:
    """List the attachments on the caller's own enquiry; a foreign enquiry is NOT_FOUND."""
    return await container.require_journey().list_attachments(actor, enquiry_id)
