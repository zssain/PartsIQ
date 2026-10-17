"""Persistence port for workflow runs and step outcomes (durable, fenced).

The runner depends on this injected async interface, never on a concrete database. At runtime
an asyncpg-backed adapter (foundation 03 schema: ``workflow_runs`` + ``workflow_step_results``,
keyed by ``enquiry_id`` plus ``revision``) implements it; unit tests inject
:class:`InMemoryWorkflowRepository`, which mirrors the SAME durability and fencing rules so the
loop can be tested offline (persistence itself is BLOCKED — no live DB here).

Durability (F50): each completed step persists exactly one :class:`StepOutcome`; a replay of an
already-recorded step is a no-op that returns the committed outcome, so an interrupted run
resumes from committed results and never repeats a step.

Fencing (F50): a commit is accepted only if the lease token, the enquiry revision AND the demo
session generation still match what they were when the step began. A stale revision or an old
session generation causes the result to be DISCARDED (``commit_step`` returns ``False``), so a
duplicate/expired worker cannot overwrite current data or repeat publication.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import StepOutcome
from partsiq.core.contracts import WorkflowStep


@dataclass(frozen=True, slots=True)
class WorkflowFence:
    """The fence captured when a step begins; rechecked at commit time (F50)."""

    enquiry_id: UUID
    revision: int
    session_generation: int | None
    lease_token: UUID


@dataclass(frozen=True, slots=True)
class RecordedStep:
    """A durably committed step result (one per enquiry/revision/step)."""

    enquiry_id: UUID
    revision: int
    step: WorkflowStep
    input_hash: str
    outcome: StepOutcome


class WorkflowRepository(Protocol):
    """Injected async persistence port. asyncpg at runtime, fake in tests."""

    async def load_recorded(
        self, enquiry_id: UUID, revision: int, step: WorkflowStep
    ) -> RecordedStep | None:
        """Return the committed result for this step, if one exists (durable replay)."""
        ...

    async def current_fence(self, enquiry_id: UUID) -> tuple[int, int | None] | None:
        """Return the enquiry's current ``(revision, session_generation)`` or ``None`` if gone."""
        ...

    async def commit_step(
        self,
        fence: WorkflowFence,
        step: WorkflowStep,
        input_hash: str,
        outcome: StepOutcome,
    ) -> bool:
        """Persist the step result + next state atomically if the fence still holds.

        Returns ``True`` when committed, ``False`` when the result is discarded because the
        revision/generation changed or the lease is no longer valid (F50). An identical
        already-committed step is treated as success (idempotent).
        """
        ...


@dataclass
class InMemoryWorkflowRepository:
    """Deterministic in-memory fake mirroring the fencing/durability contract.

    It is NOT a database and performs no I/O; it exists so the plain runner loop can be
    exercised offline with the same semantics the asyncpg adapter must enforce.
    """

    # The authoritative current fence per enquiry: (revision, session_generation).
    current: dict[UUID, tuple[int, int | None]] = field(default_factory=dict)
    # Committed results keyed by (enquiry_id, revision, step).
    recorded: dict[tuple[UUID, int, WorkflowStep], RecordedStep] = field(default_factory=dict)
    # Audit of rejected (fenced-out) commit attempts — never silently dropped.
    discarded: list[tuple[WorkflowFence, WorkflowStep]] = field(default_factory=list)
    # Valid lease tokens per enquiry; an expired/reclaimed lease is removed to fence it out.
    leases: dict[UUID, UUID] = field(default_factory=dict)

    def set_current(
        self, enquiry_id: UUID, revision: int, session_generation: int | None = None
    ) -> None:
        self.current[enquiry_id] = (revision, session_generation)

    def set_lease(self, enquiry_id: UUID, lease_token: UUID) -> None:
        self.leases[enquiry_id] = lease_token

    async def load_recorded(
        self, enquiry_id: UUID, revision: int, step: WorkflowStep
    ) -> RecordedStep | None:
        return self.recorded.get((enquiry_id, revision, step))

    async def current_fence(self, enquiry_id: UUID) -> tuple[int, int | None] | None:
        return self.current.get(enquiry_id)

    def _fence_holds(self, fence: WorkflowFence) -> bool:
        current = self.current.get(fence.enquiry_id)
        if current is None:
            return False
        current_revision, current_generation = current
        if fence.revision != current_revision:
            return False
        # An old session generation (after a demo reset) is stale and fenced out.
        if (
            fence.session_generation is not None
            and fence.session_generation != current_generation
        ):
            return False
        # The lease must still be the one the enquiry currently recognises.
        active_lease = self.leases.get(fence.enquiry_id)
        if active_lease is not None and active_lease != fence.lease_token:
            return False
        return True

    async def commit_step(
        self,
        fence: WorkflowFence,
        step: WorkflowStep,
        input_hash: str,
        outcome: StepOutcome,
    ) -> bool:
        key = (fence.enquiry_id, fence.revision, step)
        existing = self.recorded.get(key)
        if existing is not None and existing.input_hash == input_hash:
            # Idempotent replay of a completed step: accept without re-writing (durable).
            return True
        if not self._fence_holds(fence):
            # Stale revision / old generation / expired lease: discard and audit (F50).
            self.discarded.append((fence, step))
            return False
        self.recorded[key] = RecordedStep(
            enquiry_id=fence.enquiry_id,
            revision=fence.revision,
            step=step,
            input_hash=input_hash,
            outcome=outcome,
        )
        return True
