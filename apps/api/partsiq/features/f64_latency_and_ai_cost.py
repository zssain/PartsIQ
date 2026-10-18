"""F64 Latency & AI cost facade (helpers ``ai.read_allowance`` / ``ai.configure_allowance``).

Exposes the manually-confirmed free-credit allowance that gates the live AI path. Two surfaces,
both ADMIN:

  * ``read_allowance`` returns the current allowance view (enabled, confirmed/consumed/reserved
    USD, expiry, model) built by :func:`partsiq.analytics.service.allowance_view`. ``enabled`` is
    true ONLY when a confirmed, unexpired, zero-paid-budget allowance exists — it is NEVER implied
    by the presence of an API key.
  * ``configure_allowance`` records an explicit owner confirmation. The :class:`AllowanceSet` is
    routed through :func:`partsiq.analytics.service.allowance_from_set`, which calls
    ``validate_allowance`` and HARD-BLOCKS a non-zero paid budget, a non-positive amount or an
    already-expired credit (CONSTRAINTS 13/14: no paid fallback). Only after validation does the
    store persist it; the fresh view is returned.

The consumed/reserved figures and persistence are a DB-backed port that is BLOCKED offline, so an
admin gets a clean 503 rather than a fabricated allowance — but an invalid :class:`AllowanceSet`
is rejected BEFORE the store is consulted, so a paid/expired allowance can never be configured.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from partsiq.analytics.service import allowance_from_set, allowance_view
from partsiq.core.api_models import AllowanceSet, AllowanceView
from partsiq.core.contracts import ActorContext, CreditAllowance
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.features._ops_ports import require_store


def require_admin(actor: ActorContext) -> None:
    """Refuse a non-admin caller with FORBIDDEN before any allowance is read or set (403)."""
    if "admin" not in actor.roles:
        raise PartsIQError("FORBIDDEN", internal_detail="AI allowance is admin-only")


@runtime_checkable
class AllowanceSource(Protocol):
    """Admin allowance read/persist port (yields consumed/reserved usage + the stored allowance)."""

    async def read(
        self, actor: ActorContext
    ) -> tuple[CreditAllowance | None, Decimal, Decimal, str | None]:
        """Return ``(allowance, consumed_usd, reserved_usd, model)`` for the current window."""
        ...

    async def persist(
        self, actor: ActorContext, allowance: CreditAllowance, model: str
    ) -> tuple[Decimal, Decimal]:
        """Persist the validated allowance; return the current ``(consumed_usd, reserved_usd)``."""
        ...


async def read_allowance(
    actor: ActorContext,
    *,
    container: AppContainer,
    source: AllowanceSource | None = None,
) -> AllowanceView:
    """Return the current allowance view; ``enabled`` is never implied by an API key (admin-only)."""
    require_admin(actor)
    source = source or require_store(container, "ai_allowance")
    allowance, consumed, reserved, model = await source.read(actor)
    return allowance_view(
        allowance, consumed_usd=consumed, reserved_usd=reserved, model=model
    )


async def configure_allowance(
    actor: ActorContext,
    request: AllowanceSet,
    *,
    container: AppContainer,
    source: AllowanceSource | None = None,
) -> AllowanceView:
    """Record an explicit owner-confirmed allowance (admin-only).

    The request is validated by ``allowance_from_set`` FIRST (no paid fallback, positive amount,
    future expiry) so a paid/expired allowance is rejected before the store is consulted.
    """
    require_admin(actor)
    allowance = allowance_from_set(request)  # hard-blocks paid/non-positive/expired
    source = source or require_store(container, "ai_allowance")
    consumed, reserved = await source.persist(actor, allowance, request.model)
    return allowance_view(
        allowance, consumed_usd=consumed, reserved_usd=reserved, model=request.model
    )
