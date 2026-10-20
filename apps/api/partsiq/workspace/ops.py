"""Ops and administration ports for the workspace runtime (F55–F65 + users/audit/jobs/analytics).

Every admin operation requires a server-granted capability (:mod:`partsiq.auth.actors`) and acts
only on the caller's workspace: a demo visitor's "admin" preview changes its own disposable
sandbox (synthetic personas, a sandbox catalogue version) and nothing shared. Real account
administration goes through the injected :class:`AccountDirectory` (Supabase Auth admin API) and
is audited. Metrics are computed from recorded events only; a value that was not measured is
returned as ``None`` (rendered "not measured"), never as an invented zero.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from partsiq.auth.actors import actor_kind, capabilities_for, require_capability
from partsiq.catalogue.models import build_snapshot
from partsiq.catalogue.validation import validate_snapshot
from partsiq.core.api_models import (
    AnalyticsSyncView,
    ArchiveResult,
    CatalogueRecord,
    EvalRequest,
    ImportCreate,
    ImportIssue,
    ImportUpload,
    ImportView,
    InboxQuery,
    JobView,
    MachinePage,
    MachineSave,
    MissingPage,
    MissingUpdate,
    MissingView,
    PageQuery,
    PublishRequest,
    RepeatRequest,
    SavedMachineView,
    VersionList,
    VersionView,
)
from partsiq.core.contracts import (
    ActorContext,
    EnquiryCreate,
    EnquiryView,
    EvalOutput,
    UploadTicket,
)
from partsiq.core.errors import PartsIQError

from .records import JobRecord, MachineRecord, MemberRecord, utcnow
from .tenant import EvalRunRecord, ImportBatch

IMPORT_TYPES = ("parts", "part_aliases", "part_compatibility", "part_supersessions", "model_configurations")
IMPORT_COLUMNS = (
    "entity_type", "part_number", "name_en", "name_ar", "description_en", "category", "unit_of_measure",
    "is_active", "alias", "language", "brand", "model_code", "config_code", "quantity_per_unit",
    "source_reference", "old_part_number", "new_part_number", "effective_date", "reason",
    "description", "serial_start", "serial_end",
)
MAX_IMPORT_ROWS = 2000
_FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")
_VERSION_NS = uuid5(NAMESPACE_URL, "partsiq.catalogue.import")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, int(round(0.95 * len(ordered) + 0.5)) - 1)
    return ordered[min(index, len(ordered) - 1)]


class OpsMixin:
    # ================================================================== saved machines (F55)

    async def save(self, actor: ActorContext, request: MachineSave, key: UUID) -> SavedMachineView:
        require_capability(actor, "machines.manage_own")
        ws = await self.workspace(actor)
        async with ws.lock:
            existing = next((m for m in ws.machines.values() if m.owner_id == actor.user_id and m.idempotency_key == key), None)
            if existing is not None:
                return _machine_view(existing)
            if sum(1 for m in ws.machines.values() if m.owner_id == actor.user_id and not m.archived) >= 50:
                raise PartsIQError("QUOTA_EXCEEDED", detail="You can save up to 50 machines.")
            machine = MachineRecord(id=uuid4(), owner_id=actor.user_id, label=request.label, model_text=request.model_text, serial_text=request.serial_text, created_at=utcnow(), idempotency_key=key)
            ws.machines[machine.id] = machine
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="machine.saved", entity_type="machine", entity_id=str(machine.id), request_id=actor.request_id)
            return _machine_view(machine)

    async def list_machines(self, actor: ActorContext, query: PageQuery) -> MachinePage:
        ws = await self.workspace(actor)
        rows = sorted((m for m in ws.machines.values() if m.owner_id == actor.user_id and not m.archived), key=lambda m: m.created_at, reverse=True)
        start = int(query.cursor) if query.cursor and query.cursor.isdigit() else 0
        page = rows[start: start + query.limit]
        return MachinePage(items=[_machine_view(m) for m in page], next_cursor=str(start + query.limit) if start + query.limit < len(rows) else None)

    async def archive(self, actor: ActorContext, machine_id: UUID) -> ArchiveResult:
        ws = await self.workspace(actor)
        async with ws.lock:
            machine = ws.machines.get(machine_id)
            if machine is None or machine.owner_id != actor.user_id or machine.archived:
                raise PartsIQError("NOT_FOUND", internal_detail="machine not found")
            machine.archived = True
            return ArchiveResult(id=machine.id)

    async def machine_check(self, actor: ActorContext, machine_id: UUID) -> dict[str, Any]:
        """Re-validate a saved machine against the CURRENT catalogue (never trust an old match)."""
        from .domain import identify_item
        from .records import ItemRecord

        ws = await self.workspace(actor)
        machine = ws.machines.get(machine_id)
        if machine is None or machine.owner_id != actor.user_id or machine.archived:
            raise PartsIQError("NOT_FOUND", internal_detail="machine not found")
        probe = ItemRecord(id=uuid4(), ordinal=1, description=machine.model_text, quantity=None, quantity_assumed=False, model_text=machine.model_text, serial_text=machine.serial_text, config_code_text=None, part_numbers=[])
        outcome = await identify_item(probe, ws.catalogue)
        return {"id": str(machine.id), "state": outcome.state, "configuration_label": outcome.label, "note": outcome.note, "catalogue_version_id": str(ws.catalogue.version_id)}

    # ================================================================== repeat enquiry (F56)

    async def repeat_enquiry(self, actor: ActorContext, source_enquiry_id: UUID, request: RepeatRequest, key: UUID) -> EnquiryView:
        ws = await self.workspace(actor)
        source = self._record(actor, ws, source_enquiry_id)
        if source.owner_id != actor.user_id and ws.kind != "demo":
            raise PartsIQError("NOT_FOUND", internal_detail="only the owner can repeat")
        replay = ws.idempotency.get(("repeat", key))
        if replay is not None:
            return replay[1]
        text = source.messages[0].body if source.messages else ""
        view = await self.create_enquiry_atomic(actor, EnquiryCreate(text=text, locale=request.locale, destination_warehouse_id=request.destination_warehouse_id))
        ws.idempotency[("repeat", key)] = ("repeat", view)
        return view

    # ================================================================== jobs (F51/F52)

    def _jobs(self, ws: Any) -> list[JobView]:
        out = []
        for run in ws.runs.values():
            status = {
                "queued": "pending", "running": "running", "pausing": "running", "paused": "pending",
                "waiting_user": "pending", "waiting_consent": "pending", "blocked": "failed", "awaiting_review": "succeeded",
                "completed": "succeeded", "cancelled": "cancelled", "failed": "failed", "superseded": "cancelled", "needs_staff": "succeeded",
            }.get(run.status, "pending")
            out.append(JobView(id=run.id, status=status, kind=f"workflow:{run.mode}", attempts=1 + run.usage.retries, error_code=run.blocked_reason, resource_id=run.enquiry_id))  # type: ignore[arg-type]
        for job in ws.jobs.values():
            out.append(JobView(id=job.id, status=job.status, kind=job.kind, attempts=job.attempts, error_code=job.error_code, resource_id=job.resource_id))
        return out

    async def get_status(self, actor: ActorContext, job_id: UUID) -> JobView:
        ws = await self.workspace(actor)
        run = ws.runs.get(job_id)
        if run is not None:
            self._record(actor, ws, run.enquiry_id)
        elif job_id in ws.jobs:
            job = ws.jobs[job_id]
            if job.owner_id != actor.user_id and not (actor_kind(actor) == "demo" or "admin" in actor.roles):
                raise PartsIQError("NOT_FOUND", internal_detail="job not visible")
        else:
            raise PartsIQError("NOT_FOUND", internal_detail="job not found")
        return next(j for j in self._jobs(ws) if j.id == job_id)

    async def list_jobs(self, actor: ActorContext, *, status: str | None, cursor: int, limit: int) -> dict[str, Any]:
        require_capability(actor, "jobs.read")
        ws = await self.workspace(actor)
        rows = self._jobs(ws)
        if status:
            rows = [j for j in rows if j.status == status]
        detail = []
        for job in rows:
            run = ws.runs.get(job.id)
            detail.append({
                **job.model_dump(mode="json"),
                "created_at": (run.created_at if run else ws.jobs[job.id].created_at).isoformat(),
                "updated_at": (run.updated_at if run else ws.jobs[job.id].updated_at).isoformat(),
                "error_category": _error_category(job.error_code),
                "retryable": job.status == "failed",
                "execution_source": run.execution_source if run else "system",
                "revision": run.revision if run else None,
            })
        detail.sort(key=lambda j: j["updated_at"], reverse=True)
        counts: dict[str, int] = {}
        for job in rows:
            counts[job.status] = counts.get(job.status, 0) + 1
        return {"items": detail[cursor: cursor + limit], "total": len(detail), "counts": counts, "next_cursor": cursor + limit if cursor + limit < len(detail) else None, "dependencies": self.dependency_status()}

    def dependency_status(self) -> list[dict[str, Any]]:
        status = self.execution_status()
        durable = getattr(self, "_store", None) is not None
        worker = durable and getattr(self.executor, "nameplates", None) is not None
        return [
            {"name": "Workflow engine (LangGraph)", "state": "available", "detail": "Checkpoints in PostgreSQL; interrupted runs resume after a restart." if durable else "In-process; checkpoints in memory for this deployment."},
            {"name": "Catalogue", "state": "available", "detail": f"Synthetic {self.settings.data_source} catalogue (seed 42)."},
            {"name": "Live AI provider", "state": "available" if status["live_available"] else "unavailable", "detail": (status["live_unavailable_reason"] or "Configured with a confirmed allowance (invited accounts only; the public demo uses fixture AI).")},
            {"name": "Supabase Auth (accounts)", "state": "configured" if status["accounts_enabled"] else "not configured", "detail": "Invited-account sign-in." if status["accounts_enabled"] else "SUPABASE_URL is not set on this server."},
            {"name": "Account directory", "state": "configured" if self.directory is not None else "not configured", "detail": "Supabase admin API (service role, server-side)." if self.directory is not None else "SUPABASE_SERVICE_ROLE_KEY is not set; user administration is unavailable."},
            {"name": "PostgreSQL persistence", "state": "available" if durable else "not configured", "detail": "Account workspace, runs, jobs and the AI allowance ledger persist in PostgreSQL. Demo sandboxes stay in memory." if durable else "Operational state is held in process memory in this deployment."},
            {"name": "Redis / worker", "state": "configured" if worker else "not configured", "detail": "Background worker reads nameplate photos and renders PDFs; PostgreSQL jobs with Redis wake-ups." if worker else "Runs execute in the API process; there is no external queue in this deployment."},
            {"name": "PDF rendering", "state": "configured" if worker else "unavailable", "detail": "Chromium in the background worker (approved revisions only)." if worker else "Needs database mode and the background worker."},
        ]

    async def retry_failed(self, actor: ActorContext, job_id: UUID, expected_revision: int, key: UUID) -> JobView:
        require_capability(actor, "jobs.retry")
        ws = await self.workspace(actor)
        replay = ws.idempotency.get(("retry", key))
        if replay is not None:
            return replay[1]
        run = ws.runs.get(job_id)
        if run is None or run.status not in ("failed", "blocked"):
            raise PartsIQError("CONFLICT", detail="Only a failed or blocked job can be retried.")
        view = await self.start_new_run(actor, run.enquiry_id, mode=run.mode, expected_revision=expected_revision)
        job = next(j for j in self._jobs(ws) if str(j.id) == view["id"])
        ws.idempotency[("retry", key)] = ("retry", job)
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="job.retried", entity_type="run", entity_id=str(job_id), request_id=actor.request_id, enquiry_id=run.enquiry_id, revision=expected_revision)
        return job

    # ================================================================== catalogue (F57 + detail)

    async def catalogue_browse(self, actor: ActorContext, *, query: str | None, category: str | None, model_code: str | None, cursor: int, limit: int) -> dict[str, Any]:
        require_capability(actor, "enquiry.read_own")
        ws = await self.workspace(actor)
        catalogue = ws.catalogue
        allowed: set[int] | None = None
        if model_code:
            models = await catalogue.repository.fetch_models()
            model = next((m for m in models if m.model_code.lower() == model_code.lower()), None)
            allowed = set()
            if model:
                for cfg in model.configurations:
                    allowed |= {row.part_id for row in await catalogue.repository.fetch_compatibility(cfg.id)}
        aliases: dict[str, list[str]] = {}
        for record in catalogue.records_of("part_aliases"):
            aliases.setdefault(str(record.payload.get("part_number")), []).append(str(record.payload.get("alias")))
        rows = []
        needle = (query or "").strip().casefold()
        for record in catalogue.records_of("parts"):
            p = record.payload
            pid = int(p["id"])
            if allowed is not None and pid not in allowed:
                continue
            if category and p.get("category") != category:
                continue
            hay = f"{p.get('part_number')} {p.get('name_en')} {p.get('name_ar')} {' '.join(aliases.get(str(p.get('part_number')), []))}".casefold()
            if needle and needle not in hay:
                continue
            rows.append({
                "id": pid, "part_number": p.get("part_number"), "name_en": p.get("name_en"), "name_ar": p.get("name_ar"),
                "category": p.get("category"), "unit_of_measure": p.get("unit_of_measure"), "is_active": bool(p.get("is_active")),
                "aliases": aliases.get(str(p.get("part_number")), [])[:4],
            })
        rows.sort(key=lambda r: r["id"])
        categories = sorted({str(r.payload.get("category")) for r in catalogue.records_of("parts")})
        models = sorted({str(r.payload.get("model_code")) for r in catalogue.records_of("equipment_models")})
        active = next((v for v in catalogue.versions if v.state == "published"), None)
        return {
            "items": rows[cursor: cursor + limit], "total": len(rows),
            "next_cursor": cursor + limit if cursor + limit < len(rows) else None,
            "categories": categories, "models": models,
            "version": None if active is None else {"id": str(active.id), "label": active.label, "published_at": active.published_at.isoformat() if active.published_at else None, "source": active.source, "content_sha256": active.content_sha256},
        }

    async def catalogue_part(self, actor: ActorContext, part_number: str) -> dict[str, Any]:
        require_capability(actor, "enquiry.read_own")
        ws = await self.workspace(actor)
        catalogue = ws.catalogue
        part = catalogue.part_by_number(part_number)
        if part is None:
            raise PartsIQError("NOT_FOUND", detail="That part number is not in the active catalogue.")
        pid = int(part["id"])
        number = str(part["part_number"])
        aliases = [{"alias": r.payload.get("alias"), "language": r.payload.get("language")} for r in catalogue.records_of("part_aliases") if r.payload.get("part_number") == number]
        compat = [
            {"brand": r.payload.get("brand"), "model_code": r.payload.get("model_code"), "config_code": r.payload.get("config_code"), "quantity_per_unit": r.payload.get("quantity_per_unit"), "source_reference": r.payload.get("source_reference")}
            for r in catalogue.records_of("part_compatibility") if r.payload.get("part_number") == number
        ]
        supersedes = [{"old": r.payload.get("old_part_number"), "effective_date": r.payload.get("effective_date"), "reason": r.payload.get("reason")} for r in catalogue.records_of("part_supersessions") if r.payload.get("new_part_number") == number]
        superseded_by = [{"new": r.payload.get("new_part_number"), "effective_date": r.payload.get("effective_date"), "reason": r.payload.get("reason")} for r in catalogue.records_of("part_supersessions") if r.payload.get("old_part_number") == number]
        stock = [{"warehouse_code": s.warehouse_code, "warehouse_name": s.warehouse_name, "available": s.available, "observed_at": s.observed_at.isoformat()} for s in catalogue.stock.observe(pid)]
        return {
            "id": pid, "part_number": number, "name_en": part.get("name_en"), "name_ar": part.get("name_ar"),
            "description_en": part.get("description_en"), "category": part.get("category"), "unit_of_measure": part.get("unit_of_measure"),
            "is_active": bool(part.get("is_active")), "aliases": aliases, "compatibility": compat,
            "supersedes": supersedes, "superseded_by": superseded_by, "stock": stock,
            "catalogue_version_id": str(catalogue.version_id), "synthetic": True,
        }

    # ================================================================== imports (F58/F59)

    async def stage_import(self, actor: ActorContext, request: ImportCreate) -> ImportView:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        if request.format != "csv":
            raise PartsIQError("UNSUPPORTED_MEDIA_TYPE", detail="Only CSV imports are supported in this deployment (no spreadsheet macros or formulas are evaluated).")
        async with ws.lock:
            batch = ImportBatch(id=uuid4(), filename=request.filename, format=request.format, size_bytes=request.size_bytes, state="staged", created_by=actor.user_id, created_at=utcnow(), updated_at=utcnow(), base_version_id=ws.catalogue.version_id)
            ws.imports[batch.id] = batch
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="import.staged", entity_type="import", entity_id=str(batch.id), request_id=actor.request_id, payload={"filename": request.filename[:80]})
            return _import_view(batch)

    async def read_import(self, actor: ActorContext, import_id: UUID) -> ImportView:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        return _import_view(self._batch(ws, import_id))

    def _batch(self, ws: Any, import_id: UUID) -> ImportBatch:
        batch = ws.imports.get(import_id)
        if batch is None:
            raise PartsIQError("NOT_FOUND", internal_detail="import not found")
        return batch

    async def sign_import_upload(self, actor: ActorContext, import_id: UUID, request: ImportUpload) -> UploadTicket:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        batch = self._batch(ws, import_id)
        if request.media_type != "text/csv":
            raise PartsIQError("UNSUPPORTED_MEDIA_TYPE", detail="Only CSV imports are supported in this deployment.")
        return UploadTicket(attachment_id=batch.id, upload_url=f"/v1/admin/imports/{batch.id}/content", expires_at=utcnow() + timedelta(minutes=10))

    async def upload_import_content(self, actor: ActorContext, import_id: UUID, data: bytes) -> dict[str, Any]:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        async with ws.lock:
            batch = self._batch(ws, import_id)
            if batch.state not in ("staged", "uploaded", "invalid", "validated"):
                raise PartsIQError("CONFLICT", detail="This batch can no longer be changed.")
            if len(data) > 1_048_576 or len(data) > batch.size_bytes * 4 + 1024:
                raise PartsIQError("PAYLOAD_TOO_LARGE", detail="The CSV is larger than the import limit (1 MB).")
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise PartsIQError("VALIDATION_FAILED", detail="The CSV must be UTF-8 text.") from exc
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None or "entity_type" not in [f.strip() for f in reader.fieldnames]:
                raise PartsIQError("VALIDATION_FAILED", detail="The first row must be a header containing entity_type.")
            unknown = [f for f in reader.fieldnames if f and f.strip() not in IMPORT_COLUMNS]
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append({(k or "").strip(): (v or "") for k, v in row.items()})
                if len(rows) > MAX_IMPORT_ROWS:
                    raise PartsIQError("PAYLOAD_TOO_LARGE", detail=f"Imports are limited to {MAX_IMPORT_ROWS} rows.")
            batch.rows = rows
            batch.state = "uploaded"
            batch.issues = [{"row_number": 1, "field": f, "code": "UNKNOWN_COLUMN", "message": f"Column '{f}' is not part of the import format and will be ignored."} for f in unknown]
            batch.content_sha256 = hashlib.sha256(data).hexdigest()
            batch.updated_at = utcnow()
            return {"rows": len(rows), "content_sha256": batch.content_sha256}

    async def validate_import(self, actor: ActorContext, import_id: UUID) -> JobView:
        """Dry run: parse rows, merge onto the active version, run the full catalogue validation."""
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        async with ws.lock:
            batch = self._batch(ws, import_id)
            if batch.state not in ("uploaded", "invalid", "validated"):
                raise PartsIQError("CONFLICT", detail="Upload a CSV before validating.")
            job = JobRecord(id=uuid4(), kind="catalog_import", status="running", attempts=1, resource_id=batch.id, owner_id=actor.user_id, created_at=utcnow(), updated_at=utcnow())
            ws.jobs[job.id] = job
            issues = [i for i in batch.issues if i["code"] == "UNKNOWN_COLUMN"]
            staged, row_keys, row_issues, preview = _stage_records(ws.catalogue, batch.rows)
            issues.extend(row_issues)
            batch.preview = preview
            if not row_issues:
                version_id = uuid5(_VERSION_NS, f"{ws.catalogue.version_id}:{batch.content_sha256}")
                snapshot = build_snapshot(version_id=version_id, source="fixture", records=staged)
                for issue in validate_snapshot(snapshot):
                    row = row_keys.get((issue.entity_type, issue.entity_key))
                    issues.append({"row_number": row or 0, "field": issue.field, "code": issue.code, "message": issue.message})
                batch.staged_snapshot = snapshot if not [i for i in issues if i["code"] != "UNKNOWN_COLUMN"] else None
                batch.version_id = version_id if batch.staged_snapshot is not None else None
            blocking = [i for i in issues if i["code"] != "UNKNOWN_COLUMN"]
            batch.issues = issues
            batch.state = "validated" if not blocking else "invalid"
            batch.base_version_id = ws.catalogue.version_id
            if batch.staged_snapshot is not None:
                batch.content_sha256 = batch.staged_snapshot.content_sha256
            batch.updated_at = utcnow()
            job.status = "succeeded"
            job.updated_at = utcnow()
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="import.validated", entity_type="import", entity_id=str(batch.id), request_id=actor.request_id, payload={"state": batch.state, "issues": len(blocking)})
            return JobView(id=job.id, status="succeeded", kind="catalog_import", attempts=1, error_code=None if not blocking else "IMPORT_INVALID", resource_id=batch.id)

    async def import_preview(self, actor: ActorContext, import_id: UUID) -> dict[str, Any]:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        batch = self._batch(ws, import_id)
        return {
            **_import_view(batch).model_dump(mode="json"),
            "filename": batch.filename, "preview": batch.preview, "created_at": batch.created_at.isoformat(),
            "base_version_id": str(batch.base_version_id) if batch.base_version_id else None,
            "active_version_id": str(ws.catalogue.version_id),
            "base_is_active": batch.base_version_id == ws.catalogue.version_id,
        }

    async def list_imports(self, actor: ActorContext) -> list[dict[str, Any]]:
        require_capability(actor, "catalogue.import")
        ws = await self.workspace(actor)
        return [
            {"id": str(b.id), "filename": b.filename, "state": b.state, "rows": len(b.rows), "issues": len([i for i in b.issues if i["code"] != "UNKNOWN_COLUMN"]), "created_at": b.created_at.isoformat(), "version_id": str(b.version_id) if b.version_id else None}
            for b in sorted(ws.imports.values(), key=lambda b: b.created_at, reverse=True)
        ]

    async def request_publish(self, actor: ActorContext, import_id: UUID, request: PublishRequest, key: UUID) -> JobView:
        require_capability(actor, "catalogue.publish")
        ws = await self.workspace(actor)
        async with ws.lock:
            batch = self._batch(ws, import_id)
            replay = ws.idempotency.get(("publish", key))
            if replay is not None:
                if replay[0] != request.model_dump_json():
                    raise PartsIQError("IDEMPOTENCY_MISMATCH", detail="This idempotency key was used for a different publish.")
                return replay[1]
            if batch.state != "validated" or batch.staged_snapshot is None:
                raise PartsIQError("CONFLICT", detail="Only a validated batch with no blocking issues can be published.")
            if request.content_sha256 != batch.staged_snapshot.content_sha256:
                raise PartsIQError("CONFLICT", detail="The validated content changed. Validate again before publishing.")
            if request.expected_active_version_id != ws.catalogue.version_id or batch.base_version_id != ws.catalogue.version_id:
                raise PartsIQError("STALE_CATALOGUE", detail="Another version became active. Re-validate this batch against the current version.")
            job = JobRecord(id=uuid4(), kind="catalog_publish", status="succeeded", attempts=1, resource_id=batch.id, owner_id=actor.user_id, created_at=utcnow(), updated_at=utcnow())
            ws.jobs[job.id] = job
            if ws.store is not None:
                # Durable compare-and-set publication + catalogue mirror first; memory follows.
                await ws.store.publish_version(batch.staged_snapshot, label=f"Import {batch.filename[:40]}", actor=actor.user_id)
            ws.catalogue.activate(batch.staged_snapshot, published_by=actor.user_id, import_id=batch.id, label=f"Import {batch.filename[:40]}")
            batch.state = "published"
            batch.updated_at = utcnow()
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="catalogue.published", entity_type="catalogue_version", entity_id=str(batch.staged_snapshot.version_id), request_id=actor.request_id, payload={"import_id": str(batch.id)})
            view = JobView(id=job.id, status="succeeded", kind="catalog_publish", attempts=1, error_code=None, resource_id=batch.staged_snapshot.version_id)
            ws.idempotency[("publish", key)] = (request.model_dump_json(), view)
            return view

    async def list_versions(self, actor: ActorContext) -> VersionList:
        require_capability(actor, "catalogue.browse")
        ws = await self.workspace(actor)
        return VersionList(items=[
            VersionView(id=v.id, label=v.label, state=v.state, content_sha256=v.content_sha256, published_at=v.published_at, source="fixture" if v.source == "fixture" else "snowflake")
            for v in reversed(ws.catalogue.versions)
        ])

    # ================================================================== evaluations (F62)

    async def enqueue_run(self, actor: ActorContext, request: EvalRequest, key: UUID) -> JobView:
        from partsiq.evaluation.runner import dataset_sha256, evaluate_case, load_cases

        require_capability(actor, "evaluation.run")
        if request.suite == "live":
            raise PartsIQError("CREDIT_UNAVAILABLE", detail="A live evaluation needs the live provider and a confirmed allowance.")
        ws = await self.workspace(actor)
        replay = ws.idempotency.get(("eval", key))
        if replay is not None:
            return replay[1]
        cases = load_cases()
        run = EvalRunRecord(id=uuid4(), suite=request.suite, state="running", created_by=actor.user_id, created_at=utcnow(), dataset_sha256=dataset_sha256(cases))
        ws.evaluations[run.id] = run
        results = []
        for case in cases:
            actual = await self._solve_case(case)
            results.append(evaluate_case(case, actual))
        run.results = results
        labelled = [r for r, c in zip(results, cases) if c.expected_status != "unlabelled"]
        run.total = len(labelled)
        run.passed = sum(1 for r in labelled if r.passed)
        run.failed = run.total - run.passed
        run.state = "succeeded"
        job = JobView(id=run.id, status="succeeded", kind="evaluation", attempts=1, error_code=None, resource_id=run.id)
        ws.idempotency[("eval", key)] = ("eval", job)
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="evaluation.run", entity_type="evaluation", entity_id=str(run.id), request_id=actor.request_id, payload={"passed": run.passed, "total": run.total})
        return job

    async def _solve_case(self, case: Any) -> EvalOutput:
        """Run one labelled case through the REAL guided pipeline in a scratch record (fixture)."""
        from .catalogue import fixture_catalogue_context
        from .language import FixtureLanguage
        from .records import EnquiryRecord
        from .steps import Pipeline
        from partsiq.core.contracts import MessageView

        if case.expected_status == "unlabelled":
            return EvalOutput(status="unlabelled", part_ids=[], clarification_code="none")
        catalogue = fixture_catalogue_context(self._snapshot_factory())
        pipe = Pipeline(catalogue, FixtureLanguage())
        now = utcnow()
        eid = uuid4()
        record = EnquiryRecord(id=eid, owner_id=uuid4(), session_id=None, session_generation=None, locale="en", destination_warehouse_id=1, created_at=now, updated_at=now, revision=1, status="processing", language="en", urgency="normal")
        record.messages = [MessageView(id=uuid4(), enquiry_id=eid, revision=1, kind="customer", body=case.input_text, created_at=now)]
        for step in ("intake", "identify", "search", "plan", "draft", "verify"):
            if step in ("draft", "verify") and not any(i.status == "ready" for i in record.items):
                break
            report = await getattr(pipe, step)(record)
            if report.status == "waiting":
                ready = [i.selected_part_id for i in record.items if i.selected_part_id]
                return EvalOutput(status="needs_information", part_ids=[c.part_id for i in record.items for c in i.candidates[:3]] if record.pending_code == "ambiguous_part" else [p for p in ready if p], clarification_code=record.pending_code or "none")
            if report.status == "failed":
                return EvalOutput(status="needs_staff", part_ids=[], clarification_code="none")
        if record.verification is not None and record.verification.passed:
            return EvalOutput(status="awaiting_review", part_ids=[i.selected_part_id for i in record.items if i.selected_part_id], clarification_code="none")
        return EvalOutput(status="needs_staff", part_ids=[], clarification_code="none")

    async def read_run(self, actor: ActorContext, run_id: UUID) -> Any:
        from partsiq.core.api_models import EvaluationView

        require_capability(actor, "evaluation.run")
        ws = await self.workspace(actor)
        run = ws.evaluations.get(run_id)
        if run is None:
            raise PartsIQError("NOT_FOUND", internal_detail="evaluation not found")
        return EvaluationView(run_id=run.id, state=run.state, total=run.total, passed=run.passed, failed=run.failed, results=run.results)

    async def list_evaluations(self, actor: ActorContext) -> list[dict[str, Any]]:
        require_capability(actor, "evaluation.run")
        ws = await self.workspace(actor)
        return [
            {"id": str(r.id), "suite": r.suite, "state": r.state, "total": r.total, "passed": r.passed, "failed": r.failed, "dataset": r.labelled_set, "dataset_sha256": r.dataset_sha256, "created_at": r.created_at.isoformat()}
            for r in sorted(ws.evaluations.values(), key=lambda r: r.created_at, reverse=True)
        ]

    async def list_corrections(self, actor: ActorContext) -> list[dict[str, Any]]:
        require_capability(actor, "evaluation.run")
        ws = await self.workspace(actor)
        return [
            {"id": str(c.id), "enquiry_id": str(c.enquiry_id), "revision": c.revision, "field": c.field, "before": c.before, "after": c.after, "reviewed": c.reviewed, "curated_case_id": c.curated_case_id, "created_at": c.created_at.isoformat()}
            for c in sorted(ws.corrections.values(), key=lambda c: c.created_at, reverse=True)
        ]

    async def mark_correction_reviewed(self, actor: ActorContext, correction_id: UUID) -> dict[str, Any]:
        require_capability(actor, "evaluation.run")
        ws = await self.workspace(actor)
        correction = ws.corrections.get(correction_id)
        if correction is None:
            raise PartsIQError("NOT_FOUND", internal_detail="correction not found")
        correction.reviewed = True
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="correction.reviewed", entity_type="correction", entity_id=str(correction.id), request_id=actor.request_id)
        return {"id": str(correction.id), "reviewed": True}

    # ================================================================== missing parts (F60)

    async def list_missing(self, actor: ActorContext, query: InboxQuery) -> MissingPage:
        require_capability(actor, "review.queue")
        ws = await self.workspace(actor)
        rows = []
        for record in ws.enquiries.values():
            if not self._can_review(actor, ws, record):
                continue
            for item in record.items:
                if item.status == "unavailable":
                    state = ws.idempotency.get(("missing", item.id), (None, ("open", None)))[1]
                    rows.append(MissingView(item_id=item.id, enquiry_id=record.id, state=state[0], note=state[1], updated_at=record.updated_at))
        start = int(query.cursor) if query.cursor and query.cursor.isdigit() else 0
        return MissingPage(items=rows[start: start + query.limit], next_cursor=str(start + query.limit) if start + query.limit < len(rows) else None)

    async def update_missing(self, actor: ActorContext, item_id: UUID, update: MissingUpdate) -> MissingView:
        require_capability(actor, "review.decide")
        ws = await self.workspace(actor)
        for record in ws.enquiries.values():
            item = next((i for i in record.items if i.id == item_id), None)
            if item is None or not self._can_review(actor, ws, record):
                continue
            if update.expected_revision != record.revision:
                raise PartsIQError("STALE_REVISION", detail="The enquiry changed. Reload first.")
            ws.idempotency[("missing", item.id)] = ("missing", (update.state, update.note))
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="missing_part.updated", entity_type="item", entity_id=str(item.id), request_id=actor.request_id, enquiry_id=record.id, revision=record.revision, payload={"state": update.state})
            return MissingView(item_id=item.id, enquiry_id=record.id, state=update.state, note=update.note, updated_at=utcnow())
        raise PartsIQError("NOT_FOUND", internal_detail="item not found")

    # ================================================================== analytics (F63) + overview

    async def samples(self, actor: ActorContext, query: Any) -> Any:
        from partsiq.analytics.service import MetricsSamples

        ws = await self.workspace(actor)
        rows = [r for r in ws.enquiries.values() if query.start <= r.created_at <= query.end and self._can_review(actor, ws, r)]
        return MetricsSamples(
            enquiry_count=len(rows),
            approved_count=sum(1 for r in rows if r.status == "approved"),
            clarification_count=sum(1 for r in rows if any(m.kind == "customer" and m.revision > 1 for m in r.messages)),
            review_seconds=list(ws.stage_samples.get("review_seconds", [])),
            latencies_ms=[v for k, vals in ws.stage_samples.items() if k.startswith("latency.") for v in vals],
            estimated_cost_usd=sum((run.usage.estimated_usd for run in ws.runs.values()), Decimal("0")),
        )

    async def read_sync(self, actor: ActorContext) -> AnalyticsSyncView:
        return AnalyticsSyncView(last_success_at=None, pending_events=0, source="fixture", stale=True)

    async def analytics_overview(self, actor: ActorContext) -> dict[str, Any]:
        require_capability(actor, "analytics.read")
        ws = await self.workspace(actor)
        enquiries = list(ws.enquiries.values())
        by_status: dict[str, int] = {}
        for r in enquiries:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        runs = list(ws.runs.values())
        by_mode: dict[str, dict[str, int]] = {}
        for run in runs:
            bucket = by_mode.setdefault(run.mode, {})
            bucket[run.status] = bucket.get(run.status, 0) + 1
        live_runs = [r for r in runs if r.execution_source == "live"]
        review = ws.stage_samples.get("review_seconds", [])
        latency = {k.removeprefix("latency."): {"p50_ms": _median(v), "p95_ms": _p95(v), "samples": len(v)} for k, v in ws.stage_samples.items() if k.startswith("latency.")}
        latest_eval = max(ws.evaluations.values(), key=lambda e: e.created_at, default=None)
        exchanges = sum(len(v) for v in ws.exchanges.values())
        ledger = getattr(self, "_ledger", None)
        allowance = None
        if ledger is not None:
            snap = ledger.snapshot()
            remaining = Decimal(snap["allowance_usd"]) - Decimal(snap["consumed_usd"]) - Decimal(snap["reserved_usd"])
            allowance = {"confirmed_usd": snap["allowance_usd"], "consumed_usd": snap["consumed_usd"], "reserved_usd": snap["reserved_usd"], "remaining_usd": str(remaining)}
        return {
            "scope": ws.kind,
            "scope_note": "Only this demo session's synthetic activity." if ws.kind == "demo" else "Invited-account workspace; public demo sessions are excluded.",
            "enquiries": {"total": len(enquiries), "by_status": by_status},
            "runs": {"total": len(runs), "by_mode": by_mode, "failed": sum(1 for r in runs if r.status in ("failed", "blocked")), "retries": sum(r.usage.retries for r in runs), "cancelled": sum(1 for r in runs if r.status == "cancelled")},
            "exchanges": exchanges,
            "review_seconds": {"median": _median(review), "p95": _p95(review), "samples": len(review)},
            "latency_ms": latency,
            "tokens": None if not live_runs else {"input": sum(r.usage.input_tokens for r in live_runs), "output": sum(r.usage.output_tokens for r in live_runs), "estimated_usd": str(sum((r.usage.estimated_usd for r in live_runs), Decimal("0")))},
            "tokens_note": None if live_runs else "Not measured: no live model calls were made (fixture execution).",
            "allowance": allowance,
            "allowance_note": None if allowance else "Unavailable: no confirmed live AI allowance is configured.",
            "accuracy": None if latest_eval is None else {"passed": latest_eval.passed, "total": latest_eval.total, "dataset": latest_eval.labelled_set, "run_id": str(latest_eval.id), "at": latest_eval.created_at.isoformat()},
            "accuracy_note": None if latest_eval else "Not measured: run the labelled evaluation to report accuracy with its denominator.",
            "demo_workspaces_active": self.demo_workspace_count() if ws.kind == "account" else None,
        }

    # ================================================================== audit (global, read-only)

    async def audit_search(self, actor: ActorContext, *, action: str | None, entity: str | None, actor_id: str | None, cursor: int, limit: int) -> dict[str, Any]:
        require_capability(actor, "audit.read")
        ws = await self.workspace(actor)
        rows = list(reversed(ws.audit))
        if action:
            rows = [a for a in rows if action.lower() in a.action.lower()]
        if entity:
            rows = [a for a in rows if entity.lower() in (a.entity_type + " " + a.entity_id).lower()]
        if actor_id:
            rows = [a for a in rows if a.actor_id == actor_id]
        labels = {str(m.id): m.display_name for m in ws.members.values()}
        page = rows[cursor: cursor + limit]
        return {
            "items": [
                {"seq": a.seq, "actor_type": a.actor_type, "actor_id": a.actor_id, "actor_label": labels.get(a.actor_id, a.actor_id if a.actor_type != "user" else a.actor_id[:8]), "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id, "enquiry_id": str(a.enquiry_id) if a.enquiry_id else None, "revision": a.revision, "payload": a.payload, "request_id": str(a.request_id), "created_at": a.created_at.isoformat()}
                for a in page
            ],
            "total": len(rows),
            "next_cursor": cursor + limit if cursor + limit < len(rows) else None,
        }

    # ================================================================== members / users

    async def list_members(self, actor: ActorContext) -> dict[str, Any]:
        require_capability(actor, "admin.users")
        ws = await self.workspace(actor)
        if ws.kind == "account":
            if self.directory is None:
                return {"source": "unavailable", "items": [], "note": "User administration needs SUPABASE_SERVICE_ROLE_KEY on the server (never in the browser)."}
            users = await self.directory.list_users()
            for user in users:
                ws.members[user.id] = user
            return {"source": "supabase", "items": [_member_view(m, actor) for m in users], "note": None}
        return {"source": "sandbox", "items": [_member_view(m, actor) for m in ws.members.values()], "note": "Synthetic personas in your demo session only. No email is sent and no real account is created."}

    async def invite_member(self, actor: ActorContext, *, email: str, display_name: str | None, roles: list[str]) -> dict[str, Any]:
        require_capability(actor, "admin.users")
        roles = _clean_roles(roles)
        ws = await self.workspace(actor)
        if ws.kind == "account":
            if self.directory is None:
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", detail="User invitations need the Supabase service role on the server.")
            member = await self.directory.invite(email=email, display_name=display_name, roles=roles)
            ws.members[member.id] = member
        else:
            member = MemberRecord(uuid4(), None, (display_name or email.split("@")[0])[:80] + " (synthetic invite)", roles, "invited", utcnow())
            ws.members[member.id] = member
        ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="member.invited", entity_type="member", entity_id=str(member.id), request_id=actor.request_id, payload={"roles": ",".join(roles)})
        return _member_view(member, actor)

    async def set_member_roles(self, actor: ActorContext, member_id: UUID, *, roles: list[str], expected_version: int) -> dict[str, Any]:
        require_capability(actor, "admin.users")
        roles = _clean_roles(roles)
        ws = await self.workspace(actor)
        async with ws.lock:
            member = ws.members.get(member_id)
            if member is None:
                raise PartsIQError("NOT_FOUND", internal_detail="member not found")
            if member.version != expected_version:
                raise PartsIQError("CONFLICT", detail="This member changed since you loaded it. Reload and try again.")
            if member_id == actor.user_id and "admin" not in roles:
                raise PartsIQError("FORBIDDEN", detail="You cannot remove your own administrator role.")
            before = list(member.roles)
            if ws.kind == "account":
                if self.directory is None:
                    raise PartsIQError("DEPENDENCY_UNAVAILABLE", detail="Role changes need the Supabase service role on the server.")
                await self.directory.set_roles(member_id, roles)
            member.roles = roles
            member.version += 1
            ws.append_audit(actor_type="user", actor_id=str(actor.user_id), action="member.roles_changed", entity_type="member", entity_id=str(member_id), request_id=actor.request_id, payload={"from": ",".join(before), "to": ",".join(roles)})
            return _member_view(member, actor)


def _clean_roles(roles: list[str]) -> list[str]:
    allowed = ("reviewer", "catalogue_admin", "admin")
    if not isinstance(roles, list) or any(r not in allowed for r in roles):
        raise PartsIQError("VALIDATION_FAILED", detail="Roles must be any of reviewer, catalogue_admin, admin.")
    return [r for r in allowed if r in roles]


def _member_view(m: MemberRecord, actor: ActorContext) -> dict[str, Any]:
    return {
        "id": str(m.id), "email": m.email, "display_name": m.display_name, "roles": m.roles, "kind": m.kind,
        "created_at": m.created_at.isoformat(), "last_sign_in_at": m.last_sign_in_at.isoformat() if m.last_sign_in_at else None,
        "version": m.version, "is_you": m.id == actor.user_id,
    }


def _machine_view(m: MachineRecord) -> SavedMachineView:
    return SavedMachineView(id=m.id, label=m.label, model_text=m.model_text, serial_text=m.serial_text, created_at=m.created_at)


def _import_view(batch: ImportBatch) -> ImportView:
    return ImportView(
        id=batch.id, state=batch.state, row_count=len(batch.rows),
        issues=[ImportIssue(row_number=i["row_number"], field=str(i["field"])[:80], code=str(i["code"])[:60], message=str(i["message"])[:300]) for i in batch.issues[:500]],
        version_id=batch.version_id, content_sha256=batch.content_sha256,
    )


def _error_category(code: str | None) -> str | None:
    if code is None:
        return None
    return {
        "provider_unavailable": "provider", "allowance_exhausted": "allowance", "run_allowance": "allowance",
        "output_tokens": "limit", "agent_turns": "limit", "tool_calls": "limit", "wall_clock": "limit",
        "loop_detected": "policy", "no_progress": "policy", "stale_catalogue": "catalogue", "IMPORT_INVALID": "validation",
    }.get(code, "internal")


def _formula(value: str) -> bool:
    return bool(value) and value.startswith(_FORMULA_PREFIXES) or (value.startswith("-") and not _is_number(value))


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _stage_records(catalogue: Any, rows: list[dict[str, str]]) -> tuple[list[CatalogueRecord], dict[tuple[str, str], int], list[dict[str, Any]], dict[str, Any]]:
    """Merge typed CSV rows onto the active version's records (dry run; nothing is activated)."""
    records = {(r.entity_type, r.entity_key): r for r in catalogue.snapshot.records}
    order = [(r.entity_type, r.entity_key) for r in catalogue.snapshot.records]
    issues: list[dict[str, Any]] = []
    row_keys: dict[tuple[str, str], int] = {}
    added: dict[str, int] = {}
    changed: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    part_ids = {str(r.payload.get("part_number")): int(r.payload["id"]) for r in catalogue.snapshot.records if r.entity_type == "parts"}
    next_part = max(part_ids.values(), default=0) + 1
    alias_keys = [int(r.entity_key) for r in catalogue.snapshot.records if r.entity_type == "part_aliases" and r.entity_key.isdigit()]
    next_alias = max(alias_keys, default=0) + 1
    configs = {(str(r.payload.get("brand")), str(r.payload.get("model_code")), str(r.payload.get("config_code"))): int(r.payload["id"]) for r in catalogue.snapshot.records if r.entity_type == "model_configurations"}
    next_config = max(configs.values(), default=0) + 1

    def need(row: dict[str, str], number: int, *fields: str) -> bool:
        ok = True
        for name in fields:
            if not row.get(name, "").strip():
                issues.append({"row_number": number, "field": name, "code": "REQUIRED", "message": f"{name} is required for {row.get('entity_type')} rows."})
                ok = False
        return ok

    for index, row in enumerate(rows, start=2):  # header is row 1
        for name, value in row.items():
            if isinstance(value, str) and _formula(value.strip()):
                issues.append({"row_number": index, "field": name, "code": "FORMULA_NOT_ALLOWED", "message": "Cells that start with =, +, - or @ are rejected; formulas are never evaluated."})
        kind = row.get("entity_type", "").strip()
        if kind not in IMPORT_TYPES:
            issues.append({"row_number": index, "field": "entity_type", "code": "UNKNOWN_ENTITY", "message": f"entity_type must be one of {', '.join(IMPORT_TYPES)}."})
            continue
        payload: dict[str, Any]
        if kind == "parts":
            if not need(row, index, "part_number", "name_en", "name_ar", "category", "unit_of_measure"):
                continue
            number = row["part_number"].strip().upper()
            pid = part_ids.get(number)
            if pid is None:
                pid = next_part
                next_part += 1
                part_ids[number] = pid
            payload = {"id": pid, "part_number": number, "name_en": row["name_en"].strip(), "name_ar": row["name_ar"].strip(), "description_en": row.get("description_en", "").strip(), "category": row["category"].strip(), "unit_of_measure": row["unit_of_measure"].strip(), "is_active": row.get("is_active", "true").strip().lower() not in ("false", "0", "no")}
            key = str(pid)
        elif kind == "part_aliases":
            if not need(row, index, "part_number", "alias", "language"):
                continue
            if row["language"].strip() not in ("en", "ar"):
                issues.append({"row_number": index, "field": "language", "code": "INVALID", "message": "language must be en or ar."})
                continue
            payload = {"part_number": row["part_number"].strip().upper(), "alias": row["alias"].strip(), "language": row["language"].strip()}
            key = str(next_alias)
            next_alias += 1
        elif kind == "part_compatibility":
            if not need(row, index, "part_number", "brand", "model_code", "config_code", "quantity_per_unit", "source_reference"):
                continue
            if not _is_number(row["quantity_per_unit"]):
                issues.append({"row_number": index, "field": "quantity_per_unit", "code": "INVALID_NUMBER", "message": "quantity_per_unit must be a number."})
                continue
            payload = {"part_number": row["part_number"].strip().upper(), "brand": row["brand"].strip(), "model_code": row["model_code"].strip(), "config_code": row["config_code"].strip(), "quantity_per_unit": float(row["quantity_per_unit"]), "source_reference": row["source_reference"].strip()}
            key = json.dumps([payload["part_number"], payload["brand"], payload["model_code"], payload["config_code"]], ensure_ascii=False, separators=(",", ":"))
        elif kind == "part_supersessions":
            if not need(row, index, "old_part_number", "new_part_number", "effective_date"):
                continue
            payload = {"old_part_number": row["old_part_number"].strip().upper(), "new_part_number": row["new_part_number"].strip().upper(), "effective_date": row["effective_date"].strip(), "reason": row.get("reason", "").strip()}
            key = json.dumps([payload["old_part_number"], payload["new_part_number"]], separators=(",", ":"))
        else:  # model_configurations
            if not need(row, index, "brand", "model_code", "config_code", "serial_start", "serial_end"):
                continue
            if not (row["serial_start"].strip().isdigit() and row["serial_end"].strip().isdigit()):
                issues.append({"row_number": index, "field": "serial_start", "code": "INVALID_NUMBER", "message": "serial_start and serial_end must be whole numbers."})
                continue
            ckey = (row["brand"].strip(), row["model_code"].strip(), row["config_code"].strip())
            cid = configs.get(ckey)
            if cid is None:
                cid = next_config
                next_config += 1
                configs[ckey] = cid
            payload = {"id": cid, "brand": ckey[0], "model_code": ckey[1], "config_code": ckey[2], "description": row.get("description", "").strip(), "serial_start": int(row["serial_start"]), "serial_end": int(row["serial_end"])}
            key = str(cid)
        identity = (kind, key)
        if identity in records:
            changed[kind] = changed.get(kind, 0) + 1
            action = "changed"
        else:
            added[kind] = added.get(kind, 0) + 1
            order.append(identity)
            action = "added"
        records[identity] = CatalogueRecord(entity_type=kind, entity_key=key, payload=payload)
        row_keys[identity] = index
        if len(samples) < 8:
            samples.append({"row_number": index, "entity_type": kind, "action": action, "summary": ", ".join(f"{k}={v}" for k, v in list(payload.items())[:4])})
    merged = [records[k] for k in order]
    return merged, row_keys, issues, {"added": added, "changed": changed, "samples": samples}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


__all__ = ["OpsMixin", "capabilities_for"]
