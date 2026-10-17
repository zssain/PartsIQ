"""F43 Overdue indicators (owner: gateway; depends on 20).

Computes a review deadline from the enquiry's created_at plus a configurable urgent/normal
threshold, and flags overdue ONLY for unresolved states. An approved/rejected/failed enquiry is
never overdue. Every instant is UTC, so a daylight-saving display change can never move the
deadline (the comparison is on tz-aware UTC instants, not local wall-clock). These thresholds
are an internal triage aid, NOT a contractual SLA.

Pure over an injected DeadlineStore; the live enquiries adapter is BLOCKED.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

RESOLVED_STATES = frozenset({"approved", "rejected", "failed"})
_DEFAULT_URGENT_SECONDS = 4 * 3600
_DEFAULT_NORMAL_SECONDS = 24 * 3600


class F43Request(Contract):
    enquiry_id: UUID
    now: datetime


class F43Result(Contract):
    due_at: datetime
    overdue: bool
    age_seconds: int


@dataclass(frozen=True, slots=True)
class DeadlineInput:
    created_at: datetime  # stored UTC
    urgency: str          # "urgent" | "normal"
    status: str


class DeadlineStore(Protocol):
    async def load_deadline_input(self, actor: ActorContext, enquiry_id: UUID) -> DeadlineInput | None: ...


def _threshold_seconds(urgency: str) -> int:
    """Configurable thresholds (env), defaulting to 4h urgent / 24h normal. Not an SLA."""
    key = "OVERDUE_URGENT_SECONDS" if urgency == "urgent" else "OVERDUE_NORMAL_SECONDS"
    default = _DEFAULT_URGENT_SECONDS if urgency == "urgent" else _DEFAULT_NORMAL_SECONDS
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


async def classify_deadline(actor: ActorContext, request: F43Request, *, store: DeadlineStore) -> F43Result:
    """Return the UTC due_at, whether it is overdue (unresolved only) and the enquiry age."""
    data = await store.load_deadline_input(actor, request.enquiry_id)
    if data is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not visible to this actor")
    due_at = data.created_at + timedelta(seconds=_threshold_seconds(data.urgency))
    age_seconds = max(0, int((request.now - data.created_at).total_seconds()))
    overdue = data.status not in RESOLVED_STATES and request.now > due_at
    return F43Result(due_at=due_at, overdue=overdue, age_seconds=age_seconds)


def sort_overdue_first(results: list[F43Result]) -> list[F43Result]:
    """Overdue items first, then by earliest deadline (stable UTC ordering)."""
    return sorted(results, key=lambda r: (not r.overdue, r.due_at))
