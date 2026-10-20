"""The workspace runtime: the single application-state service behind the /v1 API (ADR 0002).

It replaces the earlier in-memory demo journey with one coherent implementation of the existing
ports — the intake store (F09–F19), the staff review source (F36–F49), and the ops/admin ports
(F51–F65) — plus the run/collaboration contracts. Every method:

1. resolves the caller's WORKSPACE from the verified actor (demo session sandbox or the account
   workspace) — a foreign id is simply absent, so it is reported 404 without leaking existence;
2. checks the resource scope (owner / assigned reviewer / administrator) and the server-granted
   capability (:mod:`partsiq.auth.actors`);
3. performs the change atomically under the workspace lock and appends audit for every
   administrative or decision change.

Runs are advanced by :class:`~partsiq.workspace.runner.RunExecutor` in background tasks.
"""
from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from partsiq.auth.actors import actor_kind, has_capability, require_capability
from partsiq.core.api_models import (
    AttachmentList,
    ExtractionView,
    MessagePage,
    ProgressView,
)
from partsiq.core.contracts import (
    ActorContext,
    AttachmentView,
    EnquiryCreate,
    EnquiryView,
    IntakeResult,
    ItemInput,
    MessageCreate,
    MessageView,
    NameplateResult,
    UploadTicket,
    WorkflowStep,
)
from partsiq.core.errors import PartsIQError

from . import collaboration as collab
from .catalogue import CatalogueContext, fixture_catalogue_context
from .language import FixtureLanguage, LanguageProvider, LiveLanguage, live_available
from .limits import RunBudget, RunLimits, global_ledger
from .records import (
    TERMINAL_RUN_STATUSES,
    WAITING_RUN_STATUSES,
    AttachmentRecord,
    CommandRecord,
    EnquiryRecord,
    MemberRecord,
    PendingActionRecord,
    ProgressEvent,
    RunRecord,
    utcnow,
)
from .runner import RunExecutor
from .steps import Pipeline, apply_answer, reset_derived
from .tenant import Workspace

logger = logging.getLogger("partsiq.workspace")

#: Execution mode requested by the HTTP create route (query ``mode``), read by create_enquiry_atomic.
requested_mode: contextvars.ContextVar[str] = contextvars.ContextVar("requested_mode", default="guided")

ACCOUNT_KEY = "account"
DEMO_MAX_ENQUIRIES = 60
COMMAND_TYPES = frozenset({
    "pause", "resume", "cancel", "instruct", "answer", "confirm_nameplate", "resolve_delegation", "fixture_replay",
})
_FACTUAL = re.compile(r"\b(serial|s/n|model|qty|quantity|part\s*(no|number))\b|\d{4,}|رقم|موديل|الكمية", re.IGNORECASE)


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class WorkspaceRuntime:
    """Process-wide registry of workspaces plus the run executor."""

    def __init__(self, *, settings: Any, snapshot_factory: Any, demo_store: Any = None, directory: Any = None, live_client: Any = None) -> None:
        self.settings = settings
        self._snapshot_factory = snapshot_factory  # () -> CatalogueSnapshot (validated seed)
        self._demo_store = demo_store
        self.directory = directory  # AccountDirectory | None (Supabase admin) for real accounts
        self._live_client = live_client
        self._ledger = global_ledger(settings)
        self.limits = RunLimits.from_settings(settings)
        self._workspaces: "OrderedDict[str, Workspace]" = OrderedDict()
        self._registry_lock = asyncio.Lock()
        self.executor = RunExecutor(
            settings=settings,
            pipeline_for=self._pipeline_for,
            specialists_for=self._specialists_for,
            step_delay_ms=settings.fixture_step_delay_ms,
        )
        self._account_ws: Workspace | None = None

    # ================================================================== workspaces

    def _new_catalogue(self) -> CatalogueContext:
        return fixture_catalogue_context(self._snapshot_factory())

    @property
    def account_workspace(self) -> Workspace:
        if self._account_ws is None:
            self._account_ws = Workspace(key=ACCOUNT_KEY, kind="account", catalogue=self._new_catalogue())
        return self._account_ws

    async def workspace(self, actor: ActorContext) -> Workspace:
        """Resolve the caller's workspace. Demo callers get their own session-generation sandbox."""
        if actor_kind(actor) == "account":
            ws = self.account_workspace
            ws.touch()
            return ws
        if actor.session_id is None or actor.session_generation is None:
            raise PartsIQError("NOT_FOUND", internal_detail="demo caller without an active session")
        if self._demo_store is not None and hasattr(self._demo_store, "is_current"):
            if not await self._demo_store.is_current(actor.user_id, actor.session_id, actor.session_generation):
                raise PartsIQError("NOT_FOUND", internal_detail="demo session reset or expired")
        key = f"demo:{actor.user_id}:{actor.session_id}:{actor.session_generation}"
        async with self._registry_lock:
            ws = self._workspaces.get(key)
            if ws is None:
                ws = Workspace(
                    key=key, kind="demo", catalogue=self._new_catalogue(), owner_id=actor.user_id,
                    session_id=actor.session_id, session_generation=actor.session_generation,
                )
                self._seed_demo_members(ws, actor)
                self._workspaces[key] = ws
                self._evict()
            self._workspaces.move_to_end(key)
        ws.touch()
        return ws

    def _evict(self) -> None:
        while len(self._workspaces) > self.settings.demo_max_workspaces:
            _key, old = self._workspaces.popitem(last=False)
            self._abandon(old)

    def _abandon(self, ws: Workspace) -> None:
        for run in ws.runs.values():
            self.executor.fence(run)
            if run.status not in TERMINAL_RUN_STATUSES:
                run.status = "cancelled"
                run.control = "cancelled"
                run.terminal_reason = "The demo session was reset or expired."
        for task in ws.tasks.values():
            task.cancel()

    async def reset_demo(self, actor: ActorContext, old_generation: int | None) -> None:
        """Abandon the previous generation's sandbox (called after the store bumps generation)."""
        prefix = f"demo:{actor.user_id}:"
        async with self._registry_lock:
            for key in [k for k in self._workspaces if k.startswith(prefix)]:
                ws = self._workspaces[key]
                if old_generation is None or ws.session_generation == old_generation:
                    self._abandon(ws)
                    del self._workspaces[key]

    def _seed_demo_members(self, ws: Workspace, actor: ActorContext) -> None:
        now = utcnow()
        ws.members[actor.user_id] = MemberRecord(actor.user_id, None, "You (demo visitor)", ["reviewer", "catalogue_admin", "admin"], "you", now)
        for name, roles in (("Amal (synthetic reviewer)", ["reviewer"]), ("Omar (synthetic catalogue admin)", ["catalogue_admin"])):
            member_id = uuid4()
            ws.members[member_id] = MemberRecord(member_id, None, name, roles, "persona", now)

    def demo_workspace_count(self) -> int:
        return len(self._workspaces)

    # ================================================================== providers

    def _pipeline_for(self, ws: Workspace, run: RunRecord) -> Pipeline:
        return Pipeline(ws.catalogue, self._language_for(run))

    def _language_for(self, run: RunRecord) -> LanguageProvider:
        if run.execution_source == "live":
            budget = RunBudget(ledger=self._ledger, model=self.settings.openai_text_model, limits=self.limits, usage=run.usage)
            return LiveLanguage(client=self._live_client, text_model=self.settings.openai_text_model, allowance=budget)
        return FixtureLanguage()

    def _specialists_for(self, ws: Workspace, run: RunRecord) -> dict[str, collab.Specialist]:
        if run.execution_source == "live":
            from .live_specialists import live_specialists

            budget = RunBudget(ledger=self._ledger, model=self.settings.openai_text_model, limits=self.limits, usage=run.usage)
            return live_specialists(client=self._live_client, model=self.settings.openai_text_model, budget=budget, limits=self.limits)
        return collab.fixture_specialists()

    def execution_status(self) -> dict[str, Any]:
        ok, reason = live_available(self.settings)
        return {
            "data_source": self.settings.data_source,
            "ai_mode": self.settings.ai_mode,
            "live_available": ok and self._live_client is not None,
            "live_unavailable_reason": reason if not ok else (None if self._live_client is not None else "No live client is configured."),
            "collaboration_enabled": self.settings.collaboration_enabled,
            "demo_enabled": self.settings.demo_enabled,
            "accounts_enabled": bool(self.settings.supabase_url),
        }

    # ================================================================== access

    def _is_admin(self, actor: ActorContext) -> bool:
        return actor_kind(actor) == "demo" or "admin" in actor.roles

    def _can_read(self, actor: ActorContext, ws: Workspace, record: EnquiryRecord) -> bool:
        if ws.kind == "demo":
            return True
        if record.owner_id == actor.user_id:
            return True
        return self._can_review(actor, ws, record)

    def _can_review(self, actor: ActorContext, ws: Workspace, record: EnquiryRecord) -> bool:
        if ws.kind == "demo":
            return True
        if "admin" in actor.roles:
            return True
        return "reviewer" in actor.roles and record.assigned_to == actor.user_id

    def _record(self, actor: ActorContext, ws: Workspace, enquiry_id: UUID) -> EnquiryRecord:
        record = ws.enquiries.get(enquiry_id)
        if record is None or not self._can_read(actor, ws, record):
            raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found in caller scope")
        return record

    def _review_record(self, actor: ActorContext, ws: Workspace, enquiry_id: UUID) -> EnquiryRecord:
        record = ws.enquiries.get(enquiry_id)
        if record is None or not self._can_review(actor, ws, record):
            raise PartsIQError("NOT_FOUND", internal_detail="enquiry not reviewable by caller")
        return record

    def _run(self, actor: ActorContext, ws: Workspace, run_id: UUID) -> tuple[RunRecord, EnquiryRecord]:
        run = ws.runs.get(run_id)
        if run is None:
            raise PartsIQError("NOT_FOUND", internal_detail="run not found")
        return run, self._record(actor, ws, run.enquiry_id)

    def _can_control(self, actor: ActorContext, ws: Workspace, record: EnquiryRecord) -> bool:
        if ws.kind == "demo":
            return True
        if record.owner_id == actor.user_id:
            return True
        return self._can_review(actor, ws, record)

    # ================================================================== views

    def view(self, record: EnquiryRecord) -> EnquiryView:
        return EnquiryView(
            id=record.id,
            revision=record.revision,
            status=record.status,  # type: ignore[arg-type]
            messages=list(record.messages),
            item_ids=[i.id for i in record.items],
            catalogue_version_id=record.catalogue_version_id,
            updated_at=record.updated_at,
        )

    # ================================================================== intake store (F09–F19)

    async def create_enquiry_atomic(self, actor: ActorContext, command: EnquiryCreate) -> EnquiryView:
        ws = await self.workspace(actor)
        require_capability(actor, "enquiry.create")
        mode = requested_mode.get()
        if mode not in ("guided", "collaboration"):
            raise PartsIQError("VALIDATION_FAILED", detail="Unsupported execution mode.")
        if mode == "collaboration" and not self.settings.collaboration_enabled:
            raise PartsIQError("FORBIDDEN", detail="Agent collaboration is disabled on this server.")
        if ws.catalogue.warehouse_code(command.destination_warehouse_id) is None:
            raise PartsIQError("VALIDATION_FAILED", detail="Unsupported destination warehouse.")
        async with ws.lock:
            if ws.kind == "demo" and len(ws.enquiries) >= DEMO_MAX_ENQUIRIES:
                raise PartsIQError("QUOTA_EXCEEDED", detail="This demo session holds the maximum number of enquiries. Reset the demo to start again.")
            self._check_concurrency(ws)
            now = utcnow()
            enquiry_id = uuid4()
            message = MessageView(id=uuid4(), enquiry_id=enquiry_id, revision=1, kind="customer", body=command.text, created_at=now)
            record = EnquiryRecord(
                id=enquiry_id, owner_id=actor.user_id, session_id=actor.session_id if ws.kind == "demo" else None,
                session_generation=actor.session_generation if ws.kind == "demo" else None,
                locale=command.locale, destination_warehouse_id=command.destination_warehouse_id,
                created_at=now, updated_at=now, revision=1, status="processing",
                language="en", urgency="normal", messages=[message], mode=mode,  # type: ignore[arg-type]
                catalogue_version_id=ws.catalogue.version_id, due_at=now + timedelta(hours=24),
            )
            ws.enquiries[enquiry_id] = record
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="enquiry.created", entity_type="enquiry", entity_id=str(enquiry_id), request_id=actor.request_id, enquiry_id=enquiry_id, revision=1, payload={"mode": mode})
            run = self._start_run(ws, record, actor, mode)
        await self._settle_if_synchronous(ws, run)
        return self.view(record)

    def _check_concurrency(self, ws: Workspace) -> None:
        active = [r for r in ws.runs.values() if r.status in ("queued", "running", "pausing")]
        if len(active) >= self.limits.max_concurrent_per_scope:
            raise PartsIQError("QUOTA_EXCEEDED", detail="Too many runs are active in this workspace. Wait for one to finish or pause it.")

    def _start_run(self, ws: Workspace, record: EnquiryRecord, actor: ActorContext, mode: str, *, source: str | None = None, carried_from: UUID | None = None) -> RunRecord:
        if source is None:
            ok, _reason = live_available(self.settings)
            source = "live" if ok and self._live_client is not None else "fixture"
        now = utcnow()
        for existing_id in record.run_ids:
            existing = ws.runs.get(existing_id)
            if existing is not None and existing.status not in TERMINAL_RUN_STATUSES and existing.revision != record.revision:
                self.executor.fence(existing)
                existing.status = "superseded"
                existing.terminal_reason = f"Superseded by revision {record.revision}."
                existing.completed_at = now
                existing.state_version += 1
                for pending in ws.pending.values():
                    if pending.run_id == existing.id and pending.status == "open":
                        pending.status = "cancelled"
        record.step = "intake"
        run = RunRecord(
            id=uuid4(), enquiry_id=record.id, revision=record.revision, mode=mode,  # type: ignore[arg-type]
            status="queued", control="active", execution_source=source,  # type: ignore[arg-type]
            created_by=actor.user_id, catalogue_version_id=ws.catalogue.version_id,
            session_id=record.session_id, session_generation=record.session_generation,
            limits=self.limits.as_dict(), created_at=now, updated_at=now,
            thread_id=f"enquiry:{record.id}:rev:{record.revision}:run:{uuid4().hex[:8]}",
        )
        if carried_from is not None:
            run.board["carried_from"] = str(carried_from)
        ws.runs[run.id] = run
        record.run_ids.append(run.id)
        record.current_run_id = run.id
        record.mode = mode  # type: ignore[assignment]
        record.status = "processing"
        record.wait_reason = None
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="run.started", entity_type="run", entity_id=str(run.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"mode": mode, "source": source})
        self.executor.schedule(ws, run)
        return run

    async def _settle_if_synchronous(self, ws: Workspace, run: RunRecord) -> None:
        """With no pacing configured (tests/CI), finish the run before responding (bounded)."""
        if self.settings.fixture_step_delay_ms == 0 and run.execution_source == "fixture":
            try:
                await self.executor.wait_idle(ws, run.id, timeout=10)
            except asyncio.TimeoutError:  # pragma: no cover - defensive
                pass

    async def lock_current_revision(self, actor: ActorContext, enquiry_id: UUID) -> int | None:
        try:
            ws = await self.workspace(actor)
            return self._record(actor, ws, enquiry_id).revision
        except PartsIQError:
            return None

    async def append_message_atomic(self, actor: ActorContext, enquiry_id: UUID, command: MessageCreate) -> EnquiryView:
        """A customer message is new factual input: new revision, fresh run, stale drafts dropped."""
        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._record(actor, ws, enquiry_id)
            if record.owner_id != actor.user_id and ws.kind != "demo":
                raise PartsIQError("FORBIDDEN", detail="Only the customer can add messages to this enquiry.")
            if record.status == "approved":
                raise PartsIQError("CONFLICT", detail="This enquiry is already answered. Start a new enquiry or repeat it.")
            if record.pending_code is not None and record.pending_item_id is not None:
                try:
                    apply_answer(record, command.text, ws.catalogue)
                except PartsIQError as exc:
                    if exc.code != "VALIDATION_FAILED":
                        raise
            run = self._new_revision(ws, record, actor, command.text, kind="customer")
        await self._settle_if_synchronous(ws, run)
        return self.view(record)

    def _new_revision(self, ws: Workspace, record: EnquiryRecord, actor: ActorContext, text: str, *, kind: str) -> RunRecord:
        previous = record.current_run_id
        now = utcnow()
        record.revision += 1
        record.messages.append(MessageView(id=uuid4(), enquiry_id=record.id, revision=record.revision, kind=kind, body=text, created_at=now))  # type: ignore[arg-type]
        reset_derived(record)
        record.updated_at = now
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="enquiry.revised", entity_type="enquiry", entity_id=str(record.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={})
        source = ws.runs[previous].execution_source if previous in ws.runs else None
        return self._start_run(ws, record, actor, record.mode, source=source, carried_from=previous)

    async def get_enquiry(self, actor: ActorContext, enquiry_id: UUID) -> EnquiryView:
        ws = await self.workspace(actor)
        return self.view(self._record(actor, ws, enquiry_id))

    async def read_extraction(self, actor: ActorContext, enquiry_id: UUID) -> ExtractionView:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        intake = None
        if record.items and record.messages:
            first = record.messages[0]
            intake = IntakeResult(
                language=record.language if record.language in ("en", "ar", "mixed") else "en",  # type: ignore[arg-type]
                preferred_locale=record.locale,
                urgency=record.urgency if record.urgency in ("normal", "urgent") else "normal",  # type: ignore[arg-type]
                items=[
                    ItemInput(description=i.description[:1000] or "item", quantity=i.quantity, model_text=i.model_text, serial_text=i.serial_text, source_message_id=first.id, source_start=0, source_end=min(len(first.body), 1000))
                    for i in record.items[:20]
                ],
            )
        plate = None
        if record.nameplate is not None:
            plate = NameplateResult(attachment_id=record.nameplate.attachment_id, model_text=record.nameplate.model_text, serial_text=record.nameplate.serial_text, issues=[x for x in record.nameplate.issues if x in ("unreadable", "blur", "low_resolution", "glare", "partial_plate")])  # type: ignore[misc]
        return ExtractionView(revision=record.revision, intake=intake, nameplate=plate, confirmed=bool(record.nameplate and record.nameplate.confirmed))

    async def list_messages(self, actor: ActorContext, enquiry_id: UUID, *, limit: int) -> MessagePage:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        ordered = sorted(record.messages, key=lambda m: m.created_at, reverse=True)
        return MessagePage(items=ordered[:limit], next_cursor=None)

    async def list_attachments(self, actor: ActorContext, enquiry_id: UUID) -> AttachmentList:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        return AttachmentList(items=[AttachmentView(id=a.id, status=a.status, error_code=a.error_code) for a in record.attachments])

    async def register_upload(self, actor: ActorContext, enquiry_id: UUID, ticket: UploadTicket) -> None:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        record.attachments.append(AttachmentRecord(id=ticket.attachment_id, media_type="application/octet-stream", size_bytes=0, status="pending"))

    async def read_progress(self, actor: ActorContext, enquiry_id: UUID) -> ProgressView:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        try:
            step = WorkflowStep(record.step)
        except ValueError:
            step = WorkflowStep.INTAKE
        if record.status == "approved":
            step = WorkflowStep.COMPLETE
        return ProgressView(enquiry_id=record.id, revision=record.revision, step=step, wait_reason=record.wait_reason, updated_at=record.updated_at)

    async def timeline(self, actor: ActorContext, enquiry_id: UUID) -> list[dict]:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        events = [e for e in record.events if e.revision == record.revision] or record.events
        return [{"step": e.step, "label": e.label, "at": e.at.isoformat(), "status": e.status, "detail": e.detail} for e in events]

    async def list_owned(self, actor: ActorContext, *, status: str | None, after: object | None, limit: int) -> list[object]:
        from partsiq.enquiries.history import HistoryRow

        ws = await self.workspace(actor)
        rows = [r for r in ws.enquiries.values() if (ws.kind == "demo" or r.owner_id == actor.user_id) and (status is None or r.status == status)]
        rows.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return [HistoryRow(view=self.view(r), created_at=r.created_at) for r in rows[:limit]]

    # ================================================================== uploads (fixture storage)

    async def accept_upload(self, actor: ActorContext, enquiry_id: UUID, *, data: bytes, media_type: str, fixture_key: str | None) -> AttachmentRecord:
        """Validate an uploaded nameplate image (magic bytes, size, decoded pixels) and attach it."""
        from partsiq.storage.images import validate_image

        ws = await self.workspace(actor)
        async with ws.lock:
            record = self._record(actor, ws, enquiry_id)
            if record.status == "approved":
                raise PartsIQError("CONFLICT", detail="This enquiry is already answered.")
            # Allowlist, size, magic bytes, decode and decoded-pixel cap — before anything is kept.
            info = validate_image(data, media_type, settings=self.settings)
            attachment = AttachmentRecord(id=uuid4(), media_type=info.media_type, size_bytes=len(data), status="validated", width=info.width, height=info.height, sha256=info.sha256, fixture_key=fixture_key)
            record.attachments.append(attachment)
            record.nameplate = None
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="attachment.validated", entity_type="attachment", entity_id=str(attachment.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"bytes": len(data)})
            return attachment

    # ================================================================== runs

    def run_view(self, ws: Workspace, run: RunRecord) -> dict[str, Any]:
        pending = [self.pending_view(p) for p in ws.pending.values() if p.run_id == run.id and p.status == "open"]
        record = ws.enquiries.get(run.enquiry_id)
        stale = record is not None and record.revision != run.revision
        status = run.status
        if run.control == "pause_requested" and run.in_flight:
            status = "pausing"
        roster = self._roster(ws, run)
        return {
            "id": str(run.id),
            "enquiry_id": str(run.enquiry_id),
            "revision": run.revision,
            "current_revision": record.revision if record else run.revision,
            "stale": stale,
            "mode": run.mode,
            "status": status,
            "control": run.control,
            "execution_source": run.execution_source,
            "created_by": str(run.created_by),
            "catalogue_version_id": str(run.catalogue_version_id),
            "demo_session_id": str(run.session_id) if run.session_id else None,
            "demo_session_generation": run.session_generation,
            "limits": run.limits,
            "usage": {
                "agent_turns": run.usage.agent_turns,
                "tool_calls": run.usage.tool_calls,
                "output_tokens": run.usage.output_tokens if run.execution_source == "live" else None,
                "input_tokens": run.usage.input_tokens if run.execution_source == "live" else None,
                "estimated_usd": str(run.usage.estimated_usd) if run.execution_source == "live" else None,
                "retries": run.usage.retries,
                "active_seconds": round(run.usage.active_seconds, 2),
            },
            "state_version": run.state_version,
            "in_flight": run.in_flight,
            "current_step": run.current_step,
            "blocked_reason": run.blocked_reason,
            "terminal_reason": run.terminal_reason,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "pending": pending,
            "roster": roster,
            "carried_from": run.board.get("carried_from"),
            "available_actions": self._available_actions(run, stale),
        }

    def _available_actions(self, run: RunRecord, stale: bool) -> list[str]:
        if stale or run.status in TERMINAL_RUN_STATUSES:
            return ["fixture_replay"] if run.status == "failed" else []
        actions = ["instruct"]
        if run.status in ("queued", "running", "pausing") and run.control == "active":
            actions.append("pause")
        if run.status == "paused" or run.control == "pause_requested":
            actions.append("resume")
        if run.status not in TERMINAL_RUN_STATUSES:
            actions.append("cancel")
        if run.status == "blocked":
            actions.append("fixture_replay")
            if run.blocked_reason in ("wall_clock", "agent_turns", "tool_calls", "no_progress", "loop_detected"):
                actions.remove("instruct")
        return actions

    def _roster(self, ws: Workspace, run: RunRecord) -> list[dict[str, Any]]:
        exchanges = ws.exchanges.get(run.id, [])
        participants = list(collab.AGENTS) + list(collab.SERVICES) if run.mode == "collaboration" else ["workflow"] + list(collab.SERVICES)
        out = []
        for name in participants:
            sent = [e for e in exchanges if e.sender == name]
            received = [e for e in exchanges if e.recipient == name]
            last = max(sent + received, key=lambda e: e.seq, default=None)
            if run.in_flight and run.current_step == name:
                state = "working"
            elif any(e.status == "waiting" and e.sender == name for e in exchanges) and run.status in WAITING_RUN_STATUSES:
                state = "waiting"
            elif last is None:
                state = "idle"
            else:
                state = "done" if run.status in TERMINAL_RUN_STATUSES else "active"
            out.append({
                "id": name,
                "label": collab.PARTICIPANT_LABELS.get(name, name),
                "type": "agent" if name in collab.AGENTS else "service" if name in collab.SERVICES else "workflow",
                "state": state,
                "messages": len(sent),
            })
        return out

    @staticmethod
    def exchange_view(e: Any) -> dict[str, Any]:
        return {
            "id": str(e.id),
            "seq": e.seq,
            "run_id": str(e.run_id),
            "sender": e.sender,
            "sender_label": collab.PARTICIPANT_LABELS.get(e.sender, e.sender),
            "recipient": e.recipient,
            "recipient_label": collab.PARTICIPANT_LABELS.get(e.recipient, e.recipient) if e.recipient else None,
            "kind": e.kind,
            "kind_label": collab.KIND_LABELS.get(e.kind, e.kind),
            "summary": e.summary,
            "payload": e.payload,
            "evidence_refs": e.evidence_refs,
            "source": e.source,
            "correlation_id": str(e.correlation_id) if e.correlation_id else None,
            "reply_to": str(e.reply_to) if e.reply_to else None,
            "status": e.status,
            "created_at": e.created_at.isoformat(),
        }

    @staticmethod
    def pending_view(p: PendingActionRecord) -> dict[str, Any]:
        return {
            "id": str(p.id), "run_id": str(p.run_id), "enquiry_id": str(p.enquiry_id), "revision": p.revision,
            "kind": p.kind, "code": p.code, "requested_by": p.requested_by,
            "requested_by_label": collab.PARTICIPANT_LABELS.get(p.requested_by, p.requested_by),
            "prompt": p.prompt, "options": p.options, "allowed_resolutions": p.allowed_resolutions,
            "status": p.status, "item_id": str(p.item_id) if p.item_id else None,
            "created_at": p.created_at.isoformat(),
            "resolved_by": str(p.resolved_by) if p.resolved_by else None,
            "resolved_at": p.resolved_at.isoformat() if p.resolved_at else None,
            "resolution": p.resolution,
        }

    async def list_runs(self, actor: ActorContext, enquiry_id: UUID) -> list[dict[str, Any]]:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        return [self.run_view(ws, ws.runs[r]) for r in reversed(record.run_ids) if r in ws.runs]

    async def get_run(self, actor: ActorContext, run_id: UUID) -> dict[str, Any]:
        ws = await self.workspace(actor)
        run, _record = self._run(actor, ws, run_id)
        return self.run_view(ws, run)

    async def run_events(self, actor: ActorContext, run_id: UUID, *, after: int, limit: int) -> dict[str, Any]:
        ws = await self.workspace(actor)
        run, _record = self._run(actor, ws, run_id)
        items = [e for e in ws.exchanges.get(run.id, []) if e.seq > after][:limit]
        return {
            "items": [self.exchange_view(e) for e in items],
            "next_after": items[-1].seq if items else after,
            "run": self.run_view(ws, run),
        }

    async def start_new_run(self, actor: ActorContext, enquiry_id: UUID, *, mode: str, expected_revision: int, source: str | None = None) -> dict[str, Any]:
        ws = await self.workspace(actor)
        if mode not in ("guided", "collaboration"):
            raise PartsIQError("VALIDATION_FAILED", detail="Unsupported execution mode.")
        if mode == "collaboration" and not self.settings.collaboration_enabled:
            raise PartsIQError("FORBIDDEN", detail="Agent collaboration is disabled on this server.")
        async with ws.lock:
            record = self._record(actor, ws, enquiry_id)
            if not self._can_control(actor, ws, record):
                raise PartsIQError("NOT_FOUND", internal_detail="cannot control")
            if record.revision != expected_revision:
                raise PartsIQError("STALE_REVISION", detail="The enquiry changed. Reload to see the latest revision.")
            if record.status == "approved":
                raise PartsIQError("CONFLICT", detail="This enquiry is already approved and published.")
            current = ws.runs.get(record.current_run_id) if record.current_run_id else None
            if current is not None and current.status not in TERMINAL_RUN_STATUSES and current.status != "blocked":
                raise PartsIQError("CONFLICT", detail="A run is still active for this revision. Cancel it before starting a new one; its history is kept.")
            self._check_concurrency(ws)
            if current is not None and current.status == "blocked":
                current.status = "cancelled"
                current.terminal_reason = "Replaced by a new run after being blocked."
                current.completed_at = utcnow()
                current.state_version += 1
            reset_derived(record)
            record.events = [e for e in record.events if e.revision != record.revision]
            run = self._start_run(ws, record, actor, mode, source=source, carried_from=current.id if current else None)
        await self._settle_if_synchronous(ws, run)
        return self.run_view(ws, run)

    # ================================================================== commands

    async def command(self, actor: ActorContext, run_id: UUID, body: dict[str, Any], key: UUID) -> dict[str, Any]:
        ctype = body.get("type")
        if ctype not in COMMAND_TYPES:
            raise PartsIQError("VALIDATION_FAILED", detail="Unknown command type.")
        expected_revision = body.get("expected_revision")
        if not isinstance(expected_revision, int) or expected_revision < 1:
            raise PartsIQError("VALIDATION_FAILED", detail="expected_revision is required.")
        payload = body.get("payload") or {}
        if not isinstance(payload, dict) or len(json.dumps(payload)) > self.limits.max_message_bytes:
            raise PartsIQError("VALIDATION_FAILED", detail="Command payload is invalid or too large.")
        ws = await self.workspace(actor)
        settle: RunRecord | None = None
        async with ws.lock:
            run, record = self._run(actor, ws, run_id)
            if not self._can_control(actor, ws, record):
                raise PartsIQError("NOT_FOUND", internal_detail="caller cannot control this run")
            if actor_kind(actor) == "account" and record.owner_id != actor.user_id:
                require_capability(actor, "run.control_assigned")
            request_hash = _hash({"type": ctype, "expected_revision": expected_revision, "expected_state_version": body.get("expected_state_version"), "payload": payload})
            existing = ws.commands.get((run.id, key))
            if existing is not None:
                if existing.payload_hash != request_hash:
                    raise PartsIQError("IDEMPOTENCY_MISMATCH", detail="This idempotency key was used for a different command.")
                return self._command_view(existing, replay=True, ws=ws, run=run)
            if expected_revision != record.revision:
                raise PartsIQError("STALE_REVISION", detail="The enquiry has a newer revision. Reload before sending this command.")
            esv = body.get("expected_state_version")
            if esv is not None and esv != run.state_version:
                raise PartsIQError("CONFLICT", detail="The run changed since you loaded it. Reload and try again.")
            result, settle = self._apply_command(ws, record, run, actor, ctype, payload)
            command = CommandRecord(
                id=uuid4(), run_id=run.id, actor_id=actor.user_id, type=ctype, expected_revision=expected_revision,
                expected_state_version=esv, idempotency_key=key, payload_hash=request_hash, payload=payload,
                accepted=True, result=result, created_at=utcnow(),
            )
            ws.commands[(run.id, key)] = command
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action=f"run.command.{ctype}", entity_type="run", entity_id=str(run.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"result": result[:120]})
        if settle is not None:
            await self._settle_if_synchronous(ws, settle)
        return self._command_view(command, replay=False, ws=ws, run=ws.runs.get(settle.id) if settle else run)

    def _command_view(self, command: CommandRecord, *, replay: bool, ws: Workspace, run: RunRecord) -> dict[str, Any]:
        return {
            "id": str(command.id), "run_id": str(command.run_id), "type": command.type, "accepted": command.accepted,
            "result": command.result, "replayed": replay, "created_at": command.created_at.isoformat(),
            "run": self.run_view(ws, run),
        }

    def _user_label(self, actor: ActorContext, record: EnquiryRecord) -> str:
        return "customer" if record.owner_id == actor.user_id else "reviewer"

    def _apply_command(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, actor: ActorContext, ctype: str, payload: dict[str, Any]) -> tuple[str, RunRecord | None]:
        executor = self.executor
        who = self._user_label(actor, record)
        if ctype == "pause":
            if run.status in TERMINAL_RUN_STATUSES or run.status in ("paused",):
                raise PartsIQError("CONFLICT", detail="This run cannot be paused in its current state.")
            if run.status in WAITING_RUN_STATUSES or run.status == "blocked":
                raise PartsIQError("CONFLICT", detail="The run is already waiting; nothing new will be dispatched.")
            run.control = "pause_requested"
            run.state_version += 1
            if not run.in_flight and (ws.tasks.get(run.id) is None or ws.tasks[run.id].done()):
                run.status = "paused"
                run.control = "paused"
            executor.emit(ws, run, sender=who, recipient="controller", kind="control", summary="Pause requested. The current step (if any) finishes; no new step will start.", data={"control": "pause_requested"}, source="user")
            return ("pausing after current step" if run.in_flight else "paused"), None
        if ctype == "resume":
            if run.control not in ("pause_requested", "paused") and run.status != "paused":
                raise PartsIQError("CONFLICT", detail="Only a paused run can be resumed.")
            if run.catalogue_version_id != ws.catalogue.version_id:
                executor._block(ws, record, run, "stale_catalogue", "The catalogue changed while the run was paused. Start a new run for the current version.")
                return "blocked: catalogue changed", None
            if run.execution_source == "live":
                ok, reason = live_available(self.settings)
                if not ok:
                    executor._block(ws, record, run, "provider_unavailable", reason or "The live provider is unavailable.")
                    return "blocked: live provider unavailable", None
            self._check_concurrency(ws)
            run.control = "active"
            run.status = "queued"
            run.state_version += 1
            executor.emit(ws, run, sender=who, recipient="controller", kind="control", summary="Run resumed from its saved state; completed steps are not repeated.", data={"control": "resumed"}, source="user")
            executor.schedule(ws, run)
            return "resumed", run
        if ctype == "cancel":
            if run.status in TERMINAL_RUN_STATUSES:
                raise PartsIQError("CONFLICT", detail="This run already finished.")
            executor.fence(run)
            in_flight = run.in_flight
            run.control = "cancelled"
            run.status = "cancelled"
            run.completed_at = utcnow()
            run.terminal_reason = "Cancelled by " + who + ". The enquiry and its history are kept."
            run.state_version += 1
            for pending in ws.pending.values():
                if pending.run_id == run.id and pending.status == "open":
                    pending.status = "cancelled"
            executor.emit(ws, run, sender=who, recipient="controller", kind="control", summary=("Run cancelled. The step in progress will finish but its result will be discarded." if in_flight else "Run cancelled. No further work will be dispatched."), data={"control": "cancelled"}, source="user")
            record.status = "needs_information" if record.status == "processing" else record.status
            record.wait_reason = "Run cancelled. Start a new run to continue."
            record.updated_at = utcnow()
            return "cancelled", None
        if ctype == "instruct":
            text = str(payload.get("text", "")).strip()
            if not text or len(text) > self.limits.max_instruction_chars:
                raise PartsIQError("VALIDATION_FAILED", detail=f"Instructions must be 1–{self.limits.max_instruction_chars} characters.")
            if run.status in TERMINAL_RUN_STATUSES:
                raise PartsIQError("CONFLICT", detail="This run already finished.")
            factual = bool(_FACTUAL.search(text))
            record.instructions.append(text)
            exchange = executor.emit(ws, run, sender=who, recipient="intake" if run.mode == "collaboration" else "controller", kind="user_instruction", summary=f"Instruction: “{text[:200]}”" + (" — contains factual details; send them as a message to create a new revision." if factual else ""), data={"text": text, "factual_change": factual}, source="user")
            if run.mode == "collaboration" and run.status in ("running", "queued", "paused"):
                run.agenda.append(exchange.id)
            run.state_version += 1
            return "instruction recorded" + (" (factual change needs a new message)" if factual else ""), None
        if ctype in ("answer", "confirm_nameplate"):
            pending = self._open_pending_for(ws, run, ("nameplate_confirmation",) if ctype == "confirm_nameplate" else ("clarification",))
            if ctype == "confirm_nameplate":
                plate = record.nameplate
                if plate is None:
                    raise PartsIQError("CONFLICT", detail="There is no nameplate reading to confirm.")
                model = str(payload.get("model_text") or plate.model_text or "").strip()
                serial = payload.get("serial_text", plate.serial_text)
                if not model:
                    raise PartsIQError("VALIDATION_FAILED", detail="A model is required to confirm the nameplate.")
                plate.confirmed = True
                plate.confirmed_model = model[:120]
                plate.confirmed_serial = str(serial).strip()[:120] if serial else None
                text = f"Confirmed nameplate: model {plate.confirmed_model}" + (f", serial {plate.confirmed_serial}" if plate.confirmed_serial else "")
            else:
                text = str(payload.get("text", "")).strip()
                if not text:
                    raise PartsIQError("VALIDATION_FAILED", detail="Please type an answer.")
                understood = apply_answer(record, text, ws.catalogue)
                text = text[:2000]
                pending.resolution = understood
            pending.status = "resolved"
            pending.resolved_by = actor.user_id
            pending.resolved_at = utcnow()
            executor.emit(ws, run, sender=who, recipient="controller", kind="user_answer", summary=f"Answer received: {pending.resolution or text}. A new revision will be checked from the start.", data={"pending_id": str(pending.id)}, source="user")
            new_run = self._new_revision(ws, record, actor, text, kind="customer")
            return f"new revision {record.revision} started", new_run
        if ctype == "resolve_delegation":
            pending = self._open_pending_for(ws, run, ("delegation_consent",))
            decision = payload.get("decision")
            if decision not in pending.allowed_resolutions:
                raise PartsIQError("VALIDATION_FAILED", detail="Decision must be approve or deny.")
            pending.status = "resolved"
            pending.resolved_by = actor.user_id
            pending.resolved_at = utcnow()
            pending.resolution = decision
            exchange = executor.emit(ws, run, sender="controller", recipient=pending.requested_by, kind="consent_result", summary=f"{who.capitalize()} {'allowed' if decision == 'approve' else 'declined'} the request: {pending.prompt[:200]}", data={"approved": decision == "approve", "item_id": str(pending.item_id) if pending.item_id else None, "action": pending.code}, source="user")
            for e in ws.exchanges.get(run.id, []):
                if e.id == pending.exchange_id:
                    e.status = "handled"
            run.agenda.append(exchange.id)
            run.status = "queued"
            run.control = "active"
            run.state_version += 1
            record.status = "processing"
            record.wait_reason = None
            executor.schedule(ws, run)
            return f"delegation {decision}d", run
        if ctype == "fixture_replay":
            if run.status not in ("blocked", "failed"):
                raise PartsIQError("CONFLICT", detail="Fixture replay is offered only after a run is blocked or failed.")
            run.status = "cancelled" if run.status == "blocked" else run.status
            run.terminal_reason = (run.terminal_reason or "") + " Replaced by a separate fixture replay run."
            run.completed_at = utcnow()
            run.state_version += 1
            reset_derived(record)
            record.events = [e for e in record.events if e.revision != record.revision]
            new_run = self._start_run(ws, record, actor, run.mode, source="fixture", carried_from=run.id)
            return "fixture replay started as a separate run", new_run
        raise PartsIQError("VALIDATION_FAILED", detail="Unknown command type.")  # pragma: no cover

    def _open_pending_for(self, ws: Workspace, run: RunRecord, kinds: tuple[str, ...]) -> PendingActionRecord:
        pending = next((p for p in ws.pending.values() if p.run_id == run.id and p.status == "open" and p.kind in kinds), None)
        if pending is None:
            raise PartsIQError("CONFLICT", detail="There is no open request of this kind on the run.")
        return pending

    async def list_pending(self, actor: ActorContext, enquiry_id: UUID) -> list[dict[str, Any]]:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        return [self.pending_view(p) for p in ws.pending.values() if p.enquiry_id == record.id and p.status == "open"]

    # ================================================================== detail (composed read)

    async def enquiry_detail(self, actor: ActorContext, enquiry_id: UUID) -> dict[str, Any]:
        ws = await self.workspace(actor)
        record = self._record(actor, ws, enquiry_id)
        reviewer = self._can_review(actor, ws, record)
        run = ws.runs.get(record.current_run_id) if record.current_run_id else None
        decision = record.current_decision()
        published = next((m for m in reversed(record.messages) if m.kind == "recommendation"), None)
        catalogue = ws.catalogue
        items = []
        for i in record.items:
            selected = next((c for c in i.candidates if c.part_id == i.selected_part_id), None)
            items.append({
                "id": str(i.id), "ordinal": i.ordinal, "description": i.description,
                "quantity": None if i.quantity is None else format(i.quantity.normalize(), "f"),
                "quantity_assumed": i.quantity_assumed,
                "model_text": i.model_text, "serial_text": i.serial_text, "status": i.status,
                "configuration_label": i.configuration_label, "identification_note": i.identification_note,
                "clarification_code": i.clarification_code, "clarification_text": i.clarification_text,
                "quoted_number_note": i.quoted_number_note,
                "selected": None if selected is None else {
                    "part_id": selected.part_id, "part_number": selected.part_number, "name_en": selected.name_en, "name_ar": selected.name_ar,
                    "source_reference": selected.source_reference, "reasons": selected.reasons, "matched_terms": selected.matched_terms,
                    "superseded_from": selected.superseded_from, "selection_source": i.selection_source,
                },
                "candidates": [
                    {"part_id": c.part_id, "part_number": c.part_number, "name_en": c.name_en, "name_ar": c.name_ar, "score": c.score, "reasons": c.reasons, "source_reference": c.source_reference, "superseded_from": c.superseded_from}
                    for c in i.candidates[:5]
                ],
                "plan": None if not i.plan_strategy else {
                    "strategy": i.plan_strategy, "message": i.plan_message, "shortage": i.shortage,
                    "lines": [{"warehouse_code": line.warehouse_code, "warehouse_name": catalogue.warehouse_name(line.warehouse_id), "quantity": line.quantity, "transfer_days": line.transfer_days, "observed_at": line.observed_at.isoformat()} for line in i.plan_lines],
                },
            })
        return {
            "id": str(record.id), "revision": record.revision, "status": record.status, "step": record.step,
            "wait_reason": record.wait_reason, "locale": record.locale, "language": record.language,
            "urgency": record.urgency, "priority": record.priority,
            "destination": {"id": record.destination_warehouse_id, "name": catalogue.warehouse_name(record.destination_warehouse_id)},
            "created_at": record.created_at.isoformat(), "updated_at": record.updated_at.isoformat(),
            "due_at": record.due_at.isoformat() if record.due_at else None,
            "mode": record.mode, "catalogue_version_id": str(record.catalogue_version_id) if record.catalogue_version_id else None,
            "catalogue_current": record.catalogue_version_id == catalogue.version_id,
            "messages": [{"id": str(m.id), "revision": m.revision, "kind": m.kind, "body": m.body, "created_at": m.created_at.isoformat()} for m in record.messages],
            "items": items,
            "attachments": [{"id": str(a.id), "status": a.status, "media_type": a.media_type, "width": a.width, "height": a.height, "error_code": a.error_code} for a in record.attachments],
            "nameplate": None if record.nameplate is None else {
                "model_text": record.nameplate.model_text, "serial_text": record.nameplate.serial_text, "issues": record.nameplate.issues,
                "confirmed": record.nameplate.confirmed, "confirmed_model": record.nameplate.confirmed_model, "confirmed_serial": record.nameplate.confirmed_serial,
                "source": record.nameplate.source,
            },
            "pending_question": record.pending_question, "pending_code": record.pending_code,
            "pending": [self.pending_view(p) for p in ws.pending.values() if p.enquiry_id == record.id and p.status == "open"],
            "run": self.run_view(ws, run) if run else None,
            "runs": [{"id": str(r), "mode": ws.runs[r].mode, "status": ws.runs[r].status, "revision": ws.runs[r].revision, "created_at": ws.runs[r].created_at.isoformat(), "execution_source": ws.runs[r].execution_source} for r in reversed(record.run_ids) if r in ws.runs],
            "events": [{"step": e.step, "label": e.label, "at": e.at.isoformat(), "status": e.status, "detail": e.detail if reviewer else None, "revision": e.revision} for e in record.events if e.revision == record.revision],
            "draft": None if record.draft_rendered is None or not reviewer else {"id": str(record.draft_id), "rendered": record.draft_rendered, "source": record.draft_source, "published": False},
            "verification": None if record.verification is None else {"passed": record.verification.passed, "failures": [{"code": f.code, "detail": f.detail if reviewer else None} for f in record.verification.failures]},
            "decision": None if decision is None else {"kind": decision.kind, "at": decision.at.isoformat(), "reason": decision.reason, "revision": decision.revision},
            "published_reply": None if published is None else {"id": str(published.id), "body": published.body, "revision": published.revision, "created_at": published.created_at.isoformat()},
            "assigned_to": str(record.assigned_to) if record.assigned_to else None,
            "instructions": record.instructions[-5:] if reviewer else [],
            "can_review": reviewer,
            "can_control": self._can_control(actor, ws, record),
            "is_owner": record.owner_id == actor.user_id or ws.kind == "demo",
        }

    async def warehouses(self, actor: ActorContext) -> list[dict[str, Any]]:
        ws = await self.workspace(actor)
        catalogue = ws.catalogue
        return [{"id": catalogue.warehouse_id(code), "code": code, "name": catalogue.stock.warehouses.get(code, (code, ""))[0], "region": catalogue.stock.warehouses.get(code, ("", ""))[1]} for code in catalogue.warehouse_codes]

    async def dashboard(self, actor: ActorContext) -> dict[str, Any]:
        ws = await self.workspace(actor)
        own = [r for r in ws.enquiries.values() if ws.kind == "demo" or r.owner_id == actor.user_id]
        counts: dict[str, int] = {}
        for r in own:
            counts[r.status] = counts.get(r.status, 0) + 1
        review: dict[str, Any] | None = None
        if has_capability(actor, "review.queue"):
            scope = [r for r in ws.enquiries.values() if self._can_review(actor, ws, r)]
            now = utcnow()
            review = {
                "awaiting_review": sum(1 for r in scope if r.status == "awaiting_review"),
                "needs_information": sum(1 for r in scope if r.status == "needs_information"),
                "exceptions": sum(1 for r in scope if r.status == "failed"),
                "overdue": sum(1 for r in scope if r.due_at and r.due_at < now and r.status in ("awaiting_review", "processing", "failed")),
                "assigned_to_me": sum(1 for r in scope if r.assigned_to == actor.user_id),
                "unassigned": sum(1 for r in scope if r.assigned_to is None and r.status == "awaiting_review"),
            }
        recent = sorted(own, key=lambda r: r.updated_at, reverse=True)[:6]
        return {
            "scope": ws.kind,
            "counts": counts,
            "total": len(own),
            "needs_you": [
                {"id": str(r.id), "question": r.pending_question, "updated_at": r.updated_at.isoformat()}
                for r in own if r.status == "needs_information" and r.pending_question
            ][:5],
            "recent": [self._summary(ws, r) for r in recent],
            "review": review,
            "active_runs": sum(1 for r in ws.runs.values() if r.status in ("queued", "running", "pausing", "paused", "waiting_user", "waiting_consent")),
        }

    def _summary(self, ws: Workspace, r: EnquiryRecord) -> dict[str, Any]:
        first = r.messages[0].body if r.messages else ""
        run = ws.runs.get(r.current_run_id) if r.current_run_id else None
        member = ws.members.get(r.assigned_to) if r.assigned_to else None
        return {
            "id": str(r.id), "revision": r.revision, "status": r.status, "step": r.step,
            "title": first[:140], "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
            "mode": r.mode, "priority": r.priority, "due_at": r.due_at.isoformat() if r.due_at else None,
            "overdue": bool(r.due_at and r.due_at < utcnow() and r.status in ("awaiting_review", "processing", "failed")),
            "run_status": run.status if run else None, "execution_source": run.execution_source if run else None,
            "assigned_to": str(r.assigned_to) if r.assigned_to else None,
            "assigned_label": member.display_name if member else (str(r.assigned_to)[:8] if r.assigned_to else None),
            "items": len(r.items), "pending_question": r.pending_question,
        }

    async def search_enquiries(self, actor: ActorContext, *, scope: str, status: str | None, query: str | None, cursor: int, limit: int, mode: str | None = None, assigned: str | None = None) -> dict[str, Any]:
        ws = await self.workspace(actor)
        if scope == "review":
            require_capability(actor, "review.queue")
            rows = [r for r in ws.enquiries.values() if self._can_review(actor, ws, r)]
        else:
            rows = [r for r in ws.enquiries.values() if ws.kind == "demo" or r.owner_id == actor.user_id]
        if status:
            wanted = set(status.split(","))
            rows = [r for r in rows if r.status in wanted]
        if mode:
            rows = [r for r in rows if r.mode == mode]
        if assigned == "me":
            rows = [r for r in rows if r.assigned_to == actor.user_id]
        elif assigned == "none":
            rows = [r for r in rows if r.assigned_to is None]
        if query:
            q = query.lower()[:200]
            rows = [r for r in rows if q in " ".join(m.body for m in r.messages).lower() or q in str(r.id)]
        rows.sort(key=lambda r: (r.updated_at, r.id), reverse=True)
        total = len(rows)
        page = rows[cursor: cursor + limit]
        return {
            "items": [self._summary(ws, r) for r in page],
            "total": total,
            "next_cursor": cursor + limit if cursor + limit < total else None,
        }


def demo_now() -> datetime:
    return datetime.now(tz=timezone.utc)


__all__ = ["WorkspaceRuntime", "requested_mode", "ProgressEvent", "time"]
