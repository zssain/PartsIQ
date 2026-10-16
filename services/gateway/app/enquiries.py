"""Enquiry and message intake use cases.

Contracts:
    async def create_enquiry(actor, body: EnquiryCreate, key: UUID) -> EnquiryView
    async def add_message(actor, enquiry_id, body: MessageCreate, key: UUID) -> MessageView

Rules (prompt 08):
  * Create enquiry + first message + revision snapshot + workflow start event ATOMICALLY
    (the repository performs the single transaction); the HTTP layer returns 202 only
    after that durable commit, never after an OCR/model call.
  * Idempotency-Key is a UUID: a repeated identical payload returns the existing
    resource; a different payload under the same key is a 409 (IDEMPOTENCY_MISMATCH).
  * A message carries the revision the client last saw; a stale revision is a 409.

Persistence (the atomic transaction + idempotency records) lives behind an injected
repository, so the intake logic is testable without a database.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from partsiq_common.contracts import ActorContext, EnquiryCreate, EnquiryView, MessageCreate, MessageView
from partsiq_common.errors import PartsIQError


def canonical_hash(payload: BaseModel) -> str:
    """Stable hash of a request payload for idempotency comparison."""
    data = json.loads(payload.model_dump_json())
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IdempotentEnquiry:
    payload_hash: str
    view: EnquiryView


@dataclass(frozen=True, slots=True)
class IdempotentMessage:
    payload_hash: str
    view: MessageView


class EnquiryRepo(Protocol):
    async def get_enquiry_idempotent(self, actor: ActorContext, key: UUID) -> IdempotentEnquiry | None: ...

    async def create_enquiry_atomic(
        self, actor: ActorContext, body: EnquiryCreate, key: UUID, payload_hash: str
    ) -> EnquiryView: ...

    async def get_message_idempotent(self, actor: ActorContext, key: UUID) -> IdempotentMessage | None: ...

    async def current_revision(self, actor: ActorContext, enquiry_id: UUID) -> int | None: ...

    async def add_message_atomic(
        self, actor: ActorContext, enquiry_id: UUID, body: MessageCreate, key: UUID, payload_hash: str
    ) -> MessageView: ...


# Returns True when the request is within the rate limit.
RateLimiter = Callable[[str], Awaitable[bool]]


async def create_enquiry(
    actor: ActorContext, body: EnquiryCreate, key: UUID, *, repo: EnquiryRepo, rate_limiter: RateLimiter
) -> EnquiryView:
    if not await rate_limiter(f"enquiry:{actor.user_id}"):
        raise PartsIQError("QUOTA_EXCEEDED", internal_detail="enquiry rate limit")
    payload_hash = canonical_hash(body)
    existing = await repo.get_enquiry_idempotent(actor, key)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise PartsIQError("IDEMPOTENCY_MISMATCH", internal_detail="same key, different payload")
        return existing.view
    return await repo.create_enquiry_atomic(actor, body, key, payload_hash)


async def add_message(
    actor: ActorContext, enquiry_id: UUID, body: MessageCreate, key: UUID, *, repo: EnquiryRepo
) -> MessageView:
    payload_hash = canonical_hash(body)
    existing = await repo.get_message_idempotent(actor, key)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise PartsIQError("IDEMPOTENCY_MISMATCH", internal_detail="same key, different payload")
        return existing.view
    current = await repo.current_revision(actor, enquiry_id)
    if current is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    if body.expected_revision != current:
        raise PartsIQError("STALE_REVISION", internal_detail=f"expected {body.expected_revision}, current {current}")
    return await repo.add_message_atomic(actor, enquiry_id, body, key, payload_hash)
