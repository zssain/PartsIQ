"""Shared domain steps used by BOTH workflow modes (guided LangGraph and agent collaboration).

Each function is ordinary deterministic code over an :class:`EnquiryRecord` and the workspace
:class:`CatalogueContext`. They adapt the existing domain services rather than reimplementing
them:

* machine identification -> :func:`partsiq.search.identification.identify_machine` (via
  ``SearchService.identify``), plus two explicit, reviewer-visible fallbacks: a configuration code
  the customer stated (``CA-110 (A)``) and a configuration implied by a quoted part number that
  fits exactly one configuration of the stated model;
* compatibility filtering, ranking and supersession -> ``SearchService.search_parts``
  (compatible-only by construction; explicit successor fitment, ADR-018);
* ambiguity -> :func:`partsiq.enquiries.questions.decide_ambiguity` (code thresholds);
* fulfilment -> ``SearchService.plan_fulfilment`` (stock + approved transfer routes);
* verified facts + evidence -> :func:`partsiq.enquiries.verification.verify_facts`;
* the customer reply -> :func:`partsiq.enquiries.renderer.render_reply` (code owns every fact).

No model output can introduce a candidate, a configuration, a quantity or a stock figure here.
The FIXTURE intake extractor below is a rule-based parser over the catalogue vocabulary; it is
labelled ``fixture`` wherever its output appears and is never presented as a live model.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from partsiq.core.contracts import (
    Allocation,
    CandidateEvidence,
    Locale,
    ReplySlots,
    StockEvidence,
    VerificationEvidence,
    VerificationResult,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.questions import clarification, decide_ambiguity
from partsiq.enquiries.renderer import render_reply
from partsiq.enquiries.verification import verify_facts
from partsiq.search import schemas

from .catalogue import CatalogueContext, evidence_id_for
from .records import CandidateRecord, EnquiryRecord, ItemRecord, PlanLine, utcnow

_ITEM_NS = uuid5(NAMESPACE_URL, "partsiq.workspace.item")

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PART_NUMBER_RE = re.compile(r"\b([A-Z]{2,3}-[A-Z]{2}-\d{3,5})\b", re.IGNORECASE)
_SERIAL_RE = re.compile(
    r"(?:serial(?:\s*(?:no\.?|number))?|s/?n|سيريال|الرقم التسلسلي|رقم تسلسلي|تسلسلي)\s*[:#]?\s*(\d{4,9})",
    re.IGNORECASE,
)
_BARE_SERIAL_RE = re.compile(r"(?<![\w-])(\d{6,7})(?![\w-])")
_CONFIG_RE = re.compile(r"\(\s*([A-Z])\s*\)|\b(?:config(?:uration)?|type)\s+([A-Z])\b", re.IGNORECASE)
_URGENT_RE = re.compile(r"\b(urgent|asap|immediately|emergency)\b|عاجل|ضروري|بسرعة", re.IGNORECASE)
_QTY_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "a pair of": 2,
    "واحد": 1, "اثنين": 2, "ثلاثة": 3, "أربعة": 4, "خمسة": 5,
}
MAX_ITEMS = 20


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_ARABIC_DIGITS)


def detect_language(text: str) -> str:
    arabic = any("؀" <= ch <= "ۿ" for ch in text)
    latin = any(("a" <= ch.lower() <= "z") for ch in text)
    if arabic and latin:
        return "mixed"
    return "ar" if arabic else "en"


# --------------------------------------------------------------------------- intake (fixture)


@dataclass
class ExtractedItem:
    description: str
    quantity: Decimal | None
    model_text: str | None
    serial_text: str | None
    config_code_text: str | None
    part_numbers: list[str]


@dataclass
class IntakeOutcome:
    language: str
    urgency: str
    items: list[ExtractedItem]
    source: str  # fixture | live
    notes: list[str] = field(default_factory=list)


def _vocabulary(catalogue: CatalogueContext) -> list[str]:
    """Part phrases the fixture extractor recognises: catalogue names + aliases (EN/AR)."""
    phrases: set[str] = set()
    for record in catalogue.records_of("parts"):
        for key in ("name_en", "name_ar"):
            value = str(record.payload.get(key, "")).strip()
            if value:
                phrases.add(value.lower())
                if key == "name_en" and value.lower().endswith(" element"):
                    phrases.add(value.lower().removesuffix(" element"))
    for record in catalogue.records_of("part_aliases"):
        value = str(record.payload.get("alias", "")).strip()
        if value:
            phrases.add(value.lower())
    # Generic nouns last so a specific phrase ("air filter") wins over "filter".
    phrases.update({"filter", "separator", "belt", "فلتر", "سير"})
    return sorted(phrases, key=len, reverse=True)


def _model_codes(catalogue: CatalogueContext) -> list[str]:
    return sorted(
        {str(r.payload.get("model_code", "")) for r in catalogue.records_of("equipment_models")},
        key=len,
        reverse=True,
    )


def _quantity_before(text: str, start: int) -> Decimal | None:
    window = text[max(0, start - 24):start].lower()
    match = re.search(r"(\d{1,6}(?:\.\d+)?)\s*(?:x|×|pcs|pieces|units|qty|nos?\.?)?\s*$", window)
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            return None
    for word, value in _QTY_WORDS.items():
        if window.rstrip().endswith(word):
            return Decimal(value)
    # A singular article ("a hydraulic filter") states one unit; nothing else is assumed.
    if re.search(r"(?:^|\s)(?:a|an)\s*$", window):
        return Decimal(1)
    match = re.search(r"(?:qty|quantity|الكمية|عدد)\s*[:#]?\s*(\d{1,6})", text.lower())
    if match:
        return Decimal(match.group(1))
    return None


def fixture_extract(text: str, catalogue: CatalogueContext) -> IntakeOutcome:
    """Rule-based FIXTURE intake: items, quantity, model, serial, quoted numbers (no model call)."""
    raw = _norm(text)
    lowered = raw.lower()
    language = detect_language(text)
    urgency = "urgent" if _URGENT_RE.search(raw) else "normal"

    model_text = None
    for code in _model_codes(catalogue):
        if code and re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", raw, re.IGNORECASE):
            model_text = code
            break
    if model_text is None:
        # Typed without the hyphen ("CA110"): match on the compacted catalogue code.
        compact = {c.replace("-", "").upper(): c for c in _model_codes(catalogue) if c}
        for token in re.findall(r"\b[A-Z]{2,3}\d{2,3}[A-Z]?\b", raw.upper()):
            if token in compact:
                model_text = compact[token]
                break
    if model_text is None:
        # Keep an unknown model-looking token (e.g. "CAT 320") so the question can quote it.
        match = re.search(r"\b([A-Z]{2,5}[- ]?\d{2,4}[A-Z]?)\b", raw)
        if match and not _PART_NUMBER_RE.fullmatch(match.group(1)):
            model_text = match.group(1)

    serial = None
    match = _SERIAL_RE.search(raw)
    if match:
        serial = match.group(1)
    else:
        bare = [m.group(1) for m in _BARE_SERIAL_RE.finditer(raw)]
        if len(bare) == 1:
            serial = bare[0]

    config_code = None
    match = _CONFIG_RE.search(raw)
    if match:
        config_code = (match.group(1) or match.group(2) or "").upper() or None

    part_numbers = sorted({m.group(1).upper() for m in _PART_NUMBER_RE.finditer(raw)})
    # Hyphen-less or spaced numbers ("CAAF8973") resolve to the catalogue spelling by key.
    from partsiq_common.text import part_number_key

    by_key = {part_number_key(str(r.payload.get("part_number", ""))): str(r.payload.get("part_number")) for r in catalogue.records_of("parts")}
    for token in re.findall(r"\b[A-Z]{4,5}\d{3,5}\b", raw.upper()):
        if token in by_key and by_key[token] not in part_numbers:
            part_numbers.append(by_key[token])
    part_numbers = sorted(set(part_numbers))

    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for phrase in _vocabulary(catalogue):
        for m in re.finditer(rf"(?<![\w]){re.escape(phrase)}(?:s|es)?(?![\w])", lowered):
            span = (m.start(), m.end())
            if any(not (span[1] <= a or span[0] >= b) for a, b in taken):
                continue
            taken.append(span)
            found.append((m.start(), raw[m.start():m.end()]))
    found.sort()
    notes: list[str] = []
    items: list[ExtractedItem] = []
    if found:
        seen_desc: set[str] = set()
        for start, phrase in found:
            key = phrase.lower().rstrip("s")
            if key in seen_desc:
                continue
            seen_desc.add(key)
            items.append(
                ExtractedItem(
                    description=phrase,
                    quantity=_quantity_before(raw, start),
                    model_text=model_text,
                    serial_text=serial,
                    config_code_text=config_code,
                    part_numbers=part_numbers if len(found) == 1 else [],
                )
            )
    if not items:
        description = raw.strip()[:200] or "Spare part request"
        if part_numbers:
            description = f"Part {', '.join(part_numbers)}"
        items.append(
            ExtractedItem(
                description=description,
                quantity=_quantity_before(raw, 0),
                model_text=model_text,
                serial_text=serial,
                config_code_text=config_code,
                part_numbers=part_numbers,
            )
        )
    if part_numbers and len(items) > 1:
        notes.append("Quoted part numbers apply to the whole message; matched per item.")
    return IntakeOutcome(language=language, urgency=urgency, items=items[:MAX_ITEMS], source="fixture", notes=notes)


def item_records(record: EnquiryRecord, outcome: IntakeOutcome) -> list[ItemRecord]:
    """Turn extracted items into revision-bound item records with stable ids."""
    items: list[ItemRecord] = []
    for index, extracted in enumerate(outcome.items, start=1):
        items.append(
            ItemRecord(
                id=uuid5(_ITEM_NS, f"{record.id}:{index}"),
                ordinal=index,
                description=extracted.description[:1000],
                # A missing quantity is NOT invented by a model: code applies one explicit default
                # (one unit), flags it, and the reviewer sees "quantity assumed" before approval.
                quantity=extracted.quantity if extracted.quantity is not None else Decimal("1"),
                quantity_assumed=extracted.quantity is None,
                model_text=extracted.model_text,
                serial_text=extracted.serial_text,
                config_code_text=extracted.config_code_text,
                part_numbers=list(extracted.part_numbers),
            )
        )
    return items


def apply_confirmed_identifiers(record: EnquiryRecord) -> None:
    """A customer-confirmed nameplate overrides parsed model/serial (confirmation flow, F15)."""
    plate = record.nameplate
    if plate is None or not plate.confirmed:
        return
    for item in record.items:
        if plate.confirmed_model:
            item.model_text = plate.confirmed_model
        if plate.confirmed_serial:
            item.serial_text = plate.confirmed_serial


def validate_quantity(item: ItemRecord) -> str | None:
    """Return a clarification code when the quantity cannot back a fulfilment plan."""
    if item.quantity is None or item.quantity <= 0 or item.quantity > 100000:
        return "quantity"
    if item.quantity != item.quantity.to_integral_value():
        return "quantity"
    return None


QUANTITY_QUESTION = (
    "Please confirm how many units you need (a whole number).",
    "من فضلك أكّد عدد القطع المطلوبة (رقم صحيح).",
)


def question_text(code: str, locale: Locale, *, options: list[str] | None = None) -> str:
    if code == "quantity":
        text = QUANTITY_QUESTION[1] if locale == "ar" else QUANTITY_QUESTION[0]
    else:
        text = clarification(code, locale)
    if options:
        text = f"{text} " + " / ".join(options)
    return text


# --------------------------------------------------------------------------- identification


@dataclass
class IdentifyOutcome:
    state: str  # resolved | needs_serial | ambiguous_model | serial_mismatch | not_found
    configuration_id: int | None
    label: str | None
    note: str
    candidates: list[str] = field(default_factory=list)


async def identify_item(item: ItemRecord, catalogue: CatalogueContext) -> IdentifyOutcome:
    query = " ".join(x for x in (item.model_text, item.description) if x) or item.description
    try:
        response = await catalogue.search.identify(
            schemas.IdentifyRequest(query=query[:500], serial=item.serial_text)
        )
    except ValueError as exc:  # pragma: no cover - request validator guards empty input
        raise PartsIQError("VALIDATION_FAILED", internal_detail=str(exc)) from exc
    names = [c.model.model_code for c in response.candidates]
    if response.status == "resolved" and response.configuration and response.model:
        return IdentifyOutcome(
            "resolved",
            response.configuration.id,
            f"{response.model.brand} {response.model.model_code} · configuration {response.configuration.config_code}",
            response.message,
            names,
        )
    if response.status == "needs_serial" and response.model:
        # Explicit, reviewer-visible fallbacks (never a silent guess).
        if item.config_code_text:
            for cfg in response.model.configurations:
                if cfg.config_code.upper() == item.config_code_text.upper():
                    return IdentifyOutcome(
                        "resolved",
                        cfg.id,
                        f"{response.model.brand} {response.model.model_code} · configuration {cfg.config_code}",
                        "Configuration taken from the code the customer stated; serial not provided.",
                        names,
                    )
        if item.part_numbers:
            fits: set[int] = set()
            for number in item.part_numbers:
                part = catalogue.part_by_number(number)
                if part is None:
                    continue
                for machine in await catalogue.repository.fetch_compatible_machines(int(part["id"])):
                    if machine.model_code == response.model.model_code:
                        fits.add(machine.configuration_id)
            all_configs = {c.id for c in response.model.configurations}
            if len(fits) == 1:
                cfg_id = next(iter(fits))
                cfg = next(c for c in response.model.configurations if c.id == cfg_id)
                return IdentifyOutcome(
                    "resolved",
                    cfg_id,
                    f"{response.model.brand} {response.model.model_code} · configuration {cfg.config_code}",
                    "Configuration inferred from the quoted part number (fits one configuration "
                    "of this model). Reviewer should confirm the serial.",
                    names,
                )
            if fits and fits == all_configs:
                # The quoted part is listed for EVERY configuration of the model, so fitment holds
                # whichever one the customer has; the serial is not needed for this part.
                cfg = min(response.model.configurations, key=lambda c: c.id)
                return IdentifyOutcome(
                    "resolved",
                    cfg.id,
                    f"{response.model.brand} {response.model.model_code} · all configurations",
                    "Serial not given, but the quoted part is listed as compatible with every "
                    "configuration of this model. Reviewer should confirm before approval.",
                    names,
                )
    return IdentifyOutcome(response.status, None, None, response.message, names)


def identification_question_code(state: str) -> str:
    return {
        "needs_serial": "needs_serial",
        "ambiguous_model": "ambiguous_model",
        "serial_mismatch": "mismatch",
    }.get(state, "needs_model")


# --------------------------------------------------------------------------- compatibility search


@dataclass
class SearchOutcome:
    candidates: list[CandidateRecord]
    top_score: float
    margin: float
    action: str  # resolve | clarify | needs_staff | mismatch
    selected_part_id: int | None
    note: str
    incompatible_numbers: list[str] = field(default_factory=list)


async def search_item(item: ItemRecord, catalogue: CatalogueContext) -> SearchOutcome:
    if item.configuration_id is None:
        raise PartsIQError("CONFLICT", internal_detail="search requires an identified configuration")
    query = " ".join([*item.part_numbers, item.description]).strip()[:500] or item.description
    response = await catalogue.search.search_parts(
        schemas.PartSearchRequest(configuration_id=item.configuration_id, query=query, limit=5)
    )
    candidates = [
        CandidateRecord(
            part_id=c.part.id,
            part_number=c.part.part_number,
            name_en=c.part.name_en,
            name_ar=c.part.name_ar,
            score=float(c.score),
            reasons=list(c.match_reasons),
            matched_terms=list(c.matched_terms),
            source_reference=c.source_reference,
            superseded_from=list(c.superseded_from),
            quantity_per_unit=float(c.quantity_per_unit),
        )
        for c in response.candidates
    ]
    incompatible = [m.queried_part_number for m in response.part_number_matches if not m.compatible_with_configuration]
    compatible_quoted = [m.current_part.id for m in response.part_number_matches if m.compatible_with_configuration]
    if incompatible and not compatible_quoted:
        return SearchOutcome(
            candidates, response.confidence.top_score, response.confidence.margin, "mismatch", None,
            f"Quoted part {', '.join(incompatible)} is not listed as compatible with this configuration.",
            incompatible,
        )
    if compatible_quoted:
        chosen = compatible_quoted[0]
        note = "Quoted part number is listed as compatible with this configuration."
        if any(m.superseded_chain and len(m.superseded_chain) > 1 for m in response.part_number_matches):
            note = "Quoted part number was superseded; its successor is explicitly listed as compatible."
        return SearchOutcome(candidates, response.confidence.top_score, response.confidence.margin, "resolve", chosen, note)
    decision = decide_ambiguity(
        [c.part_id for c in candidates],
        top_score=response.confidence.top_score,
        margin=response.confidence.margin,
    )
    selected = decision.candidate_part_ids[0] if decision.action == "resolve" else None
    if decision.action == "clarify":
        presented = set(decision.candidate_part_ids)
        candidates = [c for c in candidates if c.part_id in presented] or candidates
    return SearchOutcome(
        candidates, response.confidence.top_score, response.confidence.margin,
        decision.action, selected, decision.explanation,
    )


# --------------------------------------------------------------------------- fulfilment


@dataclass
class PlanOutcome:
    strategy: str
    lines: list[PlanLine]
    shortage: int
    message: str


async def plan_item(item: ItemRecord, record: EnquiryRecord, catalogue: CatalogueContext) -> PlanOutcome:
    if item.selected_part_id is None:
        raise PartsIQError("CONFLICT", internal_detail="plan requires a selected compatible part")
    part = catalogue.part_payload(item.selected_part_id)
    if part is None:
        raise PartsIQError("STALE_CATALOGUE", internal_detail="selected part missing from active version")
    destination = catalogue.warehouse_code(record.destination_warehouse_id)
    if destination is None:
        raise PartsIQError("VALIDATION_FAILED", detail="Unsupported destination warehouse.")
    response = await catalogue.search.plan_fulfilment(
        schemas.FulfilmentRequest(
            part_number=str(part["part_number"]),
            quantity=int(item.quantity),
            destination_warehouse=destination,
        )
    )
    observed = utcnow()
    lines = [
        PlanLine(
            warehouse_code=line.warehouse_code,
            warehouse_id=catalogue.warehouse_id(line.warehouse_code),
            quantity=int(line.quantity),
            transfer_days=int(line.transfer_days),
            observed_at=observed,
        )
        for line in response.lines
        if line.quantity > 0
    ]
    return PlanOutcome(response.strategy, lines, int(response.shortfall), response.message)


# --------------------------------------------------------------------------- facts / verify / reply


def build_facts(record: EnquiryRecord, catalogue: CatalogueContext) -> tuple[VerifiedFacts, VerificationEvidence]:
    """Assemble verified facts (ready items only) and the evidence the gate checks them against."""
    items: list[VerifiedItem] = []
    candidates: list[CandidateEvidence] = []
    stock: dict[tuple[int, int], StockEvidence] = {}
    version = catalogue.version_id
    for item in record.items:
        for cand in item.candidates:
            if item.configuration_id is None:
                continue
            candidates.append(
                CandidateEvidence(
                    item_id=item.id,
                    part_id=cand.part_id,
                    configuration_id=item.configuration_id,
                    evidence_id=evidence_id_for(version, cand.source_reference),
                    source_reference=cand.source_reference,
                )
            )
        if item.status != "ready" or item.selected_part_id is None or item.configuration_id is None:
            continue
        cand = next((c for c in item.candidates if c.part_id == item.selected_part_id), None)
        part = catalogue.part_payload(item.selected_part_id) or {}
        source_reference = cand.source_reference if cand else ""
        items.append(
            VerifiedItem(
                item_id=item.id,
                configuration_id=item.configuration_id,
                part_id=item.selected_part_id,
                part_number=str(part.get("part_number", cand.part_number if cand else "")),
                name_en=str(part.get("name_en", cand.name_en if cand else "")),
                name_ar=str(part.get("name_ar", cand.name_ar if cand else "")),
                requested_quantity=item.quantity,
                allocations=[
                    Allocation(
                        warehouse_id=line.warehouse_id,
                        quantity=Decimal(line.quantity),
                        transfer_days=line.transfer_days,
                        stock_updated_at=line.observed_at,
                    )
                    for line in item.plan_lines
                ],
                shortage=Decimal(item.shortage),
                source_reference=source_reference,
                evidence_id=evidence_id_for(version, source_reference),
            )
        )
        for row in catalogue.stock.observe(item.selected_part_id):
            wid = catalogue.warehouse_id(row.warehouse_code)
            stock[(item.selected_part_id, wid)] = StockEvidence(
                part_id=item.selected_part_id,
                warehouse_id=wid,
                available=Decimal(row.available),
                updated_at=row.observed_at,
            )
    if not items:
        raise PartsIQError("CONFLICT", internal_detail="no ready item to verify")
    facts = VerifiedFacts(
        enquiry_id=record.id,
        revision=record.revision,
        catalogue_version_id=record.catalogue_version_id or version,
        items=items,
    )
    evidence = VerificationEvidence(
        current_revision=record.revision,
        active_catalogue_version_id=version,
        candidates=candidates,
        stock=list(stock.values()),
    )
    return facts, evidence


def verify(record: EnquiryRecord, catalogue: CatalogueContext) -> VerificationResult:
    """Deterministic verification of the current facts against FRESH evidence (no LLM)."""
    if record.facts is None:
        raise PartsIQError("CONFLICT", internal_detail="no facts to verify")
    _fresh_facts, evidence = build_facts(record, catalogue)
    record.evidence = evidence
    return verify_facts(record.facts, evidence)


def fixture_slots(locale: Locale, facts: VerifiedFacts) -> ReplySlots:
    """Code-owned, fact-free prose for fixture mode (no provider call; numbers are rendered later)."""
    short = any(item.shortage > 0 for item in facts.items)
    transfer = any(any(a.transfer_days > 0 for a in item.allocations) for item in facts.items)
    if locale == "ar":
        explanation = "حددنا القطعة المتوافقة مع ماكينتك بناءً على بيانات الكتالوج ومرجع التوافق."
        if transfer:
            explanation += " بعض الكمية تحتاج نقلًا من مستودع آخر، والمدة تقديرية."
        if short:
            explanation += " جزء من الكمية غير متوفر حاليًا وسنبلغك عند توفره."
        return ReplySlots(
            greeting="شكرًا لتواصلك معنا.",
            explanation=explanation,
            closing="راجع أحد موظفينا هذا الاختيار قبل إرساله. نحن جاهزون لأي استفسار.",
        )
    explanation = (
        "We matched a part that is listed as compatible with your machine configuration, "
        "using the catalogue fitment reference shown below."
    )
    if transfer:
        explanation += " Part of the quantity needs a transfer from another warehouse; the timing is an estimate."
    if short:
        explanation += " Some of the quantity is not in stock right now and we will update you."
    return ReplySlots(
        greeting="Thank you for your enquiry.",
        explanation=explanation,
        closing="A member of our team reviewed this selection before it was sent. Reply here if you need anything else.",
    )


def render(record: EnquiryRecord, slots: ReplySlots, catalogue: CatalogueContext | None = None) -> str:
    if record.facts is None:
        raise PartsIQError("CONFLICT", internal_detail="no facts to render")
    names = None
    if catalogue is not None:
        names = {catalogue.warehouse_id(code): catalogue.warehouse_name(catalogue.warehouse_id(code)) for code in catalogue.warehouse_codes}
    return render_reply(slots, record.facts, record.locale, warehouse_names=names)


def new_id() -> UUID:
    return uuid4()
