"""Verified actor kinds and the server-side capability model (ADR 0002).

Two kinds of verified caller reach the API:

* :class:`DemoActorContext` — an anonymous public-demo visitor identified by an opaque
  ``X-Demo-Token``. It ALWAYS carries an empty role list. Its authority is limited to its own
  disposable, session-scoped synthetic workspace; inside that sandbox it may preview the
  customer, reviewer and administrator experiences because nothing it touches is shared.
* :class:`AccountActorContext` — an invited account whose subject comes from a verified Supabase
  access token. Its staff roles come from the server-side role directory (never token claims).

Every capability decision goes through :func:`capabilities_for`/:func:`require_capability`, so a
client-side role selector can never widen what the server allows. The capability names are the
single vocabulary the frontend receives from ``GET /v1/me`` to build navigation; hiding a link is
not authorization — every endpoint re-checks here.
"""
from __future__ import annotations

from typing import Literal

from partsiq.core.contracts import ActorContext
from partsiq.core.errors import PartsIQError

ActorKind = Literal["demo", "account"]


class DemoActorContext(ActorContext):
    """Anonymous public-demo caller. Roles are always empty (see module docstring)."""

    kind: Literal["demo"] = "demo"


class AccountActorContext(ActorContext):
    """A Supabase-authenticated invited account with directory-sourced staff roles."""

    kind: Literal["account"] = "account"
    email: str | None = None
    display_name: str | None = None


def actor_kind(actor: ActorContext) -> ActorKind:
    """Classify an actor. A bare :class:`ActorContext` (unit tests, internal calls) is an account."""
    return "demo" if isinstance(actor, DemoActorContext) else "account"


# Capability vocabulary. Customer capabilities are held by every verified caller; staff ones map
# from the existing role model (``reviewer``/``catalogue_admin``/``admin``) — there is no separate
# "reviewer" grant beyond the existing role plus per-enquiry assignment.
CUSTOMER_CAPS: tuple[str, ...] = (
    "enquiry.create",
    "enquiry.read_own",
    "machines.manage_own",
    "run.control_own",
)
REVIEWER_CAPS: tuple[str, ...] = (
    "review.queue",
    "review.decide",
    "run.control_assigned",
    "catalogue.browse",
)
CATALOGUE_ADMIN_CAPS: tuple[str, ...] = (
    "catalogue.browse",
    "catalogue.import",
    "catalogue.publish",
)
ADMIN_CAPS: tuple[str, ...] = (
    "review.queue",
    "review.decide",
    "review.all",
    "run.control_all",
    "admin.users",
    "admin.assign",
    "catalogue.browse",
    "catalogue.import",
    "catalogue.publish",
    "analytics.read",
    "audit.read",
    "jobs.read",
    "jobs.retry",
    "evaluation.run",
)

# Capabilities that act on shared, real (non-sandbox) configuration. A demo actor never gets
# these even inside its sandbox (e.g. the owner's confirmed AI allowance).
REAL_ONLY_CAPS: frozenset[str] = frozenset({"ai.allowance"})


def _ordered(*groups: tuple[str, ...]) -> list[str]:
    seen: dict[str, None] = {}
    for group in groups:
        for cap in group:
            seen.setdefault(cap, None)
    return list(seen)


def capabilities_for(actor: ActorContext) -> list[str]:
    """Return the capabilities the SERVER grants ``actor`` (sorted, stable order).

    Demo: the full sandbox set, but scoped by construction to the caller's own session workspace.
    Account: customer capabilities plus the union implied by its directory-sourced roles.
    """
    if actor_kind(actor) == "demo":
        return _ordered(CUSTOMER_CAPS, REVIEWER_CAPS, CATALOGUE_ADMIN_CAPS, ADMIN_CAPS)
    groups: list[tuple[str, ...]] = [CUSTOMER_CAPS]
    if "reviewer" in actor.roles:
        groups.append(REVIEWER_CAPS)
    if "catalogue_admin" in actor.roles:
        groups.append(CATALOGUE_ADMIN_CAPS)
    if "admin" in actor.roles:
        groups.append(ADMIN_CAPS)
        groups.append(tuple(sorted(REAL_ONLY_CAPS)))
    return _ordered(*groups)


def has_capability(actor: ActorContext, capability: str) -> bool:
    return capability in capabilities_for(actor)


def require_capability(actor: ActorContext, capability: str) -> None:
    """Refuse with FORBIDDEN (403) unless the server grants ``capability`` to ``actor``.

    The refusal reveals nothing about any specific resource; resource scoping (ownership,
    assignment, demo session) is still checked separately and reports foreign ids as 404.
    """
    if not has_capability(actor, capability):
        raise PartsIQError("FORBIDDEN", internal_detail=f"capability {capability} required")
