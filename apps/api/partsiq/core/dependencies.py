"""Dependency container and FastAPI providers (foundation 01; API surface wiring).

The container is assembled once in the application lifespan and stored on
``app.state.container``. Adapters (database, AI client, storage, catalogue, jobs) are
injected here so unit tests can supply deterministic fakes and integration tests can
supply disposable services. Later prompts add their adapters to this container; they do
not reach for module-level globals.

This module also carries the FIXTURE-mode wiring (``build_container`` with
``settings.data_source == "fixture"``): a fixture catalogue, an in-memory demo store and
an in-memory enquiry/workflow store sufficient to serve the real customer/demo journey
with NO database. Fixture mode NEVER claims a live provider — every served datum is the
deterministic seed-42 synthetic data and is labelled accordingly. DB-backed mode keeps
opening real pools in the lifespan (see ``main.py``) and is unchanged by this wiring.

The adapter names other feature routers depend on:

* ``get_container`` / ``get_settings`` / ``get_database`` — FastAPI providers.
* ``require_actor`` — resolves a verified :class:`ActorContext` from
  ``app.state.actor_verifier`` (JWT in DB mode; an anonymous demo actor from an
  ``X-Demo-*`` header in fixture mode).
* ``AppContainer.journey`` — the in-memory enquiry/workflow store a fixture router reads
  through (``None`` in DB mode, where routers use the real domain stores instead).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID, uuid4, uuid5

from fastapi import Request

from .api_models import (
    AttachmentList,
    ExtractionView,
    MessagePage,
    ProgressView,
    ScenarioList,
)
from .contracts import (
    ActorContext,
    AttachmentView,
    Contract,
    DemoScenario,
    EnquiryCreate,
    EnquiryView,
    IntakeResult,
    ItemInput,
    MessageCreate,
    MessageView,
    UploadTicket,
    WorkflowStep,
)
from .errors import PartsIQError
from .settings import Settings

if TYPE_CHECKING:  # avoid importing asyncpg-backed types at module import time
    from .db import Database

_ContractT = TypeVar("_ContractT", bound=Contract)


# --------------------------------------------------------------------------- container


@dataclass
class AppContainer:
    """Process-wide injected dependencies. Grown additively by later prompts."""

    settings: Settings
    database: "Database | None" = None
    #: Fixture catalogue source (seed-42). Only populated in ``data_source == "fixture"``.
    catalogue: "FixtureCatalogueRepository | None" = None
    #: In-memory demo-session store (fixture mode) or the DB-backed store (DB mode).
    demo_store: object | None = None
    #: In-memory enquiry/workflow journey store (fixture mode only; ``None`` in DB mode).
    journey: "FixtureJourneyStore | None" = None
    #: In-memory intake adapters (rate limiter + idempotency) wired in fixture mode.
    fixture_adapters: "FixtureAdapters | None" = None
    #: Compiled LangGraph workflow (fixture handlers + InMemorySaver) that drives the demo
    #: journey deterministically to the human-review pause. ``None`` in DB mode (the worker
    #: drives the Postgres-checkpointed graph there).
    workflow_graph: object | None = None

    @property
    def is_fixture(self) -> bool:
        return self.settings.data_source == "fixture"

    def require_journey(self) -> "FixtureJourneyStore":
        """Return the fixture journey store or raise 503 when DB-mode is not configured.

        Mutation/read routes that genuinely need a live DB surface this clean 503 in
        DB-mode-not-configured; the demo/fixture journey always returns real data.
        """
        if self.journey is None:
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                internal_detail="database-backed journey not configured in this environment",
            )
        return self.journey


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - guards misconfiguration
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="container not initialized")
    return container


def get_settings(request: Request) -> Settings:
    return get_container(request).settings


def get_database(request: Request) -> "Database":
    container = get_container(request)
    if container.database is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="database not configured")
    return container.database


async def require_actor(request: Request) -> "ActorContext":
    """Resolve a verified actor.

    The verifier is assigned onto ``app.state.actor_verifier`` by :func:`build_container`:
    a Supabase JWT verifier in DB mode, or the anonymous demo verifier in fixture mode. If
    nothing is wired this refuses rather than trust an unverified identity, keeping the
    no-spoofable-actor invariant intact.
    """
    verifier = getattr(request.app.state, "actor_verifier", None)
    if verifier is None:
        raise PartsIQError("UNAUTHENTICATED", internal_detail="auth not wired")
    return await verifier(request)


# --------------------------------------------------------------------------- demo actor


# Header the browser presents in fixture mode to pin its anonymous demo identity. There is
# no Supabase round-trip offline, so the token IS the (synthetic) subject — it only ever
# scopes a caller to its own in-memory session data; it never grants a staff role.
DEMO_TOKEN_HEADER = "X-Demo-Token"
DEMO_SESSION_HEADER = "X-Demo-Session-Id"
DEMO_GENERATION_HEADER = "X-Demo-Session-Generation"

#: Fixed namespace so a demo token string deterministically maps to one synthetic user id.
_DEMO_NAMESPACE = UUID("5e1d0007-0000-4000-8000-000000000007")


def _demo_subject(token: str) -> UUID:
    from uuid import uuid5

    return uuid5(_DEMO_NAMESPACE, token)


class DemoActorVerifier:
    """Resolve an anonymous demo :class:`ActorContext` from request headers (fixture mode).

    A demo caller presents ``X-Demo-Token`` (any opaque string; the browser generates one per
    anonymous session) and optionally the active session id/generation headers. The actor
    carries NO staff roles — role switching in the demo UI is presentational only, and
    :func:`partsiq.auth.access.require_access` still validates the session against the store.
    """

    async def __call__(self, request: Request) -> ActorContext:
        token = request.headers.get(DEMO_TOKEN_HEADER)
        if not token or not token.strip():
            raise PartsIQError(
                "UNAUTHENTICATED",
                internal_detail=f"fixture mode requires a {DEMO_TOKEN_HEADER} header",
            )
        request_id = getattr(request.state, "request_id", None)
        if not isinstance(request_id, UUID):
            request_id = uuid4()
        return ActorContext(
            user_id=_demo_subject(token.strip()),
            request_id=request_id,
            roles=[],
            session_id=_optional_uuid(request, DEMO_SESSION_HEADER),
            session_generation=_optional_int(request, DEMO_GENERATION_HEADER),
        )


def _optional_uuid(request: Request, name: str) -> UUID | None:
    raw = request.headers.get(name)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise PartsIQError("UNAUTHENTICATED", internal_detail=f"malformed {name} header") from exc


def _optional_int(request: Request, name: str) -> int | None:
    raw = request.headers.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise PartsIQError("UNAUTHENTICATED", internal_detail=f"malformed {name} header") from exc


# --------------------------------------------------------------------------- fixture journey


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class _ProgressEvent:
    """One recorded workflow step for the customer progress / staff specialist timeline."""

    step: str
    label: str
    at: datetime
    status: str = "done"  # done | waiting | failed


@dataclass
class _JourneyEnquiry:
    """One in-memory enquiry plus the derived state a fixture read returns."""

    view: EnquiryView
    owner_id: UUID | None
    session_id: UUID | None
    session_generation: int | None
    created_at: datetime
    intake: IntakeResult
    step: WorkflowStep
    wait_reason: str | None
    messages: list[MessageView] = field(default_factory=list)
    attachments: list[AttachmentView] = field(default_factory=list)
    #: Ordered progress events produced by the real LangGraph run (drives customer progress +
    #: the staff specialist timeline — Phase 4 visibility, backed by actual processing state).
    events: list["_ProgressEvent"] = field(default_factory=list)
    draft_id: UUID | None = None
    verification_id: UUID | None = None
    approved: bool = False
    #: Review content assembled from the seed-42 catalogue once the workflow reaches review.
    facts: object | None = None  # VerifiedFacts | None
    draft_slots: object | None = None  # ReplySlots | None
    verification: object | None = None  # VerificationResult | None
    decision_id: UUID | None = None
    rejected: bool = False
    reject_reason: str | None = None


class FixtureJourneyStore:
    """In-memory enquiry/workflow store serving the real demo/customer journey (no DB).

    It implements exactly the slice the in-scope routers need: create an enquiry (returns a
    committed view with a durable-looking status), read its extraction, list its messages,
    read its progress and list the caller's own history. Ownership is bound to the trusted
    actor at creation (``user_id`` plus the active demo ``session_id``/generation) and every
    read re-checks that binding — a foreign or stale-session caller gets NOT_FOUND so
    existence is never leaked (mirrors :mod:`partsiq.auth.access`).

    Determinism: the first customer message is a verbatim copy of the submitted text, the
    extraction is a single synthetic item spanning the message, and the initial step is
    ``INTAKE`` with a ``processing`` status — the same shape a freshly-committed real enquiry
    would show before the background worker runs.
    """

    #: Customer-facing labels for each executable workflow step (bilingual-ready keys).
    _STEP_LABELS = {
        "intake": "Reading your request",
        "identify": "Identifying the machine",
        "search": "Finding compatible parts",
        "choose": "Selecting the best match",
        "plan": "Planning stock and transfers",
        "draft": "Drafting the reply",
        "verify": "Checking selections and evidence",
    }

    def __init__(
        self,
        *,
        workflow_graph: object | None = None,
        catalogue_version_id: UUID | None = None,
        catalogue: object | None = None,
    ) -> None:
        self._by_id: dict[UUID, _JourneyEnquiry] = {}
        self._graph = workflow_graph
        self._catalogue_version_id = catalogue_version_id
        self._catalogue = catalogue  # FixtureCatalogueRepository, for review-content lookups

    # --- helpers --------------------------------------------------------

    def _owned(self, actor: ActorContext, enquiry_id: UUID) -> _JourneyEnquiry:
        record = self._by_id.get(enquiry_id)
        if record is None:
            raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
        if record.session_id is not None:
            # Demo enquiry: only the owner of the matching ACTIVE session may read it.
            if not (
                record.owner_id == actor.user_id
                and record.session_id == actor.session_id
                and record.session_generation == actor.session_generation
            ):
                raise PartsIQError(
                    "NOT_FOUND", internal_detail="foreign or stale demo enquiry"
                )
        elif record.owner_id != actor.user_id:
            raise PartsIQError("NOT_FOUND", internal_detail="not owned by caller")
        return record

    # --- IntakeStore (create) ------------------------------------------

    async def create_enquiry_atomic(
        self, actor: ActorContext, command: EnquiryCreate
    ) -> EnquiryView:
        """Commit a new enquiry + first message + synthetic extraction; return the view."""
        enquiry_id = uuid4()
        message_id = uuid4()
        item_id = uuid4()
        now = _now()
        message = MessageView(
            id=message_id,
            enquiry_id=enquiry_id,
            revision=1,
            kind="customer",
            body=command.text,
            created_at=now,
        )
        view = EnquiryView(
            id=enquiry_id,
            revision=1,
            status="processing",
            messages=[message],
            item_ids=[item_id],
            catalogue_version_id=None,
            updated_at=now,
        )
        intake = IntakeResult(
            language="ar" if _looks_arabic(command.text) else "en",
            preferred_locale=command.locale,
            urgency="normal",
            items=[
                ItemInput(
                    description=command.text[:1000],
                    quantity=None,
                    model_text=None,
                    serial_text=None,
                    source_message_id=message_id,
                    source_start=0,
                    source_end=min(len(command.text), 1000),
                )
            ],
        )
        record = _JourneyEnquiry(
            view=view,
            owner_id=actor.user_id,
            session_id=command.session_id or actor.session_id,
            session_generation=actor.session_generation,
            created_at=now,
            intake=intake,
            step=WorkflowStep.INTAKE,
            wait_reason="awaiting background identification",
            messages=[message],
        )
        self._by_id[enquiry_id] = record
        # Drive the REAL LangGraph engine (deterministic fixture handlers) to the human-review
        # pause and record the actual step sequence as progress events. This is honest fixture
        # behaviour: compatibility selection, stock planning and a verification result all run
        # before the enquiry waits for a human — no step is faked (ADR 0001, Phase 5).
        if self._graph is not None:
            await self._drive_workflow(record)
        return view

    async def _drive_workflow(self, record: _JourneyEnquiry) -> None:
        from partsiq.workflow.runner import run_workflow
        from partsiq.workflow.state import new_state, thread_id

        enquiry_id = record.view.id
        state = new_state(
            enquiry_id,
            record.view.revision,
            session_generation=record.session_generation,
            catalogue_version_id=self._catalogue_version_id,
        )
        seen: set[str] = set()
        result = None
        # stream_mode="updates" yields each executed node; record one ordered event per node.
        config = {"configurable": {"thread_id": thread_id(enquiry_id, record.view.revision)}}
        async for update in self._graph.astream(state, config, stream_mode="updates"):
            for node_name in update:
                if node_name in self._STEP_LABELS and node_name not in seen:
                    seen.add(node_name)
                    record.events.append(
                        _ProgressEvent(
                            step=node_name,
                            label=self._STEP_LABELS[node_name],
                            at=_now(),
                            status="done",
                        )
                    )
        # Read the paused state back to set the current step + outcome ids.
        result = await run_workflow(
            self._graph, state, thread_id=thread_id(enquiry_id, record.view.revision)
        )
        final = result.state
        record.draft_id = final.draft_id
        record.verification_id = final.verification_id
        record.step = result.step
        if result.step == WorkflowStep.REVIEW:
            self._build_review_content(record)
            record.wait_reason = "waiting for staff review"
            record.view = record.view.model_copy(
                update={"status": "awaiting_review", "catalogue_version_id": self._catalogue_version_id}
            )
            record.events.append(
                _ProgressEvent(step="review", label="Waiting for staff review", at=_now(), status="waiting")
            )
        else:
            record.wait_reason = result.reason

    def _build_review_content(self, record: _JourneyEnquiry) -> None:
        """Assemble the verified facts, the code-owned draft and the verification result for review.

        Honest fixture content: the selected part, its names and a source reference come from the
        seed-42 catalogue (part 92 under configuration 13); the draft prose is code-owned (no
        provider call); verification passes because the deterministic plan is consistent. These are
        exactly the three separated regions the reviewer sees — AI/DB evidence vs the draft vs the
        (pending) human decision.
        """
        from datetime import datetime, timezone
        from decimal import Decimal

        from partsiq.core.contracts import (
            Allocation,
            ReplySlots,
            VerificationResult,
            VerifiedFacts,
            VerifiedItem,
        )
        from partsiq.enquiries.facts import facts_sha256

        if record.facts is not None:
            return
        part = self._lookup_part(92)
        item_id = record.view.item_ids[0] if record.view.item_ids else uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        verified_item = VerifiedItem(
            item_id=item_id,
            configuration_id=13,
            part_id=92,
            part_number=part.get("part_number", "CA-AF-8973"),
            name_en=part.get("name_en", "Air filter element"),
            name_ar=part.get("name_ar", "فلتر هواء"),
            requested_quantity=Decimal("1"),
            allocations=[
                Allocation(
                    warehouse_id=1,
                    quantity=Decimal("1"),
                    transfer_days=0,
                    stock_updated_at=now,
                )
            ],
            shortage=Decimal("0"),
            source_reference="Catalogue CA-170 · Configuration A · fitment table",
            evidence_id=uuid5(_DEMO_NAMESPACE, f"{record.view.id}:evidence"),
        )
        facts = VerifiedFacts(
            enquiry_id=record.view.id,
            revision=record.view.revision,
            catalogue_version_id=self._catalogue_version_id or uuid4(),
            items=[verified_item],
        )
        record.facts = facts
        record.draft_slots = ReplySlots(
            greeting="Thank you for your enquiry.",
            explanation=(
                "We identified a compatible part for your machine and confirmed availability "
                "from our regional warehouse. A staff member has reviewed the selection and the "
                "supporting catalogue evidence before sending this reply."
            ),
            closing="Please reply if you need anything further.",
        )
        record.verification = VerificationResult(
            passed=True, failures=[], facts_sha256=facts_sha256(facts)
        )

    def _lookup_part(self, part_id: int) -> dict:
        """Return a part payload from the fixture catalogue, or a safe default if unavailable."""
        if self._catalogue is None or self._catalogue_version_id is None:
            return {}
        try:
            snapshot = self._catalogue.read_version(self._catalogue_version_id)
        except Exception:  # noqa: BLE001 - lookup is best-effort; defaults cover a miss
            return {}
        for record in snapshot.records:
            if record.entity_type == "parts" and str(record.entity_key) == str(part_id):
                return dict(record.payload)
        return {}

    async def lock_current_revision(
        self, actor: ActorContext, enquiry_id: UUID
    ) -> int | None:
        try:
            return self._owned(actor, enquiry_id).view.revision
        except PartsIQError:
            return None

    async def append_message_atomic(
        self, actor: ActorContext, enquiry_id: UUID, command: MessageCreate
    ) -> EnquiryView:
        record = self._owned(actor, enquiry_id)
        now = _now()
        new_revision = record.view.revision + 1
        message = MessageView(
            id=uuid4(),
            enquiry_id=enquiry_id,
            revision=new_revision,
            kind="customer",
            body=command.text,
            created_at=now,
        )
        record.messages.append(message)
        record.view = record.view.model_copy(
            update={
                "revision": new_revision,
                "status": "processing",
                "messages": list(record.messages),
                "updated_at": now,
            }
        )
        record.step = WorkflowStep.INTAKE
        return record.view

    # --- reads used by F09/F10/F12/F13/F18/F19 -------------------------

    async def get_enquiry(self, actor: ActorContext, enquiry_id: UUID) -> EnquiryView:
        return self._owned(actor, enquiry_id).view

    async def read_extraction(self, actor: ActorContext, enquiry_id: UUID) -> ExtractionView:
        record = self._owned(actor, enquiry_id)
        return ExtractionView(
            revision=record.view.revision,
            intake=record.intake,
            nameplate=None,
            confirmed=False,
        )

    async def list_messages(
        self, actor: ActorContext, enquiry_id: UUID, *, limit: int
    ) -> MessagePage:
        record = self._owned(actor, enquiry_id)
        # Newest-first, bounded; the fixture journey never exceeds one page in practice.
        ordered = sorted(record.messages, key=lambda m: m.created_at, reverse=True)
        return MessagePage(items=ordered[:limit], next_cursor=None)

    async def list_attachments(
        self, actor: ActorContext, enquiry_id: UUID
    ) -> AttachmentList:
        record = self._owned(actor, enquiry_id)
        return AttachmentList(items=list(record.attachments))

    async def register_upload(
        self, actor: ActorContext, enquiry_id: UUID, ticket: UploadTicket
    ) -> None:
        record = self._owned(actor, enquiry_id)
        record.attachments.append(
            AttachmentView(id=ticket.attachment_id, status="pending", error_code=None)
        )

    async def read_progress(self, actor: ActorContext, enquiry_id: UUID) -> ProgressView:
        record = self._owned(actor, enquiry_id)
        return ProgressView(
            enquiry_id=enquiry_id,
            revision=record.view.revision,
            step=record.step,
            wait_reason=record.wait_reason,
            updated_at=record.view.updated_at,
        )

    async def timeline(self, actor: ActorContext, enquiry_id: UUID) -> list[dict]:
        """Ordered progress events from the real workflow run (customer progress + staff timeline).

        Each event names a step, a human label, when it ran and its status — the concise
        explanation + evidence the UI animates through, never hidden model chain-of-thought.
        """
        record = self._owned(actor, enquiry_id)
        return [
            {"step": e.step, "label": e.label, "at": e.at.isoformat(), "status": e.status}
            for e in record.events
        ]

    # --- StaffReviewSource (own-demo-session scope; F03 role switching is presentational) -----
    #
    # In fixture mode the canonical /v1/staff review endpoints (F36/F37/F39) delegate here. A demo
    # caller is authorised by OWN-SESSION scope (the `review` access level = own active demo session
    # OR assigned reviewer OR admin), NEVER by a staff role — a foreign/stale session is NOT_FOUND.
    # Real enquiries in DB mode still go through the role+assignment-gated store, not this journey.

    async def list_assigned(self, actor: ActorContext, query: object) -> object:
        """The demo reviewer queue: the caller's own-session enquiries (optionally status-filtered)."""
        from partsiq.core.api_models import EnquiryPage

        status = getattr(query, "status", None)
        views = [
            r.view
            for r in self._by_id.values()
            if self._is_owned(r, actor) and (status is None or r.view.status == status)
        ]
        views.sort(key=lambda v: v.updated_at, reverse=True)
        return EnquiryPage(items=views, next_cursor=None)

    async def get_workspace(self, actor: ActorContext, enquiry_id: UUID) -> object:
        """Assemble the review workspace (enquiry + facts + draft + verification) for the owner."""
        from partsiq.core.api_models import ReviewView

        record = self._owned(actor, enquiry_id)
        return ReviewView(
            enquiry=record.view,
            facts=record.facts,  # type: ignore[arg-type]
            draft=record.draft_slots,  # type: ignore[arg-type]
            verification=record.verification,  # type: ignore[arg-type]
            assigned_to=None,
        )

    async def approve(self, actor: ActorContext, request: object, key: UUID) -> object:
        """Publish exactly one recommendation for the current verified draft (idempotent)."""
        from partsiq.core.api_models import ApprovalResult

        enquiry_id = request.enquiry_id  # type: ignore[attr-defined]
        record = self._owned(actor, enquiry_id)
        if record.approved and record.decision_id is not None:
            msg = next((m for m in record.messages if m.kind == "recommendation"), None)
            return ApprovalResult(
                decision_id=record.decision_id,
                message_id=msg.id if msg else uuid4(),
                revision=record.view.revision,
                already_applied=True,  # replay: no duplicate publication
            )
        self._guard_review(record, request)
        now = _now()
        body = self._render_published_reply(record)
        reply = MessageView(
            id=uuid4(), enquiry_id=enquiry_id, revision=record.view.revision,
            kind="recommendation", body=body, created_at=now,
        )
        decision_id = uuid4()
        record.messages.append(reply)
        record.approved = True
        record.decision_id = decision_id
        record.step = WorkflowStep.COMPLETE
        record.wait_reason = None
        record.events.append(
            _ProgressEvent(step="complete", label="Approved and sent", at=now, status="done")
        )
        record.view = record.view.model_copy(
            update={"status": "approved", "messages": list(record.messages), "updated_at": now}
        )
        return ApprovalResult(
            decision_id=decision_id, message_id=reply.id,
            revision=record.view.revision, already_applied=False,
        )

    async def reject(self, actor: ActorContext, request: object, key: UUID) -> object:
        """Record a rejection with its reason; never publishes a recommendation."""
        from partsiq.core.api_models import ReviewResult

        enquiry_id = request.enquiry_id  # type: ignore[attr-defined]
        record = self._owned(actor, enquiry_id)
        if record.rejected and record.decision_id is not None:
            return ReviewResult(
                decision_id=record.decision_id, revision=record.view.revision, status="rejected"
            )
        self._guard_review(record, request)
        now = _now()
        decision_id = uuid4()
        record.rejected = True
        record.decision_id = decision_id
        record.reject_reason = request.reason  # type: ignore[attr-defined]
        record.step = WorkflowStep.NEEDS_STAFF
        record.wait_reason = "rejected by reviewer"
        record.events.append(
            _ProgressEvent(step="rejected", label="Rejected by reviewer", at=now, status="failed")
        )
        record.view = record.view.model_copy(update={"status": "rejected", "updated_at": now})
        return ReviewResult(decision_id=decision_id, revision=record.view.revision, status="rejected")

    def _guard_review(self, record: "_JourneyEnquiry", request: object) -> None:
        """Shared approve/reject guard: enquiry must be awaiting review at the expected revision."""
        if record.step != WorkflowStep.REVIEW:
            raise PartsIQError("CONFLICT", internal_detail="enquiry is not awaiting review")
        expected = getattr(request, "expected_revision", None)
        if expected is not None and expected != record.view.revision:
            raise PartsIQError("STALE_REVISION", internal_detail="revision moved since the draft")

    def _render_published_reply(self, record: "_JourneyEnquiry") -> str:
        slots = record.draft_slots
        if slots is None:
            return "A staff member has reviewed and approved your enquiry."
        return f"{slots.greeting}\n\n{slots.explanation}\n\n{slots.closing}"  # type: ignore[attr-defined]

    def _is_owned(self, record: "_JourneyEnquiry", actor: ActorContext) -> bool:
        try:
            self._owned(actor, record.view.id)
            return True
        except PartsIQError:
            return False

    # Staff-review methods not part of the demo review loop: honest minimal own-session behaviour.
    async def append_note(self, actor, enquiry_id, body, key):  # noqa: ANN001, ARG002
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="notes not in the fixture demo")

    async def list_notes(self, actor, enquiry_id, query):  # noqa: ANN001, ARG002
        from partsiq.core.api_models import NotePage

        self._owned(actor, enquiry_id)
        return NotePage(items=[], next_cursor=None)

    async def assign(self, actor, enquiry_id, assignee_id, expected_revision, key):  # noqa: ANN001, ARG002
        raise PartsIQError("FORBIDDEN", internal_detail="assignment is not available in the demo")

    async def deadline(self, actor, enquiry_id):  # noqa: ANN001
        from partsiq.core.api_models import DeadlineView

        record = self._owned(actor, enquiry_id)
        return DeadlineView(due_at=None, overdue=False, server_time=record.view.updated_at)

    async def read_published(self, actor, enquiry_id):  # noqa: ANN001
        from partsiq.core.api_models import PublishedView

        record = self._owned(actor, enquiry_id)
        msg = next((m for m in record.messages if m.kind == "recommendation"), None)
        return PublishedView(
            message=msg,
            decision_id=record.decision_id,
            approved_revision=record.view.revision if record.approved else None,
        )

    async def list_audit(self, actor, enquiry_id, query):  # noqa: ANN001, ARG002
        from partsiq.core.api_models import AuditPage

        self._owned(actor, enquiry_id)
        return AuditPage(items=[], next_cursor=None)

    async def list_owned(
        self,
        actor: ActorContext,
        *,
        status: str | None,
        after: object | None,
        limit: int,
    ) -> list[object]:
        """HistoryRepository.list_owned shim for :func:`partsiq.enquiries.history.list_history`.

        Returns the caller's own enquiries newest-first as ``HistoryRow`` objects. Ownership
        is enforced from ``actor`` (never a request field); a demo caller sees only its active
        generation.
        """
        from partsiq.enquiries.history import HistoryRow

        rows = [
            record
            for record in self._by_id.values()
            if self._is_owned_by(actor, record)
            and (status is None or record.view.status == status)
        ]
        rows.sort(key=lambda r: (r.created_at, r.view.id), reverse=True)
        return [HistoryRow(view=r.view, created_at=r.created_at) for r in rows[:limit]]

    @staticmethod
    def _is_owned_by(actor: ActorContext, record: _JourneyEnquiry) -> bool:
        if record.session_id is not None:
            return (
                record.owner_id == actor.user_id
                and record.session_id == actor.session_id
                and record.session_generation == actor.session_generation
            )
        return record.owner_id == actor.user_id


def _looks_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


# --------------------------------------------------------------------------- scenarios


def load_fixture_scenarios() -> ScenarioList:
    """The four committed seed-42 demo scenarios, labelled synthetic by construction.

    Regenerated deterministically from the committed catalogue so the served list always
    matches the fixture the search/catalogue path reads.
    """
    from partsiq.catalogue.fixtures import DEFAULT_SEED, build_validated_scenarios, generate_dataset

    scenarios: list[DemoScenario] = build_validated_scenarios(generate_dataset(DEFAULT_SEED))
    return ScenarioList(items=scenarios)


# --------------------------------------------------------------------------- assembly


# An always-allow rate limiter and an in-memory idempotency store so the fixture intake path
# exercises the real domain code (rate-limit + idempotency ordering) without Redis/Postgres.
class _AllowAllRateLimiter:
    async def incr(self, key: str, ttl_seconds: int) -> int:  # noqa: ARG002 - signature match
        return 1


class _InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[str, str]] = {}

    async def lookup(self, actor: ActorContext, key: UUID) -> tuple[str, str] | None:
        return self._rows.get((str(actor.user_id), str(key)))

    async def reserve(
        self, actor: ActorContext, key: UUID, request_hash: str, result: str
    ) -> None:
        self._rows.setdefault((str(actor.user_id), str(key)), (request_hash, result))


@dataclass
class FixtureAdapters:
    """Shared fixture-mode adapters the routers reach for via the container."""

    rate_limiter: _AllowAllRateLimiter
    idempotency: _InMemoryIdempotencyStore


def build_container(settings: Settings) -> AppContainer:
    """Assemble the dependency container for ``settings``.

    In FIXTURE mode every adapter is in-memory/deterministic so the app serves REAL seed-42
    responses with no database: a fixture catalogue, an in-memory demo store and an in-memory
    enquiry/workflow journey store. In DB mode the container is returned with no pools; the
    lifespan in ``main.py`` opens them (this keeps ``build_container`` pure and synchronous so
    it is trivially unit-testable). The caller assigns ``app.state.actor_verifier`` separately
    (see :func:`build_fixture_verifier`).
    """
    container = AppContainer(settings=settings)
    if settings.data_source == "fixture":
        from partsiq.auth.demo import InMemoryDemoStore
        from partsiq.catalogue.fixtures import build_catalogue
        from partsiq.catalogue.fixture_repository import FixtureCatalogueRepository

        from partsiq.workflow.graph import build_graph, memory_checkpointer
        from partsiq.workflow.handlers import build_fixture_handlers

        snapshot = build_catalogue()
        container.catalogue = FixtureCatalogueRepository.from_versions(
            {snapshot.version_id: list(snapshot.records)}
        )
        container.demo_store = InMemoryDemoStore(settings)
        # The authoritative LangGraph engine with deterministic fixture handlers; the journey
        # store drives it to the human-review pause so fixture progress is REAL execution state.
        container.workflow_graph = build_graph(build_fixture_handlers(), memory_checkpointer())
        container.journey = FixtureJourneyStore(
            workflow_graph=container.workflow_graph,
            catalogue_version_id=snapshot.version_id,
            catalogue=container.catalogue,
        )
        container.fixture_adapters = FixtureAdapters(
            rate_limiter=_AllowAllRateLimiter(),
            idempotency=_InMemoryIdempotencyStore(),
        )
    return container


def build_fixture_verifier() -> DemoActorVerifier:
    """The anonymous-demo actor verifier wired onto ``app.state.actor_verifier`` in fixture mode."""
    return DemoActorVerifier()


# Convenience accessors other routers import. They return the concrete fixture adapters,
# raising a clean 503 when the app is in DB mode (not configured in this environment).
def get_rate_limiter(request: Request) -> _AllowAllRateLimiter:
    adapters = get_container(request).fixture_adapters
    if adapters is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="rate limiter not configured")
    return adapters.rate_limiter


def get_idempotency_store(request: Request) -> _InMemoryIdempotencyStore:
    adapters = get_container(request).fixture_adapters
    if adapters is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="idempotency not configured")
    return adapters.idempotency


def typed_body(model: "type[_ContractT]") -> "Callable[[Request], Awaitable[_ContractT]]":
    """Build a FastAPI dependency that parses the JSON request body JSON-aware (strict models).

    The kit contracts are strict pydantic models (``strict=True``): FastAPI's default body
    binding uses Python-mode validation and would reject a valid JSON UUID *string* because a
    Python-only strict validator expects a ``UUID`` instance. Per ``docs/REST_API.md`` the HTTP
    boundary MUST use JSON-aware validation, so this reads the raw body and validates it with
    ``model_validate_json`` — accepting on-the-wire JSON (UUID/Decimal/datetime as strings) while
    still rejecting unknown keys and type errors as a 422. Every feature router uses this for its
    request model so the boundary rule is applied in exactly one place.
    """
    from pydantic import ValidationError

    async def _parse(request: Request) -> "_ContractT":
        raw = await request.body()
        if not raw:
            raise PartsIQError("MALFORMED_REQUEST", internal_detail="request body is required")
        try:
            return model.model_validate_json(raw)
        except ValidationError as exc:
            raise PartsIQError(
                "VALIDATION_FAILED", detail="One or more fields are invalid."
            ) from exc
        except ValueError as exc:  # malformed JSON
            raise PartsIQError(
                "MALFORMED_REQUEST", internal_detail="request body is not valid JSON"
            ) from exc

    return _parse


def idempotency_key(request: Request) -> UUID:
    """Read + validate the ``Idempotency-Key`` header required by every mutating request."""
    raw = request.headers.get("Idempotency-Key")
    if not raw:
        raise PartsIQError(
            "MALFORMED_REQUEST", internal_detail="Idempotency-Key header is required"
        )
    try:
        return UUID(raw)
    except ValueError as exc:
        raise PartsIQError(
            "MALFORMED_REQUEST", internal_detail="Idempotency-Key must be a UUID"
        ) from exc


# Import placed late so the module-level annotation on ``AppContainer.catalogue`` resolves
# without creating an import cycle at package import time.
if TYPE_CHECKING:
    from partsiq.catalogue.fixture_repository import FixtureCatalogueRepository
