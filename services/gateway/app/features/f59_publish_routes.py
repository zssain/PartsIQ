"""F59 gateway publish adapter (owner: gateway).

Publication's DB credential belongs to the worker, not the gateway. So the gateway only
validates the caller is catalogue_admin/admin, records the idempotency key, and QUEUES a
durable publish request to the worker internal route — it never runs publish_version inline.
The worker re-checks membership and performs the version switch under the advisory lock.

The gateway stays decoupled from the catalog package: it carries only the three typed ids the
worker needs. The enqueue port is injected; with none wired the route fails closed (503).
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

_PUBLISHER_ROLES = frozenset({"catalogue_admin", "admin"})


class PublishBody(Contract):
    version_id: UUID
    expected_active_version_id: UUID
    idempotency_key: UUID


class PublishQueue(Protocol):
    async def enqueue_publish(self, actor: ActorContext, body: PublishBody) -> UUID:
        """Persist-before-dispatch a catalog_publish job carrying the signed actor; return job id."""
        ...


def _authorize(actor: ActorContext) -> None:
    if not (_PUBLISHER_ROLES & set(actor.roles)):
        raise PartsIQError("FORBIDDEN", internal_detail="catalogue publication requires catalogue_admin/admin")


async def request_publish(actor: ActorContext, body: PublishBody, *, queue: PublishQueue) -> dict:
    """Validate role and queue the publish; returns the durable job id (202, never inline)."""
    _authorize(actor)
    job_id = await queue.enqueue_publish(actor, body)
    return {"job_id": str(job_id)}
