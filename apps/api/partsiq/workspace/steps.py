"""Pipeline steps over an enquiry record — called by the guided graph nodes AND by the
collaboration controller's tools, so both modes share every safeguard (ADR 0002).

A step mutates the record's DERIVED state for the current revision and returns a
:class:`StepReport`: a concise, customer-safe label, an evidence line for staff, structured data
for agent exchanges and, when a person must act, a :class:`PendingSpec`. No step decides
compatibility from model output, invents stock or approves anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from partsiq.core.errors import PartsIQError
from partsiq.enquiries.questions import validate_selection

from . import domain
from .catalogue import CatalogueContext
from .language import CallUsage, LanguageProvider
from .records import EnquiryRecord, ItemRecord, NameplateRecord, utcnow

STEP_LABELS = {
    "intake": "Reading your request",
    "nameplate": "Reading the nameplate photo",
    "identify": "Identifying the machine",
    "search": "Finding compatible parts",
    "choose": "Applying your part choice",
    "plan": "Planning stock and transfers",
    "draft": "Drafting the reply",
    "verify": "Checking selections and evidence",
}


@dataclass
class PendingSpec:
    kind: str  # clarification | nameplate_confirmation | delegation_consent
    code: str
    item_id: UUID | None
    prompt: str
    options: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StepReport:
    step: str
    label: str
    status: str  # done | waiting | failed
    detail: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    pending: PendingSpec | None = None
    usage: CallUsage = field(default_factory=CallUsage)


def _customer_text(record: EnquiryRecord) -> str:
    return "\n".join(m.body for m in record.messages if m.kind == "customer")


def reset_derived(record: EnquiryRecord) -> None:
    """Clear everything derived from facts for a new revision (F38/F40): recompute from scratch.

    Customer-confirmed identifiers and explicit part choices are carried forward as INPUTS; the
    compatible set, plan, draft and verification are always recomputed and re-verified.
    """
    record.facts = None
    record.evidence = None
    record.draft_slots = None
    record.draft_id = None
    record.draft_rendered = None
    record.draft_source = None
    record.verification = None
    record.verification_id = None
    record.review_ready_at = None
    record.pending_question = None
    record.pending_code = None
    record.pending_item_id = None
    for item in record.items:
        item.configuration_id = None
        item.configuration_label = None
        item.identification_note = None
        item.candidates = []
        item.margin = None
        if item.selection_source != "customer_choice":
            item.selected_part_id = None
            item.selection_source = None
        item.plan_strategy = None
        item.plan_lines = []
        item.shortage = 0
        item.plan_message = None
        item.quoted_number_note = None
        item.clarification_code = None
        item.clarification_text = None
        item.status = "unresolved"


def _set_pending(record: EnquiryRecord, item: ItemRecord, code: str, options: list[dict[str, Any]] | None = None) -> PendingSpec:
    prompt = domain.question_text(code, record.locale, options=None)
    item.status = "needs_information"
    item.clarification_code = code
    item.clarification_text = prompt
    record.pending_question = prompt
    record.pending_code = code
    record.pending_item_id = item.id
    return PendingSpec(kind="clarification", code=code, item_id=item.id, prompt=prompt, options=options or [])


class Pipeline:
    """The shared deterministic pipeline for one workspace."""

    def __init__(self, catalogue: CatalogueContext, language: LanguageProvider) -> None:
        self.catalogue = catalogue
        self.language = language

    # ------------------------------------------------------------------ intake

    async def intake(self, record: EnquiryRecord) -> StepReport:
        usage = CallUsage()
        if not record.items:
            outcome, usage = await self.language.extract(_customer_text(record), self.catalogue, enquiry_id=record.id)
            record.items = domain.item_records(record, outcome)
            record.language = outcome.language
            if outcome.urgency == "urgent":
                record.urgency = "urgent"
                record.priority = "urgent"
            source = outcome.source
        else:
            source = "carried"
        domain.apply_confirmed_identifiers(record)
        record.catalogue_version_id = self.catalogue.version_id
        summary = "; ".join(
            f"{_qty(i)} × {i.description}"
            + (f" for {i.model_text}" if i.model_text else "")
            + (f" (serial {i.serial_text})" if i.serial_text else "")
            for i in record.items
        )
        report = StepReport(
            "intake",
            STEP_LABELS["intake"],
            "done",
            f"{len(record.items)} item(s): {summary}",
            data={
                "source": source,
                "language": record.language,
                "items": [_item_brief(i) for i in record.items],
            },
            usage=usage,
        )
        return report

    # ------------------------------------------------------------------ identify

    async def identify(self, record: EnquiryRecord, *, item_ids: list[UUID] | None = None) -> StepReport:
        notes: list[str] = []
        pending: PendingSpec | None = None
        resolved = []
        for item in record.items:
            if item_ids and item.id not in item_ids:
                continue
            if item.configuration_id is not None or item.status == "needs_information":
                continue
            outcome = await domain.identify_item(item, self.catalogue)
            item.identification_note = outcome.note
            if outcome.state == "resolved":
                item.configuration_id = outcome.configuration_id
                item.configuration_label = outcome.label
                resolved.append(outcome.label)
                notes.append(f"{item.description}: {outcome.label}")
            elif pending is None:
                code = domain.identification_question_code(outcome.state)
                options = [{"value": c, "label": c} for c in outcome.candidates[:3]] if outcome.state == "ambiguous_model" else []
                pending = _set_pending(record, item, code, options)
                notes.append(f"{item.description}: {outcome.state} — {outcome.note}")
        status = "waiting" if pending else "done"
        return StepReport(
            "identify",
            STEP_LABELS["identify"],
            status,
            "; ".join(notes) or "Machine already identified.",
            data={"resolved": resolved, "state": "needs_information" if pending else "resolved"},
            pending=pending,
        )

    # ------------------------------------------------------------------ search

    async def search(self, record: EnquiryRecord, *, item_ids: list[UUID] | None = None) -> StepReport:
        notes: list[str] = []
        refs: list[str] = []
        pending: PendingSpec | None = None
        for item in record.items:
            if item_ids and item.id not in item_ids:
                continue
            if item.configuration_id is None or item.candidates or item.status != "unresolved":
                continue
            outcome = await domain.search_item(item, self.catalogue)
            item.candidates = outcome.candidates
            item.margin = outcome.margin
            refs.extend(c.source_reference for c in outcome.candidates[:3])
            if item.selection_source == "customer_choice" and item.selected_part_id is not None:
                # Re-validate a carried-forward choice against the CURRENT compatible set (F26).
                validate_selection([c.part_id for c in outcome.candidates], item.selected_part_id)
                item.status = "ready"
                notes.append(f"{item.description}: customer choice confirmed compatible")
                continue
            if outcome.action == "resolve" and outcome.selected_part_id is not None:
                item.selected_part_id = outcome.selected_part_id
                item.selection_source = "search"
                item.status = "ready"
                item.quoted_number_note = outcome.note if item.part_numbers else None
                chosen = next((c for c in outcome.candidates if c.part_id == outcome.selected_part_id), None)
                notes.append(f"{item.description}: {chosen.part_number if chosen else outcome.selected_part_id} ({outcome.note})")
            elif outcome.action == "needs_staff":
                item.status = "unavailable"
                notes.append(f"{item.description}: no compatible part in the active catalogue")
            elif pending is None:
                code = "mismatch" if outcome.action == "mismatch" else "ambiguous_part"
                item.quoted_number_note = outcome.note if outcome.action == "mismatch" else None
                options = [
                    {"value": str(c.part_id), "label": f"{c.part_number} — {c.name_en}", "part_number": c.part_number}
                    for c in outcome.candidates[:3]
                ]
                pending = _set_pending(record, item, code, options)
                notes.append(f"{item.description}: {outcome.note}")
        if all(i.status == "unavailable" for i in record.items):
            record.step = "needs_staff"
        return StepReport(
            "search",
            STEP_LABELS["search"],
            "waiting" if pending else "done",
            "; ".join(notes) or "Compatible candidates already resolved.",
            data={
                "items": [
                    {
                        "item_id": str(i.id),
                        "configuration_id": i.configuration_id,
                        "candidates": [
                            {"part_id": c.part_id, "part_number": c.part_number, "score": c.score, "source_reference": c.source_reference}
                            for c in i.candidates[:3]
                        ],
                        "selected_part_id": i.selected_part_id,
                        "status": i.status,
                    }
                    for i in record.items
                ]
            },
            evidence_refs=sorted(set(refs)),
            pending=pending,
        )

    # ------------------------------------------------------------------ plan

    async def plan(self, record: EnquiryRecord) -> StepReport:
        notes = []
        # Quantity is checked only once a compatible part is known, so a fit question is
        # answered first; a missing or non-whole quantity is asked, never assumed.
        for item in record.items:
            if item.status == "ready" and domain.validate_quantity(item):
                pending = _set_pending(record, item, "quantity")
                return StepReport(
                    "plan", STEP_LABELS["plan"], "waiting",
                    f"{item.description}: quantity needed before stock can be planned.",
                    pending=pending,
                )
        for item in record.items:
            if item.status != "ready":
                continue
            outcome = await domain.plan_item(item, record, self.catalogue)
            item.plan_strategy = outcome.strategy
            item.plan_lines = outcome.lines
            item.shortage = outcome.shortage
            item.plan_message = outcome.message
            notes.append(outcome.message)
        return StepReport(
            "plan",
            STEP_LABELS["plan"],
            "done",
            " ".join(notes) or "No ready item to plan.",
            data={
                "plans": [
                    {
                        "item_id": str(i.id),
                        "strategy": i.plan_strategy,
                        "lines": [{"warehouse": line.warehouse_code, "quantity": line.quantity, "transfer_days": line.transfer_days} for line in i.plan_lines],
                        "shortage": i.shortage,
                    }
                    for i in record.items
                    if i.status == "ready"
                ]
            },
        )

    # ------------------------------------------------------------------ draft + verify

    async def draft(self, record: EnquiryRecord) -> StepReport:
        facts, evidence = domain.build_facts(record, self.catalogue)
        record.facts = facts
        record.evidence = evidence
        slots, usage = await self.language.draft(facts, record.locale)
        record.draft_slots = slots
        record.draft_rendered = domain.render(record, slots)
        record.draft_id = uuid4()
        record.draft_source = self.language.source
        return StepReport(
            "draft",
            STEP_LABELS["draft"],
            "done",
            f"Draft rendered from {len(facts.items)} verified item(s); prose source: {self.language.source}.",
            data={"draft_id": str(record.draft_id), "items": len(facts.items)},
            usage=usage,
        )

    async def verify(self, record: EnquiryRecord) -> StepReport:
        result = domain.verify(record, self.catalogue)
        record.verification = result
        record.verification_id = uuid4()
        failures = ", ".join(f.code for f in result.failures)
        return StepReport(
            "verify",
            STEP_LABELS["verify"],
            "done" if result.passed else "failed",
            "All seven verification rules passed." if result.passed else f"Verification failed: {failures}",
            data={"passed": result.passed, "failures": [f.code for f in result.failures], "facts_sha256": result.facts_sha256},
        )

    # ------------------------------------------------------------------ nameplate

    def read_nameplate(self, record: EnquiryRecord) -> StepReport | None:
        """Fixture vision: read the synthetic nameplate fixture; unknown images are 'unreadable'.

        Identifiers always require customer confirmation (F15); confidence is never accuracy.
        """
        attachment = next((a for a in record.attachments if a.status == "validated"), None)
        if attachment is None or (record.nameplate and record.nameplate.attachment_id == attachment.id):
            return None
        model, serial, issues = fixture_nameplate(attachment.fixture_key)
        record.nameplate = NameplateRecord(
            attachment_id=attachment.id,
            extraction_id=uuid4(),
            model_text=model,
            serial_text=serial,
            issues=issues,
            source="fixture",
        )
        found = ", ".join(x for x in (model and f"model {model}", serial and f"serial {serial}") if x)
        pending = PendingSpec(
            kind="nameplate_confirmation",
            code="confirm_identifiers",
            item_id=None,
            prompt=(
                "Please confirm the model and serial read from your nameplate photo."
                if record.locale == "en"
                else "من فضلك أكّد الموديل والرقم التسلسلي المقروءين من صورة لوحة الصنع."
            ),
            options=[{"value": "model", "label": model or ""}, {"value": "serial", "label": serial or ""}],
        )
        return StepReport(
            "nameplate",
            STEP_LABELS["nameplate"],
            "waiting",
            f"Read {found or 'no identifiers'} from the photo (fixture vision){'; issues: ' + ', '.join(issues) if issues else ''}. Customer confirmation required.",
            data={"model_text": model, "serial_text": serial, "issues": issues, "source": "fixture"},
            pending=pending,
        )


# The committed synthetic nameplate fixtures and what they show (tools/demo/render_assets.py).
_FIXTURE_PLATES = {
    "Corvane_Air_CA-110_800000.png": ("CA-110", "800000"),
}


def fixture_nameplate(fixture_key: str | None) -> tuple[str | None, str | None, list[str]]:
    if fixture_key and fixture_key in _FIXTURE_PLATES:
        model, serial = _FIXTURE_PLATES[fixture_key]
        return model, serial, []
    return None, None, ["unreadable"]


# ---------------------------------------------------------------------- answers


def apply_answer(record: EnquiryRecord, text: str, catalogue: CatalogueContext) -> str:
    """Apply a customer's clarification answer to the pending item as new INPUT for a revision.

    Returns a short description of what was understood. Raises VALIDATION_FAILED (422) when the
    answer cannot be read for the pending question, so the client keeps the unsent text.
    """
    code = record.pending_code
    item = next((i for i in record.items if i.id == record.pending_item_id), None)
    if code is None or item is None:
        raise PartsIQError("CONFLICT", detail="There is no open question on this enquiry.")
    raw = domain._norm(text)
    if code in ("needs_serial",):
        match = re.search(r"\d{4,9}", raw)
        if not match:
            raise PartsIQError("VALIDATION_FAILED", detail="Please include the serial number from the nameplate.")
        item.serial_text = match.group(0)
        parsed = domain.fixture_extract(raw, catalogue)
        if parsed.items and parsed.items[0].model_text and parsed.items[0].model_text in domain._model_codes(catalogue):
            item.model_text = parsed.items[0].model_text
        return f"serial {item.serial_text}"
    if code in ("needs_model", "ambiguous_model"):
        parsed = domain.fixture_extract(raw, catalogue)
        model = parsed.items[0].model_text if parsed.items else None
        if not model:
            raise PartsIQError("VALIDATION_FAILED", detail="Please include the machine model shown on the nameplate.")
        item.model_text = model
        if parsed.items[0].serial_text:
            item.serial_text = parsed.items[0].serial_text
        if parsed.items[0].config_code_text:
            item.config_code_text = parsed.items[0].config_code_text
        return f"model {model}" + (f", serial {item.serial_text}" if item.serial_text else "")
    if code == "quantity":
        match = re.search(r"\d{1,6}(?:\.\d+)?", raw)
        try:
            quantity = Decimal(match.group(0)) if match else None
        except InvalidOperation:
            quantity = None
        if quantity is None or quantity <= 0 or quantity != quantity.to_integral_value():
            raise PartsIQError("VALIDATION_FAILED", detail="Please reply with a whole number of units.")
        item.quantity = quantity
        return f"quantity {quantity}"
    if code in ("ambiguous_part", "mismatch"):
        numbers = [m.group(1).upper() for m in domain._PART_NUMBER_RE.finditer(raw)]
        candidates = item.candidates
        chosen = None
        for number in numbers:
            chosen = next((c for c in candidates if c.part_number.upper() == number), None)
            if chosen:
                break
        if chosen is None:
            ordinal = re.search(r"\b([1-3])\b|\b(first|second|third)\b", raw.lower())
            if ordinal:
                index = int(ordinal.group(1)) - 1 if ordinal.group(1) else ["first", "second", "third"].index(ordinal.group(2))
                if index < len(candidates):
                    chosen = candidates[index]
        if chosen is None:
            lowered = raw.lower()
            named = [c for c in candidates if c.name_en.lower() in lowered or c.name_ar in raw]
            if len(named) == 1:
                chosen = named[0]
        if chosen is not None:
            item.selected_part_id = chosen.part_id
            item.selection_source = "customer_choice"
            item.part_numbers = []
            return f"chose {chosen.part_number}"
        if numbers and code == "mismatch":
            item.part_numbers = numbers
            return f"corrected part number {', '.join(numbers)}"
        raise PartsIQError("VALIDATION_FAILED", detail="Please choose one of the listed parts (for example by its part number).")
    raise PartsIQError("CONFLICT", detail="This question cannot be answered here.")


def _qty(item: ItemRecord) -> str:
    return "?" if item.quantity is None else format(item.quantity.normalize(), "f")


def _item_brief(item: ItemRecord) -> dict[str, Any]:
    return {
        "item_id": str(item.id),
        "description": item.description,
        "quantity": None if item.quantity is None else format(item.quantity.normalize(), "f"),
        "model_text": item.model_text,
        "serial_text": item.serial_text,
        "config_code_text": item.config_code_text,
        "part_numbers": item.part_numbers,
    }


def now_iso() -> str:
    return utcnow().isoformat()
