"""Canonical-request-hash idempotency (foundation 08).

Ported and consolidated from ``services/gateway/app/enquiries.py`` (the ``canonical_hash``
plus the same-key/same-payload replay and same-key/different-payload 409 rules). The legacy
gateway hashed only the request body; prompt 08 step 2 widens the canonical identity to the
normalized request JSON together with the HTTP ``method``, ``path`` and the verified actor, so
the SAME ``Idempotency-Key`` presented for two genuinely different operations can never collide.

A replay with the SAME key + SAME canonical request returns the stored result; the SAME key +
a DIFFERENT canonical request raises ``IDEMPOTENCY_MISMATCH`` (409). The stored-result lookup
and the first-writer reservation both live behind an injected :class:`IdempotencyStore` port so
the rule is unit-testable without PostgreSQL. The live asyncpg adapter persists the reservation
in the SAME transaction as the business mutation (prompt 08 step 4) and is BLOCKED here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from .contracts import ActorContext
from .errors import PartsIQError


def canonical_request_hash(
    *, method: str, path: str, actor: ActorContext, payload: BaseModel
) -> str:
    """Stable SHA-256 over the normalized request JSON, method, path and actor.

    The payload is serialised through pydantic's ``model_dump_json`` and re-encoded with sorted
    keys and no insignificant whitespace, so two logically identical requests hash identically
    regardless of key ordering. The verified ``user_id`` (never a request-body actor) scopes the
    hash to its owner — the same key replayed by a different subject cannot match.
    """
    body = json.loads(payload.model_dump_json())
    canonical = {
        "method": method.upper(),
        "path": path,
        "actor": str(actor.user_id),
        "body": body,
    }
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@runtime_checkable
class IdempotencyStore(Protocol):
    """Persistence boundary for idempotency reservations, scoped to one actor + key.

    A concrete asyncpg implementation reads/writes the ``idempotency_keys`` table inside the
    business transaction opened by :meth:`partsiq.core.db.Database.request_scope`. The in-memory
    fake used by tests mirrors the same semantics: a stored row records the request hash and the
    (opaque) serialized result so a later identical replay returns it verbatim.
    """

    async def lookup(self, actor: ActorContext, key: UUID) -> tuple[str, str] | None:
        """Return ``(request_hash, stored_result)`` for ``key``, or ``None`` if unseen."""
        ...

    async def reserve(
        self, actor: ActorContext, key: UUID, request_hash: str, result: str
    ) -> None:
        """Persist the first successful ``(request_hash, result)`` for ``key``."""
        ...


async def replay_or_check(
    actor: ActorContext,
    key: UUID,
    request_hash: str,
    *,
    store: IdempotencyStore,
) -> str | None:
    """Resolve an idempotency key before performing the mutation.

    * No prior row -> return ``None`` (the caller performs the mutation, then calls
      :func:`record_result`).
    * A prior row with the SAME ``request_hash`` -> return the stored result for a verbatim
      replay (the mutation is NOT repeated).
    * A prior row with a DIFFERENT ``request_hash`` -> raise ``IDEMPOTENCY_MISMATCH`` (409):
      the same key was reused for a different payload/operation.
    """
    existing = await store.lookup(actor, key)
    if existing is None:
        return None
    stored_hash, stored_result = existing
    if stored_hash != request_hash:
        raise PartsIQError(
            "IDEMPOTENCY_MISMATCH",
            internal_detail="idempotency key reused with a different canonical request",
        )
    return stored_result


async def record_result(
    actor: ActorContext,
    key: UUID,
    request_hash: str,
    result: str,
    *,
    store: IdempotencyStore,
) -> None:
    """Persist the first-writer result so a later identical replay can return it.

    The live adapter calls this inside the same transaction as the business write; if that
    transaction rolls back, no reservation survives (prompt 08 step 9: no retry of a
    non-idempotent insert outside the transaction wrapper).
    """
    await store.reserve(actor, key, request_hash, result)
