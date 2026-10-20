"""Staff review port for the workspace runtime (F36–F50, F67): one implementation for both modes.

Approval is the existing human gate, unchanged in substance:

* the caller must hold ``review.decide`` AND be scoped to the enquiry (assigned reviewer, admin,
  or the owner of the demo sandbox) — otherwise 404, never a hint that the enquiry exists;
* ``expected_revision`` and ``draft_id`` must match the current draft (409 on any change);
* the run that produced the draft must not be cancelled/superseded;
* stock is re-read and the deterministic verification re-run at decision time — a changed plan or
  catalogue blocks the approval (409) instead of publishing stale facts;
* staff prose edits pass the same ``validate_slots`` gate and are re-rendered by code;
* the publication is idempotent on the Idempotency-Key and the enquiry publishes at most one
  recommendation per revision (replays return ``already_applied``);
* every decision appends audit in the same critical section.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from partsiq.auth.actors import actor_kind, require_capability
from partsiq.core.api_models import (
    ApprovalState,
    AssignmentView,
    AuditPage,
    DeadlineView,
    DraftEdit,
    DraftView,
    EnquiryPage,
    InboxQuery,
    NotePage,
    NoteView,
    PageQuery,
    PublishedView,
    ReviewView,
    TraceStage,
    TraceView,
    WorkflowView,
)
from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    AuditEvent,
    EnquiryView,
    MessageView,
    RejectionRequest,
    ReviewResult,
    RevisionRequest,
    VerificationResult,
    WorkflowStep,
)
from partsiq.core.errors import PartsIQError

from . import domain
from .records import TERMINAL_RUN_STATUSES, Decision, NoteRecord, ProgressEvent, utcnow
from .tenant import CorrectionRecord

_TAG = re.compile(r"<[^>]+>")


def plain_text(rendered: str) -> str:
    """Customer message body from the code-rendered (already escaped) HTML reply."""
    text = re.sub(r"</(p|li|div|h\d)>", "\n", rendered)
    text = re.sub(r"<li[^>]*>", "• ", text)
    text = _TAG.sub("", text)
    lines = [html.unescape(line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:12000]


def _cursor(raw: str | None) -> int:
    if raw is None or raw == "":
        return 0
    if not raw.isdigit():
        raise PartsIQError("VALIDATION_FAILED", detail="Invalid cursor.")
    return int(raw)


class ReviewMixin:
    """Mixed into :class:`WorkspaceService`; relies on the runtime's scope helpers."""

    # ------------------------------------------------------------------ inbox / workspace

    async def list_assigned(self, actor: ActorContext, query: InboxQuery) -> EnquiryPage:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        rows = [r for r in ws.enquiries.values() if self._can_review(actor, ws, r)]
        if query.status:
            rows = [r for r in rows if r.status == query.status]
        if query.priority:
            rows = [r for r in rows if r.priority == query.priority]
        if query.overdue:
            now = utcnow()
            rows = [r for r in rows if r.due_at and r.due_at < now and r.status in ("awaiting_review", "processing", "failed")]
        if query.query:
            q = query.query.lower()
            rows = [r for r in rows if q in " ".join(m.body for m in r.messages).lower()]
        rows.sort(key=lambda r: (r.updated_at, r.id), reverse=True)
        start = _cursor(query.cursor)
        page = rows[start: start + query.limit]
        nxt = str(start + query.limit) if start + query.limit < len(rows) else None
        return EnquiryPage(items=[self.view(r) for r in page], next_cursor=nxt)

    async def get_workspace(self, actor: ActorContext, enquiry_id: UUID) -> ReviewView:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        return ReviewView(
            enquiry=self.view(record),
            facts=record.facts,
            draft=record.draft_slots,
            verification=record.verification,
            assigned_to=record.assigned_to,
            draft_id=record.draft_id,
        )

    async def review_detail(self, actor: ActorContext, enquiry_id: UUID) -> dict[str, Any]:
        """Composed review read: enquiry detail + notes + members for assignment + revision history."""
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        detail = await self.enquiry_detail(actor, enquiry_id)
        detail["notes"] = [
            {"id": str(n.id), "author_id": str(n.author_id), "author_label": self._member_label(ws, n.author_id), "body": n.body, "created_at": n.created_at.isoformat()}
            for n in ws.notes.get(record.id, [])
        ]
        detail["reviewers"] = [
            {"id": str(m.id), "label": m.display_name, "roles": m.roles}
            for m in ws.members.values() if any(r in m.roles for r in ("reviewer", "admin"))
        ]
        detail["assigned_label"] = self._member_label(ws, record.assigned_to) if record.assigned_to else None
        detail["revisions"] = sorted({m.revision for m in record.messages})
        detail["decisions"] = [
            {"id": str(d.id), "kind": d.kind, "revision": d.revision, "at": d.at.isoformat(), "reason": d.reason, "actor_label": self._member_label(ws, d.actor_id)}
            for d in record.decisions
        ]
        detail["evidence"] = None if record.evidence is None else {
            "active_catalogue_version_id": str(record.evidence.active_catalogue_version_id),
            "stock": [{"part_id": s.part_id, "warehouse_id": s.warehouse_id, "warehouse_name": ws.catalogue.warehouse_name(s.warehouse_id), "available": str(s.available), "updated_at": s.updated_at.isoformat()} for s in record.evidence.stock],
        }
        detail["review_ready_at"] = record.review_ready_at.isoformat() if record.review_ready_at else None
        detail["can_assign"] = actor_kind(actor) == "demo" or "admin" in actor.roles
        detail["can_decide"] = record.status == "awaiting_review" and record.draft_id is not None
        return detail

    def _member_label(self, ws: Any, member_id: UUID | None) -> str | None:
        if member_id is None:
            return None
        member = ws.members.get(member_id)
        return member.display_name if member else str(member_id)[:8]

    # ------------------------------------------------------------------ decisions

    def _decision_guard(self, ws: Any, record: Any, expected_revision: int) -> None:
        if record.status != "awaiting_review" or record.draft_id is None:
            raise PartsIQError("CONFLICT", detail="This enquiry is not awaiting review.")
        if expected_revision != record.revision:
            raise PartsIQError("STALE_REVISION", detail="The enquiry changed since you opened it. Reload to review the latest revision.")
        run = ws.runs.get(record.current_run_id) if record.current_run_id else None
        if run is not None and run.status in ("cancelled", "superseded"):
            raise PartsIQError("CONFLICT", detail="The run that produced this draft was cancelled or superseded.")

    def _replay(self, ws: Any, scope: str, key: UUID, request_hash: str) -> Any:
        existing = ws.idempotency.get((scope, key))
        if existing is None:
            return None
        stored_hash, result = existing
        if stored_hash != request_hash:
            raise PartsIQError("IDEMPOTENCY_MISMATCH", detail="This idempotency key was used for a different request.")
        return result

    async def approve(self, actor: ActorContext, request: ApprovalRequest, key: UUID) -> ApprovalResult:
        require_capability(actor, "review.decide")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._review_record(actor, ws, request.enquiry_id)
            request_hash = request.model_dump_json()
            replay = self._replay(ws, "approve", key, request_hash)
            if replay is not None:
                return replay.model_copy(update={"already_applied": True})
            decision = record.current_decision()
            if decision is not None and decision.kind == "approved":
                return ApprovalResult(decision_id=decision.id, message_id=decision.message_id or uuid4(), revision=record.revision, already_applied=True)
            self._decision_guard(ws, record, request.expected_revision)
            if request.draft_id != record.draft_id:
                raise PartsIQError("CONFLICT", detail="The draft changed since you opened it. Reload to review the current draft.")
            if record.catalogue_version_id != ws.catalogue.version_id:
                raise PartsIQError("STALE_CATALOGUE", detail="The catalogue changed. Start a new run before approving.")
            if request.edited_slots is not None:
                from partsiq.ai.reply import validate_slots

                validate_slots(request.edited_slots)
                record.draft_slots = request.edited_slots
                record.draft_rendered = domain.render(record, request.edited_slots, ws.catalogue)
                record.draft_source = "staff"
            # Approval-time stock refresh + deterministic re-verification (existing rule).
            result: VerificationResult = domain.verify(record, ws.catalogue)
            record.verification = result
            if not result.passed:
                ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="review.approval_blocked", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"failures": ",".join(f.code for f in result.failures)})
                raise PartsIQError("CONFLICT", detail="Stock or evidence changed and the draft no longer verifies. Start a new run to re-plan.")
            now = utcnow()
            decision_id = uuid4()
            body = plain_text(record.draft_rendered or "")
            message = MessageView(id=uuid4(), enquiry_id=record.id, revision=record.revision, kind="recommendation", body=body or "Approved.", created_at=now)
            if any(m.kind == "recommendation" and m.revision == record.revision for m in record.messages):
                raise PartsIQError("CONFLICT", detail="This revision already has a published reply.")
            record.messages.append(message)
            record.decisions.append(Decision(id=decision_id, kind="approved", revision=record.revision, actor_id=actor.user_id, at=now, message_id=message.id))
            record.status = "approved"
            record.step = "complete"
            record.wait_reason = None
            record.updated_at = now
            for event in record.events:
                if event.step == "review" and event.status == "waiting" and event.revision == record.revision:
                    event.status = "done"
                    event.label = "Reviewed and approved"
            record.events.append(ProgressEvent(step="complete", label="Approved and sent", at=now, status="done", revision=record.revision, run_id=record.current_run_id))
            run = ws.runs.get(record.current_run_id) if record.current_run_id else None
            if run is not None:
                run.status = "completed"
                run.completed_at = now
                run.state_version += 1
                self.executor.emit(ws, run, sender="reviewer", recipient=None, kind="control", summary="A reviewer approved the verified draft; the recommendation was published once.", data={"decision": "approved"}, source="user")
            if record.review_ready_at:
                ws.sample("review_seconds", (now - record.review_ready_at).total_seconds())
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="review.approved", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"decision_id": str(decision_id), "edited": request.edited_slots is not None})
            outcome = ApprovalResult(decision_id=decision_id, message_id=message.id, revision=record.revision, already_applied=False)
            ws.idempotency[("approve", key)] = (request_hash, outcome)
            return outcome

    async def reject(self, actor: ActorContext, request: RejectionRequest, key: UUID) -> ReviewResult:
        require_capability(actor, "review.decide")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._review_record(actor, ws, request.enquiry_id)
            request_hash = request.model_dump_json()
            replay = self._replay(ws, "reject", key, request_hash)
            if replay is not None:
                return replay
            decision = record.current_decision()
            if decision is not None and decision.kind == "rejected":
                return ReviewResult(decision_id=decision.id, revision=record.revision, status="rejected")
            self._decision_guard(ws, record, request.expected_revision)
            now = utcnow()
            decision_id = uuid4()
            record.decisions.append(Decision(id=decision_id, kind="rejected", revision=record.revision, actor_id=actor.user_id, at=now, reason=request.reason))
            record.status = "rejected"
            record.step = "needs_staff"
            record.wait_reason = "A reviewer did not approve this draft. Our staff will follow up."
            record.updated_at = now
            record.events.append(ProgressEvent(step="rejected", label="Returned by reviewer", at=now, status="failed", revision=record.revision, run_id=record.current_run_id))
            run = ws.runs.get(record.current_run_id) if record.current_run_id else None
            if run is not None and run.status not in TERMINAL_RUN_STATUSES | {"awaiting_review"}:
                pass
            if run is not None:
                run.status = "completed"
                run.completed_at = now
                run.state_version += 1
                self.executor.emit(ws, run, sender="reviewer", recipient=None, kind="control", summary="A reviewer rejected the draft; nothing was published.", data={"decision": "rejected"}, source="user")
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="review.rejected", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"decision_id": str(decision_id)})
            outcome = ReviewResult(decision_id=decision_id, revision=record.revision, status="rejected")
            ws.idempotency[("reject", key)] = (request_hash, outcome)
            return outcome

    # ------------------------------------------------------------------ notes / assignment / deadlines

    async def append_note(self, actor: ActorContext, enquiry_id: UUID, body: str, key: UUID) -> NoteView:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._review_record(actor, ws, enquiry_id)
            replay = self._replay(ws, "note", key, body)
            if replay is not None:
                return replay
            note = NoteRecord(id=uuid4(), enquiry_id=record.id, author_id=actor.user_id, body=body[:4000], created_at=utcnow())
            ws.notes.setdefault(record.id, []).append(note)
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="note.added", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={})
            view = NoteView(id=note.id, author_id=note.author_id, body=note.body, created_at=note.created_at)
            ws.idempotency[("note", key)] = (body, view)
            return view

    async def list_notes(self, actor: ActorContext, enquiry_id: UUID, query: PageQuery) -> NotePage:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        notes = ws.notes.get(record.id, [])
        start = _cursor(query.cursor)
        page = notes[start: start + query.limit]
        return NotePage(items=[NoteView(id=n.id, author_id=n.author_id, body=n.body, created_at=n.created_at) for n in page], next_cursor=str(start + query.limit) if start + query.limit < len(notes) else None)

    async def assign(self, actor: ActorContext, enquiry_id: UUID, assignee_id: UUID | None, expected_revision: int, key: UUID) -> AssignmentView:
        require_capability(actor, "admin.assign")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = ws.enquiries.get(enquiry_id)
            if record is None:
                raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
            request_hash = f"{assignee_id}:{expected_revision}"
            replay = self._replay(ws, "assign", key, request_hash)
            if replay is not None:
                return replay
            if expected_revision != record.revision:
                raise PartsIQError("STALE_REVISION", detail="The enquiry changed. Reload before reassigning.")
            if assignee_id is not None:
                member = ws.members.get(assignee_id)
                if member is None or not any(r in member.roles for r in ("reviewer", "admin")):
                    raise PartsIQError("VALIDATION_FAILED", detail="Assign only to a member with a reviewer or admin role.")
            previous = record.assigned_to
            record.assigned_to = assignee_id
            record.updated_at = utcnow()
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="assignment.changed", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"from": str(previous) if previous else None, "to": str(assignee_id) if assignee_id else None})
            view = AssignmentView(enquiry_id=record.id, assigned_to=assignee_id, changed_at=record.updated_at)
            ws.idempotency[("assign", key)] = (request_hash, view)
            return view

    async def deadline(self, actor: ActorContext, enquiry_id: UUID) -> DeadlineView:
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        now = utcnow()
        overdue = bool(record.due_at and record.due_at < now and record.status in ("awaiting_review", "processing", "failed"))
        return DeadlineView(due_at=record.due_at, overdue=overdue, server_time=now)

    async def read_published(self, actor: ActorContext, enquiry_id: UUID) -> PublishedView:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        decision = next((d for d in reversed(record.decisions) if d.kind == "approved"), None)
        message = next((m for m in reversed(record.messages) if m.kind == "recommendation"), None)
        return PublishedView(message=message, decision_id=decision.id if decision else None, approved_revision=decision.revision if decision else None)

    async def list_audit(self, actor: ActorContext, enquiry_id: UUID, query: PageQuery) -> AuditPage:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        rows = [a for a in ws.audit if a.enquiry_id == record.id]
        start = _cursor(query.cursor)
        page = rows[start: start + query.limit]
        return AuditPage(items=[_audit_event(a) for a in page], next_cursor=str(start + query.limit) if start + query.limit < len(rows) else None)

    # ------------------------------------------------------------------ binding / verification / draft edit

    async def read_binding(self, actor: ActorContext, enquiry_id: UUID) -> ApprovalState:
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        decision = record.current_decision()
        previous = next((d for d in reversed(record.decisions) if d.kind == "approved" and d.revision != record.revision), None)
        return ApprovalState(
            revision=record.revision,
            approved=bool(decision and decision.kind == "approved"),
            decision_id=decision.id if decision else None,
            facts_sha256=record.verification.facts_sha256 if record.verification else None,
            invalidated_reason=("A newer revision invalidated the earlier approval." if previous and not decision else None),
        )

    async def read_verification(self, actor: ActorContext, enquiry_id: UUID) -> VerificationResult:
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        if record.verification is None:
            raise PartsIQError("NOT_FOUND", detail="No verification has run for this revision yet.")
        return record.verification

    async def save_slots(self, actor: ActorContext, enquiry_id: UUID, edit: DraftEdit, key: UUID) -> DraftView:
        from partsiq.ai.reply import validate_slots

        require_capability(actor, "review.decide")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._review_record(actor, ws, enquiry_id)
            self._decision_guard(ws, record, edit.expected_revision)
            validate_slots(edit.slots)
            record.draft_slots = edit.slots
            record.draft_rendered = domain.render(record, edit.slots, ws.catalogue)
            record.draft_source = "staff"
            record.draft_id = uuid4()
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="draft.edited", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={})
            return DraftView(revision=record.revision, slots=edit.slots, rendered_preview=record.draft_rendered, verification_passed=bool(record.verification and record.verification.passed))

    async def correct_extraction(self, actor: ActorContext, request: RevisionRequest, key: UUID) -> EnquiryView:
        """Staff correction of extracted details (F38): a new revision, recorded as a correction."""
        require_capability(actor, "review.decide")
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._review_record(actor, ws, request.enquiry_id)
            if request.expected_revision != record.revision:
                raise PartsIQError("STALE_REVISION", detail="The enquiry changed. Reload before correcting.")
            replay = self._replay(ws, "correct", key, request.model_dump_json())
            if replay is not None:
                return replay
            for correction in request.corrections:
                item = next((i for i in record.items if i.id == correction.item_id), None)
                if item is None:
                    raise PartsIQError("VALIDATION_FAILED", detail="Correction references an unknown item.")
                for field_name in ("description", "quantity", "model_text", "serial_text"):
                    value = getattr(correction, field_name)
                    if value is None:
                        continue
                    before = getattr(item, field_name)
                    setattr(item, field_name, value)
                    cid = uuid4()
                    ws.corrections[cid] = CorrectionRecord(id=cid, enquiry_id=record.id, revision=record.revision, author_id=actor.user_id, field=field_name, before=None if before is None else str(before), after=str(value), reviewed=False, created_at=utcnow())
            run = self._new_revision(ws, record, actor, f"Staff correction: {request.reason}"[:2000], kind="status")
            view = self.view(record)
            ws.idempotency[("correct", key)] = (request.model_dump_json(), view)
        await self._settle_if_synchronous(ws, run)
        return self.view(record)

    async def inspect_run(self, actor: ActorContext, enquiry_id: UUID) -> WorkflowView:
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        try:
            step = WorkflowStep(record.step)
        except ValueError:
            step = WorkflowStep.INTAKE
        run = ws.runs.get(record.current_run_id) if record.current_run_id else None
        return WorkflowView(
            enquiry_id=record.id, revision=record.revision, step=step,
            completed_steps=[e.step for e in record.events if e.revision == record.revision and e.status == "done"],
            pending_job_id=run.id if run and run.status not in TERMINAL_RUN_STATUSES else None,
            error_code=run.blocked_reason if run else None,
        )

    async def list_stages(self, actor: ActorContext, enquiry_id: UUID) -> TraceView:
        ws = await self.workspace(actor)
        record = self._review_record(actor, ws, enquiry_id)
        stages = [
            TraceStage(stage=e.step, started_at=e.at, duration_ms=None, status=e.status, error_code=None)
            for e in record.events if e.revision == record.revision
        ]
        return TraceView(enquiry_id=record.id, revision=record.revision, stages=stages)


def _audit_event(a: Any) -> AuditEvent:
    return AuditEvent(
        actor_type=a.actor_type, actor_id=a.actor_id, action=a.action, entity_type=a.entity_type,
        entity_id=a.entity_id, request_id=a.request_id, enquiry_id=a.enquiry_id, revision=a.revision,
        payload=a.payload,
    )


def _ts(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None
