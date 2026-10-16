"""Parts specialist.

Contract: ``async def run_parts(item: ItemState, context: ToolContext) -> PartsProposal``.

Deterministic code owns the decision: candidate part ids come ONLY from the search
service's compatible result set (the LLM can never introduce an incompatible part or
change a quantity), and the clarification code is chosen by tested score/margin
thresholds — an LLM cannot override low confidence (F26). The LLM's role is limited to
phrasing the explanation; the authoritative fields here are code-decided.
"""
from __future__ import annotations

from app.tools import ToolSession
from partsiq_common.contracts import ItemState, PartsProposal, ToolContext

# Tested thresholds (mirror the search service's identification/ranking constants).
RESOLVE_MIN_SCORE = 0.5
AMBIGUITY_MARGIN = 0.05
MAX_PRESENTED = 3


async def run_parts(item: ItemState, context: ToolContext, *, session: ToolSession) -> PartsProposal:
    # The machine must be identified before parts can be retrieved (handled by the
    # IDENTIFY step; if we arrive without a configuration, ask rather than guess).
    if item.configuration_id is None:
        return PartsProposal(
            explanation="The machine is not yet identified; ask for the model or serial.",
            clarification_code="needs_model",
            candidate_part_ids=[],
        )

    result = await session.search_parts(item.configuration_id, item.request.description)
    compatible_ids = [candidate.part_id for candidate in result.candidates]

    if not compatible_ids:
        return PartsProposal(
            explanation="No compatible part was found for this machine configuration.",
            clarification_code="none",
            candidate_part_ids=[],
        )

    # Low absolute confidence OR a close runner-up => ask the customer to distinguish.
    low_confidence = result.top_score < RESOLVE_MIN_SCORE
    ambiguous = len(result.candidates) > 1 and result.margin < AMBIGUITY_MARGIN
    if low_confidence or ambiguous:
        return PartsProposal(
            explanation="Multiple compatible parts match closely; please distinguish between them.",
            clarification_code="ambiguous_part",
            candidate_part_ids=compatible_ids[:MAX_PRESENTED],
        )

    return PartsProposal(
        explanation="Identified a single compatible part with high confidence.",
        clarification_code="none",
        candidate_part_ids=compatible_ids[:1],
    )


def validate_selection(candidate_part_ids: list[int], chosen_part_id: int) -> None:
    """A staff/customer choice must be one of the verified candidates; else 409 (F26)."""
    if chosen_part_id not in candidate_part_ids:
        raise _conflict()


def _conflict():
    from partsiq_common.errors import PartsIQError

    return PartsIQError("CONFLICT", internal_detail="selected part is not an available candidate")
