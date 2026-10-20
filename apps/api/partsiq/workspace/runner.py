"""Run execution for both modes, with server-enforced pause/resume/cancel and fencing (ADR 0002).

GUIDED runs drive the authoritative LangGraph graph (``workflow.graph.build_graph``) compiled with
``interrupt_before`` every node, so each dispatch executes exactly ONE node and the controller can
apply a pause or cancel at that safe boundary. Routing is still ``transitions.next_step`` — the
same deterministic table — and the checkpointer holds the per-(enquiry, revision) thread.

COLLABORATION runs dispatch one specialist turn at a time through the :mod:`collaboration`
controller.

Both loops compute each step on a COPY of the enquiry record and commit it only if the run's
fence is unchanged afterwards. A cancel, a superseding revision or a session reset bumps the fence,
so a step that was in flight (e.g. a provider call that cannot be cancelled) has its late result
discarded and recorded as such — it can never publish or overwrite newer state. A pause does not
discard: the in-flight step finishes ("pausing after current step"), its result is kept unpublished
and nothing new is dispatched until resume.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID, uuid4

from partsiq.core.contracts import EnquiryState, ItemInput, ItemState, WorkflowStep
from partsiq.core.errors import PartsIQError
from partsiq.workflow.graph import EXECUTABLE, build_graph, memory_checkpointer
from partsiq.workflow.handlers import GraphHandlers
from partsiq.workflow.state import new_state
from partsiq.workflow.transitions import next_step

from . import collaboration as collab
from .limits import LimitReached, RunLimits
from .records import (
    TERMINAL_RUN_STATUSES,
    EnquiryRecord,
    ExchangeRecord,
    PendingActionRecord,
    ProgressEvent,
    RunRecord,
    utcnow,
)
from .steps import STEP_LABELS, Pipeline, PendingSpec, StepReport, reset_derived
from .tenant import Workspace

logger = logging.getLogger("partsiq.workspace.runner")

NODE_NAMES = list(EXECUTABLE.values())


class Discarded(Exception):
    """A step finished after its run was cancelled/superseded; its result must not commit."""


@dataclass
class _Ctx:
    ws: Workspace
    record: EnquiryRecord
    run: RunRecord
    pipeline: Pipeline
    fence: int


def _commit(live: EnquiryRecord, work: EnquiryRecord) -> None:
    live.__dict__.update(work.__dict__)


class RunExecutor:
    """Owns the background tasks that advance runs. One task per run at most."""

    def __init__(self, *, settings: Any, pipeline_for: Callable[[Workspace, RunRecord], Pipeline], specialists_for: Callable[[Workspace, RunRecord], dict[str, collab.Specialist]], step_delay_ms: int) -> None:
        self._settings = settings
        self._pipeline_for = pipeline_for
        self._specialists_for = specialists_for
        self._delay = max(0, step_delay_ms) / 1000.0
        self._checkpointer = memory_checkpointer()
        self._contexts: dict[UUID, _Ctx] = {}
        self._graph = build_graph(self._guided_handlers(), self._checkpointer, interrupt_before=NODE_NAMES)
        self.limits = RunLimits.from_settings(settings)

    async def use_postgres_checkpointer(self, dsn: str) -> None:
        """Database mode: LangGraph checkpoints in PostgreSQL so guided runs resume after restart."""
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        from partsiq.workflow.graph import ContractSerde

        self._pg_pool = AsyncConnectionPool(conninfo=dsn, open=False, max_size=4, kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row})
        await self._pg_pool.open(wait=True, timeout=20)
        saver = AsyncPostgresSaver(self._pg_pool, serde=ContractSerde())
        await saver.setup()
        self._checkpointer = saver
        self._graph = build_graph(self._guided_handlers(), saver, interrupt_before=NODE_NAMES)

    async def close(self) -> None:
        pool = getattr(self, "_pg_pool", None)
        if pool is not None:
            await pool.close()

    def resume_interrupted(self, ws: Workspace) -> int:
        """After a restart, continue runs that were executing when the process stopped."""
        resumed = 0
        for run in ws.runs.values():
            if run.status in ("queued", "running", "pausing"):
                if run.control == "pause_requested" or run.status == "pausing":
                    run.status, run.control = "paused", "paused"
                    continue
                run.status = "queued"
                run.in_flight = False
                self.schedule(ws, run)
                resumed += 1
        return resumed

    # ------------------------------------------------------------------ exchanges / events

    def emit(
        self,
        ws: Workspace,
        run: RunRecord,
        *,
        sender: str,
        recipient: str | None,
        kind: str,
        summary: str,
        data: dict[str, Any] | None = None,
        refs: list[str] | None = None,
        source: str | None = None,
        reply_to: UUID | None = None,
        correlation_id: UUID | None = None,
        status: str = "delivered",
    ) -> ExchangeRecord:
        exchange = ExchangeRecord(
            id=uuid4(),
            run_id=run.id,
            seq=run.next_seq,
            sender=sender,
            recipient=recipient,
            kind=kind,
            summary=summary[:600],
            payload=dict(data or {}),
            evidence_refs=list(refs or [])[:12],
            source=source or ("system" if sender in ("controller", "workflow") else run.execution_source),  # type: ignore[arg-type]
            correlation_id=correlation_id,
            reply_to=reply_to,
            status=status,
            created_at=utcnow(),
        )
        run.next_seq += 1
        ws.exchanges.setdefault(run.id, []).append(exchange)
        run.updated_at = exchange.created_at
        return exchange

    def _event(self, record: EnquiryRecord, run: RunRecord, report: StepReport) -> None:
        status = {"done": "done", "waiting": "waiting", "failed": "failed"}.get(report.status, "done")
        record.events.append(
            ProgressEvent(step=report.step, label=report.label, at=utcnow(), status=status, detail=report.detail, revision=record.revision, run_id=run.id)
        )

    def _bump(self, run: RunRecord, **changes: Any) -> None:
        for key, value in changes.items():
            setattr(run, key, value)
        run.state_version += 1
        run.updated_at = utcnow()

    # ------------------------------------------------------------------ lifecycle

    def schedule(self, ws: Workspace, run: RunRecord) -> None:
        """Start (or resume) the background task for ``run`` if one is not already active."""
        task = ws.tasks.get(run.id)
        if task is not None and not task.done():
            return
        ws.tasks[run.id] = asyncio.create_task(self._drive(ws, run))

    async def wait_idle(self, ws: Workspace, run_id: UUID, timeout: float = 10.0) -> None:
        """Test/support helper: wait until the run's task finishes (or ``timeout``)."""
        task = ws.tasks.get(run_id)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout)

    def fence(self, run: RunRecord) -> None:
        """Invalidate any in-flight step for ``run`` (cancel / supersede / reset)."""
        run.fence += 1

    async def persist(self, ws: Workspace) -> None:
        """Database mode: write the committed step through to PostgreSQL (the lock flushes on exit)."""
        if ws.store is not None:
            async with ws.lock:
                pass

    async def _drive(self, ws: Workspace, run: RunRecord) -> None:
        record = ws.enquiries.get(run.enquiry_id)
        if record is None:
            return
        try:
            if run.mode == "guided":
                await self._drive_guided(ws, record, run)
            else:
                await self._drive_collab(ws, record, run)
        except LimitReached as exc:
            self._block(ws, record, run, exc.reason, exc.detail)
        except Discarded:
            pass
        except PartsIQError as exc:
            if exc.code == "CREDIT_UNAVAILABLE":
                self._block(ws, record, run, "provider_unavailable", "The live AI provider or allowance is unavailable. Completed work is kept.")
            elif exc.code == "STALE_CATALOGUE":
                self._block(ws, record, run, "stale_catalogue", "The active catalogue changed during this run. Start a new run to use the current version.")
            else:
                logger.warning("run failed code=%s detail=%s", exc.code, exc.internal_detail)
                self._fail(ws, record, run, exc.code)
        except Exception as exc:  # noqa: BLE001 - classify; never leak internals to the client
            logger.exception("run crashed: %s", type(exc).__name__)
            self._fail(ws, record, run, "INTERNAL")
        finally:
            self._accrue(run)
            run.in_flight = False
            try:
                await self.persist(ws)
            except Exception:  # noqa: BLE001 - the cache was reloaded from PostgreSQL by the lock
                logger.warning("run %s: final flush failed; state reloaded from the database", run.id)

    def _accrue(self, run: RunRecord) -> None:
        if run.active_since is not None:
            run.usage.active_seconds += time.monotonic() - run.active_since
            run.active_since = None

    def _check_limits(self, run: RunRecord, *, collaboration: bool) -> None:
        active = run.usage.active_seconds + (time.monotonic() - run.active_since if run.active_since else 0)
        if active > self.limits.max_wall_seconds:
            raise LimitReached("wall_clock", f"The run exceeded its {self.limits.max_wall_seconds}s time limit.")
        if collaboration:
            if run.usage.agent_turns >= self.limits.max_agent_turns:
                raise LimitReached("agent_turns", f"The run reached its limit of {self.limits.max_agent_turns} specialist turns.")
            if run.usage.tool_calls >= self.limits.max_tool_calls:
                raise LimitReached("tool_calls", f"The run reached its limit of {self.limits.max_tool_calls} tool calls.")

    def _control_gate(self, ws: Workspace, record: EnquiryRecord, run: RunRecord) -> bool:
        """Apply pause/cancel/supersede at a safe boundary. Returns False when dispatch must stop."""
        if run.status in TERMINAL_RUN_STATUSES:
            return False
        if record.revision != run.revision:
            self._bump(run, status="superseded", terminal_reason="A newer revision of the enquiry superseded this run.", completed_at=utcnow())
            return False
        if run.control in ("cancel_requested", "cancelled"):
            self._bump(run, status="cancelled", control="cancelled", completed_at=utcnow(), terminal_reason=run.terminal_reason or "Cancelled by user.")
            self.emit(ws, run, sender="controller", recipient=None, kind="control", summary="Run cancelled. No further work will be dispatched; completed evidence is kept.", data={"control": "cancelled"})
            return False
        if run.control in ("pause_requested", "paused"):
            self._bump(run, status="paused", control="paused")
            self.emit(ws, run, sender="controller", recipient=None, kind="control", summary="Run paused at a safe boundary. No new step will be dispatched until resumed.", data={"control": "paused"})
            return False
        return True

    async def _pace(self, run: RunRecord) -> None:
        if self._delay and run.execution_source == "fixture":
            await asyncio.sleep(self._delay)

    def _guard(self, ctx: _Ctx) -> None:
        if ctx.run.fence != ctx.fence or ctx.record.revision != ctx.run.revision:
            raise Discarded()

    def _discard_note(self, ws: Workspace, run: RunRecord, step: str) -> None:
        self.emit(ws, run, sender="controller", recipient=None, kind="late_result_discarded", summary=f"A '{step}' result finished after the run was cancelled or superseded and was discarded.", data={"step": step})

    # ------------------------------------------------------------------ outcomes

    def _block(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, reason: str, detail: str) -> None:
        if run.status in TERMINAL_RUN_STATUSES:
            return
        self._bump(run, status="blocked", blocked_reason=reason, terminal_reason=detail)
        self.emit(ws, run, sender="controller", recipient=None, kind="limit_reached" if reason not in ("provider_unavailable",) else "provider_unavailable", summary=detail, data={"reason": reason})
        record.wait_reason = detail
        record.updated_at = utcnow()

    def _fail(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, code: str) -> None:
        if run.status in TERMINAL_RUN_STATUSES:
            return
        self._bump(run, status="failed", terminal_reason=f"The run stopped with error {code}. Completed evidence is kept; staff can retry.", completed_at=utcnow())
        self.emit(ws, run, sender="controller", recipient=None, kind="control", summary=run.terminal_reason or "Run failed.", data={"error_code": code})
        record.status = "failed"
        record.step = "needs_staff"
        record.wait_reason = "A processing error occurred; staff will retry."
        record.updated_at = utcnow()

    def _open_pending(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, spec: PendingSpec, *, requested_by: str, exchange_id: UUID | None) -> PendingActionRecord:
        for existing in ws.pending.values():
            if existing.run_id == run.id and existing.status == "open":
                existing.status = "cancelled"
        allowed = {
            "clarification": ["answer"],
            "nameplate_confirmation": ["confirm", "correct"],
            "delegation_consent": ["approve", "deny"],
        }[spec.kind]
        pending = PendingActionRecord(
            id=uuid4(), run_id=run.id, enquiry_id=record.id, revision=record.revision,
            kind=spec.kind,  # type: ignore[arg-type]
            requested_by=requested_by, prompt=spec.prompt, options=spec.options,
            allowed_resolutions=allowed, status="open", created_at=utcnow(),
            item_id=spec.item_id, code=spec.code, exchange_id=exchange_id,
        )
        ws.pending[pending.id] = pending
        return pending

    def _await_user(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, spec: PendingSpec, *, requested_by: str, exchange_id: UUID | None = None) -> None:
        self._open_pending(ws, record, run, spec, requested_by=requested_by, exchange_id=exchange_id)
        status = "waiting_consent" if spec.kind == "delegation_consent" else "waiting_user"
        self._bump(run, status=status)
        if spec.kind != "delegation_consent":
            record.status = "needs_information"
            record.step = "confirm" if spec.kind == "nameplate_confirmation" else "clarify"
            record.wait_reason = "waiting for your answer"
        else:
            record.wait_reason = "waiting for your consent to a specialist request"
        record.updated_at = utcnow()

    def _ready(self, ws: Workspace, record: EnquiryRecord, run: RunRecord) -> None:
        record.status = "awaiting_review"
        record.step = "review"
        record.wait_reason = "waiting for staff review"
        record.review_ready_at = utcnow()
        record.updated_at = record.review_ready_at
        record.events.append(ProgressEvent(step="review", label="Waiting for staff review", at=utcnow(), status="waiting", revision=record.revision, run_id=run.id))
        self._bump(run, status="awaiting_review", completed_at=utcnow(), current_step="review")
        ws.append_audit(actor_type="system", actor_id="workflow", action="run.ready_for_review", entity_type="run", entity_id=str(run.id), request_id=uuid4(), enquiry_id=record.id, revision=record.revision, payload={"mode": run.mode})

    def _needs_staff(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, reason: str) -> None:
        record.status = "failed"
        record.step = "needs_staff"
        record.wait_reason = reason
        record.updated_at = utcnow()
        record.events.append(ProgressEvent(step="needs_staff", label="Handed to our staff", at=utcnow(), status="waiting", detail=reason, revision=record.revision, run_id=run.id))
        self._bump(run, status="needs_staff", completed_at=utcnow(), terminal_reason=reason)

    # ================================================================== GUIDED

    def _guided_handlers(self) -> GraphHandlers:
        def make(step: str):
            async def handler(state: EnquiryState) -> EnquiryState:
                ctx = self._contexts.get(state.enquiry_id)
                if ctx is None:
                    raise Discarded()
                # Restart recovery: if this run already committed this step (its result was saved
                # but the checkpoint was not), replay the committed state instead of redoing work.
                if any(e.kind == "step_completed" and e.payload.get("step") == step for e in ctx.ws.exchanges.get(ctx.run.id, [])):
                    return _state_from_record(state, ctx.record)
                work = copy.deepcopy(ctx.record)
                report = await self._guided_step(step, ctx, work)
                self._guard(ctx)
                _commit(ctx.record, work)
                ctx.run.usage.tool_calls += 1
                ctx.run.current_step = step
                self._event(ctx.record, ctx.run, report)
                self.emit(ctx.ws, ctx.run, sender="workflow", recipient=None, kind="step_completed", summary=f"{report.label}: {report.detail}", data={"step": step, "status": report.status, **_scrub(report.data)}, refs=report.evidence_refs, source=ctx.run.execution_source)
                if report.pending is not None:
                    ctx.run.pending_spec = report.pending
                ctx.ws.sample(f"step.{step}", 0.0)
                # Durability order: the step's committed result reaches PostgreSQL BEFORE LangGraph
                # writes the checkpoint that advances past this node (crash-safe replay above).
                await self.persist(ctx.ws)
                return _state_from_record(state, ctx.record)
            return handler

        return GraphHandlers(**{name: make(name) for name in NODE_NAMES})

    async def _nameplate_reading(self, ws: Workspace, record: EnquiryRecord) -> dict | None:
        """Database mode: the worker's reading of the stored photo (awaited, bounded, deduped).

        ``None`` means in-process fixture vision (demo sandboxes, or no worker configured).
        Called outside the workspace lock; a failed or timed-out job raises and blocks the run.
        """
        dispatcher = getattr(self, "nameplates", None)
        if dispatcher is None or ws.store is None:
            return None
        attachment = next((a for a in record.attachments if a.status == "validated"), None)
        if attachment is None or attachment.storage_key is None or (record.nameplate and record.nameplate.attachment_id == attachment.id):
            return None
        return await dispatcher.read(enquiry_id=record.id, revision=record.revision, attachment_id=attachment.id, object_key=attachment.storage_key)

    async def _guided_step(self, step: str, ctx: _Ctx, work: EnquiryRecord) -> StepReport:
        pipeline = ctx.pipeline
        started = time.monotonic()
        try:
            if step == "intake":
                report = await pipeline.intake(work)
                plate = pipeline.read_nameplate(work, await self._nameplate_reading(ctx.ws, work))
                if plate is not None:
                    report = plate
            elif step == "identify":
                report = await pipeline.identify(work)
            elif step == "search":
                report = await pipeline.search(work)
            elif step == "choose":
                report = StepReport("choose", STEP_LABELS["choose"], "done", "Applied the confirmed choice.")
            elif step == "plan":
                report = await pipeline.plan(work)
            elif step == "draft":
                report = await pipeline.draft(work)
            elif step == "verify":
                report = await pipeline.verify(work)
            else:  # pragma: no cover - graph only has the nodes above
                raise PartsIQError("CONFLICT", internal_detail=f"unknown step {step}")
        finally:
            ctx.ws.sample(f"latency.{step}", (time.monotonic() - started) * 1000)
        if report.usage.output_tokens:
            ctx.run.usage.output_tokens += 0  # settled by RunBudget already
        return report

    async def _drive_guided(self, ws: Workspace, record: EnquiryRecord, run: RunRecord) -> None:
        config = {"configurable": {"thread_id": run.thread_id}}
        ctx = _Ctx(ws=ws, record=record, run=run, pipeline=self._pipeline_for(ws, run), fence=run.fence)
        self._contexts[record.id] = ctx
        try:
            snapshot = await self._graph.aget_state(config)
            if not snapshot.values:
                initial = new_state(record.id, record.revision, session_generation=record.session_generation, catalogue_version_id=record.catalogue_version_id)
                async for _ in self._graph.astream(initial, config, stream_mode="updates"):
                    pass
            self._bump(run, status="running", control="active")
            run.active_since = time.monotonic()
            while True:
                if not self._control_gate(ws, record, run):
                    return
                self._check_limits(run, collaboration=False)
                snapshot = await self._graph.aget_state(config)
                if not snapshot.next:
                    break
                ctx.fence = run.fence
                run.in_flight = True
                await self._pace(run)
                if not self._control_gate(ws, record, run):
                    run.in_flight = False
                    return
                try:
                    async for _ in self._graph.astream(None, config, stream_mode="updates"):
                        pass
                except Discarded:
                    self._discard_note(ws, run, run.current_step or "step")
                    return
                finally:
                    run.in_flight = False
            snapshot = await self._graph.aget_state(config)
            values = snapshot.values
            state = values if isinstance(values, EnquiryState) else EnquiryState.model_validate_json(EnquiryState.model_construct(**values).model_dump_json())
            self._finish_guided(ws, record, run, next_step(state))
        finally:
            self._contexts.pop(record.id, None)

    def _finish_guided(self, ws: Workspace, record: EnquiryRecord, run: RunRecord, step: WorkflowStep) -> None:
        spec = getattr(run, "pending_spec", None)
        run.pending_spec = None
        if step == WorkflowStep.REVIEW:
            self._ready(ws, record, run)
        elif step in (WorkflowStep.CLARIFY, WorkflowStep.CONFIRM, WorkflowStep.AWAIT_OCR):
            if spec is None:
                item = next((i for i in record.items if i.status == "needs_information"), None)
                spec = PendingSpec("clarification", record.pending_code or "needs_model", item.id if item else None, record.pending_question or "Please add the missing details.")
            self._await_user(ws, record, run, spec, requested_by="workflow")
        elif step == WorkflowStep.NEEDS_STAFF:
            failed = record.verification is not None and not record.verification.passed
            reason = "Verification failed; staff will review the evidence." if failed else "No compatible part was found in the active catalogue; our staff will follow up."
            self._needs_staff(ws, record, run, reason)
        else:
            self._bump(run, status="completed", completed_at=utcnow())

    # ================================================================== COLLABORATION

    def _board(self, record: EnquiryRecord, run: RunRecord) -> dict[str, Any]:
        items = []
        for i in record.items:
            selected = next((c for c in i.candidates if c.part_id == i.selected_part_id), None)
            items.append({
                "item_id": str(i.id),
                "description": i.description,
                "quantity": None if i.quantity is None else format(i.quantity.normalize(), "f"),
                "quantity_assumed": i.quantity_assumed,
                "model_text": i.model_text,
                "serial_text": i.serial_text,
                "configuration_id": i.configuration_id,
                "configuration_label": i.configuration_label,
                "status": i.status,
                "clarification_code": i.clarification_code,
                "searched": bool(i.candidates) or i.status in ("ready", "unavailable"),
                "planned": bool(i.plan_strategy),
                "selected_part_id": i.selected_part_id,
                "selected_part_number": selected.part_number if selected else None,
                "source_reference": selected.source_reference if selected else None,
                "shortage": i.shortage,
                "plan_message": i.plan_message,
                "candidates": [{"part_id": c.part_id, "part_number": c.part_number, "name_en": c.name_en} for c in i.candidates[:3]],
            })
        attachment_pending = any(a.status == "validated" for a in record.attachments) and record.nameplate is None
        plate = record.nameplate
        return {
            "revision": record.revision,
            "locale": record.locale,
            "items": items,
            "attachment_pending": attachment_pending,
            "nameplate": None if plate is None else {"model_text": plate.model_text, "serial_text": plate.serial_text, "issues": plate.issues, "confirmed": plate.confirmed},
            "verification": None if record.verification is None else {"passed": record.verification.passed},
            "alternatives_checked": list(run.board.get("alternatives_checked", [])),
            "replanned": bool(run.board.get("replanned")),
            "instructions": list(record.instructions[-3:]),
        }

    async def _drive_collab(self, ws: Workspace, record: EnquiryRecord, run: RunRecord) -> None:
        specialists = self._specialists_for(ws, run)
        pipeline = self._pipeline_for(ws, run)
        ctx = _Ctx(ws=ws, record=record, run=run, pipeline=pipeline, fence=run.fence)
        if not ws.exchanges.get(run.id):
            text = "\n".join(m.body for m in record.messages if m.kind == "customer")
            # Intake's own capability (extraction) runs first so every later exchange refers to
            # confirmed record items; the result is shown as Intake's finding.
            work = copy.deepcopy(record)
            report = await pipeline.intake(work)
            self._guard(ctx)
            _commit(record, work)
            self._event(record, run, report)
            if run.board.get("carried_from"):
                summary = f"Continuing from run {str(run.board['carried_from'])[:8]} with the customer's new input (revision {record.revision})."
            else:
                summary = f"New enquiry received ({record.language}). Customer wrote: “{text[:240]}”"
            task = self.emit(ws, run, sender="controller", recipient="intake", kind="task", summary=summary, data={"revision": record.revision})
            self.emit(ws, run, sender="intake", recipient="controller", kind="finding", summary=f"Extracted {report.detail} (extractor: {report.data.get('source')}).", data={"items": report.data.get("items", [])}, reply_to=task.id, status="handled")
            run.agenda.append(task.id)
            await self.persist(ws)
        self._bump(run, status="running", control="active")
        run.active_since = time.monotonic()
        rejections = 0
        while True:
            if not self._control_gate(ws, record, run):
                return
            if run.status in TERMINAL_RUN_STATUSES or run.status in ("waiting_user", "waiting_consent", "blocked"):
                return
            if not run.agenda:
                self._block(ws, record, run, "no_progress", "No specialist has a pending message; the run stopped without a result. Staff can retry.")
                return
            self._check_limits(run, collaboration=True)
            message = self._exchange(ws, run, run.agenda.pop(0))
            if message is None or message.recipient not in collab.AGENTS:
                continue
            specialist = specialists[message.recipient]
            ctx.fence = run.fence
            if message.recipient == "nameplate" and record.nameplate is None:
                # The nameplate specialist's own capability: read the validated photo (the
                # worker in database mode, fixture vision otherwise). Identifiers still need
                # the customer's confirmation.
                work = copy.deepcopy(record)
                plate = pipeline.read_nameplate(work, await self._nameplate_reading(ws, work))
                self._guard(ctx)
                _commit(record, work)
                if plate is not None:
                    self._event(record, run, plate)
            run.in_flight = True
            run.current_step = message.recipient
            await self._pace(run)
            try:
                turn = await self._turn_with_retry(specialist, message, record, run)
            finally:
                run.in_flight = False
            try:
                self._guard(ctx)
            except Discarded:
                self._discard_note(ws, run, f"{message.recipient} turn")
                return
            run.usage.agent_turns += 1
            message.status = "handled"
            if not self._control_gate(ws, record, run):
                # Paused/cancelled during the turn: keep the turn's proposals unexecuted for resume.
                if run.status == "paused":
                    run.agenda.insert(0, message.id)
                    message.status = "delivered"
                    run.usage.agent_turns -= 1
                return
            accepted_any = False
            for action in turn.actions[: collab.MAX_ACTIONS_PER_TURN]:
                ok = await self._apply_action(ctx, specialist, message, action)
                accepted_any = accepted_any or ok
                if run.status != "running":
                    break
            if len(turn.actions) > collab.MAX_ACTIONS_PER_TURN:
                self.emit(ws, run, sender="controller", recipient=specialist.name, kind="action_rejected", summary=f"Only {collab.MAX_ACTIONS_PER_TURN} actions per turn are allowed; the rest were dropped.", data={"code": "TOO_MANY_ACTIONS"})
            if turn.actions and not accepted_any:
                rejections += 1
                if rejections >= collab.MAX_CONSECUTIVE_REJECTIONS:
                    self._block(ws, record, run, "loop_detected", "Specialists kept proposing actions the policy rejects; the run was stopped to prevent a loop.")
                    return
            else:
                rejections = 0
            await self.persist(ws)
            if run.status != "running":
                return

    async def _turn_with_retry(self, specialist: collab.Specialist, message: ExchangeRecord, record: EnquiryRecord, run: RunRecord) -> collab.Turn:
        payload = {"kind": message.kind, "sender": message.sender, "summary": message.summary, "data": message.payload}
        attempts = 0
        while True:
            try:
                return await specialist.respond(payload, self._board(record, run))
            except LimitReached:
                raise
            except PartsIQError as exc:
                if exc.code == "CREDIT_UNAVAILABLE" or attempts >= self.limits.max_retries:
                    raise
                attempts += 1
                run.usage.retries += 1

    def _exchange(self, ws: Workspace, run: RunRecord, exchange_id: UUID) -> ExchangeRecord | None:
        return next((e for e in ws.exchanges.get(run.id, []) if e.id == exchange_id), None)

    async def _apply_action(self, ctx: _Ctx, specialist: collab.Specialist, message: ExchangeRecord, action: collab.Action) -> bool:
        ws, record, run = ctx.ws, ctx.record, ctx.run
        sender = specialist.name
        item_ids = {str(i.id) for i in record.items}
        try:
            collab.validate_action(sender, action, max_bytes=self.limits.max_message_bytes, item_ids=item_ids)
            sig = collab.signature(sender, action)
            if sig in run.seen_signatures:
                raise collab.PolicyViolation("REPEATED_EXCHANGE", "An identical exchange was already sent in this run.")
            if action.kind == "proposal":
                self._check_proposal(record, action)
            if action.kind == "ready_for_review":
                if record.verification is None or not record.verification.passed or record.draft_id is None:
                    raise collab.PolicyViolation("NOT_VERIFIED", "Ready for review requires a passed verification of the current draft.")
        except collab.PolicyViolation as violation:
            self.emit(ws, run, sender="controller", recipient=sender, kind="action_rejected", summary=f"Rejected {action.kind} from {sender}: {violation.detail}", data={"code": violation.code, "rejected_kind": action.kind, "recipient": action.recipient}, reply_to=message.id)
            return False
        run.seen_signatures.add(sig)

        if action.kind == "tool_call":
            run.usage.tool_calls += 1
            call = self.emit(ws, run, sender=sender, recipient=action.recipient, kind="tool_call", summary=action.summary, data={"tool": action.recipient, "args": action.args}, reply_to=message.id, source=specialist.source)
            work = copy.deepcopy(record)
            started = time.monotonic()
            result = await self._run_tool(ctx, work, action.recipient, action.args)
            ws.sample(f"latency.{action.recipient}", (time.monotonic() - started) * 1000)
            self._guard(ctx)
            _commit(record, work)
            if result.get("report") is not None:
                self._event(record, run, result["report"])
            out = self.emit(ws, run, sender=action.recipient, recipient=sender, kind="tool_result", summary=result["summary"], data=_scrub(result["data"]), refs=result.get("refs", []), reply_to=call.id, correlation_id=call.id, source="system")
            run.agenda.append(out.id)
            return True

        if action.kind == "clarification_request":
            exchange = self.emit(ws, run, sender=sender, recipient="customer", kind="clarification_request", summary=action.summary, data=action.data, reply_to=message.id, source=specialist.source, status="waiting")
            spec = self._clarification_spec(record, action.data)
            self._await_user(ws, record, run, spec, requested_by=sender, exchange_id=exchange.id)
            return True

        if action.kind == "delegation_request":
            exchange = self.emit(ws, run, sender=sender, recipient=action.recipient, kind="delegation_request", summary=action.summary, data=action.data, reply_to=message.id, source=specialist.source, status="waiting")
            spec = PendingSpec(
                kind="delegation_consent", code=str(action.data.get("action")), item_id=_uuid(action.data.get("item_id")),
                prompt=action.summary, options=[{"value": "approve", "label": "Allow"}, {"value": "deny", "label": "Decline"}],
            )
            self._await_user(ws, record, run, spec, requested_by=sender, exchange_id=exchange.id)
            return True

        if action.kind == "ready_for_review":
            self.emit(ws, run, sender=sender, recipient="controller", kind="ready_for_review", summary=action.summary, data=action.data, reply_to=message.id, source=specialist.source, status="completed")
            self._ready(ws, record, run)
            return True

        exchange = self.emit(ws, run, sender=sender, recipient=action.recipient, kind=action.kind, summary=action.summary, data=action.data, reply_to=message.id, source=specialist.source)
        if action.kind == "finding" and action.recipient == "controller":
            exchange.status = "handled"
            if action.data.get("needs_staff"):
                self._needs_staff(ws, record, run, "Specialists found no verifiable recommendation; our staff will follow up.")
        elif action.recipient in collab.AGENTS:
            run.agenda.append(exchange.id)
        return True

    def _check_proposal(self, record: EnquiryRecord, action: collab.Action) -> None:
        """A proposal may only carry parts already in the code-computed compatible selection."""
        proposed = action.data.get("items") or []
        if not proposed:
            raise collab.PolicyViolation("EMPTY_PROPOSAL", "A proposal must name at least one item.")
        for entry in proposed:
            item = next((i for i in record.items if str(i.id) == str(entry.get("item_id"))), None)
            if item is None or item.status != "ready" or item.selected_part_id is None:
                raise collab.PolicyViolation("ITEM_NOT_READY", "Every proposed item must be resolved by the compatibility search first.")
            compatible = {c.part_id for c in item.candidates}
            if entry.get("part_id") != item.selected_part_id or item.selected_part_id not in compatible:
                raise collab.PolicyViolation("NOT_COMPATIBLE", "Proposed part is not the compatible selection for this item.")

    def _clarification_spec(self, record: EnquiryRecord, data: dict[str, Any]) -> PendingSpec:
        from . import domain
        from .steps import _set_pending

        code = str(data.get("code") or record.pending_code or "needs_model")
        if code == "confirm_identifiers" and record.nameplate is not None:
            plate = record.nameplate
            return PendingSpec(
                "nameplate_confirmation", "confirm_identifiers", None,
                "Please confirm the model and serial read from your nameplate photo." if record.locale == "en" else "من فضلك أكّد الموديل والرقم التسلسلي المقروءين من صورة لوحة الصنع.",
                [{"value": "model", "label": plate.model_text or ""}, {"value": "serial", "label": plate.serial_text or ""}],
            )
        item = next((i for i in record.items if str(i.id) == str(data.get("item_id"))), None) or next(
            (i for i in record.items if i.status == "needs_information"), record.items[0] if record.items else None
        )
        if item is None:
            return PendingSpec("clarification", code, None, domain.question_text(code, record.locale))
        options = []
        if code in ("ambiguous_part", "mismatch"):
            options = [{"value": str(c.part_id), "label": f"{c.part_number} — {c.name_en}", "part_number": c.part_number} for c in item.candidates[:3]]
        if record.pending_item_id != item.id or record.pending_code != code:
            _set_pending(record, item, code, options)
        return PendingSpec("clarification", code, item.id, record.pending_question or domain.question_text(code, record.locale), options)

    async def _run_tool(self, ctx: _Ctx, work: EnquiryRecord, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        pipeline = ctx.pipeline
        run = ctx.run
        item = next((i for i in work.items if str(i.id) == str(args.get("item_id"))), None)
        if tool == "identification":
            report = await pipeline.identify(work, item_ids=[item.id])
            state = "resolved" if item.configuration_id is not None else "needs_information"
            data = {"item_id": str(item.id), "state": state, "code": item.clarification_code, "label": item.configuration_label, "note": item.identification_note}
            if state != "resolved":
                # The specialist decides whether to ask; the pending question is opened by the controller.
                work.pending_question = None
                work.pending_code = None
                work.pending_item_id = None
                item.status = "unresolved"
                summary = f"Not resolved: {item.identification_note}"
            else:
                summary = f"Identified {item.configuration_label}. {item.identification_note}"
            return {"summary": summary, "data": data, "report": report}
        if tool == "compatibility_search":
            mode = args.get("mode", "standard")
            if mode == "in_stock_alternatives":
                alts = await self._in_stock_alternatives(pipeline, work, item)
                run.board.setdefault("alternatives_checked", []).append(str(item.id))
                summary = "No other compatible part has stock at the destination." if not alts else f"{len(alts)} other compatible part(s) have stock: " + ", ".join(a["part_number"] for a in alts[:3])
                return {"summary": summary, "data": {"item_id": str(item.id), "mode": mode, "alternatives": alts}}
            if mode == "alternatives":
                quoted = item.part_numbers
                names = [str((pipeline.catalogue.part_by_number(n) or {}).get("name_en", "")) for n in quoted]
                item.part_numbers = []
                item.description = next((n for n in names if n), item.description)
                item.candidates = []
                item.status = "unresolved"
                item.clarification_code = None
            report = await pipeline.search(work, item_ids=[item.id])
            code = item.clarification_code
            action = "resolve" if item.status == "ready" else "needs_staff" if item.status == "unavailable" else ("mismatch" if code == "mismatch" else "clarify")
            if item.status == "needs_information":
                work.pending_question = None
                work.pending_code = None
                work.pending_item_id = None
            selected = next((c for c in item.candidates if c.part_id == item.selected_part_id), None)
            data = {
                "item_id": str(item.id), "mode": mode, "action": action,
                "selected_part_number": selected.part_number if selected else None,
                "incompatible_numbers": list(item.part_numbers) if action == "mismatch" else [],
                "candidates": [{"part_id": c.part_id, "part_number": c.part_number, "name_en": c.name_en, "score": c.score, "source_reference": c.source_reference} for c in item.candidates[:3]],
                "margin": item.margin,
            }
            return {"summary": report.detail, "data": data, "refs": report.evidence_refs, "report": report}
        if tool == "fulfilment":
            if item.status == "needs_information" and item.clarification_code == "quantity":
                return {"summary": "Quantity is still needed before planning.", "data": {"item_id": str(item.id), "state": "needs_information", "code": "quantity"}}
            if item.plan_strategy:
                # A second plan for the same item is a re-plan requested after verification.
                run.board["replanned"] = True
            report = await pipeline.plan(work)
            if report.pending is not None:
                work.pending_question = None
                work.pending_code = None
                work.pending_item_id = None
                item.status = "ready"
                return {"summary": report.detail, "data": {"item_id": str(item.id), "state": "needs_information", "code": "quantity"}}
            return {"summary": report.detail, "data": {"item_id": str(item.id), "state": "planned", "strategy": item.plan_strategy, "shortage": item.shortage}, "report": report}
        if tool == "verification":
            draft = await pipeline.draft(work)
            verified = await pipeline.verify(work)
            self._event(work, run, draft)
            return {"summary": verified.detail, "data": {"passed": verified.data["passed"], "failures": verified.data["failures"], "draft_id": str(work.draft_id)}, "report": verified}
        raise collab.PolicyViolation("TOOL_NOT_ALLOWED", tool)

    async def _in_stock_alternatives(self, pipeline: Pipeline, record: EnquiryRecord, item: Any) -> list[dict[str, Any]]:
        if item.configuration_id is None or item.selected_part_id is None:
            return []
        catalogue = pipeline.catalogue
        selected = catalogue.part_payload(item.selected_part_id) or {}
        compatibility = await catalogue.repository.fetch_compatibility(item.configuration_id)
        destination = catalogue.warehouse_code(record.destination_warehouse_id)
        out = []
        for row in compatibility:
            if row.part_id == item.selected_part_id:
                continue
            part = catalogue.part_payload(row.part_id) or {}
            if part.get("name_en") != selected.get("name_en"):
                continue
            stock = {s.warehouse_code: s.available for s in catalogue.stock.observe(row.part_id)}
            if stock.get(destination, 0) >= int(item.quantity or 1):
                out.append({"part_id": row.part_id, "part_number": part.get("part_number"), "available_at_destination": stock.get(destination, 0), "source_reference": row.source_reference})
        return out


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _scrub(data: dict[str, Any]) -> dict[str, Any]:
    """Keep exchange payloads JSON-safe and bounded (no objects, no long strings)."""
    def clean(value: Any, depth: int = 0) -> Any:
        if depth > 4:
            return None
        if isinstance(value, dict):
            return {str(k): clean(v, depth + 1) for k, v in list(value.items())[:40]}
        if isinstance(value, (list, tuple)):
            return [clean(v, depth + 1) for v in list(value)[:40]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value[:600] if isinstance(value, str) else value
        return str(value)[:200]
    return clean(data)


def _state_from_record(state: EnquiryState, record: EnquiryRecord) -> EnquiryState:
    """Project the committed record onto the typed graph state the router reads."""
    first = record.messages[0] if record.messages else None
    items = [
        ItemState(
            id=i.id,
            request=ItemInput(
                description=i.description[:1000] or "item",
                quantity=i.quantity,
                model_text=i.model_text,
                serial_text=i.serial_text,
                source_message_id=first.id if first else i.id,
                source_start=0,
                source_end=min(len(first.body), 1000) if first else 0,
            ),
            configuration_id=i.configuration_id,
            candidate_part_ids=[c.part_id for c in i.candidates],
            selected_part_id=i.selected_part_id,
            status=i.status,
        )
        for i in record.items
    ]
    phase = state.phase
    if record.step == "needs_staff" or (record.verification is not None and not record.verification.passed):
        phase = "needs_staff"
    elif record.nameplate is not None and not record.nameplate.confirmed:
        phase = "confirm"
    elif any(i.plan_strategy for i in record.items) and record.draft_id is None:
        phase = "planned"
    elif record.verification_id is not None:
        phase = "verified"
    elif record.draft_id is not None:
        phase = "drafted"
    elif items:
        phase = "intake_done" if phase in ("", "intake") else phase
    return state.model_copy(update={
        "items": items,
        "pending_question": record.pending_question,
        "draft_id": record.draft_id,
        "verification_id": record.verification_id,
        "catalogue_version_id": record.catalogue_version_id,
        "phase": phase,
    })


__all__ = ["RunExecutor", "Discarded", "reset_derived"]
