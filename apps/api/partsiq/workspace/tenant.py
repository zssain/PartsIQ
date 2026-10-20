"""One isolated workspace: all operational state for a single scope (ADR 0002).

Scopes:

* ``account`` — the shared workspace of invited Supabase accounts. Customers see their own
  enquiries, reviewers see assigned ones, administrators see all.
* ``demo:<owner>:<session>:<generation>`` — a disposable synthetic workspace created for ONE
  public-demo session generation. Nothing in it is reachable from another session or from the
  account workspace; resetting the session (generation + 1) or letting it expire abandons it.

Isolation is structural: every read and write first resolves the caller's workspace, so a
foreign id is simply absent (404) — there is no cross-workspace query path to get wrong.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from .catalogue import CatalogueContext
from .records import (
    AuditRecord,
    CommandRecord,
    EnquiryRecord,
    ExchangeRecord,
    JobRecord,
    MachineRecord,
    MemberRecord,
    NoteRecord,
    PendingActionRecord,
    RunRecord,
    utcnow,
)


@dataclass
class ImportBatch:
    id: UUID
    filename: str
    format: str
    size_bytes: int
    state: str  # staged | uploaded | validating | validated | invalid | publishing | published | failed
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    rows: list[dict[str, str]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)
    content_sha256: str | None = None
    staged_snapshot: Any = None  # CatalogueSnapshot once validated
    version_id: UUID | None = None
    base_version_id: UUID | None = None
    publish_key: UUID | None = None


@dataclass
class EvalRunRecord:
    id: UUID
    suite: str
    state: str
    created_by: UUID
    created_at: datetime
    dataset_sha256: str = ""
    results: list[Any] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    labelled_set: str = "evals/cases.json"


@dataclass
class CorrectionRecord:
    id: UUID
    enquiry_id: UUID
    revision: int
    author_id: UUID
    field: str
    before: str | None
    after: str | None
    reviewed: bool
    created_at: datetime
    curated_case_id: str | None = None


class PersistingLock:
    """The workspace critical section. In database mode it is also the unit of work.

    On a clean exit every changed aggregate is flushed to PostgreSQL BEFORE the caller can report
    success. If the section raised, or the flush failed, the cache is reloaded from PostgreSQL so
    no partially applied or unsaved change survives in memory (fail closed, never fall back).
    """

    def __init__(self, ws: "Workspace") -> None:
        self._ws = ws
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "PersistingLock":
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        store = self._ws.store
        try:
            if store is None:
                return False
            if exc_type is None:
                try:
                    await store.flush(self._ws)
                except Exception as error:  # noqa: BLE001
                    from partsiq.core.errors import PartsIQError

                    await store.load(self._ws)
                    if isinstance(error, PartsIQError):
                        raise
                    raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"flush failed: {type(error).__name__}") from error
            else:
                await store.load(self._ws)
            return False
        finally:
            self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()


@dataclass
class Workspace:
    key: str
    kind: Literal["account", "demo"]
    catalogue: CatalogueContext
    owner_id: UUID | None = None
    session_id: UUID | None = None
    session_generation: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    last_used: float = field(default_factory=time.monotonic)
    #: PostgreSQL write-through store (account workspace in database mode only).
    store: Any = None
    persisted: dict[str, Any] = field(default_factory=dict)
    lock: Any = field(init=False)
    enquiries: dict[UUID, EnquiryRecord] = field(default_factory=dict)
    runs: dict[UUID, RunRecord] = field(default_factory=dict)
    exchanges: dict[UUID, list[ExchangeRecord]] = field(default_factory=dict)  # run_id -> ordered
    commands: dict[tuple[UUID, UUID], CommandRecord] = field(default_factory=dict)  # (run, key)
    pending: dict[UUID, PendingActionRecord] = field(default_factory=dict)
    audit: list[AuditRecord] = field(default_factory=list)
    jobs: dict[UUID, JobRecord] = field(default_factory=dict)
    notes: dict[UUID, list[NoteRecord]] = field(default_factory=dict)
    machines: dict[UUID, MachineRecord] = field(default_factory=dict)
    members: dict[UUID, MemberRecord] = field(default_factory=dict)
    imports: dict[UUID, ImportBatch] = field(default_factory=dict)
    evaluations: dict[UUID, EvalRunRecord] = field(default_factory=dict)
    corrections: dict[UUID, CorrectionRecord] = field(default_factory=dict)
    idempotency: dict[tuple[str, UUID], tuple[str, Any]] = field(default_factory=dict)
    #: Active background tasks keyed by run id (one at most per run).
    tasks: dict[UUID, asyncio.Task] = field(default_factory=dict)
    audit_seq: int = 0
    #: Server-measured operational samples for analytics (latency per stage, review seconds).
    stage_samples: dict[str, list[float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.lock = PersistingLock(self)

    def touch(self) -> None:
        self.last_used = time.monotonic()

    def append_audit(
        self,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        request_id: UUID,
        enquiry_id: UUID | None = None,
        revision: int | None = None,
        payload: dict[str, str | int | bool | None] | None = None,
    ) -> AuditRecord:
        """Append-only: there is no update or delete path for audit records."""
        self.audit_seq += 1
        record = AuditRecord(
            seq=self.audit_seq,
            actor_type=actor_type,  # type: ignore[arg-type]
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            enquiry_id=enquiry_id,
            revision=revision,
            payload=dict(payload or {}),
            created_at=utcnow(),
        )
        self.audit.append(record)
        return record

    def sample(self, stage: str, value: float) -> None:
        samples = self.stage_samples.setdefault(stage, [])
        samples.append(value)
        if len(samples) > 500:
            del samples[: len(samples) - 500]
