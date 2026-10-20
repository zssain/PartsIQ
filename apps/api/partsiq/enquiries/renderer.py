"""Code-owned reply renderer (prompt 13 — F45 layout, F27 safe rendering).

Contract: ``def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> str``.

The layout is built HERE in ordinary Python — NOT by the model and NEVER through a
model-authored template; no Jinja (or any template engine) is ever evaluated on model output
(CONSTRAINTS rule 5, prompt 13 step 5). The model's prose only fills greeting / explanation /
closing; every fact line — part identifier, quantity, warehouse, transfer estimate, shortage —
is composed from the verified structured data (prompt 13 step 3).

Safe rendering (F27):
  * ALL text — prose, part names and identifiers alike — is ``html.escape``d before it enters
    the markup, so customer or catalogue HTML can never execute in the dashboard or a PDF.
  * Arabic renders right-to-left (``dir="rtl"``); every identifier/number is wrapped in an
    LTR-isolated ``<bdi dir="ltr">`` so part numbers and warehouse ids read correctly inside
    RTL prose (UI_SPEC: "isolate identifiers with bdi").
  * Transfer times are labelled NON-GUARANTEED estimates (CONSTRAINTS rule 14 — warehouse
    planning is an estimate from a timestamped snapshot).
  * NO price or quotation wording appears anywhere; there is no quotation builder (CONSTRAINTS
    rules 1 and 14).

This function performs no I/O, calls no model and publishes nothing (prompt 13 step 5).
"""
from __future__ import annotations

from decimal import Decimal
from html import escape

from partsiq.core.contracts import Locale, ReplySlots, VerifiedFacts, VerifiedItem

# Bilingual, code-owned labels. Identifiers and numbers are injected around these; no label
# carries price or quotation wording.
_LABELS: dict[Locale, dict[str, str]] = {
    "en": {
        "selection": "Prepared selection",
        "qty": "Qty",
        "warehouse": "Warehouse",
        "estimate": "estimated transfer",
        "day": "day",
        "days": "days",
        "not_guaranteed": "estimate only, not guaranteed",
        "shortage": "Awaiting stock",
    },
    "ar": {
        "selection": "الاختيار المقترح",
        "qty": "الكمية",
        "warehouse": "المستودع",
        "estimate": "مدة النقل المقدرة",
        "day": "يوم",
        "days": "أيام",
        "not_guaranteed": "تقدير فقط وغير مضمون",
        "shortage": "بانتظار توفر المخزون",
    },
}


def _num(value: Decimal) -> str:
    """Render a Decimal as a plain string without trailing zeros (e.g. 2.000 -> '2').

    ``normalize`` on a whole number can yield scientific notation (``1E+1``); the ``f``
    format keeps it as a plain decimal string.
    """
    return format(value.normalize(), "f")


def _ltr(text: str) -> str:
    """Escape an identifier and isolate it left-to-right so it reads correctly inside RTL prose."""
    return f'<bdi dir="ltr">{escape(text)}</bdi>'


def _item_block(item: VerifiedItem, locale: Locale, labels: dict[str, str], warehouse_names: dict[int, str] | None = None) -> str:
    """Compose one item's code-owned fact lines (identifier, name, qty, allocations, shortage)."""
    name = escape(item.name_ar if locale == "ar" else item.name_en)
    lines = [
        f'  <li class="item">{_ltr(item.part_number)} — {name} '
        f'({escape(labels["qty"])}: {_ltr(_num(item.requested_quantity))})'
    ]
    if item.allocations:
        lines.append('    <ul class="allocations">')
        for allocation in item.allocations:
            unit = labels["day"] if allocation.transfer_days == 1 else labels["days"]
            # A catalogue warehouse name (code-owned data) reads better than a numeric id.
            where = (warehouse_names or {}).get(allocation.warehouse_id)
            label = escape(where) if where else f'{escape(labels["warehouse"])} {_ltr(str(allocation.warehouse_id))}'
            lines.append(
                f'      <li>{label}: {_ltr(_num(allocation.quantity))} — '
                f'{escape(labels["estimate"])} {_ltr(str(allocation.transfer_days))} '
                f'{escape(unit)} ({escape(labels["not_guaranteed"])})</li>'
            )
        lines.append("    </ul>")
    if item.shortage > 0:
        lines.append(
            f'    <p class="shortage">{escape(labels["shortage"])}: '
            f'{_ltr(_num(item.shortage))}</p>'
        )
    lines.append("  </li>")
    return "\n".join(lines)


def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale, *, warehouse_names: dict[int, str] | None = None) -> str:
    """Assemble the final customer message: model prose + code-owned fact lines, all escaped.

    The greeting/explanation/closing come from the validated slots (escaped); every number and
    identifier comes from the verified facts and is wrapped in an LTR ``<bdi>``. No model output
    is treated as markup; no price/quotation wording is emitted.
    """
    labels = _LABELS[locale]
    direction = "rtl" if locale == "ar" else "ltr"
    facts_html = "\n".join(_item_block(item, locale, labels, warehouse_names) for item in facts.items)
    return (
        f'<div class="reply" dir="{direction}" lang="{locale}">\n'
        f'  <p class="greeting">{escape(slots.greeting)}</p>\n'
        f'  <p class="explanation">{escape(slots.explanation)}</p>\n'
        f'  <p class="facts-title">{escape(labels["selection"])}:</p>\n'
        f'  <ul class="facts">\n{facts_html}\n  </ul>\n'
        f'  <p class="closing">{escape(slots.closing)}</p>\n'
        f"</div>"
    )
