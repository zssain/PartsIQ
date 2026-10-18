"""F02 Demo scenarios facade (helper ``demo.list_scenarios``).

Returns the four seed-42 demo scenarios as a :class:`ScenarioList`. Access is ``demo`` — any
caller with an active demo session (the anonymous demo actor) may list them. The scenarios are
synthetic by construction (derived from the committed seed-42 catalogue) and never reveal real
inventory.
"""
from __future__ import annotations

from partsiq.core.api_models import ScenarioList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, load_fixture_scenarios
from partsiq.core.errors import PartsIQError


def list_scenarios(actor: ActorContext, *, container: AppContainer) -> ScenarioList:
    """List the demo scenarios the UI can replay. Requires a demo identity; synthetic data only."""
    # A verified actor is always present (require_actor ran); demo access needs no role.
    _ = actor
    if not container.is_fixture:
        # Scenarios are a fixture-only concern; a live deployment seeds them from its catalogue
        # loader, which is not wired in this environment.
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="demo scenarios require fixture catalogue (not configured)",
        )
    return load_fixture_scenarios()
