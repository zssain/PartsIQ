"""F54 Access & permissions facade (helper ``auth.identity``).

Returns the caller's OWN resolved identity: the verified subject id, the server-trusted roles, an
``is_anonymous`` flag (true for a demo caller) and the active demo session id. It is built ENTIRELY
from the verified :class:`ActorContext` — the roles are the DB-sourced roles the token verifier
resolved, never a client-supplied or JWT-claimed role, so a demo caller sees an empty role list
here no matter what the presentational demo UI shows. This is the single place the frontend learns
what the server will actually authorise, which keeps the role gate and the UI honest. It is
read-only and reveals only the caller's own identity. Access is ``customer``.

No backing store is needed — the identity is the actor — so this returns real data offline too.
"""
from __future__ import annotations

from partsiq.core.api_models import IdentityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer


async def identity(actor: ActorContext, *, container: AppContainer) -> IdentityView:
    """Return the caller's own resolved identity and the capabilities the SERVER grants.

    Demo callers report ``kind='demo'`` with an empty role list (their capabilities are scoped to
    their disposable session workspace); accounts report directory-sourced roles. Navigation in
    the frontend is built from ``capabilities`` — hiding a link is never authorization; every
    endpoint re-checks.
    """
    from partsiq.auth.actors import actor_kind, capabilities_for

    kind = actor_kind(actor)
    expires = None
    if kind == "demo" and container.demo_store is not None and hasattr(container.demo_store, "resolve_session"):
        current = await container.demo_store.resolve_session(actor.user_id)
        if current.id == actor.session_id and current.generation == actor.session_generation:
            expires = current.expires_at
    runtime = getattr(container, "runtime", None)
    status = runtime.execution_status() if runtime is not None else {}
    return IdentityView(
        id=actor.user_id,
        roles=list(actor.roles),
        is_anonymous=kind == "demo",
        demo_session_id=actor.session_id if kind == "demo" else None,
        kind=kind,
        display_name=getattr(actor, "display_name", None) or ("Demo visitor" if kind == "demo" else None),
        email=getattr(actor, "email", None),
        capabilities=capabilities_for(actor),
        demo_session_generation=actor.session_generation if kind == "demo" else None,
        demo_expires_at=expires,
        data_source=container.settings.data_source,
        ai_mode=container.settings.ai_mode,
        live_available=bool(status.get("live_available")),
        collaboration_enabled=bool(status.get("collaboration_enabled")),
    )
