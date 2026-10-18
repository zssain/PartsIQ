"""Shared 503-or-store accessor for the ops/convenience feature facades (F38-F67).

Every one of these facades is a THIN adapter over a DB/provider-backed port that the owner wires
onto the container in production and that is deliberately NOT wired in this fixture/offline
environment (the in-memory journey store tracks only the customer intake path, never a reviewer
correction, a durable workflow run, a job, a catalogue import/version, an eval run or a metrics
query). So a facade resolves its backing store through :func:`require_store`, which mirrors
:func:`partsiq.features.f36_staff_inbox.require_staff_review`: it returns the injected store when
present and otherwise raises a CLEAN, retryable 503 — a staff/admin/owner route therefore surfaces
``DEPENDENCY_UNAVAILABLE`` rather than ever fabricating a decision, a job, a catalogue version or a
figure. Unit tests inject a deterministic fake for ``source`` and never touch this path.
"""
from __future__ import annotations

from typing import TypeVar

from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError

_StoreT = TypeVar("_StoreT")


def require_store(container: AppContainer, attr: str) -> object:
    """Return ``container.<attr>`` or raise a clean 503 when that store is not configured.

    The returned value is the owner-wired adapter; in this environment it is ``None`` for every
    DB/provider-backed port, so a retryable ``DEPENDENCY_UNAVAILABLE`` is surfaced — never a
    fabricated result.
    """
    source = getattr(container, attr, None)
    if source is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail=f"the {attr} store is not configured in this environment",
        )
    return source
