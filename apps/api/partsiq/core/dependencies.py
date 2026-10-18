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
from uuid import UUID, uuid4

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

    def __init__(self) -> None:
        self._by_id: dict[UUID, _JourneyEnquiry] = {}

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
        self._by_id[enquiry_id] = _JourneyEnquiry(
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
        return view

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

        snapshot = build_catalogue()
        container.catalogue = FixtureCatalogueRepository.from_versions(
            {snapshot.version_id: list(snapshot.records)}
        )
        container.demo_store = InMemoryDemoStore(settings)
        container.journey = FixtureJourneyStore()
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
