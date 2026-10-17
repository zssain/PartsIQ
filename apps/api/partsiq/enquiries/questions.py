"""Code-owned bilingual clarifying questions (F11) and the ambiguity decision (F26).

Two deterministic, side-effect-free surfaces, ported from the legacy orchestrator parts
specialist (``services/orchestrator/app/specialists/parts.py``) and its feature tests
(``tests/features/test_f11.py``, ``test_f26.py``):

``clarification(reason, locale)`` renders the question text for a reason code. The prose is
CODE-OWNED: the identifiers and the full bilingual strings live here, never authored by a
model. A clarifying question makes no final part recommendation, so it never requires staff
approval (WORKFLOW.md "User changes"); but it is still fixed prose, not provider output.

``decide_ambiguity(...)`` is the F26 gate. Given a compatible-only candidate set plus its
code-computed top score and runner-up margin, it returns a typed :class:`AmbiguityDecision`
whose action is one of ``resolve`` (a single confident candidate), ``clarify`` (ask the
customer to distinguish between close candidates) or ``needs_staff`` (no compatible candidate
at all). An LLM can NEVER turn a low-confidence or close set into a confident answer, and a
close/ambiguous set is never silently auto-picked (CONSTRAINTS: close candidates -> questions
/ review, never a guess). Thresholds are the tested constants mirrored from the search
identification/ranking code; they are evaluated here in ordinary Python.

``validate_selection(...)`` enforces that a customer/staff choice is one of the current
compatible candidates; an unavailable choice raises a 409 CONFLICT (F26), it is never
coerced into the candidate set.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from partsiq.core.contracts import Locale
from partsiq.core.errors import PartsIQError

# ---------------------------------------------------------------------------
# Tested thresholds — mirror the search identification/ranking constants so the
# ambiguity decision uses exactly the same code-owned score/margin rules the
# ranked set was built with. No model participates in these comparisons.
# ---------------------------------------------------------------------------
RESOLVE_MIN_SCORE = 0.5
AMBIGUITY_MARGIN = 0.05
MAX_PRESENTED = 3

#: The reason codes a clarifying question can be built for. These match the
#: ``PartsProposal.clarification_code`` vocabulary plus the identification states that drive a
#: question before search can run. ``none`` is included so a caller can ask for the (empty)
#: text of a non-question outcome without a KeyError.
ClarificationReason = Literal[
    "needs_serial",
    "needs_model",
    "ambiguous_part",
    "ambiguous_model",
    "mismatch",
    "none",
]

# ---------------------------------------------------------------------------
# Bilingual, code-owned question text. One identifier -> one (en, ar) pair. The
# strings are fixed prose; they state what to ask and never assert a chosen part.
# ---------------------------------------------------------------------------
_QUESTIONS: dict[str, tuple[str, str]] = {
    "needs_model": (
        "We could not identify the machine yet. Please tell us the model shown on the "
        "nameplate.",
        "لم نتمكن من تحديد الماكينة بعد. من فضلك أخبرنا بالموديل المكتوب على لوحة الصنع.",
    ),
    "needs_serial": (
        "This model has more than one configuration that take different parts. Please send "
        "the serial number from the nameplate so we can match the exact part.",
        "هذا الموديل له أكثر من تكوين يستخدم قطعًا مختلفة. من فضلك أرسل الرقم التسلسلي من "
        "لوحة الصنع حتى نطابق القطعة بدقة.",
    ),
    "ambiguous_model": (
        "Several machine models match your description. Please confirm the exact model from "
        "the nameplate.",
        "هناك عدة موديلات تطابق وصفك. من فضلك أكّد الموديل الدقيق من لوحة الصنع.",
    ),
    "ambiguous_part": (
        "More than one compatible part closely matches your request. Please tell us which "
        "one you need so we do not guess.",
        "أكثر من قطعة متوافقة تطابق طلبك عن قرب. من فضلك أخبرنا بأيّها تحتاج حتى لا نخمّن.",
    ),
    "mismatch": (
        "The part number you gave does not fit the machine we identified. Please re-check the "
        "nameplate or the part number so we can confirm the correct part.",
        "رقم القطعة الذي أرسلته لا يناسب الماكينة التي حدّدناها. من فضلك راجع لوحة الصنع أو رقم "
        "القطعة حتى نؤكّد القطعة الصحيحة.",
    ),
    "none": ("", ""),
}


def clarification(reason: str, locale: Locale) -> str:
    """Return the bilingual-selected, code-owned question text for a reason code.

    ``reason`` is a code the deterministic pipeline produced (a
    :class:`~partsiq.core.contracts.PartsProposal.clarification_code` or an identification
    state); ``locale`` selects the language. An unknown reason falls back to the generic
    model request rather than echoing an un-templated string, so prose is never model-authored.
    The text asks a question; it never states a final recommendation and so needs no approval.
    """
    en, ar = _QUESTIONS.get(reason, _QUESTIONS["needs_model"])
    return ar if locale == "ar" else en


def clarification_pair(reason: str) -> tuple[str, str]:
    """Return the ``(question_en, question_ar)`` pair for a reason code (both languages)."""
    return _QUESTIONS.get(reason, _QUESTIONS["needs_model"])


# ---------------------------------------------------------------------------
# F26 ambiguity decision — close/ambiguous candidates become a question or staff
# review, NEVER an auto-pick.
# ---------------------------------------------------------------------------
AmbiguityAction = Literal["resolve", "clarify", "needs_staff"]


@dataclass(frozen=True, slots=True)
class AmbiguityDecision:
    """The code-decided outcome of ranking a compatible-only candidate set (F26).

    ``action`` is ``resolve`` (one confident candidate -> ``candidate_part_ids`` has exactly
    one id), ``clarify`` (close/low-confidence set -> ask, carrying the top candidates to
    present) or ``needs_staff`` (no compatible candidate). ``clarification_code`` is the
    code-owned reason the question/handoff uses; it is ``none`` when ``resolve``.
    """

    action: AmbiguityAction
    clarification_code: ClarificationReason
    candidate_part_ids: list[int]
    explanation: str


def decide_ambiguity(
    candidate_part_ids: list[int],
    *,
    top_score: float,
    margin: float,
) -> AmbiguityDecision:
    """Decide resolve / clarify / needs_staff from the compatible set and code thresholds.

    The candidate ids MUST already be the compatible-only, score-ranked set (the compatibility
    gate lives upstream in the search service and is never re-opened here). A low absolute
    confidence OR a close runner-up margin forces a clarifying question — a model can never
    override either into a confident answer (F26). An empty set is handed to staff; it is never
    reported as a confident single pick.
    """
    if not candidate_part_ids:
        return AmbiguityDecision(
            action="needs_staff",
            clarification_code="none",
            candidate_part_ids=[],
            explanation="No compatible part was found for this machine configuration.",
        )

    low_confidence = top_score < RESOLVE_MIN_SCORE
    ambiguous = len(candidate_part_ids) > 1 and margin < AMBIGUITY_MARGIN
    if low_confidence or ambiguous:
        return AmbiguityDecision(
            action="clarify",
            clarification_code="ambiguous_part",
            candidate_part_ids=candidate_part_ids[:MAX_PRESENTED],
            explanation="Multiple compatible parts match closely; please distinguish between them.",
        )

    return AmbiguityDecision(
        action="resolve",
        clarification_code="none",
        candidate_part_ids=candidate_part_ids[:1],
        explanation="Identified a single compatible part with high confidence.",
    )


def validate_selection(candidate_part_ids: list[int], chosen_part_id: int) -> None:
    """A customer/staff choice must be one of the CURRENT compatible candidates, else 409 (F26).

    An unavailable choice is surfaced as a CONFLICT (409), never coerced into the candidate set
    or silently accepted. Mirrors the legacy ``parts.validate_selection``.
    """
    if chosen_part_id not in candidate_part_ids:
        raise PartsIQError(
            "CONFLICT",
            detail="The selected part is not one of the current compatible candidates.",
            internal_detail=f"part {chosen_part_id} is not an available candidate",
        )
