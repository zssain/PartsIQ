"""The redacted analytics outbox (foundation 23, F63).

A business mutation writes a redacted ``analytics_outbox`` row in the SAME transaction as the
event it describes (ARCHITECTURE section 6). A SEPARATE export job later ships pending rows to
the reporting sink using an idempotent, fixed ``EVENT_ID`` MERGE and acknowledges a row only
AFTER the remote write succeeds. There is NO distributed transaction spanning the operational
database and the reporting sink.

Invariants enforced here:
  * Appended events are REDACTED to the allowlist (:func:`redact_event`) before they are ever
    stored — identity, raw messages, serials, notes, keys, JWTs and signed URLs never enter an
    analytics row (CONSTRAINTS 17). Only event type, time, demo flag, status, stage, duration,
    tokens and estimated cost are kept.
  * Export is IDEMPOTENT on ``EVENT_ID``: re-exporting the same batch MERGEs the same rows and
    never duplicates them in the sink. A standard primary key is not relied upon to dedupe;
    the writer explicitly MERGEs by ``EVENT_ID``.
  * A row is ACKNOWLEDGED (marked delivered) only AFTER the remote write reports success. A
    crash AFTER the MERGE but BEFORE the acknowledgement simply re-exports the same event on
    the next run — the MERGE makes that a safe no-op (ARCHITECTURE: "ack after remote success").
  * Losing Redis or the reporting sink NEVER loses an event: the durable outbox row is the
    source of truth; nothing is deleted on export, only marked delivered.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import AnalyticsSyncReceipt, AnalyticsSyncView
from partsiq.core.observability import redact_payload

# The ONLY fields permitted to leave the operational database as a redacted analytics event
# (prompt 23 step 6 / CONSTRAINTS 17). Anything else — identity, messages, serials, notes,
# attachments, keys, tokens — is dropped before the row is appended, defence in depth on top
# of redact_payload's secret stripping.
_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "event_type",
        "occurred_at",
        "is_demo",
        "status",
        "stage",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
    }
)


def redact_event(event: Mapping[str, object]) -> dict[str, object]:
    """Reduce a raw event to the redacted analytics allowlist.

    Keeps ONLY the allowlisted reporting fields and drops everything else — identity, message
    text, serials, notes, attachments, keys, JWTs and signed URLs never survive. The allowlist
    is applied FIRST (an innocuous ``input_tokens`` count must not be mistaken for a secret by a
    substring match), then each surviving field is normalised: ``estimated_cost_usd`` to a
    string so a ``Decimal`` transports without precision loss, token counts to ``int`` and the
    demo flag to ``bool``. Surviving string/scalar fields are then passed through
    :func:`redact_payload` for bounding/defence in depth.
    """
    allowed: dict[str, object] = {key: event[key] for key in event if key in _ALLOWED_FIELDS}
    result: dict[str, object] = {}
    for key, value in allowed.items():
        if value is None:
            result[key] = None
        elif key == "estimated_cost_usd":
            result[key] = str(value)
        elif key in ("input_tokens", "output_tokens"):
            result[key] = int(value)  # type: ignore[call-overload]
        elif key == "is_demo":
            result[key] = bool(value)
        else:
            result[key] = value
    # Bound/normalise the remaining string scalars (status, stage, event_type, occurred_at).
    bounded = redact_payload({k: v for k, v in result.items() if isinstance(v, str)})
    result.update(bounded)
    return result


@dataclass(frozen=True, slots=True)
class OutboxRow:
    """One durable, already-redacted analytics event awaiting export."""

    event_id: UUID
    event_type: str
    occurred_at: datetime
    is_demo: bool
    payload: dict[str, object]
    delivered: bool = False


class OutboxStore(Protocol):
    """Durable store for redacted outbox rows (PostgreSQL in production; fake in tests).

    ``append`` participates in the caller's business transaction. ``pending`` /
    ``mark_delivered`` are used by the separate export job.
    """

    def append(self, row: OutboxRow) -> None: ...

    def pending(self, limit: int) -> list[OutboxRow]: ...

    def mark_delivered(self, event_ids: list[UUID]) -> None: ...

    def last_success_at(self) -> datetime | None: ...

    def pending_count(self) -> int: ...


class ReportingSink(Protocol):
    """A remote reporting sink that MERGEs rows idempotently by ``EVENT_ID``.

    Returns an :class:`AnalyticsSyncReceipt`. The implementation is injected
    (:class:`~partsiq.analytics.snowflake.SnowflakeReporter` in production) so the outbox is
    tested with a deterministic fake and live Snowflake stays BLOCKED.
    """

    def merge_events(self, rows: list[OutboxRow]) -> AnalyticsSyncReceipt: ...


@dataclass
class InMemoryOutboxStore:
    """Deterministic in-memory outbox used by unit tests and the fixture path.

    Models the durable PostgreSQL table: appended rows survive until explicitly marked
    delivered. ``append`` dedupes on ``event_id`` so re-appending the same business event (a
    retried mutation) does not create a second row — the same idempotency the remote MERGE
    provides, applied at the source.
    """

    _rows: dict[UUID, OutboxRow] = field(default_factory=dict)
    _last_success_at: datetime | None = None

    def append(self, row: OutboxRow) -> None:
        self._rows.setdefault(row.event_id, row)

    def pending(self, limit: int) -> list[OutboxRow]:
        rows = [row for row in self._rows.values() if not row.delivered]
        rows.sort(key=lambda r: (r.occurred_at, str(r.event_id)))
        return rows[:limit]

    def mark_delivered(self, event_ids: list[UUID]) -> None:
        for event_id in event_ids:
            existing = self._rows.get(event_id)
            if existing is not None and not existing.delivered:
                self._rows[event_id] = OutboxRow(
                    event_id=existing.event_id,
                    event_type=existing.event_type,
                    occurred_at=existing.occurred_at,
                    is_demo=existing.is_demo,
                    payload=existing.payload,
                    delivered=True,
                )

    def record_success(self, when: datetime) -> None:
        self._last_success_at = when

    def last_success_at(self) -> datetime | None:
        return self._last_success_at

    def pending_count(self) -> int:
        return sum(1 for row in self._rows.values() if not row.delivered)


def append_event(
    store: OutboxStore,
    *,
    event_id: UUID,
    event_type: str,
    occurred_at: datetime,
    is_demo: bool,
    event: Mapping[str, object],
) -> OutboxRow:
    """Append a REDACTED analytics event to the outbox (same business transaction as the event).

    The event body is reduced to the reporting allowlist by :func:`redact_event` BEFORE it is
    stored, so an analytics row can never carry identity, message text, a serial, a note, a key
    or a signed URL. The ``event_id`` is the stable idempotency key used by the later MERGE.
    """
    row = OutboxRow(
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        is_demo=is_demo,
        payload=redact_event(event),
    )
    store.append(row)
    return row


def export_events(
    store: OutboxStore,
    sink: ReportingSink,
    *,
    batch_size: int = 100,
    now: datetime | None = None,
) -> AnalyticsSyncReceipt:
    """Export one batch of pending outbox rows to the reporting sink.

    Order of operations (ARCHITECTURE section 6):
      1. Read a bounded batch of undelivered rows (durable source of truth).
      2. MERGE them remotely by ``EVENT_ID`` — idempotent, so a repeat of the same batch is a
         safe no-op in the sink.
      3. Mark the rows delivered ONLY when the remote MERGE reported success. A crash between
         (2) and (3) re-exports the same rows next run; the MERGE dedupes them.

    On a remote failure NOTHING is acknowledged: the rows stay pending for the next run, so
    Snowflake/Redis loss never loses an event. Returns the sink's receipt.
    """
    rows = store.pending(batch_size)
    if not rows:
        return AnalyticsSyncReceipt(run_id=UUID(int=0), row_count=0, query_id=None, succeeded=True)

    receipt = sink.merge_events(rows)
    if receipt.succeeded:
        store.mark_delivered([row.event_id for row in rows])
        if now is not None and hasattr(store, "record_success"):
            store.record_success(now)  # type: ignore[attr-defined]
    return receipt


def sync_view(store: OutboxStore, *, source: str, stale: bool) -> AnalyticsSyncView:
    """Report reporting freshness (``last_success_at``) separately from live counts (F63)."""
    return AnalyticsSyncView(
        last_success_at=store.last_success_at(),
        pending_events=store.pending_count(),
        source=source,  # type: ignore[arg-type]
        stale=stale,
    )


def event_cost(payload: Mapping[str, object]) -> Decimal:
    """Read a redacted event's estimated cost back as a :class:`Decimal` (0 when absent)."""
    raw = payload.get("estimated_cost_usd")
    return Decimal(str(raw)) if raw is not None else Decimal(0)
