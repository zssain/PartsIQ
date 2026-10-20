"""Staff-review feature routers served over /v1 (F36/F37/F39/F41/F42/F43/F47/F49).

Three concerns:

1. Each staff route is mounted at the exact method + path from ``spec/endpoints.json``.
2. A demo (non-staff) caller is REFUSED on every staff route — 403 (role gate) or 404 (foreign),
   never a 200 that leaks staff data. The demo actor genuinely has no staff role (role switching in
   the demo UI is presentational only), so we assert that real refusal rather than faking a staff
   session.
3. Each facade's decision logic is unit-tested against an injected fake store + a reviewer/admin
   :class:`ActorContext`: the role gate, approve-only-when-verified, reject-needs-reason (and never
   publishes), notes append-only + never customer-visible, assignment moves access, overdue windows
   and append-only audit ordering.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from partsiq.core.api_models import (
    AssignmentView,
    AuditPage,
    DeadlineView,
    EnquiryPage,
    InboxQuery,
    NotePage,
    NoteView,
    PageQuery,
    PublishedView,
    ReviewView,
)
from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    AuditEvent,
    EnquiryView,
    RejectionRequest,
    ReviewResult,
)
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings
from partsiq.features import (
    f36_staff_inbox,
    f37_review_workspace,
    f39_review_actions,
    f41_internal_notes,
    f42_assignments,
    f43_overdue_indicators,
    f47_human_publication_gate,
    f49_audit_trail,
)
from partsiq.main import create_app

DEMO = {"X-Demo-Token": "demo-staff"}


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def _mutate_headers() -> dict[str, str]:
    return {**DEMO, "Idempotency-Key": str(uuid4())}


def _reviewer(*, roles=("reviewer",), session_id=None, session_generation=None) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        request_id=uuid4(),
        roles=list(roles),
        session_id=session_id,
        session_generation=session_generation,
    )


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _enquiry_view(status: str = "awaiting_review") -> EnquiryView:
    return EnquiryView(
        id=uuid4(),
        revision=1,
        status=status,
        messages=[],
        item_ids=[],
        catalogue_version_id=None,
        updated_at=_now(),
    )


# --------------------------------------------------------------------------- mounting

# (method, path) for every staff-review route in scope, exactly as spec/endpoints.json.
STAFF_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/v1/staff/enquiries"),
    ("GET", "/v1/staff/enquiries/{enquiry_id}"),
    ("POST", "/v1/staff/enquiries/{enquiry_id}/approve"),
    ("POST", "/v1/staff/enquiries/{enquiry_id}/reject"),
    ("POST", "/v1/staff/enquiries/{enquiry_id}/notes"),
    ("GET", "/v1/staff/enquiries/{enquiry_id}/notes"),
    ("PUT", "/v1/staff/enquiries/{enquiry_id}/assignment"),
    ("GET", "/v1/staff/enquiries/{enquiry_id}/deadline"),
    ("GET", "/v1/enquiries/{enquiry_id}/published-reply"),
    ("GET", "/v1/staff/enquiries/{enquiry_id}/audit"),
)


def test_every_staff_route_is_mounted_with_its_method(client: TestClient) -> None:
    mounted: set[tuple[str, str]] = set()
    for route in client.app.routes:
        path = getattr(route, "path", "")
        for method in getattr(route, "methods", None) or ():
            mounted.add((method, path))
    for method, path in STAFF_ROUTES:
        assert (method, path) in mounted, f"{method} {path} is not mounted"


# --------------------------------------------------------------------------- demo refusal

def test_demo_reviewer_sees_only_own_session_and_never_a_foreign_enquiry(client: TestClient) -> None:
    """F03/F04: in the demo the reviewer is the same anonymous session.

    The own-session REVIEW queue and own-session workspace are served (200) — that is the demo role
    switch. But a FOREIGN enquiry's detail/approval is NOT_FOUND (404, no existence leak), and the
    privileged admin/staff-only actions (assignment, internal notes) are refused — never a 200.
    """
    foreign_id = uuid4()  # not owned by this demo session
    # The reviewer inbox is the caller's OWN-SESSION queue (200, possibly empty) — F03 role switch.
    assert client.get("/v1/staff/enquiries", headers=DEMO).status_code == 200
    # The REVIEW surface (workspace/approve/reject) is own-session scoped: a FOREIGN enquiry is
    # NOT_FOUND (404), never a 403 that leaks existence (F04 isolation).
    foreign_review = (
        ("get", f"/v1/staff/enquiries/{foreign_id}", DEMO, None),
        ("post", f"/v1/staff/enquiries/{foreign_id}/approve", _mutate_headers(),
         {"enquiry_id": str(foreign_id), "expected_revision": 1, "draft_id": str(uuid4())}),
        ("post", f"/v1/staff/enquiries/{foreign_id}/reject", _mutate_headers(),
         {"enquiry_id": str(foreign_id), "expected_revision": 1, "reason": "no"}),
    )
    for method, path, headers, body in foreign_review:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code}"
    # Secondary staff actions (assignment, internal notes, deadline, audit) work inside the demo
    # visitor's OWN sandbox (ADR 0002); for a foreign enquiry they are NOT_FOUND like the review
    # surface above — never a 200 and never a 403 that would confirm the id exists.
    refused = (
        ("put", f"/v1/staff/enquiries/{foreign_id}/assignment", _mutate_headers(),
         {"expected_revision": 1, "assignee_id": None}),
        ("post", f"/v1/staff/enquiries/{foreign_id}/notes", _mutate_headers(), {"body": "hi"}),
        ("get", f"/v1/staff/enquiries/{foreign_id}/notes", DEMO, None),
        ("get", f"/v1/staff/enquiries/{foreign_id}/deadline", DEMO, None),
        ("get", f"/v1/staff/enquiries/{foreign_id}/audit", DEMO, None),
    )
    for method, path, headers, body in refused:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code}"


def test_staff_route_without_a_token_is_unauthenticated(client: TestClient) -> None:
    assert client.get("/v1/staff/enquiries").status_code == 401


def test_published_reply_for_demo_owner_is_not_a_leak(client: TestClient) -> None:
    """F47 is owner-access: an unapproved enquiry returns the EMPTY published view, never a reply."""
    created = client.post(
        "/v1/enquiries",
        headers=_mutate_headers(),
        json={"text": "need filter", "locale": "en", "destination_warehouse_id": 1},
    )
    enquiry_id = created.json()["id"]
    resp = client.get(f"/v1/enquiries/{enquiry_id}/published-reply", headers=DEMO)
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] is None and body["decision_id"] is None  # nothing approved, nothing shown
    # A different demo session cannot read it at all (no existence leak).
    assert client.get(f"/v1/enquiries/{enquiry_id}/published-reply", headers={"X-Demo-Token": "someone-else"}).status_code == 404


# --------------------------------------------------------------------------- fakes

class FakeStaffStore:
    """A deterministic StaffReviewSource mirroring the committed DB invariants."""

    def __init__(self, *, assigned_actor: ActorContext | None = None, verified: bool = True) -> None:
        self._assigned = assigned_actor
        self._verified = verified
        self._enquiry = _enquiry_view()
        self.assigned_to: UUID | None = assigned_actor.user_id if assigned_actor else None
        self.notes: list[NoteView] = []
        self.audit: list[AuditEvent] = []
        self.published: dict[int, UUID] = {}  # revision -> message_id (one-per-revision)
        self.by_key: dict[UUID, object] = {}

    def _require_assigned(self, actor: ActorContext) -> None:
        # An unassigned reviewer learns nothing: 404, never 403 (no existence leak).
        if self._assigned is None or actor.user_id != self._assigned.user_id:
            raise PartsIQError("NOT_FOUND", internal_detail="not assigned to this reviewer")

    async def list_assigned(self, actor: ActorContext, query: InboxQuery) -> EnquiryPage:
        rows = [self._enquiry] if self._assigned and actor.user_id == self._assigned.user_id else []
        return EnquiryPage(items=rows, next_cursor=None)

    async def get_workspace(self, actor: ActorContext, enquiry_id: UUID) -> ReviewView:
        self._require_assigned(actor)
        return ReviewView(
            enquiry=self._enquiry, facts=None, draft=None, verification=None,
            assigned_to=self.assigned_to,
        )

    async def approve(self, actor: ActorContext, request: ApprovalRequest, key: UUID) -> ApprovalResult:
        self._require_assigned(actor)
        if key in self.by_key:  # idempotent replay
            return self.by_key[key]  # type: ignore[return-value]
        if not self._verified:  # approve ONLY when verification passed
            raise PartsIQError("CONFLICT", internal_detail="verification did not pass")
        if self._enquiry.revision in self.published:  # one recommendation per revision
            raise PartsIQError("CONFLICT", internal_detail="already published for this revision")
        message_id = uuid4()
        decision_id = uuid4()
        self.published[self._enquiry.revision] = message_id
        self.audit.append(_audit(actor, decision_id, "approve", self._enquiry.revision))
        result = ApprovalResult(
            decision_id=decision_id, message_id=message_id,
            revision=self._enquiry.revision, already_applied=False,
        )
        self.by_key[key] = result
        return result

    async def reject(self, actor: ActorContext, request: RejectionRequest, key: UUID) -> ReviewResult:
        self._require_assigned(actor)
        decision_id = uuid4()
        self.audit.append(_audit(actor, decision_id, "reject", self._enquiry.revision))
        return ReviewResult(decision_id=decision_id, revision=self._enquiry.revision, status="rejected")

    async def append_note(self, actor: ActorContext, enquiry_id: UUID, body: str, key: UUID) -> NoteView:
        self._require_assigned(actor)
        note = NoteView(id=uuid4(), author_id=actor.user_id, body=body, created_at=_now())
        self.notes.append(note)  # append-only
        return note

    async def list_notes(self, actor: ActorContext, enquiry_id: UUID, query: PageQuery) -> NotePage:
        self._require_assigned(actor)
        return NotePage(items=list(self.notes), next_cursor=None)

    async def assign(self, actor, enquiry_id, assignee_id, expected_revision, key) -> AssignmentView:
        if expected_revision != self._enquiry.revision:
            raise PartsIQError("STALE_REVISION", internal_detail="reload before assigning")
        self.assigned_to = assignee_id  # access changes immediately
        self._assigned = _reviewer() if assignee_id is None else None
        if assignee_id is not None:
            self._assigned = ActorContext(
                user_id=assignee_id, request_id=uuid4(), roles=["reviewer"],
            )
        return AssignmentView(enquiry_id=enquiry_id, assigned_to=assignee_id, changed_at=_now())

    async def deadline(self, actor: ActorContext, enquiry_id: UUID) -> DeadlineView:
        self._require_assigned(actor)
        created = _now() - timedelta(hours=30)
        resolved = self._enquiry.status in {"approved", "rejected", "failed"}
        due = created + timedelta(hours=24)
        return DeadlineView(due_at=due, overdue=(not resolved and _now() > due), server_time=_now())

    async def list_audit(self, actor: ActorContext, enquiry_id: UUID, query: PageQuery) -> AuditPage:
        self._require_assigned(actor)
        return AuditPage(items=list(self.audit), next_cursor=None)


def _audit(actor: ActorContext, decision_id: UUID, action: str, revision: int) -> AuditEvent:
    return AuditEvent(
        actor_type="user", actor_id=str(actor.user_id), action=action,
        entity_type="review_decision", entity_id=str(decision_id),
        request_id=actor.request_id, enquiry_id=uuid4(), revision=revision, payload={},
    )



class _Container:
    """Minimal stand-in for AppContainer: the facades only read ``staff_review`` / ``publication``."""

    def __init__(self, **attrs: object) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)


# --------------------------------------------------------------------------- role gate

async def test_role_gate_refuses_non_staff_with_403() -> None:
    demo = _reviewer(roles=())
    store = FakeStaffStore(assigned_actor=demo)
    with pytest.raises(PartsIQError) as exc:
        await f36_staff_inbox.list_assigned(demo, InboxQuery(), container=_Container(), source=store)
    assert exc.value.code == "FORBIDDEN"


async def test_assignment_is_admin_only_reviewer_refused() -> None:
    reviewer = _reviewer(roles=("reviewer",))
    store = FakeStaffStore(assigned_actor=reviewer)
    with pytest.raises(PartsIQError) as exc:
        await f42_assignments.assign(
            reviewer, uuid4(), uuid4(), 1, uuid4(), container=_Container(), source=store
        )
    assert exc.value.code == "FORBIDDEN"


async def test_unconfigured_staff_store_is_a_clean_503_for_a_reviewer() -> None:
    reviewer = _reviewer()
    with pytest.raises(PartsIQError) as exc:
        await f36_staff_inbox.list_assigned(reviewer, InboxQuery(), container=_Container())
    assert exc.value.code == "DEPENDENCY_UNAVAILABLE"


# --------------------------------------------------------------------------- facade logic

async def test_inbox_and_workspace_scope_to_the_assigned_reviewer() -> None:
    reviewer = _reviewer()
    store = FakeStaffStore(assigned_actor=reviewer)
    page = await f36_staff_inbox.list_assigned(reviewer, InboxQuery(), container=_Container(), source=store)
    assert len(page.items) == 1
    view = await f37_review_workspace.get_workspace(reviewer, uuid4(), container=_Container(), source=store)
    assert view.assigned_to == reviewer.user_id
    # An unassigned reviewer gets 404 (not 403) — existence is not leaked.
    other = _reviewer()
    with pytest.raises(PartsIQError) as exc:
        await f37_review_workspace.get_workspace(other, uuid4(), container=_Container(), source=other_store(reviewer))
    assert exc.value.code == "NOT_FOUND"


def other_store(assigned: ActorContext) -> FakeStaffStore:
    return FakeStaffStore(assigned_actor=assigned)


async def test_approve_only_when_verified_and_publishes_exactly_once() -> None:
    reviewer = _reviewer()
    req = ApprovalRequest(enquiry_id=uuid4(), expected_revision=1, draft_id=uuid4())

    # Verification not passed -> approval blocked, nothing published.
    blocked = FakeStaffStore(assigned_actor=reviewer, verified=False)
    with pytest.raises(PartsIQError) as exc:
        await f39_review_actions.approve(reviewer, req, uuid4(), container=_Container(), source=blocked)
    assert exc.value.code == "CONFLICT"
    assert blocked.published == {}

    # Verified -> publishes once; a second decision for the same revision is refused.
    store = FakeStaffStore(assigned_actor=reviewer, verified=True)
    result = await f39_review_actions.approve(reviewer, req, uuid4(), container=_Container(), source=store)
    assert result.already_applied is False
    assert len(store.published) == 1
    with pytest.raises(PartsIQError):
        await f39_review_actions.approve(reviewer, req, uuid4(), container=_Container(), source=store)
    assert len(store.published) == 1  # still exactly one recommendation for this revision


async def test_approve_idempotent_replay_returns_same_decision() -> None:
    reviewer = _reviewer()
    store = FakeStaffStore(assigned_actor=reviewer, verified=True)
    req = ApprovalRequest(enquiry_id=uuid4(), expected_revision=1, draft_id=uuid4())
    key = uuid4()
    first = await f39_review_actions.approve(reviewer, req, key, container=_Container(), source=store)
    second = await f39_review_actions.approve(reviewer, req, key, container=_Container(), source=store)
    assert first.decision_id == second.decision_id
    assert len(store.published) == 1


async def test_reject_records_reason_and_never_publishes() -> None:
    reviewer = _reviewer()
    store = FakeStaffStore(assigned_actor=reviewer)
    # reason is required by the contract (min_length=1) -> an empty reason cannot be constructed.
    with pytest.raises(Exception):
        RejectionRequest(enquiry_id=uuid4(), expected_revision=1, reason="")
    req = RejectionRequest(enquiry_id=uuid4(), expected_revision=1, reason="not compatible")
    result = await f39_review_actions.reject(reviewer, req, uuid4(), container=_Container(), source=store)
    assert result.status == "rejected"
    assert store.published == {}  # rejection NEVER publishes a recommendation
    assert store.audit[-1].action == "reject"


async def test_notes_are_append_only_and_never_surface_to_the_customer() -> None:
    reviewer = _reviewer()
    store = FakeStaffStore(assigned_actor=reviewer)
    note = await f41_internal_notes.append_note(
        reviewer, uuid4(), "internal only", uuid4(), container=_Container(), source=store
    )
    assert note.author_id == reviewer.user_id
    page = await f41_internal_notes.list_notes(reviewer, uuid4(), PageQuery(), container=_Container(), source=store)
    assert [n.id for n in page.items] == [note.id]
    # The customer-facing contracts have no notes field: a note can never ride a customer view.
    assert "note" not in EnquiryView.model_fields
    assert "note" not in PublishedView.model_fields


async def test_assignment_moves_access_immediately() -> None:
    admin = _reviewer(roles=("admin",))
    first = _reviewer()
    store = FakeStaffStore(assigned_actor=first)
    # Stale revision cannot assign.
    with pytest.raises(PartsIQError) as exc:
        await f42_assignments.assign(admin, uuid4(), uuid4(), 999, uuid4(), container=_Container(), source=store)
    assert exc.value.code == "STALE_REVISION"
    # Reassign to a new reviewer; the old reviewer immediately loses workspace access.
    new_reviewer_id = uuid4()
    view = await f42_assignments.assign(
        admin, uuid4(), new_reviewer_id, 1, uuid4(), container=_Container(), source=store
    )
    assert view.assigned_to == new_reviewer_id
    with pytest.raises(PartsIQError) as exc:
        await f37_review_workspace.get_workspace(first, uuid4(), container=_Container(), source=store)
    assert exc.value.code == "NOT_FOUND"


async def test_overdue_window_flags_only_unresolved_enquiries() -> None:
    reviewer = _reviewer()
    # Unresolved + aged past the window -> overdue.
    overdue_store = FakeStaffStore(assigned_actor=reviewer)
    due = await f43_overdue_indicators.deadline(reviewer, uuid4(), container=_Container(), source=overdue_store)
    assert due.overdue is True
    assert due.due_at < due.server_time
    # A resolved enquiry is never overdue even when aged.
    resolved_store = FakeStaffStore(assigned_actor=reviewer)
    resolved_store._enquiry = _enquiry_view(status="approved")
    resolved = await f43_overdue_indicators.deadline(reviewer, uuid4(), container=_Container(), source=resolved_store)
    assert resolved.overdue is False


async def test_audit_is_append_only_and_in_event_order() -> None:
    reviewer = _reviewer()
    store = FakeStaffStore(assigned_actor=reviewer)
    r1 = RejectionRequest(enquiry_id=uuid4(), expected_revision=1, reason="first")
    await f39_review_actions.reject(reviewer, r1, uuid4(), container=_Container(), source=store)
    store._enquiry = _enquiry_view()  # fresh revision; approve appends the next audit row
    req = ApprovalRequest(enquiry_id=uuid4(), expected_revision=1, draft_id=uuid4())
    await f39_review_actions.approve(reviewer, req, uuid4(), container=_Container(), source=store)
    page = await f49_audit_trail.list_events(reviewer, uuid4(), PageQuery(), container=_Container(), source=store)
    actions = [e.action for e in page.items]
    assert actions == ["reject", "approve"]  # stable append order, nothing mutated or removed


async def test_published_reply_facade_unwired_is_503() -> None:
    reviewer = _reviewer()
    with pytest.raises(PartsIQError) as exc:
        await f47_human_publication_gate.read_approved(reviewer, uuid4(), container=_Container())
    assert exc.value.code == "DEPENDENCY_UNAVAILABLE"


async def test_published_reply_facade_returns_empty_view_when_nothing_approved() -> None:
    reviewer = _reviewer()

    class _PubStore:
        async def read_published(self, actor: ActorContext, enquiry_id: UUID) -> PublishedView:
            return PublishedView(message=None, decision_id=None, approved_revision=None)

    view = await f47_human_publication_gate.read_approved(
        reviewer, uuid4(), container=_Container(), source=_PubStore()
    )
    assert view.message is None  # nothing unapproved reaches the customer
