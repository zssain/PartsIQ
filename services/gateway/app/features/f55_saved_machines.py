"""F55 Saved machines (owner: gateway; depends on 07, 19).

A customer may save a confirmed (model, serial) under a free-text label, list their own active
(non-archived) entries, rename the label, and archive an entry (soft delete — referenced
enquiry data is never removed). Saving is idempotent on the request's idempotency key, so a
double submit yields one row; a duplicate label is allowed because identity is the UUID, not
the label.

Crucially, a saved machine stores only IDENTIFIERS (model_id + serial, verbatim) — never a
cached configuration or candidate set. Reusing a saved machine prefills a NEW enquiry and
re-identifies against the CURRENT catalogue, so a stale configuration is never reused as
authoritative (ADR: the database/code decides facts, not a cached guess).

All operations are scoped to the verified actor (and, for a demo, the active session
generation), so a foreign id is denied as NOT_FOUND. The live Postgres adapter is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

MAX_LABEL = 120


class F55Request(Contract):
    label: str
    model_id: int
    serial_text: str
    idempotency_key: UUID


class F55Result(Contract):
    id: UUID
    label: str
    model_id: int
    serial_text: str


@dataclass(frozen=True, slots=True)
class SavedMachine:
    id: UUID
    owner_user_id: UUID | None
    session_id: UUID | None
    session_generation: int | None
    label: str
    model_id: int
    serial_text: str
    archived_at: datetime | None


class SavedMachineRepository(Protocol):
    async def save(self, actor: ActorContext, request: F55Request) -> SavedMachine:
        """Idempotent on request.idempotency_key within the actor's scope."""
        ...

    async def list_active(self, actor: ActorContext) -> list[SavedMachine]: ...

    async def get(self, actor: ActorContext, machine_id: UUID) -> SavedMachine | None:
        """Return None for a machine the actor does not own (foreign id is indistinguishable)."""
        ...

    async def set_label(self, actor: ActorContext, machine_id: UUID, label: str) -> SavedMachine: ...

    async def archive(self, actor: ActorContext, machine_id: UUID) -> None: ...


def _result(machine: SavedMachine) -> F55Result:
    return F55Result(id=machine.id, label=machine.label, model_id=machine.model_id, serial_text=machine.serial_text)


def _validate_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned or len(label) > MAX_LABEL:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="label must be 1..120 non-blank characters")
    return label  # stored verbatim (the user's chosen label, not trimmed)


def _validate_request(request: F55Request) -> None:
    _validate_label(request.label)
    if request.model_id <= 0:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="model_id must be positive")
    if not request.serial_text.strip():
        raise PartsIQError("VALIDATION_FAILED", internal_detail="serial must not be blank")


async def save_machine(actor: ActorContext, request: F55Request, *, repo: SavedMachineRepository) -> F55Result:
    """Save a confirmed (model, serial) under a label; idempotent on the request key."""
    _validate_request(request)
    machine = await repo.save(actor, request)  # serial stored verbatim (leading zeros survive)
    return _result(machine)


async def list_machines(actor: ActorContext, *, repo: SavedMachineRepository) -> list[F55Result]:
    """List the actor's own active (non-archived) saved machines."""
    return [_result(m) for m in await repo.list_active(actor)]


async def rename_machine(
    actor: ActorContext, machine_id: UUID, label: str, *, repo: SavedMachineRepository
) -> F55Result:
    """Update the label only; a foreign id is denied as NOT_FOUND."""
    _validate_label(label)
    if await repo.get(actor, machine_id) is None:
        raise PartsIQError("NOT_FOUND", internal_detail="saved machine not visible to this actor")
    return _result(await repo.set_label(actor, machine_id, label))


async def archive_machine(actor: ActorContext, machine_id: UUID, *, repo: SavedMachineRepository) -> None:
    """Soft-archive (sets archived_at); never deletes referenced enquiry data. Foreign id -> NOT_FOUND."""
    if await repo.get(actor, machine_id) is None:
        raise PartsIQError("NOT_FOUND", internal_detail="saved machine not visible to this actor")
    await repo.archive(actor, machine_id)


def prefill_from_machine(machine: F55Result) -> dict[str, object]:
    """Prefill hints for a NEW enquiry: identifiers only, so the workflow re-identifies against
    the current catalogue. No configuration or candidate set is carried (never authoritative)."""
    return {"model_id": machine.model_id, "serial_text": machine.serial_text, "label": machine.label}
