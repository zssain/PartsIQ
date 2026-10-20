"""PostgreSQL persistence for the ACCOUNT workspace (ADR 0002, database mode).

Write-through design: the runtime keeps a cache of the account workspace, but every mutating
critical section ends with :meth:`PostgresWorkspaceStore.flush`, which writes every changed
aggregate in ONE transaction before the request reports success. If the flush fails, the cache
is reloaded from PostgreSQL so no unsaved change is ever served, and the caller gets a 503.

Change detection is by content hash per aggregate (enquiry, run) plus append-only watermarks
(exchanges per run, audit, notes, commands), so a flush never misses a mutation and never
re-inserts an immutable row. The database constraints remain the backstop for the invariants the
runtime also enforces: one publication per revision (``messages_one_publication_idx``), one
active run per revision, one open pending action per run, append-only audit/exchanges/commands,
single published catalogue version.

Exactly one API process may own the account workspace: an advisory lock is taken on open and a
second instance fails at startup instead of serving a divergent cache.

Public-demo sandboxes are intentionally NOT persisted (their visitors are not Supabase users, and
the data is disposable by design). Everything here is the account workspace only.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from partsiq.core.errors import PartsIQError

logger = logging.getLogger("partsiq.persistence")

WRITER_LOCK = 710071
REQUIRED_TABLES = (
    "enquiries", "enquiry_items", "messages", "review_decisions", "drafts", "verification_results",
    "workflow_runs", "agent_exchanges", "run_commands", "pending_actions", "audit_log", "internal_notes",
    "assignment_events", "saved_machines", "import_batches", "import_rows", "catalogue_versions",
    "catalogue_records", "profiles", "workspace_idempotency", "correction_records", "eval_runs",
    "eval_cases", "eval_results", "jobs", "parts", "model_configurations", "equipment_models",
    "warehouses", "stock_levels",
)


def _default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"not serialisable: {type(value).__name__}")


def dumps(value: Any) -> str:
    return json.dumps(value, default=_default, sort_keys=True, ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


async def _init(conn: Any) -> None:
    await conn.set_type_codec("jsonb", encoder=lambda v: v if isinstance(v, str) else dumps(v), decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=lambda v: v if isinstance(v, str) else dumps(v), decoder=json.loads, schema="pg_catalog")


# --------------------------------------------------------------------- typed (de)serialisation

def _contract_types() -> dict[str, type]:
    from partsiq.core import api_models, contracts

    out: dict[str, type] = {}
    for module in (contracts, api_models):
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and hasattr(obj, "model_validate"):
                out[name] = obj
    return out


def encode_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return {"__type": type(value).__name__, "data": value.model_dump(mode="json")}
    if isinstance(value, tuple):
        return {"__tuple": [encode_value(v) for v in value]}
    return {"__json": json.loads(dumps(value))}


def decode_value(value: Any, types: dict[str, type]) -> Any:
    if isinstance(value, dict) and "__type" in value:
        # JSON mode: the contracts are strict, and stored values are JSON (UUIDs/dates as strings).
        return types[value["__type"]].model_validate_json(json.dumps(value["data"]))
    if isinstance(value, dict) and "__tuple" in value:
        return tuple(decode_value(v, types) for v in value["__tuple"])
    if isinstance(value, dict) and "__json" in value:
        return value["__json"]
    return value


class PostgresWorkspaceStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: Any = None
        self._lock_conn: Any = None
        self._hashes: dict[tuple[str, UUID], str] = {}
        self._types = _contract_types()

    # ------------------------------------------------------------------ lifecycle

    async def open(self) -> None:
        import asyncpg

        try:
            self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=6, statement_cache_size=0, init=_init, command_timeout=30)
        except Exception as exc:  # noqa: BLE001 - startup must fail clearly, never fall back to memory
            raise RuntimeError(f"database mode: cannot connect to PostgreSQL ({type(exc).__name__})") from exc
        async with self.pool.acquire() as conn:
            present = {r["table_name"] for r in await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")}
        missing = [t for t in REQUIRED_TABLES if t not in present]
        if missing:
            raise RuntimeError(f"database mode: schema not applied (missing {', '.join(missing[:6])}); run tools/apply_migrations.py")
        self._lock_conn = await self.pool.acquire()
        if not await self._lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", WRITER_LOCK):
            raise RuntimeError("database mode: another API instance owns the account workspace (writer lock held)")

    async def close(self) -> None:
        if self._lock_conn is not None:
            try:
                await self._lock_conn.execute("SELECT pg_advisory_unlock($1)", WRITER_LOCK)
            finally:
                await self.pool.release(self._lock_conn)
        if self.pool is not None:
            await self.pool.close()

    # ------------------------------------------------------------------ profiles

    async def ensure_profile(self, user_id: UUID, display_name: str | None) -> None:
        """Create the profile row for an authenticated Supabase user (FK target of every owner column)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO profiles(id, display_name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                user_id, (display_name or "Account")[:120],
            )

    # ------------------------------------------------------------------ catalogue mirror

    async def bootstrap_catalogue(self, seed_snapshot: Any, seed_ledger: Any) -> tuple[Any, Any, list[Any]]:
        """Return (active snapshot, stock ledger, versions); seed them on an empty database."""
        from partsiq.catalogue.models import build_snapshot
        from partsiq.core.api_models import CatalogueRecord
        from partsiq.workspace.catalogue import StockLedger, VersionRecord

        async with self.pool.acquire() as conn:
            active = await conn.fetchrow("SELECT * FROM catalogue_versions WHERE state='published'")
            if active is None:
                async with conn.transaction():
                    await self._insert_version(conn, seed_snapshot, label="seed-42 synthetic catalogue", state="published", actor=None)
                    await self._mirror(conn, seed_snapshot)
                    await self._seed_stock(conn, seed_snapshot, seed_ledger)
                active = await conn.fetchrow("SELECT * FROM catalogue_versions WHERE state='published'")
            rows = await conn.fetch("SELECT entity_type, entity_key, payload FROM catalogue_records WHERE version_id=$1 ORDER BY entity_type, entity_key", active["id"])
            records = [CatalogueRecord(entity_type=r["entity_type"], entity_key=r["entity_key"], payload=r["payload"]) for r in rows]
            snapshot = build_snapshot(version_id=active["id"], source="fixture", records=records)
            ledger = StockLedger()
            for w in await conn.fetch("SELECT id, code, name, region FROM warehouses ORDER BY id"):
                ledger.warehouses[w["code"]] = (w["name"], w["region"])
            for s in await conn.fetch("SELECT s.part_id, w.code, s.quantity_on_hand - s.quantity_reserved AS net FROM stock_levels s JOIN warehouses w ON w.id=s.warehouse_id"):
                ledger.levels.setdefault(int(s["part_id"]), {})[s["code"]] = int(s["net"])
            versions = [
                VersionRecord(id=v["id"], label=v["label"], state=v["state"], content_sha256=v["content_sha256"], source="fixture", created_at=v["created_at"], published_at=v["published_at"], published_by=v["created_by"])
                for v in await conn.fetch("SELECT * FROM catalogue_versions ORDER BY created_at")
            ]
        return snapshot, ledger, versions

    async def publish_version(self, snapshot: Any, *, label: str, actor: UUID) -> None:
        """Compare-and-set publication of a validated version (single published row)."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(710070)")
                await conn.execute("UPDATE catalogue_versions SET state='retired' WHERE state='published'")
                await self._insert_version(conn, snapshot, label=label, state="published", actor=actor)
                await self._mirror(conn, snapshot)

    async def _insert_version(self, conn: Any, snapshot: Any, *, label: str, state: str, actor: UUID | None) -> None:
        existing = await conn.fetchval("SELECT id FROM catalogue_versions WHERE id=$1", snapshot.version_id)
        if existing is None:
            await conn.execute(
                "INSERT INTO catalogue_versions(id,label,state,content_sha256,created_by,published_at) VALUES ($1,$2,'staging',$3,$4,NULL)",
                snapshot.version_id, f"{label} ({str(snapshot.version_id)[:8]})"[:200], snapshot.content_sha256, actor,
            )
            await conn.executemany(
                "INSERT INTO catalogue_records(version_id,entity_type,entity_key,payload) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                [(snapshot.version_id, r.entity_type, r.entity_key, dict(r.payload)) for r in snapshot.records],
            )
        if state == "published":
            await conn.execute("UPDATE catalogue_versions SET state='published', published_at=coalesce(published_at, now()) WHERE id=$1", snapshot.version_id)

    async def _mirror(self, conn: Any, snapshot: Any) -> None:
        """Upsert the legacy catalogue tables from the snapshot with ITS ids (never deletes rows)."""
        by_type: dict[str, list[Any]] = {}
        for r in snapshot.records:
            by_type.setdefault(r.entity_type, []).append(r)
        fam_ids: dict[str, int] = {}
        for i, r in enumerate(sorted(by_type.get("equipment_families", []), key=lambda r: r.entity_key), start=1):
            p = r.payload
            fid = await conn.fetchval(
                "INSERT INTO equipment_families(code,name_en,name_ar) VALUES ($1,$2,$3) ON CONFLICT (code) DO UPDATE SET name_en=EXCLUDED.name_en, name_ar=EXCLUDED.name_ar RETURNING id",
                p["code"], p["name_en"], p["name_ar"],
            )
            fam_ids[p["code"]] = fid
        model_ids: dict[tuple[str, str], int] = {}
        for r in by_type.get("equipment_models", []):
            p = r.payload
            mid = await conn.fetchval(
                "INSERT INTO equipment_models(family_id,brand,model_code,display_name,rated_output) VALUES ($1,$2,$3,$4,$5) "
                "ON CONFLICT (brand, model_code) DO UPDATE SET display_name=EXCLUDED.display_name, rated_output=EXCLUDED.rated_output RETURNING id",
                fam_ids[p["family_code"]], p["brand"], p["model_code"], p["display_name"], p.get("rated_output"),
            )
            model_ids[(p["brand"], p["model_code"])] = mid
        for r in by_type.get("model_configurations", []):
            p = r.payload
            await conn.execute(
                "INSERT INTO model_configurations(id,model_id,config_code,description,serial_start,serial_end) VALUES ($1,$2,$3,$4,$5,$6) "
                "ON CONFLICT (id) DO UPDATE SET description=EXCLUDED.description, serial_start=EXCLUDED.serial_start, serial_end=EXCLUDED.serial_end",
                int(p["id"]), model_ids[(p["brand"], p["model_code"])], p["config_code"], p.get("description") or "", int(p["serial_start"]), int(p["serial_end"]),
            )
        part_ids: dict[str, int] = {}
        for r in by_type.get("parts", []):
            p = r.payload
            await conn.execute(
                "INSERT INTO parts(id,part_number,name_en,name_ar,description_en,category,unit_of_measure,is_active) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) "
                "ON CONFLICT (id) DO UPDATE SET name_en=EXCLUDED.name_en, name_ar=EXCLUDED.name_ar, description_en=EXCLUDED.description_en, category=EXCLUDED.category, unit_of_measure=EXCLUDED.unit_of_measure, is_active=EXCLUDED.is_active",
                int(p["id"]), p["part_number"], p["name_en"], p["name_ar"], p.get("description_en") or "", p["category"], p.get("unit_of_measure") or "EA", bool(p.get("is_active", True)),
            )
            part_ids[p["part_number"]] = int(p["id"])
        for r in by_type.get("warehouses", []):
            p = r.payload
            await conn.execute("INSERT INTO warehouses(code,name,region) VALUES ($1,$2,$3) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, region=EXCLUDED.region", p["code"], p["name"], p["region"])
        # Serial sequences after explicit ids (so later SERIAL inserts never collide).
        for table in ("parts", "model_configurations"):
            await conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), greatest((SELECT max(id) FROM {table}), 1))")

    async def _seed_stock(self, conn: Any, snapshot: Any, ledger: Any) -> None:
        wh = {r["code"]: r["id"] for r in await conn.fetch("SELECT id, code FROM warehouses")}
        rows = [(pid, wh[code], max(0, qty)) for pid, levels in ledger.levels.items() for code, qty in levels.items() if code in wh]
        await conn.executemany(
            "INSERT INTO stock_levels(part_id,warehouse_id,quantity_on_hand,quantity_reserved) VALUES ($1,$2,$3,0) ON CONFLICT DO NOTHING", rows,
        )

    async def model_id(self, model_text: str) -> int | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT id FROM equipment_models WHERE upper(model_code)=upper($1) LIMIT 1", model_text.strip())

    # ------------------------------------------------------------------ load

    async def load(self, ws: Any) -> None:
        """Rebuild the account workspace cache from PostgreSQL (startup and after a failed flush)."""
        from partsiq.core.contracts import MessageView, ReplySlots, VerificationEvidence, VerificationResult, VerifiedFacts
        from partsiq.workspace import records as R
        from partsiq.workspace.tenant import CorrectionRecord, EvalRunRecord, ImportBatch

        ws.enquiries.clear()
        ws.runs.clear()
        ws.exchanges.clear()
        ws.commands.clear()
        ws.pending.clear()
        ws.audit.clear()
        ws.notes.clear()
        ws.machines.clear()
        ws.imports.clear()
        ws.idempotency.clear()
        ws.corrections.clear()
        ws.evaluations.clear()
        ws.jobs.clear()
        self._hashes.clear()
        async with self.pool.acquire() as conn:
            for e in await conn.fetch("SELECT * FROM enquiries WHERE session_id IS NULL AND owner_id IS NOT NULL ORDER BY created_at"):
                st = e["workspace_state"] or {}
                record = R.EnquiryRecord(
                    id=e["id"], owner_id=e["owner_id"], session_id=None, session_generation=None,
                    locale=e["locale"] or "en", destination_warehouse_id=int(e["destination_warehouse_id"] or 1),
                    created_at=e["created_at"], updated_at=e["updated_at"], revision=e["revision"], status=e["status"],
                    language=e["detected_language"] or "en", urgency=st.get("urgency", "normal"),
                    catalogue_version_id=e["catalogue_version_id"], priority=e["priority"], due_at=e["due_at"],
                    assigned_to=e["assigned_to"], mode=e["run_mode"] or "guided", current_run_id=e["current_run_id"],
                    idempotency_key=e["idempotency_key"],
                )
                record.run_ids = [UUID(x) for x in st.get("run_ids", [])]
                record.pending_question = st.get("pending_question")
                record.pending_code = st.get("pending_code")
                record.pending_item_id = UUID(st["pending_item_id"]) if st.get("pending_item_id") else None
                record.step = st.get("step", "intake")
                record.wait_reason = st.get("wait_reason")
                record.instructions = list(st.get("instructions", []))
                record.draft_id = UUID(st["draft_id"]) if st.get("draft_id") else None
                record.verification_id = UUID(st["verification_id"]) if st.get("verification_id") else None
                record.draft_rendered = st.get("draft_rendered")
                record.draft_source = st.get("draft_source")
                record.draft_slots = ReplySlots.model_validate(st["draft_slots"]) if st.get("draft_slots") else None
                record.facts = VerifiedFacts.model_validate_json(json.dumps(st["facts"])) if st.get("facts") else None
                record.evidence = VerificationEvidence.model_validate_json(json.dumps(st["evidence"])) if st.get("evidence") else None
                record.verification = VerificationResult.model_validate_json(json.dumps(st["verification"])) if st.get("verification") else None
                record.review_ready_at = _dt(st.get("review_ready_at"))
                record.events = [R.ProgressEvent(step=v["step"], label=v["label"], at=_dt(v["at"]), status=v["status"], detail=v.get("detail"), revision=v["revision"], run_id=UUID(v["run_id"]) if v.get("run_id") else None) for v in st.get("events", [])]
                record.attachments = [R.AttachmentRecord(id=UUID(a["id"]), media_type=a["media_type"], size_bytes=a["size_bytes"], status=a["status"], width=a.get("width"), height=a.get("height"), sha256=a.get("sha256"), error_code=a.get("error_code"), fixture_key=a.get("fixture_key"), created_at=_dt(a["created_at"]), storage_key=a.get("storage_key")) for a in st.get("attachments", [])]
                if st.get("nameplate"):
                    n = st["nameplate"]
                    record.nameplate = R.NameplateRecord(attachment_id=UUID(n["attachment_id"]), extraction_id=UUID(n["extraction_id"]), model_text=n.get("model_text"), serial_text=n.get("serial_text"), issues=n.get("issues", []), source=n["source"], confirmed=n.get("confirmed", False), confirmed_model=n.get("confirmed_model"), confirmed_serial=n.get("confirmed_serial"))
                record.messages = [
                    MessageView(id=m["id"], enquiry_id=m["enquiry_id"], revision=m["revision"], kind=m["kind"], body=m["body"], created_at=m["created_at"])
                    for m in await conn.fetch("SELECT * FROM messages WHERE enquiry_id=$1 ORDER BY created_at, id", record.id)
                ]
                for it in await conn.fetch("SELECT * FROM enquiry_items WHERE enquiry_id=$1 ORDER BY ordinal", record.id):
                    d = it["detail"] or {}
                    item = R.ItemRecord(
                        id=it["id"], ordinal=it["ordinal"], description=it["requested_text"], quantity=Decimal(it["quantity"]),
                        quantity_assumed=d.get("quantity_assumed", False), model_text=it["model_text"], serial_text=it["serial_text"],
                        config_code_text=d.get("config_code_text"), part_numbers=d.get("part_numbers", []), status=it["status"],
                        configuration_id=it["configuration_id"], selected_part_id=it["selected_part_id"],
                    )
                    for key in ("configuration_label", "identification_note", "clarification_code", "clarification_text", "margin", "selection_source", "quoted_number_note", "plan_strategy", "shortage", "plan_message"):
                        if key in d:
                            setattr(item, key, d[key])
                    item.candidates = [R.CandidateRecord(**c) for c in d.get("candidates", [])]
                    item.plan_lines = [R.PlanLine(warehouse_code=p["warehouse_code"], warehouse_id=p["warehouse_id"], quantity=p["quantity"], transfer_days=p["transfer_days"], observed_at=_dt(p["observed_at"])) for p in d.get("plan_lines", [])]
                    record.items.append(item)
                for dec in await conn.fetch("SELECT * FROM review_decisions WHERE enquiry_id=$1 ORDER BY decided_at", record.id):
                    msg = next((m for m in record.messages if m.kind == "recommendation" and m.revision == dec["revision"]), None)
                    record.decisions.append(R.Decision(id=dec["id"], kind="approved" if dec["decision"] in ("approved", "edited") else "rejected", revision=dec["revision"], actor_id=dec["reviewer_id"], at=dec["decided_at"], reason=dec["comment"], message_id=msg.id if msg else None))
                ws.enquiries[record.id] = record
                ws.notes[record.id] = [R.NoteRecord(id=n["id"], enquiry_id=n["enquiry_id"], author_id=n["author_id"], body=n["body"], created_at=n["created_at"]) for n in await conn.fetch("SELECT * FROM internal_notes WHERE enquiry_id=$1 ORDER BY created_at, id", record.id)]
            for r in await conn.fetch("SELECT * FROM workflow_runs WHERE session_id IS NULL ORDER BY created_at"):
                if r["enquiry_id"] not in ws.enquiries:
                    continue
                run = R.RunRecord(
                    id=r["id"], enquiry_id=r["enquiry_id"], revision=r["revision"], mode=r["mode"], status=r["status"], control=r["control"],
                    execution_source=r["execution_source"], created_by=r["created_by"], catalogue_version_id=r["catalogue_version_id"],
                    session_id=None, session_generation=None, limits=r["limits"], created_at=r["created_at"], updated_at=r["updated_at"],
                    state_version=r["state_version"], fence=r["fence"], completed_at=r["completed_at"], blocked_reason=r["blocked_reason"],
                    terminal_reason=r["terminal_reason"], current_step=r["current_step"], next_seq=r["next_seq"], thread_id=r["thread_id"],
                    agenda=[UUID(x) for x in r["agenda"]], board=r["board"], seen_signatures=set(r["seen_signatures"]),
                )
                run.usage = R.RunUsage(agent_turns=r["agent_turns"], tool_calls=r["tool_calls"], output_tokens=r["output_tokens"], input_tokens=r["input_tokens"], estimated_usd=Decimal(r["estimated_usd"]), retries=r["retries"], active_seconds=float(r["active_seconds"]))
                if r["carried_from"]:
                    run.board.setdefault("carried_from", str(r["carried_from"]))
                ws.runs[run.id] = run
                ws.exchanges[run.id] = [
                    R.ExchangeRecord(id=x["id"], run_id=x["run_id"], seq=x["seq"], sender=x["sender"], recipient=x["recipient"], kind=x["kind"], summary=x["summary"], payload=x["payload"], evidence_refs=list(x["evidence_refs"]), source=x["source"], correlation_id=x["correlation_id"], reply_to=x["reply_to"], status=x["status"], created_at=x["created_at"])
                    for x in await conn.fetch("SELECT * FROM agent_exchanges WHERE run_id=$1 ORDER BY seq", run.id)
                ]
                for c in await conn.fetch("SELECT * FROM run_commands WHERE run_id=$1 ORDER BY created_at", run.id):
                    ws.commands[(run.id, c["idempotency_key"])] = R.CommandRecord(id=c["id"], run_id=c["run_id"], actor_id=c["actor_id"], type=c["type"], expected_revision=c["expected_revision"], expected_state_version=c["expected_state_version"], idempotency_key=c["idempotency_key"], payload_hash=c["payload_sha256"], payload=c["payload"], accepted=c["accepted"], result=c["result"], created_at=c["created_at"])
                for p in await conn.fetch("SELECT * FROM pending_actions WHERE run_id=$1 ORDER BY created_at", run.id):
                    ws.pending[p["id"]] = R.PendingActionRecord(id=p["id"], run_id=p["run_id"], enquiry_id=p["enquiry_id"], revision=p["revision"], kind=p["kind"], requested_by=p["requested_by"], prompt=p["prompt"], options=p["options"], allowed_resolutions=list(p["allowed_resolutions"]), status=p["status"], created_at=p["created_at"], item_id=p["item_id"], code=p["code"], resolved_by=p["resolved_by"], resolved_at=p["resolved_at"], resolution=p["resolution"], exchange_id=p["exchange_id"])
            for a in await conn.fetch("SELECT * FROM audit_log ORDER BY id"):
                ws.audit.append(R.AuditRecord(seq=a["id"], actor_type=a["actor_type"], actor_id=a["actor_id"], action=a["action"], entity_type=a["entity_type"], entity_id=a["entity_id"], request_id=UUID(a["request_id"]) if a["request_id"] else UUID(int=0), enquiry_id=a["enquiry_id"], revision=a["revision"], payload=a["payload"], created_at=a["occurred_at"]))
            ws.audit_seq = ws.audit[-1].seq if ws.audit else 0
            for m in await conn.fetch("SELECT * FROM saved_machines WHERE session_id IS NULL ORDER BY created_at"):
                ws.machines[m["id"]] = R.MachineRecord(id=m["id"], owner_id=m["owner_id"], label=m["label"], model_text=m["model_text"] or "", serial_text=m["serial_text"], created_at=m["created_at"], archived=m["archived_at"] is not None)
            for b in await conn.fetch("SELECT * FROM import_batches ORDER BY created_at"):
                d = b["detail"] or {}
                rows = [json.loads(dumps(x["payload"])) for x in await conn.fetch("SELECT payload FROM import_rows WHERE batch_id=$1 ORDER BY row_number", b["id"])]
                state = {"valid": "validated"}.get(b["status"], b["status"])
                ws.imports[b["id"]] = ImportBatch(id=b["id"], filename=b["filename"] or "import.csv", format="csv", size_bytes=max(1, len(dumps(rows))), state=state, created_by=b["created_by"], created_at=b["created_at"], updated_at=b["created_at"], rows=rows, issues=d.get("issues", []), preview=d.get("preview", {}), content_sha256=b["sha256"], version_id=b["version_id"], base_version_id=b["base_version_id"])
            for c in await conn.fetch("SELECT * FROM correction_records ORDER BY created_at"):
                ws.corrections[c["id"]] = CorrectionRecord(id=c["id"], enquiry_id=c["enquiry_id"], revision=c["revision"], author_id=c["corrected_by"], field=c["field"] or "", before=(c["before_value"] or {}).get("value"), after=(c["after_value"] or {}).get("value"), reviewed=c["reviewed"], created_at=c["created_at"], curated_case_id=c["eval_case_id"])
            from partsiq.core.contracts import EvalOutput, EvalResult
            for e in await conn.fetch("SELECT * FROM eval_runs ORDER BY started_at"):
                results = [EvalResult(case_id=x["case_id"], passed=x["passed"], actual=EvalOutput.model_validate(x["actual"])) for x in await conn.fetch("SELECT * FROM eval_results WHERE run_id=$1 ORDER BY case_id", e["id"])]
                ev = EvalRunRecord(id=e["id"], suite="deterministic", state="succeeded", created_by=UUID(int=0), created_at=e["started_at"], dataset_sha256=e["dataset_sha256"], results=results)
                ev.total = len(results)
                ev.passed = sum(1 for r in results if r.passed)
                ev.failed = ev.total - ev.passed
                ws.evaluations[ev.id] = ev
            for i in await conn.fetch("SELECT * FROM workspace_idempotency"):
                ws.idempotency[(i["scope"], i["key"])] = (i["request_sha256"], decode_value(i["response"], self._types))
        self._snapshot_watermarks(ws)

    def _snapshot_watermarks(self, ws: Any) -> None:
        ws.persisted = self._marks(ws)
        for rid, e in ws.enquiries.items():
            self._hashes[("enquiry", rid)] = digest(self._enquiry_state(e))
        for rid, r in ws.runs.items():
            self._hashes[("run", rid)] = digest(self._run_row(r))

    def _marks(self, ws: Any) -> dict[str, Any]:
        """What is persisted once the current flush commits — captured BEFORE any await so a row
        appended concurrently (e.g. a run emitting an exchange) is never marked written by mistake."""
        return {
            "audit": ws.audit_seq,
            "idempotency": set(ws.idempotency.keys()),
            "notes": {nid.id for notes in ws.notes.values() for nid in notes},
            "commands": set(ws.commands.keys()),
            "machines": {mid: digest(m) for mid, m in ws.machines.items()},
            "imports": {bid: digest((b.state, b.issues, b.preview, b.version_id, b.content_sha256)) for bid, b in ws.imports.items()},
            "corrections": {cid: digest(c) for cid, c in ws.corrections.items()},
            "evaluations": set(ws.evaluations.keys()),
            "messages": {m.id for e in ws.enquiries.values() for m in e.messages},
            "items": {i.id: digest((asdict(i), e.revision)) for e in ws.enquiries.values() for i in e.items},
            "exchanges": {x.id: x.status for xs in ws.exchanges.values() for x in xs},
            "pending": {pa.id: digest((pa.status, pa.resolution, pa.resolved_by)) for pa in ws.pending.values()},
            "decisions": {d.id for e in ws.enquiries.values() for d in e.decisions},
            "profiles": (getattr(ws, "persisted", None) or {}).get("profiles", set()) | {e.owner_id for e in ws.enquiries.values()} | {r.created_by for r in ws.runs.values()},
        }

    # ------------------------------------------------------------------ flush

    @staticmethod
    def _enquiry_state(e: Any) -> dict[str, Any]:
        return {
            "urgency": e.urgency, "step": e.step, "wait_reason": e.wait_reason,
            "pending_question": e.pending_question, "pending_code": e.pending_code,
            "pending_item_id": str(e.pending_item_id) if e.pending_item_id else None,
            "instructions": e.instructions, "run_ids": [str(x) for x in e.run_ids],
            "draft_id": str(e.draft_id) if e.draft_id else None, "verification_id": str(e.verification_id) if e.verification_id else None,
            "draft_rendered": e.draft_rendered, "draft_source": e.draft_source,
            "draft_slots": e.draft_slots.model_dump(mode="json") if e.draft_slots else None,
            "facts": json.loads(e.facts.model_dump_json()) if e.facts else None,
            "evidence": json.loads(e.evidence.model_dump_json()) if e.evidence else None,
            "verification": json.loads(e.verification.model_dump_json()) if e.verification else None,
            "review_ready_at": e.review_ready_at.isoformat() if e.review_ready_at else None,
            "events": [{"step": v.step, "label": v.label, "at": v.at.isoformat(), "status": v.status, "detail": v.detail, "revision": v.revision, "run_id": str(v.run_id) if v.run_id else None} for v in e.events[-200:]],
            "attachments": [json.loads(dumps(asdict(a))) for a in e.attachments],
            "nameplate": json.loads(dumps(asdict(e.nameplate))) if e.nameplate else None,
            "_core": json.loads(dumps({"rev": e.revision, "status": e.status, "assigned": e.assigned_to, "priority": e.priority, "mode": e.mode, "run": e.current_run_id, "msgs": [m.id for m in e.messages], "items": [asdict(i) for i in e.items], "decisions": [asdict(d) for d in e.decisions], "cat": e.catalogue_version_id, "upd": e.updated_at})),
        }

    @staticmethod
    def _run_row(r: Any) -> dict[str, Any]:
        return json.loads(dumps({f.name: getattr(r, f.name) for f in fields(r) if f.name not in ("in_flight", "active_since", "usage", "pending_spec")} | {"usage": asdict(r.usage)}))

    async def flush(self, ws: Any) -> None:
        """Write every changed row in ONE transaction using batched statements (few round trips).

        Row-level change tracking (messages, items, exchanges, pending actions, decisions, logs)
        keeps a flush to a handful of pipelined ``executemany`` calls even when the database is
        far away, so a workflow step costs O(1) round trips rather than O(rows).
        """
        p = getattr(ws, "persisted", None) or {}
        msg_ids: set = p.get("messages", set())
        item_h: dict = p.get("items", {})
        ex_h: dict = p.get("exchanges", {})
        pend_h: dict = p.get("pending", {})
        dec_ids: set = p.get("decisions", set())
        profiles: set = p.get("profiles", set())
        enq_rows, msg_rows, item_rows, cur_rows, dirty_enq = [], [], [], [], []
        for e in ws.enquiries.values():
            h = digest(self._enquiry_state(e))
            if self._hashes.get(("enquiry", e.id)) != h:
                dirty_enq.append((e, h))
                enq_rows.append(self._enquiry_params(e))
                cur_rows.append((e.id, e.current_run_id if e.current_run_id in ws.runs else None))
            for m in e.messages:
                if m.kind != "recommendation" and m.id not in msg_ids:
                    msg_rows.append((m.id, e.id, m.revision, m.kind, m.body[:12000], e.owner_id if m.kind == "customer" else None, m.created_at))
            for i in e.items:
                ih = digest((asdict(i), e.revision))
                if item_h.get(i.id) != ih:
                    item_rows.append(self._item_params(e, i))
        run_rows, ex_rows, pend_rows, dirty_runs = [], [], [], []
        for r in sorted(ws.runs.values(), key=lambda r: r.created_at):
            h = digest(self._run_row(r))
            if self._hashes.get(("run", r.id)) != h:
                dirty_runs.append((r, h))
                run_rows.append(self._run_params(ws, r))
            for x in ws.exchanges.get(r.id, []):
                if ex_h.get(x.id) != x.status:
                    ex_rows.append((x.id, r.id, x.seq, x.sender, x.recipient, x.kind, x.summary[:600], json.loads(dumps(x.payload)), list(x.evidence_refs)[:12], x.source, x.correlation_id, x.reply_to, x.status, x.created_at))
        for pa in ws.pending.values():
            ph = digest((pa.status, pa.resolution, pa.resolved_by))
            if pend_h.get(pa.id) != ph and pa.run_id in ws.runs:
                pend_rows.append((pa.id, pa.run_id, pa.enquiry_id, pa.revision, pa.kind, pa.requested_by, pa.code, pa.item_id, pa.prompt[:1000], json.loads(dumps(pa.options)), pa.allowed_resolutions, pa.status, pa.exchange_id, pa.resolved_by if pa.status == "resolved" else None, pa.resolved_at if pa.status == "resolved" else None, (pa.resolution or None) and pa.resolution[:300], pa.created_at))
        new_decisions = [(e, d) for e in ws.enquiries.values() for d in e.decisions if d.id not in dec_ids]
        people = {e.owner_id for e, _ in dirty_enq} | {r.created_by for r, _ in dirty_runs} | {e.assigned_to for e, _ in dirty_enq if e.assigned_to} | {d.actor_id for _, d in new_decisions}
        people = {x for x in people if x and x not in profiles}
        logs_dirty = self._logs_dirty(ws, p)
        marks = self._marks(ws)  # synchronous: reflects exactly the rows collected above
        logs = self._log_rows(ws, p) if logs_dirty else None
        if not (enq_rows or msg_rows or item_rows or run_rows or ex_rows or pend_rows or new_decisions or logs_dirty):
            return
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if people:
                    await conn.executemany("INSERT INTO profiles(id, display_name) VALUES ($1,'Account') ON CONFLICT (id) DO NOTHING", [(x,) for x in people])
                if enq_rows:
                    await conn.executemany(_ENQUIRY_SQL, enq_rows)
                if item_rows:
                    await conn.executemany(_ITEM_SQL, item_rows)
                if msg_rows:
                    await conn.executemany("INSERT INTO messages(id,enquiry_id,revision,kind,body,author_id,idempotency_key,created_at) VALUES ($1,$2,$3,$4,$5,$6,$1,$7) ON CONFLICT (id) DO NOTHING", msg_rows)
                if run_rows:
                    await conn.executemany(_RUN_SQL, run_rows)
                if ex_rows:
                    await conn.executemany(_EXCHANGE_SQL, ex_rows)
                if pend_rows:
                    await conn.executemany(_PENDING_SQL, pend_rows)
                if cur_rows:
                    await conn.executemany("UPDATE enquiries SET current_run_id=$2 WHERE id=$1", cur_rows)
                for e, d in new_decisions:
                    await self._write_decision(conn, e, d)
                if logs is not None:
                    await self._write_logs(conn, ws, p, logs)
        for e, h in dirty_enq:
            self._hashes[("enquiry", e.id)] = h
        for r, h in dirty_runs:
            self._hashes[("run", r.id)] = h
        ws.persisted = marks

    @staticmethod
    def _logs_dirty(ws: Any, p: dict[str, Any]) -> bool:
        return (
            any(a.seq > p.get("audit", 0) for a in ws.audit[-50:])
            or set(ws.commands.keys()) != p.get("commands", set())
            or set(ws.idempotency.keys()) != p.get("idempotency", set())
            or {n.id for notes in ws.notes.values() for n in notes} != p.get("notes", set())
            or {mid: digest(m) for mid, m in ws.machines.items()} != p.get("machines", {})
            or {bid: digest((b.state, b.issues, b.preview, b.version_id, b.content_sha256)) for bid, b in ws.imports.items()} != p.get("imports", {})
            or {cid: digest(c) for cid, c in ws.corrections.items()} != p.get("corrections", {})
            or set(ws.evaluations.keys()) != p.get("evaluations", set())
        )

    def _enquiry_params(self, e: Any) -> tuple:
        first = e.messages[0].body if e.messages else ""
        config = next((i.configuration_id for i in e.items if i.configuration_id), None)
        return (
            e.id, first or "(empty)", e.language if e.language in ("en", "ar", "mixed") else None, config, e.status, e.created_at, e.updated_at,
            e.owner_id, e.revision, e.catalogue_version_id, e.destination_warehouse_id, e.assigned_to, e.priority, e.due_at,
            e.idempotency_key, e.locale, e.mode, {k: v for k, v in self._enquiry_state(e).items() if k != "_core"},
        )

    @staticmethod
    def _item_params(e: Any, i: Any) -> tuple:
        detail = {k: getattr(i, k) for k in ("quantity_assumed", "config_code_text", "part_numbers", "configuration_label", "identification_note", "clarification_code", "clarification_text", "margin", "selection_source", "quoted_number_note", "plan_strategy", "shortage", "plan_message")}
        detail["candidates"] = [asdict(c) for c in i.candidates]
        detail["plan_lines"] = [asdict(x) for x in i.plan_lines]
        return (i.id, e.id, i.ordinal, i.description or "item", i.quantity or Decimal(1), i.model_text, i.serial_text, i.configuration_id, i.selected_part_id, i.status, e.revision, json.loads(dumps(detail)))

    @staticmethod
    def _run_params(ws: Any, r: Any) -> tuple:
        carried = r.board.get("carried_from")
        board = {k: v for k, v in r.board.items() if k != "pending_spec"}
        return (
            r.id, r.enquiry_id, r.revision, r.mode, r.status, r.control, r.execution_source, r.created_by, r.catalogue_version_id,
            json.loads(dumps(r.limits)), r.usage.agent_turns, r.usage.tool_calls, r.usage.input_tokens, r.usage.output_tokens,
            r.usage.estimated_usd, r.usage.retries, round(r.usage.active_seconds, 2), r.state_version, r.fence, r.thread_id,
            UUID(carried) if carried and UUID(carried) in ws.runs else None, r.blocked_reason, (r.terminal_reason or None) and r.terminal_reason[:600],
            r.created_at, r.updated_at, r.completed_at, [str(x) for x in r.agenda], json.loads(dumps(board)), sorted(r.seen_signatures), r.next_seq, r.current_step,
        )

    async def _write_decision(self, conn: Any, e: Any, d: Any) -> None:
        verification_id = None
        if d.kind == "approved" and e.facts is not None and e.draft_slots is not None and d.revision == e.revision:
            draft_id = await conn.fetchval(
                """INSERT INTO drafts(id,enquiry_id,revision,locale,prose,verified_facts,rendered_text) VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (enquiry_id,revision) DO UPDATE SET prose=EXCLUDED.prose, verified_facts=EXCLUDED.verified_facts, rendered_text=EXCLUDED.rendered_text RETURNING id""",
                e.draft_id, e.id, e.revision, e.locale, e.draft_slots.model_dump(mode="json"), json.loads(e.facts.model_dump_json()), e.draft_rendered or "",
            )
            if e.verification is not None:
                verification_id = await conn.fetchval(
                    """INSERT INTO verification_results(id,enquiry_id,revision,draft_id,passed,failures,facts_sha256) VALUES ($1,$2,$3,$4,$5,$6,$7)
                       ON CONFLICT (enquiry_id,revision) DO UPDATE SET draft_id=EXCLUDED.draft_id, passed=EXCLUDED.passed, failures=EXCLUDED.failures, facts_sha256=EXCLUDED.facts_sha256 RETURNING id""",
                    e.verification_id, e.id, e.revision, draft_id, e.verification.passed,
                    [json.loads(f.model_dump_json()) for f in e.verification.failures], e.verification.facts_sha256,
                )
        message = next((m for m in e.messages if m.id == d.message_id), None)
        await conn.execute(
            "INSERT INTO review_decisions(id,enquiry_id,reviewer,decision,final_reply,comment,decided_at,revision,reviewer_id,verification_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
            d.id, e.id, str(d.actor_id), d.kind, message.body if message else None, d.reason, d.at, d.revision, d.actor_id, verification_id,
        )
        if message is not None:
            await conn.execute(
                "INSERT INTO messages(id,enquiry_id,revision,kind,body,author_id,decision_id,idempotency_key,created_at) VALUES ($1,$2,$3,'recommendation',$4,$5,$6,$1,$7)",
                message.id, e.id, message.revision, message.body[:12000], d.actor_id, d.id, message.created_at,
            )

    def _log_rows(self, ws: Any, persisted: dict[str, Any]) -> dict[str, Any]:
        """Copy the append-only rows to write NOW (before any await)."""
        audit_mark = persisted.get("audit", 0)
        known_cmds = persisted.get("commands", set())
        known_notes = persisted.get("notes", set())
        known_idem = persisted.get("idempotency", set())
        return {
            "audit": [a for a in ws.audit if a.seq > audit_mark],
            "commands": [c for key, c in ws.commands.items() if key not in known_cmds and c.run_id in ws.runs],
            "notes": [n for notes in ws.notes.values() for n in notes if n.id not in known_notes],
            "idempotency": [(scope, key, h, r) for (scope, key), (h, r) in ws.idempotency.items() if (scope, key) not in known_idem],
        }

    async def _write_logs(self, conn: Any, ws: Any, persisted: dict[str, Any], rows: dict[str, Any]) -> None:
        fresh = rows["audit"]
        if fresh:
            await conn.executemany(
                "INSERT INTO audit_log(occurred_at,actor_type,actor_id,action,entity_type,entity_id,request_id,payload,enquiry_id,revision) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                [(a.created_at, a.actor_type, a.actor_id, a.action, a.entity_type, a.entity_id, str(a.request_id), json.loads(dumps(a.payload)), a.enquiry_id if a.enquiry_id in ws.enquiries else None, a.revision) for a in fresh],
            )
            assignments = [(a.enquiry_id, UUID(a.payload["to"]) if a.payload.get("to") else None, UUID(a.actor_id), a.created_at) for a in fresh if a.action == "assignment.changed" and a.enquiry_id in ws.enquiries]
            if assignments:
                await conn.executemany("INSERT INTO assignment_events(enquiry_id,assigned_to,assigned_by,created_at) VALUES ($1,$2,$3,$4)", assignments)
        if rows["commands"]:
            await conn.executemany(
                "INSERT INTO run_commands(id,run_id,actor_id,type,expected_revision,expected_state_version,idempotency_key,payload_sha256,payload,accepted,result,created_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT DO NOTHING",
                [(c.id, c.run_id, c.actor_id, c.type, c.expected_revision, c.expected_state_version, c.idempotency_key, c.payload_hash, json.loads(dumps(c.payload)), c.accepted, c.result[:300], c.created_at) for c in rows["commands"]],
            )
        if rows["notes"]:
            await conn.executemany("INSERT INTO internal_notes(id,enquiry_id,author_id,body,created_at) VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING", [(n.id, n.enquiry_id, n.author_id, n.body, n.created_at) for n in rows["notes"]])
        if rows["idempotency"]:
            await conn.executemany(
                "INSERT INTO workspace_idempotency(scope,key,request_sha256,response) VALUES ($1,$2,$3,$4) ON CONFLICT (scope,key) DO UPDATE SET response=EXCLUDED.response",
                [(scope[:40], key, str(h)[:200], encode_value(r)) for scope, key, h, r in rows["idempotency"]],
            )
        known_machines = persisted.get("machines", {})
        for mid, m in ws.machines.items():
            if known_machines.get(mid) == digest(m):
                continue
            model_id = await conn.fetchval("SELECT id FROM equipment_models WHERE upper(model_code)=upper($1) LIMIT 1", m.model_text.strip())
            if model_id is None:
                raise PartsIQError("VALIDATION_FAILED", detail="Saved machines must use a model from the active catalogue.")
            await conn.execute(
                """INSERT INTO saved_machines(id,owner_id,label,model_id,model_text,serial_text,created_at,archived_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (id) DO UPDATE SET archived_at=EXCLUDED.archived_at""",
                m.id, m.owner_id, m.label, model_id, m.model_text, m.serial_text, m.created_at, datetime.now(timezone.utc) if m.archived else None,
            )
        known_imports = persisted.get("imports", {})
        for bid, b in ws.imports.items():
            if b.state == "staged" or known_imports.get(bid) == digest((b.state, b.issues, b.preview, b.version_id, b.content_sha256)):
                continue
            status = {"validated": "valid"}.get(b.state, b.state if b.state in ("uploaded", "validating", "invalid", "published") else "uploaded")
            await conn.execute(
                """INSERT INTO import_batches(id,created_by,version_id,storage_key,sha256,status,row_count,created_at,filename,detail,base_version_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                   ON CONFLICT (id) DO UPDATE SET version_id=EXCLUDED.version_id, sha256=EXCLUDED.sha256, status=EXCLUDED.status, row_count=EXCLUDED.row_count, detail=EXCLUDED.detail, base_version_id=EXCLUDED.base_version_id""",
                b.id, b.created_by, b.version_id if b.state == "published" else None, f"imports/{b.id}.csv", b.content_sha256 or "0" * 64, status, len(b.rows),
                b.created_at, b.filename, json.loads(dumps({"issues": b.issues, "preview": b.preview})),
                b.base_version_id if await conn.fetchval("SELECT 1 FROM catalogue_versions WHERE id=$1", b.base_version_id) else None,
            )
            if not await conn.fetchval("SELECT 1 FROM import_rows WHERE batch_id=$1 LIMIT 1", b.id):
                await conn.executemany(
                    "INSERT INTO import_rows(batch_id,row_number,entity_type,payload) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                    [(b.id, n, (row.get("entity_type") or "unknown")[:60], row) for n, row in enumerate(b.rows, start=2)],
                )
        known_corr = persisted.get("corrections", {})
        for cid, c in ws.corrections.items():
            if known_corr.get(cid) == digest(c):
                continue
            await conn.execute(
                """INSERT INTO correction_records(id,enquiry_id,revision,corrected_by,before_value,after_value,reason,field,reviewed,created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,'reviewer correction',$7,$8,$9) ON CONFLICT (id) DO UPDATE SET reviewed=EXCLUDED.reviewed""",
                c.id, c.enquiry_id, c.revision, c.author_id, {"value": c.before}, {"value": c.after}, c.field, c.reviewed, c.created_at,
            )
        known_evals = persisted.get("evaluations", set())
        version = None
        for eid, ev in ws.evaluations.items():
            if eid not in known_evals and version is None:
                version = await conn.fetchval("SELECT id FROM catalogue_versions WHERE state='published'")
            if eid in known_evals or ev.state != "succeeded":
                continue
            await conn.execute("INSERT INTO eval_runs(id,git_sha,model,dataset_sha256,started_at,completed_at,status) VALUES ($1,$2,$3,$4,$5,now(),$6)",
                               ev.id, "workspace", "fixture-pipeline", ev.dataset_sha256, ev.created_at, "passed" if ev.failed == 0 else "failed")
            for res in ev.results:
                await conn.execute("INSERT INTO eval_cases(id,scenario,input,expected,catalogue_version_id,language) VALUES ($1,$1,'{}'::jsonb,'{}'::jsonb,$2,'en') ON CONFLICT (id) DO NOTHING", res.case_id, version)
                await conn.execute("INSERT INTO eval_results(run_id,case_id,actual,passed,duration_ms) VALUES ($1,$2,$3,$4,0) ON CONFLICT DO NOTHING", ev.id, res.case_id, res.actual.model_dump(mode="json"), res.passed)




_ENQUIRY_SQL = """INSERT INTO enquiries(id,channel,raw_text,detected_language,extracted,configuration_id,status,created_at,updated_at,owner_id,revision,
     catalogue_version_id,destination_warehouse_id,assigned_to,priority,due_at,idempotency_key,locale,run_mode,workspace_state)
   VALUES ($1,'chat',$2,$3,'{}'::jsonb,$4,$5::enquiry_status,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
   ON CONFLICT (id) DO UPDATE SET detected_language=EXCLUDED.detected_language, configuration_id=EXCLUDED.configuration_id,
     status=EXCLUDED.status, updated_at=EXCLUDED.updated_at, revision=EXCLUDED.revision, catalogue_version_id=EXCLUDED.catalogue_version_id,
     assigned_to=EXCLUDED.assigned_to, priority=EXCLUDED.priority, due_at=EXCLUDED.due_at, locale=EXCLUDED.locale,
     run_mode=EXCLUDED.run_mode, workspace_state=EXCLUDED.workspace_state"""
_ITEM_SQL = """INSERT INTO enquiry_items(id,enquiry_id,ordinal,requested_text,quantity,model_text,serial_text,configuration_id,selected_part_id,status,revision,detail)
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
   ON CONFLICT (id) DO UPDATE SET requested_text=EXCLUDED.requested_text, quantity=EXCLUDED.quantity, model_text=EXCLUDED.model_text,
     serial_text=EXCLUDED.serial_text, configuration_id=EXCLUDED.configuration_id, selected_part_id=EXCLUDED.selected_part_id,
     status=EXCLUDED.status, revision=EXCLUDED.revision, detail=EXCLUDED.detail"""
_RUN_SQL = """INSERT INTO workflow_runs(id,enquiry_id,revision,mode,status,control,execution_source,created_by,catalogue_version_id,limits,
     agent_turns,tool_calls,input_tokens,output_tokens,estimated_usd,retries,active_seconds,state_version,fence,thread_id,carried_from,
     blocked_reason,terminal_reason,created_at,updated_at,completed_at,agenda,board,seen_signatures,next_seq,current_step)
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31)
   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, control=EXCLUDED.control, agent_turns=EXCLUDED.agent_turns, tool_calls=EXCLUDED.tool_calls,
     input_tokens=EXCLUDED.input_tokens, output_tokens=EXCLUDED.output_tokens, estimated_usd=EXCLUDED.estimated_usd, retries=EXCLUDED.retries,
     active_seconds=EXCLUDED.active_seconds, state_version=EXCLUDED.state_version, fence=EXCLUDED.fence, blocked_reason=EXCLUDED.blocked_reason,
     terminal_reason=EXCLUDED.terminal_reason, updated_at=EXCLUDED.updated_at, completed_at=EXCLUDED.completed_at, agenda=EXCLUDED.agenda,
     board=EXCLUDED.board, seen_signatures=EXCLUDED.seen_signatures, next_seq=EXCLUDED.next_seq, current_step=EXCLUDED.current_step"""
_EXCHANGE_SQL = """INSERT INTO agent_exchanges(id,run_id,seq,sender,recipient,kind,summary,payload,evidence_refs,source,correlation_id,reply_to,status,created_at)
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status"""
_PENDING_SQL = """INSERT INTO pending_actions(id,run_id,enquiry_id,revision,kind,requested_by,code,item_id,prompt,options,allowed_resolutions,status,exchange_id,resolved_by,resolved_at,resolution,created_at)
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, resolved_by=EXCLUDED.resolved_by, resolved_at=EXCLUDED.resolved_at, resolution=EXCLUDED.resolution"""

__all__ = ["PostgresWorkspaceStore", "encode_value", "decode_value"]


class PostgresIntakeIdempotency:
    """Actor-scoped idempotency for enquiry intake (``idempotency_records``), database mode.

    Same contract as the in-memory store: ``lookup`` returns ``(request_hash, stored_result)``;
    ``reserve`` keeps the FIRST result for a key (a replay never overwrites it).
    """

    def __init__(self, store: PostgresWorkspaceStore) -> None:
        self._store = store

    async def lookup(self, actor: Any, key: UUID) -> tuple[str, str] | None:
        async with self._store.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT request_sha256, response FROM idempotency_records WHERE actor_id=$1 AND operation='intake' AND key=$2", actor.user_id, key)
        if row is None:
            return None
        return row["request_sha256"], row["response"]["result"]

    async def reserve(self, actor: Any, key: UUID, request_hash: str, result: str) -> None:
        await self._store.ensure_profile(actor.user_id, getattr(actor, "email", None))
        async with self._store.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO idempotency_records(actor_id,operation,key,request_sha256,response) VALUES ($1,'intake',$2,$3,$4) ON CONFLICT DO NOTHING",
                actor.user_id, key, request_hash, {"result": result},
            )
