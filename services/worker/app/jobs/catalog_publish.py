"""F59 catalogue publication job (owner: worker; the only holder of the catalogue DB role).

The gateway validates the caller is catalogue_admin/admin and queues this job through the
worker internal route; the worker re-reads the initiating user's membership from the signed
payload (defence in depth), opens the CATALOGUE-role connection, and invokes publish_version
under the publication advisory lock. The final JobResult is fenced by the lease (prompt 15).

The catalogue-role PublicationStore (advisory lock 710070, single transaction) is injected at
startup and is BLOCKED here, so with no store wired the job reports a failed JobResult rather
than fabricating a publication. publish_version lives in the catalog package, imported lazily
because that package is outside the worker's import path at module load.
"""
from __future__ import annotations

from uuid import UUID

from partsiq_common.contracts import ActorContext, JobLease, JobResult
from partsiq_common.errors import PartsIQError

_PUBLISHER_ROLES = frozenset({"catalogue_admin", "admin"})
_VALID_ROLES = frozenset({"reviewer", "catalogue_admin", "admin"})

_store = None  # catalogue-role PublicationStore, wired at startup (BLOCKED in this environment)


def configure_store(store) -> None:
    """Owner wiring: supply the catalogue-role publication store at worker startup."""
    global _store
    _store = store


async def publish_catalogue_job(lease: JobLease) -> JobResult:
    """Re-check admin membership, publish under the lock, and return a fenced JobResult."""
    from catalog.versioning import F59Request, publish_version

    payload = lease.payload
    roles = [r for r in str(payload.get("actor_roles") or "").split(",") if r in _VALID_ROLES]
    if not (_PUBLISHER_ROLES & set(roles)):
        return JobResult(status="failed", result_id=None, error_code="FORBIDDEN")
    if _store is None:
        return JobResult(status="failed", result_id=None, error_code="DEPENDENCY_UNAVAILABLE")
    actor = ActorContext(
        user_id=UUID(str(payload["actor_user_id"])),
        request_id=UUID(str(payload["request_id"])),
        roles=roles,  # type: ignore[arg-type]
    )
    request = F59Request(
        version_id=UUID(str(payload["version_id"])),
        expected_active_version_id=UUID(str(payload["expected_active_version_id"])),
        idempotency_key=UUID(str(payload["idempotency_key"])),
    )
    try:
        result = await publish_version(actor, request, store=_store)
    except PartsIQError as exc:
        return JobResult(status="failed", result_id=None, error_code=exc.code)
    return JobResult(status="succeeded", result_id=result.version_id, error_code=None)
