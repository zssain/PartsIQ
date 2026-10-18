"""F01 Branded landing — public API metadata facade.

F01 has no privileged endpoint in ``spec/endpoints.json``: the branded landing is a web
concern (``apps/web``). This thin facade exposes the non-privileged, credit-free metadata the
landing page reads so the API side of the feature has one named home. It spends no provider
credits and touches no database.
"""
from __future__ import annotations


def landing_metadata() -> dict[str, str | bool]:
    """Public metadata for the branded landing page. No auth, no credits, no DB."""
    return {"api": "partsiq", "version": "v1", "public": True, "synthetic_demo": True}
