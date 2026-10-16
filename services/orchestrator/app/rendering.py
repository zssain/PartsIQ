"""Code-owned reply renderer (F45).

Contract: ``def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> str``.

The layout is built here in code — NOT by the model and NEVER through a model-authored
template (no Jinja is evaluated on model output, CONSTRAINTS rule 5). Every fact line
(part identifier, quantity, warehouse, transfer estimate, shortage) is composed from the
verified structured data; the model's prose only fills the greeting/explanation/closing.
All text — prose, names and identifiers alike — is HTML-escaped (F27: user HTML is
escaped). Arabic renders right-to-left with identifiers isolated left-to-right; transfer
times are labelled as non-guaranteed estimates and no price or quotation wording appears
(CONSTRAINTS rule 18).
"""
from __future__ import annotations

from decimal import Decimal
from html import escape

from partsiq_common.contracts import Locale, ReplySlots, VerifiedFacts, VerifiedItem

# Bilingual, code-owned labels. Identifiers and numbers are injected around these.
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
    """Render a Decimal as a plain string without trailing zeros (e.g. 2.000 -> '2')."""
    normalized = value.normalize()
    # Avoid scientific notation for whole numbers like 1E+1.
    return format(normalized, "f")


def _ltr(text: str) -> str:
    """Isolate an identifier left-to-right so it reads correctly inside RTL prose."""
    return f'<bdi dir="ltr">{escape(text)}</bdi>'


def _item_block(item: VerifiedItem, locale: Locale, labels: dict[str, str]) -> str:
    name = escape(item.name_ar if locale == "ar" else item.name_en)
    lines = [
        f'  <li class="item">{_ltr(item.part_number)} — {name} '
        f'({escape(labels["qty"])}: {_num(item.requested_quantity)})'
    ]
    if item.allocations:
        lines.append('    <ul class="allocations">')
        for allocation in item.allocations:
            unit = labels["day"] if allocation.transfer_days == 1 else labels["days"]
            lines.append(
                f'      <li>{escape(labels["warehouse"])} {_ltr(str(allocation.warehouse_id))}: '
                f'{_num(allocation.quantity)} — {escape(labels["estimate"])} '
                f'{allocation.transfer_days} {escape(unit)} '
                f'({escape(labels["not_guaranteed"])})</li>'
            )
        lines.append("    </ul>")
    if item.shortage > 0:
        lines.append(f'    <p class="shortage">{escape(labels["shortage"])}: {_num(item.shortage)}</p>')
    lines.append("  </li>")
    return "\n".join(lines)


def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> str:
    """Assemble the final customer message: model prose + code-owned fact lines, all escaped."""
    labels = _LABELS[locale]
    direction = "rtl" if locale == "ar" else "ltr"
    facts_html = "\n".join(_item_block(item, locale, labels) for item in facts.items)
    return (
        f'<div class="reply" dir="{direction}" lang="{locale}">\n'
        f'  <p class="greeting">{escape(slots.greeting)}</p>\n'
        f'  <p class="explanation">{escape(slots.explanation)}</p>\n'
        f'  <p class="facts-title">{escape(labels["selection"])}:</p>\n'
        f'  <ul class="facts">\n{facts_html}\n  </ul>\n'
        f'  <p class="closing">{escape(slots.closing)}</p>\n'
        f"</div>"
    )
