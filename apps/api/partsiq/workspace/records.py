"""In-process records for one workspace (ADR 0002).

These mirror the committed operational schema (``supabase/migrations``) plus the additive
collaboration tables (``20261020000100_agent_collaboration.sql``): enquiries/items/messages,
drafts/verification, review decisions, assignment/notes, workflow runs, agent exchanges, user
commands, pending actions, audit events and jobs. The workspace runtime is the only writer; all
transitions happen under the workspace lock so concurrent requests observe atomic changes.

Nothing here holds secrets or model hidden reasoning — exchanges store validated, concise
summaries and structured tool outcomes only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from partsiq.core.contracts import (
    MessageView,
    ReplySlots,
    VerificationEvidence,
    VerificationResult,
    VerifiedFacts,
)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


RunMode = Literal["guided", "collaboration"]
RunStatus = Literal[
    "queued",
    "running",
    "pausing",
    "paused",
    "waiting_user",
    "waiting_consent",
    "blocked",
    "awaiting_review",
    "completed",
    "cancelled",
    "failed",
    "superseded",
    "needs_staff",
]
#: Run statuses after which nothing is ever dispatched again for that run.
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset(
    {"awaiting_review", "completed", "cancelled", "failed", "superseded", "needs_staff"}
)
#: Statuses where a run is waiting on a person (customer answer / consent) — resumable by command.
WAITING_RUN_STATUSES: frozenset[str] = frozenset({"waiting_user", "waiting_consent"})


@dataclass
class CandidateRecord:
    """A compatible candidate as returned by the search service (never model-introduced)."""

    part_id: int
    part_number: str
    name_en: str
    name_ar: str
    score: float
    reasons: list[str]
    matched_terms: list[str]
    source_reference: str
    superseded_from: list[str]
    quantity_per_unit: float


@dataclass
class PlanLine:
    warehouse_code: str
    warehouse_id: int
    quantity: int
    transfer_days: int
    observed_at: datetime


@dataclass
class ItemRecord:
    """One requested part line and everything the pipeline derived for it (per revision)."""

    id: UUID
    ordinal: int
    description: str
    quantity: Decimal | None
    quantity_assumed: bool
    model_text: str | None
    serial_text: str | None
    config_code_text: str | None
    part_numbers: list[str]
    status: Literal["unresolved", "needs_information", "ready", "unavailable"] = "unresolved"
    configuration_id: int | None = None
    configuration_label: str | None = None
    identification_note: str | None = None
    clarification_code: str | None = None
    clarification_text: str | None = None
    candidates: list[CandidateRecord] = field(default_factory=list)
    margin: float | None = None
    selected_part_id: int | None = None
    selection_source: str | None = None  # search | customer_choice | reviewer
    quoted_number_note: str | None = None
    plan_strategy: str | None = None
    plan_lines: list[PlanLine] = field(default_factory=list)
    shortage: int = 0
    plan_message: str | None = None


@dataclass
class ProgressEvent:
    """Customer-facing progress step recorded when the step actually executed."""

    step: str
    label: str
    at: datetime
    status: str = "done"  # done | waiting | failed
    detail: str | None = None
    revision: int = 1
    run_id: UUID | None = None


@dataclass
class Decision:
    id: UUID
    kind: Literal["approved", "rejected"]
    revision: int
    actor_id: UUID
    at: datetime
    reason: str | None = None
    message_id: UUID | None = None


@dataclass
class NameplateRecord:
    attachment_id: UUID
    extraction_id: UUID
    model_text: str | None
    serial_text: str | None
    issues: list[str]
    source: str  # fixture | live
    confirmed: bool = False
    confirmed_model: str | None = None
    confirmed_serial: str | None = None


@dataclass
class AttachmentRecord:
    id: UUID
    media_type: str
    size_bytes: int
    status: Literal["pending", "validated", "rejected", "deleted"]
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    error_code: str | None = None
    fixture_key: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    #: Private ``nameplates`` object key (database mode); the worker reads the photo from here.
    storage_key: str | None = None


@dataclass
class EnquiryRecord:
    id: UUID
    owner_id: UUID
    session_id: UUID | None
    session_generation: int | None
    locale: Literal["en", "ar"]
    destination_warehouse_id: int
    created_at: datetime
    updated_at: datetime
    revision: int
    status: str
    language: str
    urgency: str
    messages: list[MessageView] = field(default_factory=list)
    items: list[ItemRecord] = field(default_factory=list)
    attachments: list[AttachmentRecord] = field(default_factory=list)
    nameplate: NameplateRecord | None = None
    catalogue_version_id: UUID | None = None
    priority: Literal["normal", "urgent"] = "normal"
    due_at: datetime | None = None
    assigned_to: UUID | None = None
    mode: RunMode = "guided"
    current_run_id: UUID | None = None
    run_ids: list[UUID] = field(default_factory=list)
    pending_question: str | None = None
    pending_code: str | None = None
    pending_item_id: UUID | None = None
    facts: VerifiedFacts | None = None
    evidence: VerificationEvidence | None = None
    draft_slots: ReplySlots | None = None
    draft_id: UUID | None = None
    draft_rendered: str | None = None
    draft_source: str | None = None  # fixture | live | staff
    verification: VerificationResult | None = None
    verification_id: UUID | None = None
    review_ready_at: datetime | None = None
    decisions: list[Decision] = field(default_factory=list)
    events: list[ProgressEvent] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    idempotency_key: UUID | None = None
    step: str = "intake"
    wait_reason: str | None = None

    def current_decision(self) -> Decision | None:
        for decision in reversed(self.decisions):
            if decision.revision == self.revision:
                return decision
        return None


@dataclass
class RunUsage:
    agent_turns: int = 0
    tool_calls: int = 0
    output_tokens: int = 0
    input_tokens: int = 0
    estimated_usd: Decimal = Decimal("0")
    retries: int = 0
    active_seconds: float = 0.0


@dataclass
class RunRecord:
    id: UUID
    enquiry_id: UUID
    revision: int
    mode: RunMode
    status: str
    control: Literal["active", "pause_requested", "paused", "cancel_requested", "cancelled"]
    execution_source: Literal["fixture", "live"]
    created_by: UUID
    catalogue_version_id: UUID
    session_id: UUID | None
    session_generation: int | None
    limits: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    usage: RunUsage = field(default_factory=RunUsage)
    state_version: int = 1
    fence: int = 0
    in_flight: bool = False
    completed_at: datetime | None = None
    blocked_reason: str | None = None
    terminal_reason: str | None = None
    current_step: str | None = None
    next_seq: int = 1
    #: Collaboration agenda: exchange ids not yet handled by their recipient specialist.
    agenda: list[UUID] = field(default_factory=list)
    #: Controller-owned blackboard (typed tool results) — never model-authored facts.
    board: dict[str, Any] = field(default_factory=dict)
    #: Hashes of already-sent (sender, recipient, kind, content) to stop repeated handoffs.
    seen_signatures: set[str] = field(default_factory=set)
    #: For guided runs: the LangGraph thread id this run checkpoints under.
    thread_id: str | None = None
    #: Monotonic start of the current active slice (for wall-clock accounting).
    active_since: float | None = None
    #: Question raised by the last guided step (transient; re-derived from the record on resume).
    pending_spec: Any = None


@dataclass
class ExchangeRecord:
    id: UUID
    run_id: UUID
    seq: int
    sender: str
    recipient: str | None
    kind: str
    summary: str
    payload: dict[str, Any]
    evidence_refs: list[str]
    source: Literal["fixture", "live", "system", "user"]
    correlation_id: UUID | None
    reply_to: UUID | None
    status: str  # delivered | handled | rejected | waiting | completed | failed | discarded
    created_at: datetime


@dataclass
class CommandRecord:
    id: UUID
    run_id: UUID
    actor_id: UUID
    type: str
    expected_revision: int | None
    expected_state_version: int | None
    idempotency_key: UUID
    payload_hash: str
    payload: dict[str, Any]
    accepted: bool
    result: str
    created_at: datetime


@dataclass
class PendingActionRecord:
    id: UUID
    run_id: UUID
    enquiry_id: UUID
    revision: int
    kind: Literal["clarification", "delegation_consent", "nameplate_confirmation"]
    requested_by: str
    prompt: str
    options: list[dict[str, Any]]
    allowed_resolutions: list[str]
    status: Literal["open", "resolved", "cancelled", "expired"]
    created_at: datetime
    item_id: UUID | None = None
    code: str | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None
    exchange_id: UUID | None = None


@dataclass
class AuditRecord:
    seq: int
    actor_type: Literal["system", "ai", "user"]
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    request_id: UUID
    enquiry_id: UUID | None
    revision: int | None
    payload: dict[str, str | int | bool | None]
    created_at: datetime


@dataclass
class JobRecord:
    id: UUID
    kind: str
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    resource_id: UUID | None
    owner_id: UUID | None
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    error_category: str | None = None
    enquiry_id: UUID | None = None
    revision: int | None = None
    retryable: bool = False


@dataclass
class NoteRecord:
    id: UUID
    enquiry_id: UUID
    author_id: UUID
    body: str
    created_at: datetime


@dataclass
class MachineRecord:
    id: UUID
    owner_id: UUID
    label: str
    model_text: str
    serial_text: str
    created_at: datetime
    archived: bool = False
    idempotency_key: UUID | None = None


@dataclass
class MemberRecord:
    """A workspace member as the admin screen shows it (sandbox persona or directory account)."""

    id: UUID
    email: str | None
    display_name: str
    roles: list[str]
    kind: Literal["you", "persona", "account", "invited"]
    created_at: datetime
    last_sign_in_at: datetime | None = None
    version: int = 1
