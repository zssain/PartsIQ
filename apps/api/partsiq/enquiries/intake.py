"""Enquiry and message intake (foundation 08).

Consolidated from ``services/gateway/app/enquiries.py`` and adapted to the single ``partsiq``
package. Two use cases, both returning a domain :class:`EnquiryView` (the route adapter, built
later, converts to a 202 HTTP response — this module never touches HTTP):

* :func:`create_enquiry` validates typed input, applies the rate limit BEFORE any database
  write, resolves the idempotency key, then commits the enquiry row, its first message, the
  revision snapshot AND the durable workflow job inside ONE transaction (prompt 08 step 4). It
  returns only AFTER that durable commit (step 5) — it never waits for OCR, vision or Snowflake.
* :func:`append_message` locks the enquiry, enforces ``expected_revision`` (a stale revision is
  a 409), and creates a new revision that invalidates previous derived results (step 8).

Every irreversible mutation writes an audit record in the SAME transaction (prompt 08). The
rate limiter and the transactional persistence both live behind injected ports so the rules are
unit-testable without Redis or PostgreSQL; the live asyncpg adapter uses
``Database.request_scope`` (bound to the verified actor) and is BLOCKED here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.contracts import (
    ActorContext,
    EnquiryCreate,
    EnquiryView,
    MessageCreate,
)
from partsiq.core.errors import PartsIQError
from partsiq.core.idempotency import (
    IdempotencyStore,
    canonical_request_hash,
    record_result,
    replay_or_check,
)
from partsiq.core.rate_limit import RateLimitBackend, check_rate_limit

# Fixed route identities for the canonical idempotency hash (prompt 08 step 2). They name the
# operation so the SAME key presented to create vs. append can never collide.
_CREATE_METHOD = "POST"
_CREATE_PATH = "/v1/enquiries"
_MESSAGE_METHOD = "POST"
_MESSAGE_PATH = "/v1/enquiries/{id}/messages"

# Per-identity request quota per fixed window; the API owner may tune these via settings.
CREATE_ENQUIRY_LIMIT = 30
APPEND_MESSAGE_LIMIT = 60
RATE_WINDOW_SECONDS = 60


@runtime_checkable
class IntakeStore(Protocol):
    """Transactional persistence boundary for one intake mutation.

    A concrete asyncpg implementation binds every method to one connection inside the
    transaction opened by :meth:`partsiq.core.db.Database.request_scope` for the verified actor.
    All writes commit together or roll back together — the caller never commits mid-way, so if
    the workflow-job insert fails the enquiry is NOT created (prompt 08 step 4, rollback
    assertion). Tests supply an in-memory fake that mirrors this all-or-nothing behaviour.
    """

    async def create_enquiry_atomic(
        self, actor: ActorContext, command: EnquiryCreate
    ) -> EnquiryView:
        """Insert the enquiry, its first message, the revision snapshot, the durable workflow
        job and the audit row in ONE transaction; return the committed view."""
        ...

    async def lock_current_revision(
        self, actor: ActorContext, enquiry_id: UUID
    ) -> int | None:
        """Lock the enquiry row and return its current revision, or ``None`` if it does not
        exist / is not owned by the actor."""
        ...

    async def append_message_atomic(
        self, actor: ActorContext, enquiry_id: UUID, command: MessageCreate
    ) -> EnquiryView:
        """Append the customer message, bump the revision (invalidating derived results) and
        write the audit row in ONE transaction; return the committed view."""
        ...


async def create_enquiry(
    actor: ActorContext,
    command: EnquiryCreate,
    key: UUID,
    *,
    store: IntakeStore,
    idempotency: IdempotencyStore,
    rate_limiter: RateLimitBackend,
    serialize: "ViewSerializer",
    deserialize: "ViewDeserializer",
) -> EnquiryView:
    """Create an enquiry and its durable workflow job atomically; return the 202-style view.

    Order (prompt 08):
      1. Rate limit the verified actor BEFORE any database write — over the limit is 429, an
         unavailable limiter is a fail-closed 503.
      2. Resolve the idempotency key: an identical replay returns the stored view; the same key
         with a different canonical request is a 409.
      3. Commit the enquiry + first message + revision snapshot + workflow job + audit in ONE
         transaction via the injected store, then persist the idempotency result.

    ``command`` is already a validated :class:`EnquiryCreate` (text 1..12000, locale,
    ``destination_warehouse_id`` > 0); invalid typed input never reaches here (422 at the edge).
    """
    # 1. Fail-closed rate limit first, so a rejected request never performs a durable write.
    await check_rate_limit(
        actor,
        "enquiry.create",
        backend=rate_limiter,
        limit=CREATE_ENQUIRY_LIMIT,
        window_seconds=RATE_WINDOW_SECONDS,
    )

    # 2. Canonical-hash idempotency over method + path + actor + body.
    request_hash = canonical_request_hash(
        method=_CREATE_METHOD, path=_CREATE_PATH, actor=actor, payload=command
    )
    replay = await replay_or_check(actor, key, request_hash, store=idempotency)
    if replay is not None:
        return deserialize(replay)

    # 3. One transaction: enquiry + message + revision snapshot + workflow job + audit.
    view = await store.create_enquiry_atomic(actor, command)
    await record_result(actor, key, request_hash, serialize(view), store=idempotency)
    return view


async def append_message(
    actor: ActorContext,
    enquiry_id: UUID,
    command: MessageCreate,
    key: UUID,
    *,
    store: IntakeStore,
    idempotency: IdempotencyStore,
    rate_limiter: RateLimitBackend,
    serialize: "ViewSerializer",
    deserialize: "ViewDeserializer",
) -> EnquiryView:
    """Append a customer message, enforcing ``expected_revision`` and idempotency.

    The enquiry is locked, its current revision read and compared to ``command.expected_revision``
    (a mismatch is a 409 ``STALE_REVISION``), then a new revision is written — invalidating any
    previously derived results (prompt 08 step 8). A nonexistent / unowned enquiry is a 404.
    """
    await check_rate_limit(
        actor,
        "enquiry.message",
        backend=rate_limiter,
        limit=APPEND_MESSAGE_LIMIT,
        window_seconds=RATE_WINDOW_SECONDS,
    )

    request_hash = canonical_request_hash(
        method=_MESSAGE_METHOD,
        path=_MESSAGE_PATH.replace("{id}", str(enquiry_id)),
        actor=actor,
        payload=command,
    )
    replay = await replay_or_check(actor, key, request_hash, store=idempotency)
    if replay is not None:
        return deserialize(replay)

    # Lock the row and enforce the optimistic revision check inside the transaction boundary.
    current = await store.lock_current_revision(actor, enquiry_id)
    if current is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found or not owned")
    if command.expected_revision != current:
        raise PartsIQError(
            "STALE_REVISION",
            internal_detail=f"expected {command.expected_revision}, current {current}",
        )

    view = await store.append_message_atomic(actor, enquiry_id, command)
    await record_result(actor, key, request_hash, serialize(view), store=idempotency)
    return view


# The idempotency store persists an opaque string result; these adapters (re)build the typed
# view so a replay returns the exact committed resource. The default pair below uses the view's
# own JSON round-trip and is the one the API adapter wires in.
class ViewSerializer(Protocol):
    def __call__(self, view: EnquiryView) -> str: ...


class ViewDeserializer(Protocol):
    def __call__(self, raw: str) -> EnquiryView: ...


def serialize_view(view: EnquiryView) -> str:
    """Default serializer: the view's canonical JSON."""
    return view.model_dump_json()


def deserialize_view(raw: str) -> EnquiryView:
    """Default deserializer: rebuild an :class:`EnquiryView` from its JSON."""
    return EnquiryView.model_validate_json(raw)
